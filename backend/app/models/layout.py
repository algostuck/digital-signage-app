import enum
import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import GUID, JSONType, UTCDateTime


class LayoutStatus(enum.StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class Layout(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """Screen composition (M07). The designer edits `draft_canvas_json`;
    publishing snapshots it into an immutable LayoutVersion."""

    __tablename__ = "layouts"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=LayoutStatus.DRAFT.value
    )
    draft_canvas_json: Mapped[dict] = mapped_column(JSONType(), nullable=False)
    # Latest published version. No FK: circular layout<->version dependency;
    # integrity is maintained by the layout service.
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)

    versions: Mapped[list["LayoutVersion"]] = relationship(
        back_populates="layout", lazy="selectin", order_by="LayoutVersion.version_no"
    )


class LayoutVersion(UUIDPrimaryKeyMixin, Base):
    """Immutable published snapshot — exactly what player manifests embed."""

    __tablename__ = "layout_versions"
    __table_args__ = (
        UniqueConstraint("layout_id", "version_no", name="uq_layout_versions_layout_no"),
    )

    layout_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("layouts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    canvas_json: Mapped[dict] = mapped_column(JSONType(), nullable=False)
    published_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), nullable=False
    )

    layout: Mapped[Layout] = relationship(back_populates="versions")
    zones: Mapped[list["LayoutZone"]] = relationship(
        lazy="selectin", cascade="all, delete-orphan", order_by="LayoutZone.zone_key"
    )


class LayoutZone(UUIDPrimaryKeyMixin, Base):
    """Normalized zone row per published version (future content-usage queries)."""

    __tablename__ = "layout_zones"
    __table_args__ = (
        UniqueConstraint("layout_version_id", "zone_key", name="uq_layout_zones_version_key"),
    )

    layout_version_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("layout_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    zone_key: Mapped[str] = mapped_column(String(50), nullable=False)
    zone_json: Mapped[dict] = mapped_column(JSONType(), nullable=False)


class TemplateStatus(enum.StrEnum):
    """Governed lifecycle (P2-CNT-001): drafts are editable; submissions go
    through the approval engine; approval snapshots an immutable version."""

    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class Template(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """Reusable design asset (FR-LYT-008, P2-CNT-001). `canvas_json` is the
    editable draft; approved snapshots live in TemplateVersion. layout_id is
    provenance only."""

    __tablename__ = "templates"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_templates_org_name"),
    )

    layout_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("layouts.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    canvas_json: Mapped[dict] = mapped_column(JSONType(), nullable=False)
    metadata_json: Mapped[dict | None] = mapped_column(JSONType(), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=TemplateStatus.DRAFT.value
    )
    # Latest approved version. No FK: circular template<->version dependency;
    # integrity is maintained by the studio service (same pattern as Layout).
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)

    versions: Mapped[list["TemplateVersion"]] = relationship(
        lazy="selectin", cascade="all, delete-orphan", order_by="TemplateVersion.version_no"
    )


class TemplateVersion(UUIDPrimaryKeyMixin, Base):
    """Immutable approved snapshot of a template canvas."""

    __tablename__ = "template_versions"
    __table_args__ = (
        UniqueConstraint("template_id", "version_no", name="uq_template_versions_no"),
    )

    template_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("templates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    canvas_json: Mapped[dict] = mapped_column(JSONType(), nullable=False)
    published_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), nullable=False
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
