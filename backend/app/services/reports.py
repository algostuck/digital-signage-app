"""Reporting foundation (M14, FR-RPT-001..005) + Phase-2 analytics
(P2-RPT-001..004): proof of play, campaign performance, device uptime."""

import datetime as dt
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ValidationAppError
from app.models import (
    Campaign,
    Deployment,
    DeploymentDevice,
    Device,
    DeviceHeartbeat,
    Location,
    PlaybackEvent,
)
from app.services import organization as org_service
from app.services.devices import connection_status


def _day_start(day: dt.date) -> datetime:
    return datetime.combine(day, dt.time.min, UTC)


def _range_filter(query, date_from: dt.date | None, date_to: dt.date | None, column):
    if date_from:
        query = query.where(column >= _day_start(date_from))
    if date_to:
        query = query.where(column < _day_start(date_to + dt.timedelta(days=1)))
    return query


async def deployments_report(db: AsyncSession, organization_id: uuid.UUID) -> list[dict]:
    """Per-campaign deployment summary (FR-RPT-001)."""
    campaigns = (
        (
            await db.execute(
                select(Campaign).where(Campaign.organization_id == organization_id)
            )
        )
        .scalars()
        .all()
    )
    rows = await db.execute(
        select(
            Deployment.campaign_id,
            func.count(Deployment.id),
            func.max(Deployment.version),
        )
        .where(Deployment.organization_id == organization_id)
        .group_by(Deployment.campaign_id)
    )
    per_campaign = {campaign_id: (count, latest) for campaign_id, count, latest in rows.all()}

    device_rows = await db.execute(
        select(Deployment.campaign_id, DeploymentDevice.status, func.count())
        .join(DeploymentDevice, DeploymentDevice.deployment_id == Deployment.id)
        .where(Deployment.organization_id == organization_id)
        .group_by(Deployment.campaign_id, DeploymentDevice.status)
    )
    acks: dict[uuid.UUID, dict[str, int]] = {}
    for campaign_id, status, count in device_rows.all():
        acks.setdefault(campaign_id, {})[status] = count

    report = []
    for campaign in campaigns:
        count, latest = per_campaign.get(campaign.id, (0, None))
        if count == 0:
            continue
        states = acks.get(campaign.id, {})
        report.append(
            {
                "campaign_id": str(campaign.id),
                "campaign_name": campaign.name,
                "status": campaign.status,
                "deployments": count,
                "latest_version": latest,
                "acknowledged": states.get("acknowledged", 0),
                "failed": states.get("failed", 0),
                "pending": states.get("pending", 0),
            }
        )
    return sorted(report, key=lambda r: r["campaign_name"])


async def playback_report(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    date_from: dt.date | None,
    date_to: dt.date | None,
) -> list[dict]:
    """Per-asset play counts — proof-of-play foundation (FR-RPT-002)."""
    from app.models import Asset

    query = (
        select(
            PlaybackEvent.asset_id,
            func.count(PlaybackEvent.id),
            func.count(func.distinct(PlaybackEvent.device_id)),
        )
        .where(
            PlaybackEvent.organization_id == organization_id,
            PlaybackEvent.asset_id.is_not(None),
        )
        .group_by(PlaybackEvent.asset_id)
    )
    if date_from:
        query = query.where(
            PlaybackEvent.started_at >= datetime.combine(date_from, dt.time.min, UTC)
        )
    if date_to:
        query = query.where(
            PlaybackEvent.started_at
            < datetime.combine(date_to + dt.timedelta(days=1), dt.time.min, UTC)
        )
    rows = (await db.execute(query)).all()
    asset_ids = [row[0] for row in rows]
    names: dict[uuid.UUID, str] = {}
    if asset_ids:
        assets = await db.execute(
            select(Asset.id, Asset.name).where(Asset.id.in_(asset_ids))
        )
        names = dict(assets.all())
    return sorted(
        (
            {
                "asset_id": str(asset_id),
                "asset_name": names.get(asset_id, "(deleted)"),
                "plays": plays,
                "devices_reached": devices,
            }
            for asset_id, plays, devices in rows
        ),
        key=lambda r: -r["plays"],
    )


# --- proof of play (P2-RPT-001, SRS §8 acceptance #6) ---

POP_DIMENSIONS = ("campaign", "asset", "device", "location")


async def proof_of_play(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
    group_by: str = "campaign",
    campaign_id: uuid.UUID | None = None,
    location_id: uuid.UUID | None = None,
) -> list[dict]:
    """Playback lifecycle rollup by a chosen dimension — the report-builder
    core: dimension + filters, columns fixed per report."""
    if group_by not in POP_DIMENSIONS:
        raise ValidationAppError(
            f"group_by must be one of {POP_DIMENSIONS}", field="group_by"
        )
    dimension = {
        "campaign": PlaybackEvent.campaign_id,
        "asset": PlaybackEvent.asset_id,
        "device": PlaybackEvent.device_id,
        "location": Device.location_id,
    }[group_by]

    query = (
        select(
            dimension,
            func.count(PlaybackEvent.id),
            func.count(PlaybackEvent.id).filter(PlaybackEvent.result == "completed"),
            func.count(func.distinct(PlaybackEvent.device_id)),
            func.min(PlaybackEvent.started_at),
            func.max(PlaybackEvent.started_at),
        )
        .where(PlaybackEvent.organization_id == organization_id)
        .group_by(dimension)
    )
    if group_by == "location" or location_id is not None:
        query = query.join(Device, Device.id == PlaybackEvent.device_id)
    query = _range_filter(query, date_from, date_to, PlaybackEvent.started_at)
    if campaign_id is not None:
        query = query.where(PlaybackEvent.campaign_id == campaign_id)
    if location_id is not None:
        location = (
            await db.execute(
                select(Location).where(
                    Location.organization_id == organization_id, Location.id == location_id
                )
            )
        ).scalar_one_or_none()
        if location is None:
            return []
        subtree = select(Location.id).where(
            Location.organization_id == organization_id,
            Location.path.like(location.path + "%"),
        )
        query = query.where(Device.location_id.in_(subtree))

    rows = (await db.execute(query)).all()

    # Resolve dimension labels.
    ids = [row[0] for row in rows if row[0] is not None]
    labels: dict = {}
    if ids:
        label_model = {
            "campaign": (Campaign, Campaign.name),
            "device": (Device, Device.name),
            "location": (Location, Location.name),
        }.get(group_by)
        if label_model is None:
            from app.models import Asset

            label_rows = await db.execute(
                select(Asset.id, Asset.name).where(Asset.id.in_(ids))
            )
        else:
            model, name_col = label_model
            label_rows = await db.execute(
                select(model.id, name_col).where(model.id.in_(ids))
            )
        labels = dict(label_rows.all())

    report = []
    for key, plays, completed, devices, first, last in rows:
        report.append(
            {
                "group_by": group_by,
                "key_id": str(key) if key else None,
                "name": labels.get(key, "(none)" if key is None else "(deleted)"),
                "plays": plays,
                "completed": completed or 0,
                "completion_rate": round((completed or 0) / plays, 3) if plays else 0,
                "devices_reached": devices,
                "first_play": first.isoformat() if first else None,
                "last_play": last.isoformat() if last else None,
            }
        )
    return sorted(report, key=lambda r: -r["plays"])


# --- campaign performance (P2-RPT-002, P2-16) ---


async def campaign_performance(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
) -> list[dict]:
    delivery = {row["campaign_id"]: row for row in await deployments_report(db, organization_id)}

    playback_query = (
        select(
            PlaybackEvent.campaign_id,
            func.count(PlaybackEvent.id),
            func.count(PlaybackEvent.id).filter(PlaybackEvent.result == "completed"),
            func.count(func.distinct(PlaybackEvent.device_id)),
        )
        .where(
            PlaybackEvent.organization_id == organization_id,
            PlaybackEvent.campaign_id.is_not(None),
        )
        .group_by(PlaybackEvent.campaign_id)
    )
    playback_query = _range_filter(playback_query, date_from, date_to, PlaybackEvent.started_at)
    playback = {
        str(campaign_id): (plays, completed, devices)
        for campaign_id, plays, completed, devices in (await db.execute(playback_query)).all()
    }

    campaigns = (
        (
            await db.execute(
                select(Campaign).where(Campaign.organization_id == organization_id)
            )
        )
        .scalars()
        .all()
    )
    report = []
    for campaign in campaigns:
        cid = str(campaign.id)
        deliv = delivery.get(cid)
        plays, completed, devices_played = playback.get(cid, (0, 0, 0))
        if deliv is None and plays == 0:
            continue
        report.append(
            {
                "campaign_id": cid,
                "campaign_name": campaign.name,
                "status": campaign.status,
                "priority": campaign.priority,
                "acknowledged": (deliv or {}).get("acknowledged", 0),
                "pending": (deliv or {}).get("pending", 0),
                "failed": (deliv or {}).get("failed", 0),
                "plays": plays,
                "completed_plays": completed,
                "completion_rate": round(completed / plays, 3) if plays else 0,
                "devices_played": devices_played,
            }
        )
    return sorted(report, key=lambda r: (-r["plays"], r["campaign_name"]))


# --- device uptime (P2-RPT-003) ---


async def device_uptime(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    date_from: dt.date,
    date_to: dt.date,
) -> list[dict]:
    """Availability from heartbeat windows: a heartbeat covers the time
    until the next one, capped at the tenant's offline threshold. Planned
    maintenance exclusions are not modeled yet (documented deviation)."""
    if date_to < date_from:
        raise ValidationAppError("date_to must not be before date_from", field="date_to")
    from app.services.organization import get_monitoring_thresholds

    thresholds = await get_monitoring_thresholds(db, organization_id)
    cap = dt.timedelta(seconds=thresholds["offline_after_seconds"])

    window_start = _day_start(date_from)
    window_end = min(_day_start(date_to + dt.timedelta(days=1)), datetime.now(UTC))
    window_seconds = max((window_end - window_start).total_seconds(), 1)

    devices = (
        (
            await db.execute(
                select(Device).where(
                    Device.organization_id == organization_id,
                    Device.status == "active",
                )
            )
        )
        .scalars()
        .all()
    )
    beats_rows = await db.execute(
        select(DeviceHeartbeat.device_id, DeviceHeartbeat.observed_at)
        .join(Device, Device.id == DeviceHeartbeat.device_id)
        .where(
            Device.organization_id == organization_id,
            DeviceHeartbeat.observed_at >= window_start,
            DeviceHeartbeat.observed_at < window_end,
        )
        .order_by(DeviceHeartbeat.device_id, DeviceHeartbeat.observed_at)
    )
    beats_by_device: dict[uuid.UUID, list[datetime]] = {}
    for device_id, observed_at in beats_rows.all():
        observed = observed_at if observed_at.tzinfo else observed_at.replace(tzinfo=UTC)
        beats_by_device.setdefault(device_id, []).append(observed)

    report = []
    for device in devices:
        beats = beats_by_device.get(device.id, [])
        covered = dt.timedelta()
        for current, following in zip(beats, beats[1:], strict=False):
            covered += min(following - current, cap)
        if beats:
            covered += min(window_end - beats[-1], cap)
        uptime_pct = min(covered.total_seconds() / window_seconds, 1.0)
        report.append(
            {
                "device_id": str(device.id),
                "device_name": device.name,
                "heartbeats": len(beats),
                "covered_seconds": int(covered.total_seconds()),
                "window_seconds": int(window_seconds),
                "uptime_pct": round(uptime_pct * 100, 2),
            }
        )
    return sorted(report, key=lambda r: r["uptime_pct"])


async def locations_report(db: AsyncSession, organization_id: uuid.UUID) -> list[dict]:
    """Device counts + health per location (FR-RPT-004)."""
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
    devices = (
        (
            await db.execute(
                select(Device).where(
                    Device.organization_id == organization_id,
                    Device.status == "active",
                    Device.location_id.is_not(None),
                )
            )
        )
        .scalars()
        .all()
    )
    now = datetime.now(UTC)
    thresholds = await org_service.get_monitoring_thresholds(db, organization_id)
    report = []
    for location in locations:
        subtree = [
            d
            for d in devices
            if any(
                loc.id == d.location_id
                for loc in locations
                if loc.path.startswith(location.path)
            )
        ]
        if not subtree:
            continue
        connections = [connection_status(d, now, thresholds) for d in subtree]
        report.append(
            {
                "location_id": str(location.id),
                "location_name": location.name,
                "depth": location.depth,
                "devices": len(subtree),
                "online": connections.count("online"),
                "warning": connections.count("warning"),
                "offline": connections.count("offline"),
            }
        )
    return sorted(report, key=lambda r: (r["depth"], r["location_name"]))
