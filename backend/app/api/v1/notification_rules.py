"""Notification rules API (P2-18): event → channels, escalation, evidence."""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentTenantId, PageParams, require_permissions
from app.db.session import get_db
from app.schemas.envelope import success
from app.schemas.notification_rules import DeliveryOut, RuleCreate, RuleOut, RuleUpdate
from app.services import notification_rules as service

router = APIRouter()


def _rule_out(rule) -> dict:
    return RuleOut.model_validate(rule).model_dump(mode="json")


@router.get("/notification-events", dependencies=[require_permissions("notifications.view")])
async def event_catalogue() -> dict:
    return success(
        [
            {"event_type": event_type, "label": label}
            for event_type, label in service.KNOWN_EVENT_TYPES.items()
        ]
    )


@router.get("/notification-rules", dependencies=[require_permissions("notifications.view")])
async def list_rules(tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)) -> dict:
    return success([_rule_out(r) for r in await service.list_rules(db, tenant_id)])


@router.post(
    "/notification-rules",
    dependencies=[require_permissions("settings.manage")],
    status_code=201,
)
async def create_rule(
    body: RuleCreate, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    rule = await service.create_rule(
        db,
        tenant_id,
        name=body.name,
        event_type=body.event_type,
        condition=body.condition_json,
        channels=[c.model_dump(mode="json") for c in body.channels_json],
        escalation_minutes=body.escalation_minutes,
    )
    return success(_rule_out(rule))


@router.patch(
    "/notification-rules/{rule_id}", dependencies=[require_permissions("settings.manage")]
)
async def update_rule(
    rule_id: uuid.UUID,
    body: RuleUpdate,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
) -> dict:
    changes = body.model_dump(exclude_unset=True)
    if "channels_json" in changes and changes["channels_json"] is not None:
        changes["channels_json"] = [dict(c) for c in changes["channels_json"]]
    rule = await service.update_rule(db, tenant_id, rule_id, **changes)
    return success(_rule_out(rule))


@router.delete(
    "/notification-rules/{rule_id}", dependencies=[require_permissions("settings.manage")]
)
async def delete_rule(
    rule_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    await service.delete_rule(db, tenant_id, rule_id)
    return success({"deleted": True})


@router.get(
    "/notification-deliveries", dependencies=[require_permissions("notifications.view")]
)
async def list_deliveries(
    tenant_id: CurrentTenantId,
    pagination: PageParams,
    rule_id: uuid.UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    rows, total = await service.list_deliveries(
        db, tenant_id, rule_id=rule_id, page=pagination.page, page_size=pagination.page_size
    )
    out = []
    for delivery, notification in rows:
        entry = DeliveryOut.model_validate(delivery)
        entry.notification_title = notification.title
        entry.notification_type = notification.type
        out.append(entry.model_dump(mode="json"))
    return success(out, page=pagination.page, page_size=pagination.page_size, total=total)
