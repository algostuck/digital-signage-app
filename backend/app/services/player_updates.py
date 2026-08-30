"""OTA player updates (P2-DEV-004/005): release registry, staged rollout
rings with stop-on-failure, device update offers and rollback.

Rollout mechanics: the target fleet (a device group — static or dynamic —
or every active device) is deterministically ordered and split by the
rings' cumulative percentages. Only the in-progress ring's devices are
offered the update (piggybacked on the heartbeat response — pull-based,
same as publishing per ADR-005). When every device in a ring reaches a
terminal state the ring either completes and activates the next ring, or —
if the failure share exceeds the ring's threshold — stops the whole
rollout, leaving per-device failure reasons as evidence.
"""

import logging
import math
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import (
    BusinessRuleError,
    ConflictError,
    NotFoundError,
    ValidationAppError,
)
from app.models import Asset, Device, PlayerRelease, RolloutBatch, RolloutDevice
from app.models.device import DeviceStatus
from app.models.release import ReleaseState, RolloutBatchState, RolloutDeviceState
from app.repositories import devices as devices_repo
from app.services import audit
from app.services.content import current_version

logger = logging.getLogger("app.player_updates")

MAX_RINGS = 6
DEFAULT_RINGS = (10, 50, 100)
UPDATE_ACK_STATES = ("updating", "succeeded", "failed")


# --- releases ---


async def create_release(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    version: str,
    package_asset_id: uuid.UUID,
    notes: str | None,
) -> PlayerRelease:
    existing = await db.execute(
        select(PlayerRelease.id).where(
            PlayerRelease.organization_id == organization_id,
            PlayerRelease.version == version,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise ConflictError(f"A release with version '{version}' already exists")

    asset = (
        await db.execute(
            select(Asset).where(
                Asset.organization_id == organization_id, Asset.id == package_asset_id
            )
        )
    ).scalar_one_or_none()
    if asset is None:
        raise NotFoundError("Package asset not found")
    package = current_version(asset)
    if package is None or package.processing_status != "ready":
        raise BusinessRuleError("Package asset has no ready version")

    release = PlayerRelease(
        organization_id=organization_id,
        version=version,
        package_asset_id=package_asset_id,
        checksum=package.checksum or "",
        size_bytes=package.size_bytes or 0,
        notes=notes,
        state=ReleaseState.DRAFT.value,
    )
    db.add(release)
    await db.flush()
    await audit.record(
        db,
        organization_id,
        action="RELEASE_CREATED",
        entity_type="player_release",
        entity_id=release.id,
        after={"version": version, "package_asset_id": str(package_asset_id)},
    )
    return release


async def get_release(
    db: AsyncSession, organization_id: uuid.UUID, release_id: uuid.UUID
) -> PlayerRelease:
    release = (
        await db.execute(
            select(PlayerRelease).where(
                PlayerRelease.organization_id == organization_id,
                PlayerRelease.id == release_id,
            )
        )
    ).scalar_one_or_none()
    if release is None:
        raise NotFoundError("Release not found")
    return release


async def list_releases(
    db: AsyncSession, organization_id: uuid.UUID
) -> list[PlayerRelease]:
    rows = await db.execute(
        select(PlayerRelease)
        .where(PlayerRelease.organization_id == organization_id)
        .order_by(PlayerRelease.created_at.desc(), PlayerRelease.id)
    )
    return list(rows.scalars().all())


# --- rollout ---


def _validate_rings(rings: list[int]) -> list[int]:
    if not rings or len(rings) > MAX_RINGS:
        raise ValidationAppError(f"rings must contain 1..{MAX_RINGS} entries", field="rings")
    previous = 0
    for pct in rings:
        if not isinstance(pct, int) or pct <= previous or pct > 100:
            raise ValidationAppError(
                "rings must be strictly increasing percentages up to 100", field="rings"
            )
        previous = pct
    if rings[-1] != 100:
        raise ValidationAppError("the final ring must reach 100%", field="rings")
    return rings


async def _release_batches(
    db: AsyncSession, release_id: uuid.UUID
) -> list[RolloutBatch]:
    rows = await db.execute(
        select(RolloutBatch)
        .where(RolloutBatch.release_id == release_id)
        .order_by(RolloutBatch.ring_no)
    )
    return list(rows.scalars().all())


async def start_rollout(
    db: AsyncSession,
    organization_id: uuid.UUID,
    release_id: uuid.UUID,
    *,
    group_id: uuid.UUID | None,
    rings: list[int] | None,
    failure_threshold_pct: int,
) -> list[RolloutBatch]:
    release = await get_release(db, organization_id, release_id)
    if release.state == ReleaseState.ROLLED_BACK.value:
        raise BusinessRuleError("A rolled-back release cannot be rolled out again")
    if await _release_batches(db, release_id):
        raise BusinessRuleError("This release already has a rollout")
    rings = _validate_rings(list(rings) if rings is not None else list(DEFAULT_RINGS))
    if not 0 <= failure_threshold_pct <= 100:
        raise ValidationAppError(
            "failure_threshold_pct must be 0..100", field="failure_threshold_pct"
        )

    # Resolve the target fleet: a group (static or dynamic) or all devices.
    if group_id is not None:
        group = await devices_repo.get_group(db, organization_id, group_id)
        if group is None:
            raise NotFoundError("Device group not found")
        from app.services import device_ops

        member_ids = await device_ops.resolve_group_member_ids(db, organization_id, group)
        target_filter = Device.id.in_(member_ids) if member_ids else Device.id.is_(None)
    else:
        target_filter = Device.id.isnot(None)
    device_ids = list(
        (
            await db.execute(
                select(Device.id)
                .where(
                    Device.organization_id == organization_id,
                    Device.status == DeviceStatus.ACTIVE.value,
                    target_filter,
                )
                .order_by(Device.id)
            )
        )
        .scalars()
        .all()
    )
    if not device_ids:
        raise BusinessRuleError("The rollout target resolves to no active devices")

    total = len(device_ids)
    batches: list[RolloutBatch] = []
    covered = 0
    now = datetime.now(UTC)
    for index, pct in enumerate(rings, start=1):
        cutoff = total if pct == 100 else min(total, math.ceil(total * pct / 100))
        ring_device_ids = device_ids[covered:cutoff]
        covered = max(covered, cutoff)
        batch = RolloutBatch(
            id=uuid.uuid4(),
            organization_id=organization_id,
            release_id=release.id,
            ring_no=index,
            percentage=pct,
            failure_threshold_pct=failure_threshold_pct,
            state=RolloutBatchState.PENDING.value,
        )
        db.add(batch)
        for device_id in ring_device_ids:
            db.add(
                RolloutDevice(
                    batch_id=batch.id,
                    device_id=device_id,
                    state=RolloutDeviceState.PENDING.value,
                )
            )
        batches.append(batch)

    release.state = ReleaseState.ACTIVE.value
    await db.flush()
    await _activate_next_batch(db, release, batches, now)
    await audit.record(
        db,
        organization_id,
        action="RELEASE_ROLLOUT_STARTED",
        entity_type="player_release",
        entity_id=release.id,
        after={
            "rings": rings,
            "failure_threshold_pct": failure_threshold_pct,
            "total_devices": total,
            "group_id": str(group_id) if group_id else None,
        },
    )
    logger.info(
        "Rollout started for release %s (%s devices, rings %s)", release.version, total, rings
    )
    return await _release_batches(db, release_id)


async def _batch_device_counts(db: AsyncSession, batch_id: uuid.UUID) -> dict[str, int]:
    rows = await db.execute(
        select(RolloutDevice.state, func.count())
        .where(RolloutDevice.batch_id == batch_id)
        .group_by(RolloutDevice.state)
    )
    return dict(rows.all())


async def _activate_next_batch(
    db: AsyncSession,
    release: PlayerRelease,
    ordered_batches: list[RolloutBatch],
    now: datetime,
) -> None:
    """Move the first pending batch to in_progress; empty rings complete
    immediately (a small fleet may not populate every percentage step)."""
    for batch in ordered_batches:
        if batch.state != RolloutBatchState.PENDING.value:
            continue
        counts = await _batch_device_counts(db, batch.id)
        if sum(counts.values()) == 0:
            batch.state = RolloutBatchState.COMPLETED.value
            batch.started_at = now
            batch.completed_at = now
            continue
        batch.state = RolloutBatchState.IN_PROGRESS.value
        batch.started_at = now
        await db.flush()
        return
    await db.flush()


async def record_update_status(
    db: AsyncSession,
    device: Device,
    release_id: uuid.UUID,
    *,
    status: str,
    error: str | None,
) -> RolloutDevice:
    """Player-side progress report for the offered update."""
    if status not in UPDATE_ACK_STATES:
        raise ValidationAppError("status must be updating, succeeded or failed", field="status")
    row = (
        await db.execute(
            select(RolloutDevice)
            .join(RolloutBatch, RolloutBatch.id == RolloutDevice.batch_id)
            .where(
                RolloutBatch.release_id == release_id,
                RolloutBatch.organization_id == device.organization_id,
                RolloutBatch.state == RolloutBatchState.IN_PROGRESS.value,
                RolloutDevice.device_id == device.id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError("No in-progress rollout offers this release to the device")
    release = await get_release(db, device.organization_id, release_id)

    if status == "updating":
        row.state = RolloutDeviceState.UPDATING.value
    elif status == "succeeded":
        row.state = RolloutDeviceState.SUCCEEDED.value
        row.failure_reason = None
        device.player_version = release.version
    else:
        row.state = RolloutDeviceState.FAILED.value
        row.failure_reason = (error or "unspecified failure")[:500]
    await db.flush()
    if status in ("succeeded", "failed"):
        await _recompute_batch(db, release, row.batch_id)
    return row


async def _recompute_batch(
    db: AsyncSession, release: PlayerRelease, batch_id: uuid.UUID
) -> None:
    """Ring completion / stop-on-failure (P2-DEV-005). Row-locked against
    concurrent device acknowledgements, mirroring deployment recompute."""
    batch = (
        await db.execute(
            select(RolloutBatch).where(RolloutBatch.id == batch_id).with_for_update()
        )
    ).scalar_one()
    if batch.state != RolloutBatchState.IN_PROGRESS.value:
        return
    counts = await _batch_device_counts(db, batch_id)
    open_count = counts.get(RolloutDeviceState.PENDING.value, 0) + counts.get(
        RolloutDeviceState.UPDATING.value, 0
    )
    if open_count > 0:
        return
    total = sum(counts.values())
    failed = counts.get(RolloutDeviceState.FAILED.value, 0)
    failed_pct = (failed / total * 100) if total else 0
    now = datetime.now(UTC)
    ordered = await _release_batches(db, release.id)

    from app.services import notifications as notifications_service

    if failed_pct > batch.failure_threshold_pct:
        batch.state = RolloutBatchState.STOPPED.value
        batch.completed_at = now
        for later in ordered:
            if later.state == RolloutBatchState.PENDING.value:
                later.state = RolloutBatchState.STOPPED.value
        await db.flush()
        await audit.record(
            db,
            release.organization_id,
            action="RELEASE_ROLLOUT_STOPPED",
            entity_type="player_release",
            entity_id=release.id,
            after={
                "ring_no": batch.ring_no,
                "failed": failed,
                "total": total,
                "failure_threshold_pct": batch.failure_threshold_pct,
            },
        )
        await notifications_service.create(
            db,
            release.organization_id,
            type="ROLLOUT_STOPPED",
            severity="critical",
            title=f"Rollout of player {release.version} stopped at ring {batch.ring_no}",
            message=(
                f"{failed} of {total} devices failed "
                f"(threshold {batch.failure_threshold_pct}%). Later rings were halted."
            ),
            payload={"release_id": str(release.id), "batch_id": str(batch.id)},
        )
        logger.warning(
            "Rollout %s stopped at ring %s: %s/%s failed", release.version, batch.ring_no,
            failed, total,
        )
        return

    batch.state = RolloutBatchState.COMPLETED.value
    batch.completed_at = now
    await db.flush()
    await _activate_next_batch(db, release, ordered, now)
    if all(
        b.state in (RolloutBatchState.COMPLETED.value, RolloutBatchState.STOPPED.value)
        for b in await _release_batches(db, release.id)
    ):
        await notifications_service.create(
            db,
            release.organization_id,
            type="ROLLOUT_COMPLETED",
            severity="info",
            title=f"Player release {release.version} rolled out",
            message="Every ring completed within its failure threshold.",
            payload={"release_id": str(release.id)},
        )


async def rollback_release(
    db: AsyncSession, organization_id: uuid.UUID, release_id: uuid.UUID
) -> PlayerRelease:
    """Halts the rollout and withdraws the update offer (P2-05 rollback
    state). Downgrading devices that already updated is done by rolling out
    a new release carrying the previous package — never an implicit push."""
    release = await get_release(db, organization_id, release_id)
    if release.state != ReleaseState.ACTIVE.value:
        raise BusinessRuleError("Only active releases can be rolled back")
    release.state = ReleaseState.ROLLED_BACK.value
    now = datetime.now(UTC)
    for batch in await _release_batches(db, release_id):
        if batch.state in (
            RolloutBatchState.PENDING.value,
            RolloutBatchState.IN_PROGRESS.value,
        ):
            batch.state = RolloutBatchState.STOPPED.value
            batch.completed_at = now
    await db.flush()
    await audit.record(
        db,
        organization_id,
        action="RELEASE_ROLLED_BACK",
        entity_type="player_release",
        entity_id=release.id,
        after={"version": release.version},
    )

    from app.services import notifications as notifications_service

    await notifications_service.create(
        db,
        organization_id,
        type="ROLLOUT_ROLLED_BACK",
        severity="warning",
        title=f"Player release {release.version} rolled back",
        message="The rollout was halted and the update is no longer offered.",
        payload={"release_id": str(release.id)},
    )
    return release


# --- device-facing offer ---


async def pending_update_for_device(db: AsyncSession, device: Device) -> dict | None:
    """The update offered to this device right now, or None. Only devices in
    the in-progress ring of an active release see the offer."""
    row = (
        await db.execute(
            select(RolloutDevice, PlayerRelease)
            .join(RolloutBatch, RolloutBatch.id == RolloutDevice.batch_id)
            .join(PlayerRelease, PlayerRelease.id == RolloutBatch.release_id)
            .where(
                RolloutDevice.device_id == device.id,
                RolloutDevice.state.in_(
                    [RolloutDeviceState.PENDING.value, RolloutDeviceState.UPDATING.value]
                ),
                RolloutBatch.state == RolloutBatchState.IN_PROGRESS.value,
                PlayerRelease.state == ReleaseState.ACTIVE.value,
                PlayerRelease.organization_id == device.organization_id,
            )
            .order_by(PlayerRelease.created_at.desc())
            .limit(1)
        )
    ).first()
    if row is None:
        return None
    _, release = row
    asset = (
        await db.execute(select(Asset).where(Asset.id == release.package_asset_id))
    ).scalar_one_or_none()
    package = current_version(asset) if asset else None
    if package is None:
        return None
    from app.integrations.storage import get_storage

    settings = get_settings()
    return {
        "release_id": str(release.id),
        "version": release.version,
        "url": get_storage().presigned_get_url(
            package.object_key, settings.signed_url_ttl_seconds
        ),
        "sha256": release.checksum,
        "size_bytes": release.size_bytes,
    }


# --- progress reads ---


async def rollout_progress(
    db: AsyncSession, organization_id: uuid.UUID, release_id: uuid.UUID
) -> list[dict]:
    release = await get_release(db, organization_id, release_id)
    batches = await _release_batches(db, release.id)
    out = []
    for batch in batches:
        counts = await _batch_device_counts(db, batch.id)
        out.append(
            {
                "id": str(batch.id),
                "ring_no": batch.ring_no,
                "percentage": batch.percentage,
                "failure_threshold_pct": batch.failure_threshold_pct,
                "state": batch.state,
                "started_at": batch.started_at.isoformat() if batch.started_at else None,
                "completed_at": batch.completed_at.isoformat() if batch.completed_at else None,
                "devices": {
                    "total": sum(counts.values()),
                    "pending": counts.get(RolloutDeviceState.PENDING.value, 0),
                    "updating": counts.get(RolloutDeviceState.UPDATING.value, 0),
                    "succeeded": counts.get(RolloutDeviceState.SUCCEEDED.value, 0),
                    "failed": counts.get(RolloutDeviceState.FAILED.value, 0),
                },
            }
        )
    return out


async def batch_devices(
    db: AsyncSession, organization_id: uuid.UUID, batch_id: uuid.UUID
) -> list[dict]:
    batch = (
        await db.execute(
            select(RolloutBatch).where(
                RolloutBatch.organization_id == organization_id, RolloutBatch.id == batch_id
            )
        )
    ).scalar_one_or_none()
    if batch is None:
        raise NotFoundError("Rollout ring not found")
    rows = await db.execute(
        select(RolloutDevice, Device.name)
        .join(Device, Device.id == RolloutDevice.device_id)
        .where(RolloutDevice.batch_id == batch_id)
        .order_by(Device.name)
    )
    return [
        {
            "device_id": str(row.device_id),
            "device_name": name,
            "state": row.state,
            "failure_reason": row.failure_reason,
        }
        for row, name in rows.all()
    ]
