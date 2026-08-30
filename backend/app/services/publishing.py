"""Publishing engine (M11, ADR-005) + campaign lifecycle (FR-CMP-005).

Publish -> deployment (frozen snapshot) -> queued fan-out -> per-device
status -> device acknowledgement. Retryable, observable, pull-based.
"""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import BusinessRuleError, ConflictError, NotFoundError
from app.models import Campaign, Deployment, DeploymentDevice, Device
from app.models.campaign import (
    CampaignStatus,
    DeploymentDeviceStatus,
    DeploymentStatus,
    TargetType,
)
from app.services import targeting
from app.services.campaigns import get_campaign

logger = logging.getLogger("app.publishing")


def _now() -> datetime:
    return datetime.now(UTC)


# --- campaign lifecycle (single approval path, SRS §19) ---

_TRANSITIONS: dict[str, set[str]] = {
    "submit-approval": {CampaignStatus.DRAFT.value},
    "approve": {CampaignStatus.PENDING_APPROVAL.value},
    "reject": {CampaignStatus.PENDING_APPROVAL.value},
    "pause": {CampaignStatus.PUBLISHED.value},
    "resume": {CampaignStatus.PAUSED.value},
}


async def transition_campaign(
    db: AsyncSession, organization_id: uuid.UUID, campaign_id: uuid.UUID, action: str
) -> Campaign:
    campaign = await get_campaign(db, organization_id, campaign_id)
    allowed = _TRANSITIONS.get(action)
    if allowed is None:
        raise NotFoundError("Unknown transition")
    if campaign.status not in allowed:
        raise BusinessRuleError(
            f"Cannot {action.replace('-', ' ')} a campaign in status '{campaign.status}'"
        )
    before_status = campaign.status
    campaign.status = {
        "submit-approval": CampaignStatus.PENDING_APPROVAL.value,
        "approve": CampaignStatus.APPROVED.value,
        "reject": CampaignStatus.DRAFT.value,
        "pause": CampaignStatus.PAUSED.value,
        "resume": CampaignStatus.PUBLISHED.value,
    }[action]
    await db.flush()

    from app.services import audit

    await audit.record(
        db,
        organization_id,
        action=f"CAMPAIGN_{action.replace('-', '_').upper()}",
        entity_type="campaign",
        entity_id=campaign.id,
        before={"status": before_status},
        after={"status": campaign.status},
    )
    if action == "submit-approval":
        # The approval engine owns the workflow record, notification and
        # (per tenant policy) maker-checker / auto-approval behavior.
        from app.core.context import user_id_ctx
        from app.services import approvals

        await approvals.submit(
            db, organization_id, "campaign", campaign.id, requester_id=user_id_ctx.get()
        )
    logger.info("Campaign %s: %s -> %s", campaign.id, action, campaign.status)
    return campaign


async def set_targets(
    db: AsyncSession,
    organization_id: uuid.UUID,
    campaign_id: uuid.UUID,
    targets: list[dict],
) -> Campaign:
    """Replace-set semantics for the logical target definition."""
    from app.models import CampaignTarget

    campaign = await get_campaign(db, organization_id, campaign_id)
    if campaign.status == CampaignStatus.ARCHIVED.value:
        raise BusinessRuleError("Restore the campaign before editing targets")
    valid_types = {t.value for t in TargetType}
    rows = []
    for spec in targets:
        if spec["target_type"] not in valid_types:
            raise BusinessRuleError(f"Unknown target type '{spec['target_type']}'")
        rows.append(
            CampaignTarget(
                campaign_id=campaign.id,
                target_type=spec["target_type"],
                target_id=spec["target_id"],
                include_descendants=spec.get("include_descendants", True),
                is_exclusion=spec.get("is_exclusion", False),
            )
        )
    campaign.targets.clear()
    await db.flush()
    campaign.targets.extend(rows)
    await db.flush()
    return campaign


async def effective_devices(
    db: AsyncSession, organization_id: uuid.UUID, campaign_id: uuid.UUID
) -> list[Device]:
    campaign = await get_campaign(db, organization_id, campaign_id)
    device_ids = await targeting.resolve_effective_devices(
        db, organization_id, campaign.targets
    )
    if not device_ids:
        return []
    result = await db.execute(select(Device).where(Device.id.in_(device_ids)))
    return sorted(result.scalars().all(), key=lambda d: d.name)


# --- deployments ---


async def get_deployment(
    db: AsyncSession, organization_id: uuid.UUID, deployment_id: uuid.UUID
) -> Deployment:
    result = await db.execute(
        select(Deployment).where(
            Deployment.organization_id == organization_id, Deployment.id == deployment_id
        )
    )
    deployment = result.scalar_one_or_none()
    if deployment is None:
        raise NotFoundError("Deployment not found")
    return deployment


async def list_deployments(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    campaign_id: uuid.UUID | None,
    status: str | None,
    page: int,
    page_size: int,
) -> tuple[list[Deployment], int]:
    query = select(Deployment).where(Deployment.organization_id == organization_id)
    if campaign_id:
        query = query.where(Deployment.campaign_id == campaign_id)
    if status:
        query = query.where(Deployment.status == status)
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    rows = await db.execute(
        query.order_by(Deployment.created_at.desc(), Deployment.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(rows.scalars().all()), total


async def publish_campaign(
    db: AsyncSession, organization_id: uuid.UUID, campaign_id: uuid.UUID
) -> Deployment:
    """Validates (FR-PUB-001), creates the deployment, and queues fan-out."""
    from app.services import entitlements as entitlements_service

    await entitlements_service.ensure_subscription_allows(db, organization_id, "publish")
    campaign = await get_campaign(db, organization_id, campaign_id)
    if campaign.status not in (CampaignStatus.APPROVED.value, CampaignStatus.PUBLISHED.value):
        raise BusinessRuleError("Campaign must be approved before publishing")
    if not campaign.schedules:
        raise BusinessRuleError("Campaign needs at least one schedule")
    if campaign.playlist_id is None and campaign.layout_id is None:
        raise BusinessRuleError("Campaign needs a playlist or a layout")

    if campaign.playlist_id is not None:
        from app.repositories import playlists as playlists_repo

        playlist = await playlists_repo.get_by_id(db, organization_id, campaign.playlist_id)
        if playlist is None or playlist.current_version_id is None:
            raise BusinessRuleError("The campaign playlist must be published first")
    if campaign.layout_id is not None:
        from app.repositories import layouts as layouts_repo

        layout = await layouts_repo.get_by_id(db, organization_id, campaign.layout_id)
        if layout is None or layout.current_version_id is None:
            raise BusinessRuleError("The campaign layout must be published first")

    device_ids = await targeting.resolve_effective_devices(
        db, organization_id, campaign.targets
    )
    if not device_ids:
        raise BusinessRuleError("Campaign targets resolve to no active devices")

    # Supersede any still-active deployment of this campaign.
    active = await db.execute(
        select(Deployment).where(
            Deployment.campaign_id == campaign.id,
            Deployment.status.in_(
                [
                    DeploymentStatus.QUEUED.value,
                    DeploymentStatus.PUBLISHING.value,
                    DeploymentStatus.PARTIAL.value,
                    DeploymentStatus.PUBLISHED.value,
                ]
            ),
        )
    )
    for old in active.scalars().all():
        old.status = DeploymentStatus.CANCELLED.value
        old.completed_at = _now()

    version = (
        await db.execute(
            select(func.coalesce(func.max(Deployment.version), 0)).where(
                Deployment.campaign_id == campaign.id
            )
        )
    ).scalar_one() + 1

    deployment = Deployment(
        organization_id=organization_id,
        campaign_id=campaign.id,
        version=version,
        status=DeploymentStatus.QUEUED.value,
        target_snapshot_json=targeting.snapshot_targets(campaign.targets),
    )
    db.add(deployment)
    campaign.status = CampaignStatus.PUBLISHED.value
    await db.flush()

    settings = get_settings()
    if settings.publishing_inline:
        await materialize_deployment(db, deployment.id)
    else:
        from app.workers.publishing import process_deployment

        process_deployment.delay(str(deployment.id))

    await db.refresh(deployment, ["devices"])

    from app.services import audit

    await audit.record(
        db,
        organization_id,
        action="CAMPAIGN_PUBLISHED",
        entity_type="campaign",
        entity_id=campaign.id,
        after={"deployment_id": str(deployment.id), "version": version,
               "devices": len(device_ids)},
    )

    from app.services import events

    await events.emit(
        db,
        organization_id,
        event_type="campaign.published",
        entity_type="campaign",
        entity_id=campaign.id,
        payload={
            "name": campaign.name,
            "deployment_id": str(deployment.id),
            "version": version,
            "devices": len(device_ids),
        },
    )
    logger.info(
        "Campaign %s published: deployment v%s (%s devices)",
        campaign.id,
        version,
        len(device_ids),
    )
    return deployment


async def materialize_deployment(db: AsyncSession, deployment_id: uuid.UUID) -> Deployment:
    """Worker step (FR-PUB-002/004): freeze the device set and open fan-out.
    Idempotent — re-running never duplicates device rows."""
    result = await db.execute(select(Deployment).where(Deployment.id == deployment_id))
    deployment = result.scalar_one_or_none()
    if deployment is None:
        raise NotFoundError("Deployment not found")
    if deployment.status not in (DeploymentStatus.QUEUED.value,):
        return deployment

    campaign = await get_campaign(db, deployment.organization_id, deployment.campaign_id)
    device_ids = await targeting.resolve_effective_devices(
        db, deployment.organization_id, campaign.targets
    )
    existing = {row.device_id for row in deployment.devices}
    for device_id in device_ids:
        if device_id not in existing:
            db.add(DeploymentDevice(deployment_id=deployment.id, device_id=device_id))
    deployment.status = DeploymentStatus.PUBLISHING.value
    deployment.started_at = _now()
    await db.flush()
    await db.refresh(deployment, ["devices"])
    return deployment


async def _recompute_status(db: AsyncSession, deployment: Deployment) -> None:
    """Aggregates from the database (not the loaded collection): concurrent
    acks would otherwise recompute from stale snapshots and the last writer
    could undercount. Callers must hold the deployment row lock."""
    rows = await db.execute(
        select(DeploymentDevice.status, func.count())
        .where(DeploymentDevice.deployment_id == deployment.id)
        .group_by(DeploymentDevice.status)
    )
    counts = dict(rows.all())
    total = sum(counts.values())
    if not total:
        return
    acked = counts.get(DeploymentDeviceStatus.ACKNOWLEDGED.value, 0)
    failed = counts.get(DeploymentDeviceStatus.FAILED.value, 0)
    previous = deployment.status
    if acked == total:
        deployment.status = DeploymentStatus.PUBLISHED.value
        deployment.completed_at = _now()
    elif failed == total:
        deployment.status = DeploymentStatus.FAILED.value
        deployment.completed_at = _now()
    elif acked or failed:
        deployment.status = DeploymentStatus.PARTIAL.value
    else:
        deployment.status = DeploymentStatus.PUBLISHING.value

    # Domain events fire once per terminal transition (3A-1) — the caller
    # holds the deployment row lock, so no double emission under load.
    if deployment.status != previous and deployment.status in (
        DeploymentStatus.PUBLISHED.value,
        DeploymentStatus.FAILED.value,
    ):
        from app.services import events

        await events.emit(
            db,
            deployment.organization_id,
            event_type="deployment.completed"
            if deployment.status == DeploymentStatus.PUBLISHED.value
            else "deployment.failed",
            entity_type="deployment",
            entity_id=deployment.id,
            payload={
                "campaign_id": str(deployment.campaign_id),
                "version": deployment.version,
                "acknowledged": acked,
                "failed": failed,
                "total": total,
            },
        )


async def acknowledge_deployment(
    db: AsyncSession,
    device: Device,
    deployment_id: uuid.UUID,
    *,
    success: bool,
    error: str | None,
) -> Deployment:
    """Player ACK (FR-PUB-006/FR-PLYR ack) — idempotent for success acks.
    Serialized per deployment via a row lock so concurrent acks aggregate
    deterministically."""
    locked = await db.execute(
        select(Deployment)
        .where(
            Deployment.organization_id == device.organization_id,
            Deployment.id == deployment_id,
        )
        .with_for_update()
    )
    deployment = locked.scalar_one_or_none()
    if deployment is None:
        raise NotFoundError("Deployment not found")
    row = next((r for r in deployment.devices if r.device_id == device.id), None)
    if row is None:
        raise NotFoundError("Deployment does not target this device")
    if deployment.status == DeploymentStatus.CANCELLED.value:
        raise ConflictError("Deployment has been cancelled")
    if row.status == DeploymentDeviceStatus.ACKNOWLEDGED.value and success:
        return deployment  # idempotent retry from an offline-recovered player
    row.attempts += 1
    if success:
        row.status = DeploymentDeviceStatus.ACKNOWLEDGED.value
        row.acknowledged_at = _now()
        row.last_error = None
    else:
        row.status = DeploymentDeviceStatus.FAILED.value
        row.last_error = (error or "player reported failure")[:1000]
        from app.services import notifications

        await notifications.create(
            db,
            device.organization_id,
            type="DEPLOYMENT_DEVICE_FAILED",
            severity="warning",
            title=f"Device '{device.name}' failed to apply a deployment",
            message=row.last_error,
            payload={"deployment_id": str(deployment.id), "device_id": str(device.id)},
        )
    await db.flush()
    await _recompute_status(db, deployment)
    await db.flush()
    return deployment


async def retry_deployment(
    db: AsyncSession, organization_id: uuid.UUID, deployment_id: uuid.UUID
) -> Deployment:
    """FR-PUB-005/008: failed targets back to pending, without duplicates."""
    deployment = await get_deployment(db, organization_id, deployment_id)
    if deployment.status == DeploymentStatus.CANCELLED.value:
        raise BusinessRuleError("Cancelled deployments cannot be retried")
    for row in deployment.devices:
        if row.status == DeploymentDeviceStatus.FAILED.value:
            row.status = DeploymentDeviceStatus.PENDING.value
            row.last_error = None
    deployment.completed_at = None
    await db.flush()
    await _recompute_status(db, deployment)
    await db.flush()
    from app.services import audit

    await audit.record(
        db, organization_id, action="DEPLOYMENT_RETRIED", entity_type="deployment",
        entity_id=deployment.id,
    )
    return deployment


async def cancel_deployment(
    db: AsyncSession, organization_id: uuid.UUID, deployment_id: uuid.UUID
) -> Deployment:
    deployment = await get_deployment(db, organization_id, deployment_id)
    if deployment.status in (
        DeploymentStatus.PUBLISHED.value,
        DeploymentStatus.CANCELLED.value,
    ):
        raise BusinessRuleError("Deployment is already finished")
    deployment.status = DeploymentStatus.CANCELLED.value
    deployment.completed_at = _now()
    await db.flush()
    from app.services import audit

    await audit.record(
        db, organization_id, action="DEPLOYMENT_CANCELLED", entity_type="deployment",
        entity_id=deployment.id,
    )
    return deployment


# --- approval engine adapter (registered at import time) ---


async def _campaign_name(
    db: AsyncSession, organization_id: uuid.UUID, entity_id: uuid.UUID
) -> str | None:
    try:
        return (await get_campaign(db, organization_id, entity_id)).name
    except NotFoundError:
        return None


async def _campaign_on_approved(
    db: AsyncSession, organization_id: uuid.UUID, entity_id: uuid.UUID
) -> None:
    await transition_campaign(db, organization_id, entity_id, "approve")


async def _campaign_on_rejected(
    db: AsyncSession, organization_id: uuid.UUID, entity_id: uuid.UUID
) -> None:
    await transition_campaign(db, organization_id, entity_id, "reject")


def _register_campaign_adapter() -> None:
    from app.services import approvals

    approvals.register_adapter(
        "campaign",
        approvals.EntityAdapter(
            approve_permission="campaigns.approve",
            get_name=_campaign_name,
            on_approved=_campaign_on_approved,
            on_rejected=_campaign_on_rejected,
        ),
    )


_register_campaign_adapter()


async def candidate_campaigns_for_device(db: AsyncSession, device) -> list:
    """Campaigns with a live deployment covering this device (shared by the
    manifest builder and the decisioning engine, P3 3B-2)."""
    from app.models import Campaign
    from app.models.campaign import CampaignStatus

    rows = await db.execute(
        select(Campaign)
        .join(Deployment, Deployment.campaign_id == Campaign.id)
        .join(DeploymentDevice, DeploymentDevice.deployment_id == Deployment.id)
        .where(
            DeploymentDevice.device_id == device.id,
            Deployment.status.in_(
                [
                    DeploymentStatus.PUBLISHING.value,
                    DeploymentStatus.PARTIAL.value,
                    DeploymentStatus.PUBLISHED.value,
                ]
            ),
            Campaign.status == CampaignStatus.PUBLISHED.value,
        )
    )
    seen: set[uuid.UUID] = set()
    candidates = []
    for campaign in rows.scalars():
        if campaign.id not in seen:
            seen.add(campaign.id)
            candidates.append(campaign)
    return candidates


async def pending_deployment_ids_for_device(
    db: AsyncSession, device_id: uuid.UUID
) -> list[uuid.UUID]:
    """Drives heartbeat sync_required and the player's sync loop."""
    result = await db.execute(
        select(DeploymentDevice.deployment_id)
        .join(Deployment, Deployment.id == DeploymentDevice.deployment_id)
        .where(
            DeploymentDevice.device_id == device_id,
            DeploymentDevice.status == DeploymentDeviceStatus.PENDING.value,
            Deployment.status.in_(
                [DeploymentStatus.PUBLISHING.value, DeploymentStatus.PARTIAL.value]
            ),
        )
    )
    return list(result.scalars().all())
