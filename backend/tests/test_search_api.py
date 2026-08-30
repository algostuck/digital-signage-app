"""Enterprise search tests (P2-SRC-001..003)."""

from tests.conftest import bearer, login
from tests.test_device_ops_api import enroll_with
from tests.test_tenant_isolation import org_b  # noqa: F401 (fixture)


async def test_global_search_across_modules(client, admin_tokens):
    await enroll_with(client, admin_tokens, "SN-SRCH-1")
    resp = await client.patch(
        "/api/v1/devices/"
        + (
            await client.get("/api/v1/devices?q=SN-SRCH-1", headers=bearer(admin_tokens))
        ).json()["data"][0]["id"],
        headers=bearer(admin_tokens),
        json={"name": "Searchable Lobby Screen"},
    )
    assert resp.status_code == 200, resp.text
    from tests.test_campaigns_api import create_campaign

    await create_campaign(client, admin_tokens, name="Searchable Winter Push")

    resp = await client.get("/api/v1/search?q=searchable", headers=bearer(admin_tokens))
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["total"] >= 2
    modules = data["modules"]
    assert any(d["name"] == "Searchable Lobby Screen" for d in modules["devices"])
    assert any(c["name"] == "Searchable Winter Push" for c in modules["campaigns"])
    # Admin sees every module key (permission-complete).
    assert {"devices", "content", "locations", "campaigns", "playlists", "users"} <= set(
        modules
    )

    # Serial search works too.
    resp = await client.get("/api/v1/search?q=SN-SRCH", headers=bearer(admin_tokens))
    assert any(
        d["subtitle"] == "SN-SRCH-1" for d in resp.json()["data"]["modules"]["devices"]
    )

    # Too-short query.
    resp = await client.get("/api/v1/search?q=a", headers=bearer(admin_tokens))
    assert resp.status_code == 400


async def test_search_is_permission_filtered(client, admin_tokens):
    resp = await client.get("/api/v1/roles", headers=bearer(admin_tokens))
    device_manager_id = next(
        r["id"] for r in resp.json()["data"] if r["name"] == "Device Manager"
    )
    await client.post(
        "/api/v1/users",
        headers=bearer(admin_tokens),
        json={
            "email": "srch-dm@demo-org.com",
            "full_name": "Search DM",
            "password": "Manager@12345",
            "role_ids": [device_manager_id],
        },
    )
    dm = await login(client, "srch-dm@demo-org.com", "Manager@12345")
    resp = await client.get("/api/v1/search?q=demo", headers=bearer(dm))
    modules = resp.json()["data"]["modules"]
    # Device Manager holds every .view permission (incl. users.view), so all
    # module keys are present — build a truly restricted role to verify
    # absence.
    resp = await client.post(
        "/api/v1/roles",
        headers=bearer(admin_tokens),
        json={
            "name": "Devices Only",
            "description": "search test",
            "permission_codes": ["devices.view"],
        },
    )
    assert resp.status_code == 201, resp.text
    role_id = resp.json()["data"]["id"]
    await client.post(
        "/api/v1/users",
        headers=bearer(admin_tokens),
        json={
            "email": "srch-narrow@demo-org.com",
            "full_name": "Narrow Searcher",
            "password": "Narrow@12345",
            "role_ids": [role_id],
        },
    )
    narrow = await login(client, "srch-narrow@demo-org.com", "Narrow@12345")
    resp = await client.get("/api/v1/search?q=demo", headers=bearer(narrow))
    narrow_modules = resp.json()["data"]["modules"]
    assert set(narrow_modules) == {"devices"}
    assert "users" in modules  # sanity for the broad role


async def test_search_tenant_isolation(client, admin_tokens, org_b):  # noqa: F811
    await enroll_with(client, admin_tokens, "SN-SRCH-ISO")
    b_tokens = await login(client, "admin@org-b-corp.com", "BAdmin@12345")
    resp = await client.get("/api/v1/search?q=SN-SRCH-ISO", headers=bearer(b_tokens))
    modules = resp.json()["data"]["modules"]
    assert all(not rows for rows in modules.values())


async def test_saved_views_lifecycle(client, admin_tokens):
    resp = await client.post(
        "/api/v1/saved-views",
        headers=bearer(admin_tokens),
        json={
            "module": "devices",
            "name": "Offline Samsungs",
            "filter_json": {"q": "samsung", "status": "active"},
            "columns_json": ["name", "serial", "connection"],
        },
    )
    assert resp.status_code == 201, resp.text
    view = resp.json()["data"]

    # Duplicate name in the same module -> 409; other module OK.
    resp = await client.post(
        "/api/v1/saved-views",
        headers=bearer(admin_tokens),
        json={"module": "devices", "name": "Offline Samsungs", "filter_json": {}},
    )
    assert resp.status_code == 409
    resp = await client.post(
        "/api/v1/saved-views",
        headers=bearer(admin_tokens),
        json={"module": "audit", "name": "Offline Samsungs", "filter_json": {}},
    )
    assert resp.status_code == 201
    # Unknown module -> 400.
    resp = await client.post(
        "/api/v1/saved-views",
        headers=bearer(admin_tokens),
        json={"module": "spaceships", "name": "x", "filter_json": {}},
    )
    assert resp.status_code == 400

    resp = await client.get(
        "/api/v1/saved-views?module=devices", headers=bearer(admin_tokens)
    )
    rows = resp.json()["data"]
    assert [r["name"] for r in rows] == ["Offline Samsungs"]
    assert rows[0]["filter_json"]["q"] == "samsung"

    resp = await client.delete(
        f"/api/v1/saved-views/{view['id']}", headers=bearer(admin_tokens)
    )
    assert resp.status_code == 200
    resp = await client.get(
        "/api/v1/saved-views?module=devices", headers=bearer(admin_tokens)
    )
    assert resp.json()["data"] == []


async def test_saved_views_are_personal(client, admin_tokens):
    resp = await client.post(
        "/api/v1/saved-views",
        headers=bearer(admin_tokens),
        json={"module": "devices", "name": "Admin private", "filter_json": {"q": "x"}},
    )
    view_id = resp.json()["data"]["id"]

    resp = await client.get("/api/v1/roles", headers=bearer(admin_tokens))
    viewer_id = next(r["id"] for r in resp.json()["data"] if r["name"] == "Viewer")
    await client.post(
        "/api/v1/users",
        headers=bearer(admin_tokens),
        json={
            "email": "sv-user@demo-org.com",
            "full_name": "SV User",
            "password": "Viewer@12345",
            "role_ids": [viewer_id],
        },
    )
    other = await login(client, "sv-user@demo-org.com", "Viewer@12345")
    resp = await client.get("/api/v1/saved-views", headers=bearer(other))
    assert resp.json()["data"] == []  # same org, different user -> invisible
    resp = await client.delete(f"/api/v1/saved-views/{view_id}", headers=bearer(other))
    assert resp.status_code == 404  # cannot delete someone else's view
