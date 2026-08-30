"""Phase-3 slice 3A-2: dynamic data sources — guarded external feeds with
versioned schemas and bounded snapshots (cache + last-known-good).

Revision ID: 0023
Revises: 0022
Create Date: 2026-08-30
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.db.types import GUID, JSONType

revision: str = "0023"
down_revision: str | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "data_sources",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "organization_id",
            GUID(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("endpoint", sa.String(1000), nullable=False),
        sa.Column("auth_header", sa.String(100), nullable=True),
        sa.Column("auth_token_ref", sa.String(100), nullable=True),
        sa.Column("cache_ttl_seconds", sa.Integer(), nullable=False),
        sa.Column("refresh_seconds", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("last_ok_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(500), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("organization_id", "name", name="uq_data_sources_org_name"),
    )
    op.create_index("ix_data_sources_organization_id", "data_sources", ["organization_id"])

    op.create_table(
        "data_source_schemas",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "source_id",
            GUID(),
            sa.ForeignKey("data_sources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("schema_json", JSONType(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("source_id", "version_no", name="uq_data_source_schemas_no"),
    )
    op.create_index("ix_data_source_schemas_source_id", "data_source_schemas", ["source_id"])

    op.create_table(
        "data_source_snapshots",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "source_id",
            GUID(),
            sa.ForeignKey("data_sources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("valid", sa.Boolean(), nullable=False),
        sa.Column("payload_json", JSONType(), nullable=True),
        sa.Column("error", sa.String(500), nullable=True),
    )
    op.create_index(
        "ix_data_source_snapshots_source_id", "data_source_snapshots", ["source_id"]
    )
    op.create_index(
        "ix_data_source_snapshots_source_fetched",
        "data_source_snapshots",
        ["source_id", "fetched_at"],
    )


def downgrade() -> None:
    op.drop_table("data_source_snapshots")
    op.drop_table("data_source_schemas")
    op.drop_table("data_sources")
