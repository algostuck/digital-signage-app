from datetime import UTC, datetime, timedelta

import jwt as pyjwt

from app.core.config import get_settings
from tests.conftest import bearer, login


async def test_login_success(client, seeded):
    data = await login(client, "admin@demo-org.com", "Admin@12345")
    assert data["token_type"] == "bearer"
    assert data["access_token"] and data["refresh_token"]
    assert data["user"]["email"] == "admin@demo-org.com"
    assert "users.manage" in data["user"]["permissions"]


async def test_login_wrong_password(client, seeded):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@demo-org.com", "password": "wrong-password"},
    )
    assert resp.status_code == 401
    assert resp.json()["errors"][0]["code"] == "UNAUTHENTICATED"


async def test_login_unknown_email(client, seeded):
    resp = await client.post(
        "/api/v1/auth/login", json={"email": "nobody@demo-org.com", "password": "whatever"}
    )
    assert resp.status_code == 401


async def test_me_requires_token(client, seeded):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401

    resp = await client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer not-a-token"}
    )
    assert resp.status_code == 401


async def test_me_returns_current_user(client, admin_tokens):
    resp = await client.get("/api/v1/auth/me", headers=bearer(admin_tokens))
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["email"] == "admin@demo-org.com"
    assert body["roles"][0]["name"] == "Organization Administrator"


async def test_refresh_rotates_and_blocks_reuse(client, admin_tokens):
    old_refresh = admin_tokens["refresh_token"]

    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert resp.status_code == 200
    new_tokens = resp.json()["data"]
    assert new_tokens["refresh_token"] != old_refresh

    # Reusing the rotated (revoked) token fails and revokes the session family.
    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert resp.status_code == 401

    resp = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": new_tokens["refresh_token"]}
    )
    assert resp.status_code == 401


async def test_logout_revokes_refresh_token(client, admin_tokens):
    resp = await client.post(
        "/api/v1/auth/logout", json={"refresh_token": admin_tokens["refresh_token"]}
    )
    assert resp.status_code == 200

    resp = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": admin_tokens["refresh_token"]}
    )
    assert resp.status_code == 401


async def test_expired_access_token_rejected(client, admin_tokens):
    settings = get_settings()
    payload = pyjwt.decode(
        admin_tokens["access_token"],
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
    )
    payload["exp"] = datetime.now(UTC) - timedelta(minutes=1)
    expired = pyjwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

    resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert resp.status_code == 401


async def test_refresh_token_cannot_be_used_as_access_token(client, admin_tokens):
    resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {admin_tokens['refresh_token']}"},
    )
    assert resp.status_code == 401
