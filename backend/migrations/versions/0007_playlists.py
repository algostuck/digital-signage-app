"""Playlists: playlists, playlist_items, playlist_versions.

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-29
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.db.types import GUID, JSONType

revision: str = "0007"
down_revision: str | None = "0006"
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
        "playlists",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "organization_id",
            GUID(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("loop_enabled", sa.Boolean(), nullable=False),
        sa.Column(
            "fallback_playlist_id",
            GUID(),
            sa.ForeignKey("playlists.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("current_version_id", GUID(), nullable=True),
        *_audit_columns(),
    )
    op.create_index("ix_playlists_organization_id", "playlists", ["organization_id"])

    op.create_table(
        "playlist_items",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "playlist_id",
            GUID(),
            sa.ForeignKey("playlists.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("item_type", sa.String(20), nullable=False),
        sa.Column(
            "asset_id", GUID(), sa.ForeignKey("assets.id", ondelete="CASCADE"), nullable=True
        ),
        sa.Column(
            "layout_id", GUID(), sa.ForeignKey("layouts.id", ondelete="CASCADE"), nullable=True
        ),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("transition_json", JSONType(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        *_audit_columns(),
    )
    op.create_index("ix_playlist_items_playlist_id", "playlist_items", ["playlist_id"])

    op.create_table(
        "playlist_versions",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "playlist_id",
            GUID(),
            sa.ForeignKey("playlists.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("items_json", JSONType(), nullable=False),
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("playlist_id", "version_no", name="uq_playlist_versions_playlist_no"),
    )
    op.create_index("ix_playlist_versions_playlist_id", "playlist_versions", ["playlist_id"])


def downgrade() -> None:
    op.drop_table("playlist_versions")
    op.drop_table("playlist_items")
    op.drop_table("playlists")
