"""P1-12 hardening tests: rate limiting and secure headers (SRS §16)."""

import pytest

from app.core.config import get_settings
from app.core.ratelimit import limiter
from tests.conftest import bearer


@pytest.fixture
def rate_limits_on():
    settings = get_settings()
    limiter.reset()
    settings.rate_limit_enabled = True
    yield settings
    settings.rate_limit_enabled = False
    limiter.reset()


async def test_login_rate_limited(client, seeded, rate_limits_on):
    rate_limits_on.rate_limit_login_per_minute = 3
    for _ in range(3):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@demo-org.com", "password": "wrong"},
        )
        assert resp.status_code == 401
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@demo-org.com", "password": "Admin@12345"},
    )
    assert resp.status_code == 429
    assert resp.json()["errors"][0]["code"] == "RATE_LIMITED"


async def test_player_register_rate_limited(client, admin_tokens, rate_limits_on):
    from tests.test_devices_api import get_enrollment_key

    rate_limits_on.rate_limit_register_per_minute = 2
    key = await get_enrollment_key(client, admin_tokens)
    for index in range(2):
        resp = await client.post(
            "/api/v1/player/register",
            json={"enrollment_key": key, "serial_no": f"SN-RL-{index}"},
        )
        assert resp.status_code == 200
    resp = await client.post(
        "/api/v1/player/register",
        json={"enrollment_key": key, "serial_no": "SN-RL-OVER"},
    )
    assert resp.status_code == 429


async def test_heartbeat_limited_per_device_not_per_ip(client, admin_tokens, rate_limits_on):
    from tests.test_devices_api import device_headers, enroll_active_device

    rate_limits_on.rate_limit_heartbeat_per_minute = 2
    rate_limits_on.rate_limit_register_per_minute = 100
    dev_a, token_a = await enroll_active_device(client, admin_tokens, "SN-RL-A")
    dev_b, token_b = await enroll_active_device(client, admin_tokens, "SN-RL-B")

    for _ in range(2):
        resp = await client.post(
            f"/api/v1/player/{dev_a}/heartbeat", headers=device_headers(token_a), json={}
        )
        assert resp.status_code == 200
    resp = await client.post(
        f"/api/v1/player/{dev_a}/heartbeat", headers=device_headers(token_a), json={}
    )
    assert resp.status_code == 429

    # Device B (same client IP) is unaffected: keyed per device.
    resp = await client.post(
        f"/api/v1/player/{dev_b}/heartbeat", headers=device_headers(token_b), json={}
    )
    assert resp.status_code == 200


async def test_upload_session_rate_limited(client, admin_tokens, rate_limits_on):
    rate_limits_on.rate_limit_uploads_per_minute = 1
    body = {"filename": "x.png", "mime_type": "image/png", "size_bytes": 10}
    resp = await client.post(
        "/api/v1/assets/uploads", headers=bearer(admin_tokens), json=body
    )
    assert resp.status_code == 201
    resp = await client.post(
        "/api/v1/assets/uploads", headers=bearer(admin_tokens), json=body
    )
    assert resp.status_code == 429


async def test_security_headers_present(client, seeded):
    resp = await client.get("/api/v1/health")
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["Referrer-Policy"] == "no-referrer"
    assert resp.headers["Cache-Control"] == "no-store"
    # Dev environment: no HSTS.
    assert "Strict-Transport-Security" not in resp.headers


async def test_signed_storage_urls_stay_cacheable(client, admin_tokens):
    from tests.test_content_api import upload_asset

    asset = await upload_asset(client, admin_tokens, name="Cacheable")
    resp = await client.get(
        f"/api/v1/assets/{asset['id']}/download-url", headers=bearer(admin_tokens)
    )
    url = resp.json()["data"]["url"]
    fetched = await client.get(url)
    assert fetched.status_code == 200
    assert fetched.headers.get("Cache-Control") != "no-store"
