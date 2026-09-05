# UI Component Migration Matrix — screen inventory

One row per screen (route or major surface), recorded before the
standardisation phases (2026-09-06). "Existing UI framework" is antd on
every row unless stated; the column records what *else* is present.
Priority: **P0** foundation blockers, **P1** high-usage business
patterns, **P2** refinement. Status is updated as phases land (see
[UI_UX_IMPLEMENTATION_STATUS.md](UI_UX_IMPLEMENTATION_STATUS.md)).

Legend for "Ant Design replacement": the design-system components named
are defined in [COMPONENT_CATALOGUE.md](COMPONENT_CATALOGUE.md).
Roles come from `docs/RBAC.md` (OA = Organization Admin, CM = Content
Manager, DM = Device Manager, AP = Approver, VW = Viewer, PA = Platform
Admin).

## Shell and authentication

| Screen | Route | Purpose | Role | Existing components | Existing UI framework | Current problems | Ant Design replacement | Design tokens | Responsive behaviour | Accessibility issues | Priority | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| App shell | `/*` | Sidebar, header, content container | all | `Layout`, `Sider`, `Header`, `Drawer`, `Menu`, `Dropdown`, `AutoComplete`, `Badge` | + Tailwind flex, `.sidebar-scroll` / `.account-trigger` CSS, raw `<button>` account trigger | Account trigger is a raw button with hand CSS; header uses `!flex !px-4` overrides | `AppShell` composition; account trigger → `Button type="text"` + `Dropdown`; header spacing via `Layout` tokens | `Layout.headerHeight` 55, `Menu` rhythm 34, `SIDEBAR_BG` | Sider ≥ md, rail on tablet, Drawer < md — done | Focus style hand-written on trigger | P0 | Planned (Phase B) |
| Login | `/login` | Sign in | anon | `Form`, `Input`, `Alert`, `Button`, `AuthShell` | + `FloatingField` custom label, hero SVG, Tailwind colours | Custom floating-label field; hex/Tailwind colours in `AuthShell` | Standard `Form` vertical, `size="large"`, `Input.Password`; `AuthShell` on tokens | `colorPrimary`, `colorBgLayout` | Two-column ≥ lg, single below — done | Autofocus, `role="alert"` error — ok | P1 | Planned (Phase D) |
| Forgot password | `/forgot-password` | Request + reset | anon | `Form`, `Result`, `Alert` | + `FloatingField` | as Login | as Login; `Result` for sent state (≤ 2 actions) | — | done | ok | P1 | Planned (Phase D) |

## Workspace

| Screen | Route | Purpose | Role | Existing components | Existing UI framework | Current problems | Ant Design replacement | Design tokens | Responsive behaviour | Accessibility issues | Priority | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Dashboard | `/dashboard` | Executive workbench: KPIs, attention, health, map, campaigns, playback, deployments, content, schedule, activity | OA, VW (widgets by permission) | `Row`/`Col`, `Card`, `Statistic`, `Progress`, `Timeline`, `Alert`, `Select`, `Tag`, plots, Leaflet | + Tailwind grids/flex, own `KpiCard`, `SeverityTag`, hand-built `TopLocationsWidget`, raw `<button>` tiles/map popups | Duplicate KPI card; own severity tags; hand list; two primary buttons in header | `KpiCard`, `StatusBadge`(severity), `EntityList` (Listy), `ChartFrame`, one primary (`Customise`) | status tones from vocabulary; chart palette from tokens | 1→2→4/5 KPIs, 15/9 split, scrollable header Segmented — done | live-screen tiles are raw buttons | P1 | Planned (Phase F) |

## Content

| Screen | Route | Purpose | Role | Existing components | Existing UI framework | Current problems | Ant Design replacement | Design tokens | Responsive behaviour | Accessibility issues | Priority | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Media Library | `/content` | Folders, assets, upload, collections | CM, OA | `PageHeader`, `FilterBar`, `Menu` (folders), `Card` grid, `Pagination`, `Modal`, `Upload` | + Tailwind grid (`grid-cols`), 4 colour utilities | No breadcrumb; media grid on Tailwind grid; card meta colours via utilities | `PageContainer` + breadcrumb, `FilterBar` v2 (`SearchBar`, type/status), `Row`/`Col` grid, `Image` with fallback, `UploadArea` | — | 2→3→4→6-up grid | card activation keyboard — ok | P1 | Planned (Phase E) |
| Asset detail | drawer | Versions, publish, archive | CM | `Drawer`, `Descriptions`, `List`, `Upload`, `Timeline` | + 1 colour utility | `List` deprecated | `EntityDrawer`, `Listy` | — | full-width drawer < md | ok | P1 | Planned (Phase C/E) |
| Upload | modal | Upload assets | CM | `Modal`, `Upload`, `Form` | — | Own validation copy | `UploadArea` (shared limits + errors) | — | ok | ok | P1 | Planned (Phase D) |

## Design

| Screen | Route | Purpose | Role | Existing components | Existing UI framework | Current problems | Ant Design replacement | Design tokens | Responsive behaviour | Accessibility issues | Priority | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Design Studio hub | `/design` | Layouts / Templates / Widgets / AI Studio tabs | CM | `PageHeader`, `Tabs`, `Card` grid, `Table` (AI), `Form` modal | + colour utility; `Table size="middle"` | No breadcrumb; AI table raw; per-tab filters differ | breadcrumb; `DataTable`; `FilterBar` per tab | — | card grid 1→2→3 | ok | P1 | Planned (Phase E) |
| Screen Designer | `/design/:layoutId` | Canvas composition | CM | `Breadcrumb`, `Button`, `Card`, `Select`, `InputNumber`, `Checkbox`, `Upload` | + custom canvas (justified), 5 colour utilities, 875-line file | Monolith; colour utilities on canvas chrome | Split into `DesignerToolbar`, `DesignerCanvas` (custom), `PropertiesPanel`, `ZoneList`; chrome on tokens; `Splitter` candidate | — | scales, does not restructure (documented) | canvas mouse-first; numeric fields are the keyboard path | P2 | Planned (Phase G) |

## Playlists

| Screen | Route | Purpose | Role | Existing components | Existing UI framework | Current problems | Ant Design replacement | Design tokens | Responsive behaviour | Accessibility issues | Priority | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Playlists | `/playlists` | List + create | CM | `PageHeader`, `Card` grid, `Modal` form | + 1 colour utility | No breadcrumb, no filter/search | breadcrumb; `FilterBar` (search, status) | — | 1→2→3 | ok | P1 | Planned (Phase E) |
| Playlist editor | `/playlists/:playlistId` | Items, order, durations, publish | CM | `PageHeader` + breadcrumb, `List`, `Upload`, `Form` | + Tailwind | `List` deprecated; 448 lines | `Listy` (draggable items), `SectionCard`, split sections | — | stacked < lg | reorder keyboard alternative (move up/down buttons) | P1 | Planned (Phase E) |

## Campaigns

| Screen | Route | Purpose | Role | Existing components | Existing UI framework | Current problems | Ant Design replacement | Design tokens | Responsive behaviour | Accessibility issues | Priority | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Campaigns | `/campaigns` | Card list, decisioning, experiments | CM, AP, OA | `PageHeader`, `Tabs`, `Card` grid, `Table` (decisioning/experiments), `Form` modal | + colour utility; `Table size="middle"` | No breadcrumb; status filter is a bare Select; two raw tables | breadcrumb; `FilterBar`; `DataTable` | status vocabulary | 1→2→3 | ok | P1 | Planned (Phase E) |
| Campaign detail | drawer | Targets, schedules, approval, publish, variants | CM, AP | `Drawer`, `Descriptions`, `Steps`, `Table`, `Form` | + Tailwind; 522 lines | Monolithic drawer; own targets table | `EntityDrawer` with tabbed sections (`Tabs`), `DataTable` | — | full-width < md | heading levels inside drawer | P1 | Planned (Phase G) |
| Approvals | `/approvals` | Pending / history, decide | AP | `PageHeader`, `Tabs`, `List`, `Timeline`, `Modal` | — | `List` deprecated; no breadcrumb | breadcrumb; `EntityList` (Listy) | — | ok | ok | P1 | Planned (Phase E) |
| Schedule | `/schedules` | Scheduling command centre | CM, OA | `PageHeader`, `Segmented`, `Calendar`, `Drawer`, `Popover`, `List`, `Progress`, custom time grid | + Tailwind (13 `!` overrides), `palette.ts` status/severity tones | `List` deprecated; local status vocabulary; overrides | `Listy`; vocabulary from design system; tone palette moved to tokens | campaign hues → categorical palette | month/week/day ≥ md, agenda < md — done | done (names, focus popovers) | P1 | Planned (Phase C) |
| Publishing | `/deployments` | Deployments, per-device status | CM, DM | `PageHeader`, `Card`, `Progress`, `Popconfirm`, `ToneTag` | + Tailwind | No breadcrumb; no filter; own progress card layout | breadcrumb; `FilterBar` (status, campaign); `SectionCard` | status vocabulary | ok | ok | P1 | Planned (Phase E) |

## Devices

| Screen | Route | Purpose | Role | Existing components | Existing UI framework | Current problems | Ant Design replacement | Design tokens | Responsive behaviour | Accessibility issues | Priority | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| All Devices | `/devices` | Fleet table, enrolment key, saved views, bulk actions, Groups/Walls/Bundles tabs | DM, OA | `PageHeader`, `FilterBar`, `Table` + `rowSelection`, `Tabs`, `Modal`, `Drawer` | + 2 colour utilities; 484 + 432 + 396 + 274-line files; `size="middle"` | Raw `Table` in all four tabs; bulk bar hand-styled | `DataTable` with `bulkActions`; `FilterBar` v2 (search, status, location TreeSelect, platform, more); split tabs into files | status vocabulary (device) | identity+status+actions < md, detail in drawer | bulk bar `aria-live` — ok | P0 | Planned (Phase E) |
| Device detail | drawer | Heartbeat, telemetry, events, screenshots, commands, TV preview | DM | `Drawer`, `Descriptions`, `Timeline`, `List`, `Tabs`, `Button` | + Tailwind (2 `!`), 379 lines | `List` deprecated | `EntityDrawer`, `Listy` | — | full-width < md | ok | P1 | Planned (Phase C) |
| Monitoring | `/monitoring` | Health roll-ups, incidents, intelligence | DM, OA | `PageHeader`, `StatCard`, `Table`, `Segmented`, `Form` | + Tailwind; raw tables `size="middle"` | No breadcrumb; raw tables; incidents filter is a Segmented only | breadcrumb; `DataTable`; `FilterBar` | status vocabulary | tables scroll at 375 → add responsive columns | ok | P1 | Planned (Phase E) |
| Player Updates | `/releases` | Releases, rollouts, upload package | DM | `PageHeader`, `Card` list, `Progress`, `Upload.Dragger`, `Popconfirm`, `List` | + Tailwind (2 `!`); 472 lines | `List` deprecated; no breadcrumb; own upload validation | breadcrumb; `Listy`; `UploadArea`; split rollout section | — | ok | ok | P1 | Planned (Phase E) |
| Player Simulator | `/simulator` | Browser player | DM | `PageHeader`, `Card`, `Form`, `Descriptions`, `ToneTag` | + Tailwind (4 colour utilities); 625 lines | Monolith; log panel hand-styled | `SectionCard`, `Listy` for logs; split registration / playback / log | — | stacked < lg | ok | P2 | Planned (Phase G) |

## Locations

| Screen | Route | Purpose | Role | Existing components | Existing UI framework | Current problems | Ant Design replacement | Design tokens | Responsive behaviour | Accessibility issues | Priority | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Locations | `/locations` | Tree master-detail, CRUD, move, tags | OA, DM | `PageHeader`, `Tree`, `Descriptions`, `Modal`, `TreeSelect`, `Tag` editor | + 1 colour utility | Top-level page without breadcrumb is correct (level 1); tag editor is bespoke input+tag | `TagInput` pattern via `Select mode="tags"` | — | 9/15 split ≥ lg, stacked below — done | tree arrow keys — ok | P2 | Planned (Phase E) |

## Reports

| Screen | Route | Purpose | Role | Existing components | Existing UI framework | Current problems | Ant Design replacement | Design tokens | Responsive behaviour | Accessibility issues | Priority | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Reports & Analytics | `/reports` | Proof of play, playback, uptime, performance, exports (tabs) | OA, VW (entitled) | `PageHeader`, `Tabs`, `Table`, `DatePicker`, `FilterBar`, `Progress`, `EntitlementGuard` | + raw tables `size="middle"` | No summary strip; tables raw; report structure varies per tab | Report template: `PageHeader` → `FilterBar` (range presets) → `KpiCard` strip → `ChartFrame` → `DataTable` → Export | — | tables need responsive columns | ok | P1 | Planned (Phase F) |
| Advertising | `/ads` | Slots, bookings | OA | `PageHeader`, `Table`, `Form` | + raw table | No breadcrumb; raw table | breadcrumb; `DataTable`; `FilterBar` | — | ok | ok | P2 | Planned (Phase E) |

## Administration

| Screen | Route | Purpose | Role | Existing components | Existing UI framework | Current problems | Ant Design replacement | Design tokens | Responsive behaviour | Accessibility issues | Priority | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Users & Roles | `/users` | Users / Roles / Members tabs | OA | `PageHeader`, `Tabs`, `Table` (server paginated), `Drawer` role editor, `Popconfirm` | + raw tables; 345 + 230 + 214 lines | No breadcrumb; raw tables | breadcrumb; `DataTable`; `FilterBar` (search, role, status) | status vocabulary (user) | ok | ok | P1 | Planned (Phase E) |
| Notifications | `/notifications` | Inbox + rules tab | OA | `PageHeader`, `Tabs`, `List`, `Badge`, `Form` | + Tailwind (3 `!`); `List` deprecated | `List` deprecated; severity tags local | breadcrumb; `Listy`; `StatusBadge`(severity) | — | ok | ok | P1 | Planned (Phase E) |
| Audit Logs | `/audit` | Searchable log table | OA | `PageHeader`, `FilterBar`, `Table`, `Input`, `Select` | + raw table | Raw table; actions column left | `DataTable`; alignment rules | — | responsive columns | ok | P1 | Planned (Phase E) |
| Security Center | `/security` | Credential lifecycle, policies, violations | OA | `PageHeader`, `StatCard`, `Table`, `Form` | + raw tables | No breadcrumb; raw tables | breadcrumb; `DataTable` | — | ok | ok | P2 | Planned (Phase E) |
| Developer | `/developer` | API keys, docs links | OA | `PageHeader`, `Card`, `Alert`, `Result` | + Tailwind (2 `!`) | No breadcrumb | breadcrumb | — | ok | ok | P2 | Planned (Phase E) |

## Settings

| Screen | Route | Purpose | Role | Existing components | Existing UI framework | Current problems | Ant Design replacement | Design tokens | Responsive behaviour | Accessibility issues | Priority | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Settings | `/settings` | General / Plan & usage / Integrations / Branding & SSO (10 sections) | OA | `PageHeader`, `Tabs`, `Card`, `Form`, `Progress`, `Table`, `List`, `Upload` | + Tailwind (9 `!`), raw tables (data sources, event bus, billing), `List` ×3; 517 + 413 + 323-line sections | Sections vary in header/actions layout; raw tables; deprecated List | `SectionCard` (title, description, actions) for every section; `DataTable`; `Listy`; `UploadArea` for branding | — | inline forms wrap at 320 | ok | P1 | Planned (Phase D/E) |

## Platform console

| Screen | Route | Purpose | Role | Existing components | Existing UI framework | Current problems | Ant Design replacement | Design tokens | Responsive behaviour | Accessibility issues | Priority | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Overview | `/platform` | Platform KPIs, recent tenants | PA | `PageHeader`, `StatCard`, `Card`, `Empty` | — | Raw `Empty`; no breadcrumb | `EmptyState`; breadcrumb | — | ok | ok | P2 | Planned (Phase E) |
| Tenants | `/platform/tenants` | Tenant table, create drawer | PA | `PageHeader`, `FilterBar`, `DataTable`, `Drawer` form | — | Reference implementation — already on the pattern | — | — | ok | ok | — | Reference |
| Tenant detail | `/platform/tenants/:tenantId` | Subscription, usage, users, actions | PA | `PageHeader` + breadcrumb, `DataTable`, `Descriptions`, `Tabs` | + Tailwind (2 `!`); 666 lines | Monolith | Split into sections (`SectionCard`); `EntityDrawer` for edits | — | ok | ok | P2 | Planned (Phase G) |
| Plans | `/platform/plans` | Plans + editor drawer | PA | `DataTable`, `FilterBar`, `Segmented`, `Drawer` | + Tailwind (2 `!` in PlanDrawer) | fine | `EntityDrawer` | — | ok | ok | P2 | Planned (Phase C) |
| Plan requests | `/platform/plan-requests` | Approve/reject requests | PA | `DataTable`, `FilterBar`, `Modal` | — | fine | `ConfirmAction` | — | ok | ok | P2 | Planned (Phase C) |
| Invoices | `/platform/invoices` | Invoices, record payment | PA | `DataTable`, `FilterBar`, `StatCard`, `Modal` | — | fine | `KpiCard` | — | ok | ok | P2 | Planned (Phase C) |

## Cross-cutting surfaces

| Surface | Where | Existing | Problems | Replacement | Priority | Status |
|---|---|---|---|---|---|---|
| TV Preview | modal from devices / campaigns | `Modal`, custom renderer, `ToneTag`, raw `<button>` | raw button; colour utilities in renderer chrome | renderer stays custom; chrome on `Button`/tokens | P2 | Planned (Phase G) |
| Exception pages | 403 (`EntitlementGuard`, `PlatformGuard`), none for 404/500 | `Result` | missing 404 route, missing error boundary page | `ExceptionPage` (`Result` 403/404/500) + router error element | P1 | Planned (Phase C) |
| Global search | header | `AutoComplete` | fine | — | — | Reference |
| Tenant switcher | header | `Select` | fine | — | — | Reference |

## Totals

| Metric | Count |
|---|---|
| Screens / surfaces inventoried | 38 |
| Already on the reference pattern | 5 |
| Need breadcrumb | 21 |
| Need `DataTable` migration | 20 files |
| Need `Listy` migration | 13 files |
| Need `FilterBar` v2 | 14 screens |
| Justified custom surfaces | 4 (designer canvas, TV renderer, schedule time grid, map) |
