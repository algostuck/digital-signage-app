"""Global search (P2-SRC-001): one query across every module the caller may
view. Results are grouped by module and strictly permission-filtered — a
module the user cannot view is absent entirely, not empty."""

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ValidationAppError
from app.models import (
    Asset,
    Campaign,
    Device,
    Location,
    Playlist,
    Schedule,
    User,
)

MAX_PER_MODULE = 10
MIN_QUERY_LENGTH = 2


async def global_search(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    query: str,
    permissions: set[str],
    is_superuser: bool = False,
) -> dict[str, list[dict]]:
    query = (query or "").strip()
    if len(query) < MIN_QUERY_LENGTH:
        raise ValidationAppError(
            f"q must be at least {MIN_QUERY_LENGTH} characters", field="q"
        )
    pattern = f"%{query.lower()}%"

    def allowed(code: str) -> bool:
        return is_superuser or code in permissions

    results: dict[str, list[dict]] = {}

    if allowed("devices.view"):
        rows = await db.execute(
            select(Device)
            .where(
                Device.organization_id == organization_id,
                or_(
                    func.lower(Device.name).like(pattern),
                    func.lower(Device.serial_no).like(pattern),
                ),
            )
            .order_by(Device.name)
            .limit(MAX_PER_MODULE)
        )
        results["devices"] = [
            {"id": str(d.id), "name": d.name, "subtitle": d.serial_no, "status": d.status}
            for d in rows.scalars().all()
        ]

    if allowed("content.view"):
        rows = await db.execute(
            select(Asset)
            .where(
                Asset.organization_id == organization_id,
                func.lower(Asset.name).like(pattern),
            )
            .order_by(Asset.name)
            .limit(MAX_PER_MODULE)
        )
        results["content"] = [
            {"id": str(a.id), "name": a.name, "subtitle": a.type, "status": a.status}
            for a in rows.scalars().all()
        ]

    if allowed("locations.view"):
        rows = await db.execute(
            select(Location)
            .where(
                Location.organization_id == organization_id,
                func.lower(Location.name).like(pattern),
            )
            .order_by(Location.path)
            .limit(MAX_PER_MODULE)
        )
        results["locations"] = [
            {"id": str(loc.id), "name": loc.name, "subtitle": f"level {loc.depth}",
             "status": loc.status}
            for loc in rows.scalars().all()
        ]

    if allowed("campaigns.view"):
        rows = await db.execute(
            select(Campaign)
            .where(
                Campaign.organization_id == organization_id,
                func.lower(Campaign.name).like(pattern),
            )
            .order_by(Campaign.name)
            .limit(MAX_PER_MODULE)
        )
        results["campaigns"] = [
            {"id": str(c.id), "name": c.name, "subtitle": f"priority {c.priority}",
             "status": c.status}
            for c in rows.scalars().all()
        ]

    if allowed("playlists.view"):
        rows = await db.execute(
            select(Playlist)
            .where(
                Playlist.organization_id == organization_id,
                func.lower(Playlist.name).like(pattern),
            )
            .order_by(Playlist.name)
            .limit(MAX_PER_MODULE)
        )
        results["playlists"] = [
            {"id": str(p.id), "name": p.name, "subtitle": None, "status": p.status}
            for p in rows.scalars().all()
        ]

    if allowed("schedules.view"):
        rows = await db.execute(
            select(Schedule)
            .where(
                Schedule.organization_id == organization_id,
                Schedule.name.is_not(None),
                func.lower(Schedule.name).like(pattern),
            )
            .order_by(Schedule.name)
            .limit(MAX_PER_MODULE)
        )
        results["schedules"] = [
            {"id": str(s.id), "name": s.name, "subtitle": s.kind, "status": None}
            for s in rows.scalars().all()
        ]

    if allowed("users.view"):
        rows = await db.execute(
            select(User)
            .where(
                User.organization_id == organization_id,
                or_(
                    func.lower(User.full_name).like(pattern),
                    func.lower(User.email).like(pattern),
                ),
            )
            .order_by(User.full_name)
            .limit(MAX_PER_MODULE)
        )
        results["users"] = [
            {"id": str(u.id), "name": u.full_name, "subtitle": u.email, "status": u.status}
            for u in rows.scalars().all()
        ]

    return results
