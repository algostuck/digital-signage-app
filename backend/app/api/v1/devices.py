import secrets
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentTenantId, CurrentUser, PageParams, require_permissions
from app.db.session import get_db
from app.models import Device
from app.repositories import devices as repo
from app.repositories import locations as locations_repo
from app.schemas.devices import (
    AssignLocationRequest,
    BulkDeviceUpdate,
    DeviceCommandOut,
    DeviceDetailOut,
    DeviceGroupCreate,
    DeviceGroupMembersRequest,
    DeviceGroupOut,
    DeviceGroupUpdate,
    DeviceOut,
    DeviceUpdate,
    EnrollmentKeyOut,
    GroupActionRequest,
    GroupPreviewRequest,
    IncidentOut,
    QueueCommandRequest,
)
from app.schemas.envelope import success
from app.services import device_ops
from app.services import devices as service
from app.services import organization as org_service

router = APIRouter()


def _out(device: Device, thresholds: dict | None = None) -> dict:
    out = DeviceOut.model_validate(device)
    out.connection_status = service.connection_status(device, thresholds=thresholds)
    return out.model_dump(mode="json")


def _detail_out(device: Device, thresholds: dict | None = None) -> dict:
    out = DeviceDetailOut.model_validate(device)
    out.connection_status = service.connection_status(device, thresholds=thresholds)
    out.has_credential = device.token_hash is not None
    return out.model_dump(mode="json")


@router.get("/devices", dependencies=[require_permissions("devices.view")])
async def list_devices(
    tenant_id: CurrentTenantId,
    pagination: PageParams,
    q: str | None = Query(None, max_length=200),
    status: str | None = Query(None, max_length=20),
    platform: str | None = Query(None, max_length=50),
    group_id: uuid.UUID | None = None,
    location_id: uuid.UUID | None = None,
    include_descendants: bool = Query(True),
    db: AsyncSession = Depends(get_db),
) -> dict:
    location = None
    if location_id is not None:
        location = await locations_repo.get_by_id(db, tenant_id, location_id)
        if location is None:
            from app.core.errors import NotFoundError

            raise NotFoundError("Location not found")
    devices, total = await repo.search(
        db,
        tenant_id,
        q=q,
        status=status,
        platform=platform,
        group_id=group_id,
        location=location,
        include_descendants=include_descendants,
        page=pagination.page,
        page_size=pagination.page_size,
    )
    thresholds = await org_service.get_monitoring_thresholds(db, tenant_id)
    return success(
        [_out(d, thresholds) for d in devices],
        page=pagination.page,
        page_size=pagination.page_size,
        total=total,
    )


@router.get("/devices/enrollment-key", dependencies=[require_permissions("devices.manage")])
async def get_enrollment_key(
    tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    org = await org_service.get_organization(db, tenant_id)
    if not org.enrollment_key:
        org.enrollment_key = secrets.token_urlsafe(24)
        await db.flush()
    return success(EnrollmentKeyOut(enrollment_key=org.enrollment_key).model_dump())


@router.get("/devices/{device_id}", dependencies=[require_permissions("devices.view")])
async def get_device(
    device_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    device = await service.get_device(db, tenant_id, device_id)
    return success(_detail_out(device, await org_service.get_monitoring_thresholds(db, tenant_id)))


@router.patch("/devices/{device_id}", dependencies=[require_permissions("devices.manage")])
async def update_device(
    device_id: uuid.UUID,
    body: DeviceUpdate,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
) -> dict:
    device = await service.update_device(
        db,
        tenant_id,
        device_id,
        name=body.name,
        group_id=body.group_id,
        clear_group=body.clear_group,
        timezone=body.timezone,
        orientation=body.orientation,
        tags=[(t.key, t.value) for t in body.tags] if body.tags is not None else None,
    )
    return success(_detail_out(device, await org_service.get_monitoring_thresholds(db, tenant_id)))


@router.post("/devices/{device_id}/approve", dependencies=[require_permissions("devices.manage")])
async def approve_device(
    device_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    device = await service.approve_device(db, tenant_id, device_id)
    return success(_out(device, await org_service.get_monitoring_thresholds(db, tenant_id)))


@router.post("/devices/{device_id}/reject", dependencies=[require_permissions("devices.manage")])
async def reject_device(
    device_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    device = await service.reject_device(db, tenant_id, device_id)
    return success(_out(device, await org_service.get_monitoring_thresholds(db, tenant_id)))


@router.post(
    "/devices/{device_id}/decommission", dependencies=[require_permissions("devices.manage")]
)
async def decommission_device(
    device_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    device = await service.decommission_device(db, tenant_id, device_id)
    return success(_out(device, await org_service.get_monitoring_thresholds(db, tenant_id)))


@router.post(
    "/devices/{device_id}/reset-token", dependencies=[require_permissions("devices.manage")]
)
async def reset_device_token(
    device_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    device = await service.reset_device_token(db, tenant_id, device_id)
    return success(_detail_out(device, await org_service.get_monitoring_thresholds(db, tenant_id)))


@router.post(
    "/devices/{device_id}/assign-location",
    dependencies=[require_permissions("devices.manage")],
)
async def assign_location(
    device_id: uuid.UUID,
    body: AssignLocationRequest,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
) -> dict:
    device = await service.assign_location(
        db, tenant_id, device_id, location_id=body.location_id
    )
    return success(_out(device, await org_service.get_monitoring_thresholds(db, tenant_id)))


@router.get(
    "/devices/{device_id}/capabilities", dependencies=[require_permissions("devices.view")]
)
async def get_capabilities(
    device_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    device = await service.get_device(db, tenant_id, device_id)
    return success(_detail_out(device)["capabilities"])


@router.post(
    "/devices/{device_id}/commands",
    dependencies=[require_permissions("devices.control")],
    status_code=201,
)
async def queue_command(
    device_id: uuid.UUID,
    body: QueueCommandRequest,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
) -> dict:
    command = await service.queue_command(
        db, tenant_id, device_id, command_type=body.command_type, payload=body.payload
    )
    return success(DeviceCommandOut.model_validate(command).model_dump(mode="json"))


@router.get(
    "/devices/{device_id}/screenshots", dependencies=[require_permissions("devices.view")]
)
async def device_screenshots(
    device_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    await service.get_device(db, tenant_id, device_id)
    return success(await device_ops.list_screenshots(db, tenant_id, device_id))


@router.get(
    "/devices/{device_id}/events", dependencies=[require_permissions("devices.view")]
)
async def device_events(
    device_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """P2-MON-004: chronological timeline — player events merged with
    incident opens/recoveries, newest first."""
    from sqlalchemy import select

    from app.models import Incident
    from app.models.ops import DeviceEvent

    await service.get_device(db, tenant_id, device_id)
    events = (
        (
            await db.execute(
                select(DeviceEvent)
                .where(DeviceEvent.device_id == device_id)
                .order_by(DeviceEvent.event_at.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    incidents = (
        (
            await db.execute(
                select(Incident)
                .where(
                    Incident.organization_id == tenant_id,
                    Incident.device_id == device_id,
                )
                .order_by(Incident.opened_at.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    timeline = [
        {
            "at": e.event_at.isoformat(),
            "kind": "event",
            "type": e.event_type,
            "title": e.event_type.replace("_", " "),
            "payload": e.payload_json,
        }
        for e in events
    ]
    for incident in incidents:
        timeline.append(
            {
                "at": incident.opened_at.isoformat(),
                "kind": "incident",
                "type": incident.type,
                "title": incident.title,
                "state": incident.state,
                "payload": incident.payload_json,
            }
        )
        if incident.resolved_at is not None:
            timeline.append(
                {
                    "at": incident.resolved_at.isoformat(),
                    "kind": "recovery",
                    "type": incident.type,
                    "title": incident.resolution or "Resolved",
                    "payload": None,
                }
            )
    timeline.sort(key=lambda row: row["at"], reverse=True)
    return success(timeline[:limit])


# --- incidents (P2-MON-004) ---


@router.get("/incidents", dependencies=[require_permissions("monitoring.view")])
async def list_incidents(
    tenant_id: CurrentTenantId,
    pagination: PageParams,
    state: str | None = Query(None, max_length=20),
    db: AsyncSession = Depends(get_db),
) -> dict:
    incidents, total = await device_ops.list_incidents(
        db, tenant_id, state=state, page=pagination.page, page_size=pagination.page_size
    )
    devices = await repo.get_by_ids(
        db, tenant_id, [i.device_id for i in incidents if i.device_id]
    )
    names = {d.id: d.name for d in devices}
    rows = []
    for incident in incidents:
        out = IncidentOut.model_validate(incident)
        out.device_name = names.get(incident.device_id, "")
        rows.append(out.model_dump(mode="json"))
    return success(
        rows, page=pagination.page, page_size=pagination.page_size, total=total
    )


@router.post(
    "/incidents/{incident_id}/acknowledge",
    dependencies=[require_permissions("incidents.manage")],
)
async def acknowledge_incident(
    incident_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    incident = await device_ops.transition_incident(
        db, tenant_id, incident_id, action="acknowledge", user_id=current_user.id
    )
    return success(IncidentOut.model_validate(incident).model_dump(mode="json"))


@router.post(
    "/incidents/{incident_id}/resolve", dependencies=[require_permissions("incidents.manage")]
)
async def resolve_incident(
    incident_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    incident = await device_ops.transition_incident(
        db, tenant_id, incident_id, action="resolve", user_id=current_user.id
    )
    return success(IncidentOut.model_validate(incident).model_dump(mode="json"))


@router.get("/devices/{device_id}/commands", dependencies=[require_permissions("devices.view")])
async def list_commands(
    device_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    await service.get_device(db, tenant_id, device_id)
    commands = await repo.list_commands(db, tenant_id, device_id)
    return success(
        [DeviceCommandOut.model_validate(c).model_dump(mode="json") for c in commands]
    )


# --- groups ---


async def _group_out(db: AsyncSession, tenant_id: uuid.UUID, group) -> dict:
    out = DeviceGroupOut.model_validate(group)
    out.member_count = await device_ops.group_member_count(db, tenant_id, group)
    return out.model_dump(mode="json")


@router.get("/device-groups", dependencies=[require_permissions("devices.view")])
async def list_groups(tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)) -> dict:
    groups = await repo.list_groups(db, tenant_id)
    return success([await _group_out(db, tenant_id, g) for g in groups])


@router.post(
    "/device-groups/preview", dependencies=[require_permissions("devices.view")]
)
async def preview_group(
    body: GroupPreviewRequest, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    member_ids = await device_ops.preview_rule_member_ids(db, tenant_id, body.rule_json)
    sample = await repo.get_by_ids(db, tenant_id, member_ids[:10])
    return success(
        {"count": len(member_ids), "sample": [d.name for d in sample]}
    )


@router.post(
    "/device-groups", dependencies=[require_permissions("devices.manage")], status_code=201
)
async def create_group(
    body: DeviceGroupCreate, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    group = await service.create_group(
        db,
        tenant_id,
        name=body.name,
        description=body.description,
        group_type=body.group_type,
        rule_json=body.rule_json,
    )
    return success(await _group_out(db, tenant_id, group))


@router.patch("/device-groups/{group_id}", dependencies=[require_permissions("devices.manage")])
async def update_group(
    group_id: uuid.UUID,
    body: DeviceGroupUpdate,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
) -> dict:
    group = await service.update_group(
        db,
        tenant_id,
        group_id,
        name=body.name,
        description=body.description,
        rule_json=body.rule_json,
    )
    return success(await _group_out(db, tenant_id, group))


@router.post(
    "/device-groups/{group_id}/actions",
    dependencies=[require_permissions("devices.control")],
)
async def bulk_group_action(
    group_id: uuid.UUID,
    body: GroupActionRequest,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await device_ops.bulk_group_command(
        db, tenant_id, group_id, command_type=body.command_type, payload=body.payload
    )
    return success(result)


@router.post("/devices/bulk", dependencies=[require_permissions("devices.manage")])
async def bulk_update_devices(
    body: BulkDeviceUpdate, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    updated = await device_ops.bulk_update_devices(
        db,
        tenant_id,
        body.device_ids,
        group_id=body.group_id,
        clear_group=body.clear_group,
        location_id=body.location_id,
        clear_location=body.clear_location,
        add_tags=[(t.key, t.value) for t in body.add_tags] if body.add_tags else None,
        remove_tags=[(t.key, t.value) for t in body.remove_tags] if body.remove_tags else None,
    )
    return success({"updated": updated})


@router.delete("/device-groups/{group_id}", dependencies=[require_permissions("devices.manage")])
async def delete_group(
    group_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    await service.delete_group(db, tenant_id, group_id)
    return success({"deleted": True})


@router.post(
    "/device-groups/{group_id}/members", dependencies=[require_permissions("devices.manage")]
)
async def assign_members(
    group_id: uuid.UUID,
    body: DeviceGroupMembersRequest,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
) -> dict:
    count = await service.assign_group_members(db, tenant_id, group_id, body.device_ids)
    return success({"assigned": count})
