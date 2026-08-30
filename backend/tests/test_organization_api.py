from tests.conftest import bearer


async def test_get_organization(client, admin_tokens):
    resp = await client.get("/api/v1/organization", headers=bearer(admin_tokens))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["code"] == "demo"
    assert data["timezone"] == "Asia/Kolkata"


async def test_update_organization(client, admin_tokens):
    resp = await client.patch(
        "/api/v1/organization",
        headers=bearer(admin_tokens),
        json={
            "name": "Demo Org Renamed",
            "timezone": "Europe/London",
            "locale": "en-GB",
            "branding_json": {"logo_url": "https://cdn.demo-org.com/logo.png"},
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["name"] == "Demo Org Renamed"
    assert data["timezone"] == "Europe/London"
    assert data["branding_json"]["logo_url"].endswith("logo.png")


async def test_update_organization_rejects_bad_timezone(client, admin_tokens):
    resp = await client.patch(
        "/api/v1/organization",
        headers=bearer(admin_tokens),
        json={"timezone": "Mars/Olympus_Mons"},
    )
    assert resp.status_code == 400
    assert resp.json()["errors"][0]["field"] == "timezone"


async def test_update_organization_requires_permission(client, admin_tokens):
    resp = await client.get("/api/v1/roles", headers=bearer(admin_tokens))
    viewer_id = next(r["id"] for r in resp.json()["data"] if r["name"] == "Viewer")
    resp = await client.post(
        "/api/v1/users",
        headers=bearer(admin_tokens),
        json={
            "email": "orgviewer@demo-org.com",
            "full_name": "Org Viewer",
            "password": "Viewer@12345",
            "role_ids": [viewer_id],
        },
    )
    assert resp.status_code == 201

    from tests.conftest import login

    viewer = await login(client, "orgviewer@demo-org.com", "Viewer@12345")
    resp = await client.get("/api/v1/organization", headers=bearer(viewer))
    assert resp.status_code == 200  # organization.view
    resp = await client.patch(
        "/api/v1/organization", headers=bearer(viewer), json={"name": "Nope"}
    )
    assert resp.status_code == 403
