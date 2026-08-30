"""Device data access. Tenant-scoped (ADR-002)."""

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Device, DeviceCommand, DeviceGroup, Location


async def get_by_id(
    db: AsyncSession, organization_id: uuid.UUID, device_id: uuid.UUID
) -> Device | None:
    result = await db.execute(
        select(Device).where(Device.organization_id == organization_id, Device.id == device_id)
    )
    return result.scalar_one_or_none()


async def get_by_serial(
    db: AsyncSession, organization_id: uuid.UUID, serial_no: str
) -> Device | None:
    result = await db.execute(
        select(Device).where(
            Device.organization_id == organization_id, Device.serial_no == serial_no
        )
    )
    return result.scalar_one_or_none()


async def get_by_token_hash(db: AsyncSession, token_hash: str) -> Device | None:
    result = await db.execute(select(Device).where(Device.token_hash == token_hash))
    return result.scalar_one_or_none()


async def search(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    q: str | None,
    status: str | None,
    platform: str | None,
    group_id: uuid.UUID | None,
    location: Location | None,
    include_descendants: bool,
    page: int,
    page_size: int,
) -> tuple[list[Device], int]:
    query = select(Device).where(Device.organization_id == organization_id)
    if q:
        pattern = f"%{q.lower()}%"
        query = query.where(
            or_(
                func.lower(Device.name).like(pattern),
                func.lower(Device.serial_no).like(pattern),
                func.lower(Device.model).like(pattern),
            )
        )
    if status:
        query = query.where(Device.status == status)
    if platform:
        query = query.where(Device.platform == platform)
    if group_id:
        query = query.where(Device.group_id == group_id)
    if location is not None:
        if include_descendants:
            subtree = select(Location.id).where(
                Location.organization_id == organization_id,
                Location.path.like(location.path + "%"),
            )
            query = query.where(Device.location_id.in_(subtree))
        else:
            query = query.where(Device.location_id == location.id)

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    rows = await db.execute(
        query.order_by(Device.created_at.desc(), Device.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(rows.scalars().all()), total


async def get_by_ids(
    db: AsyncSession, organization_id: uuid.UUID, ids: list[uuid.UUID]
) -> list[Device]:
    if not ids:
        return []
    result = await db.execute(
        select(Device).where(Device.organization_id == organization_id, Device.id.in_(ids))
    )
    return list(result.scalars().all())


# --- groups ---


async def list_groups(db: AsyncSession, organization_id: uuid.UUID) -> list[DeviceGroup]:
    result = await db.execute(
        select(DeviceGroup)
        .where(DeviceGroup.organization_id == organization_id)
        .order_by(DeviceGroup.name)
    )
    return list(result.scalars().all())


async def get_group(
    db: AsyncSession, organization_id: uuid.UUID, group_id: uuid.UUID
) -> DeviceGroup | None:
    result = await db.execute(
        select(DeviceGroup).where(
            DeviceGroup.organization_id == organization_id, DeviceGroup.id == group_id
        )
    )
    return result.scalar_one_or_none()


async def get_group_by_name(
    db: AsyncSession, organization_id: uuid.UUID, name: str
) -> DeviceGroup | None:
    result = await db.execute(
        select(DeviceGroup).where(
            DeviceGroup.organization_id == organization_id, DeviceGroup.name == name
        )
    )
    return result.scalar_one_or_none()


async def count_group_members(
    db: AsyncSession, organization_id: uuid.UUID, group_id: uuid.UUID
) -> int:
    result = await db.execute(
        select(func.count()).where(
            Device.organization_id == organization_id, Device.group_id == group_id
        )
    )
    return result.scalar_one()


# --- commands ---


async def list_commands(
    db: AsyncSession,
    organization_id: uuid.UUID,
    device_id: uuid.UUID,
    *,
    limit: int = 50,
) -> list[DeviceCommand]:
    result = await db.execute(
        select(DeviceCommand)
        .where(
            DeviceCommand.organization_id == organization_id,
            DeviceCommand.device_id == device_id,
        )
        .order_by(DeviceCommand.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def queued_commands(db: AsyncSession, device_id: uuid.UUID) -> list[DeviceCommand]:
    result = await db.execute(
        select(DeviceCommand)
        .where(DeviceCommand.device_id == device_id, DeviceCommand.status == "queued")
        .order_by(DeviceCommand.created_at)
    )
    return list(result.scalars().all())


async def get_command(
    db: AsyncSession, device_id: uuid.UUID, command_id: uuid.UUID
) -> DeviceCommand | None:
    result = await db.execute(
        select(DeviceCommand).where(
            DeviceCommand.device_id == device_id, DeviceCommand.id == command_id
        )
    )
    return result.scalar_one_or_none()
