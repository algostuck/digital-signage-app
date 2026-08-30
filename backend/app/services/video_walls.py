"""Video wall service (P3-M04, slice 3C-1).

Walls group existing devices behind a shared canvas; sync sessions hand
every member the same (session_id, start_epoch_ms, tolerance_ms) marker via
the manifest `sync` block — clock discipline is the player's job, the
platform's job is a consistent marker + degraded-state honesty:

    all members healthy → SYNCING
    any member offline while a session runs → DEGRADED + incident
    (members keep playing standalone — never a blank screen)
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import (
    BusinessRuleError,
    ConflictError,
    NotFoundError,
    ValidationAppError,
)
from app.models import Device, VideoWall, VideoWallMember
from app.models.device import DeviceStatus
from app.models.video_wall import VideoWallStatus

logger = logging.getLogger("app.video_walls")

DEFAULT_SYNC_POLICY = {"tolerance_ms": 50, "start_delay_ms": 5000}
MAX_MEMBERS = 32


def _validate_canvas(canvas: dict) -> dict:
    merged = {"width": 3840, "height": 2160, "rows": 1, "cols": 2, **(canvas or {})}
    for key in ("width", "height", "rows", "cols"):
        value = merged.get(key)
        if not isinstance(value, int) or value < 1 or value > 32768:
            raise ValidationAppError(f"canvas.{key} must be a positive integer", field="canvas")
    return merged


def _validate_viewport(viewport: dict, canvas: dict) -> dict:
    if not isinstance(viewport, dict) or not {"x", "y", "width", "height"} <= set(viewport):
        raise ValidationAppError('viewport needs {"x","y","width","height"}', field="viewport")
    for key in ("x", "y", "width", "height"):
        if not isinstance(viewport[key], int) or viewport[key] < 0:
            raise ValidationAppError(f"viewport.{key} must be a non-negative int",
                                     field="viewport")
    if (
        viewport["x"] + viewport["width"] > canvas["width"]
        or viewport["y"] + viewport["height"] > canvas["height"]
    ):
        raise ValidationAppError("viewport exceeds the wall canvas", field="viewport")
    return {k: viewport[k] for k in ("x", "y", "width", "height")}


async def get_wall(
    db: AsyncSession, organization_id: uuid.UUID, wall_id: uuid.UUID
) -> VideoWall:
    wall = (
        await db.execute(
            select(VideoWall).where(
                VideoWall.organization_id == organization_id, VideoWall.id == wall_id
            )
        )
    ).scalar_one_or_none()
    if wall is None:
        raise NotFoundError("Video wall not found")
    return wall


async def list_walls(db: AsyncSession, organization_id: uuid.UUID) -> list[VideoWall]:
    rows = await db.execute(
        select(VideoWall)
        .where(VideoWall.organization_id == organization_id)
        .order_by(VideoWall.name)
    )
    return list(rows.scalars().all())


async def create_wall(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    name: str,
    canvas: dict | None = None,
    sync_policy: dict | None = None,
    user_id: uuid.UUID | None = None,
) -> VideoWall:
    from app.services import entitlements

    await entitlements.require_feature(db, organization_id, "video_wall")
    exists = (
        await db.execute(
            select(VideoWall).where(
                VideoWall.organization_id == organization_id, VideoWall.name == name
            )
        )
    ).scalar_one_or_none()
    if exists is not None:
        raise ConflictError("A wall with this name already exists", field="name")
    policy = {**DEFAULT_SYNC_POLICY, **(sync_policy or {})}
    tolerance = policy.get("tolerance_ms")
    if not isinstance(tolerance, int) or not 10 <= tolerance <= 5000:
        raise ValidationAppError("tolerance_ms must be 10..5000", field="sync_policy")
    wall = VideoWall(
        organization_id=organization_id,
        name=name,
        canvas_json=_validate_canvas(canvas or {}),
        sync_policy_json=policy,
    )
    db.add(wall)
    await db.flush()
    await db.refresh(wall, ["members"])

    from app.services import audit

    await audit.record(
        db, organization_id, action="VIDEO_WALL_CREATED",
        entity_type="video_wall", entity_id=wall.id,
        after={"name": name}, user_id=user_id,
    )
    return wall


async def delete_wall(
    db: AsyncSession, organization_id: uuid.UUID, wall_id: uuid.UUID
) -> None:
    wall = await get_wall(db, organization_id, wall_id)
    if wall.status == VideoWallStatus.SYNCING.value:
        raise BusinessRuleError("Stop the sync session before deleting the wall")
    await db.delete(wall)
    await db.flush()


async def add_member(
    db: AsyncSession,
    organization_id: uuid.UUID,
    wall_id: uuid.UUID,
    *,
    device_id: uuid.UUID,
    viewport: dict,
    role: str = "member",
) -> VideoWall:
    wall = await get_wall(db, organization_id, wall_id)
    if len(wall.members) >= MAX_MEMBERS:
        raise BusinessRuleError(f"At most {MAX_MEMBERS} members per wall")
    if role not in ("leader", "member"):
        raise ValidationAppError("role must be leader or member", field="role")
    device = (
        await db.execute(
            select(Device).where(
                Device.organization_id == organization_id, Device.id == device_id
            )
        )
    ).scalar_one_or_none()
    if device is None:
        raise NotFoundError("Device not found")
    if device.status != DeviceStatus.ACTIVE.value:
        raise BusinessRuleError("Only active devices can join a wall")
    other = (
        await db.execute(
            select(VideoWallMember)
            .join(VideoWall, VideoWall.id == VideoWallMember.wall_id)
            .where(
                VideoWallMember.device_id == device_id,
                VideoWall.status != VideoWallStatus.ARCHIVED.value,
            )
        )
    ).scalars().first()
    if other is not None:
        raise ConflictError("This device already belongs to a wall")
    db.add(
        VideoWallMember(
            wall_id=wall.id,
            device_id=device_id,
            viewport_json=_validate_viewport(viewport, wall.canvas_json),
            role=role,
        )
    )
    await db.flush()
    await db.refresh(wall, ["members"])
    return wall


async def remove_member(
    db: AsyncSession, organization_id: uuid.UUID, wall_id: uuid.UUID, member_id: uuid.UUID
) -> VideoWall:
    wall = await get_wall(db, organization_id, wall_id)
    member = next((m for m in wall.members if m.id == member_id), None)
    if member is None:
        raise NotFoundError("Wall member not found")
    await db.delete(member)
    await db.flush()
    await db.refresh(wall, ["members"])
    return wall


async def _member_health(db: AsyncSession, wall: VideoWall) -> list[dict]:
    from app.services.organization import get_monitoring_thresholds

    thresholds = await get_monitoring_thresholds(db, wall.organization_id)
    cutoff = datetime.now(UTC) - timedelta(seconds=thresholds["offline_after_seconds"])
    health = []
    for member in wall.members:
        device = await db.get(Device, member.device_id)
        last = device.last_heartbeat_at if device else None
        last = last if (last is None or last.tzinfo) else last.replace(tzinfo=UTC)
        health.append(
            {
                "member_id": str(member.id),
                "device_id": str(member.device_id),
                "device_name": device.name if device else None,
                "viewport": member.viewport_json,
                "role": member.role,
                "online": last is not None and last > cutoff,
            }
        )
    return health


async def wall_state(db: AsyncSession, organization_id: uuid.UUID, wall_id: uuid.UUID) -> dict:
    """Live state incl. member health; a running session with unhealthy
    members flips to DEGRADED and opens one incident per episode."""
    wall = await get_wall(db, organization_id, wall_id)
    health = await _member_health(db, wall)
    offline = [h for h in health if not h["online"]]
    if wall.status in (VideoWallStatus.SYNCING.value, VideoWallStatus.DEGRADED.value):
        new_status = (
            VideoWallStatus.DEGRADED.value if offline else VideoWallStatus.SYNCING.value
        )
        if new_status != wall.status:
            wall.status = new_status
            await db.flush()
            if offline:
                from app.services import device_ops

                await device_ops.open_incident_if_absent(
                    db,
                    organization_id,
                    device_id=uuid.UUID(offline[0]["device_id"]),
                    type="wall_degraded",
                    severity="warning",
                    title=f"Video wall '{wall.name}' is degraded "
                    f"({len(offline)} member(s) offline)",
                    payload={"wall_id": str(wall.id)},
                )
                logger.warning("Wall %s degraded: %s offline", wall.id, len(offline))
    return {
        "id": str(wall.id),
        "name": wall.name,
        "status": wall.status,
        "canvas": wall.canvas_json,
        "sync_policy": wall.sync_policy_json,
        "session": {
            "id": str(wall.session_id),
            "started_at": wall.session_started_at.isoformat()
            if wall.session_started_at
            else None,
            "start_epoch_ms": wall.session_epoch_ms,
        }
        if wall.session_id
        else None,
        "members": health,
    }


async def sync(
    db: AsyncSession,
    organization_id: uuid.UUID,
    wall_id: uuid.UUID,
    *,
    action: str,
    user_id: uuid.UUID | None = None,
) -> dict:
    wall = await get_wall(db, organization_id, wall_id)
    now = datetime.now(UTC)
    if action == "start":
        if not wall.members:
            raise BusinessRuleError("Add members before starting a sync session")
        wall.session_id = uuid.uuid4()
        wall.session_started_at = now
        wall.session_epoch_ms = int(now.timestamp() * 1000) + int(
            wall.sync_policy_json.get("start_delay_ms", 5000)
        )
        wall.status = VideoWallStatus.SYNCING.value
    elif action == "stop":
        if wall.session_id is None:
            raise BusinessRuleError("No sync session is running")
        wall.session_id = None
        wall.session_started_at = None
        wall.session_epoch_ms = None
        wall.status = VideoWallStatus.IDLE.value
    else:
        raise ValidationAppError("action must be start or stop", field="action")
    await db.flush()

    from app.services import audit

    await audit.record(
        db, organization_id, action=f"VIDEO_WALL_SYNC_{action.upper()}",
        entity_type="video_wall", entity_id=wall.id, user_id=user_id,
    )
    logger.info("Wall %s sync %s", wall.id, action)
    return await wall_state(db, organization_id, wall_id)


async def sync_block_for_device(db: AsyncSession, device: Device) -> dict | None:
    """Manifest contract-v2 `sync` block for a wall member with a running
    session; None otherwise (v1 players and non-members are unaffected)."""
    row = (
        await db.execute(
            select(VideoWallMember, VideoWall)
            .join(VideoWall, VideoWall.id == VideoWallMember.wall_id)
            .where(
                VideoWallMember.device_id == device.id,
                VideoWall.session_id.is_not(None),
                VideoWall.status.in_(
                    [VideoWallStatus.SYNCING.value, VideoWallStatus.DEGRADED.value]
                ),
            )
        )
    ).first()
    if row is None:
        return None
    member, wall = row
    return {
        "wall_id": str(wall.id),
        "session": str(wall.session_id),
        "start_epoch_ms": wall.session_epoch_ms,
        "tolerance_ms": wall.sync_policy_json.get("tolerance_ms", 50),
        "canvas": wall.canvas_json,
        "viewport": member.viewport_json,
        "role": member.role,
        "degraded": wall.status == VideoWallStatus.DEGRADED.value,
    }
