"""Decisioning models (P3-M03, slice 3B-2).

A decision policy holds ordered rules that adjust WHICH schedule-eligible
campaign a device plays: pin, boost or exclude — always deterministically,
always with recorded reasons (P3-DEC-002). Guardrails (P3-DEC-004) bound
the optimizer: mandatory campaigns can never be excluded, schedule windows
are never overridden, and a per-device switch budget prevents flapping.
`decision_log` is bounded by the 2K retention engine.
"""

import datetime as dt
import uuid

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import GUID, JSONType, UTCDateTime


class DecisionPolicy(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "decision_policies"
    __table_args__ = (
        Index("uq_decision_policies_org_name", "organization_id", "name", unique=True),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    guardrails_json: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    rules: Mapped[list["DecisionRule"]] = relationship(
        lazy="selectin", cascade="all, delete-orphan", order_by="DecisionRule.priority"
    )


class DecisionRule(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "decision_rules"

    policy_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("decision_policies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    # AND-combined conditions: platform, manufacturer, location_id (subtree),
    # tag {key,value}, time {start,end,days}, data {source_id,path,op,value}.
    conditions_json: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    # Exactly one action: {"pin"|"boost"|"exclude": campaign_id, "amount"?}.
    actions_json: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)


class DecisionLog(UUIDPrimaryKeyMixin, TenantMixin, Base):
    """Auditable decision trail: only written when rules actually changed or
    confirmed the outcome (bounded/retained, never per-heartbeat noise)."""

    __tablename__ = "decision_log"
    __table_args__ = (
        Index("ix_decision_log_org_decided", "organization_id", "decided_at"),
        Index("ix_decision_log_device", "device_id", "decided_at"),
    )

    device_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False
    )
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True
    )
    reason_json: Mapped[dict] = mapped_column(JSONType(), nullable=False)
    decided_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), nullable=False
    )
