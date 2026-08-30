"""Publishing: campaign_targets, deployments, deployment_devices.

Revision ID: 0009
Revises: 0008
Create Date: 2026-08-29
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.db.types import GUID, JSONType

revision: str = "0009"
down_revision: str | None = "0008"
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
        "campaign_targets",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "campaign_id",
            GUID(),
            sa.ForeignKey("campaigns.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("target_type", sa.String(20), nullable=False),
        sa.Column("target_id", GUID(), nullable=False),
        sa.Column("include_descendants", sa.Boolean(), nullable=False),
        sa.Column("is_exclusion", sa.Boolean(), nullable=False),
        sa.Column("conditions_json", JSONType(), nullable=True),
        *_audit_columns(),
    )
    op.create_index(
        "ix_campaign_targets_lookup",
        "campaign_targets",
        ["campaign_id", "target_type", "target_id"],
    )

    op.create_table(
        "deployments",
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
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("target_snapshot_json", JSONType(), nullable=True),
        sa.Column("error", sa.String(1000), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        *_audit_columns(),
    )
    op.create_index("ix_deployments_organization_id", "deployments", ["organization_id"])
    op.create_index("ix_deployments_campaign_id", "deployments", ["campaign_id"])
    op.create_index("ix_deployments_org_created", "deployments", ["organization_id", "created_at"])
    op.create_index("ix_deployments_status", "deployments", ["status"])

    op.create_table(
        "deployment_devices",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "deployment_id",
            GUID(),
            sa.ForeignKey("deployments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "device_id", GUID(), sa.ForeignKey("devices.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.String(1000), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("deployment_id", "device_id", name="uq_deployment_devices"),
    )
    op.create_index(
        "ix_deployment_devices_deployment_id", "deployment_devices", ["deployment_id"]
    )
    op.create_index("ix_deployment_devices_device_id", "deployment_devices", ["device_id"])


def downgrade() -> None:
    op.drop_table("deployment_devices")
    op.drop_table("deployments")
    op.drop_table("campaign_targets")
