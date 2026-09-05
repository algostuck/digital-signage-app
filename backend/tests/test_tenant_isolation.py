"""Tenant isolation tests (FR-AUTH-007, ADR-002): mandatory per module."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core import security
from app.models import Organization, Role, User
from tests.conftest import bearer, login


@pytest.fixture
async def org_b(db_engine, seeded):
    """A second tenant with its own admin and one custom role."""
    from sqlalchemy import select

    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session:
        org = Organization(
            name="Org B", code="org-b", status="active", timezone="UTC", locale="en"
        )
        session.add(org)
        await session.flush()

        admin_role = (
            await session.execute(
                select(Role).where(
                    Role.organization_id.is_(None), Role.name == "Organization Administrator"
                )
            )
        ).scalar_one()
        admin = User(
            organization_id=org.id,
            email="admin@org-b-corp.com",
            full_name="B Admin",
            password_hash=security.hash_password("BAdmin@12345"),
            status="active",
        )
        admin.roles = [admin_role]
        session.add(admin)

        custom_role = Role(organization_id=org.id, name="B Only Role", is_system=False)
        session.add(custom_role)
        await session.flush()
        org_id, role_id = org.id, custom_role.id
        await session.commit()
    return {"org_id": org_id, "custom_role_id": role_id}


async def test_users_are_scoped_to_own_tenant(client, admin_tokens, org_b):
    b_tokens = await login(client, "admin@org-b-corp.com", "BAdmin@12345")

    resp = await client.get("/api/v1/users?page_size=200", headers=bearer(admin_tokens))
    emails_a = {u["email"] for u in resp.json()["data"]}
    assert "admin@org-b-corp.com" not in emails_a

    resp = await client.get("/api/v1/users?page_size=200", headers=bearer(b_tokens))
    emails_b = {u["email"] for u in resp.json()["data"]}
    assert emails_b == {"admin@org-b-corp.com"}


async def test_cross_tenant_user_lookup_is_404(client, admin_tokens, org_b):
    b_tokens = await login(client, "admin@org-b-corp.com", "BAdmin@12345")
    b_self_id = b_tokens["user"]["id"]

    resp = await client.get(f"/api/v1/users/{b_self_id}", headers=bearer(admin_tokens))
    assert resp.status_code == 404  # not 403: no existence disclosure


async def test_cross_tenant_role_is_invisible_and_unassignable(client, admin_tokens, org_b):
    resp = await client.get("/api/v1/roles", headers=bearer(admin_tokens))
    names = {r["name"] for r in resp.json()["data"]}
    assert "B Only Role" not in names

    resp = await client.post(
        "/api/v1/users",
        headers=bearer(admin_tokens),
        json={
            "email": "victim@demo-org.com",
            "full_name": "Victim",
            "role_ids": [str(org_b["custom_role_id"])],
        },
    )
    assert resp.status_code == 400


async def test_cross_tenant_role_update_is_404(client, admin_tokens, org_b):
    resp = await client.patch(
        f"/api/v1/roles/{org_b['custom_role_id']}",
        headers=bearer(admin_tokens),
        json={"name": "Stolen"},
    )
    assert resp.status_code == 404


async def test_locations_are_tenant_isolated(client, admin_tokens, org_b):
    b_tokens = await login(client, "admin@org-b-corp.com", "BAdmin@12345")

    # Org B admin sees an empty tree, not org A's seeded hierarchy.
    resp = await client.get("/api/v1/locations/tree", headers=bearer(b_tokens))
    assert resp.json()["data"] == []

    # Cross-tenant location lookup is 404.
    resp = await client.get("/api/v1/locations?q=India", headers=bearer(admin_tokens))
    india_id = resp.json()["data"][0]["id"]
    resp = await client.get(f"/api/v1/locations/{india_id}", headers=bearer(b_tokens))
    assert resp.status_code == 404

    # Cross-tenant parent is rejected as not-found.
    resp = await client.post(
        "/api/v1/locations",
        headers=bearer(b_tokens),
        json={"name": "Sneaky", "parent_id": india_id},
    )
    assert resp.status_code == 404

    # Org B's own nodes work.
    resp = await client.post(
        "/api/v1/locations", headers=bearer(b_tokens), json={"name": "B Root"}
    )
    assert resp.status_code == 201


async def test_devices_are_tenant_isolated(client, admin_tokens, org_b):
    from tests.test_devices_api import enroll_active_device

    device_id, _ = await enroll_active_device(client, admin_tokens, "SN-ISO")
    b_tokens = await login(client, "admin@org-b-corp.com", "BAdmin@12345")

    resp = await client.get("/api/v1/devices?page_size=200", headers=bearer(b_tokens))
    assert device_id not in [d["id"] for d in resp.json()["data"]]

    resp = await client.get(f"/api/v1/devices/{device_id}", headers=bearer(b_tokens))
    assert resp.status_code == 404

    resp = await client.post(
        f"/api/v1/devices/{device_id}/approve", headers=bearer(b_tokens)
    )
    assert resp.status_code == 404

    # Each org's enrollment key registers into that org only.
    key_b = (
        await client.get("/api/v1/devices/enrollment-key", headers=bearer(b_tokens))
    ).json()["data"]["enrollment_key"]
    resp = await client.post(
        "/api/v1/player/register", json={"enrollment_key": key_b, "serial_no": "SN-ISO"}
    )
    reg = resp.json()["data"]
    assert reg["device_id"] != device_id  # same serial, different tenant => new device


async def test_layouts_and_templates_are_tenant_isolated(client, admin_tokens, org_b):
    resp = await client.post(
        "/api/v1/layouts", headers=bearer(admin_tokens), json={"name": "A Layout"}
    )
    layout_id = resp.json()["data"]["id"]

    b_tokens = await login(client, "admin@org-b-corp.com", "BAdmin@12345")
    resp = await client.get(f"/api/v1/layouts/{layout_id}", headers=bearer(b_tokens))
    assert resp.status_code == 404

    # Org B has no seeded templates (seeded only for the demo tenant),
    # and cannot see org A's layouts in listings.
    resp = await client.get("/api/v1/layouts?page_size=200", headers=bearer(b_tokens))
    assert resp.json()["data"] == []

    # Cross-tenant asset binding is rejected at publish.
    from tests.test_content_api import upload_asset

    asset = await upload_asset(client, admin_tokens, name="A-only asset")
    resp = await client.post(
        "/api/v1/layouts", headers=bearer(b_tokens), json={"name": "B Layout"}
    )
    b_layout = resp.json()["data"]
    canvas = b_layout["draft_canvas_json"]
    canvas["zones"][0]["content_type"] = "image"
    canvas["zones"][0]["content_config"] = {"asset_id": asset["id"]}
    await client.patch(
        f"/api/v1/layouts/{b_layout['id']}",
        headers=bearer(b_tokens),
        json={"canvas_json": canvas},
    )
    resp = await client.post(
        f"/api/v1/layouts/{b_layout['id']}/publish", headers=bearer(b_tokens)
    )
    assert resp.status_code == 422


async def test_playlists_are_tenant_isolated(client, admin_tokens, org_b):
    from tests.test_content_api import upload_asset

    resp = await client.post(
        "/api/v1/playlists", headers=bearer(admin_tokens), json={"name": "A Playlist"}
    )
    playlist_id = resp.json()["data"]["id"]
    asset = await upload_asset(client, admin_tokens, name="A Asset For PL")

    b_tokens = await login(client, "admin@org-b-corp.com", "BAdmin@12345")
    resp = await client.get(f"/api/v1/playlists/{playlist_id}", headers=bearer(b_tokens))
    assert resp.status_code == 404

    # Org B cannot reference org A's asset in its own playlist.
    resp = await client.post(
        "/api/v1/playlists", headers=bearer(b_tokens), json={"name": "B Playlist"}
    )
    b_playlist = resp.json()["data"]
    resp = await client.post(
        f"/api/v1/playlists/{b_playlist['id']}/items",
        headers=bearer(b_tokens),
        json={"asset_id": asset["id"], "duration_ms": 1000},
    )
    assert resp.status_code == 404

    # Org B cannot use org A's playlist as fallback.
    resp = await client.patch(
        f"/api/v1/playlists/{b_playlist['id']}",
        headers=bearer(b_tokens),
        json={"fallback_playlist_id": playlist_id},
    )
    assert resp.status_code == 404


async def test_campaigns_and_schedules_are_tenant_isolated(client, admin_tokens, org_b):
    resp = await client.post(
        "/api/v1/campaigns", headers=bearer(admin_tokens), json={"name": "A Campaign"}
    )
    campaign_id = resp.json()["data"]["id"]
    resp = await client.post(
        "/api/v1/schedules",
        headers=bearer(admin_tokens),
        json={"campaign_id": campaign_id},
    )
    schedule_id = resp.json()["data"]["id"]

    b_tokens = await login(client, "admin@org-b-corp.com", "BAdmin@12345")
    resp = await client.get(f"/api/v1/campaigns/{campaign_id}", headers=bearer(b_tokens))
    assert resp.status_code == 404

    # Org B cannot schedule org A's campaign or touch its schedules.
    resp = await client.post(
        "/api/v1/schedules", headers=bearer(b_tokens), json={"campaign_id": campaign_id}
    )
    assert resp.status_code == 404
    resp = await client.delete(f"/api/v1/schedules/{schedule_id}", headers=bearer(b_tokens))
    assert resp.status_code == 404

    # Org B's calendar does not show org A's events.
    resp = await client.get(
        "/api/v1/calendar?from=2026-09-07&to=2026-09-08", headers=bearer(b_tokens)
    )
    assert resp.json()["data"]["events"] == []


async def test_same_email_in_two_tenants_logs_into_correct_org(client, admin_tokens, org_b):
    # Same email as org A's admin, different password, in org B.

    resp = await client.post(
        "/api/v1/users",
        headers=bearer(admin_tokens),
        json={
            "email": "shared@sharedmail.com",
            "full_name": "A Shared",
            "password": "SharedA@123",
            "role_ids": [],
        },
    )
    assert resp.status_code == 201

    b_tokens = await login(client, "admin@org-b-corp.com", "BAdmin@12345")
    resp = await client.post(
        "/api/v1/users",
        headers=bearer(b_tokens),
        json={
            "email": "shared@sharedmail.com",
            "full_name": "B Shared",
            "password": "SharedB@123",
            "role_ids": [],
        },
    )
    assert resp.status_code == 201

    a_login = await login(client, "shared@sharedmail.com", "SharedA@123")
    b_login = await login(client, "shared@sharedmail.com", "SharedB@123")
    assert a_login["user"]["organization_id"] != b_login["user"]["organization_id"]


async def test_campaign_targets_cannot_reference_another_tenant(client, admin_tokens, org_b):
    """A campaign in Tenant A must not accept Tenant B's ids as targets —
    for the replace-set targets call and for variant targets alike."""
    b_tokens = await login(client, "admin@org-b-corp.com", "BAdmin@12345")
    resp = await client.post(
        "/api/v1/locations", headers=bearer(b_tokens), json={"name": "B Store"}
    )
    assert resp.status_code == 201, resp.text
    b_location = resp.json()["data"]["id"]

    resp = await client.post(
        "/api/v1/campaigns", headers=bearer(admin_tokens), json={"name": "A Campaign"}
    )
    campaign_id = resp.json()["data"]["id"]

    resp = await client.post(
        f"/api/v1/campaigns/{campaign_id}/targets",
        headers=bearer(admin_tokens),
        json={"targets": [{"target_type": "location", "target_id": b_location}]},
    )
    assert resp.status_code == 404, resp.text

    resp = await client.post(
        f"/api/v1/campaigns/{campaign_id}/targets",
        headers=bearer(admin_tokens),
        json={"targets": [{"target_type": "device", "target_id": str(uuid.uuid4())}]},
    )
    assert resp.status_code == 404, resp.text

    # The campaign still has no targets stored.
    resp = await client.get(
        f"/api/v1/campaigns/{campaign_id}", headers=bearer(admin_tokens)
    )
    assert resp.json()["data"].get("targets", []) == []

    from tests.test_layouts_api import create_layout

    layout = await create_layout(client, admin_tokens, "A Layout")
    resp = await client.post(
        f"/api/v1/campaigns/{campaign_id}/variants",
        headers=bearer(admin_tokens),
        json={
            "name": "B-targeted variant",
            "layout_id": layout["id"],
            "targets": [{"target_type": "location", "target_id": b_location}],
        },
    )
    assert resp.status_code == 404, resp.text
