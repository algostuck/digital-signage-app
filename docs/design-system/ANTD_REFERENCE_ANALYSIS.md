# Ant Design Reference Analysis

Study of the Ant Design documentation set supplied for the enterprise
UI/UX governance programme (2026-09-06). Every design-spec page (42) and
every component page relevant to this product (about 60 of 75) was read
against the installed library, **antd 6.6.2** with `@ant-design/icons`
6.3. Where the website describes a newer API than the installed one, the
installed type definitions win. Pages not read in full (Rate, Slider,
Mentions, ColorPicker, Carousel, QRCode, Watermark) cover components this
product has no use for; they are listed in §4 as "not adopted".

This document is the reference the rest of `docs/design-system/` cites.
It records what Ant Design recommends, then what Digital Signage Cloud
adopts from it. Adoption decisions are marked **DSC:**.

---

## 1. Design principles and values

### 1.1 Values (the "why")

| Value | Ant Design's meaning | DSC application |
|---|---|---|
| **Natural** | Visual elements follow natural perception; interaction follows natural behaviour so nothing has to be learned. | Layout reads top-to-bottom, left-to-right: summary → filters → detail. Colour, icons and position carry meaning consistently. |
| **Certain** | Restraint ("nothing left to take away"), object-oriented reuse, modular design; users get the same appearance and interaction everywhere. | One component system; the same action looks the same on every screen (governance Rule 4). |
| **Meaningful** | Every action has a clear goal and immediate feedback; the process matches the user's skill. | Feedback vocabulary (§2.5) chosen by consequence, not habit; no toast for what the user can already see. |
| **Growing** | Product and user evolve together; functions connect to needs across scenarios. | The design system is the place new patterns enter (Rule 3), never a page. |

### 1.2 The ten principles (the "how")

| Principle | Recommendation | DSC rule derived from it |
|---|---|---|
| **Proximity** | Vertical rhythm `y = 8 + 8n`: small 8, middle 16, large 24. Distance signals grouping. | Spacing scale 4/8/12/16/24/32/40/48/64 (antd `size*` tokens). Inside a card 8–16, between cards 16, between page sections 24. |
| **Alignment** | One visual starting point; numbers right-aligned with equal decimals; form labels aligned for scanning. | Table columns: text left, numbers right, actions right. Forms vertical (label above) everywhere. |
| **Contrast** | Primary/secondary (strengthen the key action *and* weaken the rest), whole/part, static/dynamic state. | Exactly one primary button per page header, per form footer, per dialog. |
| **Repetition** | Repeating the same elements lowers learning cost and reveals relationships. | Shared `PageHeader`, `FilterBar`, `DataTable`, `StatusBadge`, `EmptyState` on every screen. |
| **Make it direct** | "Where there is output, let there be input": in-page editing, drag and drop with hover invitations and single-axis movement. | Inline editing where the object is already on screen (schedule drag-to-move, playlist reorder). |
| **Stay on the page** | Overlays, inlays, virtual pages and in-page flows beat navigation; avoid modal confirmations where an undo will do. | Drawers for detail and edit; Popconfirm for low-risk confirmations; full pages only for composition tools. |
| **Keep it lightweight** | Fitts's law: tools close and large enough; always-visible / hover-reveal / toggle-reveal tools; enlarge the hit area, not the button. | Row actions as text buttons in the row; icon buttons ≥ 32 px hit area; 44 px targets on touch. |
| **Provide an invitation** | Static (text, blank-slate, unfinished, tour) and dynamic (hover, inference, "more content") invitations. | Every empty state names the reason and offers the next action; "+N more" affordances; tour reserved for first run. |
| **Use transition** | Animate additions, removals and view changes to keep context; static content must not animate. | antd motion only; `prefers-reduced-motion` honoured (antd 6.3+ does this for controls; the theme switch suppresses transitions). |
| **React immediately** | Live suggest, live preview, progress indicators after ~2 s, periodic refresh with highlighted changes, progressive disclosure. | Loading skeletons for known layouts, `Spin` for in-place refresh, button `loading` on submit, dashboard polling with "last updated". |

### 1.3 Clarity, hierarchy, consistency, usability, feedback, density, responsiveness

* **Clarity** — copywriting is user-centred, concise, consistent, sentence
  case, no trailing periods in labels/titles/tooltips/table cells, numbers
  over words, objective error language ("unable to complete", never
  "failure"), and always a next step.
* **Hierarchy** — three to five type styles per system, summary first,
  the most important chart top-left, 5–9 modules per screen.
* **Consistency** — same component for the same content type; the same
  wording for the same concept everywhere.
* **Usability** — navigation kept shallow, flat and wide; 1–2 page
  transitions per task; radios for ≤ 5 visible options, dropdowns above
  five; switches act immediately and never need a submit button.
* **Feedback** — necessary, positive and immediate; omit feedback for
  changes the user can already see; critical failures deserve a dialog,
  not a message.
* **Density** — enterprise density: 14 px body on 22 px line height,
  32 px controls, compact tables; "as few styles as possible".
* **Responsiveness** — the 24-column grid with fixed gutters; content
  transforms rather than shrinks (side navigation becomes a drawer, tables
  drop columns, forms stack).

---

## 2. Global styles

### 2.1 Colour

* Two levels: a **system palette** (12 hues × 10 steps generated from a
  seed) and **product colours** (brand, functional, neutral).
* Functional colours are semantic: success, warning, error, info, link.
* Text colours are opacities over the surface — heading/body
  `#000000E0`, secondary `#000000A6`, disabled `#00000040` (dark:
  `#FFFFFFD9`, `#FFFFFFA6`, `#FFFFFF40`) — and are expected to meet WCAG
  contrast on both light and dark grounds.
* Colour delivers information, guidance and feedback; it is not
  decoration.

**DSC:** brand `#1E40AF` (white on it 8.6:1), success `#059669`, warning
`#D97706`, error `#DC2626` (light text variant `#991B1B`), info
`#0284C7`; text tokens raised above antd defaults so body, secondary and
placeholder text clear **7:1** in both themes. Status *fills* use the
tone palette (light 100/900, dark 900/100 pairs) so text on a pill is
≥ 7:1. Colour is never the only carrier of status (icon + text always).

### 2.2 Layout

* 24 columns; 8 px base unit; all spacing multiples of 8 (4 permitted for
  fine adjustments); fixed gutter, fluid columns.
* Two skeletons: **left–right** (fixed side navigation, fluid work area,
  recommended above six menu items and for 1–3 levels) and **top–bottom**
  (2–7 items, 1–2 levels).
* Header 64 px (48 + 8n), sider 200 px (200 + 8n), collapsed 80 px;
  the product may define its own rhythm as long as it is a rhythm.
* Reference design width 1440 px; content width 1168 px in top–bottom
  layouts.

**DSC:** left–right shell (`Layout` + `Sider` 260 px / rail 80 px +
`Header` 55 px), `Drawer` navigation below `md`. Content centred at
61.8 % of the space beside the sidebar (floor 1024, cap 1440) with 24 px
gutters (16 px below `md`). Golden ratio used only for major panel
splits (15/9, 9/15) and the sidebar rhythm.

### 2.3 Typography

* System font stack; 14 px base; ten sizes with paired line heights
  (14/22 base); limit a system to 3–5 sizes; weights 400 / 500 / 600;
  `tabular-nums` for numbers.
* Heading tokens: `fontSizeHeading1–5` = 38 / 30 / 24 / 20 / 16.

**DSC:** one stack (`-apple-system, BlinkMacSystemFont, "Segoe UI",
Roboto, "Helvetica Neue", Arial, sans-serif`); five roles — page title
24 (`Title level={3}`), section 20 (`level={4}`), card/sub-section 16
(`level={5}` or Card `title`), body 14, caption 12 (`Text` with
`fontSizeSM`). Weight 600 for titles, 500 for emphasis, 400 body.

### 2.4 Icons, shadow, dark mode

* Icons: outlined by default, filled for selected/active states, sized
  with the text (16 px at 14 px type), colour follows the text unless it
  expresses state; one library only.
* Shadow: four elevation levels — 0 (inputs), 1 (hover lift), 2 (attached
  popups), 3 (dialogs); direction follows the attached edge.
* Dark mode: comfort over contrast (avoid pure white on pure black),
  information parity with light mode, palettes regenerated for dark
  grounds (`darkAlgorithm`).

**DSC:** `@ant-design/icons` only (no emoji, no second icon set);
antd's elevation tokens untouched; dark theme via `darkAlgorithm` with
navy surfaces (`#0B1220` canvas, `#111A2E` container, `#16203A`
elevated) and per-mode text/link colours.

### 2.5 Feedback vocabulary

| Need | Ant Design component | Rule |
|---|---|---|
| Quick confirmation of a completed action | `message` (3 s, top-centre) | For actions whose result is visible or trivial; never for failures needing attention |
| Persistent, page-level information | `Alert` | Stays until dismissed; `banner` for global states |
| System-pushed or background event | `notification` (top-right, 4.5 s, stackable) | Complex content, links or actions; results of long jobs |
| Decision required | `Modal` (blocking) / `modal.confirm` | Significant, actionable, irreversible |
| Low-risk confirmation | `Popconfirm` | Inline, near the trigger |
| Operation > 2 s | `Progress` / `Spin` / button `loading` | Cancel option for long jobs |
| End of a flow with strong attention | `Result` | Max 2 follow-up actions; auto-redirect 3–5 s on success |
| Field error | `Form.Item` validation | Actionable wording ("Enter a valid start time") |

---

## 3. Design patterns and page templates

### 3.1 Navigation

* Side navigation for > 6 items, 1–3 levels; top navigation 2–7 items.
* Breadcrumb only when the hierarchy exceeds two levels; show ≤ 3 levels,
  max 5. Tabs ≤ 15 characters each; Steps 2–5 horizontal.
* Page header declares the page theme, hosts in-page navigation and
  page-level operations.

**DSC:** two-level side navigation (module › page) plus detail pages
(module › page › entity). Breadcrumbs are shown on every page under a
module and on every detail page, derived from the navigation config so
they cannot drift.

### 3.2 Data entry

* Label above the field for English/long labels; consistent within a
  system.
* Input (short text), TextArea (long), Radio (2–5 visible choices),
  Checkbox (multi-select to submit), Switch (immediate toggle), Select
  (> 5 options), Slider (intensity), DatePicker (dates/ranges).
* Good defaults, structured formats and short hints; no redundant hints
  ("Please enter your name").
* Form types: basic (few fields), step (sequential with confirmation),
  grouped (many fields in categories; card grouping above two screens),
  editable list (≤ 3 dynamic rows, 2–5 editable table, 6–8 collapse, > 8
  drawer).

### 3.3 Data display and lists

* Table for multi-attribute comparison; List for browsing with
  presentation; Card list for equal-weight objects with no fixed order.
* Table anatomy: search/filter → toolbar with batch actions → header →
  rows → pagination → empty state. Keep time/status/action columns on one
  line; "-" for empty cells; right-align numbers; hide pagination when
  everything fits.
* Detail navigation: inline expansion, drawer, page or two-column.
* Cache the browsing position on return; highlight newly created rows.
* Descriptions for read-only field groups; Collapse to hide complex
  regions; Timeline for chronology; Tree for hierarchies.

### 3.4 Page templates

| Template | Structure | DSC screens |
|---|---|---|
| **Workbench** | 5–9 modules ordered by frequency: core data, to-do, shortcuts, activity, help; role-based views | Dashboard |
| **List page** (query table / standard list / card list / search list) | filter area on top (or sidebar when many filters), toolbar, table, pagination; batch actions at page level | Devices, Campaigns, Content, Audit, Users, Tenants, Invoices… |
| **Detail page** | basic (one card), document (cards per module), advanced (tabs), process (steps); Descriptions + Collapse + Table | Device detail, Campaign detail, Tenant detail, Asset detail |
| **Form page** | basic / step / grouped; single column is the most efficient; weak grouping puts short fields on one line | Create/edit drawers and modals, Settings sections |
| **Visualisation page** | summary → filters → detail; important charts top; 5–9 modules; one topic per card | Dashboard, Reports, Monitoring |
| **Result page** | feedback, explanation, ≤ 2 actions, extra info | Forgot-password sent, publish complete |
| **Exception page** | illustration, code, description, action; friendly tone | 403 (no permission / plan), 404, 500 |
| **Empty state** | illustration + reason + action; new-user vs cleared vs no-data | Every list, table and grid |

### 3.5 Buttons

* One primary per group; default when unsure; text for table actions;
  icon buttons need tooltips; dashed for "add"; danger for risk; labels
  are verbs.
* Order like a conversation; primary first in the reading flow; footer
  buttons for collapsed or complex bodies.

**DSC:** primary = create / save / publish / schedule / approve / deploy;
default = secondary (export, duplicate, preview); danger = delete /
revoke / disable; text = row and low-emphasis actions; link = navigation.
No preset-colour buttons.

### 3.6 Copywriting and data format

* Sentence case; product names capitalised; abbreviations upper case; no
  periods in labels; limit exclamation marks.
* Thousands separators; right-aligned numbers; percentages with two
  decimals where they matter; progress as `12/30`; units lower case;
  currency symbol + number; dates `YYYY-MM-DD`, times `HH:mm:ss` (24 h),
  relative time inside 24 h ("2 hours ago"), `--` for no data, masked
  sensitive values.

**DSC:** one formatter module (`utilities/format.ts`): dates
`D MMM YYYY`, date-times `D MMM YYYY, HH:mm`, relative time within 24 h,
numbers with separators, bytes, percentages; tenant timezone for all
schedule times; `—` for missing values.

---

## 4. Component mapping

Ant Design component → intended Digital Signage Cloud usage. "Via" names
the shared design-system component that wraps it when one exists.

### General
| Component | Usage | Via |
|---|---|---|
| Button | every action; variants per §3.5; `Space.Compact` for segmented groups | — |
| FloatButton | not adopted (no global floating action; back-to-top unnecessary at our page lengths) | — |
| Icon | all iconography; outlined default, filled for selected | — |
| Typography | titles (levels 3–5), body, secondary, captions, ellipsis with tooltip for long names | `PageHeader`, `SectionCard` |

### Layout
| Component | Usage |
|---|---|
| Layout / Sider / Header / Content | application shell |
| Grid (Row/Col) | dashboards, summary strips, forms with weak grouping, master–detail splits |
| Flex | block-level arrangements without wrappers (toolbars, card internals) |
| Space / Space.Compact | inline groups of buttons and controls; compact input groups |
| Divider | section separation inside cards and drawers |
| Splitter | not adopted yet (candidate for Screen Designer panels) |
| Masonry | not adopted (media grid is uniform; Row/Col suffices) |

### Navigation
| Component | Usage |
|---|---|
| Menu | sidebar navigation only |
| Breadcrumb | page hierarchy on every page beyond the top level (`PageHeader`) |
| Dropdown | overflow actions ("More"), account menu, row action menus |
| Pagination | tables and card grids (`DataTable`, media grid) |
| Steps | approval progression, wizard-style flows (tenant onboarding) |
| Tabs | in-page sections of one entity (settings groups, entity detail) |
| Anchor / Affix | not adopted (pages are short; sticky toolbars are handled by the grid components) |

### Data entry
| Component | Usage |
|---|---|
| Form / Form.Item | every form; `layout="vertical"`; validation messages actionable |
| Input / TextArea / Password / Search | text; `Input.Search` for list search (`SearchBar`) |
| InputNumber | quotas, priorities, durations, coordinates |
| Select | > 5 options, status and enum filters, multi-select with `maxTagCount="responsive"` |
| TreeSelect | location scope pickers (targets, filters, move) |
| Cascader | not adopted (location hierarchy is variable depth; TreeSelect fits) |
| AutoComplete | global search |
| Checkbox / Radio / Switch | multi-select to submit / 2–5 visible choices / immediate toggles |
| DatePicker / RangePicker / TimePicker | every date and time; `dayjs`; presets on report ranges |
| Upload / Upload.Dragger | media library, player packages, brand assets |
| Slider, Rate, Mentions, ColorPicker, Transfer | not adopted (ColorPicker is a candidate for branding; Transfer for role permissions if the list grows) |

### Data display
| Component | Usage | Via |
|---|---|---|
| Table | all tabular data | `DataTable` |
| Listy (List deprecated) | activity, notifications, approvals, queues, now playing, agenda | `EntityList` |
| Card | grouped information, KPI, entity cards | `SectionCard`, `KpiCard` |
| Statistic | KPI values | `KpiCard` |
| Descriptions | read-only field groups in drawers and detail pages | — |
| Tag | categorisation, status pills | `StatusBadge`, `ToneTag` |
| Badge | counts (unread), status dots in lists | — |
| Tooltip | icon-button names, truncated text | — |
| Popover | rich hover cards (schedule events, map pins) | — |
| Avatar | users, tenants, media thumbnails | — |
| Calendar | schedule month view | — |
| Collapse | secondary detail, advanced options | — |
| Timeline | histories (approvals, device events) | — |
| Tree | location hierarchy, folders | — |
| Segmented | view switches (day/week/month, list/grid) | — |
| Empty | every empty list/table/grid | `EmptyState` |
| Image | media previews with fallback | — |
| Tour | first-run guidance (candidate, not yet used) | — |
| Carousel, QRCode | not adopted (QRCode is a candidate for device enrolment) | — |

### Feedback
| Component | Usage | Via |
|---|---|---|
| Alert | persistent page or section information; error banners with retry | — |
| Drawer | entity detail, edit, filters, contextual panels | `EntityDrawer` |
| Modal | confirmations and short focused forms | `ConfirmAction` |
| message / notification | see §2.5 | `App.useApp()` |
| Popconfirm | low-risk destructive confirmations | `ConfirmAction` |
| Progress | deployment progress, quotas, health | — |
| Result | error state, 403/404, flow completion | `ErrorState`, exception pages |
| Skeleton / Spin | first load / in-place refresh | `LoadingState` |
| Watermark | not adopted | — |

### Other
| Component | Usage |
|---|---|
| App | root wrapper; `App.useApp()` for message / notification / modal with theme context |
| ConfigProvider | the single theme authority (`token`, `components`, `algorithm`) |
| BorderBeam | not adopted (decorative) |
| Util types (`GetProps`, `GetRef`) | typing wrappers |

---

## 5. Design-token strategy

Ant Design's three tiers — **seed** (brand inputs), **map** (derived
palettes and sizes), **alias** (semantic names used by components) — are
all set through `ConfigProvider theme`. The product overrides seeds and
a few aliases, never component CSS.

| Group | Tokens set by DSC | Rationale |
|---|---|---|
| Colour seeds | `colorPrimary`, `colorSuccess`, `colorWarning`, `colorError`, `colorInfo`, `colorLink` | brand + semantics |
| Text aliases | `colorText`, `colorTextSecondary`, `colorTextDescription`, `colorTextTertiary`, `colorTextPlaceholder`, `colorSuccessText`, `colorWarningText`, `colorErrorText` | 7:1 in both themes |
| Surfaces | `colorBgLayout`, `colorBgContainer`, `colorBgElevated` (dark) | navy family in dark |
| Typography | `fontFamily`, `fontSize` 14, heading sizes via `Typography` levels | one stack, five roles |
| Shape | `borderRadius` 8, `borderRadiusSM` 4, `borderRadiusLG` 12 | inputs/tags 4, buttons/cards 8, dialogs 12 |
| Controls | `controlHeight` 32 (SM 24, LG 40 by antd) | enterprise density |
| Spacing | antd `size*` scale (4–64), untouched | 8-based rhythm |
| Shadows | antd `boxShadow*`, untouched | four elevations |
| Motion | antd `motion*`, untouched; reduced motion honoured | restraint |
| Component tokens | `Layout`, `Menu`, `Tabs`, `Table`, `Card`, `Button` (dark danger), `Pagination` (dark) | only where the global token cannot express the need |

Component **states** (hover, active, focus, disabled, error, warning,
loading, selected) come from antd's derived tokens; the product does not
restyle them. Focus rings use antd's `focusOutline` (6.6) and are never
removed.

---

## 6. Responsive strategy

antd breakpoints are the structural system; the brief's widths are the
QA matrix.

| Class | Width | antd | Shell | Content |
|---|---|---|---|---|
| Mobile | 320–575 | `xs` | Drawer navigation, hamburger, search hidden | single column; tables → identity + status + actions with drawer detail; forms stacked; calendars → date strip + agenda; KPIs 2-up |
| Large phone | 576–767 | `sm` | as mobile | card grids 2-up |
| Tablet | 768–991 | `md` | Sider collapsed to the 80 px rail | tables gain `lg`-hidden columns still hidden; master–detail stacked; KPIs 2–3-up |
| Laptop | 992–1199 | `lg` | Sider expanded | secondary table columns appear; master–detail side by side (15/9) |
| Desktop | 1200–1599 | `xl` | as laptop | tertiary columns; KPI rows 4–5-up; dashboards full grid |
| Large desktop | 1600+ | `xxl` (`xxxl` ≥ 1920) | as laptop | content capped at 1440 px and centred; no further restructuring |

Rules: no `window.innerWidth` listeners (`Grid.useBreakpoint()` only);
wide content scrolls inside its own container; touch targets ≥ 44 px on
touch layouts; the same interaction transforms rather than shrinks.

---

## 7. Accessibility capabilities to rely on

antd provides focus traps and focus return in `Modal`/`Drawer`
(`focusable` since 6.2), roving tabindex in `Menu`/`Tabs`/`Tree`/
`Segmented` (native radios), `aria-*` wiring in `Form.Item`, `Table`
sort/selection semantics, `Tooltip`/`Popover` on focus, `Skeleton`
`aria-busy`, and `prefers-reduced-motion` in controls. The product adds:
accessible names on icon-only buttons, status = icon + text + colour,
7:1 text, `aria-live` on bulk-action bars, and no removed outlines.

---

## 8. What Ant Design does not provide (justified custom surfaces)

* The **Screen Designer canvas** (drag/resize composition) and the
  **TV preview renderer** — pixel-exact playback surfaces.
* The **schedule time grid** (week/day blocks with lanes, current-time
  line, drag-to-move) — antd `Calendar` covers month only.
* **Charts** — `@ant-design/plots` (AntV), already present; wrapped in a
  standard chart container.
* The **Leaflet map** in the dashboard.

Everything else is Ant Design or a thin composition of it (governance
Rule 2).
