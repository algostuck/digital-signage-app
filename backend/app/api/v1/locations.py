import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentTenantId, PageParams, require_permissions
from app.db.session import get_db
from app.models import Location
from app.repositories import locations as locations_repo
from app.schemas.envelope import success
from app.schemas.locations import (
    LocationCreate,
    LocationDetailOut,
    LocationMoveRequest,
    LocationOut,
    LocationTypeCreate,
    LocationTypeOut,
    LocationUpdate,
    SetTagsRequest,
    TagOut,
)
from app.services import locations as service
from app.services import organization as org_service

router = APIRouter()


def _out(node: Location) -> dict:
    return LocationOut.model_validate(node).model_dump(mode="json")


def _tree_out(entries: list[dict]) -> list[dict]:
    return [
        {"node": _out(e["node"]), "children": _tree_out(e["children"])} for e in entries
    ]


@router.get("/locations/tree", dependencies=[require_permissions("locations.view")])
async def get_tree(tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)) -> dict:
    nodes = await locations_repo.list_all_active(db, tenant_id)
    return success(_tree_out(service.build_tree(nodes)))


@router.get("/locations", dependencies=[require_permissions("locations.view")])
async def list_locations(
    tenant_id: CurrentTenantId,
    pagination: PageParams,
    q: str | None = Query(None, max_length=200),
    type_id: uuid.UUID | None = None,
    status: str | None = Query(None, max_length=20),
    parent_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    nodes, total = await locations_repo.search(
        db,
        tenant_id,
        q=q,
        type_id=type_id,
        status=status,
        parent_id=parent_id,
        page=pagination.page,
        page_size=pagination.page_size,
    )
    return success(
        [_out(n) for n in nodes],
        page=pagination.page,
        page_size=pagination.page_size,
        total=total,
    )


@router.post("/locations", dependencies=[require_permissions("locations.manage")], status_code=201)
async def create_location(
    body: LocationCreate, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    node = await service.create_location(
        db,
        tenant_id,
        name=body.name,
        parent_id=body.parent_id,
        type_id=body.type_id,
        code=body.code,
        address=body.address,
        latitude=body.latitude,
        longitude=body.longitude,
        timezone=body.timezone,
        metadata_json=body.metadata_json,
    )
    return success(_out(node))


@router.get("/locations/{location_id}", dependencies=[require_permissions("locations.view")])
async def get_location(
    location_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    node = await service.get_location(db, tenant_id, location_id)
    org = await org_service.get_organization(db, tenant_id)
    ancestors = await locations_repo.get_by_ids(db, tenant_id, node.ancestor_ids())
    children = await locations_repo.children_of(db, tenant_id, node.id)
    _, descendants_count = await locations_repo.descendants_of(
        db, tenant_id, node, page=1, page_size=1
    )
    out = LocationDetailOut(
        **LocationOut.model_validate(node).model_dump(),
        effective_timezone=service.effective_timezone(node, ancestors, org),
        children_count=len([c for c in children if c.status == "active"]),
        descendants_count=descendants_count,
    )
    return success(out.model_dump(mode="json"))


@router.patch("/locations/{location_id}", dependencies=[require_permissions("locations.manage")])
async def update_location(
    location_id: uuid.UUID,
    body: LocationUpdate,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
) -> dict:
    node = await service.update_location(
        db,
        tenant_id,
        location_id,
        name=body.name,
        type_id=body.type_id,
        code=body.code,
        address=body.address,
        latitude=body.latitude,
        longitude=body.longitude,
        timezone=body.timezone,
        metadata_json=body.metadata_json,
    )
    return success(_out(node))


@router.post(
    "/locations/{location_id}/move", dependencies=[require_permissions("locations.manage")]
)
async def move_location(
    location_id: uuid.UUID,
    body: LocationMoveRequest,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
) -> dict:
    node = await service.move_location(
        db, tenant_id, location_id, new_parent_id=body.new_parent_id
    )
    return success(_out(node))


@router.delete("/locations/{location_id}", dependencies=[require_permissions("locations.manage")])
async def archive_location(
    location_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    node = await service.archive_location(db, tenant_id, location_id)
    return success(_out(node))


@router.post(
    "/locations/{location_id}/restore", dependencies=[require_permissions("locations.manage")]
)
async def restore_location(
    location_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    node = await service.restore_location(db, tenant_id, location_id)
    return success(_out(node))


@router.get(
    "/locations/{location_id}/children", dependencies=[require_permissions("locations.view")]
)
async def get_children(
    location_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    node = await service.get_location(db, tenant_id, location_id)
    children = await locations_repo.children_of(db, tenant_id, node.id)
    return success([_out(c) for c in children])


@router.get(
    "/locations/{location_id}/descendants",
    dependencies=[require_permissions("locations.view")],
)
async def get_descendants(
    location_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    pagination: PageParams,
    db: AsyncSession = Depends(get_db),
) -> dict:
    node = await service.get_location(db, tenant_id, location_id)
    nodes, total = await locations_repo.descendants_of(
        db, tenant_id, node, page=pagination.page, page_size=pagination.page_size
    )
    return success(
        [_out(n) for n in nodes],
        page=pagination.page,
        page_size=pagination.page_size,
        total=total,
    )


@router.post(
    "/locations/{location_id}/tags", dependencies=[require_permissions("locations.manage")]
)
async def set_tags(
    location_id: uuid.UUID,
    body: SetTagsRequest,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
) -> dict:
    node = await service.set_location_tags(
        db, tenant_id, location_id, [(t.key, t.value) for t in body.tags]
    )
    return success(_out(node))


# --- location types & tags dictionaries ---


@router.get("/location-types", dependencies=[require_permissions("locations.view")])
async def list_location_types(
    tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    types = await service.list_location_types(db, tenant_id)
    return success([LocationTypeOut.model_validate(t).model_dump(mode="json") for t in types])


@router.post(
    "/location-types", dependencies=[require_permissions("locations.manage")], status_code=201
)
async def create_location_type(
    body: LocationTypeCreate, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    location_type = await service.create_location_type(
        db, tenant_id, code=body.code, name=body.name
    )
    return success(LocationTypeOut.model_validate(location_type).model_dump(mode="json"))


@router.get("/tags", dependencies=[require_permissions("locations.view")])
async def list_tags(tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)) -> dict:
    tags = await locations_repo.list_tags(db, tenant_id)
    return success([TagOut.model_validate(t).model_dump(mode="json") for t in tags])
