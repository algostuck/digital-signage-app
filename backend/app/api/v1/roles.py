import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentTenantId, require_permissions
from app.db.session import get_db
from app.schemas.envelope import success
from app.schemas.roles import PermissionOut, RoleCreate, RoleOut, RoleUpdate
from app.services import roles as roles_service

router = APIRouter()


@router.get("/roles", dependencies=[require_permissions("roles.view")])
async def list_roles(tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)) -> dict:
    roles = await roles_service.list_roles(db, tenant_id)
    return success([RoleOut.model_validate(r).model_dump(mode="json") for r in roles])


@router.post("/roles", dependencies=[require_permissions("roles.manage")], status_code=201)
async def create_role(
    body: RoleCreate, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    role = await roles_service.create_role(
        db,
        tenant_id,
        name=body.name,
        description=body.description,
        permission_codes=body.permission_codes,
    )
    return success(RoleOut.model_validate(role).model_dump(mode="json"))


@router.patch("/roles/{role_id}", dependencies=[require_permissions("roles.manage")])
async def update_role(
    role_id: uuid.UUID,
    body: RoleUpdate,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
) -> dict:
    role = await roles_service.update_role(
        db,
        tenant_id,
        role_id,
        name=body.name,
        description=body.description,
        permission_codes=body.permission_codes,
    )
    return success(RoleOut.model_validate(role).model_dump(mode="json"))


@router.get("/permissions", dependencies=[require_permissions("roles.view")])
async def list_permissions(db: AsyncSession = Depends(get_db)) -> dict:
    permissions = await roles_service.list_permissions(db)
    return success([PermissionOut.model_validate(p).model_dump(mode="json") for p in permissions])
