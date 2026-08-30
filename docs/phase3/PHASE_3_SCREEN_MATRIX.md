# Phase 3 — Screen Matrix

Standards (unchanged from Phase 2): every screen ships loading / empty /
error / success / permission-denied / validation states, pagination +
filtering where applicable, confirmation on destructive actions, no mock
data in completed workflows. Feature-flagged screens hide their nav entry
when the tenant flag is off.

| ID | Screen | Route (existing shell) | Permissions | API deps | Components | Status |
|---|---|---|---|---|---|---|
| P3-01 | AI Content Studio | /design → AI Studio tab | content.create + ai_features | /ai/generate/text, /ai/localize | copy/localize forms, recommendation labeling + confidence badges, guardrail + approval-pending banners | **done (3B-1)** |
| P3-02 | AI Variant Manager | /design → AI Studio tab section | layouts.manage | /ai/generate/creative, /ai/requests | dimension picker, structured variant preview, explainability trail | **done (3B-1)** |
| P3-03 | Data Source Manager | /settings → Data sources (new section) | settings.manage | /data-sources (+test/refresh/health/schema) | connector form (env-var token ref — no secrets stored), health chips, test with sample | **done (3A-2)** |
| P3-04 | Dynamic Widget Designer | /design designer widget panel (EXT of 2D panel) | layouts.manage | /widgets bindings, /data-sources | source select, transform (path/fields/limit) editor, fallback note | **done (3A-2)** |
| P3-05 | Decisioning Rules | /campaigns → Decisioning tab | campaigns.manage | /decision-policies, /decision-rules/preview, /decision-log | policy list + activate toggle, ordered-rules JSON editor, dry-run preview with reasons, decision log | **done (3B-2)** |
| P3-06 | Experiment Manager | /campaigns → Experiments tab | campaigns.manage + experiments flag | /experiments (+transition, results) | create form (campaign/variant/allocation), lifecycle actions, per-arm results table | **done (3B-3)** |
| P3-07 | Video Wall Manager | /devices → Walls tab | devices.manage + video_wall flag | /video-walls (+members) | wall list, grid-cell device assignment (auto viewports), delete | **done (3C-1)** |
| P3-08 | Wall Preview / Control | /devices → Walls manage drawer | devices.control | /video-walls/{id} (+/sync) | member health chips, start/stop sync, session + tolerance, degraded banner | **done (3C-1)** |
| P3-09 | Ad Inventory | /ads (new page) → Inventory tab | advertising flag + ads.manage (new perm) | /ad-inventory | slot table, hours editor, rate-card ref | pending |
| P3-10 | Ad Campaign Manager | /ads → Bookings tab | ads.manage | /ad-campaigns | booking form, targeting, frequency, PoP link | pending |
| P3-11 | Ad Performance Report | /reports → Ads tab (EXT) | reports.view | /reports/ad-performance (+export) | booked-vs-delivered table, export buttons (2I pattern) | pending |
| P3-12 | Edge Delivery Dashboard | /devices → Bundles tab (metrics tiles; documented deviation) | monitoring.view | /edge/metrics | coverage/queued tiles, bandwidth window | **done (3C-2)** |
| P3-13 | Offline Bundle Manager | /devices → Bundles tab | devices.manage + edge_bundles flag | /edge/bundles (+publish) | bundle builder (scope + TTL), publish/supersede, sync coverage | **done (3C-2)** |
| P3-14 | Fleet Intelligence | /monitoring → Intelligence tab (EXT) | monitoring.view + fleet_ai flag | /fleet-intelligence/anomalies (+ack/remediate) | anomaly list w/ score + evidence drilldown, recommendation card | pending |
| P3-15 | AI Operations Rules | /monitoring → Intelligence settings | settings.manage | anomaly_rules CRUD | sensitivity sliders, guardrail toggles | pending |
| P3-16 | White-Label Settings | /settings → Branding section (EXT) | organization.manage + white_label flag | /organization branding, domain, email identity | theme editor, domain status, email preview | pending |
| P3-17 | Enterprise SSO | /settings → SSO section (new) | settings.manage + sso flag | /sso/providers (+test) | provider form, claim mapping, test connection | pending |
| P3-18 | Regional Platform Admin | /platform (new, superuser) | is_superuser | /platform/regions | tenant/region table, residency metadata | pending |
| P3-19 | Integration Catalog | /settings → Integrations (EXT of 2H section) | webhooks.manage | /connectors | catalogue cards, install/configure flow | pending |
| P3-20 | Event Bus / Subscriptions | /settings → Integrations (EXT) | webhooks.manage | /events, /subscriptions | event type picker, consumer status, delivery log (2H pattern) | **done (3A-1)** |
| P3-21 | Security Center | /security (new page) | settings.manage | /security/* | identity table, rotation actions, violations, auth anomalies | pending |
| P3-22 | Analytics Data Export | /reports → Exports tab (EXT) | reports.export | /data-exports | dataset picker, schedule, destination, run state | pending |
| P3-23 | Developer Portal | /developer (new page) | api_keys.manage + developer_portal flag | /developer/openapi, sandbox (+simulate-device); keys stay in Settings→Integrations (2H) | docs links, sandbox panel with enrollment key + one-time device token, contract versions + changelog | **done (3A-3)** |
| P3-24 | Platform Operations | /platform → Operations tab (superuser) | is_superuser | /platform/regions, queues/health | service status, queue depth, worker health, incidents | pending |
