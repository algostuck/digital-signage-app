"""Organization dashboard aggregation (SCR-02 redesign).

One read-only, tenant-scoped payload for the Organization Administrator's
dashboard. Every block is either a GROUP BY on an indexed column or a call
into the service that already owns the rule: connection status comes from
`devices.connection_status`, schedule windows from `scheduling`, limits
from `entitlements`, usage from `tenant_admin`. Nothing here re-derives a
business rule.

Sections the caller may not see are *omitted*, never emptied, so the client
can tell "not permitted" from "nothing to show".
"""

import datetime as dt
import logging
import uuid
from collections import defaultdict
from zoneinfo import ZoneInfo

from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Anomaly,
    AnomalyRule,
    ApprovalRequest,
    Asset,
    AuditLog,
    Campaign,
    Deployment,
    DeploymentDevice,
    Device,
    Incident,
    Location,
    Notification,
    Organization,
    PlaybackEvent,
    User,
)
from app.models.campaign import CampaignStatus, DeploymentStatus
from app.models.dashboard import DeviceHealthSnapshot
from app.models.device import DeviceStatus, IncidentState
from app.models.location import LocationType
from app.services import monitoring as monitoring_service
from app.services import organization as org_service
from app.services import scheduling
from app.services.devices import connection_status

logger = logging.getLogger("app.dashboard")

MAX_RANGE_DAYS = 92
NOW_PLAYING_WINDOW = dt.timedelta(minutes=30)
NOW_PLAYING_LIMIT = 8
# Audit actions that are bookkeeping, not activity anyone wants a feed of.
ACTIVITY_NOISE = {"USER_LOGIN", "TENANT_SWITCHED", "LOCATION_CREATED", "REPORT_EXPORTED"}
FAILED_RESULTS = ("error", "failed")


def _iso(value: dt.datetime | None) -> str | None:
    return value.isoformat() if value else None


def _pct(part: int, whole: int) -> float | None:
    return round(part / whole * 100, 1) if whole else None


class Access:
    """What the caller may see. Superusers see everything."""

    def __init__(self, permissions: set[str] | None, features: set[str]):
        self._codes = permissions
        self._features = features

    def can(self, code: str) -> bool:
        return self._codes is None or code in self._codes

    def any(self, *codes: str) -> bool:
        return any(self.can(c) for c in codes)

    def feature(self, key: str) -> bool:
        return key in self._features


async def build(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    user_id: uuid.UUID,
    access: Access,
    range_start: dt.date,
    range_end: dt.date,
) -> dict:
    org = await db.get(Organization, organization_id)
    tz_name = org.timezone if org and org.timezone else "UTC"
    try:
        tz = ZoneInfo(tz_name)
    except Exception:  # noqa: BLE001 — a bad tenant timezone must not blank the dashboard
        tz_name, tz = "UTC", ZoneInfo("UTC")
    now = dt.datetime.now(dt.UTC)
    start = dt.datetime.combine(range_start, dt.time.min, tz).astimezone(dt.UTC)
    end = dt.datetime.combine(range_end + dt.timedelta(days=1), dt.time.min, tz).astimezone(dt.UTC)
    days = [range_start + dt.timedelta(days=i) for i in range((range_end - range_start).days + 1)]

    thresholds = await org_service.get_monitoring_thresholds(db, organization_id)
    devices = (
        (await db.execute(select(Device).where(Device.organization_id == organization_id)))
        .scalars()
        .all()
    )
    state_by_device = {d.id: connection_status(d, now, thresholds) for d in devices}
    active_devices = [d for d in devices if d.status == DeviceStatus.ACTIVE.value]

    out: dict = {
        "generated_at": now.isoformat(),
        "timezone": tz_name,
        "range": {"from": range_start.isoformat(), "to": range_end.isoformat()},
    }

    if access.can("monitoring.view"):
        summary = await monitoring_service.summary(db, organization_id)
        current = {
            "online": summary["devices"]["online"],
            "warning": summary["devices"]["warning"],
            "offline": summary["devices"]["offline"],
            "na": len(devices) - len(active_devices),
        }
        playback_totals = await _playback_totals(db, organization_id, start, end)
        location_total = (
            await db.execute(
                select(func.count()).where(
                    Location.organization_id == organization_id, Location.status == "active"
                )
            )
        ).scalar_one()
        out["kpis"] = {
            "devices": summary["devices"],
            "content": summary["content"],
            "campaigns": summary["campaigns"],
            "deployments": summary["deployments"],
            "playback": playback_totals,
            "locations": {"total": location_total},
        }
        out["device_health"] = {
            "current": current,
            "thresholds": thresholds,
            **(await _health_trend(db, organization_id, start, end, tz)),
        }

    geo = None
    if access.can("monitoring.view") and access.can("locations.view"):
        geo = await _geo(db, organization_id, devices, state_by_device)
        out["geo"] = geo["anchors"]
        out["locations_top"] = geo["top"]

    if access.can("campaigns.view"):
        out["campaigns"] = await _campaigns(db, organization_id, start, end)

    if access.can("reports.view"):
        out["playback"] = await _playback(db, organization_id, start, end, days, tz_name)

    if access.can("content.view"):
        out["content"] = await _content(db, organization_id)

    if access.can("deployments.view"):
        out["deployments"] = await _deployments(db, organization_id, start, end, days, tz_name)

    if access.can("monitoring.view"):
        out["attention"] = await _attention(
            db, organization_id, user_id, access, devices, state_by_device, thresholds
        )

    if access.can("audit.view"):
        out["activity"] = await _activity(db, organization_id)

    if access.any("campaigns.approve", "layouts.manage", "settings.manage"):
        out["approvals"] = await _approvals(db, organization_id)

    if access.can("schedules.view"):
        out["schedule_today"] = await _schedule_today(db, organization_id, now, tz)

    if access.can("monitoring.view") and access.can("devices.view"):
        out["now_playing"] = await _now_playing(
            db, organization_id, now, tz_name, active_devices, state_by_device
        )

    if access.can("organization.view"):
        out["usage"] = await _usage(db, organization_id)

    if access.can("monitoring.view") and access.feature("fleet_ai"):
        out["insights"] = await _insights(db, organization_id)

    return out


# --- blocks -------------------------------------------------------------


async def _playback_totals(db, organization_id, start, end) -> dict:
    row = (
        await db.execute(
            select(
                func.count(),
                func.sum(case((PlaybackEvent.result == "completed", 1), else_=0)),
                func.sum(case((PlaybackEvent.result.in_(FAILED_RESULTS), 1), else_=0)),
                func.count(func.distinct(PlaybackEvent.device_id)),
            ).where(
                PlaybackEvent.organization_id == organization_id,
                PlaybackEvent.started_at >= start,
                PlaybackEvent.started_at < end,
            )
        )
    ).one()
    plays, completed, failed, devices = (
        int(row[0] or 0),
        int(row[1] or 0),
        int(row[2] or 0),
        int(row[3] or 0),
    )
    return {
        "plays": plays,
        "completed": completed,
        "failed": failed,
        "completion_rate": _pct(completed, plays),
        "devices": devices,
    }


async def _health_trend(db, organization_id, start, end, tz) -> dict:
    rows = (
        (
            await db.execute(
                select(DeviceHealthSnapshot)
                .where(
                    DeviceHealthSnapshot.organization_id == organization_id,
                    DeviceHealthSnapshot.captured_at >= start,
                    DeviceHealthSnapshot.captured_at < end,
                )
                .order_by(DeviceHealthSnapshot.captured_at)
            )
        )
        .scalars()
        .all()
    )
    hourly = (end - start) <= dt.timedelta(days=3)
    points: list[dict] = []
    if hourly:
        points = [_snapshot_out(s) for s in rows]
    else:
        # One point per local day: the day's last capture.
        last_per_day: dict[dt.date, DeviceHealthSnapshot] = {}
        for snap in rows:
            last_per_day[snap.captured_at.astimezone(tz).date()] = snap
        points = [_snapshot_out(last_per_day[d]) for d in sorted(last_per_day)]
    return {"trend": points, "trend_granularity": "hour" if hourly else "day"}


def _snapshot_out(snap: DeviceHealthSnapshot) -> dict:
    return {
        "at": snap.captured_at.isoformat(),
        "online": snap.online,
        "warning": snap.warning,
        "offline": snap.offline,
        "na": snap.na,
    }


async def _geo(db, organization_id, devices, state_by_device) -> dict:
    """Roll devices up to the nearest ancestor location that carries
    coordinates. Devices usually sit on leaf nodes (departments, floors)
    that have none; the store, zone or city above them does."""
    rows = (
        await db.execute(
            select(Location, LocationType.code)
            .outerjoin(LocationType, LocationType.id == Location.type_id)
            .where(Location.organization_id == organization_id, Location.status == "active")
        )
    ).all()
    by_id: dict[uuid.UUID, Location] = {}
    type_of: dict[uuid.UUID, str | None] = {}
    for loc, type_code in rows:
        by_id[loc.id] = loc
        type_of[loc.id] = type_code

    def ancestors(loc: Location) -> list[uuid.UUID]:
        # path is '/a/b/c/' — own id last; nearest first for the walk.
        ids = [uuid.UUID(p) for p in loc.path.strip("/").split("/") if p]
        return list(reversed(ids))

    anchor_of: dict[uuid.UUID, uuid.UUID | None] = {}
    named: dict[tuple[uuid.UUID, str], str | None] = {}

    def anchor_for(location_id: uuid.UUID) -> uuid.UUID | None:
        if location_id in anchor_of:
            return anchor_of[location_id]
        loc = by_id.get(location_id)
        found = None
        if loc is not None:
            for candidate_id in ancestors(loc):
                candidate = by_id.get(candidate_id)
                if candidate and candidate.latitude is not None and candidate.longitude is not None:
                    found = candidate_id
                    break
        anchor_of[location_id] = found
        return found

    def nearest_named(location_id: uuid.UUID, type_code: str) -> str | None:
        key = (location_id, type_code)
        if key in named:
            return named[key]
        loc = by_id.get(location_id)
        result = None
        if loc is not None:
            for candidate_id in ancestors(loc):
                if type_of.get(candidate_id) == type_code:
                    result = by_id[candidate_id].name
                    break
        named[key] = result
        return result

    # Published campaigns reaching each device, via deployment membership.
    reach = (
        await db.execute(
            select(DeploymentDevice.device_id, Deployment.campaign_id)
            .join(Deployment, Deployment.id == DeploymentDevice.deployment_id)
            .join(Campaign, Campaign.id == Deployment.campaign_id)
            .where(
                Deployment.organization_id == organization_id,
                Campaign.status == CampaignStatus.PUBLISHED.value,
                Deployment.status != DeploymentStatus.CANCELLED.value,
            )
            .distinct()
        )
    ).all()
    campaigns_by_device: dict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)
    for device_id, campaign_id in reach:
        campaigns_by_device[device_id].add(campaign_id)

    buckets: dict[uuid.UUID, dict] = {}
    for device in devices:
        if device.status != DeviceStatus.ACTIVE.value or not device.location_id:
            continue
        anchor_id = anchor_for(device.location_id)
        if anchor_id is None:
            continue
        bucket = buckets.get(anchor_id)
        if bucket is None:
            anchor = by_id[anchor_id]
            bucket = buckets[anchor_id] = {
                "location_id": str(anchor_id),
                "name": anchor.name,
                "type": type_of.get(anchor_id),
                "latitude": anchor.latitude,
                "longitude": anchor.longitude,
                "city": nearest_named(anchor_id, "city"),
                "state": nearest_named(anchor_id, "state"),
                "devices": 0,
                "online": 0,
                "warning": 0,
                "offline": 0,
                "_campaigns": set(),
            }
        state = state_by_device.get(device.id, "offline")
        bucket["devices"] += 1
        if state in ("online", "warning", "offline"):
            bucket[state] += 1
        bucket["_campaigns"] |= campaigns_by_device.get(device.id, set())

    anchors = []
    for bucket in buckets.values():
        bucket["campaigns"] = len(bucket.pop("_campaigns"))
        bucket["health_pct"] = _pct(bucket["online"], bucket["devices"])
        anchors.append(bucket)
    anchors.sort(key=lambda b: (-b["devices"], b["name"]))

    top = [
        {
            "location_id": b["location_id"],
            "name": b["name"],
            "city": b["city"],
            "devices": b["devices"],
            "online": b["online"],
            "health_pct": b["health_pct"],
        }
        for b in sorted(
            (b for b in anchors if b["type"] != "city" and b["devices"] >= 2),
            key=lambda b: (-(b["health_pct"] or 0), -b["devices"], b["name"]),
        )[:5]
    ]
    return {"anchors": anchors[:200], "top": top}


async def _campaigns(db, organization_id, start, end) -> dict:
    by_status = dict(
        (
            await db.execute(
                select(Campaign.status, func.count())
                .where(Campaign.organization_id == organization_id)
                .group_by(Campaign.status)
            )
        ).all()
    )
    plays = dict(
        (
            await db.execute(
                select(PlaybackEvent.campaign_id, func.count())
                .where(
                    PlaybackEvent.organization_id == organization_id,
                    PlaybackEvent.started_at >= start,
                    PlaybackEvent.started_at < end,
                    PlaybackEvent.campaign_id.is_not(None),
                )
                .group_by(PlaybackEvent.campaign_id)
            )
        ).all()
    )
    campaigns = (
        (
            await db.execute(
                select(Campaign).where(
                    Campaign.organization_id == organization_id,
                    Campaign.status.in_(
                        [
                            CampaignStatus.PUBLISHED.value,
                            CampaignStatus.PAUSED.value,
                            CampaignStatus.APPROVED.value,
                        ]
                    ),
                )
            )
        )
        .scalars()
        .all()
    )
    ranked = sorted(
        campaigns, key=lambda c: (-plays.get(c.id, 0), c.updated_at or c.created_at), reverse=False
    )
    ranked = sorted(ranked, key=lambda c: -plays.get(c.id, 0))[:5]

    # Delivery of each campaign's latest deployment.
    delivery: dict[uuid.UUID, dict] = {}
    if ranked:
        latest = (
            await db.execute(
                select(Deployment.campaign_id, func.max(Deployment.created_at))
                .where(Deployment.campaign_id.in_([c.id for c in ranked]))
                .group_by(Deployment.campaign_id)
            )
        ).all()
        latest_ids: list[uuid.UUID] = []
        for campaign_id, created_at in latest:
            dep = (
                await db.execute(
                    select(Deployment.id)
                    .where(
                        Deployment.campaign_id == campaign_id, Deployment.created_at == created_at
                    )
                    .limit(1)
                )
            ).scalar_one_or_none()
            if dep:
                latest_ids.append(dep)
        if latest_ids:
            counts = (
                await db.execute(
                    select(Deployment.campaign_id, DeploymentDevice.status, func.count())
                    .join(Deployment, Deployment.id == DeploymentDevice.deployment_id)
                    .where(Deployment.id.in_(latest_ids))
                    .group_by(Deployment.campaign_id, DeploymentDevice.status)
                )
            ).all()
            for campaign_id, status, count in counts:
                delivery.setdefault(
                    campaign_id, {"devices": 0, "acknowledged": 0, "failed": 0, "pending": 0}
                )
                delivery[campaign_id]["devices"] += count
                delivery[campaign_id][status] = delivery[campaign_id].get(status, 0) + count

    return {
        "by_status": {k: int(v) for k, v in by_status.items()},
        "top": [
            {
                "id": str(c.id),
                "name": c.name,
                "status": c.status,
                "priority": c.priority,
                "plays": int(plays.get(c.id, 0)),
                "updated_at": _iso(c.updated_at),
                **delivery.get(c.id, {"devices": 0, "acknowledged": 0, "failed": 0, "pending": 0}),
            }
            for c in ranked
        ],
    }


def _local_day(column, tz_name: str):
    return func.date(func.timezone(tz_name, column))


async def _playback(db, organization_id, start, end, days, tz_name) -> dict:
    day = _local_day(PlaybackEvent.started_at, tz_name)
    rows = (
        await db.execute(
            select(
                day,
                func.count(),
                func.sum(case((PlaybackEvent.result == "completed", 1), else_=0)),
                func.sum(case((PlaybackEvent.result.in_(FAILED_RESULTS), 1), else_=0)),
            )
            .where(
                PlaybackEvent.organization_id == organization_id,
                PlaybackEvent.started_at >= start,
                PlaybackEvent.started_at < end,
            )
            .group_by(day)
        )
    ).all()
    by_day = {r[0]: (int(r[1]), int(r[2] or 0), int(r[3] or 0)) for r in rows}
    series = [
        {
            "date": d.isoformat(),
            "plays": by_day.get(d, (0, 0, 0))[0],
            "completed": by_day.get(d, (0, 0, 0))[1],
            "failed": by_day.get(d, (0, 0, 0))[2],
        }
        for d in days
    ]
    top = (
        await db.execute(
            select(
                Asset.id,
                Asset.name,
                Asset.type,
                func.count().label("plays"),
                func.count(func.distinct(PlaybackEvent.device_id)),
            )
            .join(Asset, Asset.id == PlaybackEvent.asset_id)
            .where(
                PlaybackEvent.organization_id == organization_id,
                PlaybackEvent.started_at >= start,
                PlaybackEvent.started_at < end,
            )
            .group_by(Asset.id, Asset.name, Asset.type)
            .order_by(func.count().desc())
            .limit(5)
        )
    ).all()
    return {
        "series": series,
        "top_assets": [
            {
                "asset_id": str(r[0]),
                "name": r[1],
                "type": r[2],
                "plays": int(r[3]),
                "devices": int(r[4]),
            }
            for r in top
        ],
    }


async def _content(db, organization_id) -> dict:
    by_type = dict(
        (
            await db.execute(
                select(Asset.type, func.count())
                .where(Asset.organization_id == organization_id, Asset.status != "archived")
                .group_by(Asset.type)
            )
        ).all()
    )
    by_status = dict(
        (
            await db.execute(
                select(Asset.status, func.count())
                .where(Asset.organization_id == organization_id)
                .group_by(Asset.status)
            )
        ).all()
    )
    recent = (
        (
            await db.execute(
                select(Asset)
                .where(Asset.organization_id == organization_id, Asset.status != "archived")
                .order_by(Asset.created_at.desc())
                .limit(5)
            )
        )
        .scalars()
        .all()
    )
    from app.services.content import thumbnail_url

    return {
        "by_type": {k: int(v) for k, v in by_type.items()},
        "by_status": {k: int(v) for k, v in by_status.items()},
        "recent": [
            {
                "id": str(a.id),
                "name": a.name,
                "type": a.type,
                "status": a.status,
                "created_at": _iso(a.created_at),
                "thumbnail_url": thumbnail_url(a),
            }
            for a in recent
        ],
    }


async def _deployments(db, organization_id, start, end, days, tz_name) -> dict:
    by_status = dict(
        (
            await db.execute(
                select(Deployment.status, func.count())
                .where(Deployment.organization_id == organization_id)
                .group_by(Deployment.status)
            )
        ).all()
    )
    day = _local_day(Deployment.created_at, tz_name)
    rows = (
        await db.execute(
            select(day, DeploymentDevice.status, func.count())
            .join(Deployment, Deployment.id == DeploymentDevice.deployment_id)
            .where(
                Deployment.organization_id == organization_id,
                Deployment.created_at >= start,
                Deployment.created_at < end,
            )
            .group_by(day, DeploymentDevice.status)
        )
    ).all()
    history: dict[dt.date, dict] = defaultdict(
        lambda: {"acknowledged": 0, "failed": 0, "pending": 0}
    )
    for d, status, count in rows:
        history[d][status] = history[d].get(status, 0) + int(count)
    recent = (
        (
            await db.execute(
                select(Deployment)
                .where(Deployment.organization_id == organization_id)
                .order_by(Deployment.created_at.desc())
                .limit(6)
            )
        )
        .scalars()
        .all()
    )
    recent_ids = [d.id for d in recent]
    counts: dict[uuid.UUID, dict] = defaultdict(
        lambda: {"acknowledged": 0, "failed": 0, "pending": 0}
    )
    if recent_ids:
        for dep_id, status, count in (
            await db.execute(
                select(DeploymentDevice.deployment_id, DeploymentDevice.status, func.count())
                .where(DeploymentDevice.deployment_id.in_(recent_ids))
                .group_by(DeploymentDevice.deployment_id, DeploymentDevice.status)
            )
        ).all():
            counts[dep_id][status] = int(count)
    names = (
        dict(
            (
                await db.execute(
                    select(Campaign.id, Campaign.name).where(
                        Campaign.id.in_({d.campaign_id for d in recent})
                    )
                )
            ).all()
        )
        if recent
        else {}
    )
    failed_devices = sum(h["failed"] for h in history.values())
    return {
        "by_status": {k: int(v) for k, v in by_status.items()},
        "history": [
            {
                "date": d.isoformat(),
                **history.get(d, {"acknowledged": 0, "failed": 0, "pending": 0}),
            }
            for d in days
        ],
        "failed_devices_in_range": failed_devices,
        "recent": [
            {
                "id": str(d.id),
                "campaign_id": str(d.campaign_id),
                "campaign_name": names.get(d.campaign_id, "Campaign"),
                "version": d.version,
                "status": d.status,
                "started_at": _iso(d.started_at),
                "created_at": _iso(d.created_at),
                "total_devices": sum(counts[d.id].values()),
                **counts[d.id],
            }
            for d in recent
        ],
    }


async def _attention(
    db, organization_id, user_id, access, devices, state_by_device, thresholds
) -> list[dict]:
    items: list[dict] = []
    active = [d for d in devices if d.status == DeviceStatus.ACTIVE.value]
    offline = sum(1 for d in active if state_by_device[d.id] == "offline")
    warning = sum(1 for d in active if state_by_device[d.id] == "warning")
    if offline:
        share = offline / len(active) if active else 0
        items.append(
            {
                "key": "devices_offline",
                "severity": "critical" if share >= 0.25 else "high",
                "count": offline,
                "label": f"{offline} display{'s' if offline != 1 else ''} offline",
                "detail": f"{round(share * 100)}% of the active fleet",
                "href": "/devices?connection_status=offline",
                "action": "View devices",
            }
        )
    if warning:
        items.append(
            {
                "key": "devices_warning",
                "severity": "medium",
                "count": warning,
                "label": f"{warning} display{'s' if warning != 1 else ''} not reporting reliably",
                "detail": (
                    "No heartbeat for more than "
                    f"{thresholds['warning_after_seconds'] // 60} minutes"
                ),
                "href": "/devices?connection_status=warning",
                "action": "View devices",
            }
        )
    open_incidents = (
        await db.execute(
            select(func.count()).where(
                Incident.organization_id == organization_id,
                Incident.state.in_([IncidentState.OPEN.value, IncidentState.ACKNOWLEDGED.value]),
            )
        )
    ).scalar_one()
    if open_incidents:
        items.append(
            {
                "key": "incidents_open",
                "severity": "high",
                "count": open_incidents,
                "label": f"{open_incidents} open incident{'s' if open_incidents != 1 else ''}",
                "detail": "Awaiting acknowledgement or resolution",
                "href": "/monitoring",
                "action": "Review incidents",
            }
        )
    if access.can("deployments.view"):
        failed = (
            await db.execute(
                select(func.count()).where(
                    Deployment.organization_id == organization_id,
                    Deployment.status == DeploymentStatus.FAILED.value,
                )
            )
        ).scalar_one()
        if failed:
            items.append(
                {
                    "key": "deployments_failed",
                    "severity": "high",
                    "count": failed,
                    "label": f"{failed} deployment{'s' if failed != 1 else ''} failed",
                    "detail": "Content did not reach every targeted screen",
                    "href": "/deployments?status=failed",
                    "action": "Review deployments",
                }
            )
        stuck = (
            await db.execute(
                select(func.count(func.distinct(DeploymentDevice.deployment_id)))
                .join(Deployment, Deployment.id == DeploymentDevice.deployment_id)
                .where(
                    Deployment.organization_id == organization_id,
                    Deployment.status == DeploymentStatus.PARTIAL.value,
                    DeploymentDevice.status == "failed",
                )
            )
        ).scalar_one()
        if stuck:
            items.append(
                {
                    "key": "deployments_partial",
                    "severity": "medium",
                    "count": stuck,
                    "label": f"{stuck} deployment{'s' if stuck != 1 else ''} partially delivered",
                    "detail": "Some screens rejected or never acknowledged the content",
                    "href": "/deployments?status=partial",
                    "action": "Review deployments",
                }
            )
    if access.any("campaigns.approve", "layouts.manage", "settings.manage"):
        pending = (
            await db.execute(
                select(func.count()).where(
                    ApprovalRequest.organization_id == organization_id,
                    ApprovalRequest.state == "pending",
                )
            )
        ).scalar_one()
        if pending:
            items.append(
                {
                    "key": "approvals_pending",
                    "severity": "medium",
                    "count": pending,
                    "label": f"{pending} item{'s' if pending != 1 else ''} awaiting your approval",
                    "detail": "Campaigns cannot publish until approved",
                    "href": "/approvals?state=pending",
                    "action": "Open approvals",
                }
            )
    if access.can("notifications.view"):
        critical = (
            await db.execute(
                select(func.count()).where(
                    Notification.organization_id == organization_id,
                    Notification.severity == "critical",
                    Notification.read_at.is_(None),
                    or_(Notification.user_id.is_(None), Notification.user_id == user_id),
                )
            )
        ).scalar_one()
        if critical:
            items.append(
                {
                    "key": "notifications_critical",
                    "severity": "critical",
                    "count": critical,
                    "label": f"{critical} unread critical alert{'s' if critical != 1 else ''}",
                    "detail": "Raised by monitoring rules",
                    "href": "/notifications?severity=critical",
                    "action": "Open notifications",
                }
            )
    if access.can("campaigns.view"):
        from app.models.campaign import Schedule

        soon = dt.date.today() + dt.timedelta(days=7)
        ending = (
            await db.execute(
                select(func.count(func.distinct(Campaign.id)))
                .join(Schedule, Schedule.campaign_id == Campaign.id)
                .where(
                    Campaign.organization_id == organization_id,
                    Campaign.status == CampaignStatus.PUBLISHED.value,
                    Schedule.end_date.is_not(None),
                    Schedule.end_date >= dt.date.today(),
                    Schedule.end_date <= soon,
                )
            )
        ).scalar_one()
        if ending:
            items.append(
                {
                    "key": "campaigns_ending",
                    "severity": "info",
                    "count": ending,
                    "label": f"{ending} campaign{'s' if ending != 1 else ''} end within 7 days",
                    "detail": "Schedule a follow-up or the screens fall back",
                    "href": "/schedules",
                    "action": "Open schedule",
                }
            )
    if access.can("organization.view"):
        from app.services import tenant_admin

        usage = await tenant_admin.get_usage(db, organization_id)
        for key, label in (("devices", "Device"), ("users", "User"), ("storage_mb", "Storage")):
            used, limit = usage[key]["used"], usage[key]["limit"]
            if not limit:
                continue
            share = used / limit
            if share >= 0.8:
                items.append(
                    {
                        "key": f"usage_{key}",
                        "severity": "high" if share >= 0.95 else "medium",
                        "count": round(share * 100),
                        "label": f"{label} usage at {round(share * 100)}% of plan limit",
                        "detail": f"{used:,.0f} of {limit:,} — growth is blocked at the limit",
                        "href": "/settings",
                        "action": "Review plan",
                    }
                )
    outdated = sum(
        1
        for d in active
        if monitoring_service.is_version_outdated(
            d.player_version, thresholds.get("min_player_version")
        )
    )
    if outdated:
        items.append(
            {
                "key": "players_outdated",
                "severity": "info",
                "count": outdated,
                "label": (
                    f"{outdated} player{'s' if outdated != 1 else ''} below the minimum version"
                ),
                "detail": f"Minimum {thresholds.get('min_player_version')}",
                "href": "/releases",
                "action": "Open releases",
            }
        )
    if access.feature("fleet_ai"):
        anomalies = (
            await db.execute(
                select(func.count()).where(
                    Anomaly.organization_id == organization_id, Anomaly.state == "open"
                )
            )
        ).scalar_one()
        if anomalies:
            items.append(
                {
                    "key": "anomalies_open",
                    "severity": "high",
                    "count": anomalies,
                    "label": (
                        f"{anomalies} device{'s' if anomalies != 1 else ''} with abnormal behaviour"
                    ),
                    "detail": "Flagged by fleet intelligence with evidence",
                    "href": "/devices?tab=intelligence",
                    "action": "Review findings",
                }
            )
    order = {"critical": 0, "high": 1, "medium": 2, "info": 3}
    items.sort(key=lambda i: (order[i["severity"]], -i["count"]))
    return items


async def _activity(db, organization_id) -> list[dict]:
    rows = (
        (
            await db.execute(
                select(AuditLog)
                .where(
                    AuditLog.organization_id == organization_id,
                    AuditLog.action.not_in(ACTIVITY_NOISE),
                )
                .order_by(AuditLog.created_at.desc())
                .limit(10)
            )
        )
        .scalars()
        .all()
    )
    user_ids = {r.user_id for r in rows if r.user_id}
    names = (
        dict((await db.execute(select(User.id, User.full_name).where(User.id.in_(user_ids)))).all())
        if user_ids
        else {}
    )
    return [
        {
            "id": str(r.id),
            "action": r.action,
            "entity_type": r.entity_type,
            "entity_id": r.entity_id,
            "entity_name": (r.after_json or {}).get("name")
            if isinstance(r.after_json, dict)
            else None,
            "user_name": names.get(r.user_id),
            "created_at": _iso(r.created_at),
        }
        for r in rows
    ]


async def _approvals(db, organization_id) -> list[dict]:
    rows = (
        (
            await db.execute(
                select(ApprovalRequest)
                .where(
                    ApprovalRequest.organization_id == organization_id,
                    ApprovalRequest.state == "pending",
                )
                .order_by(ApprovalRequest.submitted_at)
                .limit(5)
            )
        )
        .scalars()
        .all()
    )
    if not rows:
        return []
    requester_ids = {r.requester_id for r in rows if r.requester_id}
    names = (
        dict(
            (
                await db.execute(select(User.id, User.full_name).where(User.id.in_(requester_ids)))
            ).all()
        )
        if requester_ids
        else {}
    )
    campaign_ids = [r.entity_id for r in rows if r.entity_type == "campaign"]
    campaign_names = (
        dict(
            (
                await db.execute(
                    select(Campaign.id, Campaign.name).where(Campaign.id.in_(campaign_ids))
                )
            ).all()
        )
        if campaign_ids
        else {}
    )
    return [
        {
            "id": str(r.id),
            "entity_type": r.entity_type,
            "entity_id": str(r.entity_id),
            "entity_name": campaign_names.get(r.entity_id) if r.entity_type == "campaign" else None,
            "requester_name": names.get(r.requester_id),
            "submitted_at": _iso(r.submitted_at),
        }
        for r in rows
    ]


async def _schedule_today(db, organization_id, now, tz) -> list[dict]:
    from app.services import campaigns as campaigns_service

    today = now.astimezone(tz).date()
    now_minute = now.astimezone(tz).hour * 60 + now.astimezone(tz).minute
    campaigns = await campaigns_service.campaigns_with_schedules(db, organization_id)
    published = [c for c in campaigns if c.status == CampaignStatus.PUBLISHED.value]
    events = scheduling.expand_calendar(published, today, today)
    conflicts = {id(e) for pair in scheduling.detect_conflicts(events) for e in pair}
    events.sort(key=lambda e: (e.start_minute, -e.campaign_priority))
    return [
        {
            "campaign_id": e.campaign_id,
            "campaign_name": e.campaign_name,
            "kind": e.kind,
            "start_minute": e.start_minute,
            "end_minute": e.end_minute,
            "live": e.start_minute <= now_minute < e.end_minute,
            "conflict": id(e) in conflicts,
        }
        for e in events[:12]
    ]


async def _now_playing(
    db, organization_id, now, tz_name, active_devices, state_by_device
) -> list[dict]:
    from app.services.content import thumbnail_url

    since = now - NOW_PLAYING_WINDOW
    recent = (
        (
            await db.execute(
                select(PlaybackEvent)
                .where(
                    PlaybackEvent.organization_id == organization_id,
                    PlaybackEvent.started_at >= since,
                )
                .order_by(PlaybackEvent.started_at.desc())
                .limit(400)
            )
        )
        .scalars()
        .all()
    )
    latest: dict[uuid.UUID, PlaybackEvent] = {}
    for event in recent:
        latest.setdefault(event.device_id, event)
        if len(latest) >= NOW_PLAYING_LIMIT:
            break

    device_by_id = {d.id: d for d in active_devices}
    location_ids = {d.location_id for d in active_devices if d.location_id}
    location_names = (
        dict(
            (
                await db.execute(
                    select(Location.id, Location.name).where(Location.id.in_(location_ids))
                )
            ).all()
        )
        if location_ids
        else {}
    )

    entries: list[dict] = []
    asset_ids = {e.asset_id for e in latest.values() if e.asset_id}
    campaign_ids = {e.campaign_id for e in latest.values() if e.campaign_id}
    assets = (
        {
            a.id: a
            for a in (await db.execute(select(Asset).where(Asset.id.in_(asset_ids))))
            .scalars()
            .all()
        }
        if asset_ids
        else {}
    )
    campaign_names = (
        dict(
            (
                await db.execute(
                    select(Campaign.id, Campaign.name).where(Campaign.id.in_(campaign_ids))
                )
            ).all()
        )
        if campaign_ids
        else {}
    )
    for device_id, event in latest.items():
        device = device_by_id.get(device_id)
        if device is None:
            continue
        asset = assets.get(event.asset_id) if event.asset_id else None
        entries.append(
            {
                "device_id": str(device.id),
                "device_name": device.name,
                "location_name": location_names.get(device.location_id),
                "connection_status": state_by_device.get(device.id),
                "campaign_name": campaign_names.get(event.campaign_id),
                "asset_name": asset.name if asset else None,
                "asset_type": asset.type if asset else None,
                "thumbnail_url": thumbnail_url(asset) if asset else None,
                "reported_at": _iso(event.started_at),
                "source": "reported",
            }
        )

    if len(entries) < NOW_PLAYING_LIMIT:
        # Fall back to what the schedule says an online screen should be
        # showing, resolved by the same function the player uses. Labelled
        # so it is never mistaken for a proof-of-play record.
        seen = set(latest)
        candidates = [
            d for d in active_devices if d.id not in seen and state_by_device.get(d.id) == "online"
        ][: NOW_PLAYING_LIMIT * 4]
        if candidates:
            rows = (
                await db.execute(
                    select(
                        DeploymentDevice.device_id, Deployment.campaign_id, Deployment.created_at
                    )
                    .join(Deployment, Deployment.id == DeploymentDevice.deployment_id)
                    .where(
                        DeploymentDevice.device_id.in_([d.id for d in candidates]),
                        DeploymentDevice.status == "acknowledged",
                    )
                    .order_by(Deployment.created_at.desc())
                )
            ).all()
            latest_campaign: dict[uuid.UUID, uuid.UUID] = {}
            for device_id, campaign_id, _created in rows:
                latest_campaign.setdefault(device_id, campaign_id)
            campaigns = {
                c.id: c
                for c in (
                    await db.execute(
                        select(Campaign).where(Campaign.id.in_(set(latest_campaign.values())))
                    )
                )
                .scalars()
                .all()
            }
            for device in candidates:
                campaign = campaigns.get(latest_campaign.get(device.id))
                if campaign is None or campaign.status != CampaignStatus.PUBLISHED.value:
                    continue
                if (
                    scheduling.resolve_active_campaign([campaign], now, device.timezone or tz_name)
                    is None
                ):
                    continue
                entries.append(
                    {
                        "device_id": str(device.id),
                        "device_name": device.name,
                        "location_name": location_names.get(device.location_id),
                        "connection_status": state_by_device.get(device.id),
                        "campaign_name": campaign.name,
                        "asset_name": None,
                        "asset_type": None,
                        "thumbnail_url": None,
                        "reported_at": None,
                        "source": "scheduled",
                    }
                )
                if len(entries) >= NOW_PLAYING_LIMIT:
                    break
    return entries


async def _usage(db, organization_id) -> dict:
    from app.services import entitlements as entitlements_service
    from app.services import tenant_admin

    usage = await tenant_admin.get_usage(db, organization_id)
    effective = await entitlements_service.get_effective(db, organization_id)
    subscription = await entitlements_service.latest_subscription(db, organization_id)
    locations = (
        await db.execute(
            select(func.count()).where(
                Location.organization_id == organization_id, Location.status == "active"
            )
        )
    ).scalar_one()
    return {
        "plan_code": effective.plan_code,
        "plan_name": effective.plan_name,
        "subscription_status": effective.subscription_status,
        "period_end": _iso(subscription.current_period_end) if subscription else None,
        "billing_cycle": subscription.billing_cycle if subscription else None,
        "devices": usage["devices"],
        "users": usage["users"],
        "storage_mb": usage["storage_mb"],
        "locations": {"used": locations, "limit": effective.limit("max_locations")},
    }


async def _insights(db, organization_id) -> list[dict]:
    rows = (
        await db.execute(
            select(Anomaly, AnomalyRule.name, AnomalyRule.signal_type, Device.name)
            .outerjoin(AnomalyRule, AnomalyRule.id == Anomaly.rule_id)
            .join(Device, Device.id == Anomaly.device_id)
            .where(Anomaly.organization_id == organization_id, Anomaly.state == "open")
            .order_by(Anomaly.score.desc())
            .limit(5)
        )
    ).all()
    out = []
    for anomaly, rule_name, signal, device_name in rows:
        evidence = anomaly.evidence_json or {}
        why = ", ".join(
            f"{k.replace('_', ' ')} {v}"
            for k, v in evidence.items()
            if not isinstance(v, (dict, list))
        )
        out.append(
            {
                "id": str(anomaly.id),
                "device_id": str(anomaly.device_id),
                "device_name": device_name,
                "signal": signal,
                "score": float(anomaly.score),
                "finding": (
                    f"{device_name}: {rule_name or signal or 'anomaly'} "
                    f"at {float(anomaly.score):.1f}× threshold"
                ),
                "why": why or None,
                "action": anomaly.recommendation,
                "opened_at": _iso(anomaly.opened_at),
                "href": "/devices?tab=intelligence",
            }
        )
    return out


# --- snapshots ----------------------------------------------------------


async def snapshot_device_health(db: AsyncSession) -> int:
    """Beat sweep: one health row per tenant per hour, so the dashboard can
    show how the fleet moved. Idempotent within the hour."""
    now = dt.datetime.now(dt.UTC)
    hour_start = now.replace(minute=0, second=0, microsecond=0)
    org_ids = (await db.execute(select(Organization.id))).scalars().all()
    written = 0
    for org_id in org_ids:
        exists = (
            await db.execute(
                select(func.count()).where(
                    DeviceHealthSnapshot.organization_id == org_id,
                    DeviceHealthSnapshot.captured_at >= hour_start,
                )
            )
        ).scalar_one()
        if exists:
            continue
        thresholds = await org_service.get_monitoring_thresholds(db, org_id)
        devices = (
            (await db.execute(select(Device).where(Device.organization_id == org_id)))
            .scalars()
            .all()
        )
        if not devices:
            continue
        states = [connection_status(d, now, thresholds) for d in devices]
        db.add(
            DeviceHealthSnapshot(
                organization_id=org_id,
                captured_at=now,
                online=states.count("online"),
                warning=states.count("warning"),
                offline=states.count("offline"),
                na=states.count("n/a"),
            )
        )
        written += 1
    await db.flush()
    return written
