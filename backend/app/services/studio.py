"""Content studio (P2-M02): template versioning + governance, widget
framework with schema-driven config, dynamic data bindings and asset
collections.

Templates reuse the Phase-1 `templates` table: `canvas_json` stays the
editable draft, and approval (through the 2A engine, entity type
"template") snapshots it into an immutable TemplateVersion — the same
draft→immutable-version pattern layouts and playlists use.
"""

import logging
import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import (
    BusinessRuleError,
    ConflictError,
    NotFoundError,
    ValidationAppError,
)
from app.models import (
    AssetCollection,
    AssetCollectionItem,
    Template,
    TemplateVersion,
    Widget,
    WidgetVersion,
)
from app.models.layout import TemplateStatus
from app.models.studio import WidgetStatus
from app.repositories import content as content_repo
from app.repositories import layouts as layouts_repo
from app.services import approvals

logger = logging.getLogger("app.studio")

# --- data variables (P2-CNT-002): the approved binding catalogue ---

DATA_VARIABLES: dict[str, str] = {
    "date": "Current date (device-local)",
    "time": "Current time (device-local)",
    "datetime": "Current date and time",
    "device.name": "Device name",
    "device.location": "Assigned location name",
    "org.name": "Organization name",
    "weather.temp": "Temperature at the device location",
    "weather.condition": "Weather condition at the device location",
}

_BINDING_TOKEN = re.compile(r"\{\{\s*([a-z][a-z0-9_.]*)\s*\}\}")

WIDGET_FIELD_TYPES = ("string", "number", "boolean", "select", "url", "color")
_FIELD_KEY = re.compile(r"^[a-z][a-z0-9_]{0,49}$")
MAX_SCHEMA_FIELDS = 30


# --- widget schema (P2-CNT-003) ---


def validate_widget_schema(schema: dict) -> dict:
    """Field-list schema shared by the server validator and the frontend
    form renderer: {"fields": [{key, label, type, required?, options?,
    default?}]}."""
    if not isinstance(schema, dict) or not isinstance(schema.get("fields"), list):
        raise ValidationAppError(
            "config_schema_json must be {'fields': [...]}", field="config_schema_json"
        )
    fields = schema["fields"]
    if not fields or len(fields) > MAX_SCHEMA_FIELDS:
        raise ValidationAppError(
            f"Schema needs 1..{MAX_SCHEMA_FIELDS} fields", field="config_schema_json"
        )
    seen: set[str] = set()
    for field in fields:
        key = field.get("key")
        if not isinstance(key, str) or not _FIELD_KEY.match(key):
            raise ValidationAppError(
                f"Invalid field key '{key}'", field="config_schema_json"
            )
        if key in seen:
            raise ValidationAppError(
                f"Duplicate field key '{key}'", field="config_schema_json"
            )
        seen.add(key)
        if field.get("type") not in WIDGET_FIELD_TYPES:
            raise ValidationAppError(
                f"Field '{key}' has unknown type '{field.get('type')}'",
                field="config_schema_json",
            )
        if field["type"] == "select":
            options = field.get("options")
            if not isinstance(options, list) or not options:
                raise ValidationAppError(
                    f"Select field '{key}' needs options", field="config_schema_json"
                )
    return {"fields": fields}


def validate_widget_config(schema: dict, config: dict) -> None:
    fields = {f["key"]: f for f in schema.get("fields", [])}
    if not isinstance(config, dict):
        raise ValidationAppError("Widget config must be an object")
    for key in config:
        if key not in fields:
            raise ValidationAppError(f"Unknown widget config key '{key}'")
    for key, field in fields.items():
        value = config.get(key, field.get("default"))
        if value is None:
            if field.get("required"):
                raise ValidationAppError(f"Widget config '{key}' is required")
            continue
        kind = field["type"]
        if kind == "number" and not isinstance(value, int | float):
            raise ValidationAppError(f"Widget config '{key}' must be a number")
        if kind == "boolean" and not isinstance(value, bool):
            raise ValidationAppError(f"Widget config '{key}' must be a boolean")
        if kind in ("string", "url", "color") and not isinstance(value, str):
            raise ValidationAppError(f"Widget config '{key}' must be a string")
        if kind == "select" and value not in field.get("options", []):
            raise ValidationAppError(
                f"Widget config '{key}' must be one of {field.get('options')}"
            )


def validate_bindings(bindings: dict) -> None:
    """Every {{token}} must come from the approved variable catalogue."""
    if not isinstance(bindings, dict):
        raise ValidationAppError("Zone bindings must be an object")
    for prop, expression in bindings.items():
        if not isinstance(expression, str):
            raise ValidationAppError(f"Binding '{prop}' must be a string template")
        for token in _BINDING_TOKEN.findall(expression):
            if token not in DATA_VARIABLES:
                raise ValidationAppError(
                    f"Binding '{prop}' references unknown variable '{token}'"
                )


async def validate_canvas_widgets(
    db: AsyncSession, organization_id: uuid.UUID, canvas: dict
) -> None:
    """Zones may carry {"widget": {widget_id, config?, bindings?}}. Zones
    without widget refs (all Phase-1 content) validate trivially."""
    for zone in canvas.get("zones", []):
        ref = zone.get("widget")
        if ref is None:
            continue
        if not isinstance(ref, dict) or not ref.get("widget_id"):
            raise ValidationAppError("zone.widget needs a widget_id")
        try:
            widget_id = uuid.UUID(str(ref["widget_id"]))
        except ValueError as exc:
            raise ValidationAppError("zone.widget.widget_id must be a UUID") from exc
        widget = await get_widget(db, organization_id, widget_id)
        if widget.status != WidgetStatus.ACTIVE.value:
            raise BusinessRuleError(f"Widget '{widget.name}' is archived")
        current = widget.versions[-1]
        validate_widget_config(current.config_schema_json, ref.get("config") or {})
        validate_bindings(ref.get("bindings") or {})

        # Dynamic data binding (P3 3A-2): {source_id, transform?} — the
        # source must exist in this tenant, the transform must be the safe
        # declarative spec (never code).
        data_binding = ref.get("data_binding")
        if data_binding is not None:
            from app.services import data_sources as data_sources_service

            if not isinstance(data_binding, dict) or not data_binding.get("source_id"):
                raise ValidationAppError("zone.widget.data_binding needs a source_id")
            try:
                source_id = uuid.UUID(str(data_binding["source_id"]))
            except ValueError as exc:
                raise ValidationAppError(
                    "zone.widget.data_binding.source_id must be a UUID"
                ) from exc
            await data_sources_service.get_source(db, organization_id, source_id)
            if data_binding.get("transform") is not None:
                data_sources_service.validate_transform(data_binding["transform"])


# --- widgets ---


async def get_widget(
    db: AsyncSession, organization_id: uuid.UUID, widget_id: uuid.UUID
) -> Widget:
    widget = (
        await db.execute(
            select(Widget).where(
                Widget.organization_id == organization_id, Widget.id == widget_id
            )
        )
    ).scalar_one_or_none()
    if widget is None:
        raise NotFoundError("Widget not found")
    return widget


async def list_widgets(db: AsyncSession, organization_id: uuid.UUID) -> list[Widget]:
    rows = await db.execute(
        select(Widget)
        .where(Widget.organization_id == organization_id)
        .order_by(Widget.name)
    )
    return list(rows.scalars().all())


async def create_widget(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    type: str,
    name: str,
    config_schema: dict,
    defaults: dict | None,
    fallback: dict | None,
) -> Widget:
    existing = await db.execute(
        select(Widget.id).where(
            Widget.organization_id == organization_id, Widget.name == name
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise ConflictError("A widget with this name already exists", field="name")
    schema = validate_widget_schema(config_schema)
    if defaults:
        validate_widget_config(schema, defaults)
    widget = Widget(
        id=uuid.uuid4(),
        organization_id=organization_id,
        type=type,
        name=name,
        fallback_json=fallback,
    )
    db.add(widget)
    db.add(
        WidgetVersion(
            widget_id=widget.id,
            version_no=1,
            config_schema_json=schema,
            defaults_json=defaults,
        )
    )
    await db.flush()
    await db.refresh(widget, ["versions"])

    from app.services import audit

    await audit.record(
        db,
        organization_id,
        action="WIDGET_CREATED",
        entity_type="widget",
        entity_id=widget.id,
        after={"name": name, "type": type},
    )
    return widget


async def update_widget(
    db: AsyncSession,
    organization_id: uuid.UUID,
    widget_id: uuid.UUID,
    *,
    name: str | None,
    status: str | None,
    fallback: dict | None,
    clear_fallback: bool,
) -> Widget:
    widget = await get_widget(db, organization_id, widget_id)
    if name and name != widget.name:
        duplicate = await db.execute(
            select(Widget.id).where(
                Widget.organization_id == organization_id, Widget.name == name
            )
        )
        if duplicate.scalar_one_or_none() is not None:
            raise ConflictError("A widget with this name already exists", field="name")
        widget.name = name
    if status is not None:
        if status not in (WidgetStatus.ACTIVE.value, WidgetStatus.ARCHIVED.value):
            raise ValidationAppError("status must be active or archived", field="status")
        widget.status = status
    if clear_fallback:
        widget.fallback_json = None
    elif fallback is not None:
        widget.fallback_json = fallback
    await db.flush()
    return widget


async def add_widget_version(
    db: AsyncSession,
    organization_id: uuid.UUID,
    widget_id: uuid.UUID,
    *,
    config_schema: dict,
    defaults: dict | None,
) -> Widget:
    widget = await get_widget(db, organization_id, widget_id)
    schema = validate_widget_schema(config_schema)
    if defaults:
        validate_widget_config(schema, defaults)
    next_no = widget.versions[-1].version_no + 1 if widget.versions else 1
    db.add(
        WidgetVersion(
            widget_id=widget.id,
            version_no=next_no,
            config_schema_json=schema,
            defaults_json=defaults,
        )
    )
    await db.flush()
    await db.refresh(widget, ["versions"])
    return widget


# --- template lifecycle (P2-CNT-001) ---

_EDITABLE_STATES = (TemplateStatus.DRAFT.value, TemplateStatus.REJECTED.value)


async def get_template(
    db: AsyncSession, organization_id: uuid.UUID, template_id: uuid.UUID
) -> Template:
    template = await layouts_repo.get_template(db, organization_id, template_id)
    if template is None:
        raise NotFoundError("Template not found")
    return template


async def update_template(
    db: AsyncSession,
    organization_id: uuid.UUID,
    template_id: uuid.UUID,
    *,
    name: str | None,
    description: str | None,
    canvas_json: dict | None,
) -> Template:
    template = await get_template(db, organization_id, template_id)
    if template.status not in _EDITABLE_STATES:
        raise BusinessRuleError(
            "Only draft or rejected templates can be edited; archived and "
            "approved templates are immutable (submit a new draft revision)"
        )
    if name and name != template.name:
        if await layouts_repo.get_template_by_name(db, organization_id, name):
            raise ConflictError("A template with this name already exists", field="name")
        template.name = name
    if description is not None:
        template.description = description
    if canvas_json is not None:
        from app.services.layouts import parse_canvas

        template.canvas_json = parse_canvas(canvas_json).model_dump()
    # Editing a rejected template returns it to draft for resubmission.
    if template.status == TemplateStatus.REJECTED.value:
        template.status = TemplateStatus.DRAFT.value
    await db.flush()
    return template


async def submit_template(
    db: AsyncSession,
    organization_id: uuid.UUID,
    template_id: uuid.UUID,
    *,
    requester_id: uuid.UUID | None,
    comments: str | None,
) -> Template:
    """Validation happens here — approvers never hit canvas errors."""
    template = await get_template(db, organization_id, template_id)
    if template.status not in _EDITABLE_STATES:
        raise BusinessRuleError("Only draft or rejected templates can be submitted")
    await validate_canvas_widgets(db, organization_id, template.canvas_json)
    template.status = TemplateStatus.PENDING_APPROVAL.value
    await db.flush()
    await approvals.submit(
        db,
        organization_id,
        "template",
        template.id,
        requester_id=requester_id,
        comments=comments,
    )
    await db.refresh(template, ["versions"])
    return template


async def archive_template(
    db: AsyncSession, organization_id: uuid.UUID, template_id: uuid.UUID
) -> Template:
    template = await get_template(db, organization_id, template_id)
    if template.status == TemplateStatus.PENDING_APPROVAL.value:
        raise BusinessRuleError("Withdraw the pending approval before archiving")
    template.status = TemplateStatus.ARCHIVED.value
    await db.flush()
    return template


async def _template_on_approved(
    db: AsyncSession, organization_id: uuid.UUID, template_id: uuid.UUID
) -> None:
    template = await get_template(db, organization_id, template_id)
    next_no = template.versions[-1].version_no + 1 if template.versions else 1
    version = TemplateVersion(
        id=uuid.uuid4(),
        template_id=template.id,
        version_no=next_no,
        canvas_json=template.canvas_json,
    )
    db.add(version)
    template.current_version_id = version.id
    template.status = TemplateStatus.APPROVED.value
    await db.flush()
    logger.info("Template %s approved as v%s", template.id, next_no)


async def _template_on_rejected(
    db: AsyncSession, organization_id: uuid.UUID, template_id: uuid.UUID
) -> None:
    template = await get_template(db, organization_id, template_id)
    template.status = TemplateStatus.REJECTED.value
    await db.flush()


async def _template_name(
    db: AsyncSession, organization_id: uuid.UUID, template_id: uuid.UUID
) -> str | None:
    template = await layouts_repo.get_template(db, organization_id, template_id)
    return template.name if template else None


def _register_template_adapter() -> None:
    approvals.register_adapter(
        "template",
        approvals.EntityAdapter(
            approve_permission="layouts.manage",
            get_name=_template_name,
            on_approved=_template_on_approved,
            on_rejected=_template_on_rejected,
        ),
    )


_register_template_adapter()


# --- asset collections (P2-CNT-004) ---


async def get_collection(
    db: AsyncSession, organization_id: uuid.UUID, collection_id: uuid.UUID
) -> AssetCollection:
    collection = (
        await db.execute(
            select(AssetCollection).where(
                AssetCollection.organization_id == organization_id,
                AssetCollection.id == collection_id,
            )
        )
    ).scalar_one_or_none()
    if collection is None:
        raise NotFoundError("Asset collection not found")
    return collection


async def list_collections(
    db: AsyncSession, organization_id: uuid.UUID
) -> list[AssetCollection]:
    rows = await db.execute(
        select(AssetCollection)
        .where(AssetCollection.organization_id == organization_id)
        .order_by(AssetCollection.name)
    )
    return list(rows.scalars().all())


async def create_collection(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    name: str,
    description: str | None,
) -> AssetCollection:
    existing = await db.execute(
        select(AssetCollection.id).where(
            AssetCollection.organization_id == organization_id,
            AssetCollection.name == name,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise ConflictError("A collection with this name already exists", field="name")
    collection = AssetCollection(
        organization_id=organization_id, name=name, description=description
    )
    db.add(collection)
    await db.flush()
    await db.refresh(collection, ["items"])
    return collection


async def update_collection(
    db: AsyncSession,
    organization_id: uuid.UUID,
    collection_id: uuid.UUID,
    *,
    name: str | None,
    description: str | None,
) -> AssetCollection:
    collection = await get_collection(db, organization_id, collection_id)
    if name and name != collection.name:
        duplicate = await db.execute(
            select(AssetCollection.id).where(
                AssetCollection.organization_id == organization_id,
                AssetCollection.name == name,
            )
        )
        if duplicate.scalar_one_or_none() is not None:
            raise ConflictError("A collection with this name already exists", field="name")
        collection.name = name
    if description is not None:
        collection.description = description
    await db.flush()
    return collection


async def delete_collection(
    db: AsyncSession, organization_id: uuid.UUID, collection_id: uuid.UUID
) -> None:
    collection = await get_collection(db, organization_id, collection_id)
    await db.delete(collection)
    await db.flush()


async def replace_collection_items(
    db: AsyncSession,
    organization_id: uuid.UUID,
    collection_id: uuid.UUID,
    asset_ids: list[uuid.UUID],
) -> AssetCollection:
    if len(asset_ids) != len(set(asset_ids)):
        raise ValidationAppError("Duplicate assets in collection", field="asset_ids")
    collection = await get_collection(db, organization_id, collection_id)
    for asset_id in asset_ids:
        if await content_repo.get_asset(db, organization_id, asset_id) is None:
            raise NotFoundError("Asset not found")
    # Replace-set: clear+flush before re-adding (unique constraint on pairs).
    collection.items.clear()
    await db.flush()
    collection.items.extend(
        AssetCollectionItem(collection_id=collection.id, asset_id=asset_id, position=index)
        for index, asset_id in enumerate(asset_ids, start=1)
    )
    await db.flush()
    return collection


async def add_collection_to_playlist(
    db: AsyncSession,
    organization_id: uuid.UUID,
    collection_id: uuid.UUID,
    playlist_id: uuid.UUID,
):
    """Appends every collection asset as a playlist item, in order —
    the P2-CNT-004 reuse path into playlists."""
    from app.services import playlists as playlists_service

    collection = await get_collection(db, organization_id, collection_id)
    if not collection.items:
        raise BusinessRuleError("The collection is empty")
    playlist = None
    for item in collection.items:
        playlist = await playlists_service.add_item(
            db,
            organization_id,
            playlist_id,
            asset_id=item.asset_id,
            layout_id=None,
            duration_ms=None,
            transition=None,
        )
    return playlist
