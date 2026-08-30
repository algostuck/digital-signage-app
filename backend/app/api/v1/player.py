"""Player Gateway (M12) — manufacturer-neutral device-facing endpoints.

Authentication: opaque device token in the `X-Device-Token` header (issued
via the approval-gated register flow). Path device_id must match the token's
device — a mismatch is a 404 to avoid existence disclosure.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import BusinessRuleError, NotFoundError
from app.core.ratelimit import rate_limit
from app.db.session import get_db
from app.models import Device
from app.schemas.campaigns import PlayerDeploymentAck
from app.schemas.devices import (
    DeviceCommandOut,
    PlayerCapabilitiesRequest,
    PlayerCommandAckRequest,
    PlayerHeartbeatRequest,
    PlayerRegisterOut,
    PlayerRegisterRequest,
)
from app.schemas.envelope import success
from app.schemas.releases import PlayerUpdateAck
from app.services import devices as service
from app.services import manifest as manifest_service
from app.services import publishing

router = APIRouter(prefix="/player")


async def get_current_device(
    db: Annotated[AsyncSession, Depends(get_db)],
    x_device_token: Annotated[str | None, Header()] = None,
) -> Device:
    return await service.authenticate_device(db, x_device_token)


CurrentDevice = Annotated[Device, Depends(get_current_device)]


def _require_own(device: Device, device_id: uuid.UUID) -> None:
    if device.id != device_id:
        raise NotFoundError("Device not found")


@router.post(
    "/register",
    dependencies=[
        rate_limit("player-register", lambda: get_settings().rate_limit_register_per_minute)
    ],
)
async def register(body: PlayerRegisterRequest, db: AsyncSession = Depends(get_db)) -> dict:
    """Public bootstrap endpoint (rate-limited per IP). Idempotent per serial;
    returns the device token exactly once, on the first poll after approval."""
    device, token = await service.register_device(
        db,
        enrollment_key=body.enrollment_key,
        serial_no=body.serial_no,
        name=body.name,
        manufacturer=body.manufacturer,
        model=body.model,
        platform=body.platform,
        os_version=body.os_version,
        player_version=body.player_version,
        mac_address=body.mac_address,
        screen_width=body.screen_width,
        screen_height=body.screen_height,
    )
    out = PlayerRegisterOut(device_id=device.id, status=device.status, device_token=token)
    return success(out.model_dump(mode="json"))


@router.post(
    "/{device_id}/heartbeat",
    dependencies=[
        rate_limit(
            "heartbeat",
            lambda: get_settings().rate_limit_heartbeat_per_minute,
            key_param="device_id",
        )
    ],
)
async def heartbeat(
    device_id: uuid.UUID,
    body: PlayerHeartbeatRequest,
    device: CurrentDevice,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    _require_own(device, device_id)
    client_ip = request.client.host if request.client else None
    result = await service.record_heartbeat(
        db, device, payload=body.model_dump(mode="json", exclude_none=True), ip_address=client_ip
    )
    result["sync_required"] = bool(
        await publishing.pending_deployment_ids_for_device(db, device.id)
    )
    # OTA offer (P2-DEV-004): pull-based like everything device-facing.
    from app.services import player_updates

    result["update"] = await player_updates.pending_update_for_device(db, device)
    return success(result)


@router.post(
    "/{device_id}/screenshots",
    dependencies=[
        rate_limit("screenshots", lambda: 10, key_param="device_id")
    ],
)
async def upload_screenshot(
    device_id: uuid.UUID,
    request: Request,
    device: CurrentDevice,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Display evidence upload (P2-MON-003): raw PNG/JPEG body, 5 MB cap.
    Typically sent in response to a SCREENSHOT command."""
    from app.services import device_ops

    _require_own(device, device_id)
    data = await request.body()
    mime_type = request.headers.get("content-type", "").split(";")[0].strip()
    screenshot = await device_ops.store_screenshot(db, device, data=data, mime_type=mime_type)
    return success(
        {"screenshot_id": str(screenshot.id), "captured_at": screenshot.captured_at.isoformat()}
    )


@router.post("/{device_id}/capabilities")
async def set_capabilities(
    device_id: uuid.UUID,
    body: PlayerCapabilitiesRequest,
    device: CurrentDevice,
    db: AsyncSession = Depends(get_db),
) -> dict:
    _require_own(device, device_id)
    await service.set_capabilities(
        db, device, [(c.code, c.supported, c.value) for c in body.capabilities]
    )
    return success({"capabilities": len(body.capabilities)})


@router.get("/{device_id}/manifest")
async def get_manifest(
    device_id: uuid.UUID, device: CurrentDevice, db: AsyncSession = Depends(get_db)
) -> dict:
    _require_own(device, device_id)
    return success(await manifest_service.build_manifest(db, device))


@router.get("/{device_id}/assets/{asset_id}/url")
async def get_asset_url(
    device_id: uuid.UUID,
    asset_id: uuid.UUID,
    device: CurrentDevice,
    db: AsyncSession = Depends(get_db),
) -> dict:
    _require_own(device, device_id)
    from app.integrations.storage import get_storage
    from app.repositories import content as content_repo
    from app.services.content import current_version

    asset = await content_repo.get_asset(db, device.organization_id, asset_id)
    if asset is None:
        raise NotFoundError("Asset not found")
    version = current_version(asset)
    if version is None or version.processing_status != "ready":
        raise BusinessRuleError("Asset is not ready for delivery")
    settings = get_settings()
    url = get_storage().presigned_get_url(
        version.object_key, settings.signed_url_ttl_seconds
    )
    return success({"url": url, "sha256": version.checksum, "size": version.size_bytes})


@router.post("/{device_id}/deployments/{deployment_id}/ack")
async def acknowledge_deployment(
    device_id: uuid.UUID,
    deployment_id: uuid.UUID,
    body: PlayerDeploymentAck,
    device: CurrentDevice,
    db: AsyncSession = Depends(get_db),
) -> dict:
    _require_own(device, device_id)
    deployment = await publishing.acknowledge_deployment(
        db, device, deployment_id, success=body.success, error=body.error
    )
    return success({"deployment_id": str(deployment.id), "status": deployment.status})


@router.post(
    "/{device_id}/events",
    dependencies=[
        rate_limit(
            "player-events",
            lambda: get_settings().rate_limit_events_per_minute,
            key_param="device_id",
        )
    ],
)
async def report_events(
    device_id: uuid.UUID,
    body: dict,
    device: CurrentDevice,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Batch event ingestion (FR-PLYR-006): operational events plus playback
    records for proof-of-play. Idempotent enough for offline replay."""
    import datetime as dt

    from app.models import DeviceEvent, PlaybackEvent

    _require_own(device, device_id)
    events = body.get("events", [])
    if not isinstance(events, list) or len(events) > 500:
        raise BusinessRuleError("events must be a list of at most 500 entries")

    def parse_ts(value):
        if not value:
            return None
        try:
            return dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None

    stored_events = 0
    stored_playback = 0
    for event in events:
        if not isinstance(event, dict) or not event.get("type"):
            continue
        if event["type"] == "playback":
            started = parse_ts(event.get("started_at"))
            if started is None:
                continue

            def parse_id(key, entry=event):
                try:
                    return uuid.UUID(entry[key]) if entry.get(key) else None
                except ValueError:
                    return None

            db.add(
                PlaybackEvent(
                    organization_id=device.organization_id,
                    device_id=device.id,
                    campaign_id=parse_id("campaign_id"),
                    playlist_id=parse_id("playlist_id"),
                    asset_id=parse_id("asset_id"),
                    started_at=started,
                    ended_at=parse_ts(event.get("ended_at")),
                    result=str(event.get("result", ""))[:20] or None,
                )
            )
            stored_playback += 1
        else:
            db.add(
                DeviceEvent(
                    device_id=device.id,
                    event_type=str(event["type"])[:60],
                    event_at=parse_ts(event.get("timestamp")) or dt.datetime.now(dt.UTC),
                    payload_json=event.get("payload"),
                )
            )
            stored_events += 1
    await db.flush()
    return success({"stored_events": stored_events, "stored_playback": stored_playback})


@router.post("/{device_id}/releases/{release_id}/ack")
async def acknowledge_update(
    device_id: uuid.UUID,
    release_id: uuid.UUID,
    body: PlayerUpdateAck,
    device: CurrentDevice,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Update progress report (P2-DEV-005): updating -> succeeded | failed.
    A success also bumps the device's reported player_version."""
    from app.services import player_updates

    _require_own(device, device_id)
    row = await player_updates.record_update_status(
        db, device, release_id, status=body.status, error=body.error
    )
    return success({"release_id": str(release_id), "state": row.state})


@router.get("/{device_id}/commands")
async def poll_commands(
    device_id: uuid.UUID, device: CurrentDevice, db: AsyncSession = Depends(get_db)
) -> dict:
    _require_own(device, device_id)
    commands = await service.poll_commands(db, device)
    return success(
        [DeviceCommandOut.model_validate(c).model_dump(mode="json") for c in commands]
    )


@router.post("/{device_id}/commands/{command_id}/ack")
async def acknowledge_command(
    device_id: uuid.UUID,
    command_id: uuid.UUID,
    body: PlayerCommandAckRequest,
    device: CurrentDevice,
    db: AsyncSession = Depends(get_db),
) -> dict:
    _require_own(device, device_id)
    command = await service.acknowledge_command(
        db, device, command_id, success=body.success, result=body.result
    )
    return success(DeviceCommandOut.model_validate(command).model_dump(mode="json"))
