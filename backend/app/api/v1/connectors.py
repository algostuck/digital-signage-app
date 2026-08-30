"""Integration catalogue (P3-INT-101/102, slice 3E-4).

Documented decision (PHASE_3_DATABASE_CHANGES §reuse): no connector tables —
the concrete integrations already live in first-class stores (webhook
subscriptions, event-bus consumers, data sources, API keys, SSO, SMTP).
The catalogue is a live, per-tenant view over those stores so the UI can
present one consolidated surface."""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentTenantId, require_permissions
from app.db.session import get_db
from app.schemas.envelope import success

router = APIRouter()


@router.get("/connectors", dependencies=[require_permissions("webhooks.manage")])
async def catalogue(tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)) -> dict:
    from app.core.config import get_settings
    from app.models import (
        ApiKey,
        DataSource,
        EventSubscription,
        SsoProvider,
        WebhookSubscription,
    )
    from app.services import entitlements

    async def count(model, *criteria):
        return (
            await db.execute(
                select(func.count()).where(model.organization_id == tenant_id, *criteria)
            )
        ).scalar_one()

    effective = await entitlements.get_effective(db, tenant_id)
    sso = (
        await db.execute(
            select(SsoProvider).where(SsoProvider.organization_id == tenant_id)
        )
    ).scalar_one_or_none()

    connectors = [
        {
            "key": "webhooks",
            "name": "Operational webhooks",
            "description": "Signed pushes of operational notifications (2H).",
            "configured": await count(WebhookSubscription),
            "available": True,
            "surface": "settings:integrations",
        },
        {
            "key": "event_bus",
            "name": "Domain event bus",
            "description": "Normalized business events with signed deliveries.",
            "configured": await count(EventSubscription),
            "available": True,
            "surface": "settings:event-bus",
        },
        {
            "key": "data_sources",
            "name": "Data sources",
            "description": "Guarded REST/RSS feeds for dynamic widgets.",
            "configured": await count(DataSource),
            "available": effective.enabled("dynamic_data"),
            "surface": "settings:data-sources",
        },
        {
            "key": "api_keys",
            "name": "API keys",
            "description": "Scoped partner access with X-API-Key.",
            "configured": await count(ApiKey, ApiKey.revoked_at.is_(None)),
            "available": effective.enabled("api_access"),
            "surface": "settings:integrations",
        },
        {
            "key": "sso",
            "name": "Enterprise SSO",
            "description": "OIDC login mapped to platform roles.",
            "configured": 1 if (sso and sso.active) else 0,
            "available": effective.enabled("sso"),
            "surface": "settings:sso",
        },
        {
            "key": "smtp",
            "name": "Email delivery",
            "description": "Notification email via the platform SMTP adapter.",
            "configured": 1 if getattr(get_settings(), "email_backend", "log") == "smtp"
            else 0,
            "available": True,
            "surface": "platform-config",
        },
    ]
    return success(connectors)
