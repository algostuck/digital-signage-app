"""Phase-3 slice 3B-2: decisioning — deterministic rules with auditable
reasons, guardrails, manifest integration and the degradation ladder."""

import json

from tests.conftest import bearer, login
from tests.test_device_ops_api import enroll_with
from tests.test_publishing_api import publish, ready_campaign
from tests.test_tenant_isolation import org_b  # noqa: F401 (fixture)


async def make_policy(client, tokens, *, name="Main policy", guardrails=None):
    resp = await client.post(
        "/api/v1/decision-policies",
        headers=bearer(tokens),
        json={"name": name, "guardrails": guardrails},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


async def set_rules(client, tokens, policy_id, rules):
    resp = await client.put(
        f"/api/v1/decision-policies/{policy_id}/rules",
        headers=bearer(tokens),
        json={"rules": rules},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


async def test_rule_validation(client, admin_tokens):
    policy = await make_policy(client, admin_tokens, name="Validation")
    bad_rules = [
        [{"conditions": {"weather": "hot"}, "actions": {"pin": "x"}}],  # unknown key
        [{"conditions": {}, "actions": {"pin": "a", "exclude": "b"}}],  # two actions
        [{"conditions": {"time": {"start": "nine", "end": "17:00"}},
          "actions": {"pin": "x"}}],  # bad time
        [{"conditions": {}, "actions": {}}],  # no action
    ]
    for rules in bad_rules:
        resp = await client.put(
            f"/api/v1/decision-policies/{policy['id']}/rules",
            headers=bearer(admin_tokens),
            json={"rules": rules},
        )
        assert resp.status_code == 400, rules

    # Guardrail validation.
    resp = await client.post(
        "/api/v1/decision-policies",
        headers=bearer(admin_tokens),
        json={"name": "Bad guardrails", "guardrails": {"max_switches_per_hour": -1}},
    )
    assert resp.status_code == 400


async def test_pin_rule_flows_into_manifest_with_reasons(client, admin_tokens):
    samsung_id, samsung_token = await enroll_with(
        client, admin_tokens, "SN-DEC-SAM", manufacturer="Samsung", platform="tizen"
    )
    lg_id, lg_token = await enroll_with(
        client, admin_tokens, "SN-DEC-LG", manufacturer="LG", platform="webos"
    )
    campaign_a = await ready_campaign(
        client, admin_tokens, device_ids=[samsung_id, lg_id], priority=60, name="Dec A"
    )
    campaign_b = await ready_campaign(
        client, admin_tokens, device_ids=[samsung_id, lg_id], priority=40, name="Dec B"
    )
    await publish(client, admin_tokens, campaign_a["id"])
    await publish(client, admin_tokens, campaign_b["id"])

    policy = await make_policy(client, admin_tokens)
    await set_rules(
        client, admin_tokens, policy["id"],
        [{"priority": 10, "conditions": {"platform": "tizen"},
          "actions": {"pin": campaign_b["id"]}}],
    )

    # Preview (dry-run): Samsung decided to B with reasons; LG untouched.
    resp = await client.post(
        "/api/v1/decision-rules/preview",
        headers=bearer(admin_tokens),
        json={"device_id": samsung_id},
    )
    preview = resp.json()["data"]
    assert preview["scheduler_campaign_id"] == campaign_a["id"]
    assert preview["decided_campaign_id"] == campaign_b["id"]
    assert preview["reasons"][0]["action"] == "pin"
    assert "platform=tizen" in json.dumps(preview["reasons"])

    resp = await client.post(
        "/api/v1/decision-rules/preview",
        headers=bearer(admin_tokens),
        json={"device_id": lg_id},
    )
    assert resp.json()["data"]["decided_campaign_id"] == campaign_a["id"]
    assert resp.json()["data"]["reasons"] == []

    # Manifest: Samsung plays B with the auditable decision block.
    resp = await client.get(
        f"/api/v1/player/{samsung_id}/manifest",
        headers={"X-Device-Token": samsung_token},
    )
    manifest = resp.json()["data"]
    assert manifest["campaign"]["id"] == campaign_b["id"]
    assert manifest["decision"]["reasons"][0]["action"] == "pin"

    resp = await client.get(
        f"/api/v1/player/{lg_id}/manifest", headers={"X-Device-Token": lg_token}
    )
    manifest = resp.json()["data"]
    assert manifest["campaign"]["id"] == campaign_a["id"]
    assert "decision" not in manifest

    # The switch is logged ONCE — a sustained identical decision doesn't
    # multiply log rows (anti-flapping accounting).
    await client.get(
        f"/api/v1/player/{samsung_id}/manifest",
        headers={"X-Device-Token": samsung_token},
    )
    resp = await client.get(
        f"/api/v1/decision-log?device_id={samsung_id}", headers=bearer(admin_tokens)
    )
    log_rows = resp.json()["data"]
    assert len(log_rows) == 1
    assert log_rows[0]["campaign_id"] == campaign_b["id"]


async def test_boost_exclude_and_mandatory_guardrail(client, admin_tokens):
    device_id, _token = await enroll_with(client, admin_tokens, "SN-DEC-GRD")
    campaign_a = await ready_campaign(
        client, admin_tokens, device_ids=[device_id], priority=60, name="Grd A"
    )
    campaign_b = await ready_campaign(
        client, admin_tokens, device_ids=[device_id], priority=40, name="Grd B"
    )
    await publish(client, admin_tokens, campaign_a["id"])
    await publish(client, admin_tokens, campaign_b["id"])

    policy = await make_policy(
        client, admin_tokens, name="Guarded",
        guardrails={"mandatory_campaign_ids": [campaign_a["id"]]},
    )

    async def decided():
        resp = await client.post(
            "/api/v1/decision-rules/preview",
            headers=bearer(admin_tokens),
            json={"device_id": device_id},
        )
        return resp.json()["data"]

    # Boost outranks the scheduler's priority ordering.
    await set_rules(
        client, admin_tokens, policy["id"],
        [{"priority": 10, "conditions": {},
          "actions": {"boost": campaign_b["id"], "amount": 100}}],
    )
    assert (await decided())["decided_campaign_id"] == campaign_b["id"]

    # Excluding a mandatory campaign is refused with a recorded reason.
    await set_rules(
        client, admin_tokens, policy["id"],
        [{"priority": 10, "conditions": {}, "actions": {"exclude": campaign_a["id"]}}],
    )
    result = await decided()
    assert result["decided_campaign_id"] == campaign_a["id"]
    assert any(r["action"] == "exclude-blocked" for r in result["reasons"])

    # Excluding the non-mandatory one works.
    await set_rules(
        client, admin_tokens, policy["id"],
        [{"priority": 10, "conditions": {}, "actions": {"exclude": campaign_b["id"]}}],
    )
    result = await decided()
    assert result["decided_campaign_id"] == campaign_a["id"]
    assert any(r["action"] == "exclude" for r in result["reasons"])


async def test_frequency_cap_zero_never_switches(client, admin_tokens):
    device_id, token = await enroll_with(client, admin_tokens, "SN-DEC-CAP")
    campaign_a = await ready_campaign(
        client, admin_tokens, device_ids=[device_id], priority=60, name="Cap A"
    )
    campaign_b = await ready_campaign(
        client, admin_tokens, device_ids=[device_id], priority=40, name="Cap B"
    )
    await publish(client, admin_tokens, campaign_a["id"])
    await publish(client, admin_tokens, campaign_b["id"])

    policy = await make_policy(
        client, admin_tokens, name="Capped", guardrails={"max_switches_per_hour": 0}
    )
    await set_rules(
        client, admin_tokens, policy["id"],
        [{"priority": 10, "conditions": {}, "actions": {"pin": campaign_b["id"]}}],
    )

    resp = await client.get(
        f"/api/v1/player/{device_id}/manifest", headers={"X-Device-Token": token}
    )
    manifest = resp.json()["data"]
    assert manifest["campaign"]["id"] == campaign_a["id"]  # scheduler kept
    assert any(r["action"] == "frequency-capped" for r in manifest["decision"]["reasons"])
    resp = await client.get(
        f"/api/v1/decision-log?device_id={device_id}", headers=bearer(admin_tokens)
    )
    assert resp.json()["data"] == []  # capped decisions are not switches


async def test_external_data_condition(client, admin_tokens, monkeypatch):
    from app.services import data_sources as ds_engine

    async def fake(source):
        return json.dumps({"weather": {"temp_c": 38}}).encode()

    monkeypatch.setattr(ds_engine, "_fetch", fake)
    resp = await client.post(
        "/api/v1/data-sources",
        headers=bearer(admin_tokens),
        json={"name": "Weather ctx", "type": "rest_json",
              "endpoint": "https://feeds.example.com/wx.json"},
    )
    source_id = resp.json()["data"]["id"]
    await client.post(
        f"/api/v1/data-sources/{source_id}/refresh", headers=bearer(admin_tokens)
    )

    device_id, _token = await enroll_with(client, admin_tokens, "SN-DEC-WX")
    campaign_a = await ready_campaign(
        client, admin_tokens, device_ids=[device_id], priority=60, name="Wx A"
    )
    campaign_b = await ready_campaign(
        client, admin_tokens, device_ids=[device_id], priority=40, name="Wx Cold Drinks"
    )
    await publish(client, admin_tokens, campaign_a["id"])
    await publish(client, admin_tokens, campaign_b["id"])

    policy = await make_policy(client, admin_tokens, name="Weather rules")
    await set_rules(
        client, admin_tokens, policy["id"],
        [{"priority": 10,
          "conditions": {"data": {"source_id": source_id, "path": "weather.temp_c",
                                  "op": "gt", "value": 30}},
          "actions": {"pin": campaign_b["id"]}}],
    )

    resp = await client.post(
        "/api/v1/decision-rules/preview",
        headers=bearer(admin_tokens),
        json={"device_id": device_id},
    )
    result = resp.json()["data"]
    assert result["decided_campaign_id"] == campaign_b["id"]
    assert "temp_c gt 30 (actual=38)" in json.dumps(result["reasons"])


async def test_decisioning_rbac_and_isolation(client, admin_tokens, org_b):  # noqa: F811
    await make_policy(client, admin_tokens, name="Org A policy")
    b_tokens = await login(client, "admin@org-b-corp.com", "BAdmin@12345")
    resp = await client.get("/api/v1/decision-policies", headers=bearer(b_tokens))
    assert resp.json()["data"] == []

    resp = await client.get("/api/v1/roles", headers=bearer(admin_tokens))
    viewer_id = next(r["id"] for r in resp.json()["data"] if r["name"] == "Viewer")
    await client.post(
        "/api/v1/users",
        headers=bearer(admin_tokens),
        json={"email": "dec-viewer@demo-org.com", "full_name": "Dec Viewer",
              "password": "Viewer@12345", "role_ids": [viewer_id]},
    )
    viewer = await login(client, "dec-viewer@demo-org.com", "Viewer@12345")
    resp = await client.post(
        "/api/v1/decision-policies", headers=bearer(viewer), json={"name": "Nope"}
    )
    assert resp.status_code == 403
