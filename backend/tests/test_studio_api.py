"""Content studio tests (P2-CNT-001..004): template versioning through the
approval engine, widget schema validation, bindings, collections."""

from tests.conftest import bearer, login
from tests.test_approvals_api import make_approver
from tests.test_content_api import upload_asset
from tests.test_tenant_isolation import org_b  # noqa: F401 (fixture)

CLOCK_SCHEMA = {
    "fields": [
        {"key": "format", "label": "Format", "type": "select",
         "options": ["12h", "24h"], "required": True, "default": "24h"},
        {"key": "show_seconds", "label": "Show seconds", "type": "boolean"},
        {"key": "color", "label": "Color", "type": "color"},
    ]
}


async def make_widget(client, tokens, name="Clock", **overrides) -> dict:
    body = {
        "type": "clock",
        "name": name,
        "config_schema_json": CLOCK_SCHEMA,
        "defaults_json": {"format": "24h"},
        "fallback_json": {"text": "--:--"},
    }
    body.update(overrides)
    resp = await client.post("/api/v1/widgets", headers=bearer(tokens), json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


async def make_template(client, tokens, name="Menu Template") -> dict:
    resp = await client.post(
        "/api/v1/templates",
        headers=bearer(tokens),
        json={"name": name, "canvas_width": 1920, "canvas_height": 1080},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


async def test_widget_lifecycle_and_schema_validation(client, admin_tokens):
    widget = await make_widget(client, admin_tokens)
    assert widget["status"] == "active"
    assert widget["versions"][0]["version_no"] == 1
    assert widget["fallback_json"] == {"text": "--:--"}

    # Duplicate name -> 409.
    resp = await client.post(
        "/api/v1/widgets",
        headers=bearer(admin_tokens),
        json={"type": "clock", "name": "Clock", "config_schema_json": CLOCK_SCHEMA},
    )
    assert resp.status_code == 409

    # Bad schemas -> 400.
    for bad in [
        {"fields": []},
        {"fields": [{"key": "Bad Key!", "type": "string"}]},
        {"fields": [{"key": "x", "type": "unknown"}]},
        {"fields": [{"key": "x", "type": "select"}]},  # select without options
        {"nope": True},
    ]:
        resp = await client.post(
            "/api/v1/widgets",
            headers=bearer(admin_tokens),
            json={"type": "clock", "name": "Bad", "config_schema_json": bad},
        )
        assert resp.status_code == 400, bad

    # Defaults must satisfy the schema.
    resp = await client.post(
        "/api/v1/widgets",
        headers=bearer(admin_tokens),
        json={
            "type": "clock",
            "name": "Bad defaults",
            "config_schema_json": CLOCK_SCHEMA,
            "defaults_json": {"format": "13h"},
        },
    )
    assert resp.status_code == 400

    # New schema version is additive and immutable history remains.
    schema_v2 = {"fields": [*CLOCK_SCHEMA["fields"], {"key": "timezone", "label": "TZ",
                                                      "type": "string"}]}
    resp = await client.post(
        f"/api/v1/widgets/{widget['id']}/versions",
        headers=bearer(admin_tokens),
        json={"config_schema_json": schema_v2, "defaults_json": {"format": "12h"}},
    )
    assert resp.status_code == 201
    versions = resp.json()["data"]["versions"]
    assert [v["version_no"] for v in versions] == [1, 2]

    # Archive via PATCH.
    resp = await client.patch(
        f"/api/v1/widgets/{widget['id']}",
        headers=bearer(admin_tokens),
        json={"status": "archived"},
    )
    assert resp.json()["data"]["status"] == "archived"


async def test_template_submit_approve_versioning(client, admin_tokens):
    """P2-CNT-001: draft -> submit -> approval engine -> immutable version."""
    approver = await make_approver(client, admin_tokens, email="studio-appr@demo-org.com")
    template = await make_template(client, admin_tokens)
    assert template["status"] == "draft"
    assert template["current_version_no"] is None

    resp = await client.post(
        f"/api/v1/templates/{template['id']}/submit",
        headers=bearer(admin_tokens),
        json={"comments": "First cut"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["status"] == "pending_approval"

    # Pending templates are locked.
    resp = await client.put(
        f"/api/v1/templates/{template['id']}",
        headers=bearer(admin_tokens),
        json={"description": "nope"},
    )
    assert resp.status_code == 422

    # Approve through the shared inbox.
    resp = await client.get(
        "/api/v1/approvals/inbox?entity_type=template&state=pending",
        headers=bearer(approver),
    )
    request = resp.json()["data"][0]
    assert request["entity_name"] == "Menu Template"
    resp = await client.post(
        f"/api/v1/approvals/{request['id']}/approve",
        headers=bearer(approver),
        json={"comments": "Ship it"},
    )
    assert resp.status_code == 200, resp.text

    resp = await client.get("/api/v1/templates", headers=bearer(admin_tokens))
    approved = next(t for t in resp.json()["data"] if t["id"] == template["id"])
    assert approved["status"] == "approved"
    assert approved["current_version_no"] == 1

    resp = await client.get(
        f"/api/v1/templates/{template['id']}/versions", headers=bearer(admin_tokens)
    )
    versions = resp.json()["data"]
    assert len(versions) == 1 and versions[0]["version_no"] == 1

    # Approved templates are immutable too.
    resp = await client.put(
        f"/api/v1/templates/{template['id']}",
        headers=bearer(admin_tokens),
        json={"description": "nope"},
    )
    assert resp.status_code == 422


async def test_template_reject_edit_resubmit(client, admin_tokens):
    approver = await make_approver(client, admin_tokens, email="studio-rej@demo-org.com")
    template = await make_template(client, admin_tokens, name="Rejected Template")
    await client.post(
        f"/api/v1/templates/{template['id']}/submit", headers=bearer(admin_tokens), json={}
    )
    resp = await client.get(
        "/api/v1/approvals/inbox?entity_type=template&state=pending", headers=bearer(approver)
    )
    request = resp.json()["data"][0]
    await client.post(
        f"/api/v1/approvals/{request['id']}/reject",
        headers=bearer(approver),
        json={"comments": "Wrong branding"},
    )
    resp = await client.get("/api/v1/templates", headers=bearer(admin_tokens))
    rejected = next(t for t in resp.json()["data"] if t["id"] == template["id"])
    assert rejected["status"] == "rejected"

    # Editing a rejected template returns it to draft; resubmit produces v1.
    resp = await client.put(
        f"/api/v1/templates/{template['id']}",
        headers=bearer(admin_tokens),
        json={"description": "Fixed branding"},
    )
    assert resp.json()["data"]["status"] == "draft"
    resp = await client.post(
        f"/api/v1/templates/{template['id']}/submit", headers=bearer(admin_tokens), json={}
    )
    assert resp.json()["data"]["status"] == "pending_approval"


async def test_template_auto_approval_when_policy_disabled(client, admin_tokens):
    """Tenant policy OFF for templates -> submit approves + versions at once."""
    resp = await client.put(
        "/api/v1/approval-policies/template",
        headers=bearer(admin_tokens),
        json={"require_approval": False, "maker_checker": False},
    )
    assert resp.status_code == 200, resp.text
    template = await make_template(client, admin_tokens, name="Auto Template")
    resp = await client.post(
        f"/api/v1/templates/{template['id']}/submit", headers=bearer(admin_tokens), json={}
    )
    data = resp.json()["data"]
    assert data["status"] == "approved"
    assert data["current_version_no"] == 1
    # Restore the default policy for other tests.
    await client.put(
        "/api/v1/approval-policies/template",
        headers=bearer(admin_tokens),
        json={"require_approval": True, "maker_checker": False},
    )


async def test_widget_bindings_validated_on_submit(client, admin_tokens):
    widget = await make_widget(client, admin_tokens, name="Zone Clock")
    template = await make_template(client, admin_tokens, name="Bound Template")
    canvas = template["canvas_json"]
    zone = canvas["zones"][0]

    # Unknown binding token -> 400 at submit.
    zone["widget"] = {
        "widget_id": widget["id"],
        "config": {"format": "24h"},
        "bindings": {"text": "Today is {{definitely.not.approved}}"},
    }
    await client.put(
        f"/api/v1/templates/{template['id']}",
        headers=bearer(admin_tokens),
        json={"canvas_json": canvas},
    )
    resp = await client.post(
        f"/api/v1/templates/{template['id']}/submit", headers=bearer(admin_tokens), json={}
    )
    assert resp.status_code == 400
    assert "unknown variable" in resp.json()["errors"][0]["message"]

    # Bad widget config -> 400 at submit.
    zone["widget"] = {"widget_id": widget["id"], "config": {"format": "13h"}}
    await client.put(
        f"/api/v1/templates/{template['id']}",
        headers=bearer(admin_tokens),
        json={"canvas_json": canvas},
    )
    resp = await client.post(
        f"/api/v1/templates/{template['id']}/submit", headers=bearer(admin_tokens), json={}
    )
    assert resp.status_code == 400

    # Valid config + approved variables pass.
    zone["widget"] = {
        "widget_id": widget["id"],
        "config": {"format": "12h", "show_seconds": True},
        "bindings": {"text": "{{date}} — {{device.name}}"},
    }
    await client.put(
        f"/api/v1/templates/{template['id']}",
        headers=bearer(admin_tokens),
        json={"canvas_json": canvas},
    )
    resp = await client.post(
        f"/api/v1/templates/{template['id']}/submit", headers=bearer(admin_tokens), json={}
    )
    assert resp.status_code == 200, resp.text

    # The data-variable catalogue is exposed for the designer.
    resp = await client.get("/api/v1/data-variables", headers=bearer(admin_tokens))
    tokens = {v["token"] for v in resp.json()["data"]}
    assert {"date", "device.name", "weather.temp"} <= tokens


async def test_clone_uses_approved_snapshot(client, admin_tokens):
    """Consumers get the governed version, not later draft edits."""
    await client.put(
        "/api/v1/approval-policies/template",
        headers=bearer(admin_tokens),
        json={"require_approval": False, "maker_checker": False},
    )
    template = await make_template(client, admin_tokens, name="Snapshot Template")
    await client.post(
        f"/api/v1/templates/{template['id']}/submit", headers=bearer(admin_tokens), json={}
    )
    # New draft edit after approval is NOT what clones should see... but
    # approved templates are locked, so the draft cannot drift. Clone and
    # check the canvas matches the approved snapshot.
    resp = await client.post(
        f"/api/v1/templates/{template['id']}/clone",
        headers=bearer(admin_tokens),
        json={"name": "From Snapshot"},
    )
    assert resp.status_code == 201, resp.text
    layout = resp.json()["data"]
    assert layout["draft_canvas_json"]["canvas"]["width"] == 1920
    await client.put(
        "/api/v1/approval-policies/template",
        headers=bearer(admin_tokens),
        json={"require_approval": True, "maker_checker": False},
    )


async def test_asset_collections_and_playlist_reuse(client, admin_tokens):
    """P2-CNT-004: assemble a collection, reuse it in a playlist."""
    asset_a = await upload_asset(client, admin_tokens, name="Coll A", filename="a.png")
    asset_b = await upload_asset(client, admin_tokens, name="Coll B", filename="b.png")

    resp = await client.post(
        "/api/v1/asset-collections",
        headers=bearer(admin_tokens),
        json={"name": "Breakfast Menu", "description": "Morning rotation"},
    )
    assert resp.status_code == 201, resp.text
    collection = resp.json()["data"]

    resp = await client.put(
        f"/api/v1/asset-collections/{collection['id']}/items",
        headers=bearer(admin_tokens),
        json={"asset_ids": [asset_a["id"], asset_b["id"]]},
    )
    assert resp.status_code == 200, resp.text
    items = resp.json()["data"]["items"]
    assert [i["position"] for i in items] == [1, 2]

    # Reorder via replace-set.
    resp = await client.put(
        f"/api/v1/asset-collections/{collection['id']}/items",
        headers=bearer(admin_tokens),
        json={"asset_ids": [asset_b["id"], asset_a["id"]]},
    )
    assert [i["asset_id"] for i in resp.json()["data"]["items"]] == [
        asset_b["id"],
        asset_a["id"],
    ]

    # Duplicate assets rejected.
    resp = await client.put(
        f"/api/v1/asset-collections/{collection['id']}/items",
        headers=bearer(admin_tokens),
        json={"asset_ids": [asset_a["id"], asset_a["id"]]},
    )
    assert resp.status_code == 400

    # Reuse into a playlist.
    resp = await client.post(
        "/api/v1/playlists", headers=bearer(admin_tokens), json={"name": "Coll PL"}
    )
    playlist = resp.json()["data"]
    resp = await client.post(
        f"/api/v1/asset-collections/{collection['id']}/add-to-playlist",
        headers=bearer(admin_tokens),
        json={"playlist_id": playlist["id"]},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["items"] == 2

    resp = await client.get(
        f"/api/v1/playlists/{playlist['id']}", headers=bearer(admin_tokens)
    )
    playlist_items = resp.json()["data"]["items"]
    assert [i["asset_id"] for i in playlist_items] == [asset_b["id"], asset_a["id"]]


async def test_studio_permissions_and_isolation(client, admin_tokens, org_b):  # noqa: F811
    widget = await make_widget(client, admin_tokens, name="Iso Widget")
    template = await make_template(client, admin_tokens, name="Iso Template")

    # Viewer: read widgets yes, manage no.
    resp = await client.get("/api/v1/roles", headers=bearer(admin_tokens))
    viewer_id = next(r["id"] for r in resp.json()["data"] if r["name"] == "Viewer")
    await client.post(
        "/api/v1/users",
        headers=bearer(admin_tokens),
        json={
            "email": "studio-viewer@demo-org.com",
            "full_name": "Studio Viewer",
            "password": "Viewer@12345",
            "role_ids": [viewer_id],
        },
    )
    viewer = await login(client, "studio-viewer@demo-org.com", "Viewer@12345")
    assert (await client.get("/api/v1/widgets", headers=bearer(viewer))).status_code == 200
    resp = await client.post(
        "/api/v1/widgets",
        headers=bearer(viewer),
        json={"type": "clock", "name": "Nope", "config_schema_json": CLOCK_SCHEMA},
    )
    assert resp.status_code == 403

    # Cross-tenant 404s.
    b_tokens = await login(client, "admin@org-b-corp.com", "BAdmin@12345")
    resp = await client.patch(
        f"/api/v1/widgets/{widget['id']}", headers=bearer(b_tokens), json={"name": "steal"}
    )
    assert resp.status_code == 404
    resp = await client.post(
        f"/api/v1/templates/{template['id']}/submit", headers=bearer(b_tokens), json={}
    )
    assert resp.status_code == 404
