"""Platform administration surface (SaaS core) — Super Admin only.

Tenant CRUD, plan management, subscription assignment/transition and
payment recording. Every route sits behind require_superuser.
"""

import uuid

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import PlatformAdmin
from app.db.session import get_db
from app.models import Invoice, Organization
from app.models.saas import Plan, Subscription
from app.schemas.envelope import success
from app.schemas.saas import (
    AssignSubscriptionRequest,
    ChangePlanRequest,
    PlanRequestDecision,
    PlanUpsert,
    ProviderUpdate,
    RecordPaymentRequest,
    TenantCreate,
    TenantStatusUpdate,
    TenantUpdate,
    TransitionRequest,
    invoice_out,
    plan_out,
    subscription_out,
)
from app.services import entitlements as entitlements_service
from app.services import platform as platform_service
from app.services import subscriptions as subscriptions_service
from app.services import tenant_admin

router = APIRouter(prefix="/platform")


@router.get("/tenants")
async def list_tenants(_admin: PlatformAdmin, db: AsyncSession = Depends(get_db)) -> dict:
    return success(await platform_service.list_tenants(db))


@router.get("/tenants/{tenant_id}")
async def get_tenant(
    tenant_id: uuid.UUID, _admin: PlatformAdmin, db: AsyncSession = Depends(get_db)
) -> dict:
    return success(await platform_service.get_tenant(db, tenant_id))


@router.post("/tenants", status_code=201)
async def create_tenant(
    body: TenantCreate, admin: PlatformAdmin, db: AsyncSession = Depends(get_db)
) -> dict:
    org, owner = await platform_service.create_tenant(
        db,
        name=body.name,
        code=body.code,
        timezone=body.timezone,
        owner_email=body.owner_email,
        owner_full_name=body.owner_full_name,
        owner_password=body.owner_password,
        actor_id=admin.id,
    )
    return success(
        {
            "id": str(org.id),
            "name": org.name,
            "code": org.code,
            "owner": {"id": str(owner.id), "email": owner.email, "status": owner.status},
        }
    )


@router.patch("/tenants/{tenant_id}")
async def update_tenant(
    tenant_id: uuid.UUID,
    body: TenantUpdate,
    admin: PlatformAdmin,
    db: AsyncSession = Depends(get_db),
) -> dict:
    org = await platform_service.update_tenant(
        db, tenant_id, name=body.name, timezone=body.timezone,
        region=body.region, actor_id=admin.id,
    )
    return success(
        {"id": str(org.id), "name": org.name, "code": org.code,
         "timezone": org.timezone, "region": org.region}
    )


@router.post("/tenants/{tenant_id}/verify-domain")
async def verify_domain(
    tenant_id: uuid.UUID,
    body: dict,
    admin: PlatformAdmin,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """P3 3E-2: white-label custom-domain verification is an explicit,
    audited platform-admin decision (DNS/edge routing is deployment-side)."""
    from app.services import white_label

    return success(
        await white_label.verify_domain(
            db, tenant_id, verified=bool(body.get("verified", True)), actor_id=admin.id
        )
    )


@router.patch("/tenants/{tenant_id}/status")
async def set_tenant_status(
    tenant_id: uuid.UUID,
    body: TenantStatusUpdate,
    admin: PlatformAdmin,
    db: AsyncSession = Depends(get_db),
) -> dict:
    org = await platform_service.set_tenant_status(
        db, tenant_id, body.status, actor_id=admin.id
    )
    return success({"id": str(org.id), "status": org.status})


@router.get("/tenants/{tenant_id}/quotas")
async def get_tenant_quotas(
    tenant_id: uuid.UUID, _admin: PlatformAdmin, db: AsyncSession = Depends(get_db)
) -> dict:
    """Usage + the raw platform quota overrides (effective limits already
    min-combine these with the plan)."""
    org = await db.get(Organization, tenant_id)
    return success(
        {
            "usage": await tenant_admin.get_usage(db, tenant_id),
            "quotas": (org.quotas_json or {}) if org else {},
        }
    )


@router.patch("/tenants/{tenant_id}/quotas")
async def update_tenant_quotas(
    tenant_id: uuid.UUID,
    body: dict,
    admin: PlatformAdmin,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Platform quota override: tightens numeric limits below the plan.
    Tenant admins cannot edit this — Super Admin only."""
    await tenant_admin.update_quotas(db, tenant_id, body, user_id=admin.id)
    return success(await tenant_admin.get_usage(db, tenant_id))


@router.get("/entitlements")
async def entitlement_catalogue(_admin: PlatformAdmin) -> dict:
    """The catalogue driving the plan editor: key -> \"int\" | \"bool\"."""
    return success(entitlements_service.ENTITLEMENTS)


@router.get("/plans")
async def list_plans(_admin: PlatformAdmin, db: AsyncSession = Depends(get_db)) -> dict:
    plans = await subscriptions_service.list_plans(db, include_inactive=True)
    return success([plan_out(plan) for plan in plans])


@router.post("/plans", status_code=201)
async def upsert_plan(
    body: PlanUpsert, _admin: PlatformAdmin, db: AsyncSession = Depends(get_db)
) -> dict:
    plan = await subscriptions_service.upsert_plan(
        db,
        code=body.code,
        name=body.name,
        description=body.description,
        prices=body.prices,
        entitlements=[row.model_dump() for row in body.entitlements],
        is_active=body.is_active,
        sort_order=body.sort_order,
    )
    return success(plan_out(plan))


@router.post("/tenants/{tenant_id}/subscription")
async def assign_subscription(
    tenant_id: uuid.UUID,
    body: AssignSubscriptionRequest,
    admin: PlatformAdmin,
    db: AsyncSession = Depends(get_db),
) -> dict:
    subscription = await subscriptions_service.subscribe(
        db,
        tenant_id,
        plan_code=body.plan_code,
        billing_cycle=body.billing_cycle,
        trial_days=body.trial_days,
        actor_id=admin.id,
    )
    return success(subscription_out(subscription))


@router.post("/tenants/{tenant_id}/subscription/transition")
async def transition_subscription(
    tenant_id: uuid.UUID,
    body: TransitionRequest,
    admin: PlatformAdmin,
    db: AsyncSession = Depends(get_db),
) -> dict:
    subscription = await subscriptions_service.transition(
        db, tenant_id, to_status=body.to_status, event=body.event, actor_id=admin.id
    )
    return success(subscription_out(subscription))


@router.get("/tenants/{tenant_id}/subscription")
async def get_tenant_subscription(
    tenant_id: uuid.UUID, _admin: PlatformAdmin, db: AsyncSession = Depends(get_db)
) -> dict:
    subscription = await entitlements_service.latest_subscription(db, tenant_id)
    effective = await entitlements_service.get_effective(db, tenant_id)
    return success(
        {
            "subscription": subscription_out(subscription) if subscription else None,
            "entitlements": effective.values,
        }
    )


@router.get("/tenants/{tenant_id}/invoices")
async def list_tenant_invoices(
    tenant_id: uuid.UUID, _admin: PlatformAdmin, db: AsyncSession = Depends(get_db)
) -> dict:
    invoices = (
        await db.execute(
            select(Invoice)
            .where(Invoice.organization_id == tenant_id)
            .order_by(Invoice.issued_at.desc())
        )
    ).scalars()
    return success([invoice_out(invoice) for invoice in invoices])


@router.get("/invoices")
async def list_invoices(
    _admin: PlatformAdmin,
    db: AsyncSession = Depends(get_db),
    status: str | None = None,
    tenant_id: uuid.UUID | None = None,
) -> dict:
    """Every tenant's invoices in one list, so the console can work the
    receivables ledger without opening tenants one at a time."""
    query = (
        select(Invoice, Organization.name, Organization.code, Plan.code, Plan.name)
        .join(Organization, Organization.id == Invoice.organization_id)
        .join(Subscription, Subscription.id == Invoice.subscription_id)
        .join(Plan, Plan.id == Subscription.plan_id)
        .order_by(Invoice.issued_at.desc())
    )
    if status:
        query = query.where(Invoice.status == status)
    if tenant_id:
        query = query.where(Invoice.organization_id == tenant_id)
    rows = (await db.execute(query)).all()
    return success(
        [
            {
                **invoice_out(invoice),
                "organization_id": str(invoice.organization_id),
                "organization_name": org_name,
                "organization_code": org_code,
                "plan_code": plan_code,
                "plan_name": plan_name,
            }
            for invoice, org_name, org_code, plan_code, plan_name in rows
        ]
    )


@router.patch("/tenants/{tenant_id}/subscription/plan")
async def change_tenant_plan(
    tenant_id: uuid.UUID,
    body: ChangePlanRequest,
    admin: PlatformAdmin,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Direct plan change (upgrade or downgrade) by the Super Admin —
    tenants can only *request* one."""
    subscription = await subscriptions_service.change_plan(
        db, tenant_id, plan_code=body.plan_code, actor_id=admin.id
    )
    return success(subscription_out(subscription))


@router.get("/plan-requests")
async def list_plan_requests(
    _admin: PlatformAdmin,
    db: AsyncSession = Depends(get_db),
    status: str | None = "pending",
) -> dict:
    return success(
        await subscriptions_service.list_plan_requests(
            db, status=None if status in (None, "all") else status
        )
    )


@router.post("/plan-requests/{request_id}/approve")
async def approve_plan_request(
    request_id: uuid.UUID,
    body: PlanRequestDecision,
    admin: PlatformAdmin,
    db: AsyncSession = Depends(get_db),
) -> dict:
    request = await subscriptions_service.decide_plan_request(
        db, request_id, approve=True, decision_note=body.decision_note, actor_id=admin.id
    )
    return success({"id": str(request.id), "status": request.status})


@router.post("/plan-requests/{request_id}/reject")
async def reject_plan_request(
    request_id: uuid.UUID,
    body: PlanRequestDecision,
    admin: PlatformAdmin,
    db: AsyncSession = Depends(get_db),
) -> dict:
    request = await subscriptions_service.decide_plan_request(
        db, request_id, approve=False, decision_note=body.decision_note, actor_id=admin.id
    )
    return success({"id": str(request.id), "status": request.status})


@router.patch("/tenants/{tenant_id}/subscription/provider")
async def set_provider(
    tenant_id: uuid.UUID,
    body: ProviderUpdate,
    admin: PlatformAdmin,
    db: AsyncSession = Depends(get_db),
) -> dict:
    subscription = await subscriptions_service.set_provider(
        db,
        tenant_id,
        provider=body.provider,
        provider_customer_id=body.provider_customer_id,
        provider_subscription_id=body.provider_subscription_id,
        actor_id=admin.id,
    )
    return success(subscription_out(subscription))


@router.get("/tenants/{tenant_id}/invoices/{invoice_id}/download")
async def download_tenant_invoice(
    tenant_id: uuid.UUID,
    invoice_id: uuid.UUID,
    _admin: PlatformAdmin,
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


@router.post("/tenants/{tenant_id}/payments")
async def record_payment(
    tenant_id: uuid.UUID,
    body: RecordPaymentRequest,
    admin: PlatformAdmin,
    db: AsyncSession = Depends(get_db),
) -> dict:
    invoice = await subscriptions_service.record_payment(
        db,
        tenant_id,
        body.invoice_id,
        provider=body.provider,
        provider_ref=body.provider_ref,
        actor_id=admin.id,
    )
    return success(invoice_out(invoice))
