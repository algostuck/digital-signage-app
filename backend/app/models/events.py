"""Domain event bus (P3-INT-102, slice 3A-1).

`domain_events` is the normalized, append-only stream of BUSINESS facts
("campaign.published", "device.approved" …) — distinct from 2G
notifications, which are user-facing alerts. Downstream consumers attach
via `event_subscriptions`; outbound pushes are recorded in
`event_deliveries`, cloning the proven 2H signed/retry/dead-letter shape.
The stream is retention-pruned (2K engine), never unbounded.
"""

import datetime as dt
import enum
import uuid

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import GUID, JSONType, UTCDateTime


class DomainEvent(UUIDPrimaryKeyMixin, TenantMixin, Base):
    __tablename__ = "domain_events"
    __table_args__ = (
        Index("ix_domain_events_org_type", "organization_id", "event_type"),
        Index("ix_domain_events_org_occurred", "organization_id", "occurred_at"),
    )

    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(60), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    payload_json: Mapped[dict | None] = mapped_column(JSONType(), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    occurred_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), nullable=False
    )


class EventSubscription(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """Event-bus consumer: an HTTPS destination receiving signed pushes of
    selected domain event types (or ["*"])."""

    __tablename__ = "event_subscriptions"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    event_types_json: Mapped[list] = mapped_column(JSONType(), nullable=False)
    # HMAC signing secret; revealed once at create/rotate, never via GET.
    secret: Mapped[str] = mapped_column(String(128), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class EventDeliveryState(enum.StrEnum):
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"  # attempt failed, retry scheduled
    DEAD = "dead"  # retries exhausted; replayable


class EventDelivery(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "event_deliveries"
    __table_args__ = (
        Index("ix_event_deliveries_due", "state", "next_attempt_at"),
    )

    subscription_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("event_subscriptions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("domain_events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSONType(), nullable=False)
    state: Mapped[str] = mapped_column(
        String(20), nullable=False, default=EventDeliveryState.PENDING.value
    )
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    response_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    next_attempt_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    delivered_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime(), nullable=True)
