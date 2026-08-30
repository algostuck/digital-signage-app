"""Enterprise SSO API (P3-GLO-002, slice 3E-1).

Provider management is tenant-admin surface; the login/callback endpoints
are public (keyed by org code, CSRF-protected by the signed state)."""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentTenantId, CurrentUser, require_permissions
from app.api.v1.auth import _token_pair_out
from app.db.session import get_db
from app.schemas.envelope import success
from app.services import sso as service

router = APIRouter()


class ProviderUpsert(BaseModel):
    issuer: str = Field(min_length=8, max_length=500)
    client_id: str = Field(min_length=1, max_length=200)
    client_secret_ref: str = Field(min_length=1, max_length=100)
    claim_mapping: dict | None = None
    active: bool | None = None


class CallbackIn(BaseModel):
    code: str
    state: str
    redirect_uri: str


def _provider_out(provider) -> dict:
    return {
        "id": str(provider.id),
        "protocol": provider.protocol,
        "issuer": provider.issuer,
        "client_id": provider.client_id,
        "client_secret_ref": provider.client_secret_ref,  # env var NAME only
        "claim_mapping": provider.claim_mapping_json,
        "active": provider.active,
        "endpoints": provider.metadata_json,
    }


@router.get("/sso/providers", dependencies=[require_permissions("settings.manage")])
async def get_provider(tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)) -> dict:
    provider = await service.get_provider(db, tenant_id)
    return success(_provider_out(provider) if provider else None)


@router.post("/sso/providers", dependencies=[require_permissions("settings.manage")])
async def upsert_provider(
    body: ProviderUpsert,
    tenant_id: CurrentTenantId,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    provider = await service.upsert_provider(
        db, tenant_id,
        issuer=body.issuer, client_id=body.client_id,
        client_secret_ref=body.client_secret_ref,
        claim_mapping=body.claim_mapping, active=body.active, user_id=user.id,
    )
    return success(_provider_out(provider))


@router.post("/sso/providers/test", dependencies=[require_permissions("settings.manage")])
async def test_provider(tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)) -> dict:
    return success(await service.test_provider(db, tenant_id))


# --- public login flow (org-code keyed) ---


@router.get("/auth/sso/{org_code}/login")
async def sso_login(
    org_code: str,
    db: AsyncSession = Depends(get_db),
    redirect_uri: str = Query(...),
) -> dict:
    """Returns the IdP authorization URL (the SPA redirects the browser)."""
    return success(await service.login_redirect(db, org_code, redirect_uri))


@router.post("/auth/sso/{org_code}/callback")
async def sso_callback(
    org_code: str, body: CallbackIn, db: AsyncSession = Depends(get_db)
) -> dict:
    result = await service.complete_login(
        db, org_code, code=body.code, state=body.state, redirect_uri=body.redirect_uri
    )
    return success(_token_pair_out(result))
