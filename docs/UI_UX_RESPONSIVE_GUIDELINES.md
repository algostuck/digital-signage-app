# UI/UX Responsive Guidelines

How responsiveness is implemented in the modernized frontend. Companion to
[UI_UX_DESIGN_SYSTEM.md](UI_UX_DESIGN_SYSTEM.md).

## 1. Structural system

antd's 24-column grid (`Row`/`Col`) with antd's stock breakpoints is the
only layout grid:

| Token | Min width | Typical treatment |
|---|---|---|
| `xs` | <576 | Single column, drawer nav, collapsed table columns |
| `sm` | ≥576 | 2-col card grids |
| `md` | ≥768 | Persistent sidebar appears (shell switches from Drawer to Sider) |
| `lg` | ≥992 | Secondary table columns appear (`responsive: ["lg"]`) |
| `xl` | ≥1200 | Full KPI rows (4-up), golden-ratio splits activate, tertiary table columns (`responsive: ["xl"]`) |
| `xxl` | ≥1600 | No additional restructuring — content is width-capped by the shell padding |

The brief's QA widths (320/360/375/390/430/768/1024/1280/1440/1920/2560)
are the *test matrix*, not a second grid — every screen must be usable at
each of them.

## 2. Shell behavior (AppLayout)

- `≥md`: persistent dark `Sider` (240px) with a collapse toggle (80px
  icon rail; nav groups flatten in collapsed mode so group labels never
  overflow the rail).
- `<md`: the Sider is replaced by a `Drawer` opened from a hamburger
  button in the header; the global search hides (header space) and the
  user's name collapses to the avatar.
- Detection uses antd's `Grid.useBreakpoint()` — no hand-rolled
  matchMedia.

## 3. Standard responsive patterns

- **Tables**: never force every column onto mobile. Identity + status +
  actions stay always-visible; secondary columns get
  `responsive: ["lg"]`/`["xl"]`; every table wraps in
  `scroll={{ x: "max-content" }}` so nothing overflows the page body.
- **Card grids**: `xs={24} sm={12} lg={8}` (3-up) or `xs={12} sm={8}
  xl={6}` (4-up, denser media grids).
- **KPI rows**: `xs={24} sm={12} xl={6}` — 1 → 2 → 4 columns.
- **Filter rows**: `FilterBar` wraps via `Space wrap` — filters stack
  naturally on narrow screens.
- **Master-detail** (Locations, Dashboard panels): `Col xs={24} lg={9|15}`
  — side-by-side with the golden-ratio split on wide screens, stacked on
  narrow ones.
- **Forms in modals**: antd `Form layout="vertical"` — labels above
  inputs at every width (brief §10's mobile form rule, applied globally
  for consistency).
- **Action rows**: `Space wrap` so buttons wrap rather than clip.

## 4. Documented exception

The Screen Designer canvas (`/design/:layoutId`) is a fixed-aspect
composition surface scaled to fit its container; below a usable width it
scales down rather than restructuring. This is intentional — a
composition tool at 320px is not a design target (matrix row "Design /
Screen Designer").

## 5. Never do

- No fixed pixel page widths outside the canvas exception.
- No horizontal page-body scrolling — wide content scrolls inside its own
  container (`Table` scroll-x).
- No `window.innerWidth` listeners — use `Grid.useBreakpoint()` or CSS.
