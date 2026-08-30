"""Subscription lifecycle, plans and billing records (SaaS core).

Subscription answers "what is this tenant entitled to"; billing (invoices/
payments) answers "how are they charged". Payment collection itself sits
behind a provider abstraction — the default `manual` provider models
enterprise PO/invoice billing; card providers (Stripe/Razorpay) are later
config swaps and never leak provider IDs into business tables beyond the
provider_* reference columns.
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import (
    BusinessRuleError,
    ConflictError,
    NotFoundError,
    ValidationAppError,
)
from app.models import (
    Invoice,
    Payment,
    Plan,
    PlanChangeRequest,
    PlanEntitlement,
    Subscription,
    SubscriptionEvent,
)
from app.models.saas import (
    BillingCycle,
    InvoiceStatus,
    PlanChangeRequestStatus,
    SubscriptionStatus,
)
from app.services.entitlements import ENTITLEMENTS, current_subscription

logger = logging.getLogger("app.subscriptions")

# Dunning ladder (days after an unpaid invoice's due date).
PAST_DUE_AFTER_DAYS = 0
GRACE_AFTER_DAYS = 7
SUSPEND_AFTER_DAYS = 14
INVOICE_DUE_DAYS = 7

_CYCLE_DAYS = {BillingCycle.MONTHLY.value: 30, BillingCycle.YEARLY.value: 365}


def _now() -> datetime:
    return datetime.now(UTC)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


# --- plans (platform-scoped) ---


def _validate_entitlement_rows(rows: list[dict]) -> None:
    for row in rows:
        key = row.get("key")
        if key not in ENTITLEMENTS:
            raise ValidationAppError(f"Unknown entitlement '{key}'", field="entitlements")
        kind = ENTITLEMENTS[key]
        if kind == "int" and row.get("bool_value") is not None:
            raise ValidationAppError(f"'{key}' is numeric", field="entitlements")
        if kind == "bool" and row.get("int_value") is not None:
            raise ValidationAppError(f"'{key}' is boolean", field="entitlements")


async def list_plans(db: AsyncSession, *, include_inactive: bool = False) -> list[Plan]:
    query = select(Plan).order_by(Plan.sort_order, Plan.code)
    if not include_inactive:
        query = query.where(Plan.is_active.is_(True))
    return list((await db.execute(query)).scalars().all())


async def get_plan_by_code(db: AsyncSession, code: str) -> Plan:
    plan = (
        await db.execute(select(Plan).where(Plan.code == code))
    ).scalar_one_or_none()
    if plan is None:
        raise NotFoundError("Plan not found")
    return plan


async def upsert_plan(
    db: AsyncSession,
    *,
    code: str,
    name: str,
    description: str | None,
    prices: dict,
    entitlements: list[dict],
    is_active: bool = True,
    sort_order: int = 0,
) -> Plan:
    _validate_entitlement_rows(entitlements)
    plan = (
        await db.execute(select(Plan).where(Plan.code == code))
    ).scalar_one_or_none()
    if plan is None:
        plan = Plan(code=code)
        db.add(plan)
    plan.name = name
    plan.description = description
    plan.prices_json = prices
    plan.is_active = is_active
    plan.sort_order = sort_order
    await db.flush()
    await db.refresh(plan, ["entitlements"])
    plan.entitlements.clear()
    await db.flush()
    plan.entitlements.extend(
        PlanEntitlement(
            plan_id=plan.id,
            key=row["key"],
            int_value=row.get("int_value"),
            bool_value=row.get("bool_value"),
        )
        for row in entitlements
    )
    await db.flush()
    return plan


# --- subscription lifecycle ---


def _record_event(
    subscription: Subscription,
    db: AsyncSession,
    *,
    event: str,
    from_status: str | None,
    to_status: str | None,
    actor_id: uuid.UUID | None = None,
    payload: dict | None = None,
) -> None:
    db.add(
        SubscriptionEvent(
            organization_id=subscription.organization_id,
            subscription_id=subscription.id,
            event=event,
            from_status=from_status,
            to_status=to_status,
            actor_id=actor_id,
            payload_json=payload,
        )
    )


async def _issue_invoice(db: AsyncSession, subscription: Subscription) -> Invoice | None:
    price = (subscription.plan.prices_json or {}).get(subscription.billing_cycle)
    if not price or not price.get("amount"):
        return None  # custom/zero-priced (enterprise contract handled off-platform)
    count = (
        await db.execute(
            select(func.count()).where(
                Invoice.organization_id == subscription.organization_id
            )
        )
    ).scalar_one()
    invoice = Invoice(
        organization_id=subscription.organization_id,
        subscription_id=subscription.id,
        number=f"INV-{_now().year}-{str(subscription.organization_id)[:8]}-{count + 1:04d}",
        period_start=subscription.current_period_start or _now(),
        period_end=subscription.current_period_end or _now(),
        amount=price["amount"],
        currency=price.get("currency", "INR"),
        status=InvoiceStatus.ISSUED.value,
        due_at=_now() + timedelta(days=INVOICE_DUE_DAYS),
    )
    db.add(invoice)
    await db.flush()
    return invoice


async def subscribe(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    plan_code: str,
    billing_cycle: str = BillingCycle.MONTHLY.value,
    trial_days: int = 0,
    actor_id: uuid.UUID | None = None,
) -> Subscription:
    if billing_cycle not in {c.value for c in BillingCycle}:
        raise ValidationAppError("Unknown billing cycle", field="billing_cycle")
    existing = await current_subscription(db, organization_id)
    if existing is not None and existing.status in (
        SubscriptionStatus.TRIALING.value,
        SubscriptionStatus.ACTIVE.value,
        SubscriptionStatus.PAST_DUE.value,
        SubscriptionStatus.GRACE_PERIOD.value,
    ):
        raise ConflictError("An active subscription already exists; use change-plan")
    plan = await get_plan_by_code(db, plan_code)
    if not plan.is_active:
        raise BusinessRuleError("This plan is not open for subscription")

    now = _now()
    period_days = _CYCLE_DAYS.get(billing_cycle, 30)
    subscription = Subscription(
        organization_id=organization_id,
        plan_id=plan.id,
        billing_cycle=billing_cycle,
        start_at=now,
    )
    if trial_days > 0:
        subscription.status = SubscriptionStatus.TRIALING.value
        subscription.trial_start_at = now
        subscription.trial_end_at = now + timedelta(days=trial_days)
    else:
        subscription.status = SubscriptionStatus.ACTIVE.value
        subscription.current_period_start = now
        subscription.current_period_end = now + timedelta(days=period_days)
    db.add(subscription)
    await db.flush()
    await db.refresh(subscription, ["plan", "items"])
    _record_event(
        subscription, db, event="signup", from_status=None,
        to_status=subscription.status, actor_id=actor_id,
        payload={"plan": plan_code, "cycle": billing_cycle},
    )
    if subscription.status == SubscriptionStatus.ACTIVE.value:
        await _issue_invoice(db, subscription)
    await db.flush()

    from app.services import audit

    await audit.record(
        db, organization_id, action="SUBSCRIPTION_CREATED",
        entity_type="subscription", entity_id=subscription.id,
        after={"plan": plan_code, "cycle": billing_cycle, "status": subscription.status},
        user_id=actor_id,
    )
    return subscription


async def change_plan(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    plan_code: str,
    actor_id: uuid.UUID | None = None,
) -> Subscription:
    subscription = await current_subscription(db, organization_id)
    if subscription is None:
        raise NotFoundError("No subscription to change")
    plan = await get_plan_by_code(db, plan_code)
    old_code = subscription.plan.code
    if old_code == plan_code:
        raise BusinessRuleError("Already on this plan")
    subscription.plan_id = plan.id
    await db.flush()
    await db.refresh(subscription, ["plan"])
    _record_event(
        subscription, db, event="plan_changed",
        from_status=subscription.status, to_status=subscription.status,
        actor_id=actor_id, payload={"from": old_code, "to": plan_code},
    )
    await db.flush()

    from app.services import audit

    await audit.record(
        db, organization_id, action="SUBSCRIPTION_PLAN_CHANGED",
        entity_type="subscription", entity_id=subscription.id,
        after={"from": old_code, "to": plan_code}, user_id=actor_id,
    )
    return subscription


# --- plan change requests (tenant asks, Super Admin approves) ---


async def pending_plan_request(
    db: AsyncSession, organization_id: uuid.UUID
) -> PlanChangeRequest | None:
    return (
        await db.execute(
            select(PlanChangeRequest).where(
                PlanChangeRequest.organization_id == organization_id,
                PlanChangeRequest.status == PlanChangeRequestStatus.PENDING.value,
            )
        )
    ).scalars().first()


async def request_plan_change(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    plan_code: str,
    note: str | None = None,
    actor_id: uuid.UUID | None = None,
) -> PlanChangeRequest:
    """Tenant-side: records the wish to upgrade/downgrade. Nothing changes
    on the subscription until the Super Admin approves (manual payment
    verified first)."""
    subscription = await current_subscription(db, organization_id)
    if subscription is None:
        raise NotFoundError("No subscription — ask the platform administrator")
    plan = await get_plan_by_code(db, plan_code)
    if not plan.is_active:
        raise BusinessRuleError("This plan is not open for subscription")
    if subscription.plan.code == plan_code:
        raise BusinessRuleError("Already on this plan")
    if await pending_plan_request(db, organization_id) is not None:
        raise ConflictError("A plan change request is already awaiting approval")

    request = PlanChangeRequest(
        organization_id=organization_id,
        subscription_id=subscription.id,
        requested_plan_id=plan.id,
        current_plan_code=subscription.plan.code,
        note=note,
        requested_by=actor_id,
    )
    db.add(request)
    await db.flush()
    await db.refresh(request, ["requested_plan"])

    from app.services import audit

    await audit.record(
        db, organization_id, action="PLAN_CHANGE_REQUESTED",
        entity_type="plan_change_request", entity_id=request.id,
        after={"from": subscription.plan.code, "to": plan_code}, user_id=actor_id,
    )
    logger.info(
        "Org %s requested plan change %s -> %s",
        organization_id, subscription.plan.code, plan_code,
    )
    return request


async def list_plan_requests(
    db: AsyncSession, *, status: str | None = PlanChangeRequestStatus.PENDING.value
) -> list[dict]:
    """Platform-side inbox (cross-tenant, Super Admin only)."""
    from app.models import Organization

    query = (
        select(PlanChangeRequest, Organization.name, Organization.code)
        .join(Organization, Organization.id == PlanChangeRequest.organization_id)
        .order_by(PlanChangeRequest.created_at.desc())
    )
    if status is not None:
        query = query.where(PlanChangeRequest.status == status)
    rows = (await db.execute(query)).all()
    return [
        {
            "id": str(request.id),
            "organization_id": str(request.organization_id),
            "organization_name": org_name,
            "organization_code": org_code,
            "from_plan": request.current_plan_code,
            "to_plan": request.requested_plan.code,
            "to_plan_name": request.requested_plan.name,
            "status": request.status,
            "note": request.note,
            "decision_note": request.decision_note,
            "created_at": request.created_at.isoformat() if request.created_at else None,
        }
        for request, org_name, org_code in rows
    ]


async def decide_plan_request(
    db: AsyncSession,
    request_id: uuid.UUID,
    *,
    approve: bool,
    decision_note: str | None = None,
    actor_id: uuid.UUID | None = None,
) -> PlanChangeRequest:
    """Super Admin decision. Approval applies the plan change — record the
    manual payment first if one is owed."""
    request = await db.get(PlanChangeRequest, request_id)
    if request is None:
        raise NotFoundError("Plan change request not found")
    if request.status != PlanChangeRequestStatus.PENDING.value:
        raise BusinessRuleError("This request has already been decided")

    request.status = (
        PlanChangeRequestStatus.APPROVED.value
        if approve
        else PlanChangeRequestStatus.REJECTED.value
    )
    request.decided_by = actor_id
    request.decided_at = _now()
    request.decision_note = decision_note
    await db.flush()
    await db.refresh(request, ["requested_plan"])

    if approve:
        await change_plan(
            db, request.organization_id,
            plan_code=request.requested_plan.code, actor_id=actor_id,
        )

    from app.services import notifications as notifications_service

    await notifications_service.create(
        db,
        request.organization_id,
        type="PLAN_CHANGE_" + request.status.upper(),
        severity="info" if approve else "warning",
        title=(
            f"Plan change to {request.requested_plan.name} "
            f"{'approved' if approve else 'rejected'}"
        ),
        message=decision_note,
    )
    return request


async def transition(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    to_status: str,
    event: str,
    actor_id: uuid.UUID | None = None,
) -> Subscription:
    subscription = await current_subscription(db, organization_id)
    if subscription is None:
        raise NotFoundError("No subscription")
    if to_status not in {s.value for s in SubscriptionStatus}:
        raise ValidationAppError("Unknown status", field="status")
    old = subscription.status
    subscription.status = to_status
    if to_status == SubscriptionStatus.CANCELLED.value:
        subscription.cancelled_at = _now()
    await db.flush()
    _record_event(
        subscription, db, event=event, from_status=old, to_status=to_status,
        actor_id=actor_id,
    )
    await db.flush()

    from app.services import events as domain_events

    await domain_events.emit(
        db,
        organization_id,
        event_type="subscription.status_changed",
        entity_type="subscription",
        entity_id=subscription.id,
        payload={"from": old, "to": to_status, "event": event},
    )
    logger.info("Subscription %s: %s -> %s (%s)", subscription.id, old, to_status, event)
    return subscription


async def cancel(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    at_period_end: bool = True,
    actor_id: uuid.UUID | None = None,
) -> Subscription:
    subscription = await current_subscription(db, organization_id)
    if subscription is None:
        raise NotFoundError("No subscription")
    if at_period_end and subscription.current_period_end is not None:
        subscription.cancel_at = subscription.current_period_end
        _record_event(
            subscription, db, event="cancel_at_period_end",
            from_status=subscription.status, to_status=subscription.status,
            actor_id=actor_id,
        )
        await db.flush()
        return subscription
    return await transition(
        db, organization_id,
        to_status=SubscriptionStatus.CANCELLED.value, event="cancelled",
        actor_id=actor_id,
    )


async def reactivate(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    actor_id: uuid.UUID | None = None,
    by_platform: bool = False,
) -> Subscription:
    """Undoes a cancellation. A tenant cannot self-reactivate out of
    payment-driven suspension — that path is record_payment (or an explicit
    platform transition)."""
    subscription = await current_subscription(db, organization_id)
    if subscription is None:
        raise NotFoundError("No subscription")
    if not by_platform and subscription.status in (
        SubscriptionStatus.SUSPENDED.value,
        SubscriptionStatus.PAST_DUE.value,
        SubscriptionStatus.GRACE_PERIOD.value,
    ):
        raise BusinessRuleError(
            "Payment is outstanding — the subscription reactivates when the "
            "platform administrator records your payment."
        )
    subscription.cancel_at = None
    subscription.cancelled_at = None
    return await transition(
        db, organization_id,
        to_status=SubscriptionStatus.ACTIVE.value, event="reactivated",
        actor_id=actor_id,
    )


PAYMENT_PROVIDERS = ("manual", "stripe", "razorpay")


async def set_provider(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    provider: str,
    provider_customer_id: str | None = None,
    provider_subscription_id: str | None = None,
    actor_id: uuid.UUID | None = None,
) -> Subscription:
    """Payment provider abstraction: which adapter collects payment for this
    tenant. `manual` = enterprise PO/invoice flow (platform admin records
    payments). Gateway credentials (API keys) are environment configuration
    of the future adapter — never stored in business tables; only the
    provider name and its opaque references live here."""
    if provider not in PAYMENT_PROVIDERS:
        raise ValidationAppError(
            f"Unknown provider (one of: {', '.join(PAYMENT_PROVIDERS)})", field="provider"
        )
    subscription = await current_subscription(db, organization_id)
    if subscription is None:
        raise NotFoundError("No subscription")
    old = subscription.provider
    subscription.provider = provider
    subscription.provider_customer_id = provider_customer_id
    subscription.provider_subscription_id = provider_subscription_id
    await db.flush()
    _record_event(
        subscription, db, event="provider_changed",
        from_status=subscription.status, to_status=subscription.status,
        actor_id=actor_id, payload={"from": old, "to": provider},
    )
    await db.flush()

    from app.services import audit

    await audit.record(
        db, organization_id, action="SUBSCRIPTION_PROVIDER_CHANGED",
        entity_type="subscription", entity_id=subscription.id,
        after={"provider": provider}, user_id=actor_id,
    )
    return subscription


async def render_invoice_html(
    db: AsyncSession, organization_id: uuid.UUID, invoice_id: uuid.UUID
) -> tuple[str, str]:
    """Printable invoice document. Returns (filename, html)."""
    from app.models import Organization

    invoice = (
        await db.execute(
            select(Invoice).where(
                Invoice.organization_id == organization_id, Invoice.id == invoice_id
            )
        )
    ).scalar_one_or_none()
    if invoice is None:
        raise NotFoundError("Invoice not found")
    org = await db.get(Organization, organization_id)
    subscription = await db.get(Subscription, invoice.subscription_id)
    plan_name = subscription.plan.name if subscription else ""
    payments = (
        await db.execute(
            select(Payment).where(Payment.invoice_id == invoice.id).order_by(
                Payment.received_at
            )
        )
    ).scalars().all()

    def fmt(value) -> str:
        return value.strftime("%d %b %Y") if value else "—"

    payment_rows = "".join(
        f"<tr><td>{fmt(p.received_at)}</td><td>{p.provider}</td>"
        f"<td>{p.provider_ref or '—'}</td>"
        f"<td style='text-align:right'>{p.amount} {p.currency}</td></tr>"
        for p in payments
    ) or "<tr><td colspan='4' style='color:#64748b'>No payments recorded</td></tr>"

    status_color = {"paid": "#059669", "issued": "#d97706", "void": "#64748b"}.get(
        invoice.status, "#334155"
    )
    html = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{invoice.number}</title>
<style>
 body {{ font-family: system-ui, -apple-system, sans-serif; color: #0f172a;
        max-width: 720px; margin: 40px auto; padding: 0 24px; }}
 h1 {{ font-size: 20px; }} table {{ border-collapse: collapse; width: 100%; }}
 th, td {{ text-align: left; padding: 8px 10px; border-bottom: 1px solid #e2e8f0;
        font-size: 14px; }}
 th {{ color: #64748b; text-transform: uppercase; font-size: 11px; }}
 .badge {{ display: inline-block; padding: 2px 10px; border-radius: 999px;
        color: #fff; font-size: 12px; background: {status_color}; }}
 .total {{ font-size: 18px; font-weight: 600; }}
 @media print {{ body {{ margin: 0; }} }}
</style></head><body>
<h1>Digital Signage Cloud — Invoice</h1>
<table>
 <tr><th>Invoice number</th><td>{invoice.number}</td>
     <th>Status</th><td><span class="badge">{invoice.status}</span></td></tr>
 <tr><th>Billed to</th><td>{org.name if org else ''} ({org.code if org else ''})</td>
     <th>Plan</th><td>{plan_name}</td></tr>
 <tr><th>Service period</th><td>{fmt(invoice.period_start)} – {fmt(invoice.period_end)}</td>
     <th>Issued</th><td>{fmt(invoice.issued_at)}</td></tr>
 <tr><th>Due</th><td>{fmt(invoice.due_at)}</td>
     <th>Paid</th><td>{fmt(invoice.paid_at)}</td></tr>
</table>
<p class="total">Amount due: {invoice.amount} {invoice.currency}</p>
<h3 style="font-size:14px">Payments</h3>
<table>
 <tr><th>Date</th><th>Provider</th><th>Reference</th>
     <th style="text-align:right">Amount</th></tr>
 {payment_rows}
</table>
<p style="color:#64748b;font-size:12px">Generated by Digital Signage Cloud.
Questions about this invoice? Contact your platform administrator.</p>
</body></html>"""
    return f"{invoice.number}.html", html


async def record_payment(
    db: AsyncSession,
    organization_id: uuid.UUID,
    invoice_id: uuid.UUID,
    *,
    provider: str = "manual",
    provider_ref: str | None = None,
    actor_id: uuid.UUID | None = None,
) -> Invoice:
    invoice = (
        await db.execute(
            select(Invoice).where(
                Invoice.organization_id == organization_id, Invoice.id == invoice_id
            )
        )
    ).scalar_one_or_none()
    if invoice is None:
        raise NotFoundError("Invoice not found")
    if invoice.status == InvoiceStatus.PAID.value:
        raise BusinessRuleError("Invoice is already paid")
    invoice.status = InvoiceStatus.PAID.value
    invoice.paid_at = _now()
    db.add(
        Payment(
            organization_id=organization_id,
            invoice_id=invoice.id,
            amount=invoice.amount,
            currency=invoice.currency,
            provider=provider,
            provider_ref=provider_ref,
            recorded_by=actor_id,
        )
    )
    await db.flush()

    # Payment clears dunning: back to active.
    subscription = await current_subscription(db, organization_id)
    if subscription is not None and subscription.status in (
        SubscriptionStatus.PAST_DUE.value,
        SubscriptionStatus.GRACE_PERIOD.value,
        SubscriptionStatus.SUSPENDED.value,
    ):
        await transition(
            db, organization_id,
            to_status=SubscriptionStatus.ACTIVE.value, event="payment_received",
            actor_id=actor_id,
        )
    return invoice


async def run_lifecycle(db: AsyncSession) -> dict:
    """Beat sweep: trial expiry, renewals, dunning ladder, cancellation.
    Idempotent — every transition is guarded by current state."""
    now = _now()
    counts = {"renewed": 0, "trial_ended": 0, "dunned": 0, "expired": 0}
    subscriptions = (
        await db.execute(
            select(Subscription).where(
                Subscription.status != SubscriptionStatus.EXPIRED.value
            )
        )
    ).scalars().all()
    for subscription in subscriptions:
        period_days = _CYCLE_DAYS.get(subscription.billing_cycle, 30)

        # Trial ends -> first paid period begins.
        if (
            subscription.status == SubscriptionStatus.TRIALING.value
            and _as_utc(subscription.trial_end_at) is not None
            and _as_utc(subscription.trial_end_at) <= now
        ):
            subscription.status = SubscriptionStatus.ACTIVE.value
            subscription.current_period_start = now
            subscription.current_period_end = now + timedelta(days=period_days)
            _record_event(
                subscription, db, event="trial_ended",
                from_status=SubscriptionStatus.TRIALING.value,
                to_status=SubscriptionStatus.ACTIVE.value,
            )
            await db.flush()
            await db.refresh(subscription, ["plan"])
            await _issue_invoice(db, subscription)
            counts["trial_ended"] += 1
            continue

        # Scheduled cancellation reached.
        if (
            _as_utc(subscription.cancel_at) is not None
            and _as_utc(subscription.cancel_at) <= now
            and subscription.status
            not in (SubscriptionStatus.CANCELLED.value, SubscriptionStatus.EXPIRED.value)
        ):
            old = subscription.status
            subscription.status = SubscriptionStatus.EXPIRED.value
            subscription.cancelled_at = subscription.cancelled_at or now
            _record_event(
                subscription, db, event="expired_after_cancel",
                from_status=old, to_status=SubscriptionStatus.EXPIRED.value,
            )
            counts["expired"] += 1
            continue

        # Renewal.
        if (
            subscription.status == SubscriptionStatus.ACTIVE.value
            and _as_utc(subscription.current_period_end) is not None
            and _as_utc(subscription.current_period_end) <= now
        ):
            subscription.current_period_start = now
            subscription.current_period_end = now + timedelta(days=period_days)
            _record_event(
                subscription, db, event="renewed",
                from_status=SubscriptionStatus.ACTIVE.value,
                to_status=SubscriptionStatus.ACTIVE.value,
            )
            await db.flush()
            await db.refresh(subscription, ["plan"])
            await _issue_invoice(db, subscription)
            counts["renewed"] += 1

        # Dunning ladder from oldest unpaid invoice.
        oldest_due = (
            await db.execute(
                select(func.min(Invoice.due_at)).where(
                    Invoice.subscription_id == subscription.id,
                    Invoice.status == InvoiceStatus.ISSUED.value,
                )
            )
        ).scalar_one_or_none()
        oldest_due = _as_utc(oldest_due)
        if oldest_due is None:
            continue
        overdue_days = (now - oldest_due).days
        target = None
        if overdue_days >= SUSPEND_AFTER_DAYS:
            target = SubscriptionStatus.SUSPENDED.value
        elif overdue_days >= GRACE_AFTER_DAYS:
            target = SubscriptionStatus.GRACE_PERIOD.value
        elif overdue_days >= PAST_DUE_AFTER_DAYS:
            target = SubscriptionStatus.PAST_DUE.value
        ladder = [
            SubscriptionStatus.ACTIVE.value,
            SubscriptionStatus.PAST_DUE.value,
            SubscriptionStatus.GRACE_PERIOD.value,
            SubscriptionStatus.SUSPENDED.value,
        ]
        if (
            target is not None
            and subscription.status in ladder
            and ladder.index(target) > ladder.index(subscription.status)
        ):
            old = subscription.status
            subscription.status = target
            _record_event(
                subscription, db, event="dunning", from_status=old, to_status=target,
                payload={"overdue_days": overdue_days},
            )
            counts["dunned"] += 1

            from app.services import notifications as notifications_service

            await notifications_service.create(
                db,
                subscription.organization_id,
                type="SUBSCRIPTION_" + target.upper(),
                severity="critical" if target == "suspended" else "warning",
                title=f"Subscription {target.replace('_', ' ')}: payment overdue "
                f"{overdue_days} days",
                message="Existing displays continue cached playback; new "
                "registrations, uploads and publishing are restricted until "
                "payment is received.",
            )
    await db.flush()
    return counts
