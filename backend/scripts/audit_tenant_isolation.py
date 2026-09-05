"""Multi-tenant isolation audit against a running API.

Walks every route in the live OpenAPI document and, for each one that
addresses a resource by id, calls it as Tenant A's administrator with ids
harvested from Tenant B (and the other way round). Nothing is trusted
from the UI: the audit is the actual HTTP surface.

    python scripts/audit_tenant_isolation.py [--base http://localhost:8000]
                                            [--delete] [--report path.json]

Outcomes per probe
  DENIED      403/404 — the resource is invisible across the boundary
  LEAK        2xx — Tenant A reached Tenant B's data (finding)
  VALIDATION  400/422 — the request passed authentication but the empty
              body failed validation before the handler could run; the id
              check was not exercised (listed so it can be covered by a
              targeted test)
  ERROR       5xx — a crash on foreign input (finding)
  UNRESOLVED  no Tenant B id could be harvested for this route, so a
              random UUID was sent; 404 proves nothing here

`--delete` also sends DELETE probes. They are off by default because a
leak would destroy the other tenant's demo data; run them once the
read/write sweep is clean, against a database you can reseed.
"""

# ruff: noqa: E501 - probe tables read better on one line each
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import uuid
from dataclasses import asdict, dataclass

import httpx

DEMO_PASSWORD = "Demo@12345"  # noqa: S105 - documented demo credential

TENANT_A = ("Reliance Retail", "arjun.mehta@rrl-demo.signage.cloud")
TENANT_B = ("BharatMart", "rohan.nair@bharatmart-demo.signage.cloud")

# Route prefixes that are not tenant resources addressed by id.
SKIP_PREFIXES = ("/auth", "/health", "/player", "/storage", "/platform")

# Where to list a collection when the path prefix is not itself a list
# endpoint, plus the field that carries the id in that list.
HARVEST_OVERRIDES: dict[str, tuple[str, str]] = {
    "/approvals": ("/approvals/inbox", "id"),
    "/fleet-intelligence": ("/fleet-intelligence/anomalies", "id"),
    "/security/devices": ("/devices", "id"),
    "/organization/members": ("/organization/members", "membership_id"),
    "/subscriptions/deliveries": ("/subscriptions", "id"),  # nested below
    "/webhooks/deliveries": ("/webhooks", "id"),
}

# Second-level params: the sub-list to read once the parent id is known,
# and the key under `data` that holds the rows when it is a detail object.
NESTED: dict[str, tuple[str, str]] = {
    "variant_id": ("/campaigns/{campaign_id}/variants", ""),
    "item_id": ("/playlists/{playlist_id}", "items"),
    "member_id": ("/video-walls/{wall_id}", "members"),
    "delivery_id": ("/webhooks/{subscription_id}/deliveries", ""),
    "invoice_id": ("/billing/invoices", ""),
}

# Routes whose path parameter is not a resource id (nothing to leak by id).
SKIP_ROUTES = {"/approval-policies/{entity_type}"}

# Minimal valid bodies for mutating routes, so the probe reaches the
# handler's tenant check instead of stopping at schema validation. Bodies
# are inert: empty lists, harmless names, a `reboot` that would only ever
# reach a device if isolation had already failed.
BODIES: dict[str, dict] = {
    "POST /asset-collections/{collection_id}/add-to-playlist": {
        "playlist_id": "00000000-0000-4000-8000-000000000000"
    },
    "PUT /asset-collections/{collection_id}/items": {"asset_ids": []},
    "POST /assets/{asset_id}/versions": {
        "filename": "audit.png",
        "mime_type": "image/png",
        "size_bytes": 10,
    },
    "POST /campaigns/{campaign_id}/targets": {"targets": []},
    "POST /campaigns/{campaign_id}/targets/preview": {
        "targets": [{"target_type": "device", "target_id": "00000000-0000-4000-8000-000000000000"}]
    },
    "POST /campaigns/{campaign_id}/variants": {
        "name": "audit",
        "targets": [{"target_type": "device", "target_id": "00000000-0000-4000-8000-000000000000"}],
    },
    "PUT /data-sources/{source_id}/schema": {"schema_spec": {"required": ["audit.value"]}},
    "PUT /decision-policies/{policy_id}/rules": {"rules": []},
    "POST /device-groups/{group_id}/actions": {"command_type": "reboot"},
    "POST /device-groups/{group_id}/members": {"device_ids": []},
    "POST /devices/{device_id}/commands": {"command_type": "reboot"},
    "POST /experiments/{experiment_id}/transition": {"action": "stop"},
    "POST /fleet-intelligence/{anomaly_id}/remediation": {"action": "clear_cache"},
    "PATCH /folders/{folder_id}": {"name": "audit"},
    "POST /locations/{location_id}/tags": {"tags": []},
    "PUT /playlists/{playlist_id}/items": {"items": []},
    "PATCH /roles/{role_id}": {"description": "audit"},
    "POST /templates/{template_id}/clone": {"name": "audit"},
    "POST /video-walls/{wall_id}/members": {
        "device_id": "00000000-0000-4000-8000-000000000000",
        "viewport": {},
    },
    "POST /video-walls/{wall_id}/sync": {"action": "stop"},
    "POST /widgets/{widget_id}/versions": {"config_schema_json": {}},
}

PARAM = re.compile(r"\{(\w+)(?::[^}]*)?\}")


@dataclass
class Probe:
    direction: str
    method: str
    path: str
    status: int
    outcome: str
    detail: str = ""


def login(client: httpx.Client, email: str, password: str) -> tuple[str, dict]:
    for attempt in range(3):
        r = client.post("/auth/login", json={"email": email, "password": password})
        if r.status_code == 200:
            data = r.json()["data"]
            return data["access_token"], data["user"]
        if r.status_code != 429:
            break
        time.sleep(8 * (attempt + 1))
    raise SystemExit(f"login failed for {email}: {r.status_code} {r.text[:200]}")


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def load_routes(client: httpx.Client) -> list[tuple[str, str]]:
    for candidate in ("/api/openapi.json", "/openapi.json", "/api/v1/openapi.json"):
        r = client.get(candidate)
        if r.status_code == 200 and "paths" in r.json():
            spec = r.json()
            break
    else:
        raise SystemExit("could not fetch the OpenAPI document")
    routes = []
    for path, methods in spec["paths"].items():
        if not path.startswith("/api/v1"):
            continue
        short = path[len("/api/v1") :]
        for method in methods:
            routes.append((method.upper(), short))
    return sorted(routes, key=lambda r: (r[1], r[0]))


def items_of(payload: object) -> list[dict]:
    data = payload.get("data") if isinstance(payload, dict) else None
    if isinstance(data, list):
        return [d for d in data if isinstance(d, dict)]
    if isinstance(data, dict):
        for key in ("items", "results", "data"):
            if isinstance(data.get(key), list):
                return [d for d in data[key] if isinstance(d, dict)]
    return []


def dig(obj: dict, dotted: str) -> object:
    cur: object = obj
    for part in dotted.split("."):
        if isinstance(cur, list):
            cur = cur[0] if cur else None
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    if isinstance(cur, list):
        cur = cur[0] if cur else None
    return cur


class Harvester:
    """Collects one real id per collection from a tenant, lazily."""

    def __init__(self, client: httpx.Client, token: str):
        self.client = client
        self.token = token
        self.cache: dict[str, str | None] = {}
        self.seeded_ids: set[str] = set()

    def list_ids(self, list_path: str, field: str = "id", rows_key: str = "") -> str | None:
        key = f"{list_path}#{rows_key}#{field}"
        if key in self.cache:
            return self.cache[key]
        r = self.client.get(list_path, params={"page_size": 5}, headers=bearer(self.token))
        value: str | None = None
        if r.status_code == 200:
            payload = r.json()
            rows = items_of(payload)
            if rows_key:
                data = payload.get("data")
                rows = (
                    [d for d in (data.get(rows_key) or []) if isinstance(d, dict)]
                    if isinstance(data, dict)
                    else []
                )
            if list_path == "/roles":
                rows = [r for r in rows if not r.get("is_system")] or rows
            for item in rows:
                got = item.get(field) or item.get("id")
                if got:
                    value = str(got)
                    break
        self.cache[key] = value
        return value

    def resolve(self, path: str) -> tuple[str, bool]:
        """Substitute Tenant B ids into a route path. Returns the concrete
        path and whether every id was real."""
        params = PARAM.findall(path)
        concrete = path
        all_real = True
        parent_ids: dict[str, str] = {}
        for index, name in enumerate(params):
            value: str | None = None
            if index == 0:
                prefix = path.split("{")[0].rstrip("/")
                for override, (list_path, field) in HARVEST_OVERRIDES.items():
                    if prefix.startswith(override):
                        value = self.list_ids(list_path, field)
                        break
                else:
                    value = self.list_ids(prefix, "id")
            elif name in NESTED:
                sub_path, rows_key = NESTED[name]
                for pname, pval in parent_ids.items():
                    sub_path = sub_path.replace("{" + pname + "}", pval)
                value = self.list_ids(sub_path, "id", rows_key)
            if value is None:
                value = str(uuid.uuid4())
                all_real = False
            parent_ids[name] = value
            concrete = re.sub(r"\{" + name + r"(?::[^}]*)?\}", value, concrete, count=1)
        return concrete, all_real


SEEDED: list[tuple[str, str, dict]] = [
    # (collection path, delete path template, create body)
    ("/asset-collections", "/asset-collections/{id}", {"name": "audit collection"}),
    ("/decision-policies", "/decision-policies/{id}", {"name": "audit policy"}),
    (
        "/fleet-intelligence/rules",
        "/fleet-intelligence/rules/{id}",
        {"name": "audit rule", "signal_type": "heartbeat_gaps"},
    ),
    ("/video-walls", "/video-walls/{id}", {"name": "audit wall"}),
    ("/data-exports", "/data-exports/{id}", {"name": "audit export", "dataset": "playback_events"}),
    ("/edge/bundles", None, {"name": "audit bundle"}),
]


def seed_victim(client: httpx.Client, victim: Harvester) -> list[tuple[str, str]]:
    """Create one throwaway record per otherwise-empty collection in the
    victim tenant, and prime the harvester with it. Returns delete paths."""
    created: list[tuple[str, str]] = []
    for list_path, delete_tpl, body in SEEDED:
        if victim.list_ids(list_path, "id"):
            continue  # real data exists; probe that instead
        r = client.post(list_path, json=body, headers=bearer(victim.token))
        if r.status_code >= 300:
            print(f"  seed {list_path}: {r.status_code} {r.text[:100]}")
            continue
        data = r.json().get("data") or {}
        new_id = str(data.get("id") or "")
        if not new_id:
            continue
        victim.cache[f"{list_path}##id"] = new_id
        if delete_tpl:
            created.append((delete_tpl.replace("{id}", new_id), new_id))
    return created


def classify(status: int, body: str, resolved: bool) -> tuple[str, str]:
    if not resolved and status == 404:
        return "UNRESOLVED", ""
    if status in (403, 404):
        if status == 403 and "permission" in body.lower():
            return (
                "DENIED",
                "403 by permission, not tenancy — re-check with a fully privileged user",
            )
        return "DENIED", ""
    if 200 <= status < 300:
        return "LEAK", body[:160]
    if status in (400, 422, 409):
        return "VALIDATION", body[:120]
    if status >= 500:
        return "ERROR", body[:160]
    return "OTHER", body[:120]


def sweep(
    client: httpx.Client,
    routes: list[tuple[str, str]],
    attacker_token: str,
    victim: Harvester,
    direction: str,
    include_delete: bool,
) -> list[Probe]:
    probes: list[Probe] = []
    for method, path in routes:
        if path.startswith(SKIP_PREFIXES) or "{" not in path or path in SKIP_ROUTES:
            continue
        concrete, resolved = victim.resolve(path)
        if method == "DELETE" and not include_delete:
            if not any(sid in concrete for sid in victim.seeded_ids):
                continue
        kwargs: dict = {"headers": bearer(attacker_token)}
        if method in ("POST", "PUT", "PATCH"):
            kwargs["json"] = BODIES.get(f"{method} {path}", {})
        r = client.request(method, concrete, **kwargs)
        outcome, detail = classify(r.status_code, r.text, resolved)
        probes.append(Probe(direction, method, path, r.status_code, outcome, detail))
    return probes


def list_scope_check(
    client: httpx.Client, routes: list[tuple[str, str]], token: str, org_id: str, direction: str
) -> list[Probe]:
    """Every list endpoint must only ever return the caller's tenant."""
    probes: list[Probe] = []
    for method, path in routes:
        if method != "GET" or "{" in path or path.startswith(SKIP_PREFIXES):
            continue
        r = client.get(path, params={"page_size": 50}, headers=bearer(token))
        if r.status_code != 200:
            continue
        foreign = [
            i
            for i in items_of(r.json())
            if "organization_id" in i and str(i["organization_id"]) != org_id
        ]
        if foreign:
            probes.append(
                Probe(
                    direction, "GET", path, 200, "LEAK", f"{len(foreign)} rows from another tenant"
                )
            )
    return probes


def platform_check(
    client: httpx.Client, routes: list[tuple[str, str]], token: str, direction: str
) -> list[Probe]:
    """Tenant principals must never reach the platform console, whatever
    they hold."""
    probes: list[Probe] = []
    for method, path in routes:
        if not path.startswith("/platform"):
            continue
        concrete = PARAM.sub(str(uuid.uuid4()), path)
        kwargs: dict = {"headers": bearer(token)}
        if method in ("POST", "PUT", "PATCH"):
            kwargs["json"] = {}
        r = client.request(method, concrete, **kwargs)
        outcome = "DENIED" if r.status_code == 403 else ("LEAK" if r.status_code < 400 else "OTHER")
        if outcome != "DENIED":
            probes.append(Probe(direction, method, path, r.status_code, outcome, r.text[:120]))
    return probes


def relational_checks(
    client: httpx.Client, attacker_token: str, victim: Harvester, direction: str
) -> list[Probe]:
    """Cross-tenant references inside otherwise valid bodies (IDOR through
    foreign keys). Each creates at most one record in the attacker's own
    tenant and removes it again."""
    probes: list[Probe] = []
    h = bearer(attacker_token)
    b_asset = victim.list_ids("/assets", "id")
    b_playlist = victim.list_ids("/playlists", "id")
    b_layout = victim.list_ids("/layouts", "id")
    b_device = victim.list_ids("/devices", "id")
    b_campaign = victim.list_ids("/campaigns", "id")
    b_location = victim.list_ids("/locations", "id")
    stamp = uuid.uuid4().hex[:8]

    def record(label: str, r: httpx.Response) -> None:
        status = r.status_code
        if status in (403, 404):
            probes.append(Probe(direction, "REL", label, status, "DENIED"))
        elif status in (400, 409, 422):
            # Only a denial if the server rejected the *foreign reference*;
            # a schema error means the probe itself was malformed.
            body = r.text.lower()
            if any(
                w in body
                for w in (
                    "not found",
                    "does not belong",
                    "another organization",
                    "foreign",
                    "unknown",
                )
            ):
                probes.append(Probe(direction, "REL", label, status, "DENIED", r.text[:100]))
            else:
                probes.append(Probe(direction, "REL", label, status, "VALIDATION", r.text[:160]))
        elif status >= 500:
            probes.append(Probe(direction, "REL", label, status, "ERROR", r.text[:160]))
        else:
            probes.append(Probe(direction, "REL", label, status, "LEAK", r.text[:160]))

    # Campaign pointing at the other tenant's playlist / layout.
    r = client.post(
        "/campaigns",
        json={"name": f"audit-{stamp}", "playlist_id": b_playlist, "layout_id": b_layout},
        headers=h,
    )
    record("POST /campaigns with foreign playlist_id + layout_id", r)
    if r.status_code < 300:
        cid = r.json()["data"]["id"]
        client.delete(f"/campaigns/{cid}", headers=h)

    # Own campaign, then targets / publish naming the other tenant's devices
    # and locations.
    r = client.post("/campaigns", json={"name": f"audit-{stamp}-own"}, headers=h)
    if r.status_code < 300:
        cid = r.json()["data"]["id"]
        r2 = client.post(
            f"/campaigns/{cid}/targets",
            json={
                "targets": [
                    {"target_type": "device", "target_id": b_device},
                    {"target_type": "location", "target_id": b_location},
                ]
            },
            headers=h,
        )
        record("POST /campaigns/{own}/targets with foreign device_ids + location_ids", r2)
        r3 = client.post(
            f"/campaigns/{cid}/targets/preview",
            json={"targets": [{"target_type": "device", "target_id": b_device}]},
            headers=h,
        )
        if r3.status_code < 300 and any(str(d.get("id")) == b_device for d in items_of(r3.json())):
            probes.append(
                Probe(direction, "REL", "targets/preview resolves foreign device", 200, "LEAK")
            )
        client.delete(f"/campaigns/{cid}", headers=h)

    # Playlist item referencing the other tenant's asset.
    r = client.post("/playlists", json={"name": f"audit-{stamp}"}, headers=h)
    if r.status_code < 300:
        pid = r.json()["data"]["id"]
        r2 = client.post(
            f"/playlists/{pid}/items",
            json={"asset_id": b_asset, "duration_ms": 5000},
            headers=h,
        )
        record("POST /playlists/{own}/items with foreign asset_id", r2)
        client.delete(f"/playlists/{pid}", headers=h)

    # Device group membership with the other tenant's device.
    r = client.post("/device-groups", json={"name": f"audit-{stamp}"}, headers=h)
    if r.status_code < 300:
        gid = r.json()["data"]["id"]
        r2 = client.post(
            f"/device-groups/{gid}/members", json={"device_ids": [b_device]}, headers=h
        )
        if r2.status_code < 300:
            members = r2.json().get("data") or {}
            added = members.get("added") if isinstance(members, dict) else None
            if added:
                probes.append(
                    Probe(
                        direction,
                        "REL",
                        "device-groups/{own}/members adds foreign device",
                        200,
                        "LEAK",
                    )
                )
            else:
                probes.append(
                    Probe(
                        direction,
                        "REL",
                        "device-groups/{own}/members with foreign device_id",
                        200,
                        "DENIED",
                        "foreign id silently ignored",
                    )
                )
        else:
            record("POST /device-groups/{own}/members with foreign device_id", r2)
        client.delete(f"/device-groups/{gid}", headers=h)

    # Schedule for the other tenant's campaign.
    r = client.post(
        "/schedules",
        json={"campaign_id": b_campaign, "start_date": "2030-01-01", "end_date": "2030-01-02"},
        headers=h,
    )
    record("POST /schedules with foreign campaign_id", r)
    if r.status_code < 300:
        sid = r.json()["data"]["id"]
        client.delete(f"/schedules/{sid}", headers=h)

    # Device reassignment into the other tenant's location.
    a_device = None
    r = client.get("/devices", params={"page_size": 1}, headers=h)
    if r.status_code == 200 and items_of(r.json()):
        a_device = items_of(r.json())[0]["id"]
    if a_device:
        r = client.post(
            f"/devices/{a_device}/assign-location", json={"location_id": b_location}, headers=h
        )
        record("POST /devices/{own}/assign-location with foreign location_id", r)

    return probes


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--delete", action="store_true", help="also send DELETE probes")
    ap.add_argument("--report", default=None, help="write the JSON report here")
    args = ap.parse_args()

    with httpx.Client(base_url=args.base, timeout=60) as raw:
        routes = load_routes(raw)
    print(f"{len(routes)} routes in the OpenAPI document")

    with httpx.Client(base_url=args.base + "/api/v1", timeout=60) as client:
        tok_a, user_a = login(client, TENANT_A[1], DEMO_PASSWORD)
        tok_b, user_b = login(client, TENANT_B[1], DEMO_PASSWORD)
        org_a, org_b = str(user_a["organization_id"]), str(user_b["organization_id"])
        print(f"A = {TENANT_A[0]} ({org_a})\nB = {TENANT_B[0]} ({org_b})")

        harvest_a, harvest_b = Harvester(client, tok_a), Harvester(client, tok_b)
        print("seeding throwaway records for empty collections…")
        cleanup = [(p, tok_b) for p, _ in seed_victim(client, harvest_b)]
        cleanup += [(p, tok_a) for p, _ in seed_victim(client, harvest_a)]
        harvest_b.seeded_ids = {p.rsplit("/", 1)[1] for p, t in cleanup if t == tok_b}
        harvest_a.seeded_ids = {p.rsplit("/", 1)[1] for p, t in cleanup if t == tok_a}
        probes: list[Probe] = []
        probes += sweep(client, routes, tok_a, harvest_b, "A->B", args.delete)
        probes += sweep(client, routes, tok_b, harvest_a, "B->A", args.delete)
        probes += list_scope_check(client, routes, tok_a, org_a, "A lists")
        probes += list_scope_check(client, routes, tok_b, org_b, "B lists")
        probes += platform_check(client, routes, tok_a, "A->platform")
        probes += relational_checks(client, tok_a, harvest_b, "A->B rel")
        probes += relational_checks(client, tok_b, harvest_a, "B->A rel")
        for path, token in cleanup:
            client.delete(path, headers=bearer(token))

    counts: dict[str, int] = {}
    for p in probes:
        counts[p.outcome] = counts.get(p.outcome, 0) + 1
    print("\nOutcome counts:", json.dumps(counts))

    findings = [p for p in probes if p.outcome in ("LEAK", "ERROR")]
    attention = [p for p in probes if p.outcome in ("VALIDATION", "UNRESOLVED", "OTHER")]
    print(f"\n== Findings ({len(findings)}) ==")
    for p in findings:
        print(f"  {p.direction:10} {p.method:6} {p.path:60} {p.status}  {p.detail}")
    print(f"\n== Not fully exercised ({len(attention)}) ==")
    for p in attention:
        print(f"  {p.direction:10} {p.method:6} {p.path:60} {p.status} {p.outcome} {p.detail[:80]}")

    if args.report:
        with open(args.report, "w", encoding="utf-8") as fh:
            json.dump({"counts": counts, "probes": [asdict(p) for p in probes]}, fh, indent=2)
        print(f"\nreport written to {args.report}")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
