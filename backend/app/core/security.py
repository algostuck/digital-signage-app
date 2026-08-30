"""Password hashing and JWT issuance/validation.

Access tokens are short-lived stateless JWTs. Refresh tokens are JWTs whose
jti is persisted (hashed) server-side so they can be rotated and revoked
(FR-AUTH-002). Nothing secret is ever stored in plaintext.
"""

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError

from app.core.config import get_settings
from app.core.errors import UnauthenticatedError

_hasher: PasswordHasher | None = None

TOKEN_TYPE_ACCESS = "access"  # noqa: S105 - token *type* label, not a secret
TOKEN_TYPE_REFRESH = "refresh"  # noqa: S105 - token *type* label, not a secret


def _get_hasher() -> PasswordHasher:
    """Argon2id with library defaults in real environments; the test
    environment uses the cheapest valid parameters so suite time measures
    the application, not KDF cost."""
    global _hasher
    if _hasher is None:
        if get_settings().environment == "test":
            _hasher = PasswordHasher(time_cost=1, memory_cost=8 * 1024, parallelism=1)
        else:
            _hasher = PasswordHasher()
    return _hasher


def hash_password(password: str) -> str:
    return _get_hasher().hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _get_hasher().verify(password_hash, password)
    except (VerifyMismatchError, VerificationError):
        return False


def hash_token(token: str) -> str:
    """Digest stored server-side for refresh tokens (never the token itself)."""
    return hashlib.sha256(token.encode()).hexdigest()


def _create_token(
    *, user_id: uuid.UUID, organization_id: uuid.UUID, token_type: str, lifetime: timedelta
) -> tuple[str, str, datetime]:
    settings = get_settings()
    jti = str(uuid.uuid4())
    expires_at = datetime.now(UTC) + lifetime
    payload = {
        "sub": str(user_id),
        "org": str(organization_id),
        "type": token_type,
        "jti": jti,
        "iat": datetime.now(UTC),
        "exp": expires_at,
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, jti, expires_at


def create_access_token(user_id: uuid.UUID, organization_id: uuid.UUID) -> tuple[str, int]:
    settings = get_settings()
    lifetime = timedelta(minutes=settings.access_token_expire_minutes)
    token, _, _ = _create_token(
        user_id=user_id,
        organization_id=organization_id,
        token_type=TOKEN_TYPE_ACCESS,
        lifetime=lifetime,
    )
    return token, int(lifetime.total_seconds())


def create_refresh_token(
    user_id: uuid.UUID, organization_id: uuid.UUID
) -> tuple[str, str, datetime]:
    settings = get_settings()
    return _create_token(
        user_id=user_id,
        organization_id=organization_id,
        token_type=TOKEN_TYPE_REFRESH,
        lifetime=timedelta(days=settings.refresh_token_expire_days),
    )


def decode_token(token: str, *, expected_type: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError as exc:
        raise UnauthenticatedError("Token has expired") from exc
    except jwt.InvalidTokenError as exc:
        raise UnauthenticatedError("Invalid token") from exc
    if payload.get("type") != expected_type:
        raise UnauthenticatedError("Invalid token type")
    return payload
