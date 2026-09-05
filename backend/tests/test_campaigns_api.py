"""Campaign (minimal) + schedule API tests (FR-CMP subset, FR-SCH-001..007)."""

from tests.conftest import bearer
from tests.test_playlists_api import create_playlist


async def create_campaign(client, tokens, name="Diwali Campaign", **extra) -> dict:
    resp = await client.post(
        "/api/v1/campaigns", headers=bearer(tokens), json={"name": name, **extra}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


async def test_campaign_crud(client, admin_tokens):
    playlist = await create_playlist(client, admin_tokens, name="Campaign PL")
    campaign = await create_campaign(
        client, admin_tokens, playlist_id=playlist["id"], priority=70
    )
    assert campaign["status"] == "draft"
    assert campaign["priority"] == 70
    assert campaign["playlist_id"] == playlist["id"]

    resp = await client.patch(
        f"/api/v1/campaigns/{campaign['id']}",
        headers=bearer(admin_tokens),
        json={"priority": 90, "description": "Festival push"},
    )
    assert resp.json()["data"]["priority"] == 90

    resp = await client.delete(
        f"/api/v1/campaigns/{campaign['id']}", headers=bearer(admin_tokens)
    )
    assert resp.json()["data"]["status"] == "archived"
    resp = await client.get("/api/v1/campaigns?page_size=200", headers=bearer(admin_tokens))
    assert campaign["id"] not in [c["id"] for c in resp.json()["data"]]
    resp = await client.post(
        f"/api/v1/campaigns/{campaign['id']}/restore", headers=bearer(admin_tokens)
    )
    assert resp.json()["data"]["status"] == "draft"


async def test_campaign_unknown_playlist_rejected(client, admin_tokens):
    resp = await client.post(
        "/api/v1/campaigns",
        headers=bearer(admin_tokens),
        json={"name": "Bad", "playlist_id": "11111111-1111-1111-1111-111111111111"},
    )
    assert resp.status_code == 404


async def test_schedule_crud_and_validation(client, admin_tokens):
    campaign = await create_campaign(client, admin_tokens, name="Sched Campaign")

    resp = await client.post(
        "/api/v1/schedules",
        headers=bearer(admin_tokens),
        json={
            "campaign_id": campaign["id"],
            "name": "Business hours",
            "start_date": "2026-09-01",
            "end_date": "2026-09-30",
            "start_time": "09:00:00",
            "end_time": "18:00:00",
            "days_of_week": [0, 1, 2, 3, 4],
            "timezone": "Asia/Kolkata",
            "priority": 60,
        },
    )
    assert resp.status_code == 201, resp.text
    schedule = resp.json()["data"]
    assert schedule["expired"] is False

    # end before start
    resp = await client.post(
        "/api/v1/schedules",
        headers=bearer(admin_tokens),
        json={
            "campaign_id": campaign["id"],
            "start_date": "2026-09-30",
            "end_date": "2026-09-01",
        },
    )
    assert resp.status_code == 400

    # invalid weekday
    resp = await client.post(
        "/api/v1/schedules",
        headers=bearer(admin_tokens),
        json={"campaign_id": campaign["id"], "days_of_week": [7]},
    )
    assert resp.status_code == 400

    # invalid timezone
    resp = await client.post(
        "/api/v1/schedules",
        headers=bearer(admin_tokens),
        json={"campaign_id": campaign["id"], "timezone": "Mars/Colony"},
    )
    assert resp.status_code == 400

    # update + list + delete
    resp = await client.patch(
        f"/api/v1/schedules/{schedule['id']}",
        headers=bearer(admin_tokens),
        json={"priority": 80, "end_date": "2026-10-15"},
    )
    assert resp.json()["data"]["priority"] == 80

    resp = await client.get(
        f"/api/v1/schedules?campaign_id={campaign['id']}", headers=bearer(admin_tokens)
    )
    assert len(resp.json()["data"]) == 1

    resp = await client.delete(
        f"/api/v1/schedules/{schedule['id']}", headers=bearer(admin_tokens)
    )
    assert resp.status_code == 200
    resp = await client.get(
        f"/api/v1/schedules?campaign_id={campaign['id']}", headers=bearer(admin_tokens)
    )
    assert resp.json()["data"] == []


async def test_schedule_requires_own_campaign(client, admin_tokens):
    resp = await client.post(
        "/api/v1/schedules",
        headers=bearer(admin_tokens),
        json={"campaign_id": "11111111-1111-1111-1111-111111111111"},
    )
    assert resp.status_code == 404


async def test_expired_flag(client, admin_tokens):
    campaign = await create_campaign(client, admin_tokens, name="Old Campaign")
    resp = await client.post(
        "/api/v1/schedules",
        headers=bearer(admin_tokens),
        json={"campaign_id": campaign["id"], "end_date": "2020-01-01"},
    )
    assert resp.json()["data"]["expired"] is True


async def test_calendar_endpoint(client, admin_tokens):
    from tests.test_device_ops_api import enroll_with

    device_id, _ = await enroll_with(client, admin_tokens, "SN-CALBASIC")
    a = await create_campaign(client, admin_tokens, name="Cal A", priority=50)
    b = await create_campaign(client, admin_tokens, name="Cal B", priority=50)
    for campaign, (start, end) in ((a, ("09:00", "12:00")), (b, ("11:00", "14:00"))):
        resp = await client.post(
            f"/api/v1/campaigns/{campaign['id']}/targets",
            headers=bearer(admin_tokens),
            json={"targets": [{"target_type": "device", "target_id": device_id}]},
        )
        assert resp.status_code == 200
        resp = await client.post(
            "/api/v1/schedules",
            headers=bearer(admin_tokens),
            json={
                "campaign_id": campaign["id"],
                "start_time": start,
                "end_time": end,
                "start_date": "2026-09-07",
                "end_date": "2026-09-08",
            },
        )
        assert resp.status_code == 201

    resp = await client.get(
        "/api/v1/calendar?from=2026-09-07&to=2026-09-08", headers=bearer(admin_tokens)
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data["events"]) == 4  # 2 schedules x 2 days
    # Equal priority on a shared screen, grouped across both days — but both
    # campaigns are drafts, so it is low severity and not actionable.
    ours = [c for c in data["conflicts"] if c["campaigns"][0]["campaign_id"] in (a["id"], b["id"])]
    assert len(ours) == 1
    assert ours[0]["reason"] == "equal_priority_shared_screens"
    assert ours[0]["severity"] == "low"
    assert ours[0]["dates"]["count"] == 2
    assert data["conflict_count"] == 0
    assert all(e["conflict_ids"] == [ours[0]["id"]] for e in data["events"])
    assert all(not e["conflict"] for e in data["events"])
    assert data["timezone"] and data["now"]["date"]
    assert data["events"][0]["recurrence_text"] == "Every day from 7 Sep to 8 Sep"
    assert data["events"][0]["screens"] == 1

    # Range validation
    resp = await client.get(
        "/api/v1/calendar?from=2026-09-08&to=2026-09-07", headers=bearer(admin_tokens)
    )
    assert resp.status_code == 400
    resp = await client.get(
        "/api/v1/calendar?from=2026-01-01&to=2026-12-31", headers=bearer(admin_tokens)
    )
    assert resp.status_code == 400


async def test_rbac_viewer_read_only(client, admin_tokens):
    from tests.conftest import login

    campaign = await create_campaign(client, admin_tokens, name="RBAC Campaign")
    resp = await client.get("/api/v1/roles", headers=bearer(admin_tokens))
    viewer_id = next(r["id"] for r in resp.json()["data"] if r["name"] == "Viewer")
    await client.post(
        "/api/v1/users",
        headers=bearer(admin_tokens),
        json={
            "email": "sviewer@demo-org.com",
            "full_name": "Schedule Viewer",
            "password": "Viewer@12345",
            "role_ids": [viewer_id],
        },
    )
    viewer = await login(client, "sviewer@demo-org.com", "Viewer@12345")

    resp = await client.get("/api/v1/campaigns", headers=bearer(viewer))
    assert resp.status_code == 200
    resp = await client.get(
        "/api/v1/calendar?from=2026-09-07&to=2026-09-08", headers=bearer(viewer)
    )
    assert resp.status_code == 200
    resp = await client.post(
        "/api/v1/schedules",
        headers=bearer(viewer),
        json={"campaign_id": campaign["id"]},
    )
    assert resp.status_code == 403
