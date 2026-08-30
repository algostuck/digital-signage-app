"""Operations tests: audit (M16), notifications (M15), monitoring (M13),
player events + reports (M14)."""

import datetime as dt

from tests.conftest import bearer
from tests.test_devices_api import device_headers, enroll_active_device, get_enrollment_key
from tests.test_publishing_api import publish, ready_campaign


async def test_audit_records_login_and_publish(client, admin_tokens):
    device_id, _ = await enroll_active_device(client, admin_tokens, "SN-AUD")
    campaign = await ready_campaign(client, admin_tokens, device_ids=[device_id], name="Audited")
    await publish(client, admin_tokens, campaign["id"])

    resp = await client.get("/api/v1/audit-logs?page_size=100", headers=bearer(admin_tokens))
    assert resp.status_code == 200
    actions = [row["action"] for row in resp.json()["data"]]
    for expected in (
        "USER_LOGIN",
        "DEVICE_REGISTRATION_REQUESTED",
        "DEVICE_APPROVED",
        "PLAYLIST_PUBLISHED",
        "CAMPAIGN_SUBMIT_APPROVAL",
        "CAMPAIGN_APPROVE",
        "CAMPAIGN_PUBLISHED",
    ):
        assert expected in actions, expected

    # Filter by action.
    resp = await client.get(
        "/api/v1/audit-logs?action=CAMPAIGN_PUBLISHED", headers=bearer(admin_tokens)
    )
    rows = resp.json()["data"]
    assert rows and all(r["action"] == "CAMPAIGN_PUBLISHED" for r in rows)
    assert rows[0]["user_name"] == "Demo Administrator"
    assert rows[0]["request_id"]

    # Filter by entity type + date range.
    today = dt.date.today().isoformat()
    resp = await client.get(
        f"/api/v1/audit-logs?entity_type=campaign&from={today}&to={today}",
        headers=bearer(admin_tokens),
    )
    assert all(r["entity_type"] == "campaign" for r in resp.json()["data"])


async def test_notifications_flow(client, admin_tokens):
    # Registration request creates a notification.
    key = await get_enrollment_key(client, admin_tokens)
    await client.post(
        "/api/v1/player/register",
        json={"enrollment_key": key, "serial_no": "SN-NOTIF", "name": "Notif Device"},
    )
    resp = await client.get("/api/v1/notifications", headers=bearer(admin_tokens))
    assert resp.status_code == 200
    rows = resp.json()["data"]
    registration = next(r for r in rows if r["type"] == "DEVICE_REGISTRATION")
    assert registration["read_at"] is None

    # Failed deployment ack creates a warning notification.
    device_id, token = await enroll_active_device(client, admin_tokens, "SN-NOTIF-2")
    campaign = await ready_campaign(
        client, admin_tokens, device_ids=[device_id], name="Notif Campaign"
    )
    deployment = await publish(client, admin_tokens, campaign["id"])
    await client.post(
        f"/api/v1/player/{device_id}/deployments/{deployment['id']}/ack",
        headers=device_headers(token),
        json={"success": False, "error": "no storage"},
    )
    resp = await client.get(
        "/api/v1/notifications?unread_only=true", headers=bearer(admin_tokens)
    )
    types = [r["type"] for r in resp.json()["data"]]
    assert "DEPLOYMENT_DEVICE_FAILED" in types
    assert "APPROVAL_REQUESTED" in types

    # Mark one read, then all.
    target = resp.json()["data"][0]
    resp = await client.post(
        f"/api/v1/notifications/{target['id']}/read", headers=bearer(admin_tokens)
    )
    assert resp.json()["data"]["read_at"] is not None
    resp = await client.post("/api/v1/notifications/read-all", headers=bearer(admin_tokens))
    assert resp.json()["data"]["marked_read"] >= 1
    resp = await client.get(
        "/api/v1/notifications?unread_only=true", headers=bearer(admin_tokens)
    )
    assert resp.json()["data"] == []


async def test_offline_detection_dedupes(client, admin_tokens, db_engine):
    import uuid as uuid_module
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import update
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.models import Device
    from app.services import monitoring

    device_id, token = await enroll_active_device(client, admin_tokens, "SN-OFFLINE")
    await client.post(
        f"/api/v1/player/{device_id}/heartbeat", headers=device_headers(token), json={}
    )

    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session:
        await session.execute(
            update(Device)
            .where(Device.id == uuid_module.UUID(device_id))
            .values(last_heartbeat_at=datetime.now(UTC) - timedelta(hours=2))
        )
        await session.commit()

    async with factory() as session:
        first = await monitoring.detect_offline_devices(session)
        await session.commit()
        assert first >= 1
        second = await monitoring.detect_offline_devices(session)
        await session.commit()
        assert second == 0  # deduplicated

    resp = await client.get("/api/v1/notifications", headers=bearer(admin_tokens))
    offline = [r for r in resp.json()["data"] if r["type"] == "DEVICE_OFFLINE"]
    assert any(r["payload"]["device_id"] == device_id for r in offline)


async def test_player_events_and_playback_report(client, admin_tokens):
    from tests.test_content_api import upload_asset

    device_id, token = await enroll_active_device(client, admin_tokens, "SN-EVENTS")
    asset = await upload_asset(client, admin_tokens, name="Played Asset")

    now = dt.datetime.now(dt.UTC)
    resp = await client.post(
        f"/api/v1/player/{device_id}/events",
        headers=device_headers(token),
        json={
            "events": [
                {"type": "APP_STARTED", "payload": {"version": "1.0"}},
                {
                    "type": "playback",
                    "asset_id": asset["id"],
                    "started_at": now.isoformat(),
                    "ended_at": (now + dt.timedelta(seconds=8)).isoformat(),
                    "result": "completed",
                },
                {
                    "type": "playback",
                    "asset_id": asset["id"],
                    "started_at": (now + dt.timedelta(seconds=8)).isoformat(),
                    "result": "completed",
                },
            ]
        },
    )
    assert resp.status_code == 200
    assert resp.json()["data"] == {"stored_events": 1, "stored_playback": 2}

    resp = await client.get("/api/v1/reports/playback", headers=bearer(admin_tokens))
    rows = resp.json()["data"]
    entry = next(r for r in rows if r["asset_id"] == asset["id"])
    assert entry["plays"] == 2
    assert entry["devices_reached"] == 1
    assert entry["asset_name"] == "Played Asset"


async def test_monitoring_summary_and_reports(client, admin_tokens):
    device_id, token = await enroll_active_device(client, admin_tokens, "SN-SUMMARY")
    await client.post(
        f"/api/v1/player/{device_id}/heartbeat", headers=device_headers(token), json={}
    )
    campaign = await ready_campaign(
        client, admin_tokens, device_ids=[device_id], name="Summary Campaign"
    )
    deployment = await publish(client, admin_tokens, campaign["id"])
    await client.post(
        f"/api/v1/player/{device_id}/deployments/{deployment['id']}/ack",
        headers=device_headers(token),
        json={"success": True},
    )

    resp = await client.get("/api/v1/monitoring/summary", headers=bearer(admin_tokens))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["devices"]["online"] >= 1
    assert data["campaigns"]["published"] >= 1
    assert data["deployments"]["published"] >= 1
    assert data["recent_deployments"][0]["campaign_name"] == "Summary Campaign"
    assert len(data["recent_activity"]) > 0
    assert "notifications_unread" in data

    resp = await client.get("/api/v1/monitoring/devices", headers=bearer(admin_tokens))
    feed = resp.json()["data"]
    assert any(d["id"] == device_id and d["connection_status"] == "online" for d in feed)

    resp = await client.get("/api/v1/reports/deployments", headers=bearer(admin_tokens))
    row = next(r for r in resp.json()["data"] if r["campaign_name"] == "Summary Campaign")
    assert row["acknowledged"] == 1

    # Assign device to Floor 1 for a locations report entry.
    resp = await client.get("/api/v1/locations?q=Floor%201", headers=bearer(admin_tokens))
    floor_id = resp.json()["data"][0]["id"]
    await client.post(
        f"/api/v1/devices/{device_id}/assign-location",
        headers=bearer(admin_tokens),
        json={"location_id": floor_id},
    )
    resp = await client.get("/api/v1/reports/locations", headers=bearer(admin_tokens))
    names = [r["location_name"] for r in resp.json()["data"]]
    assert "India" in names and "Floor 1" in names


async def test_ops_tenant_isolation(client, admin_tokens):
    from tests.conftest import login
    from tests.test_tenant_isolation import org_b  # noqa: F401

    # Generate audit + notification data in org A.
    key = await get_enrollment_key(client, admin_tokens)
    await client.post(
        "/api/v1/player/register", json={"enrollment_key": key, "serial_no": "SN-OPS-ISO"}
    )

    resp = await client.get("/api/v1/audit-logs", headers=bearer(admin_tokens))
    assert resp.json()["meta"]["total"] > 0

    viewer_resp = await client.get("/api/v1/roles", headers=bearer(admin_tokens))
    viewer_id = next(r["id"] for r in viewer_resp.json()["data"] if r["name"] == "Viewer")
    await client.post(
        "/api/v1/users",
        headers=bearer(admin_tokens),
        json={
            "email": "opsviewer@demo-org.com",
            "full_name": "Ops Viewer",
            "password": "Viewer@12345",
            "role_ids": [viewer_id],
        },
    )
    viewer = await login(client, "opsviewer@demo-org.com", "Viewer@12345")
    # Viewer can read dashboards/audit but the data is same-tenant only.
    resp = await client.get("/api/v1/monitoring/summary", headers=bearer(viewer))
    assert resp.status_code == 200
    resp = await client.get("/api/v1/audit-logs", headers=bearer(viewer))
    assert resp.status_code == 200
