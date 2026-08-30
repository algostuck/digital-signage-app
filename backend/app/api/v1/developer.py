"""Developer platform API (P3-M12 / P3-INT-103, slice 3A-3).

Everything gated by api_keys.manage AND the developer_portal entitlement —
the SRS pattern of permission + plan working together."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentTenantId, CurrentUser, require_permissions
from app.db.session import get_db
from app.schemas.envelope import success
from app.services import developer as developer_service

router = APIRouter(prefix="/developer")


class SimulateDeviceRequest(BaseModel):
    serial_no: str | None = Field(default=None, min_length=3, max_length=100)


async def _require_portal(db: AsyncSession, tenant_id) -> None:
    from app.services import entitlements

    await entitlements.require_feature(db, tenant_id, "developer_portal")


@router.get("/openapi", dependencies=[require_permissions("api_keys.manage")])
async def openapi_meta(tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)) -> dict:
    """Versioned API catalogue: products, lifecycle/deprecation, changelog,
    plus the interactive docs location (non-production)."""
    await _require_portal(db, tenant_id)
    return success(await developer_service.openapi_meta(db))


@router.get("/sandbox", dependencies=[require_permissions("api_keys.manage")])
async def get_sandbox(tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)) -> dict:
    await _require_portal(db, tenant_id)
    return success(await developer_service.sandbox_info(db, tenant_id))


@router.post("/sandbox", dependencies=[require_permissions("api_keys.manage")])
async def provision_sandbox(
    tenant_id: CurrentTenantId, user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> dict:
    """Idempotent: creates the tenant's isolated sandbox organization and
    grants the caller an owner membership (switch to it from the header)."""
    await _require_portal(db, tenant_id)
    _, created = await developer_service.ensure_sandbox(db, tenant_id, user)
    info = await developer_service.sandbox_info(db, tenant_id)
    return success({**(info or {}), "created": created})


@router.post(
    "/sandbox/simulate-device", dependencies=[require_permissions("api_keys.manage")]
)
async def simulate_device(
    body: SimulateDeviceRequest,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Registers + approves a simulated display in the sandbox through the
    real player pipeline; the token is shown exactly once."""
    await _require_portal(db, tenant_id)
    return success(
        await developer_service.simulate_device(db, tenant_id, serial=body.serial_no)
    )
