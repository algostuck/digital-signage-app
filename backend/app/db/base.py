import uuid
from datetime import UTC, datetime

from sqlalchemy import ForeignKey, func
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column

from app.db.types import GUID, JSONType, UTCDateTime


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    type_annotation_map = {
        uuid.UUID: GUID(),
        dict: JSONType(),
        datetime: UTCDateTime(),
    }


class UUIDPrimaryKeyMixin:
    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        server_default=func.now(),
        # Python-side onupdate: a SQL-side default would expire the attribute
        # after every UPDATE, breaking serialization in the async session.
        onupdate=utcnow,
        nullable=False,
    )


class TenantMixin:
    """Adds mandatory tenant ownership. Every tenant-owned model uses this."""

    @declared_attr
    def organization_id(cls) -> Mapped[uuid.UUID]:
        return mapped_column(
            GUID(), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True
        )
