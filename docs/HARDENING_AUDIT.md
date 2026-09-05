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
list.

### UI pass: what each role is shown

Every top-level page was loaded in the browser as Amit (Viewer), Priya
(Content Manager) and Rahul (Device Manager) in the seeded Reliance tenant,
and every action control in the page body (buttons, icon buttons,
dropdown triggers) was listed and compared with the role's permission
codes from `/roles`.

| Page | Viewer | Content Manager | Device Manager |
|---|---|---|---|
| Content | read only | Upload, New folder, Archive folder | read only |
| Design / Playlists | read only | New layout, New playlist | read only |
| Campaigns / Schedule | read only | New campaign, Archive, New schedule, Delete | read only |
| Approvals | read only (API refuses the inbox: 403) | read only | read only |
| Publishing | read only | read only | Cancel, Retry failed |
| Devices | Save view (saved views are per-user, no permission) | Save view | Show enrollment key, Save view |
| Player Updates | "requires releases.manage" state | same | New release |
| Developer | "requires api_keys.manage" state | same | same |
| Users, Settings, Security, Audit, Notifications, Reports, Monitoring, Ads, Locations | read only | read only | read only |

No control rendered for a role whose API would refuse it. The pages that a
role may open without holding the page's permission (Player Updates,
Developer) show a clear "you need X" state instead of an empty or broken
page. The tab-overflow "…" antd renders on tabbed pages is not an action.

Not covered by this pass: secondary tabs (device groups, video walls,
templates, widgets, roles, members, notification rules), row-level
drawers, the playlist editor and the screen designer — the designer hides
its editing controls behind `layouts.manage` in code, the others are
covered by the module tests.

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

## 4. Subscription & entitlements

`audit_entitlements.py` runs on the revived `e2e-audit` tenant — nothing in
the demo tenants is touched — and checks the whole chain
plan → entitlement → usage → limit → feature access. 85 checks, 0 failures
after the fixes below.

| Scenario | Behaviour verified |
|---|---|
| Feature not in plan (Business): AI, SSO, video walls, experiments, edge bundles, fleet rules, developer portal, advertising, white label | Refused with `'<feature>' is not included in the Business. Upgrade your subscription.`; the integration catalogue marks SSO unavailable |
| Device limit reached | Platform quota tightened to what is in use → next registration refused with `Device limit reached (n/m)`; a decommissioned screen frees its seat (answers J3) |
| User limit reached | `User limit reached (n/m)` |
| Storage limit reached | A 5 MB upload is refused with the storage message; a 64 KB upload within the remaining headroom is accepted |
| Quota overrides cleared | Limits fall back to the plan (Business: 100 devices) |
| Suspended / cancelled | Cannot create campaigns, register devices, open uploads, add users or publish — each refusal names the status (`Subscription is suspended: cannot publish campaigns. Renew or reactivate…`). Players still fetch manifests and heartbeat: screens are never blanked over billing |
| Grace period / past due | Growth allowed; players unaffected |
| Expired → renewed | Growth blocked while expired; renewal assigns a new subscription and growth resumes |
| Upgrade to Professional | Video walls open, AI on, device limit 500 |
| Downgrade to Starter | Features close again with the plan named; device limit 10; over-limit registration refused with the numbers; proof of play and analytics refused |
| API keys | A key can be created on any plan (management is a permission); using it on Starter is refused with `'api_access' is not included`; the same key works on Business |

The refusals are the messages the UI shows verbatim (`message.error(err.message)`
on every mutation), and Settings › Plan & usage reads the same live usage
(`/billing/subscription`) the limits are computed from.

### Findings

| # | Finding | Status |
|---|---|---|
| E1 | **An expired subscription turned the tenant into unrestricted "legacy mode".** `current_subscription` skipped expired rows, so `get_effective` saw no subscription and lifted every limit and feature gate, and growth actions were allowed. | Fixed — `latest_subscription` (any status) now drives entitlements and growth checks: an expired tenant keeps its plan's limits and is blocked from growth until it renews; billing, platform and dashboard read the expired subscription instead of "none". Test `test_expired_subscription_blocks_growth_and_keeps_plan`. |
| E2 | **`proof_of_play` and `advanced_analytics` were UI-only gates.** A Starter tenant could call `/reports/proof-of-play`, `/reports/playback`, `/reports/campaign-performance`, `/analytics/*` and `/data-exports` directly. | Fixed — `require_entitlement(key)` route guard added to those routes (alongside `require_permissions`); the Reports page wraps the same tabs in `EntitlementGuard`. Test `test_reports_follow_plan_entitlements`. |
| E3 | `/billing/usage` (the metered snapshot list) is empty for a tenant until the hourly usage snapshot has run. The plan page does not use it — it reads live counts from `/billing/subscription` — so this only affects API consumers. | Open (minor). |

## 5. Player API contract — frozen

`docs/PLAYER_API_CONTRACT.md` freezes the device-facing surface the cloud
already serves: registration and the one-time token, capabilities,
manifest (shape, signed-URL lifetime, `manifest_version`), deployment
acknowledgement, heartbeat (and what its response tells the player to do
next), commands, screenshots, player updates, event batches for proof of
play and operational events, prefetch bundles, timings, error handling and
the normative offline behaviour. Anything that changes a meaning in it
needs a new prefix or manifest version.

## 6. Player Simulator — a real player in the browser

**Devices › Player Simulator** (`frontend/src/modules/simulator/`) is the
executable form of the contract and the tool for cloud-to-device testing
before any native client exists. It:

- registers with the tenant's enrollment key (prefilled for users who may
  read it), waits for approval, and keeps the device token it is issued
  once — stored per serial, never a user session;
- reports capabilities, fetches the manifest with `X-Device-Token` and
  renders it through the same renderer as the operator's TV preview;
- heartbeats on the server's interval (or every 10 s in fast mode), re-syncs
  when the heartbeat says so, acknowledges every pending deployment, polls
  and acknowledges commands (`refresh_content`, `reboot`, `clear_cache`,
  display / volume; `screenshot` is acknowledged as unsupported);
- reports one proof-of-play row per item shown, batched and replayed if
  the report fails, plus `APP_STARTED` operational events;
- shows the contract activity live: heartbeats, syncs, plays reported,
  deployments and commands acknowledged, queued events, and a log.

Verified 2026-09-05 in the Reliance tenant: register → pending → approved
from the page → token → bootstrap → `refresh_content` command round trip →
a campaign published to the simulated screen → heartbeat `sync_required`
→ manifest v1 → deployment acknowledged (Publishing shows *published,
1/1*) → content on screen → proof of play shows 3 plays, 100 % completion
→ device decommissioned → the simulator's next call is refused and it
shows the token-revoked state. Nothing was left behind.

## 7. Client demo journey

`docs/CLIENT_DEMO_GUIDE.md` — one controlled tenant (Reliance Retail), the
presenter accounts, a 10-minute preparation checklist (seed refresh,
audits green, a live simulator screen on a second display), the 20-minute
story Dashboard → Map → Device → Content → Designer → Playlist → Campaign →
Schedule → Approval → Preview → Publish → live screen → Monitoring →
Proof of play → Analytics, what to do when something goes wrong, and the
clean-up.

## Next gates

8. UX polish pass, 9. performance, 10. observability, 11. production
   security review, 12. CI/CD, 13. documentation freeze.
6. UX polish, performance, observability, production security review,
   CI/CD, documentation freeze — in that order.
