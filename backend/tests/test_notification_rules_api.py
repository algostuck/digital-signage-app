"""Notification rules engine tests (P2-NTF-001..003)."""

import datetime as dt

from sqlalchemy import update

from tests.conftest import bearer, login
from tests.test_device_ops_api import enroll_with
from tests.test_devices_api import device_headers
from tests.test_tenant_isolation import org_b  # noqa: F401 (fixture)


async def make_rule(client, tokens, **overrides) -> dict:
    body = {
        "name": "Storage alerts",
        "event_type": "DEVICE_STORAGE",
        "channels_json": [
            {"channel": "in_app"},
            {"channel": "email", "recipient": "noc@demo-org.com"},
        ],
    }
    body.update(overrides)
    resp = await client.post("/api/v1/notification-rules", headers=bearer(tokens), json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


async def trigger_storage_alert(client, admin_tokens, serial, used=95):
    """Fires a DEVICE_STORAGE notification via the real heartbeat path."""
    device_id, token = await enroll_with(client, admin_tokens, serial)
    await client.put(
        "/api/v1/monitoring/thresholds",
        headers=bearer(admin_tokens),
        json={"storage_alert_percent": 80},
    )
    resp = await client.post(
        f"/api/v1/player/{device_id}/heartbeat",
        headers=device_headers(token),
        json={"status": "online", "storage": {"used_percent": used}},
    )
    assert resp.status_code == 200, resp.text
    return device_id


async def test_rule_crud_and_validation(client, admin_tokens):
    rule = await make_rule(client, admin_tokens)
    assert rule["active"] is True

    # Duplicate name -> 409; unknown event/channel/recipient problems -> 400.
    resp = await client.post(
        "/api/v1/notification-rules",
        headers=bearer(admin_tokens),
        json={"name": "Storage alerts", "event_type": "DEVICE_STORAGE",
              "channels_json": [{"channel": "in_app"}]},
    )
    assert resp.status_code == 409
    for bad in [
        {"name": "x1", "event_type": "NOPE", "channels_json": [{"channel": "in_app"}]},
        {"name": "x2", "event_type": "DEVICE_OFFLINE",
         "channels_json": [{"channel": "email"}]},  # missing recipient
        {"name": "x3", "event_type": "DEVICE_OFFLINE",
         "channels_json": [{"channel": "webhook", "recipient": "ftp://nope"}]},
        {"name": "x4", "event_type": "DEVICE_OFFLINE",
         "channels_json": [{"channel": "in_app"}],
         "condition_json": {"severity": ["catastrophic"]}},
    ]:
        resp = await client.post(
            "/api/v1/notification-rules", headers=bearer(admin_tokens), json=bad
        )
        assert resp.status_code == 400, bad

    # Update + deactivate.
    resp = await client.patch(
        f"/api/v1/notification-rules/{rule['id']}",
        headers=bearer(admin_tokens),
        json={"active": False, "escalation_minutes": 30},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["active"] is False
    assert resp.json()["data"]["escalation_minutes"] == 30

    # Catalogue for the UI.
    resp = await client.get("/api/v1/notification-events", headers=bearer(admin_tokens))
    types = {row["event_type"] for row in resp.json()["data"]}
    assert {"DEVICE_OFFLINE", "ROLLOUT_STOPPED", "*"} <= types


async def test_rule_dispatch_in_app_and_email(client, admin_tokens):
    rule = await make_rule(client, admin_tokens, name="Storage watch")
    await trigger_storage_alert(client, admin_tokens, "SN-NR-DISPATCH")

    resp = await client.get(
        f"/api/v1/notification-deliveries?rule_id={rule['id']}&page_size=50",
        headers=bearer(admin_tokens),
    )
    assert resp.status_code == 200, resp.text
    deliveries = resp.json()["data"]
    by_channel = {d["channel"]: d for d in deliveries}
    assert by_channel["in_app"]["state"] == "delivered"
    assert by_channel["email"]["state"] == "delivered"
    assert by_channel["email"]["recipient"] == "noc@demo-org.com"
    assert by_channel["email"]["notification_type"] == "DEVICE_STORAGE"


async def test_condition_and_inactive_rules_filter(client, admin_tokens):
    critical_only = await make_rule(
        client,
        admin_tokens,
        name="Critical only",
        event_type="*",
        condition_json={"severity": ["critical"]},
    )
    inactive = await make_rule(client, admin_tokens, name="Sleeping", event_type="*")
    await client.patch(
        f"/api/v1/notification-rules/{inactive['id']}",
        headers=bearer(admin_tokens),
        json={"active": False},
    )
    # DEVICE_STORAGE fires as warning -> neither rule delivers.
    await trigger_storage_alert(client, admin_tokens, "SN-NR-COND")
    for rule_id in (critical_only["id"], inactive["id"]):
        resp = await client.get(
            f"/api/v1/notification-deliveries?rule_id={rule_id}",
            headers=bearer(admin_tokens),
        )
        assert resp.json()["data"] == []


async def test_wildcard_rule_matches_any_event(client, admin_tokens):
    rule = await make_rule(client, admin_tokens, name="Catch all", event_type="*")
    await trigger_storage_alert(client, admin_tokens, "SN-NR-WILD")
    resp = await client.get(
        f"/api/v1/notification-deliveries?rule_id={rule['id']}",
        headers=bearer(admin_tokens),
    )
    assert len(resp.json()["data"]) >= 1


async def test_webhook_delivery_never_sent_inline(client, admin_tokens):
    rule = await make_rule(
        client,
        admin_tokens,
        name="Webhook watch",
        channels_json=[{"channel": "webhook", "recipient": "https://hooks.example.com/x"}],
    )
    await trigger_storage_alert(client, admin_tokens, "SN-NR-HOOK")

    resp = await client.get(
        f"/api/v1/notification-deliveries?rule_id={rule['id']}",
        headers=bearer(admin_tokens),
    )
    delivery = resp.json()["data"][0]
    assert delivery["state"] == "pending"  # queued for the async sweep
    assert delivery["attempts"] == 0


async def test_webhook_sweep_and_escalation(client, admin_tokens, db_session, monkeypatch):
    from app.models import Notification
    from app.services import notification_rules as engine

    hook_rule = await make_rule(
        client,
        admin_tokens,
        name="Hook + escalate",
        channels_json=[{"channel": "webhook", "recipient": "https://hooks.example.com/y"},
                       {"channel": "in_app"}],
        escalation_minutes=15,
    )
    await trigger_storage_alert(client, admin_tokens, "SN-NR-SWEEP")

    # 1) Failing endpoint: attempts accumulate, then state=failed.
    async def boom(url, payload):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(engine, "_post_webhook", boom)
    for _ in range(engine.MAX_WEBHOOK_ATTEMPTS):
        await engine.process_pending_deliveries(db_session)
        await db_session.commit()
    resp = await client.get(
        f"/api/v1/notification-deliveries?rule_id={hook_rule['id']}",
        headers=bearer(admin_tokens),
    )
    hook = next(d for d in resp.json()["data"] if d["channel"] == "webhook")
    assert hook["state"] == "failed"
    assert hook["attempts"] == engine.MAX_WEBHOOK_ATTEMPTS
    assert "connection refused" in hook["last_error"]

    # 2) Escalation: backdate the unread notification past the delay.
    await db_session.execute(
        update(Notification)
        .where(Notification.type == "DEVICE_STORAGE")
        .values(created_at=dt.datetime.now(dt.UTC) - dt.timedelta(minutes=30))
    )
    await db_session.commit()
    escalated = await engine.process_escalations(db_session)
    await db_session.commit()
    assert escalated >= 1
    # Idempotent: a second sweep escalates nothing new.
    assert await engine.process_escalations(db_session) == 0

    resp = await client.get("/api/v1/notifications?page_size=100", headers=bearer(admin_tokens))
    escalations = [n for n in resp.json()["data"] if n["type"] == "ESCALATION"]
    assert escalations and escalations[0]["severity"] == "critical"
    assert escalations[0]["title"].startswith("ESCALATED:")


async def test_successful_webhook_sweep(client, admin_tokens, db_session, monkeypatch):
    from app.services import notification_rules as engine

    rule = await make_rule(
        client,
        admin_tokens,
        name="Hook ok",
        channels_json=[{"channel": "webhook", "recipient": "https://hooks.example.com/z"}],
    )
    await trigger_storage_alert(client, admin_tokens, "SN-NR-OK")

    calls: list[dict] = []

    async def ok(url, payload):
        calls.append({"url": url, "payload": payload})

    monkeypatch.setattr(engine, "_post_webhook", ok)
    result = await engine.process_pending_deliveries(db_session)
    await db_session.commit()
    assert result["delivered"] == 1
    assert calls[0]["url"] == "https://hooks.example.com/z"
    assert calls[0]["payload"]["type"] == "DEVICE_STORAGE"

    resp = await client.get(
        f"/api/v1/notification-deliveries?rule_id={rule['id']}",
        headers=bearer(admin_tokens),
    )
    assert resp.json()["data"][0]["state"] == "delivered"


async def test_rules_rbac_and_isolation(client, admin_tokens, org_b):  # noqa: F811
    rule = await make_rule(client, admin_tokens, name="Iso rule")

    resp = await client.get("/api/v1/roles", headers=bearer(admin_tokens))
    viewer_id = next(r["id"] for r in resp.json()["data"] if r["name"] == "Viewer")
    await client.post(
        "/api/v1/users",
        headers=bearer(admin_tokens),
        json={
            "email": "nr-viewer@demo-org.com",
            "full_name": "NR Viewer",
            "password": "Viewer@12345",
            "role_ids": [viewer_id],
        },
    )
    viewer = await login(client, "nr-viewer@demo-org.com", "Viewer@12345")
    assert (
        await client.get("/api/v1/notification-rules", headers=bearer(viewer))
    ).status_code == 200
    resp = await client.post(
        "/api/v1/notification-rules",
        headers=bearer(viewer),
        json={"name": "nope", "event_type": "*", "channels_json": [{"channel": "in_app"}]},
    )
    assert resp.status_code == 403

    b_tokens = await login(client, "admin@org-b-corp.com", "BAdmin@12345")
    resp = await client.get("/api/v1/notification-rules", headers=bearer(b_tokens))
    assert resp.json()["data"] == []
    resp = await client.delete(
        f"/api/v1/notification-rules/{rule['id']}", headers=bearer(b_tokens)
    )
    assert resp.status_code == 404
