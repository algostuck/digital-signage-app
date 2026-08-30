"""Enterprise search API (P2-SRC-001/002): global search + saved views."""

import uuid

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentTenantId, CurrentUser, user_permission_codes
from app.core.errors import ConflictError, NotFoundError, ValidationAppError
from app.db.session import get_db
from app.models import SavedView
from app.models.saved_view import SAVED_VIEW_MODULES
from app.schemas.envelope import success
from app.services import search as search_service

router = APIRouter()


@router.get("/search")
async def global_search(
    tenant_id: CurrentTenantId,
    user: CurrentUser,
    q: str = Query(min_length=1, max_length=200),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """P2-SRC-001: one query, every module the caller may view."""
    results = await search_service.global_search(
        db,
        tenant_id,
        query=q,
        permissions=user_permission_codes(user),
        is_superuser=bool(user.is_superuser),
    )
    return success(
        {
            "query": q,
            "modules": results,
            "total": sum(len(rows) for rows in results.values()),
        }
    )


# --- saved views (P2-SRC-002): personal, no extra permission needed ---


class SavedViewCreate(BaseModel):
    module: str = Field(min_length=1, max_length=30)
    name: str = Field(min_length=1, max_length=100)
    filter_json: dict
    columns_json: list[str] | None = Field(default=None, max_length=30)


class SavedViewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    module: str
    name: str
    filter_json: dict
    columns_json: list[str] | None


@router.get("/saved-views")
async def list_saved_views(
    tenant_id: CurrentTenantId,
    user: CurrentUser,
    module: str | None = Query(None, max_length=30),
    db: AsyncSession = Depends(get_db),
) -> dict:
    query = select(SavedView).where(
        SavedView.organization_id == tenant_id, SavedView.user_id == user.id
    )
    if module:
        query = query.where(SavedView.module == module)
    rows = await db.execute(query.order_by(SavedView.module, SavedView.name))
    return success(
        [SavedViewOut.model_validate(v).model_dump(mode="json") for v in rows.scalars()]
    )


@router.post("/saved-views", status_code=201)
async def create_saved_view(
    body: SavedViewCreate,
    tenant_id: CurrentTenantId,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    if body.module not in SAVED_VIEW_MODULES:
        raise ValidationAppError(
            f"module must be one of {SAVED_VIEW_MODULES}", field="module"
        )
    existing = await db.execute(
        select(SavedView.id).where(
            SavedView.organization_id == tenant_id,
            SavedView.user_id == user.id,
            SavedView.module == body.module,
            SavedView.name == body.name,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise ConflictError(
            "You already have a view with this name in this module", field="name"
        )
    view = SavedView(
        organization_id=tenant_id,
        user_id=user.id,
        module=body.module,
        name=body.name,
        filter_json=body.filter_json,
        columns_json=body.columns_json,
    )
    db.add(view)
    await db.flush()
    return success(SavedViewOut.model_validate(view).model_dump(mode="json"))


@router.delete("/saved-views/{view_id}")
async def delete_saved_view(
    view_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    view = (
        await db.execute(
            select(SavedView).where(
                SavedView.organization_id == tenant_id,
                SavedView.user_id == user.id,  # owner-only, even same-org
                SavedView.id == view_id,
            )
        )
    ).scalar_one_or_none()
    if view is None:
        raise NotFoundError("Saved view not found")
    await db.delete(view)
    await db.flush()
    return success({"deleted": True})
