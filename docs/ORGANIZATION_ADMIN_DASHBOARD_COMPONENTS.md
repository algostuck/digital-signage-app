# Organization Administrator Dashboard — Components

All under `frontend/src/modules/dashboard/`. Every widget takes the
section it renders plus `loading`, `error`, `onRetry`, and renders through
`ChartFrame`. A widget receiving `undefined` for its section renders
nothing — that is the "not permitted" signal from the server.

## Shell

| Component | Props | Notes |
|---|---|---|
| `DashboardPage` | — | Range state, the single query, layout order → grid |
| `widgets/DashboardHeader` | `range`, `setPreset`, `setCustom`, `generatedAt`, `onRefresh`, `refreshing`, `layout` | Greeting from `SessionUser.full_name`; org name from `/auth/memberships`; `Segmented` presets + `RangePicker` for custom; refresh shows "Updated 42s ago"; Customise `Drawer` with `Switch` + move up/down + Reset |
| `customise.ts` → `useDashboardLayout(userId)` | — | `order`, `isVisible`, `toggle`, `move`, `reset`, `isDefault`; persisted per user in `localStorage` |

## Charts (`charts/`)

| Component | Props | Reuse |
|---|---|---|
| `ChartFrame` | `title`, `extra`, `summary`, `loading`, `error`, `onRetry`, `empty`, `emptyTitle/Description/Action`, `minHeight` | Any card-shaped widget anywhere in the app |
| `Donut` | `slices[{key,label,value,color}]`, `centre`, `centreLabel`, `onSelect`, `height` | Any status mix; the legend list is the accessible twin and both drill |
| `TrendLine` | `series[{key,label,color,points[{x,y}]}]`, `height`, `xLabel`, `yLabel` | Any time series |
| `StackedColumn` | same shape as `TrendLine` | Outcomes per period |
| `RankBar` | `rows[{key,label,sublabel,value,display,color,onClick}]`, `max`, `ariaLabel` | Any top-N list |
| `ChartHost` | `children` (a plot element), `height` | Wraps every plot in its own React root; see the architecture doc |
| `theme.ts` | `STATUS_COLORS`, `SERIES_COLORS`, `STATUS_TEXT[mode]`, `useChartTheme()`, `statusLabel()` | Palette for any future chart; `STATUS_TEXT` for status-coloured text |

## Widgets (`widgets/`)

| Widget | Section | antd used | Drill-down |
|---|---|---|---|
| `KpiGrid` | `kpis` | `Card`, `Typography` | six filtered routes |
| `DeviceHealthWidget` | `device_health` | `Donut`, `TrendLine` | `/devices?connection_status=…` |
| `AttentionWidget` | `attention` | `SeverityTag` (`ToneTag`), `Button` | each row's `href` |
| `LocationMapWidget` | `geo` | `Select`, `Tag`, `Popup` + Leaflet | city → anchors → `/locations?id=` |
| `CampaignWidget` | `campaigns` | status strip, `DataTable`, `Progress` | `/campaigns?status=…` |
| `PlaybackWidget` | `playback` + `kpis.playback` | `Statistic`, `TrendLine`, `RankBar`, `EntitlementGuard` | `/reports`, `/content?type=` |
| `DeploymentWidget` | `deployments` | `StatusBadge`, `StackedColumn`, `Progress`, `Tag` | `/deployments?status=…` |
| `ContentWidget` | `content` | `StatusBadge`, `Donut`, `Avatar` | `/content?type=`, `?status=` |
| `TopLocationsWidget` | `locations_top` | `RankBar` | `/locations?id=` |
| `NowPlayingWidget` | `now_playing` | `Avatar`, `Tag`, `StatusBadge` | `/devices?q=` |
| `LiveScreensWidget` | `now_playing[0..3]` | `TVScreen` + `DeviceTVPreview` from the preview module | opens the TV preview |
| `ActivityWidget` | `activity` | `Typography` | entity route map |
| `ApprovalsWidget` | `approvals` | `Button` | `/approvals?state=pending` |
| `ScheduleTodayWidget` | `schedule_today` | `Timeline`, `Tag` | `/schedules` |
| `UsageWidget` | `usage` | `Progress`, `StatusBadge` | `/settings` |
| `InsightsWidget` | `insights` | `Button` | `/devices?tab=intelligence` |
| `widgets/shared.tsx` | — | `ViewAll`, `SeverityTag`, `When` (relative + exact on hover), `humanizeAction`, `ENTITY_ROUTES`, `dayLabel`, `hourLabel` |

## Added to the shared UI kit (`components/ui/`)

| Component | Props | Notes |
|---|---|---|
| `tone.ts` → `toneStyle(tone, mode)` | `Tone` = success / warning / error / high / processing / default | Tinted pill colours measured ≥7:1 in both themes; replaces antd's `variant="filled"` tags, which fall to 2.9–5.6:1 in dark mode |
| `ToneTag` | `tone` + antd `Tag` props (minus `color`/`variant`) | The tag to use wherever a status pill is needed |
| `StatusBadge` | unchanged API | Now painted with `toneStyle`, so every status badge in the app clears AAA |

## Reused from the app

`PageHeader` is intentionally *not* used — the dashboard header carries a
greeting, range and refresh that the generic header has no slot for.
Everything else is shared: `StatusBadge`, `DataTable`, `EmptyState` /
`ErrorState`, `EntitlementGuard`, `useAuth().hasPermission`, `timeAgo`,
the preview module's `TVScreen` / `usePlayback` / `useDevicePreviewSource`
/ `DeviceTVPreview`, `BRAND` and the golden container.

## Conventions

- No `any`: `types.ts` mirrors the server contract field for field.
- No new global CSS. Leaflet's stylesheet is imported by the map widget;
  chart styling is inline through G2's spec.
- Colour is never the only signal: every status has icon + text
  (`StatusBadge`, `SeverityTag`), every chart a summary sentence, the
  donut a legend list, the map a city list.
- Every list has a "View all"; every KPI, slice, row and marker leads
  somewhere with its filter applied.
