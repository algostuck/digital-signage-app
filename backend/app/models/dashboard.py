"""Device-health history for the organization dashboard.

Connection status is derived from heartbeat age and never stored, so the
platform had no way to show how a fleet's health moved over time. A beat
sweep writes one row per tenant per hour; the dashboard's trend reads it.
Counts are of the whole fleet at capture time: online + warning + offline
are the active devices, `na` the rest (pending, rejected, decommissioned),
so the four always sum to the device total of that moment.
"""

import datetime as dt

from sqlalchemy import Index, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantMixin, UUIDPrimaryKeyMixin
from app.db.types import UTCDateTime


class DeviceHealthSnapshot(UUIDPrimaryKeyMixin, TenantMixin, Base):
    __tablename__ = "device_health_snapshots"
    __table_args__ = (
        Index("ix_device_health_snapshots_org_captured", "organization_id", "captured_at"),
    )

    captured_at: Mapped[dt.datetime] = mapped_column(UTCDateTime(), nullable=False)
    online: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    warning: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    offline: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    na: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
