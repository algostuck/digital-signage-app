"""Schedule workspace calendar (docs/SCHEDULE_UX_AUDIT.md §10).

One richer `GET /schedules/calendar` response: expanded events with campaign
status, recurrence text and target counts, *actionable* conflicts computed
by `scheduling.analyse_conflicts` on shared screens, a summary strip and the
tenant clock. Filters resolve through the same targeting service that
publishing uses, so "campaigns reaching this location" means exactly what a
deployment would mean.

The conflict analysis always runs on the unfiltered estate — a conflict
between two campaigns exists whether or not the user is looking at one of
them — and only the *presentation* is narrowed.
"""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Campaign, Device, Organization
from app.models.campaign import CampaignStatus
from app.models.device import DeviceStatus
from app.services import scheduling, targeting


@dataclass
class CalendarFilters:
    location_id: uuid.UUID | None = None
    group_id: uuid.UUID | None = None
    device_id: uuid.UUID | None = None
    campaign_ids: list[uuid.UUID] = field(default_factory=list)
    statuses: list[str] = field(default_factory=list)
    kind: str | None = None
    priority_min: int | None = None
    priority_max: int | None = None
    conflicts_only: bool = False


async def organization_timezone(
    db: AsyncSession, organization_id: uuid.UUID
) -> tuple[str, ZoneInfo]:
    org = await db.get(Organization, organization_id)
    name = org.timezone if org and org.timezone else "UTC"
    try:
        return name, ZoneInfo(name)
    except Exception:  # noqa: BLE001 — a bad tenant timezone must not blank the calendar
        return "UTC", ZoneInfo("UTC")


async def campaigns_with_targets(db: AsyncSession, organization_id: uuid.UUID) -> list[Campaign]:
    result = await db.execute(
        select(Campaign)
        .where(
            Campaign.organization_id == organization_id,
            Campaign.status != CampaignStatus.ARCHIVED.value,
        )
        .options(selectinload(Campaign.schedules), selectinload(Campaign.targets))
    )
    return list(result.scalars().unique().all())


async def campaign_device_sets(
    db: AsyncSession, organization_id: uuid.UUID, campaigns: list[Campaign]
) -> dict[str, set[uuid.UUID]]:
    """Effective *active* device ids per campaign. Each distinct target is
    resolved once — campaigns share location and group targets heavily."""
    active = set(
        (
            await db.execute(
                select(Device.id).where(
                    Device.organization_id == organization_id,
                    Device.status == DeviceStatus.ACTIVE.value,
                )
            )
        )
        .scalars()
        .all()
    )
    memo: dict[tuple, set[uuid.UUID]] = {}
    sets: dict[str, set[uuid.UUID]] = {}
    for campaign in campaigns:
        included: set[uuid.UUID] = set()
        excluded: set[uuid.UUID] = set()
        for target in campaign.targets:
            key = (target.target_type, target.target_id, bool(target.include_descendants))
            if key not in memo:
                memo[key] = await targeting._devices_for_target(db, organization_id, target)
            if target.is_exclusion:
                excluded |= memo[key]
            else:
                included |= memo[key]
        sets[str(campaign.id)] = (included - excluded) & active
    return sets


async def _scope_devices(
    db: AsyncSession, organization_id: uuid.UUID, filters: CalendarFilters
) -> set[uuid.UUID] | None:
    """Devices the location / group / device filters select; None = no scope."""
    if not (filters.location_id or filters.group_id or filters.device_id):
        return None
    from types import SimpleNamespace

    scope: set[uuid.UUID] | None = None
    for target_type, target_id in (
        ("location", filters.location_id),
        ("group", filters.group_id),
        ("device", filters.device_id),
    ):
        if target_id is None:
            continue
        target = SimpleNamespace(
            target_type=target_type, target_id=target_id, include_descendants=True
        )
        devices = await targeting._devices_for_target(db, organization_id, target)
        scope = devices if scope is None else scope & devices
    return scope or set()


def _event_matches(
    event: scheduling.CalendarEvent, filters: CalendarFilters, campaign_ids: set[str] | None
) -> bool:
    if campaign_ids is not None and event.campaign_id not in campaign_ids:
        return False
    if filters.campaign_ids and uuid.UUID(event.campaign_id) not in filters.campaign_ids:
        return False
    if filters.statuses and event.campaign_status not in filters.statuses:
        return False
    if filters.kind and event.kind != filters.kind:
        return False
    if filters.priority_min is not None and event.campaign_priority < filters.priority_min:
        return False
    if filters.priority_max is not None and event.campaign_priority > filters.priority_max:
        return False
    if filters.conflicts_only and not event.conflict:
        return False
    return True


async def build_calendar(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    range_start: dt.date,
    range_end: dt.date,
    filters: CalendarFilters | None = None,
    now: dt.datetime | None = None,
) -> dict:
    filters = filters or CalendarFilters()
    now = now or dt.datetime.now(dt.UTC)
    tz_name, tz = await organization_timezone(db, organization_id)
    local_now = now.astimezone(tz)
    today = local_now.date()
    now_minute = local_now.hour * 60 + local_now.minute

    campaigns = await campaigns_with_targets(db, organization_id)
    device_sets = await campaign_device_sets(db, organization_id, campaigns)
    devices = (
        await db.execute(
            select(Device.id, Device.name, Device.location_id).where(
                Device.organization_id == organization_id
            )
        )
    ).all()
    device_names = {row.id: row.name for row in devices}
    device_location = {row.id: row.location_id for row in devices}

    events = scheduling.expand_calendar(campaigns, range_start, range_end)
    conflicts = scheduling.analyse_conflicts(events, device_sets, device_names=device_names)

    # Per-event enrichment: target counts and the live flag in the event's
    # own zone (a schedule may override the tenant zone). A play window
    # inside one of the campaign's own blackouts is never "live".
    blackouts: dict[tuple[str, dt.date], list[tuple[int, int]]] = {}
    for event in events:
        if event.kind == "blackout":
            blackouts.setdefault((event.campaign_id, event.date), []).append(
                (event.start_minute, event.end_minute)
            )
    zone_cache: dict[str, ZoneInfo] = {tz_name: tz}
    for event in events:
        screens = device_sets.get(event.campaign_id, set())
        event.screens = len(screens)
        event.locations = len({device_location[d] for d in screens if device_location.get(d)})
        if event.kind == "play" and event.campaign_status == CampaignStatus.PUBLISHED.value:
            zone = tz
            if event.timezone and event.timezone != tz_name:
                zone = zone_cache.get(event.timezone)
                if zone is None:
                    try:
                        zone = ZoneInfo(event.timezone)
                    except Exception:  # noqa: BLE001
                        zone = tz
                    zone_cache[event.timezone] = zone
            local = now.astimezone(zone)
            minute = local.hour * 60 + local.minute
            event.live = (
                event.date == local.date() and event.start_minute <= minute < event.end_minute
            ) and not any(
                start <= minute < end
                for start, end in blackouts.get((event.campaign_id, event.date), [])
            )

    # Presentation filters.
    scope = await _scope_devices(db, organization_id, filters)
    scoped_campaigns: set[str] | None = None
    if scope is not None:
        scoped_campaigns = {cid for cid, devs in device_sets.items() if devs & scope}
    visible = [e for e in events if _event_matches(e, filters, scoped_campaigns)]
    visible_campaigns = {e.campaign_id for e in visible}
    visible_conflicts = [
        c for c in conflicts if any(x["campaign_id"] in visible_campaigns for x in c["campaigns"])
    ]

    screens_covered: set[uuid.UUID] = set()
    for cid in visible_campaigns:
        screens_covered |= device_sets.get(cid, set())
    actionable = [c for c in visible_conflicts if c["severity"] != "low"]

    return {
        "range_start": range_start,
        "range_end": range_end,
        "timezone": tz_name,
        "now": {
            "at": now,
            "date": today,
            "minute": now_minute,
        },
        "events": visible,
        "conflicts": visible_conflicts,
        "summary": {
            "campaigns": len(visible_campaigns),
            "screens": len(screens_covered),
            "play_windows": sum(1 for e in visible if e.kind == "play"),
            "blackout_windows": sum(1 for e in visible if e.kind == "blackout"),
            "conflicts_actionable": len(actionable),
            "conflicts_high": sum(1 for c in actionable if c["severity"] == "high"),
            "conflicts_medium": sum(1 for c in actionable if c["severity"] == "medium"),
            "conflicts_low": len(visible_conflicts) - len(actionable),
            "conflicts_total_estate": sum(1 for c in conflicts if c["severity"] != "low"),
        },
        "conflict_count": len(actionable),
    }

