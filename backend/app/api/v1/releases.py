"""Player Update Center API (P2-05): releases, staged rollouts, rollback."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentTenantId, require_permissions
from app.db.session import get_db
from app.schemas.envelope import success
from app.schemas.releases import ReleaseCreate, ReleaseOut, RolloutStart
from app.services import player_updates

router = APIRouter()


async def _release_out(db: AsyncSession, tenant_id: uuid.UUID, release) -> dict:
    out = ReleaseOut.model_validate(release).model_dump(mode="json")
    out["rollout"] = await player_updates.rollout_progress(db, tenant_id, release.id)
    return out


@router.get("/player-releases", dependencies=[require_permissions("releases.manage")])
async def list_releases(tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)) -> dict:
    releases = await player_updates.list_releases(db, tenant_id)
    return success([await _release_out(db, tenant_id, r) for r in releases])


@router.post("/player-releases", dependencies=[require_permissions("releases.manage")])
async def create_release(
    body: ReleaseCreate, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    release = await player_updates.create_release(
        db,
        tenant_id,
        version=body.version,
        package_asset_id=body.package_asset_id,
        notes=body.notes,
    )
    return success(await _release_out(db, tenant_id, release))


@router.get(
    "/player-releases/{release_id}", dependencies=[require_permissions("releases.manage")]
)
async def get_release(
    release_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    release = await player_updates.get_release(db, tenant_id, release_id)
    return success(await _release_out(db, tenant_id, release))


@router.post(
    "/player-releases/{release_id}/rollouts",
    dependencies=[require_permissions("releases.manage")],
)
async def start_rollout(
    release_id: uuid.UUID,
    body: RolloutStart,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
) -> dict:
    await player_updates.start_rollout(
        db,
        tenant_id,
        release_id,
        group_id=body.group_id,
        rings=body.rings,
        failure_threshold_pct=body.failure_threshold_pct,
    )
    release = await player_updates.get_release(db, tenant_id, release_id)
    return success(await _release_out(db, tenant_id, release))


@router.post(
    "/player-releases/{release_id}/rollback",
    dependencies=[require_permissions("releases.manage")],
)
async def rollback_release(
    release_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    release = await player_updates.rollback_release(db, tenant_id, release_id)
    return success(await _release_out(db, tenant_id, release))


@router.get("/rollouts", dependencies=[require_permissions("releases.manage")])
async def list_rollouts(tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)) -> dict:
    """Every release that has rings, newest first — the Update Center list."""
    releases = await player_updates.list_releases(db, tenant_id)
    out = []
    for release in releases:
        rollout = await player_updates.rollout_progress(db, tenant_id, release.id)
        if rollout:
            entry = ReleaseOut.model_validate(release).model_dump(mode="json")
            entry["rollout"] = rollout
            out.append(entry)
    return success(out)


@router.get("/rollouts/{batch_id}", dependencies=[require_permissions("releases.manage")])
async def rollout_batch_devices(
    batch_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    return success(await player_updates.batch_devices(db, tenant_id, batch_id))
