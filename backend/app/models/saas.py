"""SaaS core: multi-tenant membership, plans, entitlements, subscriptions,
usage and billing records.

Design (docs/SAAS_CORE.md):
- A user's row lives in their *home* organization (unchanged from Phase 1);
  `tenant_users` grants that same identity access to OTHER organizations
  with a per-membership role. Home-org access is implicit — no backfill.
- Subscription answers "what is this tenant entitled to"; billing
  (invoices/payments) answers "how are they charged"; usage counters answer
  "how much are they consuming". The three are deliberately separate.
- Entitlements are data (plan_entitlements + subscription_items overrides),
  never `if plan == "enterprise"` branches.
"""

import datetime as dt
import enum
import uuid

from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import GUID, JSONType, UTCDateTime


class MembershipStatus(enum.StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"


class TenantUser(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Cross-organization membership: grants an existing user identity
    access to another tenant with a single tenant-scoped role."""

    __tablename__ = "tenant_users"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_tenant_users_member"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("roles.id", ondelete="SET NULL"), nullable=True
    )
    is_owner: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=MembershipStatus.ACTIVE.value
    )
    joined_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), nullable=False
    )

    role = relationship("Role", lazy="selectin")


class BillingCycle(enum.StrEnum):
    MONTHLY = "monthly"
    YEARLY = "yearly"
    CUSTOM = "custom"


class Plan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Platform-scoped reusable subscription plan (no organization_id)."""

    __tablename__ = "plans"

    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # {"monthly": {"amount": "25000", "currency": "INR"}, "yearly": {...}}
    prices_json: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    entitlements: Mapped[list["PlanEntitlement"]] = relationship(
        lazy="selectin", cascade="all, delete-orphan"
    )


class PlanEntitlement(UUIDPrimaryKeyMixin, Base):
    """One entitlement value on a plan. Numeric entitlements use int_value
    (NULL = unlimited); feature entitlements use bool_value."""

    __tablename__ = "plan_entitlements"
    __table_args__ = (
        UniqueConstraint("plan_id", "key", name="uq_plan_entitlements_key"),
    )

    plan_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("plans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    key: Mapped[str] = mapped_column(String(60), nullable=False)
    int_value: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bool_value: Mapped[bool | None] = mapped_column(Boolean, nullable=True)


class SubscriptionStatus(enum.StrEnum):
    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    GRACE_PERIOD = "grace_period"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class Subscription(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "subscriptions"
    __table_args__ = (Index("ix_subscriptions_org_status", "organization_id", "status"),)

    plan_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=SubscriptionStatus.ACTIVE.value
    )
    billing_cycle: Mapped[str] = mapped_column(
        String(20), nullable=False, default=BillingCycle.MONTHLY.value
    )
    start_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), nullable=False
    )
    current_period_start: Mapped[dt.datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    current_period_end: Mapped[dt.datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    trial_start_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    trial_end_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    cancel_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    cancelled_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    # Billing-provider references (abstraction: manual/stripe/razorpay).
    provider: Mapped[str] = mapped_column(String(30), nullable=False, default="manual")
    provider_customer_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    provider_subscription_id: Mapped[str | None] = mapped_column(String(200), nullable=True)

    plan: Mapped[Plan] = relationship(lazy="selectin")
    items: Mapped[list["SubscriptionItem"]] = relationship(
        lazy="selectin", cascade="all, delete-orphan"
    )


class SubscriptionItem(UUIDPrimaryKeyMixin, Base):
    """Per-subscription entitlement override / add-on (e.g. extra device
    packs, enterprise-negotiated limits)."""

    __tablename__ = "subscription_items"
    __table_args__ = (
        UniqueConstraint("subscription_id", "key", name="uq_subscription_items_key"),
    )

    subscription_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("subscriptions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    key: Mapped[str] = mapped_column(String(60), nullable=False)
    int_value: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bool_value: Mapped[bool | None] = mapped_column(Boolean, nullable=True)


class SubscriptionEvent(UUIDPrimaryKeyMixin, TenantMixin, Base):
    """Append-only lifecycle trail (signup, renewals, status transitions)."""

    __tablename__ = "subscription_events"

    subscription_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("subscriptions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event: Mapped[str] = mapped_column(String(60), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    to_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    payload_json: Mapped[dict | None] = mapped_column(JSONType(), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), nullable=False
    )


class PlanChangeRequestStatus(enum.StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class PlanChangeRequest(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """Tenant-requested upgrade/downgrade. Plans never change self-serve:
    the Super Admin approves (after manual payment is received) and only
    then does the subscription move to the requested plan."""

    __tablename__ = "plan_change_requests"
    __table_args__ = (
        Index("ix_plan_change_requests_status", "status"),
    )

    subscription_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("subscriptions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    requested_plan_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False
    )
    current_plan_code: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=PlanChangeRequestStatus.PENDING.value
    )
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    requested_by: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    decided_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    decision_note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    requested_plan: Mapped[Plan] = relationship(lazy="selectin")


class UsageCounter(UUIDPrimaryKeyMixin, TenantMixin, Base):
    """Aggregated usage per metric and period — dashboards and limit checks
    read this, not repeated COUNT(*) over live tables."""

    __tablename__ = "usage_counters"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "metric", "period_start", name="uq_usage_counters_period"
        ),
    )

    metric: Mapped[str] = mapped_column(String(60), nullable=False)
    period_start: Mapped[dt.date] = mapped_column(Date, nullable=False)
    period_end: Mapped[dt.date] = mapped_column(Date, nullable=False)
    used_value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    limit_value: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), nullable=False
    )


class UsageEvent(UUIDPrimaryKeyMixin, TenantMixin, Base):
    """Slim metered-consumption record (api calls batched, ai credits …)."""

    __tablename__ = "usage_events"
    __table_args__ = (Index("ix_usage_events_org_metric", "organization_id", "metric"),)

    metric: Mapped[str] = mapped_column(String(60), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    ref: Mapped[str | None] = mapped_column(String(200), nullable=True)
    occurred_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), nullable=False
    )


class InvoiceStatus(enum.StrEnum):
    ISSUED = "issued"
    PAID = "paid"
    VOID = "void"


class Invoice(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "invoices"
    __table_args__ = (UniqueConstraint("number", name="uq_invoices_number"),)

    subscription_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("subscriptions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    number: Mapped[str] = mapped_column(String(40), nullable=False)
    period_start: Mapped[dt.datetime] = mapped_column(UTCDateTime(), nullable=False)
    period_end: Mapped[dt.datetime] = mapped_column(UTCDateTime(), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=InvoiceStatus.ISSUED.value
    )
    issued_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), nullable=False
    )
    due_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    paid_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class Payment(UUIDPrimaryKeyMixin, TenantMixin, Base):
    __tablename__ = "payments"

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    provider: Mapped[str] = mapped_column(String(30), nullable=False, default="manual")
    provider_ref: Mapped[str | None] = mapped_column(String(200), nullable=True)
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    received_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), nullable=False
    )
