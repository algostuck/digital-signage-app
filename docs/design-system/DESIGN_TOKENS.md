# Design Tokens

The single token vocabulary of Digital Signage Cloud. Every value lives
in `frontend/src/design-system/tokens/` and reaches components through
Ant Design's `ConfigProvider` (`design-system/theme/buildTheme.ts`).
Nothing in a page may restate a colour, size or radius; pages use the
token (via antd props or `theme.useToken()`) or the shared component
that already applies it.

## 1. Colours

### Brand and functional seeds (`tokens/brand.ts`)

| Token | Light | Dark | Use |
|---|---|---|---|
| `colorPrimary` | `#1E40AF` | `#1E40AF` | primary buttons, selected states, links on solid surfaces (white on it 8.6:1) |
| `colorSuccess` | `#059669` | `#059669` | success fills, progress |
| `colorWarning` | `#D97706` | `#D97706` | warning fills |
| `colorError` | `#991B1B` | `#DC2626` | danger buttons and error fills (light uses red-800 so danger text clears 7:1) |
| `colorInfo` | `#0284C7` | `#0284C7` | informational fills |
| `colorLink` | `#1E40AF` | `#93C5FD` | text links (7:1 on each canvas) |

### Text (alias tokens)

| Token | Light | Dark | Measured contrast |
|---|---|---|---|
| `colorText` | `#0F172A` | `rgba(255,255,255,.92)` | ≥ 15:1 |
| `colorTextSecondary` / `colorTextDescription` | `#475569` | `rgba(255,255,255,.75)` | ≥ 7:1 |
| `colorTextTertiary` / `colorTextPlaceholder` | `#475569` | `rgba(255,255,255,.72)` | ≥ 7:1 |
| `colorSuccessText` | `#065F46` | `#4ADE80` | ≥ 7:1 |
| `colorWarningText` | `#92400E` | `#FBBF24` | ≥ 7:1 |
| `colorErrorText` | `#991B1B` | `#FCA5A5` | ≥ 7:1 |

### Surfaces

| Token | Light | Dark |
|---|---|---|
| `colorBgLayout` (canvas) | `#F8FAFC` | `#0B1220` |
| `colorBgContainer` (cards, tables, inputs) | antd white | `#111A2E` |
| `colorBgElevated` (popups, drawers) | antd white | `#16203A` |
| Sidebar (`SIDEBAR_BG`) | `#FFFFFF` | `#0F172A` |
| `colorBorder` / `colorBorderSecondary` | antd | antd (dark algorithm) |

### Status tone palette (`tokens/tone.ts`)

Fills for pills and chips. Each pair measures ≥ 7:1 for the text on its
own fill in the given theme.

| Tone | Light bg / fg | Dark bg / fg | Meaning |
|---|---|---|---|
| `success` | `#DCFCE7` / `#14532D` | `#14532D` / `#BBF7D0` | healthy, done, live |
| `warning` | `#FEF3C7` / `#78350F` | `#451A03` / `#FDE68A` | needs attention, pending |
| `error` | `#FEE2E2` / `#7F1D1D` | `#450A0A` / `#FECACA` | failed, offline, critical |
| `high` | `#FFEDD5` / `#7C2D12` | `#431407` / `#FED7AA` | high severity (between warning and error) |
| `processing` | `#DBEAFE` / `#1E3A8A` | `#172554` / `#BFDBFE` | in progress, informational |
| `default` | `#F1F5F9` / `#1E293B` | `#1E293B` / `#E2E8F0` | neutral, inactive, draft |

### Categorical palette (`tokens/palette.ts`)

Eight hues for series and campaign colours, chosen as Tailwind 100/900
(light) and 900/100 (dark) pairs (≥ 9:1 text on fill) with a 700 "bar"
shade for borders and chart strokes: blue, teal, violet, amber, rose,
emerald, sky, fuchsia. `seriesColor(i)` and `campaignHue(id)` are the
only entry points; the dashboard chart palette derives from the same
list. Chart *status* series use the functional seeds.

### Status vocabulary (`tokens/status.ts`)

One table maps every domain status to `{ tone, icon, label }`:

| Domain | Statuses |
|---|---|
| device | online, warning, offline, pending, active, decommissioned, suspended |
| campaign | draft, pending_approval, approved, published, paused, expired, archived |
| content | processing, ready, published, archived, failed |
| deployment | draft, ready, queued, publishing, partial, published, failed, cancelled; per-device pending / acknowledged / failed |
| subscription | trial, active, past_due, suspended, cancelled, expired |
| approval | pending, approved, rejected, returned |
| schedule | play, blackout, live, conflict; severity high / medium / low |
| user | invited, active, deactivated |
| incident / severity | critical, high, medium, info; open, acknowledged, resolved |
| generic | enabled, disabled, running, completed, error, unknown |

`StatusBadge` and every chart or chip colour reads from this table;
adding a status means adding a row, never a colour in a page.

## 2. Typography

| Role | antd | Size / line | Weight | Where |
|---|---|---|---|---|
| Page title | `Typography.Title level={3}` | 24 / 32 | 600 | `PageHeader` only |
| Section heading | `Typography.Title level={4}` | 20 / 28 | 600 | `SectionCard` title, drawer section |
| Card / sub-section heading | `Typography.Title level={5}` or `Card title` | 16 / 24 | 600 | cards, drawer groups |
| Body | `Typography.Text` / default | 14 / 22 | 400 | everything |
| Body secondary | `Text type="secondary"` | 14 / 22 | 400 | descriptions, meta |
| Caption | `Text type="secondary" size="small"` (`fontSizeSM` 12 / 20) | 12 / 20 | 400 | timestamps, helper text under KPIs |
| Label | `Form.Item` label | 14 / 22 | 500 | forms |
| Helper text | `Form.Item extra` | 12 / 20 | 400 | forms |
| Table text | Table default | 14 / 22 | 400; 500 for identity column | tables |
| Display (KPI value) | `Statistic` (`fontSizeHeading3` 24) | 24 / 32 | 600, `tabular-nums` | `KpiCard` |

Font family: `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
"Helvetica Neue", Arial, sans-serif` (token `fontFamily`). No page sets
a font or a pixel size; Tailwind `text-*` size utilities are banned
outside the justified custom surfaces (see governance).

## 3. Spacing

antd's `size` scale, used through `Space size`, `Flex gap`, `Row gutter`
and component tokens:

| Step | px | Typical use |
|---|---|---|
| `sizeXXS` | 4 | icon–text gap |
| `sizeXS` | 8 | inside a control group, chip gaps |
| `sizeSM` | 12 | card body padding (small), list item gaps |
| `size` | 16 | between cards in a grid (`gutter={[16,16]}`), card padding |
| `sizeMD` | 20 | — |
| `sizeLG` | 24 | between page sections; page gutter ≥ md |
| `sizeXL` | 32 | between page header and content |
| `sizeXXL` | 48 | empty-state vertical padding |
| 64 | 64 | reserved (hero areas) |

Rule: vertical rhythm inside a card 8–16; between cards 16; between page
sections 24. Tailwind margin utilities may only use these steps
(`mt-1`=4, `mt-2`=8, `mt-3`=12, `mt-4`=16, `mt-6`=24, `mt-8`=32) and
never with the `!` prefix.

## 4. Radius, shadow, borders

| Token | Value | Use |
|---|---|---|
| `borderRadiusSM` | 4 | inputs, tags, small buttons |
| `borderRadius` | 8 | buttons, cards, menu items |
| `borderRadiusLG` | 12 | modals, drawers, large cards |
| `PILL_RADIUS` | 9999 | status pills only |
| `boxShadowTertiary` | `0 1px 2px rgba(15,23,42,.06)` light / none dark | cards |
| `boxShadowSecondary` | antd | popups (elevation 2) |
| `boxShadow` | antd | dialogs (elevation 3) |
| `lineWidth` / `colorBorderSecondary` | antd | dividers, table lines |

## 5. Controls

| Token | Value | Use |
|---|---|---|
| `controlHeight` | 32 | all inputs, selects, buttons (default) |
| `controlHeightSM` | 24 | table row actions, tags |
| `controlHeightLG` | 40 | page primary action, auth forms |
| Touch target | 44 | minimum hit area on touch layouts (padding, not size) |

States (hover, active, focus, disabled, error, warning, loading,
selected) are antd's derived tokens and are never restyled. Focus uses
antd's `focusOutline`; outlines are never removed.

## 6. Breakpoints

antd: `xs` < 576, `sm` ≥ 576, `md` ≥ 768, `lg` ≥ 992, `xl` ≥ 1200,
`xxl` ≥ 1600, `xxxl` ≥ 1920. Detection only via `Grid.useBreakpoint()`
or `Col` responsive props. QA widths: 320, 360, 375, 390, 430, 768, 834,
1024, 1280, 1440, 1920, 2560.

## 7. Motion

antd `motionDurationFast/Mid/Slow` (100/200/300 ms) and easings, untouched.
Custom animation is limited to `SyncOutlined spin` on processing status,
the schedule current-time line (no animation) and chart transitions; all
respect `prefers-reduced-motion` (antd 6.3+ for controls; the design
system's `useReducedMotion()` for custom surfaces). The theme switch
suppresses transitions for 220 ms (`.theme-switching`, the one justified
`!important`).

## 8. Layout proportions

| Token | Value | Use |
|---|---|---|
| Sider | 260 / 80 | expanded / rail |
| Header | 55 | matches sidebar bands; 55/34 ≈ φ with menu rows |
| Content max width | `clamp(1024px, 61.8cqw, 1440px)` | centred container |
| `GOLDEN_SPLIT` | 15 / 9 | master–detail and dashboard splits (heuristic) |

## 9. Accessibility tokens

* Text ≥ 7:1 in both themes (measured; see `HARDENING_AUDIT.md`).
* Status fills ≥ 7:1 text on fill (tone palette).
* Focus ring: antd `focusOutline` 2 px, offset 1 px, `colorPrimaryBorder`.
* Minimum target 24 × 24 (WCAG 2.2 2.5.8) everywhere; 44 on touch layouts.
