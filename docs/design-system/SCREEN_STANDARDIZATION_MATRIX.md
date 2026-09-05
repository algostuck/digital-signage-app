# Screen Standardization Matrix

Tracking table for the standardisation programme. "AntD coverage" is the
share of visible UI rendered by Ant Design or a design-system
composition; "Custom" lists justified custom surfaces (J) or remaining
bespoke markup (B). Updated at the end of each phase; the baseline is
2026-09-06 before Phase A.

| Screen | AntD coverage | Custom components | Migration required | Accessibility | Responsive | Status |
|---|---|---|---|---|---|---|
| App shell | 95 % | B: account trigger button + CSS | raw button → Button/Dropdown; header overrides → tokens | names ok; focus hand-written | done | Baseline |
| Login / Forgot password | 85 % | B: FloatingField | standard Form fields | ok | done | Baseline |
| Dashboard | 85 % | J: map; B: KpiCard, SeverityTag, TopLocations list, tile buttons | KpiCard, StatusBadge, EntityList, ChartFrame | tiles unnamed roles | done | Baseline |
| Media Library | 90 % | B: Tailwind grid, colour utilities | breadcrumb, FilterBar v2, Row/Col grid, UploadArea | ok | done | Baseline |
| Asset detail | 95 % | — | Listy | ok | done | Baseline |
| Design Studio hub | 90 % | — | breadcrumb, DataTable, FilterBar | ok | done | Baseline |
| Screen Designer | 60 % | J: canvas | split file; chrome on tokens | numeric keyboard path | scales (exception) | Baseline |
| Playlists | 95 % | — | breadcrumb, FilterBar | ok | done | Baseline |
| Playlist editor | 85 % | — | Listy, sections | reorder keyboard path | done | Baseline |
| Campaigns | 90 % | — | breadcrumb, FilterBar, DataTable | ok | done | Baseline |
| Campaign detail | 90 % | — | EntityDrawer sections, DataTable | heading order | done | Baseline |
| Approvals | 90 % | — | breadcrumb, Listy | ok | done | Baseline |
| Schedule | 90 % | J: time grid | Listy, vocabulary, remove overrides | done | done | Baseline |
| Publishing | 95 % | — | breadcrumb, FilterBar, SectionCard | ok | done | Baseline |
| Devices (+tabs) | 85 % | B: bulk bar styling | DataTable ×4, FilterBar v2, split files | ok | done | Baseline |
| Device detail | 95 % | — | EntityDrawer, Listy | ok | done | Baseline |
| Monitoring | 85 % | — | breadcrumb, DataTable, FilterBar, responsive columns | ok | tables scroll only | Baseline |
| Player Updates | 90 % | — | breadcrumb, Listy, UploadArea | ok | done | Baseline |
| Player Simulator | 80 % | J: player | split, Listy log | ok | done | Baseline |
| Locations | 95 % | — | tag input via Select tags | ok | done | Baseline |
| Reports & Analytics | 85 % | — | report template, DataTable, KpiCard | ok | tables scroll only | Baseline |
| Advertising | 90 % | — | breadcrumb, DataTable, FilterBar | ok | done | Baseline |
| Users & Roles | 90 % | — | breadcrumb, DataTable ×3, FilterBar | ok | done | Baseline |
| Notifications | 90 % | — | breadcrumb, Listy, StatusBadge severity | ok | done | Baseline |
| Audit Logs | 90 % | — | DataTable, alignment | ok | responsive columns | Baseline |
| Security Center | 90 % | — | breadcrumb, DataTable | ok | done | Baseline |
| Developer | 95 % | — | breadcrumb | ok | done | Baseline |
| Settings (4 groups, 10 sections) | 85 % | — | SectionCard everywhere, DataTable ×3, Listy ×3, UploadArea | ok | inline forms wrap | Baseline |
| Platform Overview | 95 % | — | EmptyState, breadcrumb | ok | done | Baseline |
| Tenants | 100 % | — | — (reference) | ok | done | Reference |
| Tenant detail | 95 % | — | split into sections | ok | done | Baseline |
| Plans / Plan requests / Invoices | 100 % | — | EntityDrawer / ConfirmAction / KpiCard swaps | ok | done | Baseline |
| TV Preview | 70 % | J: renderer | chrome buttons → Button | ok | done | Baseline |
| Exception pages | 50 % | — | ExceptionPage 403/404/500 | ok | — | Baseline |

Status values: Baseline → In progress → Standardised (visual QA +
responsive QA + accessibility QA recorded in
`UI_UX_IMPLEMENTATION_STATUS.md`).
