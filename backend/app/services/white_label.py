"""White label + password reset (P3-GLO-001/003, slice 3E-2).

White-label state = branding_json (theme, existing since Phase 1) plus a
`white_label` namespace in settings_json: custom-domain metadata (verified
by a platform admin — DNS automation is a deployment concern) and the
tenant email sender identity used by notification email deliveries.

Password reset (closes the Phase-1 deferral now that a real SMTP adapter
exists): stateless signed token (typ=pwreset, 30 min) e-mailed via the
adapter; confirmation sets the new Argon2 hash and revokes refresh tokens.
"""

import logging
import re
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.core.config import get_settings
from app.core.errors import NotFoundError, UnauthenticatedError, ValidationAppError
from app.models import Organization, User
from app.models.user import UserStatus

logger = logging.getLogger("app.white_label")

RESET_TOKEN_TTL_MINUTES = 30
DOMAIN_RE = re.compile(
    r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)+$"
)

WHITE_LABEL_DEFAULTS = {
    "custom_domain": None,
    "domain_verified": False,
    "email_from_name": None,
    "email_from_address": None,
}


async def get_white_label(db: AsyncSession, organization_id: uuid.UUID) -> dict:
    org = await db.get(Organization, organization_id)
    if org is None:
        raise NotFoundError("Organization not found")
    stored = (org.settings_json or {}).get("white_label") or {}
    return {**WHITE_LABEL_DEFAULTS, **stored, "region": org.region,
            "branding": org.branding_json or {}}


async def update_white_label(
    db: AsyncSession,
    organization_id: uuid.UUID,
    values: dict,
    *,
    user_id: uuid.UUID | None = None,
) -> dict:
    from app.services import entitlements

    await entitlements.require_feature(db, organization_id, "white_label")
    org = await db.get(Organization, organization_id)
    if org is None:
        raise NotFoundError("Organization not found")
    unknown = set(values) - {"custom_domain", "email_from_name", "email_from_address"}
    if unknown:
        raise ValidationAppError(f"Unknown white-label keys: {sorted(unknown)}")
    settings_json = dict(org.settings_json or {})
    white_label = {**WHITE_LABEL_DEFAULTS, **(settings_json.get("white_label") or {})}

    if "custom_domain" in values:
        domain = values["custom_domain"]
        if domain is not None:
            domain = str(domain).lower().strip()
            if not DOMAIN_RE.match(domain):
                raise ValidationAppError("custom_domain is not a valid hostname",
                                         field="custom_domain")
        if domain != white_label.get("custom_domain"):
            white_label["domain_verified"] = False  # re-verify on change
        white_label["custom_domain"] = domain
    if "email_from_address" in values:
        address = values["email_from_address"]
        if address is not None and "@" not in str(address):
            raise ValidationAppError("email_from_address must be an email",
                                     field="email_from_address")
        white_label["email_from_address"] = address
    if "email_from_name" in values:
        white_label["email_from_name"] = values["email_from_name"]

    settings_json["white_label"] = white_label
    org.settings_json = settings_json
    await db.flush()

    from app.services import audit

    await audit.record(
        db, organization_id, action="WHITE_LABEL_UPDATED",
        entity_type="organization", entity_id=organization_id,
        after=white_label, user_id=user_id,
    )
    return await get_white_label(db, organization_id)


async def verify_domain(
    db: AsyncSession, organization_id: uuid.UUID, *, verified: bool,
    actor_id: uuid.UUID | None = None,
) -> dict:
    """Platform-admin action: DNS/edge routing is a deployment concern, so
    verification is an explicit, audited human decision."""
    org = await db.get(Organization, organization_id)
    if org is None:
        raise NotFoundError("Organization not found")
    settings_json = dict(org.settings_json or {})
    white_label = {**WHITE_LABEL_DEFAULTS, **(settings_json.get("white_label") or {})}
    if not white_label.get("custom_domain"):
        raise ValidationAppError("No custom domain configured", field="custom_domain")
    white_label["domain_verified"] = verified
    settings_json["white_label"] = white_label
    org.settings_json = settings_json
    await db.flush()

    from app.services import audit

    await audit.record(
        db, organization_id,
        action="DOMAIN_VERIFIED" if verified else "DOMAIN_UNVERIFIED",
        entity_type="organization", entity_id=organization_id,
        after={"custom_domain": white_label["custom_domain"]}, user_id=actor_id,
    )
    return {**white_label}


def sender_identity(org: Organization) -> str | None:
    """From header for tenant notification mail (used by 2G deliveries)."""
    white_label = ((org.settings_json or {}).get("white_label") or {})
    address = white_label.get("email_from_address")
    if not address:
        return None
    name = white_label.get("email_from_name")
    return f"{name} <{address}>" if name else address


# --- password reset (Phase-1 deferral closed) ---


def _reset_token(user: User) -> str:
    settings = get_settings()
    return jwt.encode(
        {
            "sub": str(user.id),
            "typ": "pwreset",
            "pwh": security.hash_token(user.password_hash or "")[:16],  # invalidate on use
            "exp": datetime.now(UTC) + timedelta(minutes=RESET_TOKEN_TTL_MINUTES),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


async def request_password_reset(db: AsyncSession, *, email: str) -> None:
    """Always succeeds outwardly (no account enumeration); mails a signed
    reset link when the account exists."""
    users = (
        await db.execute(
            select(User).where(
                func.lower(User.email) == email.lower(),
                User.status == UserStatus.ACTIVE.value,
            )
        )
    ).scalars().all()
    from app.integrations.email import get_email_provider

    for user in users:
        org = await db.get(Organization, user.organization_id)
        token = _reset_token(user)
        get_email_provider().send(
            to=user.email,
            subject="Reset your Digital Signage Cloud password",
            body=(
                f"A password reset was requested for your account in "
                f"{org.name if org else 'your organization'}.\n\n"
                f"Reset token (valid {RESET_TOKEN_TTL_MINUTES} minutes):\n{token}\n\n"
                "If you did not request this, ignore this message."
            ),
            from_addr=sender_identity(org) if org else None,
        )
        logger.info("Password reset issued for user %s", user.id)


async def confirm_password_reset(
    db: AsyncSession, *, token: str, new_password: str
) -> None:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret,
                             algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise UnauthenticatedError("Invalid or expired reset token") from exc
    if payload.get("typ") != "pwreset":
        raise UnauthenticatedError("Invalid reset token")
    if len(new_password) < 10:
        raise ValidationAppError("Password must be at least 10 characters",
                                 field="new_password")
    user = await db.get(User, uuid.UUID(payload["sub"]))
    if user is None or user.status != UserStatus.ACTIVE.value:
        raise UnauthenticatedError("Account is not active")
    if security.hash_token(user.password_hash or "")[:16] != payload.get("pwh"):
        raise UnauthenticatedError("Reset token already used")

    user.password_hash = security.hash_password(new_password)
    await db.flush()

    from app.repositories import auth as auth_repo
    from app.services import audit

    await auth_repo.revoke_all_for_user(db, user.id)  # kill existing sessions
    await audit.record(
        db, user.organization_id, action="PASSWORD_RESET",
        entity_type="user", entity_id=user.id, user_id=user.id,
    )
    logger.info("Password reset completed for user %s", user.id)
