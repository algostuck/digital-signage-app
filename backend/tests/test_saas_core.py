"""SaaS core tests: plans/entitlements, subscription lifecycle + dunning,
device/user/storage limits with the spec's upgrade messages, suspension
semantics (cached playback survives), memberships and tenant switching,
platform admin surface, legacy (no-subscription) mode, usage counters."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from tests.conftest import bearer, login
from tests.test_devices_api import enroll_active_device, get_enrollment_key, register
from tests.test_tenant_isolation import org_b  # noqa: F401 (fixture)

PLATFORM_EMAIL = "platform@signage.cloud"
PLATFORM_PASSWORD = "Platform@12345"


async def platform_tokens(client) -> dict:
    return await login(client, PLATFORM_EMAIL, PLATFORM_PASSWORD)


# --- plans + platform surface ---


async def test_plans_seeded_and_listed(client, admin_tokens):
    resp = await client.get("/api/v1/plans", headers=bearer(admin_tokens))
    assert resp.status_code == 200
    codes = [p["code"] for p in resp.json()["data"]]
    assert codes == ["starter", "business", "professional", "enterprise"]
    starter = resp.json()["data"][0]
    ent = {e["key"]: e for e in starter["entitlements"]}
    assert ent["max_devices"]["int_value"] == 10
    assert ent["sso"]["bool_value"] is False


async def test_platform_requires_superuser(client, admin_tokens):
    resp = await client.get("/api/v1/platform/tenants", headers=bearer(admin_tokens))
    assert resp.status_code == 403

    tokens = await platform_tokens(client)
    resp = await client.get("/api/v1/platform/tenants", headers=bearer(tokens))
    assert resp.status_code == 200
    demo = next(t for t in resp.json()["data"] if t["code"] == "demo")
    assert demo["plan_code"] == "enterprise"
    assert demo["subscription_status"] == "active"


async def test_platform_creates_tenant_with_owner(client, seeded):
    tokens = await platform_tokens(client)
    resp = await client.post(
        "/api/v1/platform/tenants",
        headers=bearer(tokens),
        json={
            "name": "Acme Retail",
            "code": "acme",
            "owner_email": "owner@acme.example",
            "owner_full_name": "Acme Owner",
            "owner_password": "Owner@12345",
        },
    )
    assert resp.status_code == 200, resp.text
    tenant_id = resp.json()["data"]["id"]

    # Assign a subscription and read it back.
    resp = await client.post(
        f"/api/v1/platform/tenants/{tenant_id}/subscription",
        headers=bearer(tokens),
        json={"plan_code": "starter", "billing_cycle": "monthly"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "active"

    # The owner can log in and sees their own org's billing.
    owner = await login(client, "owner@acme.example", "Owner@12345")
    resp = await client.get("/api/v1/billing/subscription", headers=bearer(owner))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["plan_code"] == "starter"
    assert data["entitlements"]["max_devices"] == 10


# --- billing surface ---


async def test_billing_subscription_shows_entitlements_and_usage(client, admin_tokens):
    resp = await client.get("/api/v1/billing/subscription", headers=bearer(admin_tokens))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["plan_code"] == "enterprise"
    assert data["status"] == "active"
    assert data["entitlements"]["sso"] is True
    assert data["usage"]["devices"]["limit"] == 5000


async def test_entitlements_endpoint_needs_no_billing_permission(client, admin_tokens):
    # UI_UX_API_CHANGES.md: /entitlements is permission-free (any org
    # member) so the frontend can gate locked features without billing.view.
    resp = await client.get("/api/v1/roles", headers=bearer(admin_tokens))
    viewer_id = next(r["id"] for r in resp.json()["data"] if r["name"] == "Viewer")
    resp = await client.post(
        "/api/v1/users",
        headers=bearer(admin_tokens),
        json={
            "email": "ent-viewer@demo-org.com",
            "full_name": "Entitlement Viewer",
            "password": "Viewer@12345",
            "role_ids": [viewer_id],
        },
    )
    assert resp.status_code == 201, resp.text
    viewer = await login(client, "ent-viewer@demo-org.com", "Viewer@12345")
    resp = await client.get("/api/v1/entitlements", headers=bearer(viewer))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["plan_code"] == "enterprise"
    assert data["values"]["sso"] is True


async def test_subscribe_conflicts_then_plan_change_needs_approval(client, admin_tokens):
    resp = await client.post(
        "/api/v1/billing/subscribe",
        headers=bearer(admin_tokens),
        json={"plan_code": "starter"},
    )
    assert resp.status_code == 409  # already actively subscribed

    # Tenant change-plan is a REQUEST — nothing changes yet.
    resp = await client.post(
        "/api/v1/billing/change-plan",
        headers=bearer(admin_tokens),
        json={"plan_code": "professional", "note": "growing fleet"},
    )
    assert resp.status_code == 200
    request_id = resp.json()["data"]["request_id"]
    assert resp.json()["data"]["status"] == "pending"

    billing = (
        await client.get("/api/v1/billing/subscription", headers=bearer(admin_tokens))
    ).json()["data"]
    assert billing["plan_code"] == "enterprise"  # unchanged
    assert billing["pending_plan_request"]["to_plan"] == "professional"

    # Duplicate requests are refused while one is pending.
    resp = await client.post(
        "/api/v1/billing/change-plan",
        headers=bearer(admin_tokens),
        json={"plan_code": "business"},
    )
    assert resp.status_code == 409

    # Super Admin sees the request and approves after the manual payment.
    tokens = await platform_tokens(client)
    requests = (
        await client.get("/api/v1/platform/plan-requests", headers=bearer(tokens))
    ).json()["data"]
    assert any(r["id"] == request_id and r["to_plan"] == "professional" for r in requests)
    resp = await client.post(
        f"/api/v1/platform/plan-requests/{request_id}/approve",
        headers=bearer(tokens),
        json={"decision_note": "payment received via bank transfer"},
    )
    assert resp.status_code == 200

    billing = (
        await client.get("/api/v1/billing/subscription", headers=bearer(admin_tokens))
    ).json()["data"]
    assert billing["plan_code"] == "professional"
    assert billing["pending_plan_request"] is None
    # white_label is Enterprise-only: the feature gate reflects the new plan.
    assert billing["entitlements"]["white_label"] is False


async def test_plan_request_rejection_keeps_plan(client, admin_tokens):
    resp = await client.post(
        "/api/v1/billing/change-plan",
        headers=bearer(admin_tokens),
        json={"plan_code": "starter"},
    )
    request_id = resp.json()["data"]["request_id"]

    tokens = await platform_tokens(client)
    resp = await client.post(
        f"/api/v1/platform/plan-requests/{request_id}/reject",
        headers=bearer(tokens),
        json={"decision_note": "no payment received"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "rejected"

    billing = (
        await client.get("/api/v1/billing/subscription", headers=bearer(admin_tokens))
    ).json()["data"]
    assert billing["plan_code"] == "enterprise"  # unchanged
    # A decided request no longer blocks a new one.
    resp = await client.post(
        "/api/v1/billing/change-plan",
        headers=bearer(admin_tokens),
        json={"plan_code": "business"},
    )
    assert resp.status_code == 200


async def test_platform_edits_tenant_and_changes_plan_directly(client, admin_tokens):
    tokens = await platform_tokens(client)
    tenant_id = await _demo_tenant_id(client, tokens)

    resp = await client.patch(
        f"/api/v1/platform/tenants/{tenant_id}",
        headers=bearer(tokens),
        json={"name": "Demo Organization (Renamed)", "timezone": "Asia/Kolkata"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "Demo Organization (Renamed)"

    # Direct downgrade by the Super Admin — no request needed.
    resp = await client.patch(
        f"/api/v1/platform/tenants/{tenant_id}/subscription/plan",
        headers=bearer(tokens),
        json={"plan_code": "business"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["plan"]["code"] == "business"

    # A tenant admin cannot use the direct endpoints.
    resp = await client.patch(
        f"/api/v1/platform/tenants/{tenant_id}/subscription/plan",
        headers=bearer(admin_tokens),
        json={"plan_code": "enterprise"},
    )
    assert resp.status_code == 403


async def test_cancel_and_reactivate(client, admin_tokens):
    resp = await client.post(
        "/api/v1/billing/cancel", headers=bearer(admin_tokens), json={"at_period_end": True}
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["cancel_at"] is not None

    resp = await client.post("/api/v1/billing/reactivate", headers=bearer(admin_tokens))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "active"
    assert data["cancel_at"] is None


async def test_billing_requires_permission(client, admin_tokens, org_b):  # noqa: F811
    # A viewer-role user may view billing but not manage it.
    resp = await client.get("/api/v1/roles", headers=bearer(admin_tokens))
    viewer_id = next(r["id"] for r in resp.json()["data"] if r["name"] == "Viewer")
    resp = await client.post(
        "/api/v1/users",
        headers=bearer(admin_tokens),
        json={
            "email": "viewer@demo-org.com",
            "full_name": "Viewer",
            "password": "Viewer@12345",
            "role_ids": [viewer_id],
        },
    )
    assert resp.status_code == 201, resp.text
    viewer = await login(client, "viewer@demo-org.com", "Viewer@12345")

    resp = await client.get("/api/v1/billing/subscription", headers=bearer(viewer))
    assert resp.status_code == 200
    resp = await client.post(
        "/api/v1/billing/cancel", headers=bearer(viewer), json={"at_period_end": True}
    )
    assert resp.status_code == 403


# --- limits (the spec's exact refusal messages) ---


async def _tighten_devices_to_current(client, admin_tokens):
    """Create a plan whose device cap equals the demo org's current count
    and move the org onto it (direct platform change)."""
    tokens = await platform_tokens(client)
    tenant_id = await _demo_tenant_id(client, tokens)
    usage = (
        await client.get("/api/v1/organization/usage", headers=bearer(admin_tokens))
    ).json()["data"]
    used = usage["devices"]["used"]
    resp = await client.post(
        "/api/v1/platform/plans",
        headers=bearer(tokens),
        json={
            "code": "tiny-test",
            "name": "Tiny Test",
            "prices": {},
            "entitlements": [{"key": "max_devices", "int_value": used}],
        },
    )
    assert resp.status_code == 200, resp.text
    resp = await client.patch(
        f"/api/v1/platform/tenants/{tenant_id}/subscription/plan",
        headers=bearer(tokens),
        json={"plan_code": "tiny-test"},
    )
    assert resp.status_code == 200
    return used


async def test_device_limit_blocks_next_registration(client, admin_tokens):
    used = await _tighten_devices_to_current(client, admin_tokens)
    key = await get_enrollment_key(client, admin_tokens)
    resp = await client.post(
        "/api/v1/player/register",
        json={"enrollment_key": key, "serial_no": "SN-OVER-PLAN"},
    )
    assert resp.status_code == 422
    assert f"Device limit reached ({used}/{used})" in resp.text
    assert "Upgrade your subscription" in resp.text


async def _demo_tenant_id(client, tokens) -> str:
    tenants = (
        await client.get("/api/v1/platform/tenants", headers=bearer(tokens))
    ).json()["data"]
    return next(t["id"] for t in tenants if t["code"] == "demo")


async def test_quota_override_can_only_tighten_below_plan(client, admin_tokens):
    # Enterprise allows 5000 devices; a platform quota of 1 wins. Quota
    # editing is Super Admin-only — the tenant surface is read-only.
    tokens = await platform_tokens(client)
    tenant_id = await _demo_tenant_id(client, tokens)
    resp = await client.patch(
        f"/api/v1/platform/tenants/{tenant_id}/quotas",
        headers=bearer(tokens),
        json={"max_devices": 1},
    )
    assert resp.status_code == 200, resp.text
    usage = (
        await client.get("/api/v1/organization/usage", headers=bearer(admin_tokens))
    ).json()["data"]
    assert usage["devices"]["limit"] == 1

    # A tenant admin cannot reach the platform quota endpoint.
    resp = await client.patch(
        f"/api/v1/platform/tenants/{tenant_id}/quotas",
        headers=bearer(admin_tokens),
        json={"max_devices": 5000},
    )
    assert resp.status_code == 403


async def test_invoice_download_and_provider_management(client, admin_tokens, org_b):  # noqa: F811
    b_tokens = await login(client, "admin@org-b-corp.com", "BAdmin@12345")
    resp = await client.post(
        "/api/v1/billing/subscribe",
        headers=bearer(b_tokens),
        json={"plan_code": "starter", "billing_cycle": "monthly"},
    )
    assert resp.status_code == 200, resp.text
    invoice = (
        await client.get("/api/v1/billing/invoices", headers=bearer(b_tokens))
    ).json()["data"][0]

    # Tenant download: printable HTML attachment.
    resp = await client.get(
        f"/api/v1/billing/invoices/{invoice['id']}/download", headers=bearer(b_tokens)
    )
    assert resp.status_code == 200
    assert "attachment" in resp.headers["content-disposition"]
    assert invoice["number"] in resp.text
    assert "Org B" in resp.text

    # Cross-tenant: demo admin cannot download org B's invoice.
    resp = await client.get(
        f"/api/v1/billing/invoices/{invoice['id']}/download", headers=bearer(admin_tokens)
    )
    assert resp.status_code == 404

    # Platform: same document + provider switch (gateway refs only — no keys).
    tokens = await platform_tokens(client)
    resp = await client.get(
        f"/api/v1/platform/tenants/{org_b['org_id']}/invoices/{invoice['id']}/download",
        headers=bearer(tokens),
    )
    assert resp.status_code == 200
    resp = await client.patch(
        f"/api/v1/platform/tenants/{org_b['org_id']}/subscription/provider",
        headers=bearer(tokens),
        json={"provider": "razorpay", "provider_customer_id": "cust_123"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["provider"] == "razorpay"
    resp = await client.patch(
        f"/api/v1/platform/tenants/{org_b['org_id']}/subscription/provider",
        headers=bearer(tokens),
        json={"provider": "paypal"},
    )
    assert resp.status_code == 400  # not a known provider adapter


# --- suspension semantics ---


async def test_suspension_blocks_growth_but_not_playback(client, admin_tokens):
    device_id, device_token = await enroll_active_device(
        client, admin_tokens, "SN-SUSPEND-1"
    )

    tokens = await platform_tokens(client)
    demo = next(
        t
        for t in (
            await client.get("/api/v1/platform/tenants", headers=bearer(tokens))
        ).json()["data"]
        if t["code"] == "demo"
    )
    resp = await client.post(
        f"/api/v1/platform/tenants/{demo['id']}/subscription/transition",
        headers=bearer(tokens),
        json={"to_status": "suspended", "event": "test_suspend"},
    )
    assert resp.status_code == 200

    # Growth actions refuse...
    key = await get_enrollment_key(client, admin_tokens)
    resp = await client.post(
        "/api/v1/player/register",
        json={"enrollment_key": key, "serial_no": "SN-WHILE-SUSPENDED"},
    )
    assert resp.status_code == 422
    assert "suspended" in resp.text

    resp = await client.post(
        "/api/v1/campaigns",
        headers=bearer(admin_tokens),
        json={"name": "Blocked Campaign"},
    )
    assert resp.status_code == 422

    resp = await client.post(
        "/api/v1/assets/uploads",
        headers=bearer(admin_tokens),
        json={"filename": "x.png", "mime_type": "image/png", "size_bytes": 1024},
    )
    assert resp.status_code == 422

    # ...but the existing display keeps its heartbeat and manifest (never
    # blank a screen over billing).
    resp = await client.post(
        f"/api/v1/player/{device_id}/heartbeat",
        headers={"X-Device-Token": device_token},
        json={},
    )
    assert resp.status_code == 200
    resp = await client.get(
        f"/api/v1/player/{device_id}/manifest",
        headers={"X-Device-Token": device_token},
    )
    assert resp.status_code == 200

    # A suspended tenant cannot self-reactivate — payment (or a platform
    # action) is required.
    resp = await client.post("/api/v1/billing/reactivate", headers=bearer(admin_tokens))
    assert resp.status_code == 422
    assert "payment" in resp.text.lower()

    # Platform-side reactivation restores growth.
    resp = await client.post(
        f"/api/v1/platform/tenants/{demo['id']}/subscription/transition",
        headers=bearer(tokens),
        json={"to_status": "active", "event": "payment_reconciled"},
    )
    assert resp.status_code == 200
    resp = await client.post(
        "/api/v1/player/register",
        json={"enrollment_key": key, "serial_no": "SN-AFTER-REACTIVATE"},
    )
    assert resp.status_code == 200


# --- lifecycle: invoices, payment, dunning ladder ---


async def test_invoice_payment_clears_dunning(client, admin_tokens, org_b, db_engine):  # noqa: F811
    b_tokens = await login(client, "admin@org-b-corp.com", "BAdmin@12345")
    resp = await client.post(
        "/api/v1/billing/subscribe",
        headers=bearer(b_tokens),
        json={"plan_code": "starter", "billing_cycle": "monthly"},
    )
    assert resp.status_code == 200, resp.text

    invoices = (
        await client.get("/api/v1/billing/invoices", headers=bearer(b_tokens))
    ).json()["data"]
    assert len(invoices) == 1
    assert invoices[0]["status"] == "issued"
    assert invoices[0]["number"].startswith("INV-")

    tokens = await platform_tokens(client)
    resp = await client.post(
        f"/api/v1/platform/tenants/{org_b['org_id']}/subscription/transition",
        headers=bearer(tokens),
        json={"to_status": "past_due", "event": "test_dunning"},
    )
    assert resp.status_code == 200

    resp = await client.post(
        f"/api/v1/platform/tenants/{org_b['org_id']}/payments",
        headers=bearer(tokens),
        json={"invoice_id": invoices[0]["id"]},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "paid"

    resp = await client.get("/api/v1/billing/subscription", headers=bearer(b_tokens))
    assert resp.json()["data"]["status"] == "active"


async def test_dunning_ladder_escalates_by_overdue_days(client, admin_tokens, org_b, db_engine):  # noqa: F811
    from app.models import Invoice
    from app.services import entitlements as entitlements_service
    from app.services.subscriptions import run_lifecycle

    b_tokens = await login(client, "admin@org-b-corp.com", "BAdmin@12345")
    resp = await client.post(
        "/api/v1/billing/subscribe",
        headers=bearer(b_tokens),
        json={"plan_code": "business", "billing_cycle": "monthly"},
    )
    assert resp.status_code == 200

    factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def backdate_and_run(days: int) -> str:
        async with factory() as session:
            invoice = (
                await session.execute(
                    select(Invoice).where(Invoice.organization_id == org_b["org_id"])
                )
            ).scalars().first()
            invoice.due_at = datetime.now(UTC) - timedelta(days=days)
            await session.flush()
            await run_lifecycle(session)
            subscription = await entitlements_service.current_subscription(
                session, org_b["org_id"]
            )
            status = subscription.status
            await session.commit()
            return status

    assert await backdate_and_run(1) == "past_due"
    assert await backdate_and_run(8) == "grace_period"
    assert await backdate_and_run(15) == "suspended"
    # Idempotent: re-running at the same overdue depth changes nothing.
    assert await backdate_and_run(16) == "suspended"


# --- legacy mode (no subscription) ---


async def test_org_without_subscription_is_unrestricted(client, org_b):  # noqa: F811
    b_tokens = await login(client, "admin@org-b-corp.com", "BAdmin@12345")
    resp = await client.get("/api/v1/billing/subscription", headers=bearer(b_tokens))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["subscription"] is None
    assert data["entitlements"]["max_devices"] is None  # unlimited
    assert data["entitlements"]["sso"] is True  # legacy: features on

    resp = await client.get("/api/v1/devices/enrollment-key", headers=bearer(b_tokens))
    key = resp.json()["data"]["enrollment_key"]
    reg = await register(client, key, "SN-LEGACY-1")
    assert reg["status"] == "pending"


# --- memberships + tenant switching ---


async def test_guest_membership_and_tenant_switch(client, admin_tokens, org_b):  # noqa: F811
    # Grant org B's admin guest Viewer access to the demo org.
    resp = await client.get("/api/v1/roles", headers=bearer(admin_tokens))
    viewer_id = next(r["id"] for r in resp.json()["data"] if r["name"] == "Viewer")
    resp = await client.post(
        "/api/v1/organization/members",
        headers=bearer(admin_tokens),
        json={"email": "admin@org-b-corp.com", "role_id": viewer_id},
    )
    assert resp.status_code == 200, resp.text
    membership_id = resp.json()["data"]["membership_id"]

    # The guest sees both tenants...
    b_tokens = await login(client, "admin@org-b-corp.com", "BAdmin@12345")
    resp = await client.get("/api/v1/auth/memberships", headers=bearer(b_tokens))
    assert resp.status_code == 200
    tenants = resp.json()["data"]
    assert len(tenants) == 2
    guest_row = next(t for t in tenants if not t["is_home"])
    assert guest_row["role_name"] == "Viewer"

    # ...and can switch into the demo org.
    resp = await client.post(
        "/api/v1/auth/switch-tenant",
        headers=bearer(b_tokens),
        json={
            "organization_id": guest_row["organization_id"],
            "refresh_token": b_tokens["refresh_token"],
        },
    )
    assert resp.status_code == 200, resp.text
    switched = resp.json()["data"]
    assert switched["user"]["active_organization_id"] == guest_row["organization_id"]
    assert "users.view" in switched["user"]["permissions"]
    assert "users.manage" not in switched["user"]["permissions"]

    # In the demo org the guest reads with Viewer permissions only.
    resp = await client.get("/api/v1/devices", headers=bearer(switched))
    assert resp.status_code == 200
    resp = await client.post(
        "/api/v1/users",
        headers=bearer(switched),
        json={
            "email": "hax@demo-org.com",
            "full_name": "Nope",
            "password": "Nope@12345",
            "role_ids": [],
        },
    )
    assert resp.status_code == 403

    # /auth/me reflects the active tenant, not the home tenant.
    resp = await client.get("/api/v1/auth/me", headers=bearer(switched))
    assert resp.json()["data"]["active_organization_id"] == guest_row["organization_id"]

    # ...and so does a refresh. The portal restores its session from the
    # refresh token on every page load; if that response reported the home
    # org, the tenant switcher would show the wrong organization while the
    # API stayed scoped to the switched one.
    resp = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": switched["refresh_token"]}
    )
    assert resp.status_code == 200, resp.text
    refreshed = resp.json()["data"]
    assert refreshed["user"]["active_organization_id"] == guest_row["organization_id"]
    switched = refreshed

    # Removing the membership kills the switched token.
    resp = await client.delete(
        f"/api/v1/organization/members/{membership_id}", headers=bearer(admin_tokens)
    )
    assert resp.status_code == 200
    resp = await client.get("/api/v1/devices", headers=bearer(switched))
    assert resp.status_code == 401


async def test_membership_add_validations(client, admin_tokens, org_b):  # noqa: F811
    resp = await client.get("/api/v1/roles", headers=bearer(admin_tokens))
    viewer_id = next(r["id"] for r in resp.json()["data"] if r["name"] == "Viewer")

    # Home users cannot be re-added as guests.
    resp = await client.post(
        "/api/v1/organization/members",
        headers=bearer(admin_tokens),
        json={"email": "admin@demo-org.com", "role_id": viewer_id},
    )
    assert resp.status_code == 422

    # Unknown platform user.
    resp = await client.post(
        "/api/v1/organization/members",
        headers=bearer(admin_tokens),
        json={"email": "ghost@nowhere.example", "role_id": viewer_id},
    )
    assert resp.status_code == 404

    # Duplicates conflict.
    resp = await client.post(
        "/api/v1/organization/members",
        headers=bearer(admin_tokens),
        json={"email": "admin@org-b-corp.com", "role_id": viewer_id},
    )
    assert resp.status_code == 200
    resp = await client.post(
        "/api/v1/organization/members",
        headers=bearer(admin_tokens),
        json={"email": "admin@org-b-corp.com", "role_id": viewer_id},
    )
    assert resp.status_code == 409


async def test_switch_tenant_without_membership_is_401(client, admin_tokens, org_b):  # noqa: F811
    resp = await client.post(
        "/api/v1/auth/switch-tenant",
        headers=bearer(admin_tokens),
        json={
            "organization_id": str(org_b["org_id"]),
            "refresh_token": admin_tokens["refresh_token"],
        },
    )
    assert resp.status_code == 401


async def test_platform_admin_can_switch_into_any_active_tenant(client, admin_tokens, org_b):  # noqa: F811
    """A superuser needs no tenant_users row: every active organization is
    listed by the switcher and can be entered; a normal admin still cannot."""
    tokens = await platform_tokens(client)

    resp = await client.get("/api/v1/auth/memberships", headers=bearer(tokens))
    assert resp.status_code == 200
    tenants = resp.json()["data"]
    listed = {t["organization_id"] for t in tenants}
    assert str(org_b["org_id"]) in listed, "org B has no membership row yet must be listed"
    assert sum(1 for t in tenants if t["is_home"]) == 1

    # Every active organization is present, none listed twice.
    resp = await client.get("/api/v1/platform/tenants", headers=bearer(tokens))
    active = {t["id"] for t in resp.json()["data"] if t["status"] == "active"}
    assert active <= listed
    assert len(listed) == len(tenants)

    resp = await client.post(
        "/api/v1/auth/switch-tenant",
        headers=bearer(tokens),
        json={
            "organization_id": str(org_b["org_id"]),
            "refresh_token": tokens["refresh_token"],
        },
    )
    assert resp.status_code == 200, resp.text
    switched = resp.json()["data"]
    assert switched["user"]["active_organization_id"] == str(org_b["org_id"])

    # The switched token is scoped to org B and works for tenant reads.
    resp = await client.get(
        "/api/v1/devices", headers={"Authorization": f"Bearer {switched['access_token']}"}
    )
    assert resp.status_code == 200

    # A suspended tenant is not offered and cannot be entered.
    resp = await client.patch(
        f"/api/v1/platform/tenants/{org_b['org_id']}/status",
        headers=bearer(tokens),
        json={"status": "suspended"},
    )
    assert resp.status_code == 200
    resp = await client.get("/api/v1/auth/memberships", headers=bearer(tokens))
    assert str(org_b["org_id"]) not in {t["organization_id"] for t in resp.json()["data"]}


# --- usage counters ---


async def test_usage_snapshot_populates_counters(client, admin_tokens, db_engine):
    from app.services.usage import snapshot_usage

    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session:
        await snapshot_usage(session)
        await session.commit()

    resp = await client.get("/api/v1/billing/usage", headers=bearer(admin_tokens))
    assert resp.status_code == 200
    metrics = {row["metric"]: row for row in resp.json()["data"]}
    assert metrics["devices"]["used"] >= 3  # seeded demo devices
    assert metrics["devices"]["limit"] == 5000  # enterprise plan
    assert "storage_mb" in metrics


# --- platform console reads (tenant detail, cross-tenant invoices) ---


async def test_platform_reads_one_tenant_and_all_invoices(client, admin_tokens, org_b):  # noqa: F811
    tokens = await platform_tokens(client)

    # Single tenant carries the profile fields the console edits.
    resp = await client.get(
        f"/api/v1/platform/tenants/{org_b['org_id']}", headers=bearer(tokens)
    )
    assert resp.status_code == 200, resp.text
    tenant = resp.json()["data"]
    assert tenant["id"] == str(org_b["org_id"])
    assert {"timezone", "region", "locale", "quotas", "devices", "users"} <= tenant.keys()

    resp = await client.get(
        f"/api/v1/platform/tenants/{org_b['org_id']}", headers=bearer(admin_tokens)
    )
    assert resp.status_code == 403

    # Give org B a subscription so it has an invoice, then read the ledger.
    resp = await client.post(
        f"/api/v1/platform/tenants/{org_b['org_id']}/subscription",
        headers=bearer(tokens),
        json={"plan_code": "business", "billing_cycle": "monthly"},
    )
    assert resp.status_code == 200, resp.text

    resp = await client.get("/api/v1/platform/invoices", headers=bearer(tokens))
    assert resp.status_code == 200
    rows = resp.json()["data"]
    mine = [r for r in rows if r["organization_id"] == str(org_b["org_id"])]
    assert mine, "org B's invoice should appear in the platform ledger"
    assert mine[0]["organization_code"] == tenant["code"]
    assert mine[0]["plan_code"] == "business"
    assert mine[0]["status"] == "issued"

    # Filters narrow, never widen.
    resp = await client.get(
        "/api/v1/platform/invoices",
        headers=bearer(tokens),
        params={"tenant_id": str(org_b["org_id"]), "status": "paid"},
    )
    assert resp.json()["data"] == []

    resp = await client.get("/api/v1/platform/invoices", headers=bearer(admin_tokens))
    assert resp.status_code == 403
