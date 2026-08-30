from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, user_permission_codes
from app.core.config import get_settings
from app.core.ratelimit import rate_limit
from app.db.session import get_db
from app.schemas.auth import (
    CurrentUserOut,
    LoginRequest,
    LogoutRequest,
    MembershipOut,
    RefreshRequest,
    SwitchTenantRequest,
    TokenPairOut,
)
from app.schemas.envelope import success
from app.services import auth as auth_service
from app.services import memberships as memberships_service

router = APIRouter(prefix="/auth")


def _token_pair_out(result: dict) -> dict:
    user = result["user"]
    user_out = CurrentUserOut.model_validate(user)
    user_out.permissions = sorted(user_permission_codes(user))
    return TokenPairOut(
        access_token=result["access_token"],
        refresh_token=result["refresh_token"],
        token_type=result["token_type"],
        expires_in=result["expires_in"],
        user=user_out,
    ).model_dump(mode="json")


@router.post(
    "/login",
    dependencies=[rate_limit("login", lambda: get_settings().rate_limit_login_per_minute)],
)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)) -> dict:
    result = await auth_service.login(db, email=body.email, password=body.password)
    return success(_token_pair_out(result))


@router.post("/refresh")
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)) -> dict:
    result = await auth_service.refresh(db, refresh_token=body.refresh_token)
    return success(_token_pair_out(result))


@router.post("/logout")
async def logout(body: LogoutRequest, db: AsyncSession = Depends(get_db)) -> dict:
    await auth_service.logout(db, refresh_token=body.refresh_token)
    return success({"logged_out": True})


@router.get("/me")
async def me(user: CurrentUser) -> dict:
    out = CurrentUserOut.model_validate(user)
    out.permissions = sorted(user_permission_codes(user))
    return success(out.model_dump(mode="json"))


@router.get("/memberships")
async def memberships(user: CurrentUser, db: AsyncSession = Depends(get_db)) -> dict:
    tenants = await memberships_service.accessible_tenants(db, user)
    return success(
        [MembershipOut(**tenant._asdict()).model_dump(mode="json") for tenant in tenants]
    )


@router.post("/switch-tenant")
async def switch_tenant(
    body: SwitchTenantRequest, user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> dict:
    result = await auth_service.switch_tenant(
        db, user, body.organization_id, refresh_token=body.refresh_token
    )
    return success(_token_pair_out(result))
