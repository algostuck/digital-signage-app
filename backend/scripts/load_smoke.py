"""Load smoke test (SRS 20.1): concurrent device heartbeats + deployment
fan-out against a running backend.

Usage (from backend/, venv active, backend running on :8000):
    python scripts/load_smoke.py [device_count]

Registers N simulated devices, storms heartbeats, publishes a campaign to
all of them, storms manifest fetches and acknowledgements, prints latency
metrics, then removes every row it created (audit entries are kept - the
trail is append-only by design).
"""

import asyncio
import statistics
import sys
import time

import httpx

BASE = "http://localhost:8000/api/v1"
DEVICES = int(sys.argv[1]) if len(sys.argv) > 1 else 50
HEARTBEATS_PER_DEVICE = 5
CONCURRENCY = 50


def pct(values: list[float], p: float) -> float:
    return statistics.quantiles(values, n=100)[int(p) - 1] if len(values) > 1 else values[0]


async def timed(client, method, url, latencies, *, retry_429: bool = False, **kw):
    for _ in range(12):
        start = time.perf_counter()
        resp = await client.request(method, url, **kw)
        latencies.append((time.perf_counter() - start) * 1000)
        if resp.status_code == 429 and retry_429:
            # Back off to the next fixed window, like a real player would.
            await asyncio.sleep(10)
            continue
        resp.raise_for_status()
        return resp.json().get("data")
    raise RuntimeError(f"still rate-limited after retries: {url}")


async def main() -> None:
    async with httpx.AsyncClient(timeout=60) as client:
        login = await client.post(
            f"{BASE}/auth/login",
            json={"email": "admin@demo-org.com", "password": "Admin@12345"},
        )
        login.raise_for_status()
        admin = {"Authorization": "Bearer " + login.json()["data"]["access_token"]}

        # Phase-2 governance: the load test self-approves its campaign, so
        # maker-checker must be off for its duration; restored afterwards.
        policy_resp = await client.get(f"{BASE}/approval-policies", headers=admin)
        original_policy = next(
            (p for p in policy_resp.json()["data"] if p["entity_type"] == "campaign"),
            None,
        )
        await client.put(
            f"{BASE}/approval-policies/campaign",
            headers=admin,
            json={"require_approval": True, "maker_checker": False},
        )
        key = (await client.get(f"{BASE}/devices/enrollment-key", headers=admin)).json()[
            "data"
        ]["enrollment_key"]

        semaphore = asyncio.Semaphore(CONCURRENCY)

        async def limited(coro_fn, *args, **kw):
            async with semaphore:
                return await coro_fn(*args, **kw)

        # --- enrollment ---
        print(f"[1/6] Registering + approving {DEVICES} devices ...")
        started = time.perf_counter()
        reg_lat: list[float] = []

        async def enroll(index: int) -> tuple[str, str]:
            serial = f"LOAD-{index:04d}"
            reg = await timed(
                client, "POST", f"{BASE}/player/register", reg_lat, retry_429=True,
                json={"enrollment_key": key, "serial_no": serial, "platform": "loadtest"},
            )
            device_id = reg["device_id"]
            token = reg.get("device_token")
            for _ in range(4):
                if token:
                    return device_id, token
                if reg["status"] == "pending":
                    await client.post(f"{BASE}/devices/{device_id}/approve", headers=admin)
                else:  # active with a credential from a prior run
                    reset = await client.post(
                        f"{BASE}/devices/{device_id}/reset-token", headers=admin
                    )
                    if reset.status_code != 200:
                        print(f"      {serial}: reset-token -> {reset.status_code} {reset.text}")
                reg = await timed(
                    client, "POST", f"{BASE}/player/register", reg_lat, retry_429=True,
                    json={"enrollment_key": key, "serial_no": serial},
                )
                token = reg.get("device_token")
            raise RuntimeError(f"{serial}: no credential after retries (status {reg['status']})")

        devices = await asyncio.gather(*(limited(enroll, i) for i in range(DEVICES)))
        print(f"      done in {time.perf_counter() - started:.1f}s")

        # --- heartbeat storm ---
        total_beats = DEVICES * HEARTBEATS_PER_DEVICE
        print(f"[2/6] Heartbeat storm: {total_beats} heartbeats, concurrency {CONCURRENCY} ...")
        hb_lat: list[float] = []
        started = time.perf_counter()

        async def beat(device_id: str, token: str):
            await timed(
                client, "POST", f"{BASE}/player/{device_id}/heartbeat", hb_lat,
                headers={"X-Device-Token": token},
                json={"status": "online", "storage": {"used_percent": 40}},
            )

        await asyncio.gather(
            *(
                limited(beat, device_id, token)
                for device_id, token in devices
                for _ in range(HEARTBEATS_PER_DEVICE)
            )
        )
        hb_elapsed = time.perf_counter() - started
        print(
            f"      {total_beats} in {hb_elapsed:.1f}s = {total_beats / hb_elapsed:.0f} req/s"
            f" | p50 {pct(hb_lat, 50):.0f}ms p95 {pct(hb_lat, 95):.0f}ms"
        )

        # --- campaign + fan-out ---
        print(f"[3/6] Publishing a campaign to all {DEVICES} devices ...")
        group_resp = await client.post(
            f"{BASE}/device-groups", headers=admin, json={"name": "LOAD Group"}
        )
        if group_resp.status_code == 409:  # leftover from a prior aborted run
            groups = (await client.get(f"{BASE}/device-groups", headers=admin)).json()["data"]
            group = next(g for g in groups if g["name"] == "LOAD Group")
        else:
            group = group_resp.json()["data"]
        await client.post(
            f"{BASE}/device-groups/{group['id']}/members",
            headers=admin,
            json={"device_ids": [d for d, _ in devices]},
        )
        playlists = (
            await client.get(f"{BASE}/playlists?status=published", headers=admin)
        ).json()["data"]
        campaign = (
            await client.post(
                f"{BASE}/campaigns",
                headers=admin,
                json={
                    "name": "LOAD Campaign",
                    "priority": 40,
                    "playlist_id": playlists[0]["id"],
                },
            )
        ).json()["data"]
        await client.post(
            f"{BASE}/schedules", headers=admin, json={"campaign_id": campaign["id"]}
        )
        await client.post(
            f"{BASE}/campaigns/{campaign['id']}/targets",
            headers=admin,
            json={"targets": [{"target_type": "group", "target_id": group["id"]}]},
        )
        await client.post(f"{BASE}/campaigns/{campaign['id']}/submit-approval", headers=admin)
        await client.post(f"{BASE}/campaigns/{campaign['id']}/approve", headers=admin)
        started = time.perf_counter()
        deployment = (
            await client.post(f"{BASE}/campaigns/{campaign['id']}/publish", headers=admin)
        ).json()["data"]
        fanout = time.perf_counter() - started
        assert deployment["total_devices"] == DEVICES, deployment
        print(f"      fan-out to {deployment['total_devices']} devices in {fanout * 1000:.0f}ms")

        # --- manifest storm ---
        print(f"[4/6] Manifest storm: {DEVICES} concurrent fetches ...")
        mf_lat: list[float] = []
        started = time.perf_counter()
        await asyncio.gather(
            *(
                limited(
                    timed, client, "GET", f"{BASE}/player/{device_id}/manifest", mf_lat,
                    headers={"X-Device-Token": token},
                )
                for device_id, token in devices
            )
        )
        mf_elapsed = time.perf_counter() - started
        print(
            f"      {DEVICES} in {mf_elapsed:.1f}s = {DEVICES / mf_elapsed:.0f} req/s"
            f" | p50 {pct(mf_lat, 50):.0f}ms p95 {pct(mf_lat, 95):.0f}ms"
        )

        # --- ack storm ---
        print("[5/6] Acknowledgement storm ...")
        ack_lat: list[float] = []
        started = time.perf_counter()
        await asyncio.gather(
            *(
                limited(
                    timed, client, "POST",
                    f"{BASE}/player/{device_id}/deployments/{deployment['id']}/ack",
                    ack_lat, headers={"X-Device-Token": token}, json={"success": True},
                )
                for device_id, token in devices
            )
        )
        ack_elapsed = time.perf_counter() - started
        final = (
            await client.get(f"{BASE}/deployments/{deployment['id']}", headers=admin)
        ).json()["data"]
        print(
            f"      {DEVICES} acks in {ack_elapsed:.1f}s"
            f" | p95 {pct(ack_lat, 95):.0f}ms | deployment -> {final['status']}"
            f" ({final['acknowledged']}/{final['total_devices']})"
        )
        assert final["status"] == "published"

        # --- cleanup ---
        print("[6/6] Cleaning up load-test rows ...")
        if original_policy is not None:
            await client.put(
                f"{BASE}/approval-policies/campaign",
                headers=admin,
                json={
                    "require_approval": original_policy["require_approval"],
                    "maker_checker": original_policy["maker_checker"],
                },
            )
        from sqlalchemy import text

        from app.db.session import get_engine

        engine = get_engine()
        async with engine.begin() as conn:
            await conn.execute(
                text("DELETE FROM campaigns WHERE name = 'LOAD Campaign'")
            )
            await conn.execute(text("DELETE FROM devices WHERE serial_no LIKE 'LOAD-%'"))
            await conn.execute(text("DELETE FROM device_groups WHERE name = 'LOAD Group'"))
            await conn.execute(
                text("DELETE FROM notifications WHERE title LIKE '%LOAD-%'")
            )
        await engine.dispose()
        print("      done. (Audit entries are intentionally kept.)")


if __name__ == "__main__":
    asyncio.run(main())
