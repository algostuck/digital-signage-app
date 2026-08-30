"""Playlist engine tests (FR-PLY-001..006)."""

from tests.conftest import bearer
from tests.test_content_api import upload_asset
from tests.test_layouts_api import create_layout


async def create_playlist(client, tokens, name="My Playlist", **extra) -> dict:
    resp = await client.post(
        "/api/v1/playlists", headers=bearer(tokens), json={"name": name, **extra}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


async def published_layout(client, tokens, name="PL Layout") -> dict:
    layout = await create_layout(client, tokens, name=name)
    resp = await client.post(f"/api/v1/layouts/{layout['id']}/publish", headers=bearer(tokens))
    assert resp.status_code == 200
    return resp.json()["data"]


async def test_create_and_list(client, admin_tokens):
    playlist = await create_playlist(client, admin_tokens, description="Morning loop")
    assert playlist["status"] == "draft"
    assert playlist["loop_enabled"] is True
    assert playlist["items"] == []

    resp = await client.get("/api/v1/playlists", headers=bearer(admin_tokens))
    assert any(p["id"] == playlist["id"] for p in resp.json()["data"])


async def test_add_items_and_ordering(client, admin_tokens):
    playlist = await create_playlist(client, admin_tokens)
    asset = await upload_asset(client, admin_tokens, name="Slide A")
    layout = await published_layout(client, admin_tokens)

    resp = await client.post(
        f"/api/v1/playlists/{playlist['id']}/items",
        headers=bearer(admin_tokens),
        json={"asset_id": asset["id"], "duration_ms": 5000},
    )
    assert resp.status_code == 201
    resp = await client.post(
        f"/api/v1/playlists/{playlist['id']}/items",
        headers=bearer(admin_tokens),
        json={"layout_id": layout["id"], "duration_ms": 10000},
    )
    data = resp.json()["data"]
    assert [i["position"] for i in data["items"]] == [1, 2]
    assert data["items"][0]["name"] == "Slide A"
    assert data["items"][0]["thumbnail_url"]
    assert data["items"][1]["name"] == layout["name"]
    assert data["total_duration_ms"] == 15000


async def test_item_reference_validation(client, admin_tokens):
    playlist = await create_playlist(client, admin_tokens)
    resp = await client.post(
        f"/api/v1/playlists/{playlist['id']}/items",
        headers=bearer(admin_tokens),
        json={},
    )
    assert resp.status_code == 400

    asset = await upload_asset(client, admin_tokens)
    layout = await published_layout(client, admin_tokens, name="Both Layout")
    resp = await client.post(
        f"/api/v1/playlists/{playlist['id']}/items",
        headers=bearer(admin_tokens),
        json={"asset_id": asset["id"], "layout_id": layout["id"]},
    )
    assert resp.status_code == 400

    resp = await client.post(
        f"/api/v1/playlists/{playlist['id']}/items",
        headers=bearer(admin_tokens),
        json={"asset_id": "11111111-1111-1111-1111-111111111111"},
    )
    assert resp.status_code == 404


async def test_reorder_via_position_patch(client, admin_tokens):
    playlist = await create_playlist(client, admin_tokens)
    names = ["One", "Two", "Three"]
    for name in names:
        asset = await upload_asset(client, admin_tokens, name=name)
        await client.post(
            f"/api/v1/playlists/{playlist['id']}/items",
            headers=bearer(admin_tokens),
            json={"asset_id": asset["id"], "duration_ms": 1000},
        )
    resp = await client.get(
        f"/api/v1/playlists/{playlist['id']}", headers=bearer(admin_tokens)
    )
    items = resp.json()["data"]["items"]
    assert [i["name"] for i in items] == names

    # Move "Three" to the front.
    third = items[2]
    resp = await client.patch(
        f"/api/v1/playlists/{playlist['id']}/items/{third['id']}",
        headers=bearer(admin_tokens),
        json={"position": 1},
    )
    reordered = resp.json()["data"]["items"]
    assert [i["name"] for i in reordered] == ["Three", "One", "Two"]
    assert [i["position"] for i in reordered] == [1, 2, 3]


async def test_replace_items_put(client, admin_tokens):
    playlist = await create_playlist(client, admin_tokens)
    a = await upload_asset(client, admin_tokens, name="A")
    b = await upload_asset(client, admin_tokens, name="B")

    resp = await client.put(
        f"/api/v1/playlists/{playlist['id']}/items",
        headers=bearer(admin_tokens),
        json={
            "items": [
                {"asset_id": b["id"], "duration_ms": 4000},
                {"asset_id": a["id"], "duration_ms": 6000},
            ]
        },
    )
    assert resp.status_code == 200
    items = resp.json()["data"]["items"]
    assert [i["name"] for i in items] == ["B", "A"]


async def test_remove_item_compacts_positions(client, admin_tokens):
    playlist = await create_playlist(client, admin_tokens)
    ids = []
    for name in ["X", "Y", "Z"]:
        asset = await upload_asset(client, admin_tokens, name=name)
        resp = await client.post(
            f"/api/v1/playlists/{playlist['id']}/items",
            headers=bearer(admin_tokens),
            json={"asset_id": asset["id"], "duration_ms": 1000},
        )
        ids = [i["id"] for i in resp.json()["data"]["items"]]

    resp = await client.delete(
        f"/api/v1/playlists/{playlist['id']}/items/{ids[1]}", headers=bearer(admin_tokens)
    )
    items = resp.json()["data"]["items"]
    assert [i["name"] for i in items] == ["X", "Z"]
    assert [i["position"] for i in items] == [1, 2]


async def test_publish_snapshot_and_versions(client, admin_tokens):
    playlist = await create_playlist(client, admin_tokens)
    asset = await upload_asset(client, admin_tokens, name="Pub Slide")
    layout = await published_layout(client, admin_tokens, name="Pub Layout")
    await client.post(
        f"/api/v1/playlists/{playlist['id']}/items",
        headers=bearer(admin_tokens),
        json={"asset_id": asset["id"], "duration_ms": 5000},
    )
    resp = await client.post(
        f"/api/v1/playlists/{playlist['id']}/items",
        headers=bearer(admin_tokens),
        json={"layout_id": layout["id"], "duration_ms": 7000},
    )
    # Disable the layout item: it must be excluded from the snapshot.
    layout_item = resp.json()["data"]["items"][1]
    await client.patch(
        f"/api/v1/playlists/{playlist['id']}/items/{layout_item['id']}",
        headers=bearer(admin_tokens),
        json={"enabled": False},
    )

    resp = await client.post(
        f"/api/v1/playlists/{playlist['id']}/publish", headers=bearer(admin_tokens)
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "published"
    assert data["current_version_no"] == 1

    # Re-enable and publish again -> v2 including the pinned layout version.
    await client.patch(
        f"/api/v1/playlists/{playlist['id']}/items/{layout_item['id']}",
        headers=bearer(admin_tokens),
        json={"enabled": True},
    )
    resp = await client.post(
        f"/api/v1/playlists/{playlist['id']}/publish", headers=bearer(admin_tokens)
    )
    assert resp.json()["data"]["current_version_no"] == 2

    resp = await client.get(
        f"/api/v1/playlists/{playlist['id']}/versions", headers=bearer(admin_tokens)
    )
    assert [v["version_no"] for v in resp.json()["data"]] == [1, 2]


async def test_publish_requires_enabled_items_and_durations(client, admin_tokens):
    playlist = await create_playlist(client, admin_tokens)
    resp = await client.post(
        f"/api/v1/playlists/{playlist['id']}/publish", headers=bearer(admin_tokens)
    )
    assert resp.status_code == 422  # empty

    # Image item without duration cannot publish.
    asset = await upload_asset(client, admin_tokens, name="No Duration")
    resp = await client.post(
        f"/api/v1/playlists/{playlist['id']}/items",
        headers=bearer(admin_tokens),
        json={"asset_id": asset["id"]},
    )
    item = resp.json()["data"]["items"][0]
    assert item["duration_ms"] == 8000  # image default applied
    await client.patch(
        f"/api/v1/playlists/{playlist['id']}/items/{item['id']}",
        headers=bearer(admin_tokens),
        json={"clear_duration": True},
    )
    resp = await client.post(
        f"/api/v1/playlists/{playlist['id']}/publish", headers=bearer(admin_tokens)
    )
    assert resp.status_code == 422


async def test_publish_requires_published_layout(client, admin_tokens):
    playlist = await create_playlist(client, admin_tokens)
    draft_layout = await create_layout(client, admin_tokens, name="Draft Only")
    await client.post(
        f"/api/v1/playlists/{playlist['id']}/items",
        headers=bearer(admin_tokens),
        json={"layout_id": draft_layout["id"], "duration_ms": 5000},
    )
    resp = await client.post(
        f"/api/v1/playlists/{playlist['id']}/publish", headers=bearer(admin_tokens)
    )
    assert resp.status_code == 422


async def test_fallback_rules(client, admin_tokens):
    a = await create_playlist(client, admin_tokens, name="FB-A")
    b = await create_playlist(client, admin_tokens, name="FB-B")

    resp = await client.patch(
        f"/api/v1/playlists/{a['id']}",
        headers=bearer(admin_tokens),
        json={"fallback_playlist_id": b["id"]},
    )
    assert resp.status_code == 200

    # Self-fallback rejected.
    resp = await client.patch(
        f"/api/v1/playlists/{b['id']}",
        headers=bearer(admin_tokens),
        json={"fallback_playlist_id": b["id"]},
    )
    assert resp.status_code == 422

    # Cycle A -> B -> A rejected.
    resp = await client.patch(
        f"/api/v1/playlists/{b['id']}",
        headers=bearer(admin_tokens),
        json={"fallback_playlist_id": a["id"]},
    )
    assert resp.status_code == 422

    # Clearing works.
    resp = await client.patch(
        f"/api/v1/playlists/{a['id']}",
        headers=bearer(admin_tokens),
        json={"clear_fallback": True},
    )
    assert resp.json()["data"]["fallback_playlist_id"] is None


async def test_archive_hides_and_locks(client, admin_tokens):
    playlist = await create_playlist(client, admin_tokens, name="Archive Me")
    resp = await client.delete(
        f"/api/v1/playlists/{playlist['id']}", headers=bearer(admin_tokens)
    )
    assert resp.json()["data"]["status"] == "archived"

    resp = await client.get("/api/v1/playlists?page_size=200", headers=bearer(admin_tokens))
    assert playlist["id"] not in [p["id"] for p in resp.json()["data"]]

    resp = await client.patch(
        f"/api/v1/playlists/{playlist['id']}",
        headers=bearer(admin_tokens),
        json={"name": "Nope"},
    )
    assert resp.status_code == 422

    resp = await client.post(
        f"/api/v1/playlists/{playlist['id']}/restore", headers=bearer(admin_tokens)
    )
    assert resp.json()["data"]["status"] == "draft"


async def test_rbac_viewer_read_only(client, admin_tokens):
    from tests.conftest import login

    resp = await client.get("/api/v1/roles", headers=bearer(admin_tokens))
    viewer_id = next(r["id"] for r in resp.json()["data"] if r["name"] == "Viewer")
    await client.post(
        "/api/v1/users",
        headers=bearer(admin_tokens),
        json={
            "email": "pviewer@demo-org.com",
            "full_name": "Playlist Viewer",
            "password": "Viewer@12345",
            "role_ids": [viewer_id],
        },
    )
    viewer = await login(client, "pviewer@demo-org.com", "Viewer@12345")
    resp = await client.get("/api/v1/playlists", headers=bearer(viewer))
    assert resp.status_code == 200
    resp = await client.post(
        "/api/v1/playlists", headers=bearer(viewer), json={"name": "Nope"}
    )
    assert resp.status_code == 403
