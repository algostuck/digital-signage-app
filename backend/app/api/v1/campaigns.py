import datetime as dt
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentTenantId, CurrentUser, PageParams, require_permissions
from app.core.errors import ValidationAppError
from app.db.session import get_db
from app.models import Campaign
from app.schemas.campaigns import (
    CalendarEventOut,
    CalendarOut,
    CampaignCreate,
    CampaignDetailOut,
    CampaignOut,
    CampaignUpdate,
    ConflictCheckRequest,
    EffectiveDeviceOut,
    ScheduleCreate,
    ScheduleOut,
    ScheduleUpdate,
    SetTargetsRequest,
    TargetOut,
    TargetsPreviewRequest,
    VariantCreate,
    VariantOut,
)
from app.schemas.envelope import success
from app.services import campaigns as service
from app.services import publishing, scheduling

router = APIRouter()

MAX_CALENDAR_DAYS = 62


def _schedule_out(schedule, today: dt.date) -> dict:
    out = ScheduleOut.model_validate(schedule)
    out.expired = scheduling.is_schedule_expired(schedule, today)
    return out.model_dump(mode="json")


def _summary(campaign: Campaign) -> dict:
    out = CampaignOut.model_validate(campaign)
    out.schedule_count = len(campaign.schedules)
    return out.model_dump(mode="json")


def _detail(campaign: Campaign) -> dict:
    today = dt.date.today()
    out = CampaignDetailOut.model_validate(campaign)
    out.schedule_count = len(campaign.schedules)
    result = out.model_dump(mode="json")
    result["schedules"] = [_schedule_out(s, today) for s in campaign.schedules]
    result["targets"] = [
        TargetOut.model_validate(t).model_dump(mode="json") for t in campaign.targets
    ]
    result["variants"] = [
        VariantOut.model_validate(v).model_dump(mode="json") for v in campaign.variants
    ]
    return result


@router.get("/campaigns", dependencies=[require_permissions("campaigns.view")])
async def list_campaigns(
    tenant_id: CurrentTenantId,
    pagination: PageParams,
    q: str | None = Query(None, max_length=200),
    status: str | None = Query(None, max_length=30),
    db: AsyncSession = Depends(get_db),
) -> dict:
    campaigns, total = await service.search_campaigns(
        db, tenant_id, q=q, status=status, page=pagination.page, page_size=pagination.page_size
    )
    return success(
        [_summary(c) for c in campaigns],
        page=pagination.page,
        page_size=pagination.page_size,
        total=total,
    )


@router.post("/campaigns", dependencies=[require_permissions("campaigns.manage")], status_code=201)
async def create_campaign(
    body: CampaignCreate, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    campaign = await service.create_campaign(
        db,
        tenant_id,
        name=body.name,
        description=body.description,
        priority=body.priority,
        playlist_id=body.playlist_id,
        layout_id=body.layout_id,
    )
    return success(_detail(campaign))


@router.get("/campaigns/{campaign_id}", dependencies=[require_permissions("campaigns.view")])
async def get_campaign(
    campaign_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    campaign = await service.get_campaign(db, tenant_id, campaign_id)
    return success(_detail(campaign))


@router.patch("/campaigns/{campaign_id}", dependencies=[require_permissions("campaigns.manage")])
async def update_campaign(
    campaign_id: uuid.UUID,
    body: CampaignUpdate,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
) -> dict:
    campaign = await service.update_campaign(
        db,
        tenant_id,
        campaign_id,
        name=body.name,
        description=body.description,
        priority=body.priority,
        playlist_id=body.playlist_id,
        layout_id=body.layout_id,
        clear_playlist=body.clear_playlist,
        clear_layout=body.clear_layout,
    )
    return success(_detail(campaign))


@router.delete("/campaigns/{campaign_id}", dependencies=[require_permissions("campaigns.manage")])
async def archive_campaign(
    campaign_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    campaign = await service.archive_campaign(db, tenant_id, campaign_id)
    return success(_summary(campaign))


@router.post(
    "/campaigns/{campaign_id}/restore", dependencies=[require_permissions("campaigns.manage")]
)
async def restore_campaign(
    campaign_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    campaign = await service.restore_campaign(db, tenant_id, campaign_id)
    return success(_summary(campaign))


# --- variants (P2-CAM-001) ---


@router.get(
    "/campaigns/{campaign_id}/variants", dependencies=[require_permissions("campaigns.view")]
)
async def list_variants(
    campaign_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    campaign = await service.get_campaign(db, tenant_id, campaign_id)
    return success(
        [VariantOut.model_validate(v).model_dump(mode="json") for v in campaign.variants]
    )


@router.post(
    "/campaigns/{campaign_id}/variants",
    dependencies=[require_permissions("campaigns.manage")],
    status_code=201,
)
async def create_variant(
    campaign_id: uuid.UUID,
    body: VariantCreate,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
) -> dict:
    campaign = await service.create_variant(
        db,
        tenant_id,
        campaign_id,
        name=body.name,
        layout_id=body.layout_id,
        playlist_id=body.playlist_id,
        priority=body.priority,
        targets=[t.model_dump(mode="json") for t in body.targets],
    )
    return success(_detail(campaign))


@router.delete(
    "/campaigns/{campaign_id}/variants/{variant_id}",
    dependencies=[require_permissions("campaigns.manage")],
)
async def delete_variant(
    campaign_id: uuid.UUID,
    variant_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
) -> dict:
    campaign = await service.delete_variant(db, tenant_id, campaign_id, variant_id)
    return success(_detail(campaign))


# --- targeting & lifecycle (1I) ---


@router.post(
    "/campaigns/{campaign_id}/targets", dependencies=[require_permissions("campaigns.manage")]
)
async def set_targets(
    campaign_id: uuid.UUID,
    body: SetTargetsRequest,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
) -> dict:
    campaign = await publishing.set_targets(
        db, tenant_id, campaign_id, [t.model_dump() for t in body.targets]
    )
    return success(_detail(campaign))


@router.get(
    "/campaigns/{campaign_id}/effective-targets",
    dependencies=[require_permissions("campaigns.view")],
)
async def effective_targets(
    campaign_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    devices = await publishing.effective_devices(db, tenant_id, campaign_id)
    return success(
        [
            EffectiveDeviceOut(
                id=d.id, name=d.name, serial_no=d.serial_no, platform=d.platform
            ).model_dump(mode="json")
            for d in devices
        ]
    )


@router.post(
    "/campaigns/{campaign_id}/targets/preview",
    dependencies=[require_permissions("campaigns.view")],
)
async def preview_targets(
    campaign_id: uuid.UUID,
    body: TargetsPreviewRequest,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Resolves a proposed target set without saving it (P2-10 preview)."""
    from types import SimpleNamespace

    from app.repositories import devices as devices_repo
    from app.services import targeting

    await service.get_campaign(db, tenant_id, campaign_id)
    proposed = [
        SimpleNamespace(
            target_type=t.target_type,
            target_id=t.target_id,
            include_descendants=t.include_descendants,
            is_exclusion=t.is_exclusion,
        )
        for t in body.targets
    ]
    device_ids = await targeting.resolve_effective_devices(db, tenant_id, proposed)
    sample = await devices_repo.get_by_ids(db, tenant_id, device_ids[:10])
    return success(
        {
            "count": len(device_ids),
            "sample": [{"id": str(d.id), "name": d.name} for d in sample],
        }
    )


@router.post(
    "/campaigns/{campaign_id}/submit-approval",
    dependencies=[require_permissions("campaigns.manage")],
)
async def submit_approval(
    campaign_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    campaign = await publishing.transition_campaign(db, tenant_id, campaign_id, "submit-approval")
    return success(_detail(campaign))


@router.post(
    "/campaigns/{campaign_id}/approve", dependencies=[require_permissions("campaigns.approve")]
)
async def approve(
    campaign_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Legacy per-entity path: delegates into the approval engine so the
    workflow record, maker-checker policy and action trail stay consistent."""
    from app.services import approvals

    await approvals.decide_for_entity(
        db, tenant_id, "campaign", campaign_id, actor=user, approve=True
    )
    campaign = await service.get_campaign(db, tenant_id, campaign_id)
    return success(_detail(campaign))


@router.post(
    "/campaigns/{campaign_id}/reject", dependencies=[require_permissions("campaigns.approve")]
)
async def reject(
    campaign_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.services import approvals

    await approvals.decide_for_entity(
        db, tenant_id, "campaign", campaign_id, actor=user, approve=False
    )
    campaign = await service.get_campaign(db, tenant_id, campaign_id)
    return success(_detail(campaign))


@router.post(
    "/campaigns/{campaign_id}/pause", dependencies=[require_permissions("campaigns.publish")]
)
async def pause(
    campaign_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    campaign = await publishing.transition_campaign(db, tenant_id, campaign_id, "pause")
    return success(_detail(campaign))


@router.post(
    "/campaigns/{campaign_id}/resume", dependencies=[require_permissions("campaigns.publish")]
)
async def resume(
    campaign_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    campaign = await publishing.transition_campaign(db, tenant_id, campaign_id, "resume")
    return success(_detail(campaign))


@router.post(
    "/campaigns/{campaign_id}/publish", dependencies=[require_permissions("campaigns.publish")]
)
async def publish(
    campaign_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    from app.api.v1.deployments import deployment_out

    deployment = await publishing.publish_campaign(db, tenant_id, campaign_id)
    return success(await deployment_out(db, tenant_id, deployment))


# --- schedules ---


@router.get("/schedules", dependencies=[require_permissions("schedules.view")])
async def list_schedules(
    tenant_id: CurrentTenantId,
    campaign_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    schedules = await service.list_schedules(db, tenant_id, campaign_id=campaign_id)
    today = dt.date.today()
    return success([_schedule_out(s, today) for s in schedules])


@router.post("/schedules", dependencies=[require_permissions("schedules.manage")], status_code=201)
async def create_schedule(
    body: ScheduleCreate, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    schedule = await service.create_schedule(
        db,
        tenant_id,
        campaign_id=body.campaign_id,
        name=body.name,
        kind=body.kind,
        start_date=body.start_date,
        end_date=body.end_date,
        start_time=body.start_time,
        end_time=body.end_time,
        days_of_week=body.days_of_week,
        recurrence=body.recurrence_json,
        exception_dates=body.exception_dates_json,
        timezone=body.timezone,
        priority=body.priority,
    )
    return success(_schedule_out(schedule, dt.date.today()))


@router.patch("/schedules/{schedule_id}", dependencies=[require_permissions("schedules.manage")])
async def update_schedule(
    schedule_id: uuid.UUID,
    body: ScheduleUpdate,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
) -> dict:
    changes = body.model_dump(exclude_unset=True)
    schedule = await service.update_schedule(db, tenant_id, schedule_id, **changes)
    return success(_schedule_out(schedule, dt.date.today()))


@router.delete("/schedules/{schedule_id}", dependencies=[require_permissions("schedules.manage")])
async def delete_schedule(
    schedule_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    await service.delete_schedule(db, tenant_id, schedule_id)
    return success({"deleted": True})


@router.post("/schedules/conflicts", dependencies=[require_permissions("schedules.view")])
async def check_conflicts(
    body: ConflictCheckRequest, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    """Dry-run (P2-SCH-004): expands a proposed schedule against the whole
    calendar and reports every overlap with the deterministic winner —
    before anything is saved or published."""
    import datetime as dtm
    from types import SimpleNamespace

    from app.services.campaigns import _validate_schedule_fields

    campaign = await service.get_campaign(db, tenant_id, body.campaign_id)
    _validate_schedule_fields(
        start_date=body.start_date,
        end_date=body.end_date,
        days_of_week=body.days_of_week,
        timezone=body.timezone,
        kind=body.kind,
        recurrence=body.recurrence_json,
        exception_dates=body.exception_dates_json,
    )
    range_start = body.range_start or body.start_date or dtm.date.today()
    default_end = range_start + dtm.timedelta(days=31)
    range_end = body.range_end or (
        min(body.end_date, default_end) if body.end_date else default_end
    )
    if range_end < range_start:
        raise ValidationAppError("range_end must not be before range_start", field="range_end")
    if (range_end - range_start).days > MAX_CALENDAR_DAYS:
        raise ValidationAppError(
            f"Conflict check range is limited to {MAX_CALENDAR_DAYS} days", field="range_end"
        )

    proposal_schedule = SimpleNamespace(
        id="proposed",
        name="(proposed)",
        kind=body.kind,
        start_date=body.start_date,
        end_date=body.end_date,
        start_time=body.start_time,
        end_time=body.end_time,
        days_of_week=body.days_of_week,
        recurrence_json=body.recurrence_json,
        exception_dates_json=body.exception_dates_json,
        timezone=body.timezone,
        priority=body.priority,
    )
    proposal_campaign = SimpleNamespace(
        id=campaign.id,
        name=campaign.name,
        priority=campaign.priority,
        created_at=campaign.created_at,
        schedules=[proposal_schedule],
    )
    existing = await service.campaigns_with_schedules(db, tenant_id)
    events = scheduling.expand_calendar(existing, range_start, range_end)
    events += scheduling.expand_calendar([proposal_campaign], range_start, range_end)
    report = [
        row
        for row in scheduling.overlap_report(events)
        if any(c["campaign_id"] == str(campaign.id) for c in row["campaigns"])
    ]
    return success(
        {
            "range_start": range_start.isoformat(),
            "range_end": range_end.isoformat(),
            "overlaps": report,
            "conflict_count": sum(1 for row in report if row["conflict"]),
        }
    )


@router.get("/schedules/calendar", dependencies=[require_permissions("schedules.view")])
@router.get("/calendar", dependencies=[require_permissions("schedules.view")])
async def get_calendar(
    tenant_id: CurrentTenantId,
    range_start: dt.date = Query(alias="from"),
    range_end: dt.date = Query(alias="to"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if range_end < range_start:
        raise ValidationAppError("'to' must not be before 'from'", field="to")
    if (range_end - range_start).days > MAX_CALENDAR_DAYS:
        raise ValidationAppError(
            f"Calendar range is limited to {MAX_CALENDAR_DAYS} days", field="to"
        )
    campaigns = await service.campaigns_with_schedules(db, tenant_id)
    events = scheduling.expand_calendar(campaigns, range_start, range_end)
    conflicts = scheduling.detect_conflicts(events)
    out = CalendarOut(
        range_start=range_start,
        range_end=range_end,
        events=[CalendarEventOut.model_validate(vars(e)) for e in events],
        conflict_count=len(conflicts),
    )
    return success(out.model_dump(mode="json"))
