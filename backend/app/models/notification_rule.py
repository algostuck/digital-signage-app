"""Notification rules + delivery evidence (P2-M08).

A rule maps an event type (a notification `type`, or `*`) plus an optional
severity condition to one or more delivery channels. Every firing leaves a
delivery row as evidence — including the implicit in-app channel — so the
Notification Rules screen can show exactly what went where.
"""

import datetime as dt
import enum
import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import GUID, JSONType, UTCDateTime


class DeliveryChannel(enum.StrEnum):
    IN_APP = "in_app"
    EMAIL = "email"
    WEBHOOK = "webhook"


class DeliveryState(enum.StrEnum):
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"


class NotificationRule(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "notification_rules"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_notification_rules_org_name"),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # A notification type (DEVICE_OFFLINE, ROLLOUT_STOPPED, ...) or "*".
    event_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    # {"severity": ["warning", "critical"]} — absent = any severity.
    condition_json: Mapped[dict | None] = mapped_column(JSONType(), nullable=True)
    # [{"channel": "email", "recipient": "noc@corp.com"}, ...]
    channels_json: Mapped[list] = mapped_column(JSONType(), nullable=False)
    # Critical-alert escalation delay (P2-NTF-002); NULL = never escalate.
    escalation_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class NotificationDelivery(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "notification_deliveries"

    rule_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("notification_rules.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    notification_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("notifications.id", ondelete="CASCADE"), nullable=False
    )
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    recipient: Mapped[str] = mapped_column(String(500), nullable=False)
    state: Mapped[str] = mapped_column(
        String(20), nullable=False, default=DeliveryState.PENDING.value, index=True
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    delivered_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime(), nullable=True)
