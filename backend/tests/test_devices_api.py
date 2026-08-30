"""Device management tests (FR-DEV-001..008)."""

from tests.conftest import bearer


async def get_enrollment_key(client, tokens) -> str:
    resp = await client.get("/api/v1/devices/enrollment-key", headers=bearer(tokens))
    assert resp.status_code == 200
    return resp.json()["data"]["enrollment_key"]


async def register(client, key, serial="SN-1000", **extra) -> dict:
    resp = await client.post(
        "/api/v1/player/register",
        json={"enrollment_key": key, "serial_no": serial, **extra},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


async def enroll_active_device(client, admin_tokens, serial="SN-ACTIVE") -> tuple[str, str]:
    """Full flow: register -> approve -> poll token. Returns (device_id, token)."""
    key = await get_enrollment_key(client, admin_tokens)
    reg = await register(client, key, serial)
    assert reg["status"] == "pending"
    resp = await client.post(
        f"/api/v1/devices/{reg['device_id']}/approve", headers=bearer(admin_tokens)
    )
    assert resp.status_code == 200
    reg2 = await register(client, key, serial)
    assert reg2["status"] == "active"
    assert reg2["device_token"]
    return reg["device_id"], reg2["device_token"]


def device_headers(token: str) -> dict:
    return {"X-Device-Token": token}


async def test_registration_requires_valid_key(client, admin_tokens):
    resp = await client.post(
        "/api/v1/player/register",
        json={"enrollment_key": "definitely-wrong-key", "serial_no": "SN-X"},
    )
    assert resp.status_code == 401


async def test_registration_approval_token_flow(client, admin_tokens):
    key = await get_enrollment_key(client, admin_tokens)
    reg = await register(client, key, "SN-2000", manufacturer="LG", platform="webos")
    assert reg["status"] == "pending"
    assert reg["device_token"] is None

    # Polling again while pending stays pending, same device.
    reg_again = await register(client, key, "SN-2000")
    assert reg_again["device_id"] == reg["device_id"]
    assert reg_again["status"] == "pending"

    resp = await client.post(
        f"/api/v1/devices/{reg['device_id']}/approve", headers=bearer(admin_tokens)
    )
    assert resp.status_code == 200

    # First poll after approval issues the token exactly once.
    with_token = await register(client, key, "SN-2000")
    assert with_token["device_token"]
    without_token = await register(client, key, "SN-2000")
    assert without_token["device_token"] is None


async def test_reject_flow(client, admin_tokens):
    key = await get_enrollment_key(client, admin_tokens)
    reg = await register(client, key, "SN-REJECT")
    resp = await client.post(
        f"/api/v1/devices/{reg['device_id']}/reject", headers=bearer(admin_tokens)
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "rejected"
    # A rejected device never receives a token.
    polled = await register(client, key, "SN-REJECT")
    assert polled["status"] == "rejected"
    assert polled["device_token"] is None


async def test_heartbeat_updates_state(client, admin_tokens):
    device_id, token = await enroll_active_device(client, admin_tokens, "SN-HB")
    resp = await client.post(
        f"/api/v1/player/{device_id}/heartbeat",
        headers=device_headers(token),
        json={
            "player_version": "1.2.0",
            "status": "online",
            "storage": {"used_percent": 41},
            "current": {"campaign_id": None},
        },
    )
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["acknowledged"] is True
    assert body["heartbeat_interval_seconds"] > 0

    resp = await client.get(f"/api/v1/devices/{device_id}", headers=bearer(admin_tokens))
    data = resp.json()["data"]
    assert data["last_heartbeat_at"] is not None
    assert data["connection_status"] == "online"
    assert data["player_version"] == "1.2.0"
    assert data["last_heartbeat_json"]["storage"]["used_percent"] == 41


async def test_heartbeat_rejects_bad_token(client, admin_tokens):
    device_id, _ = await enroll_active_device(client, admin_tokens, "SN-BADTOK")
    resp = await client.post(
        f"/api/v1/player/{device_id}/heartbeat",
        headers=device_headers("not-a-real-token"),
        json={},
    )
    assert resp.status_code == 401

    resp = await client.post(f"/api/v1/player/{device_id}/heartbeat", json={})
    assert resp.status_code == 401


async def test_token_stops_working_after_decommission(client, admin_tokens):
    device_id, token = await enroll_active_device(client, admin_tokens, "SN-DECOM")
    resp = await client.post(
        f"/api/v1/devices/{device_id}/decommission", headers=bearer(admin_tokens)
    )
    assert resp.status_code == 200
    resp = await client.post(
        f"/api/v1/player/{device_id}/heartbeat", headers=device_headers(token), json={}
    )
    assert resp.status_code == 401


async def test_reset_token_revokes_and_reissues(client, admin_tokens):
    device_id, token = await enroll_active_device(client, admin_tokens, "SN-RESET")
    resp = await client.post(
        f"/api/v1/devices/{device_id}/reset-token", headers=bearer(admin_tokens)
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["has_credential"] is False

    resp = await client.post(
        f"/api/v1/player/{device_id}/heartbeat", headers=device_headers(token), json={}
    )
    assert resp.status_code == 401

    key = await get_enrollment_key(client, admin_tokens)
    reissued = await register(client, key, "SN-RESET")
    assert reissued["device_token"]
    resp = await client.post(
        f"/api/v1/player/{device_id}/heartbeat",
        headers=device_headers(reissued["device_token"]),
        json={},
    )
    assert resp.status_code == 200


async def test_device_cannot_act_as_another_device(client, admin_tokens):
    id_a, token_a = await enroll_active_device(client, admin_tokens, "SN-A")
    id_b, _ = await enroll_active_device(client, admin_tokens, "SN-B")
    resp = await client.post(
        f"/api/v1/player/{id_b}/heartbeat", headers=device_headers(token_a), json={}
    )
    assert resp.status_code == 404


async def test_command_queue_roundtrip(client, admin_tokens):
    device_id, token = await enroll_active_device(client, admin_tokens, "SN-CMD")

    resp = await client.post(
        f"/api/v1/devices/{device_id}/commands",
        headers=bearer(admin_tokens),
        json={"command_type": "RESTART_PLAYER", "payload": {"delay_seconds": 5}},
    )
    assert resp.status_code == 201
    command_id = resp.json()["data"]["id"]

    # Device polls: command delivered and marked sent; second poll is empty.
    resp = await client.get(
        f"/api/v1/player/{device_id}/commands", headers=device_headers(token)
    )
    delivered = resp.json()["data"]
    assert [c["id"] for c in delivered] == [command_id]
    assert delivered[0]["status"] == "sent"
    resp = await client.get(
        f"/api/v1/player/{device_id}/commands", headers=device_headers(token)
    )
    assert resp.json()["data"] == []

    resp = await client.post(
        f"/api/v1/player/{device_id}/commands/{command_id}/ack",
        headers=device_headers(token),
        json={"success": True, "result": {"restarted": True}},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "acknowledged"

    # Double-ack is rejected.
    resp = await client.post(
        f"/api/v1/player/{device_id}/commands/{command_id}/ack",
        headers=device_headers(token),
        json={"success": True},
    )
    assert resp.status_code == 409

    resp = await client.get(
        f"/api/v1/devices/{device_id}/commands", headers=bearer(admin_tokens)
    )
    assert resp.json()["data"][0]["result_json"] == {"restarted": True}


async def test_capabilities_replace_set(client, admin_tokens):
    device_id, token = await enroll_active_device(client, admin_tokens, "SN-CAP")
    resp = await client.post(
        f"/api/v1/player/{device_id}/capabilities",
        headers=device_headers(token),
        json={
            "capabilities": [
                {"code": "POWER_CONTROL", "supported": True},
                {"code": "SCREENSHOT", "supported": False},
            ]
        },
    )
    assert resp.status_code == 200

    resp = await client.get(
        f"/api/v1/devices/{device_id}/capabilities", headers=bearer(admin_tokens)
    )
    caps = {c["capability_code"]: c["supported"] for c in resp.json()["data"]}
    assert caps == {"POWER_CONTROL": True, "SCREENSHOT": False}

    resp = await client.post(
        f"/api/v1/player/{device_id}/capabilities",
        headers=device_headers(token),
        json={"capabilities": [{"code": "POWER_CONTROL", "supported": False}]},
    )
    resp = await client.get(
        f"/api/v1/devices/{device_id}/capabilities", headers=bearer(admin_tokens)
    )
    caps = {c["capability_code"]: c["supported"] for c in resp.json()["data"]}
    assert caps == {"POWER_CONTROL": False}


async def test_commands_only_for_active_devices(client, admin_tokens):
    key = await get_enrollment_key(client, admin_tokens)
    reg = await register(client, key, "SN-PENDINGCMD")
    resp = await client.post(
        f"/api/v1/devices/{reg['device_id']}/commands",
        headers=bearer(admin_tokens),
        json={"command_type": "RESTART_PLAYER"},
    )
    assert resp.status_code == 422


async def test_groups_and_bulk_assign(client, admin_tokens):
    id_a, _ = await enroll_active_device(client, admin_tokens, "SN-G1")
    id_b, _ = await enroll_active_device(client, admin_tokens, "SN-G2")

    resp = await client.post(
        "/api/v1/device-groups",
        headers=bearer(admin_tokens),
        json={"name": "Premium Stores", "description": "High-traffic displays"},
    )
    assert resp.status_code == 201
    group_id = resp.json()["data"]["id"]

    resp = await client.post(
        "/api/v1/device-groups", headers=bearer(admin_tokens), json={"name": "Premium Stores"}
    )
    assert resp.status_code == 409

    resp = await client.post(
        f"/api/v1/device-groups/{group_id}/members",
        headers=bearer(admin_tokens),
        json={"device_ids": [id_a, id_b]},
    )
    assert resp.json()["data"]["assigned"] == 2

    resp = await client.get(
        f"/api/v1/devices?group_id={group_id}", headers=bearer(admin_tokens)
    )
    assert {d["id"] for d in resp.json()["data"]} == {id_a, id_b}

    # Group with members cannot be deleted.
    resp = await client.delete(
        f"/api/v1/device-groups/{group_id}", headers=bearer(admin_tokens)
    )
    assert resp.status_code == 422


async def test_assign_location_and_subtree_filter(client, admin_tokens):
    device_id, _ = await enroll_active_device(client, admin_tokens, "SN-LOC")

    resp = await client.get("/api/v1/locations?q=Kolkata", headers=bearer(admin_tokens))
    kolkata_id = resp.json()["data"][0]["id"]
    resp = await client.get("/api/v1/locations?q=Floor%201", headers=bearer(admin_tokens))
    floor_id = resp.json()["data"][0]["id"]

    resp = await client.post(
        f"/api/v1/devices/{device_id}/assign-location",
        headers=bearer(admin_tokens),
        json={"location_id": floor_id},
    )
    assert resp.status_code == 200

    # Subtree filter: device on Floor 1 appears under Kolkata with descendants.
    resp = await client.get(
        f"/api/v1/devices?location_id={kolkata_id}&include_descendants=true",
        headers=bearer(admin_tokens),
    )
    assert device_id in [d["id"] for d in resp.json()["data"]]

    resp = await client.get(
        f"/api/v1/devices?location_id={kolkata_id}&include_descendants=false",
        headers=bearer(admin_tokens),
    )
    assert device_id not in [d["id"] for d in resp.json()["data"]]


async def test_rbac_viewer_cannot_manage_devices(client, admin_tokens):
    from tests.conftest import login

    device_id, _ = await enroll_active_device(client, admin_tokens, "SN-RBAC")
    resp = await client.get("/api/v1/roles", headers=bearer(admin_tokens))
    viewer_id = next(r["id"] for r in resp.json()["data"] if r["name"] == "Viewer")
    await client.post(
        "/api/v1/users",
        headers=bearer(admin_tokens),
        json={
            "email": "dviewer@demo-org.com",
            "full_name": "Device Viewer",
            "password": "Viewer@12345",
            "role_ids": [viewer_id],
        },
    )
    viewer = await login(client, "dviewer@demo-org.com", "Viewer@12345")

    resp = await client.get("/api/v1/devices", headers=bearer(viewer))
    assert resp.status_code == 200
    resp = await client.post(
        f"/api/v1/devices/{device_id}/commands",
        headers=bearer(viewer),
        json={"command_type": "RESTART_PLAYER"},
    )
    assert resp.status_code == 403
    resp = await client.get("/api/v1/devices/enrollment-key", headers=bearer(viewer))
    assert resp.status_code == 403
