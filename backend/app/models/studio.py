"""Content studio models (P2-M02): widget framework and asset collections.

Widgets are org-scoped catalogue entries with schema-driven configuration
(P2-CNT-003). The schema uses a deliberately small field-list format —
`{"fields": [{key, label, type, required, options?, default?}]}` — which
both the server validator and the frontend form renderer consume; a full
JSON-Schema engine is out of scope and documented as a deviation.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import GUID, JSONType, UTCDateTime


class WidgetStatus(enum.StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class Widget(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "widgets"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_widgets_org_name"),
    )

    type: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=WidgetStatus.ACTIVE.value
    )
    # Shown when the widget's data source is unavailable (P2-CNT-003).
    fallback_json: Mapped[dict | None] = mapped_column(JSONType(), nullable=True)

    versions: Mapped[list["WidgetVersion"]] = relationship(
        lazy="selectin", cascade="all, delete-orphan", order_by="WidgetVersion.version_no"
    )


class WidgetVersion(UUIDPrimaryKeyMixin, Base):
    """Immutable configuration contract for one widget version."""

    __tablename__ = "widget_versions"
    __table_args__ = (
        UniqueConstraint("widget_id", "version_no", name="uq_widget_versions_no"),
    )

    widget_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("widgets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    config_schema_json: Mapped[dict] = mapped_column(JSONType(), nullable=False)
    defaults_json: Mapped[dict | None] = mapped_column(JSONType(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), nullable=False
    )


class AssetCollection(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """Reusable ordered set of assets for campaigns/playlists (P2-CNT-004)."""

    __tablename__ = "asset_collections"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_asset_collections_org_name"),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    items: Mapped[list["AssetCollectionItem"]] = relationship(
        lazy="selectin", cascade="all, delete-orphan", order_by="AssetCollectionItem.position"
    )


class AssetCollectionItem(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "asset_collection_items"
    __table_args__ = (
        UniqueConstraint("collection_id", "asset_id", name="uq_asset_collection_items_asset"),
    )

    collection_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("asset_collections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
