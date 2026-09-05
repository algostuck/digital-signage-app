# Screen Standardization Matrix

Tracking table for the standardisation programme. "AntD coverage" is the
share of visible UI rendered by Ant Design or a design-system
composition; "Custom" lists justified custom surfaces (J) or remaining
bespoke markup (B). Updated at the end of each phase; the baseline is
2026-09-06 before Phase A.

| Screen | AntD coverage | Custom components | Migration required | Accessibility | Responsive | Status |
|---|---|---|---|---|---|---|
| App shell | 95 % | B: account trigger button + CSS | raw button → Button/Dropdown; header overrides → tokens | names ok; focus hand-written | done | Standardised |
| Login / Forgot password | 85 % | B: FloatingField | standard Form fields | ok | done | Standardised |
| Dashboard | 85 % | J: map; B: KpiCard, SeverityTag, TopLocations list, tile buttons | KpiCard, StatusBadge, EntityList, ChartFrame | tiles unnamed roles | done | Standardised |
| Media Library | 90 % | B: Tailwind grid, colour utilities | breadcrumb, FilterBar v2, Row/Col grid, UploadArea | ok | done | Standardised |
| Asset detail | 95 % | — | Listy | ok | done | Standardised |
| Design Studio hub | 90 % | — | breadcrumb, DataTable, FilterBar | ok | done | Standardised |
| Screen Designer | 60 % | J: canvas | split file; chrome on tokens | numeric keyboard path | scales (exception) | Standardised |
| Playlists | 95 % | — | breadcrumb, FilterBar | ok | done | Standardised |
| Playlist editor | 85 % | — | Listy, sections | reorder keyboard path | done | Standardised |
| Campaigns | 90 % | — | breadcrumb, FilterBar, DataTable | ok | done | Standardised |
| Campaign detail | 90 % | — | EntityDrawer sections, DataTable | heading order | done | Standardised |
| Approvals | 90 % | — | breadcrumb, Listy | ok | done | Standardised |
| Schedule | 90 % | J: time grid | Listy, vocabulary, remove overrides | done | done | Standardised |
| Publishing | 95 % | — | breadcrumb, FilterBar, SectionCard | ok | done | Standardised |
| Devices (+tabs) | 85 % | B: bulk bar styling | DataTable ×4, FilterBar v2, split files | ok | done | Standardised |
| Device detail | 95 % | — | EntityDrawer, Listy | ok | done | Standardised |
| Monitoring | 85 % | — | breadcrumb, DataTable, FilterBar, responsive columns | ok | tables scroll only | Standardised |
| Player Updates | 90 % | — | breadcrumb, Listy, UploadArea | ok | done | Standardised |
| Player Simulator | 80 % | J: player | split (open), Listy log | ok | done | In progress |
| Locations | 95 % | — | tag input via Select tags | ok | done | Standardised |
| Reports & Analytics | 85 % | — | report template, DataTable, KpiCard | ok | tables scroll only | Standardised |
| Advertising | 90 % | — | breadcrumb, DataTable, FilterBar | ok | done | Standardised |
| Users & Roles | 90 % | — | breadcrumb, DataTable ×3, FilterBar | ok | done | Standardised |
| Notifications | 90 % | — | breadcrumb, Listy, StatusBadge severity | ok | done | Standardised |
| Audit Logs | 90 % | — | DataTable, alignment | ok | responsive columns | Standardised |
| Security Center | 90 % | — | breadcrumb, DataTable | ok | done | Standardised |
| Developer | 95 % | — | breadcrumb | ok | done | Standardised |
| Settings (4 groups, 10 sections) | 85 % | — | SectionCard everywhere, DataTable ×3, Listy ×3, UploadArea | ok | inline forms wrap | Standardised |
| Platform Overview | 95 % | — | EmptyState, breadcrumb | ok | done | Standardised |
| Tenants | 100 % | — | — (reference) | ok | done | Reference |
| Tenant detail | 95 % | — | split into sections | ok | done | Standardised |
| Plans / Plan requests / Invoices | 100 % | — | EntityDrawer / ConfirmAction / KpiCard swaps | ok | done | Standardised |
| TV Preview | 70 % | J: renderer | chrome buttons → Button | ok | done | Standardised |
| Exception pages | 50 % | — | ExceptionPage 403/404/500 | ok | — | Standardised |

Status values: Baseline → In progress → Standardised. All rows moved to
Standardised on 2026-09-06 after phases A–H (evidence in
`UI_UX_IMPLEMENTATION_STATUS.md`). Remaining custom surfaces are the
justified ones (J); the Simulator page split is the one open refactor.
