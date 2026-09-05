# Full Frontend UI/UX Audit

Scope: the whole `frontend/src` tree (159 files, ~25.6k lines of TSX)
inspected on 2026-09-06 against
[ANTD_REFERENCE_ANALYSIS.md](ANTD_REFERENCE_ANALYSIS.md) and the
governance brief. Every number below was measured with the commands in
§9, not estimated. Screen-level findings are in
[UI_COMPONENT_MIGRATION_MATRIX.md](UI_COMPONENT_MIGRATION_MATRIX.md).

Context: an Ant Design migration already happened on 2026-08-30
(`docs/UI_UX_IMPLEMENTATION_STATUS.md`). This audit therefore does not
find "no design system"; it finds where the system is **incomplete,
duplicated or bypassed**. The starting position is good; the gaps are
real and listed without softening.

---

## 1. Repository structure

```
src/
  components/layout/   9 files   app shell (AppLayout, Sidebar, MainNavigation, AccountMenu,
                                 HeaderActions, GlobalSearch, TenantSwitcher, SidebarLogo, PlaceholderPage)
  components/ui/       9 files   shared primitives (PageHeader, DataTable, FilterBar, StatCard,
                                 StatusBadge, ToneTag, states, EntitlementGuard, tone.ts)
  config/              navigation.tsx (one nav config, permission-gated)
  lib/                 api client, auth, entitlements
  modules/<domain>/    22 domains, 120 files: pages, tabs, modals, drawers, widgets
  routes/              index.tsx (33 routes, all lazy), ProtectedRoute
  theme/               tokens.ts (buildTheme → ConfigProvider), ThemeProvider (light/dark)
  index.css            141 lines (cascade layers, sidebar scrollbar/guide lines, theme swap)
  modules/preview/preview.css   67 lines (TV renderer)
```

There is **no `src/design-system/`**. The pieces of a design system
exist but live in four places: `theme/tokens.ts`, `components/ui/`
(primitives + `tone.ts` palette), `modules/campaigns/schedule/palette.ts`
(campaign hues, status tones, severity tones) and
`modules/dashboard/charts/theme.ts` (chart palette, series colours). A
developer looking for "the design system" cannot find it, and three of
those files re-declare status colour mappings independently
(finding F-03).

## 2. Framework inventory

| Framework / library | Where | Verdict |
|---|---|---|
| **antd 6.6.2** | 135 of 149 TSX files import it; 1 `ConfigProvider` at the root (`ThemeProvider`), `App` wrapper present | Primary system — correct |
| `@ant-design/icons` 6.3 | only icon source; no emoji, no second icon set | Correct |
| `@ant-design/plots` 2.6 | dashboard charts inside `ChartFrame` | Keep; standardise container |
| **Tailwind 4** (via `@tailwindcss/vite`) | ~1,190 `className` usages; cascade-layer coexistence | Used far beyond "layout gaps": colour utilities, typography utilities and 94 `!important`-prefixed overrides against antd |
| Leaflet | dashboard map | Keep; documented custom surface |
| dayjs | via antd; used for civil-date maths in the schedule module only | Under-used: 21 `toLocaleString()` calls format dates ad hoc |

14 TSX files import no antd at all. Eleven are legitimate (pure
renderers, chart hosts, the auth illustration, the router shell); three
are not: `MainNavigation`-adjacent `Sidebar.tsx` (div flex column — fine),
`dashboard/widgets/TopLocationsWidget.tsx` (hand-built ranked list) and
`campaigns/SchedulesPage.tsx` (a re-export — fine).

## 3. Findings

Severity: **P0** breaks the "one component system" goal or accessibility;
**P1** visible inconsistency; **P2** hygiene.

| # | Sev | Finding | Evidence |
|---|---|---|---|
| F-01 | P0 | **Tables bypass the shared table.** Only 6 usages of `DataTable`; 20 files render `Table` directly with their own empty/loading/error handling and density. | `<Table` in 21 files vs `<DataTable` in 6 |
| F-02 | P0 | **Deprecated antd 6 size value everywhere.** `size="middle"` (v5) is used 61 times on Table/Space/Button; antd 6 standardised on `"medium"` for Table, Button, Card, Descriptions, Progress, Switch, Spin. `List` (deprecated in 6.6, removed in 7) is used in 13 files. | grep counts; console warning on every page that renders a List |
| F-03 | P0 | **Three status vocabularies.** `StatusBadge` (`STATUS_META`, 40 statuses → antd colour names → `toneStyle`), `schedule/palette.ts` (`statusTone`, `severityTone`), `dashboard/charts/theme.ts` (`STATUS_COLORS`) and `dashboard/widgets/shared.tsx` (`SeverityTag`) each map statuses to colours independently. The same "paused" or "critical" can differ by screen. | four files, no shared source |
| F-04 | P0 | **Colour is hard-coded outside tokens.** 57 Tailwind colour utilities (`text-slate-600`, `bg-emerald-50`, `text-red-600`…) in 16 files and ~30 hex literals outside `tokens.ts`/illustrations. Tailwind colours ignore the theme tokens and the dark algorithm; several were only made dark-safe with `dark:` variants by hand. | `states.tsx` (`text-slate-800 dark:text-slate-100`), `StatCard` (`!text-emerald-600`), `ContentPage`, `DesignerPage`, `renderers.tsx`, `SimulatorPage`… |
| F-05 | P1 | **`!important` by another name.** 94 `!`-prefixed Tailwind utilities (`!mb-0` ×30, `!me-0`/`!mr-0` ×19, `!mb-3`, `!mt-1`, `!text-xs`, `!p-0`, `!h-auto`…) override antd component styles. The brief forbids solving system-wide spacing with `!important`; the correct tools are antd props (`Typography` `style`, Tag `styles`, `Space` `size`) or component tokens. `index.css` carries 3 real `!important` (theme swap, justified). | grep counts |
| F-06 | P1 | **Breadcrumbs are inconsistent.** 27 pages use `PageHeader`; only 6 pass `breadcrumbs`. Every page sits under a module (Content › Media Library, Campaigns › Schedule…), so the "Module → Page → Entity" standard is met on 6 screens and silently absent on 21. | grep `breadcrumbs=` |
| F-07 | P1 | **Filter pattern used on 8 pages only.** `FilterBar` is a `Space wrap` + Reset; the "Search + primary filters + More filters + Reset" pattern is not defined, and list pages (Campaigns, Playlists, Layouts, Locations, Monitoring, Notifications, Releases, Ads…) build their own filter rows or have none. Search inputs are plain `Input` with a `SearchOutlined` prefix (6) rather than `Input.Search`. | grep |
| F-08 | P1 | **Date and number formatting is ad hoc.** 21 `toLocaleString()`/`toLocaleDateString()` calls with five different option sets; no shared formatter; no tenant-timezone handling outside the schedule module; no thousands-separator helper (Statistic does it, table cells do not). | grep |
| F-09 | P1 | **KPI cards implemented twice.** `components/ui/StatCard` (Card + Statistic) and `dashboard/widgets/KpiGrid.tsx` (`KpiCard`: Card + hand-set 28 px Typography + Tailwind). Two visual treatments for the same concept. | two files |
| F-10 | P1 | **Custom form field on the auth pages.** `auth/FloatingField.tsx` re-implements a floating-label input over `Form.Item`; the rest of the app uses standard vertical `Form` labels. No product justification. | `LoginPage`, `ForgotPasswordPage` |
| F-11 | P1 | **Raw HTML controls remain in four places.** `AccountMenu` trigger `<button>`, `LiveScreensWidget` tile `<button>`, `LocationMapWidget` popup `<button>`, `TVPreviewModal` `<button>`. Each hand-styles hover/focus (`.account-trigger` CSS). The schedule time grid's `<button>` blocks are a justified custom surface. | grep |
| F-12 | P1 | **Giant page components.** 8 files over 450 lines mix page, sections, forms and data access: `DesignerPage` 875, `TenantDetailPage` 666, `SimulatorPage` 625, `ScheduleWorkspace` 578, `CampaignDetailModal` 522, `IntegrationsSection` 517, `DevicesPage` 484, `ReleasesPage` 472. | wc |
| F-13 | P1 | **Confirmation flows are uneven.** 28 `Popconfirm`, 2 `modal.confirm`; no shared `ConfirmAction`, so wording ("Delete this…?" vs "Are you sure") and button types vary; `window.confirm` is not used (good). | grep |
| F-14 | P1 | **Notification channel unused.** `message` is used 27 times (correct for quick feedback); `notification` 0 times — background job results (deployments, exports, uploads) surface only via polling tables. | grep |
| F-15 | P2 | **Headings.** Only 5 `Typography.Title` usages outside `PageHeader`; section headings are otherwise Tailwind (`text-sm font-semibold uppercase`) or Card titles. No raw `<h1>–<h6>` (good). Hierarchy is undocumented. | grep |
| F-16 | P2 | **Layout utilities duplicate antd layout.** 5 Tailwind `grid-cols-*` grids and many `flex … gap-*` wrappers where `Row`/`Col`, `Flex` or `Space` exist. Acceptable as a phased-coexistence remnant; must not grow. | grep |
| F-17 | P2 | **Responsive columns are partial.** 47 `responsive:` column hints across 56 column sets; several tables (Monitoring roll-ups, Reports, Audit) still rely on horizontal scroll alone at 375 px. | grep |
| F-18 | P2 | **No lint gate.** No ESLint in the frontend: nothing stops a raw `<button>`, a `text-red-600`, or a new `List` from landing. Typecheck is the only gate. | package.json |
| F-19 | P2 | **Exception pages.** 403 is handled by `EntitlementGuard`/`PlatformGuard` (`Result`), but there is no 404 route and no 500 boundary page with the standard structure. | routes |
| F-20 | P2 | **Upload pattern.** `Upload` appears in 8 files with different `beforeUpload` validation and progress handling (media library, releases, branding, designer, playlist). No shared `UploadArea`. | grep |

### What is already right (keep)

* One `ConfigProvider` with centralised tokens; light/dark with measured
  AAA text contrast; antd `App` wrapper so `message`/`modal` carry theme.
* Responsive shell: `Sider` ≥ md, `Drawer` < md, collapsible rail,
  permission-filtered `Menu` from one navigation config, sticky logo and
  account bands.
* Route-level code splitting (33 lazy routes), vendor chunking.
* Shared `PageHeader`, `StatusBadge` (icon + text + colour), `EmptyState`
  (51 uses), `ErrorState` (12), `LoadingState` (33), `EntitlementGuard`.
* Forms: 42 `layout="vertical"`, 9 `inline` (filters); antd validation
  throughout; `Popconfirm` on destructive row actions.
* Drawers for entity detail (device, asset, campaign, plan, tenant);
  `Descriptions` (24) for read-only groups; `Steps` for approval.
* Zero page-body horizontal overflow at 320–1920 (hardening pass, 2026-09-05).

## 4. Component-level audit

### 4.1 Buttons
All buttons are antd `Button` except the four raw `<button>`s (F-11) and
the justified schedule/time-grid blocks. Variants used: primary, default,
text, link, danger. `Space.Compact` used once (schedule header). Missing
rule: exactly one primary per header — Dashboard header and Settings
sections currently show two primaries in places (verified in matrix).

### 4.2 Inputs, selects, pickers
antd throughout (`Input` 13 files, `Select` 9, `TreeSelect` 2,
`DatePicker`/`TimePicker` 1–2, `InputNumber` 2, `Switch`, `Checkbox`,
`Upload`). Custom: `FloatingField` (F-10). Comma-separated text inputs
for lists were removed with the schedule redesign; none remain.

### 4.3 Tables
See F-01/F-02/F-17. Alignment: 67 `align: "right"` (numbers) — good;
actions columns are right-aligned in most tables but not all (Audit,
Reports left-align). Density: `small` in 307 places (mostly Space/Button),
`middle` on tables. Row actions use text buttons — good.

### 4.4 Lists and cards
`List` 13 files (deprecated). Card grids: Content, Campaigns, Playlists,
Layouts, Releases use `Row`/`Col` + `Card`; 5 use Tailwind grids.
`Card` 14 files; nesting depth ≤ 2 (good).

### 4.5 Modals and drawers
Modals: focused forms (create playlist, folder, location, record payment,
schedule window, upload) — correct use. Drawers: entity detail/edit
(device, asset, campaign, plan, tenant create, filters, conflicts) —
correct. No multi-screen workflows in modals (good). Missing shared
`EntityDrawer`/`ConfirmAction` (F-13).

### 4.6 Navigation
`Menu` (sidebar) with route-derived open/selected keys; `Tabs` 12
screens; `Segmented` 7; `Breadcrumb` via `PageHeader` (F-06);
`Dropdown` account menu; `Pagination` via Table and media grid.

### 4.7 Feedback and states
`EmptyState` 51, `Empty` 4 raw, `ErrorState` 12, `Result` 9, `Skeleton`
6 raw, `LoadingState` 33, `Spin` 3, `Alert` 13 files, `message` 27,
`Popconfirm` 28. Consistent except F-13/F-14/F-19.

### 4.8 Charts
`ChartFrame` (Card + Skeleton + title/subtitle) wraps every plot; custom
`Donut`/`RankBar` SVG/Progress charts; palette in `charts/theme.ts`
(F-03 — colours must come from the design system).

### 4.9 Icons
`@ant-design/icons` only. Sizes follow text except a few `text-[13px]`
hand sizes in dashboard widgets.

### 4.10 Typography
One font stack via token. Page titles `Title level={3}` (24 px) in
`PageHeader`; Card titles 16 px; body 14; captions `text-xs` (Tailwind)
in ~90 places rather than `Typography.Text` with `fontSizeSM` — a
consistency and dark-mode risk when combined with colour utilities.

## 5. Design-token audit

| Area | State | Gap |
|---|---|---|
| Colour seeds and text aliases | centralised, AAA-measured | tone palette and chart palette live outside `tokens.ts` |
| Typography | `fontFamily`, `fontSize` 14 | no documented role scale; captions via Tailwind |
| Spacing | antd defaults | 94 `!m*` overrides; ad-hoc `mt-1`/`mb-3` in pages |
| Radius | 8/4/12 + pill | fine |
| Shadows | antd defaults, Card shadow tuned | fine |
| Control heights | 32 | fine; `size="middle"` residue |
| Breakpoints | antd | fine |
| Motion | antd; theme-swap suppression | `prefers-reduced-motion` not applied to custom animations (`SyncOutlined spin`, map, time-grid) |

## 6. Responsive audit (summary)

Measured at 320/375/768/1024/1280/1440/1920 during the hardening cycle
and re-checked for the schedule workspace: no page-body overflow. Gaps:
tables that only scroll (F-17), the Screen Designer (documented
exception: scales, does not restructure), TV preview modal below 768
(letterboxed 16:9 — acceptable), Settings inline forms at 320 (wrap but
labels truncate). Full per-screen state in the migration matrix; rules
in [RESPONSIVE_COMPONENT_RULES.md](RESPONSIVE_COMPONENT_RULES.md).

## 7. Accessibility audit (summary)

Systemic: antd focus management, roving tabindex, form wiring, 7:1 text
in both themes, status icon + text, named icon buttons (automated scan:
0 unnamed app buttons). Gaps: no automated a11y lint/axe; the four raw
buttons carry hand-written focus styles; custom animations ignore
reduced motion; heading order inside some drawers skips levels; live
regions only on the device bulk bar and the schedule range label. Rules
in [ACCESSIBILITY_GUIDELINES.md](ACCESSIBILITY_GUIDELINES.md).

## 8. Duplicate component audit

| Concept | Implementations | Decision |
|---|---|---|
| Status pill | `StatusBadge`, `ToneTag`, `SeverityTag` (dashboard), `statusTone` (schedule) | One `status` vocabulary module → `StatusBadge` (domain + status) and `ToneTag` (raw tone). Severity and schedule tones become entries in the vocabulary. |
| KPI card | `StatCard`, dashboard `KpiCard` | One `KpiCard` (Card + Statistic + trend + context); dashboard grid consumes it |
| Chart status colours | `charts/theme.ts` `STATUS_COLORS` | Derived from design-system status tokens |
| Campaign hue palette | `schedule/palette.ts` | Move to `design-system/tokens/palette.ts` (categorical palette shared with chart `SERIES_COLORS`) |
| Filter row | `FilterBar` + 10 ad-hoc rows | One `FilterBar` pattern with `SearchBar`, primary filters, `More filters` drawer, Reset |
| Empty text | `EmptyState` + 4 raw `Empty` | `EmptyState` only |
| Date formatting | 21 inline calls | `format.ts` |
| Confirmation | 28 Popconfirm + 2 modal.confirm with varied copy | `ConfirmAction` with standard wording |

## 9. How the numbers were obtained

```bash
# antd usage frequency
grep -rhoE '^import \{[^}]+\} from "antd"' src | tr ',' '\n' | sort | uniq -c
# raw HTML controls
grep -rn '<button\b\|<input\b\|<select\b\|<table\b' src --include=*.tsx
# important-style overrides
grep -rho 'className="[^"]*![a-z0-9:-]*' src --include=*.tsx | wc -l
# colour utilities
grep -rhoE '\b(text|bg|border)-(slate|red|emerald|amber|blue|…)(-[0-9]+)?\b' src | wc -l
# deprecated sizes / components
grep -rho 'size="middle"' src | wc -l ; grep -rl '\bList\b' src | xargs grep -l 'from "antd"'
# tables outside DataTable
grep -rl '<Table[<\s]' src --include=*.tsx
# date formatting
grep -rho 'toLocale[A-Za-z]*String([^)]*)' src | sort | uniq -c
```

## 10. Conclusion

The application runs on Ant Design with a central theme; the
standardisation work is about **closing the system**: one folder that is
the design system, one status vocabulary, one table, one filter pattern,
one formatter, breadcrumbs everywhere, the deprecated-API sweep, the
removal of colour and `!important` utilities, and a lint gate so it
stays closed. The phased plan is in
[UI_UX_IMPLEMENTATION_STATUS.md](UI_UX_IMPLEMENTATION_STATUS.md).
