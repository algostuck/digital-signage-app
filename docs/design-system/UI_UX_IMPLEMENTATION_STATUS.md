# UI/UX Implementation Status — enterprise design-system programme

Living record of the phased standardisation (started 2026-09-06). The
earlier migration record (`docs/UI_UX_IMPLEMENTATION_STATUS.md`, August
2026) is the starting point; this file tracks the governance programme
defined by [FULL_UI_UX_AUDIT.md](FULL_UI_UX_AUDIT.md).

## Phases

| Phase | Scope | Status |
|---|---|---|
| **A — Global theme + tokens** | `src/design-system/` structure; tokens (brand, tone, palette, status vocabulary, typography, spacing); `buildTheme`; `@/design-system` barrel; formatter utilities; feedback helpers | Planned |
| **B — Application shell** | AppShell composition on tokens; account trigger → antd; header overrides removed; derived breadcrumbs; ExceptionPage 403/404/500 | Planned |
| **C — Common components** | PageContainer, SectionCard, DataTable v2, FilterBar v2 + SearchBar, KpiCard, StatusBadge (vocabulary), EntityDrawer, EntityList (Listy), ConfirmAction, UploadArea, ResponsiveActions, ChartFrame move; `List` → `Listy` sweep; `size="middle"` sweep | Planned |
| **D — Forms** | auth forms on standard fields; settings sections on SectionCard; form rules applied (grouping, validation copy, pickers) | Planned |
| **E — Tables / lists** | all 20 raw tables → DataTable; alignment + responsive columns; FilterBar v2 + breadcrumbs on every list page | Planned |
| **F — Dashboards / reports** | dashboard on KpiCard/StatusBadge/EntityList/ChartFrame; report template on Reports tabs | Planned |
| **G — Complex experiences** | Designer split, TV preview chrome, schedule cleanup, Simulator split, Tenant/Campaign detail sections | Planned |
| **H — Accessibility + responsive hardening** | lint gate (eslint + jsx-a11y + design-system rules), reduced motion, visual QA at 320–2560, a11y QA per screen, performance check | Planned |

## Definition of done checklist (brief §84)

| Item | State |
|---|---|
| Ant Design primary system | ✔ (baseline) |
| Global theme/tokens centralised | ✔ baseline; palette/status consolidation in Phase A |
| Typography standardised | Phase A/C |
| Colours standardised (no arbitrary colours) | Phase A + sweep |
| Spacing standardised (no `!` utilities) | Phase C + sweep |
| Grid/layout standardised | Phase C/E |
| Breadcrumbs standardised | Phase B |
| Sidebar/navigation standardised | ✔ baseline; trigger fix Phase B |
| Buttons standardised | Phase B/C |
| Forms standardised | Phase D |
| Date/time controls standardised | Phase A (formatter) + D |
| Upload standardised | Phase C/D |
| Tables standardised | Phase E |
| Lists standardised (Listy) | Phase C |
| Cards standardised | Phase C |
| Status indicators standardised | Phase A/C |
| Modals / drawers standardised | Phase C |
| Notifications standardised | Phase A (helpers) |
| Dashboard / report patterns | Phase F |
| Filters standardised | Phase C/E |
| Loading / empty / error states | ✔ baseline; ExceptionPage Phase B |
| Responsive standardised | Phase H |
| WCAG 2.2 AA baseline | Phase H |
| No duplicate frameworks / random CSS / `!important` | Phase C sweep + H lint |
| APIs and business logic intact | continuous (no backend change planned) |
| Real data, tenant boundaries | continuous |
| Visual / responsive / a11y QA | Phase H |
| Shared components documented | COMPONENT_CATALOGUE.md |
| Developer rules | DESIGN_SYSTEM_USAGE.md |

## Log

* 2026-09-06 — Documentation study (`ANTD_REFERENCE_ANALYSIS.md`), full
  audit, migration matrix, token/component/responsive/accessibility/usage
  documents written. No code changed yet.
