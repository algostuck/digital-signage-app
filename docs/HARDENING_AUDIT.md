# Product Hardening Audit

The hardening cycle that follows feature development: every gate below is
a **script that runs against the live API** with the seeded Indian demo
tenants, so it can be re-run before every client demo and after every
change. Results here are from 2026-09-05 on the local development stack.

| Gate | Script | Result |
|---|---|---|
| 1. End-to-end product journey | `backend/scripts/audit_e2e_journey.py` | 178 steps, 0 failures |
| 2. Role-based access (API) | part of the journey script | 12 checks across Viewer / Content Manager / Device Manager, all correct |
| 3. Multi-tenant isolation | `backend/scripts/audit_tenant_isolation.py` | 239 probes denied, 0 leaks (one hole found and fixed) |

Both scripts print PASS/FAIL per step, write a JSON report with
`--report`, and exit non-zero on any finding.

## 1. End-to-end journey

`audit_e2e_journey.py` plays the full story twice:

1. **A fresh tenant from the platform console.** Platform Admin creates
   the tenant with its owner → assigns a Business subscription (14-day
   trial) → owner signs in, entitlements resolve, the empty dashboard
   renders zeros rather than errors → locations (region → city → store)
   → two players register, are approved, receive tokens, are assigned to
   the store → a PNG is uploaded through the signed URL and published →
   a two-zone layout is drafted and published → a playlist with the
   layout and the asset is published → a campaign bound to both targets
   the store subtree, gets an all-day Asia/Kolkata schedule, is submitted
   and approved → publish creates a deployment for exactly the two
   screens → each player fetches its manifest (campaign, ticker zone,
   downloadable asset URL), acknowledges, heartbeats, reports four
   completed plays, receives and acknowledges a queued reboot → the
   deployment reads *published, 2/2 acknowledged* → the operator's TV
   preview shows the same campaign → proof of play counts the plays;
   playback, uptime, campaign-performance, deployment and location
   reports, analytics aggregates, monitoring summary and the executive
   dashboard (online count includes the new screens) all answer → the
   audit trail records the publish.
2. **The same organisation-side journey inside Reliance Retail**, under
   Kolkata, among 130 seeded devices and 22 campaigns. Here the tenant has
   maker-checker enabled, so the script verifies that Arjun (submitter)
   is refused and Sneha (Campaign Approver) approves — the product
   behaviour, not a shortcut. Everything it creates is removed afterwards
   (schedule, campaign, playlist, layout, asset archived, device
   decommissioned, location deleted) and the fleet count is checked.

The audit tenant (`e2e-audit`) is archived at the end; the archived
owner can no longer sign in. The next run revives and reuses it, so
repeated audits do not accumulate tenants.

### Findings from the journey

| # | Finding | Status |
|---|---|---|
| J1 | `POST /platform/tenants` and `POST /platform/plans` answered `200` where every other create in the API answers `201`. | Fixed — both return 201; tests updated. |
| J2 | `GET /analytics/aggregates` requires `date_from`/`date_to` with no default range, unlike the reports endpoints. | Open (minor; the UI always sends a range). |
| J3 | Decommissioned devices stay in the fleet list and total. This is by design (audit history), but the entitlement audit (gate 4) must confirm they do not count against the device limit. | Carried to gate 4. |

## 2. Role-based access

Checked with three freshly created users in the audit tenant. Each row is
an actual request, not a UI observation.

| Role | Can | Cannot |
|---|---|---|
| Viewer | read campaigns, devices | create a campaign (403), send device commands (403), reach `/platform/*` (403) |
| Content Manager | create a playlist (201) | send device commands (403), create users (403) |
| Device Manager | send device commands (201) | create a campaign (403), publish a campaign (403) |

`/auth/me` exposes each user's permission set, which is what the UI's
`hasPermission` gating reads — so the API and the UI decide from the same
list. The UI-side pass (buttons that render for roles that cannot execute
them) is tracked separately in the UX polish gate.

Existing pytest coverage: `tests/test_rbac.py` (viewer read-only, no-role
denial, content manager cannot manage users) and per-module
`*_rbac_and_isolation` tests.

## 3. Multi-tenant isolation

`audit_tenant_isolation.py` reads the live OpenAPI document (339 routes),
harvests one real id per collection from Tenant B (BharatMart) and calls
every id-addressed route as Tenant A's administrator (Reliance), then the
reverse. Mutating routes are sent minimal valid bodies so the probe
reaches the handler's tenant check rather than stopping at schema
validation. It also verifies that every list endpoint returns only the
caller's `organization_id`, that tenant principals are refused on every
`/platform/*` route, and it probes **relational** access — foreign ids
inside otherwise valid bodies:

- campaign with another tenant's `playlist_id` / `layout_id`
- campaign targets and target preview naming another tenant's devices and locations
- playlist item with another tenant's `asset_id`
- device-group membership with another tenant's device
- schedule for another tenant's campaign
- device reassignment into another tenant's location

For collections the demo data leaves empty (asset collections, decision
policies, fleet rules, video walls, data exports, edge bundles) it creates
a throwaway record in the victim tenant, probes it — including `DELETE` —
and removes it.

### Result

239 probes **denied** (403/404), 0 leaks, 0 server errors. 16 probes stay
unresolved in the BharatMart→Reliance direction because BharatMart's
Business plan does not include fleet rules, video walls or edge bundles
and the demo data has no anomalies, rollouts, policy violations, ad
bookings or open upload sessions; each of those modules has its own
isolation test in `backend/tests`.

### Findings

| # | Finding | Status |
|---|---|---|
| T1 | **`POST /campaigns/{id}/targets` and `POST /campaigns/{id}/variants` accepted another tenant's device, location, group and tag ids.** Resolution already filtered by organisation, so a foreign id could never reach another tenant's screens, but the API stored a dangling cross-tenant reference and reported success. | Fixed — `targeting.validate_targets` rejects any target that does not exist in the caller's tenant with 404, for campaigns and variants. Regression test `test_campaign_targets_cannot_reference_another_tenant` in `tests/test_tenant_isolation.py`. |

Every other relational probe was already refused: playlists reject a
foreign asset, campaigns reject a foreign playlist/layout, schedules
reject a foreign campaign, device groups ignore foreign devices, and
devices cannot be moved into a foreign location.

## How to run

With the API up on port 8000 and the demo data seeded:

```bash
cd backend && .venv/Scripts/python scripts/audit_tenant_isolation.py --report isolation.json
```

```bash
cd backend && .venv/Scripts/python scripts/audit_e2e_journey.py --report journey.json
```

Add `--keep` to the journey to leave the audit tenant and its records in
place for inspection. Both scripts back off on the login rate limiter.

## Next gates

4. Subscription & entitlement behaviour (limits, expiry, grace, upgrade /
   downgrade, and *why* something is unavailable in the UI).
5. Player API contract freeze and the signage player simulator.
6. UX polish, performance, observability, production security review,
   CI/CD, documentation freeze — in that order.
