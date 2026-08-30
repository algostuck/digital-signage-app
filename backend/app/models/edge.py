"""Edge bundle models (P3-M06, slice 3C-2).

A bundle is a SIGNED prefetch manifest — asset descriptors (checksums,
sizes, signed URLs are minted at serve time) plus validity metadata — never
copies of binaries (asset bytes stay in object storage). Devices covered by
a published bundle receive contract-v2 `bundle`/`prefetch`/`bandwidth`
blocks and pull ahead of need; the ladder is: live manifest → valid
unexpired bundle → cached prior manifest.
"""

import datetime as dt
import enum
import uuid

from sqlalchemy import ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import GUID, JSONType, UTCDateTime


class EdgeBundleState(enum.StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    EXPIRED = "expired"


class EdgeBundle(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "edge_bundles"
    __table_args__ = (
        Index("ix_edge_bundles_org_state", "organization_id", "state"),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    bundle_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # Optional scope: a device group; NULL = every active device.
    group_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("device_groups.id", ondelete="SET NULL"), nullable=True
    )
    # {"assets": [{id, name, sha256, size, mime_type}], "generated_at": iso}
    manifest_json: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    signature: Mapped[str | None] = mapped_column(String(64), nullable=True)
    expires_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    state: Mapped[str] = mapped_column(
        String(20), nullable=False, default=EdgeBundleState.DRAFT.value
    )

    devices: Mapped[list["EdgeBundleDevice"]] = relationship(
        lazy="selectin", cascade="all, delete-orphan"
    )


class EdgeBundleDevice(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "edge_bundle_devices"
    __table_args__ = (
        UniqueConstraint("bundle_id", "device_id", name="uq_edge_bundle_devices"),
    )

    bundle_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("edge_bundles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    device_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    state: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    synced_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), nullable=False
    )
