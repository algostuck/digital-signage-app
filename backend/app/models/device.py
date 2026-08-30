import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import GUID, JSONType, UTCDateTime  # noqa: F401 (UTCDateTime used below)


class DeviceStatus(enum.StrEnum):
    """Lifecycle state (FR-DEV-001/002/007). Online/offline is derived from
    last_heartbeat_at at read time, never stored."""

    PENDING = "pending"
    ACTIVE = "active"
    REJECTED = "rejected"
    DECOMMISSIONED = "decommissioned"


class CommandStatus(enum.StrEnum):
    QUEUED = "queued"
    SENT = "sent"
    ACKNOWLEDGED = "acknowledged"
    FAILED = "failed"
    CANCELLED = "cancelled"


device_tags = Table(
    "device_tags",
    Base.metadata,
    Column("device_id", GUID(), ForeignKey("devices.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", GUID(), ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class DeviceGroupType(enum.StrEnum):
    STATIC = "static"
    DYNAMIC = "dynamic"


class DeviceGroup(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """Static membership via devices.group_id; dynamic membership evaluated
    from rule_json at read/publish time (P2-DEV-001)."""

    __tablename__ = "device_groups"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_device_groups_org_name"),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    group_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default=DeviceGroupType.STATIC.value
    )
    rule_json: Mapped[dict | None] = mapped_column(JSONType(), nullable=True)


class Screenshot(UUIDPrimaryKeyMixin, TenantMixin, Base):
    """Device display evidence (P2-MON-003). Binary lives in object storage."""

    __tablename__ = "screenshots"
    __table_args__ = (Index("ix_screenshots_device_captured", "device_id", "captured_at"),)

    device_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False
    )
    object_key: Mapped[str] = mapped_column(String(1000), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(50), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), nullable=False
    )


class IncidentState(enum.StrEnum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class Incident(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """Operational incident with acknowledgement + auto-recovery (P2-MON-004)."""

    __tablename__ = "incidents"
    __table_args__ = (Index("ix_incidents_org_state", "organization_id", "state"),)

    device_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("devices.id", ondelete="CASCADE"), nullable=True, index=True
    )
    type: Mapped[str] = mapped_column(String(60), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="warning")
    state: Mapped[str] = mapped_column(
        String(20), nullable=False, default=IncidentState.OPEN.value
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    opened_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), nullable=False
    )
    acknowledged_by: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    resolution: Mapped[str | None] = mapped_column(String(200), nullable=True)
    payload_json: Mapped[dict | None] = mapped_column(JSONType(), nullable=True)


class Device(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "devices"
    __table_args__ = (
        UniqueConstraint("organization_id", "serial_no", name="uq_devices_org_serial"),
        Index("ix_devices_org_status", "organization_id", "status"),
        Index("ix_devices_last_heartbeat_at", "last_heartbeat_at"),
    )

    location_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("locations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    group_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("device_groups.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    manufacturer: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    platform: Mapped[str | None] = mapped_column(String(50), nullable=True)
    os_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    player_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    serial_no: Mapped[str] = mapped_column(String(100), nullable=False)
    mac_address: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(50), nullable=True)
    orientation: Mapped[str | None] = mapped_column(String(20), nullable=True)
    screen_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    screen_height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=DeviceStatus.PENDING.value
    )
    # Opaque device credential: only the SHA-256 digest is stored, and it is
    # independently revocable (reset-token) per SRS §16.
    token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    token_issued_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime(), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime(), nullable=True
    )
    last_heartbeat_json: Mapped[dict | None] = mapped_column(JSONType(), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONType(), nullable=True)

    group: Mapped[DeviceGroup | None] = relationship(lazy="selectin")
    tags = relationship("Tag", secondary=device_tags, lazy="selectin")
    capabilities: Mapped[list["DeviceCapability"]] = relationship(
        lazy="selectin", cascade="all, delete-orphan", order_by="DeviceCapability.capability_code"
    )


class DeviceCapability(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "device_capabilities"
    __table_args__ = (
        UniqueConstraint("device_id", "capability_code", name="uq_device_capabilities_code"),
    )

    device_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    capability_code: Mapped[str] = mapped_column(String(100), nullable=False)
    supported: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    value_json: Mapped[dict | None] = mapped_column(JSONType(), nullable=True)


class DeviceCommand(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """Remote command queue (FR-DEV-008), capability-driven, vendor-neutral."""

    __tablename__ = "device_commands"
    __table_args__ = (Index("ix_device_commands_device_status", "device_id", "status"),)

    device_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False
    )
    command_type: Mapped[str] = mapped_column(String(50), nullable=False)
    payload_json: Mapped[dict | None] = mapped_column(JSONType(), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=CommandStatus.QUEUED.value
    )
    sent_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime(), nullable=True
    )
    result_json: Mapped[dict | None] = mapped_column(JSONType(), nullable=True)


class DeviceHeartbeat(UUIDPrimaryKeyMixin, Base):
    """Append-only heartbeat history (retention-managed later, NFR-013)."""

    __tablename__ = "device_heartbeats"
    __table_args__ = (Index("ix_device_heartbeats_device_observed", "device_id", "observed_at"),)

    device_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False
    )
    observed_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), nullable=False
    )
    payload_json: Mapped[dict | None] = mapped_column(JSONType(), nullable=True)
