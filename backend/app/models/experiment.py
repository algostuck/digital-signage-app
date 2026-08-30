"""Experimentation models (P3-DEC-003, slice 3B-3).

An experiment A/B-tests a campaign's 2E variants: each variant gets an
allocation percentage (the remainder plays the base/control creative).
Assignment is a STABLE hash of (experiment_id, device_id) — a device always
sees the same arm, assignments are persisted as evidence, and stopping the
experiment reverts every device to normal variant resolution.
"""

import datetime as dt
import enum
import uuid

from sqlalchemy import ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import GUID, UTCDateTime


class ExperimentStatus(enum.StrEnum):
    DRAFT = "draft"
    RUNNING = "running"
    COMPLETED = "completed"


class Experiment(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "experiments"
    __table_args__ = (
        Index("uq_experiments_org_name", "organization_id", "name", unique=True),
    )

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ExperimentStatus.DRAFT.value
    )
    start_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    end_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    variants: Mapped[list["ExperimentVariant"]] = relationship(
        lazy="selectin", cascade="all, delete-orphan", order_by="ExperimentVariant.created_at"
    )


class ExperimentVariant(UUIDPrimaryKeyMixin, Base):
    """One arm: a 2E campaign variant with its traffic share. The base
    campaign creative is the implicit control arm (100 - sum(allocations))."""

    __tablename__ = "experiment_variants"
    __table_args__ = (
        UniqueConstraint("experiment_id", "variant_id", name="uq_experiment_variants_ref"),
    )

    experiment_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    variant_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("campaign_variants.id", ondelete="CASCADE"), nullable=False
    )
    allocation_pct: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), nullable=False
    )


class ExperimentAssignment(UUIDPrimaryKeyMixin, Base):
    """Persisted evidence of which arm a device saw (stable + auditable)."""

    __tablename__ = "experiment_assignments"
    __table_args__ = (
        UniqueConstraint("experiment_id", "device_id", name="uq_experiment_assignments"),
    )

    experiment_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    device_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # NULL = control arm (base campaign creative).
    variant_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("campaign_variants.id", ondelete="CASCADE"), nullable=True
    )
    assigned_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), nullable=False
    )
