"""Monitoring & dashboard aggregation (M13, SCR-02) and offline detection."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Asset,
    Campaign,
    Deployment,
    Device,
    Organization,
)
from app.models.device import DeviceStatus
from app.services import organization as org_service
from app.services.devices import connection_status


async def _count_by(db: AsyncSession, model, organization_id: uuid.UUID, column) -> dict[str, int]:
    rows = await db.execute(
        select(column, func.count())
        .where(model.organization_id == organization_id)
        .group_by(column)
    )
    return dict(rows.all())


async def summary(db: AsyncSession, organization_id: uuid.UUID) -> dict:
    devices = (
        (
            await db.execute(
                select(Device).where(Device.organization_id == organization_id)
            )
        )
        .scalars()
        .all()
    )
    now = datetime.now(UTC)
    thresholds = await org_service.get_monitoring_thresholds(db, organization_id)
    connections = [connection_status(d, now, thresholds) for d in devices]
    device_status = {}
    for device in devices:
        device_status[device.status] = device_status.get(device.status, 0) + 1

    asset_status = await _count_by(db, Asset, organization_id, Asset.status)
    campaign_status = await _count_by(db, Campaign, organization_id, Campaign.status)
    deployment_status = await _count_by(db, Deployment, organization_id, Deployment.status)

    return {
        "devices": {
            "total": len(devices),
            "online": connections.count("online"),
            "warning": connections.count("warning"),
            "offline": connections.count("offline"),
            "pending": device_status.get(DeviceStatus.PENDING.value, 0),
            "active": device_status.get(DeviceStatus.ACTIVE.value, 0),
        },
        "content": {
            "total": sum(asset_status.values()),
            "published": asset_status.get("published", 0),
            "draft": asset_status.get("draft", 0),
        },
        "campaigns": {
            "published": campaign_status.get("published", 0),
            "pending_approval": campaign_status.get("pending_approval", 0),
            "approved": campaign_status.get("approved", 0),
            "draft": campaign_status.get("draft", 0),
            "paused": campaign_status.get("paused", 0),
        },
        "deployments": {
            "publishing": deployment_status.get("publishing", 0),
            "partial": deployment_status.get("partial", 0),
            "published": deployment_status.get("published", 0),
            "failed": deployment_status.get("failed", 0),
        },
    }


async def device_feed(db: AsyncSession, organization_id: uuid.UUID) -> list[dict]:
    """Live health feed (FR-MON-001..003), worst connection state first."""
    devices = (
        (
            await db.execute(
                select(Device).where(
                    Device.organization_id == organization_id,
                    Device.status == DeviceStatus.ACTIVE.value,
                )
            )
        )
        .scalars()
        .all()
    )
    now = datetime.now(UTC)
    thresholds = await org_service.get_monitoring_thresholds(db, organization_id)
    order = {"offline": 0, "warning": 1, "online": 2, "n/a": 3}
    entries = []
    for device in devices:
        heartbeat = device.last_heartbeat_json or {}
        entries.append(
            {
                "id": str(device.id),
                "name": device.name,
                "platform": device.platform,
                "connection_status": connection_status(device, now, thresholds),
                "last_heartbeat_at": (
                    device.last_heartbeat_at.isoformat() if device.last_heartbeat_at else None
                ),
                "storage": heartbeat.get("storage"),
                "network": heartbeat.get("network"),
                "current": heartbeat.get("current"),
            }
        )
    return sorted(entries, key=lambda e: (order.get(e["connection_status"], 9), e["name"]))


def _parse_version(raw: str | None) -> tuple:
    """Best-effort semver ordering; unparsable parts compare as strings."""
    if not raw:
        return ()
    parts: list = []
    for chunk in raw.split("."):
        digits = "".join(ch for ch in chunk if ch.isdigit())
        parts.append((0, int(digits)) if digits else (1, chunk))
    return tuple(parts)


def is_version_outdated(current: str | None, minimum: str | None) -> bool:
    if not minimum or not current:
        return False
    return _parse_version(current) < _parse_version(minimum)


async def fleet_health(db: AsyncSession, organization_id: uuid.UUID) -> dict:
    """P2-MON-001: health rollups by organization, location and group,
    evaluated against the tenant's thresholds."""
    from sqlalchemy import func as sa_func

    from app.models import DeviceGroup, Incident, Location
    from app.models.device import IncidentState
    from app.services import device_ops
    from app.services.organization import get_monitoring_thresholds

    thresholds = await get_monitoring_thresholds(db, organization_id)
    devices = (
        (
            await db.execute(
                select(Device).where(
                    Device.organization_id == organization_id,
                    Device.status == DeviceStatus.ACTIVE.value,
                )
            )
        )
        .scalars()
        .all()
    )
    now = datetime.now(UTC)
    state_by_device = {
        d.id: connection_status(d, now, thresholds) for d in devices
    }
    outdated_ids = [
        d.id
        for d in devices
        if is_version_outdated(d.player_version, thresholds.get("min_player_version"))
    ]

    def rollup(device_ids) -> dict:
        states = [state_by_device[i] for i in device_ids if i in state_by_device]
        return {
            "total": len(states),
            "online": states.count("online"),
            "warning": states.count("warning"),
            "offline": states.count("offline"),
        }

    locations = (
        (
            await db.execute(
                select(Location).where(
                    Location.organization_id == organization_id,
                    Location.status == "active",
                )
            )
        )
        .scalars()
        .all()
    )
    path_by_location = {loc.id: loc.path for loc in locations}
    location_rollups = []
    for location in sorted(locations, key=lambda loc: loc.path):
        subtree_ids = [
            d.id
            for d in devices
            if d.location_id
            and path_by_location.get(d.location_id, "").startswith(location.path)
        ]
        if not subtree_ids:
            continue
        location_rollups.append(
            {"id": str(location.id), "name": location.name, "depth": location.depth,
             **rollup(subtree_ids)}
        )

    groups = (
        (
            await db.execute(
                select(DeviceGroup).where(DeviceGroup.organization_id == organization_id)
            )
        )
        .scalars()
        .all()
    )
    group_rollups = []
    for group in sorted(groups, key=lambda g: g.name):
        member_ids = await device_ops.resolve_group_member_ids(db, organization_id, group)
        group_rollups.append(
            {"id": str(group.id), "name": group.name, "group_type": group.group_type,
             **rollup(member_ids)}
        )

    open_incidents = (
        await db.execute(
            select(sa_func.count()).where(
                Incident.organization_id == organization_id,
                Incident.state.in_(
                    [IncidentState.OPEN.value, IncidentState.ACKNOWLEDGED.value]
                ),
            )
        )
    ).scalar_one()

    return {
        "thresholds": thresholds,
        "organization": {
            **rollup(list(state_by_device)),
            "open_incidents": open_incidents,
            "outdated_players": len(outdated_ids),
        },
        "locations": location_rollups,
        "groups": group_rollups,
    }


async def detect_offline_devices(db: AsyncSession) -> int:
    """Maintenance sweep (FR-NOT-002, FR-MON-006): one warning notification
    per offline transition, deduplicated against the last heartbeat.
    Honors each tenant's offline threshold (P2-MON-002)."""
    from app.services.organization import get_monitoring_thresholds

    orgs = (await db.execute(select(Organization.id))).scalars().all()
    created = 0
    for org_id in orgs:
        org_thresholds = await get_monitoring_thresholds(db, org_id)
        threshold = datetime.now(UTC) - timedelta(
            seconds=org_thresholds["offline_after_seconds"]
        )
        devices = (
            (
                await db.execute(
                    select(Device).where(
                        Device.organization_id == org_id,
                        Device.status == DeviceStatus.ACTIVE.value,
                    )
                )
            )
            .scalars()
            .all()
        )
        for device in devices:
            last = device.last_heartbeat_at
            last_utc = last if (last is None or last.tzinfo) else last.replace(tzinfo=UTC)
            if last_utc is not None and last_utc > threshold:
                continue
            # One incident per offline episode is the dedupe primitive; the
            # notification rides along with it (P2-MON-004).
            from app.services import device_ops
            from app.services import notifications as notifications_service

            incident = await device_ops.open_incident_if_absent(
                db,
                org_id,
                device_id=device.id,
                type="device_offline",
                severity="warning",
                title=f"Device '{device.name}' appears offline",
                payload={"device_id": str(device.id)},
            )
            if incident is None:
                continue
            await notifications_service.create(
                db,
                org_id,
                type="DEVICE_OFFLINE",
                severity="warning",
                title=f"Device '{device.name}' appears offline",
                message="No heartbeat within the configured threshold.",
                payload={"device_id": str(device.id), "incident_id": str(incident.id)},
            )

            from app.services import events

            await events.emit(
                db,
                org_id,
                event_type="device.offline",
                entity_type="device",
                entity_id=device.id,
                payload={"incident_id": str(incident.id)},
            )
            created += 1
    await db.flush()
    return created
