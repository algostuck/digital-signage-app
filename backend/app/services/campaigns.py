"""Campaign (minimal, M09) and schedule (M10) management.

Targeting, approval and publishing land in milestone 1I; this slice owns the
campaign shell plus the full schedule CRUD and validation.
"""

import datetime as dt
import logging
import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BusinessRuleError, NotFoundError, ValidationAppError
from app.models import Campaign, CampaignVariant, CampaignVariantTarget, Schedule
from app.models.campaign import CampaignStatus, ScheduleKind, TargetType
from app.repositories import layouts as layouts_repo
from app.repositories import playlists as playlists_repo
from app.services.organization import validate_timezone

logger = logging.getLogger("app.campaigns")


async def get_campaign(
    db: AsyncSession, organization_id: uuid.UUID, campaign_id: uuid.UUID
) -> Campaign:
    result = await db.execute(
        select(Campaign).where(
            Campaign.organization_id == organization_id, Campaign.id == campaign_id
        )
    )
    campaign = result.scalar_one_or_none()
    if campaign is None:
        raise NotFoundError("Campaign not found")
    return campaign


async def search_campaigns(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    q: str | None,
    status: str | None,
    page: int,
    page_size: int,
) -> tuple[list[Campaign], int]:
    query = select(Campaign).where(Campaign.organization_id == organization_id)
    if q:
        pattern = f"%{q.lower()}%"
        query = query.where(
            or_(
                func.lower(Campaign.name).like(pattern),
                func.lower(Campaign.description).like(pattern),
            )
        )
    if status:
        query = query.where(Campaign.status == status)
    else:
        query = query.where(Campaign.status != CampaignStatus.ARCHIVED.value)
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    rows = await db.execute(
        query.order_by(Campaign.updated_at.desc(), Campaign.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(rows.scalars().all()), total


async def _validate_bindings(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    playlist_id: uuid.UUID | None,
    layout_id: uuid.UUID | None,
) -> None:
    if playlist_id is not None:
        if await playlists_repo.get_by_id(db, organization_id, playlist_id) is None:
            raise NotFoundError("Playlist not found")
    if layout_id is not None:
        if await layouts_repo.get_by_id(db, organization_id, layout_id) is None:
            raise NotFoundError("Layout not found")


async def create_campaign(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    name: str,
    description: str | None,
    priority: int,
    playlist_id: uuid.UUID | None,
    layout_id: uuid.UUID | None,
) -> Campaign:
    from app.services import entitlements as entitlements_service

    await entitlements_service.ensure_subscription_allows(db, organization_id, "campaign_create")
    await _validate_bindings(db, organization_id, playlist_id=playlist_id, layout_id=layout_id)
    campaign = Campaign(
        organization_id=organization_id,
        name=name,
        description=description,
        priority=priority,
        playlist_id=playlist_id,
        layout_id=layout_id,
        status=CampaignStatus.DRAFT.value,
    )
    db.add(campaign)
    await db.flush()
    await db.refresh(campaign, ["schedules", "targets", "variants"])
    logger.info("Campaign %s created", campaign.id)
    return campaign


async def update_campaign(
    db: AsyncSession,
    organization_id: uuid.UUID,
    campaign_id: uuid.UUID,
    *,
    name: str | None = None,
    description: str | None = None,
    priority: int | None = None,
    playlist_id: uuid.UUID | None = None,
    layout_id: uuid.UUID | None = None,
    clear_playlist: bool = False,
    clear_layout: bool = False,
) -> Campaign:
    campaign = await get_campaign(db, organization_id, campaign_id)
    if campaign.status == CampaignStatus.ARCHIVED.value:
        raise BusinessRuleError("Restore the campaign before editing")
    await _validate_bindings(db, organization_id, playlist_id=playlist_id, layout_id=layout_id)
    if name is not None:
        campaign.name = name
    if description is not None:
        campaign.description = description
    if priority is not None:
        campaign.priority = priority
    if clear_playlist:
        campaign.playlist_id = None
    elif playlist_id is not None:
        campaign.playlist_id = playlist_id
    if clear_layout:
        campaign.layout_id = None
    elif layout_id is not None:
        campaign.layout_id = layout_id
    await db.flush()
    return campaign


async def archive_campaign(
    db: AsyncSession, organization_id: uuid.UUID, campaign_id: uuid.UUID
) -> Campaign:
    campaign = await get_campaign(db, organization_id, campaign_id)
    campaign.status = CampaignStatus.ARCHIVED.value
    await db.flush()
    return campaign


async def restore_campaign(
    db: AsyncSession, organization_id: uuid.UUID, campaign_id: uuid.UUID
) -> Campaign:
    campaign = await get_campaign(db, organization_id, campaign_id)
    if campaign.status == CampaignStatus.ARCHIVED.value:
        campaign.status = CampaignStatus.DRAFT.value
        await db.flush()
    return campaign


# --- variants (P2-CAM-001) ---

VARIANT_TARGET_TYPES = {t.value for t in TargetType}
MAX_VARIANTS = 20


def _validate_variant_targets(targets: list[dict]) -> list[dict]:
    if not isinstance(targets, list) or not targets:
        raise ValidationAppError("A variant needs at least one target", field="targets")
    seen = set()
    for target in targets:
        if target.get("target_type") not in VARIANT_TARGET_TYPES:
            raise ValidationAppError(
                f"Unknown target_type '{target.get('target_type')}'", field="targets"
            )
        key = (target["target_type"], str(target.get("target_id")))
        if key in seen:
            raise ValidationAppError("Duplicate variant target", field="targets")
        seen.add(key)
    return targets


async def create_variant(
    db: AsyncSession,
    organization_id: uuid.UUID,
    campaign_id: uuid.UUID,
    *,
    name: str,
    layout_id: uuid.UUID | None,
    playlist_id: uuid.UUID | None,
    priority: int,
    targets: list[dict],
) -> Campaign:
    campaign = await get_campaign(db, organization_id, campaign_id)
    if campaign.status == CampaignStatus.ARCHIVED.value:
        raise BusinessRuleError("Restore the campaign before editing")
    if len(campaign.variants) >= MAX_VARIANTS:
        raise BusinessRuleError(f"A campaign supports at most {MAX_VARIANTS} variants")
    if any(v.name == name for v in campaign.variants):
        raise ValidationAppError("A variant with this name already exists", field="name")
    if layout_id is None and playlist_id is None:
        raise ValidationAppError(
            "A variant must override layout_id and/or playlist_id", field="layout_id"
        )
    await _validate_bindings(db, organization_id, playlist_id=playlist_id, layout_id=layout_id)
    _validate_variant_targets(targets)
    from app.services import targeting

    await targeting.validate_targets(db, organization_id, targets)

    variant = CampaignVariant(
        id=uuid.uuid4(),
        campaign_id=campaign.id,
        name=name,
        layout_id=layout_id,
        playlist_id=playlist_id,
        priority=priority,
    )
    db.add(variant)
    for target in targets:
        db.add(
            CampaignVariantTarget(
                variant_id=variant.id,
                target_type=target["target_type"],
                target_id=uuid.UUID(str(target["target_id"])),
                include_descendants=bool(target.get("include_descendants", True)),
            )
        )
    await db.flush()
    await db.refresh(variant, ["targets"])
    await db.refresh(campaign, ["variants"])
    logger.info("Variant %s created for campaign %s", variant.id, campaign.id)
    return campaign


async def delete_variant(
    db: AsyncSession,
    organization_id: uuid.UUID,
    campaign_id: uuid.UUID,
    variant_id: uuid.UUID,
) -> Campaign:
    campaign = await get_campaign(db, organization_id, campaign_id)
    variant = next((v for v in campaign.variants if v.id == variant_id), None)
    if variant is None:
        raise NotFoundError("Variant not found")
    await db.delete(variant)
    await db.flush()
    await db.refresh(campaign, ["variants"])
    return campaign


async def resolve_variant_for_device(
    db: AsyncSession, organization_id: uuid.UUID, campaign: Campaign, device_id: uuid.UUID
) -> CampaignVariant | None:
    """Highest-priority variant whose targets match the device; ties break by
    variant name for determinism. None = base campaign creative."""
    from app.services import targeting

    matching = []
    for variant in campaign.variants:
        if await targeting.device_matches_targets(db, organization_id, device_id, variant.targets):
            matching.append(variant)
    if not matching:
        return None
    return max(matching, key=lambda v: (v.priority, v.name))


# --- schedules (FR-SCH-001..007) ---


def _validate_schedule_fields(
    *,
    start_date: dt.date | None,
    end_date: dt.date | None,
    days_of_week: list[int] | None,
    timezone: str | None,
    kind: str = ScheduleKind.PLAY.value,
    recurrence: dict | None = None,
    exception_dates: list | None = None,
) -> None:
    if start_date and end_date and end_date < start_date:
        raise ValidationAppError("end_date must not be before start_date", field="end_date")
    if days_of_week is not None:
        if not days_of_week:
            raise ValidationAppError(
                "days_of_week must be omitted or non-empty", field="days_of_week"
            )
        if any(day not in range(7) for day in days_of_week):
            raise ValidationAppError(
                "days_of_week entries must be 0 (Monday) .. 6 (Sunday)", field="days_of_week"
            )
    if timezone is not None:
        validate_timezone(timezone)
    if kind not in (ScheduleKind.PLAY.value, ScheduleKind.BLACKOUT.value):
        raise ValidationAppError("kind must be 'play' or 'blackout'", field="kind")
    if recurrence is not None:
        if not isinstance(recurrence, dict) or set(recurrence) - {"days_of_month"}:
            raise ValidationAppError(
                "recurrence_json supports only {'days_of_month': [1..31]}",
                field="recurrence_json",
            )
        days = recurrence.get("days_of_month")
        if (
            not isinstance(days, list)
            or not days
            or any(not isinstance(d, int) or d not in range(1, 32) for d in days)
        ):
            raise ValidationAppError(
                "days_of_month must be a non-empty list of 1..31", field="recurrence_json"
            )
    if exception_dates is not None:
        if not isinstance(exception_dates, list) or len(exception_dates) > 100:
            raise ValidationAppError(
                "exception_dates_json must be a list of at most 100 ISO dates",
                field="exception_dates_json",
            )
        for value in exception_dates:
            try:
                dt.date.fromisoformat(str(value))
            except ValueError as exc:
                raise ValidationAppError(
                    f"'{value}' is not an ISO date", field="exception_dates_json"
                ) from exc


async def get_schedule(
    db: AsyncSession, organization_id: uuid.UUID, schedule_id: uuid.UUID
) -> Schedule:
    result = await db.execute(
        select(Schedule).where(
            Schedule.organization_id == organization_id, Schedule.id == schedule_id
        )
    )
    schedule = result.scalar_one_or_none()
    if schedule is None:
        raise NotFoundError("Schedule not found")
    return schedule


async def list_schedules(
    db: AsyncSession, organization_id: uuid.UUID, *, campaign_id: uuid.UUID | None
) -> list[Schedule]:
    query = select(Schedule).where(Schedule.organization_id == organization_id)
    if campaign_id is not None:
        query = query.where(Schedule.campaign_id == campaign_id)
    result = await db.execute(query.order_by(Schedule.created_at))
    return list(result.scalars().all())


async def create_schedule(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    campaign_id: uuid.UUID,
    name: str | None,
    start_date: dt.date | None,
    end_date: dt.date | None,
    start_time: dt.time | None,
    end_time: dt.time | None,
    days_of_week: list[int] | None,
    timezone: str | None,
    priority: int,
    kind: str = ScheduleKind.PLAY.value,
    recurrence: dict | None = None,
    exception_dates: list | None = None,
) -> Schedule:
    campaign = await get_campaign(db, organization_id, campaign_id)
    if campaign.status == CampaignStatus.ARCHIVED.value:
        raise BusinessRuleError("Cannot schedule an archived campaign")
    _validate_schedule_fields(
        start_date=start_date,
        end_date=end_date,
        days_of_week=days_of_week,
        timezone=timezone,
        kind=kind,
        recurrence=recurrence,
        exception_dates=exception_dates,
    )
    schedule = Schedule(
        organization_id=organization_id,
        campaign_id=campaign_id,
        name=name,
        kind=kind,
        start_date=start_date,
        end_date=end_date,
        start_time=start_time,
        end_time=end_time,
        days_of_week=days_of_week,
        recurrence_json=recurrence,
        exception_dates_json=exception_dates,
        timezone=timezone,
        priority=priority,
    )
    db.add(schedule)
    await db.flush()
    logger.info("Schedule %s created for campaign %s", schedule.id, campaign_id)
    return schedule


async def update_schedule(
    db: AsyncSession,
    organization_id: uuid.UUID,
    schedule_id: uuid.UUID,
    **changes,
) -> Schedule:
    schedule = await get_schedule(db, organization_id, schedule_id)
    fields = {
        "name",
        "kind",
        "start_date",
        "end_date",
        "start_time",
        "end_time",
        "days_of_week",
        "recurrence_json",
        "exception_dates_json",
        "timezone",
        "priority",
    }
    for field, value in changes.items():
        if field in fields and value is not ...:
            setattr(schedule, field, value)
    _validate_schedule_fields(
        start_date=schedule.start_date,
        end_date=schedule.end_date,
        days_of_week=schedule.days_of_week,
        timezone=schedule.timezone,
        kind=schedule.kind,
        recurrence=schedule.recurrence_json,
        exception_dates=schedule.exception_dates_json,
    )
    await db.flush()
    return schedule


async def delete_schedule(
    db: AsyncSession, organization_id: uuid.UUID, schedule_id: uuid.UUID
) -> None:
    schedule = await get_schedule(db, organization_id, schedule_id)
    await db.delete(schedule)
    await db.flush()


async def campaigns_with_schedules(db: AsyncSession, organization_id: uuid.UUID) -> list[Campaign]:
    result = await db.execute(
        select(Campaign).where(
            Campaign.organization_id == organization_id,
            Campaign.status != CampaignStatus.ARCHIVED.value,
        )
    )
    return list(result.scalars().all())
