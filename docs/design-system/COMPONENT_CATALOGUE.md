# Component Catalogue

The reusable UI patterns of Digital Signage Cloud. All live in
`frontend/src/design-system/components/` and are imported from the
barrel `@/design-system`. Each is a thin composition over Ant Design;
none re-implements an antd control. A page that needs something not
listed here first asks whether Ant Design already provides it (see
[ANTD_REFERENCE_ANALYSIS.md](ANTD_REFERENCE_ANALYSIS.md) §4), then adds
the pattern *here*, never inside a module.

Format per entry: Purpose · Ant Design base · Variants · Usage · Do /
Don't · Responsive · Accessibility.

---

## Page structure

### PageContainer
* **Purpose**: the vertical rhythm of every business page: header, optional filters, content sections with 24 px spacing.
* **Base**: `Flex vertical gap={24}` + `PageHeader`.
* **Variants**: `width="full" | "narrow"` (narrow = forms/settings, max 960 px).
* **Usage**: `<PageContainer title description breadcrumbs actions filters>{sections}</PageContainer>`.
* **Do**: one per route. **Don't**: nest page containers; add page-level margins in modules.
* **Responsive**: gutters from the shell; sections stack.
* **A11y**: renders the page `h1`-equivalent (`Title level={3}`) exactly once.

### PageHeader
* **Purpose**: breadcrumb, title, description, primary + secondary actions.
* **Base**: `Breadcrumb`, `Typography.Title level={3}`, `Typography.Text type="secondary"`, `Flex`, `Space`.
* **Variants**: `breadcrumbs` explicit or **derived from the navigation config** (default); `actions` node; `extra` (tags beside the title, e.g. status).
* **Usage**: through `PageContainer`; directly only on composition tools (designer).
* **Do**: exactly one `type="primary"` button. **Don't**: put filters in the header.
* **Responsive**: actions wrap; on mobile `ResponsiveActions` collapses secondaries.
* **A11y**: title is the page heading; breadcrumb is a `nav` with `aria-label="Breadcrumb"` (antd).

### SectionCard
* **Purpose**: a titled section on a page or in a drawer (settings sections, detail groups).
* **Base**: `Card` with `title` (`Title level={4}`/`5`), `extra` (actions), `description` line, `size="small"|"medium"`.
* **Variants**: `variant="outlined"|"borderless"`, `collapsible`.
* **Do**: one topic per card; keep nesting ≤ 2. **Don't**: cards inside cards inside cards.
* **Responsive**: full-width; internal `Row` collapses.
* **A11y**: heading level passed in so order stays valid.

### ExceptionPage
* **Purpose**: 403 (no permission / plan), 404, 500 with the standard structure.
* **Base**: `Result status` + up to two `Button`s.
* **Usage**: router `errorElement`, `EntitlementGuard`, `PlatformGuard`, unknown routes.
* **Do**: say what happened and what to do. **Don't**: show stack traces.

---

## Data display

### DataTable
* **Purpose**: every enterprise table.
* **Base**: `Table` with `size="medium"` (compact-but-readable density), `sticky`, `scroll={{ x: "max-content" }}`, standard empty (`EmptyState`), loading (skeleton rows) and error (`ErrorState` with retry) contracts, pagination (`showTotal`, `showSizeChanger` above 50 rows, `hideOnSinglePage`).
* **Variants**: `density="compact"|"medium"`; `bulkActions` (renders the selection toolbar with `aria-live`); `mobileDetail` (row tap opens a drawer below `md`).
* **Usage**: `columns` follow the alignment rules — identity/text left; numbers right with `tabular-nums`; status centre or left with `StatusBadge`; actions right, text buttons, ≤ 3 visible then `Dropdown`; dates formatted by `formatDate`; secondary columns `responsive: ["lg"]`, tertiary `["xl"]`.
* **Do**: keep time/status/action cells on one line (`ellipsis` elsewhere). **Don't**: hand-roll an empty state or a spinner.
* **Responsive**: see RESPONSIVE_COMPONENT_RULES.
* **A11y**: antd table semantics; row action names include the row identity ("Delete Kolkata Store 3").

### EntityList
* **Purpose**: list-shaped content: activity, notifications, approvals, queues, now playing, agenda.
* **Base**: `Listy` (virtual for > 100 items, sticky group headers), `Avatar`, `Typography`, `StatusBadge`, `Flex`.
* **Variants**: `grouped` (by date/severity), `dense`.
* **Do**: use for browsing, not comparison. **Don't**: use `Table` for feeds.
* **Responsive**: actions wrap under the meta line.
* **A11y**: items are `li` with a heading + description; actions are buttons.

### KpiCard
* **Purpose**: metric → value → trend → context.
* **Base**: `Card size="small"` + `Statistic` (24 px, `tabular-nums`) + trend (`RiseOutlined`/`FallOutlined` + text in `colorSuccessText`/`colorErrorText`) + caption.
* **Variants**: `tone` (success/warning/error value colour), `loading`, `onClick` (links to the filtered list; renders as a button), `progress` (quota usage).
* **Do**: always give context ("vs previous 7 days"). **Don't**: decorative numbers.
* **Responsive**: `Col flex="1 1 150px"` strips.
* **A11y**: clickable cards are buttons with a full name ("Devices offline, 12, view devices").

### StatusBadge
* **Purpose**: the one way to show any status.
* **Base**: `Tag` with icon + text + tone fill from the status vocabulary (`tokens/status.ts`).
* **Variants**: `domain` (device, campaign, content, deployment, subscription, approval, schedule, user, severity, generic); `size="small"`; `dot` (Badge status dot + text for dense lists).
* **Do**: pass the raw backend status; labels come from the vocabulary. **Don't**: colour a Tag by hand.
* **A11y**: never colour-only.

### ToneTag
* **Purpose**: a tinted pill for non-status labels that still need a tone (severity counts, "Today", categories).
* **Base**: `Tag` + tone palette.
* **Don't**: use for statuses (use `StatusBadge`).

### ChartFrame
* **Purpose**: the container for every chart.
* **Base**: `Card` + title/subtitle (`Title level={5}` + secondary text) + `Skeleton` + `EmptyState` + `ErrorState` + fixed height.
* **Variants**: `height`, `legendPosition`, `actions` (range/segmented in `extra`).
* **Do**: series colours from `seriesColor()`; status series from functional colours; a text summary beside the chart.
* **A11y**: chart is `aria-hidden` with a caption; the summary/table is the accessible data.

---

## Data entry and filtering

### FilterBar
* **Purpose**: the recognisable "Search · primary filters · More filters · Reset" row of every data-heavy page.
* **Base**: `Space wrap` (desktop) / `Drawer` (mobile) + `SearchBar` + `Select`/`TreeSelect`/`RangePicker` children + `Button` Reset + `Badge` on "More filters".
* **Variants**: `primary` (always visible, ≤ 4 controls), `more` (in the drawer), `onReset`, `activeCount`.
* **Do**: keep filter state in the URL for list pages. **Don't**: put a primary button in the filter row.
* **Responsive**: see rules.
* **A11y**: each control has `aria-label` or a `Form.Item` label inside the drawer.

### SearchBar
* **Purpose**: list search.
* **Base**: `Input.Search` with `allowClear`, debounced `onSearch`, `aria-label`.
* **Variants**: `width` (default 260), `loading`.

### UploadArea
* **Purpose**: media, packages, brand assets with one validation and progress language.
* **Base**: `Upload.Dragger` (desktop) / `Upload` button (mobile), `beforeUpload` limits (`accept`, `maxSize`, `maxCount`), progress via `Progress`, errors via `Alert`, retry per file.
* **Do**: state limits in the hint ("MP4, JPG, PNG up to 512 MB"). **Don't**: silently drop files.

### FormSection
* **Purpose**: a titled group inside a long form (weak grouping / in-area grouping from the Ant Design form research).
* **Base**: `Divider titlePlacement="start"` or `SectionCard`, `Row gutter` for paired short fields.
* **Do**: short fields paired (`Col md={12}`); required marks; `extra` for helper text. **Don't**: 30 fields in one column without groups.

---

## Overlays and feedback

### EntityDrawer
* **Purpose**: entity detail and contextual editing that keeps page context.
* **Base**: `Drawer` (`size` 480 default, 640 wide, `100%` on mobile), header with title + `StatusBadge` + `extra` actions, body of `Descriptions`/`Tabs`/`SectionCard`, `footer` with one primary.
* **Variants**: `tabs`, `loading` (antd skeleton), `destroyOnHidden`.
* **Do**: one primary in the footer. **Don't**: multi-screen wizards.
* **A11y**: focus trap and return (antd); heading levels start at 4 inside.

### ConfirmAction
* **Purpose**: one confirmation language.
* **Base**: `Popconfirm` for low-risk / reversible; `modal.confirm` (via `App.useApp()`) for destructive or irreversible with `okButtonProps={{ danger: true }}`; standard copy "Delete <entity>?" + consequence + "Delete" / "Cancel".
* **Variants**: `severity="low"|"high"`, `okText`, `consequence`.
* **Don't**: `window.confirm`; a modal for a reversible action.

### Feedback helpers
* `notify.success/error/info(title, description?)` → `notification` (background events, long-job results).
* `toast.success/error(text)` → `message` (immediate, visible-result actions).
* `Alert` for persistent page state; form errors stay in the form.

### EmptyState / ErrorState / LoadingState
* **Base**: `Empty` (title, reason, ≤ 1 action) / `Result status="error"` + retry / `Skeleton` (known layout) or `Spin` (in-place refresh).
* **Do**: name the reason ("No devices match these filters"). **Don't**: a blank area or a page-wide spinner for one widget.

### EntitlementGuard / PermissionGuard
* **Base**: `Result` (403 structure) with "why" (plan, limit, subscription state) and an action ("View plans").

### ResponsiveActions
* **Purpose**: N actions on desktop, primary + "More" `Dropdown` on mobile.
* **Base**: `Space` + `Dropdown` (`Grid.useBreakpoint`).

---

## Justified custom surfaces (documented, not design-system components)

| Surface | Why custom | Rules |
|---|---|---|
| Screen Designer canvas | pixel composition | chrome on antd; numeric keyboard path |
| TV preview renderer | playback fidelity | outside the theme; static |
| Schedule time grid | week/day blocks with lanes | antd `Calendar` for month; popovers/drawers antd |
| Dashboard map (Leaflet) | geography | `aria-hidden`; list beside it |
