"""Playlist data access. Tenant-scoped (ADR-002)."""

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Playlist


async def get_by_id(
    db: AsyncSession, organization_id: uuid.UUID, playlist_id: uuid.UUID
) -> Playlist | None:
    result = await db.execute(
        select(Playlist).where(
            Playlist.organization_id == organization_id, Playlist.id == playlist_id
        )
    )
    return result.scalar_one_or_none()


async def search(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    q: str | None,
    status: str | None,
    page: int,
    page_size: int,
) -> tuple[list[Playlist], int]:
    query = select(Playlist).where(Playlist.organization_id == organization_id)
    if q:
        pattern = f"%{q.lower()}%"
        query = query.where(
            or_(
                func.lower(Playlist.name).like(pattern),
                func.lower(Playlist.description).like(pattern),
            )
        )
    if status:
        query = query.where(Playlist.status == status)
    else:
        query = query.where(Playlist.status != "archived")

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    rows = await db.execute(
        query.order_by(Playlist.updated_at.desc(), Playlist.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(rows.scalars().all()), total
