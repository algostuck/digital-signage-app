"""Subscription & entitlement audit against a running API.

Plan -> entitlement -> usage -> limit -> feature access, exercised end to
end on the throwaway `e2e-audit` tenant (created by audit_e2e_journey.py,
or here if missing). Nothing in the seeded demo tenants is touched.

  1. Feature gates on the Business plan (AI, SSO, video walls, experiments,
     edge bundles, fleet rules, developer portal, advertising, white label)
  2. Numeric limits through platform quota overrides: device, user and
     storage limits reached, and whether decommissioned devices still count
  3. Subscription lifecycle: suspended / grace period / past due /
     cancelled / expired / renewed — growth actions blocked or allowed,
     players never blanked
  4. Plan upgrade and downgrade: entitlements follow the plan, features
     switch on and off, usage above the new limit
  5. API-key access follows the `api_access` entitlement

Every refusal must carry a message that says *why* (limit n/m, plan name,
subscription status) — the UI shows these messages verbatim.

    python scripts/audit_entitlements.py [--base http://localhost:8000] [--report path.json]
"""

# ruff: noqa: E501 - long request literals read better on one line
from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from dataclasses import asdict, dataclass

import httpx

PLATFORM = ("platform@signage.cloud", "Platform@12345")  # noqa: S105 - documented demo credential
OWNER = ("owner@e2e-audit.signage.cloud", "E2eAudit@12345")  # noqa: S105 - throwaway tenant
TENANT_CODE = "e2e-audit"
ZERO = "00000000-0000-4000-8000-000000000000"


@dataclass
class Step:
    phase: str
    name: str
    ok: bool
    detail: str = ""


class Audit:
    def __init__(self, base: str):
        self.api = httpx.Client(base_url=base + "/api/v1", timeout=60)
        self.raw = httpx.Client(base_url=base, timeout=60)
        self.steps: list[Step] = []
        self.phase = ""
        self.tenant_id = ""
        self.platform = ""
        self.owner = ""

    def check(self, name: str, ok: bool, detail: str = "") -> bool:
        self.steps.append(Step(self.phase, name, bool(ok), "" if ok else detail[:300]))
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}{'' if ok else '  — ' + detail[:170]}")
        return bool(ok)

    @staticmethod
    def msg(r: httpx.Response) -> str:
        try:
            return "; ".join(e.get("message", "") for e in r.json().get("errors") or [])
        except ValueError:
            return r.text[:200]

    def refused(self, name: str, r: httpx.Response, *needles: str) -> bool:
        """A refusal must be 4xx *and* explain itself."""
        m = self.msg(r).lower()
        ok = r.status_code in (403, 422) and all(n.lower() in m for n in needles)
        return self.check(name, ok, f"{r.status_code} {self.msg(r)}")

    def allowed(self, name: str, r: httpx.Response) -> bool:
        return self.check(name, r.status_code < 300, f"{r.status_code} {self.msg(r)}")

    def login(self, email: str, password: str) -> str:
        for attempt in range(4):
            r = self.api.post("/auth/login", json={"email": email, "password": password})
            if r.status_code == 200:
                return r.json()["data"]["access_token"]
            if r.status_code != 429:
                raise RuntimeError(f"login {email}: {r.status_code} {r.text[:200]}")
            time.sleep(8 * (attempt + 1))
        raise RuntimeError(f"login {email}: rate limited")

    @staticmethod
    def h(token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    # -- platform helpers ------------------------------------------------------
    def set_status(self, status: str) -> httpx.Response:
        return self.api.post(
            f"/platform/tenants/{self.tenant_id}/subscription/transition",
            headers=self.h(self.platform),
            json={"to_status": status, "event": "audit"},
        )

    def set_plan(self, code: str) -> httpx.Response:
        return self.api.patch(
            f"/platform/tenants/{self.tenant_id}/subscription/plan",
            headers=self.h(self.platform),
            json={"plan_code": code, "note": "audit"},
        )

    def set_quotas(self, quotas: dict) -> httpx.Response:
        return self.api.patch(
            f"/platform/tenants/{self.tenant_id}/quotas", headers=self.h(self.platform), json=quotas
        )

    def usage(self) -> dict:
        """Live counts as the tenant's plan page shows them
        (`/billing/subscription` → usage); `/billing/usage` is the metered
        snapshot list and is empty until the hourly snapshot has run."""
        r = self.api.get("/billing/subscription", headers=self.h(self.owner))
        return (r.json().get("data") or {}).get("usage") or {}

    def entitlements(self) -> dict:
        r = self.api.get("/entitlements", headers=self.h(self.owner))
        return r.json().get("data") or {}

    # -- tenant helpers ----------------------------------------------------------
    def register_device(self, serial: str) -> tuple[httpx.Response, str | None]:
        r = self.api.get("/devices/enrollment-key", headers=self.h(self.owner))
        key = (r.json().get("data") or {}).get("enrollment_key")
        r = self.api.post("/player/register", json={"enrollment_key": key, "serial_no": serial})
        if r.status_code >= 300:
            return r, None
        device_id = r.json()["data"]["device_id"]
        r2 = self.api.post(f"/devices/{device_id}/approve", headers=self.h(self.owner))
        return r2, device_id

    def device_token(self, serial: str) -> str | None:
        r = self.api.get("/devices/enrollment-key", headers=self.h(self.owner))
        key = (r.json().get("data") or {}).get("enrollment_key")
        r = self.api.post("/player/register", json={"enrollment_key": key, "serial_no": serial})
        return (r.json().get("data") or {}).get("device_token") if r.status_code < 300 else None

    def upload_session(self, size_bytes: int) -> httpx.Response:
        return self.api.post(
            "/assets/uploads",
            headers=self.h(self.owner),
            json={"filename": "audit.png", "mime_type": "image/png", "size_bytes": size_bytes},
        )

    def create_user(self, stamp: str) -> httpx.Response:
        return self.api.post(
            "/users",
            headers=self.h(self.owner),
            json={
                "email": f"limit.{stamp}@e2e-audit.signage.cloud",
                "full_name": "Limit Probe",
                "password": OWNER[1],
            },
        )

    def create_campaign(self, name: str) -> httpx.Response:
        return self.api.post("/campaigns", headers=self.h(self.owner), json={"name": name})

    # -- phases ------------------------------------------------------------------
    def setup(self) -> bool:
        self.phase = "setup"
        print("\n== Setup: revive the audit tenant on the Business plan ==")
        self.platform = self.login(*PLATFORM)
        r = self.api.get("/platform/tenants", headers=self.h(self.platform))
        tenant = next((t for t in r.json().get("data", []) if t.get("code") == TENANT_CODE), None)
        if tenant is None:
            r = self.api.post(
                "/platform/tenants",
                headers=self.h(self.platform),
                json={
                    "name": "E2E Audit Tenant",
                    "code": TENANT_CODE,
                    "timezone": "Asia/Kolkata",
                    "owner_email": OWNER[0],
                    "owner_full_name": "E2E Owner",
                    "owner_password": OWNER[1],
                },
            )
            if not self.check("create the audit tenant", r.status_code in (200, 201), r.text[:200]):
                return False
            tenant = r.json()["data"]
        self.tenant_id = tenant["id"]
        self.api.patch(
            f"/platform/tenants/{self.tenant_id}/status",
            headers=self.h(self.platform),
            json={"status": "active"},
        )
        r = self.api.get(
            f"/platform/tenants/{self.tenant_id}/subscription", headers=self.h(self.platform)
        )
        sub = r.json().get("data") or {}
        if r.status_code != 200 or not sub or sub.get("status") == "expired":
            r = self.api.post(
                f"/platform/tenants/{self.tenant_id}/subscription",
                headers=self.h(self.platform),
                json={"plan_code": "business", "billing_cycle": "monthly", "trial_days": 0},
            )
            self.check("assign a Business subscription", r.status_code in (200, 201), r.text[:200])
        else:
            if sub.get("plan_code") != "business":
                self.set_plan("business")
            if sub.get("status") != "active":
                self.set_status("active")
        self.set_quotas({"max_devices": None, "max_users": None, "max_storage_mb": None})
        self.owner = self.login(*OWNER)
        ent = self.entitlements()
        self.check(
            "owner sees the Business plan",
            (ent.get("plan_code") or "").lower() == "business",
            json.dumps(ent)[:200],
        )
        self.check(
            "entitlements expose feature flags and limits",
            "values" in ent or "features" in ent or "max_devices" in json.dumps(ent),
            json.dumps(ent)[:200],
        )
        return True

    def feature_gates(self) -> None:
        self.phase = "features"
        print("\n== 1. Feature gates on the Business plan ==")
        h = self.h(self.owner)
        probes = [
            (
                "AI text generation",
                "POST",
                "/ai/generate/text",
                {"template": "headline", "text": "Weekend sale on all electronics"},
                "ai_features",
            ),
            (
                "AI localisation",
                "POST",
                "/ai/localize",
                {"text": "Sale today", "target_locale": "hi-IN"},
                "ai_features",
            ),
            (
                "SSO provider setup",
                "POST",
                "/sso/providers",
                {
                    "issuer": "https://login.example.test/",
                    "client_id": "audit",
                    "client_secret_ref": "AUDIT_SECRET",
                },
                "sso",
            ),
            ("video wall creation", "POST", "/video-walls", {"name": "audit wall"}, "video_wall"),
            (
                "experiment creation",
                "POST",
                "/experiments",
                {
                    "campaign_id": ZERO,
                    "name": "audit",
                    "arms": [{"variant_id": ZERO, "allocation_pct": 100}],
                },
                "experiments",
            ),
            (
                "edge bundle creation",
                "POST",
                "/edge/bundles",
                {"name": "audit bundle"},
                "edge_bundles",
            ),
            (
                "fleet-intelligence rule",
                "POST",
                "/fleet-intelligence/rules",
                {"name": "audit", "signal_type": "heartbeat_gaps"},
                "fleet_ai",
            ),
            ("developer sandbox", "GET", "/developer/sandbox", None, "developer_portal"),
            (
                "advertising inventory",
                "POST",
                "/ad-inventory",
                {"name": "audit slot"},
                "advertising",
            ),
            (
                "white-label branding",
                "PUT",
                "/organization/white-label",
                {"product_name": "Audit"},
                "white_label",
            ),
        ]
        for label, method, path, body, key in probes:
            r = self.api.request(method, path, headers=h, json=body)
            self.refused(
                f"{label} is refused and names the plan ({key})", r, "not included", "business"
            )
        r = self.api.get("/connectors", headers=h)
        rows = r.json().get("data") or []
        sso = next((c for c in rows if "sso" in json.dumps(c).lower()), None)
        self.check(
            "integration catalogue marks SSO as unavailable on Business",
            bool(sso) and sso.get("available") is False,
            json.dumps(sso)[:160],
        )
        for label, path in (
            ("proof of play", "/reports/proof-of-play"),
            ("dynamic data sources", "/data-sources"),
        ):
            r = self.api.get(path, headers=h)
            self.allowed(f"{label} is included on Business and answers", r)

    def limits(self) -> dict:
        self.phase = "limits"
        print("\n== 2. Limits reached (via platform quota overrides) ==")
        stamp = uuid.uuid4().hex[:6]
        state: dict = {"devices": []}
        u = self.usage()
        used = int((u.get("devices") or {}).get("used") or 0)
        r = self.set_quotas({"max_devices": used + 1})
        self.check(
            "platform can tighten the device quota below the plan",
            r.status_code == 200,
            r.text[:160],
        )
        self.check(
            "tenant usage now shows the tightened limit",
            int((self.usage().get("devices") or {}).get("limit") or 0) == used + 1,
            json.dumps(self.usage())[:160],
        )
        r, dev_a = self.register_device(f"LIM-{stamp}-A")
        self.allowed("one more device registers within the limit", r)
        if dev_a:
            state["devices"].append(dev_a)
        r, dev_b = self.register_device(f"LIM-{stamp}-B")
        if r.status_code < 300:
            self.check(
                "device beyond the limit is refused with 'limit reached (n/m)'",
                False,
                f"registration and approval both succeeded: {r.text[:120]}",
            )
            if dev_b:
                state["devices"].append(dev_b)
        else:
            self.refused(
                "device beyond the limit is refused with 'limit reached (n/m)'",
                r,
                "limit reached",
                f"/{used + 1}",
            )
        # Does a decommissioned screen free its seat?
        if dev_a:
            self.api.post(f"/devices/{dev_a}/decommission", headers=self.h(self.owner))
            r, dev_c = self.register_device(f"LIM-{stamp}-C")
            self.check(
                "decommissioning a device frees its seat under the limit",
                r.status_code < 300,
                f"{r.status_code} {self.msg(r)}",
            )
            if dev_c:
                state["devices"].append(dev_c)
        # Users
        users_used = int((self.usage().get("users") or {}).get("used") or 0)
        r = self.set_quotas({"max_users": max(users_used, 1)})
        self.check(
            "platform can tighten the user quota to what is in use",
            r.status_code == 200,
            r.text[:160],
        )
        r = self.create_user(stamp)
        self.refused(
            "user beyond the limit is refused with 'limit reached (n/m)'",
            r,
            "limit reached",
            f"/{max(users_used, 1)}",
        )
        # Storage
        storage_used = float((self.usage().get("storage_mb") or {}).get("used") or 0)
        self.set_quotas({"max_storage_mb": int(storage_used) + 1})
        r = self.upload_session(5 * 1024 * 1024)
        self.refused("upload beyond the storage limit is refused with an explanation", r, "storage")
        r = self.upload_session(64 * 1024)
        self.allowed("a small upload within the remaining storage is accepted", r)
        # Clear
        r = self.set_quotas({"max_devices": None, "max_users": None, "max_storage_mb": None})
        self.check(
            "quota overrides can be cleared",
            r.status_code == 200
            and int((self.usage().get("devices") or {}).get("limit") or 0) == 100,
            json.dumps(self.usage())[:160],
        )
        return state

    def lifecycle(self, state: dict) -> None:
        self.phase = "lifecycle"
        print("\n== 3. Subscription lifecycle ==")
        stamp = uuid.uuid4().hex[:6]
        h = self.h(self.owner)
        # A campaign ready to publish, and a live device, before we suspend.
        serial = f"LIFE-{stamp}"
        r, device_id = self.register_device(serial)
        token = self.device_token(serial) if device_id else None
        if device_id:
            state["devices"].append(device_id)
        r = self.api.post("/layouts", headers=h, json={"name": f"Lifecycle layout {stamp}"})
        layout = r.json().get("data") or {}
        if layout:
            canvas = layout["draft_canvas_json"]
            canvas["zones"] = [
                {
                    "key": "main",
                    "x": 0,
                    "y": 0,
                    "width": 1920,
                    "height": 1080,
                    "content_type": "ticker",
                    "content_config": {"text": "audit"},
                }
            ]
            self.api.patch(f"/layouts/{layout['id']}", headers=h, json={"canvas_json": canvas})
            self.api.post(f"/layouts/{layout['id']}/publish", headers=h)
        r = self.api.post(
            "/campaigns",
            headers=h,
            json={"name": f"Lifecycle {stamp}", "layout_id": layout.get("id")},
        )
        campaign = r.json().get("data") or {}
        if campaign:
            self.api.post(
                f"/campaigns/{campaign['id']}/targets",
                headers=h,
                json={"targets": [{"target_type": "device", "target_id": device_id}]},
            )
            self.api.post(
                "/schedules",
                headers=h,
                json={
                    "campaign_id": campaign["id"],
                    "start_time": "00:00",
                    "end_time": "23:59",
                    "timezone": "Asia/Kolkata",
                },
            )
            self.api.post(f"/campaigns/{campaign['id']}/submit-approval", headers=h)
            self.api.post(f"/campaigns/{campaign['id']}/approve", headers=h)

        def growth(label: str, expect_blocked: bool, status_word: str) -> None:
            probes = [
                ("create a campaign", self.create_campaign(f"{label} {uuid.uuid4().hex[:4]}")),
                (
                    "register a device",
                    self.api.post(
                        "/player/register",
                        json={
                            "enrollment_key": (
                                self.api.get("/devices/enrollment-key", headers=h)
                                .json()
                                .get("data")
                                or {}
                            ).get("enrollment_key"),
                            "serial_no": f"G-{uuid.uuid4().hex[:6]}",
                        },
                    ),
                ),
                ("open an upload", self.upload_session(64 * 1024)),
                ("add a user", self.create_user(uuid.uuid4().hex[:6])),
            ]
            if campaign:
                probes.append(
                    ("publish", self.api.post(f"/campaigns/{campaign['id']}/publish", headers=h))
                )
            for what, r in probes:
                if expect_blocked:
                    self.refused(
                        f"{label}: cannot {what} — message names the status", r, status_word
                    )
                else:
                    self.allowed(f"{label}: can {what}", r)
                if r.status_code < 300 and what == "create a campaign":
                    self.api.delete(f"/campaigns/{r.json()['data']['id']}", headers=h)
                if r.status_code < 300 and what == "add a user":
                    pass  # users have no delete in the limit sense; the tenant is archived after the audit
            if token and device_id:
                m = self.api.get(f"/player/{device_id}/manifest", headers={"X-Device-Token": token})
                hb = self.api.post(
                    f"/player/{device_id}/heartbeat",
                    headers={"X-Device-Token": token},
                    json={"status": "online"},
                )
                self.check(
                    f"{label}: players still fetch manifests and heartbeat (screens never blanked over billing)",
                    m.status_code == 200 and hb.status_code == 200,
                    f"manifest {m.status_code}, heartbeat {hb.status_code}",
                )

        for status, blocked in (
            ("suspended", True),
            ("grace_period", False),
            ("past_due", False),
            ("cancelled", True),
            ("active", False),
        ):
            r = self.set_status(status)
            if not self.check(
                f"platform moves the subscription to {status}", r.status_code == 200, r.text[:160]
            ):
                continue
            sub = self.api.get("/billing/subscription", headers=h).json().get("data") or {}
            self.check(
                f"tenant sees status {status} on its billing page",
                sub.get("status") == status,
                json.dumps(sub)[:160],
            )
            growth(status, blocked, status.replace("_", " ") if status != "grace_period" else "")
        # Expired is special: current_subscription() skips it.
        r = self.set_status("expired")
        if self.check("platform can expire the subscription", r.status_code == 200, r.text[:160]):
            r = self.create_campaign(f"expired {stamp}")
            self.refused(
                "expired: cannot create a campaign — growth blocked, not silently unrestricted",
                r,
                "expired",
            )
            if r.status_code < 300:
                self.api.delete(f"/campaigns/{r.json()['data']['id']}", headers=h)
            ent = self.entitlements()
            sub = self.api.get("/billing/subscription", headers=h).json().get("data") or {}
            self.check(
                "expired: the plan's limits stay in force and the status reads expired (not unlimited legacy mode)",
                ent.get("plan_code") == "business"
                and (ent.get("values") or {}).get("max_devices") == 100
                and sub.get("status") == "expired",
                json.dumps({"entitlements": ent, "status": sub.get("status")})[:220],
            )
            # Renewal after expiry = a new subscription.
            r = self.api.post(
                f"/platform/tenants/{self.tenant_id}/subscription",
                headers=self.h(self.platform),
                json={"plan_code": "business", "billing_cycle": "monthly", "trial_days": 0},
            )
            self.check(
                "renewal after expiry: a new Business subscription is assigned",
                r.status_code in (200, 201),
                r.text[:160],
            )
            r = self.create_campaign(f"renewed {stamp}")
            self.allowed("renewed: campaign creation works again", r)
            if r.status_code < 300:
                self.api.delete(f"/campaigns/{r.json()['data']['id']}", headers=h)
        if campaign:
            self.api.delete(f"/campaigns/{campaign['id']}", headers=h)

    def plan_changes(self, state: dict) -> None:
        self.phase = "plan changes"
        print("\n== 4. Plan upgrade / downgrade ==")
        h = self.h(self.owner)
        r = self.set_plan("professional")
        self.check("upgrade to Professional", r.status_code == 200, r.text[:160])
        ent = self.entitlements()
        self.check(
            "entitlements follow the upgrade (ai_features on)",
            "professional" in json.dumps(ent).lower()
            and '"ai_features": true' in json.dumps(ent).replace("'", '"').lower(),
            json.dumps(ent)[:200],
        )
        r = self.api.post("/video-walls", headers=h, json={"name": "audit wall"})
        self.check(
            "a Business-locked feature (video walls) opens after the upgrade",
            r.status_code < 300 or "not included" not in self.msg(r).lower(),
            f"{r.status_code} {self.msg(r)}",
        )
        if r.status_code < 300:
            self.api.delete(f"/video-walls/{r.json()['data']['id']}", headers=h)
        self.check(
            "device limit follows the plan (500)",
            int((self.usage().get("devices") or {}).get("limit") or 0) == 500,
            json.dumps(self.usage())[:160],
        )

        r = self.set_plan("starter")
        self.check("downgrade to Starter", r.status_code == 200, r.text[:160])
        u = self.usage()
        self.check(
            "device limit follows the downgrade (10)",
            int((u.get("devices") or {}).get("limit") or 0) == 10,
            json.dumps(u)[:160],
        )
        r = self.api.post("/video-walls", headers=h, json={"name": "audit wall"})
        self.refused("features close again after the downgrade", r, "not included", "starter")
        r = self.api.get("/reports/proof-of-play", headers=h)
        self.check(
            "proof of play (off on Starter) is refused by the API, not only hidden by the UI",
            r.status_code in (403, 422) and "not included" in self.msg(r).lower(),
            f"{r.status_code} {self.msg(r)[:120]}",
        )
        r = self.api.get(
            "/analytics/aggregates",
            headers=h,
            params={"date_from": "2026-09-01", "date_to": "2026-09-05"},
        )
        self.check(
            "advanced analytics (off on Starter) is refused by the API",
            r.status_code in (403, 422) and "not included" in self.msg(r).lower(),
            f"{r.status_code} {self.msg(r)[:120]}",
        )
        # Usage above the new limit: tighten to below what is in use.
        used = int((u.get("devices") or {}).get("used") or 0)
        if used >= 1:
            self.set_quotas({"max_devices": max(used - 1, 0)})
            r, dev = self.register_device(f"OVER-{uuid.uuid4().hex[:6]}")
            self.refused(
                "over the limit after a downgrade: no new devices, with the numbers",
                r,
                "limit reached",
            )
            if dev:
                state["devices"].append(dev)
            self.set_quotas({"max_devices": None})
        # API keys follow api_access.
        r = self.api.post(
            "/api-keys",
            headers=h,
            json={"name": f"audit-{uuid.uuid4().hex[:6]}", "scopes": ["devices.view"]},
        )
        key = (
            (r.json().get("data") or {}).get("api_key")
            or (r.json().get("data") or {}).get("key")
            or (r.json().get("data") or {}).get("secret")
        )
        if self.check(
            "an API key can be created (management is a permission, use is an entitlement)",
            r.status_code in (200, 201),
            f"{r.status_code} {self.msg(r)}",
        ):
            r2 = self.api.get("/devices", headers={"X-API-Key": key or ""})
            self.refused(
                "using the key on Starter is refused: api_access not included", r2, "api_access"
            )
        r = self.set_plan("business")
        self.check("back to Business", r.status_code == 200, r.text[:160])
        if key:
            r2 = self.api.get("/devices", headers={"X-API-Key": key})
            self.allowed("the same key works on Business (api_access included)", r2)

    def teardown(self, state: dict) -> None:
        self.phase = "teardown"
        print("\n== Teardown ==")
        self.set_quotas({"max_devices": None, "max_users": None, "max_storage_mb": None})
        for device_id in state.get("devices", []):
            self.api.post(f"/devices/{device_id}/decommission", headers=self.h(self.owner))
        r = self.api.patch(
            f"/platform/tenants/{self.tenant_id}/status",
            headers=self.h(self.platform),
            json={"status": "archived"},
        )
        self.check("audit tenant archived again", r.status_code == 200, r.text[:120])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--report", default=None)
    args = ap.parse_args()
    a = Audit(args.base)
    state: dict = {"devices": []}
    try:
        if a.setup():
            a.feature_gates()
            state = a.limits()
            a.lifecycle(state)
            a.plan_changes(state)
    except RuntimeError as exc:
        a.check(f"aborted: {exc}", False, str(exc))
    finally:
        if a.tenant_id:
            a.teardown(state)
    failed = [s for s in a.steps if not s.ok]
    print(f"\n{len(a.steps) - len(failed)} passed, {len(failed)} failed")
    for s in failed:
        print(f"  FAIL [{s.phase}] {s.name} — {s.detail[:220]}")
    if args.report:
        with open(args.report, "w", encoding="utf-8") as fh:
            json.dump([asdict(s) for s in a.steps], fh, indent=2)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
