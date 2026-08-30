import enum
import uuid

from sqlalchemy import (
    Column,
    Float,
    ForeignKey,
    Index,
    String,
    Table,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import GUID, JSONType


class LocationStatus(enum.StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class LocationType(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """Per-tenant dictionary of node types (Country, City, Store, ...)."""

    __tablename__ = "location_types"
    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_location_types_org_code"),
    )

    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)


location_tags = Table(
    "location_tags",
    Base.metadata,
    Column(
        "location_id", GUID(), ForeignKey("locations.id", ondelete="CASCADE"), primary_key=True
    ),
    Column("tag_id", GUID(), ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class Tag(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """Org-scoped key/value tag, shared by locations (and later devices/assets)."""

    __tablename__ = "tags"
    __table_args__ = (
        UniqueConstraint("organization_id", "key", "value", name="uq_tags_org_key_value"),
    )

    key: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[str] = mapped_column(String(200), nullable=False)


class Location(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """Generic hierarchy node (ADR-003: adjacency list + materialized path).

    `path` is `/<ancestor ids>/<own id>/`, maintained transactionally by the
    location service. Subtree = path LIKE '<node.path>%'.
    """

    __tablename__ = "locations"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "parent_id", "code", name="uq_locations_org_parent_code"
        ),
        Index("ix_locations_org_parent", "organization_id", "parent_id"),
        Index("ix_locations_org_path", "organization_id", "path"),
    )

    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("locations.id", ondelete="RESTRICT"), nullable=True
    )
    type_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("location_types.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    path: Mapped[str] = mapped_column(String(4000), nullable=False)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=LocationStatus.ACTIVE.value
    )
    metadata_json: Mapped[dict | None] = mapped_column(JSONType(), nullable=True)

    type: Mapped[LocationType | None] = relationship(lazy="selectin")
    tags: Mapped[list[Tag]] = relationship(secondary=location_tags, lazy="selectin")

    @property
    def depth(self) -> int:
        return self.path.count("/") - 2

    def ancestor_ids(self) -> list[uuid.UUID]:
        parts = [p for p in self.path.split("/") if p]
        return [uuid.UUID(p) for p in parts[:-1]]
