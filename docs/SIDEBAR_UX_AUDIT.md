# Sidebar & Application Shell — UX Audit

Date: 2026-08-30. Scope: the global application shell only
(`AppLayout`, sidebar, primary navigation, account surface). Business
pages, routing, APIs, and RBAC semantics are explicitly out of scope.

## 1. Current structure

`frontend/src/components/layout/AppLayout.tsx` — a single ~250-line file
holding the entire shell: nav data, menu construction, active-key logic,
brand mark, header, and content wrapper.

```
Layout
├── Sider (dark, width 240, collapsible)   ← desktop
│   ├── Brand (h-14)
│   └── Menu (theme dark, mode inline)
│       └── flat `type: "group"` sections
└── Layout
    ├── Header (hamburger, GlobalSearch, TenantSwitcher, account Dropdown)
    └── Content (p-4/6, inner max-w-1600 wrapper)
```

Mobile (`<md`) swaps the Sider for an antd `Drawer` holding the same
brand + menu.

## 2. Problems

| # | Problem | Severity |
|---|---|---|
| 1 | **Sidebar is not viewport-height-pinned.** The Sider stretches to document height inside `min-h-screen`; on a long page the brand scrolls out of view and there is nowhere to pin a footer. | P0 |
| 2 | **No account/plan surface in the sidebar.** The account dropdown lives in the top-right header; there is no persistent identity/subscription context. | P0 |
| 3 | **Sections are non-collapsible `type: "group"` headings**, not submenus. Every module is permanently expanded, so the menu is 20 items long with no way to collapse noise. | P0 |
| 4 | **Navigation is not permission-aware.** Every item renders for every user; only `/platform` is gated (on `is_superuser`). A Viewer sees Player Updates, Security and Developer, all of which return 403 pages. | P0 |
| 5 | **No "MAIN NAVIGATION" section framing**; the menu starts abruptly under the brand. | P2 |
| 6 | **Nav definition is embedded in the layout component** (`NAV_GROUPS` + `buildMenuItems` + `selectedKeyFor` all in `AppLayout.tsx`), so nav data, filtering and rendering are entangled. | P1 |
| 7 | **Collapsed rail flattens groups** as a workaround for group labels not fitting 80px — real submenus would give popup flyouts instead. | P1 |
| 8 | No open-state persistence concept (there are no submenus to persist). | P1 |

Working well and worth preserving: antd `Layout`/`Sider`/`Menu`/`Drawer`
are already the foundation; active-key matching already derives from
`useLocation()` (longest-prefix match, so `/design/:id` correctly selects
`/design`); the collapse toggle and mobile drawer already exist; the dark
`#0F172A` sider with a `#1D4ED8` selected state is already themed through
`ConfigProvider` tokens.

## 3. Existing routes (23) and their real server-side gates

Verified against `backend/app/api/v1/*` — the nav filter uses exactly
these, so a visible item is always a reachable page.

| Route | Required permission (server-verified) |
|---|---|
| `/dashboard` | `monitoring.view` (never hidden — it is the index redirect target; degrades to an ErrorState) |
| `/content` | `content.view` |
| `/design`, `/design/:layoutId` | `layouts.view` |
| `/playlists`, `/playlists/:id` | `playlists.view` |
| `/campaigns` | `campaigns.view` |
| `/approvals` | any of `campaigns.approve`, `layouts.manage`, `settings.manage` (`approvals._can_view_inbox`) |
| `/schedules` | `schedules.view` |
| `/deployments` | `deployments.view` |
| `/devices` | `devices.view` |
| `/locations` | `locations.view` |
| `/monitoring` | `monitoring.view` |
| `/releases` | `releases.manage` (page already renders a 403 `Result` without it) |
| `/reports` | `reports.view` |
| `/ads` | `ads.view` |
| `/users` | `users.view` |
| `/notifications` | `notifications.view` |
| `/audit` | `audit.view` |
| `/security` | `settings.manage` |
| `/developer` | `api_keys.manage` (page already renders a 403 `Result`) |
| `/settings` | `organization.view` |
| `/platform` | `is_superuser` |

Effect on the seeded **Viewer** role (`_ALL_VIEW` only): Player Updates,
Security, Developer, Approvals and Platform disappear from the menu
instead of leading to 403 pages.

## 4. Route-to-navigation mapping

The requested IA references child pages that do not exist as routes in
this codebase — they are **tabs inside existing pages**. Per the brief's
own instruction to map existing routes rather than invent functionality:

- "Templates" and "Widgets" are tabs inside `/design`, not routes.
- "Device Groups" is a tab inside `/devices` (with Video Walls and Edge Bundles).
- "Analytics" is a tab inside `/reports`.
- "Roles & Permissions" is a tab inside `/users`.
- "Subscription" and "System Settings" are tabs inside `/settings`.

Deep-linking those tabs would require changing page-level routing, which
this iteration excludes. The parent route is the nav target.

Resulting structure:

```
Dashboard                          /dashboard
MAIN NAVIGATION
  Content            ▼
    Media Library                  /content
    Design Studio                  /design
    Playlists                      /playlists
  Campaigns          ▼
    Campaigns                      /campaigns
    Approvals                      /approvals
    Schedule                       /schedules
    Publishing                     /deployments
  Devices            ▼
    All Devices                    /devices
    Monitoring                     /monitoring
    Player Updates                 /releases
  Locations                        /locations
  Reports            ▼
    Reports & Analytics            /reports
    Advertising                    /ads
  Administration     ▼
    Users & Roles                  /users
    Notifications                  /notifications
    Audit Logs                     /audit
    Security                       /security
    Developer                      /developer
  Settings                         /settings
  Platform Console                 /platform   (superuser)
```

`Locations`, `Settings` and `Platform Console` are single destinations, so
they are direct menu items rather than one-child submenus (the brief's own
rule for Dashboard in §8).

## 5. Recommended structure

```
Sider (260px, height 100vh, position sticky, top 0)
└── flex column, h-full
    ├── SidebarLogo         flex-shrink: 0     ← never scrolls
    ├── MainNavigation      flex: 1; overflow-y: auto; min-height: 0
    │   ├── "MAIN NAVIGATION" label
    │   └── antd Menu (mode inline, dark, submenus)
    └── AccountMenu         flex-shrink: 0     ← never scrolls
        └── Dropdown(Avatar + name + real plan name + chevron)
```

- **One authoritative nav definition** in `src/config/navigation.tsx`
  (`NavNode[]` with `path`, `permission`, `superuserOnly`, `children`),
  consumed by a single builder that filters on RBAC and emits antd
  `MenuProps["items"]`. A submenu whose children are all filtered out is
  dropped automatically.
- **Open state**: derived from the pathname on mount (so refresh and deep
  links restore correctly), unioned with the user's own toggles on
  navigation, so sections never snap shut while working.
- **Plan name** comes from the existing `useEntitlements()` hook
  (`GET /entitlements`) — real data, never hard-coded.
- **Collapsed rail** keeps real submenus, which antd renders as popup
  flyouts, replacing the current flattening workaround.

## 6. Responsive behavior

| Width | Behavior |
|---|---|
| `<768px` (`xs`/`sm`) | Sider hidden; hamburger in the header opens an antd `Drawer` containing the identical sidebar shell (logo, scrollable nav, account footer). |
| `768–991px` (`md`) | Sider present, **collapsed by default** to the 80px icon rail so tablets keep working width; submenus open as popups. |
| `≥992px` (`lg`+) | Full 260px sider, expanded by default, user-toggleable. |

Only the navigation column scrolls at every size; the logo and account
areas stay pinned.

## 7. Delivered (2026-08-30)

Implemented as `src/config/navigation.tsx` (the one authoritative nav
definition) plus `components/layout/{Sidebar,SidebarLogo,MainNavigation,
AccountMenu,HeaderActions}.tsx`.

- **Full-height sticky sider** (260px, `height:100vh; position:sticky`),
  logo and account bands `flex-shrink:0`, only the nav band scrolls —
  verified by scrolling the nav 642px while both bands stayed pinned.
- **Collapsible submenus** with route-derived `openKeys` unioned with the
  user's own toggles; deep links and refreshes restore the open section.
- **RBAC-filtered** against the real server gates in §3; empty submenus
  drop out entirely.
- **Light + dark themes.** `ThemeProvider` owns the mode (localStorage,
  falling back to `prefers-color-scheme`), feeds antd's
  `defaultAlgorithm`/`darkAlgorithm`, and the sider/menu follow with
  `theme={mode}`. Transitions are suppressed for the ~200ms swap so text
  never cross-fades through its own background.
- **Header**: global search (kept, restyled as a filled large input that
  flexes to 360px), tenant switcher, notification bell with a live unread
  `Badge`, and the theme toggle.

### Documented deviations

1. **Collapsed rail flattens to destinations.** antd 6 does not mount the
   popup portal for inline-collapsed submenus in this setup (verified:
   `aria-expanded="true"` with no popup node in the document, while
   Dropdown portals work normally). Rather than ship a rail whose groups
   cannot be opened, the 80px rail lists every permitted destination with
   its own icon — one click to anywhere, which is what §14's "do not
   destroy navigation usability" actually requires.
2. **Sub-page tabs are not nav entries.** Templates/Widgets, Device
   Groups, Roles, Subscription etc. are tabs inside their parent route;
   deep-linking them would require page-level routing changes that this
   iteration excludes.

## 8. Accessibility

antd `Menu` supplies the ARIA roles, roving tabindex and arrow-key
behavior, so no custom keyboard handling is added. On top of that: the
nav region is labelled (`aria-label="Main navigation"`), the account
trigger is a real `<button>` with `aria-haspopup`/`aria-expanded`, the
collapse toggle keeps a state-accurate `aria-label`, and selected state
is conveyed by a filled pill plus a heavier font weight — not by colour
alone.

**Measured contrast** (canvas-composited, real computed colours, both
themes, on `/campaigns`): every shell and content surface sampled —
sidebar section label, menu item, submenu title, selected row, logo
subtitle, account plan, page title, page description, active/inactive
tabs, link buttons, card text — scores **AAA (≥7:1)** in light *and*
dark. Reaching that required raising three token families above antd's
defaults: `colorTextDescription` (what `Typography type="secondary"`
actually resolves to), `colorLink` (blue-800 on light, blue-300 on dark —
the brand blue is only used for solid surfaces), and the Tabs item
colours.

**On "golden ratio compliance":** there is no such standard — WCAG is a
standard, the golden ratio is a proportion heuristic. It is applied here
deliberately but selectively: 40px menu rows against the 64px logo and
account bands is 1:1.6, and the dashboard's primary/secondary split is
`Col span={15}/{9}` (62.5/37.5). Spacing otherwise follows an 8pt scale
and type a 12/14/15/24px scale, because legibility beats forcing a ratio.
