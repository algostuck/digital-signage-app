"""Layout data access. Tenant-scoped (ADR-002)."""

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Layout, Template


async def get_by_id(
    db: AsyncSession, organization_id: uuid.UUID, layout_id: uuid.UUID
) -> Layout | None:
    result = await db.execute(
        select(Layout).where(Layout.organization_id == organization_id, Layout.id == layout_id)
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
) -> tuple[list[Layout], int]:
    query = select(Layout).where(Layout.organization_id == organization_id)
    if q:
        pattern = f"%{q.lower()}%"
        query = query.where(
            or_(
                func.lower(Layout.name).like(pattern),
                func.lower(Layout.description).like(pattern),
            )
        )
    if status:
        query = query.where(Layout.status == status)
    else:
        query = query.where(Layout.status != "archived")

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    rows = await db.execute(
        query.order_by(Layout.updated_at.desc(), Layout.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(rows.scalars().all()), total


async def list_templates(db: AsyncSession, organization_id: uuid.UUID) -> list[Template]:
    result = await db.execute(
        select(Template)
        .where(Template.organization_id == organization_id)
        .order_by(Template.name)
    )
    return list(result.scalars().all())


async def get_template(
    db: AsyncSession, organization_id: uuid.UUID, template_id: uuid.UUID
) -> Template | None:
    result = await db.execute(
        select(Template).where(
            Template.organization_id == organization_id, Template.id == template_id
        )
    )
    return result.scalar_one_or_none()


async def get_template_by_name(
    db: AsyncSession, organization_id: uuid.UUID, name: str
) -> Template | None:
    result = await db.execute(
        select(Template).where(
            Template.organization_id == organization_id, Template.name == name
        )
    )
    return result.scalar_one_or_none()
