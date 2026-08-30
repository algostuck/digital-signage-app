"""Layout engine service (FR-LYT-001..008)."""

import logging
import uuid

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BusinessRuleError, ConflictError, NotFoundError, ValidationAppError
from app.models import Layout, LayoutVersion, LayoutZone, Template
from app.models.content import ProcessingStatus
from app.models.layout import LayoutStatus
from app.repositories import content as content_repo
from app.repositories import layouts as repo
from app.schemas.canvas import LayoutCanvas, default_canvas
from app.services.content import current_version as asset_current_version

logger = logging.getLogger("app.layouts")


def parse_canvas(raw: dict) -> LayoutCanvas:
    """Structural validation of a canvas document (FR-LYT-002/003/004)."""
    try:
        return LayoutCanvas.model_validate(raw)
    except ValidationError as exc:
        first = exc.errors()[0]
        location = ".".join(str(part) for part in first["loc"])
        raise ValidationAppError(
            f"Invalid layout canvas at '{location}': {first['msg']}", field="canvas_json"
        ) from exc


async def validate_asset_bindings(
    db: AsyncSession, organization_id: uuid.UUID, canvas: LayoutCanvas
) -> None:
    """Publish-time referential validation: bound assets must exist in this
    tenant and have a READY current version (FR-LYT-005)."""
    for raw_id in canvas.referenced_asset_ids():
        try:
            asset_id = uuid.UUID(raw_id)
        except ValueError as exc:
            raise ValidationAppError(
                f"Zone content_config.asset_id '{raw_id}' is not a valid id",
                field="canvas_json",
            ) from exc
        asset = await content_repo.get_asset(db, organization_id, asset_id)
        if asset is None:
            raise BusinessRuleError(f"Bound asset {raw_id} does not exist")
        version = asset_current_version(asset)
        if version is None or version.processing_status != ProcessingStatus.READY.value:
            raise BusinessRuleError(f"Bound asset '{asset.name}' is not READY")


async def get_layout(
    db: AsyncSession, organization_id: uuid.UUID, layout_id: uuid.UUID
) -> Layout:
    layout = await repo.get_by_id(db, organization_id, layout_id)
    if layout is None:
        raise NotFoundError("Layout not found")
    return layout


async def create_layout(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    name: str,
    description: str | None,
    canvas_width: int,
    canvas_height: int,
    template_id: uuid.UUID | None,
) -> Layout:
    if template_id is not None:
        template = await repo.get_template(db, organization_id, template_id)
        if template is None:
            raise NotFoundError("Template not found")
        canvas = parse_canvas(template_canvas(template)).model_dump()
    else:
        canvas = default_canvas(canvas_width, canvas_height)
    layout = Layout(
        organization_id=organization_id,
        name=name,
        description=description,
        status=LayoutStatus.DRAFT.value,
        draft_canvas_json=canvas,
    )
    db.add(layout)
    await db.flush()
    await db.refresh(layout, ["versions"])
    logger.info("Layout %s created", layout.id)
    return layout


async def update_layout(
    db: AsyncSession,
    organization_id: uuid.UUID,
    layout_id: uuid.UUID,
    *,
    name: str | None = None,
    description: str | None = None,
    canvas_json: dict | None = None,
) -> Layout:
    layout = await get_layout(db, organization_id, layout_id)
    if layout.status == LayoutStatus.ARCHIVED.value:
        raise BusinessRuleError("Restore the layout before editing")
    if name is not None:
        layout.name = name
    if description is not None:
        layout.description = description
    if canvas_json is not None:
        layout.draft_canvas_json = parse_canvas(canvas_json).model_dump()
    await db.flush()
    return layout


async def preview_layout(
    db: AsyncSession, organization_id: uuid.UUID, layout_id: uuid.UUID
) -> dict:
    """Validation preflight (FR-LYT-006): normalized draft canvas + binding
    check, without creating a version."""
    layout = await get_layout(db, organization_id, layout_id)
    canvas = parse_canvas(layout.draft_canvas_json)
    await validate_asset_bindings(db, organization_id, canvas)
    return canvas.model_dump()


async def publish_layout(
    db: AsyncSession, organization_id: uuid.UUID, layout_id: uuid.UUID
) -> Layout:
    """Snapshots the draft into an immutable version (FR-LYT-007)."""
    layout = await get_layout(db, organization_id, layout_id)
    if layout.status == LayoutStatus.ARCHIVED.value:
        raise BusinessRuleError("Restore the layout before publishing")
    canvas = parse_canvas(layout.draft_canvas_json)
    if not canvas.zones:
        raise BusinessRuleError("A layout needs at least one zone to be published")
    await validate_asset_bindings(db, organization_id, canvas)

    version_no = (layout.versions[-1].version_no + 1) if layout.versions else 1
    version = LayoutVersion(
        layout_id=layout.id, version_no=version_no, canvas_json=canvas.model_dump()
    )
    version.zones = [
        LayoutZone(zone_key=zone.key, zone_json=zone.model_dump()) for zone in canvas.zones
    ]
    db.add(version)
    await db.flush()

    layout.current_version_id = version.id
    layout.status = LayoutStatus.PUBLISHED.value
    await db.flush()
    await db.refresh(layout, ["versions"])
    from app.services import audit

    await audit.record(
        db, organization_id, action="LAYOUT_PUBLISHED", entity_type="layout",
        entity_id=layout.id, after={"version": version_no},
    )
    logger.info("Layout %s published as v%s", layout.id, version_no)
    return layout


async def archive_layout(
    db: AsyncSession, organization_id: uuid.UUID, layout_id: uuid.UUID
) -> Layout:
    layout = await get_layout(db, organization_id, layout_id)
    layout.status = LayoutStatus.ARCHIVED.value
    await db.flush()
    return layout


async def restore_layout(
    db: AsyncSession, organization_id: uuid.UUID, layout_id: uuid.UUID
) -> Layout:
    layout = await get_layout(db, organization_id, layout_id)
    if layout.status == LayoutStatus.ARCHIVED.value:
        layout.status = (
            LayoutStatus.PUBLISHED.value if layout.current_version_id else LayoutStatus.DRAFT.value
        )
        await db.flush()
    return layout


# --- templates ---


def template_canvas(template: Template) -> dict:
    """Consumers (clone, layout-from-template) get the approved snapshot
    when one exists; the editable draft otherwise (P2-CNT-001)."""
    if template.current_version_id:
        for version in template.versions:
            if version.id == template.current_version_id:
                return version.canvas_json
    return template.canvas_json


async def create_template(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    layout_id: uuid.UUID | None,
    name: str,
    description: str | None,
    canvas_width: int = 1920,
    canvas_height: int = 1080,
) -> Template:
    if await repo.get_template_by_name(db, organization_id, name):
        raise ConflictError("A template with this name already exists", field="name")
    if layout_id is not None:
        layout = await get_layout(db, organization_id, layout_id)
        canvas = parse_canvas(layout.draft_canvas_json).model_dump()
    else:
        canvas = default_canvas(canvas_width, canvas_height)
    template = Template(
        organization_id=organization_id,
        layout_id=layout_id,
        name=name,
        description=description,
        canvas_json=canvas,
    )
    db.add(template)
    await db.flush()
    await db.refresh(template, ["versions"])
    return template


async def clone_template(
    db: AsyncSession, organization_id: uuid.UUID, template_id: uuid.UUID, *, name: str
) -> Layout:
    template = await repo.get_template(db, organization_id, template_id)
    if template is None:
        raise NotFoundError("Template not found")
    layout = Layout(
        organization_id=organization_id,
        name=name,
        description=template.description,
        status=LayoutStatus.DRAFT.value,
        draft_canvas_json=parse_canvas(template_canvas(template)).model_dump(),
    )
    db.add(layout)
    await db.flush()
    await db.refresh(layout, ["versions"])
    logger.info("Layout %s cloned from template %s", layout.id, template_id)
    return layout


async def seed_default_templates(db: AsyncSession, organization_id: uuid.UUID) -> None:
    """Idempotent starter templates (fullscreen / split / split + ticker)."""
    from app.schemas.canvas import CanvasDef, ZoneDef

    def canvas(zones: list[ZoneDef]) -> dict:
        return LayoutCanvas(canvas=CanvasDef(width=1920, height=1080), zones=zones).model_dump()

    presets = {
        "Fullscreen": canvas([ZoneDef(key="main", name="Main", x=0, y=0, width=1920, height=1080)]),
        "Two Zone Split": canvas(
            [
                ZoneDef(key="left", name="Left", x=0, y=0, width=960, height=1080),
                ZoneDef(key="right", name="Right", x=960, y=0, width=960, height=1080),
            ]
        ),
        "Media with Ticker": canvas(
            [
                ZoneDef(key="main", name="Main", x=0, y=0, width=1920, height=960),
                ZoneDef(
                    key="ticker",
                    name="Ticker",
                    x=0,
                    y=960,
                    width=1920,
                    height=120,
                    content_type="ticker",
                    content_config={"text": "Welcome", "speed": 60},
                ),
            ]
        ),
    }
    for name, canvas_json in presets.items():
        if await repo.get_template_by_name(db, organization_id, name) is None:
            db.add(
                Template(
                    organization_id=organization_id,
                    name=name,
                    description="Starter template",
                    canvas_json=canvas_json,
                )
            )
    await db.flush()
