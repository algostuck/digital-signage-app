"""Video wall API (P3-M04, slice 3C-1)."""

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentTenantId, CurrentUser, require_permissions
from app.db.session import get_db
from app.schemas.envelope import success
from app.services import video_walls as service

router = APIRouter(prefix="/video-walls")


class WallCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    canvas: dict | None = None
    sync_policy: dict | None = None


class MemberAdd(BaseModel):
    device_id: uuid.UUID
    viewport: dict
    role: str = "member"


class SyncIn(BaseModel):
    action: str  # start | stop


@router.get("", dependencies=[require_permissions("devices.view")])
async def list_walls(tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)) -> dict:
    walls = await service.list_walls(db, tenant_id)
    return success(
        [
            {"id": str(w.id), "name": w.name, "status": w.status,
             "canvas": w.canvas_json, "members": len(w.members)}
            for w in walls
        ]
    )


@router.post("", dependencies=[require_permissions("devices.manage")], status_code=201)
async def create_wall(
    body: WallCreate,
    tenant_id: CurrentTenantId,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    wall = await service.create_wall(
        db, tenant_id, name=body.name, canvas=body.canvas,
        sync_policy=body.sync_policy, user_id=user.id,
    )
    return success(await service.wall_state(db, tenant_id, wall.id))


@router.get("/{wall_id}", dependencies=[require_permissions("devices.view")])
async def get_wall(
    wall_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    return success(await service.wall_state(db, tenant_id, wall_id))


@router.delete("/{wall_id}", dependencies=[require_permissions("devices.manage")])
async def delete_wall(
    wall_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    await service.delete_wall(db, tenant_id, wall_id)
    return success({"deleted": True})


@router.post("/{wall_id}/members", dependencies=[require_permissions("devices.manage")])
async def add_member(
    wall_id: uuid.UUID,
    body: MemberAdd,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
) -> dict:
    await service.add_member(
        db, tenant_id, wall_id, device_id=body.device_id,
        viewport=body.viewport, role=body.role,
    )
    return success(await service.wall_state(db, tenant_id, wall_id))


@router.delete(
    "/{wall_id}/members/{member_id}", dependencies=[require_permissions("devices.manage")]
)
async def remove_member(
    wall_id: uuid.UUID,
    member_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
) -> dict:
    await service.remove_member(db, tenant_id, wall_id, member_id)
    return success(await service.wall_state(db, tenant_id, wall_id))


@router.post("/{wall_id}/sync", dependencies=[require_permissions("devices.control")])
async def sync(
    wall_id: uuid.UUID,
    body: SyncIn,
    tenant_id: CurrentTenantId,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    return success(
        await service.sync(db, tenant_id, wall_id, action=body.action, user_id=user.id)
    )
