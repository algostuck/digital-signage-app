"""Edge bundle service (P3-M06, slice 3C-2).

Bundle build reuses existing truth: the assets referenced by the target
devices' live deployments (nothing is copied — the bundle is a signed
descriptor manifest; binaries stay on the storage adapter and downloads
resume via Range). Bandwidth policy lives in settings_json (no DDL):
`settings_json.bandwidth = {"windows": [{"start","end"}], "concurrency": n}`.
"""

import hashlib
import hmac
import json
import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import (
    BusinessRuleError,
    ConflictError,
    NotFoundError,
    ValidationAppError,
)
from app.models import (
    Device,
    DeviceGroup,
    EdgeBundle,
    EdgeBundleDevice,
    Organization,
)
from app.models.device import DeviceStatus
from app.models.edge import EdgeBundleState

logger = logging.getLogger("app.edge")

DEFAULT_TTL_DAYS = 7
DEFAULT_BANDWIDTH = {"windows": [{"start": "01:00", "end": "05:00"}], "concurrency": 2}


def _sign(payload: dict) -> str:
    """Integrity signature over the canonical manifest. HMAC with the server
    secret — server-verified trust; asymmetric player-side verification is a
    documented later hardening step."""
    from app.core.config import get_settings

    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hmac.new(get_settings().jwt_secret.encode(), body, hashlib.sha256).hexdigest()


async def _target_devices(
    db: AsyncSession, organization_id: uuid.UUID, group_id: uuid.UUID | None
) -> list[Device]:
    query = select(Device).where(
        Device.organization_id == organization_id,
        Device.status == DeviceStatus.ACTIVE.value,
    )
    if group_id is not None:
        group = (
            await db.execute(
                select(DeviceGroup).where(
                    DeviceGroup.organization_id == organization_id,
                    DeviceGroup.id == group_id,
                )
            )
        ).scalar_one_or_none()
        if group is None:
            raise NotFoundError("Device group not found")
        query = query.where(Device.group_id == group_id)
    return list((await db.execute(query)).scalars().all())


async def _collect_assets(db: AsyncSession, devices: list[Device]) -> list[dict]:
    """Union of READY assets referenced by the targets' live manifests —
    computed from each device's real manifest so bundle content always
    matches what the player would fetch."""
    from app.services.manifest import build_manifest

    seen: dict[str, dict] = {}
    for device in devices:
        manifest = await build_manifest(db, device)
        for asset in manifest.get("assets", []):
            seen.setdefault(
                asset["id"],
                {
                    "id": asset["id"],
                    "name": asset["name"],
                    "sha256": asset["sha256"],
                    "size": asset["size"],
                    "mime_type": asset["mime_type"],
                },
            )
    return sorted(seen.values(), key=lambda a: a["id"])


async def get_bundle(
    db: AsyncSession, organization_id: uuid.UUID, bundle_id: uuid.UUID
) -> EdgeBundle:
    bundle = (
        await db.execute(
            select(EdgeBundle).where(
                EdgeBundle.organization_id == organization_id, EdgeBundle.id == bundle_id
            )
        )
    ).scalar_one_or_none()
    if bundle is None:
        raise NotFoundError("Bundle not found")
    return bundle


async def list_bundles(db: AsyncSession, organization_id: uuid.UUID) -> list[EdgeBundle]:
    await _expire_due(db, organization_id)
    rows = await db.execute(
        select(EdgeBundle)
        .where(EdgeBundle.organization_id == organization_id)
        .order_by(EdgeBundle.created_at.desc())
    )
    return list(rows.scalars().all())


async def _expire_due(db: AsyncSession, organization_id: uuid.UUID) -> None:
    now = datetime.now(UTC)
    rows = (
        await db.execute(
            select(EdgeBundle).where(
                EdgeBundle.organization_id == organization_id,
                EdgeBundle.state == EdgeBundleState.PUBLISHED.value,
                EdgeBundle.expires_at.is_not(None),
            )
        )
    ).scalars()
    for bundle in rows:
        expires = (
            bundle.expires_at
            if bundle.expires_at.tzinfo
            else bundle.expires_at.replace(tzinfo=UTC)
        )
        if expires <= now:
            bundle.state = EdgeBundleState.EXPIRED.value
    await db.flush()


async def create_bundle(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    name: str,
    group_id: uuid.UUID | None = None,
    ttl_days: int = DEFAULT_TTL_DAYS,
    user_id: uuid.UUID | None = None,
) -> EdgeBundle:
    from app.services import entitlements

    await entitlements.require_feature(db, organization_id, "edge_bundles")
    if not 1 <= ttl_days <= 90:
        raise ValidationAppError("ttl_days must be 1..90", field="ttl_days")
    exists = (
        await db.execute(
            select(EdgeBundle).where(
                EdgeBundle.organization_id == organization_id,
                EdgeBundle.name == name,
                EdgeBundle.state != EdgeBundleState.EXPIRED.value,
            )
        )
    ).scalar_one_or_none()
    if exists is not None:
        raise ConflictError("An active bundle with this name already exists", field="name")

    devices = await _target_devices(db, organization_id, group_id)
    if not devices:
        raise BusinessRuleError("The bundle target resolves to no active devices")
    assets = await _collect_assets(db, devices)
    version = (
        await db.execute(
            select(func.coalesce(func.max(EdgeBundle.bundle_version), 0)).where(
                EdgeBundle.organization_id == organization_id
            )
        )
    ).scalar_one() + 1
    manifest = {
        "assets": assets,
        "generated_at": datetime.now(UTC).isoformat(),
        "device_count": len(devices),
    }
    bundle = EdgeBundle(
        organization_id=organization_id,
        name=name,
        bundle_version=version,
        group_id=group_id,
        manifest_json=manifest,
        signature=_sign(manifest),
        expires_at=datetime.now(UTC) + timedelta(days=ttl_days),
    )
    db.add(bundle)
    await db.flush()
    for device in devices:
        db.add(EdgeBundleDevice(bundle_id=bundle.id, device_id=device.id))
    await db.flush()
    await db.refresh(bundle, ["devices"])

    from app.services import audit

    await audit.record(
        db, organization_id, action="EDGE_BUNDLE_CREATED",
        entity_type="edge_bundle", entity_id=bundle.id,
        after={"name": name, "version": version, "assets": len(assets),
               "devices": len(devices)},
        user_id=user_id,
    )
    return bundle


async def publish_bundle(
    db: AsyncSession,
    organization_id: uuid.UUID,
    bundle_id: uuid.UUID,
    *,
    user_id: uuid.UUID | None = None,
) -> EdgeBundle:
    bundle = await get_bundle(db, organization_id, bundle_id)
    if bundle.state != EdgeBundleState.DRAFT.value:
        raise BusinessRuleError("Only draft bundles can be published")
    # Supersede any other published bundle covering the same scope.
    others = (
        await db.execute(
            select(EdgeBundle).where(
                EdgeBundle.organization_id == organization_id,
                EdgeBundle.state == EdgeBundleState.PUBLISHED.value,
                EdgeBundle.group_id == bundle.group_id,
            )
        )
    ).scalars()
    for other in others:
        other.state = EdgeBundleState.EXPIRED.value
    bundle.state = EdgeBundleState.PUBLISHED.value
    await db.flush()

    from app.services import audit

    await audit.record(
        db, organization_id, action="EDGE_BUNDLE_PUBLISHED",
        entity_type="edge_bundle", entity_id=bundle.id, user_id=user_id,
    )
    logger.info("Edge bundle %s v%s published", bundle.id, bundle.bundle_version)
    return bundle


def bandwidth_policy(org: Organization) -> dict:
    stored = (org.settings_json or {}).get("bandwidth") or {}
    return {**DEFAULT_BANDWIDTH, **stored}


async def bundle_blocks_for_device(db: AsyncSession, device: Device) -> dict | None:
    """Contract-v2 `bundle` + `prefetch` + `bandwidth` blocks for a device
    covered by a published, unexpired bundle."""
    await _expire_due(db, device.organization_id)
    row = (
        await db.execute(
            select(EdgeBundle, EdgeBundleDevice)
            .join(EdgeBundleDevice, EdgeBundleDevice.bundle_id == EdgeBundle.id)
            .where(
                EdgeBundleDevice.device_id == device.id,
                EdgeBundle.state == EdgeBundleState.PUBLISHED.value,
            )
            .order_by(EdgeBundle.bundle_version.desc())
        )
    ).first()
    if row is None:
        return None
    bundle, _member = row
    org = await db.get(Organization, device.organization_id)
    return {
        "bundle": {
            "id": str(bundle.id),
            "version": bundle.bundle_version,
            "url": f"/api/v1/player/{device.id}/bundles/{bundle.id}",
            "signature": bundle.signature,
            "expires_at": bundle.expires_at.isoformat() if bundle.expires_at else None,
        },
        "prefetch": bundle.manifest_json.get("assets", []),
        "bandwidth": bandwidth_policy(org) if org else DEFAULT_BANDWIDTH,
    }


async def serve_bundle(
    db: AsyncSession, device: Device, bundle_id: uuid.UUID
) -> dict:
    """Bundle download for a covered device; marks the member synced. Asset
    URLs are minted fresh (signed, Range-resumable via the storage layer)."""
    from app.core.config import get_settings
    from app.integrations.storage import get_storage
    from app.repositories import content as content_repo
    from app.services.content import current_version

    bundle = (
        await db.execute(
            select(EdgeBundle).where(
                EdgeBundle.organization_id == device.organization_id,
                EdgeBundle.id == bundle_id,
                EdgeBundle.state == EdgeBundleState.PUBLISHED.value,
            )
        )
    ).scalar_one_or_none()
    if bundle is None:
        raise NotFoundError("Bundle not found")
    member = (
        await db.execute(
            select(EdgeBundleDevice).where(
                EdgeBundleDevice.bundle_id == bundle.id,
                EdgeBundleDevice.device_id == device.id,
            )
        )
    ).scalar_one_or_none()
    if member is None:
        raise NotFoundError("Bundle not found")

    storage = get_storage()
    settings = get_settings()
    assets = []
    for descriptor in bundle.manifest_json.get("assets", []):
        asset = await content_repo.get_asset(
            db, device.organization_id, uuid.UUID(descriptor["id"])
        )
        if asset is None:
            continue
        version = current_version(asset)
        if version is None:
            continue
        assets.append(
            {**descriptor,
             "url": storage.presigned_get_url(
                 version.object_key, settings.signed_url_ttl_seconds
             )}
        )
    member.state = "synced"
    member.synced_at = datetime.now(UTC)
    await db.flush()
    return {
        "id": str(bundle.id),
        "version": bundle.bundle_version,
        "signature": bundle.signature,
        "expires_at": bundle.expires_at.isoformat() if bundle.expires_at else None,
        "generated_at": bundle.manifest_json.get("generated_at"),
        "assets": assets,
    }


async def metrics(db: AsyncSession, organization_id: uuid.UUID) -> dict:
    await _expire_due(db, organization_id)
    bundles = await list_bundles(db, organization_id)
    by_state: dict[str, int] = {}
    pending = synced = 0
    for bundle in bundles:
        by_state[bundle.state] = by_state.get(bundle.state, 0) + 1
        if bundle.state == EdgeBundleState.PUBLISHED.value:
            for member in bundle.devices:
                if member.state == "synced":
                    synced += 1
                else:
                    pending += 1
    org = await db.get(Organization, organization_id)
    return {
        "bundles_by_state": by_state,
        "published_coverage": {"synced": synced, "pending": pending},
        "bandwidth_policy": bandwidth_policy(org) if org else DEFAULT_BANDWIDTH,
    }
