# Demo Data Catalog

What `python -m app.demo_seed` builds, and why each part exists.
Counts below are from an actual seeded database, not targets.

## Tenants

| | RRL-DEMO | BMR-DEMO | USP-DEMO |
|---|---|---|---|
| Name | Reliance Retail Digital Experience | BharatMart Retail Network | UrbanSquare Properties |
| Industry | Retail | Grocery Retail | Commercial Real Estate |
| Plan | Enterprise (yearly) | Business (monthly) | Professional (yearly) |
| Devices | 130 | 88 | 40 |
| Users | 10 | 6 | 5 |
| Locations | 158 | 96 | 70 |
| Timezone / currency | Asia/Kolkata · INR | Asia/Kolkata · INR | Asia/Kolkata · INR |

All three are fictional demo tenants inspired by an Indian enterprise
context — not real customers, and not represented as such anywhere.

**BMR-DEMO sits at 88 of its 100-device plan limit on purpose**, so the
Plan & Usage screens have a genuinely near-limit tenant. No tenant
exceeds its limits.

## Volumes (totals across the three tenants)

| Entity | Count | Notes |
|---|---|---|
| Organizations | 3 | Three plans, three feature sets |
| Users | 21 | Every system role plus three custom roles |
| Roles (tenant-defined) | 9 | 3 custom roles × 3 tenants |
| Locations | 324 | Six levels: Country → State → City → Zone → Facility → Department |
| Devices | 258 | 8 commercial display/player models |
| Device groups | 30 | Regional, placement and fleet groupings |
| Tags | 66 | Device tags + content tags |
| Folders | 42 | Marketing / Corporate / Regional / Archived trees |
| Assets | 90 | Each with a real rendered JPEG + thumbnail |
| Layouts | 30 | Fullscreen, split, ticker and 6-zone grids |
| Templates | 39 | 10 business presets + platform starter templates |
| Widgets | 24 | Clock, weather, ticker, countdown, QR, API, RSS |
| Playlists | 27 | 3–7 items each, varied durations |
| Campaigns | 46 | Mixed lifecycle (below) |
| Campaign targets | 46 | Location, group and tag targeting |
| Campaign variants | 12 | A/B creatives for experiments |
| Schedules | 87 | Indian retail dayparts + deliberate conflicts |
| Deployments | 34 | Per-device acknowledged / pending / failed |
| Playback events | ~13,800 | 14–30 days of proof-of-play |
| Notifications | 81 | Info / warning / critical |
| Audit logs | ~570 | Real actors and real entity ids |
| Incidents | 18 | Opened / acknowledged / resolved |
| Video walls | 4 | 2×2 and 3×3 (entitled tenants only) |
| Ad bookings | 4 | Enterprise tenant only |
| Experiments | 2 | Two-arm creative tests |
| Anomalies | 6 | Evidence-backed, with recommendations |
| Approval requests | 4 | Pending maker-checker items |
| API keys | 6 | Hashed exactly as the product does; no raw key stored |
| Webhook subscriptions / deliveries | 3 / 16 | Delivered and failed attempts |
| Event-bus subscriptions / domain events | 3 / 6 | Phase-3 event bus |
| Data sources | 6 | REST + RSS feeds, token by env-var *reference* |
| Notification rules | 6 | in-app / email channels with severity conditions |
| Saved views | 3 | A saved device filter per tenant admin |
| Cross-tenant membership | 1 | One person in two tenants (see below) |

## Geography

Six states, thirteen cities, real localities, real coordinates:

```
India
├── Maharashtra   Mumbai (Andheri, Bandra, Lower Parel, Powai), Pune (Hinjawadi, Kharadi, Viman Nagar)
├── West Bengal   Kolkata (Salt Lake, Park Street, New Town, Rajarhat), Durgapur
├── Karnataka     Bengaluru (Whitefield, Koramangala, Electronic City, Indiranagar), Mysuru
├── Telangana     Hyderabad (Banjara Hills, HITEC City, Gachibowli, Secunderabad)
├── Tamil Nadu    Chennai (T Nagar, OMR, Anna Nagar), Coimbatore
└── Delhi NCR     New Delhi, Gurugram, Noida, Ghaziabad
```

Every city and locality carries its true latitude/longitude, a plausible
PIN code, a synthetic *commercial* address (never a private residence),
`Asia/Kolkata`, operating hours and a contact number.

Facilities are stores for the retail tenants and towers for UrbanSquare;
each has 2–4 screen zones (Main Entrance, Billing Area, Food Court,
Elevator Lobby, Outdoor Facade, …) and devices hang off those zones.

## Fleet health

Connection state is *derived* from heartbeat age, so the demo tenants set
their own monitoring window (`warning_after_seconds: 14400`,
`offline_after_seconds: 86400`) — otherwise a database seeded an hour ago
would read as entirely offline. The seeded mix:

| State | Share | How it is produced |
|---|---|---|
| Online | ~84% of active | heartbeat 0–3h old |
| Warning | ~8% | heartbeat 5–20h old |
| Offline | ~8% | heartbeat 30–120h old |
| Pending approval | 3 per tenant | `status='pending'`, never approved |
| Decommissioned / rejected | a few | lifecycle states, report as `n/a` |

`python -m app.demo_seed --refresh` re-stamps heartbeats in about a
second if a demo database has been idle for days.

Each device also carries plausible telemetry (CPU, memory, storage,
temperature, network, signal), a player version, MAC/IP, orientation and
panel size — all varied, never identical.

## Content

30 business-titled assets per tenant — *Monsoon Mega Savings Banner*,
*Diwali Preview Showreel*, *Customer Safety Guidelines*, *East Zone
Regional Offer* … — filed under Marketing / Corporate / Regional trees and
tagged (`promotion`, `festival`, `safety`, `premium`, …).

Every asset gets a **real generated JPEG** (1920×1080) plus a 480×270
thumbnail written to the storage adapter, so the content library shows
true previews rather than broken images. Video-typed assets carry a real
poster thumbnail; their `.mp4` payload is a placeholder, so previews look
right but playback is not expected in a demo database.

## Campaign lifecycle

Deliberately not all published — every tenant shows a spread:

| Tenant | Spread |
|---|---|
| RRL-DEMO | published 12, draft 3, expired 2, approved 2, paused 1, pending_approval 1, archived 1 |
| BMR-DEMO | published 7, approved 2, expired 2, pending_approval 2, archived 1 |
| USP-DEMO | published 5, approved 2, draft 1, expired 1, pending_approval 1 |

Schedules use Indian retail dayparts (Morning 08:00–11:00 … Late Evening
21:00–23:00), some weekday-only, some open-ended, some starting in the
future. A small number of **deliberately overlapping windows** exist so
conflict detection has something real to find.

Deployments record per-device acknowledged / pending / failed states —
never 100% success — and playback is skewed so a few campaigns carry most
of the plays (13,477 ok vs 298 error) rather than every asset having an
identical count.

## Phase-2 / Phase-3 surfaces

Seeded only where the tenant's plan entitles it, which is itself part of
the demonstration:

| Feature | RRL (Enterprise) | BMR (Business) | USP (Professional) |
|---|---|---|---|
| Video walls | ✓ 2×2 + 3×3 | — | ✓ |
| Advertising | ✓ 4 bookings | — | — |
| Experiments (A/B) | ✓ | — | ✓ |
| Fleet AI anomalies | ✓ | — | ✓ |
| Approval workflow | ✓ | ✓ | ✓ |

Anomalies carry real evidence (`playback_events`, `failures`,
`location_baseline_pct`) and a recommendation tied to that evidence —
not a random score.

## Dates

Nothing shares a `created_at`. Locations and devices are spread over
20–300 days, content over 3–150 days, campaigns over 2–90 days, playback
across the last 14–30 days, audit over ~55 days and notifications over
~25 days. Some schedules and subscription renewals sit in the future so
upcoming activity is visible.

## Multi-tenancy

**Vikram Malhotra** is a Regional Operations Manager in RRL-DEMO (his
home tenant) and a guest **Viewer** in BharatMart — the only account with
two tenants, so the header's tenant switcher appears and switching can be
demonstrated end to end. His guest role is enforced after switching: he
can read BharatMart but not create campaigns there.

No `TenantUser` row is written for a user's *own* organization: the
platform treats home membership as implicit, and adding one would make
the switcher list the home tenant twice.

## Secrets

Nothing secret is stored in readable form. API keys are generated and
immediately hashed with the product's own hasher (only a 12-character
prefix is retained); webhook and event-bus signing secrets are random
per subscription; data-source credentials are stored as an environment
variable *name* (`DEMO_FEED_TOKEN`), never a value; user passwords are
bcrypt hashes of the documented demo password.

## Determinism

The seeder runs from a fixed RNG seed (`SEED = 20260830`), so a rerun
produces the same believable world rather than a different random one.
