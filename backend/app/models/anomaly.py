"""Fleet intelligence models (P3-M07, slice 3D-3).

Deterministic first (AI architecture §5): anomalies are explainable
statistics over EXISTING telemetry — every score carries `evidence_json`
pointing at the exact signals behind it, recommendations never
auto-execute, and remediation is limited to a whitelisted command set with
a full action trail (P3-OPS-003).
"""

import datetime as dt
import enum
import uuid

from sqlalchemy import Boolean, ForeignKey, Index, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import GUID, JSONType, UTCDateTime


class AnomalySignal(enum.StrEnum):
    HEARTBEAT_GAPS = "heartbeat_gaps"
    PLAYBACK_FAILURES = "playback_failures"
    ERROR_EVENTS = "error_events"


class AnomalyState(enum.StrEnum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class AnomalyRule(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "anomaly_rules"
    __table_args__ = (
        Index("uq_anomaly_rules_org_name", "organization_id", "name", unique=True),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    signal_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # Per signal: heartbeat_gaps {gap_minutes, max_gaps};
    # playback_failures {min_events, max_failure_pct};
    # error_events {max_count}.
    threshold_json: Mapped[dict] = mapped_column(JSONType(), nullable=False)
    window_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=24)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="warning")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Anomaly(UUIDPrimaryKeyMixin, TenantMixin, Base):
    __tablename__ = "anomalies"
    __table_args__ = (
        Index("ix_anomalies_org_state", "organization_id", "state"),
        Index("ix_anomalies_device", "device_id", "state"),
    )

    device_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False
    )
    rule_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("anomaly_rules.id", ondelete="SET NULL"), nullable=True
    )
    # score >= 1.0 means the threshold is exceeded; magnitude = how badly.
    score: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    state: Mapped[str] = mapped_column(
        String(20), nullable=False, default=AnomalyState.OPEN.value
    )
    evidence_json: Mapped[dict] = mapped_column(JSONType(), nullable=False)
    recommendation: Mapped[str | None] = mapped_column(String(500), nullable=True)
    opened_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), nullable=False
    )
    resolved_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class AnomalyAction(UUIDPrimaryKeyMixin, Base):
    """Human-in-the-loop trail: ack, resolve, whitelisted remediation."""

    __tablename__ = "anomaly_actions"

    anomaly_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("anomalies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    outcome: Mapped[str | None] = mapped_column(String(200), nullable=True)
    executed_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), nullable=False
    )
