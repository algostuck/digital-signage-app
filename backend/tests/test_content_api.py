"""Content CMS tests (FR-CNT-001..008, FR-MED-001/002/003/006)."""

import io

from PIL import Image

from tests.conftest import bearer


def make_png(width=64, height=48, color=(200, 30, 30)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buffer, format="PNG")
    return buffer.getvalue()


async def upload_asset(
    client, tokens, *, filename="banner.png", mime="image/png", data: bytes | None = None,
    folder_id=None, name=None, asset_id=None,
) -> dict:
    data = data if data is not None else make_png()
    body = {
        "filename": filename,
        "mime_type": mime,
        "size_bytes": len(data),
        "folder_id": folder_id,
        "asset_id": asset_id,
        "name": name,
    }
    resp = await client.post("/api/v1/assets/uploads", headers=bearer(tokens), json=body)
    assert resp.status_code == 201, resp.text
    session = resp.json()["data"]

    put = await client.put(
        session["upload_url"], content=data, headers={"Content-Type": mime}
    )
    assert put.status_code == 200, put.text

    resp = await client.post(
        f"/api/v1/assets/uploads/{session['upload_session_id']}/complete",
        headers=bearer(tokens),
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


async def test_upload_image_end_to_end(client, admin_tokens):
    asset = await upload_asset(client, admin_tokens, name="Summer Banner")
    assert asset["name"] == "Summer Banner"
    assert asset["type"] == "image"
    assert asset["status"] == "draft"
    version = asset["current_version"]
    assert version["version_no"] == 1
    assert version["processing_status"] == "ready"
    assert version["width"] == 64 and version["height"] == 48
    assert version["checksum"] and asset["checksum"] == version["checksum"]
    assert asset["thumbnail_url"]  # image pipeline produced a thumbnail


async def test_upload_policy_rejects_bad_mime(client, admin_tokens):
    resp = await client.post(
        "/api/v1/assets/uploads",
        headers=bearer(admin_tokens),
        json={"filename": "x.exe", "mime_type": "application/x-msdownload", "size_bytes": 100},
    )
    assert resp.status_code == 400
    assert resp.json()["errors"][0]["field"] == "mime_type"


async def test_upload_policy_rejects_oversize(client, admin_tokens):
    resp = await client.post(
        "/api/v1/assets/uploads",
        headers=bearer(admin_tokens),
        json={
            "filename": "big.mp4",
            "mime_type": "video/mp4",
            "size_bytes": 600 * 1024 * 1024,
        },
    )
    assert resp.status_code == 400
    assert resp.json()["errors"][0]["field"] == "size_bytes"


async def test_complete_without_bytes_fails(client, admin_tokens):
    resp = await client.post(
        "/api/v1/assets/uploads",
        headers=bearer(admin_tokens),
        json={"filename": "ghost.png", "mime_type": "image/png", "size_bytes": 10},
    )
    session_id = resp.json()["data"]["upload_session_id"]
    resp = await client.post(
        f"/api/v1/assets/uploads/{session_id}/complete", headers=bearer(admin_tokens)
    )
    assert resp.status_code == 422


async def test_size_mismatch_marks_version_failed(client, admin_tokens):
    data = make_png()
    resp = await client.post(
        "/api/v1/assets/uploads",
        headers=bearer(admin_tokens),
        json={"filename": "lie.png", "mime_type": "image/png", "size_bytes": len(data) + 5},
    )
    session = resp.json()["data"]
    await client.put(session["upload_url"], content=data)
    resp = await client.post(
        f"/api/v1/assets/uploads/{session['upload_session_id']}/complete",
        headers=bearer(admin_tokens),
    )
    assert resp.status_code == 200
    version = resp.json()["data"]["current_version"]
    assert version["processing_status"] == "failed"
    assert "does not match" in version["processing_error"]


async def test_download_url_serves_bytes(client, admin_tokens):
    data = make_png(color=(0, 120, 200))
    asset = await upload_asset(client, admin_tokens, data=data)
    resp = await client.get(
        f"/api/v1/assets/{asset['id']}/download-url", headers=bearer(admin_tokens)
    )
    assert resp.status_code == 200
    url = resp.json()["data"]["url"]
    fetched = await client.get(url)
    assert fetched.status_code == 200
    assert fetched.content == data


async def test_download_url_bad_signature_rejected(client, admin_tokens):
    asset = await upload_asset(client, admin_tokens)
    resp = await client.get(
        f"/api/v1/assets/{asset['id']}/download-url", headers=bearer(admin_tokens)
    )
    url = resp.json()["data"]["url"]
    tampered = url.replace("sig=", "sig=00")
    fetched = await client.get(tampered)
    assert fetched.status_code == 403


async def test_new_version_flow(client, admin_tokens):
    asset = await upload_asset(client, admin_tokens, name="Versioned")
    v2_data = make_png(width=100, height=80)

    resp = await client.post(
        f"/api/v1/assets/{asset['id']}/versions",
        headers=bearer(admin_tokens),
        json={"filename": "v2.png", "mime_type": "image/png", "size_bytes": len(v2_data)},
    )
    assert resp.status_code == 201
    session = resp.json()["data"]
    assert session["version_no"] == 2

    await client.put(session["upload_url"], content=v2_data)
    resp = await client.post(
        f"/api/v1/assets/uploads/{session['upload_session_id']}/complete",
        headers=bearer(admin_tokens),
    )
    updated = resp.json()["data"]
    assert updated["current_version"]["version_no"] == 2
    assert updated["current_version"]["width"] == 100

    resp = await client.get(
        f"/api/v1/assets/{asset['id']}/versions", headers=bearer(admin_tokens)
    )
    assert [v["version_no"] for v in resp.json()["data"]] == [1, 2]


async def test_lifecycle_publish_archive_restore(client, admin_tokens):
    asset = await upload_asset(client, admin_tokens)

    resp = await client.post(
        f"/api/v1/assets/{asset['id']}/publish", headers=bearer(admin_tokens)
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "published"

    resp = await client.post(
        f"/api/v1/assets/{asset['id']}/archive", headers=bearer(admin_tokens)
    )
    assert resp.json()["data"]["status"] == "archived"

    # Archived assets are hidden from the default listing.
    resp = await client.get("/api/v1/assets?page_size=200", headers=bearer(admin_tokens))
    assert asset["id"] not in [a["id"] for a in resp.json()["data"]]

    resp = await client.post(
        f"/api/v1/assets/{asset['id']}/restore", headers=bearer(admin_tokens)
    )
    assert resp.json()["data"]["status"] == "draft"


async def test_publish_requires_ready_version(client, admin_tokens):
    data = make_png()
    resp = await client.post(
        "/api/v1/assets/uploads",
        headers=bearer(admin_tokens),
        json={"filename": "bad.png", "mime_type": "image/png", "size_bytes": len(data) + 1},
    )
    session = resp.json()["data"]
    await client.put(session["upload_url"], content=data)
    resp = await client.post(
        f"/api/v1/assets/uploads/{session['upload_session_id']}/complete",
        headers=bearer(admin_tokens),
    )
    asset_id = resp.json()["data"]["id"]

    resp = await client.post(
        f"/api/v1/assets/{asset_id}/publish", headers=bearer(admin_tokens)
    )
    assert resp.status_code == 422


async def test_asset_metadata_tags_and_search(client, admin_tokens):
    asset = await upload_asset(client, admin_tokens, name="Diwali Video Poster")
    resp = await client.patch(
        f"/api/v1/assets/{asset['id']}",
        headers=bearer(admin_tokens),
        json={
            "description": "Poster for the Diwali campaign",
            "tags": [{"key": "campaign", "value": "diwali"}],
        },
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["tags"][0]["value"] == "diwali"

    resp = await client.get("/api/v1/assets?q=diwali", headers=bearer(admin_tokens))
    assert any(a["id"] == asset["id"] for a in resp.json()["data"])

    resp = await client.get(
        "/api/v1/assets?tag_key=campaign&tag_value=diwali", headers=bearer(admin_tokens)
    )
    assert [a["id"] for a in resp.json()["data"]] == [asset["id"]]

    resp = await client.get("/api/v1/assets?type=video", headers=bearer(admin_tokens))
    assert asset["id"] not in [a["id"] for a in resp.json()["data"]]


async def test_folders_crud_and_archive_rules(client, admin_tokens):
    resp = await client.post(
        "/api/v1/folders", headers=bearer(admin_tokens), json={"name": "Campaigns"}
    )
    assert resp.status_code == 201
    folder = resp.json()["data"]

    resp = await client.post(
        "/api/v1/folders", headers=bearer(admin_tokens), json={"name": "Campaigns"}
    )
    assert resp.status_code == 409

    asset = await upload_asset(client, admin_tokens, folder_id=folder["id"])
    assert asset["folder_id"] == folder["id"]

    resp = await client.get(
        f"/api/v1/assets?folder_id={folder['id']}", headers=bearer(admin_tokens)
    )
    assert [a["id"] for a in resp.json()["data"]] == [asset["id"]]

    # Cannot archive a folder that still holds assets.
    resp = await client.delete(f"/api/v1/folders/{folder['id']}", headers=bearer(admin_tokens))
    assert resp.status_code == 422

    await client.post(f"/api/v1/assets/{asset['id']}/archive", headers=bearer(admin_tokens))
    resp = await client.delete(f"/api/v1/folders/{folder['id']}", headers=bearer(admin_tokens))
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "archived"


async def test_viewer_cannot_upload(client, admin_tokens):
    from tests.conftest import login

    resp = await client.get("/api/v1/roles", headers=bearer(admin_tokens))
    viewer_id = next(r["id"] for r in resp.json()["data"] if r["name"] == "Viewer")
    await client.post(
        "/api/v1/users",
        headers=bearer(admin_tokens),
        json={
            "email": "cviewer@demo-org.com",
            "full_name": "Content Viewer",
            "password": "Viewer@12345",
            "role_ids": [viewer_id],
        },
    )
    viewer = await login(client, "cviewer@demo-org.com", "Viewer@12345")

    resp = await client.get("/api/v1/assets", headers=bearer(viewer))
    assert resp.status_code == 200

    resp = await client.post(
        "/api/v1/assets/uploads",
        headers=bearer(viewer),
        json={"filename": "x.png", "mime_type": "image/png", "size_bytes": 10},
    )
    assert resp.status_code == 403
