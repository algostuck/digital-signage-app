"""Analytics platform API (P3-M11, slice 3D-2)."""

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentTenantId, CurrentUser, require_entitlement, require_permissions
from app.db.session import get_db
from app.schemas.envelope import success
from app.services import analytics as service

router = APIRouter()


class ExportCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    dataset: str
    cadence: str = "daily"


def _export_out(export) -> dict:
    return {
        "id": str(export.id),
        "name": export.name,
        "dataset": export.dataset,
        "destination": export.destination,
        "schedule": export.schedule_json,
        "state": export.state,
        "last_run_at": export.last_run_at.isoformat() if export.last_run_at else None,
        "last_error": export.last_error,
        "last_object_key": export.last_object_key,
    }


@router.get("/analytics/metrics", dependencies=[require_permissions("reports.view")])
async def semantic_metrics() -> dict:
    """The single-source metric definitions (P3-M11)."""
    return success(service.METRICS)


@router.get(
    "/analytics/aggregates",
    dependencies=[require_permissions("reports.view"), require_entitlement("advanced_analytics")],
)
async def aggregates(
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
    dimension_type: str = Query(default="campaign"),
    date_from: dt.date = Query(...),
    date_to: dt.date = Query(...),
) -> dict:
    return success(
        await service.list_aggregates(
            db,
            tenant_id,
            dimension_type=dimension_type,
            date_from=date_from,
            date_to=date_to,
        )
    )


@router.get(
    "/analytics/reconciliation",
    dependencies=[require_permissions("reports.view"), require_entitlement("advanced_analytics")],
)
async def reconciliation(
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
    date: dt.date = Query(...),
) -> dict:
    return success(await service.reconcile(db, tenant_id, for_date=date))


@router.get(
    "/data-exports",
    dependencies=[require_permissions("reports.export"), require_entitlement("advanced_analytics")],
)
async def list_exports(tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)) -> dict:
    return success([_export_out(e) for e in await service.list_exports(db, tenant_id)])


@router.post(
    "/data-exports",
    dependencies=[require_permissions("reports.export"), require_entitlement("advanced_analytics")],
    status_code=201,
)
async def create_export(
    body: ExportCreate,
    tenant_id: CurrentTenantId,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    export = await service.create_export(
        db,
        tenant_id,
        name=body.name,
        dataset=body.dataset,
        cadence=body.cadence,
        user_id=user.id,
    )
    return success(_export_out(export))


@router.post("/data-exports/{export_id}/run", dependencies=[require_permissions("reports.export")])
async def run_export(
    export_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    export = await service.run_export(db, tenant_id, export_id)
    return success(_export_out(export))


@router.delete("/data-exports/{export_id}", dependencies=[require_permissions("reports.export")])
async def delete_export(
    export_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    await service.delete_export(db, tenant_id, export_id)
    return success({"deleted": True})
