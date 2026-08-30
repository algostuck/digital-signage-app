"""Playlist engine service (FR-PLY-001..006).

Draft item rows are edited freely; publishing validates and snapshots the
enabled items into an immutable version (layout versions pinned at publish
time so player manifests stay deterministic).
"""

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BusinessRuleError, NotFoundError, ValidationAppError
from app.models import Asset, Layout, Playlist, PlaylistItem, PlaylistVersion
from app.models.content import AssetStatus, AssetType, ProcessingStatus
from app.models.layout import LayoutStatus
from app.models.playlist import PlaylistItemType, PlaylistStatus
from app.repositories import content as content_repo
from app.repositories import layouts as layouts_repo
from app.repositories import playlists as repo
from app.services.content import current_version as asset_current_version

logger = logging.getLogger("app.playlists")

DEFAULT_ITEM_DURATION_MS = 8000
_NATURAL_DURATION_TYPES = {AssetType.VIDEO.value, AssetType.AUDIO.value}


async def get_playlist(
    db: AsyncSession, organization_id: uuid.UUID, playlist_id: uuid.UUID
) -> Playlist:
    playlist = await repo.get_by_id(db, organization_id, playlist_id)
    if playlist is None:
        raise NotFoundError("Playlist not found")
    return playlist


async def _validate_fallback(
    db: AsyncSession,
    organization_id: uuid.UUID,
    playlist: Playlist | None,
    fallback_id: uuid.UUID,
) -> None:
    """Fallback must exist in-tenant and not create a cycle (FR-PLY-005)."""
    if playlist is not None and fallback_id == playlist.id:
        raise BusinessRuleError("A playlist cannot be its own fallback")
    seen: set[uuid.UUID] = {playlist.id} if playlist is not None else set()
    cursor: uuid.UUID | None = fallback_id
    while cursor is not None:
        if cursor in seen:
            raise BusinessRuleError("Fallback playlists must not form a cycle")
        seen.add(cursor)
        node = await repo.get_by_id(db, organization_id, cursor)
        if node is None:
            raise NotFoundError("Fallback playlist not found")
        cursor = node.fallback_playlist_id


async def create_playlist(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    name: str,
    description: str | None,
    loop_enabled: bool,
    fallback_playlist_id: uuid.UUID | None,
) -> Playlist:
    if fallback_playlist_id is not None:
        await _validate_fallback(db, organization_id, None, fallback_playlist_id)
    playlist = Playlist(
        organization_id=organization_id,
        name=name,
        description=description,
        loop_enabled=loop_enabled,
        fallback_playlist_id=fallback_playlist_id,
        status=PlaylistStatus.DRAFT.value,
    )
    db.add(playlist)
    await db.flush()
    await db.refresh(playlist, ["items", "versions"])
    logger.info("Playlist %s created", playlist.id)
    return playlist


async def update_playlist(
    db: AsyncSession,
    organization_id: uuid.UUID,
    playlist_id: uuid.UUID,
    *,
    name: str | None = None,
    description: str | None = None,
    loop_enabled: bool | None = None,
    fallback_playlist_id: uuid.UUID | None = None,
    clear_fallback: bool = False,
) -> Playlist:
    playlist = await get_playlist(db, organization_id, playlist_id)
    if playlist.status == PlaylistStatus.ARCHIVED.value:
        raise BusinessRuleError("Restore the playlist before editing")
    if name is not None:
        playlist.name = name
    if description is not None:
        playlist.description = description
    if loop_enabled is not None:
        playlist.loop_enabled = loop_enabled
    if clear_fallback:
        playlist.fallback_playlist_id = None
    elif fallback_playlist_id is not None:
        await _validate_fallback(db, organization_id, playlist, fallback_playlist_id)
        playlist.fallback_playlist_id = fallback_playlist_id
    await db.flush()
    return playlist


# --- items ---


async def _resolve_reference(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    asset_id: uuid.UUID | None,
    layout_id: uuid.UUID | None,
) -> tuple[str, Asset | None, Layout | None]:
    if (asset_id is None) == (layout_id is None):
        raise ValidationAppError(
            "A playlist item must reference exactly one of asset_id or layout_id"
        )
    if asset_id is not None:
        asset = await content_repo.get_asset(db, organization_id, asset_id)
        if asset is None:
            raise NotFoundError("Asset not found")
        return PlaylistItemType.ASSET.value, asset, None
    layout = await layouts_repo.get_by_id(db, organization_id, layout_id)
    if layout is None:
        raise NotFoundError("Layout not found")
    return PlaylistItemType.LAYOUT.value, None, layout


def _default_duration(item_type: str, asset: Asset | None) -> int | None:
    """Natural-length media may omit duration; everything else defaults."""
    if item_type == PlaylistItemType.ASSET.value and asset is not None:
        if asset.type in _NATURAL_DURATION_TYPES:
            return None
    return DEFAULT_ITEM_DURATION_MS


async def _editable_playlist(
    db: AsyncSession, organization_id: uuid.UUID, playlist_id: uuid.UUID
) -> Playlist:
    playlist = await get_playlist(db, organization_id, playlist_id)
    if playlist.status == PlaylistStatus.ARCHIVED.value:
        raise BusinessRuleError("Restore the playlist before editing")
    return playlist


async def add_item(
    db: AsyncSession,
    organization_id: uuid.UUID,
    playlist_id: uuid.UUID,
    *,
    asset_id: uuid.UUID | None,
    layout_id: uuid.UUID | None,
    duration_ms: int | None,
    transition: dict | None,
) -> Playlist:
    playlist = await _editable_playlist(db, organization_id, playlist_id)
    item_type, asset, _ = await _resolve_reference(
        db, organization_id, asset_id=asset_id, layout_id=layout_id
    )
    item = PlaylistItem(
        playlist_id=playlist.id,
        position=len(playlist.items) + 1,
        item_type=item_type,
        asset_id=asset_id,
        layout_id=layout_id,
        duration_ms=duration_ms if duration_ms is not None else _default_duration(item_type, asset),
        transition_json=transition,
    )
    playlist.items.append(item)
    await db.flush()
    return playlist


async def replace_items(
    db: AsyncSession,
    organization_id: uuid.UUID,
    playlist_id: uuid.UUID,
    items: list[dict],
) -> Playlist:
    """PUT semantics: the array order becomes the playlist order."""
    playlist = await _editable_playlist(db, organization_id, playlist_id)
    new_rows: list[PlaylistItem] = []
    for position, spec in enumerate(items, start=1):
        item_type, asset, _ = await _resolve_reference(
            db,
            organization_id,
            asset_id=spec.get("asset_id"),
            layout_id=spec.get("layout_id"),
        )
        duration = spec.get("duration_ms")
        new_rows.append(
            PlaylistItem(
                playlist_id=playlist.id,
                position=position,
                item_type=item_type,
                asset_id=spec.get("asset_id"),
                layout_id=spec.get("layout_id"),
                duration_ms=(
                    duration if duration is not None else _default_duration(item_type, asset)
                ),
                transition_json=spec.get("transition"),
                enabled=spec.get("enabled", True),
            )
        )
    playlist.items.clear()
    await db.flush()
    playlist.items.extend(new_rows)
    await db.flush()
    return playlist


def _find_item(playlist: Playlist, item_id: uuid.UUID) -> PlaylistItem:
    for item in playlist.items:
        if item.id == item_id:
            return item
    raise NotFoundError("Playlist item not found")


async def update_item(
    db: AsyncSession,
    organization_id: uuid.UUID,
    playlist_id: uuid.UUID,
    item_id: uuid.UUID,
    *,
    duration_ms: int | None = None,
    clear_duration: bool = False,
    transition: dict | None = None,
    enabled: bool | None = None,
    position: int | None = None,
) -> Playlist:
    playlist = await _editable_playlist(db, organization_id, playlist_id)
    item = _find_item(playlist, item_id)
    if clear_duration:
        item.duration_ms = None
    elif duration_ms is not None:
        item.duration_ms = duration_ms
    if transition is not None:
        item.transition_json = transition
    if enabled is not None:
        item.enabled = enabled
    if position is not None:
        ordered = [entry for entry in playlist.items if entry.id != item.id]
        target = max(0, min(position - 1, len(ordered)))
        ordered.insert(target, item)
        for index, entry in enumerate(ordered, start=1):
            entry.position = index
    await db.flush()
    return playlist


async def remove_item(
    db: AsyncSession, organization_id: uuid.UUID, playlist_id: uuid.UUID, item_id: uuid.UUID
) -> Playlist:
    playlist = await _editable_playlist(db, organization_id, playlist_id)
    item = _find_item(playlist, item_id)
    playlist.items.remove(item)
    for index, entry in enumerate(playlist.items, start=1):
        entry.position = index
    await db.flush()
    return playlist


# --- publish ---


async def publish_playlist(
    db: AsyncSession, organization_id: uuid.UUID, playlist_id: uuid.UUID
) -> Playlist:
    playlist = await _editable_playlist(db, organization_id, playlist_id)
    enabled_items = [item for item in playlist.items if item.enabled]
    if not enabled_items:
        raise BusinessRuleError("A playlist needs at least one enabled item to be published")

    snapshot_items: list[dict] = []
    for item in enabled_items:
        entry: dict = {
            "position": len(snapshot_items) + 1,
            "item_type": item.item_type,
            "duration_ms": item.duration_ms,
            "transition": item.transition_json,
        }
        if item.item_type == PlaylistItemType.ASSET.value:
            asset = await content_repo.get_asset(db, organization_id, item.asset_id)
            if asset is None:
                raise BusinessRuleError("A playlist item references a missing asset")
            version = asset_current_version(asset)
            if version is None or version.processing_status != ProcessingStatus.READY.value:
                raise BusinessRuleError(f"Asset '{asset.name}' is not READY")
            if asset.status == AssetStatus.ARCHIVED.value:
                raise BusinessRuleError(f"Asset '{asset.name}' is archived")
            if item.duration_ms is None and asset.type not in _NATURAL_DURATION_TYPES:
                raise BusinessRuleError(
                    f"Item '{asset.name}' needs a duration "
                    "(only video/audio may use natural length)"
                )
            entry.update(
                {
                    "asset_id": str(asset.id),
                    "asset_type": asset.type,
                    "name": asset.name,
                    "asset_version_no": version.version_no,
                }
            )
        else:
            layout = await layouts_repo.get_by_id(db, organization_id, item.layout_id)
            if layout is None:
                raise BusinessRuleError("A playlist item references a missing layout")
            if layout.status != LayoutStatus.PUBLISHED.value or not layout.versions:
                raise BusinessRuleError(f"Layout '{layout.name}' must be published first")
            if item.duration_ms is None:
                raise BusinessRuleError(f"Layout item '{layout.name}' needs a duration")
            entry.update(
                {
                    "layout_id": str(layout.id),
                    "name": layout.name,
                    # Pinned so the manifest stays deterministic (SRS §12).
                    "layout_version_no": layout.versions[-1].version_no,
                }
            )
        snapshot_items.append(entry)

    version_no = (playlist.versions[-1].version_no + 1) if playlist.versions else 1
    version = PlaylistVersion(
        playlist_id=playlist.id,
        version_no=version_no,
        items_json={"loop": playlist.loop_enabled, "items": snapshot_items},
    )
    db.add(version)
    await db.flush()

    playlist.current_version_id = version.id
    playlist.status = PlaylistStatus.PUBLISHED.value
    await db.flush()
    await db.refresh(playlist, ["items", "versions"])
    from app.services import audit

    await audit.record(
        db, organization_id, action="PLAYLIST_PUBLISHED", entity_type="playlist",
        entity_id=playlist.id, after={"version": version_no},
    )
    logger.info("Playlist %s published as v%s", playlist.id, version_no)
    return playlist


async def archive_playlist(
    db: AsyncSession, organization_id: uuid.UUID, playlist_id: uuid.UUID
) -> Playlist:
    playlist = await get_playlist(db, organization_id, playlist_id)
    playlist.status = PlaylistStatus.ARCHIVED.value
    await db.flush()
    return playlist


async def restore_playlist(
    db: AsyncSession, organization_id: uuid.UUID, playlist_id: uuid.UUID
) -> Playlist:
    playlist = await get_playlist(db, organization_id, playlist_id)
    if playlist.status == PlaylistStatus.ARCHIVED.value:
        playlist.status = (
            PlaylistStatus.PUBLISHED.value
            if playlist.current_version_id
            else PlaylistStatus.DRAFT.value
        )
        await db.flush()
    return playlist
