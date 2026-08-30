"""Schemas for the SaaS core: plans, billing, memberships, platform admin."""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class EntitlementRowIn(BaseModel):
    key: str = Field(max_length=60)
    int_value: int | None = None
    bool_value: bool | None = None


class PlanUpsert(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    prices: dict = Field(default_factory=dict)
    entitlements: list[EntitlementRowIn] = Field(default_factory=list)
    is_active: bool = True
    sort_order: int = 0


class SubscribeRequest(BaseModel):
    plan_code: str = Field(min_length=1, max_length=50)
    billing_cycle: str = "monthly"
    trial_days: int = Field(default=0, ge=0, le=365)


class ChangePlanRequest(BaseModel):
    plan_code: str = Field(min_length=1, max_length=50)
    note: str | None = Field(default=None, max_length=500)


class PlanRequestDecision(BaseModel):
    decision_note: str | None = Field(default=None, max_length=500)


class TenantUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    timezone: str | None = None


class CancelRequest(BaseModel):
    at_period_end: bool = True


class MemberAdd(BaseModel):
    email: EmailStr
    role_id: uuid.UUID
    is_owner: bool = False


class MemberUpdate(BaseModel):
    role_id: uuid.UUID | None = None
    is_owner: bool | None = None
    status: str | None = None


class TenantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    code: str = Field(min_length=1, max_length=50, pattern=r"^[a-z0-9][a-z0-9-]*$")
    timezone: str = "UTC"
    owner_email: EmailStr
    owner_full_name: str = Field(min_length=1, max_length=200)
    owner_password: str | None = Field(default=None, min_length=8, max_length=200)


class TenantStatusUpdate(BaseModel):
    status: str


class AssignSubscriptionRequest(BaseModel):
    plan_code: str = Field(min_length=1, max_length=50)
    billing_cycle: str = "monthly"
    trial_days: int = Field(default=0, ge=0, le=365)


class TransitionRequest(BaseModel):
    to_status: str
    event: str = "admin_transition"


class ProviderUpdate(BaseModel):
    provider: str = Field(min_length=1, max_length=30)
    provider_customer_id: str | None = Field(default=None, max_length=200)
    provider_subscription_id: str | None = Field(default=None, max_length=200)


class RecordPaymentRequest(BaseModel):
    invoice_id: uuid.UUID
    provider: str = "manual"
    provider_ref: str | None = Field(default=None, max_length=200)


def plan_out(plan) -> dict:
    return {
        "id": str(plan.id),
        "code": plan.code,
        "name": plan.name,
        "description": plan.description,
        "prices": plan.prices_json or {},
        "is_active": plan.is_active,
        "sort_order": plan.sort_order,
        "entitlements": [
            {"key": row.key, "int_value": row.int_value, "bool_value": row.bool_value}
            for row in plan.entitlements
        ],
    }


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def subscription_out(subscription) -> dict:
    return {
        "id": str(subscription.id),
        "plan": {
            "code": subscription.plan.code,
            "name": subscription.plan.name,
        },
        "status": subscription.status,
        "billing_cycle": subscription.billing_cycle,
        "start_at": _iso(subscription.start_at),
        "current_period_start": _iso(subscription.current_period_start),
        "current_period_end": _iso(subscription.current_period_end),
        "trial_end_at": _iso(subscription.trial_end_at),
        "cancel_at": _iso(subscription.cancel_at),
        "cancelled_at": _iso(subscription.cancelled_at),
        "provider": subscription.provider,
        "items": [
            {"key": item.key, "int_value": item.int_value, "bool_value": item.bool_value}
            for item in subscription.items
        ],
    }


def invoice_out(invoice) -> dict:
    return {
        "id": str(invoice.id),
        "number": invoice.number,
        "period_start": _iso(invoice.period_start),
        "period_end": _iso(invoice.period_end),
        "amount": str(invoice.amount),
        "currency": invoice.currency,
        "status": invoice.status,
        "issued_at": _iso(invoice.issued_at),
        "due_at": _iso(invoice.due_at),
        "paid_at": _iso(invoice.paid_at),
    }
