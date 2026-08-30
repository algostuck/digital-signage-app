"""Tenant administration + compliance tests (P2-TNT-001..003, P2-AUD-002/003)."""

import csv
import datetime as dt
import io

from sqlalchemy import select

from tests.conftest import bearer, login
from tests.test_content_api import make_png
from tests.test_device_ops_api import enroll_with
from tests.test_devices_api import get_enrollment_key, register
from tests.test_tenant_isolation import org_b  # noqa: F401 (fixture)


async def patch_quotas(client, values: dict, org_code: str = "demo"):
    """Quota overrides are Super Admin-only (SaaS core): edit via /platform."""
    tokens = await login(client, "platform@signage.cloud", "Platform@12345")
    tenants = (
        await client.get("/api/v1/platform/tenants", headers=bearer(tokens))
    ).json()["data"]
    tenant_id = next(t["id"] for t in tenants if t["code"] == org_code)
    return await client.patch(
        f"/api/v1/platform/tenants/{tenant_id}/quotas",
        headers=bearer(tokens),
        json=values,
    )


async def test_usage_and_quota_updates(client, admin_tokens):
    await enroll_with(client, admin_tokens, "SN-QUOTA-1")
    resp = await client.get("/api/v1/organization/usage", headers=bearer(admin_tokens))
    assert resp.status_code == 200, resp.text
    usage = resp.json()["data"]
    assert usage["devices"]["used"] >= 1
    assert usage["users"]["used"] >= 1
    # Effective limit = plan entitlement (demo rides Enterprise: 5000).
    assert usage["devices"]["limit"] == 5000

    # Tenant admins can no longer edit quotas — the endpoint is gone.
    resp = await client.patch(
        "/api/v1/organization/quotas",
        headers=bearer(admin_tokens),
        json={"max_devices": 10},
    )
    assert resp.status_code in (404, 405)

    resp = await patch_quotas(
        client, {"max_devices": 10, "max_users": 5, "max_storage_mb": 100}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["devices"]["limit"] == 10

    for bad in [{"max_potatoes": 3}, {"max_devices": 0}, {"max_users": "many"}]:
        resp = await patch_quotas(client, bad)
        assert resp.status_code == 400, bad


async def test_device_quota_enforced_at_registration(client, admin_tokens):
    device_id, _ = await enroll_with(client, admin_tokens, "SN-QUOTA-CAP")
    usage = (
        await client.get("/api/v1/organization/usage", headers=bearer(admin_tokens))
    ).json()["data"]
    await patch_quotas(client, {"max_devices": usage["devices"]["used"]})
    key = await get_enrollment_key(client, admin_tokens)
    resp = await client.post(
        "/api/v1/player/register",
        json={"enrollment_key": key, "serial_no": "SN-QUOTA-OVER"},
    )
    assert resp.status_code == 422
    assert "limit reached" in resp.text.lower()
    # Existing devices can still re-poll (idempotent path is not a creation).
    reg = await register(client, key, "SN-QUOTA-CAP")
    assert reg["device_id"] == device_id


async def test_user_and_storage_quotas_enforced(client, admin_tokens):
    usage = (
        await client.get("/api/v1/organization/usage", headers=bearer(admin_tokens))
    ).json()["data"]
    await patch_quotas(
        client, {"max_users": usage["users"]["used"], "max_storage_mb": 1}
    )
    resp = await client.get("/api/v1/roles", headers=bearer(admin_tokens))
    viewer_id = next(r["id"] for r in resp.json()["data"] if r["name"] == "Viewer")
    resp = await client.post(
        "/api/v1/users",
        headers=bearer(admin_tokens),
        json={
            "email": "over-quota@demo-org.com",
            "full_name": "Over Quota",
            "password": "Over@12345",
            "role_ids": [viewer_id],
        },
    )
    assert resp.status_code == 422
    assert "limit reached" in resp.text.lower()

    # Storage: 1 MB limit -> a 2 MB upload session is refused up front.
    resp = await client.post(
        "/api/v1/assets/uploads",
        headers=bearer(admin_tokens),
        json={"filename": "big.png", "mime_type": "image/png",
              "size_bytes": 2 * 1024 * 1024},
    )
    assert resp.status_code == 422
    assert "limit reached" in resp.text.lower()
    # Small upload still fits.
    data = make_png()
    resp = await client.post(
        "/api/v1/assets/uploads",
        headers=bearer(admin_tokens),
        json={"filename": "small.png", "mime_type": "image/png", "size_bytes": len(data)},
    )
    assert resp.status_code == 201, resp.text


async def test_retention_settings_with_platform_floors(client, admin_tokens):
    resp = await client.get("/api/v1/organization/retention", headers=bearer(admin_tokens))
    assert resp.status_code == 200, resp.text
    retention = resp.json()["data"]
    assert retention["audit_logs"]["floor"] == 90
    assert retention["device_heartbeats"]["days"] == 30  # platform default

    resp = await client.put(
        "/api/v1/organization/retention",
        headers=bearer(admin_tokens),
        json={"device_heartbeats": 14, "audit_logs": 120},
    )
    assert resp.status_code == 200, resp.text
    updated = resp.json()["data"]
    assert updated["device_heartbeats"]["days"] == 14
    assert updated["audit_logs"]["days"] == 120

    # Below the compliance floor / above the ceiling / unknown key.
    for bad in [{"audit_logs": 30}, {"device_heartbeats": 5000}, {"selfies": 5}]:
        resp = await client.put(
            "/api/v1/organization/retention", headers=bearer(admin_tokens), json=bad
        )
        assert resp.status_code == 400, bad


async def test_retention_prune_respects_policy(client, admin_tokens, db_session):
    from app.models import Device, DeviceHeartbeat, Notification
    from app.services import tenant_admin

    device_id, token = await enroll_with(client, admin_tokens, "SN-PRUNE")
    await client.put(
        "/api/v1/organization/retention",
        headers=bearer(admin_tokens),
        json={"device_heartbeats": 7, "notifications": 7},
    )

    device_pk = (
        await db_session.execute(select(Device.id).where(Device.serial_no == "SN-PRUNE"))
    ).scalar_one()
    org_id = (
        await db_session.execute(
            select(Device.organization_id).where(Device.id == device_pk)
        )
    ).scalar_one()
    now = dt.datetime.now(dt.UTC)
    db_session.add(  # ancient: pruned
        DeviceHeartbeat(device_id=device_pk, observed_at=now - dt.timedelta(days=30))
    )
    db_session.add(  # recent: kept
        DeviceHeartbeat(device_id=device_pk, observed_at=now - dt.timedelta(days=1))
    )
    db_session.add(
        Notification(
            organization_id=org_id,
            type="TEST_OLD",
            severity="info",
            title="old",
            created_at=now - dt.timedelta(days=30),
        )
    )
    await db_session.commit()

    totals = await tenant_admin.prune_retention(db_session)
    await db_session.commit()
    assert totals.get("device_heartbeats", 0) >= 1
    assert totals.get("notifications", 0) >= 1

    remaining = (
        await db_session.execute(
            select(DeviceHeartbeat).where(DeviceHeartbeat.device_id == device_pk)
        )
    ).scalars().all()
    assert all(
        (hb.observed_at.replace(tzinfo=dt.UTC) if hb.observed_at.tzinfo is None
         else hb.observed_at) > now - dt.timedelta(days=7)
        for hb in remaining
    )
    # The sweep itself is audited.
    resp = await client.get(
        "/api/v1/audit-logs?action=RETENTION_PRUNED", headers=bearer(admin_tokens)
    )
    assert resp.json()["data"], resp.text


async def test_audit_export_requires_audit_view(client, admin_tokens):
    await enroll_with(client, admin_tokens, "SN-AUDX")  # generates audit rows
    resp = await client.post(
        "/api/v1/reports/export",
        headers=bearer(admin_tokens),
        json={"report": "audit", "format": "csv",
              "filters": {"action": "DEVICE_APPROVED"}},
    )
    assert resp.status_code == 200, resp.text
    rows = list(csv.DictReader(io.StringIO(resp.content.decode("utf-8-sig"))))
    assert rows and all(r["action"] == "DEVICE_APPROVED" for r in rows)

    # A role holding reports.export but NOT audit.view -> 403 on audit export.
    resp = await client.post(
        "/api/v1/roles",
        headers=bearer(admin_tokens),
        json={
            "name": "Exporter No Audit",
            "description": "audit export test",
            "permission_codes": ["reports.view", "reports.export"],
        },
    )
    role_id = resp.json()["data"]["id"]
    await client.post(
        "/api/v1/users",
        headers=bearer(admin_tokens),
        json={
            "email": "audx-cm@demo-org.com",
            "full_name": "Audit Export CM",
            "password": "Manager@12345",
            "role_ids": [role_id],
        },
    )
    manager = await login(client, "audx-cm@demo-org.com", "Manager@12345")
    resp = await client.post(
        "/api/v1/reports/export",
        headers=bearer(manager),
        json={"report": "audit", "format": "csv"},
    )
    assert resp.status_code == 403


async def test_quota_isolation(client, admin_tokens, org_b):  # noqa: F811
    await patch_quotas(client, {"max_devices": 3})
    b_tokens = await login(client, "admin@org-b-corp.com", "BAdmin@12345")
    resp = await client.get("/api/v1/organization/usage", headers=bearer(b_tokens))
    assert resp.json()["data"]["devices"]["limit"] is None  # org A quota not leaked