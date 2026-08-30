"""Content data access (folders, assets, versions). Tenant-scoped (ADR-002)."""

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Asset, AssetVersion, Folder, Tag, UploadSession, asset_tags


async def get_folder(
    db: AsyncSession, organization_id: uuid.UUID, folder_id: uuid.UUID
) -> Folder | None:
    result = await db.execute(
        select(Folder).where(Folder.organization_id == organization_id, Folder.id == folder_id)
    )
    return result.scalar_one_or_none()


async def list_folders(db: AsyncSession, organization_id: uuid.UUID) -> list[Folder]:
    result = await db.execute(
        select(Folder)
        .where(Folder.organization_id == organization_id, Folder.status == "active")
        .order_by(Folder.name)
    )
    return list(result.scalars().all())


async def folder_has_children(
    db: AsyncSession, organization_id: uuid.UUID, folder_id: uuid.UUID
) -> bool:
    subfolders = (
        await db.execute(
            select(func.count()).where(
                Folder.organization_id == organization_id,
                Folder.parent_id == folder_id,
                Folder.status == "active",
            )
        )
    ).scalar_one()
    if subfolders:
        return True
    assets = (
        await db.execute(
            select(func.count()).where(
                Asset.organization_id == organization_id,
                Asset.folder_id == folder_id,
                Asset.status != "archived",
            )
        )
    ).scalar_one()
    return bool(assets)


async def get_asset(
    db: AsyncSession, organization_id: uuid.UUID, asset_id: uuid.UUID
) -> Asset | None:
    result = await db.execute(
        select(Asset).where(Asset.organization_id == organization_id, Asset.id == asset_id)
    )
    return result.scalar_one_or_none()


async def search_assets(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    q: str | None,
    type_: str | None,
    status: str | None,
    folder_id: uuid.UUID | None,
    tag_key: str | None,
    tag_value: str | None,
    page: int,
    page_size: int,
) -> tuple[list[Asset], int]:
    query = select(Asset).where(Asset.organization_id == organization_id)
    if q:
        pattern = f"%{q.lower()}%"
        query = query.where(
            or_(
                func.lower(Asset.name).like(pattern),
                func.lower(Asset.description).like(pattern),
            )
        )
    if type_:
        query = query.where(Asset.type == type_)
    if status:
        query = query.where(Asset.status == status)
    else:
        query = query.where(Asset.status != "archived")
    if folder_id:
        query = query.where(Asset.folder_id == folder_id)
    if tag_key:
        tag_query = select(asset_tags.c.asset_id).join(Tag, Tag.id == asset_tags.c.tag_id).where(
            Tag.organization_id == organization_id, Tag.key == tag_key
        )
        if tag_value:
            tag_query = tag_query.where(Tag.value == tag_value)
        query = query.where(Asset.id.in_(tag_query))

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    rows = await db.execute(
        query.order_by(Asset.created_at.desc(), Asset.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(rows.scalars().all()), total


async def get_version(db: AsyncSession, version_id: uuid.UUID) -> AssetVersion | None:
    result = await db.execute(select(AssetVersion).where(AssetVersion.id == version_id))
    return result.scalar_one_or_none()


async def max_version_no(db: AsyncSession, asset_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.coalesce(func.max(AssetVersion.version_no), 0)).where(
            AssetVersion.asset_id == asset_id
        )
    )
    return result.scalar_one()


async def get_upload_session(
    db: AsyncSession, organization_id: uuid.UUID, session_id: uuid.UUID
) -> UploadSession | None:
    result = await db.execute(
        select(UploadSession).where(
            UploadSession.organization_id == organization_id, UploadSession.id == session_id
        )
    )
    return result.scalar_one_or_none()
