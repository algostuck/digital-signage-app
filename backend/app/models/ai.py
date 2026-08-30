"""AI content intelligence models (P3-M01, slice 3B-1).

Governance-first: every AI operation writes an `ai_requests` row (who/what/
which provider/model/template version — the explainability trail, P3-AI-005)
and its result lands in `ai_outputs` with confidence, safety status and
revision number (P3-AI-004). Secrets are never stored — providers resolve
credentials from server configuration; only template VERSIONS are recorded.
`ai_requests` doubles as the per-tenant usage ledger (STEP 39).
"""

import datetime as dt
import enum
import uuid

from sqlalchemy import Boolean, ForeignKey, Index, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import GUID, JSONType, UTCDateTime


class AiOperation(enum.StrEnum):
    TEXT = "text"
    CREATIVE = "creative"
    LOCALIZATION = "localization"


class AiRequestStatus(enum.StrEnum):
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class AiSafetyStatus(enum.StrEnum):
    PENDING = "pending"  # awaiting approval routing
    PASSED = "passed"
    FLAGGED = "flagged"  # guardrail violation — requires human action
    REJECTED = "rejected"


class AiPolicy(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """One row per policy_type: 'operations' (allowed ops), 'guardrails'
    (banned terms, tone), 'approval' (routing into the 2A engine)."""

    __tablename__ = "ai_policies"
    __table_args__ = (
        Index("ix_ai_policies_org_type", "organization_id", "policy_type", unique=True),
    )

    policy_type: Mapped[str] = mapped_column(String(30), nullable=False)
    rules_json: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class AiRequest(UUIDPrimaryKeyMixin, TenantMixin, Base):
    __tablename__ = "ai_requests"
    __table_args__ = (
        Index("ix_ai_requests_org_created", "organization_id", "created_at"),
    )

    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    operation: Mapped[str] = mapped_column(String(30), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model_ref: Mapped[str | None] = mapped_column(String(100), nullable=True)
    template_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=AiRequestStatus.RUNNING.value
    )
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), nullable=False
    )

    outputs: Mapped[list["AiOutput"]] = relationship(
        lazy="selectin", cascade="all, delete-orphan", order_by="AiOutput.revision_no"
    )


class AiOutput(UUIDPrimaryKeyMixin, TenantMixin, Base):
    __tablename__ = "ai_outputs"

    request_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("ai_requests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    output_kind: Mapped[str] = mapped_column(String(30), nullable=False)
    content_json: Mapped[dict] = mapped_column(JSONType(), nullable=False)
    # Optional materialization target (later slices): draft asset/template.
    asset_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("assets.id", ondelete="SET NULL"), nullable=True
    )
    confidence: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False, default=0)
    fallback: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    safety_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=AiSafetyStatus.PASSED.value
    )
    safety_notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), nullable=False
    )
