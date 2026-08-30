"""Phase-3 slice 3D-3: fleet intelligence — deterministic detection with
evidence, self-healing resolution, ack + whitelisted remediation."""


from tests.conftest import bearer, login
from tests.test_devices_api import device_headers, enroll_active_device
from tests.test_publishing_api import publish, ready_campaign
from tests.test_reports_phase2_api import send_playback
from tests.test_tenant_isolation import org_b  # noqa: F401 (fixture)


async def make_rule(client, tokens, *, name, signal_type, threshold=None, window=24):
    resp = await client.post(
        "/api/v1/fleet-intelligence/rules",
        headers=bearer(tokens),
        json={"name": name, "signal_type": signal_type,
              "threshold": threshold, "window_hours": window},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


async def test_rule_validation(client, admin_tokens):
    resp = await client.post(
        "/api/v1/fleet-intelligence/rules",
        headers=bearer(admin_tokens),
        json={"name": "Bad", "signal_type": "vibes"},
    )
    assert resp.status_code == 400
    resp = await client.post(
        "/api/v1/fleet-intelligence/rules",
        headers=bearer(admin_tokens),
        json={"name": "Bad2", "signal_type": "error_events",
              "threshold": {"max_count": -1}},
    )
    assert resp.status_code == 400
    rule = await make_rule(
        client, admin_tokens, name="Errors", signal_type="error_events"
    )
    assert rule["threshold"]["max_count"] == 5  # default merged


async def test_detection_evidence_and_self_heal(client, admin_tokens, db_session):
    from app.services import anomaly as engine

    device_id, token = await enroll_active_device(client, admin_tokens, "SN-FLEET-1")
    campaign = await ready_campaign(
        client, admin_tokens, device_ids=[device_id], name="Fleet Campaign"
    )
    await publish(client, admin_tokens, campaign["id"])
    resp = await client.get(
        f"/api/v1/player/{device_id}/manifest", headers=device_headers(token)
    )
    asset_id = resp.json()["data"]["assets"][0]["id"]
    # 12 plays, 6 failed -> 50% failure rate.
    await send_playback(
        client, device_id, token, campaign["id"], asset_id,
        ["completed"] * 6 + ["failed"] * 6,
    )

    await make_rule(
        client, admin_tokens, name="Playback health",
        signal_type="playback_failures",
        threshold={"min_events": 10, "max_failure_pct": 20},
    )

    result = await engine.detect(db_session)
    await db_session.commit()
    assert result["opened"] >= 1

    resp = await client.get(
        "/api/v1/fleet-intelligence/anomalies?state=open", headers=bearer(admin_tokens)
    )
    anomalies = resp.json()["data"]
    mine = next(a for a in anomalies if a["device_id"] == device_id)
    assert mine["score"] == 2.5  # 50% / 20%
    assert mine["evidence"]["failed"] == 6
    assert mine["evidence"]["total"] == 12
    assert "cache" in mine["recommendation"] or "content" in mine["recommendation"]

    # Re-scan does not duplicate the open anomaly.
    again = await engine.detect(db_session)
    await db_session.commit()
    assert again["opened"] == 0

    # Signal clears (enough new successful plays) -> auto-resolve with trail.
    await send_playback(
        client, device_id, token, campaign["id"], asset_id, ["completed"] * 30
    )
    healed = await engine.detect(db_session)
    await db_session.commit()
    assert healed["resolved"] >= 1
    resp = await client.get(
        f"/api/v1/fleet-intelligence/anomalies/{mine['id']}/actions",
        headers=bearer(admin_tokens),
    )
    assert any(a["action"] == "auto_resolve" for a in resp.json()["data"])


async def test_ack_and_whitelisted_remediation(client, admin_tokens, db_session):
    from app.services import anomaly as engine

    device_id, token = await enroll_active_device(client, admin_tokens, "SN-FLEET-REM")
    campaign = await ready_campaign(
        client, admin_tokens, device_ids=[device_id], name="Fleet Rem"
    )
    await publish(client, admin_tokens, campaign["id"])
    resp = await client.get(
        f"/api/v1/player/{device_id}/manifest", headers=device_headers(token)
    )
    asset_id = resp.json()["data"]["assets"][0]["id"]
    await send_playback(
        client, device_id, token, campaign["id"], asset_id, ["failed"] * 12
    )
    await make_rule(
        client, admin_tokens, name="Rem health", signal_type="playback_failures",
        threshold={"min_events": 10, "max_failure_pct": 20},
    )
    await engine.detect(db_session)
    await db_session.commit()

    resp = await client.get(
        "/api/v1/fleet-intelligence/anomalies?state=open", headers=bearer(admin_tokens)
    )
    anomaly = next(
        a for a in resp.json()["data"] if a["device_id"] == device_id
    )

    resp = await client.post(
        f"/api/v1/fleet-intelligence/{anomaly['id']}/acknowledge",
        headers=bearer(admin_tokens),
    )
    assert resp.json()["data"]["state"] == "acknowledged"

    # Non-whitelisted action refused; whitelisted queues a real command.
    resp = await client.post(
        f"/api/v1/fleet-intelligence/{anomaly['id']}/remediation",
        headers=bearer(admin_tokens),
        json={"action": "rm_rf"},
    )
    assert resp.status_code == 400
    resp = await client.post(
        f"/api/v1/fleet-intelligence/{anomaly['id']}/remediation",
        headers=bearer(admin_tokens),
        json={"action": "restart"},
    )
    assert resp.status_code == 200, resp.text
    command_id = resp.json()["data"]["command_id"]

    # The device actually receives it through the standard command poll.
    resp = await client.get(
        f"/api/v1/player/{device_id}/commands", headers=device_headers(token)
    )
    commands = resp.json()["data"]
    assert any(c["id"] == command_id and c["command_type"] == "restart" for c in commands)


async def test_fleet_entitlement_and_isolation(client, admin_tokens, org_b):  # noqa: F811
    b_tokens = await login(client, "admin@org-b-corp.com", "BAdmin@12345")
    resp = await client.post(
        "/api/v1/billing/subscribe", headers=bearer(b_tokens), json={"plan_code": "business"}
    )
    assert resp.status_code == 200  # Business: fleet_ai=False
    resp = await client.post(
        "/api/v1/fleet-intelligence/rules",
        headers=bearer(b_tokens),
        json={"name": "Nope", "signal_type": "error_events"},
    )
    assert resp.status_code == 422
    assert "fleet_ai" in resp.text

    await make_rule(client, admin_tokens, name="Org A rule", signal_type="error_events")
    resp = await client.get("/api/v1/fleet-intelligence/rules", headers=bearer(b_tokens))
    assert resp.json()["data"] == []