"""Content CMS: folders, assets, asset_versions, asset_tags, upload_sessions.

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-29
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.db.types import GUID

revision: str = "0004"
down_revision: str | None = "0003"
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
        "folders",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "organization_id",
            GUID(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "parent_id", GUID(), sa.ForeignKey("folders.id", ondelete="RESTRICT"), nullable=True
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        *_audit_columns(),
        sa.UniqueConstraint(
            "organization_id", "parent_id", "name", name="uq_folders_org_parent_name"
        ),
    )
    op.create_index("ix_folders_organization_id", "folders", ["organization_id"])

    op.create_table(
        "assets",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "organization_id",
            GUID(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "folder_id", GUID(), sa.ForeignKey("folders.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=True),
        sa.Column("current_version_id", GUID(), nullable=True),
        *_audit_columns(),
    )
    op.create_index("ix_assets_organization_id", "assets", ["organization_id"])
    op.create_index("ix_assets_org_type_status", "assets", ["organization_id", "type", "status"])
    op.create_index("ix_assets_checksum", "assets", ["checksum"])
    op.create_index("ix_assets_folder_id", "assets", ["folder_id"])

    op.create_table(
        "asset_versions",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "asset_id", GUID(), sa.ForeignKey("assets.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("object_key", sa.String(1000), nullable=False),
        sa.Column("thumbnail_key", sa.String(1000), nullable=True),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("mime_type", sa.String(200), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("processing_status", sa.String(20), nullable=False),
        sa.Column("processing_error", sa.String(1000), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("asset_id", "version_no", name="uq_asset_versions_asset_no"),
    )
    op.create_index("ix_asset_versions_asset_id", "asset_versions", ["asset_id"])

    op.create_table(
        "asset_tags",
        sa.Column(
            "asset_id", GUID(), sa.ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column(
            "tag_id", GUID(), sa.ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True
        ),
    )

    op.create_table(
        "upload_sessions",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "organization_id",
            GUID(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("asset_id", GUID(), nullable=False),
        sa.Column("is_new_asset", sa.Boolean(), nullable=False),
        sa.Column("folder_id", GUID(), nullable=True),
        sa.Column("asset_name", sa.String(255), nullable=True),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("mime_type", sa.String(200), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("object_key", sa.String(1000), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        *_audit_columns(),
    )
    op.create_index(
        "ix_upload_sessions_organization_id", "upload_sessions", ["organization_id"]
    )


def downgrade() -> None:
    op.drop_table("upload_sessions")
    op.drop_table("asset_tags")
    op.drop_table("asset_versions")
    op.drop_table("assets")
    op.drop_table("folders")
