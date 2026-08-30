"""Integrations tests (P2-INT-001..003, NFR2-05): signed webhooks with
retry/dead-letter, scoped API keys with the X-API-Key auth path."""

import datetime as dt
import hashlib
import hmac

from tests.conftest import bearer, login
from tests.test_device_ops_api import enroll_with
from tests.test_devices_api import device_headers
from tests.test_tenant_isolation import org_b  # noqa: F401 (fixture)


async def make_webhook(client, tokens, **overrides) -> dict:
    body = {
        "url": "https://hooks.example.com/signage",
        "description": "Ops feed",
        "event_types_json": ["DEVICE_STORAGE", "ROLLOUT_STOPPED"],
    }
    body.update(overrides)
    resp = await client.post("/api/v1/webhooks", headers=bearer(tokens), json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


async def fire_storage_event(client, admin_tokens, serial):
    device_id, token = await enroll_with(client, admin_tokens, serial)
    await client.put(
        "/api/v1/monitoring/thresholds",
        headers=bearer(admin_tokens),
        json={"storage_alert_percent": 80},
    )
    resp = await client.post(
        f"/api/v1/player/{device_id}/heartbeat",
        headers=device_headers(token),
        json={"status": "online", "storage": {"used_percent": 97}},
    )
    assert resp.status_code == 200, resp.text


async def test_webhook_crud_and_secret_handling(client, admin_tokens):
    webhook = await make_webhook(client, admin_tokens)
    assert webhook["secret"].startswith("whsec_")

    # The secret never appears again in list output.
    resp = await client.get("/api/v1/webhooks", headers=bearer(admin_tokens))
    listed = resp.json()["data"][0]
    assert "secret" not in listed

    # Rotation returns a NEW secret exactly once.
    resp = await client.post(
        f"/api/v1/webhooks/{webhook['id']}/rotate-secret", headers=bearer(admin_tokens)
    )
    rotated = resp.json()["data"]
    assert rotated["secret"].startswith("whsec_")
    assert rotated["secret"] != webhook["secret"]

    # Validation.
    for bad in [
        {"url": "ftp://nope", "event_types_json": ["*"]},
        {"url": "https://x.example.com", "event_types_json": []},
        {"url": "https://x.example.com", "event_types_json": ["NOT_A_THING"]},
    ]:
        resp = await client.post("/api/v1/webhooks", headers=bearer(admin_tokens), json=bad)
        assert resp.status_code == 400, bad

    # Update + audit never leaks the secret.
    resp = await client.patch(
        f"/api/v1/webhooks/{webhook['id']}",
        headers=bearer(admin_tokens),
        json={"event_types_json": ["*"], "active": False},
    )
    assert resp.json()["data"]["active"] is False
    resp = await client.get("/api/v1/audit-logs?page_size=50", headers=bearer(admin_tokens))
    assert "whsec_" not in resp.text


async def test_event_enqueue_respects_filter_and_active(client, admin_tokens):
    matching = await make_webhook(
        client, admin_tokens, url="https://hooks.example.com/a",
        event_types_json=["DEVICE_STORAGE"],
    )
    other = await make_webhook(
        client, admin_tokens, url="https://hooks.example.com/b",
        event_types_json=["ROLLOUT_STOPPED"],
    )
    inactive = await make_webhook(
        client, admin_tokens, url="https://hooks.example.com/c", event_types_json=["*"]
    )
    await client.patch(
        f"/api/v1/webhooks/{inactive['id']}", headers=bearer(admin_tokens),
        json={"active": False},
    )

    await fire_storage_event(client, admin_tokens, "SN-WH-FILTER")

    async def deliveries(webhook_id):
        resp = await client.get(
            f"/api/v1/webhooks/{webhook_id}/deliveries", headers=bearer(admin_tokens)
        )
        return resp.json()["data"]

    assert len(await deliveries(matching["id"])) == 1
    assert (await deliveries(matching["id"]))[0]["state"] == "pending"
    assert await deliveries(other["id"]) == []
    assert await deliveries(inactive["id"]) == []


async def test_signed_delivery_and_worker(client, admin_tokens, db_session, monkeypatch):
    from app.services import webhooks as engine

    webhook = await make_webhook(
        client, admin_tokens, url="https://hooks.example.com/signed",
        event_types_json=["DEVICE_STORAGE"],
    )
    await fire_storage_event(client, admin_tokens, "SN-WH-SIGN")

    seen: list[dict] = []

    async def capture(url, body, headers):
        seen.append({"url": url, "body": body, "headers": headers})
        return 200

    monkeypatch.setattr(engine, "_post", capture)
    result = await engine.process_deliveries(db_session)
    await db_session.commit()
    assert result["delivered"] == 1

    call = seen[0]
    assert call["url"] == "https://hooks.example.com/signed"
    # Signature verifies against the ONE-TIME secret from creation.
    expected = hmac.new(
        webhook["secret"].encode(), call["body"], hashlib.sha256
    ).hexdigest()
    assert call["headers"]["X-Webhook-Signature"] == expected
    assert call["headers"]["X-Webhook-Event"] == "DEVICE_STORAGE"
    assert call["headers"]["X-Webhook-Attempt"] == "1"

    resp = await client.get(
        f"/api/v1/webhooks/{webhook['id']}/deliveries", headers=bearer(admin_tokens)
    )
    row = resp.json()["data"][0]
    assert row["state"] == "delivered" and row["response_code"] == 200


async def test_retry_backoff_dead_letter_and_replay(
    client, admin_tokens, db_session, monkeypatch
):
    from sqlalchemy import update

    from app.models import WebhookDelivery
    from app.services import webhooks as engine

    webhook = await make_webhook(
        client, admin_tokens, url="https://hooks.example.com/dead",
        event_types_json=["DEVICE_STORAGE"],
    )
    await fire_storage_event(client, admin_tokens, "SN-WH-DEAD")

    async def failing(url, body, headers):
        return 503

    monkeypatch.setattr(engine, "_post", failing)
    for _attempt in range(engine.MAX_ATTEMPTS):
        # Bring the scheduled retry due, then sweep again.
        await db_session.execute(
            update(WebhookDelivery).values(
                next_attempt_at=dt.datetime.now(dt.UTC) - dt.timedelta(seconds=1)
            )
        )
        await db_session.commit()
        await engine.process_deliveries(db_session)
        await db_session.commit()

    resp = await client.get(
        f"/api/v1/webhooks/{webhook['id']}/deliveries", headers=bearer(admin_tokens)
    )
    row = resp.json()["data"][0]
    assert row["state"] == "dead"
    assert row["attempt_no"] == engine.MAX_ATTEMPTS
    assert row["response_code"] == 503
    assert row["next_attempt_at"] is None

    # Replay resets the dead letter; a healthy endpoint then delivers it.
    resp = await client.post(
        f"/api/v1/webhooks/deliveries/{row['id']}/replay", headers=bearer(admin_tokens)
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["state"] == "pending"

    async def ok(url, body, headers):
        return 200

    monkeypatch.setattr(engine, "_post", ok)
    result = await engine.process_deliveries(db_session)
    await db_session.commit()
    assert result["delivered"] == 1


async def test_api_key_lifecycle_and_auth_path(client, admin_tokens):
    resp = await client.post(
        "/api/v1/api-keys",
        headers=bearer(admin_tokens),
        json={"name": "Reporting bot", "scopes": ["devices.view", "monitoring.view"]},
    )
    assert resp.status_code == 201, resp.text
    created = resp.json()["data"]
    raw = created["key"]
    assert raw.startswith("dsk_")
    assert created["prefix"] == raw[:12]

    # Raw key is never listed again (NFR2-05).
    resp = await client.get("/api/v1/api-keys", headers=bearer(admin_tokens))
    listed = resp.json()["data"][0]
    assert "key" not in listed and "key_hash" not in listed

    # The key authenticates within its scopes...
    resp = await client.get("/api/v1/devices", headers={"X-API-Key": raw})
    assert resp.status_code == 200, resp.text
    # ...and is rejected outside them.
    resp = await client.get("/api/v1/campaigns", headers={"X-API-Key": raw})
    assert resp.status_code == 403
    resp = await client.post(
        "/api/v1/device-groups", headers={"X-API-Key": raw}, json={"name": "nope"}
    )
    assert resp.status_code == 403

    # Usage is tracked.
    resp = await client.get("/api/v1/api-keys", headers=bearer(admin_tokens))
    assert resp.json()["data"][0]["last_used_at"] is not None

    # Revocation blocks immediately.
    resp = await client.delete(
        f"/api/v1/api-keys/{created['id']}", headers=bearer(admin_tokens)
    )
    assert resp.json()["data"]["revoked_at"] is not None
    resp = await client.get("/api/v1/devices", headers={"X-API-Key": raw})
    assert resp.status_code == 401


async def test_api_key_validation_and_expiry(client, admin_tokens):
    for bad in [
        {"name": "x", "scopes": ["not.a.permission"]},
        {"name": "y", "scopes": []},
        {"name": "z", "scopes": ["devices.view"],
         "expires_at": "2020-01-01T00:00:00Z"},
    ]:
        resp = await client.post("/api/v1/api-keys", headers=bearer(admin_tokens), json=bad)
        assert resp.status_code == 400, bad

    future = (dt.datetime.now(dt.UTC) + dt.timedelta(seconds=1)).isoformat()
    resp = await client.post(
        "/api/v1/api-keys",
        headers=bearer(admin_tokens),
        json={"name": "Short lived", "scopes": ["devices.view"], "expires_at": future},
    )
    raw = resp.json()["data"]["key"]
    import asyncio

    await asyncio.sleep(1.2)
    resp = await client.get("/api/v1/devices", headers={"X-API-Key": raw})
    assert resp.status_code == 401  # expired

    resp = await client.get("/api/v1/devices", headers={"X-API-Key": "dsk_definitely-wrong"})
    assert resp.status_code == 401


async def test_integrations_rbac_and_isolation(client, admin_tokens, org_b):  # noqa: F811
    webhook = await make_webhook(client, admin_tokens, url="https://hooks.example.com/iso")
    resp = await client.post(
        "/api/v1/api-keys",
        headers=bearer(admin_tokens),
        json={"name": "Iso key", "scopes": ["devices.view"]},
    )
    key = resp.json()["data"]

    # Viewer lacks both manage permissions.
    resp = await client.get("/api/v1/roles", headers=bearer(admin_tokens))
    viewer_id = next(r["id"] for r in resp.json()["data"] if r["name"] == "Viewer")
    await client.post(
        "/api/v1/users",
        headers=bearer(admin_tokens),
        json={
            "email": "int-viewer@demo-org.com",
            "full_name": "Int Viewer",
            "password": "Viewer@12345",
            "role_ids": [viewer_id],
        },
    )
    viewer = await login(client, "int-viewer@demo-org.com", "Viewer@12345")
    assert (
        await client.get("/api/v1/webhooks", headers=bearer(viewer))
    ).status_code == 403
    assert (
        await client.get("/api/v1/api-keys", headers=bearer(viewer))
    ).status_code == 403

    # Cross-tenant 404s; org B's key list is empty.
    b_tokens = await login(client, "admin@org-b-corp.com", "BAdmin@12345")
    resp = await client.post(
        f"/api/v1/webhooks/{webhook['id']}/rotate-secret", headers=bearer(b_tokens)
    )
    assert resp.status_code == 404
    resp = await client.delete(f"/api/v1/api-keys/{key['id']}", headers=bearer(b_tokens))
    assert resp.status_code == 404
    resp = await client.get("/api/v1/api-keys", headers=bearer(b_tokens))
    assert resp.json()["data"] == []

    # An org-A key never reads org-B data: tenant comes from the key itself.
    resp = await client.get("/api/v1/devices", headers={"X-API-Key": key.get("key", "")})
    if key.get("key"):
        assert resp.status_code == 200
        serials = {d["serial_no"] for d in resp.json()["data"]}
        assert all(not s.startswith("ORG-B") for s in serials)
