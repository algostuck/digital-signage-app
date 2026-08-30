"""Shared API dependencies: authentication, tenant context, RBAC, pagination.

Tenant context comes exclusively from the authenticated principal
(FR-AUTH-007); nothing tenant-related is ever trusted from request input.
"""

import uuid
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.core.config import get_settings
from app.core.context import tenant_id_ctx, user_id_ctx
from app.core.errors import ForbiddenError, UnauthenticatedError
from app.db.session import get_db
from app.models import User
from app.models.user import UserStatus

_bearer = HTTPBearer(auto_error=False)


def user_permission_codes(user: User) -> set[str]:
    # API-key principals carry an explicit scope list (P2-INT-002).
    scopes = getattr(user, "api_key_scopes", None)
    if scopes is not None:
        return set(scopes)
    # Guest tenant context (SaaS core): permissions come from the
    # membership's role, not the home-org role assignments.
    membership_codes = getattr(user, "membership_permission_codes", None)
    if membership_codes is not None:
        return set(membership_codes)
    return {perm.code for role in user.roles for perm in role.permissions}


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Annotated[AsyncSession, Depends(get_db)],
    x_api_key: Annotated[str | None, Header()] = None,
) -> User:
    # X-API-Key path (P2-INT-002): a transient principal scoped to the
    # key's tenant + explicit scopes. Attributed to the key's creator for
    # auditing; never persisted.
    if x_api_key is not None:
        from app.services import api_keys as api_keys_service
        from app.services import entitlements as entitlements_service
        from app.services import usage as usage_service

        key = await api_keys_service.authenticate(db, x_api_key)

        # Entitlement gate (SaaS core): API access is plan-dependent, and
        # calls are metered against max_api_calls_month.
        effective = await entitlements_service.get_effective(db, key.organization_id)
        if not effective.enabled("api_access"):
            raise ForbiddenError(
                f"'api_access' is not included in the {effective.plan_name or 'current plan'}. "
                "Upgrade your subscription."
            )
        call_limit = effective.limit("max_api_calls_month")
        if call_limit is not None:
            used = await usage_service.metered_used(db, key.organization_id, "api_calls")
            if used >= call_limit:
                raise ForbiddenError(
                    f"API call limit reached ({used}/{call_limit}). "
                    "Upgrade your subscription."
                )
        await usage_service.record_metered(db, key.organization_id, "api_calls")

        principal = User(
            id=key.created_by,
            organization_id=key.organization_id,
            email=f"api-key:{key.prefix}",
            full_name=f"API key '{key.name}'",
            password_hash="",
            status=UserStatus.ACTIVE.value,
            is_superuser=False,
        )
        principal.api_key_scopes = list(key.scopes_json)  # type: ignore[attr-defined]
        tenant_id_ctx.set(key.organization_id)
        user_id_ctx.set(key.created_by)
        return principal

    if credentials is None:
        raise UnauthenticatedError("Missing bearer token")
    payload = security.decode_token(
        credentials.credentials, expected_type=security.TOKEN_TYPE_ACCESS
    )
    user = await db.get(User, uuid.UUID(payload["sub"]))
    if user is None or user.status != UserStatus.ACTIVE.value:
        raise UnauthenticatedError("Account is not active")

    # Active tenant comes from the token's org claim, verified against a
    # server-side membership — never from any client-supplied header/body.
    active_org = user.organization_id
    claim = payload.get("org")
    if claim is not None and uuid.UUID(claim) != user.organization_id:
        from app.services import memberships as memberships_service

        membership = await memberships_service.can_access(db, user, uuid.UUID(claim))
        if not membership:
            raise UnauthenticatedError("No active membership for this organization")
        active_org = uuid.UUID(claim)
        role = getattr(membership, "role", None)
        user.membership_permission_codes = (  # type: ignore[attr-defined]
            {perm.code for perm in role.permissions} if role is not None else set()
        )
        user.membership_is_owner = membership.is_owner  # type: ignore[attr-defined]

    user.active_organization_id = active_org  # type: ignore[attr-defined]
    tenant_id_ctx.set(active_org)
    user_id_ctx.set(user.id)
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_tenant_id(user: CurrentUser) -> uuid.UUID:
    return getattr(user, "active_organization_id", None) or user.organization_id


CurrentTenantId = Annotated[uuid.UUID, Depends(get_tenant_id)]


async def require_superuser(user: CurrentUser) -> User:
    """Platform-admin guard (SaaS core): tenant-facing roles never reach
    the /platform surface, whatever permissions they hold."""
    if not user.is_superuser:
        raise ForbiddenError("Platform administrator access required")
    return user


PlatformAdmin = Annotated[User, Depends(require_superuser)]


def require_permissions(*codes: str):
    """Endpoint guard: the user must hold every listed permission
    (superusers bypass)."""

    async def dependency(user: CurrentUser) -> User:
        if user.is_superuser:
            return user
        held = user_permission_codes(user)
        missing = [code for code in codes if code not in held]
        if missing:
            raise ForbiddenError(f"Missing permission: {', '.join(missing)}")
        return user

    return Depends(dependency)


@dataclass
class Pagination:
    page: int
    page_size: int


def get_pagination(
    page: int = Query(1, ge=1),
    page_size: int = Query(None, ge=1),
) -> Pagination:
    settings = get_settings()
    size = page_size or settings.default_page_size
    return Pagination(page=page, page_size=min(size, settings.max_page_size))


PageParams = Annotated[Pagination, Depends(get_pagination)]
