"""Tenant membership (SaaS core): one user identity, many organizations.

A user's row lives in their HOME organization (Phase-1 model, unchanged) —
home access is implicit and uses the existing user_roles. `tenant_users`
rows grant the same identity access to OTHER organizations with exactly one
tenant-scoped role. Never trust a client-supplied tenant id: every switch
verifies membership server-side.
"""

import logging
import uuid
from typing import NamedTuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import (
    BusinessRuleError,
    ConflictError,
    NotFoundError,
    ValidationAppError,
)
from app.models import Organization, Role, TenantUser, User
from app.models.saas import MembershipStatus
from app.models.user import UserStatus

logger = logging.getLogger("app.memberships")


class TenantAccess(NamedTuple):
    organization_id: uuid.UUID
    organization_name: str
    is_home: bool
    is_owner: bool
    role_name: str | None


async def get_membership(
    db: AsyncSession, organization_id: uuid.UUID, user_id: uuid.UUID
) -> TenantUser | None:
    return (
        await db.execute(
            select(TenantUser).where(
                TenantUser.organization_id == organization_id,
                TenantUser.user_id == user_id,
            )
        )
    ).scalar_one_or_none()


async def can_access(
    db: AsyncSession, user: User, organization_id: uuid.UUID
) -> TenantUser | None | bool:
    """True/membership when the user may act inside the organization:
    home org (implicit), any active organization for a platform
    administrator, or an active guest membership."""
    if organization_id == user.organization_id:
        return True
    if user.is_superuser:
        # The platform administrator operates every tenant by definition;
        # requiring a tenant_users row per organization only meant new
        # tenants were invisible to the switcher until someone remembered
        # to add one. Superusers bypass permission checks, so the home-org
        # shape (True) is the right return.
        org = await db.get(Organization, organization_id)
        return org is not None and org.status == "active"
    membership = await get_membership(db, organization_id, user.id)
    if membership is not None and membership.status == MembershipStatus.ACTIVE.value:
        return membership
    return None


async def accessible_tenants(db: AsyncSession, user: User) -> list[TenantAccess]:
    home = await db.get(Organization, user.organization_id)
    result = [
        TenantAccess(
            organization_id=user.organization_id,
            organization_name=home.name if home else "",
            is_home=True,
            is_owner=True,
            role_name=None,
        )
    ]
    if user.is_superuser:
        # Every active tenant, home first; explicit guest rows would only
        # duplicate entries here.
        orgs = (
            await db.execute(
                select(Organization)
                .where(
                    Organization.status == "active",
                    Organization.id != user.organization_id,
                )
                .order_by(Organization.name)
            )
        ).scalars()
        result.extend(
            TenantAccess(
                organization_id=org.id,
                organization_name=org.name,
                is_home=False,
                is_owner=True,
                role_name="Platform administrator",
            )
            for org in orgs
        )
        return result
    rows = await db.execute(
        select(TenantUser, Organization)
        .join(Organization, Organization.id == TenantUser.organization_id)
        .where(
            TenantUser.user_id == user.id,
            TenantUser.status == MembershipStatus.ACTIVE.value,
        )
        .order_by(Organization.name)
    )
    for membership, org in rows.all():
        result.append(
            TenantAccess(
                organization_id=org.id,
                organization_name=org.name,
                is_home=False,
                is_owner=membership.is_owner,
                role_name=membership.role.name if membership.role else None,
            )
        )
    return result


async def list_members(db: AsyncSession, organization_id: uuid.UUID) -> list[dict]:
    """Home users + guest memberships of one organization."""
    members: list[dict] = []
    home_users = (
        await db.execute(
            select(User).where(User.organization_id == organization_id).order_by(User.email)
        )
    ).scalars()
    for user in home_users:
        members.append(
            {
                "user_id": str(user.id),
                "email": user.email,
                "full_name": user.full_name,
                "status": user.status,
                "kind": "home",
                "is_owner": bool(user.is_superuser),
                "roles": [role.name for role in user.roles],
            }
        )
    rows = await db.execute(
        select(TenantUser, User)
        .join(User, User.id == TenantUser.user_id)
        .where(TenantUser.organization_id == organization_id)
        .order_by(User.email)
    )
    for membership, user in rows.all():
        members.append(
            {
                "user_id": str(user.id),
                "membership_id": str(membership.id),
                "email": user.email,
                "full_name": user.full_name,
                "status": membership.status,
                "kind": "guest",
                "is_owner": membership.is_owner,
                "roles": [membership.role.name] if membership.role else [],
            }
        )
    return members


async def add_member(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    email: str,
    role_id: uuid.UUID,
    is_owner: bool = False,
) -> TenantUser:
    """Grants an EXISTING platform user (from another organization) access
    to this organization. Creating brand-new users stays on /users."""
    user = (
        await db.execute(
            select(User).where(
                func.lower(User.email) == email.lower(),
                User.status == UserStatus.ACTIVE.value,
            )
        )
    ).scalars().first()
    if user is None:
        raise NotFoundError("No active user with this email exists on the platform")
    if user.organization_id == organization_id:
        raise BusinessRuleError("This user already belongs to this organization")
    if await get_membership(db, organization_id, user.id) is not None:
        raise ConflictError("This user is already a member")

    role = (
        await db.execute(
            select(Role).where(
                Role.id == role_id,
                (Role.organization_id == organization_id)
                | (Role.organization_id.is_(None)),
            )
        )
    ).scalar_one_or_none()
    if role is None:
        raise ValidationAppError("Role not found in this organization", field="role_id")

    membership = TenantUser(
        organization_id=organization_id,
        user_id=user.id,
        role_id=role.id,
        is_owner=is_owner,
    )
    db.add(membership)
    await db.flush()
    await db.refresh(membership, ["role"])

    from app.services import audit

    await audit.record(
        db,
        organization_id,
        action="MEMBER_ADDED",
        entity_type="tenant_user",
        entity_id=membership.id,
        after={"email": user.email, "role": role.name, "is_owner": is_owner},
    )
    logger.info("User %s added to org %s as %s", user.id, organization_id, role.name)
    return membership


async def update_member(
    db: AsyncSession,
    organization_id: uuid.UUID,
    membership_id: uuid.UUID,
    *,
    role_id: uuid.UUID | None = None,
    is_owner: bool | None = None,
    status: str | None = None,
) -> TenantUser:
    membership = (
        await db.execute(
            select(TenantUser).where(
                TenantUser.organization_id == organization_id,
                TenantUser.id == membership_id,
            )
        )
    ).scalar_one_or_none()
    if membership is None:
        raise NotFoundError("Membership not found")
    if role_id is not None:
        role = (
            await db.execute(
                select(Role).where(
                    Role.id == role_id,
                    (Role.organization_id == organization_id)
                    | (Role.organization_id.is_(None)),
                )
            )
        ).scalar_one_or_none()
        if role is None:
            raise ValidationAppError("Role not found in this organization", field="role_id")
        membership.role_id = role.id
    if is_owner is not None:
        membership.is_owner = is_owner
    if status is not None:
        if status not in {s.value for s in MembershipStatus}:
            raise ValidationAppError("Unknown membership status", field="status")
        membership.status = status
    await db.flush()
    await db.refresh(membership, ["role"])
    return membership


async def remove_member(
    db: AsyncSession, organization_id: uuid.UUID, membership_id: uuid.UUID
) -> None:
    membership = (
        await db.execute(
            select(TenantUser).where(
                TenantUser.organization_id == organization_id,
                TenantUser.id == membership_id,
            )
        )
    ).scalar_one_or_none()
    if membership is None:
        raise NotFoundError("Membership not found")
    await db.delete(membership)
    await db.flush()

    from app.services import audit

    await audit.record(
        db,
        organization_id,
        action="MEMBER_REMOVED",
        entity_type="tenant_user",
        entity_id=membership_id,
    )
