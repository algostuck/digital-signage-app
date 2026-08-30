# Phase 3 — Initiation Report (Audit before code)

Date: 2026-08-30 · Source of truth: `docs/Digital_Signage_Cloud_Phase_3_SRS_FRD.md`
(converted from the .docx of the same name). This report is the required
first deliverable: repository audit, Phase-1/2 verification and gap analysis.
No Phase-3 code has been written before this document.

## 1. Current technology stack (verified from the repository)

| Layer | Technology | Notes |
|---|---|---|
| API | FastAPI + Uvicorn, `/api/v1`, envelope `{data, meta, errors}` | 22 route modules |
| ORM/DB | SQLAlchemy 2 async + asyncpg → **PostgreSQL 18** (dev `digital_app_dev`, test `digital_app_test`, parity `digital_app_parity`) | PostgreSQL-only everywhere (Phase-2L decision); 19 migrations, head **0019**, parity-tested against models |
| Jobs | Celery + Redis: queues media / publishing / maintenance; beat schedule (offline detection 2m, rule deliveries 1m, webhook deliveries 1m, escalations 5m, retention daily) | All sweeps DB-backed + idempotent |
| Storage | Adapter: S3/MinIO (prod) / LocalStorage with HMAC-signed URLs (dev) — ADR-004 | Email uses the same adapter pattern (logging provider in dev) |
| AuthN/Z | JWT access + rotating refresh (reuse detection), Argon2id, RBAC catalogue (40 permissions) + system roles, X-API-Key scoped principals, per-tenant approval policies | Tenant context only from the principal |
| Frontend | React 18 + TypeScript + Vite + Tailwind v4, React Router, TanStack Query | 14 modules, 37 components/pages, envelope-aware client with single-flight refresh + binary download helper |
| Infra | docker-compose (postgres, redis, minio, api, worker), backend Dockerfile, GitHub Actions CI, structured logging w/ request-id, rate limiting, security headers | Local dev runs without Docker |
| Testing | pytest (asyncio) — **240 tests, PostgreSQL-only**, truncate isolation, migration-parity guard, load-smoke script | Final Phase-2 sign-off: **240/240 on PostgreSQL, 9m55s** |

Notable absences (relevant to Phase 3): no AI/ML libraries, no Kafka, no
separate analytics store, no OIDC/SAML client library, no CDN config. httpx
is present (used for webhook delivery) and is the outbound-HTTP foundation.

## 2. Phase-1 status

**Completed** (verified by the passing 240-test suite, golden §20.2 E2E and
per-milestone live E2Es): foundation, auth/RBAC/tenancy, locations
(materialized path), content pipeline + storage, devices + player gateway
(pull-based, ADR-005), layouts (draft→immutable versions), playlists,
scheduling engine (timezone-aware, shared cloud/player), publishing
(frozen snapshots, idempotent acks), dashboard/ops (audit, notifications,
monitoring, reports), P1-12 hardening (rate limits, headers, load smoke,
runbook).

**Partial / deferred within scope** (none blocks Phase 3; two intersect it):
| Item | Where it lands |
|---|---|
| Password reset (needs email infra) | With P3-M08 email identity work |
| Video metadata/transcode (FFmpeg worker slot exists) | Optional alongside P3-M01 creative work |
| Multipart/resumable upload + **resumable download** | **Required by NFR3-03** → scheduled into P3-C (edge) |
| WebSocket/MQTT push channel | Deliberately pull-based (ADR-005); P3 sync uses scheduled markers, not push |
| Malware-scan hook | P3-M10 policy engine slot |

**Missing**: nothing that Phase-1 scope promised.

## 3. Phase-2 status

**Completed — all 12 slices** (2A approvals … 2L hardening), signed off
2026-08-29: migrations 0011–0019 applied + parity-verified, all six SRS §8
acceptance scenarios automated AND demonstrated live, load smoke without
fan-out regression, **final regression 240/240 on PostgreSQL**. Detailed
per-slice evidence: `docs/PHASE_2_IMPLEMENTATION_STATUS.md`.

**Partial / deferred within Phase-2 scope** (with Phase-3 landing spots):
| Item | Phase-3 dependency |
|---|---|
| PDF export; scheduled report exports; column selection in builder | P3-M11 `data_exports` implements scheduling; PDF stays out (SRS never re-requires it) |
| P2-01 dashboard "enterprise" extension (fleet health lives at /monitoring) | P3-14/P3-24 screens revisit the dashboard |
| Uptime maintenance exclusions | P3-M11 semantic metrics define uptime canonically |
| Email = logging provider | P3-M08 white-label email identity requires a real SMTP adapter (config swap, interface exists) |
| Weather/data variables are placeholder tokens | P3-M02 data sources make them real |

**Missing**: nothing that Phase-2 scope promised. Phase 3 is NOT built on a
broken foundation.

## 4–7. Phase-3 requirements vs existing implementation

Requirement-by-requirement matrix (SRS ref → existing → gap → change →
acceptance): `PHASE_3_GAP_ANALYSIS.md`. Summary:

**Already supported (extend, don't build)**
- Widget framework w/ schema-driven config, bindings whitelist, fallbacks (2D) → P3-M02 rendering half exists; only the *data source* half is new.
- Deterministic scheduling/priority resolver + campaign variants + targeting (1H/2E) → P3-M03's deterministic layer exists; decision rules/experiments wrap it.
- PoP events + report/export engine (1J/2I) → P3-M05 billing aggregates and P3-M11 exports reuse it.
- Webhook delivery machinery: signing, retries, dead-letter, replay (2H) → P3-M09 event bus generalizes the same tables/worker pattern.
- API keys w/ scopes + hash-only storage (2H) → P3-M12 developer platform base.
- Incidents, thresholds, telemetry history, fleet rollups (2B/2F) → P3-M07 anomaly detection has its signal store and its UI patterns.
- Approval engine w/ pluggable entity adapters (2A) → P3-M01 AI outputs and P3-M05 ad campaigns become new adapter entity types — governance for free.
- branding_json + settings_json tenant stores, quotas, retention (2K) → P3-M08 white-label + feature flags slot in.
- Signed URLs + storage abstraction + offline-first manifest (1D/1I) → P3-M06 bundles = signed manifest packaging over the same primitives.

**Partial** — decisioning context (device/location/time exist; external
context needs P3-M02), sandbox tenant (seed machinery exists, needs an
isolated flow), OpenAPI (FastAPI generates it; needs versioned publication).

**Missing (genuinely new)** — AI provider abstraction + governance records;
data-source connectors w/ SSRF-guarded fetch, schema validation, cache;
experiments; video walls + sync markers + player contract v2 fields; ad
inventory/booking/linkage; offline bundles; anomaly engine; OIDC SSO;
connector catalogue + domain event bus; device certificates + policy engine;
analytics aggregates + scheduled exports; developer portal UI.

## 8. Architecture changes

Documented in `PHASE_3_ARCHITECTURE.md`. Core decisions (anti-over-engineering, per project directive):
1. **Modular monolith stays.** No microservices, no Kafka, no Kubernetes, no vector DB, no separate warehouse engine. Every P3 workload fits the existing FastAPI + Celery + PostgreSQL shape at the target scale we can actually validate locally.
2. **Intelligence layer = new service modules** (`ai/`, `decisioning`, `anomaly`) behind provider adapters — exactly the LocalStorage/LogEmail pattern: deterministic local providers in dev/test, real providers as config swaps. AI optional + flag-gated (NFR3-06).
3. **Event/data path**: a `domain_events` table + the proven delivery-worker pattern (2H) becomes the event bus; high-volume analytics live in *aggregate tables* filled by beat tasks + the existing retention pruning — separation of OLTP/analytics by table + workload, not by database (SRS §7 says "separated", the report engine reads aggregates not raw events; a physical warehouse is a deployment concern the `data_exports` job feeds).
4. **Player contract v2** — additive manifest fields (sync markers, bundles, data snapshots, ad slots) with `contract_version` negotiation; never breaking v1 players (NFR3-08).
5. **Feature flags** — implemented pre-Phase-3 as the SaaS-core entitlement engine (`docs/SAAS_CORE.md`): plan/subscription-driven `entitlements.require_feature(db, org, key)` next to `require_permissions()`. Phase-3 modules gate on entitlement keys (`ai_features`, `dynamic_data`, `experiments`, `video_wall`, `advertising`, `fleet_ai`, `sso`, `white_label`, `developer_portal`, `edge_bundles`).

## 9. Database changes
Planned migrations 0021–0030 (0020 is the SaaS core; one per sub-phase slice, additive, parity-guarded): `PHASE_3_DATABASE_CHANGES.md`.

## 10. API changes
32 SRS endpoints mapped, all under `/api/v1`, same envelope/RBAC/idempotency rules: `PHASE_3_API_MATRIX.md`. No breaking changes to existing endpoints; the public/partner surface gets explicit versioned OpenAPI publication (P3-INT-103).

## 11. Frontend changes
24 screens mapped to the existing module/tab system (most extend existing pages; genuinely new pages: AI Studio, Data Sources, Decisioning, Experiments, Video Walls, Ads, Edge, Fleet Intelligence, SSO/White-label, Developer Portal, Platform Ops): `PHASE_3_SCREEN_MATRIX.md`.

## 12. AI architecture — `PHASE_3_AI_ARCHITECTURE.md`
Provider adapter (generate/transform/localize) + governance tables (`ai_policies/ai_requests/ai_outputs` storing model ref, template version, confidence, decision — never secrets/prompts with secrets) + approval-engine adapter for outputs + deterministic fallback everywhere.

## 13. Device/player changes — `PHASE_3_DEVICE_ARCHITECTURE.md`
Contract stays pull-based; additive v2: `sync` block (wall id, viewport, start marker, tolerance), `bundle` block (signed offline bundle ref), `data` block (widget data snapshots), `ad_slots`. Capability-driven; zero manufacturer branches in core.

## 14. Security changes — `PHASE_3_SECURITY_MODEL.md`
SSRF-guarded outbound fetch (scheme/host allowlist, no redirects to private ranges, response caps); secret-ref storage for connector credentials; OIDC token validation without weakening RBAC (SSO answers *who you are*; RBAC still answers *what you may do*); device identity/certificate lifecycle tables; central policy evaluation + violations; AI data-isolation rules.

## 15. Infrastructure changes
None required to start. Optional-when-justified: CDN in front of MinIO/S3 (config), SMTP provider (config), OIDC lib (`authlib` or `pyjwt`+JWKS — one small dependency), partitioning of `playback_events` (PostgreSQL native, when volume demands).

## 16. Performance risks
Playback/telemetry volume vs OLTP (mitigation: aggregates + retention + partition-ready schema); decisioning on the manifest hot path (mitigation: per-device decision cached in manifest build, deterministic + cheap); data-source fetch storms (mitigation: per-source TTL cache + stale-while-revalidate, fetch in worker not request path); wall sync fan-out (small N per wall).

## 17. Data/analytics risks
Double-counting in ad billing aggregates (mitigation: link table unique per playback_event, reconciliation report — SRS acceptance #4); aggregate drift vs raw (mitigation: recompute-window design + reconciliation test).

## 18. Recommended implementation order (sub-phases, mirroring SRS §11 + repo dependencies)
```
P3-A  Foundation: feature flags → domain event bus → data sources + dynamic widgets → developer platform (OpenAPI/sandbox/portal)
P3-B  Intelligence: AI provider + governance → AI studio → decisioning rules → experimentation
P3-C  Playback: video walls + sync → edge bundles + prefetch/bandwidth + resumable download
P3-D  Monetization/analytics: ad inventory/booking/PoP linkage → billing aggregates → analytics aggregates + scheduled exports → fleet anomaly engine
P3-E  Global/enterprise: SSO (OIDC) → white-label/custom domain/email → device identity + policy engine + security analytics → regional metadata + platform ops → hardening & sign-off
```
Each slice: migration → models → services → APIs → tests → frontend → live E2E → docs → full PostgreSQL regression (the Phase-2 cadence, unchanged).

## 19. Dependencies
2H webhook machinery → event bus; 2D widgets → dynamic data; 2E variants → experiments; 2I PoP → ads; 2F incidents/telemetry → anomalies; 2A approval adapters → AI + ads governance; 2K settings_json → flags/white-label; fleet groups → walls & bundles.

## 20. Risks
| Risk | Mitigation |
|---|---|
| AI over-engineering / provider lock-in | Adapter + deterministic local provider; flag-gated; core works with AI off (NFR3-06) |
| SSRF via data sources/connectors | Central guarded fetch util, allowlist policy, tested with hostile fixtures |
| Sync overclaiming | Scheduled markers + declared tolerance budget; degraded state; never claim frame-accuracy (SRS §7) |
| Scope explosion (12 modules) | Sub-phase gates with per-slice sign-off; out-of-scope list (§12) enforced |
| Regression of P1/P2 | Full PostgreSQL suite per slice (now 9m55s) + migration parity + acceptance re-runs |

## 21. Rollback strategy
Per-slice: feature flag off (tenant or platform) → behavior reverts instantly; migrations are additive with tested downgrades (up/down/up gate per slice); player contract v2 blocks are additive so v1 players ignore them; worker tasks are idempotent so disabling a beat entry is safe.

## 22. Acceptance criteria
The seven SRS §9 scenarios, each to be automated AND demonstrated live (Phase-2 discipline), plus: full P1+P2 regression green per slice, security review checklist (§14 doc) per slice, migration parity green, all 24 screens resolved in the screen matrix, every FR row in the gap analysis carrying a final status.
