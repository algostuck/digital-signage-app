"""Security center API (P3-M10, slice 3E-3)."""

import uuid

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentTenantId, CurrentUser, PageParams, require_permissions
from app.db.session import get_db
from app.schemas.envelope import success
from app.services import security_center as service

router = APIRouter(prefix="/security")


class PolicyUpsert(BaseModel):
    scope_type: str
    conditions: dict | None = None
    severity: str = Field(default="warning", pattern="^(info|warning|critical)$")
    active: bool = True


@router.get("/summary", dependencies=[require_permissions("settings.manage")])
async def summary(tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)) -> dict:
    return success(await service.summary(db, tenant_id))


@router.get("/devices/identities", dependencies=[require_permissions("devices.view")])
async def identities(tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)) -> dict:
    return success(await service.device_identities(db, tenant_id))


@router.post(
    "/devices/{device_id}/rotate", dependencies=[require_permissions("settings.manage")]
)
async def rotate(
    device_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    return success(
        await service.rotate_device_credential(db, tenant_id, device_id, user_id=user.id)
    )


@router.get("/policies", dependencies=[require_permissions("settings.manage")])
async def list_policies(tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)) -> dict:
    return success(
        [
            {
                "id": str(p.id),
                "scope_type": p.scope_type,
                "conditions": p.conditions_json,
                "severity": p.actions_json.get("severity", "warning"),
                "active": p.active,
            }
            for p in await service.list_policies(db, tenant_id)
        ]
    )


@router.post("/policies", dependencies=[require_permissions("settings.manage")])
async def upsert_policy(
    body: PolicyUpsert,
    tenant_id: CurrentTenantId,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    policy = await service.upsert_policy(
        db, tenant_id, scope_type=body.scope_type, conditions=body.conditions,
        severity=body.severity, active=body.active, user_id=user.id,
    )
    return success({"id": str(policy.id), "scope_type": policy.scope_type})


@router.get("/policy-violations", dependencies=[require_permissions("settings.manage")])
async def violations(
    tenant_id: CurrentTenantId,
    page: PageParams,
    db: AsyncSession = Depends(get_db),
    state: str | None = Query(default=None),
) -> dict:
    rows, total = await service.list_violations(
        db, tenant_id, state=state, page=page.page, page_size=page.page_size
    )
    return success(
        [
            {
                "id": str(v.id),
                "entity_type": v.entity_type,
                "entity_id": str(v.entity_id),
                "severity": v.severity,
                "state": v.state,
                "detail": v.detail,
                "detected_at": v.detected_at.isoformat() if v.detected_at else None,
            }
            for v in rows
        ],
        page=page.page, page_size=page.page_size, total=total,
    )


@router.post(
    "/policy-violations/{violation_id}/resolve",
    dependencies=[require_permissions("settings.manage")],
)
async def resolve(
    violation_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    violation = await service.resolve_violation(db, tenant_id, violation_id, user_id=user.id)
    return success({"id": str(violation.id), "state": violation.state})
