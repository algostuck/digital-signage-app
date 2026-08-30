"""Rich Indian enterprise demo dataset.

Usage:
    python -m app.demo_seed            # reset + reseed the demo tenants
    python -m app.demo_seed --validate # validate only, change nothing
    python -m app.demo_seed --reset    # remove the demo tenants, no reseed

Safety contract (docs/DEMO_SEED_MASTER_DATA.md):
  * Only organizations whose `code` is in DEMO_ORG_CODES are ever touched.
  * System master data — permissions, system roles, plans, plan
    entitlements and the API catalogue — is never written or deleted here;
    that remains the job of `app.seed`.
  * The `demo` organization is deliberately NOT a demo-reset target: it
    homes `platform@signage.cloud` and is the fixture the automated test
    suite logs into.
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import hashlib
import io
import logging
import random
import secrets
import uuid
from pathlib import Path

from sqlalchemy import delete, func, insert, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.base import Base
from app.db.session import get_session_factory
from app.demo_catalog import (
    AD_ADVERTISERS,
    ADDRESS_TEMPLATES,
    AUDIT_ACTIONS,
    CAMPAIGN_NAMES,
    CONTENT_ITEMS,
    CUSTOM_ROLES,
    DAYPARTS,
    DEMO_ORG_CODES,
    DEMO_ORGS,
    DEVICE_MODELS,
    DEVICE_TAGS,
    FOLDER_TREE,
    INDIA_GEOGRAPHY,
    NOTIFICATION_TEMPLATES,
    PEOPLE,
    PIN_BY_CITY,
    PLAYER_VERSIONS,
    PLAYLIST_NAMES,
    PROPERTY_ZONES,
    STORE_ZONES,
    TEMPLATE_PRESETS,
    TICKER_MESSAGES,
    WIDGET_PRESETS,
)
from app.models import Organization, Role, User
from app.models.ads import AdBooking, AdInventory
from app.models.anomaly import Anomaly, AnomalyRule
from app.models.approval import ApprovalPolicy, ApprovalRequest
from app.models.campaign import (
    Campaign,
    CampaignTarget,
    CampaignVariant,
    Deployment,
    DeploymentDevice,
    Schedule,
)
from app.models.content import Asset, AssetVersion, Folder
from app.models.device import Device, DeviceGroup, Incident
from app.models.experiment import Experiment, ExperimentVariant
from app.models.layout import Layout, LayoutVersion, Template
from app.models.location import Tag
from app.models.ops import AuditLog, Notification, PlaybackEvent
from app.models.organization import OrganizationStatus
from app.models.playlist import Playlist, PlaylistItem, PlaylistVersion
from app.models.saas import TenantUser
from app.models.studio import Widget, WidgetVersion
from app.models.user import UserStatus
from app.models.video_wall import VideoWall, VideoWallMember
from app.services import locations as locations_service

logger = logging.getLogger("app.demo_seed")

DEMO_PASSWORD = "Demo@12345"  # noqa: S105 - documented demo credential
PLATFORM_ADMIN_EMAIL = "platform@signage.cloud"
SEED = 20260830  # deterministic: reruns produce the same believable world


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _back(days: float = 0, hours: float = 0, minutes: float = 0) -> dt.datetime:
    return _now() - dt.timedelta(days=days, hours=hours, minutes=minutes)


# ---------------------------------------------------------------------------
# Scoped reset
# ---------------------------------------------------------------------------


async def _delete_self_referential(db: AsyncSession, table: str, org_ids: list[uuid.UUID]) -> int:
    """`locations.parent_id` and `folders.parent_id` are RESTRICT, and
    PostgreSQL checks RESTRICT per row even inside one statement — so peel
    the tree leaf-first instead of deleting it in a single sweep."""
    total = 0
    while True:
        result = await db.execute(
            text(
                f"DELETE FROM {table} WHERE organization_id = ANY(:ids) "  # noqa: S608 - fixed table names
                f"AND id NOT IN (SELECT parent_id FROM {table} WHERE parent_id IS NOT NULL)"
            ),
            {"ids": org_ids},
        )
        if not result.rowcount:
            return total
        total += result.rowcount


async def reset_demo(db: AsyncSession) -> dict[str, int]:
    """Delete every row belonging to the demo tenants. Nothing outside
    DEMO_ORG_CODES is considered, so system master data and the `demo`
    fixture org are untouched by construction."""
    orgs = (
        await db.execute(select(Organization).where(Organization.code.in_(DEMO_ORG_CODES)))
    ).scalars().all()
    if not orgs:
        return {}
    org_ids = [o.id for o in orgs]
    deleted: dict[str, int] = {}

    for table_name in ("locations", "folders"):
        count = await _delete_self_referential(db, table_name, org_ids)
        if count:
            deleted[table_name] = count

    # Children before parents; anything without organization_id is removed
    # by ON DELETE CASCADE from its tenant-scoped parent.
    for table in reversed(Base.metadata.sorted_tables):
        if table.name in ("organizations", "locations", "folders"):
            continue
        column = table.c.get("organization_id")
        if column is None:
            continue
        result = await db.execute(delete(table).where(column.in_(org_ids)))
        if result.rowcount:
            deleted[table.name] = result.rowcount

    result = await db.execute(delete(Organization.__table__).where(Organization.id.in_(org_ids)))
    deleted["organizations"] = result.rowcount
    await db.flush()
    logger.info("Reset demo tenants: %s", ", ".join(f"{k}={v}" for k, v in deleted.items()))
    return deleted


async def refresh_heartbeats(db: AsyncSession) -> int:
    """Re-stamp demo heartbeats against the clock.

    Connection state is *derived* from heartbeat age, never stored. Demo
    tenants widen the window to 4h/24h (see `create_org`) so the mix holds
    for a whole session; this re-stamps it without rebuilding anything —
    useful when a demo database has been sitting idle for days.
    """
    rng = random.Random()  # noqa: S311 - demo jitter, not cryptography
    org_ids = [
        row for row in (
            await db.execute(
                select(Organization.id).where(Organization.code.in_(DEMO_ORG_CODES))
            )
        ).scalars().all()
    ]
    if not org_ids:
        return 0
    devices = (
        await db.execute(
            select(Device.id)
            .where(Device.organization_id.in_(org_ids), Device.status == "active")
            .order_by(Device.serial_no)
        )
    ).scalars().all()
    if not devices:
        return 0

    updates = []
    for index, device_id in enumerate(devices):
        bucket = index % 100
        if bucket < 84:  # online
            stamp = _back(hours=rng.uniform(0, 3))
        elif bucket < 92:  # warning
            stamp = _back(hours=rng.uniform(5, 20))
        else:  # offline
            stamp = _back(hours=rng.uniform(30, 120))
        updates.append({"d": device_id, "ts": stamp})

    from sqlalchemy import bindparam, update

    await db.execute(
        update(Device.__table__)
        .where(Device.__table__.c.id == bindparam("d"))
        .values(last_heartbeat_at=bindparam("ts")),
        updates,
    )
    await db.flush()
    logger.info("Refreshed heartbeats for %d demo devices", len(updates))
    return len(updates)


# ---------------------------------------------------------------------------
# Media
# ---------------------------------------------------------------------------

PALETTE = [
    (29, 78, 216), (5, 150, 105), (217, 119, 6), (190, 24, 93),
    (109, 40, 217), (2, 132, 199), (180, 83, 9), (15, 118, 110),
]


def _render_media(title: str, kind: str, index: int) -> tuple[bytes, bytes, int, int]:
    """A real JPEG per asset so the content library shows true thumbnails
    instead of broken images. Returns (original, thumbnail, w, h)."""
    from PIL import Image, ImageDraw, ImageFont

    width, height = (1920, 1080)
    base = PALETTE[index % len(PALETTE)]
    image = Image.new("RGB", (width, height), base)
    draw = ImageDraw.Draw(image)
    # Simple vertical wash so the tile does not read as a flat colour chip.
    for y in range(height):
        factor = 1 - (y / height) * 0.45
        draw.line(
            [(0, y), (width, y)],
            fill=(int(base[0] * factor), int(base[1] * factor), int(base[2] * factor)),
        )
    try:
        font = ImageFont.load_default(size=72)
        small = ImageFont.load_default(size=36)
    except TypeError:  # very old Pillow
        font = small = ImageFont.load_default()
    draw.text((90, height // 2 - 80), title[:34], font=font, fill=(255, 255, 255))
    draw.text((90, height // 2 + 30), f"{kind.upper()} · DEMO ASSET", font=small,
              fill=(255, 255, 255))

    original = io.BytesIO()
    image.save(original, format="JPEG", quality=78)
    thumb = image.resize((480, 270))
    thumbnail = io.BytesIO()
    thumb.save(thumbnail, format="JPEG", quality=70)
    return original.getvalue(), thumbnail.getvalue(), width, height


def _write_object(key: str, data: bytes) -> None:
    settings = get_settings()
    path = Path(settings.local_storage_dir) / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


class OrgBuilder:
    """Builds one tenant's world. Every collection it creates is kept on the
    instance so later stages can wire real relationships rather than
    inventing dangling ids."""

    def __init__(
        self, db: AsyncSession, spec: dict,
        system_roles: dict[str, Role], rng: random.Random,
    ):
        self.db = db
        self.spec = spec
        self.system_roles = system_roles
        self.rng = rng
        self.counts: dict[str, int] = {}

    def _bump(self, key: str, n: int = 1) -> None:
        self.counts[key] = self.counts.get(key, 0) + n

    # --- organization + people --------------------------------------------

    async def create_org(self) -> Organization:
        self.org = Organization(
            name=self.spec["name"],
            code=self.spec["code"],
            status=OrganizationStatus.ACTIVE.value,
            timezone="Asia/Kolkata",
            locale="en",
            region="in-south",
            enrollment_key=secrets.token_urlsafe(24),
            settings_json={
                "demo": True,
                "industry": self.spec["industry"],
                "country": "India",
                "currency": "INR",
                # Connection state is derived from heartbeat age, so with
                # the platform defaults (150s/300s) a seeded fleet reads as
                # entirely offline minutes later. Demo tenants use a
                # 4h/24h window so the health mix stays true for a whole
                # session without a background player simulator.
                "monitoring": {
                    "warning_after_seconds": 14400,
                    "offline_after_seconds": 86400,
                },
            },
        )
        self.db.add(self.org)
        await self.db.flush()
        self._bump("organizations")
        return self.org

    async def create_users(self, offset: int, count: int) -> None:
        """System roles first (so every built-in role is represented), then
        the tenant's own custom roles."""
        password_hash = security.hash_password(DEMO_PASSWORD)
        self.custom_roles: dict[str, Role] = {}
        self.owner_flags: dict[uuid.UUID, bool] = {}
        from app.models import Permission

        perms = {p.code: p for p in (await self.db.execute(select(Permission))).scalars().all()}
        for spec in CUSTOM_ROLES:
            role = Role(
                organization_id=self.org.id,
                name=spec["name"],
                description=spec["description"],
                is_system=False,
            )
            role.permissions = [perms[c] for c in spec["permissions"] if c in perms]
            self.db.add(role)
            self.custom_roles[spec["name"]] = role
            self._bump("roles")
        await self.db.flush()

        assignments = [
            ("Organization Administrator", True),
            ("Content Manager", False),
            ("Device Manager", False),
            ("Campaign Approver", False),
            ("Regional Operations Manager", False),
            ("Report Viewer", False),
            ("Viewer", False),
            ("Content Manager", False),
            ("Device Manager", False),
            ("Viewer", False),
        ][:count]

        self.users: list[User] = []
        domain = self.spec["domain"]
        for i, (role_name, is_owner) in enumerate(assignments):
            full_name, handle = PEOPLE[(offset + i) % len(PEOPLE)]
            user = User(
                organization_id=self.org.id,
                email=f"{handle}@{domain}",
                full_name=full_name,
                password_hash=password_hash,
                status=UserStatus.ACTIVE.value,
                created_at=_back(days=self.rng.randint(60, 180)),
                last_login_at=_back(hours=self.rng.randint(1, 96)),
            )
            role = self.system_roles.get(role_name) or self.custom_roles[role_name]
            user.roles = [role]
            self.db.add(user)
            await self.db.flush()
            # No TenantUser row for a user's *own* organization: the app
            # treats home membership as implicit (`accessible_tenants`
            # synthesises it from user.organization_id, and only
            # `add_member` writes TenantUser). Adding one here would make
            # the tenant switcher list the home org twice.
            self.owner_flags[user.id] = is_owner
            self.users.append(user)
            self._bump("users")
        await self.db.flush()
        self.admin = self.users[0]

    # --- geography ---------------------------------------------------------

    async def create_locations(self, states: list, stores_per_area: int) -> None:
        await locations_service.seed_default_location_types(self.db, self.org.id)
        from app.repositories import locations as loc_repo

        types = {t.code: t.id for t in await loc_repo.list_types(self.db, self.org.id)}
        zone_names = PROPERTY_ZONES if self.spec["code"] == "USP-DEMO" else STORE_ZONES
        facility_word = "Tower" if self.spec["code"] == "USP-DEMO" else "Store"
        facility_type = "building" if self.spec["code"] == "USP-DEMO" else "store"

        async def node(name, parent, type_code, code=None, **kw):
            loc = await locations_service.create_location(
                self.db, self.org.id, name=name, parent_id=parent,
                type_id=types.get(type_code), code=code, **kw
            )
            self._bump("locations")
            return loc

        country = await node("India", None, "country", "IN", timezone="Asia/Kolkata")
        self.screen_locations: list[tuple[uuid.UUID, str, str]] = []  # (id, city, label)
        self.city_locations: list[tuple[uuid.UUID, str]] = []

        for state_name, state_code, cities in states:
            state = await node(state_name, country.id, "state", state_code)
            for city_name, lat, lon, areas in cities:
                city = await node(
                    city_name, state.id, "city", city_name[:3].upper(),
                    latitude=lat, longitude=lon,
                )
                self.city_locations.append((city.id, city_name))
                for area_name, alat, alon in areas:
                    area = await node(
                        area_name, city.id, "zone",
                        f"{city_name[:3].upper()}-{area_name[:3].upper()}",
                        latitude=alat, longitude=alon,
                    )
                    for s in range(stores_per_area):
                        pin = PIN_BY_CITY.get(city_name, "560001")
                        phone = (
                            f"+91-{self.rng.randint(70, 99)}"
                            f"{self.rng.randint(10000000, 99999999)}"
                        )
                        address = self.rng.choice(ADDRESS_TEMPLATES).format(
                            n=self.rng.randint(2, 88), f=self.rng.randint(1, 6),
                            area=area_name, city=city_name, state=state_name, pin=pin,
                        )
                        facility = await node(
                            f"{area_name} {facility_word}" + ("" if s == 0 else f" {s + 1}"),
                            area.id, facility_type,
                            f"{area_name[:3].upper()}{s + 1}",
                            latitude=round(alat + self.rng.uniform(-0.01, 0.01), 6),
                            longitude=round(alon + self.rng.uniform(-0.01, 0.01), 6),
                            address=address,
                            timezone="Asia/Kolkata",
                            metadata_json={
                                "pin_code": pin,
                                "city": city_name,
                                "state": state_name,
                                "operating_hours": "10:00-22:00",
                                "contact": phone,
                            },
                        )
                        for zone_name in self.rng.sample(zone_names, self.rng.randint(2, 4)):
                            screen = await node(
                                zone_name, facility.id, "department",
                                f"{zone_name[:3].upper()}",
                            )
                            self.screen_locations.append(
                                (screen.id, city_name, f"{facility.name} · {zone_name}")
                            )

    # --- devices -----------------------------------------------------------

    async def create_devices(self, target: int) -> None:
        self.tags: dict[tuple[str, str], Tag] = {}
        for key, value in DEVICE_TAGS:
            tag = Tag(organization_id=self.org.id, key=key, value=value)
            self.db.add(tag)
            self.tags[(key, value)] = tag
            self._bump("tags")
        await self.db.flush()

        group_names = [
            "Mumbai Retail Stores", "Kolkata Premium Stores", "Bengaluru Flagship Stores",
            "North India Displays", "Outdoor Displays", "Indoor Displays",
            "LG Fleet", "Samsung Fleet", "High Priority Screens", "24x7 Screens",
        ]
        self.groups = []
        for name in group_names:
            group = DeviceGroup(organization_id=self.org.id, name=name, group_type="static")
            self.db.add(group)
            self.groups.append(group)
            self._bump("device_groups")
        await self.db.flush()

        tag_values = list(self.tags.values())
        # Health mix: mostly healthy, with enough degradation that the
        # monitoring screens have something real to show.
        plan = (
            ["online"] * 78 + ["warning"] * 8 + ["offline"] * 8
            + ["pending"] * 3 + ["decommissioned"] * 2 + ["rejected"] * 1
        )
        self.devices: list[Device] = []
        spots = self.screen_locations or [(None, "Mumbai", "Unassigned")]
        for i in range(target):
            manufacturer, model, platform, prefix, w, h, inches = DEVICE_MODELS[
                i % len(DEVICE_MODELS)
            ]
            location_id, city, label = spots[i % len(spots)]
            state = plan[i % len(plan)]
            serial = f"{prefix}-{i + 1:06d}"
            name = f'{label} — {manufacturer} {inches}"'

            status, heartbeat, approved = "active", None, _back(days=self.rng.randint(30, 300))
            if state == "online":
                heartbeat = _back(hours=self.rng.uniform(0, 3))
            elif state == "warning":
                heartbeat = _back(hours=self.rng.uniform(5, 20))
            elif state == "offline":
                heartbeat = _back(hours=self.rng.uniform(30, 120))
            elif state == "pending":
                status, approved = "pending", None
            elif state == "decommissioned":
                status, heartbeat = "decommissioned", _back(days=self.rng.randint(20, 90))
            else:
                status, approved = "rejected", None

            lan_ip = (
                f"10.{self.rng.randint(1, 40)}.{self.rng.randint(1, 250)}"
                f".{self.rng.randint(2, 250)}"
            )
            # A portrait-mounted panel reports its rotated resolution. Picking
            # orientation independently of w/h produced "portrait" screens
            # advertising 1920x1080, which made every consumer of the geometry
            # (preview framing included) disagree with itself.
            orientation = "landscape" if self.rng.random() < 0.85 else "portrait"
            screen_w, screen_h = (w, h) if orientation == "landscape" else (h, w)
            device = Device(
                organization_id=self.org.id,
                location_id=location_id,
                group_id=self.rng.choice(self.groups).id if self.rng.random() < 0.8 else None,
                name=name[:200],
                serial_no=serial,
                manufacturer=manufacturer,
                model=model,
                platform=platform,
                os_version=f"{platform}-{self.rng.randint(4, 9)}.{self.rng.randint(0, 4)}",
                player_version=self.rng.choice(PLAYER_VERSIONS),
                status=status,
                approved_at=approved,
                last_heartbeat_at=heartbeat,
                screen_width=screen_w,
                screen_height=screen_h,
                orientation=orientation,
                timezone="Asia/Kolkata",
                mac_address=":".join(f"{self.rng.randint(0, 255):02x}" for _ in range(6)),
                ip_address=lan_ip,
                created_at=_back(days=self.rng.randint(20, 240)),
                last_heartbeat_json={
                    "cpu_percent": self.rng.randint(8, 78),
                    "memory_percent": self.rng.randint(30, 88),
                    "storage_percent": self.rng.randint(35, 92),
                    "temperature_c": self.rng.randint(31, 58),
                    "network": self.rng.choice(["ethernet", "wifi", "wifi", "ethernet"]),
                    "signal_strength": self.rng.randint(45, 99),
                } if heartbeat else None,
                metadata_json={"city": city, "demo": True},
            )
            # Assigned while the row is still transient: touching a
            # collection after flush would lazy-load under asyncio.
            if self.rng.random() < 0.66:
                device.tags = self.rng.sample(tag_values, self.rng.randint(1, 3))
            self.db.add(device)
            self.devices.append(device)
            self._bump("devices")
        await self.db.flush()

        self.active_devices = [d for d in self.devices if d.status == "active"]

    # --- content -----------------------------------------------------------

    async def create_content(self) -> None:
        self.folders: dict[str, Folder] = {}
        for parent_name, children in FOLDER_TREE.items():
            parent = Folder(organization_id=self.org.id, name=parent_name)
            self.db.add(parent)
            await self.db.flush()
            self.folders[parent_name] = parent
            self._bump("folders")
            for child in children:
                node = Folder(organization_id=self.org.id, name=child, parent_id=parent.id)
                self.db.add(node)
                self.folders[child] = node
                self._bump("folders")
        await self.db.flush()

        self.content_tags: dict[str, Tag] = {}
        from app.demo_catalog import CONTENT_TAGS

        for value in CONTENT_TAGS:
            tag = Tag(organization_id=self.org.id, key="content", value=value)
            self.db.add(tag)
            self.content_tags[value] = tag
            self._bump("tags")
        await self.db.flush()

        self.assets: list[Asset] = []
        for index, (title, kind, folder_name, tags) in enumerate(CONTENT_ITEMS):
            created = _back(days=self.rng.randint(3, 150))
            asset = Asset(
                organization_id=self.org.id,
                folder_id=self.folders[folder_name].id,
                type=kind,
                name=title,
                description=f"{title} — demo creative for {self.spec['name']}.",
                status="published" if self.rng.random() < 0.8 else "draft",
                created_at=created,
            )
            asset.tags = [self.content_tags[t] for t in tags if t in self.content_tags]
            self.db.add(asset)
            await self.db.flush()

            original, thumbnail, w, h = _render_media(title, kind, index)
            ext = "jpg" if kind == "image" else "mp4"
            filename = f"{title.lower().replace(' ', '-').replace('—', '-')[:60]}.{ext}"
            base = f"tenant/{self.org.id}/content/{asset.id}/v1"
            object_key = f"{base}/original/{filename}"
            thumb_key = f"{base}/thumbnail/thumb.jpg"
            _write_object(object_key, original)
            _write_object(thumb_key, thumbnail)

            version = AssetVersion(
                asset_id=asset.id,
                version_no=1,
                object_key=object_key,
                thumbnail_key=thumb_key,
                original_filename=filename,
                mime_type="image/jpeg" if kind == "image" else "video/mp4",
                size_bytes=len(original),
                checksum=hashlib.sha256(original).hexdigest(),
                processing_status="ready",
                width=w,
                height=h,
                duration_ms=(
                    None if kind == "image"
                    else self.rng.choice([10000, 15000, 20000, 30000])
                ),
                created_at=created,
            )
            self.db.add(version)
            await self.db.flush()
            asset.current_version_id = version.id
            self.assets.append(asset)
            self._bump("assets")
        await self.db.flush()

    async def create_studio(self) -> None:
        """Layouts, templates and widgets."""
        from app.services import layouts as layouts_service

        await layouts_service.seed_default_templates(self.db, self.org.id)

        def canvas(zones: list[dict]) -> dict:
            return {"canvas": {"width": 1920, "height": 1080, "background": "#000000"},
                    "zones": zones}

        def zone(key, name, x, y, w, h, z=1, content_type="placeholder", config=None):
            return {"key": key, "name": name, "x": x, "y": y, "width": w, "height": h,
                    "z_index": z, "rotation": 0, "style": {}, "content_type": content_type,
                    "content_config": config or {}}

        # The main zone is typed `playlist`: that is the slot the campaign's
        # playlist plays in. Leaving it `placeholder` (the schema default)
        # describes a layout nobody has finished configuring, which is not
        # what a published demo layout should look like.
        shapes = {
            "fullscreen": [zone("main", "Main", 0, 0, 1920, 1080, content_type="playlist")],
            "split": [zone("main", "Main", 0, 0, 1250, 1080, content_type="playlist"),
                      zone("side", "Information", 1250, 0, 670, 1080, content_type="text",
                           config={"text": self.rng.choice(TICKER_MESSAGES)})],
            "ticker": [zone("header", "Header", 0, 0, 1920, 110, content_type="clock"),
                       zone("main", "Main", 0, 110, 1920, 860, content_type="playlist"),
                       zone("ticker", "Ticker", 0, 970, 1920, 110, content_type="ticker",
                            config={"text": self.rng.choice(TICKER_MESSAGES)})],
            "grid": [zone("main", "Panel 1", 0, 0, 640, 540, content_type="playlist")]
                    + [zone(f"z{i + 1}", f"Panel {i + 1}", (i % 3) * 640, (i // 3) * 540,
                            640, 540)
                       for i in range(1, 6)],
        }

        self.layouts: list[Layout] = []
        self.published_layouts: list[Layout] = []
        for name, shape in TEMPLATE_PRESETS:
            canvas_json = canvas(shapes[shape])
            layout = Layout(
                organization_id=self.org.id, name=name,
                draft_canvas_json=canvas_json,
                status="published" if self.rng.random() < 0.7 else "draft",
                created_at=_back(days=self.rng.randint(20, 160)),
            )
            self.db.add(layout)
            await self.db.flush()
            # A published layout without a version is not actually publishable
            # content: `build_manifest` resolves the canvas through
            # `current_version_id`, so a device would receive layout=null and
            # show nothing at all.
            if layout.status == "published":
                version = LayoutVersion(
                    layout_id=layout.id, version_no=1, canvas_json=canvas_json
                )
                self.db.add(version)
                await self.db.flush()
                layout.current_version_id = version.id
                self.published_layouts.append(layout)
            self.layouts.append(layout)
            self._bump("layouts")
            self.db.add(Template(
                organization_id=self.org.id, name=f"{name} Template",
                canvas_json=canvas(shapes[shape]),
                status=self.rng.choice(["approved", "approved", "draft", "pending_approval"]),
                created_at=_back(days=self.rng.randint(20, 160)),
            ))
            self._bump("templates")
        await self.db.flush()

        for name, wtype in WIDGET_PRESETS:
            widget = Widget(organization_id=self.org.id, type=wtype, name=name, status="active",
                            created_at=_back(days=self.rng.randint(10, 120)))
            self.db.add(widget)
            await self.db.flush()
            self.db.add(WidgetVersion(
                widget_id=widget.id, version_no=1,
                config_schema_json={"fields": [
                    {"key": "title", "label": "Title", "type": "text", "required": False},
                    {"key": "refresh_seconds", "label": "Refresh (s)", "type": "number",
                     "required": False, "default": 300},
                ]},
            ))
            self._bump("widgets")
        await self.db.flush()

    async def create_playlists(self) -> None:
        self.playlists: list[Playlist] = []
        self.published_playlists: list[Playlist] = []
        published = [a for a in self.assets if a.status == "published"] or self.assets
        for name in PLAYLIST_NAMES:
            playlist = Playlist(
                organization_id=self.org.id, name=name,
                status="published" if self.rng.random() < 0.75 else "draft",
                loop_enabled=True,
                created_at=_back(days=self.rng.randint(10, 120)),
            )
            self.db.add(playlist)
            await self.db.flush()
            snapshot: list[dict] = []
            for position, asset in enumerate(self.rng.sample(published, self.rng.randint(3, 7))):
                duration_ms = self.rng.choice([10000, 12000, 15000, 20000, 30000])
                self.db.add(PlaylistItem(
                    playlist_id=playlist.id, position=position, item_type="asset",
                    asset_id=asset.id, enabled=True,
                    duration_ms=duration_ms,
                ))
                snapshot.append({
                    "position": position + 1,
                    "item_type": "asset",
                    "duration_ms": duration_ms,
                    "transition": None,
                    "asset_id": str(asset.id),
                    "asset_type": asset.type,
                    "name": asset.name,
                    "asset_version_no": 1,
                })
            # Same reasoning as layouts: without a version the manifest
            # resolves playlist=null, so every device in the demo fleet would
            # receive an empty screen. The snapshot mirrors what
            # `playlists.publish_playlist` writes.
            if playlist.status == "published":
                version = PlaylistVersion(
                    playlist_id=playlist.id, version_no=1,
                    items_json={"loop": playlist.loop_enabled, "items": snapshot},
                )
                self.db.add(version)
                await self.db.flush()
                playlist.current_version_id = version.id
                self.published_playlists.append(playlist)
            self.playlists.append(playlist)
            self._bump("playlists")
        await self.db.flush()

    # --- campaigns ---------------------------------------------------------

    async def create_campaigns(self, count: int) -> None:
        # Deliberately spread across the lifecycle: a demo where everything
        # is "published" shows none of the workflow.
        distribution = (
            ["published"] * 8 + ["scheduled_like"] * 4 + ["approved"] * 2
            + ["pending_approval"] * 2 + ["draft"] * 3 + ["paused"] * 1
            + ["expired"] * 2 + ["archived"] * 1
        )
        # Shuffled, not indexed modulo: a tenant with fewer campaigns than
        # the distribution length would otherwise only ever see the head of
        # the list and end up 100% published.
        self.rng.shuffle(distribution)
        self.campaigns: list[Campaign] = []
        self.published_campaigns: list[Campaign] = []
        for i in range(count):
            name = CAMPAIGN_NAMES[i % len(CAMPAIGN_NAMES)]
            if i >= len(CAMPAIGN_NAMES):
                name = f"{name} — Phase {i // len(CAMPAIGN_NAMES) + 1}"
            state = distribution[i % len(distribution)]
            status = "published" if state == "scheduled_like" else state
            # A published campaign must point at *versioned* content or the
            # manifest resolves nothing and the screen stays black; drafts may
            # reference work in progress, which is realistic.
            playlist_pool = self.published_playlists if status == "published" else self.playlists
            layout_pool = self.published_layouts if status == "published" else self.layouts
            campaign = Campaign(
                organization_id=self.org.id,
                name=name,
                status=status,
                priority=self.rng.choice([40, 50, 55, 60, 70, 80]),
                playlist_id=self.rng.choice(playlist_pool or self.playlists).id,
                layout_id=self.rng.choice(layout_pool or self.layouts).id,
                created_at=_back(days=self.rng.randint(2, 90)),
            )
            self.db.add(campaign)
            await self.db.flush()
            self.campaigns.append(campaign)
            if status == "published":
                self.published_campaigns.append(campaign)
            self._bump("campaigns")

            # Targeting: mix location, group and tag targeting.
            targets: list[tuple[str, uuid.UUID]] = []
            mode = self.rng.random()
            if mode < 0.45 and self.city_locations:
                targets = [("location", self.rng.choice(self.city_locations)[0])]
            elif mode < 0.8:
                targets = [("group", self.rng.choice(self.groups).id)]
            else:
                targets = [("tag", self.rng.choice(list(self.tags.values())).id)]
            for target_type, target_id in targets:
                self.db.add(CampaignTarget(
                    campaign_id=campaign.id, target_type=target_type,
                    target_id=target_id, include_descendants=True, is_exclusion=False,
                ))
                self._bump("campaign_targets")

            # Schedules, on Indian retail dayparts.
            for _ in range(self.rng.randint(1, 3)):
                label, start, end = self.rng.choice(DAYPARTS)
                future = state in ("approved", "pending_approval") and self.rng.random() < 0.6
                start_date = (
                    _now().date() + dt.timedelta(days=self.rng.randint(2, 30)) if future
                    else _now().date() - dt.timedelta(days=self.rng.randint(1, 45))
                )
                self.db.add(Schedule(
                    organization_id=self.org.id, campaign_id=campaign.id,
                    name=f"{label} — {name[:40]}", kind="play",
                    start_date=start_date,
                    end_date=start_date + dt.timedelta(days=self.rng.randint(14, 120)),
                    start_time=dt.time.fromisoformat(start),
                    end_time=dt.time.fromisoformat(end),
                    days_of_week=None if self.rng.random() < 0.6 else self.rng.sample(range(7), 5),
                    timezone="Asia/Kolkata",
                    priority=campaign.priority,
                ))
                self._bump("schedules")

        # A/B variants on two published campaigns (Phase-3 experiments).
        self.variants: list[CampaignVariant] = []
        for campaign in self.published_campaigns[:2]:
            for label in ("Variant A — 20% Off Creative", "Variant B — Buy One Get One"):
                variant = CampaignVariant(
                    campaign_id=campaign.id, name=label,
                    playlist_id=self.rng.choice(self.playlists).id,
                    priority=60,
                )
                self.db.add(variant)
                self.variants.append(variant)
                self._bump("campaign_variants")
        await self.db.flush()

        # A couple of deliberate overlapping windows so conflict detection
        # has something to find — not the whole estate.
        if self.published_campaigns:
            clash = self.published_campaigns[0]
            self.db.add(Schedule(
                organization_id=self.org.id, campaign_id=clash.id,
                name="Overlapping Midday Window (demo conflict)", kind="play",
                start_date=_now().date() - dt.timedelta(days=5),
                end_date=_now().date() + dt.timedelta(days=25),
                start_time=dt.time(12, 0), end_time=dt.time(15, 0),
                timezone="Asia/Kolkata", priority=clash.priority,
            ))
            self._bump("schedules")
        await self.db.flush()

    async def create_deployments(self) -> None:
        self.deployments: list[Deployment] = []
        if not self.active_devices:
            return
        for campaign in self.published_campaigns:
            fleet = self.rng.sample(
                self.active_devices, min(len(self.active_devices), self.rng.randint(8, 40))
            )
            acked = int(len(fleet) * self.rng.uniform(0.82, 0.99))
            failed = 1 if self.rng.random() < 0.45 and len(fleet) - acked > 0 else 0
            status = "published" if acked == len(fleet) else "partial"
            deployment = Deployment(
                organization_id=self.org.id, campaign_id=campaign.id,
                version=1, status=status,
                created_at=_back(days=self.rng.randint(1, 40)),
            )
            self.db.add(deployment)
            await self.db.flush()
            for i, device in enumerate(fleet):
                if i < acked:
                    state, error = "acknowledged", None
                elif failed and i == len(fleet) - 1:
                    state, error = "failed", "Player did not acknowledge within the retry window"
                else:
                    state, error = "pending", None
                self.db.add(DeploymentDevice(
                    deployment_id=deployment.id, device_id=device.id,
                    status=state, attempts=1 if state != "pending" else 0,
                    last_error=error,
                ))
            self.deployments.append(deployment)
            self._bump("deployments")
        await self.db.flush()

    # --- telemetry ---------------------------------------------------------

    async def create_playback(self, days: int, per_device_per_day: int) -> None:
        """Bulk-inserted proof-of-play so reports have real history. Written
        with Core inserts — 10k+ ORM objects would be needlessly slow."""
        if not self.active_devices or not self.published_campaigns:
            return
        rows: list[dict] = []
        assets = [a for a in self.assets if a.status == "published"] or self.assets
        # Popularity is skewed: a few campaigns carry most of the plays.
        weights = [max(1, int(20 * (0.6 ** i))) for i in range(len(self.published_campaigns))]
        for day in range(days):
            day_start = _now() - dt.timedelta(days=day)
            for device in self.active_devices:
                for _ in range(self.rng.randint(0, per_device_per_day)):
                    campaign = self.rng.choices(self.published_campaigns, weights=weights)[0]
                    asset = self.rng.choice(assets)
                    started = day_start - dt.timedelta(
                        hours=self.rng.uniform(0, 14), minutes=self.rng.uniform(0, 59)
                    )
                    duration = self.rng.choice([10, 12, 15, 20, 30])
                    ok = self.rng.random() > 0.02
                    rows.append({
                        "id": uuid.uuid4(),
                        "organization_id": self.org.id,
                        "device_id": device.id,
                        "campaign_id": campaign.id,
                        "playlist_id": campaign.playlist_id,
                        "asset_id": asset.id,
                        "started_at": started,
                        "ended_at": started + dt.timedelta(seconds=duration),
                        "result": "ok" if ok else "error",
                    })
        for chunk in range(0, len(rows), 2000):
            await self.db.execute(insert(PlaybackEvent.__table__), rows[chunk:chunk + 2000])
        self._bump("playback_events", len(rows))
        await self.db.flush()

    async def create_ops(self) -> None:
        """Incidents, notifications and audit history."""
        offline = [d for d in self.devices
                   if d.status == "active" and d.last_heartbeat_at
                   and (_now() - d.last_heartbeat_at).total_seconds() > 300]
        for device in offline[:6]:
            self.db.add(Incident(
                organization_id=self.org.id, device_id=device.id,
                type="device_offline", severity="warning",
                title=f"{device.name[:120]} has not reported in",
                state=self.rng.choice(["open", "open", "acknowledged", "resolved"]),
                opened_at=_back(hours=self.rng.randint(2, 60)),
            ))
            self._bump("incidents")

        cities = [c[1] for c in self.city_locations] or ["Kolkata"]
        for i in range(self.rng.randint(18, 30)):
            ntype, severity, template = NOTIFICATION_TEMPLATES[i % len(NOTIFICATION_TEMPLATES)]
            title = template.format(
                n=self.rng.randint(2, 14),
                campaign=self.rng.choice(self.campaigns).name if self.campaigns else "Campaign",
                location=self.rng.choice(cities),
            )
            self.db.add(Notification(
                organization_id=self.org.id,
                user_id=self.rng.choice(self.users).id if self.rng.random() < 0.5 else None,
                type=ntype, severity=severity, title=title[:200],
                message=None,
                read_at=None if self.rng.random() < 0.55 else _back(hours=self.rng.randint(1, 40)),
                created_at=_back(days=self.rng.uniform(0, 25)),
            ))
            self._bump("notifications")

        entity_pool: dict[str, list] = {
            "campaign": self.campaigns, "asset": self.assets,
            "playlist": self.playlists, "device": self.devices,
        }
        for i in range(self.rng.randint(60, 100)):
            action, entity_type = AUDIT_ACTIONS[i % len(AUDIT_ACTIONS)]
            pool = entity_pool.get(entity_type)
            entity = self.rng.choice(pool) if pool else None
            actor = self.rng.choice(self.users)
            actor_ip = (
                f"103.{self.rng.randint(1, 250)}.{self.rng.randint(1, 250)}"
                f".{self.rng.randint(2, 250)}"
            )
            self.db.add(AuditLog(
                organization_id=self.org.id,
                user_id=actor.id,
                action=action,
                entity_type=entity_type,
                entity_id=str(entity.id) if entity is not None else None,
                after_json={"name": getattr(entity, "name", None)} if entity is not None else None,
                ip_address=actor_ip,
                created_at=_back(days=self.rng.uniform(0, 55)),
            ))
            self._bump("audit_logs")
        await self.db.flush()

    # --- governance & phase 3 ---------------------------------------------

    async def create_governance(self) -> None:
        for entity_type in ("campaign", "template"):
            self.db.add(ApprovalPolicy(
                organization_id=self.org.id, entity_type=entity_type,
                require_approval=True, maker_checker=entity_type == "campaign", active=True,
            ))
        await self.db.flush()
        for campaign in [c for c in self.campaigns if c.status == "pending_approval"]:
            self.db.add(ApprovalRequest(
                organization_id=self.org.id, entity_type="campaign", entity_id=campaign.id,
                state="pending", requester_id=self.rng.choice(self.users).id,
                submitted_at=_back(days=self.rng.uniform(0.2, 6)),
            ))
            self._bump("approval_requests")
        await self.db.flush()

    async def create_phase3(self, *, video_walls: bool, advertising: bool,
                            experiments: bool, fleet_ai: bool) -> None:
        if video_walls and len(self.active_devices) >= 13:
            for wall_name, cols, rows_ in (("Kolkata Mall Lobby Video Wall", 2, 2),
                                           ("Mumbai Flagship Media Wall", 3, 3)):
                members = self.active_devices[: cols * rows_]
                wall = VideoWall(
                    organization_id=self.org.id, name=wall_name,
                    canvas_json={"width": 1920 * cols, "height": 1080 * rows_},
                    sync_policy_json={"max_drift_ms": 120},
                    status="idle",
                )
                self.db.add(wall)
                await self.db.flush()
                for index, device in enumerate(members):
                    self.db.add(VideoWallMember(
                        wall_id=wall.id, device_id=device.id,
                        role="leader" if index == 0 else "member",
                        viewport_json={"x": (index % cols) * 1920, "y": (index // cols) * 1080,
                                       "width": 1920, "height": 1080},
                    ))
                self._bump("video_walls")
                self.active_devices = self.active_devices[cols * rows_:] + members
            await self.db.flush()

        if advertising and self.published_campaigns:
            for i, advertiser in enumerate(AD_ADVERTISERS):
                spot = (
                    self.screen_locations[i % len(self.screen_locations)]
                    if self.screen_locations else None
                )
                inventory = AdInventory(
                    organization_id=self.org.id,
                    name=f"Premium Network Slot {i + 1}",
                    location_id=spot[0] if spot else None,
                    slot_type="fullscreen",
                    operating_hours_json={"start": "10:00", "end": "22:00"},
                    active=True,
                )
                self.db.add(inventory)
                await self.db.flush()
                start = _now() - dt.timedelta(days=self.rng.randint(2, 20))
                self.db.add(AdBooking(
                    organization_id=self.org.id, inventory_id=inventory.id,
                    campaign_id=self.rng.choice(self.published_campaigns).id,
                    advertiser_ref=advertiser,
                    booked_units=self.rng.choice([500, 900, 1200, 2000]),
                    start_at=start, end_at=start + dt.timedelta(days=self.rng.randint(14, 45)),
                    status=self.rng.choice(["confirmed", "confirmed", "pending", "completed"]),
                ))
                self._bump("ad_bookings")
            await self.db.flush()

        if experiments and self.variants:
            campaign = self.published_campaigns[0]
            experiment = Experiment(
                organization_id=self.org.id, campaign_id=campaign.id,
                name="Summer Promotion — Creative Test", status="running",
            )
            self.db.add(experiment)
            await self.db.flush()
            for variant in self.variants[:2]:
                self.db.add(ExperimentVariant(
                    experiment_id=experiment.id, variant_id=variant.id, allocation_pct=50,
                ))
            self._bump("experiments")
            await self.db.flush()

        if fleet_ai and self.active_devices:
            rule = AnomalyRule(
                organization_id=self.org.id, name="Playback failure spike",
                signal_type="playback_failures",
                threshold_json={"min_events": 20, "max_failure_pct": 5},
                window_hours=24, severity="warning", active=True,
            )
            self.db.add(rule)
            await self.db.flush()
            for device in self.active_devices[:3]:
                self.db.add(Anomaly(
                    organization_id=self.org.id, device_id=device.id, rule_id=rule.id,
                    score=round(self.rng.uniform(2.1, 4.4), 2),
                    state="open",
                    evidence_json={
                        "window_hours": 24,
                        "playback_events": self.rng.randint(120, 400),
                        "failures": self.rng.randint(14, 60),
                        "location_baseline_pct": 2.1,
                    },
                    recommendation="Playback failures are well above the location baseline; "
                                   "restart the player and re-sync its bundle.",
                    opened_at=_back(hours=self.rng.randint(3, 40)),
                ))
                self._bump("anomalies")
            await self.db.flush()

    async def create_integrations(self, *, dynamic_data: bool) -> None:
        """API keys, webhooks, the event bus, live data sources, alert
        rules and saved views — the surfaces under Settings → Integrations
        and Developer. Secrets are generated and hashed exactly the way
        the product does; no raw key is ever stored or logged."""
        from app.models.data_source import DataSource
        from app.models.events import DomainEvent, EventSubscription
        from app.models.integration import ApiKey, WebhookDelivery, WebhookSubscription
        from app.models.notification_rule import NotificationRule
        from app.models.saved_view import SavedView
        from app.services.api_keys import KEY_PREFIX, _hash

        for name, scopes in (
            ("Store Ops Integration", ["devices.view", "monitoring.view"]),
            ("BI Warehouse Export", ["reports.view", "reports.export"]),
        ):
            raw = KEY_PREFIX + secrets.token_urlsafe(32)  # discarded immediately
            self.db.add(ApiKey(
                organization_id=self.org.id, name=name, prefix=raw[:12],
                key_hash=_hash(raw), scopes_json=sorted(scopes),
                created_by=self.admin.id,
                created_at=_back(days=self.rng.randint(20, 120)),
            ))
            self._bump("api_keys")

        hook = WebhookSubscription(
            organization_id=self.org.id,
            url="https://ops.example-demo.internal/hooks/signage",
            event_types_json=["device.offline", "campaign.published", "deployment.failed"],
            secret=secrets.token_urlsafe(32),
            active=True,
            created_at=_back(days=self.rng.randint(30, 90)),
        )
        self.db.add(hook)
        await self.db.flush()
        self._bump("webhook_subscriptions")
        for _ in range(self.rng.randint(4, 9)):
            delivered = self.rng.random() < 0.85
            self.db.add(WebhookDelivery(
                organization_id=self.org.id, subscription_id=hook.id,
                event_type=self.rng.choice(["device.offline", "campaign.published"]),
                event_id=uuid.uuid4(),
                payload_json={"demo": True},
                state="delivered" if delivered else "failed",
                attempt_no=1 if delivered else 3,
                created_at=_back(days=self.rng.uniform(0, 20)),
            ))
            self._bump("webhook_deliveries")

        self.db.add(EventSubscription(
            organization_id=self.org.id, name="Data Platform Consumer",
            url="https://events.example-demo.internal/ingest",
            event_types_json=["*"], secret=secrets.token_urlsafe(32), active=True,
        ))
        self._bump("event_subscriptions")
        for event_type, entity in (("campaign.published", "campaign"),
                                   ("device.approved", "device")):
            self.db.add(DomainEvent(
                organization_id=self.org.id, event_type=event_type,
                entity_type=entity, entity_id=uuid.uuid4(),
                payload_json={"demo": True},
                occurred_at=_back(days=self.rng.uniform(0, 14)),
            ))
            self._bump("domain_events")

        if dynamic_data:
            for name, kind, endpoint in (
                ("Store Queue Status", "rest_json", "https://feeds.example-demo.internal/queue.json"),
                ("Corporate News Feed", "rss", "https://feeds.example-demo.internal/news.xml"),
            ):
                self.db.add(DataSource(
                    organization_id=self.org.id, name=name, type=kind, endpoint=endpoint,
                    # An env-var NAME, never a secret value (P3 3A-2 contract).
                    auth_token_ref="DEMO_FEED_TOKEN",  # noqa: S106
                    refresh_seconds=900, state="active",
                    last_ok_at=_back(minutes=self.rng.randint(2, 50)),
                ))
                self._bump("data_sources")

        for name, event_type, channels in (
            ("Critical device offline", "DEVICE_OFFLINE", ["in_app", "email"]),
            ("Deployment failures", "DEPLOYMENT_FAILED", ["in_app"]),
        ):
            self.db.add(NotificationRule(
                organization_id=self.org.id, name=name, event_type=event_type,
                channels_json=[{"channel": c, "recipients": []} for c in channels],
                condition_json={"severity": ["warning", "critical"]},
                active=True,
            ))
            self._bump("notification_rules")

        self.db.add(SavedView(
            organization_id=self.org.id, user_id=self.admin.id, module="devices",
            name="Offline displays", filter_json={"q": "", "status": "active"},
        ))
        self._bump("saved_views")
        await self.db.flush()

    async def create_subscription(self) -> None:
        from app.services import subscriptions as subscriptions_service

        await subscriptions_service.subscribe(
            self.db, self.org.id,
            plan_code=self.spec["plan"],
            billing_cycle=self.spec["billing_cycle"],
        )
        self._bump("subscriptions")


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


async def seed_demo(db: AsyncSession) -> dict[str, int]:
    rng = random.Random(SEED)  # noqa: S311 - demo data, not cryptography
    system_roles = {
        r.name: r for r in (
            await db.execute(select(Role).where(Role.organization_id.is_(None)))
        ).scalars().all()
    }
    if not system_roles:
        raise RuntimeError("System roles are missing — run `python -m app.seed` first.")

    totals: dict[str, int] = {}
    geography = INDIA_GEOGRAPHY
    profiles = [
        # (states slice, stores per area, users, campaigns, playback days, plays/device/day)
        (geography, 1, 10, 22, 30, 5),
        (geography[:3], 1, 6, 14, 21, 4),
        (geography[3:], 1, 5, 10, 14, 3),
    ]

    builders: list[OrgBuilder] = []
    for spec, profile in zip(DEMO_ORGS, profiles, strict=True):
        states, stores, users, campaigns, pb_days, pb_rate = profile
        logger.info("Seeding %s ...", spec["name"])
        builder = OrgBuilder(db, spec, system_roles, rng)
        await builder.create_org()
        await builder.create_users(offset=DEMO_ORGS.index(spec) * 7, count=users)
        await builder.create_locations(states, stores)
        await builder.create_devices(spec["device_target"])
        await builder.create_content()
        await builder.create_studio()
        await builder.create_playlists()
        await builder.create_campaigns(campaigns)
        await builder.create_deployments()
        await builder.create_playback(pb_days, pb_rate)
        await builder.create_ops()
        await builder.create_governance()
        await builder.create_subscription()
        await builder.create_integrations(
            dynamic_data=spec["plan"] in ("business", "professional", "enterprise"),
        )
        entitled = spec["plan"] in ("professional", "enterprise")
        await builder.create_phase3(
            video_walls=entitled,
            advertising=spec["plan"] == "enterprise",
            experiments=entitled,
            fleet_ai=entitled,
        )
        builders.append(builder)
        for key, value in builder.counts.items():
            totals[key] = totals.get(key, 0) + value
        await db.flush()
        logger.info("  %s: %s", spec["code"],
                    ", ".join(f"{k}={v}" for k, v in sorted(builder.counts.items())))

    # One person, two tenants, different roles — this is what makes the
    # header's tenant switcher appear and is the only way to demo tenant
    # switching and isolation as the same human.
    guest = next(u for u in builders[0].users if u.email.startswith("vikram.malhotra"))
    host = builders[1]
    db.add(
        TenantUser(
            organization_id=host.org.id,
            user_id=guest.id,
            role_id=system_roles["Viewer"].id,
            is_owner=False,
            status="active",
        )
    )
    totals["cross_tenant_memberships"] = 1

    # `is_superuser` unlocks /platform but does NOT bypass tenant scoping:
    # every tenant-facing screen reads the active organization, which the
    # server verifies against a real membership. Without one, the Super
    # Admin can only ever see its own home org. Granting an explicit
    # membership in each demo tenant is how the product itself models
    # this, and it makes the tenant switcher able to reach all of them.
    platform_admin = (
        await db.execute(select(User).where(User.email == PLATFORM_ADMIN_EMAIL))
    ).scalars().first()
    if platform_admin is not None:
        for builder in builders:
            db.add(
                TenantUser(
                    organization_id=builder.org.id,
                    user_id=platform_admin.id,
                    role_id=system_roles["Organization Administrator"].id,
                    is_owner=False,
                    status="active",
                )
            )
        totals["platform_admin_memberships"] = len(builders)
    await db.flush()

    # Usage counters drive the Plan & Usage screens.
    from app.services import usage as usage_service

    await usage_service.snapshot_usage(db)
    return totals


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


async def validate_demo(db: AsyncSession) -> tuple[list[str], list[str]]:
    """Returns (checks_passed, failures). Every check is a real query."""
    passed: list[str] = []
    failed: list[str] = []

    def check(ok: bool, label: str) -> None:
        (passed if ok else failed).append(label)

    orgs = (
        await db.execute(select(Organization).where(Organization.code.in_(DEMO_ORG_CODES)))
    ).scalars().all()
    check(len(orgs) == len(DEMO_ORG_CODES), f"all {len(DEMO_ORG_CODES)} demo tenants exist")
    org_ids = [o.id for o in orgs]
    if not org_ids:
        return passed, failed

    # System master data preserved.
    from app.models import Permission
    from app.models.saas import Plan

    perms = (await db.execute(select(func.count()).select_from(Permission))).scalar_one()
    plans = (await db.execute(select(func.count()).select_from(Plan))).scalar_one()
    sys_roles = (
        await db.execute(
            select(func.count()).select_from(Role).where(Role.organization_id.is_(None))
        )
    ).scalar_one()
    check(perms > 40, f"permission catalogue intact ({perms})")
    check(plans >= 4, f"plan catalogue intact ({plans})")
    check(sys_roles >= 4, f"system roles intact ({sys_roles})")

    platform = (
        await db.execute(select(User).where(User.email == "platform@signage.cloud"))
    ).scalars().first()
    check(platform is not None and platform.is_superuser, "platform administrator preserved")

    fixture = (
        await db.execute(select(User).where(User.email == "admin@demo-org.com"))
    ).scalars().first()
    check(fixture is not None, "test-fixture admin (admin@demo-org.com) preserved")

    # Referential integrity of the demo world.
    orphan_devices = (await db.execute(text(
        "SELECT count(*) FROM devices d WHERE d.organization_id = ANY(:ids) "
        "AND d.location_id IS NOT NULL AND NOT EXISTS "
        "(SELECT 1 FROM locations l WHERE l.id = d.location_id "
        "AND l.organization_id = d.organization_id)"
    ), {"ids": org_ids})).scalar_one()
    check(orphan_devices == 0, "every device points at a location in its own tenant")

    broken_parents = (await db.execute(text(
        "SELECT count(*) FROM locations l WHERE l.organization_id = ANY(:ids) "
        "AND l.parent_id IS NOT NULL AND NOT EXISTS "
        "(SELECT 1 FROM locations p WHERE p.id = l.parent_id)"
    ), {"ids": org_ids})).scalar_one()
    check(broken_parents == 0, "location tree has no broken parents")

    orphan_playback = (await db.execute(text(
        "SELECT count(*) FROM playback_events e WHERE e.organization_id = ANY(:ids) "
        "AND NOT EXISTS (SELECT 1 FROM devices d WHERE d.id = e.device_id)"
    ), {"ids": org_ids})).scalar_one()
    check(orphan_playback == 0, "every playback event references a live device")

    orphan_items = (await db.execute(text(
        "SELECT count(*) FROM playlist_items i JOIN playlists p ON p.id = i.playlist_id "
        "WHERE p.organization_id = ANY(:ids) AND i.asset_id IS NOT NULL "
        "AND NOT EXISTS (SELECT 1 FROM assets a WHERE a.id = i.asset_id)"
    ), {"ids": org_ids})).scalar_one()
    check(orphan_items == 0, "every playlist item references a real asset")

    empty_playlists = (await db.execute(text(
        "SELECT count(*) FROM playlists p WHERE p.organization_id = ANY(:ids) "
        "AND NOT EXISTS (SELECT 1 FROM playlist_items i WHERE i.playlist_id = p.id)"
    ), {"ids": org_ids})).scalar_one()
    check(empty_playlists == 0, "no empty playlists")

    untargeted = (await db.execute(text(
        "SELECT count(*) FROM campaigns c WHERE c.organization_id = ANY(:ids) "
        "AND NOT EXISTS (SELECT 1 FROM campaign_targets t WHERE t.campaign_id = c.id)"
    ), {"ids": org_ids})).scalar_one()
    check(untargeted == 0, "every campaign has at least one target")

    assets_without_version = (await db.execute(text(
        "SELECT count(*) FROM assets a WHERE a.organization_id = ANY(:ids) "
        "AND a.current_version_id IS NULL"
    ), {"ids": org_ids})).scalar_one()
    check(assets_without_version == 0, "every asset has a current version")

    roleless = (await db.execute(text(
        "SELECT count(*) FROM users u WHERE u.organization_id = ANY(:ids) "
        "AND NOT EXISTS (SELECT 1 FROM user_roles r WHERE r.user_id = u.id)"
    ), {"ids": org_ids})).scalar_one()
    check(roleless == 0, "every demo user holds a role")

    unsubscribed = (await db.execute(text(
        "SELECT count(*) FROM organizations o WHERE o.id = ANY(:ids) AND NOT EXISTS "
        "(SELECT 1 FROM subscriptions s WHERE s.organization_id = o.id)"
    ), {"ids": org_ids})).scalar_one()
    check(unsubscribed == 0, "every demo tenant has a subscription")

    # Cross-tenant leakage: no child row may point at another tenant's parent.
    leaks = (await db.execute(text(
        "SELECT count(*) FROM devices d JOIN locations l ON l.id = d.location_id "
        "WHERE d.organization_id <> l.organization_id"
    ))).scalar_one()
    check(leaks == 0, "no device/location cross-tenant leakage")

    statuses = (await db.execute(text(
        "SELECT count(DISTINCT status) FROM campaigns WHERE organization_id = ANY(:ids)"
    ), {"ids": org_ids})).scalar_one()
    check(statuses >= 5, f"campaign lifecycle is varied ({statuses} distinct statuses)")

    # Published content must be *versioned*: `build_manifest` resolves the
    # canvas and item list through `current_version_id`, so a published
    # playlist or layout without one leaves every targeted device with an
    # empty manifest and a black screen.
    unversioned_pl = (await db.execute(text(
        "SELECT count(*) FROM playlists WHERE organization_id = ANY(:ids) "
        "AND status = 'published' AND current_version_id IS NULL"
    ), {"ids": org_ids})).scalar_one()
    check(unversioned_pl == 0, "every published playlist has a version")

    unversioned_layout = (await db.execute(text(
        "SELECT count(*) FROM layouts WHERE organization_id = ANY(:ids) "
        "AND status = 'published' AND current_version_id IS NULL"
    ), {"ids": org_ids})).scalar_one()
    check(unversioned_layout == 0, "every published layout has a version")

    dangling = (await db.execute(text(
        "SELECT count(*) FROM campaigns c JOIN playlists p ON p.id = c.playlist_id "
        "WHERE c.organization_id = ANY(:ids) AND c.status = 'published' "
        "AND p.current_version_id IS NULL"
    ), {"ids": org_ids})).scalar_one()
    check(dangling == 0, "every published campaign resolves playable content")

    return passed, failed


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


async def main() -> None:
    parser = argparse.ArgumentParser(description="Indian enterprise demo dataset")
    parser.add_argument("--reset", action="store_true", help="remove demo tenants and stop")
    parser.add_argument("--validate", action="store_true", help="validate only")
    parser.add_argument(
        "--refresh", action="store_true",
        help="re-stamp demo device heartbeats so the fleet reads healthy again",
    )
    args = parser.parse_args()

    configure_logging()
    settings = get_settings()
    if settings.is_production:
        raise SystemExit("Refusing to seed demo data into a production environment.")

    async with get_session_factory()() as db:
        if args.refresh:
            count = await refresh_heartbeats(db)
            await db.commit()
            logger.info("Refreshed %d device heartbeats.", count)
            return
        if args.validate:
            passed, failed = await validate_demo(db)
        elif args.reset:
            await reset_demo(db)
            await db.commit()
            logger.info("Demo tenants removed.")
            return
        else:
            await reset_demo(db)
            totals = await seed_demo(db)
            await db.commit()
            logger.info("Demo seed complete: %s",
                        ", ".join(f"{k}={v}" for k, v in sorted(totals.items())))
            passed, failed = await validate_demo(db)

    for label in passed:
        logger.info("  PASS  %s", label)
    for label in failed:
        logger.error("  FAIL  %s", label)
    if failed:
        raise SystemExit(f"{len(failed)} validation check(s) failed")
    logger.info("All %d validation checks passed.", len(passed))


if __name__ == "__main__":
    asyncio.run(main())
