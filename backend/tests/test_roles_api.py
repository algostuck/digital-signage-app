from tests.conftest import bearer


async def test_list_roles_includes_system_roles(client, admin_tokens):
    resp = await client.get("/api/v1/roles", headers=bearer(admin_tokens))
    assert resp.status_code == 200
    names = {r["name"] for r in resp.json()["data"]}
    assert {"Organization Administrator", "Content Manager", "Device Manager", "Viewer"} <= names


async def test_permission_catalogue(client, admin_tokens):
    resp = await client.get("/api/v1/permissions", headers=bearer(admin_tokens))
    assert resp.status_code == 200
    codes = {p["code"] for p in resp.json()["data"]}
    assert "content.create" in codes
    assert "devices.control" in codes


async def test_create_custom_role(client, admin_tokens):
    resp = await client.post(
        "/api/v1/roles",
        headers=bearer(admin_tokens),
        json={
            "name": "Store Operator",
            "description": "Operates store screens",
            "permission_codes": ["devices.view", "monitoring.view"],
        },
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["is_system"] is False
    assert {p["code"] for p in data["permissions"]} == {"devices.view", "monitoring.view"}


async def test_create_role_unknown_permission(client, admin_tokens):
    resp = await client.post(
        "/api/v1/roles",
        headers=bearer(admin_tokens),
        json={"name": "Broken", "permission_codes": ["not.a.permission"]},
    )
    assert resp.status_code == 400
    assert "not.a.permission" in resp.json()["errors"][0]["message"]


async def test_duplicate_role_name_conflict(client, admin_tokens):
    payload = {"name": "Dup Role", "permission_codes": []}
    resp = await client.post("/api/v1/roles", headers=bearer(admin_tokens), json=payload)
    assert resp.status_code == 201
    resp = await client.post("/api/v1/roles", headers=bearer(admin_tokens), json=payload)
    assert resp.status_code == 409


async def test_system_role_cannot_be_modified(client, admin_tokens):
    resp = await client.get("/api/v1/roles", headers=bearer(admin_tokens))
    viewer = next(r for r in resp.json()["data"] if r["name"] == "Viewer")

    resp = await client.patch(
        f"/api/v1/roles/{viewer['id']}",
        headers=bearer(admin_tokens),
        json={"name": "Hacked"},
    )
    assert resp.status_code == 422


async def test_update_custom_role(client, admin_tokens):
    resp = await client.post(
        "/api/v1/roles",
        headers=bearer(admin_tokens),
        json={"name": "Editable", "permission_codes": ["reports.view"]},
    )
    role_id = resp.json()["data"]["id"]

    resp = await client.patch(
        f"/api/v1/roles/{role_id}",
        headers=bearer(admin_tokens),
        json={"name": "Edited", "permission_codes": ["reports.view", "audit.view"]},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["name"] == "Edited"
    assert {p["code"] for p in data["permissions"]} == {"reports.view", "audit.view"}
