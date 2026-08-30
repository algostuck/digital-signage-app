"""Advanced device ops: dynamic groups, screenshots, incidents.

Revision ID: 0012
Revises: 0011
Create Date: 2026-08-29
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.db.types import GUID, JSONType

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "device_groups",
        sa.Column("group_type", sa.String(20), nullable=False, server_default="static"),
    )
    op.add_column("device_groups", sa.Column("rule_json", JSONType(), nullable=True))

    op.create_table(
        "screenshots",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "organization_id",
            GUID(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "device_id", GUID(), sa.ForeignKey("devices.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("object_key", sa.String(1000), nullable=False),
        sa.Column("mime_type", sa.String(50), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column(
            "captured_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_screenshots_organization_id", "screenshots", ["organization_id"])
    op.create_index(
        "ix_screenshots_device_captured", "screenshots", ["device_id", "captured_at"]
    )

    op.create_table(
        "incidents",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "organization_id",
            GUID(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "device_id", GUID(), sa.ForeignKey("devices.id", ondelete="CASCADE"), nullable=True
        ),
        sa.Column("type", sa.String(60), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column(
            "opened_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "acknowledged_by",
            GUID(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution", sa.String(200), nullable=True),
        sa.Column("payload_json", JSONType(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_incidents_organization_id", "incidents", ["organization_id"])
    op.create_index("ix_incidents_org_state", "incidents", ["organization_id", "state"])
    op.create_index("ix_incidents_device_id", "incidents", ["device_id"])


def downgrade() -> None:
    op.drop_table("incidents")
    op.drop_table("screenshots")
    op.drop_column("device_groups", "rule_json")
    op.drop_column("device_groups", "group_type")
