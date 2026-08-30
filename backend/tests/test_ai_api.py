"""Phase-3 slice 3B-1: AI foundation — deterministic provider, governance
ledger, guardrails, approval routing, entitlement + credit metering."""

from tests.conftest import bearer, login
from tests.test_tenant_isolation import org_b  # noqa: F401 (fixture)


async def test_text_generation_is_deterministic_and_recorded(client, admin_tokens):
    resp = await client.post(
        "/api/v1/ai/generate/text",
        headers=bearer(admin_tokens),
        json={"template": "headline", "text": "big summer sale on all displays"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["provider"] == "local"
    assert data["model_ref"] == "deterministic-rules"
    assert data["template_version"] == "headline@1"
    output = data["outputs"][0]
    assert output["content"]["text"] == "Big Summer Sale On All Displays"
    assert output["safety_status"] == "passed"
    assert output["fallback"] is False
    assert 0 < output["confidence"] <= 1

    # Shorten respects word boundaries.
    resp = await client.post(
        "/api/v1/ai/generate/text",
        headers=bearer(admin_tokens),
        json={"template": "shorten",
              "text": "This is a very long promotional message for the lobby screen",
              "max_chars": 30},
    )
    text = resp.json()["data"]["outputs"][0]["content"]["text"]
    assert len(text) <= 31 and text.endswith("…")

    # Explainability trail is queryable.
    resp = await client.get("/api/v1/ai/requests", headers=bearer(admin_tokens))
    assert resp.status_code == 200
    rows = resp.json()["data"]
    assert len(rows) >= 2
    assert all(r["provider"] == "local" and r["template_version"] for r in rows)


async def test_creative_variants_fit_dimensions(client, admin_tokens):
    resp = await client.post(
        "/api/v1/ai/generate/creative",
        headers=bearer(admin_tokens),
        json={"headline": "grand opening celebration this weekend",
              "body": "Join us for offers.", "width": 3840, "height": 1080},
    )
    assert resp.status_code == 200, resp.text
    content = resp.json()["data"]["outputs"][0]["content"]
    assert content["layout_hint"] == "banner"
    assert content["dimensions"] == {"width": 3840, "height": 1080}
    assert len(content["headline"]) <= 61

    resp = await client.post(
        "/api/v1/ai/generate/creative",
        headers=bearer(admin_tokens),
        json={"headline": "menu", "width": 1080, "height": 1920},
    )
    assert resp.json()["data"]["outputs"][0]["content"]["layout_hint"] == "portrait"


async def test_localization_preserves_placeholders(client, admin_tokens):
    resp = await client.post(
        "/api/v1/ai/localize",
        headers=bearer(admin_tokens),
        json={"text": "Welcome {{store_name}} — sale today, free offer now",
              "target_locale": "es"},
    )
    assert resp.status_code == 200, resp.text
    output = resp.json()["data"]["outputs"][0]
    text = output["content"]["text"]
    assert "{{store_name}}" in text  # P3-AI-003: placeholder intact
    assert "rebajas" in text and "hoy" in text and "gratis" in text
    assert output["confidence"] > 0.4

    # Unsupported locale is a clean validation error, not a crash.
    resp = await client.post(
        "/api/v1/ai/localize",
        headers=bearer(admin_tokens),
        json={"text": "Welcome", "target_locale": "xx"},
    )
    assert resp.status_code == 400


async def test_guardrails_flag_banned_terms(client, admin_tokens):
    resp = await client.put(
        "/api/v1/ai/policies",
        headers=bearer(admin_tokens),
        json={"guardrails": {"banned_terms": ["cheapest", "guaranteed"]}},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["guardrails"]["banned_terms"] == ["cheapest", "guaranteed"]

    resp = await client.post(
        "/api/v1/ai/generate/text",
        headers=bearer(admin_tokens),
        json={"template": "headline", "text": "the cheapest deals in town"},
    )
    output = resp.json()["data"]["outputs"][0]
    assert output["safety_status"] == "flagged"
    assert "cheapest" in output["safety_notes"]

    # Disable an operation via policy.
    resp = await client.put(
        "/api/v1/ai/policies",
        headers=bearer(admin_tokens),
        json={"operations": {"allowed": ["text"]}},
    )
    assert resp.status_code == 200
    resp = await client.post(
        "/api/v1/ai/localize",
        headers=bearer(admin_tokens),
        json={"text": "Welcome", "target_locale": "es"},
    )
    assert resp.status_code == 422
    assert "disabled by your organization" in resp.text


async def test_approval_routing_via_2a_engine(client, admin_tokens):
    resp = await client.put(
        "/api/v1/ai/policies",
        headers=bearer(admin_tokens),
        json={"approval": {"require_approval": True},
              "operations": {"allowed": ["text", "creative", "localization"]},
              "guardrails": {"banned_terms": []}},
    )
    assert resp.status_code == 200

    resp = await client.post(
        "/api/v1/ai/generate/text",
        headers=bearer(admin_tokens),
        json={"template": "cta", "text": "New autumn collection"},
    )
    request = resp.json()["data"]
    output = request["outputs"][0]
    assert output["safety_status"] == "pending"

    # The output sits in the same approval inbox as campaigns/templates.
    resp = await client.get(
        "/api/v1/approvals/inbox?entity_type=ai_output&state=pending",
        headers=bearer(admin_tokens),
    )
    assert resp.status_code == 200, resp.text
    inbox = resp.json()["data"]
    row = next(r for r in inbox if r["entity_id"] == output["id"])

    resp = await client.post(
        f"/api/v1/approvals/{row['id']}/approve",
        headers=bearer(admin_tokens),
        json={"comments": "brand-safe"},
    )
    assert resp.status_code == 200, resp.text

    resp = await client.get(
        f"/api/v1/ai/requests/{request['id']}", headers=bearer(admin_tokens)
    )
    assert resp.json()["data"]["outputs"][0]["safety_status"] == "passed"

    # Reset approval policy for other tests.
    await client.put(
        "/api/v1/ai/policies",
        headers=bearer(admin_tokens),
        json={"approval": {"require_approval": False}},
    )


async def test_entitlement_and_credit_limits(client, admin_tokens, org_b):  # noqa: F811
    # Starter has ai_features=False.
    b_tokens = await login(client, "admin@org-b-corp.com", "BAdmin@12345")
    resp = await client.post(
        "/api/v1/billing/subscribe", headers=bearer(b_tokens), json={"plan_code": "starter"}
    )
    assert resp.status_code == 200
    resp = await client.post(
        "/api/v1/ai/generate/text",
        headers=bearer(b_tokens),
        json={"template": "headline", "text": "hello"},
    )
    assert resp.status_code == 422
    assert "ai_features" in resp.text

    # A plan with AI enabled but a 1-credit budget: first call ok, second blocked.
    platform = await login(client, "platform@signage.cloud", "Platform@12345")
    resp = await client.post(
        "/api/v1/platform/plans",
        headers=bearer(platform),
        json={
            "code": "ai-tiny",
            "name": "AI Tiny",
            "prices": {},
            "entitlements": [
                {"key": "ai_features", "bool_value": True},
                {"key": "ai_credits_month", "int_value": 1},
            ],
        },
    )
    assert resp.status_code == 200, resp.text
    tenants = (
        await client.get("/api/v1/platform/tenants", headers=bearer(platform))
    ).json()["data"]
    org_b_id = next(t["id"] for t in tenants if t["code"] == "org-b")
    resp = await client.patch(
        f"/api/v1/platform/tenants/{org_b_id}/subscription/plan",
        headers=bearer(platform),
        json={"plan_code": "ai-tiny"},
    )
    assert resp.status_code == 200

    resp = await client.post(
        "/api/v1/ai/generate/text",
        headers=bearer(b_tokens),
        json={"template": "headline", "text": "first call"},
    )
    assert resp.status_code == 200, resp.text
    resp = await client.post(
        "/api/v1/ai/generate/text",
        headers=bearer(b_tokens),
        json={"template": "headline", "text": "second call"},
    )
    assert resp.status_code == 422
    assert "AI credit limit reached (1/1)" in resp.text


async def test_ai_rbac_and_isolation(client, admin_tokens, org_b):  # noqa: F811
    resp = await client.get("/api/v1/roles", headers=bearer(admin_tokens))
    viewer_id = next(r["id"] for r in resp.json()["data"] if r["name"] == "Viewer")
    resp = await client.post(
        "/api/v1/users",
        headers=bearer(admin_tokens),
        json={"email": "ai-viewer@demo-org.com", "full_name": "AI Viewer",
              "password": "Viewer@12345", "role_ids": [viewer_id]},
    )
    assert resp.status_code == 201
    viewer = await login(client, "ai-viewer@demo-org.com", "Viewer@12345")
    resp = await client.post(
        "/api/v1/ai/generate/text",
        headers=bearer(viewer),
        json={"template": "headline", "text": "nope"},
    )
    assert resp.status_code == 403

    # Org A's trail is invisible to org B (legacy unrestricted).
    await client.post(
        "/api/v1/ai/generate/text",
        headers=bearer(admin_tokens),
        json={"template": "headline", "text": "org a only"},
    )
    b_tokens = await login(client, "admin@org-b-corp.com", "BAdmin@12345")
    resp = await client.get("/api/v1/ai/requests", headers=bearer(b_tokens))
    assert resp.json()["data"] == []
