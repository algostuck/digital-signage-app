"""Layout engine tests (FR-LYT-001..008)."""

from tests.conftest import bearer
from tests.test_content_api import upload_asset


async def create_layout(client, tokens, name="My Layout", **extra) -> dict:
    resp = await client.post(
        "/api/v1/layouts", headers=bearer(tokens), json={"name": name, **extra}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


async def test_create_layout_default_canvas(client, admin_tokens):
    layout = await create_layout(client, admin_tokens)
    assert layout["status"] == "draft"
    canvas = layout["draft_canvas_json"]
    assert canvas["schema_version"] == 1
    assert canvas["canvas"]["width"] == 1920
    assert len(canvas["zones"]) == 1
    assert canvas["zones"][0]["key"] == "zone-1"


async def test_save_draft_canvas(client, admin_tokens):
    layout = await create_layout(client, admin_tokens)
    canvas = {
        "schema_version": 1,
        "canvas": {"width": 1920, "height": 1080, "orientation": "landscape"},
        "zones": [
            {"key": "main", "name": "Main", "x": 0, "y": 0, "width": 1280, "height": 1080},
            {
                "key": "side",
                "name": "Sidebar",
                "x": 1280,
                "y": 0,
                "width": 640,
                "height": 1080,
                "z_index": 2,
                "content_type": "text",
                "content_config": {"text": "Hello"},
            },
        ],
    }
    resp = await client.patch(
        f"/api/v1/layouts/{layout['id']}",
        headers=bearer(admin_tokens),
        json={"canvas_json": canvas},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["zone_count"] == 2
    assert data["draft_canvas_json"]["zones"][1]["content_config"]["text"] == "Hello"


async def test_invalid_canvas_rejected(client, admin_tokens):
    layout = await create_layout(client, admin_tokens)

    def canvas_with_zones(zones):
        return {
            "schema_version": 1,
            "canvas": {"width": 1920, "height": 1080},
            "zones": zones,
        }

    # Duplicate keys
    resp = await client.patch(
        f"/api/v1/layouts/{layout['id']}",
        headers=bearer(admin_tokens),
        json={
            "canvas_json": canvas_with_zones(
                [
                    {"key": "a", "x": 0, "y": 0, "width": 100, "height": 100},
                    {"key": "a", "x": 100, "y": 0, "width": 100, "height": 100},
                ]
            )
        },
    )
    assert resp.status_code == 400

    # Negative coordinates
    resp = await client.patch(
        f"/api/v1/layouts/{layout['id']}",
        headers=bearer(admin_tokens),
        json={
            "canvas_json": canvas_with_zones(
                [{"key": "a", "x": -5, "y": 0, "width": 100, "height": 100}]
            )
        },
    )
    assert resp.status_code == 400

    # Unknown content type
    resp = await client.patch(
        f"/api/v1/layouts/{layout['id']}",
        headers=bearer(admin_tokens),
        json={
            "canvas_json": canvas_with_zones(
                [
                    {
                        "key": "a",
                        "x": 0,
                        "y": 0,
                        "width": 100,
                        "height": 100,
                        "content_type": "hologram",
                    }
                ]
            )
        },
    )
    assert resp.status_code == 400


async def test_publish_creates_immutable_versions(client, admin_tokens):
    layout = await create_layout(client, admin_tokens)

    resp = await client.post(
        f"/api/v1/layouts/{layout['id']}/publish", headers=bearer(admin_tokens)
    )
    assert resp.status_code == 200
    published = resp.json()["data"]
    assert published["status"] == "published"
    assert published["current_version_no"] == 1

    # Change the draft and publish again -> v2; v1 remains.
    canvas = published["draft_canvas_json"]
    canvas["zones"][0]["width"] = 960
    canvas["zones"].append(
        {"key": "zone-2", "name": "Right", "x": 960, "y": 0, "width": 960, "height": 1080}
    )
    await client.patch(
        f"/api/v1/layouts/{layout['id']}",
        headers=bearer(admin_tokens),
        json={"canvas_json": canvas},
    )
    resp = await client.post(
        f"/api/v1/layouts/{layout['id']}/publish", headers=bearer(admin_tokens)
    )
    assert resp.json()["data"]["current_version_no"] == 2

    resp = await client.get(
        f"/api/v1/layouts/{layout['id']}/versions", headers=bearer(admin_tokens)
    )
    assert [v["version_no"] for v in resp.json()["data"]] == [1, 2]


async def test_publish_validates_asset_bindings(client, admin_tokens):
    layout = await create_layout(client, admin_tokens)
    canvas = {
        "schema_version": 1,
        "canvas": {"width": 1920, "height": 1080},
        "zones": [
            {
                "key": "img",
                "x": 0,
                "y": 0,
                "width": 1920,
                "height": 1080,
                "content_type": "image",
                "content_config": {"asset_id": "11111111-1111-1111-1111-111111111111"},
            }
        ],
    }
    await client.patch(
        f"/api/v1/layouts/{layout['id']}",
        headers=bearer(admin_tokens),
        json={"canvas_json": canvas},
    )
    resp = await client.post(
        f"/api/v1/layouts/{layout['id']}/publish", headers=bearer(admin_tokens)
    )
    assert resp.status_code == 422  # unknown asset

    # Bind a real READY asset and publish successfully.
    asset = await upload_asset(client, admin_tokens, name="Layout BG")
    canvas["zones"][0]["content_config"]["asset_id"] = asset["id"]
    await client.patch(
        f"/api/v1/layouts/{layout['id']}",
        headers=bearer(admin_tokens),
        json={"canvas_json": canvas},
    )
    resp = await client.post(
        f"/api/v1/layouts/{layout['id']}/publish", headers=bearer(admin_tokens)
    )
    assert resp.status_code == 200


async def test_preview_returns_normalized_canvas(client, admin_tokens):
    layout = await create_layout(client, admin_tokens)
    resp = await client.post(
        f"/api/v1/layouts/{layout['id']}/preview", headers=bearer(admin_tokens)
    )
    assert resp.status_code == 200
    canvas = resp.json()["data"]
    assert canvas["schema_version"] == 1
    assert canvas["zones"][0]["content_type"] == "placeholder"


async def test_archive_and_restore(client, admin_tokens):
    layout = await create_layout(client, admin_tokens)
    resp = await client.delete(f"/api/v1/layouts/{layout['id']}", headers=bearer(admin_tokens))
    assert resp.json()["data"]["status"] == "archived"

    # Archived layouts are hidden and locked.
    resp = await client.get("/api/v1/layouts?page_size=200", headers=bearer(admin_tokens))
    assert layout["id"] not in [item["id"] for item in resp.json()["data"]]
    resp = await client.patch(
        f"/api/v1/layouts/{layout['id']}",
        headers=bearer(admin_tokens),
        json={"name": "Nope"},
    )
    assert resp.status_code == 422

    resp = await client.post(
        f"/api/v1/layouts/{layout['id']}/restore", headers=bearer(admin_tokens)
    )
    assert resp.json()["data"]["status"] == "draft"


async def test_templates_seeded_and_clone(client, admin_tokens):
    resp = await client.get("/api/v1/templates", headers=bearer(admin_tokens))
    names = {t["name"] for t in resp.json()["data"]}
    assert {"Fullscreen", "Two Zone Split", "Media with Ticker"} <= names
    ticker_template = next(
        t for t in resp.json()["data"] if t["name"] == "Media with Ticker"
    )

    resp = await client.post(
        f"/api/v1/templates/{ticker_template['id']}/clone",
        headers=bearer(admin_tokens),
        json={"name": "Store Front Screen"},
    )
    assert resp.status_code == 201
    layout = resp.json()["data"]
    assert layout["zone_count"] == 2
    assert layout["draft_canvas_json"]["zones"][1]["content_type"] == "ticker"


async def test_create_template_from_layout(client, admin_tokens):
    layout = await create_layout(client, admin_tokens, name="Template Source")
    resp = await client.post(
        "/api/v1/templates",
        headers=bearer(admin_tokens),
        json={"layout_id": layout["id"], "name": "My Custom Template"},
    )
    assert resp.status_code == 201

    resp = await client.post(
        "/api/v1/templates",
        headers=bearer(admin_tokens),
        json={"layout_id": layout["id"], "name": "My Custom Template"},
    )
    assert resp.status_code == 409


async def test_create_layout_from_template(client, admin_tokens):
    resp = await client.get("/api/v1/templates", headers=bearer(admin_tokens))
    split = next(t for t in resp.json()["data"] if t["name"] == "Two Zone Split")
    layout = await create_layout(
        client, admin_tokens, name="From Template", template_id=split["id"]
    )
    assert layout["zone_count"] == 2


async def test_rbac_viewer_read_only(client, admin_tokens):
    from tests.conftest import login

    resp = await client.get("/api/v1/roles", headers=bearer(admin_tokens))
    viewer_id = next(r["id"] for r in resp.json()["data"] if r["name"] == "Viewer")
    await client.post(
        "/api/v1/users",
        headers=bearer(admin_tokens),
        json={
            "email": "lviewer@demo-org.com",
            "full_name": "Layout Viewer",
            "password": "Viewer@12345",
            "role_ids": [viewer_id],
        },
    )
    viewer = await login(client, "lviewer@demo-org.com", "Viewer@12345")

    resp = await client.get("/api/v1/layouts", headers=bearer(viewer))
    assert resp.status_code == 200
    resp = await client.post(
        "/api/v1/layouts", headers=bearer(viewer), json={"name": "Nope"}
    )
    assert resp.status_code == 403
