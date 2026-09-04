# Organization Administrator Dashboard — QA

What was verified, how, and what is still open. Everything below was run
against the demo tenant "Reliance Retail Digital Experience" on
2026-09-05: the production build served by `vite preview` (port 4173)
and the Vite dev server (port 5173), both proxied to the local API.

## Method

- **Contrast** is measured, not eyeballed: a script walks every element
  in `<main>` that has its own text node, composites the computed text
  colour over the computed background chain (Tailwind emits oklab, antd
  emits rgba), and reports the WCAG ratio. Anything under 7:1 is listed.
- **Runtime errors** are captured with `unhandledrejection` / `error`
  listeners installed in the page, then the dashboard is refreshed, the
  range changed and a 30 s poll cycle waited out.
- **Roles** are exercised by signing in as seeded demo users and reading
  which sections the page renders.
- **API failure** is simulated in-page by rejecting the dashboard request
  (`window.fetch` override) — once with data on screen, once for a range
  that has never loaded.

## Results

### Accessibility

| Check | Result |
|---|---|
| Text contrast, light mode (415 text nodes) | All ≥ 7:1 (AAA) except white-on-primary button text at 6.7:1 (AA). Solid primary surfaces keep the brand blue by an earlier decision; recorded as AA. |
| Text contrast, dark mode (415 text nodes) | All ≥ 7.2:1 (AAA). |
| Status / severity tags, both modes | All ≥ 7.5:1 via `toneStyle` (antd's filled tags measured 2.9–5.6:1 in dark and were replaced). |
| Status-coloured numbers (KPIs, statistics) | `STATUS_TEXT[mode]`: darker shades in light, lighter tints in dark, all ≥ 7:1. Chart fills are unchanged and only used for marks. |
| Placeholder text (filters) | Raised from antd's 1.8:1 to 7.5:1 (`colorTextPlaceholder`). |
| Map attribution | Leaflet's default 3.6:1 restyled to ≥ 8:1 on a solid strip. |
| Keyboard | Tab order runs header (presets, refresh, customise) → widgets; every stop shows the 2.4 px focus-visible outline; drill-down links and tag filters are reachable. |
| Colour-only signals | None: every status carries icon + text, every chart a summary sentence, the donut a legend list, the map a city list. |

### Rendering

| Check | Result |
|---|---|
| Production build, all 13 sections | Render with data; 0 console errors on load, on manual refresh, across a 30 s poll and on range change. |
| Development server | Same — after the three dev-only fixes documented in the architecture doc (ReactDOM race, source-text sniffing, StrictMode double-render). |
| Light / dark toggle at runtime | Switches fully; note that measuring during the 300 ms transition, or in a background tab where transitions are paused, reports mid-transition colours — measure after reload. |
| Widths | 375 px: single column, no horizontal scroll. 740 px (pane): two columns. 2560 px: container capped at 1440 px and centred, `scrollWidth` = viewport, no overflow. |

### Roles and tenancy

| User (seeded) | Sections rendered | Notes |
|---|---|---|
| Organization Administrator (Arjun) | 13 | Full page. |
| Viewer (Amit, 17 `*.view` permissions) | 13 | Read-only role sees everything read-only; no errors. |
| Report Viewer (Neha: `campaigns.view`, `devices.view`, `reports.*`) | 2 — Campaigns, Playback | KPIs and device health need `monitoring.view` (see the data map). No errors, no empty placeholders for omitted sections. |
| Platform Administrator switched into the tenant | 13 | Superuser sees every section; data is scoped to the selected tenant. |

Tenant scoping is enforced server-side (`tests/test_dashboard_api.py::test_dashboard_is_tenant_scoped`).

### Degradation

| Scenario | Behaviour |
|---|---|
| Poll or manual refresh fails, data on screen | Last good data stays; a warning banner "The dashboard could not be refreshed — showing the last successful data from 14 s ago" with Retry appears above the grid; the next poll clears it. |
| First load (or a new range) fails | Full-page error state "Unable to load the dashboard" with Retry; nothing blank. |
| A widget throws | Its `WidgetBoundary` shows an inline error with Retry; the rest of the page is unaffected. |
| Map tiles unreachable | The city list beside the map takes over (`tileerror`). |

### Data correctness (spot checks)

- KPI "Online 106 / 85.5 %" matches the donut legend and the summary
  sentence; offline count equals the rows returned by
  `/devices?connection_status=offline`.
- Playback totals equal the sum of the daily series for the range.
- Deployment stacked column shows only days with activity; the tag counts
  match the list below it.
- Backend: `pytest backend/tests/test_dashboard_api.py` — 5 passed
  (reconciliation, tenant scoping, range validation, connection filter,
  hourly snapshot idempotence).

## Open items

- Primary button text is AA (6.7:1), not AAA — changing it means a darker
  brand primary across the app.
- The dashboard's map needs internet access for OpenStreetMap tiles.
- A failed first load replaces the whole page, including the range
  controls; Retry is the only action until the API answers.
