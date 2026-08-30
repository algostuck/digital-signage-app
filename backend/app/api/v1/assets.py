import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentTenantId, PageParams, require_permissions
from app.core.config import get_settings
from app.core.ratelimit import rate_limit
from app.db.session import get_db
from app.models import Asset
from app.schemas.content import (
    AssetOut,
    AssetUpdate,
    AssetVersionOut,
    DownloadUrlOut,
    FolderCreate,
    FolderOut,
    FolderUpdate,
    UploadSessionCreate,
    UploadSessionOut,
)
from app.schemas.envelope import success
from app.services import content as service

router = APIRouter()


def _asset_out(asset: Asset) -> dict:
    out = AssetOut.model_validate(asset)
    version = service.current_version(asset)
    if version is not None:
        out.current_version = AssetVersionOut.model_validate(version)
    out.thumbnail_url = service.thumbnail_url(asset)
    return out.model_dump(mode="json")


# --- upload sessions ---


@router.post(
    "/assets/uploads",
    dependencies=[
        require_permissions("content.create"),
        rate_limit("uploads", lambda: get_settings().rate_limit_uploads_per_minute),
    ],
    status_code=201,
)
async def create_upload_session(
    body: UploadSessionCreate, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    session, upload_url = await service.create_upload_session(
        db,
        tenant_id,
        filename=body.filename,
        mime_type=body.mime_type,
        size_bytes=body.size_bytes,
        folder_id=body.folder_id,
        asset_id=body.asset_id,
        name=body.name,
    )
    out = UploadSessionOut(
        upload_session_id=session.id,
        upload_url=upload_url,
        headers={"Content-Type": session.mime_type},
        expires_at=session.expires_at,
        asset_id=session.asset_id,
        version_no=session.version_no,
    )
    return success(out.model_dump(mode="json"))


@router.post(
    "/assets/uploads/{session_id}/complete",
    dependencies=[require_permissions("content.create")],
)
async def complete_upload(
    session_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    asset = await service.complete_upload(db, tenant_id, session_id)
    return success(_asset_out(asset))


# --- assets ---


@router.get("/assets", dependencies=[require_permissions("content.view")])
async def list_assets(
    tenant_id: CurrentTenantId,
    pagination: PageParams,
    q: str | None = Query(None, max_length=200),
    type: str | None = Query(None, max_length=20),
    status: str | None = Query(None, max_length=20),
    folder_id: uuid.UUID | None = None,
    tag_key: str | None = Query(None, max_length=100),
    tag_value: str | None = Query(None, max_length=200),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.repositories import content as repo

    assets, total = await repo.search_assets(
        db,
        tenant_id,
        q=q,
        type_=type,
        status=status,
        folder_id=folder_id,
        tag_key=tag_key,
        tag_value=tag_value,
        page=pagination.page,
        page_size=pagination.page_size,
    )
    return success(
        [_asset_out(a) for a in assets],
        page=pagination.page,
        page_size=pagination.page_size,
        total=total,
    )


@router.get("/assets/{asset_id}", dependencies=[require_permissions("content.view")])
async def get_asset(
    asset_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    asset = await service.get_asset(db, tenant_id, asset_id)
    return success(_asset_out(asset))


@router.patch("/assets/{asset_id}", dependencies=[require_permissions("content.edit")])
async def update_asset(
    asset_id: uuid.UUID,
    body: AssetUpdate,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
) -> dict:
    asset = await service.update_asset(
        db,
        tenant_id,
        asset_id,
        name=body.name,
        description=body.description,
        folder_id=body.folder_id,
        clear_folder=body.clear_folder,
        tags=[(t.key, t.value) for t in body.tags] if body.tags is not None else None,
    )
    return success(_asset_out(asset))


@router.get(
    "/assets/{asset_id}/download-url", dependencies=[require_permissions("content.view")]
)
async def get_download_url(
    asset_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    asset = await service.get_asset(db, tenant_id, asset_id)
    url = service.download_url(asset)
    settings = get_settings()
    return success(
        DownloadUrlOut(url=url, expires_in=settings.signed_url_ttl_seconds).model_dump()
    )


@router.get("/assets/{asset_id}/versions", dependencies=[require_permissions("content.view")])
async def list_versions(
    asset_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    asset = await service.get_asset(db, tenant_id, asset_id)
    return success(
        [AssetVersionOut.model_validate(v).model_dump(mode="json") for v in asset.versions]
    )


@router.post(
    "/assets/{asset_id}/versions",
    dependencies=[require_permissions("content.edit")],
    status_code=201,
)
async def create_version_upload(
    asset_id: uuid.UUID,
    body: UploadSessionCreate,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
) -> dict:
    session, upload_url = await service.create_upload_session(
        db,
        tenant_id,
        filename=body.filename,
        mime_type=body.mime_type,
        size_bytes=body.size_bytes,
        asset_id=asset_id,
    )
    out = UploadSessionOut(
        upload_session_id=session.id,
        upload_url=upload_url,
        headers={"Content-Type": session.mime_type},
        expires_at=session.expires_at,
        asset_id=session.asset_id,
        version_no=session.version_no,
    )
    return success(out.model_dump(mode="json"))


@router.post("/assets/{asset_id}/publish", dependencies=[require_permissions("content.edit")])
async def publish_asset(
    asset_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    asset = await service.publish_asset(db, tenant_id, asset_id)
    return success(_asset_out(asset))


@router.post("/assets/{asset_id}/archive", dependencies=[require_permissions("content.delete")])
async def archive_asset(
    asset_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    asset = await service.archive_asset(db, tenant_id, asset_id)
    return success(_asset_out(asset))


@router.post("/assets/{asset_id}/restore", dependencies=[require_permissions("content.delete")])
async def restore_asset(
    asset_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    asset = await service.restore_asset(db, tenant_id, asset_id)
    return success(_asset_out(asset))


# --- folders ---


@router.get("/folders", dependencies=[require_permissions("content.view")])
async def list_folders(tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)) -> dict:
    from app.repositories import content as repo

    folders = await repo.list_folders(db, tenant_id)
    return success([FolderOut.model_validate(f).model_dump(mode="json") for f in folders])


@router.post("/folders", dependencies=[require_permissions("content.create")], status_code=201)
async def create_folder(
    body: FolderCreate, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    folder = await service.create_folder(
        db, tenant_id, name=body.name, parent_id=body.parent_id
    )
    return success(FolderOut.model_validate(folder).model_dump(mode="json"))


@router.patch("/folders/{folder_id}", dependencies=[require_permissions("content.edit")])
async def rename_folder(
    folder_id: uuid.UUID,
    body: FolderUpdate,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
) -> dict:
    folder = await service.rename_folder(db, tenant_id, folder_id, name=body.name)
    return success(FolderOut.model_validate(folder).model_dump(mode="json"))


@router.delete("/folders/{folder_id}", dependencies=[require_permissions("content.delete")])
async def archive_folder(
    folder_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    folder = await service.archive_folder(db, tenant_id, folder_id)
    return success(FolderOut.model_validate(folder).model_dump(mode="json"))
