# Phase 3 — API Matrix

Conventions unchanged (docs/api-guidelines.md): `/api/v1`, envelope
`{data, meta, errors}`, tenant from principal only, 404 for cross-tenant,
pagination on collections, audit on mutations, rate limits on public/hot
surfaces, Idempotency where retries are expected. Feature-flag check
(`require_feature`) precedes permission check on flagged surfaces. No
existing endpoint changes shape; new player-manifest blocks are additive.

| Method | Endpoint | Auth/Perm (+flag) | Notes | Status |
|---|---|---|---|---|
| POST | /ai/generate/text | content.create + ai_features | governed by ai_policies; deterministic local provider (real providers = config swap); records ai_request/output | **done (3B-1)** |
| POST | /ai/generate/creative | layouts.manage + ai_features | dimension-aware structured variant + governance record (materialization to assets = later slice) | **done (3B-1)** |
| POST | /ai/localize | content.create + ai_features | placeholder/format preservation validated post-generation (rejects damage) | **done (3B-1)** |
| GET/PUT | /ai/policies | settings.manage + ai_features | allowed operations, guardrail banned-terms, approval routing | **done (3B-1)** |
| GET | /ai/requests(/{id}) | content.view | explainability trail (provider/model/template-version/confidence/fallback) | **done (3B-1)** |
| GET/POST/PATCH/DELETE | /data-sources(/{id}) (+PUT /schema) | settings.manage (write) / layouts.view (read) + dynamic_data | env-var token ref only (no secrets stored); SSRF-guarded endpoint validation | **done (3A-2)** |
| POST | /data-sources/{id}/test, /{id}/refresh | settings.manage + dynamic_data | guarded fetch + schema validation dry-run / stored refresh | **done (3A-2)** |
| GET | /data-sources/{id}/health | layouts.view | last fetch, validity, cache age, last-known-good | **done (3A-2)** |
| POST | ~~/widgets/{id}/bindings~~ | layouts.manage | superseded: bindings are per-zone in the canvas (`zone.widget.data_binding` = {source_id, transform}) — richer than widget-global, validated at layout publish/template submit | **done (3A-2, deviation documented)** |
| GET/POST/PATCH/DELETE | /decision-policies (+PUT /{id}/rules replace-set) | campaigns.manage (view: campaigns.view) | deterministic priority, guardrails, external-data conditions | **done (3B-2)** |
| POST | /decision-rules/preview (+GET /decision-log) | campaigns.view | context in → decision + ordered reasons out; bounded auditable log | **done (3B-2)** |
| GET/POST/DELETE | /experiments (+/transition, /{id}/results) | campaigns.manage + experiments (view: campaigns.view) | allocation validation; stable assignment; per-arm results | **done (3B-3)** |
| GET/POST/DELETE | /video-walls(/{id}) (+/members) | devices.manage + video_wall (view: devices.view) | canvas/viewport validation; member uniqueness (one wall per device) | **done (3C-1)** |
| POST | /video-walls/{id}/sync | devices.control | start/stop session: epoch marker + tolerance; degraded state surfaced + incident | **done (3C-1)** |
| GET/POST/PATCH | /ad-inventory(/{id}) | ads.manage + advertising (view: ads.view) | slot/hours/rate-card; device or location scope | **done (3D-1)** |
| GET/POST | /ad-campaigns (+/{id}/cancel) | ads.manage | overlap-refused booking; 2A approval adapter (pending→confirmed) | **done (3D-1)** |
| GET | /reports/ad-performance | reports.view | booked vs delivered vs fill rate; export via 2I engine (report ad-performance) | **done (3D-1)** |
| GET/POST | /edge/bundles (+/{id}/publish) | devices.manage + edge_bundles (view: devices.view) | signed manifest, TTL expiry, supersede-on-publish, rollout state | **done (3C-2)** |
| GET | /edge/metrics | monitoring.view | bundle states, sync coverage, bandwidth policy | **done (3C-2)** |
| GET | /fleet-intelligence/anomalies (+/rules CRUD, /{id}/actions) | monitoring.view + fleet_ai (rules write: settings.manage) | score + evidence + recommendation; hourly detect beat with auto-resolve | **done (3D-3)** |
| POST | /fleet-intelligence/{id}/acknowledge | incidents.manage | human-in-the-loop with action trail | **done (3D-3)** |
| POST | /fleet-intelligence/{id}/remediation | devices.control | whitelisted commands only (restart/clear_cache/refresh_content) via the 1E command queue; logged + audited | **done (3D-3)** |
| GET/POST | /sso/providers (+/test) + public /auth/sso/{org}/login|callback | settings.manage + sso | OIDC; secrets by env ref; signed state; JWKS-verified id_token; claim mapping + auto-provision | **done (3E-1)** |
| GET | /connectors | webhooks.manage | live catalogue over concrete stores (no-DDL decision); entitlement-aware availability | **done (3E-4)** |
| GET | /events, /events/catalogue | webhooks.manage | normalized domain events (paginated, filterable) + type catalogue | **done (3A-1)** |
| GET/POST/PATCH/DELETE | /subscriptions (+/rotate-secret, /{id}/deliveries, /deliveries/{id}/replay) | webhooks.manage | event-bus consumers; signed deliveries (2H pattern) | **done (3A-1)** |
| GET | /security/devices/identities (+/summary) | devices.view (summary: settings.manage) | identity + credential lifecycle, fingerprints only | **done (3E-3)** |
| POST | /security/devices/{id}/rotate | settings.manage | revoke → standard re-registration reissue; audited | **done (3E-3)** |
| GET/POST | /security/policies + /security/policy-violations (+resolve) | settings.manage | declarative age policies; daily sweep opens/self-resolves; never auto-enforced | **done (3E-3)** |
| GET/POST/DELETE | /data-exports (+/{id}/run) + GET /analytics/aggregates|metrics|reconciliation | reports.export (reads: reports.view) | daily-grain aggregates, semantic metrics, reconciliation, scheduled exports via beat | **done (3D-2)** |
| GET | /platform/regions | is_superuser | tenant/region/service health; no tenant content | pending |
| GET | /developer/openapi | api_keys.manage + developer_portal | versioned OpenAPI + changelog metadata | **done (3A-3)** |
| GET/POST | /developer/sandbox (+/simulate-device) | api_keys.manage + developer_portal | idempotent sandbox org + owner membership; simulator via real player pipeline | **done (3A-3)** |
| — | Player manifest additive blocks: data (3A-2), decision (3B-2), experiment (3B-3), sync (3C-1), bundle/prefetch/bandwidth (3C-2) + player GET /player/{id}/bundles/{bid} | device token | contract v2, ignored by v1 players | **partially done** (ad_slots pending 3D-1) |
