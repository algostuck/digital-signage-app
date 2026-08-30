"""Authorization (RBAC) enforcement tests."""

from tests.conftest import bearer, login


async def _create_user(client, admin_tokens, email, password, role_names):
    resp = await client.get("/api/v1/roles", headers=bearer(admin_tokens))
    roles = resp.json()["data"]
    role_ids = [r["id"] for r in roles if r["name"] in role_names]
    resp = await client.post(
        "/api/v1/users",
        headers=bearer(admin_tokens),
        json={
            "email": email,
            "full_name": email.split("@")[0],
            "password": password,
            "role_ids": role_ids,
        },
    )
    assert resp.status_code == 201, resp.text
    return await login(client, email, password)


async def test_viewer_can_read_but_not_write(client, admin_tokens):
    viewer = await _create_user(
        client, admin_tokens, "viewer@demo-org.com", "Viewer@12345", ["Viewer"]
    )

    resp = await client.get("/api/v1/users", headers=bearer(viewer))
    assert resp.status_code == 200

    resp = await client.post(
        "/api/v1/users",
        headers=bearer(viewer),
        json={"email": "x@demo-org.com", "full_name": "X", "role_ids": []},
    )
    assert resp.status_code == 403
    assert resp.json()["errors"][0]["code"] == "FORBIDDEN"

    resp = await client.post(
        "/api/v1/roles", headers=bearer(viewer), json={"name": "Nope", "permission_codes": []}
    )
    assert resp.status_code == 403


async def test_user_with_no_roles_is_denied(client, admin_tokens):
    bare = await _create_user(client, admin_tokens, "bare@demo-org.com", "Bare@12345", [])

    resp = await client.get("/api/v1/users", headers=bearer(bare))
    assert resp.status_code == 403

    # But can still see their own identity.
    resp = await client.get("/api/v1/auth/me", headers=bearer(bare))
    assert resp.status_code == 200


async def test_content_manager_cannot_manage_users(client, admin_tokens):
    cm = await _create_user(
        client, admin_tokens, "cm@demo-org.com", "Cm@1234567", ["Content Manager"]
    )

    resp = await client.get("/api/v1/users", headers=bearer(cm))
    assert resp.status_code == 200  # users.view via all-view

    resp = await client.post(
        "/api/v1/users",
        headers=bearer(cm),
        json={"email": "y@demo-org.com", "full_name": "Y", "role_ids": []},
    )
    assert resp.status_code == 403
