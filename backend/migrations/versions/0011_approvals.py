"""Approval & governance engine: policies, requests, actions.

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-29
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.db.types import GUID, JSONType

revision: str = "0011"
down_revision: str | None = "0010"
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
        "approval_policies",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "organization_id",
            GUID(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("entity_type", sa.String(40), nullable=False),
        sa.Column("require_approval", sa.Boolean(), nullable=False),
        sa.Column("maker_checker", sa.Boolean(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("rules_json", JSONType(), nullable=True),
        *_audit_columns(),
        sa.UniqueConstraint("organization_id", "entity_type", name="uq_approval_policies_org_type"),
    )
    op.create_index(
        "ix_approval_policies_organization_id", "approval_policies", ["organization_id"]
    )

    op.create_table(
        "approval_requests",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "organization_id",
            GUID(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("entity_type", sa.String(40), nullable=False),
        sa.Column("entity_id", GUID(), nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column(
            "requester_id", GUID(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "decided_by", GUID(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("comments", sa.String(2000), nullable=True),
        *_audit_columns(),
    )
    op.create_index(
        "ix_approval_requests_organization_id", "approval_requests", ["organization_id"]
    )
    op.create_index(
        "ix_approval_requests_org_state", "approval_requests", ["organization_id", "state"]
    )
    op.create_index(
        "ix_approval_requests_entity", "approval_requests", ["entity_type", "entity_id"]
    )

    op.create_table(
        "approval_actions",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "approval_request_id",
            GUID(),
            sa.ForeignKey("approval_requests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "actor_id", GUID(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("comments", sa.String(2000), nullable=True),
        sa.Column("from_state", sa.String(20), nullable=True),
        sa.Column("to_state", sa.String(20), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_approval_actions_approval_request_id", "approval_actions", ["approval_request_id"]
    )


def downgrade() -> None:
    op.drop_table("approval_actions")
    op.drop_table("approval_requests")
    op.drop_table("approval_policies")
