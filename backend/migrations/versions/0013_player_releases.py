"""OTA player updates: releases, rollout rings, per-device rollout state.

Revision ID: 0013
Revises: 0012
Create Date: 2026-08-29
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.db.types import GUID

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "player_releases",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "organization_id",
            GUID(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column(
            "package_asset_id",
            GUID(),
            sa.ForeignKey("assets.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("notes", sa.String(1000), nullable=True),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("organization_id", "version", name="uq_player_releases_org_version"),
    )
    op.create_index("ix_player_releases_organization_id", "player_releases", ["organization_id"])

    op.create_table(
        "rollout_batches",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "organization_id",
            GUID(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "release_id",
            GUID(),
            sa.ForeignKey("player_releases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ring_no", sa.Integer(), nullable=False),
        sa.Column("percentage", sa.Integer(), nullable=False),
        sa.Column("failure_threshold_pct", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("release_id", "ring_no", name="uq_rollout_batches_release_ring"),
    )
    op.create_index("ix_rollout_batches_organization_id", "rollout_batches", ["organization_id"])
    op.create_index("ix_rollout_batches_release_id", "rollout_batches", ["release_id"])
    op.create_index("ix_rollout_batches_state", "rollout_batches", ["state"])

    op.create_table(
        "rollout_devices",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "batch_id",
            GUID(),
            sa.ForeignKey("rollout_batches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "device_id", GUID(), sa.ForeignKey("devices.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("failure_reason", sa.String(500), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("batch_id", "device_id", name="uq_rollout_devices_batch_device"),
    )
    op.create_index("ix_rollout_devices_batch_id", "rollout_devices", ["batch_id"])
    op.create_index("ix_rollout_devices_device_state", "rollout_devices", ["device_id", "state"])


def downgrade() -> None:
    op.drop_table("rollout_devices")
    op.drop_table("rollout_batches")
    op.drop_table("player_releases")
