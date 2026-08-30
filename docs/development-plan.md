# Development Plan — Phase 1

Requirements: SRS/FRD §18 (workstreams P1-01..P1-12), §24 (sprint sequence).
Method: vertical slices — DB -> migration -> model -> repository -> service ->
API -> tests -> frontend integration -> UI -> validation. No disconnected
frontend mockups.

## Milestone status

| Milestone | Scope | Status |
|---|---|---|
| **1A Foundation** | Repo structure, backend+frontend scaffold, Docker dev env, PostgreSQL, Redis, Alembic, env config, structured logging, error handling, API versioning, health endpoints, CI workflow, test harness | **Done** (2026-08-29; verified: 9 backend tests, migration up/down/up cycle, frontend typecheck + build) |
| **1B Authentication** | Login/logout/refresh (rotating refresh tokens with reuse detection), Argon2 password hashing, RBAC permission guard, tenant context, users/roles/permissions APIs, seed (catalogue + system roles + demo tenant), login/users/roles UI | **Done** (2026-08-29; verified: 41 backend tests incl. RBAC + tenant isolation, lint clean, migration cycle, frontend build, full browser E2E: login → create user → assign role → viewer read-only). Deferred within scope: password reset (needs email infra), auth audit events (land with 1J audit slice), login rate limiting (readiness only) |
| **1C Organization / Locations** | Org settings (get/patch, IANA tz validation), location CRUD with materialized path, tree/children/descendants endpoints, move with cycle prevention + subtree path rewrite, archive/restore rules, per-tenant type dictionary, key=value tags (replace-set), effective-timezone inheritance, Location Tree + Details UI, Org Settings UI | **Done** (2026-08-29; verified: 59 backend tests, lint, migration cycle, frontend build, browser E2E: tree render → details → tag add → create child → move under new parent) |
| **1D Content** | Upload sessions (policy-validated, presigned PUT), assets + immutable versions, processing pipeline (validate → checksum → metadata → thumbnail → READY/FAILED), storage abstraction (S3/MinIO + local dev backend with HMAC-signed URLs), folders, tags, search/filters, draft/publish/archive lifecycle, signed download URLs, Celery media task (inline in dev), Content Library/Upload/Details UI | **Done** (2026-08-29; verified: 72 backend tests, lint, migration cycle, frontend build, live E2E: API upload → thumbnail in library grid → detail modal → publish). Deferred within scope: video metadata/transcode (needs FFmpeg worker; pipeline slot exists), multipart/resumable upload, malware-scan hook |
| **1E Devices** | Registry with lifecycle (pending/active/rejected/decommissioned), enrollment-key registration + approval + one-time device credential (hash-stored, revocable), player gateway foundation (register/heartbeat/capabilities/command poll+ack via X-Device-Token), heartbeat history, derived online/warning/offline, groups + bulk assign, capability registry, remote command queue, location assignment + subtree device filter, Device List/Details/Groups UI with enrollment key reveal and approve/reject | **Done** (2026-08-29; verified: 87 backend tests, lint, migration cycle, frontend build, live E2E: simulated player enroll → approve → token → heartbeat → capabilities, UI approval + detail view). Deferred: WebSocket/MQTT push channel (pull model per ADR-005), device events feed (1J) |
| **1F Layouts** | Layout CRUD with mutable draft canvas + immutable published versions (normalized zone rows per version), versioned canvas JSON schema (schema_version 1, generic zones, 10 content types), publish-time asset-binding validation (tenant + READY), preview/preflight endpoint, templates (create-from-layout, clone, 3 seeded starters), screen designer UI (drag/move/resize, properties panel, content binding, publish) | **Done** (2026-08-29; verified: 99 backend tests, lint, migration cycle, frontend build, browser E2E: create from ticker template → select zone → bind image asset → publish with live preview). Deferred: snapping/alignment guides, layer panel, zone rotation UI (schema supports it) |
| **1G Playlists** | CRUD, ordered items over assets/layouts (add / replace-set PUT / position reorder / remove with compaction), per-item duration (image default 8s, natural length for video/audio) + transition + enable/disable, loop flag, fallback playlists with cycle detection, publish → immutable versions (disabled items excluded, layout versions pinned), Playlists + Editor UI | **Done** (2026-08-29; verified: 112 backend tests, lint, migration cycle, frontend build, browser E2E: create → add asset + layout items → reorder → publish v1). Deferred: drag-and-drop reordering (arrow-based now), per-item effective/expiry dates (campaign scheduling covers the primary case in 1H) |
| **1H Scheduling** | Timezone-aware evaluation engine (pure functions shared with the 1I manifest builder): date ranges, day-of-week recurrence, daily wall-clock windows incl. midnight-wrapping, schedule-tz overriding target-tz, priority resolver (campaign > schedule > recency); schedule CRUD with IANA/weekday/date validation; calendar expansion endpoint with equal-priority conflict detection; minimal campaign shell (name/priority/playlist/layout, full lifecycle enum staged for 1I); Campaigns + Schedule Calendar UI with conflict highlighting | **Done** (2026-08-29; verified: 132 backend tests incl. 13 engine unit tests, lint, migration cycle, frontend build, browser E2E: two campaigns with overlapping windows → 7 conflicts flagged in week view). Deferred to 1I/1J: campaign approval/publish transitions, auto-expiry worker (expired flag computed now) |
| **1I Publishing** | Targeting (location subtree / device / group / tag, exclusions-win, effective-target resolution + preview), approval workflow (draft→pending→approved→published, pause/resume, permission-split manage/approve/publish), deployments with frozen target snapshots, versioning + supersede-on-republish, queued fan-out (Celery task, inline in dev), per-device ack (idempotent) with PARTIAL/PUBLISHED/FAILED aggregation, retry/cancel, player manifest (SRS §9.1: resolved campaign via the shared scheduling engine, layout canvas, playlist versions, fallback, schedules for offline evaluation, assets with sha256 + signed URLs), heartbeat sync_required, Campaign Editor + Publishing UI | **Done** (2026-08-29; verified: 141 backend tests incl. golden §20.2 E2E, lint, migration cycle, frontend build, live E2E: UI target→approve→publish → 3 simulated players sync manifests, download assets, ack → deployment 3/3 Published) |
| **1J Dashboard & Ops** | Audit trail (server-side records for login, user/device/campaign/deployment/content/layout/playlist/location actions, with actor/IP/request-id from request context; filterable API+UI), notifications (registration/approval/deployment-failure + offline-detection beat task with dedupe; inbox with read state), monitoring summary + device health feed, player event ingestion (device_events + playback proof-of-play), reports (deployments per campaign, playback per asset, device health per location), real Dashboard/Notifications/Audit/Reports pages | **Done** (2026-08-29; verified: 147 backend tests, lint, PostgreSQL migration chain, live E2E on Postgres: dashboard stats, playback report 10 plays/2 devices, offline sweep → warning notification, audit trail with actor+IP). **Also: backend switched from SQLite dev DB to local PostgreSQL 18 (digital_app_dev); all 10 migrations validated up/down/up on Postgres** |

| **P1-12 Hardening** | Rate limiting (login/register per IP, heartbeat/events per device, uploads; fixed-window, configurable, 429 envelope), OWASP secure headers (+ HSTS in prod, no-store on API responses, signed URLs stay cacheable), security lint (ruff S) in CI with production fail-fast on default/short JWT_SECRET, load smoke script (scripts/load_smoke.py) with client backoff, production runbook (docs/runbook.md) | **Done** (2026-08-29; verified: 153 backend tests, live load smoke 50 devices: fan-out 128 ms, 250 concurrent heartbeats, deployment → published 50/50. The load test exposed and led to fixing a real race: concurrent acks recomputed deployment status from stale snapshots — now serialized per deployment via row lock + fresh aggregate) |

### Phase 2 (enterprise operations) — all slices Done 2026-08-29

| Slice | Scope | Status |
|---|---|---|
| 2A Approval engine | Polymorphic maker-checker workflow (campaigns + templates), per-tenant policies, immutable action trail, approval inbox UI | **Done** |
| 2B Device operations | Dynamic rule groups + preview, bulk group commands + bulk edit, screenshot evidence, incident engine with auto-recovery | **Done** |
| 2C OTA updates | Release registry, staged rollout rings with stop-on-failure + rollback, pull-based signed package offers, Update Center UI | **Done** |
| 2D Content studio | Template versioning through the approval engine, schema-driven widget framework, data-variable bindings, asset collections | **Done** |
| 2E Campaigns/scheduling | Audience variants, blackout windows, monthly recurrence + exception dates, conflict dry-run with deterministic winner, month calendar | **Done** |
| 2F Monitoring | Fleet-health rollups (org/location/group), per-tenant thresholds (enforced), storage incidents, device event timeline, Incident Center | **Done** |
| 2G Notifications | Event rules → in-app/email/webhook channels, delivery evidence, idempotent escalation | **Done** |
| 2H Integrations | HMAC-signed webhook subscriptions with backoff + replayable dead-letter, scoped API keys (hash-only) with X-API-Key auth path | **Done** |
| 2I Reporting | Proof-of-play by dimension, campaign analytics, heartbeat-window uptime, CSV/XLSX exports (dependency-free OOXML) | **Done** |
| 2J Search | Permission-filtered global search, personal saved views, device bulk-edit UI | **Done** |
| 2K Tenant admin | Quotas (enforced at creation choke points) + usage, retention policies with compliance floors + audited pruning, audit export + evidence links | **Done** |
| 2L Hardening | All 6 SRS §8 acceptance scenarios automated + demonstrated live, sweeps wired into beat, load smoke (no fan-out regression), **PostgreSQL-only test infrastructure**, 240-test regression sign-off on PostgreSQL | **Done** |

Detailed per-slice records: docs/PHASE_2_IMPLEMENTATION_STATUS.md.

First delivery focus (per agreed approach): **Foundation + Auth + Multi-tenancy
+ Location hierarchy**, hardened before Content/Devices build on top.

## Definition of done (per feature)

Database + migration + model + repository + service + API + validation +
authorization + tests (unit, API, tenant-isolation) + frontend integration +
error handling + documentation update (this folder).

## Golden end-to-end scenario (SRS §20.2)

Org -> hierarchy (Country>State>City>Store>Floor) -> 10 simulated devices ->
upload image+MP4+text -> 3-zone layout -> playlist -> campaign targeting City
(descendants) -> schedule 09:00–18:00 Asia/Kolkata -> publish -> fan-out +
per-device ack -> simulated player manifest+signed URLs -> heartbeat +
playback event -> dashboard reflects state -> audit trail complete.
Automate this as the capstone integration test of Phase 1.

## Working agreements

- SRS/FRD is the baseline spec; deviations require an ADR in docs/decisions/.
- No LG/Samsung-specific logic in core; capability-driven design.
- No mock data in production screens once the real API exists.
- Migrations are never skipped or edited after merge; new migration per change.

### SaaS Core (pre-Phase-3 foundation) - Done 2026-08-30

| Slice | Scope | Status |
|---|---|---|
| SaaS core | Multi-tenancy memberships (tenant_users, guest roles, /auth/memberships + switch-tenant with server-side membership validation), data-driven plans + entitlements engine (19-key catalogue, subscription_items overrides, min-combine with 2K quotas), subscriptions (trialing/active/past_due/grace_period/suspended/cancelled/expired; monthly/yearly/custom), invoices + manual payment provider, dunning ladder beat (0/7/14 days) with suspension semantics that never interrupt cached playback, usage counters + snapshot beat, entitlement enforcement at all growth choke points incl. exact "limit reached... Upgrade your subscription." refusals, X-API-Key api_access gate + metering, /platform Super Admin surface (tenants/plans/subscriptions/payments), Plan & Billing screen, Platform console, Members tab, header tenant switcher, seeded Starter/Business/Professional/Enterprise plans + platform admin + demo Enterprise subscription | **Done** (migration 0020 up/down/up on PG; 17 new tests in test_saas_core.py; docs/SAAS_CORE.md) |

| SaaS core refinement | Plan changes approval-gated (plan_change_requests, migration 0021): tenant requests upgrade/downgrade -> Super Admin verifies manual payment -> approves on /platform inbox -> plan activates; Super Admin direct plan change + tenant info editing; quota overrides moved to Super Admin only (tenant usage view read-only); suspended tenants cannot self-reactivate without payment; printable HTML invoice downloads (tenant + platform); payment provider per subscription (manual/stripe/razorpay refs only, gateway keys stay env config); Platform UI plan editor + request inbox + Manage drawer | **Done** (2026-08-30; 27 tests in saas+tenant-admin suites; live UI verification) |
