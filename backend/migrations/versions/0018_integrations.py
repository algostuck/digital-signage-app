"""Integrations: webhook subscriptions with signed retried deliveries and
scoped API keys (P2-INT-001..003).

Revision ID: 0018
Revises: 0017
Create Date: 2026-08-29
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.db.types import GUID, JSONType

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "webhook_subscriptions",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "organization_id",
            GUID(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("url", sa.String(1000), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("event_types_json", JSONType(), nullable=False),
        sa.Column("secret", sa.String(128), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_webhook_subscriptions_organization_id",
        "webhook_subscriptions",
        ["organization_id"],
    )

    op.create_table(
        "webhook_deliveries",
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
            sa.ForeignKey("webhook_subscriptions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(60), nullable=False),
        sa.Column("event_id", GUID(), nullable=False),
        sa.Column("payload_json", JSONType(), nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("response_code", sa.Integer(), nullable=True),
        sa.Column("last_error", sa.String(500), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_webhook_deliveries_organization_id", "webhook_deliveries", ["organization_id"]
    )
    op.create_index(
        "ix_webhook_deliveries_subscription_id", "webhook_deliveries", ["subscription_id"]
    )
    op.create_index(
        "ix_webhook_deliveries_state_next",
        "webhook_deliveries",
        ["state", "next_attempt_at"],
    )

    op.create_table(
        "api_keys",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "organization_id",
            GUID(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("prefix", sa.String(12), nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("scopes_json", JSONType(), nullable=False),
        sa.Column(
            "created_by", GUID(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("organization_id", "name", name="uq_api_keys_org_name"),
    )
    op.create_index("ix_api_keys_organization_id", "api_keys", ["organization_id"])


def downgrade() -> None:
    op.drop_table("api_keys")
    op.drop_table("webhook_deliveries")
    op.drop_table("webhook_subscriptions")
