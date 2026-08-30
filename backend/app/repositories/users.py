"""User data access. Every query is tenant-scoped (ADR-002)."""

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User


async def get_by_id(
    db: AsyncSession, organization_id: uuid.UUID, user_id: uuid.UUID
) -> User | None:
    result = await db.execute(
        select(User).where(User.organization_id == organization_id, User.id == user_id)
    )
    return result.scalar_one_or_none()


async def get_by_email(db: AsyncSession, organization_id: uuid.UUID, email: str) -> User | None:
    result = await db.execute(
        select(User).where(
            User.organization_id == organization_id, func.lower(User.email) == email.lower()
        )
    )
    return result.scalar_one_or_none()


async def find_for_login(db: AsyncSession, email: str) -> list[User]:
    """Login is email-first (SCR-01 has no org field); returns all matches
    across tenants — the service disambiguates."""
    result = await db.execute(select(User).where(func.lower(User.email) == email.lower()))
    return list(result.scalars().all())


async def search(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    q: str | None,
    status: str | None,
    page: int,
    page_size: int,
) -> tuple[list[User], int]:
    query = select(User).where(User.organization_id == organization_id)
    if q:
        pattern = f"%{q.lower()}%"
        query = query.where(
            or_(func.lower(User.email).like(pattern), func.lower(User.full_name).like(pattern))
        )
    if status:
        query = query.where(User.status == status)

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    rows = await db.execute(
        query.order_by(User.created_at.desc(), User.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(rows.scalars().all()), total
