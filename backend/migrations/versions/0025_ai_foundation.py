"""Phase-3 slice 3B-1: AI foundation — policies, request ledger and
governed outputs (explainability, safety, approval routing).

Revision ID: 0025
Revises: 0024
Create Date: 2026-08-30
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.db.types import GUID, JSONType

revision: str = "0025"
down_revision: str | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_policies",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "organization_id",
            GUID(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("policy_type", sa.String(30), nullable=False),
        sa.Column("rules_json", JSONType(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_ai_policies_organization_id", "ai_policies", ["organization_id"])
    op.create_index(
        "ix_ai_policies_org_type", "ai_policies", ["organization_id", "policy_type"], unique=True
    )

    op.create_table(
        "ai_requests",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "organization_id",
            GUID(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "actor_id", GUID(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("operation", sa.String(30), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("model_ref", sa.String(100), nullable=True),
        sa.Column("template_version", sa.String(50), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("error", sa.String(500), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_ai_requests_organization_id", "ai_requests", ["organization_id"])
    op.create_index(
        "ix_ai_requests_org_created", "ai_requests", ["organization_id", "created_at"]
    )

    op.create_table(
        "ai_outputs",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "organization_id",
            GUID(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "request_id",
            GUID(),
            sa.ForeignKey("ai_requests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("output_kind", sa.String(30), nullable=False),
        sa.Column("content_json", JSONType(), nullable=False),
        sa.Column(
            "asset_id", GUID(), sa.ForeignKey("assets.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=False),
        sa.Column("fallback", sa.Boolean(), nullable=False),
        sa.Column("safety_status", sa.String(20), nullable=False),
        sa.Column("safety_notes", sa.String(500), nullable=True),
        sa.Column(
            "approved_by", GUID(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_ai_outputs_organization_id", "ai_outputs", ["organization_id"])
    op.create_index("ix_ai_outputs_request_id", "ai_outputs", ["request_id"])


def downgrade() -> None:
    op.drop_table("ai_outputs")
    op.drop_table("ai_requests")
    op.drop_table("ai_policies")
