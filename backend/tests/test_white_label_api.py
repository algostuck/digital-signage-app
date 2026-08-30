"""Phase-3 slice 3E-2: white label (domain metadata + email identity +
region) and the password-reset flow (Phase-1 deferral closed)."""

from tests.conftest import bearer, login
from tests.test_tenant_isolation import org_b  # noqa: F401 (fixture)


async def test_white_label_settings_and_domain_verification(client, admin_tokens):
    resp = await client.get("/api/v1/organization/white-label", headers=bearer(admin_tokens))
    assert resp.status_code == 200
    assert resp.json()["data"]["custom_domain"] is None
    assert resp.json()["data"]["region"] == "default"

    resp = await client.put(
        "/api/v1/organization/white-label",
        headers=bearer(admin_tokens),
        json={"custom_domain": "Signage.Acme.Com",
              "email_from_name": "Acme Signage",
              "email_from_address": "displays@acme.com"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["custom_domain"] == "signage.acme.com"  # normalized
    assert data["domain_verified"] is False

    resp = await client.put(
        "/api/v1/organization/white-label",
        headers=bearer(admin_tokens),
        json={"custom_domain": "not a domain"},
    )
    assert resp.status_code == 400

    # Only a platform admin verifies the domain (audited decision).
    platform = await login(client, "platform@signage.cloud", "Platform@12345")
    tenants = (
        await client.get("/api/v1/platform/tenants", headers=bearer(platform))
    ).json()["data"]
    demo_id = next(t["id"] for t in tenants if t["code"] == "demo")
    resp = await client.post(
        f"/api/v1/platform/tenants/{demo_id}/verify-domain",
        headers=bearer(platform),
        json={"verified": True},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["domain_verified"] is True

    # Region metadata via the platform tenant editor.
    resp = await client.patch(
        f"/api/v1/platform/tenants/{demo_id}",
        headers=bearer(platform),
        json={"region": "ap-south"},
    )
    assert resp.json()["data"]["region"] == "ap-south"
    resp = await client.get("/api/v1/organization/white-label", headers=bearer(admin_tokens))
    assert resp.json()["data"]["region"] == "ap-south"


async def test_white_label_entitlement_gate(client, org_b):  # noqa: F811
    b_tokens = await login(client, "admin@org-b-corp.com", "BAdmin@12345")
    resp = await client.post(
        "/api/v1/billing/subscribe", headers=bearer(b_tokens),
        json={"plan_code": "professional"},  # white_label=False on Professional
    )
    assert resp.status_code == 200
    resp = await client.put(
        "/api/v1/organization/white-label",
        headers=bearer(b_tokens),
        json={"email_from_name": "Nope"},
    )
    assert resp.status_code == 422
    assert "white_label" in resp.text


async def test_password_reset_flow(client, admin_tokens, caplog):
    import logging
    import re

    # Request always "succeeds" (no account enumeration)…
    with caplog.at_level(logging.INFO, logger="app.email"):
        resp = await client.post(
            "/api/v1/auth/password-reset/request",
            json={"email": "nobody@nowhere.example"},
        )
        assert resp.status_code == 200
        resp = await client.post(
            "/api/v1/auth/password-reset/request",
            json={"email": "admin@demo-org.com"},
        )
        assert resp.status_code == 200
    # …but only the real account got mail (log provider records it).
    mails = [r.message for r in caplog.records if "EMAIL to=" in r.message]
    assert len(mails) == 1 and "admin@demo-org.com" in mails[0]
    token = re.search(r"minutes\):\\n([\w.\-]+)", mails[0]).group(1)

    # Weak password refused; strong accepted; old sessions revoked.
    resp = await client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": token, "new_password": "short"},
    )
    assert resp.status_code in (400, 422)
    resp = await client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": token, "new_password": "Brand-new-pass-1"},
    )
    assert resp.status_code == 200, resp.text

    # Old password dead, new one works; token is single-use.
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@demo-org.com", "password": "Admin@12345"},
    )
    assert resp.status_code == 401
    fresh = await login(client, "admin@demo-org.com", "Brand-new-pass-1")
    assert fresh["access_token"]
    resp = await client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": token, "new_password": "Another-pass-22"},
    )
    assert resp.status_code == 401  # pwh mismatch after the first use

    # Old refresh token family is revoked.
    resp = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": admin_tokens["refresh_token"]}
    )
    assert resp.status_code == 401