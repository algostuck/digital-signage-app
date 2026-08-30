"""Phase-3 slice 3D-3: fleet intelligence — anomaly rules, evidence-backed
anomalies and the human-in-the-loop action trail.

Revision ID: 0032
Revises: 0031
Create Date: 2026-08-30
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.db.types import GUID, JSONType

revision: str = "0032"
down_revision: str | None = "0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "anomaly_rules",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "organization_id",
            GUID(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("signal_type", sa.String(30), nullable=False),
        sa.Column("threshold_json", JSONType(), nullable=False),
        sa.Column("window_hours", sa.Integer(), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_anomaly_rules_organization_id", "anomaly_rules", ["organization_id"])
    op.create_index(
        "uq_anomaly_rules_org_name", "anomaly_rules", ["organization_id", "name"], unique=True
    )

    op.create_table(
        "anomalies",
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
        sa.Column(
            "rule_id",
            GUID(),
            sa.ForeignKey("anomaly_rules.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("score", sa.Numeric(6, 2), nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("evidence_json", JSONType(), nullable=False),
        sa.Column("recommendation", sa.String(500), nullable=True),
        sa.Column(
            "opened_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_anomalies_organization_id", "anomalies", ["organization_id"])
    op.create_index("ix_anomalies_org_state", "anomalies", ["organization_id", "state"])
    op.create_index("ix_anomalies_device", "anomalies", ["device_id", "state"])

    op.create_table(
        "anomaly_actions",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "anomaly_id", GUID(), sa.ForeignKey("anomalies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "actor_id", GUID(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("outcome", sa.String(200), nullable=True),
        sa.Column(
            "executed_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_anomaly_actions_anomaly_id", "anomaly_actions", ["anomaly_id"])


def downgrade() -> None:
    op.drop_table("anomaly_actions")
    op.drop_table("anomalies")
    op.drop_table("anomaly_rules")
