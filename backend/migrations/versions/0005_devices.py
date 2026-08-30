"""Devices: registry, groups, capabilities, commands, heartbeats; org enrollment key.

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-29
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.db.types import GUID, JSONType

revision: str = "0005"
down_revision: str | None = "0004"
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
    # Plain column + unique index: SQLite cannot ALTER-add a unique constraint.
    op.add_column("organizations", sa.Column("enrollment_key", sa.String(64), nullable=True))
    op.create_index(
        "uq_organizations_enrollment_key", "organizations", ["enrollment_key"], unique=True
    )

    op.create_table(
        "device_groups",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "organization_id",
            GUID(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        *_audit_columns(),
        sa.UniqueConstraint("organization_id", "name", name="uq_device_groups_org_name"),
    )
    op.create_index("ix_device_groups_organization_id", "device_groups", ["organization_id"])

    op.create_table(
        "devices",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "organization_id",
            GUID(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "location_id", GUID(), sa.ForeignKey("locations.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column(
            "group_id",
            GUID(),
            sa.ForeignKey("device_groups.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("manufacturer", sa.String(100), nullable=True),
        sa.Column("model", sa.String(100), nullable=True),
        sa.Column("platform", sa.String(50), nullable=True),
        sa.Column("os_version", sa.String(50), nullable=True),
        sa.Column("player_version", sa.String(50), nullable=True),
        sa.Column("serial_no", sa.String(100), nullable=False),
        sa.Column("mac_address", sa.String(50), nullable=True),
        sa.Column("ip_address", sa.String(50), nullable=True),
        sa.Column("orientation", sa.String(20), nullable=True),
        sa.Column("screen_width", sa.Integer(), nullable=True),
        sa.Column("screen_height", sa.Integer(), nullable=True),
        sa.Column("timezone", sa.String(64), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=True),
        sa.Column("token_issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_heartbeat_json", JSONType(), nullable=True),
        sa.Column("metadata_json", JSONType(), nullable=True),
        *_audit_columns(),
        sa.UniqueConstraint("organization_id", "serial_no", name="uq_devices_org_serial"),
    )
    op.create_index("ix_devices_organization_id", "devices", ["organization_id"])
    op.create_index("ix_devices_org_status", "devices", ["organization_id", "status"])
    op.create_index("ix_devices_location_id", "devices", ["location_id"])
    op.create_index("ix_devices_group_id", "devices", ["group_id"])
    op.create_index("ix_devices_last_heartbeat_at", "devices", ["last_heartbeat_at"])
    op.create_index("ix_devices_token_hash", "devices", ["token_hash"])

    op.create_table(
        "device_tags",
        sa.Column(
            "device_id", GUID(), sa.ForeignKey("devices.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column(
            "tag_id", GUID(), sa.ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True
        ),
    )

    op.create_table(
        "device_capabilities",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "device_id", GUID(), sa.ForeignKey("devices.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("capability_code", sa.String(100), nullable=False),
        sa.Column("supported", sa.Boolean(), nullable=False),
        sa.Column("value_json", JSONType(), nullable=True),
        sa.UniqueConstraint("device_id", "capability_code", name="uq_device_capabilities_code"),
    )
    op.create_index("ix_device_capabilities_device_id", "device_capabilities", ["device_id"])

    op.create_table(
        "device_commands",
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
        sa.Column("command_type", sa.String(50), nullable=False),
        sa.Column("payload_json", JSONType(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result_json", JSONType(), nullable=True),
        *_audit_columns(),
    )
    op.create_index(
        "ix_device_commands_organization_id", "device_commands", ["organization_id"]
    )
    op.create_index(
        "ix_device_commands_device_status", "device_commands", ["device_id", "status"]
    )

    op.create_table(
        "device_heartbeats",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "device_id", GUID(), sa.ForeignKey("devices.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "observed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("payload_json", JSONType(), nullable=True),
    )
    op.create_index(
        "ix_device_heartbeats_device_observed", "device_heartbeats", ["device_id", "observed_at"]
    )


def downgrade() -> None:
    op.drop_table("device_heartbeats")
    op.drop_table("device_commands")
    op.drop_table("device_capabilities")
    op.drop_table("device_tags")
    op.drop_table("devices")
    op.drop_table("device_groups")
    op.drop_index("uq_organizations_enrollment_key", "organizations")
    op.drop_column("organizations", "enrollment_key")
