import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentTenantId, PageParams, require_permissions
from app.db.session import get_db
from app.models import Playlist
from app.models.content import ProcessingStatus
from app.models.layout import LayoutStatus
from app.models.playlist import PlaylistItemType
from app.repositories import content as content_repo
from app.repositories import layouts as layouts_repo
from app.repositories import playlists as repo
from app.schemas.envelope import success
from app.schemas.playlists import (
    PlaylistCreate,
    PlaylistDetailOut,
    PlaylistItemIn,
    PlaylistItemOut,
    PlaylistItemUpdate,
    PlaylistOut,
    PlaylistUpdate,
    PlaylistVersionOut,
    ReplaceItemsRequest,
)
from app.services import content as content_service
from app.services import playlists as service

router = APIRouter()


def _summary(playlist: Playlist) -> dict:
    out = PlaylistOut.model_validate(playlist)
    out.item_count = len(playlist.items)
    out.total_duration_ms = sum(item.duration_ms or 0 for item in playlist.items)
    out.current_version_no = playlist.versions[-1].version_no if playlist.versions else None
    return out.model_dump(mode="json")


async def _detail(db: AsyncSession, tenant_id: uuid.UUID, playlist: Playlist) -> dict:
    base = _summary(playlist)
    items_out: list[dict] = []
    # The loaded collection keeps its original order after in-place
    # position updates; sort explicitly.
    for item in sorted(playlist.items, key=lambda entry: entry.position):
        out = PlaylistItemOut.model_validate(item)
        if item.item_type == PlaylistItemType.ASSET.value and item.asset_id:
            asset = await content_repo.get_asset(db, tenant_id, item.asset_id)
            if asset is not None:
                out.name = asset.name
                out.asset_type = asset.type
                out.thumbnail_url = content_service.thumbnail_url(asset)
                version = content_service.current_version(asset)
                out.ready = (
                    version is not None
                    and version.processing_status == ProcessingStatus.READY.value
                )
        elif item.layout_id:
            layout = await layouts_repo.get_by_id(db, tenant_id, item.layout_id)
            if layout is not None:
                out.name = layout.name
                out.ready = layout.status == LayoutStatus.PUBLISHED.value
        items_out.append(out.model_dump(mode="json"))
    detail = PlaylistDetailOut.model_validate(playlist)
    result = detail.model_dump(mode="json")
    result.update(base)
    result["items"] = items_out
    result["versions"] = [
        PlaylistVersionOut.model_validate(v).model_dump(mode="json") for v in playlist.versions
    ]
    return result


@router.get("/playlists", dependencies=[require_permissions("playlists.view")])
async def list_playlists(
    tenant_id: CurrentTenantId,
    pagination: PageParams,
    q: str | None = Query(None, max_length=200),
    status: str | None = Query(None, max_length=20),
    db: AsyncSession = Depends(get_db),
) -> dict:
    playlists, total = await repo.search(
        db, tenant_id, q=q, status=status, page=pagination.page, page_size=pagination.page_size
    )
    return success(
        [_summary(p) for p in playlists],
        page=pagination.page,
        page_size=pagination.page_size,
        total=total,
    )


@router.post("/playlists", dependencies=[require_permissions("playlists.manage")], status_code=201)
async def create_playlist(
    body: PlaylistCreate, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    playlist = await service.create_playlist(
        db,
        tenant_id,
        name=body.name,
        description=body.description,
        loop_enabled=body.loop_enabled,
        fallback_playlist_id=body.fallback_playlist_id,
    )
    return success(await _detail(db, tenant_id, playlist))


@router.get("/playlists/{playlist_id}", dependencies=[require_permissions("playlists.view")])
async def get_playlist(
    playlist_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    playlist = await service.get_playlist(db, tenant_id, playlist_id)
    return success(await _detail(db, tenant_id, playlist))


@router.patch("/playlists/{playlist_id}", dependencies=[require_permissions("playlists.manage")])
async def update_playlist(
    playlist_id: uuid.UUID,
    body: PlaylistUpdate,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
) -> dict:
    playlist = await service.update_playlist(
        db,
        tenant_id,
        playlist_id,
        name=body.name,
        description=body.description,
        loop_enabled=body.loop_enabled,
        fallback_playlist_id=body.fallback_playlist_id,
        clear_fallback=body.clear_fallback,
    )
    return success(await _detail(db, tenant_id, playlist))


@router.put(
    "/playlists/{playlist_id}/items", dependencies=[require_permissions("playlists.manage")]
)
async def replace_items(
    playlist_id: uuid.UUID,
    body: ReplaceItemsRequest,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
) -> dict:
    playlist = await service.replace_items(
        db,
        tenant_id,
        playlist_id,
        [item.model_dump() for item in body.items],
    )
    return success(await _detail(db, tenant_id, playlist))


@router.post(
    "/playlists/{playlist_id}/items",
    dependencies=[require_permissions("playlists.manage")],
    status_code=201,
)
async def add_item(
    playlist_id: uuid.UUID,
    body: PlaylistItemIn,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
) -> dict:
    playlist = await service.add_item(
        db,
        tenant_id,
        playlist_id,
        asset_id=body.asset_id,
        layout_id=body.layout_id,
        duration_ms=body.duration_ms,
        transition=body.transition,
    )
    return success(await _detail(db, tenant_id, playlist))


@router.patch(
    "/playlists/{playlist_id}/items/{item_id}",
    dependencies=[require_permissions("playlists.manage")],
)
async def update_item(
    playlist_id: uuid.UUID,
    item_id: uuid.UUID,
    body: PlaylistItemUpdate,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
) -> dict:
    playlist = await service.update_item(
        db,
        tenant_id,
        playlist_id,
        item_id,
        duration_ms=body.duration_ms,
        clear_duration=body.clear_duration,
        transition=body.transition,
        enabled=body.enabled,
        position=body.position,
    )
    return success(await _detail(db, tenant_id, playlist))


@router.delete(
    "/playlists/{playlist_id}/items/{item_id}",
    dependencies=[require_permissions("playlists.manage")],
)
async def remove_item(
    playlist_id: uuid.UUID,
    item_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
) -> dict:
    playlist = await service.remove_item(db, tenant_id, playlist_id, item_id)
    return success(await _detail(db, tenant_id, playlist))


@router.post(
    "/playlists/{playlist_id}/publish", dependencies=[require_permissions("playlists.manage")]
)
async def publish_playlist(
    playlist_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    playlist = await service.publish_playlist(db, tenant_id, playlist_id)
    return success(await _detail(db, tenant_id, playlist))


@router.get(
    "/playlists/{playlist_id}/versions", dependencies=[require_permissions("playlists.view")]
)
async def list_versions(
    playlist_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    playlist = await service.get_playlist(db, tenant_id, playlist_id)
    return success(
        [PlaylistVersionOut.model_validate(v).model_dump(mode="json") for v in playlist.versions]
    )


@router.delete("/playlists/{playlist_id}", dependencies=[require_permissions("playlists.manage")])
async def archive_playlist(
    playlist_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    playlist = await service.archive_playlist(db, tenant_id, playlist_id)
    return success(_summary(playlist))


@router.post(
    "/playlists/{playlist_id}/restore", dependencies=[require_permissions("playlists.manage")]
)
async def restore_playlist(
    playlist_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    playlist = await service.restore_playlist(db, tenant_id, playlist_id)
    return success(_summary(playlist))
