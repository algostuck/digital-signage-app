"""Audit trail service (M16, FR-AUD-001..004).

record() reads actor/request/IP from request context vars set by middleware
and the auth dependency, so services call it with just the business facts.
"""

import datetime as dt
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import client_ip_ctx, request_id_ctx, user_id_ctx
from app.models import AuditLog


async def record(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID | str | None = None,
    before: dict | None = None,
    after: dict | None = None,
    user_id: uuid.UUID | None = None,
) -> None:
    db.add(
        AuditLog(
            organization_id=organization_id,
            user_id=user_id or user_id_ctx.get(),
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            before_json=before,
            after_json=after,
            ip_address=client_ip_ctx.get(),
            request_id=request_id_ctx.get(),
        )
    )
    await db.flush()


async def search(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    action: str | None,
    entity_type: str | None,
    user_id: uuid.UUID | None,
    date_from: dt.date | None,
    date_to: dt.date | None,
    page: int,
    page_size: int,
) -> tuple[list[AuditLog], int]:
    query = select(AuditLog).where(AuditLog.organization_id == organization_id)
    if action:
        query = query.where(AuditLog.action == action)
    if entity_type:
        query = query.where(AuditLog.entity_type == entity_type)
    if user_id:
        query = query.where(AuditLog.user_id == user_id)
    if date_from:
        query = query.where(
            AuditLog.created_at >= dt.datetime.combine(date_from, dt.time.min, dt.UTC)
        )
    if date_to:
        query = query.where(
            AuditLog.created_at < dt.datetime.combine(
                date_to + dt.timedelta(days=1), dt.time.min, dt.UTC
            )
        )
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    rows = await db.execute(
        query.order_by(AuditLog.created_at.desc(), AuditLog.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(rows.scalars().all()), total
