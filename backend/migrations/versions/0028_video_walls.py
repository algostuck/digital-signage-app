"""Phase-3 slice 3C-1: video walls — shared canvases, member viewports and
sync sessions.

Revision ID: 0028
Revises: 0027
Create Date: 2026-08-30
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.db.types import GUID, JSONType

revision: str = "0028"
down_revision: str | None = "0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "video_walls",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "organization_id",
            GUID(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("canvas_json", JSONType(), nullable=False),
        sa.Column("sync_policy_json", JSONType(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("session_id", GUID(), nullable=True),
        sa.Column("session_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("session_epoch_ms", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_video_walls_organization_id", "video_walls", ["organization_id"])
    op.create_index(
        "uq_video_walls_org_name", "video_walls", ["organization_id", "name"], unique=True
    )

    op.create_table(
        "video_wall_members",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "wall_id", GUID(), sa.ForeignKey("video_walls.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "device_id", GUID(), sa.ForeignKey("devices.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("viewport_json", JSONType(), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("wall_id", "device_id", name="uq_video_wall_members_device"),
    )
    op.create_index("ix_video_wall_members_wall_id", "video_wall_members", ["wall_id"])
    op.create_index("ix_video_wall_members_device_id", "video_wall_members", ["device_id"])


def downgrade() -> None:
    op.drop_table("video_wall_members")
    op.drop_table("video_walls")
