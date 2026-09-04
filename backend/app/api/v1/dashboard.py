"""Organization dashboard (SCR-02 redesign) — one read-only aggregate."""

import datetime as dt

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentTenantId, CurrentUser, user_permission_codes
from app.core.errors import ValidationAppError
from app.db.session import get_db
from app.schemas.envelope import success
from app.services import dashboard as dashboard_service
from app.services import entitlements as entitlements_service

router = APIRouter(prefix="/dashboard")


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
    access = dashboard_service.Access(
        None if user.is_superuser else user_permission_codes(user), features
    )
    data = await dashboard_service.build(
        db,
        tenant_id,
        user_id=user.id,
        access=access,
        range_start=range_start,
        range_end=range_end,
    )
    return success(data)
