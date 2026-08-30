"""Phase-3 slice 3D-2: analytics platform — daily aggregates and scheduled
data exports.

Revision ID: 0031
Revises: 0030
Create Date: 2026-08-30
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.db.types import GUID, JSONType

revision: str = "0031"
down_revision: str | None = "0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "analytics_aggregates",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "organization_id",
            GUID(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("grain_date", sa.Date(), nullable=False),
        sa.Column("dimension_type", sa.String(30), nullable=False),
        sa.Column("dimension_id", GUID(), nullable=True),
        sa.Column("metrics_json", JSONType(), nullable=False),
        sa.Column(
            "computed_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "organization_id", "grain_date", "dimension_type", "dimension_id",
            name="uq_analytics_aggregates_dim",
        ),
    )
    op.create_index(
        "ix_analytics_aggregates_organization_id", "analytics_aggregates", ["organization_id"]
    )
    op.create_index(
        "ix_analytics_aggregates_org_date",
        "analytics_aggregates",
        ["organization_id", "grain_date"],
    )

    op.create_table(
        "data_exports",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "organization_id",
            GUID(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("dataset", sa.String(50), nullable=False),
        sa.Column("destination", sa.String(30), nullable=False),
        sa.Column("schedule_json", JSONType(), nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(500), nullable=True),
        sa.Column("last_object_key", sa.String(500), nullable=True),
        sa.Column(
            "created_by", GUID(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_data_exports_organization_id", "data_exports", ["organization_id"])
    op.create_index(
        "uq_data_exports_org_name", "data_exports", ["organization_id", "name"], unique=True
    )


def downgrade() -> None:
    op.drop_table("data_exports")
    op.drop_table("analytics_aggregates")
