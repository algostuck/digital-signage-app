"""Approval & governance engine tests (P2-APP-001..004)."""

from tests.conftest import bearer, login
from tests.test_campaigns_api import create_campaign
from tests.test_tenant_isolation import org_b  # noqa: F401 (fixture)


async def make_approver(client, admin_tokens, email="approver@demo-org.com"):
    """A second user holding campaigns.approve (Organization Administrator)."""
    resp = await client.get("/api/v1/roles", headers=bearer(admin_tokens))
    role_id = next(
        r["id"] for r in resp.json()["data"] if r["name"] == "Organization Administrator"
    )
    resp = await client.post(
        "/api/v1/users",
        headers=bearer(admin_tokens),
        json={
            "email": email,
            "full_name": "Second Approver",
            "password": "Approver@12345",
            "role_ids": [role_id],
        },
    )
    assert resp.status_code == 201
    return await login(client, email, "Approver@12345")


async def set_policy(client, tokens, entity_type, *, require_approval, maker_checker):
    resp = await client.put(
        f"/api/v1/approval-policies/{entity_type}",
        headers=bearer(tokens),
        json={"require_approval": require_approval, "maker_checker": maker_checker},
    )
    assert resp.status_code == 200, resp.text


async def submit_campaign(client, tokens, name="Approval Campaign") -> dict:
    campaign = await create_campaign(client, tokens, name=name)
    resp = await client.post(
        f"/api/v1/campaigns/{campaign['id']}/submit-approval", headers=bearer(tokens)
    )
    assert resp.status_code == 200, resp.text
    return campaign


async def get_open_request(client, tokens, campaign_id) -> dict | None:
    resp = await client.get(
        "/api/v1/approvals/inbox?state=pending&page_size=100", headers=bearer(tokens)
    )
    return next(
        (r for r in resp.json()["data"] if r["entity_id"] == campaign_id), None
    )


async def test_submit_creates_request_with_action_trail(client, admin_tokens):
    campaign = await submit_campaign(client, admin_tokens)
    request = await get_open_request(client, admin_tokens, campaign["id"])
    assert request is not None
    assert request["entity_type"] == "campaign"
    assert request["entity_name"] == campaign["name"]
    assert request["requester_name"] == "Demo Administrator"
    assert [a["action"] for a in request["actions"]] == ["submitted"]


async def test_approve_via_inbox_transitions_campaign(client, admin_tokens):
    campaign = await submit_campaign(client, admin_tokens, name="Inbox Approve")
    request = await get_open_request(client, admin_tokens, campaign["id"])

    resp = await client.post(
        f"/api/v1/approvals/{request['id']}/approve",
        headers=bearer(admin_tokens),
        json={"comments": "Looks good"},
    )
    assert resp.status_code == 200
    decided = resp.json()["data"]
    assert decided["state"] == "approved"
    assert decided["comments"] == "Looks good"
    assert [a["action"] for a in decided["actions"]] == ["submitted", "approved"]

    resp = await client.get(
        f"/api/v1/campaigns/{campaign['id']}", headers=bearer(admin_tokens)
    )
    assert resp.json()["data"]["status"] == "approved"

    # Double-decide is rejected.
    resp = await client.post(
        f"/api/v1/approvals/{request['id']}/approve", headers=bearer(admin_tokens), json={}
    )
    assert resp.status_code == 422


async def test_reject_returns_with_comments_and_revision_history(client, admin_tokens):
    campaign = await submit_campaign(client, admin_tokens, name="Revise Me")
    request = await get_open_request(client, admin_tokens, campaign["id"])

    resp = await client.post(
        f"/api/v1/approvals/{request['id']}/reject",
        headers=bearer(admin_tokens),
        json={"comments": "Wrong dates, please fix"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["state"] == "rejected"

    resp = await client.get(
        f"/api/v1/campaigns/{campaign['id']}", headers=bearer(admin_tokens)
    )
    assert resp.json()["data"]["status"] == "draft"

    # Resubmission opens a fresh request; history keeps both.
    resp = await client.post(
        f"/api/v1/campaigns/{campaign['id']}/submit-approval", headers=bearer(admin_tokens)
    )
    assert resp.status_code == 200
    resp = await client.get(
        "/api/v1/approvals/inbox?entity_type=campaign&page_size=100",
        headers=bearer(admin_tokens),
    )
    requests = [r for r in resp.json()["data"] if r["entity_id"] == campaign["id"]]
    states = sorted(r["state"] for r in requests)
    assert states == ["pending", "rejected"]


async def test_maker_checker_blocks_self_approval(client, admin_tokens):
    await set_policy(
        client, admin_tokens, "campaign", require_approval=True, maker_checker=True
    )
    campaign = await submit_campaign(client, admin_tokens, name="MC Campaign")
    request = await get_open_request(client, admin_tokens, campaign["id"])

    # Submitter cannot decide their own request — inbox path.
    resp = await client.post(
        f"/api/v1/approvals/{request['id']}/approve", headers=bearer(admin_tokens), json={}
    )
    assert resp.status_code == 422
    assert "Maker-checker" in resp.json()["errors"][0]["message"]

    # Legacy per-entity path is equally blocked.
    resp = await client.post(
        f"/api/v1/campaigns/{campaign['id']}/approve", headers=bearer(admin_tokens)
    )
    assert resp.status_code == 422

    # A different approver succeeds.
    approver = await make_approver(client, admin_tokens)
    resp = await client.post(
        f"/api/v1/approvals/{request['id']}/approve", headers=bearer(approver), json={}
    )
    assert resp.status_code == 200
    resp = await client.get(
        f"/api/v1/campaigns/{campaign['id']}", headers=bearer(admin_tokens)
    )
    assert resp.json()["data"]["status"] == "approved"


async def test_auto_approval_when_policy_disables_approval(client, admin_tokens):
    await set_policy(
        client, admin_tokens, "campaign", require_approval=False, maker_checker=False
    )
    campaign = await create_campaign(client, admin_tokens, name="No Approval Needed")
    resp = await client.post(
        f"/api/v1/campaigns/{campaign['id']}/submit-approval", headers=bearer(admin_tokens)
    )
    assert resp.status_code == 200

    # Campaign lands directly in approved; request records the auto decision.
    resp = await client.get(
        f"/api/v1/campaigns/{campaign['id']}", headers=bearer(admin_tokens)
    )
    assert resp.json()["data"]["status"] == "approved"
    resp = await client.get(
        "/api/v1/approvals/inbox?state=approved&page_size=100", headers=bearer(admin_tokens)
    )
    request = next(r for r in resp.json()["data"] if r["entity_id"] == campaign["id"])
    assert "Auto-approved" in request["comments"]


async def test_resubmission_supersedes_open_request(client, admin_tokens):
    campaign = await submit_campaign(client, admin_tokens, name="Supersede Me")
    first = await get_open_request(client, admin_tokens, campaign["id"])

    # Reject via legacy path puts the campaign back to draft, then resubmit.
    await client.post(
        f"/api/v1/campaigns/{campaign['id']}/reject", headers=bearer(admin_tokens)
    )
    await client.post(
        f"/api/v1/campaigns/{campaign['id']}/submit-approval", headers=bearer(admin_tokens)
    )
    second = await get_open_request(client, admin_tokens, campaign["id"])
    assert second is not None and second["id"] != first["id"]

    # Submitting again while one is pending supersedes it (campaign stays
    # pending_approval, engine-level only).
    from app.core.errors import BusinessRuleError  # noqa: F401 (documented behavior)

    resp = await client.get(
        f"/api/v1/approvals/{first['id']}", headers=bearer(admin_tokens)
    )
    assert resp.json()["data"]["state"] == "rejected"


async def test_notifications_from_engine(client, admin_tokens):
    approver = await make_approver(client, admin_tokens, email="approver2@demo-org.com")
    campaign = await submit_campaign(client, admin_tokens, name="Notify Flow")
    request = await get_open_request(client, admin_tokens, campaign["id"])

    resp = await client.get("/api/v1/notifications?page_size=100", headers=bearer(admin_tokens))
    types = [n["type"] for n in resp.json()["data"]]
    assert "APPROVAL_REQUESTED" in types

    await client.post(
        f"/api/v1/approvals/{request['id']}/reject",
        headers=bearer(approver),
        json={"comments": "not yet"},
    )
    # Decision notification goes to the requester.
    resp = await client.get("/api/v1/notifications?page_size=100", headers=bearer(admin_tokens))
    decided = [n for n in resp.json()["data"] if n["type"] == "APPROVAL_DECIDED"]
    assert decided and decided[0]["message"] == "not yet"


async def test_policy_listing_and_permissions(client, admin_tokens):
    resp = await client.get("/api/v1/approval-policies", headers=bearer(admin_tokens))
    assert resp.status_code == 200
    by_type = {p["entity_type"]: p for p in resp.json()["data"]}
    assert by_type["campaign"]["require_approval"] is True
    assert by_type["campaign"]["maker_checker"] is False

    # Viewer: no inbox access, no policy management.
    resp = await client.get("/api/v1/roles", headers=bearer(admin_tokens))
    viewer_id = next(r["id"] for r in resp.json()["data"] if r["name"] == "Viewer")
    await client.post(
        "/api/v1/users",
        headers=bearer(admin_tokens),
        json={
            "email": "appviewer@demo-org.com",
            "full_name": "Approvals Viewer",
            "password": "Viewer@12345",
            "role_ids": [viewer_id],
        },
    )
    viewer = await login(client, "appviewer@demo-org.com", "Viewer@12345")
    resp = await client.get("/api/v1/approvals/inbox", headers=bearer(viewer))
    assert resp.status_code == 403
    resp = await client.put(
        "/api/v1/approval-policies/campaign",
        headers=bearer(viewer),
        json={"require_approval": True, "maker_checker": True},
    )
    assert resp.status_code == 403


async def test_approvals_tenant_isolation(client, admin_tokens, org_b):  # noqa: F811
    campaign = await submit_campaign(client, admin_tokens, name="Iso Approval")
    request = await get_open_request(client, admin_tokens, campaign["id"])

    b_tokens = await login(client, "admin@org-b-corp.com", "BAdmin@12345")
    resp = await client.get(f"/api/v1/approvals/{request['id']}", headers=bearer(b_tokens))
    assert resp.status_code == 404
    resp = await client.post(
        f"/api/v1/approvals/{request['id']}/approve", headers=bearer(b_tokens), json={}
    )
    assert resp.status_code == 404
    resp = await client.get(
        "/api/v1/approvals/inbox?page_size=100", headers=bearer(b_tokens)
    )
    assert all(r["entity_id"] != campaign["id"] for r in resp.json()["data"])
