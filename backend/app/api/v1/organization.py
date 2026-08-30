from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentTenantId, CurrentUser, require_permissions
from app.db.session import get_db
from app.schemas.envelope import success
from app.schemas.organization import OrganizationOut, OrganizationUpdate
from app.services import organization as org_service
from app.services import tenant_admin

router = APIRouter(prefix="/organization")


@router.get("", dependencies=[require_permissions("organization.view")])
async def get_organization(
    tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    org = await org_service.get_organization(db, tenant_id)
    return success(OrganizationOut.model_validate(org).model_dump(mode="json"))


@router.get("/usage", dependencies=[require_permissions("organization.view")])
async def usage(tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)) -> dict:
    """Effective limits (plan ∧ platform quota override) + live usage.
    Read-only for tenants — quota overrides are edited on /platform."""
    return success(await tenant_admin.get_usage(db, tenant_id))


@router.get("/retention", dependencies=[require_permissions("settings.manage")])
async def get_retention(tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)) -> dict:
    return success(await tenant_admin.get_retention(db, tenant_id))


@router.put("/retention", dependencies=[require_permissions("settings.manage")])
async def update_retention(
    body: dict,
    tenant_id: CurrentTenantId,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """P2-AUD-003 / NFR2-06: per-tenant retention within platform limits."""
    return success(
        await tenant_admin.update_retention(db, tenant_id, body, user_id=user.id)
    )


@router.patch("", dependencies=[require_permissions("organization.manage")])
async def update_organization(
    body: OrganizationUpdate, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    org = await org_service.update_organization(
        db,
        tenant_id,
        name=body.name,
        timezone=body.timezone,
        locale=body.locale,
        branding_json=body.branding_json,
    )
    return success(OrganizationOut.model_validate(org).model_dump(mode="json"))
