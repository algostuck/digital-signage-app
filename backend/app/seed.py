"""Idempotent database seeding.

Usage: python -m app.seed
Seeds the permission catalogue and system roles (always safe), plus a demo
organization + admin user outside production (SEED_DEMO=false to skip).
"""

import asyncio
import logging
import os

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.permissions import PERMISSIONS, SYSTEM_ROLES
from app.db.session import get_session_factory
from app.models import Organization, Permission, Role, User
from app.models.organization import OrganizationStatus
from app.models.user import UserStatus
from app.repositories import roles as roles_repo
from app.repositories import users as users_repo

logger = logging.getLogger("app.seed")

DEMO_ORG_CODE = "demo"
DEMO_ADMIN_EMAIL = "admin@demo-org.com"


async def seed_permissions(db: AsyncSession) -> dict[str, Permission]:
    existing = {p.code: p for p in await roles_repo.list_permissions(db)}
    for code, description in PERMISSIONS.items():
        if code in existing:
            existing[code].description = description
        else:
            perm = Permission(code=code, description=description)
            db.add(perm)
            existing[code] = perm
    await db.flush()
    return existing


async def seed_system_roles(db: AsyncSession, perms: dict[str, Permission]) -> dict[str, Role]:
    from sqlalchemy import select

    rows = await db.execute(select(Role).where(Role.organization_id.is_(None)))
    existing = {r.name: r for r in rows.scalars().all()}
    for name, spec in SYSTEM_ROLES.items():
        role = existing.get(name)
        if role is None:
            role = Role(organization_id=None, name=name, is_system=True)
            db.add(role)
            existing[name] = role
        role.description = spec["description"]
        role.is_system = True
        role.permissions = [perms[code] for code in spec["permissions"]]
    await db.flush()
    return existing


async def seed_demo_locations(db: AsyncSession, org: Organization) -> None:
    """India > West Bengal > Kolkata > Salt Lake Store > Floor 1 (idempotent)."""
    from app.repositories import locations as locations_repo
    from app.services import locations as locations_service

    await locations_service.seed_default_location_types(db, org.id)
    if await locations_repo.list_all_active(db, org.id):
        return

    types = {t.code: t.id for t in await locations_repo.list_types(db, org.id)}
    chain = [
        ("India", "country", "IN"),
        ("West Bengal", "state", "WB"),
        ("Kolkata", "city", "KOL"),
        ("Salt Lake Store", "store", "KOL-SL"),
        ("Floor 1", "floor", "F1"),
    ]
    parent_id = None
    for name, type_code, code in chain:
        node = await locations_service.create_location(
            db,
            org.id,
            name=name,
            parent_id=parent_id,
            type_id=types.get(type_code),
            code=code,
            timezone="Asia/Kolkata" if type_code == "country" else None,
        )
        parent_id = node.id
    logger.info("Seeded demo location hierarchy for %s", org.code)


async def seed_demo_devices(db: AsyncSession, org: Organization) -> None:
    """Three simulated active displays assigned to seeded locations."""
    from datetime import UTC, datetime

    from app.models import Device
    from app.repositories import devices as devices_repo
    from app.repositories import locations as locations_repo

    if not org.enrollment_key:
        import secrets

        org.enrollment_key = secrets.token_urlsafe(24)
        await db.flush()

    locations = {loc.name: loc.id for loc in await locations_repo.list_all_active(db, org.id)}
    demo = [
        ("Salt Lake Entrance Display", "DEMO-LG-0001", "LG", "55UH5N", "webos",
         locations.get("Salt Lake Store")),
        ("Salt Lake Floor 1 Menu Board", "DEMO-SS-0002", "Samsung", "QM55B", "tizen",
         locations.get("Floor 1")),
        ("Kolkata Window Display", "DEMO-AN-0003", "Generic", "AndroidBox-4K", "android",
         locations.get("Kolkata")),
    ]
    for name, serial, manufacturer, model, platform, location_id in demo:
        if await devices_repo.get_by_serial(db, org.id, serial):
            continue
        db.add(
            Device(
                organization_id=org.id,
                location_id=location_id,
                name=name,
                serial_no=serial,
                manufacturer=manufacturer,
                model=model,
                platform=platform,
                status="active",
                approved_at=datetime.now(UTC),
                last_heartbeat_at=datetime.now(UTC),
                screen_width=3840,
                screen_height=2160,
            )
        )
    await db.flush()
    logger.info("Seeded demo devices for %s", org.code)


async def seed_demo_tenant(db: AsyncSession, system_roles: dict[str, Role]) -> None:
    from sqlalchemy import select

    org = (
        await db.execute(select(Organization).where(Organization.code == DEMO_ORG_CODE))
    ).scalar_one_or_none()
    if org is None:
        org = Organization(
            name="Demo Organization",
            code=DEMO_ORG_CODE,
            status=OrganizationStatus.ACTIVE.value,
            timezone="Asia/Kolkata",
            locale="en",
        )
        db.add(org)
        await db.flush()
        logger.info("Created demo organization %s", org.id)

    admin = await users_repo.get_by_email(db, org.id, DEMO_ADMIN_EMAIL)
    if admin is None:
        password = os.environ.get("SEED_ADMIN_PASSWORD", "Admin@12345")
        admin = User(
            organization_id=org.id,
            email=DEMO_ADMIN_EMAIL,
            full_name="Demo Administrator",
            password_hash=security.hash_password(password),
            status=UserStatus.ACTIVE.value,
        )
        admin.roles = [system_roles["Organization Administrator"]]
        db.add(admin)
        await db.flush()
        logger.info("Created demo admin %s (email: %s)", admin.id, DEMO_ADMIN_EMAIL)

    await seed_demo_locations(db, org)
    await seed_demo_devices(db, org)
    await seed_platform_admin(db, org)
    await seed_demo_subscription(db, org)

    from app.services import layouts as layouts_service

    await layouts_service.seed_default_templates(db, org.id)


PLANS = [
    {
        "code": "starter",
        "name": "Starter",
        "description": "Small deployments getting started with digital signage",
        "prices": {"monthly": {"amount": 4999, "currency": "INR"},
                   "yearly": {"amount": 49990, "currency": "INR"}},
        "sort_order": 1,
        "entitlements": {
            "max_devices": 10, "max_users": 3, "max_storage_mb": 51200,
            "max_locations": 10, "max_api_calls_month": 0, "ai_credits_month": 0,
            "proof_of_play": False, "advanced_analytics": False, "api_access": False,
            "sso": False, "white_label": False, "video_wall": False,
            "ai_features": False, "dynamic_data": False, "experiments": False,
            "advertising": False, "fleet_ai": False, "developer_portal": False,
            "edge_bundles": False,
        },
    },
    {
        "code": "business",
        "name": "Business",
        "description": "Growing networks with analytics and API access",
        "prices": {"monthly": {"amount": 14999, "currency": "INR"},
                   "yearly": {"amount": 149990, "currency": "INR"}},
        "sort_order": 2,
        "entitlements": {
            "max_devices": 100, "max_users": 20, "max_storage_mb": 512000,
            "max_locations": 100, "max_api_calls_month": 100000,
            "ai_credits_month": 0,
            "proof_of_play": True, "advanced_analytics": True, "api_access": True,
            "sso": False, "white_label": False, "video_wall": False,
            "ai_features": False, "dynamic_data": True, "experiments": False,
            "advertising": False, "fleet_ai": False, "developer_portal": False,
            "edge_bundles": False,
        },
    },
    {
        "code": "professional",
        "name": "Professional",
        "description": "Large networks with SSO, video walls and AI",
        "prices": {"monthly": {"amount": 49999, "currency": "INR"},
                   "yearly": {"amount": 499990, "currency": "INR"}},
        "sort_order": 3,
        "entitlements": {
            "max_devices": 500, "max_users": 100, "max_storage_mb": 2048000,
            "max_locations": 500, "max_api_calls_month": 1000000,
            "ai_credits_month": 10000,
            "proof_of_play": True, "advanced_analytics": True, "api_access": True,
            "sso": True, "white_label": False, "video_wall": True,
            "ai_features": True, "dynamic_data": True, "experiments": True,
            "advertising": False, "fleet_ai": True, "developer_portal": True,
            "edge_bundles": True,
        },
    },
    {
        "code": "enterprise",
        "name": "Enterprise",
        "description": "Everything, at contract pricing",
        "prices": {},  # custom pricing: invoices handled off-platform
        "sort_order": 4,
        "entitlements": {
            "max_devices": 5000, "max_users": 500, "max_storage_mb": 5120000,
            "max_locations": 5000, "max_api_calls_month": None,
            "ai_credits_month": None,
            "proof_of_play": True, "advanced_analytics": True, "api_access": True,
            "sso": True, "white_label": True, "video_wall": True,
            "ai_features": True, "dynamic_data": True, "experiments": True,
            "advertising": True, "fleet_ai": True, "developer_portal": True,
            "edge_bundles": True,
        },
    },
]

PLATFORM_ADMIN_EMAIL = "platform@signage.cloud"


async def seed_plans(db: AsyncSession) -> None:
    from app.services import entitlements as entitlements_service
    from app.services import subscriptions as subscriptions_service

    for spec in PLANS:
        rows = []
        for key, value in spec["entitlements"].items():
            kind = entitlements_service.ENTITLEMENTS[key]
            rows.append(
                {
                    "key": key,
                    "int_value": value if kind == "int" else None,
                    "bool_value": value if kind == "bool" else None,
                }
            )
        await subscriptions_service.upsert_plan(
            db,
            code=spec["code"],
            name=spec["name"],
            description=spec["description"],
            prices=spec["prices"],
            entitlements=rows,
            sort_order=spec["sort_order"],
        )
    logger.info("Seeded %d plans", len(PLANS))


async def seed_platform_admin(db: AsyncSession, org: Organization) -> None:
    """Super Admin identity homed in the demo org; is_superuser bypasses
    tenant RBAC and unlocks the /platform surface."""
    admin = await users_repo.get_by_email(db, org.id, PLATFORM_ADMIN_EMAIL)
    if admin is None:
        password = os.environ.get("SEED_PLATFORM_PASSWORD", "Platform@12345")
        admin = User(
            organization_id=org.id,
            email=PLATFORM_ADMIN_EMAIL,
            full_name="Platform Administrator",
            password_hash=security.hash_password(password),
            status=UserStatus.ACTIVE.value,
            is_superuser=True,
        )
        db.add(admin)
        await db.flush()
        logger.info("Created platform admin (email: %s)", PLATFORM_ADMIN_EMAIL)


async def seed_demo_subscription(db: AsyncSession, org: Organization) -> None:
    """Demo org rides Enterprise so its limits never constrain dev/tests."""
    from app.services import entitlements as entitlements_service
    from app.services import subscriptions as subscriptions_service

    if await entitlements_service.current_subscription(db, org.id) is None:
        await subscriptions_service.subscribe(
            db, org.id, plan_code="enterprise", billing_cycle="yearly"
        )
        logger.info("Demo org subscribed to Enterprise")


async def run_seed(db: AsyncSession, *, include_demo: bool) -> None:
    perms = await seed_permissions(db)
    system_roles = await seed_system_roles(db, perms)
    await seed_plans(db)
    if include_demo:
        await seed_demo_tenant(db, system_roles)


async def main() -> None:
    configure_logging()
    settings = get_settings()
    include_demo = (
        os.environ.get("SEED_DEMO", "true").lower() == "true" and not settings.is_production
    )
    async with get_session_factory()() as db:
        await run_seed(db, include_demo=include_demo)
        await db.commit()
    logger.info("Seed complete (demo tenant: %s)", include_demo)


if __name__ == "__main__":
    asyncio.run(main())
