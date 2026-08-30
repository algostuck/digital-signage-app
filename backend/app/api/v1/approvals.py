"""Approval inbox, decisions and tenant approval policies (P2-M03)."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    CurrentTenantId,
    CurrentUser,
    PageParams,
    require_permissions,
    user_permission_codes,
)
from app.core.errors import ForbiddenError
from app.db.session import get_db
from app.models import ApprovalRequest, User
from app.schemas.envelope import success
from app.services import approvals as service

router = APIRouter()


class ApprovalActionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    actor_id: uuid.UUID | None
    action: str
    comments: str | None
    from_state: str | None
    to_state: str | None
    created_at: datetime
    actor_name: str | None = None


class ApprovalRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entity_type: str
    entity_id: uuid.UUID
    state: str
    requester_id: uuid.UUID | None
    submitted_at: datetime
    decided_at: datetime | None
    decided_by: uuid.UUID | None
    comments: str | None
    entity_name: str | None = None
    requester_name: str | None = None
    actions: list[ApprovalActionOut] = []


class DecisionRequest(BaseModel):
    comments: str | None = Field(default=None, max_length=2000)


class PolicyIn(BaseModel):
    require_approval: bool = True
    maker_checker: bool = False


def _can_view_inbox(user: User) -> None:
    held = user_permission_codes(user)
    if user.is_superuser:
        return
    allowed = {"campaigns.approve", "layouts.manage", "settings.manage"}
    if not (held & allowed):
        raise ForbiddenError("No approval permissions")


async def _request_out(
    db: AsyncSession, tenant_id: uuid.UUID, request: ApprovalRequest
) -> dict:
    out = ApprovalRequestOut.model_validate(request)
    adapter = service.get_adapter(request.entity_type)
    out.entity_name = await adapter.get_name(db, tenant_id, request.entity_id)

    user_ids = {request.requester_id, *(a.actor_id for a in request.actions)} - {None}
    names: dict = {}
    if user_ids:
        rows = await db.execute(
            select(User.id, User.full_name).where(User.id.in_(user_ids))
        )
        names = dict(rows.all())
    out.requester_name = names.get(request.requester_id)
    result = out.model_dump(mode="json")
    for index, action in enumerate(request.actions):
        result["actions"][index]["actor_name"] = names.get(action.actor_id)
    return result


@router.get("/approvals/inbox")
async def approvals_inbox(
    tenant_id: CurrentTenantId,
    user: CurrentUser,
    pagination: PageParams,
    state: str | None = Query(None, max_length=20),
    entity_type: str | None = Query(None, max_length=40),
    db: AsyncSession = Depends(get_db),
) -> dict:
    _can_view_inbox(user)
    requests, total = await service.inbox(
        db,
        tenant_id,
        state=state,
        entity_type=entity_type,
        page=pagination.page,
        page_size=pagination.page_size,
    )
    return success(
        [await _request_out(db, tenant_id, r) for r in requests],
        page=pagination.page,
        page_size=pagination.page_size,
        total=total,
    )


@router.get("/approvals/{request_id}")
async def get_approval(
    request_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    _can_view_inbox(user)
    request = await service.get_request(db, tenant_id, request_id)
    return success(await _request_out(db, tenant_id, request))


async def _decide_endpoint(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    user: User,
    request_id: uuid.UUID,
    *,
    approve: bool,
    comments: str | None,
) -> dict:
    request = await service.get_request(db, tenant_id, request_id)
    adapter = service.get_adapter(request.entity_type)
    if not user.is_superuser and adapter.approve_permission not in user_permission_codes(user):
        raise ForbiddenError(f"Missing permission: {adapter.approve_permission}")
    request = await service.decide(
        db, tenant_id, request_id, actor=user, approve=approve, comments=comments
    )
    return success(await _request_out(db, tenant_id, request))


@router.post("/approvals/{request_id}/approve")
async def approve_request(
    request_id: uuid.UUID,
    body: DecisionRequest,
    tenant_id: CurrentTenantId,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await _decide_endpoint(
        db, tenant_id, user, request_id, approve=True, comments=body.comments
    )


@router.post("/approvals/{request_id}/reject")
async def reject_request(
    request_id: uuid.UUID,
    body: DecisionRequest,
    tenant_id: CurrentTenantId,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await _decide_endpoint(
        db, tenant_id, user, request_id, approve=False, comments=body.comments
    )


# --- policies (P2-APP-001) ---


@router.get("/approval-policies", dependencies=[require_permissions("settings.manage")])
async def list_policies(
    tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    result = []
    for entity_type in service.SUPPORTED_ENTITY_TYPES:
        policy = await service.get_policy(db, tenant_id, entity_type)
        result.append(
            {
                "entity_type": entity_type,
                "require_approval": policy.require_approval,
                "maker_checker": policy.maker_checker,
            }
        )
    return success(result)


@router.put(
    "/approval-policies/{entity_type}", dependencies=[require_permissions("settings.manage")]
)
async def upsert_policy(
    entity_type: str,
    body: PolicyIn,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
) -> dict:
    await service.upsert_policy(
        db,
        tenant_id,
        entity_type,
        require_approval=body.require_approval,
        maker_checker=body.maker_checker,
    )
    return success(
        {
            "entity_type": entity_type,
            "require_approval": body.require_approval,
            "maker_checker": body.maker_checker,
        }
    )
