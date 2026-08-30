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
| GET/POST/PATCH | /ad-inventory(/{id}) | ads.manage + advertising | slot/hours/rate-card | pending |
| GET/POST/PATCH | /ad-campaigns(/{id}) | ads.manage | booking against availability; approval adapter | pending |
| GET | /reports/ad-performance | reports.view | booked vs delivered; export via 2I engine | pending |
| GET/POST | /edge/bundles (+/{id}/publish) | devices.manage + edge_bundles (view: devices.view) | signed manifest, TTL expiry, supersede-on-publish, rollout state | **done (3C-2)** |
| GET | /edge/metrics | monitoring.view | bundle states, sync coverage, bandwidth policy | **done (3C-2)** |
| GET | /fleet-intelligence/anomalies | monitoring.view + fleet_ai | score + evidence | pending |
| POST | /fleet-intelligence/{id}/acknowledge | incidents.manage | human-in-the-loop | pending |
| POST | /fleet-intelligence/{id}/remediation | devices.control | whitelisted commands only; logged | pending |
| GET/POST/PATCH | /sso/providers (+/{id}/test) | settings.manage + sso | OIDC first; secrets by ref; test = metadata/JWKS fetch | pending |
| GET/POST | /connectors (+instances) | webhooks.manage | catalogue + install/config/health | pending |
| GET | /events, /events/catalogue | webhooks.manage | normalized domain events (paginated, filterable) + type catalogue | **done (3A-1)** |
| GET/POST/PATCH/DELETE | /subscriptions (+/rotate-secret, /{id}/deliveries, /deliveries/{id}/replay) | webhooks.manage | event-bus consumers; signed deliveries (2H pattern) | **done (3A-1)** |
| GET | /security/devices/{id}/identity | devices.view | identity + credential lifecycle | pending |
| POST | /security/certificates/rotate | settings.manage | rotation sweep trigger; audited | pending |
| GET | /security/policy-violations | settings.manage | central policy engine output | pending |
| GET/POST | /data-exports | reports.export | dataset/schedule/destination; runs via beat | pending |
| GET | /platform/regions | is_superuser | tenant/region/service health; no tenant content | pending |
| GET | /developer/openapi | api_keys.manage + developer_portal | versioned OpenAPI + changelog metadata | **done (3A-3)** |
| GET/POST | /developer/sandbox (+/simulate-device) | api_keys.manage + developer_portal | idempotent sandbox org + owner membership; simulator via real player pipeline | **done (3A-3)** |
| — | Player manifest additive blocks: data (3A-2), decision (3B-2), experiment (3B-3), sync (3C-1), bundle/prefetch/bandwidth (3C-2) + player GET /player/{id}/bundles/{bid} | device token | contract v2, ignored by v1 players | **partially done** (ad_slots pending 3D-1) |
