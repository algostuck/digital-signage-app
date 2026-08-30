"""Advanced device operations tests (P2-DEV-001/002, P2-MON-003/004, P2-SRC-003)."""

import io

from PIL import Image

from tests.conftest import bearer, login
from tests.test_devices_api import device_headers, enroll_active_device
from tests.test_tenant_isolation import org_b  # noqa: F401 (fixture)


async def assign_location(client, tokens, device_id, query):
    resp = await client.get(f"/api/v1/locations?q={query}", headers=bearer(tokens))
    location_id = resp.json()["data"][0]["id"]
    resp = await client.post(
        f"/api/v1/devices/{device_id}/assign-location",
        headers=bearer(tokens),
        json={"location_id": location_id},
    )
    assert resp.status_code == 200
    return location_id


async def enroll_with(client, admin_tokens, serial, **attrs) -> tuple[str, str]:
    """Enrollment with registration attributes (manufacturer, platform...)."""
    from tests.test_devices_api import get_enrollment_key, register

    key = await get_enrollment_key(client, admin_tokens)
    reg = await register(client, key, serial, **attrs)
    resp = await client.post(
        f"/api/v1/devices/{reg['device_id']}/approve", headers=bearer(admin_tokens)
    )
    assert resp.status_code == 200
    polled = await register(client, key, serial)
    return reg["device_id"], polled["device_token"]


async def test_dynamic_group_preview_and_campaign_publish(client, admin_tokens):
    """SRS §8 acceptance #1: dynamic Samsung-in-subtree group -> preview ->
    publish a campaign to the group."""
    samsung_in, _ = await enroll_with(
        client, admin_tokens, "SN-DG-SAM1", manufacturer="Samsung", platform="tizen"
    )
    samsung_out, _ = await enroll_with(
        client, admin_tokens, "SN-DG-SAM2", manufacturer="Samsung", platform="tizen"
    )
    lg_in, _ = await enroll_with(
        client, admin_tokens, "SN-DG-LG", manufacturer="LG", platform="webos"
    )

    kolkata_id = await assign_location(client, admin_tokens, samsung_in, "Kolkata")
    await assign_location(client, admin_tokens, lg_in, "Kolkata")
    # samsung_out stays unassigned (outside the subtree)

    rule = {
        "match": "all",
        "conditions": [
            {"field": "manufacturer", "operator": "eq", "value": "Samsung"},
            {"field": "location", "operator": "in_subtree", "value": kolkata_id},
        ],
    }
    # Preview before creating.
    resp = await client.post(
        "/api/v1/device-groups/preview",
        headers=bearer(admin_tokens),
        json={"rule_json": rule},
    )
    assert resp.status_code == 200, resp.text
    preview = resp.json()["data"]

    resp = await client.post(
        "/api/v1/device-groups",
        headers=bearer(admin_tokens),
        json={"name": "Samsung Kolkata", "group_type": "dynamic", "rule_json": rule},
    )
    assert resp.status_code == 201, resp.text
    group = resp.json()["data"]
    assert group["group_type"] == "dynamic"
    assert group["member_count"] == preview["count"]

    # Publish a campaign targeting the dynamic group.
    from tests.test_publishing_api import make_published_playlist, publish

    playlist = await make_published_playlist(client, admin_tokens, name="DG PL")
    from tests.test_campaigns_api import create_campaign

    campaign = await create_campaign(
        client, admin_tokens, name="DG Campaign", playlist_id=playlist["id"]
    )
    await client.post(
        "/api/v1/schedules", headers=bearer(admin_tokens), json={"campaign_id": campaign["id"]}
    )
    await client.post(
        f"/api/v1/campaigns/{campaign['id']}/targets",
        headers=bearer(admin_tokens),
        json={"targets": [{"target_type": "group", "target_id": group["id"]}]},
    )
    await client.post(
        f"/api/v1/campaigns/{campaign['id']}/submit-approval", headers=bearer(admin_tokens)
    )
    await client.post(
        f"/api/v1/campaigns/{campaign['id']}/approve", headers=bearer(admin_tokens)
    )
    deployment = await publish(client, admin_tokens, campaign["id"])
    assert deployment["total_devices"] == preview["count"]

    resp = await client.get(
        f"/api/v1/deployments/{deployment['id']}/devices", headers=bearer(admin_tokens)
    )
    targeted = {row["device_id"] for row in resp.json()["data"]}
    assert samsung_in in targeted
    assert lg_in not in targeted and samsung_out not in targeted


async def test_rule_validation(client, admin_tokens):
    async def preview(rule):
        return await client.post(
            "/api/v1/device-groups/preview",
            headers=bearer(admin_tokens),
            json={"rule_json": rule},
        )

    resp = await preview({"match": "sometimes", "conditions": []})
    assert resp.status_code == 400
    resp = await preview({"match": "all", "conditions": [{"field": "hack", "value": "x"}]})
    assert resp.status_code == 400
    resp = await preview(
        {"match": "all", "conditions": [{"field": "platform", "operator": "regex", "value": "x"}]}
    )
    assert resp.status_code == 400
    resp = await preview({"match": "all", "conditions": [{"field": "tag", "value": "flat"}]})
    assert resp.status_code == 400

    # Static groups reject rules.
    resp = await client.post(
        "/api/v1/device-groups",
        headers=bearer(admin_tokens),
        json={
            "name": "Static With Rule",
            "group_type": "static",
            "rule_json": {"match": "all", "conditions": [{"field": "platform", "value": "x"}]},
        },
    )
    assert resp.status_code == 201  # rule silently ignored for static
    assert resp.json()["data"]["rule_json"] is None


async def test_tag_rule_and_any_match(client, admin_tokens):
    dev_a, _ = await enroll_active_device(client, admin_tokens, "SN-TAGRULE-A")
    dev_b, _ = await enroll_active_device(client, admin_tokens, "SN-TAGRULE-B")
    await client.patch(
        f"/api/v1/devices/{dev_a}",
        headers=bearer(admin_tokens),
        json={"tags": [{"key": "tier", "value": "vip"}]},
    )
    resp = await client.post(
        "/api/v1/device-groups/preview",
        headers=bearer(admin_tokens),
        json={
            "rule_json": {
                "match": "any",
                "conditions": [
                    {"field": "tag", "operator": "eq", "value": {"key": "tier", "value": "vip"}},
                ],
            }
        },
    )
    data = resp.json()["data"]
    assert data["count"] == 1


async def test_bulk_group_action_queues_commands(client, admin_tokens):
    dev_a, token_a = await enroll_active_device(client, admin_tokens, "SN-BULK-A")
    dev_b, token_b = await enroll_active_device(client, admin_tokens, "SN-BULK-B")
    resp = await client.post(
        "/api/v1/device-groups", headers=bearer(admin_tokens), json={"name": "Bulk Group"}
    )
    group_id = resp.json()["data"]["id"]
    await client.post(
        f"/api/v1/device-groups/{group_id}/members",
        headers=bearer(admin_tokens),
        json={"device_ids": [dev_a, dev_b]},
    )

    resp = await client.post(
        f"/api/v1/device-groups/{group_id}/actions",
        headers=bearer(admin_tokens),
        json={"command_type": "SYNC_NOW"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"] == {"queued": 2, "skipped": 0}

    for device_id, token in ((dev_a, token_a), (dev_b, token_b)):
        resp = await client.get(
            f"/api/v1/player/{device_id}/commands", headers=device_headers(token)
        )
        assert [c["command_type"] for c in resp.json()["data"]] == ["SYNC_NOW"]


async def test_bulk_update_devices(client, admin_tokens):
    dev_a, _ = await enroll_active_device(client, admin_tokens, "SN-BU-A")
    dev_b, _ = await enroll_active_device(client, admin_tokens, "SN-BU-B")
    resp = await client.get("/api/v1/locations?q=Floor%201", headers=bearer(admin_tokens))
    floor_id = resp.json()["data"][0]["id"]

    resp = await client.post(
        "/api/v1/devices/bulk",
        headers=bearer(admin_tokens),
        json={
            "device_ids": [dev_a, dev_b],
            "location_id": floor_id,
            "add_tags": [{"key": "wave", "value": "1"}],
        },
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["updated"] == 2

    resp = await client.get(f"/api/v1/devices/{dev_a}", headers=bearer(admin_tokens))
    data = resp.json()["data"]
    assert data["location_id"] == floor_id
    assert {(t["key"], t["value"]) for t in data["tags"]} == {("wave", "1")}

    resp = await client.post(
        "/api/v1/devices/bulk",
        headers=bearer(admin_tokens),
        json={"device_ids": [dev_a], "remove_tags": [{"key": "wave", "value": "1"}]},
    )
    resp = await client.get(f"/api/v1/devices/{dev_a}", headers=bearer(admin_tokens))
    assert resp.json()["data"]["tags"] == []


async def test_screenshot_evidence_flow(client, admin_tokens):
    device_id, token = await enroll_active_device(client, admin_tokens, "SN-SHOT")
    buffer = io.BytesIO()
    Image.new("RGB", (320, 180), (10, 200, 120)).save(buffer, format="PNG")
    png = buffer.getvalue()

    resp = await client.post(
        f"/api/v1/player/{device_id}/screenshots",
        headers={**device_headers(token), "Content-Type": "image/png"},
        content=png,
    )
    assert resp.status_code == 200, resp.text

    # Wrong mime rejected.
    resp = await client.post(
        f"/api/v1/player/{device_id}/screenshots",
        headers={**device_headers(token), "Content-Type": "text/html"},
        content=b"<html>",
    )
    assert resp.status_code == 400

    # Another device's token cannot upload for this device.
    other_id, other_token = await enroll_active_device(client, admin_tokens, "SN-SHOT-2")
    resp = await client.post(
        f"/api/v1/player/{device_id}/screenshots",
        headers={**device_headers(other_token), "Content-Type": "image/png"},
        content=png,
    )
    assert resp.status_code == 404

    # Admin evidence list with a working signed URL.
    resp = await client.get(
        f"/api/v1/devices/{device_id}/screenshots", headers=bearer(admin_tokens)
    )
    rows = resp.json()["data"]
    assert len(rows) == 1
    fetched = await client.get(rows[0]["url"])
    assert fetched.status_code == 200
    assert fetched.content == png


async def test_incident_lifecycle_with_auto_recovery(client, admin_tokens, db_engine):
    """SRS §8 acceptance #5: offline -> notification; recovery -> incident
    auto-transitions to resolved."""
    import uuid as uuid_module
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import update
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.models import Device
    from app.services import monitoring

    device_id, token = await enroll_active_device(client, admin_tokens, "SN-INC")
    await client.post(
        f"/api/v1/player/{device_id}/heartbeat", headers=device_headers(token), json={}
    )

    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session:
        await session.execute(
            update(Device)
            .where(Device.id == uuid_module.UUID(device_id))
            .values(last_heartbeat_at=datetime.now(UTC) - timedelta(hours=3))
        )
        await session.commit()
    async with factory() as session:
        assert await monitoring.detect_offline_devices(session) == 1
        await session.commit()
        assert await monitoring.detect_offline_devices(session) == 0  # incident dedupe
        await session.commit()

    resp = await client.get("/api/v1/incidents?state=open", headers=bearer(admin_tokens))
    incident = next(
        i for i in resp.json()["data"] if i["device_id"] == device_id
    )
    assert incident["type"] == "device_offline"
    assert incident["device_name"]

    # Acknowledge.
    resp = await client.post(
        f"/api/v1/incidents/{incident['id']}/acknowledge", headers=bearer(admin_tokens)
    )
    assert resp.json()["data"]["state"] == "acknowledged"

    # Heartbeat recovers the device -> incident auto-resolves + notification.
    resp = await client.post(
        f"/api/v1/player/{device_id}/heartbeat", headers=device_headers(token), json={}
    )
    assert resp.status_code == 200
    resp = await client.get("/api/v1/incidents", headers=bearer(admin_tokens))
    incident_now = next(i for i in resp.json()["data"] if i["id"] == incident["id"])
    assert incident_now["state"] == "resolved"
    assert incident_now["resolution"] == "Device sent a heartbeat"

    resp = await client.get("/api/v1/notifications?page_size=100", headers=bearer(admin_tokens))
    types = [n["type"] for n in resp.json()["data"]]
    assert "DEVICE_RECOVERED" in types and "DEVICE_OFFLINE" in types


async def test_incident_permissions_and_isolation(client, admin_tokens, org_b):  # noqa: F811
    device_id, token = await enroll_active_device(client, admin_tokens, "SN-INC-ISO")

    from sqlalchemy.ext.asyncio import async_sessionmaker  # noqa: F401

    # Manually open an incident via service path (offline simulation covered
    # above); here just check RBAC + isolation on the list endpoints.
    resp = await client.get("/api/v1/roles", headers=bearer(admin_tokens))
    viewer_id = next(r["id"] for r in resp.json()["data"] if r["name"] == "Viewer")
    await client.post(
        "/api/v1/users",
        headers=bearer(admin_tokens),
        json={
            "email": "incviewer@demo-org.com",
            "full_name": "Incident Viewer",
            "password": "Viewer@12345",
            "role_ids": [viewer_id],
        },
    )
    viewer = await login(client, "incviewer@demo-org.com", "Viewer@12345")
    resp = await client.get("/api/v1/incidents", headers=bearer(viewer))
    assert resp.status_code == 200  # monitoring.view
    resp = await client.post(
        "/api/v1/incidents/00000000-0000-0000-0000-000000000000/acknowledge",
        headers=bearer(viewer),
    )
    assert resp.status_code == 403  # incidents.manage missing

    b_tokens = await login(client, "admin@org-b-corp.com", "BAdmin@12345")
    resp = await client.get("/api/v1/incidents?page_size=100", headers=bearer(b_tokens))
    assert all(i["device_id"] != device_id for i in resp.json()["data"])
