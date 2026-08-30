"""Video wall models (P3-M04, slice 3C-1).

A wall is a logical canvas spanning member devices; each member renders a
viewport (crop) of the shared canvas. Sync sessions hand every member the
same session id + epoch start marker + clock tolerance via the manifest
`sync` block (contract v2, additive) — the platform never streams frames;
players discipline their own clocks against the marker (pull model,
ADR-005 unchanged).
"""

import datetime as dt
import enum
import uuid

from sqlalchemy import BigInteger, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import GUID, JSONType, UTCDateTime


class VideoWallStatus(enum.StrEnum):
    IDLE = "idle"
    SYNCING = "syncing"
    DEGRADED = "degraded"  # session active but members unhealthy
    ARCHIVED = "archived"


class VideoWall(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "video_walls"
    __table_args__ = (
        Index("uq_video_walls_org_name", "organization_id", "name", unique=True),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # {"width": px, "height": px, "rows": n, "cols": n}
    canvas_json: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    # {"tolerance_ms": 50, "start_delay_ms": 5000}
    sync_policy_json: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=VideoWallStatus.IDLE.value
    )
    # Active sync session (None when idle).
    session_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    session_started_at: Mapped[dt.datetime | None] = mapped_column(
        UTCDateTime(), nullable=True
    )
    session_epoch_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    members: Mapped[list["VideoWallMember"]] = relationship(
        lazy="selectin", cascade="all, delete-orphan", order_by="VideoWallMember.created_at"
    )


class VideoWallMember(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "video_wall_members"
    __table_args__ = (
        UniqueConstraint("wall_id", "device_id", name="uq_video_wall_members_device"),
    )

    wall_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("video_walls.id", ondelete="CASCADE"), nullable=False, index=True
    )
    device_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # {"x": px, "y": px, "width": px, "height": px}
    viewport_json: Mapped[dict] = mapped_column(JSONType(), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="member")
    created_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), nullable=False
    )
