"""Advanced campaigns + enterprise scheduling tests (P2-CAM-001/004,
P2-SCH-001/002/004, SRS §8 acceptance #4)."""

import datetime as dt

from tests.conftest import bearer, login
from tests.test_device_ops_api import assign_location, enroll_with
from tests.test_devices_api import device_headers
from tests.test_publishing_api import make_published_playlist, publish, ready_campaign
from tests.test_tenant_isolation import org_b  # noqa: F401 (fixture)


async def get_manifest(client, device_id, token) -> dict:
    resp = await client.get(
        f"/api/v1/player/{device_id}/manifest", headers=device_headers(token)
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


# --- recurrence engine unit coverage (P2-SCH-002) ---


def test_monthly_recurrence_and_exception_dates():
    from types import SimpleNamespace

    from app.services.scheduling import is_schedule_active

    def schedule(**kw):
        base = {
            "kind": "play",
            "start_date": None,
            "end_date": None,
            "start_time": None,
            "end_time": None,
            "days_of_week": None,
            "recurrence_json": None,
            "exception_dates_json": None,
            "timezone": None,
            "priority": 50,
        }
        base.update(kw)
        return SimpleNamespace(**base)

    at = dt.datetime(2026, 8, 15, 12, 0, tzinfo=dt.UTC)
    assert is_schedule_active(schedule(recurrence_json={"days_of_month": [15]}), at, "UTC")
    assert not is_schedule_active(
        schedule(recurrence_json={"days_of_month": [1, 31]}), at, "UTC"
    )
    # Exception date knocks out an otherwise-selected day.
    assert not is_schedule_active(
        schedule(exception_dates_json=["2026-08-15"]), at, "UTC"
    )
    # Exceptions are evaluated in the schedule's timezone.
    late_utc = dt.datetime(2026, 8, 15, 20, 0, tzinfo=dt.UTC)  # already Aug 16 in Kolkata
    assert is_schedule_active(
        schedule(exception_dates_json=["2026-08-15"], timezone="Asia/Kolkata"),
        late_utc,
        "UTC",
    )
    # Monthly + weekday combine (both must match).
    saturday = dt.datetime(2026, 8, 15, 12, 0, tzinfo=dt.UTC)  # 2026-08-15 is a Saturday
    assert is_schedule_active(
        schedule(recurrence_json={"days_of_month": [15]}, days_of_week=[5]), saturday, "UTC"
    )
    assert not is_schedule_active(
        schedule(recurrence_json={"days_of_month": [15]}, days_of_week=[0]), saturday, "UTC"
    )


async def test_blackout_suppresses_campaign(client, admin_tokens):
    """P2-CAM-004: an active blackout window suppresses an otherwise
    eligible campaign; removing it restores playback."""
    device_id, token = await enroll_with(client, admin_tokens, "SN-BLACKOUT")
    campaign = await ready_campaign(
        client, admin_tokens, device_ids=[device_id], name="Blackout Campaign"
    )
    await publish(client, admin_tokens, campaign["id"])
    manifest = await get_manifest(client, device_id, token)
    assert manifest["campaign_active_now"] is True

    resp = await client.post(
        "/api/v1/schedules",
        headers=bearer(admin_tokens),
        json={"campaign_id": campaign["id"], "kind": "blackout", "name": "Maintenance"},
    )
    assert resp.status_code == 201, resp.text
    blackout_id = resp.json()["data"]["id"]

    manifest = await get_manifest(client, device_id, token)
    assert manifest["campaign_active_now"] is False
    # The player still receives the blackout window to evaluate offline.
    kinds = {s["kind"] for s in manifest["schedules"]}
    assert kinds == {"play", "blackout"}

    await client.delete(f"/api/v1/schedules/{blackout_id}", headers=bearer(admin_tokens))
    manifest = await get_manifest(client, device_id, token)
    assert manifest["campaign_active_now"] is True


async def test_variant_overrides_creative_per_device(client, admin_tokens):
    """P2-CAM-001: location-targeted variant swaps the playlist for matching
    devices only; everyone else keeps the base creative."""
    kolkata_dev, kolkata_token = await enroll_with(client, admin_tokens, "SN-VAR-KOL")
    other_dev, other_token = await enroll_with(client, admin_tokens, "SN-VAR-OTH")
    kolkata_id = await assign_location(client, admin_tokens, kolkata_dev, "Kolkata")

    campaign = await ready_campaign(
        client, admin_tokens, device_ids=[kolkata_dev, other_dev], name="Variant Campaign"
    )
    variant_playlist = await make_published_playlist(
        client, admin_tokens, name="Kolkata Special"
    )
    resp = await client.post(
        f"/api/v1/campaigns/{campaign['id']}/variants",
        headers=bearer(admin_tokens),
        json={
            "name": "Kolkata creative",
            "playlist_id": variant_playlist["id"],
            "priority": 60,
            "targets": [
                {"target_type": "location", "target_id": kolkata_id, "include_descendants": True}
            ],
        },
    )
    assert resp.status_code == 201, resp.text
    detail = resp.json()["data"]
    assert len(detail["variants"]) == 1

    await publish(client, admin_tokens, campaign["id"])

    kolkata_manifest = await get_manifest(client, kolkata_dev, kolkata_token)
    assert kolkata_manifest["variant"]["name"] == "Kolkata creative"
    assert kolkata_manifest["playlist"]["id"] == variant_playlist["id"]

    other_manifest = await get_manifest(client, other_dev, other_token)
    assert other_manifest["variant"] is None
    assert other_manifest["playlist"]["id"] != variant_playlist["id"]

    # Deleting the variant restores the base creative.
    resp = await client.delete(
        f"/api/v1/campaigns/{campaign['id']}/variants/{detail['variants'][0]['id']}",
        headers=bearer(admin_tokens),
    )
    assert resp.status_code == 200
    kolkata_manifest = await get_manifest(client, kolkata_dev, kolkata_token)
    assert kolkata_manifest["variant"] is None


async def test_variant_validation(client, admin_tokens):
    device_id, _ = await enroll_with(client, admin_tokens, "SN-VAR-VAL")
    campaign = await ready_campaign(
        client, admin_tokens, device_ids=[device_id], name="Variant Val Campaign"
    )

    async def create(body):
        return await client.post(
            f"/api/v1/campaigns/{campaign['id']}/variants",
            headers=bearer(admin_tokens),
            json=body,
        )

    # No creative override at all.
    resp = await create(
        {"name": "empty", "targets": [{"target_type": "device", "target_id": device_id}]}
    )
    assert resp.status_code == 400
    # No targets (schema-level).
    playlist = await make_published_playlist(client, admin_tokens, name="VV PL")
    resp = await create({"name": "no targets", "playlist_id": playlist["id"], "targets": []})
    assert resp.status_code == 400
    # Valid, then duplicate name.
    body = {
        "name": "dup",
        "playlist_id": playlist["id"],
        "targets": [{"target_type": "device", "target_id": device_id}],
    }
    assert (await create(body)).status_code == 201
    assert (await create(body)).status_code == 400


async def test_targets_preview_does_not_persist(client, admin_tokens):
    device_a, _ = await enroll_with(client, admin_tokens, "SN-PREV-A")
    device_b, _ = await enroll_with(client, admin_tokens, "SN-PREV-B")
    campaign = await ready_campaign(
        client, admin_tokens, device_ids=[device_a], name="Preview Campaign"
    )
    resp = await client.post(
        f"/api/v1/campaigns/{campaign['id']}/targets/preview",
        headers=bearer(admin_tokens),
        json={
            "targets": [
                {"target_type": "device", "target_id": device_a},
                {"target_type": "device", "target_id": device_b},
                {"target_type": "device", "target_id": device_b, "is_exclusion": True},
            ]
        },
    )
    assert resp.status_code == 200, resp.text
    preview = resp.json()["data"]
    assert preview["count"] == 1  # exclusion wins over inclusion
    assert preview["sample"][0]["id"] == device_a

    # Saved targets are untouched (still just device_a from ready_campaign).
    resp = await client.get(
        f"/api/v1/campaigns/{campaign['id']}", headers=bearer(admin_tokens)
    )
    assert len(resp.json()["data"]["targets"]) == 1


async def test_conflict_dry_run_reports_winner(client, admin_tokens):
    """SRS §8 acceptance #4: overlapping campaigns -> conflict shown with the
    deterministic winner before anything is published."""
    device_id, _ = await enroll_with(client, admin_tokens, "SN-CONF")
    high = await ready_campaign(
        client, admin_tokens, device_ids=[device_id], priority=80, name="High Prio"
    )
    equal = await ready_campaign(
        client, admin_tokens, device_ids=[device_id], priority=50, name="Equal Prio"
    )

    async def check(campaign_id, priority_note=None):
        resp = await client.post(
            "/api/v1/schedules/conflicts",
            headers=bearer(admin_tokens),
            json={
                "campaign_id": campaign_id,
                "start_time": "09:00:00",
                "end_time": "17:00:00",
            },
        )
        assert resp.status_code == 200, resp.text
        return resp.json()["data"]

    # Proposed schedule on 'equal' (50) overlaps 'High Prio' (80, always-on)
    # and any other 50s. Overlap vs High Prio: deterministic, winner High.
    result = await check(equal["id"])
    against_high = [
        row
        for row in result["overlaps"]
        if any(c["campaign_name"] == "High Prio" for c in row["campaigns"])
    ]
    assert against_high, result
    assert all(row["winner_campaign_name"] == "High Prio" for row in against_high)
    assert all(row["conflict"] is False for row in against_high)

    # A proposal on the high-priority campaign overlapping 'Equal Prio' (50)
    # also resolves deterministically: High Prio's proposal wins.
    result_high = await check(high["id"])
    vs_equal = [
        row
        for row in result_high["overlaps"]
        if any(c["campaign_name"] == "Equal Prio" for c in row["campaigns"])
    ]
    assert vs_equal, result_high
    assert all(row["winner_campaign_name"] == "High Prio" for row in vs_equal)
    assert all(row["conflict"] is False for row in vs_equal)


async def test_conflict_dry_run_equal_priority_flags(client, admin_tokens):
    device_id, _ = await enroll_with(client, admin_tokens, "SN-CONF2")
    a = await ready_campaign(
        client, admin_tokens, device_ids=[device_id], priority=50, name="Same A"
    )
    await ready_campaign(client, admin_tokens, device_ids=[device_id], priority=50, name="Same B")
    resp = await client.post(
        "/api/v1/schedules/conflicts",
        headers=bearer(admin_tokens),
        json={"campaign_id": a["id"], "start_time": "10:00:00", "end_time": "12:00:00"},
    )
    data = resp.json()["data"]
    same_b_rows = [
        row
        for row in data["overlaps"]
        if any(c["campaign_name"] == "Same B" for c in row["campaigns"])
    ]
    assert same_b_rows, data
    assert all(row["conflict"] for row in same_b_rows)
    assert data["conflict_count"] >= len({row["date"] for row in same_b_rows})
    # Winner is still reported deterministically (newest campaign tie-break).
    assert all(row["winner_campaign_name"] in ("Same A", "Same B") for row in same_b_rows)


async def test_calendar_shows_blackouts_without_conflicts(client, admin_tokens):
    device_id, _ = await enroll_with(client, admin_tokens, "SN-CAL")
    campaign = await ready_campaign(
        client, admin_tokens, device_ids=[device_id], name="Calendar Campaign"
    )
    await client.post(
        "/api/v1/schedules",
        headers=bearer(admin_tokens),
        json={"campaign_id": campaign["id"], "kind": "blackout", "name": "CAL Blackout"},
    )
    today = dt.date.today()
    resp = await client.get(
        f"/api/v1/schedules/calendar?from={today}&to={today}", headers=bearer(admin_tokens)
    )
    assert resp.status_code == 200, resp.text
    events = resp.json()["data"]["events"]
    ours = [e for e in events if e["campaign_id"] == campaign["id"]]
    assert {e["kind"] for e in ours} == {"play", "blackout"}
    # Blackouts never register as conflicts.
    assert all(not e["conflict"] for e in ours if e["kind"] == "blackout")


async def test_schedule_field_validation(client, admin_tokens):
    device_id, _ = await enroll_with(client, admin_tokens, "SN-SVAL")
    campaign = await ready_campaign(
        client, admin_tokens, device_ids=[device_id], name="SVal Campaign"
    )

    async def create(extra):
        return await client.post(
            "/api/v1/schedules",
            headers=bearer(admin_tokens),
            json={"campaign_id": campaign["id"], **extra},
        )

    assert (await create({"recurrence_json": {"days_of_month": [0]}})).status_code == 400
    assert (await create({"recurrence_json": {"days_of_month": [32]}})).status_code == 400
    assert (await create({"recurrence_json": {"frequency": "lunar"}})).status_code == 400
    assert (await create({"exception_dates_json": ["not-a-date"]})).status_code == 400
    assert (await create({"kind": "eclipse"})).status_code == 400
    ok = await create(
        {
            "kind": "play",
            "recurrence_json": {"days_of_month": [1, 15]},
            "exception_dates_json": ["2026-12-25"],
        }
    )
    assert ok.status_code == 201, ok.text
    data = ok.json()["data"]
    assert data["recurrence_json"] == {"days_of_month": [1, 15]}
    assert data["exception_dates_json"] == ["2026-12-25"]


async def test_variant_isolation(client, admin_tokens, org_b):  # noqa: F811
    device_id, _ = await enroll_with(client, admin_tokens, "SN-VAR-ISO")
    campaign = await ready_campaign(
        client, admin_tokens, device_ids=[device_id], name="Iso Variant Campaign"
    )
    b_tokens = await login(client, "admin@org-b-corp.com", "BAdmin@12345")
    resp = await client.post(
        f"/api/v1/campaigns/{campaign['id']}/variants",
        headers=bearer(b_tokens),
        json={
            "name": "steal",
            "playlist_id": campaign["playlist_id"],
            "targets": [{"target_type": "device", "target_id": device_id}],
        },
    )
    assert resp.status_code == 404
    resp = await client.post(
        f"/api/v1/campaigns/{campaign['id']}/targets/preview",
        headers=bearer(b_tokens),
        json={"targets": [{"target_type": "device", "target_id": device_id}]},
    )
    assert resp.status_code == 404
