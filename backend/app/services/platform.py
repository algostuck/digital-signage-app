"""Platform administration (SaaS core): Super Admin operations that span
tenants — creating tenants, assigning subscriptions, recording payments.

Everything here sits behind require_superuser; tenant-facing screens never
reach this surface.
"""

import logging
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.core.errors import ConflictError, ValidationAppError
from app.models import Device, Organization, Role, User
from app.models.organization import OrganizationStatus
from app.models.user import UserStatus
from app.services.organization import validate_timezone

logger = logging.getLogger("app.platform")


async def list_tenants(db: AsyncSession) -> list[dict]:
    orgs = (
        await db.execute(select(Organization).order_by(Organization.name))
    ).scalars().all()
    return [await tenant_row(db, org) for org in orgs]


async def get_tenant(db: AsyncSession, organization_id: uuid.UUID) -> dict:
    """One tenant with the profile fields the console edits."""
    org = await db.get(Organization, organization_id)
    if org is None:
        from app.core.errors import NotFoundError

        raise NotFoundError("Organization not found")
    row = await tenant_row(db, org)
    row.update(
        {
            "timezone": org.timezone,
            "locale": org.locale,
            "region": org.region,
            "quotas": org.quotas_json or {},
        }
    )
    return row


async def tenant_row(db: AsyncSession, org: Organization) -> dict:
    from app.services import entitlements as entitlements_service

    if True:
        devices = (
            await db.execute(
                select(func.count()).where(
                    Device.organization_id == org.id,
                    Device.status != "decommissioned",
                )
            )
        ).scalar_one()
        users = (
            await db.execute(
                select(func.count()).where(
                    User.organization_id == org.id, User.status == "active"
                )
            )
        ).scalar_one()
        effective = await entitlements_service.get_effective(db, org.id)
        return (
            {
                "id": str(org.id),
                "name": org.name,
                "code": org.code,
                "status": org.status,
                "plan_code": effective.plan_code,
                "plan_name": effective.plan_name,
                "subscription_status": effective.subscription_status,
                "devices": devices,
                "users": users,
                "created_at": org.created_at.isoformat() if org.created_at else None,
            }
        )


async def create_tenant(
    db: AsyncSession,
    *,
    name: str,
    code: str,
    timezone: str = "UTC",
    owner_email: str,
    owner_full_name: str,
    owner_password: str | None = None,
    actor_id: uuid.UUID | None = None,
) -> tuple[Organization, User]:
    """New organization + its first Organization Administrator."""
    validate_timezone(timezone)
    exists = (
        await db.execute(select(Organization).where(Organization.code == code))
    ).scalar_one_or_none()
    if exists is not None:
        raise ConflictError("An organization with this code already exists", field="code")

    org = Organization(
        name=name, code=code, status=OrganizationStatus.ACTIVE.value, timezone=timezone
    )
    db.add(org)
    await db.flush()

    admin_role = (
        await db.execute(
            select(Role).where(
                Role.organization_id.is_(None),
                Role.name == "Organization Administrator",
            )
        )
    ).scalar_one_or_none()
    if admin_role is None:
        raise ValidationAppError(
            "System roles are not seeded; run the seed first", field="owner_email"
        )
    owner = User(
        organization_id=org.id,
        email=owner_email.lower(),
        full_name=owner_full_name,
        password_hash=security.hash_password(owner_password) if owner_password else None,
        status=UserStatus.ACTIVE.value if owner_password else UserStatus.INVITED.value,
    )
    owner.roles = [admin_role]
    db.add(owner)
    await db.flush()

    from app.services import locations as locations_service

    await locations_service.seed_default_location_types(db, org.id)

    from app.services import audit

    await audit.record(
        db,
        org.id,
        action="TENANT_CREATED",
        entity_type="organization",
        entity_id=org.id,
        after={"name": name, "code": code, "owner": owner_email},
        user_id=actor_id,
    )
    logger.info("Tenant %s (%s) created with owner %s", org.id, code, owner_email)
    return org, owner


async def update_tenant(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    name: str | None = None,
    timezone: str | None = None,
    region: str | None = None,
    actor_id: uuid.UUID | None = None,
) -> Organization:
    org = await db.get(Organization, organization_id)
    if org is None:
        from app.core.errors import NotFoundError

        raise NotFoundError("Organization not found")
    changes: dict = {}
    if name is not None and name != org.name:
        org.name = name
        changes["name"] = name
    if timezone is not None and timezone != org.timezone:
        validate_timezone(timezone)
        org.timezone = timezone
        changes["timezone"] = timezone
    if region is not None and region != org.region:
        org.region = region  # residency metadata (P3-GLO-004)
        changes["region"] = region
    if changes:
        await db.flush()

        from app.services import audit

        await audit.record(
            db,
            organization_id,
            action="TENANT_UPDATED",
            entity_type="organization",
            entity_id=organization_id,
            after=changes,
            user_id=actor_id,
        )
    return org


async def set_tenant_status(
    db: AsyncSession,
    organization_id: uuid.UUID,
    status: str,
    *,
    actor_id: uuid.UUID | None = None,
) -> Organization:
    if status not in {s.value for s in OrganizationStatus}:
        raise ValidationAppError("Unknown organization status", field="status")
    org = await db.get(Organization, organization_id)
    if org is None:
        from app.core.errors import NotFoundError

        raise NotFoundError("Organization not found")
    org.status = status
    await db.flush()

    from app.services import audit

    await audit.record(
        db,
        organization_id,
        action="TENANT_STATUS_CHANGED",
        entity_type="organization",
        entity_id=organization_id,
        after={"status": status},
        user_id=actor_id,
    )
    return org
