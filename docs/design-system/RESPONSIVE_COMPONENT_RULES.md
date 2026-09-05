# Responsive Component Rules

Behaviour of every major component at the three classes the brief
names. Widths map to antd breakpoints: **Mobile** = `xs`/`sm`
(320–767), **Tablet** = `md` (768–991), **Desktop** = `lg` and above
(992+; content caps at 1440 px and centres beyond). Detection is only
`Grid.useBreakpoint()` or `Col` responsive props; wide content scrolls
inside its own container, never the page body.

| Component | Desktop | Tablet | Mobile |
|---|---|---|---|
| **App shell** | `Sider` 260 px expanded (user may collapse to 80 px rail) | `Sider` starts collapsed to the rail | `Drawer` navigation from the hamburger; global search hidden; tenant switcher icon-only |
| **Header** | search, tenant switcher, notifications, theme | same | hamburger, tenant, notifications, theme |
| **PageHeader** | breadcrumb → title + description left, actions right on one line | actions wrap under the title | title stacks; primary action full-width first, secondary actions collapse into a `Dropdown` "More" (`ResponsiveActions`) |
| **Breadcrumb** | full trail | full trail | trail truncated to parent › current |
| **FilterBar** | search + primary filters inline, "More filters" opens a `Drawer`, Reset at the end | inline, wraps to two rows | search full-width; filters and Reset behind one "Filters" button that opens the `Drawer` |
| **DataTable** | all columns; sticky header; pagination with size changer | columns marked `responsive: ["lg"]` hidden; horizontal scroll inside the table | identity + status + actions only (`responsive: ["md"]` hides the rest); row tap opens the detail `Drawer`; simple pagination |
| **Bulk actions** | toolbar above the table | same | sticky bottom bar |
| **EntityList (Listy)** | title / meta / actions on one row | same | actions wrap under meta |
| **Card grids** | 3–6 per row (`Col lg={8} xl={6}`) | 2 per row | 1 per row (2 for media thumbnails) |
| **KpiCard strip** | 4–5 per row (`flex="1 1 150px"`) | 2–3 per row | 2 per row (`xs={12}`) |
| **SectionCard / detail sections** | two columns where grouped (`Row` 12/12 or 15/9) | stacked | stacked |
| **Forms** | vertical labels; short fields paired on one row (`Col md={12}`) | same | every field full-width |
| **Modal** | width 520–680 centred | same | full-width with 16 px margins; footer buttons stack |
| **Drawer** | 480–640 px (`size` per catalogue) | same | full-width (`size="100%"`) |
| **Tabs** | line tabs | line tabs | scrollable tabs (antd `more` overflow) |
| **Descriptions** | `column={{ xs:1, md:2, xl:3 }}` | 2 | 1 |
| **Statistic / KPI** | 24 px value | same | same |
| **Charts (ChartFrame)** | fixed 240–320 px height, responsive width | same | 200 px height, legend below |
| **Calendar (schedule)** | month/week/day with side panel (15/9) | same, panel below | date strip + agenda list |
| **Time grid** | 7 columns ≥ 120 px each, horizontal scroll inside if narrower | same | not rendered (agenda instead) |
| **Tree (locations)** | 9/15 master–detail | stacked | stacked; detail in a `Drawer` |
| **Upload** | `Upload.Dragger` area | same | button-style upload |
| **Menu (sidebar)** | inline with groups | rail with tooltips | inline inside the Drawer |
| **Popover / Tooltip** | hover + focus | hover + focus | tap; long content moves to a `Drawer` |
| **message / notification** | top-centre / top-right | same | top-centre for both; max 1 stacked |
| **Screen Designer** | full tool | scales the artboard | scales; editing not a target (documented) |
| **TV Preview** | 16:9 modal ≤ 1200 px | same | 16:9 letterboxed, controls below |

## Standard responsive props

```tsx
// card grid
<Row gutter={[16, 16]}>
  <Col xs={24} sm={12} lg={8} xl={6}>…</Col>
</Row>
// KPI strip
<Col xs={12} sm={8} xl={4}>… or <Col flex="1 1 150px">
// master–detail (golden)
<Col xs={24} lg={15}>…</Col><Col xs={24} lg={9}>…</Col>
// table columns
{ title: "Location", dataIndex: "location", responsive: ["lg"] }
{ title: "Updated", dataIndex: "updated_at", responsive: ["xl"], align: "right" }
```

## Never

* `window.innerWidth` or `matchMedia` in components.
* Fixed pixel page widths outside the designer canvas.
* Horizontal page-body scroll.
* Hiding the primary action on mobile.
* Shrinking desktop tables onto a phone without dropping columns.
