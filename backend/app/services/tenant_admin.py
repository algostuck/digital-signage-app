"""Tenant administration (P2-M11) + retention compliance (P2-AUD-003).

Quotas (P2-TNT-002) live in organizations.quotas_json and are enforced at
the choke points that create the governed resources (device registration,
user creation, upload sessions). Retention (NFR2-06) lives in
organizations.settings_json.retention_days, clamped to platform floors and
ceilings — audit logs cannot be pruned below the compliance floor — and is
applied by the prune_retention maintenance sweep, which is itself audited.
"""

import datetime as dt
import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BusinessRuleError, ValidationAppError
from app.models import (
    Asset,
    AssetVersion,
    AuditLog,
    DecisionLog,
    Device,
    DeviceEvent,
    DeviceHeartbeat,
    DomainEvent,
    EventDelivery,
    Notification,
    Organization,
    PlaybackEvent,
    User,
    WebhookDelivery,
)

logger = logging.getLogger("app.tenant_admin")

QUOTA_KEYS = ("max_devices", "max_users", "max_storage_mb")

# key -> (floor_days, ceiling_days, default_days)
RETENTION_POLICY: dict[str, tuple[int, int, int]] = {
    "device_heartbeats": (1, 365, 30),
    "device_events": (1, 730, 90),
    "playback_events": (7, 1095, 365),
    "notifications": (1, 365, 90),
    "webhook_deliveries": (1, 365, 30),
    "audit_logs": (90, 3650, 365),  # compliance floor: 90 days minimum
    # Phase-3 streams: bounded raw history, aggregate-fed later.
    "domain_events": (1, 730, 90),
    "event_deliveries": (1, 365, 30),
    "data_source_snapshots": (1, 90, 14),
    "decision_log": (1, 365, 30),
}


# --- quotas (P2-TNT-002) ---


async def get_usage(db: AsyncSession, organization_id: uuid.UUID) -> dict:
    # Limits shown are the EFFECTIVE ones: plan entitlements min-combined
    # with the platform quota overrides (SaaS core supersedes raw quotas).
    from app.services import entitlements as entitlements_service

    effective = await entitlements_service.get_effective(db, organization_id)
    devices = (
        await db.execute(
            select(func.count()).where(
                Device.organization_id == organization_id,
                Device.status != "decommissioned",
            )
        )
    ).scalar_one()
    users = (
        await db.execute(
            select(func.count()).where(
                User.organization_id == organization_id, User.status == "active"
            )
        )
    ).scalar_one()
    storage_bytes = (
        await db.execute(
            select(func.coalesce(func.sum(AssetVersion.size_bytes), 0))
            .join(Asset, Asset.id == AssetVersion.asset_id)
            .where(Asset.organization_id == organization_id)
        )
    ).scalar_one()
    return {
        "devices": {"used": devices, "limit": effective.limit("max_devices")},
        "users": {"used": users, "limit": effective.limit("max_users")},
        "storage_mb": {
            "used": round(storage_bytes / (1024 * 1024), 2),
            "limit": effective.limit("max_storage_mb"),
        },
    }


async def update_quotas(
    db: AsyncSession,
    organization_id: uuid.UUID,
    values: dict,
    *,
    user_id: uuid.UUID | None = None,
) -> dict:
    unknown = set(values) - set(QUOTA_KEYS)
    if unknown:
        raise ValidationAppError(f"Unknown quota keys: {sorted(unknown)}")
    for key, value in values.items():
        if value is not None and (not isinstance(value, int) or value < 1):
            raise ValidationAppError(f"{key} must be a positive integer or null", field=key)
    org = await db.get(Organization, organization_id)
    quotas = dict(org.quotas_json or {})
    for key, value in values.items():
        if value is None:
            quotas.pop(key, None)
        else:
            quotas[key] = value
    org.quotas_json = quotas
    await db.flush()

    from app.services import audit

    await audit.record(
        db,
        organization_id,
        action="QUOTAS_UPDATED",
        entity_type="organization",
        entity_id=organization_id,
        after=quotas,
        user_id=user_id,
    )
    return quotas


# The ensure_* gates delegate to the entitlement engine (SaaS core): the
# effective limit is the plan entitlement min-combined with any platform
# quota override, and growth is refused outside GROWTH_ALLOWED_STATUSES.


async def ensure_device_quota(db: AsyncSession, organization_id: uuid.UUID) -> None:
    from app.services import entitlements as entitlements_service

    await entitlements_service.ensure_subscription_allows(
        db, organization_id, "device_register"
    )
    used = (
        await db.execute(
            select(func.count()).where(
                Device.organization_id == organization_id,
                Device.status != "decommissioned",
            )
        )
    ).scalar_one()
    await entitlements_service.ensure_limit(
        db, organization_id, "max_devices", used, resource_label="Device"
    )


async def ensure_user_quota(db: AsyncSession, organization_id: uuid.UUID) -> None:
    from app.services import entitlements as entitlements_service

    await entitlements_service.ensure_subscription_allows(db, organization_id, "user_create")
    used = (
        await db.execute(
            select(func.count()).where(
                User.organization_id == organization_id, User.status == "active"
            )
        )
    ).scalar_one()
    await entitlements_service.ensure_limit(
        db, organization_id, "max_users", used, resource_label="User"
    )


async def ensure_storage_quota(
    db: AsyncSession, organization_id: uuid.UUID, incoming_bytes: int
) -> None:
    from app.services import entitlements as entitlements_service

    await entitlements_service.ensure_subscription_allows(
        db, organization_id, "content_upload"
    )
    effective = await entitlements_service.get_effective(db, organization_id)
    limit_mb = effective.limit("max_storage_mb")
    if limit_mb is None:
        return
    used = (
        await db.execute(
            select(func.coalesce(func.sum(AssetVersion.size_bytes), 0))
            .join(Asset, Asset.id == AssetVersion.asset_id)
            .where(Asset.organization_id == organization_id)
        )
    ).scalar_one()
    if used + incoming_bytes > limit_mb * 1024 * 1024:
        raise BusinessRuleError(
            f"Storage limit reached ({round(used / 1048576, 1)} of {limit_mb} MB used). "
            "Upgrade your subscription."
        )


# --- retention (P2-AUD-003, NFR2-06) ---


async def get_retention(db: AsyncSession, organization_id: uuid.UUID) -> dict:
    org = await db.get(Organization, organization_id)
    stored = (org.settings_json or {}).get("retention_days") or {}
    return {
        key: {
            "days": stored.get(key, default),
            "floor": floor,
            "ceiling": ceiling,
        }
        for key, (floor, ceiling, default) in RETENTION_POLICY.items()
    }


async def update_retention(
    db: AsyncSession,
    organization_id: uuid.UUID,
    values: dict,
    *,
    user_id: uuid.UUID | None = None,
) -> dict:
    unknown = set(values) - set(RETENTION_POLICY)
    if unknown:
        raise ValidationAppError(f"Unknown retention keys: {sorted(unknown)}")
    for key, days in values.items():
        floor, ceiling, _ = RETENTION_POLICY[key]
        if not isinstance(days, int) or not floor <= days <= ceiling:
            raise ValidationAppError(
                f"{key} must be {floor}..{ceiling} days (platform limits)", field=key
            )
    org = await db.get(Organization, organization_id)
    settings_json = dict(org.settings_json or {})
    retention = dict(settings_json.get("retention_days") or {})
    retention.update(values)
    settings_json["retention_days"] = retention
    org.settings_json = settings_json
    await db.flush()

    from app.services import audit

    await audit.record(
        db,
        organization_id,
        action="RETENTION_UPDATED",
        entity_type="organization",
        entity_id=organization_id,
        after=retention,
        user_id=user_id,
    )
    return await get_retention(db, organization_id)


async def _prune_org(db: AsyncSession, org_id: uuid.UUID) -> dict[str, int]:
    retention = await get_retention(db, org_id)
    now = datetime.now(UTC)
    device_ids = select(Device.id).where(Device.organization_id == org_id)

    def cutoff(key: str) -> datetime:
        return now - dt.timedelta(days=retention[key]["days"])

    statements = {
        "device_heartbeats": delete(DeviceHeartbeat).where(
            DeviceHeartbeat.device_id.in_(device_ids),
            DeviceHeartbeat.observed_at < cutoff("device_heartbeats"),
        ),
        "device_events": delete(DeviceEvent).where(
            DeviceEvent.device_id.in_(device_ids),
            DeviceEvent.event_at < cutoff("device_events"),
        ),
        "playback_events": delete(PlaybackEvent).where(
            PlaybackEvent.organization_id == org_id,
            PlaybackEvent.started_at < cutoff("playback_events"),
        ),
        "notifications": delete(Notification).where(
            Notification.organization_id == org_id,
            Notification.created_at < cutoff("notifications"),
        ),
        "webhook_deliveries": delete(WebhookDelivery).where(
            WebhookDelivery.organization_id == org_id,
            WebhookDelivery.created_at < cutoff("webhook_deliveries"),
        ),
        "audit_logs": delete(AuditLog).where(
            AuditLog.organization_id == org_id,
            AuditLog.created_at < cutoff("audit_logs"),
        ),
        "domain_events": delete(DomainEvent).where(
            DomainEvent.organization_id == org_id,
            DomainEvent.occurred_at < cutoff("domain_events"),
        ),
        "decision_log": delete(DecisionLog).where(
            DecisionLog.organization_id == org_id,
            DecisionLog.decided_at < cutoff("decision_log"),
        ),
        "event_deliveries": delete(EventDelivery).where(
            EventDelivery.organization_id == org_id,
            EventDelivery.created_at < cutoff("event_deliveries"),
        ),
    }
    pruned: dict[str, int] = {}
    for key, statement in statements.items():
        result = await db.execute(statement)
        if result.rowcount:
            pruned[key] = result.rowcount

    # Data-source snapshots (3A-2): prune by age but ALWAYS keep each
    # source's newest valid snapshot — last-known-good must survive.
    from app.models import DataSource, DataSourceSnapshot

    source_ids = select(DataSource.id).where(DataSource.organization_id == org_id)
    keep = (
        select(DataSourceSnapshot.id)
        .where(DataSourceSnapshot.valid.is_(True))
        .distinct(DataSourceSnapshot.source_id)
        .order_by(DataSourceSnapshot.source_id, DataSourceSnapshot.fetched_at.desc())
    )
    result = await db.execute(
        delete(DataSourceSnapshot).where(
            DataSourceSnapshot.source_id.in_(source_ids),
            DataSourceSnapshot.fetched_at < cutoff("data_source_snapshots"),
            DataSourceSnapshot.id.not_in(keep),
        )
    )
    if result.rowcount:
        pruned["data_source_snapshots"] = result.rowcount
    return pruned


async def prune_retention(db: AsyncSession) -> dict:
    """Maintenance sweep: deletes rows past each tenant's retention window.
    Device-scoped tables are pruned via the org's device ids; the sweep
    itself leaves an audit record per organization that lost rows."""
    from app.services import audit

    orgs = (await db.execute(select(Organization.id))).scalars().all()
    totals: dict[str, int] = {}
    for org_id in orgs:
        pruned = await _prune_org(db, org_id)
        if pruned:
            await audit.record(
                db,
                org_id,
                action="RETENTION_PRUNED",
                entity_type="organization",
                entity_id=org_id,
                after=pruned,
            )
            logger.info("Retention pruned for org %s: %s", org_id, pruned)
            for key, count in pruned.items():
                totals[key] = totals.get(key, 0) + count
    await db.flush()
    return totals
