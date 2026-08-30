"""Analytics platform (P3-M11, slice 3D-2).

Semantic metrics are defined ONCE here (single source of truth) and used by
both the aggregation sweep and the read APIs. Aggregation is an idempotent
per-day recompute over raw truth (late events self-heal on the next run);
reconciliation proves aggregates against raw counts on demand.

Data exports render a dataset window through the 2I engine and write the
file to the storage adapter — the warehouse hand-off, not a warehouse.
"""

import datetime as dt
import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError, ValidationAppError
from app.models import (
    AnalyticsAggregate,
    DataExport,
    Organization,
    PlaybackEvent,
)
from app.models.analytics import DataExportState

logger = logging.getLogger("app.analytics")

# Semantic metric definitions (P3-M11 "semantic metrics single-source").
METRICS: dict[str, str] = {
    "plays": "Playback events started",
    "completed": "Playback events that finished successfully",
    "completion_rate_pct": "completed / plays * 100",
    "devices": "Distinct devices that played",
}

DIMENSIONS = ("org", "campaign", "device", "asset")
EXPORT_DATASETS = ("playback_events", "analytics_aggregates", "ad_performance")


def _metrics_row(plays: int, completed: int, devices: int) -> dict:
    return {
        "plays": plays,
        "completed": completed,
        "completion_rate_pct": round(100 * completed / plays, 1) if plays else 0.0,
        "devices": devices,
    }


async def aggregate_daily(
    db: AsyncSession, *, for_date: dt.date | None = None
) -> dict:
    """Idempotent recompute of one day's aggregates for every org."""
    day = for_date or (datetime.now(UTC).date() - timedelta(days=1))
    start = datetime.combine(day, dt.time.min, UTC)
    end = datetime.combine(day, dt.time.max, UTC)
    orgs = (await db.execute(select(Organization.id))).scalars().all()
    written = 0
    for org_id in orgs:
        for dimension in DIMENSIONS:
            column = {
                "org": None,
                "campaign": PlaybackEvent.campaign_id,
                "device": PlaybackEvent.device_id,
                "asset": PlaybackEvent.asset_id,
            }[dimension]
            group_cols = [column] if column is not None else []
            query = (
                select(
                    *(group_cols),
                    func.count().label("plays"),
                    func.count()
                    .filter(PlaybackEvent.result == "completed")
                    .label("completed"),
                    func.count(func.distinct(PlaybackEvent.device_id)).label("devices"),
                )
                .where(
                    PlaybackEvent.organization_id == org_id,
                    PlaybackEvent.started_at >= start,
                    PlaybackEvent.started_at <= end,
                )
            )
            if group_cols:
                query = query.group_by(*group_cols)
            rows = (await db.execute(query)).all()
            for row in rows:
                if column is not None:
                    dimension_id, plays, completed, devices = row
                    if dimension_id is None:
                        continue
                else:
                    plays, completed, devices = row
                    dimension_id = None
                    if plays == 0:
                        continue
                existing = (
                    await db.execute(
                        select(AnalyticsAggregate).where(
                            AnalyticsAggregate.organization_id == org_id,
                            AnalyticsAggregate.grain_date == day,
                            AnalyticsAggregate.dimension_type == dimension,
                            AnalyticsAggregate.dimension_id == dimension_id,
                        )
                    )
                ).scalar_one_or_none()
                metrics = _metrics_row(plays, completed, devices)
                if existing is None:
                    db.add(
                        AnalyticsAggregate(
                            organization_id=org_id,
                            grain_date=day,
                            dimension_type=dimension,
                            dimension_id=dimension_id,
                            metrics_json=metrics,
                        )
                    )
                else:
                    existing.metrics_json = metrics
                    existing.computed_at = datetime.now(UTC)
                written += 1
    await db.flush()
    return {"date": day.isoformat(), "rows": written}


async def list_aggregates(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    dimension_type: str,
    date_from: dt.date,
    date_to: dt.date,
) -> list[dict]:
    if dimension_type not in DIMENSIONS:
        raise ValidationAppError(f"dimension_type must be one of {DIMENSIONS}")
    rows = (
        await db.execute(
            select(AnalyticsAggregate)
            .where(
                AnalyticsAggregate.organization_id == organization_id,
                AnalyticsAggregate.dimension_type == dimension_type,
                AnalyticsAggregate.grain_date >= date_from,
                AnalyticsAggregate.grain_date <= date_to,
            )
            .order_by(AnalyticsAggregate.grain_date, AnalyticsAggregate.dimension_id)
        )
    ).scalars().all()
    return [
        {
            "date": row.grain_date.isoformat(),
            "dimension_type": row.dimension_type,
            "dimension_id": str(row.dimension_id) if row.dimension_id else None,
            **row.metrics_json,
        }
        for row in rows
    ]


async def reconcile(
    db: AsyncSession, organization_id: uuid.UUID, *, for_date: dt.date
) -> dict:
    """Aggregate totals must equal raw counts — the independent check."""
    start = datetime.combine(for_date, dt.time.min, UTC)
    end = datetime.combine(for_date, dt.time.max, UTC)
    raw = (
        await db.execute(
            select(func.count()).where(
                PlaybackEvent.organization_id == organization_id,
                PlaybackEvent.started_at >= start,
                PlaybackEvent.started_at <= end,
            )
        )
    ).scalar_one()
    org_row = (
        await db.execute(
            select(AnalyticsAggregate).where(
                AnalyticsAggregate.organization_id == organization_id,
                AnalyticsAggregate.grain_date == for_date,
                AnalyticsAggregate.dimension_type == "org",
            )
        )
    ).scalar_one_or_none()
    aggregated = org_row.metrics_json.get("plays", 0) if org_row else 0
    return {
        "date": for_date.isoformat(),
        "raw_plays": raw,
        "aggregated_plays": aggregated,
        "consistent": raw == aggregated,
        "delta": raw - aggregated,
    }


# --- scheduled data exports ---


async def list_exports(db: AsyncSession, organization_id: uuid.UUID) -> list[DataExport]:
    rows = await db.execute(
        select(DataExport)
        .where(DataExport.organization_id == organization_id)
        .order_by(DataExport.name)
    )
    return list(rows.scalars().all())


async def create_export(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    name: str,
    dataset: str,
    cadence: str = "daily",
    user_id: uuid.UUID | None = None,
) -> DataExport:
    if dataset not in EXPORT_DATASETS:
        raise ValidationAppError(
            f"dataset must be one of {EXPORT_DATASETS}", field="dataset"
        )
    if cadence not in ("daily",):
        raise ValidationAppError("cadence must be 'daily'", field="cadence")
    exists = (
        await db.execute(
            select(DataExport).where(
                DataExport.organization_id == organization_id, DataExport.name == name
            )
        )
    ).scalar_one_or_none()
    if exists is not None:
        raise ConflictError("An export with this name already exists", field="name")
    export = DataExport(
        organization_id=organization_id,
        name=name,
        dataset=dataset,
        schedule_json={"cadence": cadence},
        created_by=user_id,
    )
    db.add(export)
    await db.flush()

    from app.services import audit

    await audit.record(
        db, organization_id, action="DATA_EXPORT_CREATED",
        entity_type="data_export", entity_id=export.id,
        after={"name": name, "dataset": dataset}, user_id=user_id,
    )
    return export


async def delete_export(
    db: AsyncSession, organization_id: uuid.UUID, export_id: uuid.UUID
) -> None:
    export = (
        await db.execute(
            select(DataExport).where(
                DataExport.organization_id == organization_id, DataExport.id == export_id
            )
        )
    ).scalar_one_or_none()
    if export is None:
        raise NotFoundError("Data export not found")
    await db.delete(export)
    await db.flush()


async def _dataset_rows(
    db: AsyncSession, organization_id: uuid.UUID, dataset: str, day: dt.date
) -> list[dict]:
    if dataset == "playback_events":
        start = datetime.combine(day, dt.time.min, UTC)
        end = datetime.combine(day, dt.time.max, UTC)
        rows = (
            await db.execute(
                select(PlaybackEvent)
                .where(
                    PlaybackEvent.organization_id == organization_id,
                    PlaybackEvent.started_at >= start,
                    PlaybackEvent.started_at <= end,
                )
                .order_by(PlaybackEvent.started_at)
                .limit(100_000)
            )
        ).scalars()
        return [
            {
                "started_at": r.started_at.isoformat(),
                "ended_at": r.ended_at.isoformat() if r.ended_at else None,
                "device_id": str(r.device_id),
                "campaign_id": str(r.campaign_id) if r.campaign_id else None,
                "asset_id": str(r.asset_id) if r.asset_id else None,
                "result": r.result,
            }
            for r in rows
        ]
    if dataset == "analytics_aggregates":
        return await list_aggregates(
            db, organization_id, dimension_type="campaign", date_from=day, date_to=day
        ) + await list_aggregates(
            db, organization_id, dimension_type="org", date_from=day, date_to=day
        )
    from app.services import ads as ads_service

    return await ads_service.ad_performance(db, organization_id)


async def run_export(
    db: AsyncSession,
    organization_id: uuid.UUID,
    export_id: uuid.UUID,
    *,
    for_date: dt.date | None = None,
) -> DataExport:
    from app.integrations.storage import get_storage
    from app.services.report_export import to_csv

    export = (
        await db.execute(
            select(DataExport).where(
                DataExport.organization_id == organization_id, DataExport.id == export_id
            )
        )
    ).scalar_one_or_none()
    if export is None:
        raise NotFoundError("Data export not found")
    day = for_date or (datetime.now(UTC).date() - timedelta(days=1))
    export.state = DataExportState.RUNNING.value
    await db.flush()
    try:
        rows = await _dataset_rows(db, organization_id, export.dataset, day)
        key = (
            f"exports/{organization_id}/{export.dataset}/"
            f"{day.isoformat()}-{export.id.hex[:8]}.csv"
        )
        get_storage().write(key, to_csv(rows))
        export.last_object_key = key
        export.state = DataExportState.IDLE.value
        export.last_error = None
    except Exception as exc:  # noqa: BLE001 — the run state is the evidence
        export.state = DataExportState.ERROR.value
        export.last_error = str(exc)[:500]
        logger.exception("Data export %s failed", export.id)
    export.last_run_at = datetime.now(UTC)
    await db.flush()
    return export


async def run_due_exports(db: AsyncSession) -> dict:
    """Beat sweep (daily): run every export whose last run predates today."""
    today = datetime.now(UTC).date()
    exports = (
        await db.execute(
            select(DataExport).where(DataExport.state != DataExportState.RUNNING.value)
        )
    ).scalars().all()
    ran = 0
    for export in exports:
        last = export.last_run_at
        if last is not None:
            last = last if last.tzinfo else last.replace(tzinfo=UTC)
            if last.date() >= today:
                continue
        await run_export(db, export.organization_id, export.id)
        ran += 1
    return {"ran": ran, "exports": len(exports)}
