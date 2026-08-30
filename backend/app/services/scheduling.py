"""Schedule evaluation engine (M10, SRS §13).

Pure functions over Schedule/Campaign rows — no I/O. The player manifest
builder (1I) and the calendar view both resolve through here, so cloud and
player agree on what is active.

Timezone rule (NFR-012): instants are UTC; a schedule's window is wall-clock
in its own timezone, falling back to the caller-provided target timezone
(device -> location -> organization).
"""

import datetime as dt
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from app.models import Campaign, Schedule

FULL_DAY_START = dt.time(0, 0)


def _window(schedule: Schedule) -> tuple[dt.time, dt.time | None]:
    """Returns (start, end); end None means midnight (exclusive end of day)."""
    return schedule.start_time or FULL_DAY_START, schedule.end_time


def _time_in_window(now: dt.time, start: dt.time, end: dt.time | None) -> bool:
    if end is None:
        return now >= start
    if end <= start:  # wraps past midnight, e.g. 22:00-02:00
        return now >= start or now < end
    return start <= now < end


def _date_in_range(day: dt.date, schedule: Schedule) -> bool:
    if schedule.start_date and day < schedule.start_date:
        return False
    if schedule.end_date and day > schedule.end_date:
        return False
    return True


def _day_selected(day: dt.date, schedule: Schedule) -> bool:
    """Weekday + monthly recurrence + exception dates (P2-SCH-002)."""
    if day.isoformat() in (schedule.exception_dates_json or []):
        return False
    days_of_month = (schedule.recurrence_json or {}).get("days_of_month")
    if days_of_month and day.day not in days_of_month:
        return False
    if schedule.days_of_week and day.weekday() not in schedule.days_of_week:
        return False
    return True


def _play_schedules(campaign: Campaign) -> list[Schedule]:
    return [s for s in campaign.schedules if getattr(s, "kind", "play") != "blackout"]


def _blackout_schedules(campaign: Campaign) -> list[Schedule]:
    return [s for s in campaign.schedules if getattr(s, "kind", "play") == "blackout"]


def is_blacked_out(campaign: Campaign, at_utc: dt.datetime, target_timezone: str) -> bool:
    """P2-CAM-004: an active blackout window suppresses the campaign."""
    return any(
        is_schedule_active(s, at_utc, target_timezone)
        for s in _blackout_schedules(campaign)
    )


def is_schedule_active(
    schedule: Schedule, at_utc: dt.datetime, target_timezone: str
) -> bool:
    """True when the schedule covers the UTC instant, evaluated in the
    schedule's own timezone (or the target's as fallback)."""
    tz = ZoneInfo(schedule.timezone or target_timezone)
    local = at_utc.astimezone(tz)
    start, end = _window(schedule)
    today_selected = _date_in_range(local.date(), schedule) and _day_selected(
        local.date(), schedule
    )

    overnight = end is not None and end <= start
    if not overnight:
        return today_selected and _time_in_window(local.time(), start, end)

    # Overnight window: the evening part belongs to today's occurrence, the
    # early-morning tail belongs to *yesterday's* occurrence.
    if today_selected and local.time() >= start:
        return True
    yesterday = local.date() - dt.timedelta(days=1)
    return (
        local.time() < end
        and _date_in_range(yesterday, schedule)
        and _day_selected(yesterday, schedule)
    )


def is_schedule_expired(schedule: Schedule, today: dt.date) -> bool:
    """FR-SCH-007: past its final date (in its own tz this is approximate by
    one day at most, which is acceptable for expiry housekeeping)."""
    return schedule.end_date is not None and schedule.end_date < today


def resolve_active_campaign(
    campaigns: list[Campaign], at_utc: dt.datetime, target_timezone: str
) -> Campaign | None:
    """Highest-priority campaign with an active schedule (SRS §13).

    Tie-break: campaign priority, then best matching schedule priority, then
    most recently created campaign. Campaigns without schedules never match.
    """
    best: tuple[int, int, dt.datetime] | None = None
    winner: Campaign | None = None
    for campaign in campaigns:
        active = [
            s
            for s in _play_schedules(campaign)
            if is_schedule_active(s, at_utc, target_timezone)
        ]
        if not active or is_blacked_out(campaign, at_utc, target_timezone):
            continue
        key = (
            campaign.priority,
            max(s.priority for s in active),
            campaign.created_at,
        )
        if best is None or key > best:
            best = key
            winner = campaign
    return winner


# --- calendar expansion & conflicts (FR-SCH-006, SCR-21) ---


@dataclass
class CalendarEvent:
    schedule_id: str
    campaign_id: str
    campaign_name: str
    schedule_name: str | None
    date: dt.date
    start_minute: int  # minutes-of-day, local to the schedule's timezone
    end_minute: int  # exclusive; 1440 = midnight
    priority: int
    campaign_priority: int
    timezone: str | None
    kind: str = "play"
    campaign_created_at: dt.datetime | None = None
    overnight: bool = False
    conflict: bool = False


def _day_segments(schedule: Schedule) -> list[tuple[int, int, bool]]:
    """Daily window as same-day minute segments; overnight windows split."""
    start, end = _window(schedule)
    start_minute = start.hour * 60 + start.minute
    if end is None:
        return [(start_minute, 1440, False)]
    end_minute = end.hour * 60 + end.minute
    if end_minute > start_minute:
        return [(start_minute, end_minute, False)]
    # Overnight: [start, 24:00) today plus [00:00, end) tomorrow.
    return [(start_minute, 1440, True), (0, end_minute, True)]


def expand_calendar(
    campaigns: list[Campaign], range_start: dt.date, range_end: dt.date
) -> list[CalendarEvent]:
    """One event per schedule per active day in [range_start, range_end]."""
    events: list[CalendarEvent] = []
    for campaign in campaigns:
        for schedule in campaign.schedules:
            segments = _day_segments(schedule)
            day = range_start
            while day <= range_end:
                if _date_in_range(day, schedule) and _day_selected(day, schedule):
                    start_minute, end_minute, overnight = segments[0]
                    events.append(
                        CalendarEvent(
                            schedule_id=str(schedule.id),
                            campaign_id=str(campaign.id),
                            campaign_name=campaign.name,
                            schedule_name=schedule.name,
                            date=day,
                            start_minute=start_minute,
                            end_minute=end_minute,
                            priority=schedule.priority,
                            campaign_priority=campaign.priority,
                            timezone=schedule.timezone,
                            kind=getattr(schedule, "kind", "play") or "play",
                            campaign_created_at=campaign.created_at,
                            overnight=overnight,
                        )
                    )
                day += dt.timedelta(days=1)
    return events


def detect_conflicts(events: list[CalendarEvent]) -> list[tuple[CalendarEvent, CalendarEvent]]:
    """Same-day, time-overlapping events from different campaigns with equal
    campaign priority: the resolver cannot deterministically pick by priority,
    so surface them (FR-SCH-006). Different priorities resolve cleanly and are
    not conflicts."""
    conflicts: list[tuple[CalendarEvent, CalendarEvent]] = []
    by_day: dict[dt.date, list[CalendarEvent]] = {}
    for event in events:
        if event.kind == "blackout":
            continue  # blackouts suppress, they never compete for playback
        by_day.setdefault(event.date, []).append(event)
    for day_events in by_day.values():
        for i, a in enumerate(day_events):
            for b in day_events[i + 1 :]:
                if a.campaign_id == b.campaign_id:
                    continue
                if a.campaign_priority != b.campaign_priority:
                    continue
                if a.start_minute < b.end_minute and b.start_minute < a.end_minute:
                    a.conflict = True
                    b.conflict = True
                    conflicts.append((a, b))
    return conflicts


def _resolution_key(event: CalendarEvent) -> tuple:
    """Mirrors resolve_active_campaign: campaign priority, schedule priority,
    newest campaign wins the final tie."""
    return (
        event.campaign_priority,
        event.priority,
        event.campaign_created_at or dt.datetime.min.replace(tzinfo=dt.UTC),
    )


def overlap_report(events: list[CalendarEvent]) -> list[dict]:
    """Dry-run conflict check (P2-SCH-004): every cross-campaign overlap with
    the deterministic winner per the resolution rule. Equal campaign priority
    is flagged as a true conflict (winner decided only by tie-breaks)."""
    report: list[dict] = []
    by_day: dict[dt.date, list[CalendarEvent]] = {}
    for event in events:
        if event.kind == "blackout":
            continue
        by_day.setdefault(event.date, []).append(event)
    for day in sorted(by_day):
        day_events = by_day[day]
        for i, a in enumerate(day_events):
            for b in day_events[i + 1 :]:
                if a.campaign_id == b.campaign_id:
                    continue
                if not (a.start_minute < b.end_minute and b.start_minute < a.end_minute):
                    continue
                winner = a if _resolution_key(a) > _resolution_key(b) else b
                equal_priority = a.campaign_priority == b.campaign_priority
                report.append(
                    {
                        "date": day.isoformat(),
                        "window": [
                            max(a.start_minute, b.start_minute),
                            min(a.end_minute, b.end_minute),
                        ],
                        "campaigns": [
                            {
                                "campaign_id": e.campaign_id,
                                "campaign_name": e.campaign_name,
                                "campaign_priority": e.campaign_priority,
                                "schedule_priority": e.priority,
                            }
                            for e in (a, b)
                        ],
                        "winner_campaign_id": winner.campaign_id,
                        "winner_campaign_name": winner.campaign_name,
                        "conflict": equal_priority,
                        "reason": (
                            "equal campaign priority — resolved only by schedule "
                            "priority and recency tie-breaks"
                            if equal_priority
                            else "higher campaign priority wins"
                        ),
                    }
                )
    return report
