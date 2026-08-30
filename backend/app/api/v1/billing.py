"""Tenant-facing billing surface (SaaS core): plans, subscription, usage,
invoices, and tenant membership management.

Permission AND entitlement are separate axes — these endpoints check
`billing.*` permissions; the entitlement engine itself is enforced at the
resource choke points (device registration, uploads, publishing, ...).
"""

import uuid

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentTenantId, CurrentUser, require_permissions
from app.db.session import get_db
from app.models import Invoice
from app.schemas.envelope import success
from app.schemas.saas import (
    CancelRequest,
    ChangePlanRequest,
    MemberAdd,
    MemberUpdate,
    SubscribeRequest,
    invoice_out,
    plan_out,
    subscription_out,
)
from app.services import entitlements as entitlements_service
from app.services import memberships as memberships_service
from app.services import subscriptions as subscriptions_service
from app.services import usage as usage_service
from app.services.tenant_admin import get_usage

router = APIRouter()


@router.get("/plans")
async def list_plans(_user: CurrentUser, db: AsyncSession = Depends(get_db)) -> dict:
    plans = await subscriptions_service.list_plans(db)
    return success([plan_out(plan) for plan in plans])


@router.get("/billing/subscription", dependencies=[require_permissions("billing.view")])
async def get_subscription(
    tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    subscription = await entitlements_service.current_subscription(db, tenant_id)
    effective = await entitlements_service.get_effective(db, tenant_id)
    pending = await subscriptions_service.pending_plan_request(db, tenant_id)
    return success(
        {
            "subscription": subscription_out(subscription) if subscription else None,
            "entitlements": effective.values,
            "plan_code": effective.plan_code,
            "plan_name": effective.plan_name,
            "status": effective.subscription_status,
            "usage": await get_usage(db, tenant_id),
            "pending_plan_request": (
                {
                    "id": str(pending.id),
                    "to_plan": pending.requested_plan.code,
                    "to_plan_name": pending.requested_plan.name,
                    "created_at": pending.created_at.isoformat()
                    if pending.created_at
                    else None,
                }
                if pending
                else None
            ),
        }
    )


@router.post("/billing/subscribe", dependencies=[require_permissions("billing.manage")])
async def subscribe(
    body: SubscribeRequest,
    tenant_id: CurrentTenantId,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    subscription = await subscriptions_service.subscribe(
        db,
        tenant_id,
        plan_code=body.plan_code,
        billing_cycle=body.billing_cycle,
        trial_days=body.trial_days,
        actor_id=user.id,
    )
    return success(subscription_out(subscription))


@router.post("/billing/change-plan", dependencies=[require_permissions("billing.manage")])
async def request_change_plan(
    body: ChangePlanRequest,
    tenant_id: CurrentTenantId,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Plans never change self-serve: this records an upgrade/downgrade
    REQUEST. The Super Admin approves after the manual payment arrives."""
    request = await subscriptions_service.request_plan_change(
        db, tenant_id, plan_code=body.plan_code, note=body.note, actor_id=user.id
    )
    return success(
        {
            "request_id": str(request.id),
            "status": request.status,
            "to_plan": request.requested_plan.code,
            "message": "Request submitted. The plan activates once the platform "
            "administrator confirms payment and approves.",
        }
    )


@router.post("/billing/cancel", dependencies=[require_permissions("billing.manage")])
async def cancel(
    body: CancelRequest,
    tenant_id: CurrentTenantId,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    subscription = await subscriptions_service.cancel(
        db, tenant_id, at_period_end=body.at_period_end, actor_id=user.id
    )
    return success(subscription_out(subscription))


@router.post("/billing/reactivate", dependencies=[require_permissions("billing.manage")])
async def reactivate(
    tenant_id: CurrentTenantId, user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> dict:
    subscription = await subscriptions_service.reactivate(db, tenant_id, actor_id=user.id)
    return success(subscription_out(subscription))


@router.get("/billing/invoices", dependencies=[require_permissions("billing.view")])
async def list_invoices(
    tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    invoices = (
        await db.execute(
            select(Invoice)
            .where(Invoice.organization_id == tenant_id)
            .order_by(Invoice.issued_at.desc())
        )
    ).scalars()
    return success([invoice_out(invoice) for invoice in invoices])


@router.get(
    "/billing/invoices/{invoice_id}/download",
    dependencies=[require_permissions("billing.view")],
)
async def download_invoice(
    invoice_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
) -> Response:
    filename, html = await subscriptions_service.render_invoice_html(
        db, tenant_id, invoice_id
    )
    return Response(
        content=html,
        media_type="text/html",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/billing/usage", dependencies=[require_permissions("billing.view")])
async def usage(tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)) -> dict:
    return success(await usage_service.usage_summary(db, tenant_id))


# --- tenant members (guest memberships) ---


@router.get("/organization/members", dependencies=[require_permissions("users.view")])
async def list_members(
    tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    return success(await memberships_service.list_members(db, tenant_id))


def _member_out(membership) -> dict:
    return {
        "membership_id": str(membership.id),
        "user_id": str(membership.user_id),
        "role": membership.role.name if membership.role else None,
        "is_owner": membership.is_owner,
        "status": membership.status,
    }


@router.post("/organization/members", dependencies=[require_permissions("members.manage")])
async def add_member(
    body: MemberAdd, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    membership = await memberships_service.add_member(
        db, tenant_id, email=body.email, role_id=body.role_id, is_owner=body.is_owner
    )
    return success(_member_out(membership))


@router.patch(
    "/organization/members/{membership_id}",
    dependencies=[require_permissions("members.manage")],
)
async def update_member(
    membership_id: uuid.UUID,
    body: MemberUpdate,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
) -> dict:
    membership = await memberships_service.update_member(
        db,
        tenant_id,
        membership_id,
        role_id=body.role_id,
        is_owner=body.is_owner,
        status=body.status,
    )
    return success(_member_out(membership))


@router.delete(
    "/organization/members/{membership_id}",
    dependencies=[require_permissions("members.manage")],
)
async def remove_member(
    membership_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
) -> dict:
    await memberships_service.remove_member(db, tenant_id, membership_id)
    return success({"removed": True})
