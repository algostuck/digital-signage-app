"""Device management + player enrollment service (M04, FR-DEV-001..008).

Enrollment flow (approval-gated, credential shown exactly once):
  register(enrollment_key, serial) -> PENDING
  admin approves -> device polls register again -> opaque token issued once
  (SHA-256 digest stored); admin can reset-token to revoke and reissue.
"""

import logging
import secrets
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.core.config import get_settings
from app.core.errors import (
    BusinessRuleError,
    ConflictError,
    NotFoundError,
    UnauthenticatedError,
)
from app.models import Device, DeviceCapability, DeviceCommand, DeviceGroup, DeviceHeartbeat
from app.models.device import CommandStatus, DeviceStatus
from app.repositories import devices as repo
from app.repositories import locations as locations_repo
from app.services.organization import validate_timezone

logger = logging.getLogger("app.devices")


def _now() -> datetime:
    return datetime.now(UTC)


def _as_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def connection_status(
    device: Device, now: datetime | None = None, thresholds: dict | None = None
) -> str:
    """Derived health state (FR-DEV-006/FR-MON-006) — never persisted.
    `thresholds` carries the tenant's overrides (P2-MON-002); platform
    defaults apply otherwise."""
    if device.status != DeviceStatus.ACTIVE.value:
        return "n/a"
    if device.last_heartbeat_at is None:
        return "offline"
    settings = get_settings()
    thresholds = thresholds or {}
    warning_after = thresholds.get(
        "warning_after_seconds", settings.device_warning_after_seconds
    )
    offline_after = thresholds.get(
        "offline_after_seconds", settings.device_offline_after_seconds
    )
    age = ((now or _now()) - _as_utc(device.last_heartbeat_at)).total_seconds()
    if age <= warning_after:
        return "online"
    if age <= offline_after:
        return "warning"
    return "offline"


# --- enrollment / player auth ---


async def _org_by_enrollment_key(db: AsyncSession, enrollment_key: str):
    from app.models import Organization

    result = await db.execute(
        select(Organization).where(
            Organization.enrollment_key == enrollment_key,
            Organization.status == "active",
        )
    )
    org = result.scalar_one_or_none()
    if org is None:
        raise UnauthenticatedError("Unknown enrollment key")
    return org


async def register_device(
    db: AsyncSession,
    *,
    enrollment_key: str,
    serial_no: str,
    name: str | None = None,
    manufacturer: str | None = None,
    model: str | None = None,
    platform: str | None = None,
    os_version: str | None = None,
    player_version: str | None = None,
    mac_address: str | None = None,
    screen_width: int | None = None,
    screen_height: int | None = None,
) -> tuple[Device, str | None]:
    """Idempotent by (org, serial). Returns (device, token-or-None); the token
    is returned exactly once, on the first poll after approval."""
    org = await _org_by_enrollment_key(db, enrollment_key)
    device = await repo.get_by_serial(db, org.id, serial_no)

    if device is None:
        from app.services.tenant_admin import ensure_device_quota

        await ensure_device_quota(db, org.id)  # P2-TNT-002
        device = Device(
            organization_id=org.id,
            serial_no=serial_no,
            name=name or serial_no,
            manufacturer=manufacturer,
            model=model,
            platform=platform,
            os_version=os_version,
            player_version=player_version,
            mac_address=mac_address,
            screen_width=screen_width,
            screen_height=screen_height,
            status=DeviceStatus.PENDING.value,
        )
        db.add(device)
        await db.flush()
        await db.refresh(device, ["group", "tags", "capabilities"])

        from app.services import audit, notifications

        await audit.record(
            db,
            org.id,
            action="DEVICE_REGISTRATION_REQUESTED",
            entity_type="device",
            entity_id=device.id,
            after={"serial_no": serial_no, "platform": platform},
        )
        await notifications.create(
            db,
            org.id,
            type="DEVICE_REGISTRATION",
            title=f"Device '{device.name}' requests registration",
            message="Approve or reject it on the Devices page.",
            payload={"device_id": str(device.id)},
        )

        from app.services import events

        await events.emit(
            db,
            org.id,
            event_type="device.registered",
            entity_type="device",
            entity_id=device.id,
            payload={"serial_no": serial_no, "platform": platform},
        )
        logger.info("Device registration requested: %s (%s)", device.id, serial_no)
        return device, None

    if device.status == DeviceStatus.ACTIVE.value and device.token_hash is None:
        token = secrets.token_urlsafe(32)
        device.token_hash = security.hash_token(token)
        device.token_issued_at = _now()
        await db.flush()

        # Credential lifecycle record (P3 3E-3) — fingerprint only.
        from app.services.security_center import record_issuance

        await record_issuance(db, device)
        logger.info("Device credential issued: %s", device.id)
        return device, token

    return device, None


async def authenticate_device(db: AsyncSession, token: str | None) -> Device:
    if not token:
        raise UnauthenticatedError("Missing device token")
    device = await repo.get_by_token_hash(db, security.hash_token(token))
    if device is None:
        raise UnauthenticatedError("Invalid device token")
    if device.status != DeviceStatus.ACTIVE.value:
        raise UnauthenticatedError("Device is not active")
    return device


async def record_heartbeat(
    db: AsyncSession, device: Device, *, payload: dict, ip_address: str | None
) -> dict:
    device.last_heartbeat_at = _now()
    device.last_heartbeat_json = payload
    if ip_address:
        device.ip_address = ip_address
    if payload.get("player_version"):
        device.player_version = str(payload["player_version"])[:50]
    if payload.get("os_version"):
        device.os_version = str(payload["os_version"])[:50]
    db.add(DeviceHeartbeat(device_id=device.id, observed_at=device.last_heartbeat_at,
                           payload_json=payload))
    await db.flush()

    # Recovery: a heartbeat closes any open offline incident (P2 acceptance:
    # offline -> notification -> recovery -> incident auto-resolves).
    from app.services import device_ops
    from app.services import notifications as notifications_service

    resolved = await device_ops.resolve_device_incidents(
        db,
        device.organization_id,
        device.id,
        type="device_offline",
        resolution="Device sent a heartbeat",
    )
    if resolved:
        await notifications_service.create(
            db,
            device.organization_id,
            type="DEVICE_RECOVERED",
            title=f"Device '{device.name}' is back online",
            payload={"device_id": str(device.id)},
        )

    # Storage threshold (P2-MON-002): open one incident per episode while
    # usage stays above the tenant's limit; auto-resolve when it drops.
    used_percent = (payload.get("storage") or {}).get("used_percent")
    if isinstance(used_percent, int | float):
        from app.services.organization import get_monitoring_thresholds

        thresholds = await get_monitoring_thresholds(db, device.organization_id)
        if used_percent >= thresholds["storage_alert_percent"]:
            incident = await device_ops.open_incident_if_absent(
                db,
                device.organization_id,
                device_id=device.id,
                type="device_storage",
                severity="warning",
                title=f"Device '{device.name}' storage at {used_percent:.0f}%",
                payload={"used_percent": used_percent},
            )
            if incident is not None:
                await notifications_service.create(
                    db,
                    device.organization_id,
                    type="DEVICE_STORAGE",
                    severity="warning",
                    title=f"Device '{device.name}' storage at {used_percent:.0f}%",
                    message=f"Above the {thresholds['storage_alert_percent']}% threshold.",
                    payload={"device_id": str(device.id), "incident_id": str(incident.id)},
                )
        else:
            await device_ops.resolve_device_incidents(
                db,
                device.organization_id,
                device.id,
                type="device_storage",
                resolution=f"Storage back at {used_percent:.0f}%",
            )

    queued = await repo.queued_commands(db, device.id)
    settings = get_settings()
    return {
        "acknowledged": True,
        "heartbeat_interval_seconds": settings.device_heartbeat_interval_seconds,
        "pending_commands": len(queued),
        "sync_required": False,  # becomes deployment-aware in milestone 1I
    }


async def set_capabilities(
    db: AsyncSession, device: Device, capabilities: list[tuple[str, bool, dict | None]]
) -> Device:
    # Delete-then-insert in two flushes: a single flush would insert the new
    # rows before removing orphans and trip the (device, code) unique key.
    device.capabilities.clear()
    await db.flush()
    device.capabilities.extend(
        DeviceCapability(
            device_id=device.id, capability_code=code, supported=supported, value_json=value
        )
        for code, supported, value in capabilities
    )
    await db.flush()
    return device


async def poll_commands(db: AsyncSession, device: Device) -> list[DeviceCommand]:
    commands = await repo.queued_commands(db, device.id)
    for command in commands:
        command.status = CommandStatus.SENT.value
        command.sent_at = _now()
    await db.flush()
    return commands


async def acknowledge_command(
    db: AsyncSession, device: Device, command_id: uuid.UUID, *, success: bool, result: dict | None
) -> DeviceCommand:
    command = await repo.get_command(db, device.id, command_id)
    if command is None:
        raise NotFoundError("Command not found")
    if command.status not in (CommandStatus.SENT.value, CommandStatus.QUEUED.value):
        raise ConflictError("Command is not awaiting acknowledgement")
    command.status = CommandStatus.ACKNOWLEDGED.value if success else CommandStatus.FAILED.value
    command.acknowledged_at = _now()
    command.result_json = result
    await db.flush()
    return command


# --- admin operations ---


async def get_device(db: AsyncSession, organization_id: uuid.UUID, device_id: uuid.UUID) -> Device:
    device = await repo.get_by_id(db, organization_id, device_id)
    if device is None:
        raise NotFoundError("Device not found")
    return device


async def approve_device(
    db: AsyncSession, organization_id: uuid.UUID, device_id: uuid.UUID
) -> Device:
    device = await get_device(db, organization_id, device_id)
    if device.status not in (DeviceStatus.PENDING.value, DeviceStatus.REJECTED.value):
        raise BusinessRuleError("Only pending or rejected devices can be approved")
    device.status = DeviceStatus.ACTIVE.value
    device.approved_at = _now()
    await db.flush()
    from app.services import audit

    await audit.record(
        db, organization_id, action="DEVICE_APPROVED", entity_type="device", entity_id=device.id
    )

    from app.services import events

    await events.emit(
        db,
        organization_id,
        event_type="device.approved",
        entity_type="device",
        entity_id=device.id,
        payload={"serial_no": device.serial_no},
    )
    logger.info("Device approved: %s", device.id)
    return device


async def reject_device(
    db: AsyncSession, organization_id: uuid.UUID, device_id: uuid.UUID
) -> Device:
    device = await get_device(db, organization_id, device_id)
    if device.status != DeviceStatus.PENDING.value:
        raise BusinessRuleError("Only pending devices can be rejected")
    device.status = DeviceStatus.REJECTED.value
    await db.flush()
    return device


async def decommission_device(
    db: AsyncSession, organization_id: uuid.UUID, device_id: uuid.UUID
) -> Device:
    device = await get_device(db, organization_id, device_id)
    device.status = DeviceStatus.DECOMMISSIONED.value
    device.token_hash = None  # credential revoked immediately (SRS §16)
    await db.flush()
    from app.services import audit

    await audit.record(
        db,
        organization_id,
        action="DEVICE_DECOMMISSIONED",
        entity_type="device",
        entity_id=device.id,
    )
    logger.info("Device decommissioned: %s", device.id)
    return device


async def reset_device_token(
    db: AsyncSession, organization_id: uuid.UUID, device_id: uuid.UUID
) -> Device:
    """Revokes the credential; the device re-obtains one via register polling."""
    device = await get_device(db, organization_id, device_id)
    if device.status != DeviceStatus.ACTIVE.value:
        raise BusinessRuleError("Only active devices can have credentials reset")
    device.token_hash = None
    device.token_issued_at = None
    await db.flush()
    return device


async def update_device(
    db: AsyncSession,
    organization_id: uuid.UUID,
    device_id: uuid.UUID,
    *,
    name: str | None = None,
    group_id: uuid.UUID | None = None,
    clear_group: bool = False,
    timezone: str | None = None,
    orientation: str | None = None,
    tags: list[tuple[str, str]] | None = None,
) -> Device:
    device = await get_device(db, organization_id, device_id)
    if name is not None:
        device.name = name
    if clear_group:
        device.group_id = None
    elif group_id is not None:
        if await repo.get_group(db, organization_id, group_id) is None:
            raise NotFoundError("Device group not found")
        device.group_id = group_id
    if timezone is not None:
        validate_timezone(timezone)
        device.timezone = timezone
    if orientation is not None:
        device.orientation = orientation
    if tags is not None:
        device.tags = [
            await locations_repo.get_or_create_tag(db, organization_id, key, value)
            for key, value in tags
        ]
    await db.flush()
    await db.refresh(device, ["group", "tags", "capabilities"])
    return device


async def assign_location(
    db: AsyncSession,
    organization_id: uuid.UUID,
    device_id: uuid.UUID,
    *,
    location_id: uuid.UUID | None,
) -> Device:
    device = await get_device(db, organization_id, device_id)
    if location_id is not None:
        location = await locations_repo.get_by_id(db, organization_id, location_id)
        if location is None:
            raise NotFoundError("Location not found")
        if location.status != "active":
            raise BusinessRuleError("Cannot assign a device to an archived location")
    device.location_id = location_id
    await db.flush()
    return device


async def queue_command(
    db: AsyncSession,
    organization_id: uuid.UUID,
    device_id: uuid.UUID,
    *,
    command_type: str,
    payload: dict | None,
) -> DeviceCommand:
    device = await get_device(db, organization_id, device_id)
    if device.status != DeviceStatus.ACTIVE.value:
        raise BusinessRuleError("Commands can only be sent to active devices")
    command = DeviceCommand(
        organization_id=organization_id,
        device_id=device.id,
        command_type=command_type,
        payload_json=payload,
        status=CommandStatus.QUEUED.value,
    )
    db.add(command)
    await db.flush()
    return command


# --- groups ---


async def create_group(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    name: str,
    description: str | None,
    group_type: str = "static",
    rule_json: dict | None = None,
) -> DeviceGroup:
    if await repo.get_group_by_name(db, organization_id, name):
        raise ConflictError("A device group with this name already exists", field="name")
    if group_type == "dynamic":
        from app.services import device_ops

        rule_json = device_ops.validate_rule(rule_json)
    elif group_type != "static":
        raise BusinessRuleError("group_type must be 'static' or 'dynamic'")
    else:
        rule_json = None
    group = DeviceGroup(
        organization_id=organization_id,
        name=name,
        description=description,
        group_type=group_type,
        rule_json=rule_json,
    )
    db.add(group)
    await db.flush()
    return group


async def update_group(
    db: AsyncSession,
    organization_id: uuid.UUID,
    group_id: uuid.UUID,
    *,
    name: str | None,
    description: str | None,
    rule_json: dict | None = None,
) -> DeviceGroup:
    group = await repo.get_group(db, organization_id, group_id)
    if group is None:
        raise NotFoundError("Device group not found")
    if name is not None and name != group.name:
        if await repo.get_group_by_name(db, organization_id, name):
            raise ConflictError("A device group with this name already exists", field="name")
        group.name = name
    if description is not None:
        group.description = description
    if rule_json is not None:
        if group.group_type != "dynamic":
            raise BusinessRuleError("Only dynamic groups have rules")
        from app.services import device_ops

        group.rule_json = device_ops.validate_rule(rule_json)
    await db.flush()
    return group


async def delete_group(
    db: AsyncSession, organization_id: uuid.UUID, group_id: uuid.UUID
) -> None:
    group = await repo.get_group(db, organization_id, group_id)
    if group is None:
        raise NotFoundError("Device group not found")
    if await repo.count_group_members(db, organization_id, group_id) > 0:
        raise BusinessRuleError("Remove devices from the group first")
    await db.delete(group)
    await db.flush()


async def assign_group_members(
    db: AsyncSession, organization_id: uuid.UUID, group_id: uuid.UUID, device_ids: list[uuid.UUID]
) -> int:
    group = await repo.get_group(db, organization_id, group_id)
    if group is None:
        raise NotFoundError("Device group not found")
    devices = await repo.get_by_ids(db, organization_id, device_ids)
    if len(devices) != len(set(device_ids)):
        raise NotFoundError("One or more devices not found")
    for device in devices:
        device.group_id = group_id
    await db.flush()
    return len(devices)
