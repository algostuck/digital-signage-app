"""Dynamic data sources (P3-M02, slice 3A-2).

A data source is a guarded external feed (REST/JSON or RSS/Atom) whose
fetched payloads are validated against a declared schema and stored as
bounded snapshots. Widgets bind to a source (zone.widget.data_binding) and
the manifest ships the latest VALID snapshot — devices never fetch external
feeds themselves, and a downed source degrades to last-known-good, then to
the widget's fallback (P3-DAT-004/005).

Secrets: the source stores only `auth_token_ref` — the NAME of a server
environment variable resolved at fetch time. No credential ever lands in
the database or any API response.
"""

import datetime as dt
import enum
import uuid

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import GUID, JSONType, UTCDateTime


class DataSourceType(enum.StrEnum):
    REST_JSON = "rest_json"
    RSS = "rss"


class DataSourceState(enum.StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    ERROR = "error"  # last fetch failed; serving last-known-good


class DataSource(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "data_sources"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_data_sources_org_name"),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(1000), nullable=False)
    # Optional bearer/header auth: header name + env-var NAME (never a value).
    auth_header: Mapped[str | None] = mapped_column(String(100), nullable=True)
    auth_token_ref: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cache_ttl_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=300)
    refresh_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=900)
    state: Mapped[str] = mapped_column(
        String(20), nullable=False, default=DataSourceState.ACTIVE.value
    )
    last_ok_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)

    schemas: Mapped[list["DataSourceSchema"]] = relationship(
        lazy="selectin", cascade="all, delete-orphan", order_by="DataSourceSchema.version_no"
    )


class DataSourceSchema(UUIDPrimaryKeyMixin, Base):
    """Versioned declared shape (P3-DAT-002). Deliberately small format —
    {"required": ["dot.path", ...]} — matching the 2D widget-schema
    philosophy; a full JSON-Schema engine is a documented non-goal."""

    __tablename__ = "data_source_schemas"
    __table_args__ = (
        UniqueConstraint("source_id", "version_no", name="uq_data_source_schemas_no"),
    )

    source_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("data_sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    schema_json: Mapped[dict] = mapped_column(JSONType(), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), nullable=False
    )


class DataSourceSnapshot(UUIDPrimaryKeyMixin, Base):
    """Bounded fetch history: cache + last-known-good + evidence."""

    __tablename__ = "data_source_snapshots"
    __table_args__ = (
        Index("ix_data_source_snapshots_source_fetched", "source_id", "fetched_at"),
    )

    source_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("data_sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    fetched_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), nullable=False
    )
    valid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    payload_json: Mapped[dict | None] = mapped_column(JSONType(), nullable=True)
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
