"""Dynamic data sources API (P3-M02, slice 3A-2).

Reads need layouts.view (designers pick sources); writes need
settings.manage AND the `dynamic_data` entitlement (checked in the
service). Secrets are never stored — only env-var references."""

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentTenantId, require_permissions
from app.db.session import get_db
from app.schemas.envelope import success
from app.services import data_sources as service

router = APIRouter(prefix="/data-sources")


class DataSourceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    type: str = "rest_json"
    endpoint: str = Field(min_length=1, max_length=1000)
    auth_header: str | None = Field(default=None, max_length=100)
    auth_token_ref: str | None = Field(default=None, max_length=100)
    cache_ttl_seconds: int = Field(default=300, ge=30)
    refresh_seconds: int = Field(default=900, ge=60)
    schema_spec: dict | None = None


class DataSourceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    endpoint: str | None = Field(default=None, min_length=1, max_length=1000)
    auth_header: str | None = Field(default=None, max_length=100)
    auth_token_ref: str | None = Field(default=None, max_length=100)
    cache_ttl_seconds: int | None = Field(default=None, ge=30)
    refresh_seconds: int | None = Field(default=None, ge=60)
    state: str | None = None


class SchemaIn(BaseModel):
    schema_spec: dict


def _source_out(source) -> dict:
    return {
        "id": str(source.id),
        "name": source.name,
        "type": source.type,
        "endpoint": source.endpoint,
        "auth_header": source.auth_header,
        "auth_token_ref": source.auth_token_ref,  # env-var NAME, not a secret
        "cache_ttl_seconds": source.cache_ttl_seconds,
        "refresh_seconds": source.refresh_seconds,
        "state": source.state,
        "last_ok_at": source.last_ok_at.isoformat() if source.last_ok_at else None,
        "last_error": source.last_error,
        "schema": service.current_schema(source),
        "schema_version": source.schemas[-1].version_no if source.schemas else None,
    }


@router.get("", dependencies=[require_permissions("layouts.view")])
async def list_sources(tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)) -> dict:
    sources = await service.list_sources(db, tenant_id)
    return success([_source_out(s) for s in sources])


@router.post("", dependencies=[require_permissions("settings.manage")], status_code=201)
async def create_source(
    body: DataSourceCreate, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    source = await service.create_source(
        db,
        tenant_id,
        name=body.name,
        type=body.type,
        endpoint=body.endpoint,
        auth_header=body.auth_header,
        auth_token_ref=body.auth_token_ref,
        cache_ttl_seconds=body.cache_ttl_seconds,
        refresh_seconds=body.refresh_seconds,
        schema=body.schema_spec,
    )
    return success(_source_out(source))


@router.patch("/{source_id}", dependencies=[require_permissions("settings.manage")])
async def update_source(
    source_id: uuid.UUID,
    body: DataSourceUpdate,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
) -> dict:
    source = await service.update_source(
        db,
        tenant_id,
        source_id,
        name=body.name,
        endpoint=body.endpoint,
        auth_header=body.auth_header,
        auth_token_ref=body.auth_token_ref,
        cache_ttl_seconds=body.cache_ttl_seconds,
        refresh_seconds=body.refresh_seconds,
        state=body.state,
    )
    return success(_source_out(source))


@router.delete("/{source_id}", dependencies=[require_permissions("settings.manage")])
async def delete_source(
    source_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    await service.delete_source(db, tenant_id, source_id)
    return success({"deleted": True})


@router.put("/{source_id}/schema", dependencies=[require_permissions("settings.manage")])
async def put_schema(
    source_id: uuid.UUID,
    body: SchemaIn,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
) -> dict:
    row = await service.add_schema_version(db, tenant_id, source_id, body.schema_spec)
    return success({"version_no": row.version_no, "schema": row.schema_json})


@router.post("/{source_id}/test", dependencies=[require_permissions("settings.manage")])
async def test_source(
    source_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    """Dry-run: guarded fetch + schema validation, nothing stored."""
    from app.services import entitlements

    await entitlements.require_feature(db, tenant_id, "dynamic_data")
    source = await service.get_source(db, tenant_id, source_id)
    snapshot = await service.fetch_source(db, source, store=False)
    sample = snapshot.payload_json
    if isinstance(sample, list):
        sample = sample[:3]
    elif isinstance(sample, dict) and isinstance(sample.get("items"), list):
        sample = {**sample, "items": sample["items"][:3]}
    return success({"ok": snapshot.valid, "error": snapshot.error, "sample": sample})


@router.post("/{source_id}/refresh", dependencies=[require_permissions("settings.manage")])
async def refresh_source(
    source_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    from app.services import entitlements

    await entitlements.require_feature(db, tenant_id, "dynamic_data")
    source = await service.get_source(db, tenant_id, source_id)
    snapshot = await service.fetch_source(db, source)
    return success({"ok": snapshot.valid, "error": snapshot.error})


@router.get("/{source_id}/health", dependencies=[require_permissions("layouts.view")])
async def source_health(
    source_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    return success(await service.health(db, tenant_id, source_id))
