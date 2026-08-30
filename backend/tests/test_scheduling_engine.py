"""Unit tests for the pure schedule evaluation engine (SRS §13, M10)."""

import datetime as dt
import uuid

from app.models import Campaign, Schedule
from app.services import scheduling


def make_schedule(**kw) -> Schedule:
    defaults = dict(
        id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        campaign_id=uuid.uuid4(),
        start_date=None,
        end_date=None,
        start_time=None,
        end_time=None,
        days_of_week=None,
        timezone=None,
        priority=50,
    )
    defaults.update(kw)
    return Schedule(**defaults)


def utc(year, month, day, hour=0, minute=0) -> dt.datetime:
    return dt.datetime(year, month, day, hour, minute, tzinfo=dt.UTC)


def test_always_active_when_unbounded():
    schedule = make_schedule()
    assert scheduling.is_schedule_active(schedule, utc(2026, 8, 29, 12), "UTC")


def test_date_range_inclusive_bounds():
    schedule = make_schedule(
        start_date=dt.date(2026, 9, 1), end_date=dt.date(2026, 9, 30)
    )
    assert not scheduling.is_schedule_active(schedule, utc(2026, 8, 31, 12), "UTC")
    assert scheduling.is_schedule_active(schedule, utc(2026, 9, 1, 0), "UTC")
    assert scheduling.is_schedule_active(schedule, utc(2026, 9, 30, 23), "UTC")
    assert not scheduling.is_schedule_active(schedule, utc(2026, 10, 1, 0), "UTC")


def test_time_window_in_target_timezone():
    # 09:00-18:00 evaluated in Asia/Kolkata (UTC+5:30).
    schedule = make_schedule(start_time=dt.time(9, 0), end_time=dt.time(18, 0))
    # 04:00 UTC == 09:30 IST -> active
    assert scheduling.is_schedule_active(schedule, utc(2026, 8, 29, 4, 0), "Asia/Kolkata")
    # 03:00 UTC == 08:30 IST -> inactive
    assert not scheduling.is_schedule_active(schedule, utc(2026, 8, 29, 3, 0), "Asia/Kolkata")
    # 12:30 UTC == 18:00 IST -> end is exclusive
    assert not scheduling.is_schedule_active(schedule, utc(2026, 8, 29, 12, 30), "Asia/Kolkata")


def test_schedule_own_timezone_beats_target():
    schedule = make_schedule(
        start_time=dt.time(9, 0), end_time=dt.time(18, 0), timezone="UTC"
    )
    # 04:00 UTC is inside the window in IST but outside in UTC; own tz wins.
    assert not scheduling.is_schedule_active(schedule, utc(2026, 8, 29, 4, 0), "Asia/Kolkata")
    assert scheduling.is_schedule_active(schedule, utc(2026, 8, 29, 9, 0), "Asia/Kolkata")


def test_days_of_week():
    # 2026-08-29 is a Saturday (weekday 5).
    weekday_only = make_schedule(days_of_week=[0, 1, 2, 3, 4])
    weekend_only = make_schedule(days_of_week=[5, 6])
    at = utc(2026, 8, 29, 12)
    assert not scheduling.is_schedule_active(weekday_only, at, "UTC")
    assert scheduling.is_schedule_active(weekend_only, at, "UTC")


def test_overnight_window_wraps_midnight():
    schedule = make_schedule(start_time=dt.time(22, 0), end_time=dt.time(2, 0))
    assert scheduling.is_schedule_active(schedule, utc(2026, 8, 29, 23, 0), "UTC")
    assert scheduling.is_schedule_active(schedule, utc(2026, 8, 30, 1, 30), "UTC")
    assert not scheduling.is_schedule_active(schedule, utc(2026, 8, 30, 3, 0), "UTC")


def test_overnight_window_respects_start_day_selection():
    # Saturday-night-only 22:00-02:00: active early Sunday, not early Saturday.
    schedule = make_schedule(
        start_time=dt.time(22, 0), end_time=dt.time(2, 0), days_of_week=[5]
    )
    assert scheduling.is_schedule_active(schedule, utc(2026, 8, 30, 1, 0), "UTC")  # Sun 01:00
    assert not scheduling.is_schedule_active(schedule, utc(2026, 8, 29, 1, 0), "UTC")  # Sat 01:00


def make_campaign(priority=50, schedules=None, created=None) -> Campaign:
    campaign = Campaign(
        id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        name=f"c-{priority}",
        priority=priority,
        status="draft",
    )
    campaign.created_at = created or dt.datetime(2026, 1, 1, tzinfo=dt.UTC)
    campaign.schedules = schedules or []
    return campaign


def test_resolver_picks_highest_campaign_priority():
    low = make_campaign(priority=10, schedules=[make_schedule()])
    high = make_campaign(priority=90, schedules=[make_schedule()])
    inactive = make_campaign(priority=100, schedules=[])  # no schedules -> never active
    winner = scheduling.resolve_active_campaign(
        [low, high, inactive], utc(2026, 8, 29, 12), "UTC"
    )
    assert winner is high


def test_resolver_ignores_campaigns_outside_window():
    morning = make_campaign(
        priority=50,
        schedules=[make_schedule(start_time=dt.time(6, 0), end_time=dt.time(12, 0))],
    )
    evening = make_campaign(
        priority=50,
        schedules=[make_schedule(start_time=dt.time(18, 0), end_time=dt.time(23, 0))],
        created=dt.datetime(2026, 1, 2, tzinfo=dt.UTC),
    )
    assert (
        scheduling.resolve_active_campaign([morning, evening], utc(2026, 8, 29, 8), "UTC")
        is morning
    )
    assert (
        scheduling.resolve_active_campaign([morning, evening], utc(2026, 8, 29, 20), "UTC")
        is evening
    )


def test_calendar_expansion_and_conflicts():
    campaign_a = make_campaign(
        priority=50,
        schedules=[
            make_schedule(start_time=dt.time(9, 0), end_time=dt.time(12, 0)),
        ],
    )
    campaign_b = make_campaign(
        priority=50,
        schedules=[
            make_schedule(start_time=dt.time(11, 0), end_time=dt.time(14, 0)),
        ],
    )
    campaign_c = make_campaign(  # different priority -> resolves cleanly, no conflict
        priority=90,
        schedules=[make_schedule(start_time=dt.time(9, 0), end_time=dt.time(18, 0))],
    )
    start = dt.date(2026, 9, 7)  # Monday
    end = dt.date(2026, 9, 9)
    events = scheduling.expand_calendar([campaign_a, campaign_b, campaign_c], start, end)
    assert len(events) == 9  # 3 schedules x 3 days
    conflicts = scheduling.detect_conflicts(events)
    # A and B overlap 11:00-12:00 at equal priority, each of the 3 days.
    assert len(conflicts) == 3
    assert all(a.campaign_priority == b.campaign_priority for a, b in conflicts)
    conflicted = [e for e in events if e.conflict]
    assert len(conflicted) == 6


def test_calendar_respects_dates_and_days():
    campaign = make_campaign(
        schedules=[
            make_schedule(
                start_date=dt.date(2026, 9, 8),
                end_date=dt.date(2026, 9, 8),
                days_of_week=[1],  # Tuesday; 2026-09-08 is a Tuesday
            )
        ]
    )
    events = scheduling.expand_calendar([campaign], dt.date(2026, 9, 7), dt.date(2026, 9, 13))
    assert [e.date for e in events] == [dt.date(2026, 9, 8)]


def test_expired_helper():
    schedule = make_schedule(end_date=dt.date(2026, 8, 1))
    assert scheduling.is_schedule_expired(schedule, dt.date(2026, 8, 29))
    assert not scheduling.is_schedule_expired(schedule, dt.date(2026, 8, 1))
    assert not scheduling.is_schedule_expired(make_schedule(), dt.date(2026, 8, 29))
