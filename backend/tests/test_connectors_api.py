"""Phase-3 slice 3E-4: integration catalogue — live per-tenant view over
the concrete integration stores (documented no-DDL decision)."""

from tests.conftest import bearer, login
from tests.test_tenant_isolation import org_b  # noqa: F401 (fixture)


async def test_catalogue_reflects_configured_state(client, admin_tokens):
    resp = await client.get("/api/v1/connectors", headers=bearer(admin_tokens))
    assert resp.status_code == 200
    by_key = {c["key"]: c for c in resp.json()["data"]}
    assert set(by_key) == {"webhooks", "event_bus", "data_sources", "api_keys",
                           "sso", "smtp"}
    assert by_key["event_bus"]["configured"] == 0
    assert by_key["data_sources"]["available"] is True  # enterprise plan

    # Configure an event-bus consumer and a data source — counts move.
    await client.post(
        "/api/v1/subscriptions",
        headers=bearer(admin_tokens),
        json={"name": "Cat consumer", "url": "https://x.example.com/hook",
              "event_types": ["*"]},
    )
    await client.post(
        "/api/v1/data-sources",
        headers=bearer(admin_tokens),
        json={"name": "Cat feed", "type": "rest_json",
              "endpoint": "https://feeds.example.com/cat.json"},
    )
    resp = await client.get("/api/v1/connectors", headers=bearer(admin_tokens))
    by_key = {c["key"]: c for c in resp.json()["data"]}
    assert by_key["event_bus"]["configured"] == 1
    assert by_key["data_sources"]["configured"] == 1


async def test_catalogue_availability_follows_entitlements(client, org_b):  # noqa: F811
    b_tokens = await login(client, "admin@org-b-corp.com", "BAdmin@12345")
    resp = await client.post(
        "/api/v1/billing/subscribe", headers=bearer(b_tokens), json={"plan_code": "starter"}
    )
    assert resp.status_code == 200
    resp = await client.get("/api/v1/connectors", headers=bearer(b_tokens))
    by_key = {c["key"]: c for c in resp.json()["data"]}
    assert by_key["data_sources"]["available"] is False  # Starter: dynamic_data off
    assert by_key["sso"]["available"] is False
    assert by_key["webhooks"]["available"] is True