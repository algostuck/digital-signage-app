# Phase 3 — API Matrix

Conventions unchanged (docs/api-guidelines.md): `/api/v1`, envelope
`{data, meta, errors}`, tenant from principal only, 404 for cross-tenant,
pagination on collections, audit on mutations, rate limits on public/hot
surfaces, Idempotency where retries are expected. Feature-flag check
(`require_feature`) precedes permission check on flagged surfaces. No
existing endpoint changes shape; new player-manifest blocks are additive.

| Method | Endpoint | Auth/Perm (+flag) | Notes | Status |
|---|---|---|---|---|
| POST | /ai/generate/text | content.create + ai | governed by ai_policies; async provider call w/ timeout; records ai_request/output | pending |
| POST | /ai/generate/creative | layouts.manage + ai | structured variant → draft asset/template + governance record | pending |
| POST | /ai/localize | content.create + ai | placeholder/format preservation validated post-generation | pending |
| GET/PUT | /ai/policies | settings.manage + ai | allowed operations, approval routing, provider config ref | pending |
| GET | /ai/requests(/{id}) | content.view + ai | explainability trail (model/template/version/confidence) | pending |
| GET/POST/PATCH/DELETE | /data-sources(/{id}) | settings.manage (write) / layouts.view (read) + dynamic_data | secret-ref only; SSRF-guarded endpoint validation | pending |
| POST | /data-sources/{id}/test | settings.manage | guarded fetch + schema validation dry-run | pending |
| GET | /data-sources/{id}/health | layouts.view | last fetch, validity, cache age | pending |
| POST | /widgets/{id}/bindings | layouts.manage | binds widget → source + transform + fallback | pending |
| GET/POST/PATCH | /decision-policies, /decision-rules | campaigns.manage | deterministic priority, guardrails | pending |
| POST | /decision-rules/preview | campaigns.view | context in → decision + ordered reasons out | pending |
| GET/POST/PATCH | /experiments(/{id}) | campaigns.manage + experiments | allocation validation; stable assignment | pending |
| GET/POST/PATCH/DELETE | /video-walls(/{id}) (+/members) | devices.manage + video_wall | canvas/viewport validation; member uniqueness | pending |
| POST | /video-walls/{id}/sync | devices.control | starts session: epoch marker + tolerance; degraded state surfaced | pending |
| GET/POST/PATCH | /ad-inventory(/{id}) | ads.manage + advertising | slot/hours/rate-card | pending |
| GET/POST/PATCH | /ad-campaigns(/{id}) | ads.manage | booking against availability; approval adapter | pending |
| GET | /reports/ad-performance | reports.view | booked vs delivered; export via 2I engine | pending |
| GET/POST | /edge/bundles (+/{id}/publish) | devices.manage + edge_bundles | signed manifest, expiry, rollout state | pending |
| GET | /edge/metrics | monitoring.view | cache/bandwidth/download queue | pending |
| GET | /fleet-intelligence/anomalies | monitoring.view + fleet_ai | score + evidence | pending |
| POST | /fleet-intelligence/{id}/acknowledge | incidents.manage | human-in-the-loop | pending |
| POST | /fleet-intelligence/{id}/remediation | devices.control | whitelisted commands only; logged | pending |
| GET/POST/PATCH | /sso/providers (+/{id}/test) | settings.manage + sso | OIDC first; secrets by ref; test = metadata/JWKS fetch | pending |
| GET/POST | /connectors (+instances) | webhooks.manage | catalogue + install/config/health | pending |
| GET | /events | webhooks.manage | normalized domain events (paginated) | pending |
| GET/POST/DELETE | /subscriptions | webhooks.manage | event-bus consumers; signed deliveries (2H pattern) | pending |
| GET | /security/devices/{id}/identity | devices.view | identity + credential lifecycle | pending |
| POST | /security/certificates/rotate | settings.manage | rotation sweep trigger; audited | pending |
| GET | /security/policy-violations | settings.manage | central policy engine output | pending |
| GET/POST | /data-exports | reports.export | dataset/schedule/destination; runs via beat | pending |
| GET | /platform/regions | is_superuser | tenant/region/service health; no tenant content | pending |
| GET | /developer/openapi | api_keys.manage + developer_portal | versioned OpenAPI + changelog metadata | pending |
| — | Player manifest additive blocks: sync/bundle/data/ad_slots/bandwidth/prefetch | device token | contract v2, ignored by v1 players | pending |
