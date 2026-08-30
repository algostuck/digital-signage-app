"""Content studio API (P2-08 widgets, P2-CNT-002 data variables,
P2-CNT-004 asset collections)."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentTenantId, require_permissions
from app.db.session import get_db
from app.schemas.envelope import success
from app.schemas.studio import (
    CollectionCreate,
    CollectionItemsReplace,
    CollectionOut,
    CollectionToPlaylist,
    CollectionUpdate,
    WidgetCreate,
    WidgetOut,
    WidgetUpdate,
    WidgetVersionCreate,
)
from app.services import studio

router = APIRouter()


# --- data variables ---


@router.get("/data-variables", dependencies=[require_permissions("layouts.view")])
async def list_data_variables() -> dict:
    return success(
        [{"token": token, "label": label} for token, label in studio.DATA_VARIABLES.items()]
    )


# --- widgets (P2-CNT-003) ---


def _widget_out(widget) -> dict:
    return WidgetOut.model_validate(widget).model_dump(mode="json")


@router.get("/widgets", dependencies=[require_permissions("layouts.view")])
async def list_widgets(tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)) -> dict:
    widgets = await studio.list_widgets(db, tenant_id)
    return success([_widget_out(w) for w in widgets])


@router.post("/widgets", dependencies=[require_permissions("widgets.manage")], status_code=201)
async def create_widget(
    body: WidgetCreate, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    widget = await studio.create_widget(
        db,
        tenant_id,
        type=body.type,
        name=body.name,
        config_schema=body.config_schema_json,
        defaults=body.defaults_json,
        fallback=body.fallback_json,
    )
    return success(_widget_out(widget))


@router.patch("/widgets/{widget_id}", dependencies=[require_permissions("widgets.manage")])
async def update_widget(
    widget_id: uuid.UUID,
    body: WidgetUpdate,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
) -> dict:
    widget = await studio.update_widget(
        db,
        tenant_id,
        widget_id,
        name=body.name,
        status=body.status,
        fallback=body.fallback_json,
        clear_fallback=body.clear_fallback,
    )
    return success(_widget_out(widget))


@router.post(
    "/widgets/{widget_id}/versions",
    dependencies=[require_permissions("widgets.manage")],
    status_code=201,
)
async def add_widget_version(
    widget_id: uuid.UUID,
    body: WidgetVersionCreate,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
) -> dict:
    widget = await studio.add_widget_version(
        db,
        tenant_id,
        widget_id,
        config_schema=body.config_schema_json,
        defaults=body.defaults_json,
    )
    return success(_widget_out(widget))


# --- asset collections (P2-CNT-004) ---


def _collection_out(collection) -> dict:
    return CollectionOut.model_validate(collection).model_dump(mode="json")


@router.get("/asset-collections", dependencies=[require_permissions("content.view")])
async def list_collections(
    tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    collections = await studio.list_collections(db, tenant_id)
    return success([_collection_out(c) for c in collections])


@router.post(
    "/asset-collections", dependencies=[require_permissions("content.edit")], status_code=201
)
async def create_collection(
    body: CollectionCreate, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    collection = await studio.create_collection(
        db, tenant_id, name=body.name, description=body.description
    )
    return success(_collection_out(collection))


@router.patch(
    "/asset-collections/{collection_id}", dependencies=[require_permissions("content.edit")]
)
async def update_collection(
    collection_id: uuid.UUID,
    body: CollectionUpdate,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
) -> dict:
    collection = await studio.update_collection(
        db, tenant_id, collection_id, name=body.name, description=body.description
    )
    return success(_collection_out(collection))


@router.delete(
    "/asset-collections/{collection_id}", dependencies=[require_permissions("content.edit")]
)
async def delete_collection(
    collection_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    await studio.delete_collection(db, tenant_id, collection_id)
    return success({"deleted": True})


@router.put(
    "/asset-collections/{collection_id}/items",
    dependencies=[require_permissions("content.edit")],
)
async def replace_collection_items(
    collection_id: uuid.UUID,
    body: CollectionItemsReplace,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
) -> dict:
    collection = await studio.replace_collection_items(
        db, tenant_id, collection_id, body.asset_ids
    )
    return success(_collection_out(collection))


@router.post(
    "/asset-collections/{collection_id}/add-to-playlist",
    dependencies=[require_permissions("playlists.manage")],
)
async def add_collection_to_playlist(
    collection_id: uuid.UUID,
    body: CollectionToPlaylist,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
) -> dict:
    playlist = await studio.add_collection_to_playlist(
        db, tenant_id, collection_id, body.playlist_id
    )
    return success({"playlist_id": str(playlist.id), "items": len(playlist.items)})
