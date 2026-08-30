"""Authentication service: login, refresh rotation, logout (FR-AUTH-001/002)."""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.core.errors import UnauthenticatedError
from app.models import Organization, User
from app.models.organization import OrganizationStatus
from app.models.user import UserStatus
from app.repositories import auth as auth_repo
from app.repositories import users as users_repo

logger = logging.getLogger("app.auth")

_BAD_CREDENTIALS = "Invalid email or password"


def _as_utc(dt: datetime) -> datetime:
    """SQLite returns naive datetimes; treat naive as UTC."""
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


async def _issue_token_pair(
    db: AsyncSession, user: User, active_org: uuid.UUID | None = None
) -> dict:
    org_id = active_org or user.organization_id
    access_token, expires_in = security.create_access_token(user.id, org_id)
    refresh_token, jti, refresh_expires = security.create_refresh_token(user.id, org_id)
    await auth_repo.store(
        db,
        user_id=user.id,
        jti=jti,
        token_hash=security.hash_token(refresh_token),
        expires_at=refresh_expires,
    )
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": expires_in,
        "user": user,
    }


async def login(db: AsyncSession, *, email: str, password: str) -> dict:
    candidates = await users_repo.find_for_login(db, email)
    # Verify against every candidate (same email may exist in several tenants);
    # constant behavior regardless of which check fails.
    matched: User | None = None
    for candidate in candidates:
        if candidate.password_hash and security.verify_password(password, candidate.password_hash):
            matched = candidate
            break
    if matched is None:
        raise UnauthenticatedError(_BAD_CREDENTIALS)
    if matched.status != UserStatus.ACTIVE.value:
        raise UnauthenticatedError("Account is not active")

    org = await db.get(Organization, matched.organization_id)
    if org is None or org.status != OrganizationStatus.ACTIVE.value:
        raise UnauthenticatedError("Organization is not active")

    matched.last_login_at = datetime.now(UTC)
    await db.flush()
    from app.services import audit

    await audit.record(
        db,
        matched.organization_id,
        action="USER_LOGIN",
        entity_type="user",
        entity_id=matched.id,
        user_id=matched.id,
    )
    logger.info("User %s logged in", matched.id)
    return await _issue_token_pair(db, matched)


async def refresh(db: AsyncSession, *, refresh_token: str) -> dict:
    payload = security.decode_token(refresh_token, expected_type=security.TOKEN_TYPE_REFRESH)
    row = await auth_repo.get_by_hash(db, security.hash_token(refresh_token))
    if row is None or row.jti != payload["jti"]:
        raise UnauthenticatedError("Unknown refresh token")
    if row.revoked_at is not None:
        # Reuse of a rotated token is a theft signal: kill the whole session family.
        logger.warning("Revoked refresh token reused for user %s", row.user_id)
        await auth_repo.revoke_all_for_user(db, row.user_id)
        # Commit before raising — the request transaction rolls back on error,
        # and this revocation must survive the 401.
        await db.commit()
        raise UnauthenticatedError("Refresh token has been revoked")
    if _as_utc(row.expires_at) < datetime.now(UTC):
        raise UnauthenticatedError("Refresh token has expired")

    user = await db.get(User, row.user_id)
    if user is None or user.status != UserStatus.ACTIVE.value:
        raise UnauthenticatedError("Account is not active")

    # Preserve the active tenant across rotation — but only after
    # re-validating that the membership still exists and is active.
    active_org: uuid.UUID | None = None
    claim = payload.get("org")
    if claim is not None and uuid.UUID(claim) != user.organization_id:
        from app.services import memberships as memberships_service

        if not await memberships_service.can_access(db, user, uuid.UUID(claim)):
            raise UnauthenticatedError("No active membership for this organization")
        active_org = uuid.UUID(claim)

    await auth_repo.revoke(db, row)  # rotation: old token is single-use
    return await _issue_token_pair(db, user, active_org)


async def switch_tenant(
    db: AsyncSession, user: User, organization_id: uuid.UUID, *, refresh_token: str
) -> dict:
    """Issues a token pair scoped to another organization the user is a
    member of. The presented refresh token is revoked (rotation)."""
    from app.services import memberships as memberships_service

    membership = await memberships_service.can_access(db, user, organization_id)
    if not membership:
        raise UnauthenticatedError("No active membership for this organization")
    if membership is not True:  # guest org: permissions come from the membership role
        role = membership.role
        user.membership_permission_codes = (  # type: ignore[attr-defined]
            {perm.code for perm in role.permissions} if role is not None else set()
        )
    user.active_organization_id = organization_id  # type: ignore[attr-defined]
    org = await db.get(Organization, organization_id)
    if org is None or org.status != OrganizationStatus.ACTIVE.value:
        raise UnauthenticatedError("Organization is not active")

    row = await auth_repo.get_by_hash(db, security.hash_token(refresh_token))
    if row is not None and row.user_id == user.id and row.revoked_at is None:
        await auth_repo.revoke(db, row)

    from app.services import audit

    await audit.record(
        db,
        organization_id,
        action="TENANT_SWITCHED",
        entity_type="organization",
        entity_id=organization_id,
        user_id=user.id,
    )
    return await _issue_token_pair(db, user, organization_id)


async def logout(db: AsyncSession, *, refresh_token: str) -> None:
    """Revokes the presented refresh token. Idempotent; invalid tokens are
    ignored so logout never fails client-side."""
    try:
        security.decode_token(refresh_token, expected_type=security.TOKEN_TYPE_REFRESH)
    except UnauthenticatedError:
        return
    row = await auth_repo.get_by_hash(db, security.hash_token(refresh_token))
    if row is not None and row.revoked_at is None:
        await auth_repo.revoke(db, row)
        logger.info("User %s logged out", row.user_id)
