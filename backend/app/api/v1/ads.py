"""Ad monetization API (P3-M05, slice 3D-1)."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentTenantId, CurrentUser, require_permissions
from app.db.session import get_db
from app.schemas.envelope import success
from app.services import ads as service

router = APIRouter()


class InventoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    location_id: uuid.UUID | None = None
    device_id: uuid.UUID | None = None
    zone_ref: str | None = Field(default=None, max_length=50)
    slot_type: str = "fullscreen"
    operating_hours: dict | None = None
    rate_card_ref: str | None = Field(default=None, max_length=100)


class InventoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    zone_ref: str | None = None
    operating_hours: dict | None = None
    rate_card_ref: str | None = None
    active: bool | None = None


class BookingCreate(BaseModel):
    inventory_id: uuid.UUID
    campaign_id: uuid.UUID
    advertiser_ref: str = Field(min_length=1, max_length=200)
    booked_units: int = Field(ge=1)
    start_at: datetime
    end_at: datetime
    frequency: dict | None = None


def _inventory_out(inventory) -> dict:
    return {
        "id": str(inventory.id),
        "name": inventory.name,
        "location_id": str(inventory.location_id) if inventory.location_id else None,
        "device_id": str(inventory.device_id) if inventory.device_id else None,
        "zone_ref": inventory.zone_ref,
        "slot_type": inventory.slot_type,
        "operating_hours": inventory.operating_hours_json,
        "rate_card_ref": inventory.rate_card_ref,
        "active": inventory.active,
        "bookings": len(inventory.bookings),
    }


def _booking_out(booking) -> dict:
    return {
        "id": str(booking.id),
        "inventory_id": str(booking.inventory_id),
        "campaign_id": str(booking.campaign_id),
        "advertiser_ref": booking.advertiser_ref,
        "booked_units": booking.booked_units,
        "start_at": booking.start_at.isoformat(),
        "end_at": booking.end_at.isoformat(),
        "frequency": booking.frequency_json,
        "status": booking.status,
        "links": len(booking.links),
    }


@router.get("/ad-inventory", dependencies=[require_permissions("ads.view")])
async def list_inventory(tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)) -> dict:
    return success([_inventory_out(i) for i in await service.list_inventory(db, tenant_id)])


@router.post(
    "/ad-inventory", dependencies=[require_permissions("ads.manage")], status_code=201
)
async def create_inventory(
    body: InventoryCreate,
    tenant_id: CurrentTenantId,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    inventory = await service.create_inventory(
        db, tenant_id,
        name=body.name, location_id=body.location_id, device_id=body.device_id,
        zone_ref=body.zone_ref, slot_type=body.slot_type,
        operating_hours=body.operating_hours, rate_card_ref=body.rate_card_ref,
        user_id=user.id,
    )
    return success(_inventory_out(inventory))


@router.patch("/ad-inventory/{inventory_id}", dependencies=[require_permissions("ads.manage")])
async def update_inventory(
    inventory_id: uuid.UUID,
    body: InventoryUpdate,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
) -> dict:
    inventory = await service.update_inventory(
        db, tenant_id, inventory_id,
        name=body.name, zone_ref=body.zone_ref, operating_hours=body.operating_hours,
        rate_card_ref=body.rate_card_ref, active=body.active,
    )
    return success(_inventory_out(inventory))


@router.get("/ad-campaigns", dependencies=[require_permissions("ads.view")])
async def list_bookings(tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)) -> dict:
    return success([_booking_out(b) for b in await service.list_bookings(db, tenant_id)])


@router.post(
    "/ad-campaigns", dependencies=[require_permissions("ads.manage")], status_code=201
)
async def create_booking(
    body: BookingCreate,
    tenant_id: CurrentTenantId,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    booking = await service.create_booking(
        db, tenant_id,
        inventory_id=body.inventory_id, campaign_id=body.campaign_id,
        advertiser_ref=body.advertiser_ref, booked_units=body.booked_units,
        start_at=body.start_at, end_at=body.end_at, frequency=body.frequency,
        user_id=user.id,
    )
    return success(_booking_out(booking))


@router.post(
    "/ad-campaigns/{booking_id}/cancel", dependencies=[require_permissions("ads.manage")]
)
async def cancel_booking(
    booking_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    booking = await service.cancel_booking(db, tenant_id, booking_id, user_id=user.id)
    return success(_booking_out(booking))


@router.get("/reports/ad-performance", dependencies=[require_permissions("reports.view")])
async def ad_performance(
    tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    return success(await service.ad_performance(db, tenant_id))
