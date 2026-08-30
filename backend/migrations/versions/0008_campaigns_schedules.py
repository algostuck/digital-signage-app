"""Campaigns (minimal, extended in 1I) and timezone-aware schedules.

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-29
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.db.types import GUID, JSONType

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _audit_columns() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "campaigns",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "organization_id",
            GUID(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column(
            "playlist_id", GUID(), sa.ForeignKey("playlists.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column(
            "layout_id", GUID(), sa.ForeignKey("layouts.id", ondelete="SET NULL"), nullable=True
        ),
        *_audit_columns(),
    )
    op.create_index("ix_campaigns_organization_id", "campaigns", ["organization_id"])
    op.create_index("ix_campaigns_org_status", "campaigns", ["organization_id", "status"])

    op.create_table(
        "schedules",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "organization_id",
            GUID(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "campaign_id",
            GUID(),
            sa.ForeignKey("campaigns.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("start_time", sa.Time(), nullable=True),
        sa.Column("end_time", sa.Time(), nullable=True),
        sa.Column("days_of_week", JSONType(), nullable=True),
        sa.Column("timezone", sa.String(64), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False),
        *_audit_columns(),
    )
    op.create_index("ix_schedules_organization_id", "schedules", ["organization_id"])
    op.create_index("ix_schedules_campaign_id", "schedules", ["campaign_id"])
    op.create_index(
        "ix_schedules_dates", "schedules", ["organization_id", "start_date", "end_date"]
    )


def downgrade() -> None:
    op.drop_table("schedules")
    op.drop_table("campaigns")
