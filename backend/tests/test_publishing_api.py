"""Publishing engine tests (SRS §12, §14, M11/M12) + golden E2E (§20.2)."""

from tests.conftest import bearer
from tests.test_campaigns_api import create_campaign
from tests.test_content_api import upload_asset
from tests.test_devices_api import device_headers, enroll_active_device
from tests.test_playlists_api import create_playlist


async def make_published_playlist(client, tokens, name="Pub PL") -> dict:
    playlist = await create_playlist(client, tokens, name=name)
    asset = await upload_asset(client, tokens, name=f"{name} slide")
    await client.post(
        f"/api/v1/playlists/{playlist['id']}/items",
        headers=bearer(tokens),
        json={"asset_id": asset["id"], "duration_ms": 5000},
    )
    resp = await client.post(
        f"/api/v1/playlists/{playlist['id']}/publish", headers=bearer(tokens)
    )
    assert resp.status_code == 200
    return resp.json()["data"]


async def ready_campaign(
    client, tokens, *, device_ids, priority=50, name="Ready Campaign", schedule=None
):
    """Campaign with published playlist, always-on schedule, device targets,
    approved and ready to publish. `schedule` overrides the always-on window."""
    playlist = await make_published_playlist(client, tokens, name=f"{name} PL")
    campaign = await create_campaign(
        client, tokens, name=name, playlist_id=playlist["id"], priority=priority
    )
    await client.post(
        "/api/v1/schedules",
        headers=bearer(tokens),
        json={"campaign_id": campaign["id"], **(schedule or {})},
    )
    resp = await client.post(
        f"/api/v1/campaigns/{campaign['id']}/targets",
        headers=bearer(tokens),
        json={
            "targets": [
                {"target_type": "device", "target_id": device_id}
                for device_id in device_ids
            ]
        },
    )
    assert resp.status_code == 200
    await client.post(
        f"/api/v1/campaigns/{campaign['id']}/submit-approval", headers=bearer(tokens)
    )
    resp = await client.post(
        f"/api/v1/campaigns/{campaign['id']}/approve", headers=bearer(tokens)
    )
    assert resp.status_code == 200
    return campaign


async def publish(client, tokens, campaign_id) -> dict:
    resp = await client.post(
        f"/api/v1/campaigns/{campaign_id}/publish", headers=bearer(tokens)
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


async def test_targeting_location_subtree_group_tag_exclusion(client, admin_tokens):
    # Devices: one on Floor 1 (inside Kolkata subtree), one unassigned.
    dev_floor, _ = await enroll_active_device(client, admin_tokens, "SN-TGT-FLOOR")
    dev_free, _ = await enroll_active_device(client, admin_tokens, "SN-TGT-FREE")
    resp = await client.get("/api/v1/locations?q=Floor%201", headers=bearer(admin_tokens))
    floor_id = resp.json()["data"][0]["id"]
    resp = await client.get("/api/v1/locations?q=Kolkata", headers=bearer(admin_tokens))
    kolkata_id = resp.json()["data"][0]["id"]
    await client.post(
        f"/api/v1/devices/{dev_floor}/assign-location",
        headers=bearer(admin_tokens),
        json={"location_id": floor_id},
    )

    campaign = await create_campaign(client, admin_tokens, name="Target Test")

    async def effective(targets):
        resp = await client.post(
            f"/api/v1/campaigns/{campaign['id']}/targets",
            headers=bearer(admin_tokens),
            json={"targets": targets},
        )
        assert resp.status_code == 200
        resp = await client.get(
            f"/api/v1/campaigns/{campaign['id']}/effective-targets",
            headers=bearer(admin_tokens),
        )
        return {d["id"] for d in resp.json()["data"]}

    # Location subtree targeting reaches the floor device.
    devices = await effective(
        [{"target_type": "location", "target_id": kolkata_id, "include_descendants": True}]
    )
    assert dev_floor in devices and dev_free not in devices

    # Without descendants the floor device is missed.
    devices = await effective(
        [{"target_type": "location", "target_id": kolkata_id, "include_descendants": False}]
    )
    assert dev_floor not in devices

    # Group targeting.
    resp = await client.post(
        "/api/v1/device-groups", headers=bearer(admin_tokens), json={"name": "Target Group"}
    )
    group_id = resp.json()["data"]["id"]
    await client.post(
        f"/api/v1/device-groups/{group_id}/members",
        headers=bearer(admin_tokens),
        json={"device_ids": [dev_free]},
    )
    devices = await effective([{"target_type": "group", "target_id": group_id}])
    assert devices == {dev_free}

    # Tag targeting.
    await client.patch(
        f"/api/v1/devices/{dev_floor}",
        headers=bearer(admin_tokens),
        json={"tags": [{"key": "tier", "value": "gold"}]},
    )
    resp = await client.get("/api/v1/tags", headers=bearer(admin_tokens))
    tag_id = next(
        t["id"] for t in resp.json()["data"] if t["key"] == "tier" and t["value"] == "gold"
    )
    devices = await effective([{"target_type": "tag", "target_id": tag_id}])
    assert devices == {dev_floor}

    # Exclusion wins over inclusion (SRS §12.1).
    devices = await effective(
        [
            {"target_type": "location", "target_id": kolkata_id, "include_descendants": True},
            {"target_type": "device", "target_id": dev_free},
            {"target_type": "device", "target_id": dev_floor, "is_exclusion": True},
        ]
    )
    assert dev_floor not in devices and dev_free in devices

    # Decommissioned devices are filtered out.
    await client.post(
        f"/api/v1/devices/{dev_free}/decommission", headers=bearer(admin_tokens)
    )
    devices = await effective([{"target_type": "device", "target_id": dev_free}])
    assert devices == set()


async def test_approval_workflow_transitions(client, admin_tokens):
    campaign = await create_campaign(client, admin_tokens, name="Approval Flow")

    # Approve before submission is invalid.
    resp = await client.post(
        f"/api/v1/campaigns/{campaign['id']}/approve", headers=bearer(admin_tokens)
    )
    assert resp.status_code == 422

    resp = await client.post(
        f"/api/v1/campaigns/{campaign['id']}/submit-approval", headers=bearer(admin_tokens)
    )
    assert resp.json()["data"]["status"] == "pending_approval"

    resp = await client.post(
        f"/api/v1/campaigns/{campaign['id']}/reject", headers=bearer(admin_tokens)
    )
    assert resp.json()["data"]["status"] == "draft"

    await client.post(
        f"/api/v1/campaigns/{campaign['id']}/submit-approval", headers=bearer(admin_tokens)
    )
    resp = await client.post(
        f"/api/v1/campaigns/{campaign['id']}/approve", headers=bearer(admin_tokens)
    )
    assert resp.json()["data"]["status"] == "approved"


async def test_publish_validations(client, admin_tokens):
    device_id, _ = await enroll_active_device(client, admin_tokens, "SN-PUBVAL")

    # Unapproved campaign cannot publish.
    campaign = await create_campaign(client, admin_tokens, name="Unapproved")
    resp = await client.post(
        f"/api/v1/campaigns/{campaign['id']}/publish", headers=bearer(admin_tokens)
    )
    assert resp.status_code == 422

    # Approved but no schedules.
    playlist = await make_published_playlist(client, admin_tokens, name="Val PL")
    campaign = await create_campaign(
        client, admin_tokens, name="No Schedule", playlist_id=playlist["id"]
    )
    await client.post(
        f"/api/v1/campaigns/{campaign['id']}/targets",
        headers=bearer(admin_tokens),
        json={"targets": [{"target_type": "device", "target_id": device_id}]},
    )
    await client.post(
        f"/api/v1/campaigns/{campaign['id']}/submit-approval", headers=bearer(admin_tokens)
    )
    await client.post(
        f"/api/v1/campaigns/{campaign['id']}/approve", headers=bearer(admin_tokens)
    )
    resp = await client.post(
        f"/api/v1/campaigns/{campaign['id']}/publish", headers=bearer(admin_tokens)
    )
    assert resp.status_code == 422

    # With schedule but unpublished playlist.
    draft_playlist = await create_playlist(client, admin_tokens, name="Draft PL")
    campaign2 = await create_campaign(
        client, admin_tokens, name="Draft PL Campaign", playlist_id=draft_playlist["id"]
    )
    await client.post(
        "/api/v1/schedules", headers=bearer(admin_tokens), json={"campaign_id": campaign2["id"]}
    )
    await client.post(
        f"/api/v1/campaigns/{campaign2['id']}/targets",
        headers=bearer(admin_tokens),
        json={"targets": [{"target_type": "device", "target_id": device_id}]},
    )
    await client.post(
        f"/api/v1/campaigns/{campaign2['id']}/submit-approval", headers=bearer(admin_tokens)
    )
    await client.post(
        f"/api/v1/campaigns/{campaign2['id']}/approve", headers=bearer(admin_tokens)
    )
    resp = await client.post(
        f"/api/v1/campaigns/{campaign2['id']}/publish", headers=bearer(admin_tokens)
    )
    assert resp.status_code == 422

    # No resolvable targets.
    campaign3 = await ready_campaign(
        client, admin_tokens, device_ids=[device_id], name="Will Detarget"
    )
    await client.post(
        f"/api/v1/campaigns/{campaign3['id']}/targets",
        headers=bearer(admin_tokens),
        json={"targets": []},
    )
    resp = await client.post(
        f"/api/v1/campaigns/{campaign3['id']}/publish", headers=bearer(admin_tokens)
    )
    assert resp.status_code == 422


async def test_publish_ack_lifecycle_and_manifest(client, admin_tokens):
    dev_a, token_a = await enroll_active_device(client, admin_tokens, "SN-LIFE-A")
    dev_b, token_b = await enroll_active_device(client, admin_tokens, "SN-LIFE-B")
    campaign = await ready_campaign(
        client, admin_tokens, device_ids=[dev_a, dev_b], name="Lifecycle"
    )
    deployment = await publish(client, admin_tokens, campaign["id"])
    assert deployment["status"] == "publishing"
    assert deployment["total_devices"] == 2
    assert deployment["pending"] == 2

    # Heartbeat now signals sync_required.
    resp = await client.post(
        f"/api/v1/player/{dev_a}/heartbeat", headers=device_headers(token_a), json={}
    )
    assert resp.json()["data"]["sync_required"] is True

    # Manifest for device A.
    resp = await client.get(
        f"/api/v1/player/{dev_a}/manifest", headers=device_headers(token_a)
    )
    assert resp.status_code == 200
    manifest = resp.json()["data"]
    assert manifest["active_campaign"] == campaign["id"]
    assert manifest["campaign_active_now"] is True
    assert manifest["manifest_version"] == deployment["version"]
    assert manifest["playlist"]["items"][0]["duration_ms"] == 5000
    assert len(manifest["assets"]) == 1
    asset_entry = manifest["assets"][0]
    assert asset_entry["sha256"] and asset_entry["size"] > 0
    fetched = await client.get(asset_entry["url"])
    assert fetched.status_code == 200  # signed URL delivers bytes
    assert manifest["pending_deployments"] == [deployment["id"]]

    # Device A acks -> PARTIAL; B acks -> PUBLISHED.
    resp = await client.post(
        f"/api/v1/player/{dev_a}/deployments/{deployment['id']}/ack",
        headers=device_headers(token_a),
        json={"success": True},
    )
    assert resp.json()["data"]["status"] == "partial"
    resp = await client.post(
        f"/api/v1/player/{dev_b}/deployments/{deployment['id']}/ack",
        headers=device_headers(token_b),
        json={"success": True},
    )
    assert resp.json()["data"]["status"] == "published"

    # Idempotent re-ack after reconnect.
    resp = await client.post(
        f"/api/v1/player/{dev_a}/deployments/{deployment['id']}/ack",
        headers=device_headers(token_a),
        json={"success": True},
    )
    assert resp.status_code == 200

    # Heartbeat no longer requires sync.
    resp = await client.post(
        f"/api/v1/player/{dev_a}/heartbeat", headers=device_headers(token_a), json={}
    )
    assert resp.json()["data"]["sync_required"] is False


async def test_failed_ack_retry_and_cancel(client, admin_tokens):
    dev, token = await enroll_active_device(client, admin_tokens, "SN-FAIL")
    campaign = await ready_campaign(client, admin_tokens, device_ids=[dev], name="Fail Flow")
    deployment = await publish(client, admin_tokens, campaign["id"])

    resp = await client.post(
        f"/api/v1/player/{dev}/deployments/{deployment['id']}/ack",
        headers=device_headers(token),
        json={"success": False, "error": "disk full"},
    )
    assert resp.json()["data"]["status"] == "failed"

    resp = await client.get(
        f"/api/v1/deployments/{deployment['id']}/devices", headers=bearer(admin_tokens)
    )
    row = resp.json()["data"][0]
    assert row["status"] == "failed" and row["last_error"] == "disk full"

    # Retry resets to pending.
    resp = await client.post(
        f"/api/v1/deployments/{deployment['id']}/retry", headers=bearer(admin_tokens)
    )
    assert resp.json()["data"]["status"] == "publishing"
    assert resp.json()["data"]["pending"] == 1

    # Cancel closes it; further acks are rejected.
    resp = await client.post(
        f"/api/v1/deployments/{deployment['id']}/cancel", headers=bearer(admin_tokens)
    )
    assert resp.json()["data"]["status"] == "cancelled"
    resp = await client.post(
        f"/api/v1/player/{dev}/deployments/{deployment['id']}/ack",
        headers=device_headers(token),
        json={"success": True},
    )
    assert resp.status_code == 409


async def test_preview_manifest_matches_what_the_device_would_fetch(client, admin_tokens):
    """The operator preview must resolve content exactly as the player does,
    otherwise the preview lies about what is on the screen."""
    dev, token = await enroll_active_device(client, admin_tokens, "SN-PREVIEW")
    campaign = await ready_campaign(client, admin_tokens, device_ids=[dev], name="Previewable")
    await publish(client, admin_tokens, campaign["id"])

    resp = await client.get(
        f"/api/v1/devices/{dev}/preview-manifest", headers=bearer(admin_tokens)
    )
    assert resp.status_code == 200, resp.text
    preview = resp.json()["data"]
    resp = await client.get(f"/api/v1/player/{dev}/manifest", headers=device_headers(token))
    player = resp.json()["data"]

    # `generated_at` is the evaluation instant and the signed asset URLs carry
    # their own expiry, so both differ between two calls by construction.
    ignored = {"generated_at", "assets"}
    assert {k: v for k, v in preview.items() if k not in ignored} == {
        k: v for k, v in player.items() if k not in ignored
    }
    assert [a["sha256"] for a in preview["assets"]] == [a["sha256"] for a in player["assets"]]
    # The preview's URLs must actually serve bytes, not just look plausible.
    fetched = await client.get(preview["assets"][0]["url"])
    assert fetched.status_code == 200


async def test_preview_manifest_evaluates_schedules_at_a_chosen_instant(client, admin_tokens):
    """`at` is what makes 'what does this screen show at 7pm Saturday?'
    answerable on the server instead of re-deriving schedule rules in JS."""
    dev, _ = await enroll_active_device(client, admin_tokens, "SN-PREVIEW-AT")
    campaign = await ready_campaign(
        client,
        admin_tokens,
        device_ids=[dev],
        name="Evening Only",
        schedule={"start_time": "18:00", "end_time": "22:00", "timezone": "UTC"},
    )
    await publish(client, admin_tokens, campaign["id"])

    async def active_at(instant: str) -> bool:
        resp = await client.get(
            f"/api/v1/devices/{dev}/preview-manifest",
            headers=bearer(admin_tokens),
            params={"at": instant},
        )
        assert resp.status_code == 200, resp.text
        return resp.json()["data"]["campaign_active_now"]

    assert await active_at("2026-06-10T19:30:00+00:00") is True
    assert await active_at("2026-06-10T09:00:00+00:00") is False
    # Outside the window the campaign is still shipped (the player evaluates
    # windows locally, offline-first) — only the active flag changes.
    resp = await client.get(
        f"/api/v1/devices/{dev}/preview-manifest",
        headers=bearer(admin_tokens),
        params={"at": "2026-06-10T09:00:00+00:00"},
    )
    assert resp.json()["data"]["active_campaign"] == campaign["id"]


async def test_preview_manifest_requires_device_view_permission(client, admin_tokens):
    dev, _ = await enroll_active_device(client, admin_tokens, "SN-PREVIEW-AUTH")
    resp = await client.get(f"/api/v1/devices/{dev}/preview-manifest")
    assert resp.status_code == 401


async def test_republish_supersedes_previous_deployment(client, admin_tokens):
    dev, _ = await enroll_active_device(client, admin_tokens, "SN-SUPER")
    campaign = await ready_campaign(client, admin_tokens, device_ids=[dev], name="Supersede")
    first = await publish(client, admin_tokens, campaign["id"])
    second = await publish(client, admin_tokens, campaign["id"])
    assert second["version"] == first["version"] + 1

    resp = await client.get(
        f"/api/v1/deployments/{first['id']}", headers=bearer(admin_tokens)
    )
    assert resp.json()["data"]["status"] == "cancelled"


async def test_manifest_priority_and_pause(client, admin_tokens):
    dev, token = await enroll_active_device(client, admin_tokens, "SN-PRIO")
    low = await ready_campaign(
        client, admin_tokens, device_ids=[dev], priority=30, name="Low Prio"
    )
    high = await ready_campaign(
        client, admin_tokens, device_ids=[dev], priority=80, name="High Prio"
    )
    await publish(client, admin_tokens, low["id"])
    await publish(client, admin_tokens, high["id"])

    resp = await client.get(
        f"/api/v1/player/{dev}/manifest", headers=device_headers(token)
    )
    assert resp.json()["data"]["active_campaign"] == high["id"]

    # Pausing the high-priority campaign falls back to the low one.
    await client.post(f"/api/v1/campaigns/{high['id']}/pause", headers=bearer(admin_tokens))
    resp = await client.get(
        f"/api/v1/player/{dev}/manifest", headers=device_headers(token)
    )
    assert resp.json()["data"]["active_campaign"] == low["id"]

    await client.post(f"/api/v1/campaigns/{high['id']}/resume", headers=bearer(admin_tokens))
    resp = await client.get(
        f"/api/v1/player/{dev}/manifest", headers=device_headers(token)
    )
    assert resp.json()["data"]["active_campaign"] == high["id"]


async def test_deployments_are_tenant_isolated(client, admin_tokens):
    from tests.conftest import login
    from tests.test_tenant_isolation import org_b  # noqa: F401 (fixture reuse via param)

    dev, _ = await enroll_active_device(client, admin_tokens, "SN-DEPISO")
    campaign = await ready_campaign(client, admin_tokens, device_ids=[dev], name="Iso Deploy")
    deployment = await publish(client, admin_tokens, campaign["id"])

    # A viewer of the same org can read but not manage.
    resp = await client.get("/api/v1/roles", headers=bearer(admin_tokens))
    viewer_id = next(r["id"] for r in resp.json()["data"] if r["name"] == "Viewer")
    await client.post(
        "/api/v1/users",
        headers=bearer(admin_tokens),
        json={
            "email": "depviewer@demo-org.com",
            "full_name": "Deploy Viewer",
            "password": "Viewer@12345",
            "role_ids": [viewer_id],
        },
    )
    viewer = await login(client, "depviewer@demo-org.com", "Viewer@12345")
    resp = await client.get(
        f"/api/v1/deployments/{deployment['id']}", headers=bearer(viewer)
    )
    assert resp.status_code == 200
    resp = await client.post(
        f"/api/v1/deployments/{deployment['id']}/retry", headers=bearer(viewer)
    )
    assert resp.status_code == 403


async def test_golden_end_to_end(client, admin_tokens):
    """SRS §20.2 condensed: hierarchy -> devices -> content -> layout ->
    playlist -> campaign -> schedule -> publish -> manifest -> ack."""
    from tests.test_layouts_api import create_layout

    # A dedicated store under Kolkata (the seeded subtree also holds demo
    # devices, so target this fresh node's subtree for a deterministic set).
    resp = await client.get("/api/v1/locations?q=Kolkata", headers=bearer(admin_tokens))
    kolkata_id = resp.json()["data"][0]["id"]
    resp = await client.post(
        "/api/v1/locations",
        headers=bearer(admin_tokens),
        json={"name": "Golden Store", "parent_id": kolkata_id},
    )
    store_id = resp.json()["data"]["id"]

    devices = []
    for index in range(3):
        device_id, token = await enroll_active_device(
            client, admin_tokens, f"SN-GOLD-{index}"
        )
        await client.post(
            f"/api/v1/devices/{device_id}/assign-location",
            headers=bearer(admin_tokens),
            json={"location_id": store_id},
        )
        devices.append((device_id, token))

    # Content + 2-zone layout bound to the asset.
    asset = await upload_asset(client, admin_tokens, name="Golden Banner")
    layout = await create_layout(client, admin_tokens, name="Golden Layout")
    canvas = layout["draft_canvas_json"]
    canvas["zones"] = [
        {"key": "main", "x": 0, "y": 0, "width": 1920, "height": 960,
         "content_type": "image", "content_config": {"asset_id": asset["id"]}},
        {"key": "ticker", "x": 0, "y": 960, "width": 1920, "height": 120,
         "content_type": "ticker", "content_config": {"text": "Golden path"}},
    ]
    await client.patch(
        f"/api/v1/layouts/{layout['id']}",
        headers=bearer(admin_tokens),
        json={"canvas_json": canvas},
    )
    await client.post(f"/api/v1/layouts/{layout['id']}/publish", headers=bearer(admin_tokens))

    # Playlist with the layout + asset.
    playlist = await create_playlist(client, admin_tokens, name="Golden PL")
    await client.post(
        f"/api/v1/playlists/{playlist['id']}/items",
        headers=bearer(admin_tokens),
        json={"layout_id": layout["id"], "duration_ms": 15000},
    )
    await client.post(
        f"/api/v1/playlists/{playlist['id']}/items",
        headers=bearer(admin_tokens),
        json={"asset_id": asset["id"], "duration_ms": 8000},
    )
    await client.post(f"/api/v1/playlists/{playlist['id']}/publish", headers=bearer(admin_tokens))

    # Campaign targeting the Kolkata subtree, 09:00-18:00 Asia/Kolkata.
    campaign = await create_campaign(
        client, admin_tokens, name="Golden Campaign",
        playlist_id=playlist["id"], layout_id=layout["id"], priority=95,
    )
    await client.post(
        "/api/v1/schedules",
        headers=bearer(admin_tokens),
        json={
            "campaign_id": campaign["id"],
            "start_time": "00:00", "end_time": "23:59",
            "timezone": "Asia/Kolkata",
        },
    )
    await client.post(
        f"/api/v1/campaigns/{campaign['id']}/targets",
        headers=bearer(admin_tokens),
        json={
            "targets": [
                {"target_type": "location", "target_id": store_id, "include_descendants": True}
            ]
        },
    )
    await client.post(
        f"/api/v1/campaigns/{campaign['id']}/submit-approval", headers=bearer(admin_tokens)
    )
    await client.post(f"/api/v1/campaigns/{campaign['id']}/approve", headers=bearer(admin_tokens))
    deployment = await publish(client, admin_tokens, campaign["id"])
    assert deployment["total_devices"] == 3

    # Every simulated player syncs and acknowledges.
    for device_id, token in devices:
        resp = await client.get(
            f"/api/v1/player/{device_id}/manifest", headers=device_headers(token)
        )
        manifest = resp.json()["data"]
        assert manifest["active_campaign"] == campaign["id"]
        assert manifest["layout"]["canvas"]["zones"][1]["content_config"]["text"] == "Golden path"
        assert any(a["id"] == asset["id"] for a in manifest["assets"])
        for entry in manifest["assets"]:
            fetched = await client.get(entry["url"])
            assert fetched.status_code == 200
        resp = await client.post(
            f"/api/v1/player/{device_id}/deployments/{deployment['id']}/ack",
            headers=device_headers(token),
            json={"success": True},
        )
        assert resp.status_code == 200

    resp = await client.get(
        f"/api/v1/deployments/{deployment['id']}", headers=bearer(admin_tokens)
    )
    data = resp.json()["data"]
    assert data["acknowledged"] == data["total_devices"]
    assert data["status"] == "published"
