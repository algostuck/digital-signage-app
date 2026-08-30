import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import GUID, UTCDateTime


class AssetType(enum.StrEnum):
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"
    HTML = "html"
    TEXT = "text"
    DATA = "data"
    OTHER = "other"


class AssetStatus(enum.StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class ProcessingStatus(enum.StrEnum):
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class UploadSessionStatus(enum.StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"


class Folder(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "folders"
    __table_args__ = (
        UniqueConstraint("organization_id", "parent_id", "name", name="uq_folders_org_parent_name"),
    )

    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("folders.id", ondelete="RESTRICT"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")


asset_tags = Table(
    "asset_tags",
    Base.metadata,
    Column("asset_id", GUID(), ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", GUID(), ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class Asset(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "assets"
    __table_args__ = (
        Index("ix_assets_org_type_status", "organization_id", "type", "status"),
        Index("ix_assets_checksum", "checksum"),
        Index("ix_assets_folder_id", "folder_id"),
    )

    folder_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("folders.id", ondelete="SET NULL"), nullable=True
    )
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=AssetStatus.DRAFT.value)
    checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Latest READY version. Intentionally no FK: circular asset<->version
    # dependency; integrity is maintained by the content service.
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)

    versions: Mapped[list["AssetVersion"]] = relationship(
        back_populates="asset", lazy="selectin", order_by="AssetVersion.version_no"
    )
    tags = relationship("Tag", secondary=asset_tags, lazy="selectin")


class AssetVersion(UUIDPrimaryKeyMixin, Base):
    """Immutable uploaded file version with its processing state (M06)."""

    __tablename__ = "asset_versions"
    __table_args__ = (
        UniqueConstraint("asset_id", "version_no", name="uq_asset_versions_asset_no"),
    )

    asset_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    object_key: Mapped[str] = mapped_column(String(1000), nullable=False)
    thumbnail_key: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(200), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    processing_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ProcessingStatus.PROCESSING.value
    )
    processing_error: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), nullable=False
    )

    asset: Mapped[Asset] = relationship(back_populates="versions")


class UploadSession(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """Server-created upload intent: policy-validated before any bytes move."""

    __tablename__ = "upload_sessions"

    asset_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)
    is_new_asset: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    folder_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    asset_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(200), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    object_key: Mapped[str] = mapped_column(String(1000), nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=UploadSessionStatus.PENDING.value
    )
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
