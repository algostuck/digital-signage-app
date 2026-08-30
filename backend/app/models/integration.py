"""Integration models (P2-M10): webhook subscriptions + scoped API keys.

Secrets policy (NFR2-05): API keys are stored only as SHA-256 hashes — the
raw key is returned exactly once at creation. Webhook signing secrets must
be usable for HMAC, so the secret itself is stored server-side but is never
returned by any API after the one-time reveal (create / rotate); moving it
into managed secret storage is a deployment concern behind this column.
"""

import datetime as dt
import enum
import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import GUID, JSONType, UTCDateTime


class WebhookDeliveryState(enum.StrEnum):
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"  # attempt failed, retry scheduled
    DEAD = "dead"  # retries exhausted (dead-letter, P2-INT-003)


class WebhookSubscription(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "webhook_subscriptions"

    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Event types from the notification catalogue, or ["*"].
    event_types_json: Mapped[list] = mapped_column(JSONType(), nullable=False)
    secret: Mapped[str] = mapped_column(String(128), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class WebhookDelivery(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "webhook_deliveries"

    subscription_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("webhook_subscriptions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    event_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSONType(), nullable=False)
    state: Mapped[str] = mapped_column(
        String(20), nullable=False, default=WebhookDeliveryState.PENDING.value
    )
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    response_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    next_attempt_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    delivered_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class ApiKey(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "api_keys"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_api_keys_org_name"),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    prefix: Mapped[str] = mapped_column(String(12), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    # Permission codes this key may exercise (subset of the catalogue).
    scopes_json: Mapped[list] = mapped_column(JSONType(), nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    expires_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    revoked_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    last_used_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime(), nullable=True)
