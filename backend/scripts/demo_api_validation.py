"""Live API validation for the Indian demo dataset.

Exercises the running API the way the product does — login, tenant
scoping, RBAC and cross-tenant isolation — rather than inspecting the
database. Run against a dev server:

    python scripts/demo_api_validation.py [base_url]
"""

from __future__ import annotations

import sys
import time

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000/api/v1"
DEMO_PASSWORD = "Demo@12345"  # noqa: S105 - documented demo credential

PASS: list[str] = []
FAIL: list[str] = []
# Switching tenants rotates the token pair, so it needs the refresh token
# just like the portal does.
REFRESH: dict[str, str] = {}


def check(ok: bool, label: str, detail: str = "") -> None:
    (PASS if ok else FAIL).append(f"{label}{f' — {detail}' if detail and not ok else ''}")


def login(client: httpx.Client, email: str, password: str) -> tuple[str | None, dict]:
    """The script logs in a dozen times in a burst; the auth rate limiter
    legitimately pushes back, so back off once before giving up."""
    for attempt in range(2):
        response = client.post("/auth/login", json={"email": email, "password": password})
        if response.status_code == 200:
            data = response.json()["data"]
            REFRESH[email] = data["refresh_token"]
            return data["access_token"], data["user"]
        if response.status_code != 429 or attempt:
            return None, {}
        time.sleep(8)
    return None, {}


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def main() -> int:
    with httpx.Client(base_url=BASE, timeout=30) as client:
        # --- platform administrator still works -------------------------
        token, user = login(client, "platform@signage.cloud", "Platform@12345")
        check(token is not None, "platform@signage.cloud can log in")
        if token:
            check(user.get("is_superuser") is True, "platform admin retains superuser")
            response = client.get("/platform/tenants", headers=auth(token))
            check(response.status_code == 200, "platform console lists tenants")
            if response.status_code == 200:
                codes = {t["code"] for t in response.json()["data"]}
                check({"RRL-DEMO", "BMR-DEMO", "USP-DEMO"} <= codes,
                      "all three demo tenants visible to the platform console")

        # --- the test fixture admin is untouched ------------------------
        token, _ = login(client, "admin@demo-org.com", "Admin@12345")
        check(token is not None, "test-fixture admin (admin@demo-org.com) still logs in")

        # --- one login per seeded role ---------------------------------
        role_users = [
            ("arjun.mehta@rrl-demo.signage.cloud", "Organization Administrator"),
            ("priya.sharma@rrl-demo.signage.cloud", "Content Manager"),
            ("rahul.sen@rrl-demo.signage.cloud", "Device Manager"),
            ("sneha.iyer@rrl-demo.signage.cloud", "Campaign Approver"),
            ("vikram.malhotra@rrl-demo.signage.cloud", "Regional Operations Manager"),
            ("neha.kapoor@rrl-demo.signage.cloud", "Report Viewer"),
            ("amit.banerjee@rrl-demo.signage.cloud", "Viewer"),
        ]
        rrl_token = None
        tokens: dict[str, str] = {}
        for email, expected_role in role_users:
            token, user = login(client, email, DEMO_PASSWORD)
            check(token is not None, f"login: {expected_role} ({email.split('@')[0]})")
            if token is None:
                continue
            names = {r["name"] for r in user.get("roles", [])}
            check(expected_role in names, f"role granted: {expected_role}", str(names))
            tokens[expected_role] = token
            if expected_role == "Organization Administrator":
                rrl_token = token

        # --- the admin sees a populated tenant --------------------------
        if rrl_token:
            headers = auth(rrl_token)
            summary = client.get("/monitoring/summary", headers=headers)
            check(summary.status_code == 200, "dashboard summary loads")
            if summary.status_code == 200:
                data = summary.json()["data"]
                check(data["devices"]["total"] > 100,
                      f"dashboard shows a real fleet ({data['devices']['total']} devices)")
                check(data["devices"]["online"] > 0, "dashboard shows online devices")
                check(data["devices"]["offline"] > 0,
                      "dashboard shows offline devices (health mix is not all-green)")

            for path, label in [
                ("/devices?page_size=20", "devices list"),
                ("/locations/tree", "location tree"),
                ("/assets?page_size=20", "content library"),
                ("/campaigns?page_size=50", "campaigns"),
                ("/playlists", "playlists"),
                ("/schedules", "schedules"),
                ("/deployments", "deployments"),
                ("/notifications", "notifications"),
                ("/audit-logs", "audit logs"),
                ("/billing/subscription", "subscription"),
                ("/reports/deployments", "deployment report"),
                ("/reports/playback", "proof-of-play report"),
            ]:
                response = client.get(path, headers=headers)
                ok = response.status_code == 200
                rows = response.json().get("data") if ok else None
                populated = bool(rows)
                check(ok and populated, f"{label} returns data",
                      f"status={response.status_code}")

            # Locations really are a deep Indian hierarchy.
            tree = client.get("/locations/tree", headers=headers)
            if tree.status_code == 200:
                def depth(nodes: list, level: int = 1) -> int:
                    return max(
                        [level] + [depth(n["children"], level + 1) for n in nodes if n["children"]]
                    )
                entries = tree.json()["data"]
                check(depth(entries) >= 5, f"location hierarchy is deep ({depth(entries)} levels)")
                check(entries and entries[0]["node"]["name"] == "India",
                      "location tree is rooted at India")

        # --- cross-tenant isolation (the mandatory check) ---------------
        bmr_token, _ = login(client, "rohan.nair@bharatmart-demo.signage.cloud", DEMO_PASSWORD)
        check(bmr_token is not None, "BharatMart admin can log in")
        if rrl_token and bmr_token:
            rrl_devices = client.get("/devices?page_size=5", headers=auth(rrl_token)).json()["data"]
            bmr_devices = client.get("/devices?page_size=5", headers=auth(bmr_token)).json()["data"]
            rrl_ids = {d["id"] for d in rrl_devices}
            bmr_ids = {d["id"] for d in bmr_devices}
            check(bool(rrl_ids) and bool(bmr_ids), "both tenants return their own devices")
            check(not (rrl_ids & bmr_ids), "tenant device lists do not overlap")

            # A tenant must not be able to fetch another tenant's record by id.
            if bmr_devices:
                victim = bmr_devices[0]["id"]
                response = client.get(f"/devices/{victim}", headers=auth(rrl_token))
                check(response.status_code in (403, 404),
                      "cross-tenant device fetch is refused",
                      f"got {response.status_code}")
            # ...and must not reach the platform console.
            response = client.get("/platform/tenants", headers=auth(rrl_token))
            check(response.status_code == 403,
                  "tenant admin cannot reach the platform console",
                  f"got {response.status_code}")

        # --- one person, two tenants ------------------------------------
        # Reuse the token from the role loop: re-logging in here would
        # push this burst past the auth rate limit for no added coverage.
        guest_token = tokens.get("Regional Operations Manager")
        check(guest_token is not None, "multi-tenant user is authenticated")
        if guest_token:
            response = client.get("/auth/memberships", headers=auth(guest_token))
            memberships = response.json()["data"] if response.status_code == 200 else []
            names = [m["organization_name"] for m in memberships]
            check(len(memberships) == 2, "multi-tenant user sees 2 tenants", str(names))
            check(len(names) == len(set(names)),
                  "tenant switcher lists each organization once", str(names))
            guest = next((m for m in memberships if not m["is_home"]), None)
            if guest:
                switched = client.post(
                    "/auth/switch-tenant",
                    headers=auth(guest_token),
                    json={
                        "organization_id": guest["organization_id"],
                        "refresh_token": REFRESH["vikram.malhotra@rrl-demo.signage.cloud"],
                    },
                )
                check(switched.status_code == 200, "tenant switch succeeds",
                      f"got {switched.status_code}")
                if switched.status_code == 200:
                    new_token = switched.json()["data"]["access_token"]
                    devices = client.get("/devices?page_size=5", headers=auth(new_token))
                    rows = devices.json()["data"] if devices.status_code == 200 else []
                    check(bool(rows), "switched tenant returns its own devices")
                    # The guest role is Viewer in the second tenant.
                    refused = client.post("/campaigns", headers=auth(new_token),
                                          json={"name": "Refused", "priority": 50})
                    check(refused.status_code == 403,
                          "guest role is enforced in the switched tenant",
                          f"got {refused.status_code}")

        # --- RBAC actually restricts -----------------------------------
        viewer_token = tokens.get("Viewer")
        check(viewer_token is not None, "viewer is authenticated for the RBAC check")
        if viewer_token:
            response = client.post("/campaigns", headers=auth(viewer_token),
                                   json={"name": "Should be refused", "priority": 50})
            check(response.status_code == 403, "viewer cannot create a campaign",
                  f"got {response.status_code}")

    for label in PASS:
        print(f"  PASS  {label}")
    for label in FAIL:
        print(f"  FAIL  {label}")
    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
