"""Phase-3 slice 3E-1: enterprise SSO — provider config (secrets by ref),
signed state, claim mapping, auto-provisioning, entitlement gate."""

from tests.conftest import bearer, login
from tests.test_tenant_isolation import org_b  # noqa: F401 (fixture)

MAPPING = {
    "email": "email",
    "name": "name",
    "groups": "groups",
    "role_map": {"signage-admins": "Organization Administrator"},
    "auto_provision": True,
    "default_role": "Viewer",
}


async def configure(client, tokens, *, active=True, mapping=None):
    resp = await client.post(
        "/api/v1/sso/providers",
        headers=bearer(tokens),
        json={
            "issuer": "https://idp.example.com",
            "client_id": "signage-cloud",
            "client_secret_ref": "SSO_TEST_SECRET",
            "claim_mapping": mapping or MAPPING,
            "active": active,
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


def fake_exchange(claims):
    async def _exchange(provider, code, redirect_uri):
        return claims

    return _exchange


async def test_provider_config_and_state_flow(client, admin_tokens, monkeypatch):
    from app.services import sso as engine

    provider = await configure(client, admin_tokens)
    assert provider["client_secret_ref"] == "SSO_TEST_SECRET"  # name, never a value
    assert provider["claim_mapping"]["auto_provision"] is True

    # Metadata comes from discovery — fake it in place of a real IdP.
    monkeypatch.setattr(
        engine, "guarded_fetch",
        lambda url, **kw: _fake_discovery(),
    )
    resp = await client.post("/api/v1/sso/providers/test", headers=bearer(admin_tokens))
    assert resp.json()["data"]["ok"] is True
    assert "authorization_endpoint" in resp.json()["data"]["endpoints"]

    resp = await client.get(
        "/api/v1/auth/sso/demo/login?redirect_uri=https://portal.example.com/cb"
    )
    assert resp.status_code == 200, resp.text
    url = resp.json()["data"]["authorization_url"]
    assert url.startswith("https://idp.example.com/authorize?")
    assert "state=" in url and "client_id=signage-cloud" in url

    # Tampered/foreign state is refused.
    resp = await client.post(
        "/api/v1/auth/sso/demo/callback",
        json={"code": "x", "state": "bogus", "redirect_uri": "https://portal.example.com/cb"},
    )
    assert resp.status_code == 401


async def _fake_discovery():
    import json

    return json.dumps(
        {
            "issuer": "https://idp.example.com",
            "authorization_endpoint": "https://idp.example.com/authorize",
            "token_endpoint": "https://idp.example.com/token",
            "jwks_uri": "https://idp.example.com/jwks",
        }
    ).encode()


async def test_callback_maps_claims_and_provisions(client, admin_tokens, monkeypatch):
    from app.services import sso as engine

    await configure(client, admin_tokens)
    monkeypatch.setattr(engine, "guarded_fetch", lambda url, **kw: _fake_discovery())
    await client.post("/api/v1/sso/providers/test", headers=bearer(admin_tokens))

    state_url = (
        await client.get(
            "/api/v1/auth/sso/demo/login?redirect_uri=https://portal.example.com/cb"
        )
    ).json()["data"]["authorization_url"]
    from urllib.parse import parse_qs, urlparse

    state = parse_qs(urlparse(state_url).query)["state"][0]

    # Existing user logs in via mapped email claim.
    monkeypatch.setattr(
        engine, "_exchange_code",
        fake_exchange({"email": "admin@demo-org.com", "name": "Demo Administrator"}),
    )
    resp = await client.post(
        "/api/v1/auth/sso/demo/callback",
        json={"code": "authcode", "state": state,
              "redirect_uri": "https://portal.example.com/cb"},
    )
    assert resp.status_code == 200, resp.text
    tokens = resp.json()["data"]
    assert tokens["access_token"]
    assert tokens["user"]["email"] == "admin@demo-org.com"

    # Unknown identity auto-provisions with the group-mapped role.
    monkeypatch.setattr(
        engine, "_exchange_code",
        fake_exchange({"email": "new.hire@demo-org.com", "name": "New Hire",
                       "groups": ["signage-admins"]}),
    )
    state = parse_qs(urlparse((
        await client.get(
            "/api/v1/auth/sso/demo/login?redirect_uri=https://portal.example.com/cb"
        )
    ).json()["data"]["authorization_url"]).query)["state"][0]
    resp = await client.post(
        "/api/v1/auth/sso/demo/callback",
        json={"code": "authcode", "state": state,
              "redirect_uri": "https://portal.example.com/cb"},
    )
    assert resp.status_code == 200, resp.text
    provisioned = resp.json()["data"]["user"]
    assert provisioned["email"] == "new.hire@demo-org.com"
    assert "Organization Administrator" in [r["name"] for r in provisioned["roles"]]

    # With auto_provision off, unknown identities are refused.
    await configure(
        client, admin_tokens, mapping={**MAPPING, "auto_provision": False}
    )
    state = parse_qs(urlparse((
        await client.get(
            "/api/v1/auth/sso/demo/login?redirect_uri=https://portal.example.com/cb"
        )
    ).json()["data"]["authorization_url"]).query)["state"][0]
    monkeypatch.setattr(
        engine, "_exchange_code", fake_exchange({"email": "stranger@else.com"})
    )
    resp = await client.post(
        "/api/v1/auth/sso/demo/callback",
        json={"code": "authcode", "state": state,
              "redirect_uri": "https://portal.example.com/cb"},
    )
    assert resp.status_code == 401
    assert "auto-provision is off" in resp.text


async def test_sso_entitlement_and_disabled_flow(client, admin_tokens, org_b):  # noqa: F811
    # Business plan has sso=False.
    b_tokens = await login(client, "admin@org-b-corp.com", "BAdmin@12345")
    resp = await client.post(
        "/api/v1/billing/subscribe", headers=bearer(b_tokens), json={"plan_code": "business"}
    )
    assert resp.status_code == 200
    resp = await client.post(
        "/api/v1/sso/providers",
        headers=bearer(b_tokens),
        json={"issuer": "https://idp.example.com", "client_id": "x",
              "client_secret_ref": "REF"},
    )
    assert resp.status_code == 422
    assert "sso" in resp.text

    # Orgs without an active provider refuse the public flow.
    resp = await client.get(
        "/api/v1/auth/sso/org-b/login?redirect_uri=https://x.example.com/cb"
    )
    assert resp.status_code == 422
    assert "not enabled" in resp.text