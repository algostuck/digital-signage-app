# Phase 2 — Test Plan

Baseline: the full Phase-1 suite (153 tests) must stay green after every
slice — this is the standing regression gate for Login, Organization,
Locations, Devices, Content, Layouts, Playlists, Scheduling, Publishing,
Device sync and Dashboard.

## Per-slice tests (added with each vertical slice)

| Slice | Coverage |
|---|---|
| Approval engine | policy on/off per entity type; maker cannot self-approve (403/422); second approver can; reject returns with comments + revision history; approve → entity transitions; legacy campaign endpoints still work; audit rows for every action; tenant isolation |
| Device ops | dynamic group rule evaluation (tag/location-subtree/manufacturer/status), preview counts, static groups unchanged; bulk action fans out commands to every member (async), partial failure reporting; bulk edit tags/location; screenshots upload→evidence fetch; incident open→ack→resolve, auto-recover on heartbeat |
| OTA | release create (checksum), ring materialization (pilot→10→50→100), stop-on-failure threshold halts later rings, rollback state, device update offered via heartbeat + acked via player endpoint (deviation from command channel: dedicated rollout_devices tracking), evidence — **covered** (test_releases_api.py, 8 tests incl. acceptance #2) |
| Studio | template versions immutable; publish/submit-approval; widget schema validation rejects bad config; binding resolution with fallback; collections ordering — **covered** (test_studio_api.py, 8 tests; plus test_migration_parity.py guarding model/migration drift). Suite runs on SQLite by default and on PostgreSQL via TEST_DATABASE_URL (per-test schema create/drop, NullPool) |
| Campaigns/scheduling | variant target resolution precedence (explicit variant priority, ties by name — deviation from type-based precedence, simpler and user-controlled); manifest picks correct variant; blackout suppresses active campaign in resolver + calendar; monthly recurrence + exception dates in engine unit tests; conflict dry-run endpoint — **covered** (test_advanced_campaigns_api.py, 10 tests incl. SRS acceptance #4) |
| Monitoring | fleet-health rollups match device states; per-tenant thresholds honored by offline detection; storage incident open/dedupe/auto-resolve; version-outdated counting; merged device timeline; threshold RBAC + isolation — **covered** (test_monitoring_api.py, 9 tests) |
| Notifications | rule matching by event+condition; channel fan-out rows; escalation after delay (sweep task, idempotent); email delivered via logging provider; webhook queued → sweep retries → failed after max attempts; wildcard + inactive-rule filtering; RBAC + isolation — **covered** (test_notification_rules_api.py, 8 tests) |
| Integrations | webhook secret shown once; signature verification (HMAC test vector); retry/backoff to dead-letter; replay; API key auth path (X-API-Key) enforces scopes + tenant; revoked/expired keys rejected; last_used updated — **covered** (test_integrations_api.py, 7 tests) |
| Reports | uptime windows math; PoP lifecycle counts reconcile with raw events (acceptance scenario); CSV/XLSX export content correctness — **covered** (test_reports_phase2_api.py, 7 tests incl. acceptance #6; XLSX validated as a zip package with sheet content) |
| Search | cross-module results permission-filtered; saved views CRUD per user — **covered** (test_search_api.py, 5 tests: module presence by permission, tenant isolation, owner-only views, module whitelist, name conflicts) |
| Tenant admin | quota usage math; policy defaults drive thresholds/approval/retention; retention pruning respects floors and is audited — **covered** (test_tenant_admin_api.py, 7 tests: quota enforcement at all three choke points, retention floors, prune sweep + audit evidence, audit-export RBAC, isolation) |

## End-to-end acceptance (SRS §8) — SIGN-OFF (2026-08-29): all six automated AND demonstrated live

| # | Scenario | Automated coverage | Live demonstration |
|---|---|---|---|
| 1 | Dynamic Samsung-in-subtree group → preview → publish → devices reached | test_device_ops_api::test_dynamic_group_preview_and_campaign_publish | 2B E2E: "Samsung Kolkata Fleet" previewed 1 match, created, bulk-commanded |
| 2 | Maker-checker: creator blocked from self-approval; approver approves; deployment starts | test_approvals_api maker-checker tests (both inbox + legacy paths) | 2A E2E: self-approval 422, checker approved with comments |
| 3 | Pilot ring rollout with forced failure → halt at threshold + evidence | test_releases_api::test_pilot_failure_stops_rollout | 2C E2E: release 2.5.0, ring 2 stopped, failure reason + red bar in Update Center |
| 4 | Overlapping campaigns → conflict + deterministic winner pre-publish | test_advanced_campaigns_api conflict dry-run tests | 2E E2E: 32 overlaps reported with winner Store Hours Promo (p60>p55) |
| 5 | Offline/threshold → notification → recovery → incident auto-resolves | test_device_ops_api incident lifecycle + test_monitoring_api storage lifecycle | 2F E2E: 92% storage opened incident, ack via UI, 48% heartbeat auto-resolved |
| 6 | PoP by location/campaign → export → counts reconcile with raw events | test_reports_phase2_api::test_export_csv_reconciles + dimension test | 2I E2E: plays=6/completed=5 reconciled exactly; CSV + XLSX validated |

## Security tests

Cross-tenant probes for every new resource; IDOR on approval/rollout/webhook
ids; API-key privilege escalation attempts; webhook SSRF guard (scheme/host
validation); secrets absent from all responses/logs; rate limits on new
public surfaces.

## Test infrastructure — PostgreSQL only (2L decision)

The suite runs exclusively on PostgreSQL (`digital_app_test`, auto-created;
override via TEST_DATABASE_URL — non-PostgreSQL URLs are rejected). Schema
is built once per run and tests are isolated by TRUNCATE … CASCADE; the
migration-parity test runs the full Alembic chain on a scratch
`digital_app_parity` PostgreSQL database and diffs it against the models.
SQLite has been removed from the toolchain entirely (aiosqlite dependency
dropped). The test environment uses minimum-cost Argon2 parameters so suite
time measures the application, not the KDF (~2s/test; full suite ≈ 9 min).

## Load smoke (2L re-run, Phase-2 backend)

50 devices: fan-out 135ms (Phase-1 baseline 128ms — no regression),
deployment published 50/50; heartbeat/manifest p95 ≈ 2.3s at concurrency 50
on a single dev uvicorn worker (queueing-dominated, matches Phase-1 shape;
production scale-out is horizontal per NFR2-02). The load script now
manages the campaign approval policy around its run (maker-checker aware).
