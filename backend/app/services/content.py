"""Content CMS service (M05): upload sessions, assets, versions, folders."""

import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import BusinessRuleError, ConflictError, NotFoundError, ValidationAppError
from app.integrations.storage import get_storage
from app.models import Asset, AssetVersion, Folder, UploadSession
from app.models.content import (
    AssetStatus,
    AssetType,
    ProcessingStatus,
    UploadSessionStatus,
)
from app.repositories import content as repo
from app.repositories import locations as locations_repo

logger = logging.getLogger("app.content")

_MIME_TYPE_MAP: list[tuple[str, str]] = [
    ("image/", AssetType.IMAGE.value),
    ("video/", AssetType.VIDEO.value),
    ("audio/", AssetType.AUDIO.value),
    ("application/pdf", AssetType.DOCUMENT.value),
    ("text/html", AssetType.HTML.value),
    ("text/plain", AssetType.TEXT.value),
    ("application/json", AssetType.DATA.value),
]


def asset_type_for_mime(mime_type: str) -> str:
    for prefix, asset_type in _MIME_TYPE_MAP:
        if mime_type.startswith(prefix):
            return asset_type
    return AssetType.OTHER.value


def validate_upload_policy(mime_type: str, size_bytes: int) -> None:
    settings = get_settings()
    if not any(mime_type.startswith(p) for p in settings.allowed_mime_prefixes):
        raise ValidationAppError(f"Unsupported content type: {mime_type}", field="mime_type")
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if size_bytes <= 0 or size_bytes > max_bytes:
        raise ValidationAppError(
            f"File size must be between 1 byte and {settings.max_upload_size_mb} MB",
            field="size_bytes",
        )


# --- upload sessions ---


async def create_upload_session(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    filename: str,
    mime_type: str,
    size_bytes: int,
    folder_id: uuid.UUID | None = None,
    asset_id: uuid.UUID | None = None,
    name: str | None = None,
) -> tuple[UploadSession, str]:
    """Validates policy and returns (session, presigned PUT url) — FR-CNT-001."""
    validate_upload_policy(mime_type, size_bytes)
    from app.services.tenant_admin import ensure_storage_quota

    await ensure_storage_quota(db, organization_id, size_bytes)  # P2-TNT-002
    settings = get_settings()

    if folder_id is not None and await repo.get_folder(db, organization_id, folder_id) is None:
        raise NotFoundError("Folder not found")

    if asset_id is not None:
        asset = await repo.get_asset(db, organization_id, asset_id)
        if asset is None:
            raise NotFoundError("Asset not found")
        if asset.status == AssetStatus.ARCHIVED.value:
            raise BusinessRuleError("Cannot upload a new version of an archived asset")
        target_asset_id = asset.id
        version_no = await repo.max_version_no(db, asset.id) + 1
        is_new = False
    else:
        target_asset_id = uuid.uuid4()
        version_no = 1
        is_new = True

    safe_filename = filename.replace("/", "_").replace("\\", "_")[:255]
    object_key = (
        f"tenant/{organization_id}/content/{target_asset_id}/v{version_no}"
        f"/original/{safe_filename}"
    )

    session = UploadSession(
        organization_id=organization_id,
        asset_id=target_asset_id,
        is_new_asset=is_new,
        folder_id=folder_id,
        asset_name=name,
        original_filename=safe_filename,
        mime_type=mime_type,
        size_bytes=size_bytes,
        object_key=object_key,
        version_no=version_no,
        status=UploadSessionStatus.PENDING.value,
        expires_at=datetime.now(UTC) + timedelta(seconds=settings.upload_url_ttl_seconds),
    )
    db.add(session)
    await db.flush()

    upload_url = get_storage().presigned_put_url(
        object_key, mime_type, settings.upload_url_ttl_seconds
    )
    return session, upload_url


def _as_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


async def complete_upload(
    db: AsyncSession, organization_id: uuid.UUID, session_id: uuid.UUID
) -> Asset:
    """Verifies the uploaded object and creates the asset/version, then runs
    or enqueues processing (upload -> validate -> process -> ready)."""
    session = await repo.get_upload_session(db, organization_id, session_id)
    if session is None:
        raise NotFoundError("Upload session not found")
    if session.status == UploadSessionStatus.COMPLETED.value:
        raise ConflictError("Upload session already completed")
    if _as_utc(session.expires_at) < datetime.now(UTC):
        raise BusinessRuleError("Upload session has expired")
    if not get_storage().exists(session.object_key):
        raise BusinessRuleError("No uploaded file found for this session")

    if session.is_new_asset:
        asset = Asset(
            id=session.asset_id,
            organization_id=organization_id,
            folder_id=session.folder_id,
            type=asset_type_for_mime(session.mime_type),
            name=session.asset_name or session.original_filename,
            status=AssetStatus.DRAFT.value,
        )
        db.add(asset)
    else:
        asset = await repo.get_asset(db, organization_id, session.asset_id)
        if asset is None:
            raise NotFoundError("Asset not found")

    version = AssetVersion(
        asset_id=session.asset_id,
        version_no=session.version_no,
        object_key=session.object_key,
        original_filename=session.original_filename,
        mime_type=session.mime_type,
        size_bytes=session.size_bytes,
        processing_status=ProcessingStatus.PROCESSING.value,
    )
    db.add(version)
    session.status = UploadSessionStatus.COMPLETED.value
    await db.flush()

    settings = get_settings()
    if settings.media_processing_inline:
        from app.services import media

        await media.process_version(db, version.id)
    else:
        from app.workers.media import process_asset_version

        process_asset_version.delay(str(version.id))

    await db.refresh(asset, ["versions", "tags"])
    logger.info(
        "Upload completed: asset %s v%s (%s)", asset.id, version.version_no, session.mime_type
    )
    return asset


# --- assets ---


async def get_asset(db: AsyncSession, organization_id: uuid.UUID, asset_id: uuid.UUID) -> Asset:
    asset = await repo.get_asset(db, organization_id, asset_id)
    if asset is None:
        raise NotFoundError("Asset not found")
    return asset


async def update_asset(
    db: AsyncSession,
    organization_id: uuid.UUID,
    asset_id: uuid.UUID,
    *,
    name: str | None = None,
    description: str | None = None,
    folder_id: uuid.UUID | None = None,
    clear_folder: bool = False,
    tags: list[tuple[str, str]] | None = None,
) -> Asset:
    asset = await get_asset(db, organization_id, asset_id)
    if name is not None:
        asset.name = name
    if description is not None:
        asset.description = description
    if clear_folder:
        asset.folder_id = None
    elif folder_id is not None:
        if await repo.get_folder(db, organization_id, folder_id) is None:
            raise NotFoundError("Folder not found")
        asset.folder_id = folder_id
    if tags is not None:
        asset.tags = [
            await locations_repo.get_or_create_tag(db, organization_id, key, value)
            for key, value in tags
        ]
    await db.flush()
    return asset


def current_version(asset: Asset) -> AssetVersion | None:
    if asset.current_version_id:
        for version in asset.versions:
            if version.id == asset.current_version_id:
                return version
    return asset.versions[-1] if asset.versions else None


async def publish_asset(
    db: AsyncSession, organization_id: uuid.UUID, asset_id: uuid.UUID
) -> Asset:
    asset = await get_asset(db, organization_id, asset_id)
    version = current_version(asset)
    if version is None or version.processing_status != ProcessingStatus.READY.value:
        raise BusinessRuleError("Asset cannot be published until processing is READY")
    if asset.status == AssetStatus.ARCHIVED.value:
        raise BusinessRuleError("Restore the asset before publishing")
    asset.status = AssetStatus.PUBLISHED.value
    await db.flush()
    from app.services import audit

    await audit.record(
        db, organization_id, action="CONTENT_PUBLISHED", entity_type="asset",
        entity_id=asset.id, after={"name": asset.name},
    )

    from app.services import events

    await events.emit(
        db,
        organization_id,
        event_type="content.published",
        entity_type="asset",
        entity_id=asset.id,
        payload={"name": asset.name, "type": asset.type},
    )
    return asset


async def archive_asset(
    db: AsyncSession, organization_id: uuid.UUID, asset_id: uuid.UUID
) -> Asset:
    asset = await get_asset(db, organization_id, asset_id)
    asset.status = AssetStatus.ARCHIVED.value
    await db.flush()
    return asset


async def restore_asset(
    db: AsyncSession, organization_id: uuid.UUID, asset_id: uuid.UUID
) -> Asset:
    asset = await get_asset(db, organization_id, asset_id)
    if asset.status == AssetStatus.ARCHIVED.value:
        asset.status = AssetStatus.DRAFT.value
        await db.flush()
    return asset


def download_url(asset: Asset) -> str:
    version = current_version(asset)
    if version is None or version.processing_status != ProcessingStatus.READY.value:
        raise BusinessRuleError("Asset has no READY version to download")
    settings = get_settings()
    return get_storage().presigned_get_url(
        version.object_key,
        settings.signed_url_ttl_seconds,
        filename=version.original_filename,
    )


def thumbnail_url(asset: Asset) -> str | None:
    version = current_version(asset)
    if version is None or not version.thumbnail_key:
        return None
    settings = get_settings()
    return get_storage().presigned_get_url(
        version.thumbnail_key, settings.signed_url_ttl_seconds
    )


# --- folders ---


async def create_folder(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    name: str,
    parent_id: uuid.UUID | None,
) -> Folder:
    if parent_id is not None:
        parent = await repo.get_folder(db, organization_id, parent_id)
        if parent is None or parent.status != "active":
            raise NotFoundError("Parent folder not found")
    for existing in await repo.list_folders(db, organization_id):
        if existing.parent_id == parent_id and existing.name == name:
            raise ConflictError("A folder with this name already exists here", field="name")
    folder = Folder(organization_id=organization_id, parent_id=parent_id, name=name)
    db.add(folder)
    await db.flush()
    return folder


async def rename_folder(
    db: AsyncSession, organization_id: uuid.UUID, folder_id: uuid.UUID, *, name: str
) -> Folder:
    folder = await repo.get_folder(db, organization_id, folder_id)
    if folder is None:
        raise NotFoundError("Folder not found")
    folder.name = name
    await db.flush()
    return folder


async def archive_folder(
    db: AsyncSession, organization_id: uuid.UUID, folder_id: uuid.UUID
) -> Folder:
    folder = await repo.get_folder(db, organization_id, folder_id)
    if folder is None:
        raise NotFoundError("Folder not found")
    if await repo.folder_has_children(db, organization_id, folder_id):
        raise BusinessRuleError("Move or archive the folder's contents first")
    folder.status = "archived"
    await db.flush()
    return folder
