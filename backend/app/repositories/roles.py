"""Role/permission data access. Roles visible to a tenant = system roles
(organization_id NULL) + the tenant's own roles."""

import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Permission, Role


def _visible(organization_id: uuid.UUID):
    return or_(Role.organization_id.is_(None), Role.organization_id == organization_id)


async def list_visible(db: AsyncSession, organization_id: uuid.UUID) -> list[Role]:
    result = await db.execute(
        select(Role).where(_visible(organization_id)).order_by(Role.is_system.desc(), Role.name)
    )
    return list(result.scalars().all())


async def get_visible_by_id(
    db: AsyncSession, organization_id: uuid.UUID, role_id: uuid.UUID
) -> Role | None:
    result = await db.execute(
        select(Role).where(_visible(organization_id), Role.id == role_id)
    )
    return result.scalar_one_or_none()


async def get_visible_by_ids(
    db: AsyncSession, organization_id: uuid.UUID, role_ids: list[uuid.UUID]
) -> list[Role]:
    if not role_ids:
        return []
    result = await db.execute(
        select(Role).where(_visible(organization_id), Role.id.in_(role_ids))
    )
    return list(result.scalars().all())


async def get_org_role_by_name(
    db: AsyncSession, organization_id: uuid.UUID, name: str
) -> Role | None:
    result = await db.execute(
        select(Role).where(Role.organization_id == organization_id, Role.name == name)
    )
    return result.scalar_one_or_none()


async def list_permissions(db: AsyncSession) -> list[Permission]:
    result = await db.execute(select(Permission).order_by(Permission.code))
    return list(result.scalars().all())


async def get_permissions_by_codes(db: AsyncSession, codes: list[str]) -> list[Permission]:
    if not codes:
        return []
    result = await db.execute(select(Permission).where(Permission.code.in_(codes)))
    return list(result.scalars().all())
