"""Phase-3 slice 3A-3: developer platform — versioned API catalogue,
entitlement gate, sandbox tenant isolation, device simulator."""

from tests.conftest import bearer, login
from tests.test_tenant_isolation import org_b  # noqa: F401 (fixture)


async def test_openapi_catalogue_versions_and_changelog(client, admin_tokens):
    resp = await client.get("/api/v1/developer/openapi", headers=bearer(admin_tokens))
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["docs_url"] == "/api/docs"  # test env is not production

    products = {p["name"]: p for p in data["products"]}
    control = products["Control Plane API"]
    assert [v["version"] for v in control["versions"]] == ["v1"]
    assert control["versions"][0]["lifecycle_state"] == "current"
    assert control["versions"][0]["changelog"]

    player = products["Player Contract"]
    states = {v["version"]: v["lifecycle_state"] for v in player["versions"]}
    assert states == {"v1": "current", "v2": "preview"}


async def test_developer_portal_entitlement_gate(client, org_b):  # noqa: F811
    b_tokens = await login(client, "admin@org-b-corp.com", "BAdmin@12345")
    resp = await client.post(
        "/api/v1/billing/subscribe",
        headers=bearer(b_tokens),
        json={"plan_code": "business"},  # developer_portal is False on Business
    )
    assert resp.status_code == 200
    resp = await client.get("/api/v1/developer/openapi", headers=bearer(b_tokens))
    assert resp.status_code == 422
    assert "developer_portal" in resp.text


async def test_sandbox_provision_membership_and_simulator(client, admin_tokens):
    # No sandbox yet.
    resp = await client.get("/api/v1/developer/sandbox", headers=bearer(admin_tokens))
    assert resp.status_code == 200
    assert resp.json()["data"] is None

    # Provision — idempotent.
    resp = await client.post("/api/v1/developer/sandbox", headers=bearer(admin_tokens))
    assert resp.status_code == 200, resp.text
    sandbox = resp.json()["data"]
    assert sandbox["created"] is True
    assert sandbox["code"] == "demo-sbx"
    assert sandbox["enrollment_key"]
    resp = await client.post("/api/v1/developer/sandbox", headers=bearer(admin_tokens))
    assert resp.json()["data"]["created"] is False

    # The caller got an owner membership: the sandbox shows up as a tenant
    # they can switch into (SaaS-core mechanism).
    resp = await client.get("/api/v1/auth/memberships", headers=bearer(admin_tokens))
    rows = resp.json()["data"]
    sandbox_row = next(t for t in rows if t["organization_id"] == sandbox["organization_id"])
    assert sandbox_row["is_home"] is False

    # Simulate a device through the real pipeline.
    resp = await client.post(
        "/api/v1/developer/sandbox/simulate-device",
        headers=bearer(admin_tokens),
        json={},
    )
    assert resp.status_code == 200, resp.text
    sim = resp.json()["data"]
    assert sim["serial_no"].startswith("SIM-")
    assert sim["device_token"]

    # The simulated device is alive on the player contract...
    resp = await client.post(
        f"/api/v1/player/{sim['device_id']}/heartbeat",
        headers={"X-Device-Token": sim["device_token"]},
        json={},
    )
    assert resp.status_code == 200
    resp = await client.get(
        f"/api/v1/player/{sim['device_id']}/manifest",
        headers={"X-Device-Token": sim["device_token"]},
    )
    assert resp.status_code == 200

    # ...and fully isolated from the parent tenant's device registry.
    resp = await client.get("/api/v1/devices?page_size=200", headers=bearer(admin_tokens))
    serials = {d["serial_no"] for d in resp.json()["data"]}
    assert sim["serial_no"] not in serials

    # Inside the sandbox the device IS visible; a sandbox cannot nest.
    resp = await client.post(
        "/api/v1/auth/switch-tenant",
        headers=bearer(admin_tokens),
        json={
            "organization_id": sandbox["organization_id"],
            "refresh_token": admin_tokens["refresh_token"],
        },
    )
    assert resp.status_code == 200, resp.text
    switched = resp.json()["data"]
    resp = await client.get("/api/v1/devices?page_size=200", headers=bearer(switched))
    serials = {d["serial_no"] for d in resp.json()["data"]}
    assert sim["serial_no"] in serials
    resp = await client.post("/api/v1/developer/sandbox", headers=bearer(switched))
    assert resp.status_code == 422
    assert "itself a sandbox" in resp.text


async def test_developer_portal_requires_permission(client, admin_tokens):
    resp = await client.get("/api/v1/roles", headers=bearer(admin_tokens))
    viewer_id = next(r["id"] for r in resp.json()["data"] if r["name"] == "Viewer")
    resp = await client.post(
        "/api/v1/users",
        headers=bearer(admin_tokens),
        json={
            "email": "dev-viewer@demo-org.com",
            "full_name": "Dev Viewer",
            "password": "Viewer@12345",
            "role_ids": [viewer_id],
        },
    )
    assert resp.status_code == 201
    viewer = await login(client, "dev-viewer@demo-org.com", "Viewer@12345")
    resp = await client.get("/api/v1/developer/openapi", headers=bearer(viewer))
    assert resp.status_code == 403
