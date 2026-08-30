"""Integrations API (P2-19 webhooks, P2-20 API keys)."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentTenantId, CurrentUser, PageParams, require_permissions
from app.db.session import get_db
from app.schemas.envelope import success
from app.schemas.integrations import (
    ApiKeyCreate,
    ApiKeyOut,
    WebhookCreate,
    WebhookDeliveryOut,
    WebhookOut,
    WebhookUpdate,
)
from app.services import api_keys as api_keys_service
from app.services import webhooks as webhooks_service

router = APIRouter()


def _webhook_out(subscription, secret: str | None = None) -> dict:
    out = WebhookOut.model_validate(subscription).model_dump(mode="json")
    if secret is not None:
        out["secret"] = secret  # one-time reveal (create / rotate only)
    return out


@router.get("/webhooks", dependencies=[require_permissions("webhooks.manage")])
async def list_webhooks(tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)) -> dict:
    subscriptions = await webhooks_service.list_subscriptions(db, tenant_id)
    return success([_webhook_out(s) for s in subscriptions])


@router.post(
    "/webhooks", dependencies=[require_permissions("webhooks.manage")], status_code=201
)
async def create_webhook(
    body: WebhookCreate, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    subscription, secret = await webhooks_service.create_subscription(
        db,
        tenant_id,
        url=body.url,
        description=body.description,
        event_types=body.event_types_json,
    )
    return success(_webhook_out(subscription, secret))


@router.patch(
    "/webhooks/{subscription_id}", dependencies=[require_permissions("webhooks.manage")]
)
async def update_webhook(
    subscription_id: uuid.UUID,
    body: WebhookUpdate,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
) -> dict:
    changes = body.model_dump(exclude_unset=True)
    subscription = await webhooks_service.update_subscription(
        db, tenant_id, subscription_id, **changes
    )
    return success(_webhook_out(subscription))


@router.post(
    "/webhooks/{subscription_id}/rotate-secret",
    dependencies=[require_permissions("webhooks.manage")],
)
async def rotate_webhook_secret(
    subscription_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    subscription, secret = await webhooks_service.rotate_secret(
        db, tenant_id, subscription_id
    )
    return success(_webhook_out(subscription, secret))


@router.delete(
    "/webhooks/{subscription_id}", dependencies=[require_permissions("webhooks.manage")]
)
async def delete_webhook(
    subscription_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    await webhooks_service.delete_subscription(db, tenant_id, subscription_id)
    return success({"deleted": True})


@router.get(
    "/webhooks/{subscription_id}/deliveries",
    dependencies=[require_permissions("webhooks.manage")],
)
async def webhook_deliveries(
    subscription_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    pagination: PageParams,
    db: AsyncSession = Depends(get_db),
) -> dict:
    rows, total = await webhooks_service.list_deliveries(
        db, tenant_id, subscription_id, page=pagination.page, page_size=pagination.page_size
    )
    return success(
        [WebhookDeliveryOut.model_validate(r).model_dump(mode="json") for r in rows],
        page=pagination.page,
        page_size=pagination.page_size,
        total=total,
    )


@router.post(
    "/webhooks/deliveries/{delivery_id}/replay",
    dependencies=[require_permissions("webhooks.manage")],
)
async def replay_webhook_delivery(
    delivery_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    delivery = await webhooks_service.replay_delivery(db, tenant_id, delivery_id)
    return success(WebhookDeliveryOut.model_validate(delivery).model_dump(mode="json"))


# --- API keys (P2-20) ---


@router.get("/api-keys", dependencies=[require_permissions("api_keys.manage")])
async def list_api_keys(tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)) -> dict:
    keys = await api_keys_service.list_keys(db, tenant_id)
    return success([ApiKeyOut.model_validate(k).model_dump(mode="json") for k in keys])


@router.post(
    "/api-keys", dependencies=[require_permissions("api_keys.manage")], status_code=201
)
async def create_api_key(
    body: ApiKeyCreate,
    tenant_id: CurrentTenantId,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    key, raw = await api_keys_service.create_key(
        db,
        tenant_id,
        name=body.name,
        scopes=body.scopes,
        expires_at=body.expires_at,
        created_by=user.id,
    )
    out = ApiKeyOut.model_validate(key).model_dump(mode="json")
    out["key"] = raw  # one-time reveal
    return success(out)


@router.delete("/api-keys/{key_id}", dependencies=[require_permissions("api_keys.manage")])
async def revoke_api_key(
    key_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    key = await api_keys_service.revoke_key(db, tenant_id, key_id, user_id=user.id)
    return success(ApiKeyOut.model_validate(key).model_dump(mode="json"))
