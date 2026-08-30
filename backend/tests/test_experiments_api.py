"""Phase-3 slice 3B-3: experimentation — allocation validation, stable
per-device assignment, manifest arm override, results, entitlement gate."""

from tests.conftest import bearer, login
from tests.test_devices_api import enroll_active_device
from tests.test_publishing_api import make_published_playlist, publish, ready_campaign
from tests.test_tenant_isolation import org_b  # noqa: F401 (fixture)


async def campaign_with_variant(client, tokens, *, device_ids, name="Exp Campaign"):
    campaign = await ready_campaign(client, tokens, device_ids=device_ids, name=name)
    variant_playlist = await make_published_playlist(client, tokens, name=f"{name} B PL")
    # 2E variants need audience targets; the experiment path overrides that
    # resolution, so the target here is inert for assigned arms.
    resp = await client.post(
        f"/api/v1/campaigns/{campaign['id']}/variants",
        headers=bearer(tokens),
        json={"name": "Variant B", "playlist_id": variant_playlist["id"],
              "priority": 50,
              "targets": [{"target_type": "device", "target_id": device_ids[0]}]},
    )
    assert resp.status_code == 201, resp.text
    variant = next(
        v for v in resp.json()["data"]["variants"] if v["name"] == "Variant B"
    )
    return campaign, variant


async def test_allocation_validation_and_lifecycle(client, admin_tokens):
    device_id, _ = await enroll_active_device(client, admin_tokens, "SN-EXP-VAL")
    campaign, variant = await campaign_with_variant(
        client, admin_tokens, device_ids=[device_id], name="Exp Val"
    )

    # Over-allocation and foreign variants are refused.
    resp = await client.post(
        "/api/v1/experiments",
        headers=bearer(admin_tokens),
        json={"campaign_id": campaign["id"], "name": "Bad",
              "arms": [{"variant_id": variant["id"], "allocation_pct": 100},
                       {"variant_id": variant["id"], "allocation_pct": 10}]},
    )
    assert resp.status_code == 400

    resp = await client.post(
        "/api/v1/experiments",
        headers=bearer(admin_tokens),
        json={"campaign_id": campaign["id"], "name": "Exp Val Run",
              "arms": [{"variant_id": variant["id"], "allocation_pct": 50}]},
    )
    assert resp.status_code == 201, resp.text
    experiment = resp.json()["data"]
    assert experiment["control_pct"] == 50
    assert experiment["status"] == "draft"

    # Lifecycle: start → only one running per campaign → stop.
    resp = await client.post(
        f"/api/v1/experiments/{experiment['id']}/transition",
        headers=bearer(admin_tokens),
        json={"action": "start"},
    )
    assert resp.json()["data"]["status"] == "running"
    resp = await client.post(
        "/api/v1/experiments",
        headers=bearer(admin_tokens),
        json={"campaign_id": campaign["id"], "name": "Second",
              "arms": [{"variant_id": variant["id"], "allocation_pct": 10}]},
    )
    second = resp.json()["data"]
    resp = await client.post(
        f"/api/v1/experiments/{second['id']}/transition",
        headers=bearer(admin_tokens),
        json={"action": "start"},
    )
    assert resp.status_code == 422
    assert "already has a running experiment" in resp.text
    resp = await client.post(
        f"/api/v1/experiments/{experiment['id']}/transition",
        headers=bearer(admin_tokens),
        json={"action": "stop"},
    )
    assert resp.json()["data"]["status"] == "completed"


async def test_stable_assignment_and_manifest_override(client, admin_tokens):
    devices = []
    for i in range(6):
        device_id, token = await enroll_active_device(
            client, admin_tokens, f"SN-EXP-{i}"
        )
        devices.append((device_id, token))
    campaign, variant = await campaign_with_variant(
        client, admin_tokens, device_ids=[d[0] for d in devices], name="Exp Stable"
    )
    await publish(client, admin_tokens, campaign["id"])

    resp = await client.post(
        "/api/v1/experiments",
        headers=bearer(admin_tokens),
        json={"campaign_id": campaign["id"], "name": "Stable Exp",
              "arms": [{"variant_id": variant["id"], "allocation_pct": 50}]},
    )
    experiment = resp.json()["data"]
    await client.post(
        f"/api/v1/experiments/{experiment['id']}/transition",
        headers=bearer(admin_tokens),
        json={"action": "start"},
    )

    async def manifest_arm(device_id, token):
        resp = await client.get(
            f"/api/v1/player/{device_id}/manifest", headers={"X-Device-Token": token}
        )
        data = resp.json()["data"]
        assert data["experiment"]["id"] == experiment["id"]
        return data["experiment"]["arm"], data.get("variant")

    arms_first = [await manifest_arm(d, t) for d, t in devices]
    arms_second = [await manifest_arm(d, t) for d, t in devices]
    assert arms_first == arms_second  # stable across rebuilds
    labels = {arm for arm, _ in arms_first}
    assert labels <= {"control", "Variant B"}
    # Variant-arm devices actually get the variant creative in the manifest.
    for arm, variant_block in arms_first:
        if arm == "Variant B":
            assert variant_block and variant_block["name"] == "Variant B"
        else:
            assert variant_block is None

    # Results report both arms with device counts summing to the fleet.
    resp = await client.get(
        f"/api/v1/experiments/{experiment['id']}/results", headers=bearer(admin_tokens)
    )
    results = resp.json()["data"]
    assert sum(arm["devices"] for arm in results["arms"]) == len(devices)

    # Stopping restores normal resolution (no experiment block).
    await client.post(
        f"/api/v1/experiments/{experiment['id']}/transition",
        headers=bearer(admin_tokens),
        json={"action": "stop"},
    )
    resp = await client.get(
        f"/api/v1/player/{devices[0][0]}/manifest",
        headers={"X-Device-Token": devices[0][1]},
    )
    assert "experiment" not in resp.json()["data"]


async def test_experiments_entitlement_gate(client, org_b):  # noqa: F811
    b_tokens = await login(client, "admin@org-b-corp.com", "BAdmin@12345")
    resp = await client.post(
        "/api/v1/billing/subscribe", headers=bearer(b_tokens), json={"plan_code": "business"}
    )
    assert resp.status_code == 200  # Business: experiments=False
    resp = await client.post(
        "/api/v1/experiments",
        headers=bearer(b_tokens),
        json={"campaign_id": "00000000-0000-0000-0000-000000000000", "name": "Nope",
              "arms": [{"variant_id": "00000000-0000-0000-0000-000000000000",
                        "allocation_pct": 10}]},
    )
    assert resp.status_code == 422
    assert "experiments" in resp.text
