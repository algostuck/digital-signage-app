"""OTA player update models (P2-DEV-004/005): release registry, staged
rollout rings and per-device rollout state. Manufacturer-neutral — a package
is just a published asset; applicability is expressed through the targeted
device group (e.g. a dynamic platform rule), never vendor branches."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import GUID, UTCDateTime


class ReleaseState(enum.StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    ROLLED_BACK = "rolled_back"


class RolloutBatchState(enum.StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    STOPPED = "stopped"


class RolloutDeviceState(enum.StrEnum):
    PENDING = "pending"
    UPDATING = "updating"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class PlayerRelease(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "player_releases"
    __table_args__ = (
        UniqueConstraint("organization_id", "version", name="uq_player_releases_org_version"),
    )

    version: Mapped[str] = mapped_column(String(50), nullable=False)
    package_asset_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("assets.id", ondelete="RESTRICT"), nullable=False
    )
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    state: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ReleaseState.DRAFT.value
    )


class RolloutBatch(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """One ring of a staged rollout. `percentage` is the cumulative share of
    the target fleet covered once this ring completes (e.g. 10 -> 50 -> 100)."""

    __tablename__ = "rollout_batches"
    __table_args__ = (
        UniqueConstraint("release_id", "ring_no", name="uq_rollout_batches_release_ring"),
    )

    release_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("player_releases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ring_no: Mapped[int] = mapped_column(Integer, nullable=False)
    percentage: Mapped[int] = mapped_column(Integer, nullable=False)
    failure_threshold_pct: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    state: Mapped[str] = mapped_column(
        String(20), nullable=False, default=RolloutBatchState.PENDING.value, index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class RolloutDevice(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "rollout_devices"
    __table_args__ = (
        UniqueConstraint("batch_id", "device_id", name="uq_rollout_devices_batch_device"),
        Index("ix_rollout_devices_device_state", "device_id", "state"),
    )

    batch_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("rollout_batches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    device_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False
    )
    state: Mapped[str] = mapped_column(
        String(20), nullable=False, default=RolloutDeviceState.PENDING.value
    )
    failure_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
