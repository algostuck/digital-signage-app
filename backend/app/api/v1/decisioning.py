"""Decisioning API (P3-M03, slice 3B-2): policies, ordered rules,
dry-run preview and the auditable decision log."""

import uuid

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentTenantId, CurrentUser, PageParams, require_permissions
from app.db.session import get_db
from app.schemas.envelope import success
from app.services import decisioning as service

router = APIRouter()


class PolicyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    guardrails: dict | None = None


class PolicyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    guardrails: dict | None = None
    active: bool | None = None


class RuleIn(BaseModel):
    priority: int = Field(default=100, ge=1, le=10000)
    conditions: dict = Field(default_factory=dict)
    actions: dict


class RulesReplace(BaseModel):
    rules: list[RuleIn]


class PreviewRequest(BaseModel):
    device_id: uuid.UUID


def _policy_out(policy) -> dict:
    return {
        "id": str(policy.id),
        "name": policy.name,
        "guardrails": policy.guardrails_json,
        "active": policy.active,
        "rules": [
            {
                "id": str(rule.id),
                "priority": rule.priority,
                "conditions": rule.conditions_json,
                "actions": rule.actions_json,
            }
            for rule in policy.rules
        ],
    }


@router.get("/decision-policies", dependencies=[require_permissions("campaigns.view")])
async def list_policies(tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)) -> dict:
    policies = await service.list_policies(db, tenant_id)
    return success([_policy_out(p) for p in policies])


@router.post(
    "/decision-policies",
    dependencies=[require_permissions("campaigns.manage")],
    status_code=201,
)
async def create_policy(
    body: PolicyCreate,
    tenant_id: CurrentTenantId,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    policy = await service.create_policy(
        db, tenant_id, name=body.name, guardrails=body.guardrails, user_id=user.id
    )
    return success(_policy_out(policy))


@router.patch(
    "/decision-policies/{policy_id}", dependencies=[require_permissions("campaigns.manage")]
)
async def update_policy(
    policy_id: uuid.UUID,
    body: PolicyUpdate,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
) -> dict:
    policy = await service.update_policy(
        db, tenant_id, policy_id, name=body.name, guardrails=body.guardrails, active=body.active
    )
    return success(_policy_out(policy))


@router.delete(
    "/decision-policies/{policy_id}", dependencies=[require_permissions("campaigns.manage")]
)
async def delete_policy(
    policy_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    await service.delete_policy(db, tenant_id, policy_id)
    return success({"deleted": True})


@router.put(
    "/decision-policies/{policy_id}/rules",
    dependencies=[require_permissions("campaigns.manage")],
)
async def replace_rules(
    policy_id: uuid.UUID,
    body: RulesReplace,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
) -> dict:
    policy = await service.set_rules(
        db, tenant_id, policy_id, [rule.model_dump() for rule in body.rules]
    )
    return success(_policy_out(policy))


@router.post("/decision-rules/preview", dependencies=[require_permissions("campaigns.view")])
async def preview(
    body: PreviewRequest, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    return success(await service.preview(db, tenant_id, body.device_id))


@router.get("/decision-log", dependencies=[require_permissions("campaigns.view")])
async def decision_log(
    tenant_id: CurrentTenantId,
    page: PageParams,
    db: AsyncSession = Depends(get_db),
    device_id: uuid.UUID | None = Query(default=None),
) -> dict:
    rows, total = await service.list_log(
        db, tenant_id, device_id=device_id, page=page.page, page_size=page.page_size
    )
    return success(
        [
            {
                "id": str(row.id),
                "device_id": str(row.device_id),
                "campaign_id": str(row.campaign_id) if row.campaign_id else None,
                "reasons": row.reason_json,
                "decided_at": row.decided_at.isoformat() if row.decided_at else None,
            }
            for row in rows
        ],
        page=page.page,
        page_size=page.page_size,
        total=total,
    )
