"""Edge bundle API (P3-M06, slice 3C-2)."""

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentTenantId, CurrentUser, require_permissions
from app.db.session import get_db
from app.schemas.envelope import success
from app.services import edge as service

router = APIRouter(prefix="/edge")


class BundleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    group_id: uuid.UUID | None = None
    ttl_days: int = Field(default=7, ge=1, le=90)


def _bundle_out(bundle) -> dict:
    synced = sum(1 for m in bundle.devices if m.state == "synced")
    return {
        "id": str(bundle.id),
        "name": bundle.name,
        "version": bundle.bundle_version,
        "group_id": str(bundle.group_id) if bundle.group_id else None,
        "state": bundle.state,
        "expires_at": bundle.expires_at.isoformat() if bundle.expires_at else None,
        "assets": len(bundle.manifest_json.get("assets", [])),
        "devices": len(bundle.devices),
        "synced": synced,
        "signature": bundle.signature,
    }


@router.get("/bundles", dependencies=[require_permissions("devices.view")])
async def list_bundles(tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)) -> dict:
    bundles = await service.list_bundles(db, tenant_id)
    return success([_bundle_out(b) for b in bundles])


@router.post("/bundles", dependencies=[require_permissions("devices.manage")], status_code=201)
async def create_bundle(
    body: BundleCreate,
    tenant_id: CurrentTenantId,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    bundle = await service.create_bundle(
        db, tenant_id, name=body.name, group_id=body.group_id,
        ttl_days=body.ttl_days, user_id=user.id,
    )
    return success(_bundle_out(bundle))


@router.post(
    "/bundles/{bundle_id}/publish", dependencies=[require_permissions("devices.manage")]
)
async def publish_bundle(
    bundle_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    bundle = await service.publish_bundle(db, tenant_id, bundle_id, user_id=user.id)
    return success(_bundle_out(bundle))


@router.get("/metrics", dependencies=[require_permissions("monitoring.view")])
async def metrics(tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)) -> dict:
    return success(await service.metrics(db, tenant_id))
