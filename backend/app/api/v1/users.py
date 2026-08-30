import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentTenantId, CurrentUser, PageParams, require_permissions
from app.db.session import get_db
from app.schemas.envelope import success
from app.schemas.users import UserCreate, UserOut, UserUpdate
from app.services import users as users_service

router = APIRouter(prefix="/users")


@router.get("", dependencies=[require_permissions("users.view")])
async def list_users(
    tenant_id: CurrentTenantId,
    pagination: PageParams,
    q: str | None = Query(None, max_length=200),
    status: str | None = Query(None, max_length=20),
    db: AsyncSession = Depends(get_db),
) -> dict:
    users, total = await users_service.list_users(
        db, tenant_id, q=q, status=status, page=pagination.page, page_size=pagination.page_size
    )
    return success(
        [UserOut.model_validate(u).model_dump(mode="json") for u in users],
        page=pagination.page,
        page_size=pagination.page_size,
        total=total,
    )


@router.post("", dependencies=[require_permissions("users.manage")], status_code=201)
async def create_user(
    body: UserCreate, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    user = await users_service.create_user(
        db,
        tenant_id,
        email=body.email,
        full_name=body.full_name,
        password=body.password,
        role_ids=body.role_ids,
    )
    return success(UserOut.model_validate(user).model_dump(mode="json"))


@router.get("/{user_id}", dependencies=[require_permissions("users.view")])
async def get_user(
    user_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    user = await users_service.get_user(db, tenant_id, user_id)
    return success(UserOut.model_validate(user).model_dump(mode="json"))


@router.patch("/{user_id}", dependencies=[require_permissions("users.manage")])
async def update_user(
    user_id: uuid.UUID,
    body: UserUpdate,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
) -> dict:
    user = await users_service.update_user(
        db, tenant_id, user_id, full_name=body.full_name, role_ids=body.role_ids
    )
    return success(UserOut.model_validate(user).model_dump(mode="json"))


@router.delete("/{user_id}", dependencies=[require_permissions("users.manage")])
async def deactivate_user(
    user_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    user = await users_service.deactivate_user(
        db, tenant_id, user_id, acting_user_id=current_user.id
    )
    return success(UserOut.model_validate(user).model_dump(mode="json"))


@router.post("/{user_id}/activate", dependencies=[require_permissions("users.manage")])
async def activate_user(
    user_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    user = await users_service.activate_user(db, tenant_id, user_id)
    return success(UserOut.model_validate(user).model_dump(mode="json"))
