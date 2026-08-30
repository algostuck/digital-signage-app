"""Phase-3 slice 3C-2: edge bundles — build from live manifests, signed
descriptors, rollout coverage, player download + Range resumability."""

import hashlib
import hmac
import json

from tests.conftest import bearer, login
from tests.test_devices_api import enroll_active_device
from tests.test_publishing_api import publish, ready_campaign
from tests.test_tenant_isolation import org_b  # noqa: F401 (fixture)


async def test_bundle_signature_verifies(client, admin_tokens, db_session):
    """The stored signature is an HMAC over the canonical manifest."""
    device_id, _ = await enroll_active_device(client, admin_tokens, "SN-EDGE-SIG")
    campaign = await ready_campaign(
        client, admin_tokens, device_ids=[device_id], name="Sig Campaign"
    )
    await publish(client, admin_tokens, campaign["id"])
    bundle = (
        await client.post(
            "/api/v1/edge/bundles", headers=bearer(admin_tokens), json={"name": "Sig pack"}
        )
    ).json()["data"]

    import uuid as uuid_mod

    from sqlalchemy import select

    from app.core.config import get_settings
    from app.models import EdgeBundle

    row = (
        await db_session.execute(
            select(EdgeBundle).where(EdgeBundle.id == uuid_mod.UUID(bundle["id"]))
        )
    ).scalar_one()
    body = json.dumps(row.manifest_json, sort_keys=True, separators=(",", ":")).encode()
    expected = hmac.new(
        get_settings().jwt_secret.encode(), body, hashlib.sha256
    ).hexdigest()
    assert row.signature == expected


async def test_bundle_lifecycle_and_player_download(client, admin_tokens):
    device_id, token = await enroll_active_device(client, admin_tokens, "SN-EDGE-1")
    campaign = await ready_campaign(
        client, admin_tokens, device_ids=[device_id], name="Edge Campaign"
    )
    await publish(client, admin_tokens, campaign["id"])

    resp = await client.post(
        "/api/v1/edge/bundles",
        headers=bearer(admin_tokens),
        json={"name": "Store pack", "ttl_days": 3},
    )
    assert resp.status_code == 201, resp.text
    bundle = resp.json()["data"]
    assert bundle["state"] == "draft"
    assert bundle["assets"] >= 1  # the campaign's playlist asset
    assert bundle["devices"] >= 1

    # Draft bundles are invisible to players.
    resp = await client.get(
        f"/api/v1/player/{device_id}/manifest", headers={"X-Device-Token": token}
    )
    assert "bundle" not in resp.json()["data"]

    resp = await client.post(
        f"/api/v1/edge/bundles/{bundle['id']}/publish", headers=bearer(admin_tokens)
    )
    assert resp.json()["data"]["state"] == "published"

    # Manifest now carries bundle + prefetch + bandwidth blocks.
    resp = await client.get(
        f"/api/v1/player/{device_id}/manifest", headers={"X-Device-Token": token}
    )
    manifest = resp.json()["data"]
    assert manifest["bundle"]["id"] == bundle["id"]
    assert manifest["bundle"]["signature"] == bundle["signature"]
    assert manifest["prefetch"] and manifest["prefetch"][0]["sha256"]
    assert manifest["bandwidth"]["concurrency"] == 2

    resp = await client.get(
        f"/api/v1/player/{device_id}/bundles/{bundle['id']}",
        headers={"X-Device-Token": token},
    )
    assert resp.status_code == 200, resp.text
    served = resp.json()["data"]
    assert served["assets"][0]["url"]
    assert served["signature"] == bundle["signature"]

    # Download marked the device synced.
    resp = await client.get("/api/v1/edge/bundles", headers=bearer(admin_tokens))
    assert resp.json()["data"][0]["synced"] == 1

    resp = await client.get("/api/v1/edge/metrics", headers=bearer(admin_tokens))
    metrics = resp.json()["data"]
    assert metrics["bundles_by_state"]["published"] == 1
    assert metrics["published_coverage"]["synced"] == 1


async def test_range_resumable_asset_download(client, admin_tokens):
    device_id, token = await enroll_active_device(client, admin_tokens, "SN-EDGE-RANGE")
    campaign = await ready_campaign(
        client, admin_tokens, device_ids=[device_id], name="Range Campaign"
    )
    await publish(client, admin_tokens, campaign["id"])
    resp = await client.get(
        f"/api/v1/player/{device_id}/manifest", headers={"X-Device-Token": token}
    )
    asset = resp.json()["data"]["assets"][0]
    url = asset["url"]

    full = await client.get(url)
    assert full.status_code == 200
    assert full.headers["accept-ranges"] == "bytes"
    size = len(full.content)

    part = await client.get(url, headers={"Range": "bytes=0-9"})
    assert part.status_code == 206
    assert part.content == full.content[:10]
    assert part.headers["content-range"] == f"bytes 0-9/{size}"

    tail = await client.get(url, headers={"Range": f"bytes={size - 5}-"})
    assert tail.status_code == 206
    assert tail.content == full.content[-5:]

    bad = await client.get(url, headers={"Range": f"bytes={size + 10}-"})
    assert bad.status_code == 416


async def test_publish_supersedes_and_entitlement(client, admin_tokens, org_b):  # noqa: F811
    device_id, _ = await enroll_active_device(client, admin_tokens, "SN-EDGE-SUP")
    campaign = await ready_campaign(
        client, admin_tokens, device_ids=[device_id], name="Supersede Campaign"
    )
    await publish(client, admin_tokens, campaign["id"])

    first = (
        await client.post(
            "/api/v1/edge/bundles", headers=bearer(admin_tokens),
            json={"name": "Pack v1"},
        )
    ).json()["data"]
    await client.post(
        f"/api/v1/edge/bundles/{first['id']}/publish", headers=bearer(admin_tokens)
    )
    second = (
        await client.post(
            "/api/v1/edge/bundles", headers=bearer(admin_tokens),
            json={"name": "Pack v2"},
        )
    ).json()["data"]
    await client.post(
        f"/api/v1/edge/bundles/{second['id']}/publish", headers=bearer(admin_tokens)
    )

    rows = (
        await client.get("/api/v1/edge/bundles", headers=bearer(admin_tokens))
    ).json()["data"]
    states = {row["name"]: row["state"] for row in rows}
    assert states["Pack v1"] == "expired"  # superseded by same-scope publish
    assert states["Pack v2"] == "published"

    # Business plan has edge_bundles=False.
    b_tokens = await login(client, "admin@org-b-corp.com", "BAdmin@12345")
    resp = await client.post(
        "/api/v1/billing/subscribe", headers=bearer(b_tokens), json={"plan_code": "business"}
    )
    assert resp.status_code == 200
    resp = await client.post(
        "/api/v1/edge/bundles", headers=bearer(b_tokens), json={"name": "Nope"}
    )
    assert resp.status_code == 422
    assert "edge_bundles" in resp.text
