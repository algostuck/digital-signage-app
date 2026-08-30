"""User management service (FR-AUTH-004/005)."""

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.core.errors import BusinessRuleError, ConflictError, NotFoundError, ValidationAppError
from app.models import User
from app.models.user import UserStatus
from app.repositories import auth as auth_repo
from app.repositories import roles as roles_repo
from app.repositories import users as users_repo

logger = logging.getLogger("app.users")


async def _resolve_roles(db: AsyncSession, organization_id: uuid.UUID, role_ids: list[uuid.UUID]):
    roles = await roles_repo.get_visible_by_ids(db, organization_id, role_ids)
    if len(roles) != len(set(role_ids)):
        raise ValidationAppError("One or more roles do not exist", field="role_ids")
    return roles


async def list_users(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    q: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[User], int]:
    return await users_repo.search(
        db, organization_id, q=q, status=status, page=page, page_size=page_size
    )


async def get_user(db: AsyncSession, organization_id: uuid.UUID, user_id: uuid.UUID) -> User:
    user = await users_repo.get_by_id(db, organization_id, user_id)
    if user is None:
        raise NotFoundError("User not found")
    return user


async def create_user(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    email: str,
    full_name: str,
    password: str | None,
    role_ids: list[uuid.UUID],
) -> User:
    if await users_repo.get_by_email(db, organization_id, email):
        raise ConflictError("A user with this email already exists", field="email")
    from app.services.tenant_admin import ensure_user_quota

    await ensure_user_quota(db, organization_id)  # P2-TNT-002
    roles = await _resolve_roles(db, organization_id, role_ids)
    user = User(
        organization_id=organization_id,
        email=email.lower(),
        full_name=full_name,
        password_hash=security.hash_password(password) if password else None,
        status=UserStatus.ACTIVE.value if password else UserStatus.INVITED.value,
    )
    user.roles = roles
    db.add(user)
    await db.flush()
    from app.services import audit

    await audit.record(
        db,
        organization_id,
        action="USER_CREATED",
        entity_type="user",
        entity_id=user.id,
        after={"email": user.email, "roles": [r.name for r in roles]},
    )
    logger.info("User %s created", user.id)
    return user


async def update_user(
    db: AsyncSession,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    full_name: str | None = None,
    role_ids: list[uuid.UUID] | None = None,
) -> User:
    user = await get_user(db, organization_id, user_id)
    if full_name is not None:
        user.full_name = full_name
    if role_ids is not None:
        user.roles = await _resolve_roles(db, organization_id, role_ids)
    await db.flush()
    return user


async def deactivate_user(
    db: AsyncSession,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    acting_user_id: uuid.UUID,
) -> User:
    if user_id == acting_user_id:
        raise BusinessRuleError("You cannot deactivate your own account")
    user = await get_user(db, organization_id, user_id)
    user.status = UserStatus.DEACTIVATED.value
    await auth_repo.revoke_all_for_user(db, user.id)
    await db.flush()
    from app.services import audit

    await audit.record(
        db,
        organization_id,
        action="USER_DEACTIVATED",
        entity_type="user",
        entity_id=user.id,
        after={"email": user.email},
    )
    logger.info("User %s deactivated", user.id)
    return user


async def activate_user(
    db: AsyncSession, organization_id: uuid.UUID, user_id: uuid.UUID
) -> User:
    user = await get_user(db, organization_id, user_id)
    if user.status == UserStatus.INVITED.value and not user.password_hash:
        raise BusinessRuleError("Invited users become active when they set a password")
    user.status = UserStatus.ACTIVE.value
    await db.flush()
    return user
