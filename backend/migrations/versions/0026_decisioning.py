"""Phase-3 slice 3B-2: decisioning — policies, ordered rules and the
bounded decision log with auditable reasons.

Revision ID: 0026
Revises: 0025
Create Date: 2026-08-30
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.db.types import GUID, JSONType

revision: str = "0026"
down_revision: str | None = "0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "decision_policies",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "organization_id",
            GUID(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("guardrails_json", JSONType(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_decision_policies_organization_id", "decision_policies", ["organization_id"]
    )
    op.create_index(
        "uq_decision_policies_org_name",
        "decision_policies",
        ["organization_id", "name"],
        unique=True,
    )

    op.create_table(
        "decision_rules",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "policy_id",
            GUID(),
            sa.ForeignKey("decision_policies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("conditions_json", JSONType(), nullable=False),
        sa.Column("actions_json", JSONType(), nullable=False),
    )
    op.create_index("ix_decision_rules_policy_id", "decision_rules", ["policy_id"])

    op.create_table(
        "decision_log",
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
            "campaign_id",
            GUID(),
            sa.ForeignKey("campaigns.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("reason_json", JSONType(), nullable=False),
        sa.Column(
            "decided_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_decision_log_organization_id", "decision_log", ["organization_id"])
    op.create_index(
        "ix_decision_log_org_decided", "decision_log", ["organization_id", "decided_at"]
    )
    op.create_index("ix_decision_log_device", "decision_log", ["device_id", "decided_at"])


def downgrade() -> None:
    op.drop_table("decision_log")
    op.drop_table("decision_rules")
    op.drop_table("decision_policies")
