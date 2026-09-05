"""Schedule evaluation engine (M10, SRS §13).

Pure functions over Schedule/Campaign rows — no I/O. The player manifest
builder (1I) and the calendar view both resolve through here, so cloud and
player agree on what is active.

Timezone rule (NFR-012): instants are UTC; a schedule's window is wall-clock
in its own timezone, falling back to the caller-provided target timezone
(device -> location -> organization).
"""

import datetime as dt
from dataclasses import dataclass, field
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
    # Workspace contract (docs/SCHEDULE_UX_AUDIT.md §10): filled by
    # expand_calendar / analyse_conflicts / the calendar service.
    campaign_status: str | None = None
    recurrence_type: str = "daily"
    recurrence_text: str = ""
    days_of_week: list[int] | None = None
    expired: bool = False
    live: bool = False
    screens: int = 0
    locations: int = 0
    conflict_ids: list[str] = field(default_factory=list)


WEEKDAY_ABBR = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def _ordinal(day: int) -> str:
    suffix = "th" if 11 <= day % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    return f"{day}{suffix}"


def _short_date(day: dt.date) -> str:
    return f"{day.day} {day.strftime('%b')}"


def recurrence_summary(schedule: Schedule) -> tuple[str, str]:
    """(type, human text) for a schedule's recurrence rule.

    type: once | daily | weekly | monthly. The text is what the calendar
    badge and the popover show, e.g. "Every Mon, Wed, Fri until 30 Sep,
    except 2 dates"; the API is the single place that words it.
    """
    days_of_week = sorted(set(schedule.days_of_week or []))
    days_of_month = sorted(set((schedule.recurrence_json or {}).get("days_of_month") or []))
    exceptions = len(schedule.exception_dates_json or [])
    start, end = schedule.start_date, schedule.end_date

    if start and end and start == end:
        return "once", f"Once on {_short_date(start)}"

    if days_of_month:
        kind = "monthly"
        text = "Monthly on " + ", ".join(_ordinal(d) for d in days_of_month)
        if days_of_week and len(days_of_week) < 7:
            text += " (" + ", ".join(WEEKDAY_ABBR[d] for d in days_of_week) + " only)"
    elif days_of_week and len(days_of_week) < 7:
        kind = "weekly"
        if days_of_week == [0, 1, 2, 3, 4]:
            text = "Every weekday"
        elif days_of_week == [5, 6]:
            text = "Every weekend"
        else:
            text = "Every " + ", ".join(WEEKDAY_ABBR[d] for d in days_of_week)
    else:
        kind = "daily"
        text = "Every day"

    if start and end:
        text += f" from {_short_date(start)} to {_short_date(end)}"
    elif end:
        text += f" until {_short_date(end)}"
    elif start:
        text += f" from {_short_date(start)}"
    if exceptions:
        text += f", except {exceptions} date{'s' if exceptions != 1 else ''}"
    return kind, text


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
    today = dt.date.today()
    for campaign in campaigns:
        status = getattr(campaign, "status", None)
        for schedule in campaign.schedules:
            segments = _day_segments(schedule)
            recurrence_type, recurrence_text = recurrence_summary(schedule)
            expired = is_schedule_expired(schedule, today)
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
                            campaign_status=status,
                            recurrence_type=recurrence_type,
                            recurrence_text=recurrence_text,
                            days_of_week=(
                                list(schedule.days_of_week) if schedule.days_of_week else None
                            ),
                            expired=expired,
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


# Campaigns in these states will play (or are about to); anything else is
# work in progress and only ever a low-severity, non-actionable conflict.
PLAYING_STATUSES = frozenset({"published", "approved"})

REASON_EQUAL = "equal_priority_shared_screens"
REASON_SHADOWED = "shadowed_by_priority"
REASON_BLACKOUT = "inside_blackout"

REASON_TEXT = {
    REASON_EQUAL: "Same campaign priority on shared screens — the player breaks the "
    "tie by schedule priority and campaign age, not by intent.",
    REASON_SHADOWED: "This window is entirely covered by a higher-priority campaign on "
    "the same screens, so it never plays there.",
    REASON_BLACKOUT: "This play window falls entirely inside one of the campaign's own "
    "blackout windows, so it never plays.",
}


def _overlaps(a: CalendarEvent, b: CalendarEvent) -> bool:
    return a.start_minute < b.end_minute and b.start_minute < a.end_minute


def _covers(outer: CalendarEvent, inner: CalendarEvent) -> bool:
    return outer.start_minute <= inner.start_minute and inner.end_minute <= outer.end_minute


def _severity(reason: str, *statuses: str | None) -> str:
    if any(status not in PLAYING_STATUSES for status in statuses):
        return "low"
    return "high" if reason == REASON_EQUAL else "medium"


def analyse_conflicts(
    events: list[CalendarEvent],
    device_sets: dict[str, set],
    *,
    device_names: dict | None = None,
) -> list[dict]:
    """The single conflict engine behind the schedule workspace
    (docs/SCHEDULE_UX_AUDIT.md §10.4).

    Unlike detect_conflicts, a conflict needs *shared screens*: two campaigns
    that never reach the same device cannot compete. Overlaps are grouped by
    (reason, schedule pair) across the range so a daily clash for a month is
    one actionable item with 30 dates, not 30 conflicts.

    Marks `event.conflict` (high/medium only) and `event.conflict_ids`.
    Returns conflicts sorted by severity then first date.
    """
    device_names = device_names or {}
    groups: dict[tuple, dict] = {}
    by_day: dict[dt.date, list[CalendarEvent]] = {}
    for event in events:
        by_day.setdefault(event.date, []).append(event)

    def screens_of(event: CalendarEvent) -> set:
        return device_sets.get(event.campaign_id, set())

    def record(
        reason: str,
        a: CalendarEvent,
        b: CalendarEvent,
        shared: set,
        winner: CalendarEvent | None,
    ) -> None:
        key = (reason, a.schedule_id, b.schedule_id)
        group = groups.get(key)
        if group is None:
            group = groups[key] = {
                "id": f"{reason[:2]}-{a.schedule_id[:8]}-{b.schedule_id[:8]}",
                "reason": reason,
                "message": REASON_TEXT[reason],
                "severity": _severity(reason, a.campaign_status, b.campaign_status),
                "window": [max(a.start_minute, b.start_minute), min(a.end_minute, b.end_minute)],
                "campaigns": [
                    {
                        "campaign_id": e.campaign_id,
                        "campaign_name": e.campaign_name,
                        "campaign_status": e.campaign_status,
                        "campaign_priority": e.campaign_priority,
                        "schedule_id": e.schedule_id,
                        "schedule_name": e.schedule_name,
                        "schedule_priority": e.priority,
                        "kind": e.kind,
                    }
                    for e in (a, b)
                ],
                "winner_campaign_id": winner.campaign_id if winner else None,
                "screens_affected": {
                    "count": len(shared),
                    "names": sorted(device_names.get(d, str(d)) for d in shared)[:5],
                },
                "_dates": [],
                "_events": [],
            }
        group["_dates"].append(a.date)
        group["_events"].extend((a, b))

    for day_events in by_day.values():
        plays = [e for e in day_events if e.kind != "blackout"]
        blackouts = [e for e in day_events if e.kind == "blackout"]
        for i, a in enumerate(plays):
            for b in plays[i + 1 :]:
                if a.campaign_id == b.campaign_id or not _overlaps(a, b):
                    continue
                shared = screens_of(a) & screens_of(b)
                if not shared:
                    continue
                if a.campaign_priority == b.campaign_priority:
                    winner = a if _resolution_key(a) > _resolution_key(b) else b
                    record(REASON_EQUAL, a, b, shared, winner)
                    continue
                winner, loser = (a, b) if a.campaign_priority > b.campaign_priority else (b, a)
                if _covers(winner, loser):
                    record(REASON_SHADOWED, loser, winner, shared, winner)
        for play in plays:
            for blackout in blackouts:
                if blackout.campaign_id == play.campaign_id and _covers(blackout, play):
                    record(REASON_BLACKOUT, play, blackout, screens_of(play), None)

    conflicts: list[dict] = []
    for group in groups.values():
        dates = sorted(set(group.pop("_dates")))
        group["dates"] = {
            "first": dates[0].isoformat(),
            "last": dates[-1].isoformat(),
            "count": len(dates),
        }
        group["suggestions"] = _suggestions(group)
        actionable = group["severity"] != "low"
        # Who needs attention: both sides of an equal-priority clash, only
        # the shadowed / suppressed window otherwise (the winner plays fine).
        loser_only = group["reason"] != REASON_EQUAL
        for position, event in enumerate(group.pop("_events")):
            if group["id"] not in event.conflict_ids:
                event.conflict_ids.append(group["id"])
            if not actionable or event.kind == "blackout":
                continue
            if loser_only and position % 2 == 1:
                continue
            event.conflict = True
        conflicts.append(group)

    rank = {"high": 0, "medium": 1, "low": 2}
    conflicts.sort(key=lambda c: (rank[c["severity"]], c["dates"]["first"], c["window"][0]))
    return conflicts


def _suggestions(group: dict) -> list[str]:
    a, b = group["campaigns"]
    reason = group["reason"]
    if reason == REASON_EQUAL:
        return [
            f"Give {a['campaign_name']} or {b['campaign_name']} a different campaign priority",
            "Move one window so they no longer overlap",
            "Narrow the targets so the campaigns stop sharing screens",
        ]
    if reason == REASON_SHADOWED:
        return [
            f"Raise the priority of {a['campaign_name']} above {b['campaign_priority']}",
            f"Move the window of {a['campaign_name']} outside {b['campaign_name']}",
            "Exclude the shared screens from one of the campaigns",
        ]
    return [
        "Shorten the blackout or move the play window outside it",
        "Delete the play window if the blackout is intended",
    ]


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
