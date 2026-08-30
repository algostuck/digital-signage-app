# SaaS Core — Multi-Tenancy, Subscriptions & Entitlements

Status: **Implemented** (migrations `0020_saas_core` + `0021_plan_change_requests`, August 2026).
This module sits between Phase 2 and Phase 3: every Phase-3 feature gate
references the entitlement engine defined here.

## 1. Tenancy model

- The **tenant is the organization** (`organizations`), unchanged from Phase 1.
  A user is *not* a tenant.
- Every user row lives in exactly one **home organization**
  (`users.organization_id`) — Phase-1 behavior, RBAC via `user_roles`.
- **`tenant_users`** grants one existing user identity access to *other*
  organizations ("guest membership") with exactly one tenant-scoped role per
  membership. Home access is implicit and never has a `tenant_users` row.
- Tenant context comes exclusively from the JWT `org` claim, which is verified
  server-side on every request: if it differs from the user's home org, an
  **active membership must exist** or the request is rejected with 401.
  Nothing tenant-related is ever trusted from request input.

### Tenant switching

- `GET /auth/memberships` — the organizations the caller may act in
  (home + active guest memberships).
- `POST /auth/switch-tenant {organization_id, refresh_token}` — validates the
  membership, revokes the presented refresh token (rotation) and issues a new
  token pair whose `org` claim is the target organization. In a guest org the
  caller's permissions come from the **membership's role**, not home roles.
- `POST /auth/refresh` preserves the active org claim across rotation, but
  re-validates the membership first — removing a membership kills switched
  sessions at the next request/refresh.

### Member management (tenant admin)

- `GET /organization/members` — home users + guest memberships.
- `POST /organization/members {email, role_id, is_owner}` — grants an existing
  platform user access (permission `members.manage`).
- `PATCH/DELETE /organization/members/{membership_id}`.

## 2. Plans & entitlements

Data-driven — **no `if plan == "enterprise"` anywhere**. The catalogue lives
in `app/services/entitlements.py` (`ENTITLEMENTS`): 6 numeric limits
(`max_devices`, `max_users`, `max_storage_mb`, `max_locations`,
`max_api_calls_month`, `ai_credits_month`) and 13 feature flags (`sso`,
`white_label`, `video_wall`, `ai_features`, `proof_of_play`,
`advanced_analytics`, `api_access`, `dynamic_data`, `experiments`,
`advertising`, `fleet_ai`, `developer_portal`, `edge_bundles`).

- `plans` + `plan_entitlements`: one row per key per plan. `int_value NULL`
  means unlimited.
- `subscription_items`: per-subscription overrides/add-ons that win over the
  plan rows (enterprise custom limits).
- Effective value resolution:
  `subscription_items → plan_entitlements → catalogue default`,
  then numeric limits are **min-combined** with the platform quota override
  (`organizations.quotas_json`, Phase-2K) — a platform admin can always
  tighten below the plan, never widen.
- **Legacy mode**: an organization with *no* subscription runs unrestricted
  (limits unlimited, features on). Existing tenants keep behaving exactly as
  before this module existed.

Seeded plans (`python -m app.seed`): Starter (10 devices / 3 users / 50 GB),
Business (100 / 20 / 500 GB + analytics + API), Professional (500 / 100 /
2 TB + SSO + video wall + AI), Enterprise (5000 / 500 / 5 TB, everything,
custom pricing). The demo org is subscribed to Enterprise.

## 3. Subscriptions & lifecycle

`subscriptions` (one active per org): statuses `trialing → active →
past_due → grace_period → suspended`, plus `cancelled` and `expired`;
cycles `monthly | yearly | custom`. Every transition appends a
`subscription_events` row (who/what/when).

Dunning ladder (hourly `subscription_lifecycle` beat, measured from the
oldest unpaid invoice's `due_at`):

| Days overdue | Status |
|---|---|
| 0+ | `past_due` (warn) |
| 7+ | `grace_period` (warn harder) |
| 14+ | `suspended` |

The ladder only escalates (one-way); recording a payment returns the
subscription to `active`. The sweep also ends trials (first invoice), renews
periods, and expires subscriptions whose `cancel_at` has passed. Each
escalation raises a tenant notification.

### Suspension semantics — never blank a TV over billing

Growth actions are blocked outside `{trialing, active, past_due,
grace_period}`: device registration, upload sessions, campaign creation,
publishing, user creation. **Player endpoints (heartbeat, manifest, asset
URLs, acks) are never routed through subscription checks** — existing
devices keep playing cached content while suspended.

### Plan changes are approval-gated (manual payment flow)

Tenants never change plans self-serve. `POST /billing/change-plan` records a
**plan change request** (`plan_change_requests`, one pending per org); the
subscription is untouched until a Super Admin approves it on `/platform`
(`GET /platform/plan-requests`, `POST /platform/plan-requests/{id}/approve |
reject`) — the working agreement is: verify the manual money transfer first,
then approve; approval applies the change immediately and notifies the
tenant. The Super Admin can also change a tenant's plan **directly**
(`PATCH /platform/tenants/{id}/subscription/plan`) — upgrades and downgrades
alike — without a request. Similarly, a tenant whose subscription is
suspended/past-due for non-payment cannot self-reactivate: `POST
/billing/reactivate` refuses with "Payment is outstanding…"; the way back to
`active` is the platform admin recording the payment (or an explicit
platform transition). Tenant self-serve `reactivate` only undoes a
scheduled cancellation.

### Quota overrides are Super Admin-only

`PATCH /organization/quotas` was removed. Tenants see usage vs effective
limits read-only (`GET /organization/usage`); the override editor lives at
`GET/PATCH /platform/tenants/{id}/quotas` and can only tighten below the
plan.

### Billing separation

- *Subscription* = what the tenant is entitled to.
- *Billing* = `invoices` (`INV-<year>-<org8>-<seq>`, 7-day due) + `payments`.
- *Payment collection* = provider abstraction: `subscriptions.provider`
  defaults to `manual` (enterprise PO/invoice flow — a platform admin records
  payments). Stripe/Razorpay later become config swaps; provider references
  stay confined to the `provider_*` columns.
- Plans without a price for the chosen cycle (Enterprise) issue no invoices.

## 4. Enforcement points (permission AND entitlement)

| Action | Check |
|---|---|
| `POST /player/register` | growth allowed + `max_devices` — refusal: `Device limit reached (N/N). Upgrade your subscription.` |
| `POST /assets/uploads` | growth allowed + `max_storage_mb` |
| `POST /users` | growth allowed + `max_users` |
| `POST /locations` | `max_locations` |
| `POST /campaigns` | growth allowed |
| `POST /deployments` (publish) | growth allowed |
| `X-API-Key` requests | `api_access` flag + `max_api_calls_month` (metered via `usage_counters`) |
| Phase-3 features | `entitlements.require_feature(db, org, "<flag>")` |

`GET /organization/usage` now reports **effective** limits (plan ∧ quota).

## 5. Usage counters

`usage_counters` (org × metric × month) are refreshed by the 15-minute
`snapshot_usage` beat — dashboards and the billing screen never run
`COUNT(*)` against live tables per request. Metered metrics (`api_calls`,
later `ai_credits`) increment the current month's counter at consumption
time; `usage_events` keeps a slim audit trail when needed.

## 6. API surface

Tenant (`billing.view` / `billing.manage`):
`GET /plans`, `GET /billing/subscription` (plan + status + effective
entitlements + usage + pending plan request), `POST /billing/subscribe`,
`POST /billing/change-plan` (creates a *request*), `POST /billing/cancel |
reactivate`, `GET /billing/invoices` (+ `/{id}/download` printable HTML),
`GET /billing/usage`.

Platform (**Super Admin** — `users.is_superuser`, guard `require_superuser`):
`GET/POST /platform/tenants`, `PATCH /platform/tenants/{id}` (name/timezone),
`PATCH /platform/tenants/{id}/status`, `GET/PATCH
/platform/tenants/{id}/quotas`, `GET/POST /platform/plans`, `GET
/platform/entitlements` (catalogue for the plan editor), `GET/POST
/platform/tenants/{id}/subscription`, `POST
/platform/tenants/{id}/subscription/transition`, `PATCH
/platform/tenants/{id}/subscription/plan` (direct change), `PATCH
/platform/tenants/{id}/subscription/provider` (manual/stripe/razorpay +
references; gateway API keys are env config, never stored), `GET
/platform/plan-requests` + `POST /platform/plan-requests/{id}/approve |
reject`, `GET /platform/tenants/{id}/invoices` (+ `/{invoice_id}/download`),
`POST /platform/tenants/{id}/payments`.

Seeded Super Admin: `platform@signage.cloud` (password via
`SEED_PLATFORM_PASSWORD`, default `Platform@12345`, non-production only).

## 7. Screens

- **Settings › Plan & Billing** (tenant): plan card + status badge, dunning
  banner, pending-request banner, feature grid, invoice table with download,
  request-plan-change/cancel/reactivate. Usage & limits section is
  read-only.
- **Platform** (superuser-only nav item): plan-change-request inbox
  (approve/reject), tenant table with plan/status/device/user counts, a
  per-tenant Manage drawer (edit name/timezone, direct plan change, quota
  overrides, payment provider, invoices with download + record payment),
  create-tenant form, plan cards, and a full plan editor (prices +
  entitlement grid driven by the backend catalogue).
- **Users & Roles › Members** tab: home + guest members, add existing user
  by email with a role, remove guests.
- **Header tenant switcher**: shown only when the user has 2+ organizations.

## 8. New permissions

`billing.view`, `billing.manage`, `members.manage` (all included in the
Organization Administrator system role; `billing.view` in Viewer).

## 9. Tables (migrations 0020 + 0021)

`tenant_users`, `plans`, `plan_entitlements`, `subscriptions`,
`subscription_items`, `subscription_events`, `usage_counters`,
`usage_events`, `invoices`, `payments`, `plan_change_requests`.

## 10. Tests

`backend/tests/test_saas_core.py` (20 tests, PostgreSQL): plans seeding,
plan-change request/approve/reject flow, platform tenant editing + direct
plan change, invoice download + provider management,
platform RBAC + tenant creation, billing surface, device-limit refusal with
the exact spec message, quota-tightening, suspension semantics (growth
blocked, heartbeat/manifest alive), invoice + payment → reactivation,
dunning ladder day 1/8/15 idempotency, legacy no-subscription mode, guest
membership + switch + revocation, membership validations, usage snapshots.
