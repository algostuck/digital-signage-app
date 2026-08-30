"""Domain event bus API (P3-INT-102, slice 3A-1): normalized event stream
+ consumer subscriptions with signed deliveries (2H pattern)."""

import uuid

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentTenantId, PageParams, require_permissions
from app.db.session import get_db
from app.schemas.envelope import success
from app.services import events as events_service

router = APIRouter()


class EventSubscriptionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    url: str = Field(min_length=1, max_length=1000)
    event_types: list[str] = Field(min_length=1)


class EventSubscriptionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    url: str | None = Field(default=None, min_length=1, max_length=1000)
    event_types: list[str] | None = None
    active: bool | None = None


def _event_out(event) -> dict:
    return {
        "id": str(event.id),
        "event_type": event.event_type,
        "entity_type": event.entity_type,
        "entity_id": str(event.entity_id) if event.entity_id else None,
        "payload": event.payload_json,
        "request_id": event.request_id,
        "occurred_at": event.occurred_at.isoformat() if event.occurred_at else None,
    }


def _subscription_out(subscription, secret: str | None = None) -> dict:
    out = {
        "id": str(subscription.id),
        "name": subscription.name,
        "url": subscription.url,
        "event_types": subscription.event_types_json,
        "active": subscription.active,
        "created_at": subscription.created_at.isoformat()
        if subscription.created_at
        else None,
    }
    if secret is not None:
        out["secret"] = secret  # one-time reveal (create / rotate only)
    return out


def _delivery_out(delivery) -> dict:
    return {
        "id": str(delivery.id),
        "event_id": str(delivery.event_id),
        "event_type": delivery.event_type,
        "state": delivery.state,
        "attempt_no": delivery.attempt_no,
        "response_code": delivery.response_code,
        "last_error": delivery.last_error,
        "next_attempt_at": delivery.next_attempt_at.isoformat()
        if delivery.next_attempt_at
        else None,
        "delivered_at": delivery.delivered_at.isoformat()
        if delivery.delivered_at
        else None,
        "created_at": delivery.created_at.isoformat() if delivery.created_at else None,
    }


@router.get("/events/catalogue", dependencies=[require_permissions("webhooks.manage")])
async def event_catalogue() -> dict:
    """Subscribable domain event types with descriptions."""
    return success(events_service.EVENT_TYPES)


@router.get("/events", dependencies=[require_permissions("webhooks.manage")])
async def list_events(
    tenant_id: CurrentTenantId,
    page: PageParams,
    db: AsyncSession = Depends(get_db),
    event_type: str | None = Query(default=None),
    entity_type: str | None = Query(default=None),
) -> dict:
    events, total = await events_service.list_events(
        db,
        tenant_id,
        event_type=event_type,
        entity_type=entity_type,
        page=page.page,
        page_size=page.page_size,
    )
    return success(
        [_event_out(e) for e in events],
        page=page.page,
        page_size=page.page_size,
        total=total,
    )


@router.get("/subscriptions", dependencies=[require_permissions("webhooks.manage")])
async def list_subscriptions(
    tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    subscriptions = await events_service.list_subscriptions(db, tenant_id)
    return success([_subscription_out(s) for s in subscriptions])


@router.post(
    "/subscriptions", dependencies=[require_permissions("webhooks.manage")], status_code=201
)
async def create_subscription(
    body: EventSubscriptionCreate,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
) -> dict:
    subscription, secret = await events_service.create_subscription(
        db, tenant_id, name=body.name, url=body.url, event_types=body.event_types
    )
    return success(_subscription_out(subscription, secret))


@router.patch(
    "/subscriptions/{subscription_id}",
    dependencies=[require_permissions("webhooks.manage")],
)
async def update_subscription(
    subscription_id: uuid.UUID,
    body: EventSubscriptionUpdate,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
) -> dict:
    subscription = await events_service.update_subscription(
        db,
        tenant_id,
        subscription_id,
        name=body.name,
        url=body.url,
        event_types_json=body.event_types,
        active=body.active,
    )
    return success(_subscription_out(subscription))


@router.post(
    "/subscriptions/{subscription_id}/rotate-secret",
    dependencies=[require_permissions("webhooks.manage")],
)
async def rotate_secret(
    subscription_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
) -> dict:
    subscription, secret = await events_service.rotate_secret(
        db, tenant_id, subscription_id
    )
    return success(_subscription_out(subscription, secret))


@router.delete(
    "/subscriptions/{subscription_id}",
    dependencies=[require_permissions("webhooks.manage")],
)
async def delete_subscription(
    subscription_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
) -> dict:
    await events_service.delete_subscription(db, tenant_id, subscription_id)
    return success({"deleted": True})


@router.get(
    "/subscriptions/{subscription_id}/deliveries",
    dependencies=[require_permissions("webhooks.manage")],
)
async def list_deliveries(
    subscription_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    page: PageParams,
    db: AsyncSession = Depends(get_db),
) -> dict:
    deliveries, total = await events_service.list_deliveries(
        db, tenant_id, subscription_id, page=page.page, page_size=page.page_size
    )
    return success(
        [_delivery_out(d) for d in deliveries],
        page=page.page,
        page_size=page.page_size,
        total=total,
    )


@router.post(
    "/subscriptions/deliveries/{delivery_id}/replay",
    dependencies=[require_permissions("webhooks.manage")],
)
async def replay_delivery(
    delivery_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
) -> dict:
    delivery = await events_service.replay_delivery(db, tenant_id, delivery_id)
    return success(_delivery_out(delivery))
