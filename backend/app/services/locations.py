"""Location hierarchy service (FR-LOC-001..007).

Path invariant: every node's path is `<parent.path><own id>/` (root:
`/<own id>/`). All structural mutations run inside the request transaction.
"""

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BusinessRuleError, ConflictError, NotFoundError, ValidationAppError
from app.models import Location, LocationType, Organization
from app.models.location import LocationStatus
from app.repositories import locations as repo
from app.services.organization import validate_timezone

logger = logging.getLogger("app.locations")

DEFAULT_LOCATION_TYPES: list[tuple[str, str]] = [
    ("country", "Country"),
    ("region", "Region"),
    ("state", "State"),
    ("city", "City"),
    ("zone", "Zone"),
    ("mall", "Mall"),
    ("store", "Store"),
    ("building", "Building"),
    ("floor", "Floor"),
    ("department", "Department"),
    ("room", "Room"),
    ("outdoor", "Outdoor"),
    ("custom", "Custom"),
]


async def get_location(
    db: AsyncSession, organization_id: uuid.UUID, location_id: uuid.UUID
) -> Location:
    node = await repo.get_by_id(db, organization_id, location_id)
    if node is None:
        raise NotFoundError("Location not found")
    return node


async def _validate_type(
    db: AsyncSession, organization_id: uuid.UUID, type_id: uuid.UUID | None
) -> None:
    if type_id is not None and await repo.get_type_by_id(db, organization_id, type_id) is None:
        raise ValidationAppError("Unknown location type", field="type_id")


async def _check_code_unique(
    db: AsyncSession,
    organization_id: uuid.UUID,
    parent_id: uuid.UUID | None,
    code: str | None,
    *,
    exclude_id: uuid.UUID | None = None,
) -> None:
    if code is None:
        return
    siblings = (
        await repo.children_of(db, organization_id, parent_id)
        if parent_id
        else [
            loc
            for loc in await repo.list_all_active(db, organization_id)
            if loc.parent_id is None
        ]
    )
    for sibling in siblings:
        if sibling.code == code and sibling.id != exclude_id:
            raise ConflictError(
                "A sibling location with this code already exists", field="code"
            )


async def create_location(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    name: str,
    parent_id: uuid.UUID | None,
    type_id: uuid.UUID | None,
    code: str | None = None,
    address: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    timezone: str | None = None,
    metadata_json: dict | None = None,
) -> Location:
    from sqlalchemy import func as sa_func
    from sqlalchemy import select

    from app.services import entitlements as entitlements_service

    active_count = (
        await db.execute(
            select(sa_func.count()).where(
                Location.organization_id == organization_id,
                Location.status == LocationStatus.ACTIVE.value,
            )
        )
    ).scalar_one()
    await entitlements_service.ensure_limit(
        db, organization_id, "max_locations", active_count, resource_label="Location"
    )

    parent: Location | None = None
    if parent_id is not None:
        parent = await get_location(db, organization_id, parent_id)
        if parent.status != LocationStatus.ACTIVE.value:
            raise BusinessRuleError("Cannot create a child under an archived location")
    await _validate_type(db, organization_id, type_id)
    if timezone is not None:
        validate_timezone(timezone)
    await _check_code_unique(db, organization_id, parent_id, code)

    # The ORM default would only assign the id at flush time; the path needs
    # it now, so generate explicitly.
    node_id = uuid.uuid4()
    node = Location(
        id=node_id,
        organization_id=organization_id,
        parent_id=parent_id,
        type_id=type_id,
        name=name,
        code=code,
        address=address,
        latitude=latitude,
        longitude=longitude,
        timezone=timezone,
        metadata_json=metadata_json,
        status=LocationStatus.ACTIVE.value,
        path=f"{parent.path if parent else '/'}{node_id}/",
    )
    db.add(node)
    await db.flush()
    # New instances haven't been through a SELECT, so the selectin
    # relationships are unloaded; load them before serialization.
    await db.refresh(node, ["type", "tags"])
    from app.services import audit

    await audit.record(
        db, organization_id, action="LOCATION_CREATED", entity_type="location",
        entity_id=node.id, after={"name": name, "parent_id": str(parent_id) if parent_id else None},
    )
    logger.info("Location %s created under %s", node.id, parent_id)
    return node


async def update_location(
    db: AsyncSession,
    organization_id: uuid.UUID,
    location_id: uuid.UUID,
    *,
    name: str | None = None,
    type_id: uuid.UUID | None = None,
    code: str | None = None,
    address: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    timezone: str | None = None,
    metadata_json: dict | None = None,
) -> Location:
    node = await get_location(db, organization_id, location_id)
    if name is not None:
        node.name = name
    if type_id is not None:
        await _validate_type(db, organization_id, type_id)
        node.type_id = type_id
    if code is not None:
        await _check_code_unique(
            db, organization_id, node.parent_id, code, exclude_id=node.id
        )
        node.code = code
    if address is not None:
        node.address = address
    if latitude is not None:
        node.latitude = latitude
    if longitude is not None:
        node.longitude = longitude
    if timezone is not None:
        validate_timezone(timezone)
        node.timezone = timezone
    if metadata_json is not None:
        node.metadata_json = metadata_json
    await db.flush()
    return node


async def move_location(
    db: AsyncSession,
    organization_id: uuid.UUID,
    location_id: uuid.UUID,
    *,
    new_parent_id: uuid.UUID | None,
) -> Location:
    """Re-parents a node; rewrites the whole subtree's paths (FR-LOC-007)."""
    node = await get_location(db, organization_id, location_id)
    if new_parent_id == node.parent_id:
        return node

    new_parent_path = "/"
    if new_parent_id is not None:
        if new_parent_id == node.id:
            raise BusinessRuleError("A location cannot be its own parent")
        parent = await get_location(db, organization_id, new_parent_id)
        if parent.path.startswith(node.path):
            raise BusinessRuleError(
                "Cannot move a location into its own subtree"
            )
        if parent.status != LocationStatus.ACTIVE.value:
            raise BusinessRuleError("Cannot move a location under an archived location")
        new_parent_path = parent.path

    await _check_code_unique(db, organization_id, new_parent_id, node.code, exclude_id=node.id)

    old_prefix = node.path
    new_prefix = f"{new_parent_path}{node.id}/"
    await repo.rewrite_subtree_paths(db, organization_id, old_prefix, new_prefix)
    node.parent_id = new_parent_id
    await db.flush()
    # The bulk UPDATE bypassed the ORM; reload path (and keep relationships loaded).
    await db.refresh(node, ["path", "type", "tags"])
    logger.info("Location %s moved under %s", node.id, new_parent_id)
    return node


async def archive_location(
    db: AsyncSession, organization_id: uuid.UUID, location_id: uuid.UUID
) -> Location:
    node = await get_location(db, organization_id, location_id)
    if node.status == LocationStatus.ARCHIVED.value:
        return node
    if await repo.count_active_children(db, organization_id, node.id) > 0:
        raise BusinessRuleError("Archive or move child locations first")
    node.status = LocationStatus.ARCHIVED.value
    await db.flush()
    logger.info("Location %s archived", node.id)
    return node


async def restore_location(
    db: AsyncSession, organization_id: uuid.UUID, location_id: uuid.UUID
) -> Location:
    node = await get_location(db, organization_id, location_id)
    if node.parent_id is not None:
        parent = await get_location(db, organization_id, node.parent_id)
        if parent.status != LocationStatus.ACTIVE.value:
            raise BusinessRuleError("Restore the parent location first")
    node.status = LocationStatus.ACTIVE.value
    await db.flush()
    return node


async def set_location_tags(
    db: AsyncSession,
    organization_id: uuid.UUID,
    location_id: uuid.UUID,
    tags: list[tuple[str, str]],
) -> Location:
    """Replace-set semantics: the node ends up with exactly these tags."""
    node = await get_location(db, organization_id, location_id)
    node.tags = [
        await repo.get_or_create_tag(db, organization_id, key, value) for key, value in tags
    ]
    await db.flush()
    return node


def effective_timezone(node: Location, ancestors: list[Location], org: Organization) -> str:
    """Node timezone, else nearest ancestor's, else the organization's
    (NFR-012: explicit IANA identifiers at every level)."""
    if node.timezone:
        return node.timezone
    by_id = {a.id: a for a in ancestors}
    for ancestor_id in reversed(node.ancestor_ids()):
        ancestor = by_id.get(ancestor_id)
        if ancestor is not None and ancestor.timezone:
            return ancestor.timezone
    return org.timezone


def build_tree(nodes: list[Location]) -> list[dict]:
    """Assembles path-ordered nodes into a nested tree in one pass."""
    roots: list[dict] = []
    by_id: dict[uuid.UUID, dict] = {}
    for node in nodes:
        entry = {"node": node, "children": []}
        by_id[node.id] = entry
        parent_entry = by_id.get(node.parent_id) if node.parent_id else None
        if parent_entry is not None:
            parent_entry["children"].append(entry)
        else:
            roots.append(entry)
    return roots


# --- location types ---


async def list_location_types(
    db: AsyncSession, organization_id: uuid.UUID
) -> list[LocationType]:
    return await repo.list_types(db, organization_id)


async def create_location_type(
    db: AsyncSession, organization_id: uuid.UUID, *, code: str, name: str
) -> LocationType:
    if await repo.get_type_by_code(db, organization_id, code):
        raise ConflictError("A location type with this code already exists", field="code")
    location_type = LocationType(organization_id=organization_id, code=code, name=name)
    db.add(location_type)
    await db.flush()
    return location_type


async def seed_default_location_types(db: AsyncSession, organization_id: uuid.UUID) -> None:
    """Idempotent; used at org creation and by the seed script."""
    existing = {t.code for t in await repo.list_types(db, organization_id)}
    for code, name in DEFAULT_LOCATION_TYPES:
        if code not in existing:
            db.add(LocationType(organization_id=organization_id, code=code, name=name))
    await db.flush()
