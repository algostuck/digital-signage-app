import datetime as dt
import enum
import uuid

from sqlalchemy import Boolean, Date, ForeignKey, Index, Integer, String, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import GUID, JSONType, UTCDateTime


class CampaignStatus(enum.StrEnum):
    """Full lifecycle (FR-CMP-001); 1H uses draft/archived, the approval and
    publish transitions are wired in milestone 1I."""

    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    PUBLISHED = "published"
    PAUSED = "paused"
    EXPIRED = "expired"
    ARCHIVED = "archived"


class Campaign(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """Campaign = content package + schedule + target + priority (M09)."""

    __tablename__ = "campaigns"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=CampaignStatus.DRAFT.value
    )
    # 1..100; higher wins at playback resolution (SRS §13).
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    playlist_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("playlists.id", ondelete="SET NULL"), nullable=True
    )
    layout_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("layouts.id", ondelete="SET NULL"), nullable=True
    )

    schedules: Mapped[list["Schedule"]] = relationship(
        lazy="selectin", cascade="all, delete-orphan", order_by="Schedule.created_at"
    )
    targets: Mapped[list["CampaignTarget"]] = relationship(
        lazy="selectin", cascade="all, delete-orphan", order_by="CampaignTarget.created_at"
    )
    variants: Mapped[list["CampaignVariant"]] = relationship(
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="CampaignVariant.priority.desc()",
    )


class CampaignVariant(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Audience-specific creative override (P2-CAM-001). The base campaign's
    layout/playlist is the default; the highest-priority variant whose
    targets match the device wins. Variants never change WHO receives the
    campaign — only WHAT a matching device renders."""

    __tablename__ = "campaign_variants"
    __table_args__ = (
        UniqueConstraint("campaign_id", "name", name="uq_campaign_variants_name"),
    )

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    layout_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("layouts.id", ondelete="SET NULL"), nullable=True
    )
    playlist_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("playlists.id", ondelete="SET NULL"), nullable=True
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=50)

    targets: Mapped[list["CampaignVariantTarget"]] = relationship(
        lazy="selectin", cascade="all, delete-orphan"
    )


class CampaignVariantTarget(UUIDPrimaryKeyMixin, Base):
    """Same vocabulary as CampaignTarget (location/device/group/tag) so the
    resolution engine is shared; variants have no exclusions."""

    __tablename__ = "campaign_variant_targets"
    __table_args__ = (
        UniqueConstraint(
            "variant_id", "target_type", "target_id", name="uq_campaign_variant_targets"
        ),
    )

    variant_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("campaign_variants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_type: Mapped[str] = mapped_column(String(20), nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)
    include_descendants: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_exclusion = False  # duck-typing for the shared target resolver


class ScheduleKind(enum.StrEnum):
    PLAY = "play"
    BLACKOUT = "blackout"  # suppresses the campaign while active (P2-CAM-004)


class Schedule(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """Timezone-aware recurrence window (M10, P2-SCH-002).

    Semantics: active on dates [start_date, end_date] (NULL = open-ended),
    on the listed weekdays (NULL = every day; 0=Monday..6=Sunday), further
    narrowed by recurrence_json {"days_of_month": [1..31]} when present,
    skipping exception_dates_json (ISO dates), within the daily wall-clock
    window [start_time, end_time) evaluated in `timezone` (NULL = inherit
    device -> location -> organization). An end_time earlier than start_time
    wraps past midnight. kind='blackout' windows suppress the campaign
    instead of playing it.
    """

    __tablename__ = "schedules"

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    kind: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ScheduleKind.PLAY.value
    )
    start_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    start_time: Mapped[dt.time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[dt.time | None] = mapped_column(Time, nullable=True)
    days_of_week: Mapped[list | None] = mapped_column(JSONType(), nullable=True)
    recurrence_json: Mapped[dict | None] = mapped_column(JSONType(), nullable=True)
    exception_dates_json: Mapped[list | None] = mapped_column(JSONType(), nullable=True)
    timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=50)


class TargetType(enum.StrEnum):
    LOCATION = "location"
    DEVICE = "device"
    GROUP = "group"
    TAG = "tag"


class CampaignTarget(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Logical target definition (FR-CMP-004, SRS §12). Exclusions always win
    over inclusions for the same evaluation."""

    __tablename__ = "campaign_targets"
    __table_args__ = (
        Index("ix_campaign_targets_lookup", "campaign_id", "target_type", "target_id"),
    )

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False
    )
    target_type: Mapped[str] = mapped_column(String(20), nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)
    include_descendants: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_exclusion: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    conditions_json: Mapped[dict | None] = mapped_column(JSONType(), nullable=True)


class DeploymentStatus(enum.StrEnum):
    QUEUED = "queued"
    PUBLISHING = "publishing"
    PARTIAL = "partial"
    PUBLISHED = "published"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DeploymentDeviceStatus(enum.StrEnum):
    PENDING = "pending"
    ACKNOWLEDGED = "acknowledged"
    FAILED = "failed"


class Deployment(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """Publish job with a frozen target snapshot (M11, ADR-005). The snapshot
    never silently changes after publication (SRS §12)."""

    __tablename__ = "deployments"
    __table_args__ = (
        Index("ix_deployments_org_created", "organization_id", "created_at"),
        Index("ix_deployments_status", "status"),
    )

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=DeploymentStatus.QUEUED.value
    )
    target_snapshot_json: Mapped[dict | None] = mapped_column(JSONType(), nullable=True)
    error: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    started_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    completed_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    devices: Mapped[list["DeploymentDevice"]] = relationship(
        lazy="selectin", cascade="all, delete-orphan"
    )


class DeploymentDevice(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "deployment_devices"
    __table_args__ = (
        UniqueConstraint("deployment_id", "device_id", name="uq_deployment_devices"),
    )

    deployment_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("deployments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    device_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=DeploymentDeviceStatus.PENDING.value
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    acknowledged_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime(), nullable=True)
