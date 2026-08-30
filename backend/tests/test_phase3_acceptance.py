"""Phase-3 SRS §9 acceptance scenarios (slice 3E-5) — the seven end-to-end
flows, each exercised through the real APIs."""

import datetime as dt
import json

from sqlalchemy import update

from tests.conftest import bearer
from tests.test_devices_api import (
    device_headers,
    enroll_active_device,
)
from tests.test_publishing_api import publish, ready_campaign
from tests.test_reports_phase2_api import send_playback
from tests.test_tenant_isolation import org_b  # noqa: F401 (fixture)


async def test_s1_ai_localized_variant_through_approval_and_publish(client, admin_tokens):
    """AI localize → approval inbox → approve → metadata preserved →
    campaign published to a device."""
    await client.put(
        "/api/v1/ai/policies",
        headers=bearer(admin_tokens),
        json={"approval": {"require_approval": True}},
    )
    resp = await client.post(
        "/api/v1/ai/localize",
        headers=bearer(admin_tokens),
        json={"text": "Welcome {{store}} — sale today", "target_locale": "es"},
    )
    request = resp.json()["data"]
    output = request["outputs"][0]
    assert output["safety_status"] == "pending"
    assert request["provider"] and request["template_version"]  # explainability

    inbox = (
        await client.get(
            "/api/v1/approvals/inbox?entity_type=ai_output&state=pending",
            headers=bearer(admin_tokens),
        )
    ).json()["data"]
    row = next(r for r in inbox if r["entity_id"] == output["id"])
    await client.post(
        f"/api/v1/approvals/{row['id']}/approve", headers=bearer(admin_tokens), json={}
    )
    resp = await client.get(
        f"/api/v1/ai/requests/{request['id']}", headers=bearer(admin_tokens)
    )
    approved = resp.json()["data"]["outputs"][0]
    assert approved["safety_status"] == "passed"
    assert "{{store}}" in approved["content"]["text"]  # placeholders preserved

    device_id, _ = await enroll_active_device(client, admin_tokens, "SN-ACC-AI")
    campaign = await ready_campaign(
        client, admin_tokens, device_ids=[device_id], name="Localized Campaign"
    )
    deployment = await publish(client, admin_tokens, campaign["id"])
    assert deployment["status"] in ("publishing", "published", "partial")
    await client.put(
        "/api/v1/ai/policies",
        headers=bearer(admin_tokens),
        json={"approval": {"require_approval": False}},
    )


async def test_s2_data_source_outage_last_known_good_and_recovery(
    client, admin_tokens, db_session, monkeypatch
):
    from app.integrations.fetch import FetchError
    from app.services import data_sources as engine

    resp = await client.post(
        "/api/v1/data-sources",
        headers=bearer(admin_tokens),
        json={"name": "Acceptance feed", "type": "rest_json",
              "endpoint": "https://feeds.example.com/acc.json"},
    )
    source_id = resp.json()["data"]["id"]

    async def alive(source):
        return json.dumps({"headline": "fresh"}).encode()

    monkeypatch.setattr(engine, "_fetch", alive)
    await client.post(
        f"/api/v1/data-sources/{source_id}/refresh", headers=bearer(admin_tokens)
    )

    async def dead(source):
        raise FetchError("connection refused")

    monkeypatch.setattr(engine, "_fetch", dead)
    await client.post(
        f"/api/v1/data-sources/{source_id}/refresh", headers=bearer(admin_tokens)
    )
    health = (
        await client.get(
            f"/api/v1/data-sources/{source_id}/health", headers=bearer(admin_tokens)
        )
    ).json()["data"]
    assert health["state"] == "error"
    assert health["has_last_known_good"] is True  # widget keeps rendering

    import uuid as uuid_mod

    good = await engine.latest_valid_snapshot(db_session, uuid_mod.UUID(source_id))
    assert good.payload_json["headline"] == "fresh"

    # Source returns → automatic refresh restores freshness.
    async def recovered(source):
        return json.dumps({"headline": "recovered"}).encode()

    monkeypatch.setattr(engine, "_fetch", recovered)
    resp = await client.post(
        f"/api/v1/data-sources/{source_id}/refresh", headers=bearer(admin_tokens)
    )
    assert resp.json()["data"]["ok"] is True
    health = (
        await client.get(
            f"/api/v1/data-sources/{source_id}/health", headers=bearer(admin_tokens)
        )
    ).json()["data"]
    assert health["state"] == "active"  # automatic recovery


async def test_s3_video_wall_degrade_and_resync(client, admin_tokens, db_session):
    from app.models import Device

    resp = await client.post(
        "/api/v1/video-walls",
        headers=bearer(admin_tokens),
        json={"name": "Acceptance 2x2",
              "canvas": {"width": 3840, "height": 2160, "rows": 2, "cols": 2}},
    )
    wall = resp.json()["data"]
    members = []
    for i in range(4):
        device_id, token = await enroll_active_device(client, admin_tokens, f"SN-ACC-W{i}")
        await client.post(
            f"/api/v1/player/{device_id}/heartbeat",
            headers={"X-Device-Token": token}, json={},
        )
        x, y = (i % 2) * 1920, (i // 2) * 1080
        await client.post(
            f"/api/v1/video-walls/{wall['id']}/members",
            headers=bearer(admin_tokens),
            json={"device_id": device_id,
                  "viewport": {"x": x, "y": y, "width": 1920, "height": 1080}},
        )
        members.append((device_id, token))

    resp = await client.post(
        f"/api/v1/video-walls/{wall['id']}/sync",
        headers=bearer(admin_tokens), json={"action": "start"},
    )
    assert resp.json()["data"]["status"] == "syncing"

    # One member goes dark → degraded, others keep playing.
    await db_session.execute(
        update(Device).where(Device.serial_no == "SN-ACC-W3").values(
            last_heartbeat_at=dt.datetime.now(dt.UTC) - dt.timedelta(hours=3)
        )
    )
    await db_session.commit()
    state = (
        await client.get(f"/api/v1/video-walls/{wall['id']}", headers=bearer(admin_tokens))
    ).json()["data"]
    assert state["status"] == "degraded"
    resp = await client.get(
        f"/api/v1/player/{members[0][0]}/manifest",
        headers={"X-Device-Token": members[0][1]},
    )
    assert resp.status_code == 200  # healthy member still serves

    # Device restored → wall resynchronizes.
    await client.post(
        f"/api/v1/player/{members[3][0]}/heartbeat",
        headers={"X-Device-Token": members[3][1]}, json={},
    )
    state = (
        await client.get(f"/api/v1/video-walls/{wall['id']}", headers=bearer(admin_tokens))
    ).json()["data"]
    assert state["status"] == "syncing"


async def test_s4_ads_booked_delivered_reconciled(client, admin_tokens, db_session):
    from app.services import ads as ads_engine

    device_id, token = await enroll_active_device(client, admin_tokens, "SN-ACC-AD")
    campaign = await ready_campaign(
        client, admin_tokens, device_ids=[device_id], name="Acceptance Ads"
    )
    await publish(client, admin_tokens, campaign["id"])
    inventory = (
        await client.post(
            "/api/v1/ad-inventory",
            headers=bearer(admin_tokens),
            json={"name": "Acceptance slot", "device_id": device_id},
        )
    ).json()["data"]
    now = dt.datetime.now(dt.UTC)
    booking = (
        await client.post(
            "/api/v1/ad-campaigns",
            headers=bearer(admin_tokens),
            json={"inventory_id": inventory["id"], "campaign_id": campaign["id"],
                  "advertiser_ref": "Acceptance Advertiser", "booked_units": 4,
                  "start_at": (now - dt.timedelta(hours=1)).isoformat(),
                  "end_at": (now + dt.timedelta(hours=1)).isoformat()},
        )
    ).json()["data"]
    inbox = (
        await client.get(
            "/api/v1/approvals/inbox?entity_type=ad_booking&state=pending",
            headers=bearer(admin_tokens),
        )
    ).json()["data"]
    row = next(r for r in inbox if r["entity_id"] == booking["id"])
    await client.post(
        f"/api/v1/approvals/{row['id']}/approve", headers=bearer(admin_tokens), json={}
    )

    manifest = (
        await client.get(
            f"/api/v1/player/{device_id}/manifest", headers=device_headers(token)
        )
    ).json()["data"]
    await send_playback(
        client, device_id, token, campaign["id"],
        manifest["assets"][0]["id"], ["completed"] * 4,
    )
    await ads_engine.reconcile_bookings(db_session)
    await db_session.commit()
    report = (
        await client.get("/api/v1/reports/ad-performance", headers=bearer(admin_tokens))
    ).json()["data"]
    mine = next(r for r in report if r["booking_id"] == booking["id"])
    assert mine["delivered_billable"] == 4
    assert mine["fill_rate_pct"] == 100.0


async def test_s5_offline_bundle_prestage_expiry_recovery(client, admin_tokens, db_session):
    from app.models import EdgeBundle

    device_id, token = await enroll_active_device(client, admin_tokens, "SN-ACC-EDGE")
    campaign = await ready_campaign(
        client, admin_tokens, device_ids=[device_id], name="Acceptance Edge"
    )
    await publish(client, admin_tokens, campaign["id"])
    bundle = (
        await client.post(
            "/api/v1/edge/bundles",
            headers=bearer(admin_tokens), json={"name": "Acceptance pack"},
        )
    ).json()["data"]
    await client.post(
        f"/api/v1/edge/bundles/{bundle['id']}/publish", headers=bearer(admin_tokens)
    )

    manifest = (
        await client.get(
            f"/api/v1/player/{device_id}/manifest", headers=device_headers(token)
        )
    ).json()["data"]
    assert manifest["bundle"]["signature"] == bundle["signature"]  # signed
    served = (
        await client.get(
            f"/api/v1/player/{device_id}/bundles/{bundle['id']}",
            headers=device_headers(token),
        )
    ).json()["data"]
    assert served["assets"][0]["sha256"]  # offline playback material staged

    # Expiry: past-TTL bundle disappears from manifests (player then falls
    # back to its cached manifest until reconnect/rebuild).
    import uuid as uuid_mod

    await db_session.execute(
        update(EdgeBundle)
        .where(EdgeBundle.id == uuid_mod.UUID(bundle["id"]))
        .values(expires_at=dt.datetime.now(dt.UTC) - dt.timedelta(days=1))
    )
    await db_session.commit()
    manifest = (
        await client.get(
            f"/api/v1/player/{device_id}/manifest", headers=device_headers(token)
        )
    ).json()["data"]
    assert "bundle" not in manifest

    # Recovery: a fresh bundle restores prefetch coverage.
    fresh = (
        await client.post(
            "/api/v1/edge/bundles",
            headers=bearer(admin_tokens), json={"name": "Acceptance pack v2"},
        )
    ).json()["data"]
    await client.post(
        f"/api/v1/edge/bundles/{fresh['id']}/publish", headers=bearer(admin_tokens)
    )
    manifest = (
        await client.get(
            f"/api/v1/player/{device_id}/manifest", headers=device_headers(token)
        )
    ).json()["data"]
    assert manifest["bundle"]["id"] == fresh["id"]


async def test_s6_anomaly_recommend_ack_remediate_logged(client, admin_tokens, db_session):
    from app.services import anomaly as engine

    device_id, token = await enroll_active_device(client, admin_tokens, "SN-ACC-ANOM")
    campaign = await ready_campaign(
        client, admin_tokens, device_ids=[device_id], name="Acceptance Anomaly"
    )
    await publish(client, admin_tokens, campaign["id"])
    manifest = (
        await client.get(
            f"/api/v1/player/{device_id}/manifest", headers=device_headers(token)
        )
    ).json()["data"]
    await send_playback(
        client, device_id, token, campaign["id"],
        manifest["assets"][0]["id"], ["failed"] * 12,
    )
    await client.post(
        "/api/v1/fleet-intelligence/rules",
        headers=bearer(admin_tokens),
        json={"name": "Acceptance health", "signal_type": "playback_failures",
              "threshold": {"min_events": 10, "max_failure_pct": 20}},
    )
    await engine.detect(db_session)
    await db_session.commit()

    anomaly = next(
        a for a in (
            await client.get(
                "/api/v1/fleet-intelligence/anomalies?state=open",
                headers=bearer(admin_tokens),
            )
        ).json()["data"]
        if a["device_id"] == device_id
    )
    assert anomaly["recommendation"]  # system generated a recommendation
    await client.post(
        f"/api/v1/fleet-intelligence/{anomaly['id']}/acknowledge",
        headers=bearer(admin_tokens),
    )
    remediation = (
        await client.post(
            f"/api/v1/fleet-intelligence/{anomaly['id']}/remediation",
            headers=bearer(admin_tokens), json={"action": "restart"},
        )
    ).json()["data"]
    actions = (
        await client.get(
            f"/api/v1/fleet-intelligence/anomalies/{anomaly['id']}/actions",
            headers=bearer(admin_tokens),
        )
    ).json()["data"]
    kinds = [a["action"] for a in actions]
    assert "acknowledge" in kinds and "remediate:restart" in kinds  # fully logged
    assert remediation["command_id"]


async def test_s7_sso_configure_map_login_revoke_audit(client, admin_tokens, monkeypatch):
    from app.services import sso as engine

    await client.post(
        "/api/v1/sso/providers",
        headers=bearer(admin_tokens),
        json={"issuer": "https://idp.example.com", "client_id": "acc",
              "client_secret_ref": "ACC_SSO_SECRET",
              "claim_mapping": {"role_map": {"ops": "Device Manager"},
                                "auto_provision": True},
              "active": True},
    )

    async def discovery():
        return json.dumps(
            {"issuer": "https://idp.example.com",
             "authorization_endpoint": "https://idp.example.com/authorize",
             "token_endpoint": "https://idp.example.com/token",
             "jwks_uri": "https://idp.example.com/jwks"}
        ).encode()

    monkeypatch.setattr(engine, "guarded_fetch", lambda url, **kw: discovery())
    await client.post("/api/v1/sso/providers/test", headers=bearer(admin_tokens))

    from urllib.parse import parse_qs, urlparse

    async def fake_exchange(provider, code, redirect_uri):
        return {"email": "sso.ops@demo-org.com", "name": "SSO Ops", "groups": ["ops"]}

    monkeypatch.setattr(engine, "_exchange_code", fake_exchange)
    state = parse_qs(urlparse((
        await client.get(
            "/api/v1/auth/sso/demo/login?redirect_uri=https://portal.example.com/cb"
        )
    ).json()["data"]["authorization_url"]).query)["state"][0]
    tokens = (
        await client.post(
            "/api/v1/auth/sso/demo/callback",
            json={"code": "c", "state": state,
                  "redirect_uri": "https://portal.example.com/cb"},
        )
    ).json()["data"]
    assert "Device Manager" in [r["name"] for r in tokens["user"]["roles"]]  # mapped

    # Revoke provider access → the flow refuses.
    await client.post(
        "/api/v1/sso/providers",
        headers=bearer(admin_tokens),
        json={"issuer": "https://idp.example.com", "client_id": "acc",
              "client_secret_ref": "ACC_SSO_SECRET", "active": False},
    )
    resp = await client.get(
        "/api/v1/auth/sso/demo/login?redirect_uri=https://portal.example.com/cb"
    )
    assert resp.status_code == 422

    # Audit evidence exists for the SSO login.
    resp = await client.get(
        "/api/v1/audit-logs?action=USER_LOGIN_SSO", headers=bearer(admin_tokens)
    )
    assert resp.json()["data"], resp.text