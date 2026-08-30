# Phase 2 — Gap Analysis

Source of truth: [Digital_Signage_Cloud_Phase_2_SRS_FRD.md](Digital_Signage_Cloud_Phase_2_SRS_FRD.md)
Audited against the Phase-1 implementation (migrations 0001–0010, 153 tests, PostgreSQL 18).
Status legend: ✅ satisfied · 🟡 partial (extend) · ❌ missing (new build)

## A. What Phase 1 already provides

Stack: FastAPI + SQLAlchemy 2 (async) + PostgreSQL + Alembic + Celery/Redis +
React/TS/Vite/Tailwind. Modular monolith (ADR-001), shared-schema tenancy with
repository-level scoping (ADR-002), materialized-path locations (ADR-003),
S3/local storage abstraction (ADR-004), pull-based publishing with frozen
deployment snapshots (ADR-005).

Modules: auth/RBAC (34-permission catalogue), org settings, unlimited location
hierarchy + tags, device registry (enrollment/approval/credentials, static
groups, capabilities, command queue, heartbeat history), content CMS (upload
sessions, versions, processing pipeline, folders/tags), layout engine
(draft/immutable versions, generic zone JSON, templates-as-canvas-copies),
playlists (versions, fallback chains), campaigns (priority, lifecycle enum,
schedules with tz-aware engine, calendar + equal-priority conflicts),
targeting (location subtree/device/group/tag + exclusions), publishing
(deployments, per-device ack w/ row-lock aggregation, retry/cancel), player
gateway (register/token/manifest/heartbeat/commands/events/acks), monitoring
summary + device feed, audit trail, notifications inbox, playback events +
3 reports, rate limiting, secure headers, load-smoke, runbook.

## B. Phase-2 requirements already satisfied (no/minor work)

| Requirement | Phase-1 coverage |
|---|---|
| P2-DEV-003 diagnostics (partial ✅) | last_heartbeat, heartbeat history, storage/network/current payload, player/OS version, capabilities, command history, device_events table |
| P2-SCH-001 calendar | /calendar with day expansion + conflict flags (needs month view UI polish only) |
| P2-SCH-003 timezone | UTC storage + IANA tz at org/location/device; engine resolves in target tz |
| P2-SCH-004 conflict detection (core) | equal-priority overlap detection + deterministic resolver (winner = priority → schedule priority → recency) |
| P2-CAM-002 inheritance (core) | subtree targeting with include_descendants; exclusions win |
| P2-CAM-003 priority | deterministic 1–100 priority in resolver + manifest |
| P2-MON-004 incident timeline (data) | device_events + heartbeat history exist; UI timeline needed |
| P2-RPT-001 proof of play (foundation) | playback_events ingestion + per-asset report |
| P2-RPT-002 delivery analytics | deployment per-device states + per-campaign report |
| P2-AUD-001 audit explorer (core) | filterable audit API + UI (actor/entity/action/date) |
| Maker-checker *permission split* | campaigns.manage / campaigns.approve / campaigns.publish already separate |

## C. Partial functionality — extend, do not duplicate

| ID | Gap | Extension plan |
|---|---|---|
| P2-DEV-001 | Groups are static only | Add `group_type` + `rule_json` to device_groups; dynamic membership evaluated by the existing targeting resolver; preview endpoint |
| P2-DEV-002 | Commands are per-device | Bulk action endpoint fans out over resolved group members via existing command queue (async, batched) |
| P2-APP-001..004 | Campaign transitions exist but: no approval records/comments, no maker-checker enforcement, no policies, templates not covered | Generalized approval engine (approval_policies/requests/actions) with entity adapters; existing campaign endpoints delegate into it (backward compatible) |
| P2-CNT-001 | Templates are single canvas copies, no versions/approval | Add template_versions (immutable, like layouts); wire into approval engine |
| P2-SCH-002 | Recurrence = weekly day-of-week only | Add monthly (day-of-month) + exception dates to the schedule model & engine |
| P2-CAM-004 | No blackout windows | `kind: play|blackout` on schedules; blackout suppresses in resolver + calendar |
| P2-MON-002 | Thresholds are global settings | Per-tenant threshold overrides in org policy defaults (P2-TNT-003) |
| P2-NTF-001..003 | Fixed notification triggers, in-app only | notification_rules (event→condition→channels) + escalation + email/webhook channels over an internal event dispatch |
| P2-TNT-001..003 | Org settings has name/tz/locale/branding_json | Add quotas usage visibility + policy defaults (approval, retention, thresholds, playback) in settings_json |
| P2-RPT-004 | No exports | CSV + XLSX export service for supported reports (PDF deferred, documented) |
| P2-SRC-003 | Bulk assign group members only | Bulk update endpoint: tags/group/location for device sets |
| P2-AUD-002/003 | Payloads contain ids but no typed links; no retention | entity deep-links in UI; retention pruning task driven by tenant policy |
| P2-RPT-001 | Playback lacks scheduled/delivered/downloaded/started/completed/failed distinction | Extend playback ingestion status vocabulary + deployment-linked delivery states; report reconciles both |

## D. Missing functionality — new builds

| ID | Feature |
|---|---|
| P2-DEV-004/005 | Player releases (package registry) + staged rollout rings with stop-on-failure + rollback |
| P2-CNT-002/003 | Widget framework: catalogue, schema-driven config, versions, fallback; dynamic data-variable bindings |
| P2-CNT-004 | Asset collections |
| P2-CAM-001 | Campaign variants (creative per location/device-class/tag) + variant selection in manifest |
| P2-MON-001 | Fleet-health rollup dashboard (org/location/group/device) |
| P2-MON-003 | Device screenshots (player upload → storage → evidence view) |
| P2-14 screen | Incidents (open/ack/resolved, auto-recover transition) — modeled on device_events + incidents table |
| P2-RPT-003 | Device uptime report from heartbeat windows |
| P2-17 screen | Report builder (dimension/filter/column selection; scheduled export deferred to the maintenance queue) |
| P2-SRC-001/002 | Global search across modules; saved views |
| P2-INT-001/003 | Webhook subscriptions + signed deliveries with exponential backoff + dead-letter |
| P2-INT-002 | Scoped API keys (hash-stored, expiry, revocation, last-used) + API-key auth path |

## E. Architecture changes

- **Approval engine** (new domain module `approvals`): polymorphic
  approval_requests over campaigns/templates; adapters per entity; existing
  campaign transition endpoints preserved as thin delegates.
- **Internal event dispatch**: a small in-process `events.emit(type, payload)`
  in the service layer feeding (a) notification-rule evaluation and
  (b) webhook delivery enqueue. No message broker beyond existing Celery.
- **Webhook worker**: new Celery queue `integrations`; HMAC-signed POSTs,
  exponential backoff, dead-letter state, delivery history rows.
- **API-key auth**: second credential path in `api/deps.py`
  (`X-API-Key`) resolving to a tenant principal with scoped permissions —
  reuses `require_permissions` unchanged.
- **Screenshots**: reuse the storage abstraction; player gets a signed PUT via
  a screenshot-upload endpoint; evidence rows link device→asset key.
- **OTA**: releases reference a package asset; rollout batches materialize
  ring membership; players learn about updates via the existing command
  channel (`UPDATE_PLAYER` command + manifest field) — manufacturer-neutral.
- **Manifest**: additive fields only (variant resolution, blackout state,
  player_release hint). Existing players remain compatible.
- **Exports**: report service already separates queries; add exporters
  (csv stdlib, xlsx via openpyxl) streaming from the same service layer.
- **No new infrastructure**: same Postgres/Redis/Celery/storage; no
  microservices, no search engine (global search = per-module indexed SQL).

## F. Risks

| Risk | Mitigation |
|---|---|
| Breaking existing campaign approval flow | Keep `/campaigns/{id}/submit-approval|approve|reject` endpoints; they create/act on approval_requests internally; tests from Phase 1 must stay green |
| Manifest changes break simulated/real players | Additive JSON fields only; golden E2E + player tests pinned |
| Dynamic group resolution cost at publish | Resolution uses existing indexed queries; snapshot still frozen at publish (no behavior change) |
| Schedules table change | Additive columns (`kind`, `recurrence_json` extension, `exception_dates`) with server defaults; engine handles absent fields |
| Permission catalogue growth | Seed is idempotent and updates system roles in place; new codes added to catalogue + role specs |
| Webhook secrets leakage | secret stored hashed/encrypted-ref, returned only once at creation; never logged |
| Email channel needs SMTP | Pluggable channel with console/log provider in dev; SMTP settings documented, no hard dependency |
| Playback/event volume | Append-only + indexed; retention pruning task; aggregates via GROUP BY (no per-row Python loops) |
| Audit immutability vs retention | Pruning is the only permitted deletion path, policy-driven, itself audited |
| Regression risk overall | Full Phase-1 suite (153 tests) runs in CI; regression checklist in PHASE_2_TEST_PLAN.md |
