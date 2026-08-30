"""OTA player update tests (P2-DEV-004/005, SRS §8 acceptance #2)."""

from tests.conftest import bearer, login
from tests.test_content_api import upload_asset
from tests.test_device_ops_api import enroll_with
from tests.test_devices_api import device_headers
from tests.test_tenant_isolation import org_b  # noqa: F401 (fixture)


async def make_release(client, tokens, version="2.5.0") -> dict:
    package = await upload_asset(
        client,
        tokens,
        filename=f"player-{version}.zip",
        mime="application/zip",
        data=b"PK\x03\x04 fake player package " + version.encode(),
        name=f"Player {version}",
    )
    resp = await client.post(
        "/api/v1/player-releases",
        headers=bearer(tokens),
        json={"version": version, "package_asset_id": package["id"], "notes": "test build"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


async def enroll_fleet(
    client, admin_tokens, count, prefix="SN-OTA"
) -> tuple[list[tuple[str, str]], str]:
    """Enrolls N devices and wraps them in a static group so rollouts are
    isolated from the seeded demo devices. Returns (fleet, group_id)."""
    fleet = [
        await enroll_with(
            client, admin_tokens, f"{prefix}-{i:02d}", manufacturer="Acme", platform="tizen"
        )
        for i in range(count)
    ]
    resp = await client.post(
        "/api/v1/device-groups",
        headers=bearer(admin_tokens),
        json={"name": f"{prefix} Fleet"},
    )
    assert resp.status_code == 201, resp.text
    group_id = resp.json()["data"]["id"]
    resp = await client.post(
        f"/api/v1/device-groups/{group_id}/members",
        headers=bearer(admin_tokens),
        json={"device_ids": [d for d, _ in fleet]},
    )
    assert resp.status_code == 200, resp.text
    return fleet, group_id


async def ack_update(client, device_id, token, release_id, *, status, error=None):
    resp = await client.post(
        f"/api/v1/player/{device_id}/releases/{release_id}/ack",
        headers=device_headers(token),
        json={"status": status, "error": error},
    )
    return resp


async def heartbeat_update(client, device_id, token):
    resp = await client.post(
        f"/api/v1/player/{device_id}/heartbeat",
        headers=device_headers(token),
        json={"status": "online"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["update"]


async def test_release_creation_and_validation(client, admin_tokens):
    release = await make_release(client, admin_tokens, version="1.0.0")
    assert release["state"] == "draft"
    assert release["checksum"]
    assert release["size_bytes"] > 0

    # Duplicate version -> conflict.
    resp = await client.post(
        "/api/v1/player-releases",
        headers=bearer(admin_tokens),
        json={"version": "1.0.0", "package_asset_id": release["package_asset_id"]},
    )
    assert resp.status_code == 409

    # Unknown package asset -> 404.
    resp = await client.post(
        "/api/v1/player-releases",
        headers=bearer(admin_tokens),
        json={"version": "1.0.1", "package_asset_id": "00000000-0000-0000-0000-000000000001"},
    )
    assert resp.status_code == 404


async def test_staged_rollout_progression(client, admin_tokens):
    """Rings 50 -> 100: offer only reaches ring-1 devices until the ring
    completes, then ring 2 activates and the release finishes."""
    fleet, group_id = await enroll_fleet(client, admin_tokens, 4, prefix="SN-RING")
    release = await make_release(client, admin_tokens, version="2.0.0")

    resp = await client.post(
        f"/api/v1/player-releases/{release['id']}/rollouts",
        headers=bearer(admin_tokens),
        json={"group_id": group_id, "rings": [50, 100], "failure_threshold_pct": 0},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["state"] == "active"
    rings = data["rollout"]
    assert [r["state"] for r in rings] == ["in_progress", "pending"]
    assert rings[0]["devices"]["total"] == 2 and rings[1]["devices"]["total"] == 2

    # Only ring-1 devices are offered the update on heartbeat.
    offers = {}
    for device_id, token in fleet:
        offers[device_id] = await heartbeat_update(client, device_id, token)
    offered = [d for d, o in offers.items() if o]
    assert len(offered) == 2
    sample = offers[offered[0]]
    assert sample["version"] == "2.0.0" and sample["url"] and sample["sha256"]

    # A device outside the in-progress ring cannot ack this release.
    outside = next(d for d, _ in fleet if offers[d] is None)
    outside_token = next(t for d, t in fleet if d == outside)
    resp = await ack_update(
        client, outside, outside_token, release["id"], status="succeeded"
    )
    assert resp.status_code == 404

    # Ring 1 succeeds -> ring 2 activates and its devices get the offer.
    for device_id, token in fleet:
        if offers[device_id]:
            resp = await ack_update(
                client, device_id, token, release["id"], status="succeeded"
            )
            assert resp.status_code == 200, resp.text
    resp = await client.get(
        f"/api/v1/player-releases/{release['id']}", headers=bearer(admin_tokens)
    )
    rings = resp.json()["data"]["rollout"]
    assert [r["state"] for r in rings] == ["completed", "in_progress"]
    assert await heartbeat_update(client, outside, outside_token)

    # Ring 2 succeeds -> everything completed; success bumps player_version.
    for device_id, token in fleet:
        if not offers[device_id]:
            await ack_update(client, device_id, token, release["id"], status="succeeded")
    resp = await client.get(
        f"/api/v1/player-releases/{release['id']}", headers=bearer(admin_tokens)
    )
    rings = resp.json()["data"]["rollout"]
    assert [r["state"] for r in rings] == ["completed", "completed"]
    resp = await client.get(f"/api/v1/devices/{fleet[0][0]}", headers=bearer(admin_tokens))
    assert resp.json()["data"]["player_version"] == "2.0.0"
    # No further offer once succeeded.
    assert await heartbeat_update(client, fleet[0][0], fleet[0][1]) is None


async def test_pilot_failure_stops_rollout(client, admin_tokens):
    """SRS §8 acceptance #2: pilot ring, one forced failure above the
    threshold -> rollout stops, later rings halt, evidence exposed."""
    fleet, group_id = await enroll_fleet(client, admin_tokens, 10, prefix="SN-PILOT")
    release = await make_release(client, admin_tokens, version="3.0.0")

    resp = await client.post(
        f"/api/v1/player-releases/{release['id']}/rollouts",
        headers=bearer(admin_tokens),
        json={"group_id": group_id, "rings": [100], "failure_threshold_pct": 5},
    )
    assert resp.status_code == 200
    # Single 10-device pilot ring: force one failure (10% > 5% threshold).
    failed_device, failed_token = fleet[0]
    resp = await ack_update(
        client,
        failed_device,
        failed_token,
        release["id"],
        status="failed",
        error="signature mismatch",
    )
    assert resp.status_code == 200
    for device_id, token in fleet[1:]:
        await ack_update(client, device_id, token, release["id"], status="succeeded")

    resp = await client.get(
        f"/api/v1/player-releases/{release['id']}", headers=bearer(admin_tokens)
    )
    ring = resp.json()["data"]["rollout"][0]
    assert ring["state"] == "stopped"
    assert ring["devices"]["failed"] == 1 and ring["devices"]["succeeded"] == 9

    # Evidence: per-device failure reason via the ring drilldown.
    resp = await client.get(f"/api/v1/rollouts/{ring['id']}", headers=bearer(admin_tokens))
    rows = resp.json()["data"]
    failed_rows = [r for r in rows if r["state"] == "failed"]
    assert failed_rows[0]["failure_reason"] == "signature mismatch"
    assert failed_rows[0]["device_id"] == failed_device

    # Evidence: critical notification.
    resp = await client.get("/api/v1/notifications", headers=bearer(admin_tokens))
    assert any(n["type"] == "ROLLOUT_STOPPED" for n in resp.json()["data"])

    # No new offers from a stopped rollout.
    assert await heartbeat_update(client, failed_device, failed_token) is None


async def test_multi_ring_stop_halts_later_rings(client, admin_tokens):
    fleet, group_id = await enroll_fleet(client, admin_tokens, 4, prefix="SN-HALT")
    release = await make_release(client, admin_tokens, version="3.1.0")
    await client.post(
        f"/api/v1/player-releases/{release['id']}/rollouts",
        headers=bearer(admin_tokens),
        json={"group_id": group_id, "rings": [50, 100], "failure_threshold_pct": 0},
    )
    for device_id, token in fleet:
        if await heartbeat_update(client, device_id, token):
            await ack_update(
                client, device_id, token, release["id"], status="failed", error="boom"
            )
    resp = await client.get(
        f"/api/v1/player-releases/{release['id']}", headers=bearer(admin_tokens)
    )
    rings = resp.json()["data"]["rollout"]
    assert [r["state"] for r in rings] == ["stopped", "stopped"]


async def test_rollout_to_group_and_ring_math(client, admin_tokens):
    """Rollout scoped to a static group; ring percentages split the fleet."""
    fleet, _ = await enroll_fleet(client, admin_tokens, 5, prefix="SN-GRP")
    resp = await client.post(
        "/api/v1/device-groups", headers=bearer(admin_tokens), json={"name": "OTA Group"}
    )
    group = resp.json()["data"]
    member_ids = [d for d, _ in fleet[:3]]
    await client.post(
        f"/api/v1/device-groups/{group['id']}/members",
        headers=bearer(admin_tokens),
        json={"device_ids": member_ids},
    )
    release = await make_release(client, admin_tokens, version="4.0.0")
    resp = await client.post(
        f"/api/v1/player-releases/{release['id']}/rollouts",
        headers=bearer(admin_tokens),
        json={"group_id": group["id"], "rings": [34, 100], "failure_threshold_pct": 0},
    )
    assert resp.status_code == 200, resp.text
    rings = resp.json()["data"]["rollout"]
    # ceil(3 * 34%) = 2 devices in ring 1, remaining 1 in ring 2.
    assert rings[0]["devices"]["total"] == 2 and rings[1]["devices"]["total"] == 1
    total = rings[0]["devices"]["total"] + rings[1]["devices"]["total"]
    assert total == len(member_ids)  # non-members excluded


async def test_rollout_validation(client, admin_tokens):
    _, group_id = await enroll_fleet(client, admin_tokens, 1, prefix="SN-VAL")
    release = await make_release(client, admin_tokens, version="5.0.0")

    async def start(body):
        return await client.post(
            f"/api/v1/player-releases/{release['id']}/rollouts",
            headers=bearer(admin_tokens),
            json={"group_id": group_id, **body},
        )

    assert (await start({"rings": [50]})).status_code == 400  # last ring must be 100
    assert (await start({"rings": [50, 40, 100]})).status_code == 400  # not increasing
    assert (await start({"rings": [], "failure_threshold_pct": 0})).status_code == 400

    resp = await start({"rings": [100]})
    assert resp.status_code == 200
    # A second rollout for the same release is rejected.
    assert (await start({"rings": [100]})).status_code == 422


async def test_rollback_withdraws_offer(client, admin_tokens):
    fleet, group_id = await enroll_fleet(client, admin_tokens, 2, prefix="SN-RB")
    release = await make_release(client, admin_tokens, version="6.0.0")
    await client.post(
        f"/api/v1/player-releases/{release['id']}/rollouts",
        headers=bearer(admin_tokens),
        json={"group_id": group_id, "rings": [100], "failure_threshold_pct": 0},
    )
    device_id, token = fleet[0]
    assert await heartbeat_update(client, device_id, token)

    resp = await client.post(
        f"/api/v1/player-releases/{release['id']}/rollback", headers=bearer(admin_tokens)
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["state"] == "rolled_back"
    assert all(r["state"] == "stopped" for r in data["rollout"])
    assert await heartbeat_update(client, device_id, token) is None
    # A rolled-back release cannot be rolled out again.
    resp = await client.post(
        f"/api/v1/player-releases/{release['id']}/rollouts",
        headers=bearer(admin_tokens),
        json={"rings": [100]},
    )
    assert resp.status_code == 422


async def test_release_permissions_and_isolation(client, admin_tokens, org_b):  # noqa: F811
    release = await make_release(client, admin_tokens, version="7.0.0")

    # Viewer (no releases.manage) is forbidden.
    resp = await client.get("/api/v1/roles", headers=bearer(admin_tokens))
    viewer_id = next(r["id"] for r in resp.json()["data"] if r["name"] == "Viewer")
    await client.post(
        "/api/v1/users",
        headers=bearer(admin_tokens),
        json={
            "email": "ota-viewer@demo-org.com",
            "full_name": "OTA Viewer",
            "password": "Viewer@12345",
            "role_ids": [viewer_id],
        },
    )
    viewer_tokens = await login(client, "ota-viewer@demo-org.com", "Viewer@12345")
    resp = await client.get("/api/v1/player-releases", headers=bearer(viewer_tokens))
    assert resp.status_code == 403

    # Cross-tenant: org B cannot see or act on org A's release.
    b_tokens = await login(client, "admin@org-b-corp.com", "BAdmin@12345")
    resp = await client.get(
        f"/api/v1/player-releases/{release['id']}", headers=bearer(b_tokens)
    )
    assert resp.status_code == 404
    resp = await client.post(
        f"/api/v1/player-releases/{release['id']}/rollback", headers=bearer(b_tokens)
    )
    assert resp.status_code == 404
