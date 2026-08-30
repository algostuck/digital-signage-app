from tests.conftest import bearer, login


async def _role_id(client, tokens, name: str) -> str:
    resp = await client.get("/api/v1/roles", headers=bearer(tokens))
    return next(r["id"] for r in resp.json()["data"] if r["name"] == name)


async def test_create_user_with_password_is_active(client, admin_tokens):
    viewer_id = await _role_id(client, admin_tokens, "Viewer")
    resp = await client.post(
        "/api/v1/users",
        headers=bearer(admin_tokens),
        json={
            "email": "jane@demo-org.com",
            "full_name": "Jane Doe",
            "password": "Jane@12345",
            "role_ids": [viewer_id],
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["status"] == "active"
    assert data["roles"][0]["name"] == "Viewer"

    # New user can log in immediately.
    await login(client, "jane@demo-org.com", "Jane@12345")


async def test_create_user_without_password_is_invited(client, admin_tokens):
    resp = await client.post(
        "/api/v1/users",
        headers=bearer(admin_tokens),
        json={"email": "invitee@demo-org.com", "full_name": "Invitee", "role_ids": []},
    )
    assert resp.status_code == 201
    assert resp.json()["data"]["status"] == "invited"


async def test_duplicate_email_conflict(client, admin_tokens):
    payload = {"email": "dup@demo-org.com", "full_name": "Dup", "role_ids": []}
    resp = await client.post("/api/v1/users", headers=bearer(admin_tokens), json=payload)
    assert resp.status_code == 201
    resp = await client.post("/api/v1/users", headers=bearer(admin_tokens), json=payload)
    assert resp.status_code == 409
    assert resp.json()["errors"][0]["code"] == "CONFLICT"


async def test_list_users_paginated(client, admin_tokens):
    resp = await client.get(
        "/api/v1/users?page=1&page_size=10", headers=bearer(admin_tokens)
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["meta"]["page"] == 1
    assert body["meta"]["total"] >= 1
    assert any(u["email"] == "admin@demo-org.com" for u in body["data"])


async def test_update_user_roles(client, admin_tokens):
    resp = await client.post(
        "/api/v1/users",
        headers=bearer(admin_tokens),
        json={"email": "edit@demo-org.com", "full_name": "Before", "role_ids": []},
    )
    user_id = resp.json()["data"]["id"]
    cm_id = await _role_id(client, admin_tokens, "Content Manager")

    resp = await client.patch(
        f"/api/v1/users/{user_id}",
        headers=bearer(admin_tokens),
        json={"full_name": "After", "role_ids": [cm_id]},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["full_name"] == "After"
    assert data["roles"][0]["name"] == "Content Manager"


async def test_deactivate_blocks_login_and_activate_restores(client, admin_tokens):
    resp = await client.post(
        "/api/v1/users",
        headers=bearer(admin_tokens),
        json={
            "email": "temp@demo-org.com",
            "full_name": "Temp",
            "password": "Temp@12345",
            "role_ids": [],
        },
    )
    user_id = resp.json()["data"]["id"]

    resp = await client.delete(f"/api/v1/users/{user_id}", headers=bearer(admin_tokens))
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "deactivated"

    resp = await client.post(
        "/api/v1/auth/login", json={"email": "temp@demo-org.com", "password": "Temp@12345"}
    )
    assert resp.status_code == 401

    resp = await client.post(
        f"/api/v1/users/{user_id}/activate", headers=bearer(admin_tokens)
    )
    assert resp.status_code == 200
    await login(client, "temp@demo-org.com", "Temp@12345")


async def test_cannot_deactivate_self(client, admin_tokens):
    self_id = admin_tokens["user"]["id"]
    resp = await client.delete(f"/api/v1/users/{self_id}", headers=bearer(admin_tokens))
    assert resp.status_code == 422
    assert resp.json()["errors"][0]["code"] == "BUSINESS_RULE_VIOLATION"


async def test_deactivated_user_token_stops_working(client, admin_tokens):
    resp = await client.post(
        "/api/v1/users",
        headers=bearer(admin_tokens),
        json={
            "email": "revoked@demo-org.com",
            "full_name": "Revoked",
            "password": "Revoked@12345",
            "role_ids": [],
        },
    )
    user_id = resp.json()["data"]["id"]
    victim_tokens = await login(client, "revoked@demo-org.com", "Revoked@12345")

    await client.delete(f"/api/v1/users/{user_id}", headers=bearer(admin_tokens))

    resp = await client.get("/api/v1/auth/me", headers=bearer(victim_tokens))
    assert resp.status_code == 401
