"""Operations APIs: dashboard/monitoring, audit trail, notifications, reports."""

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    CurrentTenantId,
    CurrentUser,
    PageParams,
    require_entitlement,
    require_permissions,
)
from app.db.session import get_db
from app.models import AuditLog, Deployment, Notification, User
from app.schemas.envelope import success
from app.services import audit as audit_service
from app.services import monitoring as monitoring_service
from app.services import notifications as notifications_service
from app.services import reports as reports_service

router = APIRouter()


@router.get("/monitoring/summary", dependencies=[require_permissions("monitoring.view")])
async def monitoring_summary(
    tenant_id: CurrentTenantId, user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> dict:
    data = await monitoring_service.summary(db, tenant_id)
    data["notifications_unread"] = await notifications_service.unread_count(db, tenant_id, user.id)

    recent = await db.execute(
        select(Deployment)
        .where(Deployment.organization_id == tenant_id)
        .order_by(Deployment.created_at.desc())
        .limit(5)
    )
    from app.api.v1.deployments import deployment_out

    data["recent_deployments"] = [
        await deployment_out(db, tenant_id, d) for d in recent.scalars().all()
    ]

    activity = await db.execute(
        select(AuditLog)
        .where(AuditLog.organization_id == tenant_id)
        .order_by(AuditLog.created_at.desc())
        .limit(8)
    )
    rows = list(activity.scalars().all())
    user_ids = {row.user_id for row in rows if row.user_id}
    user_names: dict = {}
    if user_ids:
        users = await db.execute(select(User.id, User.full_name).where(User.id.in_(user_ids)))
        user_names = dict(users.all())
    data["recent_activity"] = [_audit_out(row, user_names) for row in rows]
    return success(data)


@router.get("/monitoring/devices", dependencies=[require_permissions("monitoring.view")])
async def monitoring_devices(
    tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    return success(await monitoring_service.device_feed(db, tenant_id))


@router.get("/monitoring/fleet-health", dependencies=[require_permissions("monitoring.view")])
async def fleet_health(tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)) -> dict:
    """P2-MON-001: rollups by organization, location subtree and group."""
    return success(await monitoring_service.fleet_health(db, tenant_id))


@router.get("/monitoring/thresholds", dependencies=[require_permissions("monitoring.view")])
async def get_thresholds(tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)) -> dict:
    from app.services.organization import get_monitoring_thresholds

    return success(await get_monitoring_thresholds(db, tenant_id))


@router.put("/monitoring/thresholds", dependencies=[require_permissions("settings.manage")])
async def put_thresholds(
    body: dict,
    tenant_id: CurrentTenantId,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """P2-MON-002: per-tenant offline/storage/version thresholds."""
    from app.services.organization import update_monitoring_thresholds

    return success(await update_monitoring_thresholds(db, tenant_id, body, user_id=user.id))


# --- audit ---


def _audit_out(row: AuditLog, user_names: dict) -> dict:
    return {
        "id": str(row.id),
        "user_id": str(row.user_id) if row.user_id else None,
        "user_name": user_names.get(row.user_id),
        "action": row.action,
        "entity_type": row.entity_type,
        "entity_id": row.entity_id,
        "before": row.before_json,
        "after": row.after_json,
        "ip_address": row.ip_address,
        "request_id": row.request_id,
        "created_at": row.created_at.isoformat(),
    }


@router.get("/audit-logs", dependencies=[require_permissions("audit.view")])
async def audit_logs(
    tenant_id: CurrentTenantId,
    pagination: PageParams,
    action: str | None = Query(None, max_length=60),
    entity_type: str | None = Query(None, max_length=40),
    user_id: uuid.UUID | None = None,
    date_from: dt.date | None = Query(None, alias="from"),
    date_to: dt.date | None = Query(None, alias="to"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    rows, total = await audit_service.search(
        db,
        tenant_id,
        action=action,
        entity_type=entity_type,
        user_id=user_id,
        date_from=date_from,
        date_to=date_to,
        page=pagination.page,
        page_size=pagination.page_size,
    )
    user_ids = {row.user_id for row in rows if row.user_id}
    user_names: dict = {}
    if user_ids:
        users = await db.execute(select(User.id, User.full_name).where(User.id.in_(user_ids)))
        user_names = dict(users.all())
    return success(
        [_audit_out(row, user_names) for row in rows],
        page=pagination.page,
        page_size=pagination.page_size,
        total=total,
    )


# --- notifications ---


def _notification_out(row: Notification) -> dict:
    return {
        "id": str(row.id),
        "type": row.type,
        "severity": row.severity,
        "title": row.title,
        "message": row.message,
        "payload": row.payload_json,
        "read_at": row.read_at.isoformat() if row.read_at else None,
        "created_at": row.created_at.isoformat(),
    }


@router.get("/notifications", dependencies=[require_permissions("notifications.view")])
async def notifications_inbox(
    tenant_id: CurrentTenantId,
    user: CurrentUser,
    pagination: PageParams,
    unread_only: bool = Query(False),
    db: AsyncSession = Depends(get_db),
) -> dict:
    rows, total = await notifications_service.inbox(
        db,
        tenant_id,
        user.id,
        unread_only=unread_only,
        page=pagination.page,
        page_size=pagination.page_size,
    )
    return success(
        [_notification_out(row) for row in rows],
        page=pagination.page,
        page_size=pagination.page_size,
        total=total,
    )


@router.post(
    "/notifications/{notification_id}/read",
    dependencies=[require_permissions("notifications.view")],
)
async def mark_notification_read(
    notification_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    row = await notifications_service.mark_read(db, tenant_id, user.id, notification_id)
    return success(_notification_out(row))


@router.post("/notifications/read-all", dependencies=[require_permissions("notifications.view")])
async def mark_all_notifications_read(
    tenant_id: CurrentTenantId, user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> dict:
    count = await notifications_service.mark_all_read(db, tenant_id, user.id)
    return success({"marked_read": count})


# --- reports ---


@router.get("/reports/deployments", dependencies=[require_permissions("reports.view")])
async def report_deployments(
    tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    return success(await reports_service.deployments_report(db, tenant_id))


@router.get(
    "/reports/playback",
    dependencies=[require_permissions("reports.view"), require_entitlement("proof_of_play")],
)
async def report_playback(
    tenant_id: CurrentTenantId,
    date_from: dt.date | None = Query(None, alias="from"),
    date_to: dt.date | None = Query(None, alias="to"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return success(
        await reports_service.playback_report(db, tenant_id, date_from=date_from, date_to=date_to)
    )


@router.get(
    "/reports/proof-of-play",
    dependencies=[require_permissions("reports.view"), require_entitlement("proof_of_play")],
)
async def report_proof_of_play(
    tenant_id: CurrentTenantId,
    date_from: dt.date | None = Query(None),
    date_to: dt.date | None = Query(None),
    group_by: str = Query("campaign", max_length=20),
    campaign_id: uuid.UUID | None = Query(None),
    location_id: uuid.UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """P2-RPT-001: playback lifecycle rollup by dimension (P2-17 builder core)."""
    return success(
        await reports_service.proof_of_play(
            db,
            tenant_id,
            date_from=date_from,
            date_to=date_to,
            group_by=group_by,
            campaign_id=campaign_id,
            location_id=location_id,
        )
    )


@router.get(
    "/reports/campaign-performance",
    dependencies=[require_permissions("reports.view"), require_entitlement("advanced_analytics")],
)
async def report_campaign_performance(
    tenant_id: CurrentTenantId,
    date_from: dt.date | None = Query(None),
    date_to: dt.date | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return success(
        await reports_service.campaign_performance(
            db, tenant_id, date_from=date_from, date_to=date_to
        )
    )


@router.get("/reports/device-uptime", dependencies=[require_permissions("reports.view")])
async def report_device_uptime(
    tenant_id: CurrentTenantId,
    date_from: dt.date | None = Query(None),
    date_to: dt.date | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    today = dt.date.today()
    return success(
        await reports_service.device_uptime(
            db,
            tenant_id,
            date_from=date_from or today - dt.timedelta(days=7),
            date_to=date_to or today,
        )
    )


@router.post("/reports/export", dependencies=[require_permissions("reports.export")])
async def export_report(
    body: dict,
    tenant_id: CurrentTenantId,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """P2-RPT-004: CSV/XLSX file download for any operational report."""
    from fastapi import Response

    from app.services import audit
    from app.services import report_export as export_service

    report = str(body.get("report") or "")
    format = str(body.get("format") or "csv")
    filters = body.get("filters")
    if filters is None:
        filters = {}
    if not isinstance(filters, dict):
        from app.core.errors import ValidationAppError

        raise ValidationAppError("filters must be an object", field="filters")
    if report == "audit":
        # Audit exports need audit.view on top of reports.export (P2-22).
        from app.api.deps import user_permission_codes
        from app.core.errors import ForbiddenError

        if not user.is_superuser and "audit.view" not in user_permission_codes(user):
            raise ForbiddenError("Missing permission: audit.view")
    rows = await export_service.run_report(db, tenant_id, report, filters)
    content, media_type = export_service.render(rows, format)
    await audit.record(
        db,
        tenant_id,
        action="REPORT_EXPORTED",
        entity_type="report",
        entity_id=report,
        after={"format": format, "rows": len(rows), "filters": filters},
        user_id=user.id,
    )
    filename = f"{report}-{dt.date.today().isoformat()}.{format}"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/reports/locations", dependencies=[require_permissions("reports.view")])
async def report_locations(tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)) -> dict:
    return success(await reports_service.locations_report(db, tenant_id))
