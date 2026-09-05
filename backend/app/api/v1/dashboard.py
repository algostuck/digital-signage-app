"""Organization dashboard (SCR-02 redesign) — one read-only aggregate."""

import asyncio
import datetime as dt
import time

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentTenantId, CurrentUser, user_permission_codes
from app.core.errors import ValidationAppError
from app.db.session import get_db
from app.schemas.envelope import success
from app.services import dashboard as dashboard_service
from app.services import entitlements as entitlements_service

router = APIRouter(prefix="/dashboard")

# The dashboard polls every 30 s and several people in one tenant watch it
# during a demo or an incident. The aggregate runs ~15 queries; serving the
# same answer for a few seconds keeps p95 flat under concurrency, and the
# payload's `generated_at` makes the age visible ("Updated 12 s ago").
DASHBOARD_CACHE_TTL_SECONDS = 15
_cache: dict[tuple, tuple[float, dict]] = {}
# Single-flight: when eight viewers miss the cache in the same instant
# (page load after a deploy, the 30 s poll lining up), one builds and the
# rest read the result instead of each running the aggregate.
_locks: dict[tuple, asyncio.Lock] = {}


def _cache_get(key: tuple) -> dict | None:
    hit = _cache.get(key)
    if hit and hit[0] > time.monotonic():
        return hit[1]
    return None


def _cache_put(key: tuple, data: dict) -> None:
    if len(_cache) > 512:  # bounded; entries expire on their own
        now = time.monotonic()
        for k in [k for k, (exp, _) in _cache.items() if exp <= now]:
            _cache.pop(k, None)
    _cache[key] = (time.monotonic() + DASHBOARD_CACHE_TTL_SECONDS, data)


@router.get("/organization")
async def organization_dashboard(
    tenant_id: CurrentTenantId,
    user: CurrentUser,
    range_start: dt.date | None = Query(None, alias="from"),
    range_end: dt.date | None = Query(None, alias="to"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Everything the Organization Administrator's dashboard shows, scoped
    to the active tenant. No single permission gates the route: each
    section is included only when the caller holds its permission, so a
    Viewer gets the read-only picture and an approver additionally gets
    the approval queue. Nothing here writes."""
    today = dt.date.today()
    range_end = range_end or today
    range_start = range_start or (range_end - dt.timedelta(days=6))
    if range_end < range_start:
        raise ValidationAppError("'to' must not be before 'from'", field="to")
    if (range_end - range_start).days >= dashboard_service.MAX_RANGE_DAYS:
        raise ValidationAppError(
            f"Range is limited to {dashboard_service.MAX_RANGE_DAYS} days", field="to"
        )

    effective = await entitlements_service.get_effective(db, tenant_id)
    features = {key for key, value in effective.values.items() if value is True}
    codes = None if user.is_superuser else user_permission_codes(user)
    access = dashboard_service.Access(codes, features)
    key = (
        str(tenant_id),
        str(user.id),
        range_start.isoformat(),
        range_end.isoformat(),
        "*" if codes is None else tuple(sorted(codes)),
        tuple(sorted(features)),
    )
    if (cached := _cache_get(key)) is not None:
        return success(cached)
    lock = _locks.setdefault(key, asyncio.Lock())
    async with lock:
        if (cached := _cache_get(key)) is not None:
            return success(cached)
        data = await dashboard_service.build(
            db,
            tenant_id,
            user_id=user.id,
            access=access,
            range_start=range_start,
            range_end=range_end,
        )
        _cache_put(key, data)
    if len(_locks) > 512:
        _locks.clear()
    return success(data)
