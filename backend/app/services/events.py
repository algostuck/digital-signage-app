"""Domain event bus (P3-INT-102, slice 3A-1).

`emit()` records a normalized business fact on the tenant's event stream
and fans it out to matching subscriptions as queued deliveries. The
delivery worker clones the 2H webhook mechanics (HMAC-SHA256 signature of
the exact body, exponential backoff, replayable dead-letter) — reusing the
2H signing/post helpers rather than duplicating them.

The stream also feeds later Phase-3 consumers (decisioning, analytics,
integrations) — they read `domain_events` directly; only external HTTP
consumers go through subscriptions.
"""

import json
import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import request_id_ctx
from app.core.errors import BusinessRuleError, NotFoundError, ValidationAppError
from app.models import DomainEvent, EventDelivery, EventSubscription
from app.models.events import EventDeliveryState
from app.services.webhooks import _post, sign  # 2H helpers, deliberately shared

logger = logging.getLogger("app.events")

MAX_ATTEMPTS = 5
BACKOFF_BASE_SECONDS = 60  # 1m, 2m, 4m, 8m, then dead
MAX_SUBSCRIPTIONS = 20

# Normalized catalogue: `<entity>.<fact>` (past tense). Adding a type here
# is the only step needed for it to become subscribable.
EVENT_TYPES: dict[str, str] = {
    "device.registered": "Device registered (pending approval)",
    "device.approved": "Device approved and activated",
    "device.offline": "Device detected offline",
    "content.published": "Asset published",
    "campaign.published": "Campaign published (deployment created)",
    "deployment.completed": "Deployment reached all target devices",
    "deployment.failed": "Deployment failed or partially failed",
    "incident.opened": "Incident opened",
    "incident.resolved": "Incident resolved",
    "subscription.status_changed": "Tenant subscription status changed",
}


def _new_secret() -> str:
    return "evsec_" + secrets.token_urlsafe(32)


# --- emission ---


def _envelope(event: DomainEvent) -> dict:
    return {
        "event_id": str(event.id),
        "event_type": event.event_type,
        "entity_type": event.entity_type,
        "entity_id": str(event.entity_id) if event.entity_id else None,
        "payload": event.payload_json,
        "occurred_at": event.occurred_at.isoformat() if event.occurred_at else None,
        "request_id": event.request_id,
    }


async def emit(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    event_type: str,
    entity_type: str,
    entity_id: uuid.UUID | None = None,
    payload: dict | None = None,
) -> DomainEvent:
    """Appends to the tenant stream and queues deliveries for matching
    active subscriptions. Runs inside the caller's transaction — the event
    commits (or rolls back) atomically with the business change."""
    if event_type not in EVENT_TYPES:
        raise ValidationAppError(f"Unknown event type '{event_type}'", field="event_type")
    event = DomainEvent(
        organization_id=organization_id,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        payload_json=payload,
        request_id=request_id_ctx.get(),
        occurred_at=datetime.now(UTC),
    )
    db.add(event)
    await db.flush()

    subscriptions = (
        await db.execute(
            select(EventSubscription).where(
                EventSubscription.organization_id == organization_id,
                EventSubscription.active.is_(True),
            )
        )
    ).scalars()
    for subscription in subscriptions:
        types = subscription.event_types_json
        if "*" not in types and event_type not in types:
            continue
        db.add(
            EventDelivery(
                organization_id=organization_id,
                subscription_id=subscription.id,
                event_id=event.id,
                event_type=event_type,
                payload_json=_envelope(event),
                next_attempt_at=datetime.now(UTC),
            )
        )
    await db.flush()
    return event


async def list_events(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    event_type: str | None = None,
    entity_type: str | None = None,
    page: int,
    page_size: int,
) -> tuple[list[DomainEvent], int]:
    query = select(DomainEvent).where(DomainEvent.organization_id == organization_id)
    if event_type:
        query = query.where(DomainEvent.event_type == event_type)
    if entity_type:
        query = query.where(DomainEvent.entity_type == entity_type)
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    rows = await db.execute(
        query.order_by(DomainEvent.occurred_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(rows.scalars().all()), total


# --- subscriptions (consumers) ---


def _validate(url: str, event_types: list) -> None:
    if not url.startswith(("http://", "https://")):
        raise ValidationAppError("url must be http(s)", field="url")
    if not isinstance(event_types, list) or not event_types:
        raise ValidationAppError(
            "event_types must be a non-empty list", field="event_types"
        )
    unknown = [e for e in event_types if e != "*" and e not in EVENT_TYPES]
    if unknown:
        raise ValidationAppError(f"Unknown event types: {unknown}", field="event_types")


async def get_subscription(
    db: AsyncSession, organization_id: uuid.UUID, subscription_id: uuid.UUID
) -> EventSubscription:
    row = (
        await db.execute(
            select(EventSubscription).where(
                EventSubscription.organization_id == organization_id,
                EventSubscription.id == subscription_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError("Event subscription not found")
    return row


async def list_subscriptions(
    db: AsyncSession, organization_id: uuid.UUID
) -> list[EventSubscription]:
    rows = await db.execute(
        select(EventSubscription)
        .where(EventSubscription.organization_id == organization_id)
        .order_by(EventSubscription.created_at)
    )
    return list(rows.scalars().all())


async def create_subscription(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    name: str,
    url: str,
    event_types: list,
) -> tuple[EventSubscription, str]:
    """Returns (subscription, raw_secret) — the secret is shown exactly
    once; only rotation issues a new one."""
    _validate(url, event_types)
    count = (
        await db.execute(
            select(func.count()).where(
                EventSubscription.organization_id == organization_id
            )
        )
    ).scalar_one()
    if count >= MAX_SUBSCRIPTIONS:
        raise BusinessRuleError(f"At most {MAX_SUBSCRIPTIONS} event subscriptions")
    secret = _new_secret()
    subscription = EventSubscription(
        organization_id=organization_id,
        name=name,
        url=url,
        event_types_json=event_types,
        secret=secret,
        active=True,
    )
    db.add(subscription)
    await db.flush()

    from app.services import audit

    await audit.record(
        db,
        organization_id,
        action="EVENT_SUBSCRIPTION_CREATED",
        entity_type="event_subscription",
        entity_id=subscription.id,
        after={"name": name, "url": url, "event_types": event_types},  # never the secret
    )
    return subscription, secret


async def update_subscription(
    db: AsyncSession,
    organization_id: uuid.UUID,
    subscription_id: uuid.UUID,
    **changes,
) -> EventSubscription:
    subscription = await get_subscription(db, organization_id, subscription_id)
    for field in ("name", "url", "event_types_json", "active"):
        if field in changes and changes[field] is not None:
            setattr(subscription, field, changes[field])
    _validate(subscription.url, subscription.event_types_json)
    await db.flush()
    return subscription


async def rotate_secret(
    db: AsyncSession, organization_id: uuid.UUID, subscription_id: uuid.UUID
) -> tuple[EventSubscription, str]:
    subscription = await get_subscription(db, organization_id, subscription_id)
    secret = _new_secret()
    subscription.secret = secret
    await db.flush()

    from app.services import audit

    await audit.record(
        db,
        organization_id,
        action="EVENT_SUBSCRIPTION_SECRET_ROTATED",
        entity_type="event_subscription",
        entity_id=subscription.id,
    )
    return subscription, secret


async def delete_subscription(
    db: AsyncSession, organization_id: uuid.UUID, subscription_id: uuid.UUID
) -> None:
    subscription = await get_subscription(db, organization_id, subscription_id)
    await db.delete(subscription)
    await db.flush()


# --- delivery worker (2H mechanics) ---


async def process_deliveries(db: AsyncSession, *, limit: int = 50) -> dict:
    """Beat sweep: pushes due event deliveries with X-Event-Signature;
    exponential backoff; dead-letter after MAX_ATTEMPTS. Idempotent and
    DB-backed — worker restarts lose nothing (NFR2-08)."""
    now = datetime.now(UTC)
    rows = (
        await db.execute(
            select(EventDelivery, EventSubscription)
            .join(
                EventSubscription,
                EventSubscription.id == EventDelivery.subscription_id,
            )
            .where(
                EventDelivery.state.in_(
                    [EventDeliveryState.PENDING.value, EventDeliveryState.FAILED.value]
                ),
                EventDelivery.next_attempt_at <= now,
            )
            .order_by(EventDelivery.next_attempt_at)
            .limit(limit)
        )
    ).all()
    delivered = dead = retried = 0
    for delivery, subscription in rows:
        delivery.attempt_no += 1
        body = json.dumps(delivery.payload_json, separators=(",", ":")).encode()
        headers = {
            "Content-Type": "application/json",
            "X-Event-Signature": sign(subscription.secret, body),
            "X-Event-Type": delivery.event_type,
            "X-Event-Delivery": str(delivery.id),
            "X-Event-Attempt": str(delivery.attempt_no),
        }
        try:
            status = await _post(subscription.url, body, headers)
            delivery.response_code = status
            if 200 <= status < 300:
                delivery.state = EventDeliveryState.DELIVERED.value
                delivery.delivered_at = datetime.now(UTC)
                delivery.last_error = None
                delivered += 1
                continue
            delivery.last_error = f"HTTP {status}"
        except Exception as exc:  # noqa: BLE001 — every transport error is a failed attempt
            delivery.response_code = None
            delivery.last_error = str(exc)[:500]
        if delivery.attempt_no >= MAX_ATTEMPTS:
            delivery.state = EventDeliveryState.DEAD.value
            delivery.next_attempt_at = None
            dead += 1
            logger.warning(
                "Event delivery %s dead after %s attempts", delivery.id, delivery.attempt_no
            )
        else:
            delivery.state = EventDeliveryState.FAILED.value
            backoff = BACKOFF_BASE_SECONDS * (2 ** (delivery.attempt_no - 1))
            delivery.next_attempt_at = datetime.now(UTC) + timedelta(seconds=backoff)
            retried += 1
    await db.flush()
    return {"delivered": delivered, "retried": retried, "dead": dead, "scanned": len(rows)}


async def replay_delivery(
    db: AsyncSession, organization_id: uuid.UUID, delivery_id: uuid.UUID
) -> EventDelivery:
    delivery = (
        await db.execute(
            select(EventDelivery).where(
                EventDelivery.organization_id == organization_id,
                EventDelivery.id == delivery_id,
            )
        )
    ).scalar_one_or_none()
    if delivery is None:
        raise NotFoundError("Event delivery not found")
    delivery.state = EventDeliveryState.PENDING.value
    delivery.attempt_no = 0
    delivery.next_attempt_at = datetime.now(UTC)
    delivery.last_error = None
    await db.flush()
    return delivery


async def list_deliveries(
    db: AsyncSession,
    organization_id: uuid.UUID,
    subscription_id: uuid.UUID,
    *,
    page: int,
    page_size: int,
) -> tuple[list[EventDelivery], int]:
    await get_subscription(db, organization_id, subscription_id)
    query = select(EventDelivery).where(
        EventDelivery.organization_id == organization_id,
        EventDelivery.subscription_id == subscription_id,
    )
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    rows = await db.execute(
        query.order_by(EventDelivery.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(rows.scalars().all()), total
