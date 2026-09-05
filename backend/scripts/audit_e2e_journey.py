"""End-to-end product journey against a running API.

Plays the whole story twice and reports every step as PASS / FAIL:

  1. A brand-new tenant, from the platform console down to proof of play:
     Platform Admin -> tenant -> subscription -> users + roles ->
     locations -> devices -> content -> layout -> playlist -> campaign ->
     approval -> schedule -> publish -> device sync -> TV preview ->
     playback / proof of play -> analytics -> dashboard, then the
     role-based checks (what a Viewer / Content Manager / Device Manager
     can actually *do*, not just see).
  2. The same organisation-side journey inside the seeded Reliance Retail
     tenant, so it runs among realistic data rather than an empty account.

Everything it creates is named `E2E Audit …`; the fresh tenant is archived
at the end and the records created inside the seeded tenant are removed.

    python scripts/audit_e2e_journey.py [--base http://localhost:8000]
                                       [--report path.json] [--keep]
"""

# ruff: noqa: E501 - long request literals read better on one line
from __future__ import annotations

import argparse
import datetime as dt
import json
import struct
import sys
import time
import uuid
import zlib
from dataclasses import asdict, dataclass

import httpx

PLATFORM = ("platform@signage.cloud", "Platform@12345")  # noqa: S105 - documented demo credential
SEEDED_ADMIN = ("arjun.mehta@rrl-demo.signage.cloud", "Demo@12345")  # noqa: S105
SEEDED_APPROVER = ("sneha.iyer@rrl-demo.signage.cloud", "Demo@12345")  # noqa: S105 - Campaign Approver
OWNER_PASSWORD = "E2eAudit@12345"  # noqa: S105 - throwaway tenant, archived at the end


@dataclass
class Step:
    phase: str
    name: str
    ok: bool
    detail: str = ""


class Journey:
    def __init__(self, base: str, keep: bool):
        self.api = httpx.Client(base_url=base + "/api/v1", timeout=60)
        self.raw = httpx.Client(base_url=base, timeout=60)
        self.keep = keep
        self.steps: list[Step] = []
        self.phase = ""

    # -- bookkeeping ---------------------------------------------------------
    def check(self, name: str, ok: bool, detail: str = "") -> bool:
        self.steps.append(Step(self.phase, name, bool(ok), "" if ok else detail[:300]))
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}{'' if ok else '  — ' + detail[:160]}")
        return bool(ok)

    def expect(self, name: str, r: httpx.Response, *codes: int) -> dict:
        ok = r.status_code in (codes or (200, 201))
        self.check(name, ok, f"{r.status_code} {r.text}")
        try:
            return r.json().get("data") or {}
        except ValueError:
            return {}

    # -- helpers ---------------------------------------------------------------
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

    @staticmethod
    def png(width: int = 320, height: int = 180) -> bytes:
        """A valid PNG without any imaging library: solid brand-blue."""
        raw = b"".join(b"\x00" + b"\x1d\x4e\xd8" * width for _ in range(height))

        def chunk(tag: bytes, body: bytes) -> bytes:
            return struct.pack(">I", len(body)) + tag + body + struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF)

        return (
            b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9))
            + chunk(b"IEND", b"")
        )

    def upload_asset(self, token: str, name: str) -> dict:
        data = self.png()
        r = self.api.post(
            "/assets/uploads",
            headers=self.h(token),
            json={"filename": f"{name}.png", "mime_type": "image/png", "size_bytes": len(data), "name": name},
        )
        session = self.expect("content: open upload session", r, 201)
        if not session:
            return {}
        url = session["upload_url"]
        put = (self.raw if url.startswith(("http", "/")) else self.api).put(
            url, content=data, headers={"Content-Type": "image/png", **session.get("headers", {})}
        )
        self.check("content: PUT bytes to signed upload URL", put.status_code == 200, f"{put.status_code} {put.text}")
        r = self.api.post(f"/assets/uploads/{session['upload_session_id']}/complete", headers=self.h(token))
        asset = self.expect("content: complete upload (media processed inline)", r, 200)
        if asset:
            r = self.api.post(f"/assets/{asset['id']}/publish", headers=self.h(token))
            self.expect("content: publish asset", r, 200)
        return asset

    def enroll_device(self, token: str, serial: str, name: str) -> tuple[str, str] | None:
        r = self.api.get("/devices/enrollment-key", headers=self.h(token))
        key = self.expect("devices: read enrollment key", r).get("enrollment_key")
        if not key:
            return None
        r = self.api.post("/player/register", json={"enrollment_key": key, "serial_no": serial, "name": name, "platform": "webos"})
        reg = self.expect(f"devices: player {serial} registers (pending)", r, 200, 201)
        if not reg or not self.check("devices: registration is pending approval", reg.get("status") == "pending", json.dumps(reg)):
            return None
        r = self.api.post(f"/devices/{reg['device_id']}/approve", headers=self.h(token))
        self.expect("devices: administrator approves the device", r, 200)
        r = self.api.post("/player/register", json={"enrollment_key": key, "serial_no": serial})
        reg2 = self.expect("devices: player re-registers and receives its token", r, 200, 201)
        if not self.check("devices: device is active with a token", reg2.get("status") == "active" and bool(reg2.get("device_token")), json.dumps(reg2)):
            return None
        return reg["device_id"], reg2["device_token"]

    # -- the organisation-side journey ------------------------------------------
    def org_journey(self, token: str, parent_location: str | None, stamp: str, expect_devices: int = 2, approver: tuple[str, str] | None = None) -> dict:
        """Locations -> devices -> content -> layout -> playlist -> campaign ->
        approval -> schedule -> publish -> sync -> preview -> reports."""
        created: dict = {"devices": [], "locations": []}
        h = self.h(token)

        # Locations
        parent = parent_location
        for name in (["E2E Audit Region", "E2E Audit City"] if parent_location is None else []) + [f"E2E Audit Store {stamp}"]:
            r = self.api.post("/locations", headers=h, json={"name": name, "parent_id": parent})
            loc = self.expect(f"locations: create '{name}'", r, 201)
            if not loc:
                return created
            created["locations"].insert(0, loc["id"])
            parent = loc["id"]
        store_id = parent
        r = self.api.get("/locations/tree", headers=h)
        self.expect("locations: tree endpoint", r)

        # Devices
        for index in range(expect_devices):
            pair = self.enroll_device(token, f"E2E-{stamp}-{index}", f"E2E Audit Screen {index}")
            if not pair:
                return created
            device_id, dtoken = pair
            r = self.api.post(f"/devices/{device_id}/assign-location", headers=h, json={"location_id": store_id})
            self.expect("devices: assign to store", r, 200)
            created["devices"].append((device_id, dtoken))
        r = self.api.get("/devices", headers=h, params={"q": f"E2E-{stamp}", "page_size": 10})
        self.check("devices: list finds the new screens", len(r.json().get("data") or []) >= expect_devices, r.text[:200])

        # Content
        asset = self.upload_asset(token, f"E2E Audit Banner {stamp}")
        if not asset:
            return created
        created["asset"] = asset["id"]

        # Layout
        r = self.api.post("/layouts", headers=h, json={"name": f"E2E Audit Layout {stamp}"})
        layout = self.expect("layout: create 1920x1080", r, 201)
        if not layout:
            return created
        created["layout"] = layout["id"]
        canvas = layout["draft_canvas_json"]
        canvas["zones"] = [
            {"key": "main", "x": 0, "y": 0, "width": 1920, "height": 960, "content_type": "image", "content_config": {"asset_id": asset["id"]}},
            {"key": "ticker", "x": 0, "y": 960, "width": 1920, "height": 120, "content_type": "ticker", "content_config": {"text": "E2E audit"}},
        ]
        r = self.api.patch(f"/layouts/{layout['id']}", headers=h, json={"canvas_json": canvas})
        self.expect("layout: save designer draft with two zones", r, 200)
        r = self.api.post(f"/layouts/{layout['id']}/publish", headers=h)
        self.expect("layout: publish", r, 200)

        # Playlist
        r = self.api.post("/playlists", headers=h, json={"name": f"E2E Audit Playlist {stamp}"})
        playlist = self.expect("playlist: create", r, 201)
        if not playlist:
            return created
        created["playlist"] = playlist["id"]
        r = self.api.post(f"/playlists/{playlist['id']}/items", headers=h, json={"layout_id": layout["id"], "duration_ms": 15000})
        self.expect("playlist: add layout item", r, 200, 201)
        r = self.api.post(f"/playlists/{playlist['id']}/items", headers=h, json={"asset_id": asset["id"], "duration_ms": 8000})
        self.expect("playlist: add asset item", r, 200, 201)
        r = self.api.post(f"/playlists/{playlist['id']}/publish", headers=h)
        self.expect("playlist: publish", r, 200)

        # Campaign + targets + schedule + approval
        r = self.api.post("/campaigns", headers=h, json={"name": f"E2E Audit Campaign {stamp}", "playlist_id": playlist["id"], "layout_id": layout["id"], "priority": 95})
        campaign = self.expect("campaign: create bound to playlist + layout", r, 201)
        if not campaign:
            return created
        created["campaign"] = campaign["id"]
        r = self.api.post(f"/campaigns/{campaign['id']}/targets", headers=h, json={"targets": [{"target_type": "location", "target_id": store_id, "include_descendants": True}]})
        self.expect("campaign: target the store subtree", r, 200)
        r = self.api.post(f"/campaigns/{campaign['id']}/targets/preview", headers=h, json={"targets": [{"target_type": "location", "target_id": store_id}]})
        preview = self.expect("campaign: preview effective targets", r, 200)
        resolved = preview.get("count") if isinstance(preview, dict) else None
        self.check("campaign: preview resolves exactly the new screens", resolved == expect_devices, json.dumps(preview)[:200])
        r = self.api.post("/schedules", headers=h, json={"campaign_id": campaign["id"], "name": "All day", "start_time": "00:00", "end_time": "23:59", "timezone": "Asia/Kolkata"})
        schedule = self.expect("schedule: all-day play window", r, 201)
        if schedule:
            created["schedule"] = schedule["id"]
        r = self.api.post("/schedules/conflicts", headers=h, json={"campaign_id": campaign["id"], "start_time": "00:00", "end_time": "23:59", "timezone": "Asia/Kolkata"})
        self.check("schedule: conflict check answers", r.status_code in (200, 201), r.text[:160])
        r = self.api.post(f"/campaigns/{campaign['id']}/submit-approval", headers=h)
        self.expect("approval: submit campaign for approval", r, 200)
        r = self.api.get("/approvals/inbox", headers=h, params={"page_size": 50})
        inbox = r.json().get("data") or []
        self.check("approval: request appears in the inbox", any(str(i.get("entity_id")) == campaign["id"] for i in inbox), r.text[:200])
        r = self.api.post(f"/campaigns/{campaign['id']}/approve", headers=h)
        if r.status_code == 422 and "maker-checker" in r.text.lower() and approver:
            # Four-eyes is on in this tenant: the submitter cannot approve
            # their own request, so a Campaign Approver decides it.
            self.check("approval: maker-checker blocks self-approval", True)
            r = self.api.post(f"/campaigns/{campaign['id']}/approve", headers=self.h(self.login(*approver)))
        self.expect("approval: approve campaign", r, 200)

        # Publish
        r = self.api.post(f"/campaigns/{campaign['id']}/publish", headers=h)
        deployment = self.expect("publish: create deployment", r, 200, 201, 202)
        if not deployment:
            return created
        dep_id = deployment.get("id") or (deployment.get("deployment") or {}).get("id")
        if not dep_id:
            r = self.api.get("/deployments", headers=h, params={"page_size": 5})
            dep_id = next((d["id"] for d in r.json().get("data", []) if d.get("campaign_id") == campaign["id"]), None)
        created["deployment"] = dep_id
        r = self.api.get(f"/deployments/{dep_id}", headers=h)
        dep = self.expect("publish: deployment is readable", r)
        self.check("publish: deployment targets exactly the new screens", dep.get("total_devices") == expect_devices, json.dumps(dep)[:200])

        # Device sync
        for device_id, dtoken in created["devices"]:
            dh = {"X-Device-Token": dtoken}
            r = self.api.get(f"/player/{device_id}/manifest", headers=dh)
            manifest = self.expect("sync: player fetches manifest", r)
            self.check("sync: manifest carries the published campaign", manifest.get("active_campaign") == campaign["id"], json.dumps(manifest)[:200])
            self.check("sync: manifest layout has the ticker zone", any(z.get("content_type") == "ticker" for z in ((manifest.get("layout") or {}).get("canvas") or {}).get("zones", [])), "")
            for entry in manifest.get("assets") or []:
                url = entry.get("url", "")
                fetched = (self.raw if url.startswith(("http", "/")) else self.api).get(url)
                self.check("sync: asset URL downloads", fetched.status_code == 200, f"{fetched.status_code} {url[:80]}")
                break
            r = self.api.post(f"/player/{device_id}/deployments/{dep_id}/ack", headers=dh, json={"success": True})
            self.expect("sync: player acknowledges deployment", r, 200)
            r = self.api.post(f"/player/{device_id}/heartbeat", headers=dh, json={"status": "online", "player_version": "e2e-1.0", "storage": {"used_percent": 40}})
            self.expect("sync: heartbeat", r, 200)
            now = dt.datetime.now(dt.UTC)
            events = [{"type": "APP_STARTED", "payload": {"version": "e2e-1.0"}}]
            for i in range(4):
                start = now - dt.timedelta(minutes=i * 2)
                events.append({"type": "playback", "asset_id": asset["id"], "campaign_id": campaign["id"], "started_at": start.isoformat(), "ended_at": (start + dt.timedelta(seconds=8)).isoformat(), "result": "completed"})
            r = self.api.post(f"/player/{device_id}/events", headers=dh, json={"events": events})
            self.expect("playback: player reports 4 completed plays", r, 200, 201, 202)
            # Command round-trip
            r = self.api.post(f"/devices/{device_id}/commands", headers=h, json={"command_type": "reboot"})
            self.expect("commands: administrator queues a reboot", r, 200, 201, 202)
            r = self.api.get(f"/player/{device_id}/commands", headers=dh)
            cmds = r.json().get("data") or []
            cmd_id = cmds[0].get("id") if cmds else None
            self.check("commands: player receives the queued command", bool(cmd_id), r.text[:160])
            if cmd_id:
                r = self.api.post(f"/player/{device_id}/commands/{cmd_id}/ack", headers=dh, json={"success": True})
                self.expect("commands: player acknowledges", r, 200)
        r = self.api.get(f"/deployments/{dep_id}", headers=h)
        dep = r.json().get("data") or {}
        self.check("publish: all screens acknowledged, deployment published", dep.get("acknowledged") == expect_devices and dep.get("status") == "published", json.dumps(dep)[:200])

        # TV preview (what the operator sees) matches the device manifest
        device_id = created["devices"][0][0]
        r = self.api.get(f"/devices/{device_id}/preview-manifest", headers=h)
        pm = self.expect("tv preview: preview manifest for a screen", r)
        self.check("tv preview: preview shows the same active campaign", pm.get("active_campaign") == campaign["id"], json.dumps(pm)[:200])

        # Reports / analytics / dashboard
        today = dt.date.today()
        r = self.api.get("/reports/proof-of-play", headers=h, params={"date_from": (today - dt.timedelta(days=1)).isoformat(), "date_to": today.isoformat(), "campaign_id": campaign["id"]})
        pop = self.expect("reports: proof of play for the campaign", r)
        rows = pop if isinstance(pop, list) else (pop.get("rows") or pop.get("items") or [pop])
        plays = 0
        for row in rows:
            if isinstance(row, dict):
                plays += int(row.get("plays") or row.get("total_plays") or row.get("count") or 0)
        self.check("reports: proof of play counts the reported plays", plays >= 4 * expect_devices, json.dumps(pop)[:200])
        for path in ("/reports/playback", "/reports/device-uptime", "/reports/campaign-performance", "/reports/deployments", "/reports/locations"):
            r = self.api.get(path, headers=h)
            self.expect(f"reports: {path.split('/')[-1]} answers", r)
        r = self.api.get("/analytics/aggregates", headers=h, params={"date_from": (today - dt.timedelta(days=7)).isoformat(), "date_to": today.isoformat()})
        self.expect("analytics: aggregates answer for the last 7 days", r)
        r = self.api.get("/monitoring/summary", headers=h)
        self.expect("monitoring: summary answers", r)
        r = self.api.get("/dashboard/organization", headers=h)
        dash = self.expect("dashboard: organisation dashboard answers", r)
        kpis = dash.get("kpis") or {}
        self.check("dashboard: online count includes the heartbeating screens", int((kpis.get("devices") or {}).get("online") or 0) >= expect_devices, json.dumps(kpis)[:200])
        r = self.api.get("/audit-logs", headers=h, params={"page_size": 50})
        logs = r.json().get("data") or []
        self.check("audit: trail records the publish", any("PUBLISH" in str(entry.get("action", "")).upper() for entry in logs), str([entry.get("action") for entry in logs[:10]]))
        return created

    # -- role checks -----------------------------------------------------------
    def role_checks(self, owner_token: str, created: dict, stamp: str) -> None:
        h = self.h(owner_token)
        r = self.api.get("/roles", headers=h)
        roles = {x["name"]: x["id"] for x in r.json().get("data") or []}
        self.check("roles: system roles present", all(k in roles for k in ("Viewer", "Content Manager", "Device Manager")), str(list(roles)))
        people = {
            "Viewer": "viewer@e2e-audit.signage.cloud",
            "Content Manager": "content@e2e-audit.signage.cloud",
            "Device Manager": "devices@e2e-audit.signage.cloud",
        }
        tokens: dict[str, str] = {}
        for role, email in people.items():
            r = self.api.post("/users", headers=h, json={"email": email, "full_name": f"E2E {role}", "password": OWNER_PASSWORD, "role_ids": [roles.get(role)]})
            if self.check(f"users: create {role}", r.status_code in (201, 409), f"{r.status_code} {r.text[:120]}"):
                tokens[role] = self.login(email, OWNER_PASSWORD)
        device_id = created["devices"][0][0] if created.get("devices") else None
        campaign_id = created.get("campaign")
        matrix = [
            ("Viewer", "GET", "/campaigns", None, (200,), "can read campaigns"),
            ("Viewer", "GET", "/devices", None, (200,), "can read devices"),
            ("Viewer", "POST", "/campaigns", {"name": "x"}, (403,), "cannot create a campaign"),
            ("Viewer", "POST", f"/devices/{device_id}/commands", {"command_type": "reboot"}, (403,), "cannot send device commands"),
            ("Viewer", "GET", "/platform/tenants", None, (403,), "cannot reach the platform console"),
            ("Content Manager", "POST", "/playlists", {"name": f"E2E CM {stamp}"}, (201,), "can create a playlist"),
            ("Content Manager", "POST", f"/devices/{device_id}/commands", {"command_type": "reboot"}, (403,), "cannot send device commands"),
            ("Content Manager", "POST", "/users", {"email": f"x.{stamp}@e2e-audit.signage.cloud", "full_name": "x"}, (403,), "cannot create users"),
            ("Device Manager", "POST", f"/devices/{device_id}/commands", {"command_type": "reboot"}, (200, 201, 202), "can send device commands"),
            ("Device Manager", "POST", "/campaigns", {"name": "x"}, (403,), "cannot create a campaign"),
            ("Device Manager", "POST", f"/campaigns/{campaign_id}/publish", None, (403,), "cannot publish a campaign"),
            ("Device Manager", "GET", "/billing/subscription", None, (200, 403), "billing read is permission-gated"),
        ]
        for role, method, path, body, codes, label in matrix:
            tok = tokens.get(role)
            if not tok:
                continue
            r = self.api.request(method, path, headers=self.h(tok), json=body)
            self.check(f"rbac: {role} {label}", r.status_code in codes, f"{r.status_code} {r.text[:120]}")
            if r.status_code in (200, 201) and method == "POST" and path == "/playlists":
                self.api.delete(f"/playlists/{r.json()['data']['id']}", headers=self.h(tokens[role]))
        # The UI reads the same permission list the API enforces.
        for role, tok in tokens.items():
            r = self.api.get("/auth/me", headers=self.h(tok))
            me = r.json().get("data") or {}
            perms = set(me.get("permissions") or me.get("permission_codes") or [])
            self.check(f"rbac: /auth/me exposes {role}'s permission set for UI gating", bool(perms), json.dumps(me)[:160])

    # -- phases ------------------------------------------------------------------
    def fresh_tenant(self, stamp: str) -> None:
        self.phase = "fresh tenant"
        print("\n== Phase 1: fresh tenant from the platform console ==")
        platform = self.login(*PLATFORM)
        ph = self.h(platform)
        code = "e2e-audit"
        owner_email = "owner@e2e-audit.signage.cloud"
        r = self.api.get("/platform/tenants", headers=ph)
        existing = next((t for t in r.json().get("data", []) if t.get("code") == code), None)
        if existing:
            # Left archived by the previous run; revive it rather than
            # accumulating one archived tenant per audit.
            r = self.api.patch(f"/platform/tenants/{existing['id']}/status", headers=ph, json={"status": "active"})
            self.expect("platform: reactivate the audit tenant from the previous run", r, 200)
            tenant, tenant_id = existing, existing["id"]
        else:
            r = self.api.post("/platform/tenants", headers=ph, json={"name": "E2E Audit Tenant", "code": code, "timezone": "Asia/Kolkata", "owner_email": owner_email, "owner_full_name": "E2E Owner", "owner_password": OWNER_PASSWORD})
            tenant = self.expect("platform: create tenant with owner", r, 200, 201)
            self.check("platform: create responds 201 Created like every other create", r.status_code == 201, f"{r.status_code}")
            tenant_id = (tenant.get("organization") or tenant).get("id") if tenant else None
        if not self.check("platform: tenant id resolved", bool(tenant_id), json.dumps(tenant)[:200]):
            return
        r = self.api.post(f"/platform/tenants/{tenant_id}/subscription", headers=ph, json={"plan_code": "business", "billing_cycle": "monthly", "trial_days": 14})
        if existing and r.status_code == 409:
            self.check("platform: assigning a second subscription is refused (change-plan instead)", True)
        else:
            self.expect("platform: assign Business subscription (14-day trial)", r, 200, 201)
        r = self.api.get(f"/platform/tenants/{tenant_id}/subscription", headers=ph)
        sub = self.expect("platform: subscription readable", r)
        self.check("platform: subscription is on the Business plan", "business" in json.dumps(sub).lower(), json.dumps(sub)[:200])
        r = self.api.get(f"/platform/tenants/{tenant_id}/quotas", headers=ph)
        self.expect("platform: quotas readable", r)

        owner = self.login(owner_email, OWNER_PASSWORD)
        self.check("tenant: owner can sign in", bool(owner))
        r = self.api.get("/entitlements", headers=self.h(owner))
        ent = self.expect("tenant: entitlements resolve for the owner", r)
        self.check("tenant: entitlements name the plan", "business" in json.dumps(ent).lower(), json.dumps(ent)[:200])
        r = self.api.get("/dashboard/organization", headers=self.h(owner))
        dash = self.expect("tenant: dashboard renders without error", r)
        if not existing:
            self.check("tenant: empty tenant reports zero devices, not an error", ((dash.get("kpis") or {}).get("devices") or {}).get("total", 0) == 0, json.dumps(dash.get("kpis"))[:160])

        created = self.org_journey(owner, None, stamp, expect_devices=2)
        self.role_checks(owner, created, stamp)

        if not self.keep:
            r = self.api.patch(f"/platform/tenants/{tenant_id}/status", headers=ph, json={"status": "archived"})
            self.expect("cleanup: archive the audit tenant", r, 200)
            r = self.api.post("/auth/login", json={"email": owner_email, "password": OWNER_PASSWORD})
            self.check("cleanup: archived tenant's owner can no longer sign in", r.status_code in (401, 403), f"{r.status_code}")

    def seeded_tenant(self, stamp: str) -> None:
        self.phase = "seeded tenant"
        print("\n== Phase 2: the same journey inside Reliance Retail (seeded data) ==")
        admin = self.login(*SEEDED_ADMIN)
        h = self.h(admin)
        r = self.api.get("/locations", headers=h, params={"q": "Kolkata", "page_size": 5})
        rows = r.json().get("data") or []
        kolkata = next((x["id"] for x in rows if x.get("name") == "Kolkata"), rows[0]["id"] if rows else None)
        if not self.check("seeded: Kolkata exists in the hierarchy", bool(kolkata), r.text[:160]):
            return
        r = self.api.get("/devices", headers=h, params={"page_size": 1})
        total_before = (r.json().get("meta") or {}).get("total")
        created = self.org_journey(admin, kolkata, stamp, expect_devices=1, approver=SEEDED_APPROVER)
        r = self.api.get("/campaigns", headers=h, params={"page_size": 100})
        self.check("seeded: existing campaigns untouched alongside the audit campaign", len(r.json().get("data") or []) > 5, r.text[:100])

        if self.keep:
            return
        self.phase = "seeded cleanup"
        if created.get("schedule"):
            self.expect("cleanup: delete schedule", self.api.delete(f"/schedules/{created['schedule']}", headers=h), 200, 204)
        if created.get("deployment"):
            self.api.post(f"/deployments/{created['deployment']}/cancel", headers=h)
        if created.get("campaign"):
            self.expect("cleanup: delete campaign", self.api.delete(f"/campaigns/{created['campaign']}", headers=h), 200, 204)
        if created.get("playlist"):
            self.expect("cleanup: delete playlist", self.api.delete(f"/playlists/{created['playlist']}", headers=h), 200, 204)
        if created.get("layout"):
            self.expect("cleanup: delete layout", self.api.delete(f"/layouts/{created['layout']}", headers=h), 200, 204)
        if created.get("asset"):
            self.expect("cleanup: archive asset", self.api.post(f"/assets/{created['asset']}/archive", headers=h), 200)
        for device_id, _ in created.get("devices", []):
            self.expect("cleanup: decommission audit device", self.api.post(f"/devices/{device_id}/decommission", headers=h), 200)
        for loc in created.get("locations", []):
            self.expect("cleanup: delete audit location", self.api.delete(f"/locations/{loc}", headers=h), 200, 204)
        for device_id, _ in created.get("devices", []):
            r = self.api.get(f"/devices/{device_id}", headers=h)
            self.check("cleanup: audit device is decommissioned", (r.json().get("data") or {}).get("status") == "decommissioned", r.text[:160])
        r = self.api.get("/devices", headers=h, params={"page_size": 1})
        total_after = (r.json().get("meta") or {}).get("total")
        self.check("cleanup: only the decommissioned audit device was added to the fleet", total_after == (total_before or 0) + len(created.get("devices", [])), f"{total_before} -> {total_after}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--report", default=None)
    ap.add_argument("--keep", action="store_true", help="leave everything in place for inspection")
    args = ap.parse_args()
    stamp = uuid.uuid4().hex[:6]
    j = Journey(args.base, args.keep)
    try:
        j.fresh_tenant(stamp)
        j.seeded_tenant(stamp)
    except RuntimeError as exc:
        j.check(f"aborted: {exc}", False, str(exc))
    failed = [s for s in j.steps if not s.ok]
    print(f"\n{len(j.steps) - len(failed)} passed, {len(failed)} failed")
    for s in failed:
        print(f"  FAIL [{s.phase}] {s.name} — {s.detail[:200]}")
    if args.report:
        with open(args.report, "w", encoding="utf-8") as fh:
            json.dump([asdict(s) for s in j.steps], fh, indent=2)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
