# Platform Console

The Super Admin surface (`users.is_superuser`). It used to be one page —
tenants, plans, a plan editor, a request inbox and a per-tenant drawer with
four forms in it — which became unworkable as the tenant count grew. It is
now a section with one page per concern.

## Information architecture

```
Platform Console            (sidebar submenu, Super Admin only)
├── Overview                /platform
├── Tenants                 /platform/tenants
│   └── Tenant workspace    /platform/tenants/:tenantId
│         Subscription · Usage & quotas · Invoices · Profile
├── Plans                   /platform/plans
├── Plan requests           /platform/plan-requests
└── Invoices                /platform/invoices
```

The submenu is declared once in `frontend/src/config/navigation.tsx`, so it
gets the same RBAC filtering, collapsed-rail flattening and route-to-menu
matching as every other section. `/platform/tenants/:id` selects the
Tenants entry through the existing longest-prefix rule.

Every page renders inside `PlatformGuard`, which shows a 403 result for
deep links reached by a non-superuser. The API enforces the same rule on
every `/platform/*` route.

## Pages

**Overview** — the numbers that need attention today: tenants (active, on a
live subscription), plans open for subscription, pending plan requests,
outstanding and overdue invoices; plus the five most recent requests and
any subscription in `past_due` / `grace_period` / `suspended`, each one
click from the page that resolves it.

**Tenants** — every organization with status, plan, subscription health,
device and user counts. Filters: search (name/code), tenant status,
subscription status (including "None (legacy)"), plan. Rows open the
workspace; nothing is edited inline. **New tenant** opens a drawer that
creates the organization and its owner and can assign a plan in the same
step, with a note explaining that a tenant without a plan runs in legacy
mode with no limits.

**Tenant workspace** — a header with lifecycle actions (suspend, reactivate,
archive), each behind a confirmation that states the consequence in plain
language, and four tabs:

| Tab | What it does |
|---|---|
| Subscription | Assign a plan (with cycle and trial) when there is none. Otherwise: the current subscription, **Change plan** (immediate, up or down, with a warning that limits change for every user), **Set status** (every transition behind a confirmation; destructive ones marked), and the payment-provider references. |
| Usage & quotas | Usage bars against *effective* limits, and the platform quota overrides with the rule spelled out: overrides only tighten, blank removes. |
| Invoices | The tenant's invoices with overdue highlighting, download, and **Record payment** (provider + reference; states that a past-due subscription reactivates). |
| Profile | Name, timezone (searchable IANA list), data region. Save is disabled until something changes; Discard restores. Code is shown but permanent. |

**Plans** — the catalogue as a table: pricing, the three headline limits,
feature count, and how many tenants are on each plan. Segmented filter for
"open for subscription" vs all. Create and edit share one drawer whose limit
and feature fields are generated from the backend entitlement catalogue,
so the form cannot drift from the engine. Editing shows a notice that
changes reach every tenant on the plan.

**Plan requests** — the inbox, filtered by pending / approved / rejected /
all. Approve and reject both open a modal that takes a note to the tenant;
approve warns to confirm payment first (the plan switches on approval), and
reject requires a reason.

**Invoices** — the receivables ledger across all tenants, with outstanding
totals per currency and an overdue count. Filters: number, status, tenant.
Download and Record payment per row.

## Conventions

- Lists are `DataTable` with `FilterBar`; forms live in `Drawer` (create,
  edit) or `Modal` (decisions); irreversible actions confirm with the
  consequence, not just "Are you sure?".
- Every mutation reports through `usePlatformFeedback`: one success toast,
  one error toast shape, and invalidation of everything under the
  `["platform"]` query key so no page shows stale data after a change made
  on another.
- Money is formatted with `Intl.NumberFormat` in the invoice's own
  currency; dates with the viewer's locale.
- Every status renders through `StatusBadge` (icon + text, never colour
  alone).

## Backend additions

Two read-only endpoints the split needed; both `require_superuser`.

| Endpoint | Purpose |
|---|---|
| `GET /platform/tenants/{tenant_id}` | One tenant with the profile fields the workspace edits (`timezone`, `locale`, `region`, `quotas`). The list row builder was factored into `platform_service.tenant_row` so both share it. |
| `GET /platform/invoices?status=&tenant_id=` | Every tenant's invoices joined with organization and plan, newest first. Without it the ledger would have needed one request per tenant. |

Covered by `test_platform_reads_one_tenant_and_all_invoices` in
`tests/test_saas_core.py`: field presence, non-superuser 403, the ledger
containing a freshly issued invoice, and filters narrowing rather than
widening.

## Not changed

No existing endpoint, permission or business rule was altered. The old
single page (`PlatformPage.tsx`, `PlanEditor.tsx`) is removed; `/platform`
still works (it is now the overview), so the account menu's link and any
bookmark keep resolving.
