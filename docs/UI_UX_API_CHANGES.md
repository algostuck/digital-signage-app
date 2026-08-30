# UI/UX API Changes

Per the modernization brief (§76): the initiative is UI/UX-only, and any
backend adjustment a frontend issue genuinely requires is documented here
first. This file is the complete list — anything not listed is untouched.

## 1. `GET /api/v1/entitlements` (new, additive)

- **Why the frontend needs it:** audit finding #5 — the frontend had no
  way to know the tenant's plan entitlements, so plan-locked features
  (SSO, experiments, video walls, …) rendered as broken/empty surfaces
  instead of a consistent "upgrade to unlock" state. The only existing
  entitlement read (`GET /billing/subscription`) requires `billing.view`,
  which most users (e.g. Viewer role) don't have — UI gating must work
  for every authenticated member.
- **What it is:** a read-only, permission-free (authenticated org members
  only) projection of `entitlements.get_effective()`:
  `{ plan_code, plan_name, values: {feature: bool|int|null, ...} }`.
- **What it is not:** an enforcement surface. Server-side enforcement at
  the resource choke points is unchanged; this endpoint only informs UI
  affordances.
- **Files:** `backend/app/api/v1/billing.py` (one route),
  `backend/tests/test_saas_core.py::test_entitlements_endpoint_needs_no_billing_permission`.

No other backend change has been made or is planned for this initiative.
