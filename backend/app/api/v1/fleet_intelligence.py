"""Fleet intelligence API (P3-M07, slice 3D-3)."""

import uuid

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentTenantId, CurrentUser, PageParams, require_permissions
from app.db.session import get_db
from app.schemas.envelope import success
from app.services import anomaly as service

router = APIRouter(prefix="/fleet-intelligence")


class RuleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    signal_type: str
    threshold: dict | None = None
    window_hours: int = Field(default=24, ge=1, le=168)
    severity: str = "warning"


class RuleUpdate(BaseModel):
    name: str | None = None
    threshold: dict | None = None
    window_hours: int | None = Field(default=None, ge=1, le=168)
    severity: str | None = None
    active: bool | None = None


class RemediateIn(BaseModel):
    action: str


def _rule_out(rule) -> dict:
    return {
        "id": str(rule.id),
        "name": rule.name,
        "signal_type": rule.signal_type,
        "threshold": rule.threshold_json,
        "window_hours": rule.window_hours,
        "severity": rule.severity,
        "active": rule.active,
    }


def _anomaly_out(anomaly) -> dict:
    return {
        "id": str(anomaly.id),
        "device_id": str(anomaly.device_id),
        "rule_id": str(anomaly.rule_id) if anomaly.rule_id else None,
        "score": float(anomaly.score),
        "state": anomaly.state,
        "evidence": anomaly.evidence_json,
        "recommendation": anomaly.recommendation,
        "opened_at": anomaly.opened_at.isoformat() if anomaly.opened_at else None,
        "resolved_at": anomaly.resolved_at.isoformat() if anomaly.resolved_at else None,
    }


@router.get("/rules", dependencies=[require_permissions("monitoring.view")])
async def list_rules(tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)) -> dict:
    return success([_rule_out(r) for r in await service.list_rules(db, tenant_id)])


@router.post("/rules", dependencies=[require_permissions("settings.manage")], status_code=201)
async def create_rule(
    body: RuleCreate,
    tenant_id: CurrentTenantId,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    rule = await service.create_rule(
        db, tenant_id, name=body.name, signal_type=body.signal_type,
        threshold=body.threshold, window_hours=body.window_hours,
        severity=body.severity, user_id=user.id,
    )
    return success(_rule_out(rule))


@router.patch("/rules/{rule_id}", dependencies=[require_permissions("settings.manage")])
async def update_rule(
    rule_id: uuid.UUID,
    body: RuleUpdate,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
) -> dict:
    rule = await service.update_rule(
        db, tenant_id, rule_id, name=body.name, threshold=body.threshold,
        window_hours=body.window_hours, severity=body.severity, active=body.active,
    )
    return success(_rule_out(rule))


@router.delete("/rules/{rule_id}", dependencies=[require_permissions("settings.manage")])
async def delete_rule(
    rule_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    await service.delete_rule(db, tenant_id, rule_id)
    return success({"deleted": True})


@router.get("/anomalies", dependencies=[require_permissions("monitoring.view")])
async def list_anomalies(
    tenant_id: CurrentTenantId,
    page: PageParams,
    db: AsyncSession = Depends(get_db),
    state: str | None = Query(default=None),
) -> dict:
    rows, total = await service.list_anomalies(
        db, tenant_id, state=state, page=page.page, page_size=page.page_size
    )
    return success(
        [_anomaly_out(a) for a in rows],
        page=page.page, page_size=page.page_size, total=total,
    )


@router.get(
    "/anomalies/{anomaly_id}/actions", dependencies=[require_permissions("monitoring.view")]
)
async def anomaly_actions(
    anomaly_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    rows = await service.actions_for(db, tenant_id, anomaly_id)
    return success(
        [
            {
                "action": row.action,
                "outcome": row.outcome,
                "actor_id": str(row.actor_id) if row.actor_id else None,
                "executed_at": row.executed_at.isoformat() if row.executed_at else None,
            }
            for row in rows
        ]
    )


@router.post(
    "/{anomaly_id}/acknowledge", dependencies=[require_permissions("incidents.manage")]
)
async def acknowledge(
    anomaly_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    anomaly = await service.acknowledge(db, tenant_id, anomaly_id, user_id=user.id)
    return success(_anomaly_out(anomaly))


@router.post(
    "/{anomaly_id}/remediation", dependencies=[require_permissions("devices.control")]
)
async def remediate(
    anomaly_id: uuid.UUID,
    body: RemediateIn,
    tenant_id: CurrentTenantId,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    return success(
        await service.remediate(db, tenant_id, anomaly_id, action=body.action, user_id=user.id)
    )
