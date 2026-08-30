"""Dynamic data sources (P3-M02, slice 3A-2).

Lifecycle: create source → (optional) declare schema → fetch (guarded) →
validate → snapshot. The refresh beat keeps snapshots warm; the manifest
serves the latest VALID snapshot with staleness metadata so widgets follow
the degradation ladder: fresh → TTL-stale (still served) → last-known-good
→ widget fallback_json (P3-DAT-004/005). Devices never fetch feeds.

Transformations (P3-DAT-003) are a declarative pick/map/limit spec —
never code: {"path": "a.b", "fields": {"out": "in.path"}, "limit": N}.
"""

import logging
import os
import uuid
import xml.etree.ElementTree as ET  # noqa: S405 - bounded, size-capped feed input
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import (
    BusinessRuleError,
    ConflictError,
    NotFoundError,
    ValidationAppError,
)
from app.integrations.fetch import FetchError, guarded_fetch
from app.models import DataSource, DataSourceSchema, DataSourceSnapshot
from app.models.data_source import DataSourceState, DataSourceType

logger = logging.getLogger("app.data_sources")

MAX_SOURCES = 25
SNAPSHOT_KEEP = 20  # bounded history per source
MIN_REFRESH_SECONDS = 60
TRANSFORM_KEYS = {"path", "fields", "limit"}


# --- transforms + schema validation (pure, deterministic) ---


def _pick(data, path: str):
    """Dot-path lookup; a list at any step means 'first element'."""
    current = data
    for part in path.split("."):
        if isinstance(current, list):
            current = current[0] if current else None
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def validate_transform(spec: dict) -> None:
    if not isinstance(spec, dict):
        raise ValidationAppError("transform must be an object", field="transform")
    unknown = set(spec) - TRANSFORM_KEYS
    if unknown:
        raise ValidationAppError(
            f"Unknown transform keys: {sorted(unknown)}", field="transform"
        )
    if "path" in spec and not isinstance(spec["path"], str):
        raise ValidationAppError("transform.path must be a string", field="transform")
    fields = spec.get("fields")
    if fields is not None and (
        not isinstance(fields, dict)
        or not all(isinstance(k, str) and isinstance(v, str) for k, v in fields.items())
    ):
        raise ValidationAppError(
            "transform.fields must map output keys to input paths", field="transform"
        )
    limit = spec.get("limit")
    if limit is not None and (not isinstance(limit, int) or not 1 <= limit <= 100):
        raise ValidationAppError("transform.limit must be 1..100", field="transform")


def apply_transform(data, spec: dict | None):
    """Safe mapping/filter (P3-DAT-003): no code execution, bounded output."""
    if not spec:
        return data
    result = _pick(data, spec["path"]) if spec.get("path") else data
    fields = spec.get("fields")
    if isinstance(result, list):
        limit = spec.get("limit", 50)
        items = result[:limit]
        if fields:
            items = [{out: _pick(item, path) for out, path in fields.items()} for item in items]
        return items
    if fields and isinstance(result, dict):
        return {out: _pick(result, path) for out, path in fields.items()}
    return result


def validate_schema_spec(schema: dict) -> None:
    """Declared shape: {"required": ["dot.path", ...]} (2D-small format)."""
    if not isinstance(schema, dict):
        raise ValidationAppError("schema must be an object", field="schema")
    required = schema.get("required")
    if (
        required is None
        or not isinstance(required, list)
        or not required
        or not all(isinstance(p, str) and p for p in required)
    ):
        raise ValidationAppError(
            'schema needs {"required": ["dot.path", ...]}', field="schema"
        )
    unknown = set(schema) - {"required"}
    if unknown:
        raise ValidationAppError(f"Unknown schema keys: {sorted(unknown)}", field="schema")


def validate_payload(schema: dict | None, payload) -> str | None:
    """Returns an error string when the payload violates the declared
    schema; None when valid (or no schema declared)."""
    if not schema:
        return None
    root = payload[0] if isinstance(payload, list) and payload else payload
    missing = [path for path in schema["required"] if _pick(root, path) is None]
    if missing:
        return f"Missing required paths: {missing}"
    return None


# --- parsing ---


def _parse_rss(body: bytes) -> dict:
    """RSS 2.0 / Atom → normalized {"title", "items": [...]} JSON."""
    try:
        root = ET.fromstring(body)  # noqa: S314 - size-capped, no external entities in ET
    except ET.ParseError as exc:
        raise FetchError(f"Invalid XML: {str(exc)[:200]}") from exc

    def text(el, *names):
        for name in names:
            found = el.find(name)
            if found is not None and found.text:
                return found.text.strip()
        return None

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    items = []
    channel = root.find("channel")
    if channel is not None:  # RSS 2.0
        title = text(channel, "title")
        for item in channel.findall("item")[:100]:
            items.append(
                {
                    "title": text(item, "title"),
                    "link": text(item, "link"),
                    "published": text(item, "pubDate"),
                    "summary": text(item, "description"),
                }
            )
    elif root.tag.endswith("feed"):  # Atom
        title = text(root, "atom:title") or text(root, "title")
        for entry in root.findall("atom:entry", ns)[:100]:
            link = entry.find("atom:link", ns)
            items.append(
                {
                    "title": text(entry, "atom:title"),
                    "link": link.get("href") if link is not None else None,
                    "published": text(entry, "atom:updated", "atom:published"),
                    "summary": text(entry, "atom:summary", "atom:content"),
                }
            )
    else:
        raise FetchError("Not an RSS/Atom document")
    return {"title": title, "items": items}


def _parse_payload(source: DataSource, body: bytes):
    if source.type == DataSourceType.RSS.value:
        return _parse_rss(body)
    import json

    try:
        return json.loads(body)
    except ValueError as exc:
        raise FetchError(f"Invalid JSON: {str(exc)[:200]}") from exc


# --- CRUD ---


async def get_source(
    db: AsyncSession, organization_id: uuid.UUID, source_id: uuid.UUID
) -> DataSource:
    source = (
        await db.execute(
            select(DataSource).where(
                DataSource.organization_id == organization_id,
                DataSource.id == source_id,
            )
        )
    ).scalar_one_or_none()
    if source is None:
        raise NotFoundError("Data source not found")
    return source


async def list_sources(db: AsyncSession, organization_id: uuid.UUID) -> list[DataSource]:
    rows = await db.execute(
        select(DataSource)
        .where(DataSource.organization_id == organization_id)
        .order_by(DataSource.name)
    )
    return list(rows.scalars().all())


def _validate_settings(
    type_: str, endpoint: str, cache_ttl_seconds: int, refresh_seconds: int
) -> None:
    if type_ not in {t.value for t in DataSourceType}:
        raise ValidationAppError("type must be rest_json or rss", field="type")
    if not endpoint.startswith(("http://", "https://")):
        raise ValidationAppError("endpoint must be http(s)", field="endpoint")
    if cache_ttl_seconds < 30:
        raise ValidationAppError("cache_ttl_seconds must be >= 30", field="cache_ttl_seconds")
    if refresh_seconds < MIN_REFRESH_SECONDS:
        raise ValidationAppError(
            f"refresh_seconds must be >= {MIN_REFRESH_SECONDS}", field="refresh_seconds"
        )


async def create_source(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    name: str,
    type: str,
    endpoint: str,
    auth_header: str | None = None,
    auth_token_ref: str | None = None,
    cache_ttl_seconds: int = 300,
    refresh_seconds: int = 900,
    schema: dict | None = None,
) -> DataSource:
    from app.services import entitlements

    await entitlements.require_feature(db, organization_id, "dynamic_data")
    _validate_settings(type, endpoint, cache_ttl_seconds, refresh_seconds)
    if schema is not None:
        validate_schema_spec(schema)
    count = (
        await db.execute(
            select(func.count()).where(DataSource.organization_id == organization_id)
        )
    ).scalar_one()
    if count >= MAX_SOURCES:
        raise BusinessRuleError(f"At most {MAX_SOURCES} data sources")
    exists = (
        await db.execute(
            select(DataSource).where(
                DataSource.organization_id == organization_id, DataSource.name == name
            )
        )
    ).scalar_one_or_none()
    if exists is not None:
        raise ConflictError("A data source with this name already exists", field="name")

    source = DataSource(
        organization_id=organization_id,
        name=name,
        type=type,
        endpoint=endpoint,
        auth_header=auth_header,
        auth_token_ref=auth_token_ref,
        cache_ttl_seconds=cache_ttl_seconds,
        refresh_seconds=refresh_seconds,
    )
    db.add(source)
    await db.flush()
    if schema is not None:
        db.add(DataSourceSchema(source_id=source.id, version_no=1, schema_json=schema))
        await db.flush()
    await db.refresh(source, ["schemas"])

    from app.services import audit

    await audit.record(
        db,
        organization_id,
        action="DATA_SOURCE_CREATED",
        entity_type="data_source",
        entity_id=source.id,
        after={"name": name, "type": type, "endpoint": endpoint},
    )
    return source


async def update_source(
    db: AsyncSession,
    organization_id: uuid.UUID,
    source_id: uuid.UUID,
    **changes,
) -> DataSource:
    from app.services import entitlements

    await entitlements.require_feature(db, organization_id, "dynamic_data")
    source = await get_source(db, organization_id, source_id)
    for field in (
        "name",
        "endpoint",
        "auth_header",
        "auth_token_ref",
        "cache_ttl_seconds",
        "refresh_seconds",
        "state",
    ):
        if field in changes and changes[field] is not None:
            setattr(source, field, changes[field])
    if source.state not in {s.value for s in DataSourceState}:
        raise ValidationAppError("Unknown state", field="state")
    _validate_settings(
        source.type, source.endpoint, source.cache_ttl_seconds, source.refresh_seconds
    )
    await db.flush()
    return source


async def delete_source(
    db: AsyncSession, organization_id: uuid.UUID, source_id: uuid.UUID
) -> None:
    source = await get_source(db, organization_id, source_id)
    await db.delete(source)
    await db.flush()


async def add_schema_version(
    db: AsyncSession, organization_id: uuid.UUID, source_id: uuid.UUID, schema: dict
) -> DataSourceSchema:
    from app.services import entitlements

    await entitlements.require_feature(db, organization_id, "dynamic_data")
    validate_schema_spec(schema)
    source = await get_source(db, organization_id, source_id)
    next_no = (source.schemas[-1].version_no + 1) if source.schemas else 1
    row = DataSourceSchema(source_id=source.id, version_no=next_no, schema_json=schema)
    db.add(row)
    await db.flush()
    await db.refresh(source, ["schemas"])
    return row


def current_schema(source: DataSource) -> dict | None:
    return source.schemas[-1].schema_json if source.schemas else None


# --- fetch + snapshots ---


def _request_headers(source: DataSource) -> dict:
    headers = {"Accept": "application/json, application/rss+xml, application/xml, text/xml"}
    if source.auth_token_ref:
        token = os.environ.get(source.auth_token_ref)
        if token:
            headers[source.auth_header or "Authorization"] = (
                token if source.auth_header else f"Bearer {token}"
            )
    return headers


async def _fetch(source: DataSource) -> bytes:
    """Isolated for tests (monkeypatch target)."""
    return await guarded_fetch(source.endpoint, headers=_request_headers(source))


async def _bound_snapshots(db: AsyncSession, source_id: uuid.UUID) -> None:
    keep_ids = (
        await db.execute(
            select(DataSourceSnapshot.id)
            .where(DataSourceSnapshot.source_id == source_id)
            .order_by(DataSourceSnapshot.fetched_at.desc())
            .limit(SNAPSHOT_KEEP)
        )
    ).scalars().all()
    await db.execute(
        delete(DataSourceSnapshot).where(
            DataSourceSnapshot.source_id == source_id,
            DataSourceSnapshot.id.not_in(keep_ids),
        )
    )


async def fetch_source(
    db: AsyncSession, source: DataSource, *, store: bool = True
) -> DataSourceSnapshot:
    """Guarded fetch → parse → schema-validate → snapshot. Never raises on
    feed failure — the failure IS the snapshot (state machine + evidence)."""
    now = datetime.now(UTC)
    payload = None
    error: str | None = None
    try:
        body = await _fetch(source)
        payload = _parse_payload(source, body)
        error = validate_payload(current_schema(source), payload)
    except FetchError as exc:
        error = str(exc)

    snapshot = DataSourceSnapshot(
        source_id=source.id,
        fetched_at=now,
        valid=error is None,
        payload_json=payload if error is None else None,
        error=error,
    )
    if store:
        db.add(snapshot)
        if error is None:
            source.state = DataSourceState.ACTIVE.value
            source.last_ok_at = now
            source.last_error = None
        else:
            source.state = DataSourceState.ERROR.value
            source.last_error = error[:500]
            logger.warning("Data source %s fetch failed: %s", source.id, error)
        await db.flush()
        await _bound_snapshots(db, source.id)
        await db.flush()
    return snapshot


async def latest_valid_snapshot(
    db: AsyncSession, source_id: uuid.UUID
) -> DataSourceSnapshot | None:
    """Last-known-good (P3-DAT-004): survives any number of failed fetches."""
    return (
        await db.execute(
            select(DataSourceSnapshot)
            .where(
                DataSourceSnapshot.source_id == source_id,
                DataSourceSnapshot.valid.is_(True),
            )
            .order_by(DataSourceSnapshot.fetched_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def health(db: AsyncSession, organization_id: uuid.UUID, source_id: uuid.UUID) -> dict:
    source = await get_source(db, organization_id, source_id)
    latest = (
        await db.execute(
            select(DataSourceSnapshot)
            .where(DataSourceSnapshot.source_id == source_id)
            .order_by(DataSourceSnapshot.fetched_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    good = await latest_valid_snapshot(db, source_id)
    now = datetime.now(UTC)

    def age(ts):
        if ts is None:
            return None
        ts = ts if ts.tzinfo else ts.replace(tzinfo=UTC)
        return int((now - ts).total_seconds())

    return {
        "state": source.state,
        "last_ok_at": source.last_ok_at.isoformat() if source.last_ok_at else None,
        "last_error": source.last_error,
        "last_fetch": {
            "at": latest.fetched_at.isoformat() if latest else None,
            "valid": latest.valid if latest else None,
            "error": latest.error if latest else None,
        },
        "cache_age_seconds": age(good.fetched_at) if good else None,
        "stale": (age(good.fetched_at) or 0) > source.cache_ttl_seconds if good else None,
        "has_last_known_good": good is not None,
    }


async def refresh_due_sources(db: AsyncSession, *, limit: int = 20) -> dict:
    """Beat sweep: refetch active sources whose newest snapshot is older
    than refresh_seconds (or that have never been fetched)."""
    now = datetime.now(UTC)
    sources = (
        await db.execute(
            select(DataSource).where(DataSource.state != DataSourceState.PAUSED.value)
        )
    ).scalars().all()
    refreshed = failed = 0
    for source in sources:
        if refreshed + failed >= limit:
            break
        newest_at = (
            await db.execute(
                select(func.max(DataSourceSnapshot.fetched_at)).where(
                    DataSourceSnapshot.source_id == source.id
                )
            )
        ).scalar_one_or_none()
        if newest_at is not None:
            newest_at = newest_at if newest_at.tzinfo else newest_at.replace(tzinfo=UTC)
            if newest_at > now - timedelta(seconds=source.refresh_seconds):
                continue
        snapshot = await fetch_source(db, source)
        if snapshot.valid:
            refreshed += 1
        else:
            failed += 1
    return {"refreshed": refreshed, "failed": failed, "scanned": len(sources)}


# --- manifest integration (player contract v2 `data` block) ---


async def data_block_for_canvas(
    db: AsyncSession, organization_id: uuid.UUID, canvas: dict | None
) -> dict:
    """{zone_key: {source_id, fetched_at, stale, data}} for every zone whose
    widget carries a data_binding. Serves the latest VALID snapshot with the
    declared transform applied; a source with no good snapshot yields
    data=None and the player falls back to the widget's fallback_json."""
    if not canvas:
        return {}
    block: dict = {}
    now = datetime.now(UTC)
    for zone in canvas.get("zones", []):
        ref = zone.get("widget") or {}
        binding = ref.get("data_binding") or {}
        raw_id = binding.get("source_id")
        if not raw_id:
            continue
        try:
            source = await get_source(db, organization_id, uuid.UUID(str(raw_id)))
        except (NotFoundError, ValueError):
            continue
        good = await latest_valid_snapshot(db, source.id)
        entry = {
            "source_id": str(source.id),
            "fetched_at": None,
            "stale": None,
            "data": None,
        }
        if good is not None:
            fetched = (
                good.fetched_at
                if good.fetched_at.tzinfo
                else good.fetched_at.replace(tzinfo=UTC)
            )
            entry["fetched_at"] = fetched.isoformat()
            entry["stale"] = (now - fetched).total_seconds() > source.cache_ttl_seconds
            try:
                entry["data"] = apply_transform(good.payload_json, binding.get("transform"))
            except Exception:  # noqa: BLE001 - a bad transform must never break the manifest
                entry["data"] = good.payload_json
        block[str(zone.get("key"))] = entry
    return block
