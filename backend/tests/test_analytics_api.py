"""Phase-3 slice 3D-2: analytics platform — idempotent daily aggregates,
reconciliation vs raw, semantic metrics, scheduled data exports."""

import datetime as dt

from tests.conftest import bearer, login
from tests.test_devices_api import device_headers, enroll_active_device
from tests.test_publishing_api import publish, ready_campaign
from tests.test_reports_phase2_api import send_playback
from tests.test_tenant_isolation import org_b  # noqa: F401 (fixture)


async def seed_playback_today(client, admin_tokens, *, serial, name, plays=5, failed=2):
    device_id, token = await enroll_active_device(client, admin_tokens, serial)
    campaign = await ready_campaign(client, admin_tokens, device_ids=[device_id], name=name)
    await publish(client, admin_tokens, campaign["id"])
    resp = await client.get(
        f"/api/v1/player/{device_id}/manifest", headers=device_headers(token)
    )
    asset_id = resp.json()["data"]["assets"][0]["id"]
    await send_playback(
        client, device_id, token, campaign["id"], asset_id,
        ["completed"] * plays + ["failed"] * failed,
    )
    return device_id, campaign


async def test_aggregates_idempotent_and_reconciled(client, admin_tokens, db_session):
    from app.services import analytics

    await seed_playback_today(
        client, admin_tokens, serial="SN-AGG-1", name="Agg One", plays=5, failed=2
    )
    today = dt.datetime.now(dt.UTC).date()

    result = await analytics.aggregate_daily(db_session, for_date=today)
    await db_session.commit()
    assert result["rows"] >= 3  # org + campaign + device + asset rows

    # Idempotent: recompute overwrites, row count stable.
    again = await analytics.aggregate_daily(db_session, for_date=today)
    await db_session.commit()
    assert again["rows"] == result["rows"]

    resp = await client.get(
        f"/api/v1/analytics/aggregates?dimension_type=campaign"
        f"&date_from={today}&date_to={today}",
        headers=bearer(admin_tokens),
    )
    rows = resp.json()["data"]
    mine = next(r for r in rows if r["plays"] == 7)
    assert mine["completed"] == 5
    assert mine["completion_rate_pct"] == 71.4
    assert mine["devices"] == 1

    resp = await client.get(
        f"/api/v1/analytics/reconciliation?date={today}", headers=bearer(admin_tokens)
    )
    recon = resp.json()["data"]
    assert recon["consistent"] is True
    assert recon["raw_plays"] == recon["aggregated_plays"] == 7

    # Semantic metrics are exposed from the single source.
    resp = await client.get("/api/v1/analytics/metrics", headers=bearer(admin_tokens))
    assert "completion_rate_pct" in resp.json()["data"]


async def test_late_events_self_heal(client, admin_tokens, db_session):
    from app.services import analytics

    device_id, campaign = await seed_playback_today(
        client, admin_tokens, serial="SN-AGG-LATE", name="Agg Late", plays=2, failed=0
    )
    today = dt.datetime.now(dt.UTC).date()
    await analytics.aggregate_daily(db_session, for_date=today)
    await db_session.commit()

    # A late event arrives after aggregation…
    from sqlalchemy import select

    from app.models import Device

    token_resp = await client.get(
        f"/api/v1/analytics/reconciliation?date={today}", headers=bearer(admin_tokens)
    )
    before = token_resp.json()["data"]
    assert before["consistent"] is True

    from app.models import PlaybackEvent

    org_id = (
        await db_session.execute(
            select(Device.organization_id).where(Device.id.in_([device_id]))
        )
    ).scalar_one()
    db_session.add(
        PlaybackEvent(
            organization_id=org_id,
            device_id=device_id,
            campaign_id=campaign["id"],
            started_at=dt.datetime.now(dt.UTC),
            result="completed",
        )
    )
    await db_session.commit()

    resp = await client.get(
        f"/api/v1/analytics/reconciliation?date={today}", headers=bearer(admin_tokens)
    )
    assert resp.json()["data"]["consistent"] is False  # drift detected…

    await analytics.aggregate_daily(db_session, for_date=today)  # …and healed
    await db_session.commit()
    resp = await client.get(
        f"/api/v1/analytics/reconciliation?date={today}", headers=bearer(admin_tokens)
    )
    assert resp.json()["data"]["consistent"] is True


async def test_data_export_lifecycle(client, admin_tokens, db_session):
    await seed_playback_today(
        client, admin_tokens, serial="SN-EXP-DS", name="Export DS", plays=3, failed=0
    )
    resp = await client.post(
        "/api/v1/data-exports",
        headers=bearer(admin_tokens),
        json={"name": "Nightly playback", "dataset": "playback_events"},
    )
    assert resp.status_code == 201, resp.text
    export = resp.json()["data"]
    assert export["state"] == "idle"

    # Unknown dataset refused; duplicate name conflicts.
    resp = await client.post(
        "/api/v1/data-exports",
        headers=bearer(admin_tokens),
        json={"name": "Bad", "dataset": "users"},
    )
    assert resp.status_code == 400
    resp = await client.post(
        "/api/v1/data-exports",
        headers=bearer(admin_tokens),
        json={"name": "Nightly playback", "dataset": "playback_events"},
    )
    assert resp.status_code == 409

    # Manual run writes a CSV to the storage adapter (today has the data —
    # the scheduled window is yesterday, so pass today via the service).
    import uuid as uuid_mod

    from sqlalchemy import select

    from app.models import Organization
    from app.services import analytics

    org_id = (
        await db_session.execute(
            select(Organization.id).where(Organization.code == "demo")
        )
    ).scalar_one()
    run = await analytics.run_export(
        db_session, org_id, uuid_mod.UUID(export["id"]),
        for_date=dt.datetime.now(dt.UTC).date(),
    )
    await db_session.commit()
    assert run.state == "idle"
    assert run.last_object_key and run.last_object_key.startswith("exports/")

    from app.integrations.storage import get_storage

    content = get_storage().read(run.last_object_key)
    assert b"started_at" in content and b"device_id" in content

    resp = await client.get("/api/v1/data-exports", headers=bearer(admin_tokens))
    row = resp.json()["data"][0]
    assert row["last_run_at"] is not None

    resp = await client.delete(
        f"/api/v1/data-exports/{export['id']}", headers=bearer(admin_tokens)
    )
    assert resp.status_code == 200


async def test_analytics_rbac_and_isolation(client, admin_tokens, org_b):  # noqa: F811
    b_tokens = await login(client, "admin@org-b-corp.com", "BAdmin@12345")
    today = dt.datetime.now(dt.UTC).date()
    resp = await client.get(
        f"/api/v1/analytics/aggregates?dimension_type=org&date_from={today}&date_to={today}",
        headers=bearer(b_tokens),
    )
    assert resp.json()["data"] == []

    resp = await client.get("/api/v1/roles", headers=bearer(admin_tokens))
    viewer_id = next(r["id"] for r in resp.json()["data"] if r["name"] == "Viewer")
    await client.post(
        "/api/v1/users",
        headers=bearer(admin_tokens),
        json={"email": "an-viewer@demo-org.com", "full_name": "Analytics Viewer",
              "password": "Viewer@12345", "role_ids": [viewer_id]},
    )
    viewer = await login(client, "an-viewer@demo-org.com", "Viewer@12345")
    resp = await client.post(
        "/api/v1/data-exports", headers=bearer(viewer),
        json={"name": "Nope", "dataset": "playback_events"},
    )
    assert resp.status_code == 403  # reports.export not held by Viewer