# Organization Administrator Dashboard — Architecture

Companion to [ORGANIZATION_ADMIN_DASHBOARD_AUDIT.md](ORGANIZATION_ADMIN_DASHBOARD_AUDIT.md),
which records why each decision below was forced.

## Shape

```
GET /dashboard/organization?from=&to=           one tenant-scoped payload
        │
        ▼
useOrganizationDashboard(range)                  one TanStack query, 30 s poll
        │
        ▼
DashboardPage ─ layout.order ─▶ widgets[key]     each widget: own states,
        │                                        renders nothing if its
        ▼                                        section was omitted
ChartFrame → Donut / TrendLine / StackedColumn / RankBar / Leaflet
```

There is exactly one request per range. Every widget reads a slice of the
same response; a range change refetches the whole payload with the
previous one kept on screen (`placeholderData`), so a filter never blanks
the page. The header bell keeps its own `/monitoring/summary` poll.

## Backend

`app/services/dashboard.py::build` composes the payload. Rules it follows:

- **It re-derives nothing.** Connection status comes from
  `devices.connection_status`; schedule windows from `scheduling`; limits
  from `entitlements`; usage from `tenant_admin`; the monitoring summary
  from `monitoring.summary`. The dashboard cannot disagree with the pages
  it links to, because it calls the same functions they do.
- **Every block is a GROUP BY on an indexed column** or a bounded scan
  (devices, locations — a few hundred rows). Measured on the largest demo
  tenant: 0.76 s cold for a 7-day range, 0.30 s warm for 31 days.
- **Sections are omitted, not emptied**, when the caller lacks the
  permission. `Access` is built from `user_permission_codes` (superusers
  see all) plus the tenant's enabled entitlements. The client treats
  `undefined` as "not permitted" and an empty array as real data.

| Section | Permission | Ranged |
|---|---|---|
| kpis, device_health, attention | monitoring.view | playback KPI only |
| geo, locations_top | monitoring.view + locations.view | no |
| campaigns | campaigns.view | plays only |
| playback | reports.view | yes |
| content | content.view | no |
| deployments | deployments.view | history only |
| activity | audit.view | no |
| approvals | campaigns.approve / layouts.manage / settings.manage | no |
| schedule_today | schedules.view | no |
| now_playing | monitoring.view + devices.view | no |
| usage | organization.view | no |
| insights | monitoring.view + `fleet_ai` entitlement | no |

Tenant scoping is the JWT's active-organization claim resolved in
`app/api/deps.py`; the route accepts no tenant id. The test
`test_dashboard_is_tenant_scoped` asserts one tenant's payload contains
only its own devices and locations.

### Device-health history

Connection status is never stored, so the trend needed a source. The beat
task `snapshot_device_health` (hourly) writes one
`device_health_snapshots` row per tenant — `online / warning / offline /
na` — idempotent within the hour. `_health_trend` returns hourly points
for ranges up to three days and the last capture per local day beyond
that. The demo seeder back-fills 30 days.

### Geography

Devices sit on leaf locations that usually carry no coordinates. `_geo`
walks each device's `path` upward to the nearest ancestor with
latitude/longitude — store, zone or city — and rolls counts up there,
tagging each anchor with its nearest `city` and `state` ancestor by
`location_types.code`. The client groups anchors by city for the country
view and expands a city into its anchors on click.

### Now playing

`reported` rows are the latest `playback_events` row per device inside the
last 30 minutes. If fewer than eight, `scheduled` rows are added for
online devices whose latest acknowledged deployment's campaign resolves
active *right now* through `scheduling.resolve_active_campaign` — the
same call the player manifest makes. The two sources are labelled and
never merged.

## Frontend

`frontend/src/modules/dashboard/`

| Path | Role |
|---|---|
| `types.ts` | The response contract, every section optional |
| `api.ts` | Query key, range presets, refresh, relative-age clock, formatters |
| `customise.ts` | Widget registry; hide/reorder/reset in `localStorage` per user |
| `charts/theme.ts` | Palette from the exported `BRAND`; G2 theme per mode |
| `charts/ChartFrame.tsx` | The one card every widget renders through: title, "View all", text summary, loading/empty/error |
| `charts/Donut.tsx` | Status mix; legend list is the accessible twin; segments and rows drill down |
| `charts/TrendLine.tsx` | Multi-series time line, interactive legend, crosshair tooltip |
| `charts/StackedColumn.tsx` | Outcomes per period (deployments) |
| `charts/RankBar.tsx` | Ranked rows with proportional bars — a list, not a chart |
| `widgets/*` | One file per section (see COMPONENTS doc) |
| `DashboardPage.tsx` | Composition: header, then `layout.order` into a 24-column grid |

### Grid

Spans on ≥ xl follow the codebase's golden split: 15/9 for device health /
attention, map / campaigns, playback / deployments, now playing /
activity; 12/12 for content / top locations, approvals / schedule, usage /
insights; 24 for the KPI strip and live screens. Below xl every widget
stacks to 24; the KPI strip becomes a horizontally scrolling snap row.
Everything sits inside the shell's centred container
(`clamp(1024px, 61.8cqw, 1440px)`).

### Charts

`@ant-design/plots` 2.6 (G2 5). It is lazy-loaded with the dashboard
route only — the shell bundle is untouched — and lands in a 1.7 MB (500 kB
gzip) chunk together with Leaflet. Every chart:

- takes its colours from `STATUS_COLORS` / `SERIES_COLORS`, never a
  library default;
- switches G2 theme with the app's light/dark mode and paints on a
  transparent view so it sits on the antd card;
- has `animate` off (the dashboard polls; animation on every poll is
  noise);
- carries a text summary in its `ChartFrame` and, for the donut, a legend
  list with the same numbers, so nothing is conveyed by colour alone.

### Map

`leaflet` 1.9 + `react-leaflet` 4 with OpenStreetMap tiles.
`CircleMarker`s (SVG) rather than image markers, so no asset pipeline and
colour, radius and popup all come from data. Dark mode inverts the tiles
with a CSS filter. A `tileerror` collapses the map and leaves the city
list, which is always rendered beside it as the text alternative. Tiles
need internet access; that is documented, not hidden.

### Refresh strategy

| What | Cadence |
|---|---|
| The dashboard payload | 30 s poll, plus the header's Refresh |
| Range change | immediate refetch, previous data kept on screen |
| Live-screen thumbnails | manifest re-fetched every 10 min (signed-URL TTL) |
| Header bell | unchanged, 60 s |

No per-widget requests, so the page never fans out. The only extra calls
are the three device details behind Live screens.

### Drill-down

Dashboard links carry query strings; the destination pages now seed their
filter state from `useSearchParams`:

| Link | Page reads |
|---|---|
| `/devices?connection_status=offline` | new server-side filter |
| `/devices?status=pending`, `?q=` | lifecycle status, search |
| `/campaigns?status=published` | new status control |
| `/deployments?status=failed` | new status control |
| `/content?type=video`, `?status=draft` | type; status (now sent) |
| `/locations?id=…` | selects the node |
| `/approvals?state=pending` | tab |
| `/notifications?severity=critical`, `?unread=1` | new controls |
| `/audit?entity_type=…&action=…` | filters |

### Customise

Hide/show and reorder live in `localStorage` under the user id, with
Reset. Server-side persistence was deliberately not added: the brief asks
for personalisation only where it fits cleanly, and a preference table
for a visibility list does not.
