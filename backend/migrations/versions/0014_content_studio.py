"""Content studio: template versioning + approval status, widget framework,
asset collections.

Revision ID: 0014
Revises: 0013
Create Date: 2026-08-29
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.db.types import GUID, JSONType

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Existing templates become versioned + governed (P2-CNT-001).
    op.add_column(
        "templates",
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
    )
    op.add_column("templates", sa.Column("current_version_id", GUID(), nullable=True))

    op.create_table(
        "template_versions",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "template_id",
            GUID(),
            sa.ForeignKey("templates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("canvas_json", JSONType(), nullable=False),
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "created_by", GUID(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.UniqueConstraint("template_id", "version_no", name="uq_template_versions_no"),
    )
    op.create_index("ix_template_versions_template_id", "template_versions", ["template_id"])

    op.create_table(
        "widgets",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "organization_id",
            GUID(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("fallback_json", JSONType(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("organization_id", "name", name="uq_widgets_org_name"),
    )
    op.create_index("ix_widgets_organization_id", "widgets", ["organization_id"])

    op.create_table(
        "widget_versions",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "widget_id", GUID(), sa.ForeignKey("widgets.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("config_schema_json", JSONType(), nullable=False),
        sa.Column("defaults_json", JSONType(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("widget_id", "version_no", name="uq_widget_versions_no"),
    )
    op.create_index("ix_widget_versions_widget_id", "widget_versions", ["widget_id"])

    op.create_table(
        "asset_collections",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "organization_id",
            GUID(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("organization_id", "name", name="uq_asset_collections_org_name"),
    )
    op.create_index(
        "ix_asset_collections_organization_id", "asset_collections", ["organization_id"]
    )

    op.create_table(
        "asset_collection_items",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "collection_id",
            GUID(),
            sa.ForeignKey("asset_collections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "asset_id", GUID(), sa.ForeignKey("assets.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.UniqueConstraint(
            "collection_id", "asset_id", name="uq_asset_collection_items_asset"
        ),
    )
    op.create_index(
        "ix_asset_collection_items_collection_id", "asset_collection_items", ["collection_id"]
    )


def downgrade() -> None:
    op.drop_table("asset_collection_items")
    op.drop_table("asset_collections")
    op.drop_table("widget_versions")
    op.drop_table("widgets")
    op.drop_table("template_versions")
    op.drop_column("templates", "current_version_id")
    op.drop_column("templates", "status")
