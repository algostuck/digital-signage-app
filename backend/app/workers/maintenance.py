"""Celery maintenance tasks (queue: maintenance) + beat schedule.

Phase-2 sweeps ride the same worker: notification-rule webhook pushes,
subscription webhook deliveries (signed, retried), escalations, and
retention pruning. Every sweep is idempotent and safe to re-run — state
lives in the database, so worker restarts lose nothing (NFR2-08).
"""

import asyncio

from app.workers.celery_app import celery_app


def _run(coro_factory):
    async def wrapper():
        from app.db.session import get_session_factory

        async with get_session_factory()() as db:
            result = await coro_factory(db)
            await db.commit()
            return result

    return asyncio.run(wrapper())


@celery_app.task(name="app.workers.maintenance.detect_offline_devices")
def detect_offline_devices() -> int:
    from app.services import monitoring

    return _run(monitoring.detect_offline_devices)


@celery_app.task(name="app.workers.maintenance.push_rule_deliveries")
def push_rule_deliveries() -> dict:
    from app.services import notification_rules

    return _run(notification_rules.process_pending_deliveries)


@celery_app.task(name="app.workers.maintenance.push_webhook_deliveries")
def push_webhook_deliveries() -> dict:
    from app.services import webhooks

    return _run(webhooks.process_deliveries)


@celery_app.task(name="app.workers.maintenance.process_escalations")
def process_escalations() -> int:
    from app.services import notification_rules

    return _run(notification_rules.process_escalations)


@celery_app.task(name="app.workers.maintenance.prune_retention")
def prune_retention() -> dict:
    from app.services import tenant_admin

    return _run(tenant_admin.prune_retention)


@celery_app.task(name="app.workers.maintenance.push_event_deliveries")
def push_event_deliveries() -> dict:
    """P3 3A-1: signed domain-event pushes (backoff, dead-letter)."""
    from app.services import events

    return _run(events.process_deliveries)


@celery_app.task(name="app.workers.maintenance.refresh_data_sources")
def refresh_data_sources() -> dict:
    """P3 3A-2: keep data-source snapshots warm (guarded fetch, per-source
    refresh interval, last-known-good preserved on failure)."""
    from app.services import data_sources

    return _run(data_sources.refresh_due_sources)


@celery_app.task(name="app.workers.maintenance.reconcile_ad_bookings")
def reconcile_ad_bookings() -> dict:
    """P3 3D-1: link proof-of-play events to confirmed ad bookings."""
    from app.services import ads

    return _run(ads.reconcile_bookings)


@celery_app.task(name="app.workers.maintenance.aggregate_analytics")
def aggregate_analytics() -> dict:
    """P3 3D-2: idempotent daily aggregate recompute (late events heal)."""
    from app.services import analytics

    return _run(analytics.aggregate_daily)


@celery_app.task(name="app.workers.maintenance.run_data_exports")
def run_data_exports() -> dict:
    """P3 3D-2: scheduled dataset exports to the storage adapter."""
    from app.services import analytics

    return _run(analytics.run_due_exports)


@celery_app.task(name="app.workers.maintenance.detect_anomalies")
def detect_anomalies() -> dict:
    """P3 3D-3: deterministic anomaly scan over fleet telemetry."""
    from app.services import anomaly

    return _run(anomaly.detect)


@celery_app.task(name="app.workers.maintenance.security_sweep")
def security_sweep() -> dict:
    """P3 3E-3: credential-age policy violations (open/resolve)."""
    from app.services import security_center

    return _run(security_center.sweep_violations)


@celery_app.task(name="app.workers.maintenance.subscription_lifecycle")
def subscription_lifecycle() -> dict:
    """SaaS core: trial expiry, renewals, dunning ladder
    (past_due day 0 -> grace day 7 -> suspended day 14)."""
    from app.services import subscriptions

    return _run(subscriptions.run_lifecycle)


@celery_app.task(name="app.workers.maintenance.snapshot_usage")
def snapshot_usage() -> int:
    """SaaS core: refresh usage_counters so dashboards never COUNT(*) live."""
    from app.services import usage

    return _run(usage.snapshot_usage)


celery_app.conf.beat_schedule = {
    "detect-offline-devices": {
        "task": "app.workers.maintenance.detect_offline_devices",
        "schedule": 120.0,
    },
    "push-rule-deliveries": {
        "task": "app.workers.maintenance.push_rule_deliveries",
        "schedule": 60.0,
    },
    "push-webhook-deliveries": {
        "task": "app.workers.maintenance.push_webhook_deliveries",
        "schedule": 60.0,
    },
    "process-escalations": {
        "task": "app.workers.maintenance.process_escalations",
        "schedule": 300.0,
    },
    "prune-retention": {
        "task": "app.workers.maintenance.prune_retention",
        "schedule": 86400.0,  # daily
    },
    "push-event-deliveries": {
        "task": "app.workers.maintenance.push_event_deliveries",
        "schedule": 60.0,
    },
    "refresh-data-sources": {
        "task": "app.workers.maintenance.refresh_data_sources",
        "schedule": 60.0,
    },
    "reconcile-ad-bookings": {
        "task": "app.workers.maintenance.reconcile_ad_bookings",
        "schedule": 3600.0,  # hourly
    },
    "aggregate-analytics": {
        "task": "app.workers.maintenance.aggregate_analytics",
        "schedule": 86400.0,  # daily
    },
    "run-data-exports": {
        "task": "app.workers.maintenance.run_data_exports",
        "schedule": 86400.0,  # daily
    },
    "detect-anomalies": {
        "task": "app.workers.maintenance.detect_anomalies",
        "schedule": 3600.0,  # hourly
    },
    "security-sweep": {
        "task": "app.workers.maintenance.security_sweep",
        "schedule": 86400.0,  # daily
    },
    "subscription-lifecycle": {
        "task": "app.workers.maintenance.subscription_lifecycle",
        "schedule": 3600.0,  # hourly
    },
    "snapshot-usage": {
        "task": "app.workers.maintenance.snapshot_usage",
        "schedule": 900.0,  # every 15 minutes
    },
}
