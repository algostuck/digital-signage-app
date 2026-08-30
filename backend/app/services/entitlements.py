"""Entitlement engine (SaaS core).

Two kinds of authorization exist side by side and BOTH must pass:
- Permission  — "what may this user do?"      (RBAC, Phase 1)
- Entitlement — "what is this tenant paying for?" (subscription → plan)

Resolution order for the effective value of a key:
  subscription_items override → plan_entitlements → catalogue default.
Numeric limits are additionally min-combined with the platform quota
override (organizations.quotas_json, Phase-2K) so a platform admin can
always tighten below the plan.

Legacy mode: an organization with NO subscription runs unrestricted
(every boolean on, every limit unlimited). Existing tenants therefore
behave exactly as before this module existed; limits begin the moment a
subscription is attached.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BusinessRuleError
from app.models import Organization, Subscription
from app.models.saas import SubscriptionStatus

# Catalogue: key -> ("int" | "bool"). Numeric default = None (unlimited);
# boolean default = True (legacy mode). Plans then restrict.
ENTITLEMENTS: dict[str, str] = {
    # numeric limits
    "max_devices": "int",
    "max_users": "int",
    "max_storage_mb": "int",
    "max_locations": "int",
    "max_api_calls_month": "int",
    "ai_credits_month": "int",
    # feature flags
    "proof_of_play": "bool",
    "advanced_analytics": "bool",
    "api_access": "bool",
    "sso": "bool",
    "white_label": "bool",
    "video_wall": "bool",
    "ai_features": "bool",
    "dynamic_data": "bool",
    "experiments": "bool",
    "advertising": "bool",
    "fleet_ai": "bool",
    "developer_portal": "bool",
    "edge_bundles": "bool",
}

# Subscription states in which the tenant may still GROW (create new
# billable resources). Outside these, growth actions are blocked — but
# existing devices keep playing their cached content (never blank a
# screen over billing).
GROWTH_ALLOWED_STATUSES = {
    SubscriptionStatus.TRIALING.value,
    SubscriptionStatus.ACTIVE.value,
    SubscriptionStatus.PAST_DUE.value,
    SubscriptionStatus.GRACE_PERIOD.value,
}

GROWTH_ACTIONS = {
    "device_register": "register new devices",
    "content_upload": "upload new content",
    "campaign_create": "create new campaigns",
    "publish": "publish campaigns",
    "user_create": "add users",
}


@dataclass(frozen=True)
class EffectiveEntitlements:
    values: dict[str, int | bool | None]
    plan_code: str | None
    plan_name: str | None
    subscription_status: str | None

    def limit(self, key: str) -> int | None:
        value = self.values.get(key)
        return value if isinstance(value, int) else None

    def enabled(self, key: str) -> bool:
        value = self.values.get(key)
        return bool(value) if value is not None else True


async def current_subscription(
    db: AsyncSession, organization_id: uuid.UUID
) -> Subscription | None:
    """The tenant's newest non-expired subscription (one logical active)."""
    rows = await db.execute(
        select(Subscription)
        .where(Subscription.organization_id == organization_id)
        .order_by(Subscription.created_at.desc())
    )
    for subscription in rows.scalars():
        if subscription.status != SubscriptionStatus.EXPIRED.value:
            return subscription
    return None


async def get_effective(
    db: AsyncSession, organization_id: uuid.UUID
) -> EffectiveEntitlements:
    subscription = await current_subscription(db, organization_id)

    values: dict[str, int | bool | None] = {
        key: (None if kind == "int" else True) for key, kind in ENTITLEMENTS.items()
    }
    plan_code = plan_name = status = None
    if subscription is not None:
        status = subscription.status
        plan = subscription.plan
        plan_code, plan_name = plan.code, plan.name
        for row in plan.entitlements:
            if row.key in ENTITLEMENTS:
                values[row.key] = (
                    row.int_value if ENTITLEMENTS[row.key] == "int" else row.bool_value
                )
        for item in subscription.items:  # add-ons / enterprise overrides win
            if item.key in ENTITLEMENTS:
                values[item.key] = (
                    item.int_value if ENTITLEMENTS[item.key] == "int" else item.bool_value
                )

    # Platform quota overrides (2K) can only tighten numeric limits.
    org = await db.get(Organization, organization_id)
    quotas = (org.quotas_json or {}) if org else {}
    for key in ("max_devices", "max_users", "max_storage_mb"):
        override = quotas.get(key)
        if override is not None:
            current = values.get(key)
            values[key] = override if current is None else min(current, override)

    return EffectiveEntitlements(
        values=values,
        plan_code=plan_code,
        plan_name=plan_name,
        subscription_status=status,
    )


async def require_feature(
    db: AsyncSession, organization_id: uuid.UUID, key: str
) -> None:
    """Feature gate: permission may pass while the tenant's plan does not
    include the feature — both are required."""
    effective = await get_effective(db, organization_id)
    if not effective.enabled(key):
        plan = effective.plan_name or "current plan"
        raise BusinessRuleError(
            f"'{key}' is not included in the {plan}. Upgrade your subscription."
        )


async def ensure_subscription_allows(
    db: AsyncSession, organization_id: uuid.UUID, action: str
) -> None:
    """Suspension semantics: growth actions are blocked when the
    subscription is suspended/cancelled/expired; player heartbeats,
    manifests and cached playback are NEVER routed through this check."""
    subscription = await current_subscription(db, organization_id)
    if subscription is None:
        return  # legacy tenant — unrestricted
    if subscription.status not in GROWTH_ALLOWED_STATUSES:
        what = GROWTH_ACTIONS.get(action, action)
        raise BusinessRuleError(
            f"Subscription is {subscription.status}: cannot {what}. "
            "Renew or reactivate the subscription to continue."
        )


async def ensure_limit(
    db: AsyncSession,
    organization_id: uuid.UUID,
    key: str,
    current_used: int,
    *,
    increment: int = 1,
    resource_label: str,
) -> None:
    effective = await get_effective(db, organization_id)
    limit = effective.limit(key)
    if limit is not None and current_used + increment > limit:
        raise BusinessRuleError(
            f"{resource_label} limit reached ({current_used}/{limit}). "
            "Upgrade your subscription."
        )
