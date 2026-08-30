"""Security center (P3-M10, slice 3E-3).

Formalizes what already exists: device tokens (1E) and API keys (2H) get a
tracked credential lifecycle, declarative age policies, a daily violation
sweep, and an explicit — audited — rotation action that forces the device
through the standard re-registration flow (no new credential channel).
Violations are surfaced, never auto-enforced.
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, ValidationAppError
from app.models import (
    ApiKey,
    Device,
    DeviceIdentity,
    IdentityCredential,
    PolicyViolation,
    SecurityPolicy,
)
from app.models.device import DeviceStatus
from app.models.security import ViolationState

logger = logging.getLogger("app.security_center")

SCOPE_TYPES = ("device_credentials", "api_keys")
POLICY_DEFAULTS = {"max_age_days": 180}


async def _ensure_identity(db: AsyncSession, device: Device) -> DeviceIdentity:
    identity = (
        await db.execute(
            select(DeviceIdentity).where(DeviceIdentity.device_id == device.id)
        )
    ).scalar_one_or_none()
    if identity is None:
        identity = DeviceIdentity(
            organization_id=device.organization_id, device_id=device.id
        )
        db.add(identity)
        await db.flush()
        if device.token_hash:
            db.add(
                IdentityCredential(
                    identity_id=identity.id,
                    fingerprint=device.token_hash[:16],
                    issued_at=device.token_issued_at or datetime.now(UTC),
                )
            )
            await db.flush()
        await db.refresh(identity, ["credentials"])
    return identity


async def record_issuance(db: AsyncSession, device: Device) -> None:
    """Called when the register flow mints a device token (1E hook)."""
    identity = await _ensure_identity(db, device)
    current = device.token_hash[:16] if device.token_hash else None
    if current and not any(
        c.fingerprint == current and c.revoked_at is None for c in identity.credentials
    ):
        db.add(IdentityCredential(identity_id=identity.id, fingerprint=current))
        await db.flush()


async def device_identities(db: AsyncSession, organization_id: uuid.UUID) -> list[dict]:
    devices = (
        await db.execute(
            select(Device).where(
                Device.organization_id == organization_id,
                Device.status == DeviceStatus.ACTIVE.value,
            )
        )
    ).scalars().all()
    now = datetime.now(UTC)
    rows = []
    for device in devices:
        identity = await _ensure_identity(db, device)
        issued = device.token_issued_at
        issued = issued if (issued is None or issued.tzinfo) else issued.replace(tzinfo=UTC)
        rows.append(
            {
                "device_id": str(device.id),
                "device_name": device.name,
                "identity_id": str(identity.id),
                "identity_type": identity.identity_type,
                "has_credential": device.token_hash is not None,
                "fingerprint": device.token_hash[:16] if device.token_hash else None,
                "issued_at": issued.isoformat() if issued else None,
                "age_days": (now - issued).days if issued else None,
                "credential_history": len(identity.credentials),
            }
        )
    return rows


async def rotate_device_credential(
    db: AsyncSession, organization_id: uuid.UUID, device_id: uuid.UUID,
    *, user_id: uuid.UUID | None = None,
) -> dict:
    """Revokes the current token; the player re-registers with the
    enrollment key on its next poll and receives a fresh credential through
    the standard 1E pipeline — no side channel."""
    device = (
        await db.execute(
            select(Device).where(
                Device.organization_id == organization_id, Device.id == device_id
            )
        )
    ).scalar_one_or_none()
    if device is None:
        raise NotFoundError("Device not found")
    identity = await _ensure_identity(db, device)
    now = datetime.now(UTC)
    for credential in identity.credentials:
        if credential.revoked_at is None:
            credential.revoked_at = now
    device.token_hash = None
    device.token_issued_at = None
    await db.flush()

    from app.services import audit

    await audit.record(
        db, organization_id, action="DEVICE_CREDENTIAL_ROTATED",
        entity_type="device", entity_id=device.id, user_id=user_id,
    )
    logger.info("Device %s credential rotated (re-registration required)", device.id)
    return {"device_id": str(device.id), "status": "revoked_pending_reissue"}


# --- policies + violation sweep ---


async def list_policies(db: AsyncSession, organization_id: uuid.UUID) -> list[SecurityPolicy]:
    rows = await db.execute(
        select(SecurityPolicy)
        .where(SecurityPolicy.organization_id == organization_id)
        .order_by(SecurityPolicy.scope_type)
    )
    return list(rows.scalars().all())


async def upsert_policy(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    scope_type: str,
    conditions: dict | None = None,
    severity: str = "warning",
    active: bool = True,
    user_id: uuid.UUID | None = None,
) -> SecurityPolicy:
    if scope_type not in SCOPE_TYPES:
        raise ValidationAppError(f"scope_type must be one of {SCOPE_TYPES}",
                                 field="scope_type")
    merged = {**POLICY_DEFAULTS, **(conditions or {})}
    max_age = merged.get("max_age_days")
    if not isinstance(max_age, int) or not 1 <= max_age <= 3650:
        raise ValidationAppError("conditions.max_age_days must be 1..3650")
    policy = (
        await db.execute(
            select(SecurityPolicy).where(
                SecurityPolicy.organization_id == organization_id,
                SecurityPolicy.scope_type == scope_type,
            )
        )
    ).scalar_one_or_none()
    if policy is None:
        policy = SecurityPolicy(organization_id=organization_id, scope_type=scope_type)
        db.add(policy)
    policy.conditions_json = merged
    policy.actions_json = {"severity": severity}
    policy.active = active
    await db.flush()

    from app.services import audit

    await audit.record(
        db, organization_id, action="SECURITY_POLICY_UPDATED",
        entity_type="security_policy", entity_id=policy.id,
        after={"scope_type": scope_type, **merged, "severity": severity},
        user_id=user_id,
    )
    return policy


async def sweep_violations(db: AsyncSession) -> dict:
    """Daily beat: evaluate active policies; open one violation per entity
    per episode; resolve violations whose condition has cleared."""
    policies = (
        await db.execute(select(SecurityPolicy).where(SecurityPolicy.active.is_(True)))
    ).scalars().all()
    now = datetime.now(UTC)
    opened = resolved = 0
    for policy in policies:
        max_age = timedelta(days=policy.conditions_json.get("max_age_days", 180))
        severity = policy.actions_json.get("severity", "warning")
        offenders: dict[uuid.UUID, str] = {}
        if policy.scope_type == "device_credentials":
            devices = (
                await db.execute(
                    select(Device).where(
                        Device.organization_id == policy.organization_id,
                        Device.status == DeviceStatus.ACTIVE.value,
                        Device.token_issued_at.is_not(None),
                    )
                )
            ).scalars().all()
            for device in devices:
                issued = device.token_issued_at
                issued = issued if issued.tzinfo else issued.replace(tzinfo=UTC)
                if now - issued > max_age:
                    offenders[device.id] = (
                        f"Device token is {(now - issued).days} days old "
                        f"(policy: {policy.conditions_json['max_age_days']})"
                    )
            entity_type = "device"
        else:  # api_keys
            keys = (
                await db.execute(
                    select(ApiKey).where(
                        ApiKey.organization_id == policy.organization_id,
                        ApiKey.revoked_at.is_(None),
                    )
                )
            ).scalars().all()
            for key in keys:
                created = key.created_at
                created = created if created.tzinfo else created.replace(tzinfo=UTC)
                if now - created > max_age:
                    offenders[key.id] = (
                        f"API key '{key.name}' is {(now - created).days} days old"
                    )
            entity_type = "api_key"

        existing = (
            await db.execute(
                select(PolicyViolation).where(
                    PolicyViolation.policy_id == policy.id,
                    PolicyViolation.state == ViolationState.OPEN.value,
                )
            )
        ).scalars().all()
        open_by_entity = {v.entity_id: v for v in existing}
        for entity_id, detail in offenders.items():
            if entity_id not in open_by_entity:
                db.add(
                    PolicyViolation(
                        organization_id=policy.organization_id,
                        policy_id=policy.id,
                        entity_type=entity_type,
                        entity_id=entity_id,
                        severity=severity,
                        detail=detail,
                    )
                )
                opened += 1
        for entity_id, violation in open_by_entity.items():
            if entity_id not in offenders:
                violation.state = ViolationState.RESOLVED.value
                violation.resolved_at = now
                resolved += 1
    await db.flush()
    return {"opened": opened, "resolved": resolved, "policies": len(policies)}


async def list_violations(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    state: str | None,
    page: int,
    page_size: int,
) -> tuple[list[PolicyViolation], int]:
    query = select(PolicyViolation).where(
        PolicyViolation.organization_id == organization_id
    )
    if state:
        query = query.where(PolicyViolation.state == state)
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    rows = await db.execute(
        query.order_by(PolicyViolation.detected_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(rows.scalars().all()), total


async def resolve_violation(
    db: AsyncSession, organization_id: uuid.UUID, violation_id: uuid.UUID,
    *, user_id: uuid.UUID | None = None,
) -> PolicyViolation:
    violation = (
        await db.execute(
            select(PolicyViolation).where(
                PolicyViolation.organization_id == organization_id,
                PolicyViolation.id == violation_id,
            )
        )
    ).scalar_one_or_none()
    if violation is None:
        raise NotFoundError("Violation not found")
    violation.state = ViolationState.RESOLVED.value
    violation.resolved_at = datetime.now(UTC)
    await db.flush()

    from app.services import audit

    await audit.record(
        db, organization_id, action="SECURITY_VIOLATION_RESOLVED",
        entity_type="policy_violation", entity_id=violation.id, user_id=user_id,
    )
    return violation


async def summary(db: AsyncSession, organization_id: uuid.UUID) -> dict:
    """Security analytics: violation + credential-age posture at a glance."""
    open_by_severity = dict(
        (
            await db.execute(
                select(PolicyViolation.severity, func.count())
                .where(
                    PolicyViolation.organization_id == organization_id,
                    PolicyViolation.state == ViolationState.OPEN.value,
                )
                .group_by(PolicyViolation.severity)
            )
        ).all()
    )
    identities = await device_identities(db, organization_id)
    ages = [row["age_days"] for row in identities if row["age_days"] is not None]
    return {
        "open_violations": open_by_severity,
        "device_identities": len(identities),
        "credentials_missing": sum(1 for r in identities if not r["has_credential"]),
        "oldest_credential_days": max(ages) if ages else 0,
    }
