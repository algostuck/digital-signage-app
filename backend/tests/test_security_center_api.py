"""Phase-3 slice 3E-3: security center — credential lifecycle, rotation via
the standard re-registration flow, policy sweep with self-resolve."""

import datetime as dt

from sqlalchemy import update

from tests.conftest import bearer, login
from tests.test_devices_api import enroll_active_device, get_enrollment_key, register
from tests.test_tenant_isolation import org_b  # noqa: F401 (fixture)


async def test_identity_tracking_and_rotation(client, admin_tokens):
    device_id, _token = await enroll_active_device(client, admin_tokens, "SN-SEC-1")

    resp = await client.get(
        "/api/v1/security/devices/identities", headers=bearer(admin_tokens)
    )
    assert resp.status_code == 200
    row = next(r for r in resp.json()["data"] if r["device_id"] == device_id)
    assert row["has_credential"] is True
    assert row["fingerprint"] and len(row["fingerprint"]) == 16
    assert row["credential_history"] >= 1

    # Rotation revokes; the player re-registers and receives a NEW token
    # through the standard pipeline (no side channel).
    resp = await client.post(
        f"/api/v1/security/devices/{device_id}/rotate", headers=bearer(admin_tokens)
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "revoked_pending_reissue"

    key = await get_enrollment_key(client, admin_tokens)
    reissued = await register(client, key, "SN-SEC-1")
    assert reissued["device_token"]  # fresh credential

    resp = await client.get(
        "/api/v1/security/devices/identities", headers=bearer(admin_tokens)
    )
    row = next(r for r in resp.json()["data"] if r["device_id"] == device_id)
    assert row["has_credential"] is True
    assert row["credential_history"] >= 2  # old revoked + new issued


async def test_policy_sweep_opens_and_resolves(client, admin_tokens, db_session):
    from app.models import Device
    from app.services import security_center as engine

    device_id, _token = await enroll_active_device(client, admin_tokens, "SN-SEC-AGE")
    resp = await client.post(
        "/api/v1/security/policies",
        headers=bearer(admin_tokens),
        json={"scope_type": "device_credentials",
              "conditions": {"max_age_days": 30}, "severity": "critical"},
    )
    assert resp.status_code == 200, resp.text

    # Age the credential beyond the policy.
    await db_session.execute(
        update(Device)
        .where(Device.serial_no == "SN-SEC-AGE")
        .values(token_issued_at=dt.datetime.now(dt.UTC) - dt.timedelta(days=90))
    )
    await db_session.commit()

    result = await engine.sweep_violations(db_session)
    await db_session.commit()
    assert result["opened"] >= 1

    resp = await client.get(
        "/api/v1/security/policy-violations?state=open", headers=bearer(admin_tokens)
    )
    violation = next(
        v for v in resp.json()["data"] if v["entity_id"] == device_id
    )
    assert violation["severity"] == "critical"
    assert "days old" in violation["detail"]

    # Sweep is idempotent per episode.
    again = await engine.sweep_violations(db_session)
    await db_session.commit()
    assert again["opened"] == 0

    # Rotation + re-registration clears the condition -> auto-resolve.
    await client.post(
        f"/api/v1/security/devices/{device_id}/rotate", headers=bearer(admin_tokens)
    )
    key = await get_enrollment_key(client, admin_tokens)
    await register(client, key, "SN-SEC-AGE")
    healed = await engine.sweep_violations(db_session)
    await db_session.commit()
    assert healed["resolved"] >= 1

    resp = await client.get("/api/v1/security/summary", headers=bearer(admin_tokens))
    summary = resp.json()["data"]
    assert summary["device_identities"] >= 1
    assert "open_violations" in summary


async def test_security_rbac_and_isolation(client, admin_tokens, org_b):  # noqa: F811
    resp = await client.get("/api/v1/roles", headers=bearer(admin_tokens))
    viewer_id = next(r["id"] for r in resp.json()["data"] if r["name"] == "Viewer")
    await client.post(
        "/api/v1/users",
        headers=bearer(admin_tokens),
        json={"email": "sec-viewer@demo-org.com", "full_name": "Sec Viewer",
              "password": "Viewer@12345", "role_ids": [viewer_id]},
    )
    viewer = await login(client, "sec-viewer@demo-org.com", "Viewer@12345")
    resp = await client.get("/api/v1/security/summary", headers=bearer(viewer))
    assert resp.status_code == 403

    b_tokens = await login(client, "admin@org-b-corp.com", "BAdmin@12345")
    resp = await client.get(
        "/api/v1/security/devices/identities", headers=bearer(b_tokens)
    )
    assert resp.json()["data"] == []