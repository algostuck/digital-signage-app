"""Analytics platform models (P3-M11, slice 3D-2).

`analytics_aggregates` is the daily-grain read layer (SRS §7): dashboards
and reports read here, never raw event tables at scale. Rows are
idempotently recomputable from raw truth, so a re-run heals late events.
`data_exports` are scheduled dataset dumps rendered by the 2I engine and
written to the storage adapter — the hand-off point to a customer's own
warehouse (no warehouse engine in this phase, by design).
"""

import datetime as dt
import enum
import uuid

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import GUID, JSONType, UTCDateTime


class AnalyticsAggregate(UUIDPrimaryKeyMixin, TenantMixin, Base):
    __tablename__ = "analytics_aggregates"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "grain_date", "dimension_type", "dimension_id",
            name="uq_analytics_aggregates_dim",
        ),
        Index("ix_analytics_aggregates_org_date", "organization_id", "grain_date"),
    )

    grain_date: Mapped[dt.date] = mapped_column(nullable=False)
    dimension_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # NULL dimension_id = org-level totals row.
    dimension_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    metrics_json: Mapped[dict] = mapped_column(JSONType(), nullable=False)
    computed_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), nullable=False
    )


class DataExportState(enum.StrEnum):
    IDLE = "idle"
    RUNNING = "running"
    ERROR = "error"


class DataExport(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "data_exports"
    __table_args__ = (
        Index("uq_data_exports_org_name", "organization_id", "name", unique=True),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    dataset: Mapped[str] = mapped_column(String(50), nullable=False)
    # "storage" = the platform storage adapter (S3/local); external
    # destinations become adapter swaps later.
    destination: Mapped[str] = mapped_column(String(30), nullable=False, default="storage")
    # {"cadence": "daily"} — window is always the previous full day.
    schedule_json: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    state: Mapped[str] = mapped_column(
        String(20), nullable=False, default=DataExportState.IDLE.value
    )
    last_run_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    last_object_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
