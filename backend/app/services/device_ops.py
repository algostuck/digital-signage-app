"""Advanced device operations (P2-M01/P2-M06 parts): dynamic group rules,
bulk actions, bulk edit, screenshot evidence and incidents."""

import hashlib
import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import BusinessRuleError, NotFoundError, ValidationAppError
from app.integrations.storage import get_storage
from app.models import (
    Device,
    DeviceCommand,
    DeviceGroup,
    Incident,
    Location,
    Screenshot,
    Tag,
)
from app.models.device import (
    CommandStatus,
    DeviceGroupType,
    DeviceStatus,
    IncidentState,
    device_tags,
)
from app.repositories import devices as devices_repo
from app.repositories import locations as locations_repo

logger = logging.getLogger("app.device_ops")

RULE_FIELDS = ("manufacturer", "platform", "model", "status", "tag", "location")
RULE_OPERATORS = {"eq", "ne", "contains", "in_subtree"}
MAX_RULE_CONDITIONS = 20
MAX_BULK_DEVICES = 1000


def validate_rule(rule: dict | None) -> dict:
    """Whitelisted, schema-checked group rule (never raw SQL from input)."""
    if not isinstance(rule, dict):
        raise ValidationAppError("rule_json must be an object", field="rule_json")
    match = rule.get("match", "all")
    if match not in ("all", "any"):
        raise ValidationAppError("rule_json.match must be 'all' or 'any'", field="rule_json")
    conditions = rule.get("conditions")
    if not isinstance(conditions, list) or not conditions:
        raise ValidationAppError(
            "rule_json.conditions must be a non-empty list", field="rule_json"
        )
    if len(conditions) > MAX_RULE_CONDITIONS:
        raise ValidationAppError("Too many rule conditions", field="rule_json")
    for condition in conditions:
        field = condition.get("field")
        operator = condition.get("operator", "eq")
        if field not in RULE_FIELDS:
            raise ValidationAppError(f"Unknown rule field '{field}'", field="rule_json")
        if operator not in RULE_OPERATORS:
            raise ValidationAppError(f"Unknown operator '{operator}'", field="rule_json")
        if field == "location" and operator not in ("eq", "in_subtree"):
            raise ValidationAppError(
                "location conditions support 'eq' or 'in_subtree'", field="rule_json"
            )
        if field == "tag":
            value = condition.get("value")
            if not isinstance(value, dict) or not value.get("key"):
                raise ValidationAppError(
                    "tag conditions need value {key, value}", field="rule_json"
                )
        elif condition.get("value") in (None, ""):
            raise ValidationAppError("Rule condition needs a value", field="rule_json")
    return {"match": match, "conditions": conditions}


async def _condition_clause(db: AsyncSession, organization_id: uuid.UUID, condition: dict):
    field = condition["field"]
    operator = condition.get("operator", "eq")
    value = condition.get("value")

    if field in ("manufacturer", "platform", "model", "status"):
        column = getattr(Device, field)
        if operator == "eq":
            return func.lower(column) == str(value).lower()
        if operator == "ne":
            return func.lower(column) != str(value).lower()
        return func.lower(column).like(f"%{str(value).lower()}%")

    if field == "tag":
        tag_query = (
            select(device_tags.c.device_id)
            .join(Tag, Tag.id == device_tags.c.tag_id)
            .where(Tag.organization_id == organization_id, Tag.key == value["key"])
        )
        if value.get("value"):
            tag_query = tag_query.where(Tag.value == value["value"])
        clause = Device.id.in_(tag_query)
        return ~clause if operator == "ne" else clause

    # location
    try:
        location_id = uuid.UUID(str(value))
    except ValueError as exc:
        raise ValidationAppError("location value must be a location id") from exc
    location = await locations_repo.get_by_id(db, organization_id, location_id)
    if location is None:
        return Device.id.is_(None)  # unknown location matches nothing
    if operator == "in_subtree":
        subtree = select(Location.id).where(
            Location.organization_id == organization_id,
            Location.path.like(location.path + "%"),
        )
        return Device.location_id.in_(subtree)
    return Device.location_id == location.id


async def resolve_group_member_ids(
    db: AsyncSession, organization_id: uuid.UUID, group: DeviceGroup
) -> list[uuid.UUID]:
    if group.group_type == DeviceGroupType.STATIC.value:
        result = await db.execute(
            select(Device.id).where(
                Device.organization_id == organization_id, Device.group_id == group.id
            )
        )
        return list(result.scalars().all())
    return await preview_rule_member_ids(db, organization_id, group.rule_json or {})


async def preview_rule_member_ids(
    db: AsyncSession, organization_id: uuid.UUID, rule: dict
) -> list[uuid.UUID]:
    rule = validate_rule(rule)
    clauses = [
        await _condition_clause(db, organization_id, condition)
        for condition in rule["conditions"]
    ]
    combined = and_(*clauses) if rule["match"] == "all" else or_(*clauses)
    result = await db.execute(
        select(Device.id).where(Device.organization_id == organization_id, combined)
    )
    return list(result.scalars().all())


async def group_member_count(
    db: AsyncSession, organization_id: uuid.UUID, group: DeviceGroup
) -> int:
    return len(await resolve_group_member_ids(db, organization_id, group))


# --- bulk operations (P2-DEV-002, P2-SRC-003) ---


async def bulk_group_command(
    db: AsyncSession,
    organization_id: uuid.UUID,
    group_id: uuid.UUID,
    *,
    command_type: str,
    payload: dict | None,
) -> dict:
    group = await devices_repo.get_group(db, organization_id, group_id)
    if group is None:
        raise NotFoundError("Device group not found")
    member_ids = await resolve_group_member_ids(db, organization_id, group)
    if len(member_ids) > MAX_BULK_DEVICES:
        raise BusinessRuleError(
            f"Group resolves to {len(member_ids)} devices; the bulk limit is {MAX_BULK_DEVICES}"
        )
    active = await db.execute(
        select(Device.id).where(
            Device.id.in_(member_ids) if member_ids else Device.id.is_(None),
            Device.status == DeviceStatus.ACTIVE.value,
        )
    )
    active_ids = list(active.scalars().all())
    for device_id in active_ids:
        db.add(
            DeviceCommand(
                organization_id=organization_id,
                device_id=device_id,
                command_type=command_type,
                payload_json=payload,
                status=CommandStatus.QUEUED.value,
            )
        )
    await db.flush()

    from app.services import audit

    await audit.record(
        db,
        organization_id,
        action="DEVICE_BULK_COMMAND",
        entity_type="device_group",
        entity_id=group.id,
        after={"command_type": command_type, "queued": len(active_ids)},
    )
    logger.info(
        "Bulk command %s queued for %s devices (group %s)",
        command_type,
        len(active_ids),
        group.id,
    )
    return {"queued": len(active_ids), "skipped": len(member_ids) - len(active_ids)}


async def bulk_update_devices(
    db: AsyncSession,
    organization_id: uuid.UUID,
    device_ids: list[uuid.UUID],
    *,
    group_id: uuid.UUID | None = None,
    clear_group: bool = False,
    location_id: uuid.UUID | None = None,
    clear_location: bool = False,
    add_tags: list[tuple[str, str]] | None = None,
    remove_tags: list[tuple[str, str]] | None = None,
) -> int:
    if not device_ids:
        raise ValidationAppError("device_ids must not be empty", field="device_ids")
    if len(device_ids) > MAX_BULK_DEVICES:
        raise BusinessRuleError(f"Bulk limit is {MAX_BULK_DEVICES} devices")
    devices = await devices_repo.get_by_ids(db, organization_id, device_ids)
    if len(devices) != len(set(device_ids)):
        raise NotFoundError("One or more devices not found")

    if group_id is not None:
        if await devices_repo.get_group(db, organization_id, group_id) is None:
            raise NotFoundError("Device group not found")
    location = None
    if location_id is not None:
        location = await locations_repo.get_by_id(db, organization_id, location_id)
        if location is None or location.status != "active":
            raise NotFoundError("Location not found")

    tag_rows = {}
    for key, value in add_tags or []:
        tag_rows[(key, value)] = await locations_repo.get_or_create_tag(
            db, organization_id, key, value
        )

    for device in devices:
        if clear_group:
            device.group_id = None
        elif group_id is not None:
            device.group_id = group_id
        if clear_location:
            device.location_id = None
        elif location is not None:
            device.location_id = location.id
        if add_tags:
            existing = {(t.key, t.value) for t in device.tags}
            for pair, tag in tag_rows.items():
                if pair not in existing:
                    device.tags.append(tag)
        if remove_tags:
            removals = set(remove_tags)
            device.tags = [t for t in device.tags if (t.key, t.value) not in removals]
    await db.flush()

    from app.services import audit

    await audit.record(
        db,
        organization_id,
        action="DEVICE_BULK_UPDATED",
        entity_type="device",
        after={"count": len(devices)},
    )
    return len(devices)


# --- screenshots (P2-MON-003) ---

SCREENSHOT_MIME = {"image/png": "png", "image/jpeg": "jpg"}
MAX_SCREENSHOT_BYTES = 5 * 1024 * 1024


async def store_screenshot(
    db: AsyncSession, device: Device, *, data: bytes, mime_type: str
) -> Screenshot:
    if mime_type not in SCREENSHOT_MIME:
        raise ValidationAppError("Screenshots must be image/png or image/jpeg")
    if not data or len(data) > MAX_SCREENSHOT_BYTES:
        raise ValidationAppError("Screenshot must be between 1 byte and 5 MB")
    now = datetime.now(UTC)
    extension = SCREENSHOT_MIME[mime_type]
    object_key = (
        f"tenant/{device.organization_id}/screenshots/{device.id}/"
        f"{now.strftime('%Y%m%dT%H%M%S%f')}.{extension}"
    )
    get_storage().write(object_key, data)
    screenshot = Screenshot(
        organization_id=device.organization_id,
        device_id=device.id,
        object_key=object_key,
        mime_type=mime_type,
        size_bytes=len(data),
        checksum=hashlib.sha256(data).hexdigest(),
        captured_at=now,
    )
    db.add(screenshot)
    await db.flush()
    return screenshot


async def list_screenshots(
    db: AsyncSession, organization_id: uuid.UUID, device_id: uuid.UUID, *, limit: int = 20
) -> list[dict]:
    settings = get_settings()
    storage = get_storage()
    rows = await db.execute(
        select(Screenshot)
        .where(
            Screenshot.organization_id == organization_id,
            Screenshot.device_id == device_id,
        )
        .order_by(Screenshot.captured_at.desc())
        .limit(limit)
    )
    return [
        {
            "id": str(row.id),
            "captured_at": row.captured_at.isoformat(),
            "size_bytes": row.size_bytes,
            "checksum": row.checksum,
            "url": storage.presigned_get_url(row.object_key, settings.signed_url_ttl_seconds),
        }
        for row in rows.scalars().all()
    ]


# --- incidents (P2-MON-004) ---


async def open_incident_if_absent(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    device_id: uuid.UUID,
    type: str,
    severity: str,
    title: str,
    payload: dict | None = None,
) -> Incident | None:
    """Opens an incident unless one of this type is already open/acked for
    the device — the dedupe primitive for offline detection."""
    existing = await db.execute(
        select(Incident).where(
            Incident.organization_id == organization_id,
            Incident.device_id == device_id,
            Incident.type == type,
            Incident.state.in_(
                [IncidentState.OPEN.value, IncidentState.ACKNOWLEDGED.value]
            ),
        )
    )
    if existing.scalar_one_or_none() is not None:
        return None
    incident = Incident(
        organization_id=organization_id,
        device_id=device_id,
        type=type,
        severity=severity,
        title=title,
        payload_json=payload,
    )
    db.add(incident)
    await db.flush()

    from app.services import events

    await events.emit(
        db,
        organization_id,
        event_type="incident.opened",
        entity_type="incident",
        entity_id=incident.id,
        payload={"type": type, "severity": severity, "device_id": str(device_id)},
    )
    return incident


async def resolve_device_incidents(
    db: AsyncSession,
    organization_id: uuid.UUID,
    device_id: uuid.UUID,
    *,
    type: str,
    resolution: str,
) -> list[Incident]:
    rows = await db.execute(
        select(Incident).where(
            Incident.organization_id == organization_id,
            Incident.device_id == device_id,
            Incident.type == type,
            Incident.state.in_(
                [IncidentState.OPEN.value, IncidentState.ACKNOWLEDGED.value]
            ),
        )
    )
    resolved = []
    for incident in rows.scalars().all():
        incident.state = IncidentState.RESOLVED.value
        incident.resolved_at = datetime.now(UTC)
        incident.resolution = resolution
        resolved.append(incident)
    if resolved:
        await db.flush()

        from app.services import events

        for incident in resolved:
            await events.emit(
                db,
                organization_id,
                event_type="incident.resolved",
                entity_type="incident",
                entity_id=incident.id,
                payload={"type": incident.type, "resolution": resolution},
            )
    return resolved


async def list_incidents(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    state: str | None,
    page: int,
    page_size: int,
) -> tuple[list[Incident], int]:
    query = select(Incident).where(Incident.organization_id == organization_id)
    if state:
        query = query.where(Incident.state == state)
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    rows = await db.execute(
        query.order_by(Incident.opened_at.desc(), Incident.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(rows.scalars().all()), total


async def transition_incident(
    db: AsyncSession,
    organization_id: uuid.UUID,
    incident_id: uuid.UUID,
    *,
    action: str,
    user_id: uuid.UUID | None,
) -> Incident:
    incident = (
        await db.execute(
            select(Incident).where(
                Incident.organization_id == organization_id, Incident.id == incident_id
            )
        )
    ).scalar_one_or_none()
    if incident is None:
        raise NotFoundError("Incident not found")
    if action == "acknowledge":
        if incident.state != IncidentState.OPEN.value:
            raise BusinessRuleError("Only open incidents can be acknowledged")
        incident.state = IncidentState.ACKNOWLEDGED.value
        incident.acknowledged_by = user_id
        incident.acknowledged_at = datetime.now(UTC)
    elif action == "resolve":
        if incident.state == IncidentState.RESOLVED.value:
            raise BusinessRuleError("Incident is already resolved")
        incident.state = IncidentState.RESOLVED.value
        incident.resolved_at = datetime.now(UTC)
        incident.resolution = "Resolved manually"

        from app.services import events

        await events.emit(
            db,
            organization_id,
            event_type="incident.resolved",
            entity_type="incident",
            entity_id=incident.id,
            payload={"type": incident.type, "resolution": incident.resolution},
        )
    else:
        raise NotFoundError("Unknown incident action")
    await db.flush()
    return incident
