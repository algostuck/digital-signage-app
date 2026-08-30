# Demo Seed — Validation Report

Evidence that the seeded dataset is actually usable through the product,
not just present in the database.

## 1. Database integrity — 17/17

`python -m app.demo_seed --validate` (also runs automatically after every
seed). Each check is a real query, not an assumption.

| # | Check | Result |
|---|---|---|
| 1 | All 3 demo tenants exist | PASS |
| 2 | Permission catalogue intact (43 codes) | PASS |
| 3 | Plan catalogue intact (4 plans) | PASS |
| 4 | System roles intact (4) | PASS |
| 5 | `platform@signage.cloud` preserved, still superuser | PASS |
| 6 | `admin@demo-org.com` test fixture preserved | PASS |
| 7 | Every device points at a location in its own tenant | PASS |
| 8 | Location tree has no broken parents | PASS |
| 9 | Every playback event references a live device | PASS |
| 10 | Every playlist item references a real asset | PASS |
| 11 | No empty playlists | PASS |
| 12 | Every campaign has at least one target | PASS |
| 13 | Every asset has a current version | PASS |
| 14 | Every demo user holds a role | PASS |
| 15 | Every demo tenant has a subscription | PASS |
| 16 | No device/location cross-tenant leakage | PASS |
| 17 | Campaign lifecycle is varied (≥5 distinct statuses) | PASS |

## 2. Live API validation — 50/50

`python backend/scripts/demo_api_validation.py` against a running server.
This exercises HTTP endpoints with real tokens, not the ORM.

- **Platform admin** — logs in, retains `is_superuser`, `/platform/tenants`
  lists all three demo tenants.
- **Test fixture admin** — `admin@demo-org.com` still logs in.
- **Every role logs in** and receives the expected role: Organization
  Administrator, Content Manager, Device Manager, Campaign Approver,
  Regional Operations Manager, Report Viewer, Viewer.
- **Populated tenant** — dashboard summary, devices, location tree,
  content, campaigns, playlists, schedules, deployments, notifications,
  audit logs, subscription, deployment report and proof-of-play report
  all return non-empty data.
- **Fleet is not all-green** — the summary reports online *and* offline
  devices.
- **Location hierarchy is 6 levels deep and rooted at India.**

### Cross-tenant isolation (mandatory)

| Check | Result |
|---|---|
| Both tenants return their own devices | PASS |
| Tenant device lists do not overlap | PASS |
| RRL admin fetching a BMR device by id → refused (404) | PASS |
| Tenant admin reaching `/platform/tenants` → 403 | PASS |

### Multi-tenant switching (one person, two tenants)

Vikram Malhotra is a Regional Operations Manager in RRL-DEMO (his home
tenant) and a guest **Viewer** in BharatMart.

| Check | Result |
|---|---|
| `/auth/memberships` returns exactly 2 tenants | PASS |
| The switcher lists each organization once (no duplicate home row) | PASS |
| `/auth/switch-tenant` rotates the token pair | PASS |
| After switching, the tenant's *own* devices are returned | PASS |
| The guest role is enforced after switching (campaign create → 403) | PASS |

### RBAC

| Check | Result |
|---|---|
| Viewer can list devices (200) | PASS |
| Viewer creating a campaign → 403 | PASS |

## 3. Frontend smoke test

Signed in as Arjun Mehta (RRL-DEMO) in the browser:

| Screen | Observed |
|---|---|
| Dashboard | 108/130 online · 8 warning · 8 offline · 3 pending approval; recent deployments with partial/failed states; recent activity feed |
| Devices | Realistic names (*Anna Nagar Store · Product Display — LG 55"*), synthetic serials, platform, group, lifecycle + connection status, heartbeat ages |
| Locations | India → Delhi NCR → New Delhi → Connaught Place → Connaught Place Store → Customer Service (6 levels) |
| Content | Real rendered thumbnails, published/draft badges, file sizes, folder tree |
| Reports | Per-campaign deployments with acked / failed / pending counts |

No `NaN`, `undefined`, `null`, broken images, invalid dates or empty
states were observed on these screens.

## 4. Idempotency

The seeder resets its own tenants before rebuilding, so reruns are safe.
Two consecutive runs produced **identical counts** (258 devices, 13,775
playback events, 46 campaigns, 324 locations, 21 users) with 17/17 checks
passing each time. A fixed RNG seed keeps the world stable across runs.

## 5. Issue found and fixed: tenant thresholds were ignored

Seeding surfaced a real product bug, unrelated to the demo data itself.

Device connection state is derived from heartbeat age, and a tenant can
widen that window under **Monitoring → Tenant thresholds**. Only
`fleet_health` actually passed those thresholds to `connection_status()`.
The dashboard summary, the monitoring device feed, the device list/detail
serializers and the location health report all used the platform defaults
— so **one tenant could see three different fleets on three screens**.

Fixed by passing the tenant's thresholds at every call site
(`app/services/monitoring.py`, `app/services/reports.py`,
`app/api/v1/devices.py`). Behaviour is unchanged for tenants on the
defaults. A regression test
(`tests/test_monitoring_api.py::test_tenant_thresholds_apply_consistently_across_surfaces`)
now asserts the device detail, device list, dashboard summary and fleet
health all agree after a threshold change.

## 6. Known constraints

- **Heartbeat decay.** Connection state is time-derived, so a static
  database cannot stay "live" forever without a player simulator. Demo
  tenants therefore use a 4h/24h monitoring window, and
  `--refresh` re-stamps heartbeats in ~1s before a demo.
- **Video payloads are placeholders.** Video-typed assets have real
  poster thumbnails so the library looks correct, but no encoded media —
  playback is not expected in a demo database.
- **The `demo` organization is intentionally preserved** (platform admin
  home + test fixture); it is not part of the Indian demo set.

## 7. Commands

```bash
python -m app.seed                          # system master data
python -m app.demo_seed                     # reset + rebuild demo tenants
python -m app.demo_seed --validate          # 17 integrity checks
python -m app.demo_seed --refresh           # restore the live-looking fleet
python -m app.demo_seed --reset             # remove demo tenants only
python scripts/demo_api_validation.py       # 44 live API checks
```
