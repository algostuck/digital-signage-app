# UI/UX Audit — Digital Signage Cloud Frontend

Date: 2026-08-30. Scope: `frontend/src/` as it stands after Phase 1–3
(63 module files, 23 authenticated routes + login). This is a structural
and systemic audit, not a page-by-page opinion piece — every finding below
is backed by a concrete file/line reference. Full per-screen breakdown
lives in [UI_UX_SCREEN_REDESIGN_MATRIX.md](UI_UX_SCREEN_REDESIGN_MATRIX.md).

## 1. Executive summary

The application is **functionally complete and well-organized** (permission
gating, API layer, routing, and business logic are all sound), but it has
**no design system whatsoever**. Every page hand-rolls its own buttons,
tables, cards, tabs, and empty states directly in Tailwind utility classes.
There are exactly **4 shared UI primitives** (`FormField`, `Modal`,
`Spinner`, `StatusBadge`) covering a fraction of the ~20 bespoke tables,
~15 bespoke forms, and dozens of hand-copied buttons/cards/tabs across 63
files.

The single most consequential fact for planning this initiative:

> **Ant Design (`antd`) is not installed anywhere in this codebase.**
> The frontend is React 18 + TypeScript + Vite + Tailwind CSS v4 +
> TanStack Query + react-router-dom v6, with zero UI kit, zero form
> library, zero design tokens (no `@theme` block, no `tailwind.config`),
> zero dark-mode groundwork, and no icon library in use anywhere.

Adopting Ant Design per the modernization brief is therefore a
**foundational dependency adoption**, not an incremental restyle. Section
5 lays out the recommended approach and the decisions that need a call
before any code changes begin.

## 2. Architecture audit

| Area | Current state | Assessment |
|---|---|---|
| Structure | `components/{layout,ui}`, `lib/` (api + auth), `routes/`, `modules/<18 domains>` — no `pages/`, `hooks/`, `stores/`, `styles/`, `utils/` | Reasonable for size; module-colocated state is fine to keep |
| Routing | Flat single-level table, 23 authenticated routes + `/login`, all under one `ProtectedRoute > AppLayout` | No nested routes/sub-outlets; no route-level permission guard (gating happens inside each page) |
| Code splitting | **None** — every route component is a static top-level import; no `React.lazy`/`Suspense` anywhere | P0: the Screen Designer, media library, and every other heavy module ship in the initial bundle |
| Auth/permission | `useAuth().hasPermission(code)` — flat string-array check, superuser bypass, no shared permission-code enum (~30 literals typed ad hoc across 44 files) | Sound at runtime; fragile to typos, no compile-time safety |
| Entitlement gating | **No `hasFeature`/entitlement helper exists in the frontend at all.** Only `IntegrationCatalogSection.tsx` renders a "plan locked" state (from a bespoke API field), everywhere else a plan-gated feature has no dedicated frontend affordance | P0/P1: the backend's entitlement engine (`entitlements.get_effective`) has no frontend counterpart — locked features risk rendering broken/empty rather than an "Upgrade to unlock" state |
| Shared components | `components/ui/{FormField,Modal,Spinner,StatusBadge}` — 4 total. No Button, Card, Table, Drawer, Tag, PageHeader, EmptyState, ErrorState, Tabs, or FilterBar | P0: root cause of nearly every consistency issue below |
| Tables | ~20 files with raw `<table>` markup, stylistically consistent by copy-paste convention (not abstraction); no client-side sort; filtering/pagination is server-driven via query params | P1: works, but any future table-wide change (density, a11y, sort) means editing 20 files |
| Forms | 100% manual — one `useState` per field, no `react-hook-form`/`zod`/`formik`; only text inputs go through `FormField`, every `<select>`/`<textarea>`/checkbox is hand-coded with visible class drift | P1 |
| Theme/tokens | `index.css` is 9 lines: `@import "tailwindcss"` + `body { @apply bg-slate-50 text-slate-900 antialiased }`. No `@theme` block, no `tailwind.config`, i.e. **zero brand-level design tokens** — the app runs on stock Tailwind defaults | P0: nothing to anchor a "design system" on today |
| Responsive design | 36 responsive-prefix occurrences across 26 of 71 files — mostly a single `md:grid-cols-2` on a stat grid. `AppLayout.tsx`'s sidebar is a fixed `w-60` with **no collapse/drawer logic at all** | P0: the shell itself does not adapt below desktop width |
| Status system | `StatusBadge` covers ~23 files/53 call sites, but **48 files** still hand-roll raw `bg-emerald-*/bg-red-*/bg-amber-*` pills in parallel with it (e.g. Approve/Reject row actions in `DevicesPage.tsx:439,446` use raw text colors, not the shared component) | P1: partial adoption is worse than no adoption — two sources of truth for the same visual language |
| Dark mode | **None.** Zero `dark:` classes, no theme context, `color-scheme: light` hardcoded | Confirmed absent, not "needs polish" |
| Iconography | **No icon library in use anywhere in the app** (not reported in any survey pass — confirmed zero icon imports) | The current UI is effectively icon-free; this is a blank slate, not a migration |
| Accessibility | `aria-`/`role`/`tabIndex` appear in 58/71 files but shallowly (1–3 per file, mostly a lone `aria-label` on a search/filter input); `Modal.tsx` has no focus trap, no initial focus, no focus-return on close; no landmark roles (`role="banner"`/`"complementary"`); no `axe`/`eslint-plugin-jsx-a11y` configured | P0 on focus management (affects every modal-driven workflow — ~10+ modules), P2 on the rest |

## 3. Severity-tagged systemic findings

**P0 — Critical, blocks a coherent design system**
1. No component library / design tokens exist — every page invents its own button, card, table, and tab markup independently (root cause, see §2).
2. App shell (`AppLayout.tsx`) has zero responsive behavior — content is squeezed, not restructured, below desktop width; there is no drawer navigation.
3. No code splitting — the entire 23-route app, including the canvas-heavy Screen Designer, ships as one JS bundle.
4. `Modal.tsx` lacks focus trapping, initial focus, and focus-return — a WCAG 2.2 keyboard-accessibility gap present in every one of the ~10+ modules that use it for create/edit/confirm flows.
5. No frontend concept of entitlement/plan-gating distinct from permission-gating — a Starter-plan tenant hitting a locked feature has no consistent "upgrade to unlock" UI.

**P1 — Major UX/consistency issues**
6. 20 independently-implemented tables with no shared sort/filter/bulk-action/empty/loading contract.
7. Forms are 100% manual state with no validation library; non-text controls (`select`, `textarea`, checkbox) have visibly drifted styling per call site.
8. `StatusBadge` is bypassed by raw color classes in 48 files — two parallel status-color systems coexist.
9. Responsive coverage is narrow and opportunistic (26/71 files, usually one breakpoint each) rather than systematic.

**P2 — Medium inconsistency**
10. ~30 permission-code string literals with no shared enum/constants file — a typo silently disables a feature instead of failing to compile.
11. `role="tablist"`/`"tab"` markup hand-rolled independently in at least 4 files instead of one shared `Tabs` primitive.
12. Empty-state markup (dashed border + centered text) duplicated near-verbatim across most list pages instead of an `EmptyState` component.

**P3 — Cosmetic/polish**
13. Accessibility attributes present but shallow — no landmark structure, no automated a11y tooling in CI.
14. No dark mode (acceptable to defer; flagged here only for completeness against the master-prompt checklist).

## 4. Screen inventory

18 module folders / 63 files map to 23 authenticated routes + `/login`.
See [UI_UX_SCREEN_REDESIGN_MATRIX.md](UI_UX_SCREEN_REDESIGN_MATRIX.md) for
the full per-screen table (current issues, target design, components,
responsive/accessibility notes, priority, status).

## 5. Recommended direction (needs your decision before any code changes)

**Adopt `antd` v5** as the primary component framework, per the brief.
Concretely:

- Use `ConfigProvider` + `theme.token` to define the design-token layer
  this app currently lacks (color, spacing, radius, shadow, control
  height) — this becomes the single source of truth §2's "zero tokens"
  problem is asking for.
- Introduce the reusable business components the brief names in §60
  (`PageHeader`, `StatCard`, `FilterBar`, `DataTable` wrapper over antd
  `Table`, `StatusBadge` rebuilt on antd `Tag`/`Badge`, `EmptyState`,
  `ErrorState`, `LoadingState`) as a thin layer *on top of* antd — not
  reimplementations of what antd already provides.
- Rebuild the app shell (sidebar/header) using antd `Layout` + `Menu`,
  with a Drawer-based nav for narrow viewports (currently absent).
- The **Screen Designer's canvas** (drag/resize/zoom composition surface)
  has no antd equivalent and is out of scope for component replacement —
  only its surrounding toolbar/property-panel chrome gets antd-ified.

**Three open questions genuinely need your call, not mine, before I touch
any screen:**

1. **Tailwind's fate.** Run antd and Tailwind side-by-side during a
   phased migration (each screen drops Tailwind as it's redesigned, both
   frameworks coexist until the last screen migrates), or cut over in one
   pass? Running both indefinitely reintroduces exactly the "two sources
   of truth" problem flagged in finding #8 — I'd recommend phased-with-a-
   deadline, but it's your codebase's tolerance for a mixed state during
   the transition.
2. **Icons.** The app currently has zero icons anywhere. I'd recommend
   `@ant-design/icons` as the sole icon set (ships with antd, zero new
   dependency) — flagging only because it's a visible, permanent choice.
3. **Dark mode.** Nothing exists to build on today. Given the master
   prompt lists it as conditional ("if supported, standardize it"), I
   recommend deferring it to a dedicated pass *after* the light-theme
   design system and screen migration are done, so token work isn't done
   twice. Say if you want it in scope now instead.

**Non-goals / preservation constraints** (per the brief's §70–77): all 23
route paths stay exactly as-is, all ~30 permission codes and their
call-site logic stay as-is, no API/query contract changes, no business
logic changes, no mock data introduced at any point.

## 6. Proposed execution order

Following the brief's own priority ladder (§75) and phase ordering (§84):

1. This audit + the screen matrix (done — this document)
2. **Design system proposal** — tokens, primitive component list, theme
   config (next; see `docs/UI_UX_DESIGN_SYSTEM.md` once drafted)
3. **Stop for your review** of 1–2 before any screen is touched
4. App shell + navigation (P0)
5. Login + Dashboard (P0)
6. Content, Devices, Locations, Campaigns, Playlists, Scheduling, Screen
   Designer chrome (P1)
7. Reports, Users/Roles, Notifications, Audit, Settings (P2)
8. Remaining screens — Ads, Security, Monitoring, Releases, Deployments,
   Approvals, Developer, Platform (P3)
9. Responsive + accessibility hardening pass across all screens
10. Performance check (bundle size, code-split verification) + visual QA
