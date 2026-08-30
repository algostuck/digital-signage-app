"""Location hierarchy tests (FR-LOC-001..007)."""

from tests.conftest import bearer

H = None  # populated per-test via helpers


async def _types(client, tokens) -> dict[str, str]:
    resp = await client.get("/api/v1/location-types", headers=bearer(tokens))
    assert resp.status_code == 200
    return {t["code"]: t["id"] for t in resp.json()["data"]}


async def _create(client, tokens, name, parent_id=None, **extra) -> dict:
    resp = await client.post(
        "/api/v1/locations",
        headers=bearer(tokens),
        json={"name": name, "parent_id": parent_id, **extra},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


async def test_seeded_hierarchy_and_tree(client, admin_tokens):
    resp = await client.get("/api/v1/locations/tree", headers=bearer(admin_tokens))
    assert resp.status_code == 200
    tree = resp.json()["data"]
    india = next(r for r in tree if r["node"]["name"] == "India")
    assert india["node"]["depth"] == 0
    wb = india["children"][0]["node"]
    assert wb["name"] == "West Bengal"
    floor = india["children"][0]["children"][0]["children"][0]["children"][0]["node"]
    assert floor["name"] == "Floor 1"
    assert floor["depth"] == 4


async def test_create_deep_hierarchy(client, admin_tokens):
    types = await _types(client, admin_tokens)
    parent = None
    names = ["USA", "California", "Los Angeles", "Downtown", "Mall One", "Level 2", "Wing A"]
    for name in names:
        node = await _create(
            client, admin_tokens, name, parent, type_id=types.get("custom")
        )
        parent = node["id"]
    assert node["depth"] == len(names) - 1
    # Path encodes the full ancestry.
    assert node["path"].count("/") == len(names) + 1


async def test_location_detail_effective_timezone(client, admin_tokens):
    resp = await client.get(
        "/api/v1/locations?q=Floor%201", headers=bearer(admin_tokens)
    )
    floor_id = resp.json()["data"][0]["id"]
    resp = await client.get(f"/api/v1/locations/{floor_id}", headers=bearer(admin_tokens))
    assert resp.status_code == 200
    data = resp.json()["data"]
    # Floor has no tz; India (root ancestor) has Asia/Kolkata.
    assert data["effective_timezone"] == "Asia/Kolkata"
    assert data["children_count"] == 0


async def test_descendants_and_children(client, admin_tokens):
    resp = await client.get("/api/v1/locations?q=India", headers=bearer(admin_tokens))
    india_id = resp.json()["data"][0]["id"]

    resp = await client.get(
        f"/api/v1/locations/{india_id}/descendants", headers=bearer(admin_tokens)
    )
    names = {n["name"] for n in resp.json()["data"]}
    assert {"West Bengal", "Kolkata", "Salt Lake Store", "Floor 1"} <= names

    resp = await client.get(
        f"/api/v1/locations/{india_id}/children", headers=bearer(admin_tokens)
    )
    child_names = [n["name"] for n in resp.json()["data"]]
    assert child_names == ["West Bengal"]


async def test_move_rewrites_subtree_paths(client, admin_tokens):
    a = await _create(client, admin_tokens, "Region A")
    b = await _create(client, admin_tokens, "Region B")
    child = await _create(client, admin_tokens, "Child", a["id"])
    grandchild = await _create(client, admin_tokens, "Grandchild", child["id"])

    resp = await client.post(
        f"/api/v1/locations/{child['id']}/move",
        headers=bearer(admin_tokens),
        json={"new_parent_id": b["id"]},
    )
    assert resp.status_code == 200
    moved = resp.json()["data"]
    assert moved["parent_id"] == b["id"]
    assert moved["path"].startswith(b["path"])

    resp = await client.get(
        f"/api/v1/locations/{grandchild['id']}", headers=bearer(admin_tokens)
    )
    assert resp.json()["data"]["path"].startswith(moved["path"])


async def test_move_into_own_subtree_rejected(client, admin_tokens):
    a = await _create(client, admin_tokens, "Cycle Root")
    b = await _create(client, admin_tokens, "Cycle Child", a["id"])

    resp = await client.post(
        f"/api/v1/locations/{a['id']}/move",
        headers=bearer(admin_tokens),
        json={"new_parent_id": b["id"]},
    )
    assert resp.status_code == 422

    resp = await client.post(
        f"/api/v1/locations/{a['id']}/move",
        headers=bearer(admin_tokens),
        json={"new_parent_id": a["id"]},
    )
    assert resp.status_code == 422


async def test_move_to_root(client, admin_tokens):
    a = await _create(client, admin_tokens, "Parent X")
    b = await _create(client, admin_tokens, "Child X", a["id"])
    resp = await client.post(
        f"/api/v1/locations/{b['id']}/move",
        headers=bearer(admin_tokens),
        json={"new_parent_id": None},
    )
    assert resp.status_code == 200
    moved = resp.json()["data"]
    assert moved["parent_id"] is None
    assert moved["depth"] == 0


async def test_archive_requires_no_active_children(client, admin_tokens):
    a = await _create(client, admin_tokens, "Archive Root")
    b = await _create(client, admin_tokens, "Archive Child", a["id"])

    resp = await client.delete(f"/api/v1/locations/{a['id']}", headers=bearer(admin_tokens))
    assert resp.status_code == 422

    resp = await client.delete(f"/api/v1/locations/{b['id']}", headers=bearer(admin_tokens))
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "archived"

    resp = await client.delete(f"/api/v1/locations/{a['id']}", headers=bearer(admin_tokens))
    assert resp.status_code == 200

    # Restoring the child requires restoring the parent first.
    resp = await client.post(
        f"/api/v1/locations/{b['id']}/restore", headers=bearer(admin_tokens)
    )
    assert resp.status_code == 422
    resp = await client.post(
        f"/api/v1/locations/{a['id']}/restore", headers=bearer(admin_tokens)
    )
    assert resp.status_code == 200
    resp = await client.post(
        f"/api/v1/locations/{b['id']}/restore", headers=bearer(admin_tokens)
    )
    assert resp.status_code == 200


async def test_archived_nodes_excluded_from_tree(client, admin_tokens):
    node = await _create(client, admin_tokens, "Ephemeral")
    await client.delete(f"/api/v1/locations/{node['id']}", headers=bearer(admin_tokens))
    resp = await client.get("/api/v1/locations/tree", headers=bearer(admin_tokens))
    names = [r["node"]["name"] for r in resp.json()["data"]]
    assert "Ephemeral" not in names


async def test_sibling_code_conflict(client, admin_tokens):
    parent = await _create(client, admin_tokens, "Code Parent")
    await _create(client, admin_tokens, "First", parent["id"], code="S1")
    resp = await client.post(
        "/api/v1/locations",
        headers=bearer(admin_tokens),
        json={"name": "Second", "parent_id": parent["id"], "code": "S1"},
    )
    assert resp.status_code == 409


async def test_tags_replace_set(client, admin_tokens):
    node = await _create(client, admin_tokens, "Tagged Store")
    resp = await client.post(
        f"/api/v1/locations/{node['id']}/tags",
        headers=bearer(admin_tokens),
        json={"tags": [{"key": "tier", "value": "premium"}, {"key": "env", "value": "mall"}]},
    )
    assert resp.status_code == 200
    tags = {(t["key"], t["value"]) for t in resp.json()["data"]["tags"]}
    assert tags == {("tier", "premium"), ("env", "mall")}

    resp = await client.post(
        f"/api/v1/locations/{node['id']}/tags",
        headers=bearer(admin_tokens),
        json={"tags": [{"key": "tier", "value": "standard"}]},
    )
    tags = {(t["key"], t["value"]) for t in resp.json()["data"]["tags"]}
    assert tags == {("tier", "standard")}

    resp = await client.get("/api/v1/tags", headers=bearer(admin_tokens))
    all_tags = {(t["key"], t["value"]) for t in resp.json()["data"]}
    assert ("tier", "premium") in all_tags  # dictionary keeps historical tags


async def test_invalid_location_timezone_rejected(client, admin_tokens):
    resp = await client.post(
        "/api/v1/locations",
        headers=bearer(admin_tokens),
        json={"name": "Bad TZ", "timezone": "Not/AZone"},
    )
    assert resp.status_code == 400


async def test_location_type_crud(client, admin_tokens):
    resp = await client.post(
        "/api/v1/location-types",
        headers=bearer(admin_tokens),
        json={"code": "kiosk", "name": "Kiosk"},
    )
    assert resp.status_code == 201
    resp = await client.post(
        "/api/v1/location-types",
        headers=bearer(admin_tokens),
        json={"code": "kiosk", "name": "Duplicate"},
    )
    assert resp.status_code == 409
