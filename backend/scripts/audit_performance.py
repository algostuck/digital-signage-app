"""Performance audit against a running API with the seeded demo data.

Times the requests behind the screens a customer watches during a demo —
dashboard, device list, content library, location tree, campaign list,
reports, the screen designer's layout detail and the TV preview manifest —
first one at a time (p50 / p95 over N runs) and then under modest
concurrency, against the largest seeded tenant (Reliance Retail: 130
devices, 22 campaigns, ~30 days of playback).

Budgets (per request, warm, local PostgreSQL):
  list / detail endpoints   p95 < 300 ms
  aggregates (dashboard, reports, analytics)   p95 < 800 ms
  under 8 concurrent clients the p95 must stay under 2x the sequential p95

    python scripts/audit_performance.py [--base http://localhost:8000] [--runs 8] [--report path.json]
"""

# ruff: noqa: E501 - table rows read better on one line
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import statistics
import sys
import time

import httpx

ADMIN = ("arjun.mehta@rrl-demo.signage.cloud", "Demo@12345")  # noqa: S105 - documented demo credential

TODAY = dt.date.today()
FROM_7 = (TODAY - dt.timedelta(days=7)).isoformat()
FROM_30 = (TODAY - dt.timedelta(days=30)).isoformat()

# (label, path, params, budget_ms)
TARGETS: list[tuple[str, str, dict, int]] = [
    ("Dashboard (7 days)", "/dashboard/organization", {"from": FROM_7, "to": TODAY.isoformat()}, 800),
    ("Dashboard (30 days)", "/dashboard/organization", {"from": FROM_30, "to": TODAY.isoformat()}, 800),
    ("Device list (page of 50)", "/devices", {"page_size": 50}, 300),
    ("Device list (page of 200)", "/devices", {"page_size": 200}, 300),
    ("Device list, offline filter", "/devices", {"connection_status": "offline", "page_size": 50}, 300),
    ("Device list, search", "/devices", {"q": "Kolkata", "page_size": 50}, 300),
    ("Monitoring devices", "/monitoring/devices", {}, 300),
    ("Monitoring fleet health", "/monitoring/fleet-health", {}, 800),
    ("Content library (page of 50)", "/assets", {"page_size": 50}, 300),
    ("Content library, search", "/assets", {"q": "sale", "page_size": 50}, 300),
    ("Location tree", "/locations/tree", {}, 300),
    ("Location list (page of 100)", "/locations", {"page_size": 100}, 300),
    ("Campaign list", "/campaigns", {"page_size": 50}, 300),
    ("Playlist list", "/playlists", {"page_size": 50}, 300),
    ("Layout list", "/layouts", {"page_size": 50}, 300),
    ("Schedule calendar (30 days)", "/schedules/calendar", {"from": FROM_30, "to": TODAY.isoformat()}, 800),
    ("Deployments", "/deployments", {"page_size": 50}, 300),
    ("Proof of play (30 days)", "/reports/proof-of-play", {"date_from": FROM_30, "date_to": TODAY.isoformat()}, 800),
    ("Playback report", "/reports/playback", {}, 800),
    ("Device uptime report", "/reports/device-uptime", {}, 800),
    ("Campaign performance", "/reports/campaign-performance", {}, 800),
    ("Analytics aggregates (30 days)", "/analytics/aggregates", {"date_from": FROM_30, "date_to": TODAY.isoformat()}, 800),
    ("Notifications", "/notifications", {"page_size": 50}, 300),
    ("Audit log (page of 50)", "/audit-logs", {"page_size": 50}, 300),
    ("Global search", "/search", {"q": "store"}, 300),
    ("Fleet anomalies", "/fleet-intelligence/anomalies", {"page_size": 50}, 300),
]


def pct(values: list[float], p: int) -> float:
    if len(values) < 2:
        return values[0]
    return statistics.quantiles(values, n=100)[p - 1]


async def login(client: httpx.AsyncClient) -> str:
    for attempt in range(4):
        r = await client.post("/auth/login", json={"email": ADMIN[0], "password": ADMIN[1]})
        if r.status_code == 200:
            return r.json()["data"]["access_token"]
        if r.status_code != 429:
            raise SystemExit(f"login failed: {r.status_code} {r.text[:160]}")
        await asyncio.sleep(8 * (attempt + 1))
    raise SystemExit("login rate limited")


async def time_get(client: httpx.AsyncClient, path: str, params: dict, headers: dict) -> tuple[float, int, int]:
    start = time.perf_counter()
    r = await client.get(path, params=params, headers=headers)
    ms = (time.perf_counter() - start) * 1000
    return ms, r.status_code, len(r.content)


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--runs", type=int, default=8)
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--report", default=None)
    args = ap.parse_args()

    rows: list[dict] = []
    async with httpx.AsyncClient(base_url=args.base + "/api/v1", timeout=60) as client:
        token = await login(client)
        h = {"Authorization": f"Bearer {token}"}

        # Detail endpoints need real ids.
        r = await client.get("/devices", params={"page_size": 1}, headers=h)
        device_id = (r.json().get("data") or [{}])[0].get("id")
        r = await client.get("/layouts", params={"page_size": 1}, headers=h)
        layout_id = (r.json().get("data") or [{}])[0].get("id")
        r = await client.get("/campaigns", params={"page_size": 1}, headers=h)
        campaign_id = (r.json().get("data") or [{}])[0].get("id")
        targets = list(TARGETS)
        if device_id:
            targets.append(("Device detail", f"/devices/{device_id}", {}, 300))
            targets.append(("TV preview manifest", f"/devices/{device_id}/preview-manifest", {}, 800))
            targets.append(("Device events", f"/devices/{device_id}/events", {"limit": 50}, 300))
        if layout_id:
            targets.append(("Screen designer: layout detail", f"/layouts/{layout_id}", {}, 300))
        if campaign_id:
            targets.append(("Campaign detail", f"/campaigns/{campaign_id}", {}, 300))
            targets.append(("Campaign effective targets", f"/campaigns/{campaign_id}/effective-targets", {}, 800))

        print(f"{'endpoint':38} {'p50 ms':>8} {'p95 ms':>8} {'max ms':>8} {'bytes':>9}  budget  status")
        for label, path, params, budget in targets:
            # one warm-up, then N timed runs
            await time_get(client, path, params, h)
            samples, sizes, codes = [], [], set()
            for _ in range(args.runs):
                ms, code, size = await time_get(client, path, params, h)
                samples.append(ms)
                sizes.append(size)
                codes.add(code)
            p50, p95, mx = pct(samples, 50), pct(samples, 95), max(samples)
            ok = p95 <= budget and codes == {200}
            rows.append({"endpoint": label, "path": path, "p50_ms": round(p50), "p95_ms": round(p95), "max_ms": round(mx), "bytes": max(sizes), "budget_ms": budget, "status": sorted(codes), "ok": ok})
            print(f"{label:38} {p50:8.0f} {p95:8.0f} {mx:8.0f} {max(sizes):9}  {budget:>5}  {'ok' if ok else 'SLOW' if codes == {200} else 'ERR ' + ','.join(map(str, codes))}")

        # Concurrency: the demo's heaviest screens fetched by N clients at once.
        heavy = [t for t in targets if t[0] in ("Dashboard (7 days)", "Device list (page of 50)", "Content library (page of 50)", "Proof of play (30 days)", "Location tree", "TV preview manifest")]
        print(f"\n{args.concurrency} concurrent clients, each fetching every heavy endpoint {args.runs} times:")
        conc: dict[str, list[float]] = {t[0]: [] for t in heavy}

        async def worker() -> None:
            for _ in range(args.runs):
                for label, path, params, _budget in heavy:
                    ms, code, _size = await time_get(client, path, params, h)
                    if code == 200:
                        conc[label].append(ms)

        start = time.perf_counter()
        await asyncio.gather(*(worker() for _ in range(args.concurrency)))
        wall = time.perf_counter() - start
        total = sum(len(v) for v in conc.values())
        print(f"  {total} requests in {wall:.1f}s = {total / wall:.0f} req/s")
        for label, values in conc.items():
            seq = next(r for r in rows if r["endpoint"] == label)
            p95c = pct(values, 95) if values else float("nan")
            ratio = p95c / seq["p95_ms"] if seq["p95_ms"] else float("nan")
            ok = values and ratio <= 2.0
            rows.append({"endpoint": f"{label} @{args.concurrency}x", "p50_ms": round(pct(values, 50)) if values else None, "p95_ms": round(p95c) if values else None, "ratio_vs_sequential": round(ratio, 2), "ok": bool(ok)})
            print(f"  {label:36} p95 {p95c:7.0f} ms  ({ratio:.1f}x sequential){'' if ok else '  DEGRADED'}")

    slow = [r for r in rows if not r["ok"]]
    print(f"\n{len(rows) - len(slow)} within budget, {len(slow)} outside")
    for r in slow:
        print(f"  {r['endpoint']}: p95 {r['p95_ms']} ms")
    if args.report:
        with open(args.report, "w", encoding="utf-8") as fh:
            json.dump(rows, fh, indent=2)
    return 1 if slow else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
