"""Usage layer (SaaS core): counters + metered events.

Dashboards and limit displays read `usage_counters`, refreshed by the
maintenance sweep — never repeated COUNT(*) per request. Metered
consumption (api_calls now; ai_credits in Phase 3) increments the current
month's counter and leaves a slim usage_event.
"""

import datetime as dt
import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Organization, UsageCounter, UsageEvent

logger = logging.getLogger("app.usage")

SNAPSHOT_METRICS = ("devices", "users", "storage_mb", "locations")
_METRIC_LIMIT_KEY = {
    "devices": "max_devices",
    "users": "max_users",
    "storage_mb": "max_storage_mb",
    "locations": "max_locations",
    "api_calls": "max_api_calls_month",
    "ai_credits": "ai_credits_month",
}


def month_period(today: dt.date | None = None) -> tuple[dt.date, dt.date]:
    today = today or datetime.now(UTC).date()
    start = today.replace(day=1)
    next_month = (start + dt.timedelta(days=32)).replace(day=1)
    return start, next_month - dt.timedelta(days=1)


async def _counter(
    db: AsyncSession, organization_id: uuid.UUID, metric: str
) -> UsageCounter:
    period_start, period_end = month_period()
    counter = (
        await db.execute(
            select(UsageCounter).where(
                UsageCounter.organization_id == organization_id,
                UsageCounter.metric == metric,
                UsageCounter.period_start == period_start,
            )
        )
    ).scalar_one_or_none()
    if counter is None:
        counter = UsageCounter(
            organization_id=organization_id,
            metric=metric,
            period_start=period_start,
            period_end=period_end,
        )
        db.add(counter)
        await db.flush()
    return counter


async def record_metered(
    db: AsyncSession,
    organization_id: uuid.UUID,
    metric: str,
    *,
    quantity: int = 1,
    ref: str | None = None,
    with_event: bool = False,
) -> None:
    counter = await _counter(db, organization_id, metric)
    counter.used_value += quantity
    counter.updated_at = datetime.now(UTC)
    if with_event:
        db.add(
            UsageEvent(
                organization_id=organization_id, metric=metric, quantity=quantity, ref=ref
            )
        )
    await db.flush()


async def metered_used(
    db: AsyncSession, organization_id: uuid.UUID, metric: str
) -> int:
    period_start, _ = month_period()
    counter = (
        await db.execute(
            select(UsageCounter.used_value).where(
                UsageCounter.organization_id == organization_id,
                UsageCounter.metric == metric,
                UsageCounter.period_start == period_start,
            )
        )
    ).scalar_one_or_none()
    return counter or 0


async def snapshot_usage(db: AsyncSession) -> int:
    """Beat sweep: refresh snapshot counters (devices/users/storage/
    locations) with current usage + effective limits for every org."""
    from sqlalchemy import func as sa_func

    from app.models import Location
    from app.services import entitlements as entitlements_service
    from app.services.tenant_admin import get_usage

    orgs = (await db.execute(select(Organization.id))).scalars().all()
    updated = 0
    for org_id in orgs:
        usage = await get_usage(db, org_id)
        effective = await entitlements_service.get_effective(db, org_id)
        location_count = (
            await db.execute(
                select(sa_func.count())
                .select_from(Location)
                .where(Location.organization_id == org_id, Location.status == "active")
            )
        ).scalar_one()
        values = {
            "devices": usage["devices"]["used"],
            "users": usage["users"]["used"],
            "storage_mb": int(usage["storage_mb"]["used"]),
            "locations": location_count,
        }
        for metric, used in values.items():
            counter = await _counter(db, org_id, metric)
            counter.used_value = used
            counter.limit_value = effective.limit(_METRIC_LIMIT_KEY[metric])
            counter.updated_at = datetime.now(UTC)
            updated += 1
        # Keep the metered api_calls counter's limit label fresh too.
        api_counter = await _counter(db, org_id, "api_calls")
        api_counter.limit_value = effective.limit("max_api_calls_month")
    await db.flush()
    return updated


async def usage_summary(db: AsyncSession, organization_id: uuid.UUID) -> list[dict]:
    period_start, _ = month_period()
    rows = (
        await db.execute(
            select(UsageCounter)
            .where(
                UsageCounter.organization_id == organization_id,
                UsageCounter.period_start == period_start,
            )
            .order_by(UsageCounter.metric)
        )
    ).scalars()
    return [
        {
            "metric": row.metric,
            "used": row.used_value,
            "limit": row.limit_value,
            "period_start": row.period_start.isoformat(),
            "period_end": row.period_end.isoformat(),
        }
        for row in rows
    ]
