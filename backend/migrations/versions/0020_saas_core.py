"""SaaS core: tenant memberships, plans, entitlements, subscriptions,
usage counters/events, invoices and payments.

Revision ID: 0020
Revises: 0019
Create Date: 2026-08-30
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.db.types import GUID, JSONType

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _ts(name: str):
    return sa.Column(
        name, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


def upgrade() -> None:
    op.create_table(
        "tenant_users",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "organization_id",
            GUID(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id", GUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "role_id", GUID(), sa.ForeignKey("roles.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("is_owner", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        _ts("joined_at"),
        _ts("created_at"),
        _ts("updated_at"),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_tenant_users_member"),
    )
    op.create_index("ix_tenant_users_organization_id", "tenant_users", ["organization_id"])
    op.create_index("ix_tenant_users_user_id", "tenant_users", ["user_id"])

    op.create_table(
        "plans",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("code", sa.String(50), nullable=False, unique=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("prices_json", JSONType(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        _ts("created_at"),
        _ts("updated_at"),
    )

    op.create_table(
        "plan_entitlements",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "plan_id", GUID(), sa.ForeignKey("plans.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("key", sa.String(60), nullable=False),
        sa.Column("int_value", sa.Integer(), nullable=True),
        sa.Column("bool_value", sa.Boolean(), nullable=True),
        sa.UniqueConstraint("plan_id", "key", name="uq_plan_entitlements_key"),
    )
    op.create_index("ix_plan_entitlements_plan_id", "plan_entitlements", ["plan_id"])

    op.create_table(
        "subscriptions",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "organization_id",
            GUID(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "plan_id", GUID(), sa.ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("billing_cycle", sa.String(20), nullable=False),
        _ts("start_at"),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trial_start_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trial_end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("provider_customer_id", sa.String(200), nullable=True),
        sa.Column("provider_subscription_id", sa.String(200), nullable=True),
        _ts("created_at"),
        _ts("updated_at"),
    )
    op.create_index("ix_subscriptions_organization_id", "subscriptions", ["organization_id"])
    op.create_index(
        "ix_subscriptions_org_status", "subscriptions", ["organization_id", "status"]
    )

    op.create_table(
        "subscription_items",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "subscription_id",
            GUID(),
            sa.ForeignKey("subscriptions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("key", sa.String(60), nullable=False),
        sa.Column("int_value", sa.Integer(), nullable=True),
        sa.Column("bool_value", sa.Boolean(), nullable=True),
        sa.UniqueConstraint("subscription_id", "key", name="uq_subscription_items_key"),
    )
    op.create_index(
        "ix_subscription_items_subscription_id", "subscription_items", ["subscription_id"]
    )

    op.create_table(
        "subscription_events",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "organization_id",
            GUID(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "subscription_id",
            GUID(),
            sa.ForeignKey("subscriptions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event", sa.String(60), nullable=False),
        sa.Column("from_status", sa.String(20), nullable=True),
        sa.Column("to_status", sa.String(20), nullable=True),
        sa.Column(
            "actor_id", GUID(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("payload_json", JSONType(), nullable=True),
        _ts("created_at"),
    )
    op.create_index(
        "ix_subscription_events_organization_id", "subscription_events", ["organization_id"]
    )
    op.create_index(
        "ix_subscription_events_subscription_id", "subscription_events", ["subscription_id"]
    )

    op.create_table(
        "usage_counters",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "organization_id",
            GUID(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("metric", sa.String(60), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("used_value", sa.Integer(), nullable=False),
        sa.Column("limit_value", sa.Integer(), nullable=True),
        _ts("updated_at"),
        sa.UniqueConstraint(
            "organization_id", "metric", "period_start", name="uq_usage_counters_period"
        ),
    )
    op.create_index("ix_usage_counters_organization_id", "usage_counters", ["organization_id"])

    op.create_table(
        "usage_events",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "organization_id",
            GUID(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("metric", sa.String(60), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("ref", sa.String(200), nullable=True),
        _ts("occurred_at"),
    )
    op.create_index("ix_usage_events_organization_id", "usage_events", ["organization_id"])
    op.create_index("ix_usage_events_org_metric", "usage_events", ["organization_id", "metric"])

    op.create_table(
        "invoices",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "organization_id",
            GUID(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "subscription_id",
            GUID(),
            sa.ForeignKey("subscriptions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("number", sa.String(40), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        _ts("issued_at"),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        _ts("created_at"),
        _ts("updated_at"),
        sa.UniqueConstraint("number", name="uq_invoices_number"),
    )
    op.create_index("ix_invoices_organization_id", "invoices", ["organization_id"])
    op.create_index("ix_invoices_subscription_id", "invoices", ["subscription_id"])

    op.create_table(
        "payments",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "organization_id",
            GUID(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "invoice_id",
            GUID(),
            sa.ForeignKey("invoices.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("provider_ref", sa.String(200), nullable=True),
        sa.Column(
            "recorded_by", GUID(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        _ts("received_at"),
    )
    op.create_index("ix_payments_organization_id", "payments", ["organization_id"])
    op.create_index("ix_payments_invoice_id", "payments", ["invoice_id"])


def downgrade() -> None:
    op.drop_table("payments")
    op.drop_table("invoices")
    op.drop_table("usage_events")
    op.drop_table("usage_counters")
    op.drop_table("subscription_events")
    op.drop_table("subscription_items")
    op.drop_table("subscriptions")
    op.drop_table("plan_entitlements")
    op.drop_table("plans")
    op.drop_table("tenant_users")
