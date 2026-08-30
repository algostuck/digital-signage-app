"""Webhook subscriptions with signed, retried deliveries (P2-INT-001/003).

Subscriptions listen to the operational event stream (the same catalogue
the notification-rule engine uses). Deliveries are enqueued inline but
pushed only by the async worker: each POST carries an HMAC-SHA256 signature
of the exact body (X-Webhook-Signature) computed with the subscription's
secret, plus event metadata headers. Failures back off exponentially and
land in a replayable dead-letter state after MAX_ATTEMPTS (NFR2-08 — the
queue lives in the database, so worker restarts lose nothing).
"""

import hashlib
import hmac
import json
import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, ValidationAppError
from app.models import Notification, WebhookDelivery, WebhookSubscription
from app.models.integration import WebhookDeliveryState

logger = logging.getLogger("app.webhooks")

MAX_ATTEMPTS = 5
BACKOFF_BASE_SECONDS = 60  # 1m, 2m, 4m, 8m, then dead
MAX_SUBSCRIPTIONS = 20


def _new_secret() -> str:
    return "whsec_" + secrets.token_urlsafe(32)


def sign(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _validate(url: str, event_types: list) -> None:
    if not url.startswith(("http://", "https://")):
        raise ValidationAppError("url must be http(s)", field="url")
    from app.services.notification_rules import KNOWN_EVENT_TYPES

    if not isinstance(event_types, list) or not event_types:
        raise ValidationAppError(
            "event_types_json must be a non-empty list", field="event_types_json"
        )
    unknown = [e for e in event_types if e not in KNOWN_EVENT_TYPES]
    if unknown:
        raise ValidationAppError(
            f"Unknown event types: {unknown}", field="event_types_json"
        )


async def get_subscription(
    db: AsyncSession, organization_id: uuid.UUID, subscription_id: uuid.UUID
) -> WebhookSubscription:
    row = (
        await db.execute(
            select(WebhookSubscription).where(
                WebhookSubscription.organization_id == organization_id,
                WebhookSubscription.id == subscription_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError("Webhook subscription not found")
    return row


async def list_subscriptions(
    db: AsyncSession, organization_id: uuid.UUID
) -> list[WebhookSubscription]:
    rows = await db.execute(
        select(WebhookSubscription)
        .where(WebhookSubscription.organization_id == organization_id)
        .order_by(WebhookSubscription.created_at)
    )
    return list(rows.scalars().all())


async def create_subscription(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    url: str,
    description: str | None,
    event_types: list,
) -> tuple[WebhookSubscription, str]:
    """Returns (subscription, raw_secret). The secret is never retrievable
    again — only rotation issues a new one."""
    _validate(url, event_types)
    count = (
        await db.execute(
            select(func.count()).where(
                WebhookSubscription.organization_id == organization_id
            )
        )
    ).scalar_one()
    if count >= MAX_SUBSCRIPTIONS:
        from app.core.errors import BusinessRuleError

        raise BusinessRuleError(f"At most {MAX_SUBSCRIPTIONS} webhook subscriptions")
    secret = _new_secret()
    subscription = WebhookSubscription(
        organization_id=organization_id,
        url=url,
        description=description,
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
        action="WEBHOOK_CREATED",
        entity_type="webhook_subscription",
        entity_id=subscription.id,
        after={"url": url, "event_types": event_types},  # never the secret
    )
    return subscription, secret


async def update_subscription(
    db: AsyncSession,
    organization_id: uuid.UUID,
    subscription_id: uuid.UUID,
    **changes,
) -> WebhookSubscription:
    subscription = await get_subscription(db, organization_id, subscription_id)
    for field in ("url", "description", "event_types_json", "active"):
        if field in changes and changes[field] is not None:
            setattr(subscription, field, changes[field])
    _validate(subscription.url, subscription.event_types_json)
    await db.flush()
    return subscription


async def rotate_secret(
    db: AsyncSession, organization_id: uuid.UUID, subscription_id: uuid.UUID
) -> tuple[WebhookSubscription, str]:
    subscription = await get_subscription(db, organization_id, subscription_id)
    secret = _new_secret()
    subscription.secret = secret
    await db.flush()

    from app.services import audit

    await audit.record(
        db,
        organization_id,
        action="WEBHOOK_SECRET_ROTATED",
        entity_type="webhook_subscription",
        entity_id=subscription.id,
    )
    return subscription, secret


async def delete_subscription(
    db: AsyncSession, organization_id: uuid.UUID, subscription_id: uuid.UUID
) -> None:
    subscription = await get_subscription(db, organization_id, subscription_id)
    await db.delete(subscription)
    await db.flush()


# --- event enqueue + delivery worker ---


def _payload_for(notification: Notification) -> dict:
    return {
        "event_id": str(notification.id),
        "event_type": notification.type,
        "severity": notification.severity,
        "title": notification.title,
        "message": notification.message,
        "payload": notification.payload_json,
        "occurred_at": notification.created_at.isoformat()
        if notification.created_at
        else None,
    }


async def enqueue(db: AsyncSession, notification: Notification) -> int:
    """Called from notifications.create for every operational event."""
    subscriptions = (
        await db.execute(
            select(WebhookSubscription).where(
                WebhookSubscription.organization_id == notification.organization_id,
                WebhookSubscription.active.is_(True),
            )
        )
    ).scalars()
    queued = 0
    for subscription in subscriptions:
        events = subscription.event_types_json
        if "*" not in events and notification.type not in events:
            continue
        db.add(
            WebhookDelivery(
                organization_id=notification.organization_id,
                subscription_id=subscription.id,
                event_type=notification.type,
                event_id=notification.id,
                payload_json=_payload_for(notification),
                next_attempt_at=datetime.now(UTC),
            )
        )
        queued += 1
    if queued:
        await db.flush()
    return queued


async def _post(url: str, body: bytes, headers: dict) -> int:
    """Isolated for tests; returns the HTTP status, raises on transport errors."""
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(url, content=body, headers=headers)
        return response.status_code


async def process_deliveries(db: AsyncSession, *, limit: int = 50) -> dict:
    """Worker sweep: pushes due deliveries with signatures; exponential
    backoff; dead-letter after MAX_ATTEMPTS."""
    now = datetime.now(UTC)
    rows = (
        await db.execute(
            select(WebhookDelivery, WebhookSubscription)
            .join(
                WebhookSubscription,
                WebhookSubscription.id == WebhookDelivery.subscription_id,
            )
            .where(
                WebhookDelivery.state.in_(
                    [WebhookDeliveryState.PENDING.value, WebhookDeliveryState.FAILED.value]
                ),
                WebhookDelivery.next_attempt_at <= now,
            )
            .order_by(WebhookDelivery.next_attempt_at)
            .limit(limit)
        )
    ).all()
    delivered = dead = retried = 0
    for delivery, subscription in rows:
        delivery.attempt_no += 1
        body = json.dumps(delivery.payload_json, separators=(",", ":")).encode()
        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Signature": sign(subscription.secret, body),
            "X-Webhook-Event": delivery.event_type,
            "X-Webhook-Delivery": str(delivery.id),
            "X-Webhook-Attempt": str(delivery.attempt_no),
        }
        try:
            status = await _post(subscription.url, body, headers)
            delivery.response_code = status
            if 200 <= status < 300:
                delivery.state = WebhookDeliveryState.DELIVERED.value
                delivery.delivered_at = datetime.now(UTC)
                delivery.last_error = None
                delivered += 1
                continue
            delivery.last_error = f"HTTP {status}"
        except Exception as exc:  # noqa: BLE001 — every transport error is a failed attempt
            delivery.response_code = None
            delivery.last_error = str(exc)[:500]
        if delivery.attempt_no >= MAX_ATTEMPTS:
            delivery.state = WebhookDeliveryState.DEAD.value
            delivery.next_attempt_at = None
            dead += 1
            logger.warning(
                "Webhook delivery %s dead after %s attempts", delivery.id, delivery.attempt_no
            )
        else:
            delivery.state = WebhookDeliveryState.FAILED.value
            backoff = BACKOFF_BASE_SECONDS * (2 ** (delivery.attempt_no - 1))
            delivery.next_attempt_at = datetime.now(UTC) + timedelta(seconds=backoff)
            retried += 1
    await db.flush()
    return {"delivered": delivered, "retried": retried, "dead": dead, "scanned": len(rows)}


async def replay_delivery(
    db: AsyncSession, organization_id: uuid.UUID, delivery_id: uuid.UUID
) -> WebhookDelivery:
    """Dead-letter replay (P2-19): re-queue for the next worker sweep."""
    delivery = (
        await db.execute(
            select(WebhookDelivery).where(
                WebhookDelivery.organization_id == organization_id,
                WebhookDelivery.id == delivery_id,
            )
        )
    ).scalar_one_or_none()
    if delivery is None:
        raise NotFoundError("Webhook delivery not found")
    delivery.state = WebhookDeliveryState.PENDING.value
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
) -> tuple[list[WebhookDelivery], int]:
    await get_subscription(db, organization_id, subscription_id)
    query = select(WebhookDelivery).where(
        WebhookDelivery.organization_id == organization_id,
        WebhookDelivery.subscription_id == subscription_id,
    )
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    rows = await db.execute(
        query.order_by(WebhookDelivery.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(rows.scalars().all()), total
