"""Phase-3 slice 3B-3: experimentation — A/B arms over 2E campaign
variants with stable per-device assignment evidence.

Revision ID: 0027
Revises: 0026
Create Date: 2026-08-30
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.db.types import GUID

revision: str = "0027"
down_revision: str | None = "0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "experiments",
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
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_experiments_organization_id", "experiments", ["organization_id"])
    op.create_index("ix_experiments_campaign_id", "experiments", ["campaign_id"])
    op.create_index(
        "uq_experiments_org_name", "experiments", ["organization_id", "name"], unique=True
    )

    op.create_table(
        "experiment_variants",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "experiment_id",
            GUID(),
            sa.ForeignKey("experiments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "variant_id",
            GUID(),
            sa.ForeignKey("campaign_variants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("allocation_pct", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("experiment_id", "variant_id", name="uq_experiment_variants_ref"),
    )
    op.create_index(
        "ix_experiment_variants_experiment_id", "experiment_variants", ["experiment_id"]
    )

    op.create_table(
        "experiment_assignments",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "experiment_id",
            GUID(),
            sa.ForeignKey("experiments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "device_id", GUID(), sa.ForeignKey("devices.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "variant_id",
            GUID(),
            sa.ForeignKey("campaign_variants.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "assigned_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("experiment_id", "device_id", name="uq_experiment_assignments"),
    )
    op.create_index(
        "ix_experiment_assignments_experiment_id", "experiment_assignments", ["experiment_id"]
    )
    op.create_index(
        "ix_experiment_assignments_device_id", "experiment_assignments", ["device_id"]
    )


def downgrade() -> None:
    op.drop_table("experiment_assignments")
    op.drop_table("experiment_variants")
    op.drop_table("experiments")
