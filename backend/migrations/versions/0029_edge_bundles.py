"""Phase-3 slice 3C-2: edge bundles — signed prefetch manifests with
per-device rollout state.

Revision ID: 0029
Revises: 0028
Create Date: 2026-08-30
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.db.types import GUID, JSONType

revision: str = "0029"
down_revision: str | None = "0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "edge_bundles",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "organization_id",
            GUID(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("bundle_version", sa.Integer(), nullable=False),
        sa.Column(
            "group_id",
            GUID(),
            sa.ForeignKey("device_groups.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("manifest_json", JSONType(), nullable=False),
        sa.Column("signature", sa.String(64), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_edge_bundles_organization_id", "edge_bundles", ["organization_id"])
    op.create_index("ix_edge_bundles_org_state", "edge_bundles", ["organization_id", "state"])

    op.create_table(
        "edge_bundle_devices",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "bundle_id",
            GUID(),
            sa.ForeignKey("edge_bundles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "device_id", GUID(), sa.ForeignKey("devices.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("bundle_id", "device_id", name="uq_edge_bundle_devices"),
    )
    op.create_index("ix_edge_bundle_devices_bundle_id", "edge_bundle_devices", ["bundle_id"])
    op.create_index("ix_edge_bundle_devices_device_id", "edge_bundle_devices", ["device_id"])


def downgrade() -> None:
    op.drop_table("edge_bundle_devices")
    op.drop_table("edge_bundles")
