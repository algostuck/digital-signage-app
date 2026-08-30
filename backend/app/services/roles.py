"""Role management service. System roles are read-only for tenants."""

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BusinessRuleError, ConflictError, NotFoundError, ValidationAppError
from app.models import Permission, Role
from app.repositories import roles as roles_repo

logger = logging.getLogger("app.roles")


async def list_roles(db: AsyncSession, organization_id: uuid.UUID) -> list[Role]:
    return await roles_repo.list_visible(db, organization_id)


async def list_permissions(db: AsyncSession) -> list[Permission]:
    return await roles_repo.list_permissions(db)


async def _resolve_permissions(db: AsyncSession, codes: list[str]) -> list[Permission]:
    permissions = await roles_repo.get_permissions_by_codes(db, codes)
    if len(permissions) != len(set(codes)):
        known = {p.code for p in permissions}
        missing = sorted(set(codes) - known)
        raise ValidationAppError(
            f"Unknown permission codes: {', '.join(missing)}", field="permission_codes"
        )
    return permissions


async def create_role(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    name: str,
    description: str | None,
    permission_codes: list[str],
) -> Role:
    if await roles_repo.get_org_role_by_name(db, organization_id, name):
        raise ConflictError("A role with this name already exists", field="name")
    role = Role(
        organization_id=organization_id, name=name, description=description, is_system=False
    )
    role.permissions = await _resolve_permissions(db, permission_codes)
    db.add(role)
    await db.flush()
    logger.info("Role %s created", role.id)
    return role


async def update_role(
    db: AsyncSession,
    organization_id: uuid.UUID,
    role_id: uuid.UUID,
    *,
    name: str | None = None,
    description: str | None = None,
    permission_codes: list[str] | None = None,
) -> Role:
    role = await roles_repo.get_visible_by_id(db, organization_id, role_id)
    if role is None:
        raise NotFoundError("Role not found")
    if role.is_system or role.organization_id is None:
        raise BusinessRuleError("System roles cannot be modified")
    if name is not None and name != role.name:
        if await roles_repo.get_org_role_by_name(db, organization_id, name):
            raise ConflictError("A role with this name already exists", field="name")
        role.name = name
    if description is not None:
        role.description = description
    if permission_codes is not None:
        role.permissions = await _resolve_permissions(db, permission_codes)
    await db.flush()
    return role
