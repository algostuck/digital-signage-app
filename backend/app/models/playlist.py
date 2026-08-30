import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import GUID, JSONType, UTCDateTime


class PlaylistStatus(enum.StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class PlaylistItemType(enum.StrEnum):
    ASSET = "asset"
    LAYOUT = "layout"


class Playlist(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """Ordered content sequence (M08). Playlist = WHAT plays; scheduling and
    targeting live elsewhere by design."""

    __tablename__ = "playlists"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=PlaylistStatus.DRAFT.value
    )
    loop_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    fallback_playlist_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("playlists.id", ondelete="SET NULL"), nullable=True
    )
    # Latest published version. No FK: circular playlist<->version dependency;
    # integrity is maintained by the playlist service.
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)

    items: Mapped[list["PlaylistItem"]] = relationship(
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="PlaylistItem.position",
        foreign_keys="PlaylistItem.playlist_id",
    )
    versions: Mapped[list["PlaylistVersion"]] = relationship(
        lazy="selectin", order_by="PlaylistVersion.version_no"
    )


class PlaylistItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Draft item row. Exactly one of asset_id / layout_id is set."""

    __tablename__ = "playlist_items"

    playlist_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("playlists.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    item_type: Mapped[str] = mapped_column(String(20), nullable=False)
    asset_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("assets.id", ondelete="CASCADE"), nullable=True
    )
    layout_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("layouts.id", ondelete="CASCADE"), nullable=True
    )
    # NULL duration = natural media length (videos/audio only).
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    transition_json: Mapped[dict | None] = mapped_column(JSONType(), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class PlaylistVersion(UUIDPrimaryKeyMixin, Base):
    """Immutable published snapshot of the ordered item set (SRS §11)."""

    __tablename__ = "playlist_versions"
    __table_args__ = (
        UniqueConstraint("playlist_id", "version_no", name="uq_playlist_versions_playlist_no"),
    )

    playlist_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("playlists.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    items_json: Mapped[dict] = mapped_column(JSONType(), nullable=False)
    published_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), nullable=False
    )
