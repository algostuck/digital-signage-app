"""Scoped API keys (P2-INT-002, NFR2-05).

The raw key (`dsk_...`) is returned exactly once at creation; only its
SHA-256 digest is stored. Keys carry an explicit scope list (permission
codes) enforced by the same require_permissions guard as user sessions,
plus optional expiry and immediate revocation.
"""

import hashlib
import logging
import secrets
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import (
    ConflictError,
    NotFoundError,
    UnauthenticatedError,
    ValidationAppError,
)
from app.core.permissions import PERMISSIONS
from app.models import ApiKey

logger = logging.getLogger("app.api_keys")

KEY_PREFIX = "dsk_"
MAX_KEYS = 25


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


async def list_keys(db: AsyncSession, organization_id: uuid.UUID) -> list[ApiKey]:
    rows = await db.execute(
        select(ApiKey)
        .where(ApiKey.organization_id == organization_id)
        .order_by(ApiKey.created_at.desc())
    )
    return list(rows.scalars().all())


async def create_key(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    name: str,
    scopes: list[str],
    expires_at: datetime | None,
    created_by: uuid.UUID | None,
) -> tuple[ApiKey, str]:
    if not scopes or any(scope not in PERMISSIONS for scope in scopes):
        raise ValidationAppError(
            "scopes must be a non-empty list of known permission codes", field="scopes"
        )
    if expires_at is not None and expires_at <= datetime.now(UTC):
        raise ValidationAppError("expires_at must be in the future", field="expires_at")
    existing = await db.execute(
        select(ApiKey.id).where(
            ApiKey.organization_id == organization_id, ApiKey.name == name
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise ConflictError("An API key with this name already exists", field="name")
    count = len(await list_keys(db, organization_id))
    if count >= MAX_KEYS:
        from app.core.errors import BusinessRuleError

        raise BusinessRuleError(f"At most {MAX_KEYS} API keys per organization")

    raw = KEY_PREFIX + secrets.token_urlsafe(32)
    key = ApiKey(
        organization_id=organization_id,
        name=name,
        prefix=raw[:12],
        key_hash=_hash(raw),
        scopes_json=sorted(set(scopes)),
        created_by=created_by,
        expires_at=expires_at,
    )
    db.add(key)
    await db.flush()

    from app.services import audit

    await audit.record(
        db,
        organization_id,
        action="API_KEY_CREATED",
        entity_type="api_key",
        entity_id=key.id,
        after={"name": name, "prefix": key.prefix, "scopes": key.scopes_json},
        user_id=created_by,
    )
    logger.info("API key %s created (prefix %s)", key.id, key.prefix)
    return key, raw


async def revoke_key(
    db: AsyncSession,
    organization_id: uuid.UUID,
    key_id: uuid.UUID,
    *,
    user_id: uuid.UUID | None,
) -> ApiKey:
    key = (
        await db.execute(
            select(ApiKey).where(
                ApiKey.organization_id == organization_id, ApiKey.id == key_id
            )
        )
    ).scalar_one_or_none()
    if key is None:
        raise NotFoundError("API key not found")
    if key.revoked_at is None:
        key.revoked_at = datetime.now(UTC)
        await db.flush()

        from app.services import audit

        await audit.record(
            db,
            organization_id,
            action="API_KEY_REVOKED",
            entity_type="api_key",
            entity_id=key.id,
            after={"name": key.name, "prefix": key.prefix},
            user_id=user_id,
        )
    return key


async def authenticate(db: AsyncSession, raw_key: str) -> ApiKey:
    """X-API-Key auth path. Timing-safe by construction: lookup is by hash."""
    if not raw_key.startswith(KEY_PREFIX):
        raise UnauthenticatedError("Invalid API key")
    key = (
        await db.execute(select(ApiKey).where(ApiKey.key_hash == _hash(raw_key)))
    ).scalar_one_or_none()
    if key is None:
        raise UnauthenticatedError("Invalid API key")
    now = datetime.now(UTC)
    if key.revoked_at is not None:
        raise UnauthenticatedError("API key has been revoked")
    expires = key.expires_at
    if expires is not None:
        expires = expires if expires.tzinfo else expires.replace(tzinfo=UTC)
        if expires <= now:
            raise UnauthenticatedError("API key has expired")
    key.last_used_at = now
    await db.flush()
    return key
