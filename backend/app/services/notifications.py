"""Operational notifications (M15, FR-NOT-001..005)."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.models import Notification


async def create(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    type: str,
    title: str,
    message: str | None = None,
    severity: str = "info",
    user_id: uuid.UUID | None = None,
    payload: dict | None = None,
) -> Notification:
    notification = Notification(
        organization_id=organization_id,
        user_id=user_id,
        type=type,
        severity=severity,
        title=title,
        message=message,
        payload_json=payload,
    )
    db.add(notification)
    await db.flush()

    # Rule dispatch (P2-NTF-001): every operational notification is offered
    # to the tenant's alert rules; failures there must never break the
    # business action that raised the notification.
    from app.services import notification_rules, webhooks

    try:
        await notification_rules.dispatch(db, notification)
        await webhooks.enqueue(db, notification)
    except Exception:  # noqa: BLE001 — deliberately isolate rule errors
        import logging

        logging.getLogger("app.notifications").exception(
            "Notification rule dispatch failed for %s", notification.id
        )
    return notification


def _inbox_filter(query, organization_id: uuid.UUID, user_id: uuid.UUID):
    """A user sees org-wide broadcasts plus notifications addressed to them."""
    return query.where(
        Notification.organization_id == organization_id,
        (Notification.user_id.is_(None)) | (Notification.user_id == user_id),
    )


async def inbox(
    db: AsyncSession,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    unread_only: bool,
    page: int,
    page_size: int,
) -> tuple[list[Notification], int]:
    query = _inbox_filter(select(Notification), organization_id, user_id)
    if unread_only:
        query = query.where(Notification.read_at.is_(None))
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    rows = await db.execute(
        query.order_by(Notification.created_at.desc(), Notification.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(rows.scalars().all()), total


async def unread_count(db: AsyncSession, organization_id: uuid.UUID, user_id: uuid.UUID) -> int:
    query = _inbox_filter(select(func.count()), organization_id, user_id).where(
        Notification.read_at.is_(None)
    )
    return (await db.execute(query.select_from(Notification))).scalar_one()


async def mark_read(
    db: AsyncSession, organization_id: uuid.UUID, user_id: uuid.UUID, notification_id: uuid.UUID
) -> Notification:
    result = await db.execute(
        _inbox_filter(select(Notification), organization_id, user_id).where(
            Notification.id == notification_id
        )
    )
    notification = result.scalar_one_or_none()
    if notification is None:
        raise NotFoundError("Notification not found")
    if notification.read_at is None:
        notification.read_at = datetime.now(UTC)
        await db.flush()
    return notification


async def mark_all_read(
    db: AsyncSession, organization_id: uuid.UUID, user_id: uuid.UUID
) -> int:
    rows = await db.execute(
        _inbox_filter(select(Notification), organization_id, user_id).where(
            Notification.read_at.is_(None)
        )
    )
    now = datetime.now(UTC)
    count = 0
    for notification in rows.scalars().all():
        notification.read_at = now
        count += 1
    await db.flush()
    return count
