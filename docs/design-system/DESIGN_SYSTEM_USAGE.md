# Design System Usage

How to build inside Digital Signage Cloud without bypassing the design
system. Read this before adding a page, a form, a table, a dialog or a
colour. The governance rules at the end are enforced by review and by
the frontend lint (`npm run lint`).

Everything is imported from one place:

```tsx
import {
  PageContainer, SectionCard, DataTable, FilterBar, SearchBar, KpiCard,
  StatusBadge, ToneTag, EntityDrawer, EntityList, ConfirmAction, EmptyState,
  ErrorState, LoadingState, UploadArea, ChartFrame, ResponsiveActions,
  useBreadcrumbs, useFeedback, formatDate, formatDateTime, formatNumber,
} from "@/design-system";
```

## 1. How to create a page

```tsx
export function DevicesPage() {
  return (
    <PageContainer
      title="Devices"
      description="Every screen in the estate, its health and what it plays."
      // breadcrumbs derive from src/config/navigation.tsx; pass `breadcrumbs`
      // only for detail pages: [{ label: "Devices", to: "/devices" }, { label: device.name }]
      actions={<Button type="primary" icon={<PlusOutlined />}>Enrol device</Button>}
      filters={<FilterBar …/>}
    >
      <KpiStrip />          {/* optional summary */}
      <DataTable …/>        {/* main content */}
    </PageContainer>
  );
}
```

Structure is fixed: breadcrumb → title/description → actions → filters
→ content. One primary action. Sections are components in the module's
folder (`Page → Sections → Business components → Design system → antd`);
a page file stays under ~250 lines.

## 2. How to create a form

* `Form layout="vertical"`, `requiredMark`, `scrollToFirstError`.
* Every control inside `Form.Item` with a `label`; helper text in `extra`;
  short fields paired with `Row gutter={16}` + `Col xs={24} md={12}`.
* Group long forms with `FormSection` (title + fields); use `Steps` for
  sequential flows and `Tabs` only for independent groups.
* Validation messages say what to do: `"Enter a valid campaign start time."`
* Submit: `Button type="primary" htmlType="submit" loading={pending}`;
  on success `toast.success("Campaign created")` and close/redirect; on
  failure keep the form open with an `Alert type="error"` (server message)
  or field errors (`form.setFields`).
* Pickers: `DatePicker`/`RangePicker`/`TimePicker` only (`dayjs`), format
  from `format.ts`; `Select` for > 5 options, `Radio.Group` for ≤ 5,
  `Switch` only when the change applies immediately.

## 3. How to create a table

```tsx
<DataTable<Device>
  rowKey="id"
  columns={[
    { title: "Device", dataIndex: "name", render: (v, r) => <Link …>{v}</Link> },            // identity left
    { title: "Location", dataIndex: "location", responsive: ["lg"], ellipsis: true },
    { title: "Status", dataIndex: "status", render: (s) => <StatusBadge domain="device" status={s} /> },
    { title: "Uptime", dataIndex: "uptime", align: "right", render: (v) => formatPercent(v), responsive: ["xl"] },
    { title: "Last seen", dataIndex: "last_seen", align: "right", render: (v) => formatRelative(v), responsive: ["lg"] },
    { title: "Actions", align: "right", render: (_, r) => <Space size={0}><Button type="link" size="small">Open</Button>…</Space> },
  ]}
  dataSource={rows}
  loading={query.isLoading}
  error={query.error}
  onRetry={query.refetch}
  emptyTitle="No devices match these filters"
  emptyAction={<Button onClick={reset}>Clear filters</Button>}
  pagination={{ total, pageSize, current, onChange }}
  bulkActions={selected.length ? <Button danger>Decommission</Button> : undefined}
  mobileDetail={(row) => setOpen(row.id)}
/>
```

Rules: numbers right; actions right as text buttons (≤ 3, then a
`Dropdown`); status via `StatusBadge`; dates via the formatter; secondary
columns hidden with `responsive`; never a bespoke empty/loading/error.

## 4. How to create a modal

Only for confirmations and short focused forms (≤ ~8 fields):
`Modal` with `destroyOnHidden`, width 520–680, `okText` a verb,
`confirmLoading`. Anything longer or that must keep page context is a
drawer.

## 5. How to create a drawer

```tsx
<EntityDrawer
  open={!!id}
  onClose={close}
  title={device.name}
  status={<StatusBadge domain="device" status={device.status} />}
  extra={<Button>TV preview</Button>}
  size="wide"
  footer={<Button type="primary" onClick={save}>Save changes</Button>}
>
  <Descriptions … />
  <SectionCard title="Telemetry" level={5}>…</SectionCard>
</EntityDrawer>
```

## 6. How to add filters

`FilterBar` with `SearchBar` first, up to four primary controls, the
rest under "More filters" (a `Drawer` with a vertical `Form`), and Reset.
Keep filter state in the URL (`useSearchParams`) so links are shareable;
apply server-side where the API supports it.

## 7. How to use statuses

`<StatusBadge domain="campaign" status={campaign.status} />`. Never
`<Tag color="green">`. New statuses are added to
`design-system/tokens/status.ts` (tone + icon + label) once.

## 8. How to use spacing

`Space size="small|middle|large"`, `Flex gap`, `Row gutter={[16,16]}`,
`Card size`. Tailwind margin/padding utilities only from the scale
(`mt-1/2/3/4/6/8`) and never with `!`. Vertical rhythm: 8–16 inside a
card, 16 between cards, 24 between sections (`PageContainer` does it).

## 9. How to use typography

`Typography.Title level={3|4|5}` for page/section/card headings (never
`level={1|2}` in the app, never `<h2>`), `Typography.Text` and
`type="secondary"` for body and meta, `Text` with `size="small"` for
captions. No `text-xl font-semibold` or `text-[13px]`.

## 10. How to add responsive behaviour

`Grid.useBreakpoint()` for structural decisions, `Col` responsive props
for layout, `responsive` on table columns, `ResponsiveActions` for
action rows, `EntityDrawer` full-width below `md`. See
`RESPONSIVE_COMPONENT_RULES.md`.

## 11. How to use Ant Design tokens

```tsx
const { token } = theme.useToken();
<div style={{ borderColor: token.colorBorderSecondary, background: token.colorBgContainer }} />
```

Read tokens; never write hex in a module. Status colours come from
`useStatusTone()`; series colours from `seriesColor(i)`. If a token is
missing, add it in `design-system/theme/buildTheme.ts`, never inline.

## 12. Feedback

| Situation | Call |
|---|---|
| Saved, deleted, copied — result visible | `toast.success("Playlist published")` |
| Failed action needing attention | `toast.error(message)` (short) or inline `Alert` |
| Background job finished, export ready, deployment result | `notify.success(title, description)` |
| Destructive / irreversible | `ConfirmAction severity="high"` |
| Low-risk confirmation | `ConfirmAction` (Popconfirm) |
| Persistent page condition | `Alert` |

## 13. Governance rules

1. Ant Design is the default component framework.
2. Custom components require a written justification in
   `COMPONENT_CATALOGUE.md` (justified custom surfaces).
3. New reusable patterns enter `src/design-system/`, never a module.
4. No page may create its own visual language.
5. No arbitrary colours: no hex, no Tailwind colour utilities in modules.
6. No arbitrary spacing where tokens exist; no `!`-prefixed utilities.
7. No duplicated UI components without justification.
8. Accessibility is mandatory (`ACCESSIBILITY_GUIDELINES.md`).
9. Responsive behaviour is mandatory (`RESPONSIVE_COMPONENT_RULES.md`).
10. Business logic stays in services/hooks; visual components render.

The lint enforces 1, 5, 6 and the raw-control ban
(`<button>`, `<input>`, `<select>`, `<table>` outside justified files).
