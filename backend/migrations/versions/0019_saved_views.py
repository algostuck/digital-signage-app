"""Enterprise search: per-user saved views (P2-SRC-002).

Revision ID: 0019
Revises: 0018
Create Date: 2026-08-29
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.db.types import GUID, JSONType

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "saved_views",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "organization_id",
            GUID(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "user_id", GUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("module", sa.String(30), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("filter_json", JSONType(), nullable=False),
        sa.Column("columns_json", JSONType(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint(
            "organization_id", "user_id", "module", "name", name="uq_saved_views_owner_name"
        ),
    )
    op.create_index("ix_saved_views_organization_id", "saved_views", ["organization_id"])
    op.create_index("ix_saved_views_user_module", "saved_views", ["user_id", "module"])


def downgrade() -> None:
    op.drop_table("saved_views")
