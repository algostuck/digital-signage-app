# UI/UX Design System

Companion to [UI_UX_AUDIT.md](UI_UX_AUDIT.md) /
[UI_UX_SCREEN_REDESIGN_MATRIX.md](UI_UX_SCREEN_REDESIGN_MATRIX.md).
**Implemented** after user sign-off (2026-08-30): tokens live in
`frontend/src/theme/tokens.ts` (single `ConfigProvider` at the root),
shared primitives in `frontend/src/components/ui/`, and antd + Tailwind
coexist via cascade layers declared in `frontend/src/index.css`
(`@layer theme, base, antd, components, utilities` + antd `StyleProvider
layer`) — antd beats Tailwind's preflight reset, explicit Tailwind
utilities beat antd, zero `!important`. Implementation progress:
[UI_UX_IMPLEMENTATION_STATUS.md](UI_UX_IMPLEMENTATION_STATUS.md).

## 1. Design tokens

These map directly onto antd v5's `ConfigProvider` `theme.token` API, so
adopting them is a single config object, not scattered overrides.

### Color

| Token | Value | Rationale |
|---|---|---|
| `colorPrimary` | `#1D4ED8` (indigo-blue) | No existing brand color to preserve (app has none today) — a confident, enterprise-neutral blue. **Placeholder — swap in one line if you have an actual brand color.** |
| `colorSuccess` | `#059669` (emerald-600) | Matches the emerald already used for "online/approved/published" across the current `StatusBadge` |
| `colorWarning` | `#D97706` (amber-600) | Matches current "pending/warning" amber usage |
| `colorError` | `#DC2626` (red-600) | Matches current "offline/critical/rejected" red usage |
| `colorInfo` | `#0284C7` (sky-600) | New — currently unused as a distinct semantic, reserved for informational states |
| Neutral scale | Tailwind's `slate` 50–900 | Already the app's de facto neutral palette everywhere; reuse rather than replace |

Keeping success/warning/error anchored to the *existing* emerald/amber/red
families means the rebuilt `StatusBadge` will look familiar, not jarring —
users aren't relearning a new status language, just seeing it applied
consistently for the first time.

### Typography

| Role | Size | antd token |
|---|---|---|
| Caption | 12px | `fontSizeSM` |
| Body | 14px | `fontSize` (default) |
| Body large / Title | 16px | `fontSizeLG` |
| H3 / section title | 20px | `fontSizeXL` |
| H2 / page title | 24px | `fontSizeHeading3`→override |
| H1 / dashboard hero | 32px | `fontSizeHeading2`→override |
| Display (rare) | 48px | `fontSizeHeading1`→override |

Font family: system stack (`-apple-system, "Segoe UI", Roboto, ...`) —
matches current behavior exactly, no web-font dependency to add.

### Spacing

`4, 8, 12, 16, 20, 24, 32, 40, 48, 64` — this is antd's own default
4px-step scale (`sizeXXS` through `sizeXXL`), so no override is needed;
it's already what antd ships. Flagging it here only so it's an explicit,
documented decision rather than an implicit default.

### Radius & shadow

| Token | Value |
|---|---|
| `borderRadiusSM` | 4px (inputs, tags) |
| `borderRadius` | 8px (buttons, cards) |
| `borderRadiusLG` | 12px (modals, drawers) |
| pill | 9999px (status badges only) |
| `boxShadowSecondary` | antd default subtle 2-layer shadow — no custom heavier shadow introduced (brief §44: elevation explains hierarchy, not decoration) |

### Control sizing & breakpoints

- `controlHeight: 32` default, `40` for primary page-level actions.
- Structural grid: antd's 24-column `Row`/`Col` with antd's breakpoints
  (`xs<576, sm≥576, md≥768, lg≥992, xl≥1200, xxl≥1600`). Visual QA still
  hand-tests the brief's specific widths (320/360/375/390/430/768/1024/
  1280/1440/1920/2560) — the antd breakpoints are the structural system,
  the brief's widths are the QA checklist, not a second competing grid.

### Golden-ratio panel proportions (heuristic, not enforced everywhere)

| Layout | Split |
|---|---|
| Dashboard: fleet/campaign summary vs. recent activity | `Col span={15}` / `Col span={9}` (62.5/37.5) |
| List/detail screens (Playlists, Campaigns) | Table `span={15}` / Drawer or side panel `span={9}` on wide screens |
| Sidebar expanded/collapsed | 240px / 80px (≈3:1, intentionally not golden — collapsed width is set by icon+padding minimum, not proportion) |

Applied selectively per brief §7 — plenty of layouts stay a clean 50/50 or
24-col full-width where content doesn't call for asymmetry.

## 2. Reusable business components (thin wrappers over antd)

Per brief §60 — none of these reimplement what antd already does; each
adds only the app-specific defaults/business logic antd can't know about.

| Component | Wraps | What it standardizes |
|---|---|---|
| `PageHeader` | `Breadcrumb` + `Typography.Title` + `Space` (antd v5 deprecated its own `PageHeader`; this composes the replacement antd itself recommends) | Breadcrumb, title, description, primary/secondary action slot — replaces ~20 hand-copied `<h1 className="text-xl...">` blocks |
| `StatCard` | `Card` + `Statistic` | Label/value/trend/context layout (brief §15), used across Dashboard + module summary strips |
| `FilterBar` | `Space` + `Input.Search` + `Select` + `RangePicker` + reset `Button`, wraps to a `Drawer` below `md` | Standardizes the ~10 independently-built filter rows |
| `DataTable` | `Table` | Standard empty/loading/error states, default pagination, density prop (comfortable/default/compact per brief §20) — the single fix for finding #6 (20 bespoke tables) |
| `StatusBadge` (rebuilt) | `Tag` + `@ant-design/icons` | Icon + text + color per status (brief §26 color-independence rule) — single source of truth replacing the 48-file parallel pill pattern (finding #8) |
| `EmptyState` | `Empty` | Consistent icon/title/description/action — replaces the dashed-border paragraph duplicated across most list pages |
| `ErrorState` | `Result status="error"` | Actionable error messages (brief §47) — "Unable to load devices / [Retry]" pattern, never a raw stack trace |
| `LoadingState` | `Skeleton` | Layout-aware loading (brief §46) for page/data loads; the existing `Spinner` stays for small inline loads only |
| `ConfirmAction` | `Popconfirm` / `Modal.confirm` | One consistent destructive-action confirmation pattern |
| `EntityDrawer` | `Drawer` | Standard header/body/footer-actions layout for create/edit/detail flows — replaces the current single generic `Modal` for anything that isn't a small focused form or confirmation (brief §23) |
| `PermissionGuard` / `EntitlementGuard` | wraps existing `useAuth().hasPermission` + a **new** `hasFeature`/entitlement check | Closes finding #5 — gives locked-by-plan features a real "Upgrade to unlock" affordance instead of silently rendering nothing, consistent everywhere instead of only in the connectors page |
| `ResponsiveActions` | `Space` + `Dropdown` overflow | Desktop shows N buttons, mobile collapses extras into a "More" menu (brief §69) |

`Modal.tsx`'s current focus-management gap (finding #4) is fixed for free
by using antd's `Modal`/`Drawer`, which already implement focus trap,
initial focus, and focus-return — this is one of the concrete payoffs of
adopting a real component library rather than a symptom to patch
separately.

## 3. Theme wiring

- A single `ConfigProvider` at the app root (`main.tsx`) supplies
  `theme.token` from §1 — this becomes the one place brand colors,
  spacing, or radius are ever changed.
- `@ant-design/icons` as the sole icon set (ships with antd, zero new
  dependency) — the app currently has no icons anywhere, so this is
  pure addition, not a migration.
- Tailwind's role during the transition depends on the decision flagged
  in the audit (§6, Q1): recommended default is **phased coexistence** —
  Tailwind stays available for pure layout utility spacing only, is
  dropped screen-by-screen as each one migrates to antd `Row`/`Col`/
  `Space`, and is removed from `package.json` once the last screen
  migrates (tracked as a checklist item, not left open-ended).

## 4. What this proposal does not cover yet

- No packages are installed, no files are changed. This is the token +
  component inventory for you to sign off on before implementation
  starts (per your instruction to stop here).
- The Screen Designer's canvas interaction logic is explicitly out of
  scope for replacement (audit §5) — only its surrounding chrome adopts
  these primitives.
- Dark mode token values are deferred per audit §5 Q3 pending your call
  on whether it's in scope for this pass.
