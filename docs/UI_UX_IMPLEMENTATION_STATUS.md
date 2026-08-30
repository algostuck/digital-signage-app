# UI/UX Modernization — Implementation Status

Living status of the antd migration. Companions: [UI_UX_AUDIT.md](UI_UX_AUDIT.md),
[UI_UX_DESIGN_SYSTEM.md](UI_UX_DESIGN_SYSTEM.md),
[UI_UX_SCREEN_REDESIGN_MATRIX.md](UI_UX_SCREEN_REDESIGN_MATRIX.md),
[UI_UX_API_CHANGES.md](UI_UX_API_CHANGES.md).

Decisions confirmed by the user (2026-08-30): phased Tailwind coexistence
(remove at the end), dark mode deferred to a later pass, placeholder brand
color #1D4ED8, maximize antd built-ins, near-zero custom CSS.

## Foundation

| Item | Status |
|---|---|
| antd v5 + @ant-design/icons installed | Done |
| Design tokens (`src/theme/tokens.ts` → ConfigProvider) | Done |
| Cascade-layer coexistence (`@layer theme, base, antd, components, utilities` + StyleProvider layer) | Done — antd beats preflight, utilities beat antd, zero !important |
| App shell: dark Sider + grouped icon nav + collapse + mobile Drawer + header (search/tenant/user) | Done |
| Route-level code splitting (React.lazy + Skeleton fallback per route) | Done — closes audit P0 #3 |
| Shared primitives: PageHeader, StatCard, FilterBar, DataTable, EmptyState/ErrorState/LoadingState, StatusBadge (icon+text+color), EntitlementGuard | Done |
| Entitlement hook (`useEntitlements` → GET /entitlements, additive endpoint) | Done — closes audit P0 #5; endpoint documented in UI_UX_API_CHANGES.md, tested |
| Focus-trapped dialogs (antd Modal/Drawer replacing legacy Modal) | Done wherever migrated — closes audit P0 #4 |

## Screens

| Screen | Status |
|---|---|
| Login | Done (antd Form, validation, brand mark) |
| Dashboard | Done (StatCard KPIs, 15/9 golden split, List panels, Error/Loading states) |
| Content Library | Done (folder Menu card, FilterBar, media card grid, Pagination, Modal folder form) |
| Devices (+enrollment key, saved views, bulk bar) | Done (antd Table + rowSelection, tabs, aria-live bulk bar) |
| Locations | Done (antd Tree master-detail, Descriptions, golden 9/15 split) |
| Campaigns | Done (card grid + tabs + Form modal) |
| Playlists | Done (card grid + Form modal) |
| Schedules | Done (Segmented week/month, Tag-based calendar cells, schedules Table, full antd Form modal with Date/TimePicker + CheckableTag days + conflict Alert) |
| Deployments | Done (Progress cards, Popconfirm cancel, per-device grid) |
| Approvals | Done (Tabs, Timeline history, decision Modal) |
| Design (Layouts hub) | Done (tabs + card grid + Form modal) |
| Screen Designer | Done (chrome antd-ified: Breadcrumb header, toolbar Buttons, Card panels, antd Select/InputNumber/Checkbox properties; canvas drag/resize logic preserved as documented custom surface) |
| Audit Logs | Done (Table, FilterBar, code Tags) |
| Releases (Update Center) | Done (card list, ring Progress, Upload.Dragger modal, Popconfirm rollback) |
| Monitoring (health/incidents/intelligence shell) | Done (StatCard row, rollup Tables, threshold inline Form, Segmented incident filter) |
| Notifications | Done (Tabs, severity Tags, unread Badge) |
| Reports / Analytics / Exports tabs | Done (Tables, DatePicker filters preserving string state, Progress uptime bars) |
| Users & Roles (+tabs) | Done (server-paginated Table, role editor → Drawer, Popconfirm on destructive actions) |
| Settings (all 10 organization sections) | Done — new IA: General / Plan & usage / Integrations / Branding & SSO tab groups, sections as consistent Cards |
| Device/Content/Location modals + Groups/Walls/Bundles tabs | Done (device + asset details → Drawers with Descriptions/Timeline, Upload.Dragger, TreeSelect move picker, editable-tag TagEditor) |
| Campaign detail modal, Decisioning/Experiments, design tabs, Playlist editor, Intelligence tab | Done (campaign detail → Drawer with Steps approval progression; PlaylistEditorPage got PageHeader + breadcrumbs) |
| Developer / Ads / Security / Platform (+PlanEditor) | Done (reveal-once secrets as copyable code in warning Alerts; platform tenant manager → Drawer; PlanEditor → Form grid) |

## Post-migration cleanups already done

- Legacy `components/ui/Modal.tsx`, `FormField.tsx`, `Spinner.tsx` deleted (zero imports remained).
- `ScrollRestoration` added to the shell (route changes reset scroll).
- antd is **v6.6.2** (not v5): all v5-era deprecated props swept
  (`Drawer width→size`, `Space direction→orientation`,
  `Tag bordered={false}→variant="filled"`, `Statistic valueStyle→styles.content`,
  `Spin tip→description`, `destroyOnClose→destroyOnHidden`,
  `Divider orientation→titlePlacement`, `AutoComplete onDropdownVisibleChange→onOpenChange`).
- Verified in-browser: desktop shell, collapsed rail, mobile drawer nav +
  single-column dashboard at 375px, Settings tab IA, Users, Reports, Ads,
  Security. Production build green; typecheck green.

## Hardening passes (done 2026-08-30)

1. **Responsive sweep** — automated horizontal-overflow measurement of
   all 20 routes at 320/375/768/1024/1440/1920px. Five 320px overflows
   found and fixed: Schedules calendar now scrolls inside its own
   container (min-w 560px grid), Monitoring health tables got scroll-x,
   Audit action filter became shrinkable (`w-full max-w-80`), Ads slot
   input narrowed, Security age-policy form wraps. Final state: **zero
   page-body overflow at every tested width on every route**.
2. **Large screens** — Content is width-capped at 1600px and centered ≥xl
   (brief §56); verified at 1920px across representative routes.
3. **Accessible names** — automated scan of every visible button across
   all 20 routes: zero app-authored unnamed controls (only antd-internal
   input-clear/pagination arrows remain, which antd names via parent
   elements per its own ARIA pattern).
4. **Performance** — `manualChunks` splits react / antd / icons / query
   vendors into immutable cacheable chunks; app-code deploys no longer
   invalidate the ~451kB-gzip antd chunk. Route chunks unchanged.

## Remaining / future

- antd v7 heads-up: v6 deprecates the `List` component (used in a
  handful of screens) — migrate when the v7 upgrade is planned, not before.
- Tailwind end-state review (only width/flex utilities remain, per the
  phased-coexistence decision — removal optional).
- Deeper manual screen-reader walkthroughs and contrast audits remain
  worthwhile before any formal WCAG conformance claim.
