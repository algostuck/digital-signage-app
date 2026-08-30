"""Experimentation engine (P3-DEC-003, slice 3B-3).

A running experiment overrides 2E audience-variant resolution for its
campaign: each device lands deterministically in one arm via
sha256(experiment_id:device_id) → bucket 0..9999, mapped through the
cumulative allocation table (remainder = control = base creative).
Assignments are persisted as evidence; results join playback events per
arm. Stopping the experiment restores normal resolution instantly.
"""

import hashlib
import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import (
    BusinessRuleError,
    ConflictError,
    NotFoundError,
    ValidationAppError,
)
from app.models import (
    Campaign,
    CampaignVariant,
    Device,
    Experiment,
    ExperimentAssignment,
    ExperimentVariant,
    PlaybackEvent,
)
from app.models.experiment import ExperimentStatus

logger = logging.getLogger("app.experiments")


def _bucket(experiment_id: uuid.UUID, device_id: uuid.UUID) -> int:
    """Stable 0..9999 bucket — same device, same arm, forever."""
    digest = hashlib.sha256(f"{experiment_id}:{device_id}".encode()).digest()
    return int.from_bytes(digest[:4], "big") % 10000


async def get_experiment(
    db: AsyncSession, organization_id: uuid.UUID, experiment_id: uuid.UUID
) -> Experiment:
    experiment = (
        await db.execute(
            select(Experiment).where(
                Experiment.organization_id == organization_id,
                Experiment.id == experiment_id,
            )
        )
    ).scalar_one_or_none()
    if experiment is None:
        raise NotFoundError("Experiment not found")
    return experiment


async def list_experiments(
    db: AsyncSession, organization_id: uuid.UUID
) -> list[Experiment]:
    rows = await db.execute(
        select(Experiment)
        .where(Experiment.organization_id == organization_id)
        .order_by(Experiment.created_at.desc())
    )
    return list(rows.scalars().all())


async def create_experiment(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    campaign_id: uuid.UUID,
    name: str,
    arms: list[dict],
    user_id: uuid.UUID | None = None,
) -> Experiment:
    """arms: [{variant_id, allocation_pct}] — total <= 100, remainder plays
    the base creative (control)."""
    from app.services import entitlements

    await entitlements.require_feature(db, organization_id, "experiments")
    campaign = (
        await db.execute(
            select(Campaign).where(
                Campaign.organization_id == organization_id, Campaign.id == campaign_id
            )
        )
    ).scalar_one_or_none()
    if campaign is None:
        raise NotFoundError("Campaign not found")

    exists = (
        await db.execute(
            select(Experiment).where(
                Experiment.organization_id == organization_id, Experiment.name == name
            )
        )
    ).scalar_one_or_none()
    if exists is not None:
        raise ConflictError("An experiment with this name already exists", field="name")

    if not arms:
        raise ValidationAppError("At least one arm is required", field="arms")
    total = 0
    campaign_variant_ids = {str(v.id) for v in campaign.variants}
    seen: set[str] = set()
    for arm in arms:
        variant_id = str(arm.get("variant_id"))
        pct = arm.get("allocation_pct")
        if variant_id not in campaign_variant_ids:
            raise ValidationAppError(
                "Each arm must reference a variant of this campaign", field="arms"
            )
        if variant_id in seen:
            raise ValidationAppError("Duplicate variant arm", field="arms")
        seen.add(variant_id)
        if not isinstance(pct, int) or not 1 <= pct <= 100:
            raise ValidationAppError("allocation_pct must be 1..100", field="arms")
        total += pct
    if total > 100:
        raise ValidationAppError("Allocations exceed 100%", field="arms")

    experiment = Experiment(
        organization_id=organization_id, campaign_id=campaign_id, name=name
    )
    db.add(experiment)
    await db.flush()
    for arm in arms:
        db.add(
            ExperimentVariant(
                experiment_id=experiment.id,
                variant_id=uuid.UUID(str(arm["variant_id"])),
                allocation_pct=arm["allocation_pct"],
            )
        )
    await db.flush()
    await db.refresh(experiment, ["variants"])

    from app.services import audit

    await audit.record(
        db, organization_id, action="EXPERIMENT_CREATED",
        entity_type="experiment", entity_id=experiment.id,
        after={"name": name, "campaign_id": str(campaign_id),
               "arms": len(arms), "control_pct": 100 - total},
        user_id=user_id,
    )
    return experiment


async def transition(
    db: AsyncSession,
    organization_id: uuid.UUID,
    experiment_id: uuid.UUID,
    *,
    action: str,
    user_id: uuid.UUID | None = None,
) -> Experiment:
    experiment = await get_experiment(db, organization_id, experiment_id)
    now = datetime.now(UTC)
    if action == "start":
        if experiment.status != ExperimentStatus.DRAFT.value:
            raise BusinessRuleError("Only draft experiments can start")
        running = (
            await db.execute(
                select(Experiment).where(
                    Experiment.campaign_id == experiment.campaign_id,
                    Experiment.status == ExperimentStatus.RUNNING.value,
                )
            )
        ).scalar_one_or_none()
        if running is not None:
            raise BusinessRuleError("This campaign already has a running experiment")
        experiment.status = ExperimentStatus.RUNNING.value
        experiment.start_at = now
    elif action == "stop":
        if experiment.status != ExperimentStatus.RUNNING.value:
            raise BusinessRuleError("Only running experiments can stop")
        experiment.status = ExperimentStatus.COMPLETED.value
        experiment.end_at = now
    else:
        raise ValidationAppError("action must be start or stop", field="action")
    await db.flush()

    from app.services import audit

    await audit.record(
        db, organization_id, action=f"EXPERIMENT_{action.upper()}",
        entity_type="experiment", entity_id=experiment.id, user_id=user_id,
    )
    logger.info("Experiment %s %s", experiment.id, experiment.status)
    return experiment


async def delete_experiment(
    db: AsyncSession, organization_id: uuid.UUID, experiment_id: uuid.UUID
) -> None:
    experiment = await get_experiment(db, organization_id, experiment_id)
    if experiment.status == ExperimentStatus.RUNNING.value:
        raise BusinessRuleError("Stop the experiment before deleting it")
    await db.delete(experiment)
    await db.flush()


async def running_experiment_for_campaign(
    db: AsyncSession, campaign_id: uuid.UUID
) -> Experiment | None:
    return (
        await db.execute(
            select(Experiment).where(
                Experiment.campaign_id == campaign_id,
                Experiment.status == ExperimentStatus.RUNNING.value,
            )
        )
    ).scalar_one_or_none()


async def assigned_variant(
    db: AsyncSession, experiment: Experiment, device: Device
) -> CampaignVariant | None:
    """Deterministic arm for this device; persists the assignment evidence
    on first resolution. None = control (base creative)."""
    existing = (
        await db.execute(
            select(ExperimentAssignment).where(
                ExperimentAssignment.experiment_id == experiment.id,
                ExperimentAssignment.device_id == device.id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        if existing.variant_id is None:
            return None
        return await db.get(CampaignVariant, existing.variant_id)

    bucket = _bucket(experiment.id, device.id)
    cumulative = 0
    chosen: uuid.UUID | None = None
    for arm in experiment.variants:
        cumulative += arm.allocation_pct * 100  # pct -> basis points of 10000
        if bucket < cumulative:
            chosen = arm.variant_id
            break
    db.add(
        ExperimentAssignment(
            experiment_id=experiment.id, device_id=device.id, variant_id=chosen
        )
    )
    await db.flush()
    if chosen is None:
        return None
    return await db.get(CampaignVariant, chosen)


async def results(
    db: AsyncSession, organization_id: uuid.UUID, experiment_id: uuid.UUID
) -> dict:
    """Per-arm assignment counts + playback volume within the experiment
    window (from existing proof-of-play events — no new telemetry)."""
    experiment = await get_experiment(db, organization_id, experiment_id)
    assignments = (
        await db.execute(
            select(ExperimentAssignment).where(
                ExperimentAssignment.experiment_id == experiment.id
            )
        )
    ).scalars().all()
    by_arm: dict[str, list[uuid.UUID]] = {}
    for assignment in assignments:
        key = str(assignment.variant_id) if assignment.variant_id else "control"
        by_arm.setdefault(key, []).append(assignment.device_id)

    window_start = experiment.start_at
    window_end = experiment.end_at or datetime.now(UTC)
    arms_out = []
    variant_names = {
        str(arm.variant_id): (await db.get(CampaignVariant, arm.variant_id)).name
        for arm in experiment.variants
    }
    for key, device_ids in sorted(by_arm.items()):
        playback_query = select(func.count()).where(
            PlaybackEvent.organization_id == organization_id,
            PlaybackEvent.campaign_id == experiment.campaign_id,
            PlaybackEvent.device_id.in_(device_ids),
        )
        if window_start is not None:
            playback_query = playback_query.where(PlaybackEvent.started_at >= window_start)
        playback_query = playback_query.where(PlaybackEvent.started_at <= window_end)
        plays = (await db.execute(playback_query)).scalar_one()
        arms_out.append(
            {
                "arm": "control" if key == "control" else variant_names.get(key, key),
                "variant_id": None if key == "control" else key,
                "devices": len(device_ids),
                "playback_count": plays,
            }
        )
    allocated = sum(arm.allocation_pct for arm in experiment.variants)
    return {
        "experiment_id": str(experiment.id),
        "status": experiment.status,
        "start_at": experiment.start_at.isoformat() if experiment.start_at else None,
        "end_at": experiment.end_at.isoformat() if experiment.end_at else None,
        "control_pct": 100 - allocated,
        "arms": arms_out,
    }
