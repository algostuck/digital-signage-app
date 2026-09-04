# Organization Administrator Dashboard — Audit

Date: 2026-09-04. Read-only audit of the current dashboard, every tenant-scoped
data source that could feed a redesign, the seeded demo database, and the
frontend's reusable parts. Everything below was verified against code or a
live query; nothing is assumed. No code was changed during the audit.

---

## 1. Current dashboard

`frontend/src/modules/dashboard/DashboardPage.tsx` — one file, 199 lines,
no sub-components, no types module.

| Aspect | Today |
|---|---|
| Data | One call: `GET /monitoring/summary`, refetched every 30 s (key `["monitoring-summary"]`, shared with the header bell) |
| Layout | 4 `StatCard`s (devices online, content, active campaigns, deployments) → golden-split row (15/9): "Recent deployments" list + "Recent activity" list |
| Charts | None |
| Map | None |
| Attention / alerts | None (unread count only, as a bell badge) |
| Drill-down | Cards link to `/devices`, `/content`, `/campaigns`, `/deployments` with **no filter context** — and no page in the app reads URL search params anyway |
| Time filter | None |
| Refresh | Silent polling; no "last updated" |
| Deprecated | Both feeds use antd `List`, deprecated in 6.6 |
| Unused data | `/monitoring/summary` already returns `devices.active` and `campaigns.paused`; the page ignores them |
| Hard-coded colour | `#D97706 / #059669 / #DC2626` retyped instead of the theme's `BRAND` (which is not exported) |

It is a CRUD homepage: four numbers and two lists. It answers "how many" but
not "are they healthy", "where", "what is playing", or "what needs me".

---

## 2. Existing data sources (tenant-scoped, verified)

All routes are under `/api/v1`. Guard = the `require_permissions` code.
Every one is scoped by the JWT's active tenant in `app/api/deps.py`; no
endpoint accepts a client-supplied tenant id.

### Fleet & health
| Endpoint | Guard | Returns |
|---|---|---|
| `GET /monitoring/summary` | monitoring.view | devices `{total, active, online, warning, offline, pending}`, content `{total, published, draft}`, campaigns `{published, pending_approval, approved, draft, paused}`, deployments `{publishing, partial, published, failed}`, `notifications_unread`, `recent_deployments[5]`, `recent_activity[8]` |
| `GET /monitoring/fleet-health` | monitoring.view | org rollup `{devices, online, warning, offline, open_incidents, outdated_players}`; `locations[]` and `groups[]` rollups (subtree, active devices) |
| `GET /monitoring/devices` | monitoring.view | per-device `connection_status`, `storage`, `network`, **`current`** (now-playing item from the last heartbeat), worst-first — **no frontend consumer today** |
| `GET /incidents?state=` | monitoring.view | `{id, device_id, type, severity, state, opened_at, resolved_at}` |
| `GET /devices` | devices.view | filters `q, status, platform, group_id, location_id`; **no `connection_status` filter** (it is derived after the query) |
| `GET /devices/{id}/screenshots` | devices.view | real player uploads, presigned URLs, newest first |
| `GET /devices/{id}/preview-manifest` | devices.view | what one screen resolves to right now (built for the TV preview) |
| `GET /fleet-intelligence/anomalies` | monitoring.view | `{device_id, rule_id, score, state, evidence, recommendation}` |
| `GET /reports/device-uptime` | reports.view | per-device `uptime_pct` from `device_heartbeats`, default last 7 days |

`connection_status` is never stored. It is computed per read from
`last_heartbeat_at` against the tenant's thresholds
(`settings_json.monitoring.warning_after_seconds / offline_after_seconds`,
platform default 150 s / 300 s).

### Geography
| Endpoint | Guard | Returns |
|---|---|---|
| `GET /locations` (page_size ≤ 200) | locations.view | `{id, parent_id, name, code, path, depth, address, latitude, longitude, timezone, status, metadata_json, type{code,name}}` |
| `GET /locations/tree` | locations.view | nested active tree |
| `GET /reports/locations` | reports.view | `{location_id, name, depth, devices, online, warning, offline}` — **no coordinates** |

City, state and country are **levels of the tree** (per-tenant
`location_types`: country → state → city → store/building → zone →
department), not columns. `metadata_json` on seeded nodes carries `city`,
`state`, `pin_code`.

### Campaigns, schedules, approvals
| Endpoint | Guard | Returns |
|---|---|---|
| `GET /campaigns?status=` | campaigns.view | `{id, name, status, priority, schedule_count, updated_at}`; archived excluded unless asked |
| `GET /schedules/calendar?from=&to=` | schedules.view | expanded events per day (≤ 62 days), with `conflict` flags — **"today's schedule" = `from=to=today`** |
| `GET /approvals/inbox?state=pending` | any of campaigns.approve / layouts.manage / settings.manage | `{entity_type, entity_name, requester_name, submitted_at, state}` |
| `GET /reports/campaign-performance` | reports.view | per campaign `{acknowledged, pending, failed, plays, completed_plays, completion_rate, devices_played}` |

### Deployments
| Endpoint | Guard | Returns |
|---|---|---|
| `GET /deployments?status=` | deployments.view | `{campaign_name, version, status, total_devices, acknowledged, failed, pending, started_at, completed_at}` — counts computed in Python, `campaign_name` is an N+1 |
| `GET /reports/deployments` | reports.view | lifetime totals per campaign, no date filter |

### Content & playback
| Endpoint | Guard | Returns |
|---|---|---|
| `GET /assets?type=&status=` | content.view | asset rows with `current_version.size_bytes`, `thumbnail_url` |
| `GET /reports/playback?from=&to=` | reports.view | per asset `{plays, devices_reached}`, sorted by plays — the "most played" source |
| `GET /reports/proof-of-play?group_by=campaign\|asset\|device\|location` | reports.view | `{plays, completed, completion_rate, devices_reached, first_play, last_play}` |
| `GET /analytics/aggregates?dimension_type=&date_from=&date_to=` | reports.view | **the only per-day series** — but reads `analytics_aggregates`, written only by the nightly beat, never back-filled; **0 rows in every seeded tenant** |

### Activity, alerts, usage
| Endpoint | Guard | Returns |
|---|---|---|
| `GET /notifications?unread_only=` | notifications.view | `{type, severity(info\|warning\|critical), title, message, read_at, created_at}` |
| `GET /audit-logs?action=&entity_type=&from=&to=` | audit.view | `{action, entity_type, entity_id, user_name, created_at}` |
| `GET /events` | **webhooks.manage** (admin only) | domain events; no `device.online` type exists |
| `GET /organization/usage` | organization.view | live `{devices, users, storage_mb}` each `{used, limit}` |
| `GET /billing/subscription` | billing.view | plan, status, period, `usage`, `pending_plan_request` |
| `GET /entitlements` | none | plan feature flags (`proof_of_play`, `advanced_analytics`, `fleet_ai`, `ai_features`, …) |

### What does not exist
- No route contains "dashboard". `/monitoring/summary` is the de-facto one.
- No SSE / WebSocket anywhere. Everything is poll-only.
- No "insights" endpoint. AI endpoints are generation only (text, creative,
  localise). The only tenant-level *findings* are fleet-intelligence
  anomalies, whose `evidence` names the numbers behind each score.

---

## 3. Available metrics (can be shown honestly today)

| Metric | Source | Note |
|---|---|---|
| Devices total / active / pending | summary | point-in-time |
| Online / warning / offline **now** | summary, fleet-health | derived from heartbeats + tenant thresholds |
| Open incidents, outdated players | fleet-health | |
| Per-location and per-group health rollups | fleet-health | subtree, active devices only |
| Campaigns by status | summary (+ `/campaigns?status=`) | |
| Pending approvals with requester and age | approvals inbox | gated |
| Today's schedule with conflicts | calendar `from=to=today` | |
| Deployments by status; per-deployment progress | summary + `/deployments` | |
| Content by status; by type; storage used | summary, `/assets`, `/organization/usage` | |
| Most-played assets, per-campaign plays and completion | reports/playback, proof-of-play, campaign-performance | date-ranged |
| Device uptime % over a window | reports/device-uptime | from `device_heartbeats` |
| Unread notifications by severity | `/notifications` | |
| Recent audit activity | `/audit-logs` | |
| Plan, status, period, usage vs limits | billing/subscription, organization/usage | |
| Anomalies with evidence and recommendation | fleet-intelligence | needs `fleet_ai` |
| What one device is showing | preview-manifest / monitoring devices `current` | |

---

## 4. Missing metrics (no endpoint, or no data)

| Metric the brief wants | Status | Backing data that exists |
|---|---|---|
| **Device health trend** (online/offline by day) | No endpoint; status is never persisted | `device_heartbeats` — but **empty for every demo tenant** (only the fixture org has 19 rows). Incidents give a coarse offline-episode timeline |
| **Playback per day** (plays / completed / failed) | No live endpoint; aggregates table empty | `playback_events (started_at, result, asset_id, campaign_id, device_id)` — 9,365 / 3,602 / 783 rows per demo tenant, ~300/day, **frozen at 2026-08-31** |
| **Deployment success history** | No endpoint | `deployments.created_at` + `deployment_devices.status` |
| **Storage trend** | No endpoint | `usage_counters` is monthly; `asset_versions.created_at + size_bytes` gives cumulative-by-upload |
| **Per-location health with coordinates** | Two endpoints, neither has both | `/locations` (lat/lng) ⋈ `/reports/locations` or fleet-health (rollup) |
| **Now playing, fleet-wide** | Single-device only | latest `playback_events` per device; `devices.last_heartbeat_json.current` |
| **Offline devices list** | `/devices` cannot filter by `connection_status` | `last_heartbeat_at` is indexed; expressible in SQL against thresholds |
| **Unread count** | Only inside `/monitoring/summary` | fine — reuse |
| **AI insights** | No endpoint | anomalies + rules are the only honest source |

---

## 5. What the seeded demo actually contains

Profiled live on 2026-09-04 (script kept in the scratchpad). Three demo
tenants plus the test fixture org.

| | RRL-DEMO | BMR-DEMO | USP-DEMO |
|---|---|---|---|
| Devices | 130 (124 active) | 88 | 40 |
| Platforms | tizen 48 · webos 34 · android 32 · windows 16 | tizen 33 · android 22 · webos 22 · windows 11 | tizen 15 · android 10 · webos 10 · windows 5 |
| States / cities | 6 / 13 (Kolkata 24, Hyderabad 21, Bengaluru 20, Mumbai 18, Pune 14 …) | 3 / 6 | 3 / 7 |
| Locations with lat/lng | 71 of 158 — city, store, zone; **departments (where devices sit) have none** | 40 of 98 | 31 of 70 |
| Campaigns | 22 (11 published, 2 pending approval, 2 expired, 1 paused …) | 14 | 10 |
| Schedules active right now (published) | 4 | 2 | 1 |
| Deployments | 11, **all `partial`** (232 acked / 23 pending / 5 failed) | 7 | 4 |
| Assets | 30 (22 image, 8 video), 1.6 MB, thumbnails 30/30 | 30 | 30 |
| Playback events | 9,365 · 2026-08-01 → 08-31 · `ok` 9,143 / `error` 222 | 3,602 | 783 |
| Notifications | 22 (3 critical) | 20 | 29 |
| Incidents | 6 device_offline (2 open) | 6 | 6 (3 open) |
| Anomalies | 3 open (playback_failures) | 0 — no rule seeded | 3 open |
| Pending approvals | 2 | 2 | 2 |
| Subscription | Enterprise 128/5000 devices | **Business 88/100 devices, 98/100 locations** | Professional 40/500 |
| Screenshots | 0 | 0 | 0 |

### Five findings that would make widgets lie

1. **Every device reads offline.** The seed is frozen at 2026-08-31 01:11
   IST and nothing has heartbeated since. `demo_seed --refresh` re-stamps
   heartbeats and fixes this; it does not touch playback, incidents or
   notifications, so "today" stays empty for those.
2. **Playback `result` vocabulary mismatch — a real bug.** The seeder writes
   `ok` / `error` (`demo_seed.py:948`); every service counts success as
   `completed` (`reports.py:175,262`, `analytics.py:75`, `anomaly.py:227`).
   On demo tenants the app's own proof-of-play shows **0 completed and a
   100 % failure rate**. The seeder is wrong, not the services.
3. **No coordinates where devices live.** Departments (depth 5) carry no
   lat/lng; their parent zone/store and city do. Map markers must roll
   devices up to the nearest ancestor with coordinates.
4. **`device_heartbeats` is empty** for demo tenants, so a heartbeat-derived
   health trend and `/reports/device-uptime` are blank there.
5. **Audit "recent activity" is seed noise** — the newest entries are 158
   `LOCATION_CREATED` rows written at seed time.

Also found: `services/anomaly.py:248` filters `DeviceEvent.type`, but the
column is `event_type` — the `error_events` signal raises `AttributeError`
when evaluated.

---

## 6. Reusable frontend components

**As-is:** `api` client + envelope; TanStack Query defaults (`staleTime`
30 s, `retry` 1) and the 15/30/60 s polling ladder; `PageHeader`,
`StatCard`, `StatusBadge` (covers every status vocabulary the dashboard
needs), `DataTable`, `FilterBar`, `EmptyState` / `ErrorState` /
`LoadingState`, `EntitlementGuard` + `useEntitlements().hasFeature`,
`useAuth().hasPermission` (superuser short-circuits), `timeAgo`,
`GOLDEN_SPLIT` (15/9), the golden centred container
(`clamp(1024px, 61.8cqw, 1440px)`), `EVIDENCE_ROUTES` in `AuditPage.tsx`
(entity → route map, ready for a clickable activity feed), the
`Rows` stacked-list pattern from `PlatformOverviewPage` (replacement for the
deprecated `List`), `SessionUser.full_name` for the greeting.

**Small change:** `StatCard` gains a `to` prop (drill-down without wrapping
in `<Link>`) and accepts a semantic tone instead of a raw hex; export
`BRAND` from `theme/tokens.ts` so charts and cards share one palette.

**Must be built:** every chart, the map, the attention centre, now-playing,
approvals widget, usage widget, a dashboard `types.ts` + `api.ts` data
layer, and URL-param seeding on the destination pages (see §9).

---

## 7. Existing charts

**None.** No charting dependency (`package.json` has six runtime deps) and no
SVG chart primitive. Analytics, reports and monitoring are tables with the
occasional antd `Progress` bar. `StatCard.trend` exists but has never been
passed a value.

**Decision (confirmed): `@ant-design/plots` 2.6.** Antd family, matches the
"maximum Ant Design" directive, one library for donut, line, stacked bar
and horizontal bar. It renders G2 into a canvas; it cannot read antd CSS
variables (`cssVar` is off), so a thin theme-aware wrapper will pass
colours from `theme.useToken()` and the exported `BRAND`, and every chart
gets a text summary beside it so nothing is colour-only.

---

## 8. Existing map support

**None.** No map library, no SVG map, no geo aggregation. Coordinates are
shown as a string on the location detail panel. The data, however, is
map-ready: real Indian coordinates on 13 cities, 29 stores and 29 zones in
the primary demo tenant.

**Decision: `leaflet` 1.9 + `react-leaflet` 4.x** (v5 requires React 19;
the app is on 18), OpenStreetMap tiles. Real geography over a decorative
outline, because markers must correspond to actual location records.
Costs: one more dependency pair, Leaflet's stylesheet, and **internet
access for tiles during a demo** — the map degrades to a labelled list
when tiles fail. State polygons are deliberately not drawn: the map
communicates through markers, not political boundaries.

---

## 9. Drill-down: the destination pages

**Zero pages read URL search params** (`useSearchParams` appears nowhere).
Every filter is `useState(literal)`. So `/devices?status=offline` today
does nothing. The minimal change per page is a `useSearchParams()`-seeded
initial value:

| Page | Filter state today | Needed |
|---|---|---|
| Devices | `status` (lifecycle), `search`, `page` | seed from URL; add **connection_status** — needs the backend filter |
| Campaigns | none (unfiltered grid) | add a status `Segmented` + seed |
| Deployments | none | add a status filter + seed |
| Content | `type`, `search`; never sends `status` | seed; send `status` |
| Locations | `selectedId` from tree click | seed from `?id=` |
| Approvals | `tab` | seed from `?state=` |
| Notifications | `tab`; never sends `unread_only` | seed; send `unread_only` |
| Audit | `entityType`, `action` | seed |

---

## 10. Performance concerns

- A naive redesign fans out to **≈ 12 endpoints**, three of which are
  expensive: `fleet-health` rolls up every location subtree in Python
  (O(L × D)), `/deployments` does an N+1 for campaign names, and
  `/reports/locations` is O(L² × D).
- Four of the brief's centrepiece metrics have **no endpoint at all** (§4),
  so composition cannot produce them regardless of cost.
- `/monitoring/summary` is already polled by the header every 60 s; the
  dashboard must share that key, not add a second poll.
- `@ant-design/plots` is a large chunk; it must be lazy-loaded with the
  dashboard, not in the shell bundle.

---

## 11. API gaps and the recommendation

The brief says not to add an aggregate endpoint automatically. Composition
was tested against the inventory above and fails on all three of the
brief's own criteria: the fan-out is expensive, the same rollups would be
duplicated across widgets, and the trend / geo / now-playing blocks need
server aggregation that exists nowhere. So:

### `GET /dashboard/organization?from=&to=` (new, read-only)

One tenant-scoped response, sections omitted server-side when the caller
lacks the permission:

```
generated_at, range
kpis            devices{total,active,online,warning,offline,pending}
                campaigns{…} content{…} deployments{…}
                playback{plays,completed,failed,completion_rate}   ← range
                locations{total}
device_health   current{online,warning,offline,na}  trend[{date,online,warning,offline}]
geo[]           {location_id,name,type,latitude,longitude,devices,online,warning,offline,active_campaigns}
campaigns       by_status{}  top[{id,name,status,devices,acknowledged,failed,plays,updated_at}]
playback        series[{date,plays,completed,failed}]  top_assets[{asset_id,name,type,plays}]   ← range
content         by_type{} by_status{} storage_mb{used,limit}
deployments     by_status{}  history[{date,acknowledged,failed,pending}]  recent[]              ← range
locations_top[] {location_id,name,devices,online,health_pct}
attention[]     {severity,kind,count,label,href}
activity[]      {id,action,entity_type,entity_id,user_name,created_at}     (audit.view)
approvals[]     pending inbox                                             (campaigns.approve)
schedule_today[] calendar events for today                                (schedules.view)
now_playing[]   {device_id,device_name,location_name,campaign_name,asset_name,reported_at,source}
usage           {plan_name,status,period_end,devices,users,storage_mb,locations}   (billing.view)
insights[]      anomalies with evidence → {finding,why,action,href}       (fleet_ai)
```

Every block is a `GROUP BY` on an indexed column or a reuse of an existing
service function. Geo rolls devices up to the nearest ancestor with
coordinates. `now_playing` is the latest playback event per device inside
the last N minutes (`source: "reported"`), falling back to the schedule
resolver without asset signing (`source: "scheduled"`) — labelled, never
conflated.

### `device_health_snapshots` (new table, migration 0036)

The trend needs a persisted series and `device_heartbeats` is empty on the
demo. The existing offline-detection beat (every 120 s) will write one
row per tenant per hour — `{organization_id, captured_at, online, warning,
offline, na}` — cheap, honest, and it accrues from the moment it ships.
The demo seeder back-fills 30 days so the chart is not empty on day one,
documented as demo data like everything else the seeder writes.

### Two small additions to existing endpoints
- `GET /devices?connection_status=online|warning|offline` — expressed in SQL
  against the tenant thresholds; makes every drill-down real.
- `GET /notifications` — nothing; the summary's unread count suffices.

### Demo data corrections (seeder, not services)
1. Write `result = "completed"`, the canonical value, instead of `ok`.
2. Make `--refresh` shift **playback, incidents, notifications and
   snapshots** forward with the heartbeats, so the demo reads as live.
3. Seed one fleet-intelligence rule for BMR-DEMO so the insights section is
   not empty on one tenant only.
4. Fix `DeviceEvent.type` → `event_type` in `anomaly.py`.

Screenshots stay empty — the seeder will not fabricate them. The "Live
screens" widget instead renders three devices through the existing TV
preview engine (what each screen resolves to right now), which is real.

---

## 12. Recommended architecture

```
frontend/src/modules/dashboard/
├── DashboardPage.tsx            composition only — grid, widget visibility
├── types.ts                     the response contract above
├── api.ts                       useDashboard(range), useDashboardRange, keys
├── charts/                      theme-aware wrappers over @ant-design/plots
│   ├── ChartFrame.tsx           title, text summary, loading/empty/error
│   ├── Donut.tsx  Trend.tsx  StackedBar.tsx  RankBar.tsx
├── widgets/
│   ├── DashboardHeader.tsx      greeting (full_name), org, range, refresh, customise
│   ├── KpiGrid.tsx / KpiCard    6 tiles, drill-down links with query params
│   ├── DeviceHealthWidget.tsx   donut + trend + text summary
│   ├── AttentionWidget.tsx      severity-ranked, every row actionable
│   ├── LocationMapWidget.tsx    leaflet, city markers, drawer on click, filter bar
│   ├── CampaignWidget.tsx       status bar + top campaigns table
│   ├── PlaybackWidget.tsx       KPIs + line series + most played
│   ├── DeploymentWidget.tsx     health summary + progress rows
│   ├── ContentWidget.tsx        type donut + recent
│   ├── TopLocationsWidget.tsx   ranked, click → /locations?id=
│   ├── NowPlayingWidget.tsx     reported / scheduled, thumbnails
│   ├── LiveScreensWidget.tsx    3 × TV preview at thumbnail size
│   ├── ActivityWidget.tsx       audit feed with EVIDENCE_ROUTES links
│   ├── ApprovalsWidget.tsx      only with campaigns.approve
│   ├── ScheduleTodayWidget.tsx  timeline
│   ├── UsageWidget.tsx          plan + progress bars + threshold warnings
│   └── InsightsWidget.tsx       anomalies → finding / why / action
└── customise.ts                 widget visibility + order, localStorage, reset
```

**Data flow.** One `useDashboard(range)` query (30 s poll, key shared by all
widgets) feeds the first viewport. Range changes refetch only the ranged
blocks. Usage is cached 5 min. Every widget owns its loading / empty /
error state through `ChartFrame`, so one failing block never blanks the
page. The header bell keeps using `["monitoring-summary"]` unchanged.

**Permissions.** The endpoint omits sections the caller cannot see; widgets
render nothing for absent sections. Viewer gets the full read-only picture
minus approvals and audit if those codes are missing; nothing on the page
mutates data.

**Customise.** Hide/show and reorder, saved per browser in `localStorage`
under the user id, with Reset. No server-side layout store — the brief
asked for this only where it fits cleanly, and it does not justify a new
table.

---

## 13. Proposed layout

Desktop (≥ xl), inside the golden container; spans are antd's 24-col grid.

```
┌──────────────────────────────────────────────────────────────────────┐
│ Dashboard · BharatMart Retail Network                                │
│ Good evening, Atanu — here's the operational overview of your network│
│                    [Today | 7d | 30d | 90d | Custom] [↻ 42s ago] [⚙] │
├──────────┬──────────┬──────────┬──────────┬──────────┬──────────────┤
│ Devices  │ Online   │ Offline  │ Active   │ Playback │ Deployments  │  6 × 4
│ 130      │ 106 82%  │ 18 ▲     │ campaigns│ 7,774    │ 3 in progress│
├──────────┴──────────┴──────────┴──┬───────┴──────────┴──────────────┤
│ DEVICE HEALTH                (15) │ NEEDS ATTENTION              (9) │
│ donut + 30-day trend + summary    │ 18 offline · 5 failed · 2 appr. │
├───────────────────────────────────┼─────────────────────────────────┤
│ SIGNAGE NETWORK — INDIA      (15) │ CAMPAIGNS                    (9) │
│ leaflet, 13 city markers, filters │ status bar + top campaigns       │
├───────────────────────────────────┼─────────────────────────────────┤
│ PLAYBACK / PROOF OF PLAY     (15) │ DEPLOYMENTS                  (9) │
│ plays·completed·failed line + KPIs│ health summary + progress rows   │
├───────────────────────────────────┼─────────────────────────────────┤
│ CONTENT                      (12) │ TOP LOCATIONS               (12) │
├───────────────────────────────────┼─────────────────────────────────┤
│ NOW PLAYING + LIVE SCREENS   (15) │ ACTIVITY | APPROVALS | TODAY (9) │
├───────────────────────────────────┼─────────────────────────────────┤
│ SUBSCRIPTION & USAGE         (12) │ INSIGHTS                    (12) │
└───────────────────────────────────┴─────────────────────────────────┘
```

15/9 is the codebase's existing golden split; 12/12 where the two halves
carry equal weight. Tablet: KPIs 3 × 8, every pair stacks to 24. Mobile:
KPIs as a horizontally scrolling strip, then Attention → Device health →
Campaigns → Map (collapsed by default) → Playback → Deployments →
Activity → Usage, each in a collapsible section.

---

## 14. Implementation order

1. Backend: seeder corrections; `device_health_snapshots` + beat + backfill;
   `GET /dashboard/organization`; `connection_status` filter; anomaly bug.
   Tests for tenant isolation of the new endpoint and for section gating.
2. Frontend data layer: `types.ts`, `api.ts`, range state.
3. Dependencies: `@ant-design/plots`, `leaflet`, `react-leaflet@4`; chart
   wrappers; lazy chunking.
4. Header, KPI grid, Device health, Attention — the first viewport.
5. Map, Campaigns, Playback, Deployments.
6. Content, Top locations, Now playing, Live screens, Activity, Approvals,
   Schedule, Usage, Insights.
7. Drill-down: URL-param seeding on the eight destination pages.
8. Customise, responsive passes (320 → 2560), dark mode, accessibility
   (contrast measured, text summaries, keyboard), performance.
9. QA matrix (§95 of the brief) and the four remaining docs.
