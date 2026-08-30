"""Phase-3 slice 3C-1: video walls — viewport validation, membership
exclusivity, sync markers in manifests, degraded-state honesty."""

import datetime as dt

from sqlalchemy import select, update

from tests.conftest import bearer, login
from tests.test_devices_api import enroll_active_device
from tests.test_tenant_isolation import org_b  # noqa: F401 (fixture)


async def enroll_online_device(client, tokens, serial):
    """Wall members must be heartbeating to count as healthy."""
    device_id, token = await enroll_active_device(client, tokens, serial)
    resp = await client.post(
        f"/api/v1/player/{device_id}/heartbeat",
        headers={"X-Device-Token": token},
        json={},
    )
    assert resp.status_code == 200
    return device_id, token


async def make_wall(client, tokens, *, name="Lobby Wall", canvas=None):
    resp = await client.post(
        "/api/v1/video-walls",
        headers=bearer(tokens),
        json={"name": name,
              "canvas": canvas or {"width": 3840, "height": 1080, "rows": 1, "cols": 2}},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


async def test_wall_membership_and_validation(client, admin_tokens):
    wall = await make_wall(client, admin_tokens)
    device_a, _ = await enroll_online_device(client, admin_tokens, "SN-WALL-A")
    device_b, _ = await enroll_online_device(client, admin_tokens, "SN-WALL-B")

    # Viewport outside the canvas is refused.
    resp = await client.post(
        f"/api/v1/video-walls/{wall['id']}/members",
        headers=bearer(admin_tokens),
        json={"device_id": device_a,
              "viewport": {"x": 3000, "y": 0, "width": 2000, "height": 1080}},
    )
    assert resp.status_code == 400

    resp = await client.post(
        f"/api/v1/video-walls/{wall['id']}/members",
        headers=bearer(admin_tokens),
        json={"device_id": device_a,
              "viewport": {"x": 0, "y": 0, "width": 1920, "height": 1080},
              "role": "leader"},
    )
    assert resp.status_code == 200, resp.text
    await client.post(
        f"/api/v1/video-walls/{wall['id']}/members",
        headers=bearer(admin_tokens),
        json={"device_id": device_b,
              "viewport": {"x": 1920, "y": 0, "width": 1920, "height": 1080}},
    )

    # A device can belong to only one wall.
    other = await make_wall(client, admin_tokens, name="Second Wall")
    resp = await client.post(
        f"/api/v1/video-walls/{other['id']}/members",
        headers=bearer(admin_tokens),
        json={"device_id": device_a,
              "viewport": {"x": 0, "y": 0, "width": 1920, "height": 1080}},
    )
    assert resp.status_code == 409

    resp = await client.get(
        f"/api/v1/video-walls/{wall['id']}", headers=bearer(admin_tokens)
    )
    state = resp.json()["data"]
    assert len(state["members"]) == 2
    assert all(m["online"] for m in state["members"])


async def test_sync_session_markers_in_manifests(client, admin_tokens):
    wall = await make_wall(client, admin_tokens, name="Sync Wall")
    devices = []
    for i, x in enumerate((0, 1920)):
        device_id, token = await enroll_online_device(client, admin_tokens, f"SN-SYNC-{i}")
        await client.post(
            f"/api/v1/video-walls/{wall['id']}/members",
            headers=bearer(admin_tokens),
            json={"device_id": device_id,
                  "viewport": {"x": x, "y": 0, "width": 1920, "height": 1080},
                  "role": "leader" if i == 0 else "member"},
        )
        devices.append((device_id, token))

    resp = await client.post(
        f"/api/v1/video-walls/{wall['id']}/sync",
        headers=bearer(admin_tokens),
        json={"action": "start"},
    )
    assert resp.status_code == 200, resp.text
    state = resp.json()["data"]
    assert state["status"] == "syncing"
    session_id = state["session"]["id"]

    blocks = []
    for device_id, token in devices:
        resp = await client.get(
            f"/api/v1/player/{device_id}/manifest", headers={"X-Device-Token": token}
        )
        sync = resp.json()["data"]["sync"]
        blocks.append(sync)
    # Same session + epoch for every member; viewports differ; tolerance set.
    assert blocks[0]["session"] == blocks[1]["session"] == session_id
    assert blocks[0]["start_epoch_ms"] == blocks[1]["start_epoch_ms"]
    assert blocks[0]["tolerance_ms"] == 50
    assert blocks[0]["viewport"] != blocks[1]["viewport"]
    assert blocks[0]["role"] == "leader"

    # Stop: markers disappear, wall idle.
    await client.post(
        f"/api/v1/video-walls/{wall['id']}/sync",
        headers=bearer(admin_tokens),
        json={"action": "stop"},
    )
    resp = await client.get(
        f"/api/v1/player/{devices[0][0]}/manifest",
        headers={"X-Device-Token": devices[0][1]},
    )
    assert "sync" not in resp.json()["data"]


async def test_degraded_state_opens_incident(client, admin_tokens, db_session):
    from app.models import Device, Incident

    wall = await make_wall(client, admin_tokens, name="Degraded Wall")
    device_id, token = await enroll_online_device(client, admin_tokens, "SN-DEG-1")
    await client.post(
        f"/api/v1/video-walls/{wall['id']}/members",
        headers=bearer(admin_tokens),
        json={"device_id": device_id,
              "viewport": {"x": 0, "y": 0, "width": 1920, "height": 1080}},
    )
    await client.post(
        f"/api/v1/video-walls/{wall['id']}/sync",
        headers=bearer(admin_tokens),
        json={"action": "start"},
    )

    # Member goes silent past the offline threshold.
    await db_session.execute(
        update(Device)
        .where(Device.serial_no == "SN-DEG-1")
        .values(last_heartbeat_at=dt.datetime.now(dt.UTC) - dt.timedelta(hours=2))
    )
    await db_session.commit()

    resp = await client.get(
        f"/api/v1/video-walls/{wall['id']}", headers=bearer(admin_tokens)
    )
    state = resp.json()["data"]
    assert state["status"] == "degraded"
    assert state["members"][0]["online"] is False

    incident = (
        await db_session.execute(
            select(Incident).where(Incident.type == "wall_degraded")
        )
    ).scalars().first()
    assert incident is not None

    # The member's manifest still serves (standalone playback) and the sync
    # block reports degraded honestly.
    resp = await client.get(
        f"/api/v1/player/{device_id}/manifest", headers={"X-Device-Token": token}
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["sync"]["degraded"] is True


async def test_wall_entitlement_and_isolation(client, admin_tokens, org_b):  # noqa: F811
    b_tokens = await login(client, "admin@org-b-corp.com", "BAdmin@12345")
    resp = await client.post(
        "/api/v1/billing/subscribe", headers=bearer(b_tokens), json={"plan_code": "business"}
    )
    assert resp.status_code == 200  # Business: video_wall=False
    resp = await client.post(
        "/api/v1/video-walls", headers=bearer(b_tokens), json={"name": "Nope"}
    )
    assert resp.status_code == 422
    assert "video_wall" in resp.text

    await make_wall(client, admin_tokens, name="Org A wall")
    resp = await client.get("/api/v1/video-walls", headers=bearer(b_tokens))
    assert resp.json()["data"] == []
