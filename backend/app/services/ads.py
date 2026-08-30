"""Ad monetization service (P3-M05, slice 3D-1).

Delivery rides the existing campaign pipeline untouched; this module owns
the COMMERCIAL layer: inventory, bookings (2A-approved), and reconciliation
of 2I proof-of-play events into billing-ready `ad_playback_links`.
Reconciliation is idempotent (one link per playback event, unique-guarded)
and independently re-runnable — the SRS's "billing reconciled independently"
exit gate.
"""

import datetime as dt
import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import (
    BusinessRuleError,
    ConflictError,
    NotFoundError,
    ValidationAppError,
)
from app.models import (
    AdBooking,
    AdInventory,
    AdPlaybackLink,
    Campaign,
    Device,
    Location,
    PlaybackEvent,
)
from app.models.ads import AdBookingStatus, AdSlotType

logger = logging.getLogger("app.ads")


def _validate_hours(hours: dict) -> dict:
    merged = {"start": "00:00", "end": "23:59", "days": None, **(hours or {})}
    for field in ("start", "end"):
        try:
            dt.time.fromisoformat(merged[field])
        except (TypeError, ValueError) as exc:
            raise ValidationAppError(f"operating_hours.{field} must be HH:MM") from exc
    days = merged.get("days")
    if days is not None and (
        not isinstance(days, list) or not all(isinstance(d, int) and 1 <= d <= 7 for d in days)
    ):
        raise ValidationAppError("operating_hours.days must be ISO weekdays 1..7")
    return merged


# --- inventory ---


async def get_inventory(
    db: AsyncSession, organization_id: uuid.UUID, inventory_id: uuid.UUID
) -> AdInventory:
    row = (
        await db.execute(
            select(AdInventory).where(
                AdInventory.organization_id == organization_id,
                AdInventory.id == inventory_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError("Ad inventory not found")
    return row


async def list_inventory(db: AsyncSession, organization_id: uuid.UUID) -> list[AdInventory]:
    rows = await db.execute(
        select(AdInventory)
        .where(AdInventory.organization_id == organization_id)
        .order_by(AdInventory.name)
    )
    return list(rows.scalars().all())


async def create_inventory(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    name: str,
    location_id: uuid.UUID | None = None,
    device_id: uuid.UUID | None = None,
    zone_ref: str | None = None,
    slot_type: str = AdSlotType.FULLSCREEN.value,
    operating_hours: dict | None = None,
    rate_card_ref: str | None = None,
    user_id: uuid.UUID | None = None,
) -> AdInventory:
    from app.services import entitlements

    await entitlements.require_feature(db, organization_id, "advertising")
    if slot_type not in {t.value for t in AdSlotType}:
        raise ValidationAppError("slot_type must be fullscreen or zone", field="slot_type")
    if device_id is None and location_id is None:
        raise ValidationAppError(
            "Inventory needs a device_id or a location_id scope", field="device_id"
        )
    if device_id is not None:
        device = await db.get(Device, device_id)
        if device is None or device.organization_id != organization_id:
            raise NotFoundError("Device not found")
    if location_id is not None:
        location = await db.get(Location, location_id)
        if location is None or location.organization_id != organization_id:
            raise NotFoundError("Location not found")
    exists = (
        await db.execute(
            select(AdInventory).where(
                AdInventory.organization_id == organization_id, AdInventory.name == name
            )
        )
    ).scalar_one_or_none()
    if exists is not None:
        raise ConflictError("Inventory with this name already exists", field="name")

    inventory = AdInventory(
        organization_id=organization_id,
        name=name,
        location_id=location_id,
        device_id=device_id,
        zone_ref=zone_ref,
        slot_type=slot_type,
        operating_hours_json=_validate_hours(operating_hours or {}),
        rate_card_ref=rate_card_ref,
    )
    db.add(inventory)
    await db.flush()
    await db.refresh(inventory, ["bookings"])

    from app.services import audit

    await audit.record(
        db, organization_id, action="AD_INVENTORY_CREATED",
        entity_type="ad_inventory", entity_id=inventory.id,
        after={"name": name, "slot_type": slot_type}, user_id=user_id,
    )
    return inventory


async def update_inventory(
    db: AsyncSession, organization_id: uuid.UUID, inventory_id: uuid.UUID, **changes
) -> AdInventory:
    inventory = await get_inventory(db, organization_id, inventory_id)
    if changes.get("operating_hours") is not None:
        inventory.operating_hours_json = _validate_hours(changes["operating_hours"])
    for field in ("name", "rate_card_ref", "active", "zone_ref"):
        if field in changes and changes[field] is not None:
            setattr(inventory, field, changes[field])
    await db.flush()
    return inventory


# --- bookings (2A-approved) ---


async def get_booking(
    db: AsyncSession, organization_id: uuid.UUID, booking_id: uuid.UUID
) -> AdBooking:
    row = (
        await db.execute(
            select(AdBooking).where(
                AdBooking.organization_id == organization_id, AdBooking.id == booking_id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError("Ad booking not found")
    return row


async def list_bookings(db: AsyncSession, organization_id: uuid.UUID) -> list[AdBooking]:
    rows = await db.execute(
        select(AdBooking)
        .where(AdBooking.organization_id == organization_id)
        .order_by(AdBooking.created_at.desc())
    )
    return list(rows.scalars().all())


async def create_booking(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    inventory_id: uuid.UUID,
    campaign_id: uuid.UUID,
    advertiser_ref: str,
    booked_units: int,
    start_at: datetime,
    end_at: datetime,
    frequency: dict | None = None,
    user_id: uuid.UUID | None = None,
) -> AdBooking:
    from app.services import entitlements

    await entitlements.require_feature(db, organization_id, "advertising")
    inventory = await get_inventory(db, organization_id, inventory_id)
    if not inventory.active:
        raise BusinessRuleError("This inventory slot is inactive")
    campaign = (
        await db.execute(
            select(Campaign).where(
                Campaign.organization_id == organization_id, Campaign.id == campaign_id
            )
        )
    ).scalar_one_or_none()
    if campaign is None:
        raise NotFoundError("Campaign not found")
    if end_at <= start_at:
        raise ValidationAppError("end_at must be after start_at", field="end_at")
    if booked_units < 1:
        raise ValidationAppError("booked_units must be >= 1", field="booked_units")
    overlap = (
        await db.execute(
            select(AdBooking).where(
                AdBooking.inventory_id == inventory_id,
                AdBooking.status.in_(
                    [AdBookingStatus.PENDING.value, AdBookingStatus.CONFIRMED.value]
                ),
                AdBooking.start_at < end_at,
                AdBooking.end_at > start_at,
            )
        )
    ).scalars().first()
    if overlap is not None:
        raise ConflictError("The slot is already booked for an overlapping window")

    booking = AdBooking(
        organization_id=organization_id,
        inventory_id=inventory_id,
        campaign_id=campaign_id,
        advertiser_ref=advertiser_ref,
        booked_units=booked_units,
        start_at=start_at,
        end_at=end_at,
        frequency_json=frequency,
    )
    db.add(booking)
    await db.flush()
    await db.refresh(booking, ["links"])

    from app.services import approvals, audit

    await audit.record(
        db, organization_id, action="AD_BOOKING_CREATED",
        entity_type="ad_booking", entity_id=booking.id,
        after={"advertiser": advertiser_ref, "units": booked_units,
               "campaign_id": str(campaign_id)},
        user_id=user_id,
    )
    # Bookings ride the 2A engine (auto-approve when policy doesn't require).
    await approvals.submit(db, organization_id, "ad_booking", booking.id,
                           requester_id=user_id)
    await db.refresh(booking)
    return booking


async def cancel_booking(
    db: AsyncSession, organization_id: uuid.UUID, booking_id: uuid.UUID,
    *, user_id: uuid.UUID | None = None,
) -> AdBooking:
    booking = await get_booking(db, organization_id, booking_id)
    if booking.status == AdBookingStatus.COMPLETED.value:
        raise BusinessRuleError("Completed bookings cannot be cancelled")
    booking.status = AdBookingStatus.CANCELLED.value
    await db.flush()

    from app.services import audit

    await audit.record(
        db, organization_id, action="AD_BOOKING_CANCELLED",
        entity_type="ad_booking", entity_id=booking.id, user_id=user_id,
    )
    return booking


# --- reconciliation (billing-ready PoP linkage) ---


def _within_hours(event_at: datetime, hours: dict) -> bool:
    start = dt.time.fromisoformat(hours.get("start", "00:00"))
    end = dt.time.fromisoformat(hours.get("end", "23:59"))
    days = hours.get("days")
    if days is not None and event_at.isoweekday() not in days:
        return False
    current = event_at.time()
    return start <= current <= end if start <= end else current >= start or current <= end


async def reconcile_bookings(db: AsyncSession, *, limit_per_booking: int = 5000) -> dict:
    """Beat sweep: link unlinked playback events of confirmed bookings.
    Idempotent (unique playback_event_id); marks bookings completed once
    their window has passed."""
    now = datetime.now(UTC)
    bookings = (
        await db.execute(
            select(AdBooking).where(
                AdBooking.status == AdBookingStatus.CONFIRMED.value
            )
        )
    ).scalars().all()
    linked = completed = 0
    for booking in bookings:
        inventory = await db.get(AdInventory, booking.inventory_id)
        query = (
            select(PlaybackEvent)
            .where(
                PlaybackEvent.organization_id == booking.organization_id,
                PlaybackEvent.campaign_id == booking.campaign_id,
                PlaybackEvent.started_at >= booking.start_at,
                PlaybackEvent.started_at <= booking.end_at,
                PlaybackEvent.id.not_in(select(AdPlaybackLink.playback_event_id)),
            )
            .limit(limit_per_booking)
        )
        if inventory is not None and inventory.device_id is not None:
            query = query.where(PlaybackEvent.device_id == inventory.device_id)
        events = (await db.execute(query)).scalars().all()
        for event in events:
            started = (
                event.started_at
                if event.started_at.tzinfo
                else event.started_at.replace(tzinfo=UTC)
            )
            billable = inventory is None or _within_hours(
                started, inventory.operating_hours_json
            )
            db.add(
                AdPlaybackLink(
                    booking_id=booking.id,
                    playback_event_id=event.id,
                    billable=billable,
                    evidence_json={
                        "device_id": str(event.device_id),
                        "started_at": started.isoformat(),
                        **({} if billable else {"reason": "outside operating hours"}),
                    },
                )
            )
            linked += 1
        end_at = (
            booking.end_at if booking.end_at.tzinfo else booking.end_at.replace(tzinfo=UTC)
        )
        if end_at < now:
            booking.status = AdBookingStatus.COMPLETED.value
            completed += 1
    await db.flush()
    return {"linked": linked, "completed": completed, "bookings": len(bookings)}


async def ad_performance(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
) -> list[dict]:
    """Booked vs delivered per booking — the billing-ready report row."""
    await reconcile_bookings(db)
    query = select(AdBooking).where(AdBooking.organization_id == organization_id)
    if date_from:
        query = query.where(AdBooking.end_at >= datetime.combine(date_from, dt.time.min, UTC))
    if date_to:
        query = query.where(AdBooking.start_at <= datetime.combine(date_to, dt.time.max, UTC))
    bookings = (await db.execute(query.order_by(AdBooking.start_at))).scalars().all()
    rows = []
    for booking in bookings:
        inventory = await db.get(AdInventory, booking.inventory_id)
        campaign = await db.get(Campaign, booking.campaign_id)
        billable = (
            await db.execute(
                select(func.count()).where(
                    AdPlaybackLink.booking_id == booking.id,
                    AdPlaybackLink.billable.is_(True),
                )
            )
        ).scalar_one()
        total_links = (
            await db.execute(
                select(func.count()).where(AdPlaybackLink.booking_id == booking.id)
            )
        ).scalar_one()
        rows.append(
            {
                "booking_id": str(booking.id),
                "advertiser": booking.advertiser_ref,
                "inventory": inventory.name if inventory else None,
                "campaign": campaign.name if campaign else None,
                "status": booking.status,
                "window_start": booking.start_at.isoformat(),
                "window_end": booking.end_at.isoformat(),
                "booked_units": booking.booked_units,
                "delivered_billable": billable,
                "delivered_total": total_links,
                "fill_rate_pct": round(100 * billable / booking.booked_units, 1)
                if booking.booked_units
                else 0,
            }
        )
    return rows


# --- 2A approval adapter ---


async def _booking_name(
    db: AsyncSession, organization_id: uuid.UUID, booking_id: uuid.UUID
) -> str | None:
    booking = await get_booking(db, organization_id, booking_id)
    return f"Ad booking {booking.advertiser_ref} ({booking.booked_units} plays)"


async def _booking_on_approved(
    db: AsyncSession, organization_id: uuid.UUID, booking_id: uuid.UUID
) -> None:
    booking = await get_booking(db, organization_id, booking_id)
    if booking.status == AdBookingStatus.PENDING.value:
        booking.status = AdBookingStatus.CONFIRMED.value
        await db.flush()


async def _booking_on_rejected(
    db: AsyncSession, organization_id: uuid.UUID, booking_id: uuid.UUID
) -> None:
    booking = await get_booking(db, organization_id, booking_id)
    if booking.status == AdBookingStatus.PENDING.value:
        booking.status = AdBookingStatus.CANCELLED.value
        await db.flush()


def _register_booking_adapter() -> None:
    from app.services import approvals

    approvals.register_adapter(
        "ad_booking",
        approvals.EntityAdapter(
            approve_permission="ads.manage",
            get_name=_booking_name,
            on_approved=_booking_on_approved,
            on_rejected=_booking_on_rejected,
        ),
    )


_register_booking_adapter()
