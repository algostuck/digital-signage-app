"""Organization dashboard aggregate (SCR-02 redesign): section gating,
number reconciliation, tenant isolation, the connection_status device
filter and the hourly health snapshot."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from tests.conftest import bearer, login
from tests.test_devices_api import device_headers, enroll_active_device
from tests.test_tenant_isolation import org_b  # noqa: F401 (fixture)


async def test_dashboard_reconciles_with_its_sources(client, admin_tokens):
    dev, token = await enroll_active_device(client, admin_tokens, "SN-DASH-1")
    resp = await client.post(
        f"/api/v1/player/{dev}/heartbeat", headers=device_headers(token), json={"status": "online"}
    )
    assert resp.status_code == 200

    resp = await client.get("/api/v1/dashboard/organization", headers=bearer(admin_tokens))
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]

    # The org admin holds every permission, so every section is present.
    for key in (
        "kpis",
        "device_health",
        "geo",
        "locations_top",
        "campaigns",
        "playback",
        "content",
        "deployments",
        "attention",
        "activity",
        "approvals",
        "schedule_today",
        "now_playing",
        "usage",
    ):
        assert key in data, key
    assert data["range"]["from"] <= data["range"]["to"]

    # Device numbers agree with the monitoring summary, and the health mix
    # sums to the fleet total (online + warning + offline + n/a).
    summary = (await client.get("/api/v1/monitoring/summary", headers=bearer(admin_tokens))).json()[
        "data"
    ]
    assert data["kpis"]["devices"] == {**summary["devices"]}
    current = data["device_health"]["current"]
    assert sum(current.values()) == summary["devices"]["total"]
    assert current["online"] >= 1  # the device that just heartbeated

    # The playback series covers every day of the range and sums to the KPI.
    series = data["playback"]["series"]
    assert len(series) == 7
    assert sum(p["plays"] for p in series) == data["kpis"]["playback"]["plays"]

    # Attention rows are actionable: every one carries a destination.
    for item in data["attention"]:
        assert item["href"].startswith("/")
        assert item["severity"] in {"critical", "high", "medium", "info"}


async def test_dashboard_is_tenant_scoped(client, admin_tokens, org_b):  # noqa: F811
    b_tokens = await login(client, "admin@org-b-corp.com", "BAdmin@12345")
    mine = (await client.get("/api/v1/dashboard/organization", headers=bearer(b_tokens))).json()[
        "data"
    ]
    theirs = (
        await client.get("/api/v1/dashboard/organization", headers=bearer(admin_tokens))
    ).json()["data"]

    b_devices = (await client.get("/api/v1/devices?page_size=1", headers=bearer(b_tokens))).json()[
        "meta"
    ]["total"]
    assert mine["kpis"]["devices"]["total"] == b_devices
    assert mine["kpis"]["devices"]["total"] != theirs["kpis"]["devices"]["total"]

    b_locations = {
        loc["id"]
        for loc in (
            await client.get("/api/v1/locations?page_size=200", headers=bearer(b_tokens))
        ).json()["data"]
    }
    assert {g["location_id"] for g in mine["geo"]} <= b_locations
    assert all(d["device_name"] for d in mine["now_playing"]) or mine["now_playing"] == []


async def test_dashboard_range_is_validated(client, admin_tokens):
    resp = await client.get(
        "/api/v1/dashboard/organization?from=2026-09-10&to=2026-09-01",
        headers=bearer(admin_tokens),
    )
    assert resp.status_code == 400  # ValidationAppError, as the calendar endpoint
    resp = await client.get(
        "/api/v1/dashboard/organization?from=2026-01-01&to=2026-09-01",
        headers=bearer(admin_tokens),
    )
    assert resp.status_code == 400


async def test_devices_filter_by_connection_status(client, admin_tokens):
    live, token = await enroll_active_device(client, admin_tokens, "SN-DASH-LIVE")
    silent, _ = await enroll_active_device(client, admin_tokens, "SN-DASH-SILENT")
    resp = await client.post(
        f"/api/v1/player/{live}/heartbeat", headers=device_headers(token), json={"status": "online"}
    )
    assert resp.status_code == 200

    online = (
        await client.get(
            "/api/v1/devices?connection_status=online&page_size=100", headers=bearer(admin_tokens)
        )
    ).json()["data"]
    assert live in {d["id"] for d in online}
    assert silent not in {d["id"] for d in online}
    assert all(d["connection_status"] == "online" for d in online)

    offline = (
        await client.get(
            "/api/v1/devices?connection_status=offline&page_size=100", headers=bearer(admin_tokens)
        )
    ).json()["data"]
    assert silent in {d["id"] for d in offline}
    assert live not in {d["id"] for d in offline}
    assert all(d["connection_status"] == "offline" for d in offline)

    resp = await client.get(
        "/api/v1/devices?connection_status=sideways", headers=bearer(admin_tokens)
    )
    assert resp.status_code == 400  # request validation maps to 400 app-wide


async def test_health_snapshot_written_once_per_hour(db_engine, seeded):
    from app.models.dashboard import DeviceHealthSnapshot
    from app.services.dashboard import snapshot_device_health

    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as db:
        first = await snapshot_device_health(db)
        second = await snapshot_device_health(db)
        await db.commit()
        assert first >= 1
        assert second == 0  # same hour, nothing new
        rows = (
            await db.execute(select(func.count()).select_from(DeviceHealthSnapshot))
        ).scalar_one()
        assert rows == first
