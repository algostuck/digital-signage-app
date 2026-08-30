"""Phase-3 slice 3A-2: dynamic data sources — guarded fetch, schema
validation, transforms, cache/last-known-good semantics, entitlement gate,
manifest data block, retention."""

import datetime as dt
import json

from sqlalchemy import select

from tests.conftest import bearer, login
from tests.test_tenant_isolation import org_b  # noqa: F401 (fixture)

FEED = {
    "city": "Kolkata",
    "items": [
        {"title": "Sunny", "temp": 31, "extra": "x"},
        {"title": "Cloudy", "temp": 29, "extra": "y"},
        {"title": "Rain", "temp": 27, "extra": "z"},
    ],
}


def fake_fetch(payload=FEED):
    async def _fetch(source):
        return json.dumps(payload).encode()

    return _fetch


async def make_source(client, tokens, *, name="Weather", schema=None, **overrides):
    body = {
        "name": name,
        "type": "rest_json",
        "endpoint": "https://feeds.example.com/weather.json",
        "cache_ttl_seconds": 60,
        "refresh_seconds": 60,
        **overrides,
    }
    if schema is not None:
        body["schema_spec"] = schema
    resp = await client.post("/api/v1/data-sources", headers=bearer(tokens), json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


async def test_source_crud_and_validation(client, admin_tokens):
    source = await make_source(
        client, admin_tokens, schema={"required": ["city", "items"]}
    )
    assert source["schema"]["required"] == ["city", "items"]
    assert source["state"] == "active"

    # Duplicate name conflicts; bad settings are rejected.
    resp = await client.post(
        "/api/v1/data-sources",
        headers=bearer(admin_tokens),
        json={"name": "Weather", "type": "rest_json", "endpoint": "https://x.example.com"},
    )
    assert resp.status_code == 409
    resp = await client.post(
        "/api/v1/data-sources",
        headers=bearer(admin_tokens),
        json={"name": "Bad", "type": "soap", "endpoint": "https://x.example.com"},
    )
    assert resp.status_code == 400
    resp = await client.post(
        "/api/v1/data-sources",
        headers=bearer(admin_tokens),
        json={"name": "Bad2", "type": "rest_json", "endpoint": "ftp://x.example.com"},
    )
    assert resp.status_code == 400

    # Schema versioning bumps.
    resp = await client.put(
        f"/api/v1/data-sources/{source['id']}/schema",
        headers=bearer(admin_tokens),
        json={"schema_spec": {"required": ["city"]}},
    )
    assert resp.json()["data"]["version_no"] == 2

    resp = await client.delete(
        f"/api/v1/data-sources/{source['id']}", headers=bearer(admin_tokens)
    )
    assert resp.status_code == 200


async def test_entitlement_gate_blocks_starter_plan(client, org_b):  # noqa: F811
    b_tokens = await login(client, "admin@org-b-corp.com", "BAdmin@12345")
    resp = await client.post(
        "/api/v1/billing/subscribe",
        headers=bearer(b_tokens),
        json={"plan_code": "starter"},
    )
    assert resp.status_code == 200

    resp = await client.post(
        "/api/v1/data-sources",
        headers=bearer(b_tokens),
        json={"name": "Feed", "type": "rest_json", "endpoint": "https://x.example.com"},
    )
    assert resp.status_code == 422
    assert "dynamic_data" in resp.text
    assert "Upgrade your subscription" in resp.text


async def test_fetch_validate_and_last_known_good(client, admin_tokens, db_session, monkeypatch):
    from app.integrations.fetch import FetchError
    from app.services import data_sources as engine

    source = await make_source(
        client, admin_tokens, name="LKG", schema={"required": ["city", "items"]}
    )

    # Dry-run test endpoint: valid feed.
    monkeypatch.setattr(engine, "_fetch", fake_fetch())
    resp = await client.post(
        f"/api/v1/data-sources/{source['id']}/test", headers=bearer(admin_tokens)
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["ok"] is True
    assert len(resp.json()["data"]["sample"]["items"]) == 3

    # Store a good snapshot.
    resp = await client.post(
        f"/api/v1/data-sources/{source['id']}/refresh", headers=bearer(admin_tokens)
    )
    assert resp.json()["data"]["ok"] is True

    # Schema violation -> invalid snapshot, state error, LKG intact.
    monkeypatch.setattr(engine, "_fetch", fake_fetch({"wrong": True}))
    resp = await client.post(
        f"/api/v1/data-sources/{source['id']}/refresh", headers=bearer(admin_tokens)
    )
    assert resp.json()["data"]["ok"] is False
    assert "Missing required paths" in resp.json()["data"]["error"]

    # Transport failure -> same degradation.
    async def down(src):
        raise FetchError("connection refused")

    monkeypatch.setattr(engine, "_fetch", down)
    await client.post(
        f"/api/v1/data-sources/{source['id']}/refresh", headers=bearer(admin_tokens)
    )

    health = (
        await client.get(
            f"/api/v1/data-sources/{source['id']}/health", headers=bearer(admin_tokens)
        )
    ).json()["data"]
    assert health["state"] == "error"
    assert health["last_fetch"]["valid"] is False
    assert health["has_last_known_good"] is True  # P3-DAT-004

    # The bus still serves the last VALID payload.
    import uuid as uuid_mod

    good = await engine.latest_valid_snapshot(db_session, uuid_mod.UUID(source["id"]))
    assert good is not None
    assert good.payload_json["city"] == "Kolkata"


async def test_ssrf_guard_refuses_private_endpoints(client, admin_tokens):
    source = await make_source(
        client, admin_tokens, name="Evil", endpoint="http://127.0.0.1:9/latest"
    )
    resp = await client.post(
        f"/api/v1/data-sources/{source['id']}/test", headers=bearer(admin_tokens)
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["ok"] is False
    assert "non-public" in data["error"]


async def test_layout_binding_validation_and_manifest_data_block(
    client, admin_tokens, db_session, monkeypatch
):
    from app.services import data_sources as engine

    source = await make_source(client, admin_tokens, name="Ticker feed")
    monkeypatch.setattr(engine, "_fetch", fake_fetch())
    await client.post(
        f"/api/v1/data-sources/{source['id']}/refresh", headers=bearer(admin_tokens)
    )

    # A widget to bind (2D framework).
    resp = await client.post(
        "/api/v1/widgets",
        headers=bearer(admin_tokens),
        json={
            "type": "ticker",
            "name": "News ticker",
            "config_schema_json": {"fields": [{"key": "speed", "label": "Speed",
                                               "type": "number", "required": False}]},
            "fallback_json": {"text": "Welcome!"},
        },
    )
    assert resp.status_code == 201, resp.text
    widget_id = resp.json()["data"]["id"]

    def canvas(binding):
        return {
            "schema_version": 1,
            "canvas": {"width": 1920, "height": 1080},
            "zones": [
                {
                    "key": "main",
                    "name": "Main",
                    "x": 0, "y": 0, "width": 1920, "height": 1080,
                    "content_type": "widget",
                    "widget": {
                        "widget_id": widget_id,
                        "config": {},
                        "bindings": {},
                        "data_binding": binding,
                    },
                }
            ],
        }

    # Unknown source is refused at publish.
    resp = await client.post(
        "/api/v1/layouts", headers=bearer(admin_tokens),
        json={"name": "Dyn layout", "description": None},
    )
    assert resp.status_code == 201, resp.text
    layout_id = resp.json()["data"]["id"]
    bad = canvas({"source_id": "00000000-0000-0000-0000-000000000000"})
    resp = await client.patch(
        f"/api/v1/layouts/{layout_id}", headers=bearer(admin_tokens),
        json={"canvas_json": bad},
    )
    assert resp.status_code == 200, resp.text
    resp = await client.post(
        f"/api/v1/layouts/{layout_id}/publish", headers=bearer(admin_tokens)
    )
    assert resp.status_code == 404

    # Valid binding with a safe transform publishes.
    good = canvas(
        {
            "source_id": source["id"],
            "transform": {"path": "items", "fields": {"title": "title"}, "limit": 2},
        }
    )
    await client.patch(
        f"/api/v1/layouts/{layout_id}", headers=bearer(admin_tokens),
        json={"canvas_json": good},
    )
    resp = await client.post(
        f"/api/v1/layouts/{layout_id}/publish", headers=bearer(admin_tokens)
    )
    assert resp.status_code == 200, resp.text

    # Manifest data block: transformed, bounded, freshness-tagged.
    from app.models import Organization
    from app.services.data_sources import data_block_for_canvas

    org_id = (
        await db_session.execute(
            select(Organization.id).where(Organization.code == "demo")
        )
    ).scalar_one()
    block = await data_block_for_canvas(db_session, org_id, good)
    entry = block["main"]
    assert entry["source_id"] == source["id"]
    assert entry["stale"] is False
    assert entry["data"] == [{"title": "Sunny"}, {"title": "Cloudy"}]


async def test_snapshot_bounding_and_retention(client, admin_tokens, db_session, monkeypatch):
    import uuid as uuid_mod

    from app.models import DataSourceSnapshot
    from app.services import data_sources as engine
    from app.services import tenant_admin

    source = await make_source(client, admin_tokens, name="Bounded")
    source_id = uuid_mod.UUID(source["id"])

    monkeypatch.setattr(engine, "_fetch", fake_fetch())
    for _ in range(engine.SNAPSHOT_KEEP + 5):
        await client.post(
            f"/api/v1/data-sources/{source['id']}/refresh", headers=bearer(admin_tokens)
        )
    count = (
        await db_session.execute(
            select(DataSourceSnapshot).where(DataSourceSnapshot.source_id == source_id)
        )
    ).scalars().all()
    assert len(count) <= engine.SNAPSHOT_KEEP  # bounded history

    # Retention prunes by age but keeps the newest valid snapshot.
    old = dt.datetime.now(dt.UTC) - dt.timedelta(days=60)
    for row in count[:-1]:
        row.fetched_at = old
    await db_session.commit()
    totals = await tenant_admin.prune_retention(db_session)
    await db_session.commit()
    assert totals.get("data_source_snapshots", 0) >= 1
    remaining = (
        await db_session.execute(
            select(DataSourceSnapshot).where(DataSourceSnapshot.source_id == source_id)
        )
    ).scalars().all()
    assert any(s.valid for s in remaining)  # last-known-good survived


async def test_refresh_sweep_and_isolation(client, admin_tokens, org_b, db_session, monkeypatch):  # noqa: F811
    from app.services import data_sources as engine

    await make_source(client, admin_tokens, name="Sweep me")
    monkeypatch.setattr(engine, "_fetch", fake_fetch())
    result = await engine.refresh_due_sources(db_session)
    await db_session.commit()
    assert result["refreshed"] >= 1

    # Org B (legacy, unrestricted) sees nothing of org A.
    b_tokens = await login(client, "admin@org-b-corp.com", "BAdmin@12345")
    resp = await client.get("/api/v1/data-sources", headers=bearer(b_tokens))
    assert resp.json()["data"] == []
