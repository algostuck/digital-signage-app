"""Phase-2 reporting tests (P2-RPT-001..004, SRS §8 acceptance #6)."""

import csv
import datetime as dt
import io
import zipfile

from tests.conftest import bearer, login
from tests.test_device_ops_api import assign_location, enroll_with
from tests.test_devices_api import device_headers
from tests.test_publishing_api import publish, ready_campaign
from tests.test_tenant_isolation import org_b  # noqa: F401 (fixture)


async def send_playback(client, device_id, token, campaign_id, asset_id, results):
    now = dt.datetime.now(dt.UTC)
    events = [
        {
            "type": "playback",
            "campaign_id": campaign_id,
            "asset_id": asset_id,
            "started_at": (now - dt.timedelta(minutes=i + 1)).isoformat(),
            "ended_at": (now - dt.timedelta(minutes=i)).isoformat(),
            "result": result,
        }
        for i, result in enumerate(results)
    ]
    resp = await client.post(
        f"/api/v1/player/{device_id}/events",
        headers=device_headers(token),
        json={"events": events},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["stored_playback"] == len(results)


async def seed_playback(client, admin_tokens):
    """Two located devices, one campaign, seven playback events (5 completed)."""
    dev_a, tok_a = await enroll_with(client, admin_tokens, "SN-RPT-A")
    dev_b, tok_b = await enroll_with(client, admin_tokens, "SN-RPT-B")
    await assign_location(client, admin_tokens, dev_a, "Kolkata")
    await assign_location(client, admin_tokens, dev_b, "Salt Lake Store")
    campaign = await ready_campaign(
        client, admin_tokens, device_ids=[dev_a, dev_b], name="PoP Campaign"
    )
    await publish(client, admin_tokens, campaign["id"])

    resp = await client.get(
        f"/api/v1/campaigns/{campaign['id']}", headers=bearer(admin_tokens)
    )
    playlist_id = resp.json()["data"]["playlist_id"]
    resp = await client.get(
        f"/api/v1/playlists/{playlist_id}", headers=bearer(admin_tokens)
    )
    asset_id = resp.json()["data"]["items"][0]["asset_id"]

    await send_playback(
        client, dev_a, tok_a, campaign["id"], asset_id,
        ["completed", "completed", "completed", "error"],
    )
    await send_playback(
        client, dev_b, tok_b, campaign["id"], asset_id, ["completed", "completed", "skipped"]
    )
    return campaign, (dev_a, dev_b), asset_id


async def test_proof_of_play_dimensions_and_reconciliation(client, admin_tokens):
    campaign, (dev_a, dev_b), asset_id = await seed_playback(client, admin_tokens)

    resp = await client.get(
        "/api/v1/reports/proof-of-play?group_by=campaign", headers=bearer(admin_tokens)
    )
    assert resp.status_code == 200, resp.text
    row = next(r for r in resp.json()["data"] if r["key_id"] == campaign["id"])
    assert row["name"] == "PoP Campaign"
    assert row["plays"] == 7
    assert row["completed"] == 5
    assert row["devices_reached"] == 2
    assert 0 < row["completion_rate"] < 1

    # By device: per-device execution counts.
    resp = await client.get(
        "/api/v1/reports/proof-of-play?group_by=device", headers=bearer(admin_tokens)
    )
    by_device = {r["key_id"]: r for r in resp.json()["data"]}
    assert by_device[dev_a]["plays"] == 4 and by_device[dev_b]["plays"] == 3

    # By location, filtered to the Kolkata subtree: both devices roll up
    # under their own locations; the subtree filter keeps both (Salt Lake
    # Store is inside Kolkata).
    resp = await client.get(
        "/api/v1/locations?q=Kolkata", headers=bearer(admin_tokens)
    )
    kolkata_id = resp.json()["data"][0]["id"]
    resp = await client.get(
        f"/api/v1/reports/proof-of-play?group_by=location&location_id={kolkata_id}",
        headers=bearer(admin_tokens),
    )
    location_rows = resp.json()["data"]
    assert sum(r["plays"] for r in location_rows) == 7  # reconciles with raw events

    # By asset.
    resp = await client.get(
        "/api/v1/reports/proof-of-play?group_by=asset", headers=bearer(admin_tokens)
    )
    assert any(r["key_id"] == asset_id and r["plays"] == 7 for r in resp.json()["data"])

    # Campaign filter + bad dimension.
    resp = await client.get(
        f"/api/v1/reports/proof-of-play?campaign_id={campaign['id']}",
        headers=bearer(admin_tokens),
    )
    assert sum(r["plays"] for r in resp.json()["data"]) == 7
    resp = await client.get(
        "/api/v1/reports/proof-of-play?group_by=weekday", headers=bearer(admin_tokens)
    )
    assert resp.status_code == 400


async def test_campaign_performance_merges_delivery_and_playback(client, admin_tokens):
    campaign, _, _ = await seed_playback(client, admin_tokens)
    resp = await client.get(
        "/api/v1/reports/campaign-performance", headers=bearer(admin_tokens)
    )
    assert resp.status_code == 200, resp.text
    row = next(r for r in resp.json()["data"] if r["campaign_id"] == campaign["id"])
    assert row["plays"] == 7
    assert row["completed_plays"] == 5
    assert row["devices_played"] == 2
    # Delivery KPI comes from the publish fan-out (2 target devices).
    assert row["acknowledged"] + row["pending"] + row["failed"] == 2


async def test_device_uptime_heartbeat_windows(client, admin_tokens, db_session):
    from sqlalchemy import select

    from app.models import Device, DeviceHeartbeat

    device_id, token = await enroll_with(client, admin_tokens, "SN-RPT-UP")
    base = dt.datetime.now(dt.UTC) - dt.timedelta(hours=1)
    for offset in (0, 100, 1000):  # gaps: 100s (kept), 900s (capped at 300)
        db_session.add(
            DeviceHeartbeat(
                device_id=(
                    await db_session.execute(
                        select(Device.id).where(Device.serial_no == "SN-RPT-UP")
                    )
                ).scalar_one(),
                observed_at=base + dt.timedelta(seconds=offset),
            )
        )
    await db_session.commit()

    yesterday = (dt.date.today() - dt.timedelta(days=1)).isoformat()
    today = dt.date.today().isoformat()
    resp = await client.get(
        f"/api/v1/reports/device-uptime?date_from={yesterday}&date_to={today}",
        headers=bearer(admin_tokens),
    )
    assert resp.status_code == 200, resp.text
    row = next(r for r in resp.json()["data"] if r["device_id"] == device_id)
    # 100 + min(900, 300) + trailing min(~3600-1000, 300) = 700 seconds.
    assert row["heartbeats"] == 3
    assert row["covered_seconds"] == 700
    assert 0 < row["uptime_pct"] < 100

    resp = await client.get(
        f"/api/v1/reports/device-uptime?date_from={today}&date_to={yesterday}",
        headers=bearer(admin_tokens),
    )
    assert resp.status_code == 400


async def test_export_csv_reconciles(client, admin_tokens):
    campaign, _, _ = await seed_playback(client, admin_tokens)
    resp = await client.post(
        "/api/v1/reports/export",
        headers=bearer(admin_tokens),
        json={"report": "proof-of-play", "format": "csv",
              "filters": {"group_by": "campaign"}},
    )
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("text/csv")
    assert "proof-of-play" in resp.headers["content-disposition"]
    text = resp.content.decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(text)))
    row = next(r for r in rows if r["key_id"] == campaign["id"])
    assert int(row["plays"]) == 7 and int(row["completed"]) == 5  # acceptance #6

    # Export is audited.
    resp = await client.get("/api/v1/audit-logs?page_size=20", headers=bearer(admin_tokens))
    assert any(r["action"] == "REPORT_EXPORTED" for r in resp.json()["data"])


async def test_export_xlsx_is_valid_package(client, admin_tokens):
    await seed_playback(client, admin_tokens)
    resp = await client.post(
        "/api/v1/reports/export",
        headers=bearer(admin_tokens),
        json={"report": "campaign-performance", "format": "xlsx"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.content[:2] == b"PK"
    archive = zipfile.ZipFile(io.BytesIO(resp.content))
    names = set(archive.namelist())
    assert {"[Content_Types].xml", "xl/workbook.xml", "xl/worksheets/sheet1.xml"} <= names
    sheet = archive.read("xl/worksheets/sheet1.xml").decode()
    assert "PoP Campaign" in sheet
    assert "campaign_name" in sheet  # header row


async def test_export_validation_and_other_reports(client, admin_tokens):
    for bad in [
        {"report": "nope", "format": "csv"},
        {"report": "deployments", "format": "pdf"},
        {"report": "playback", "format": "csv", "filters": {"date_from": "not-a-date"}},
        {"report": "playback", "format": "csv", "filters": []},
    ]:
        resp = await client.post(
            "/api/v1/reports/export", headers=bearer(admin_tokens), json=bad
        )
        assert resp.status_code == 400, bad

    # Every catalogue report exports without error (empty data included).
    for report in ("deployments", "playback", "locations", "device-uptime"):
        resp = await client.post(
            "/api/v1/reports/export",
            headers=bearer(admin_tokens),
            json={"report": report, "format": "csv"},
        )
        assert resp.status_code == 200, report


async def test_reports_rbac_and_isolation(client, admin_tokens, org_b):  # noqa: F811
    await seed_playback(client, admin_tokens)

    # Viewer: view yes, export no (reports.export missing).
    resp = await client.get("/api/v1/roles", headers=bearer(admin_tokens))
    roles = resp.json()["data"]
    viewer_id = next(r["id"] for r in roles if r["name"] == "Viewer")
    manager_id = next(r["id"] for r in roles if r["name"] == "Content Manager")
    await client.post(
        "/api/v1/users",
        headers=bearer(admin_tokens),
        json={
            "email": "rpt-viewer@demo-org.com",
            "full_name": "Report Viewer",
            "password": "Viewer@12345",
            "role_ids": [viewer_id],
        },
    )
    await client.post(
        "/api/v1/users",
        headers=bearer(admin_tokens),
        json={
            "email": "rpt-manager@demo-org.com",
            "full_name": "Report Manager",
            "password": "Manager@12345",
            "role_ids": [manager_id],
        },
    )
    viewer = await login(client, "rpt-viewer@demo-org.com", "Viewer@12345")
    manager = await login(client, "rpt-manager@demo-org.com", "Manager@12345")
    assert (
        await client.get("/api/v1/reports/proof-of-play", headers=bearer(viewer))
    ).status_code == 200
    resp = await client.post(
        "/api/v1/reports/export",
        headers=bearer(viewer),
        json={"report": "playback", "format": "csv"},
    )
    assert resp.status_code == 403
    resp = await client.post(
        "/api/v1/reports/export",
        headers=bearer(manager),
        json={"report": "playback", "format": "csv"},
    )
    assert resp.status_code == 200  # Content Manager holds reports.export

    # Org B sees no org-A playback.
    b_tokens = await login(client, "admin@org-b-corp.com", "BAdmin@12345")
    resp = await client.get(
        "/api/v1/reports/proof-of-play", headers=bearer(b_tokens)
    )
    assert resp.json()["data"] == []
