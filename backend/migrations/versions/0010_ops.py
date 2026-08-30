"""Operations: audit_logs, notifications, device_events, playback_events.

Revision ID: 0010
Revises: 0009
Create Date: 2026-08-29
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.db.types import GUID, JSONType

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_logs",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "organization_id",
            GUID(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("user_id", GUID(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(60), nullable=False),
        sa.Column("entity_type", sa.String(40), nullable=False),
        sa.Column("entity_id", sa.String(64), nullable=True),
        sa.Column("before_json", JSONType(), nullable=True),
        sa.Column("after_json", JSONType(), nullable=True),
        sa.Column("ip_address", sa.String(50), nullable=True),
        sa.Column("request_id", sa.String(64), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_audit_logs_organization_id", "audit_logs", ["organization_id"])
    op.create_index("ix_audit_logs_org_created", "audit_logs", ["organization_id", "created_at"])
    op.create_index("ix_audit_logs_entity", "audit_logs", ["entity_type", "entity_id"])

    op.create_table(
        "notifications",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "organization_id",
            GUID(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("user_id", GUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("type", sa.String(60), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("message", sa.String(1000), nullable=True),
        sa.Column("payload_json", JSONType(), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_notifications_organization_id", "notifications", ["organization_id"])
    op.create_index(
        "ix_notifications_org_created", "notifications", ["organization_id", "created_at"]
    )

    op.create_table(
        "device_events",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "device_id", GUID(), sa.ForeignKey("devices.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("event_type", sa.String(60), nullable=False),
        sa.Column(
            "event_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("payload_json", JSONType(), nullable=True),
    )
    op.create_index("ix_device_events_device_at", "device_events", ["device_id", "event_at"])

    op.create_table(
        "playback_events",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "organization_id",
            GUID(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "device_id", GUID(), sa.ForeignKey("devices.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("campaign_id", GUID(), nullable=True),
        sa.Column("playlist_id", GUID(), nullable=True),
        sa.Column("asset_id", GUID(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result", sa.String(20), nullable=True),
    )
    op.create_index(
        "ix_playback_events_organization_id", "playback_events", ["organization_id"]
    )
    op.create_index(
        "ix_playback_events_device_started", "playback_events", ["device_id", "started_at"]
    )
    op.create_index(
        "ix_playback_events_campaign_started", "playback_events", ["campaign_id", "started_at"]
    )


def downgrade() -> None:
    op.drop_table("playback_events")
    op.drop_table("device_events")
    op.drop_table("notifications")
    op.drop_table("audit_logs")
