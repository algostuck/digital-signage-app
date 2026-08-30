"""Refresh-token persistence (rotation/revocation)."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RefreshToken


async def store(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    jti: str,
    token_hash: str,
    expires_at: datetime,
) -> RefreshToken:
    row = RefreshToken(user_id=user_id, jti=jti, token_hash=token_hash, expires_at=expires_at)
    db.add(row)
    await db.flush()
    return row


async def get_by_hash(db: AsyncSession, token_hash: str) -> RefreshToken | None:
    result = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    return result.scalar_one_or_none()


async def revoke(db: AsyncSession, row: RefreshToken) -> None:
    row.revoked_at = datetime.now(UTC)
    await db.flush()


async def revoke_all_for_user(db: AsyncSession, user_id: uuid.UUID) -> None:
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )
