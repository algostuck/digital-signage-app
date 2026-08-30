import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentTenantId, CurrentUser, PageParams, require_permissions
from app.db.session import get_db
from app.models import Layout, Template
from app.repositories import layouts as repo
from app.schemas.envelope import success
from app.schemas.layouts import (
    LayoutCreate,
    LayoutDetailOut,
    LayoutOut,
    LayoutUpdate,
    LayoutVersionOut,
    TemplateCloneRequest,
    TemplateCreate,
    TemplateOut,
    TemplateSubmit,
    TemplateUpdate,
    TemplateVersionOut,
)
from app.services import layouts as service
from app.services import studio

router = APIRouter()


def _summary(layout: Layout) -> dict:
    out = LayoutOut.model_validate(layout)
    out.zone_count = len(layout.draft_canvas_json.get("zones", []))
    out.current_version_no = layout.versions[-1].version_no if layout.versions else None
    return out.model_dump(mode="json")


def _detail(layout: Layout) -> dict:
    out = LayoutDetailOut.model_validate(layout)
    out.zone_count = len(layout.draft_canvas_json.get("zones", []))
    out.current_version_no = layout.versions[-1].version_no if layout.versions else None
    return out.model_dump(mode="json")


@router.get("/layouts", dependencies=[require_permissions("layouts.view")])
async def list_layouts(
    tenant_id: CurrentTenantId,
    pagination: PageParams,
    q: str | None = Query(None, max_length=200),
    status: str | None = Query(None, max_length=20),
    db: AsyncSession = Depends(get_db),
) -> dict:
    layouts, total = await repo.search(
        db, tenant_id, q=q, status=status, page=pagination.page, page_size=pagination.page_size
    )
    return success(
        [_summary(item) for item in layouts],
        page=pagination.page,
        page_size=pagination.page_size,
        total=total,
    )


@router.post("/layouts", dependencies=[require_permissions("layouts.manage")], status_code=201)
async def create_layout(
    body: LayoutCreate, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    layout = await service.create_layout(
        db,
        tenant_id,
        name=body.name,
        description=body.description,
        canvas_width=body.canvas_width,
        canvas_height=body.canvas_height,
        template_id=body.template_id,
    )
    return success(_detail(layout))


@router.get("/layouts/{layout_id}", dependencies=[require_permissions("layouts.view")])
async def get_layout(
    layout_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    layout = await service.get_layout(db, tenant_id, layout_id)
    return success(_detail(layout))


@router.patch("/layouts/{layout_id}", dependencies=[require_permissions("layouts.manage")])
async def update_layout(
    layout_id: uuid.UUID,
    body: LayoutUpdate,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
) -> dict:
    layout = await service.update_layout(
        db,
        tenant_id,
        layout_id,
        name=body.name,
        description=body.description,
        canvas_json=body.canvas_json,
    )
    return success(_detail(layout))


@router.post("/layouts/{layout_id}/preview", dependencies=[require_permissions("layouts.view")])
async def preview_layout(
    layout_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    canvas = await service.preview_layout(db, tenant_id, layout_id)
    return success(canvas)


@router.post("/layouts/{layout_id}/publish", dependencies=[require_permissions("layouts.manage")])
async def publish_layout(
    layout_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    layout = await service.publish_layout(db, tenant_id, layout_id)
    return success(_detail(layout))


@router.get("/layouts/{layout_id}/versions", dependencies=[require_permissions("layouts.view")])
async def list_versions(
    layout_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    layout = await service.get_layout(db, tenant_id, layout_id)
    return success(
        [LayoutVersionOut.model_validate(v).model_dump(mode="json") for v in layout.versions]
    )


@router.delete("/layouts/{layout_id}", dependencies=[require_permissions("layouts.manage")])
async def archive_layout(
    layout_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    layout = await service.archive_layout(db, tenant_id, layout_id)
    return success(_summary(layout))


@router.post("/layouts/{layout_id}/restore", dependencies=[require_permissions("layouts.manage")])
async def restore_layout(
    layout_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    layout = await service.restore_layout(db, tenant_id, layout_id)
    return success(_summary(layout))


# --- templates (P2-CNT-001: versioned + governed) ---


def _template_out(template: Template) -> dict:
    out = TemplateOut.model_validate(template)
    current = next(
        (v for v in template.versions if v.id == template.current_version_id), None
    )
    out.current_version_no = current.version_no if current else None
    return out.model_dump(mode="json")


@router.get("/templates", dependencies=[require_permissions("layouts.view")])
async def list_templates(tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)) -> dict:
    templates = await repo.list_templates(db, tenant_id)
    return success([_template_out(t) for t in templates])


@router.post("/templates", dependencies=[require_permissions("layouts.manage")], status_code=201)
async def create_template(
    body: TemplateCreate, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    template = await service.create_template(
        db,
        tenant_id,
        layout_id=body.layout_id,
        name=body.name,
        description=body.description,
        canvas_width=body.canvas_width,
        canvas_height=body.canvas_height,
    )
    return success(_template_out(template))


@router.put("/templates/{template_id}", dependencies=[require_permissions("layouts.manage")])
@router.patch("/templates/{template_id}", dependencies=[require_permissions("layouts.manage")])
async def update_template(
    template_id: uuid.UUID,
    body: TemplateUpdate,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
) -> dict:
    template = await studio.update_template(
        db,
        tenant_id,
        template_id,
        name=body.name,
        description=body.description,
        canvas_json=body.canvas_json,
    )
    return success(_template_out(template))


@router.post(
    "/templates/{template_id}/submit", dependencies=[require_permissions("layouts.manage")]
)
async def submit_template(
    template_id: uuid.UUID,
    body: TemplateSubmit,
    tenant_id: CurrentTenantId,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    template = await studio.submit_template(
        db, tenant_id, template_id, requester_id=user.id, comments=body.comments
    )
    return success(_template_out(template))


@router.get(
    "/templates/{template_id}/versions", dependencies=[require_permissions("layouts.view")]
)
async def template_versions(
    template_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    template = await studio.get_template(db, tenant_id, template_id)
    return success(
        [
            TemplateVersionOut.model_validate(v).model_dump(mode="json")
            for v in template.versions
        ]
    )


@router.delete("/templates/{template_id}", dependencies=[require_permissions("layouts.manage")])
async def archive_template(
    template_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    template = await studio.archive_template(db, tenant_id, template_id)
    return success(_template_out(template))


@router.post(
    "/templates/{template_id}/clone",
    dependencies=[require_permissions("layouts.manage")],
    status_code=201,
)
async def clone_template(
    template_id: uuid.UUID,
    body: TemplateCloneRequest,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
) -> dict:
    layout = await service.clone_template(db, tenant_id, template_id, name=body.name)
    return success(_detail(layout))
