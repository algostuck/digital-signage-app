"""Notification rules engine (P2-NTF-001..003).

Dispatch rides on notifications.create(): every operational notification is
matched against the tenant's active rules; each matching channel produces a
delivery row. In-app is implicit (the notification itself) and recorded as
delivered evidence. Email is sent through the pluggable provider (a logging
provider in dev — real SMTP is a deployment concern, same adapter). Webhook
deliveries are queued and pushed by the maintenance sweep with retries —
never inline in the request path.
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, ValidationAppError
from app.integrations.fetch import FetchError, assert_public_url, check_url_shape
from app.models import Notification, NotificationDelivery, NotificationRule
from app.models.notification_rule import DeliveryChannel, DeliveryState

logger = logging.getLogger("app.notification_rules")

# Types the engine itself produces — never re-matched, even by wildcard
# rules, so escalations cannot cascade.
_ENGINE_TYPES = {"ESCALATION"}

KNOWN_EVENT_TYPES: dict[str, str] = {
    "DEVICE_OFFLINE": "Device went offline",
    "DEVICE_RECOVERED": "Device recovered",
    "DEVICE_STORAGE": "Device storage above threshold",
    "APPROVAL_REQUESTED": "Approval requested",
    "APPROVAL_DECIDED": "Approval decided",
    "ROLLOUT_STOPPED": "OTA rollout stopped",
    "ROLLOUT_COMPLETED": "OTA rollout completed",
    "ROLLOUT_ROLLED_BACK": "OTA release rolled back",
    "*": "Any event",
}

MAX_WEBHOOK_ATTEMPTS = 3
_SEVERITIES = ("info", "warning", "critical")


def validate_rule_fields(
    *, event_type: str, condition: dict | None, channels: list, escalation_minutes: int | None
) -> None:
    if event_type not in KNOWN_EVENT_TYPES:
        raise ValidationAppError(f"Unknown event_type '{event_type}'", field="event_type")
    if condition is not None:
        if not isinstance(condition, dict) or set(condition) - {"severity"}:
            raise ValidationAppError(
                "condition_json supports only {'severity': [...]}", field="condition_json"
            )
        severities = condition.get("severity")
        if (
            not isinstance(severities, list)
            or not severities
            or any(s not in _SEVERITIES for s in severities)
        ):
            raise ValidationAppError(
                f"condition severity entries must be one of {_SEVERITIES}",
                field="condition_json",
            )
    if not isinstance(channels, list) or not channels or len(channels) > 10:
        raise ValidationAppError("channels_json needs 1..10 channel entries", field="channels_json")
    for entry in channels:
        channel = entry.get("channel") if isinstance(entry, dict) else None
        if channel not in {c.value for c in DeliveryChannel}:
            raise ValidationAppError(f"Unknown channel '{channel}'", field="channels_json")
        recipient = entry.get("recipient")
        if channel == DeliveryChannel.EMAIL.value:
            if not recipient or "@" not in str(recipient):
                raise ValidationAppError(
                    "email channels need a recipient address", field="channels_json"
                )
        if channel == DeliveryChannel.WEBHOOK.value:
            if not recipient or not str(recipient).startswith(("http://", "https://")):
                raise ValidationAppError(
                    "webhook channels need an http(s) recipient URL", field="channels_json"
                )
            try:
                check_url_shape(str(entry.get("recipient")))
            except FetchError as exc:
                raise ValidationAppError(str(exc), field="channels_json") from exc
    if escalation_minutes is not None and not 1 <= escalation_minutes <= 1440:
        raise ValidationAppError("escalation_minutes must be 1..1440", field="escalation_minutes")


# --- CRUD ---


async def list_rules(db: AsyncSession, organization_id: uuid.UUID) -> list[NotificationRule]:
    rows = await db.execute(
        select(NotificationRule)
        .where(NotificationRule.organization_id == organization_id)
        .order_by(NotificationRule.name)
    )
    return list(rows.scalars().all())


async def get_rule(
    db: AsyncSession, organization_id: uuid.UUID, rule_id: uuid.UUID
) -> NotificationRule:
    rule = (
        await db.execute(
            select(NotificationRule).where(
                NotificationRule.organization_id == organization_id,
                NotificationRule.id == rule_id,
            )
        )
    ).scalar_one_or_none()
    if rule is None:
        raise NotFoundError("Notification rule not found")
    return rule


async def create_rule(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    name: str,
    event_type: str,
    condition: dict | None,
    channels: list,
    escalation_minutes: int | None,
) -> NotificationRule:
    validate_rule_fields(
        event_type=event_type,
        condition=condition,
        channels=channels,
        escalation_minutes=escalation_minutes,
    )
    existing = await db.execute(
        select(NotificationRule.id).where(
            NotificationRule.organization_id == organization_id,
            NotificationRule.name == name,
        )
    )
    if existing.scalar_one_or_none() is not None:
        from app.core.errors import ConflictError

        raise ConflictError("A rule with this name already exists", field="name")
    rule = NotificationRule(
        organization_id=organization_id,
        name=name,
        event_type=event_type,
        condition_json=condition,
        channels_json=channels,
        escalation_minutes=escalation_minutes,
        active=True,
    )
    db.add(rule)
    await db.flush()

    from app.services import audit

    await audit.record(
        db,
        organization_id,
        action="NOTIFICATION_RULE_CREATED",
        entity_type="notification_rule",
        entity_id=rule.id,
        after={"name": name, "event_type": event_type, "channels": channels},
    )
    return rule


async def update_rule(
    db: AsyncSession,
    organization_id: uuid.UUID,
    rule_id: uuid.UUID,
    **changes,
) -> NotificationRule:
    rule = await get_rule(db, organization_id, rule_id)
    fields = {
        "name",
        "event_type",
        "condition_json",
        "channels_json",
        "escalation_minutes",
        "active",
    }
    for field, value in changes.items():
        if field in fields:
            setattr(rule, field, value)
    validate_rule_fields(
        event_type=rule.event_type,
        condition=rule.condition_json,
        channels=rule.channels_json,
        escalation_minutes=rule.escalation_minutes,
    )
    await db.flush()
    return rule


async def delete_rule(db: AsyncSession, organization_id: uuid.UUID, rule_id: uuid.UUID) -> None:
    rule = await get_rule(db, organization_id, rule_id)
    await db.delete(rule)
    await db.flush()


# --- dispatch (called from notifications.create) ---


def _matches(rule: NotificationRule, notification: Notification) -> bool:
    if rule.event_type not in ("*", notification.type):
        return False
    severities = (rule.condition_json or {}).get("severity")
    if severities and notification.severity not in severities:
        return False
    return True


async def dispatch(db: AsyncSession, notification: Notification) -> int:
    """Creates delivery rows for every matching active rule/channel.
    In-app + email complete synchronously; webhooks stay pending for the
    async sweep."""
    if notification.type in _ENGINE_TYPES:
        return 0
    rules = (
        await db.execute(
            select(NotificationRule).where(
                NotificationRule.organization_id == notification.organization_id,
                NotificationRule.active.is_(True),
            )
        )
    ).scalars()
    created = 0
    now = datetime.now(UTC)
    for rule in rules:
        if not _matches(rule, notification):
            continue
        for entry in rule.channels_json:
            channel = entry["channel"]
            delivery = NotificationDelivery(
                organization_id=notification.organization_id,
                rule_id=rule.id,
                notification_id=notification.id,
                channel=channel,
                recipient=str(entry.get("recipient") or "org-inbox"),
            )
            if channel == DeliveryChannel.IN_APP.value:
                delivery.state = DeliveryState.DELIVERED.value
                delivery.attempts = 1
                delivery.delivered_at = now
            elif channel == DeliveryChannel.EMAIL.value:
                from app.integrations.email import get_email_provider
                from app.models import Organization
                from app.services.white_label import sender_identity

                org = await db.get(Organization, notification.organization_id)
                sent = get_email_provider().send(
                    to=delivery.recipient,
                    subject=f"[{notification.severity.upper()}] {notification.title}",
                    body=notification.message or notification.title,
                    from_addr=sender_identity(org) if org else None,
                )
                delivery.attempts = 1
                if sent:
                    delivery.state = DeliveryState.DELIVERED.value
                    delivery.delivered_at = now
                else:
                    delivery.state = DeliveryState.FAILED.value
                    delivery.last_error = "email provider rejected the message"
            # webhook: stays pending for process_pending_deliveries.
            db.add(delivery)
            created += 1
    if created:
        await db.flush()
    return created


async def _post_webhook(url: str, payload: dict) -> None:
    """Isolated for tests; raises on any failure. The destination is
    resolve-checked at send time and redirects are never followed."""
    try:
        assert_public_url(url)
    except FetchError as exc:
        raise httpx.HTTPError(f"Blocked destination: {exc}") from exc
    async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()


async def process_pending_deliveries(db: AsyncSession, *, limit: int = 50) -> dict:
    """Maintenance sweep: pushes pending webhook deliveries with retries."""
    rows = (
        await db.execute(
            select(NotificationDelivery, Notification)
            .join(Notification, Notification.id == NotificationDelivery.notification_id)
            .where(
                NotificationDelivery.state == DeliveryState.PENDING.value,
                NotificationDelivery.channel == DeliveryChannel.WEBHOOK.value,
            )
            .order_by(NotificationDelivery.created_at)
            .limit(limit)
        )
    ).all()
    delivered = failed = 0
    now = datetime.now(UTC)
    for delivery, notification in rows:
        delivery.attempts += 1
        try:
            await _post_webhook(
                delivery.recipient,
                {
                    "notification_id": str(notification.id),
                    "type": notification.type,
                    "severity": notification.severity,
                    "title": notification.title,
                    "message": notification.message,
                    "payload": notification.payload_json,
                    "created_at": notification.created_at.isoformat(),
                },
            )
            delivery.state = DeliveryState.DELIVERED.value
            delivery.delivered_at = now
            delivery.last_error = None
            delivered += 1
        except Exception as exc:  # noqa: BLE001 — any transport error counts as a failed attempt
            delivery.last_error = str(exc)[:500]
            if delivery.attempts >= MAX_WEBHOOK_ATTEMPTS:
                delivery.state = DeliveryState.FAILED.value
                failed += 1
            logger.warning(
                "Webhook delivery %s attempt %s failed: %s",
                delivery.id,
                delivery.attempts,
                exc,
            )
    await db.flush()
    return {"delivered": delivered, "failed": failed, "scanned": len(rows)}


async def process_escalations(db: AsyncSession) -> int:
    """P2-NTF-002: a rule-matched notification still unread past the rule's
    escalation delay produces one critical ESCALATION notification."""
    from app.services import notifications as notifications_service

    rules = (
        await db.execute(
            select(NotificationRule).where(
                NotificationRule.active.is_(True),
                NotificationRule.escalation_minutes.isnot(None),
            )
        )
    ).scalars()
    escalated = 0
    now = datetime.now(UTC)
    for rule in rules:
        cutoff = now - timedelta(minutes=rule.escalation_minutes)
        overdue = (
            await db.execute(
                select(Notification)
                .join(
                    NotificationDelivery,
                    NotificationDelivery.notification_id == Notification.id,
                )
                .where(
                    NotificationDelivery.rule_id == rule.id,
                    Notification.read_at.is_(None),
                    Notification.created_at <= cutoff,
                )
                .distinct()
            )
        ).scalars()
        for notification in overdue:
            already = (
                await db.execute(
                    select(func.count()).where(
                        Notification.organization_id == notification.organization_id,
                        Notification.type == "ESCALATION",
                        Notification.payload_json.isnot(None),
                    )
                )
            ).scalar_one()
            # Cheap JSON filtering is engine-specific; check candidates in
            # Python (escalations are rare).
            if already:
                candidates = (
                    await db.execute(
                        select(Notification).where(
                            Notification.organization_id == notification.organization_id,
                            Notification.type == "ESCALATION",
                        )
                    )
                ).scalars()
                if any(
                    (c.payload_json or {}).get("source_notification_id") == str(notification.id)
                    for c in candidates
                ):
                    continue
            await notifications_service.create(
                db,
                notification.organization_id,
                type="ESCALATION",
                severity="critical",
                title=f"ESCALATED: {notification.title}",
                message=(
                    f"Unacknowledged for over {rule.escalation_minutes} minutes "
                    f"(rule '{rule.name}')."
                ),
                payload={
                    "source_notification_id": str(notification.id),
                    "rule_id": str(rule.id),
                },
            )
            escalated += 1
            logger.warning("Escalated notification %s via rule %s", notification.id, rule.id)
    await db.flush()
    return escalated


async def list_deliveries(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    rule_id: uuid.UUID | None,
    page: int,
    page_size: int,
) -> tuple[list[tuple[NotificationDelivery, Notification]], int]:
    query = (
        select(NotificationDelivery, Notification)
        .join(Notification, Notification.id == NotificationDelivery.notification_id)
        .where(NotificationDelivery.organization_id == organization_id)
    )
    if rule_id is not None:
        query = query.where(NotificationDelivery.rule_id == rule_id)
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    rows = await db.execute(
        query.order_by(NotificationDelivery.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(rows.all()), total
