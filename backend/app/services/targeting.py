"""Campaign target resolution (SRS §12).

Resolve -> deduplicate -> apply exclusions -> validate device status.
Exclusions always win over inclusions. The result is the deterministic device
set frozen into a deployment snapshot at publish time.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CampaignTarget, Device, Location
from app.models.campaign import TargetType
from app.models.device import DeviceStatus, device_tags


async def _devices_for_target(
    db: AsyncSession, organization_id: uuid.UUID, target: CampaignTarget
) -> set[uuid.UUID]:
    if target.target_type == TargetType.DEVICE.value:
        result = await db.execute(
            select(Device.id).where(
                Device.organization_id == organization_id, Device.id == target.target_id
            )
        )
        return set(result.scalars().all())

    if target.target_type == TargetType.GROUP.value:
        from app.repositories import devices as devices_repo
        from app.services import device_ops

        group = await devices_repo.get_group(db, organization_id, target.target_id)
        if group is None:
            return set()
        # Dynamic groups resolve their rule at evaluation time; the publish
        # snapshot still freezes the resulting device set (ADR-005).
        return set(await device_ops.resolve_group_member_ids(db, organization_id, group))

    if target.target_type == TargetType.TAG.value:
        result = await db.execute(
            select(Device.id)
            .join(device_tags, device_tags.c.device_id == Device.id)
            .where(
                Device.organization_id == organization_id,
                device_tags.c.tag_id == target.target_id,
            )
        )
        return set(result.scalars().all())

    if target.target_type == TargetType.LOCATION.value:
        location = (
            await db.execute(
                select(Location).where(
                    Location.organization_id == organization_id,
                    Location.id == target.target_id,
                )
            )
        ).scalar_one_or_none()
        if location is None:
            return set()
        if target.include_descendants:
            location_ids = select(Location.id).where(
                Location.organization_id == organization_id,
                Location.path.like(location.path + "%"),
            )
            result = await db.execute(
                select(Device.id).where(
                    Device.organization_id == organization_id,
                    Device.location_id.in_(location_ids),
                )
            )
        else:
            result = await db.execute(
                select(Device.id).where(
                    Device.organization_id == organization_id,
                    Device.location_id == location.id,
                )
            )
        return set(result.scalars().all())

    return set()


async def resolve_effective_devices(
    db: AsyncSession, organization_id: uuid.UUID, targets: list[CampaignTarget]
) -> list[uuid.UUID]:
    included: set[uuid.UUID] = set()
    excluded: set[uuid.UUID] = set()
    for target in targets:
        devices = await _devices_for_target(db, organization_id, target)
        if target.is_exclusion:
            excluded |= devices
        else:
            included |= devices

    candidates = included - excluded
    if not candidates:
        return []

    result = await db.execute(
        select(Device.id).where(
            Device.organization_id == organization_id,
            Device.id.in_(candidates),
            Device.status == DeviceStatus.ACTIVE.value,
        )
    )
    return sorted(result.scalars().all(), key=str)


async def device_matches_targets(
    db: AsyncSession, organization_id: uuid.UUID, device_id: uuid.UUID, targets: list
) -> bool:
    """True when any (variant) target covers the device. Accepts anything
    with target_type/target_id/include_descendants (shared resolver)."""
    for target in targets:
        if device_id in await _devices_for_target(db, organization_id, target):
            return True
    return False


def snapshot_targets(targets: list[CampaignTarget]) -> dict:
    """Logical target definition preserved for audit (SRS §12)."""
    return {
        "targets": [
            {
                "target_type": t.target_type,
                "target_id": str(t.target_id),
                "include_descendants": t.include_descendants,
                "is_exclusion": t.is_exclusion,
            }
            for t in targets
        ]
    }
