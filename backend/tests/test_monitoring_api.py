"""Fleet health & thresholds tests (P2-MON-001/002/004, SRS §8 acceptance #5
threshold variant)."""

import datetime as dt

from sqlalchemy import select, update

from tests.conftest import bearer, login
from tests.test_device_ops_api import assign_location, enroll_with
from tests.test_devices_api import device_headers
from tests.test_tenant_isolation import org_b  # noqa: F401 (fixture)


async def heartbeat(client, device_id, token, **extra):
    resp = await client.post(
        f"/api/v1/player/{device_id}/heartbeat",
        headers=device_headers(token),
        json={"status": "online", **extra},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


def test_connection_status_honors_tenant_thresholds():
    from types import SimpleNamespace

    from app.services.devices import connection_status

    now = dt.datetime.now(dt.UTC)
    device = SimpleNamespace(
        status="active", last_heartbeat_at=now - dt.timedelta(seconds=120)
    )
    assert connection_status(device, now) == "online"  # default warning is higher
    assert (
        connection_status(device, now, {"warning_after_seconds": 60,
                                        "offline_after_seconds": 100})
        == "offline"
    )
    assert (
        connection_status(device, now, {"warning_after_seconds": 60,
                                        "offline_after_seconds": 300})
        == "warning"
    )


def test_version_ordering():
    from app.services.monitoring import is_version_outdated

    assert is_version_outdated("1.9.0", "2.0.0")
    assert not is_version_outdated("2.0.0", "2.0.0")
    assert not is_version_outdated("2.10.0", "2.9.0")  # numeric, not lexical
    assert not is_version_outdated(None, "2.0.0")  # unknown never flagged
    assert not is_version_outdated("1.0.0", None)


async def test_thresholds_get_put_validation(client, admin_tokens):
    resp = await client.get("/api/v1/monitoring/thresholds", headers=bearer(admin_tokens))
    assert resp.status_code == 200
    defaults = resp.json()["data"]
    assert defaults["storage_alert_percent"] == 90
    assert defaults["min_player_version"] is None

    resp = await client.put(
        "/api/v1/monitoring/thresholds",
        headers=bearer(admin_tokens),
        json={"storage_alert_percent": 80, "min_player_version": "2.5.0"},
    )
    assert resp.status_code == 200, resp.text
    updated = resp.json()["data"]
    assert updated["storage_alert_percent"] == 80
    assert updated["min_player_version"] == "2.5.0"
    # Untouched keys keep platform defaults.
    assert updated["offline_after_seconds"] == defaults["offline_after_seconds"]

    for bad in [
        {"nonsense": 1},
        {"storage_alert_percent": 30},
        {"offline_after_seconds": 5},
        {"warning_after_seconds": 600, "offline_after_seconds": 300},
    ]:
        resp = await client.put(
            "/api/v1/monitoring/thresholds", headers=bearer(admin_tokens), json=bad
        )
        assert resp.status_code == 400, bad

    # Viewer: read yes, write no.
    resp = await client.get("/api/v1/roles", headers=bearer(admin_tokens))
    viewer_id = next(r["id"] for r in resp.json()["data"] if r["name"] == "Viewer")
    await client.post(
        "/api/v1/users",
        headers=bearer(admin_tokens),
        json={
            "email": "mon-viewer@demo-org.com",
            "full_name": "Mon Viewer",
            "password": "Viewer@12345",
            "role_ids": [viewer_id],
        },
    )
    viewer = await login(client, "mon-viewer@demo-org.com", "Viewer@12345")
    assert (
        await client.get("/api/v1/monitoring/thresholds", headers=bearer(viewer))
    ).status_code == 200
    resp = await client.put(
        "/api/v1/monitoring/thresholds",
        headers=bearer(viewer),
        json={"storage_alert_percent": 70},
    )
    assert resp.status_code == 403


async def test_fleet_health_rollups(client, admin_tokens):
    """P2-MON-001: org / location-subtree / group rollups."""
    online_dev, online_token = await enroll_with(
        client, admin_tokens, "SN-FH-ON", manufacturer="Acme"
    )
    offline_dev, _ = await enroll_with(client, admin_tokens, "SN-FH-OFF", manufacturer="Acme")
    await assign_location(client, admin_tokens, online_dev, "Kolkata")
    await assign_location(client, admin_tokens, offline_dev, "Salt Lake Store")
    await heartbeat(client, online_dev, online_token)

    resp = await client.post(
        "/api/v1/device-groups",
        headers=bearer(admin_tokens),
        json={
            "name": "FH Dynamic",
            "group_type": "dynamic",
            "rule_json": {
                "match": "all",
                "conditions": [{"field": "manufacturer", "operator": "eq", "value": "Acme"}],
            },
        },
    )
    assert resp.status_code == 201, resp.text

    resp = await client.get("/api/v1/monitoring/fleet-health", headers=bearer(admin_tokens))
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]

    org = data["organization"]
    assert org["online"] >= 1 and org["offline"] >= 1
    assert org["total"] == org["online"] + org["warning"] + org["offline"]

    by_name = {row["name"]: row for row in data["locations"]}
    # Salt Lake Store subtree contains the offline device; Kolkata (its
    # ancestor) rolls up both devices.
    assert by_name["Salt Lake Store"]["offline"] >= 1
    assert by_name["Kolkata"]["total"] >= 2
    assert by_name["Kolkata"]["online"] >= 1 and by_name["Kolkata"]["offline"] >= 1

    groups = {row["name"]: row for row in data["groups"]}
    assert groups["FH Dynamic"]["group_type"] == "dynamic"
    assert groups["FH Dynamic"]["total"] == 2
    assert groups["FH Dynamic"]["online"] == 1 and groups["FH Dynamic"]["offline"] == 1


async def test_outdated_player_count(client, admin_tokens):
    device_id, token = await enroll_with(client, admin_tokens, "SN-FH-VER")
    await heartbeat(client, device_id, token, player_version="1.0.0")
    await client.put(
        "/api/v1/monitoring/thresholds",
        headers=bearer(admin_tokens),
        json={"min_player_version": "2.0.0"},
    )
    resp = await client.get("/api/v1/monitoring/fleet-health", headers=bearer(admin_tokens))
    assert resp.json()["data"]["organization"]["outdated_players"] == 1
    await client.put(
        "/api/v1/monitoring/thresholds",
        headers=bearer(admin_tokens),
        json={"min_player_version": "1.0.0"},
    )
    resp = await client.get("/api/v1/monitoring/fleet-health", headers=bearer(admin_tokens))
    assert resp.json()["data"]["organization"]["outdated_players"] == 0


async def test_storage_threshold_incident_lifecycle(client, admin_tokens):
    """P2-MON-002: storage above the tenant limit opens one incident per
    episode; a heartbeat below the limit auto-resolves it."""
    device_id, token = await enroll_with(client, admin_tokens, "SN-FH-STOR")
    await client.put(
        "/api/v1/monitoring/thresholds",
        headers=bearer(admin_tokens),
        json={"storage_alert_percent": 80},
    )
    await heartbeat(client, device_id, token, storage={"used_percent": 91})
    resp = await client.get(
        "/api/v1/incidents?state=open&page_size=100", headers=bearer(admin_tokens)
    )
    storage_incidents = [
        i for i in resp.json()["data"] if i["type"] == "device_storage"
    ]
    assert len(storage_incidents) == 1

    # Repeated high-storage heartbeats do not duplicate the incident.
    await heartbeat(client, device_id, token, storage={"used_percent": 95})
    resp = await client.get(
        "/api/v1/incidents?state=open&page_size=100", headers=bearer(admin_tokens)
    )
    assert (
        len([i for i in resp.json()["data"] if i["type"] == "device_storage"]) == 1
    )

    # Recovery below the threshold resolves it.
    await heartbeat(client, device_id, token, storage={"used_percent": 60})
    resp = await client.get(
        "/api/v1/incidents?state=resolved&page_size=100", headers=bearer(admin_tokens)
    )
    resolved = [i for i in resp.json()["data"] if i["type"] == "device_storage"]
    assert resolved and resolved[0]["resolution"].startswith("Storage back")

    resp = await client.get("/api/v1/notifications?page_size=100", headers=bearer(admin_tokens))
    assert any(n["type"] == "DEVICE_STORAGE" for n in resp.json()["data"])


async def test_per_tenant_offline_threshold(client, admin_tokens, db_session):
    """detect_offline_devices honors the tenant's offline window."""
    from app.models import Device
    from app.services import monitoring

    device_id, token = await enroll_with(client, admin_tokens, "SN-FH-THRESH")
    await heartbeat(client, device_id, token)

    # Backdate the heartbeat to 2 minutes ago — inside the platform default
    # (no incident) but outside a strict 60-second tenant threshold.
    await db_session.execute(
        update(Device)
        .where(Device.serial_no == "SN-FH-THRESH")
        .values(last_heartbeat_at=dt.datetime.now(dt.UTC) - dt.timedelta(seconds=120))
    )
    await db_session.commit()

    created = await monitoring.detect_offline_devices(db_session)
    await db_session.commit()
    assert created == 0  # default threshold: still healthy

    await client.put(
        "/api/v1/monitoring/thresholds",
        headers=bearer(admin_tokens),
        json={"warning_after_seconds": 30, "offline_after_seconds": 60},
    )
    created = await monitoring.detect_offline_devices(db_session)
    await db_session.commit()
    assert created >= 1
    resp = await client.get(
        "/api/v1/incidents?state=open&page_size=100", headers=bearer(admin_tokens)
    )
    offline = [i for i in resp.json()["data"] if i["type"] == "device_offline"]
    assert offline, resp.text


async def test_device_event_timeline(client, admin_tokens):
    """P2-MON-004: merged chronological events + incidents + recoveries."""
    device_id, token = await enroll_with(client, admin_tokens, "SN-FH-TL")
    await client.put(
        "/api/v1/monitoring/thresholds",
        headers=bearer(admin_tokens),
        json={"storage_alert_percent": 80},
    )
    resp = await client.post(
        f"/api/v1/player/{device_id}/events",
        headers=device_headers(token),
        json={
            "events": [
                {"type": "app_start", "timestamp": dt.datetime.now(dt.UTC).isoformat()},
                {"type": "playback_error", "payload": {"code": "DECODE"}},
            ]
        },
    )
    assert resp.status_code == 200, resp.text
    await heartbeat(client, device_id, token, storage={"used_percent": 92})  # incident
    await heartbeat(client, device_id, token, storage={"used_percent": 40})  # recovery

    resp = await client.get(
        f"/api/v1/devices/{device_id}/events", headers=bearer(admin_tokens)
    )
    assert resp.status_code == 200, resp.text
    timeline = resp.json()["data"]
    kinds = {row["kind"] for row in timeline}
    assert {"event", "incident", "recovery"} <= kinds
    ats = [row["at"] for row in timeline]
    assert ats == sorted(ats, reverse=True)
    assert any(row["type"] == "playback_error" for row in timeline)


async def test_fleet_health_isolation(client, admin_tokens, org_b, db_session):  # noqa: F811
    device_id, _ = await enroll_with(client, admin_tokens, "SN-FH-ISO")
    b_tokens = await login(client, "admin@org-b-corp.com", "BAdmin@12345")
    resp = await client.get("/api/v1/monitoring/fleet-health", headers=bearer(b_tokens))
    assert resp.status_code == 200
    assert resp.json()["data"]["organization"]["total"] == 0

    # Org B's threshold changes never leak into org A.
    await client.put(
        "/api/v1/monitoring/thresholds",
        headers=bearer(b_tokens),
        json={"storage_alert_percent": 55},
    )
    resp = await client.get("/api/v1/monitoring/thresholds", headers=bearer(admin_tokens))
    assert resp.json()["data"]["storage_alert_percent"] == 90

    from app.models import Organization

    orgs = (await db_session.execute(select(Organization.id))).scalars().all()
    assert len(orgs) >= 2  # fixture sanity
