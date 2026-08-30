"""Player manifest builder (FR-PLYR-003, SRS §9.1, §13).

The manifest is the device's complete offline-capable state: the resolved
campaign, its layout/playlist versions, schedule windows (the player re-
evaluates these locally while offline), the fallback chain, and every asset
with checksum + signed URL. Campaign resolution reuses the scheduling engine
so cloud and player agree.
"""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.integrations.storage import get_storage
from app.models import (
    Campaign,
    Deployment,
    DeploymentDevice,
    Device,
    Organization,
    Playlist,
)
from app.models.campaign import CampaignStatus, DeploymentStatus, Schedule
from app.repositories import content as content_repo
from app.repositories import layouts as layouts_repo
from app.repositories import locations as locations_repo
from app.repositories import playlists as playlists_repo
from app.services import scheduling
from app.services.content import current_version as asset_current_version
from app.services.locations import effective_timezone
from app.services.publishing import pending_deployment_ids_for_device

logger = logging.getLogger("app.manifest")


async def device_effective_timezone(db: AsyncSession, device: Device) -> str:
    if device.timezone:
        return device.timezone
    org = await db.get(Organization, device.organization_id)
    if device.location_id:
        location = await locations_repo.get_by_id(
            db, device.organization_id, device.location_id
        )
        if location is not None:
            ancestors = await locations_repo.get_by_ids(
                db, device.organization_id, location.ancestor_ids()
            )
            return effective_timezone(location, ancestors, org)
    return org.timezone


def _schedule_out(schedule: Schedule) -> dict:
    return {
        "kind": schedule.kind,
        "start_date": schedule.start_date.isoformat() if schedule.start_date else None,
        "end_date": schedule.end_date.isoformat() if schedule.end_date else None,
        "start_time": schedule.start_time.isoformat() if schedule.start_time else None,
        "end_time": schedule.end_time.isoformat() if schedule.end_time else None,
        "days_of_week": schedule.days_of_week,
        "recurrence": schedule.recurrence_json,
        "exception_dates": schedule.exception_dates_json,
        "timezone": schedule.timezone,
        "priority": schedule.priority,
    }


async def _playlist_payload(
    db: AsyncSession, organization_id: uuid.UUID, playlist: Playlist
) -> dict | None:
    version = next(
        (v for v in playlist.versions if v.id == playlist.current_version_id), None
    )
    if version is None:
        return None
    return {
        "id": str(playlist.id),
        "version": version.version_no,
        "loop": version.items_json.get("loop", True),
        "items": version.items_json.get("items", []),
    }


async def _collect_asset_ids(payloads: list[dict | None], layout_canvas: dict | None) -> set[str]:
    asset_ids: set[str] = set()
    for payload in payloads:
        if payload is None:
            continue
        for item in payload.get("items", []):
            if item.get("asset_id"):
                asset_ids.add(item["asset_id"])
    if layout_canvas:
        for zone in layout_canvas.get("zones", []):
            asset_id = (zone.get("content_config") or {}).get("asset_id")
            if asset_id:
                asset_ids.add(str(asset_id))
    return asset_ids


async def build_manifest(db: AsyncSession, device: Device) -> dict:
    settings = get_settings()
    timezone = await device_effective_timezone(db, device)
    now = datetime.now(UTC)

    # Candidate campaigns: any non-cancelled deployment covering this device,
    # whose campaign is currently published.
    rows = await db.execute(
        select(Campaign, Deployment)
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
    deployment_by_campaign: dict[uuid.UUID, Deployment] = {}
    candidates: list[Campaign] = []
    for campaign, deployment in rows.all():
        if campaign.id not in deployment_by_campaign:
            candidates.append(campaign)
            deployment_by_campaign[campaign.id] = deployment

    # Resolve by current schedule window; when nothing is active right now,
    # ship the highest-priority candidate anyway — the player evaluates the
    # windows locally (offline-first, SRS §13).
    active = scheduling.resolve_active_campaign(candidates, now, timezone)
    winner = active or (
        max(candidates, key=lambda c: (c.priority, c.created_at)) if candidates else None
    )

    manifest: dict = {
        "device_id": str(device.id),
        "manifest_version": (
            deployment_by_campaign[winner.id].version if winner else 0
        ),
        "generated_at": now.isoformat(),
        "timezone": timezone,
        "active_campaign": str(winner.id) if winner else None,
        "campaign_active_now": active is not None,
        "campaign": None,
        "variant": None,
        "schedules": [],
        "layout": None,
        "playlist": None,
        "fallback": None,
        "assets": [],
        "pending_deployments": [
            str(d) for d in await pending_deployment_ids_for_device(db, device.id)
        ],
    }
    if winner is None:
        return manifest

    manifest["campaign"] = {
        "id": str(winner.id),
        "name": winner.name,
        "priority": winner.priority,
    }
    manifest["schedules"] = [_schedule_out(s) for s in winner.schedules]

    # Variant override (P2-CAM-001): the audience-matched creative replaces
    # the base layout/playlist for THIS device only.
    from app.services import campaigns as campaigns_service

    effective_layout_id = winner.layout_id
    effective_playlist_id = winner.playlist_id
    variant = await campaigns_service.resolve_variant_for_device(
        db, device.organization_id, winner, device.id
    )
    if variant is not None:
        effective_layout_id = variant.layout_id or effective_layout_id
        effective_playlist_id = variant.playlist_id or effective_playlist_id
        manifest["variant"] = {"id": str(variant.id), "name": variant.name}

    layout_canvas = None
    if effective_layout_id:
        layout = await layouts_repo.get_by_id(db, device.organization_id, effective_layout_id)
        if layout is not None and layout.current_version_id:
            version = next(
                (v for v in layout.versions if v.id == layout.current_version_id), None
            )
            if version is not None:
                layout_canvas = version.canvas_json
                manifest["layout"] = {
                    "id": str(layout.id),
                    "version": version.version_no,
                    "canvas": version.canvas_json,
                }

    playlist_payload = None
    fallback_payload = None
    if effective_playlist_id:
        playlist = await playlists_repo.get_by_id(
            db, device.organization_id, effective_playlist_id
        )
        if playlist is not None:
            playlist_payload = await _playlist_payload(db, device.organization_id, playlist)
            manifest["playlist"] = playlist_payload
            if playlist.fallback_playlist_id:
                fallback = await playlists_repo.get_by_id(
                    db, device.organization_id, playlist.fallback_playlist_id
                )
                if fallback is not None:
                    fallback_payload = await _playlist_payload(
                        db, device.organization_id, fallback
                    )
                    if fallback_payload is not None:
                        manifest["fallback"] = fallback_payload

    asset_ids = await _collect_asset_ids([playlist_payload, fallback_payload], layout_canvas)
    storage = get_storage()
    for raw_id in sorted(asset_ids):
        asset = await content_repo.get_asset(db, device.organization_id, uuid.UUID(raw_id))
        if asset is None:
            continue
        version = asset_current_version(asset)
        if version is None or version.processing_status != "ready":
            continue
        manifest["assets"].append(
            {
                "id": str(asset.id),
                "name": asset.name,
                "type": asset.type,
                "sha256": version.checksum,
                "size": version.size_bytes,
                "mime_type": version.mime_type,
                "url": storage.presigned_get_url(
                    version.object_key, settings.signed_url_ttl_seconds
                ),
            }
        )
    return manifest
