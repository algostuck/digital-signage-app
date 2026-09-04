"""Device-health snapshots for the organization dashboard trend.

Revision ID: 0036
Revises: 0035
Create Date: 2026-09-04
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.db.types import GUID

revision: str = "0036"
down_revision: str | None = "0035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "device_health_snapshots",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "organization_id",
            GUID(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("online", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("warning", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("offline", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("na", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index(
        "ix_device_health_snapshots_org_captured",
        "device_health_snapshots",
        ["organization_id", "captured_at"],
    )
    op.create_index(
        "ix_device_health_snapshots_organization_id",
        "device_health_snapshots",
        ["organization_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_device_health_snapshots_organization_id", table_name="device_health_snapshots")
    op.drop_index("ix_device_health_snapshots_org_captured", table_name="device_health_snapshots")
    op.drop_table("device_health_snapshots")
