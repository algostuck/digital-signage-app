"""Phase-3 slice 3A-1: domain event bus — normalized stream, subscription
filters, signed deliveries with retry→dead-letter→replay, retention, RBAC
and tenant isolation."""

import datetime as dt
import hashlib
import hmac

from sqlalchemy import select, update

from tests.conftest import bearer, login
from tests.test_devices_api import enroll_active_device, get_enrollment_key, register
from tests.test_tenant_isolation import org_b  # noqa: F401 (fixture)


async def make_subscription(client, tokens, *, name="Consumer", url=None, event_types=None):
    resp = await client.post(
        "/api/v1/subscriptions",
        headers=bearer(tokens),
        json={
            "name": name,
            "url": url or "https://consumer.example.com/events",
            "event_types": event_types or ["*"],
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


async def test_device_lifecycle_emits_normalized_events(client, admin_tokens):
    await enroll_active_device(client, admin_tokens, "SN-EVT-1")

    resp = await client.get("/api/v1/events", headers=bearer(admin_tokens))
    assert resp.status_code == 200
    types = [e["event_type"] for e in resp.json()["data"]]
    assert "device.registered" in types
    assert "device.approved" in types

    # Filter by event type + entity type.
    resp = await client.get(
        "/api/v1/events?event_type=device.approved", headers=bearer(admin_tokens)
    )
    events = resp.json()["data"]
    assert events and all(e["event_type"] == "device.approved" for e in events)
    assert events[0]["entity_type"] == "device"
    assert events[0]["payload"]["serial_no"] == "SN-EVT-1"

    # Catalogue is exposed for the subscription picker.
    resp = await client.get("/api/v1/events/catalogue", headers=bearer(admin_tokens))
    assert "device.approved" in resp.json()["data"]


async def test_subscription_secret_one_time_and_validation(client, admin_tokens):
    created = await make_subscription(client, admin_tokens, name="Signed consumer")
    assert created["secret"].startswith("evsec_")

    # Never returned again.
    resp = await client.get("/api/v1/subscriptions", headers=bearer(admin_tokens))
    row = next(s for s in resp.json()["data"] if s["id"] == created["id"])
    assert "secret" not in row

    # Unknown event types are rejected.
    resp = await client.post(
        "/api/v1/subscriptions",
        headers=bearer(admin_tokens),
        json={
            "name": "Bad",
            "url": "https://x.example.com",
            "event_types": ["device.exploded"],
        },
    )
    assert resp.status_code == 400

    resp = await client.delete(
        f"/api/v1/subscriptions/{created['id']}", headers=bearer(admin_tokens)
    )
    assert resp.status_code == 200


async def test_signed_delivery_filter_and_worker(client, admin_tokens, db_session, monkeypatch):
    from app.services import events as engine

    matching = await make_subscription(
        client, admin_tokens, name="Devices only", event_types=["device.approved"]
    )
    await make_subscription(
        client, admin_tokens, name="Content only",
        url="https://other.example.com", event_types=["content.published"],
    )

    await enroll_active_device(client, admin_tokens, "SN-EVT-SIGN")

    seen: list[dict] = []

    async def capture(url, body, headers):
        seen.append({"url": url, "body": body, "headers": headers})
        return 200

    monkeypatch.setattr(engine, "_post", capture)
    result = await engine.process_deliveries(db_session)
    await db_session.commit()

    # Only the matching subscription received the push (filter works).
    assert result["delivered"] == 1
    call = seen[0]
    assert call["url"] == "https://consumer.example.com/events"
    assert call["headers"]["X-Event-Type"] == "device.approved"
    expected = hmac.new(
        matching["secret"].encode(), call["body"], hashlib.sha256
    ).hexdigest()
    assert call["headers"]["X-Event-Signature"] == expected

    # Envelope is the normalized shape.
    import json

    envelope = json.loads(call["body"])
    assert envelope["event_type"] == "device.approved"
    assert envelope["entity_type"] == "device"
    assert envelope["payload"]["serial_no"] == "SN-EVT-SIGN"

    # Delivery log via API.
    resp = await client.get(
        f"/api/v1/subscriptions/{matching['id']}/deliveries", headers=bearer(admin_tokens)
    )
    rows = resp.json()["data"]
    assert rows and rows[0]["state"] == "delivered"


async def test_retry_dead_letter_and_replay(client, admin_tokens, db_session, monkeypatch):
    from app.models import EventDelivery
    from app.services import events as engine

    subscription = await make_subscription(
        client, admin_tokens, name="Down consumer", event_types=["device.registered"]
    )
    key = await get_enrollment_key(client, admin_tokens)
    await register(client, key, "SN-EVT-DEAD")

    async def failing(url, body, headers):
        return 503

    monkeypatch.setattr(engine, "_post", failing)
    for _attempt in range(engine.MAX_ATTEMPTS):
        await db_session.execute(
            update(EventDelivery).values(
                next_attempt_at=dt.datetime.now(dt.UTC) - dt.timedelta(seconds=1)
            )
        )
        await db_session.commit()
        await engine.process_deliveries(db_session)
        await db_session.commit()

    delivery = (
        (
            await db_session.execute(
                select(EventDelivery).order_by(EventDelivery.created_at.desc())
            )
        )
        .scalars()
        .first()
    )
    assert delivery.state == "dead"
    assert delivery.attempt_no == engine.MAX_ATTEMPTS
    assert "503" in delivery.last_error

    # Replay resets it; a healthy consumer then receives it.
    resp = await client.post(
        f"/api/v1/subscriptions/deliveries/{delivery.id}/replay",
        headers=bearer(admin_tokens),
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["state"] == "pending"

    async def healthy(url, body, headers):
        return 200

    monkeypatch.setattr(engine, "_post", healthy)
    result = await engine.process_deliveries(db_session)
    await db_session.commit()
    assert result["delivered"] == 1
    assert subscription["id"]  # subscription remains intact


async def test_event_bus_rbac_and_isolation(client, admin_tokens, org_b):  # noqa: F811
    # A role without webhooks.manage cannot read the stream.
    resp = await client.get("/api/v1/roles", headers=bearer(admin_tokens))
    viewer_id = next(r["id"] for r in resp.json()["data"] if r["name"] == "Viewer")
    resp = await client.post(
        "/api/v1/users",
        headers=bearer(admin_tokens),
        json={
            "email": "evt-viewer@demo-org.com",
            "full_name": "Event Viewer",
            "password": "Viewer@12345",
            "role_ids": [viewer_id],
        },
    )
    assert resp.status_code == 201
    viewer = await login(client, "evt-viewer@demo-org.com", "Viewer@12345")
    resp = await client.get("/api/v1/events", headers=bearer(viewer))
    assert resp.status_code == 403

    # Org A activity is invisible to org B.
    await enroll_active_device(client, admin_tokens, "SN-EVT-ISO")
    b_tokens = await login(client, "admin@org-b-corp.com", "BAdmin@12345")
    resp = await client.get("/api/v1/events", headers=bearer(b_tokens))
    assert resp.json()["data"] == []
    resp = await client.get("/api/v1/subscriptions", headers=bearer(b_tokens))
    assert resp.json()["data"] == []


async def test_domain_events_retention_pruned(client, admin_tokens, db_session):
    from app.models import DomainEvent, Organization
    from app.services import tenant_admin

    await enroll_active_device(client, admin_tokens, "SN-EVT-PRUNE")
    org_id = (
        await db_session.execute(select(Organization.id).where(Organization.code == "demo"))
    ).scalar_one()

    # Backdate one event beyond the default 90-day window.
    old = DomainEvent(
        organization_id=org_id,
        event_type="device.offline",
        entity_type="device",
        occurred_at=dt.datetime.now(dt.UTC) - dt.timedelta(days=120),
    )
    db_session.add(old)
    await db_session.commit()

    totals = await tenant_admin.prune_retention(db_session)
    await db_session.commit()
    assert totals.get("domain_events", 0) >= 1

    remaining_types = (
        (
            await db_session.execute(
                select(DomainEvent.event_type).where(
                    DomainEvent.organization_id == org_id
                )
            )
        )
        .scalars()
        .all()
    )
    # Recent events survive; the backdated one is gone.
    assert "device.approved" in remaining_types
    assert "device.offline" not in remaining_types
