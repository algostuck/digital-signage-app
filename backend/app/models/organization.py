import enum

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import JSONType


class OrganizationStatus(enum.StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    ARCHIVED = "archived"


class Organization(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=OrganizationStatus.ACTIVE.value
    )
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    locale: Mapped[str] = mapped_column(String(16), nullable=False, default="en")
    branding_json: Mapped[dict | None] = mapped_column(JSONType(), nullable=True)
    quotas_json: Mapped[dict | None] = mapped_column(JSONType(), nullable=True)
    # Per-tenant policy store (P2-MON-002 thresholds; later: defaults,
    # retention). Namespaced dict, e.g. {"monitoring": {...}}.
    settings_json: Mapped[dict | None] = mapped_column(JSONType(), nullable=True)
    # Secret devices present to enroll into this tenant (FR-DEV-001).
    enrollment_key: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
