"""Notification rules, channels and delivery evidence (P2-NTF-001..003).

Revision ID: 0017
Revises: 0016
Create Date: 2026-08-29
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.db.types import GUID, JSONType

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notification_rules",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "organization_id",
            GUID(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("event_type", sa.String(60), nullable=False),
        sa.Column("condition_json", JSONType(), nullable=True),
        sa.Column("channels_json", JSONType(), nullable=False),
        sa.Column("escalation_minutes", sa.Integer(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("organization_id", "name", name="uq_notification_rules_org_name"),
    )
    op.create_index(
        "ix_notification_rules_organization_id", "notification_rules", ["organization_id"]
    )
    op.create_index(
        "ix_notification_rules_event_type", "notification_rules", ["event_type"]
    )

    op.create_table(
        "notification_deliveries",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "organization_id",
            GUID(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "rule_id",
            GUID(),
            sa.ForeignKey("notification_rules.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "notification_id",
            GUID(),
            sa.ForeignKey("notifications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("recipient", sa.String(500), nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.String(500), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_notification_deliveries_organization_id",
        "notification_deliveries",
        ["organization_id"],
    )
    op.create_index(
        "ix_notification_deliveries_rule_id", "notification_deliveries", ["rule_id"]
    )
    op.create_index(
        "ix_notification_deliveries_state", "notification_deliveries", ["state"]
    )


def downgrade() -> None:
    op.drop_table("notification_deliveries")
    op.drop_table("notification_rules")
