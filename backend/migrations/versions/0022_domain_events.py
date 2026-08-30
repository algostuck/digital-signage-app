"""Phase-3 slice 3A-1: domain event bus — normalized business events,
consumer subscriptions and signed deliveries (2H shape).

Revision ID: 0022
Revises: 0021
Create Date: 2026-08-30
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.db.types import GUID, JSONType

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _ts(name: str, nullable: bool = False):
    return sa.Column(
        name, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=nullable
    )


def upgrade() -> None:
    op.create_table(
        "domain_events",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "organization_id",
            GUID(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(60), nullable=False),
        sa.Column("entity_type", sa.String(60), nullable=False),
        sa.Column("entity_id", GUID(), nullable=True),
        sa.Column("payload_json", JSONType(), nullable=True),
        sa.Column("request_id", sa.String(64), nullable=True),
        _ts("occurred_at"),
    )
    op.create_index("ix_domain_events_organization_id", "domain_events", ["organization_id"])
    op.create_index(
        "ix_domain_events_org_type", "domain_events", ["organization_id", "event_type"]
    )
    op.create_index(
        "ix_domain_events_org_occurred", "domain_events", ["organization_id", "occurred_at"]
    )

    op.create_table(
        "event_subscriptions",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "organization_id",
            GUID(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("url", sa.String(1000), nullable=False),
        sa.Column("event_types_json", JSONType(), nullable=False),
        sa.Column("secret", sa.String(128), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        _ts("created_at"),
        _ts("updated_at"),
    )
    op.create_index(
        "ix_event_subscriptions_organization_id", "event_subscriptions", ["organization_id"]
    )

    op.create_table(
        "event_deliveries",
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
            sa.ForeignKey("event_subscriptions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "event_id",
            GUID(),
            sa.ForeignKey("domain_events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(60), nullable=False),
        sa.Column("payload_json", JSONType(), nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("response_code", sa.Integer(), nullable=True),
        sa.Column("last_error", sa.String(500), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        _ts("created_at"),
        _ts("updated_at"),
    )
    op.create_index(
        "ix_event_deliveries_organization_id", "event_deliveries", ["organization_id"]
    )
    op.create_index(
        "ix_event_deliveries_subscription_id", "event_deliveries", ["subscription_id"]
    )
    op.create_index("ix_event_deliveries_event_id", "event_deliveries", ["event_id"])
    op.create_index("ix_event_deliveries_due", "event_deliveries", ["state", "next_attempt_at"])


def downgrade() -> None:
    op.drop_table("event_deliveries")
    op.drop_table("event_subscriptions")
    op.drop_table("domain_events")
