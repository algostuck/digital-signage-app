"""Phase-3 slice 3D-1: ads — inventory, 2A-approved bookings, idempotent
proof-of-play reconciliation, billing-ready performance report."""

import datetime as dt

from tests.conftest import bearer, login
from tests.test_devices_api import device_headers, enroll_active_device
from tests.test_publishing_api import publish, ready_campaign
from tests.test_reports_phase2_api import send_playback
from tests.test_tenant_isolation import org_b  # noqa: F401 (fixture)


async def booking_setup(client, admin_tokens, *, serial, name):
    """Device + published campaign + inventory slot scoped to the device."""
    device_id, token = await enroll_active_device(client, admin_tokens, serial)
    campaign = await ready_campaign(
        client, admin_tokens, device_ids=[device_id], name=name
    )
    await publish(client, admin_tokens, campaign["id"])
    resp = await client.post(
        "/api/v1/ad-inventory",
        headers=bearer(admin_tokens),
        json={"name": f"{name} slot", "device_id": device_id,
              "operating_hours": {"start": "00:00", "end": "23:59"}},
    )
    assert resp.status_code == 201, resp.text
    return device_id, token, campaign, resp.json()["data"]


async def test_inventory_validation_and_booking_overlap(client, admin_tokens):
    device_id, _token, campaign, inventory = await booking_setup(
        client, admin_tokens, serial="SN-ADS-1", name="Ads One"
    )

    # Inventory needs a scope; bad hours refused.
    resp = await client.post(
        "/api/v1/ad-inventory", headers=bearer(admin_tokens), json={"name": "No scope"}
    )
    assert resp.status_code == 400
    resp = await client.post(
        "/api/v1/ad-inventory",
        headers=bearer(admin_tokens),
        json={"name": "Bad hours", "device_id": device_id,
              "operating_hours": {"start": "nine"}},
    )
    assert resp.status_code == 400

    now = dt.datetime.now(dt.UTC)
    body = {
        "inventory_id": inventory["id"],
        "campaign_id": campaign["id"],
        "advertiser_ref": "ACME Beverages",
        "booked_units": 100,
        "start_at": (now - dt.timedelta(hours=1)).isoformat(),
        "end_at": (now + dt.timedelta(hours=1)).isoformat(),
    }
    resp = await client.post("/api/v1/ad-campaigns", headers=bearer(admin_tokens), json=body)
    assert resp.status_code == 201, resp.text
    booking = resp.json()["data"]
    # Default approval policy: booking auto-flow leaves it pending until the
    # 2A request is decided — the demo policy requires approval by default,
    # so approve it via the shared inbox.
    if booking["status"] == "pending":
        resp = await client.get(
            "/api/v1/approvals/inbox?entity_type=ad_booking&state=pending",
            headers=bearer(admin_tokens),
        )
        row = next(r for r in resp.json()["data"] if r["entity_id"] == booking["id"])
        resp = await client.post(
            f"/api/v1/approvals/{row['id']}/approve",
            headers=bearer(admin_tokens),
            json={"comments": "signed IO"},
        )
        assert resp.status_code == 200, resp.text

    # Overlapping second booking on the same slot is refused.
    resp = await client.post(
        "/api/v1/ad-campaigns",
        headers=bearer(admin_tokens),
        json={**body, "advertiser_ref": "Rival Corp"},
    )
    assert resp.status_code == 409


async def test_reconciliation_links_pop_and_reports(client, admin_tokens, db_session):
    from app.services import ads as ads_service

    device_id, token, campaign, inventory = await booking_setup(
        client, admin_tokens, serial="SN-ADS-POP", name="Ads PoP"
    )
    now = dt.datetime.now(dt.UTC)
    resp = await client.post(
        "/api/v1/ad-campaigns",
        headers=bearer(admin_tokens),
        json={
            "inventory_id": inventory["id"],
            "campaign_id": campaign["id"],
            "advertiser_ref": "ACME",
            "booked_units": 10,
            "start_at": (now - dt.timedelta(hours=2)).isoformat(),
            "end_at": (now + dt.timedelta(hours=2)).isoformat(),
        },
    )
    booking = resp.json()["data"]
    inbox = (
        await client.get(
            "/api/v1/approvals/inbox?entity_type=ad_booking&state=pending",
            headers=bearer(admin_tokens),
        )
    ).json()["data"]
    row = next(r for r in inbox if r["entity_id"] == booking["id"])
    await client.post(
        f"/api/v1/approvals/{row['id']}/approve",
        headers=bearer(admin_tokens),
        json={},
    )

    # Five plays land as proof-of-play events.
    resp = await client.get(
        f"/api/v1/player/{device_id}/manifest", headers=device_headers(token)
    )
    asset_id = resp.json()["data"]["assets"][0]["id"]
    await send_playback(
        client, device_id, token, campaign["id"], asset_id, ["completed"] * 5
    )

    result = await ads_service.reconcile_bookings(db_session)
    await db_session.commit()
    assert result["linked"] == 5
    # Idempotent: a second run links nothing new.
    result = await ads_service.reconcile_bookings(db_session)
    await db_session.commit()
    assert result["linked"] == 0

    resp = await client.get(
        "/api/v1/reports/ad-performance", headers=bearer(admin_tokens)
    )
    rows = resp.json()["data"]
    mine = next(r for r in rows if r["booking_id"] == booking["id"])
    assert mine["delivered_billable"] == 5
    assert mine["booked_units"] == 10
    assert mine["fill_rate_pct"] == 50.0

    # Export via the 2I engine.
    resp = await client.post(
        "/api/v1/reports/export",
        headers=bearer(admin_tokens),
        json={"report": "ad-performance", "format": "csv"},
    )
    assert resp.status_code == 200, resp.text
    assert b"delivered_billable" in resp.content


async def test_ads_entitlement_and_rbac(client, admin_tokens, org_b):  # noqa: F811
    b_tokens = await login(client, "admin@org-b-corp.com", "BAdmin@12345")
    resp = await client.post(
        "/api/v1/billing/subscribe", headers=bearer(b_tokens),
        json={"plan_code": "professional"},  # advertising=False on Professional
    )
    assert resp.status_code == 200
    resp = await client.post(
        "/api/v1/ad-inventory",
        headers=bearer(b_tokens),
        json={"name": "Nope", "device_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert resp.status_code == 422
    assert "advertising" in resp.text

    resp = await client.get("/api/v1/roles", headers=bearer(admin_tokens))
    viewer_id = next(r["id"] for r in resp.json()["data"] if r["name"] == "Viewer")
    await client.post(
        "/api/v1/users",
        headers=bearer(admin_tokens),
        json={"email": "ads-viewer@demo-org.com", "full_name": "Ads Viewer",
              "password": "Viewer@12345", "role_ids": [viewer_id]},
    )
    viewer = await login(client, "ads-viewer@demo-org.com", "Viewer@12345")
    resp = await client.get("/api/v1/ad-inventory", headers=bearer(viewer))
    assert resp.status_code == 200  # ads.view rides the viewer role
    resp = await client.post(
        "/api/v1/ad-inventory", headers=bearer(viewer), json={"name": "X"}
    )
    assert resp.status_code == 403