"""Phase-3 slice 3D-1: ad monetization — inventory, bookings and
billing-ready proof-of-play linkage.

Revision ID: 0030
Revises: 0029
Create Date: 2026-08-30
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.db.types import GUID, JSONType

revision: str = "0030"
down_revision: str | None = "0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ad_inventory",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "organization_id",
            GUID(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column(
            "location_id",
            GUID(),
            sa.ForeignKey("locations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "device_id", GUID(), sa.ForeignKey("devices.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("zone_ref", sa.String(50), nullable=True),
        sa.Column("slot_type", sa.String(20), nullable=False),
        sa.Column("operating_hours_json", JSONType(), nullable=False),
        sa.Column("rate_card_ref", sa.String(100), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_ad_inventory_organization_id", "ad_inventory", ["organization_id"])
    op.create_index(
        "uq_ad_inventory_org_name", "ad_inventory", ["organization_id", "name"], unique=True
    )

    op.create_table(
        "ad_bookings",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "organization_id",
            GUID(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "inventory_id",
            GUID(),
            sa.ForeignKey("ad_inventory.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "campaign_id",
            GUID(),
            sa.ForeignKey("campaigns.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("advertiser_ref", sa.String(200), nullable=False),
        sa.Column("booked_units", sa.Integer(), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("frequency_json", JSONType(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_ad_bookings_organization_id", "ad_bookings", ["organization_id"])
    op.create_index("ix_ad_bookings_inventory_id", "ad_bookings", ["inventory_id"])
    op.create_index("ix_ad_bookings_campaign_id", "ad_bookings", ["campaign_id"])
    op.create_index("ix_ad_bookings_org_status", "ad_bookings", ["organization_id", "status"])

    op.create_table(
        "ad_playback_links",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "booking_id",
            GUID(),
            sa.ForeignKey("ad_bookings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "playback_event_id",
            GUID(),
            sa.ForeignKey("playback_events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("billable", sa.Boolean(), nullable=False),
        sa.Column("evidence_json", JSONType(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("playback_event_id", name="uq_ad_playback_links_event"),
    )
    op.create_index("ix_ad_playback_links_booking_id", "ad_playback_links", ["booking_id"])


def downgrade() -> None:
    op.drop_table("ad_playback_links")
    op.drop_table("ad_bookings")
    op.drop_table("ad_inventory")
