"""Developer platform (P3-M12 / P3-INT-103, slice 3A-3).

Three concerns, all built on existing machinery:
- Versioned API catalogue: `api_products`/`api_versions` (platform-scoped)
  carrying lifecycle, deprecation policy and changelog. Interactive docs
  stay FastAPI's own OpenAPI.
- Sandbox: one isolated test organization per real tenant (code
  `<code>-sbx`, linked via settings_json). Access rides the SaaS-core
  guest-membership mechanism, so the requesting admin simply switches
  tenants in the header. The sandbox has no subscription → unrestricted.
- Device simulator: registers + approves a simulated display in the
  sandbox through the REAL player endpoints and hands back its token.
"""

import logging
import secrets
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.models import ApiProduct, ApiVersion, Organization, Role, TenantUser, User
from app.models.organization import OrganizationStatus

logger = logging.getLogger("app.developer")

SANDBOX_SUFFIX = "-sbx"

# Seeded catalogue: product -> versions. Idempotently upserted by the seed.
API_CATALOGUE: list[dict] = [
    {
        "name": "Control Plane API",
        "description": "Tenant-facing REST API under /api/v1 (envelope, RBAC, "
        "API keys via X-API-Key).",
        "versions": [
            {
                "version": "v1",
                "lifecycle_state": "current",
                "changelog": [
                    {"date": "2026-08-29", "note": "Phase 2 surface complete "
                     "(approvals, device ops, OTA, studio, monitoring, "
                     "integrations, reporting, search, tenant admin)."},
                    {"date": "2026-08-30", "note": "SaaS core: billing, plans, "
                     "memberships, platform admin. Phase 3: domain event bus "
                     "(/events, /subscriptions), dynamic data (/data-sources)."},
                ],
            }
        ],
    },
    {
        "name": "Player Contract",
        "description": "Pull-based device protocol: register, heartbeat, "
        "manifest, acks (X-Device-Token).",
        "versions": [
            {
                "version": "v1",
                "lifecycle_state": "current",
                "changelog": [
                    {"date": "2026-08-29", "note": "Baseline: register/approve, "
                     "heartbeat, manifest with schedules + signed assets, "
                     "command queue, OTA offers."},
                ],
            },
            {
                "version": "v2",
                "lifecycle_state": "preview",
                "changelog": [
                    {"date": "2026-08-30", "note": "Additive `data` block: "
                     "per-zone validated data-source snapshots with freshness "
                     "tags. v1 players ignore unknown blocks."},
                ],
            },
        ],
    },
]


async def seed_api_catalogue(db: AsyncSession) -> None:
    """Idempotent: upserts products/versions, refreshes changelogs."""
    for spec in API_CATALOGUE:
        product = (
            await db.execute(select(ApiProduct).where(ApiProduct.name == spec["name"]))
        ).scalar_one_or_none()
        if product is None:
            product = ApiProduct(name=spec["name"])
            db.add(product)
        product.description = spec["description"]
        await db.flush()
        existing = {
            v.version: v
            for v in (
                await db.execute(
                    select(ApiVersion).where(ApiVersion.product_id == product.id)
                )
            ).scalars()
        }
        for version_spec in spec["versions"]:
            row = existing.get(version_spec["version"])
            if row is None:
                row = ApiVersion(product_id=product.id, version=version_spec["version"])
                db.add(row)
            row.lifecycle_state = version_spec["lifecycle_state"]
            row.changelog_json = version_spec["changelog"]
        await db.flush()


async def openapi_meta(db: AsyncSession) -> dict:
    from app.core.config import get_settings

    settings = get_settings()
    products = (
        await db.execute(select(ApiProduct).order_by(ApiProduct.name))
    ).scalars().all()
    return {
        "openapi_url": "/api/openapi.json" if not settings.is_production else None,
        "docs_url": "/api/docs" if not settings.is_production else None,
        "products": [
            {
                "name": p.name,
                "description": p.description,
                "versions": [
                    {
                        "version": v.version,
                        "lifecycle_state": v.lifecycle_state,
                        "sunset_at": v.sunset_at.isoformat() if v.sunset_at else None,
                        "released_at": v.released_at.isoformat() if v.released_at else None,
                        "changelog": v.changelog_json or [],
                    }
                    for v in p.versions
                ],
            }
            for p in products
        ],
    }


# --- sandbox ---


async def _sandbox_org(db: AsyncSession, parent: Organization) -> Organization | None:
    sandbox_id = (parent.settings_json or {}).get("sandbox_org_id")
    if not sandbox_id:
        return None
    return await db.get(Organization, uuid.UUID(sandbox_id))


async def ensure_sandbox(
    db: AsyncSession, organization_id: uuid.UUID, user: User
) -> tuple[Organization, bool]:
    """Idempotently provisions the tenant's sandbox org and grants the
    requesting user an owner membership there. Returns (org, created)."""
    parent = await db.get(Organization, organization_id)
    if parent is None:
        raise NotFoundError("Organization not found")
    if (parent.settings_json or {}).get("sandbox_of"):
        from app.core.errors import BusinessRuleError

        raise BusinessRuleError("This organization is itself a sandbox")

    sandbox = await _sandbox_org(db, parent)
    created = False
    if sandbox is None:
        sandbox = Organization(
            name=f"{parent.name} (Sandbox)",
            code=f"{parent.code}{SANDBOX_SUFFIX}",
            status=OrganizationStatus.ACTIVE.value,
            timezone=parent.timezone,
            settings_json={"sandbox_of": str(parent.id)},
            enrollment_key=secrets.token_urlsafe(24),
        )
        db.add(sandbox)
        await db.flush()
        parent_settings = dict(parent.settings_json or {})
        parent_settings["sandbox_org_id"] = str(sandbox.id)
        parent.settings_json = parent_settings
        await db.flush()

        from app.services import locations as locations_service

        await locations_service.seed_default_location_types(db, sandbox.id)
        created = True

        from app.services import audit

        await audit.record(
            db,
            organization_id,
            action="SANDBOX_PROVISIONED",
            entity_type="organization",
            entity_id=sandbox.id,
            after={"code": sandbox.code},
            user_id=user.id,
        )
        logger.info("Sandbox %s provisioned for org %s", sandbox.id, organization_id)

    if not sandbox.enrollment_key:
        sandbox.enrollment_key = secrets.token_urlsafe(24)
        await db.flush()

    # Owner membership for the requester (home users of the parent only).
    if user.organization_id != sandbox.id:
        membership = (
            await db.execute(
                select(TenantUser).where(
                    TenantUser.organization_id == sandbox.id,
                    TenantUser.user_id == user.id,
                )
            )
        ).scalar_one_or_none()
        if membership is None:
            admin_role = (
                await db.execute(
                    select(Role).where(
                        Role.organization_id.is_(None),
                        Role.name == "Organization Administrator",
                    )
                )
            ).scalar_one_or_none()
            db.add(
                TenantUser(
                    organization_id=sandbox.id,
                    user_id=user.id,
                    role_id=admin_role.id if admin_role else None,
                    is_owner=True,
                )
            )
            await db.flush()
    return sandbox, created


async def sandbox_info(
    db: AsyncSession, organization_id: uuid.UUID
) -> dict | None:
    parent = await db.get(Organization, organization_id)
    if parent is None:
        raise NotFoundError("Organization not found")
    sandbox = await _sandbox_org(db, parent)
    if sandbox is None:
        return None
    from sqlalchemy import func as sa_func

    from app.models import Device

    device_count = (
        await db.execute(
            select(sa_func.count()).where(
                Device.organization_id == sandbox.id,
                Device.status != "decommissioned",
            )
        )
    ).scalar_one()
    return {
        "organization_id": str(sandbox.id),
        "name": sandbox.name,
        "code": sandbox.code,
        "enrollment_key": sandbox.enrollment_key,
        "devices": device_count,
    }


async def simulate_device(
    db: AsyncSession, organization_id: uuid.UUID, *, serial: str | None = None
) -> dict:
    """Registers + approves a simulated display in the tenant's sandbox via
    the real device pipeline and returns its one-time token."""
    parent = await db.get(Organization, organization_id)
    sandbox = await _sandbox_org(db, parent) if parent else None
    if sandbox is None:
        raise NotFoundError("Provision the sandbox first")

    from app.services import devices as devices_service

    serial = serial or f"SIM-{secrets.token_hex(4).upper()}"
    device, _ = await devices_service.register_device(
        db,
        enrollment_key=sandbox.enrollment_key,
        serial_no=serial,
        name=f"Simulated display {serial}",
        manufacturer="Simulator",
        model="DevKit",
        platform="simulator",
        os_version=None,
        player_version="sdk-dev",
        mac_address=None,
        screen_width=1920,
        screen_height=1080,
    )
    await devices_service.approve_device(db, sandbox.id, device.id)
    _, token = await devices_service.register_device(
        db,
        enrollment_key=sandbox.enrollment_key,
        serial_no=serial,
        name=None,
        manufacturer=None,
        model=None,
        platform=None,
        os_version=None,
        player_version=None,
        mac_address=None,
        screen_width=None,
        screen_height=None,
    )
    return {
        "device_id": str(device.id),
        "serial_no": serial,
        "device_token": token,  # shown once, like any device credential
        "heartbeat_url": f"/api/v1/player/{device.id}/heartbeat",
        "manifest_url": f"/api/v1/player/{device.id}/manifest",
    }
