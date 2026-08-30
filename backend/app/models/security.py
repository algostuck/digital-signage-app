"""Advanced security models (P3-M10, slice 3E-3).

Device identities formalize the credential lifecycle that already exists
(hashed device tokens, 1E): every issuance/revocation becomes an auditable
credential record with a fingerprint — never the credential itself.
Security policies are declarative checks the daily sweep evaluates
(credential age, key expiry); findings land as policy_violations with a
state machine, not automatic enforcement.
"""

import datetime as dt
import enum
import uuid

from sqlalchemy import Boolean, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import GUID, JSONType, UTCDateTime


class DeviceIdentity(UUIDPrimaryKeyMixin, TenantMixin, Base):
    __tablename__ = "device_identities"
    __table_args__ = (
        Index("uq_device_identities_device", "device_id", unique=True),
    )

    device_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False
    )
    identity_type: Mapped[str] = mapped_column(
        String(30), nullable=False, default="device_token"
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), nullable=False
    )

    credentials: Mapped[list["IdentityCredential"]] = relationship(
        lazy="selectin", cascade="all, delete-orphan",
        order_by="IdentityCredential.issued_at",
    )


class IdentityCredential(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "identity_credentials"

    identity_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("device_identities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # First 16 hex chars of the stored hash — recognizable, never usable.
    fingerprint: Mapped[str] = mapped_column(String(32), nullable=False)
    issued_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    revoked_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class SecurityPolicy(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "security_policies"
    __table_args__ = (
        Index("uq_security_policies_org_scope", "organization_id", "scope_type",
              unique=True),
    )

    # "device_credentials" | "api_keys"
    scope_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # {"max_age_days": 180}
    conditions_json: Mapped[dict] = mapped_column(JSONType(), nullable=False)
    # {"severity": "warning"} — violations are surfaced, never auto-enforced.
    actions_json: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ViolationState(enum.StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"


class PolicyViolation(UUIDPrimaryKeyMixin, TenantMixin, Base):
    __tablename__ = "policy_violations"
    __table_args__ = (
        Index("ix_policy_violations_org_state", "organization_id", "state"),
    )

    policy_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("security_policies.id", ondelete="SET NULL"), nullable=True
    )
    entity_type: Mapped[str] = mapped_column(String(30), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="warning")
    state: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ViolationState.OPEN.value
    )
    detail: Mapped[str | None] = mapped_column(String(500), nullable=True)
    detected_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), nullable=False
    )
    resolved_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime(), nullable=True)
