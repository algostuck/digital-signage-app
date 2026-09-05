# UI/UX Implementation Status — enterprise design-system programme

Living record of the phased standardisation (2026-09-06). The August
migration record (`docs/UI_UX_IMPLEMENTATION_STATUS.md`) is the starting
point; this file tracks the governance programme defined by
[FULL_UI_UX_AUDIT.md](FULL_UI_UX_AUDIT.md).

## Phases

| Phase | Scope | Status | Commit |
|---|---|---|---|
| **A — Global theme + tokens** | `src/design-system/` (theme, tokens, components, patterns, utilities); brand / tone / categorical palette / status vocabulary / scale tokens; `buildTheme`; `@/design-system` barrel; formatter, feedback and reduced-motion utilities | Done | `f7b267b` |
| **B — Application shell** | shell on tokens (antd account trigger, no utility overrides in header/sidebar), derived breadcrumbs via `BreadcrumbProvider`, `PageContainer`, `ExceptionPage` 403/404/500 + router error element, `ResponsiveActions` | Done | `d5508f3` |
| **C — Common components** | `DataTable` v2, `FilterBar` v2 + `SearchBar`, `KpiCard`, `StatusBadge` on the vocabulary, `SectionCard`, `EntityDrawer`, `EntityList` (Listy), `ConfirmAction`, `UploadArea`, `ChartFrame`; deprecated `List` (13 files) and `size="middle"` swept; one status vocabulary (schedule palette, chart colours, severity tags) | Done | `bf9d8df`, `82269b8` |
| **D — Forms** | standard antd fields on the auth screens (`FloatingField` removed), global `ConfigProvider form` defaults (scroll to first error, actionable messages), settings sections on `SectionCard`, time-zone / locale selects | Done | `6256836` |
| **E — Tables / lists** | 33 raw tables → `DataTable`; `PageContainer` on 17 pages; `SearchBar` everywhere; Search · filters · Reset on Campaigns, Publishing, Playlists, Layouts, Notifications; one primary per header | Done | `ce3593f`, `0abecad`, `bf77717` |
| **F — Dashboards / reports** | dashboard on `KpiCard` / `PageHeader` / `EntityList`, raw buttons removed from tiles, map list, preview queue and chart rows; reports overview on `SectionCard`; proof-of-play summary strip from real rows; shared date formatting | Done | `6020b78` |
| **G — Complex experiences** | tenant detail split into four sections, Designer panels extracted, detail/editor drawers on `EntityDrawer` with vocabulary pills | Done (Simulator split open) | `fc0d53e` |
| **H — Accessibility + responsive hardening** | lint gate (`npm run lint`: ESLint + jsx-a11y + design-system rules), token-driven CSS utilities, every `!` override converted, reduced-motion status icons, keyboard path for time-grid slots, phone / tablet / 1920 QA | Done | `b8039a6`, `81ef750` |

## Governance metrics (measured after Phase H)

| Metric | Before (audit) | After |
|---|---|---|
| Raw HTML controls outside justified surfaces | 6 files | 0 |
| `!`-prefixed utility overrides | 94 | 0 |
| Tailwind colour utilities | 57 | 3 (all in justified renderer / canvas files) |
| Deprecated antd `List` imports | 13 files | 0 |
| Deprecated `size="middle"` | 61 | 0 |
| Raw `Table` outside `DataTable` | 33 | 0 |
| Pages with breadcrumbs | 6 / 27 | every page under a module (derived) |
| Pages on the filter pattern | 8 | 14 |
| Status vocabularies | 4 | 1 (`tokens/status.ts`) |
| Date formatting call sites | 21 ad hoc | `format.ts` (schedule and dashboard migrated; remaining `toLocale*` calls flagged for follow-up) |
| ESLint | none | 0 errors, 27 warnings (React-Compiler-era hook rules, advisory) |
| Typecheck / production build | green | green |

## QA record

| Width | Routes checked | Result |
|---|---|---|
| 375 (mobile preset) | dashboard, devices, campaigns, settings, reports, users | no page-body overflow; drawer navigation; KPIs 2-up; search visible above the Filters drawer; tables reduced to identity + status + actions |
| 768 (tablet) | dashboard, schedule, devices, settings | rail sidebar (80 px); KPIs 3-up; week grid with day panel; no overflow |
| 1280 (pane default) | every route touched during the phases | verified per phase (screenshots in session) |
| 1920 | dashboard, schedule, devices | 6 KPIs per row; content container widened to `clamp(1024px, 88cqw, 1440px)`; no overflow |
| Dark theme | dashboard, schedule, content | tone palette pairs (900/100) measured on chips; text tokens unchanged (7:1) |

Accessibility: `jsx-a11y` recommended rules pass with the documented
exceptions (auto-focus in dialogs; mouse-first designer canvas and
playback surfaces); every chip / block / tile is a button with a full
name; time-grid cells are focusable with an Enter path; status icons stop
spinning under `prefers-reduced-motion`; `aria-live` on bulk-action bars.

## Definition of done checklist (brief §84)

| Item | State |
|---|---|
| Ant Design primary system | ✔ |
| Global theme/tokens centralised | ✔ `src/design-system/theme`, `tokens` |
| Typography standardised | ✔ heading roles 3/4/5, no arbitrary sizes (lint) |
| Colours standardised | ✔ tokens + `dsc-*` CSS utilities; lint blocks Tailwind colours |
| Spacing standardised | ✔ no `!` utilities (lint); `PageContainer` rhythm |
| Grid/layout standardised | ✔ `GRID` presets, `Row`/`Col` |
| Breadcrumbs standardised | ✔ derived from navigation |
| Sidebar/navigation standardised | ✔ |
| Buttons standardised | ✔ one primary per header; raw buttons gone |
| Forms standardised | ✔ vertical forms, global validation defaults |
| Date/time controls standardised | ✔ pickers + `format.ts` + shared time zones |
| Upload standardised | ✔ `UploadArea` (adoption in media library / releases pending) |
| Tables standardised | ✔ `DataTable` everywhere |
| Lists standardised | ✔ `EntityList` (Listy) |
| Cards standardised | ✔ `SectionCard`, `KpiCard`, `ChartFrame` |
| Status indicators standardised | ✔ one vocabulary |
| Modals / drawers standardised | ✔ `EntityDrawer`, `ConfirmAction` |
| Notifications standardised | ✔ `useFeedback` (toast / notify / confirm) |
| Dashboard / report patterns | ✔ |
| Filters standardised | ✔ `FilterBar` + `SearchBar` |
| Loading / empty / error states | ✔ + `ExceptionPage` |
| Responsive standardised | ✔ measured at 375 / 768 / 1280 / 1920 |
| WCAG 2.2 AA baseline | ✔ lint + manual checks; AAA text contrast retained |
| Golden ratio as heuristic only | ✔ (15/9 splits, sidebar rhythm) |
| No duplicate frameworks / random CSS / `!important` | ✔ (Tailwind kept for layout utilities only; 3 justified `!important` in `index.css`) |
| APIs and business logic intact | ✔ no backend change in this programme |
| Real data, tenant boundaries | ✔ |
| Shared components documented | ✔ `COMPONENT_CATALOGUE.md` |
| Developer rules | ✔ `DESIGN_SYSTEM_USAGE.md` + `npm run lint` |

## Open follow-ups

* Split `SimulatorPage` (625 lines) into registration / playback / log sections.
* Adopt `UploadArea` in the media library upload modal and the release
  package upload (both still on bare `Upload.Dragger`).
* Replace the remaining `toLocaleString()` calls outside the dashboard and
  schedule with `format.ts`.
* Address the 27 React-Compiler-era lint warnings (`set-state-in-effect`,
  `refs`) when the codebase adopts the compiler.
* Screen-reader walkthrough on Login, Dashboard, Devices, Campaigns,
  Schedule and Settings with a real assistive-technology setup.

## Log

* 2026-09-06 — Documentation study, audit and matrices written; Phases A–H
  implemented and committed; lint gate added; QA at 375 / 768 / 1280 /
  1920 recorded.
