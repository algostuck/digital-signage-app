"""Per-user saved views (P2-SRC-002): filters + column layout per module."""

import uuid

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import GUID, JSONType

SAVED_VIEW_MODULES = (
    "devices",
    "content",
    "campaigns",
    "playlists",
    "schedules",
    "audit",
    "incidents",
)


class SavedView(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "saved_views"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "user_id", "module", "name", name="uq_saved_views_owner_name"
        ),
        Index("ix_saved_views_user_module", "user_id", "module"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    module: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    filter_json: Mapped[dict] = mapped_column(JSONType(), nullable=False)
    columns_json: Mapped[list | None] = mapped_column(JSONType(), nullable=True)
