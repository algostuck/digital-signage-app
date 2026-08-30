import datetime as dt
import enum
import uuid

from sqlalchemy import Boolean, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import GUID, JSONType, UTCDateTime


class ApprovalRequestState(enum.StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"
    CANCELLED = "cancelled"


class ApprovalPolicy(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """Per-tenant governance configuration (P2-APP-001).

    Absent policy = Phase-1 behavior: approval required, maker-checker off.
    """

    __tablename__ = "approval_policies"
    __table_args__ = (
        UniqueConstraint("organization_id", "entity_type", name="uq_approval_policies_org_type"),
    )

    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    require_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    maker_checker: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    rules_json: Mapped[dict | None] = mapped_column(JSONType(), nullable=True)


class ApprovalRequest(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """Workflow header for one submission of an entity (P2-APP-002/003)."""

    __tablename__ = "approval_requests"
    __table_args__ = (
        Index("ix_approval_requests_org_state", "organization_id", "state"),
        Index("ix_approval_requests_entity", "entity_type", "entity_id"),
    )

    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)
    state: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ApprovalRequestState.PENDING.value
    )
    requester_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    submitted_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), nullable=False
    )
    decided_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    comments: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    actions: Mapped[list["ApprovalAction"]] = relationship(
        lazy="selectin", cascade="all, delete-orphan", order_by="ApprovalAction.created_at"
    )


class ApprovalAction(UUIDPrimaryKeyMixin, Base):
    """Immutable decision/audit trail row (P2-APP-003). Append-only."""

    __tablename__ = "approval_actions"

    approval_request_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("approval_requests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    comments: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    from_state: Mapped[str | None] = mapped_column(String(20), nullable=True)
    to_state: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), nullable=False
    )
