"""Developer platform metadata (P3-M12 / P3-INT-103, slice 3A-3).

Platform-scoped (no organization_id, like plans): the catalogue of
published API products and their versioned contracts with lifecycle +
deprecation policy and a structured changelog. The interactive docs remain
FastAPI's own OpenAPI; this catalogue is the versioning/deprecation layer
partners rely on.
"""

import datetime as dt
import enum
import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import GUID, JSONType, UTCDateTime


class ApiVersionLifecycle(enum.StrEnum):
    PREVIEW = "preview"
    CURRENT = "current"
    DEPRECATED = "deprecated"
    SUNSET = "sunset"


class ApiProduct(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "api_products"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)

    versions: Mapped[list["ApiVersion"]] = relationship(
        lazy="selectin", cascade="all, delete-orphan", order_by="ApiVersion.version"
    )


class ApiVersion(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "api_versions"
    __table_args__ = (
        UniqueConstraint("product_id", "version", name="uq_api_versions_version"),
    )

    product_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("api_products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    lifecycle_state: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ApiVersionLifecycle.CURRENT.value
    )
    sunset_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    # [{"date": "2026-08-30", "note": "..."}], newest last.
    changelog_json: Mapped[list | None] = mapped_column(JSONType(), nullable=True)
    released_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), nullable=False
    )
