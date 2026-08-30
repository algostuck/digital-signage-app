"""Ad monetization models (P3-M05, slice 3D-1).

Inventory describes sellable screen time (a device or location slot with
operating hours); bookings sell units of it to an advertiser against an
EXISTING campaign (creatives/delivery ride 1I unchanged — SRS keeps payment
settlement external). `ad_playback_links` join bookings to 2I proof-of-play
events one-to-one — the billing-ready, independently reconcilable record.
"""

import datetime as dt
import enum
import uuid

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import GUID, JSONType, UTCDateTime


class AdSlotType(enum.StrEnum):
    FULLSCREEN = "fullscreen"
    ZONE = "zone"


class AdBookingStatus(enum.StrEnum):
    PENDING = "pending"  # awaiting approval (2A adapter)
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class AdInventory(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "ad_inventory"
    __table_args__ = (
        Index("uq_ad_inventory_org_name", "organization_id", "name", unique=True),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    location_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("locations.id", ondelete="SET NULL"), nullable=True
    )
    device_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("devices.id", ondelete="SET NULL"), nullable=True
    )
    zone_ref: Mapped[str | None] = mapped_column(String(50), nullable=True)
    slot_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default=AdSlotType.FULLSCREEN.value
    )
    # {"start": "09:00", "end": "21:00", "days": [1..7]}
    operating_hours_json: Mapped[dict] = mapped_column(
        JSONType(), nullable=False, default=dict
    )
    rate_card_ref: Mapped[str | None] = mapped_column(String(100), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    bookings: Mapped[list["AdBooking"]] = relationship(
        lazy="selectin", cascade="all, delete-orphan"
    )


class AdBooking(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "ad_bookings"
    __table_args__ = (
        Index("ix_ad_bookings_org_status", "organization_id", "status"),
    )

    inventory_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("ad_inventory.id", ondelete="CASCADE"), nullable=False, index=True
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    advertiser_ref: Mapped[str] = mapped_column(String(200), nullable=False)
    booked_units: Mapped[int] = mapped_column(Integer, nullable=False)  # plays
    start_at: Mapped[dt.datetime] = mapped_column(UTCDateTime(), nullable=False)
    end_at: Mapped[dt.datetime] = mapped_column(UTCDateTime(), nullable=False)
    # {"max_per_hour": n} — delivery pacing hint (advisory in this slice).
    frequency_json: Mapped[dict | None] = mapped_column(JSONType(), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=AdBookingStatus.PENDING.value
    )

    links: Mapped[list["AdPlaybackLink"]] = relationship(
        lazy="selectin", cascade="all, delete-orphan"
    )


class AdPlaybackLink(UUIDPrimaryKeyMixin, Base):
    """One proof-of-play event credited to one booking (billing-ready)."""

    __tablename__ = "ad_playback_links"
    __table_args__ = (
        UniqueConstraint("playback_event_id", name="uq_ad_playback_links_event"),
    )

    booking_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("ad_bookings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    playback_event_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("playback_events.id", ondelete="CASCADE"), nullable=False
    )
    billable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    evidence_json: Mapped[dict | None] = mapped_column(JSONType(), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), nullable=False
    )
