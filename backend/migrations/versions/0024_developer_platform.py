"""Phase-3 slice 3A-3: developer platform — versioned API products with
lifecycle/deprecation metadata and changelog.

Revision ID: 0024
Revises: 0023
Create Date: 2026-08-30
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.db.types import GUID, JSONType

revision: str = "0024"
down_revision: str | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "api_products",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_table(
        "api_versions",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "product_id",
            GUID(),
            sa.ForeignKey("api_products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.String(20), nullable=False),
        sa.Column("lifecycle_state", sa.String(20), nullable=False),
        sa.Column("sunset_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("changelog_json", JSONType(), nullable=True),
        sa.Column(
            "released_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("product_id", "version", name="uq_api_versions_version"),
    )
    op.create_index("ix_api_versions_product_id", "api_versions", ["product_id"])


def downgrade() -> None:
    op.drop_table("api_versions")
    op.drop_table("api_products")
