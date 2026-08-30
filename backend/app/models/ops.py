import datetime as dt
import enum
import uuid

from sqlalchemy import ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantMixin, UUIDPrimaryKeyMixin
from app.db.types import GUID, JSONType, UTCDateTime


class AuditLog(UUIDPrimaryKeyMixin, TenantMixin, Base):
    """Immutable-style business action history (M16). Generated server-side
    only — never trusted from frontend input (SRS §16)."""

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_org_created", "organization_id", "created_at"),
        Index("ix_audit_logs_entity", "entity_type", "entity_id"),
    )

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(60), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    before_json: Mapped[dict | None] = mapped_column(JSONType(), nullable=True)
    after_json: Mapped[dict | None] = mapped_column(JSONType(), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(50), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), nullable=False
    )


class NotificationSeverity(enum.StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class Notification(UUIDPrimaryKeyMixin, TenantMixin, Base):
    """Operational inbox entry (M15). user_id NULL = org-wide broadcast
    (Phase-1 simplification: broadcasts share one read state)."""

    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_org_created", "organization_id", "created_at"),)

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    type: Mapped[str] = mapped_column(String(60), nullable=False)
    severity: Mapped[str] = mapped_column(
        String(20), nullable=False, default=NotificationSeverity.INFO.value
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    payload_json: Mapped[dict | None] = mapped_column(JSONType(), nullable=True)
    read_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), nullable=False
    )


class DeviceEvent(UUIDPrimaryKeyMixin, Base):
    """Player-reported operational events (FR-PLYR-006, FR-MON-005)."""

    __tablename__ = "device_events"
    __table_args__ = (Index("ix_device_events_device_at", "device_id", "event_at"),)

    device_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    event_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), nullable=False
    )
    payload_json: Mapped[dict | None] = mapped_column(JSONType(), nullable=True)


class PlaybackEvent(UUIDPrimaryKeyMixin, TenantMixin, Base):
    """Proof-of-play foundation (M14, FR-RPT-002)."""

    __tablename__ = "playback_events"
    __table_args__ = (
        Index("ix_playback_events_device_started", "device_id", "started_at"),
        Index("ix_playback_events_campaign_started", "campaign_id", "started_at"),
    )

    device_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False
    )
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    playlist_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    asset_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    started_at: Mapped[dt.datetime] = mapped_column(UTCDateTime(), nullable=False)
    ended_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    result: Mapped[str | None] = mapped_column(String(20), nullable=True)
