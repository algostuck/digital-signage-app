"""Enterprise SSO service (P3-GLO-002, slice 3E-1) — OIDC code flow.

The IdP authenticates; the PLATFORM authorizes: a successful callback maps
claims to an existing (or auto-provisioned) user in the tenant and issues
the standard JWT pair — RBAC, memberships and the entitlement engine are
completely untouched. Secrets by reference (env var names); the state
parameter is HMAC-signed and time-boxed; issuer metadata is fetched through
the SSRF-guarded fetcher; id_tokens are verified against the issuer's JWKS.
"""

import base64
import hashlib
import hmac
import json
import logging
import time
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import (
    BusinessRuleError,
    NotFoundError,
    UnauthenticatedError,
    ValidationAppError,
)
from app.integrations.fetch import FetchError, assert_public_url, guarded_fetch
from app.models import Organization, Role, SsoProvider, User
from app.models.organization import OrganizationStatus
from app.models.user import UserStatus

logger = logging.getLogger("app.sso")

STATE_TTL_SECONDS = 600


# --- provider CRUD ---


async def get_provider(db: AsyncSession, organization_id: uuid.UUID) -> SsoProvider | None:
    return (
        await db.execute(select(SsoProvider).where(SsoProvider.organization_id == organization_id))
    ).scalar_one_or_none()


def _validate_mapping(mapping: dict) -> dict:
    merged = {
        "email": "email",
        "name": "name",
        "groups": "groups",
        "role_map": {},
        "auto_provision": False,
        "default_role": "Viewer",
        **(mapping or {}),
    }
    if not isinstance(merged["role_map"], dict):
        raise ValidationAppError("claim_mapping.role_map must be an object")
    if not isinstance(merged["auto_provision"], bool):
        raise ValidationAppError("claim_mapping.auto_provision must be a boolean")
    return merged


async def upsert_provider(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    issuer: str,
    client_id: str,
    client_secret_ref: str,
    claim_mapping: dict | None = None,
    active: bool | None = None,
    user_id: uuid.UUID | None = None,
) -> SsoProvider:
    from app.services import entitlements

    await entitlements.require_feature(db, organization_id, "sso")
    if not issuer.startswith("https://"):
        raise ValidationAppError("issuer must be https", field="issuer")
    provider = await get_provider(db, organization_id)
    if provider is None:
        provider = SsoProvider(organization_id=organization_id)
        db.add(provider)
    provider.issuer = issuer.rstrip("/")
    provider.client_id = client_id
    provider.client_secret_ref = client_secret_ref
    provider.claim_mapping_json = _validate_mapping(claim_mapping or {})
    if active is not None:
        provider.active = active
    await db.flush()

    from app.services import audit

    await audit.record(
        db,
        organization_id,
        action="SSO_PROVIDER_UPDATED",
        entity_type="sso_provider",
        entity_id=provider.id,
        after={"issuer": issuer, "client_id": client_id, "active": provider.active},
        user_id=user_id,  # never the secret ref value
    )
    return provider


async def test_provider(db: AsyncSession, organization_id: uuid.UUID) -> dict:
    """Connection test = guarded discovery fetch; caches the metadata."""
    provider = await get_provider(db, organization_id)
    if provider is None:
        raise NotFoundError("No SSO provider configured")
    try:
        body = await guarded_fetch(f"{provider.issuer}/.well-known/openid-configuration")
        metadata = json.loads(body)
    except (FetchError, ValueError) as exc:
        return {"ok": False, "error": str(exc)[:300]}
    required = {"authorization_endpoint", "token_endpoint", "jwks_uri"}
    missing = sorted(required - set(metadata))
    if missing:
        return {"ok": False, "error": f"Discovery document missing: {missing}"}
    provider.metadata_json = {
        key: metadata[key] for key in required | {"issuer"} if key in metadata
    }
    await db.flush()
    return {"ok": True, "endpoints": provider.metadata_json}


# --- login flow ---


def _sign_state(org_code: str) -> str:
    from app.core.config import get_settings

    payload = f"{org_code}:{int(time.time())}"
    signature = hmac.new(
        get_settings().jwt_secret.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()[:32]
    return base64.urlsafe_b64encode(f"{payload}:{signature}".encode()).decode()


def _verify_state(state: str, org_code: str) -> None:
    from app.core.config import get_settings

    try:
        decoded = base64.urlsafe_b64decode(state.encode()).decode()
        code, timestamp, signature = decoded.rsplit(":", 2)
    except Exception as exc:  # noqa: BLE001
        raise UnauthenticatedError("Invalid SSO state") from exc
    expected = hmac.new(
        get_settings().jwt_secret.encode(), f"{code}:{timestamp}".encode(), hashlib.sha256
    ).hexdigest()[:32]
    if code != org_code or not hmac.compare_digest(signature, expected):
        raise UnauthenticatedError("Invalid SSO state")
    if int(timestamp) + STATE_TTL_SECONDS < time.time():
        raise UnauthenticatedError("SSO state expired")


async def _org_and_provider(db: AsyncSession, org_code: str) -> tuple[Organization, SsoProvider]:
    org = (
        await db.execute(
            select(Organization).where(
                Organization.code == org_code,
                Organization.status == OrganizationStatus.ACTIVE.value,
            )
        )
    ).scalar_one_or_none()
    if org is None:
        raise NotFoundError("Organization not found")
    provider = await get_provider(db, org.id)
    if provider is None or not provider.active:
        raise BusinessRuleError("SSO is not enabled for this organization")
    return org, provider


async def login_redirect(db: AsyncSession, org_code: str, redirect_uri: str) -> dict:
    org, provider = await _org_and_provider(db, org_code)
    metadata = provider.metadata_json or {}
    authorize = metadata.get("authorization_endpoint")
    if not authorize:
        result = await test_provider(db, org.id)
        if not result.get("ok"):
            raise BusinessRuleError(f"Issuer discovery failed: {result.get('error')}")
        authorize = provider.metadata_json["authorization_endpoint"]
    from urllib.parse import urlencode

    params = urlencode(
        {
            "response_type": "code",
            "client_id": provider.client_id,
            "redirect_uri": redirect_uri,
            "scope": "openid email profile",
            "state": _sign_state(org_code),
        }
    )
    return {"authorization_url": f"{authorize}?{params}"}


async def _exchange_code(provider: SsoProvider, code: str, redirect_uri: str) -> dict:
    """Token exchange + id_token verification against the issuer's JWKS.
    Isolated for tests (monkeypatch target); returns verified claims."""
    import os

    import httpx
    import jwt as pyjwt

    secret = os.environ.get(provider.client_secret_ref)
    if not secret:
        raise BusinessRuleError(
            f"SSO client secret env var '{provider.client_secret_ref}' is not set"
        )
    metadata = provider.metadata_json or {}
    token_endpoint = str(metadata.get("token_endpoint") or "")
    if not token_endpoint.startswith("https://"):
        raise BusinessRuleError("The identity provider's token endpoint must be https")
    try:
        assert_public_url(token_endpoint)
    except FetchError as exc:
        raise BusinessRuleError(f"Token endpoint refused: {exc}") from exc
    async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
        response = await client.post(
            token_endpoint,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": provider.client_id,
                "client_secret": secret,
            },
        )
        response.raise_for_status()
        tokens = response.json()
    id_token = tokens.get("id_token")
    if not id_token:
        raise UnauthenticatedError("IdP returned no id_token")
    jwk_client = pyjwt.PyJWKClient(metadata["jwks_uri"])
    signing_key = jwk_client.get_signing_key_from_jwt(id_token)
    return pyjwt.decode(
        id_token,
        signing_key.key,
        algorithms=["RS256", "ES256"],
        audience=provider.client_id,
        issuer=metadata.get("issuer", provider.issuer),
    )


def _claim(claims: dict, path: str):
    current = claims
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


async def _resolve_role(
    db: AsyncSession, org: Organization, mapping: dict, claims: dict
) -> Role | None:
    groups = _claim(claims, mapping.get("groups", "groups")) or []
    role_map = mapping.get("role_map", {})
    wanted = None
    for group in groups if isinstance(groups, list) else [groups]:
        if group in role_map:
            wanted = role_map[group]
            break
    wanted = wanted or mapping.get("default_role", "Viewer")
    return (
        (
            await db.execute(
                select(Role).where(
                    Role.name == wanted,
                    (Role.organization_id == org.id) | (Role.organization_id.is_(None)),
                )
            )
        )
        .scalars()
        .first()
    )


async def complete_login(
    db: AsyncSession, org_code: str, *, code: str, state: str, redirect_uri: str
) -> dict:
    """Callback: verify state → exchange+verify token → map claims → issue
    the platform's own JWT pair."""
    _verify_state(state, org_code)
    org, provider = await _org_and_provider(db, org_code)
    claims = await _exchange_code(provider, code, redirect_uri)
    mapping = provider.claim_mapping_json

    email = _claim(claims, mapping.get("email", "email"))
    if not email:
        raise UnauthenticatedError("IdP claims carry no email")
    email = str(email).lower()
    user = (
        await db.execute(
            select(User).where(User.organization_id == org.id, func.lower(User.email) == email)
        )
    ).scalar_one_or_none()

    if user is None:
        if not mapping.get("auto_provision"):
            raise UnauthenticatedError(
                "No account exists for this identity (auto-provision is off)"
            )
        role = await _resolve_role(db, org, mapping, claims)
        user = User(
            organization_id=org.id,
            email=email,
            full_name=str(_claim(claims, mapping.get("name", "name")) or email),
            password_hash=None,  # SSO-only identity
            status=UserStatus.ACTIVE.value,
        )
        if role is not None:
            user.roles = [role]
        db.add(user)
        await db.flush()
        logger.info("SSO auto-provisioned user %s in org %s", user.id, org.id)
    if user.status != UserStatus.ACTIVE.value:
        raise UnauthenticatedError("Account is not active")

    from datetime import UTC, datetime

    user.last_login_at = datetime.now(UTC)
    await db.flush()

    from app.services import audit
    from app.services.auth import _issue_token_pair

    await audit.record(
        db,
        org.id,
        action="USER_LOGIN_SSO",
        entity_type="user",
        entity_id=user.id,
        user_id=user.id,
        after={"issuer": provider.issuer},
    )
    return await _issue_token_pair(db, user)
