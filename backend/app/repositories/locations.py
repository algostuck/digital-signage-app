"""Location hierarchy data access. Every query is tenant-scoped (ADR-002).

Subtree queries use the materialized path (ADR-003).
"""

import uuid

from sqlalchemy import func, literal, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Location, LocationType, Tag


async def get_by_id(
    db: AsyncSession, organization_id: uuid.UUID, location_id: uuid.UUID
) -> Location | None:
    result = await db.execute(
        select(Location).where(
            Location.organization_id == organization_id, Location.id == location_id
        )
    )
    return result.scalar_one_or_none()


async def list_all_active(db: AsyncSession, organization_id: uuid.UUID) -> list[Location]:
    """All non-archived nodes ordered by path — one query for tree assembly."""
    result = await db.execute(
        select(Location)
        .where(Location.organization_id == organization_id, Location.status == "active")
        .order_by(Location.path)
    )
    return list(result.scalars().all())


async def search(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    q: str | None,
    type_id: uuid.UUID | None,
    status: str | None,
    parent_id: uuid.UUID | None,
    page: int,
    page_size: int,
) -> tuple[list[Location], int]:
    query = select(Location).where(Location.organization_id == organization_id)
    if q:
        pattern = f"%{q.lower()}%"
        query = query.where(
            or_(func.lower(Location.name).like(pattern), func.lower(Location.code).like(pattern))
        )
    if type_id:
        query = query.where(Location.type_id == type_id)
    if status:
        query = query.where(Location.status == status)
    if parent_id:
        query = query.where(Location.parent_id == parent_id)

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    rows = await db.execute(
        query.order_by(Location.path).offset((page - 1) * page_size).limit(page_size)
    )
    return list(rows.scalars().all()), total


async def children_of(
    db: AsyncSession, organization_id: uuid.UUID, location_id: uuid.UUID
) -> list[Location]:
    result = await db.execute(
        select(Location)
        .where(Location.organization_id == organization_id, Location.parent_id == location_id)
        .order_by(Location.name)
    )
    return list(result.scalars().all())


async def descendants_of(
    db: AsyncSession,
    organization_id: uuid.UUID,
    node: Location,
    *,
    page: int,
    page_size: int,
    include_archived: bool = False,
) -> tuple[list[Location], int]:
    query = select(Location).where(
        Location.organization_id == organization_id,
        Location.path.like(node.path + "%"),
        Location.id != node.id,
    )
    if not include_archived:
        query = query.where(Location.status == "active")
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    rows = await db.execute(
        query.order_by(Location.path).offset((page - 1) * page_size).limit(page_size)
    )
    return list(rows.scalars().all()), total


async def count_active_children(
    db: AsyncSession, organization_id: uuid.UUID, location_id: uuid.UUID
) -> int:
    result = await db.execute(
        select(func.count()).where(
            Location.organization_id == organization_id,
            Location.parent_id == location_id,
            Location.status == "active",
        )
    )
    return result.scalar_one()


async def rewrite_subtree_paths(
    db: AsyncSession, organization_id: uuid.UUID, old_prefix: str, new_prefix: str
) -> None:
    """Repoints every path in a moved subtree (`old_prefix` -> `new_prefix`).

    `literal(...) + func.substr(...)` renders as string concatenation on both
    PostgreSQL and SQLite.
    """
    await db.execute(
        update(Location)
        .where(
            Location.organization_id == organization_id,
            Location.path.like(old_prefix + "%"),
        )
        .values(
            path=literal(new_prefix) + func.substr(Location.path, len(old_prefix) + 1)
        )
    )


async def get_by_ids(
    db: AsyncSession, organization_id: uuid.UUID, ids: list[uuid.UUID]
) -> list[Location]:
    if not ids:
        return []
    result = await db.execute(
        select(Location).where(
            Location.organization_id == organization_id, Location.id.in_(ids)
        )
    )
    return list(result.scalars().all())


# --- location types ---


async def list_types(db: AsyncSession, organization_id: uuid.UUID) -> list[LocationType]:
    result = await db.execute(
        select(LocationType)
        .where(LocationType.organization_id == organization_id)
        .order_by(LocationType.name)
    )
    return list(result.scalars().all())


async def get_type_by_id(
    db: AsyncSession, organization_id: uuid.UUID, type_id: uuid.UUID
) -> LocationType | None:
    result = await db.execute(
        select(LocationType).where(
            LocationType.organization_id == organization_id, LocationType.id == type_id
        )
    )
    return result.scalar_one_or_none()


async def get_type_by_code(
    db: AsyncSession, organization_id: uuid.UUID, code: str
) -> LocationType | None:
    result = await db.execute(
        select(LocationType).where(
            LocationType.organization_id == organization_id, LocationType.code == code
        )
    )
    return result.scalar_one_or_none()


# --- tags ---


async def list_tags(db: AsyncSession, organization_id: uuid.UUID) -> list[Tag]:
    result = await db.execute(
        select(Tag).where(Tag.organization_id == organization_id).order_by(Tag.key, Tag.value)
    )
    return list(result.scalars().all())


async def get_or_create_tag(
    db: AsyncSession, organization_id: uuid.UUID, key: str, value: str
) -> Tag:
    result = await db.execute(
        select(Tag).where(
            Tag.organization_id == organization_id, Tag.key == key, Tag.value == value
        )
    )
    tag = result.scalar_one_or_none()
    if tag is None:
        tag = Tag(organization_id=organization_id, key=key, value=value)
        db.add(tag)
        await db.flush()
    return tag
