# Phase 3 — Screen Matrix

Standards (unchanged from Phase 2): every screen ships loading / empty /
error / success / permission-denied / validation states, pagination +
filtering where applicable, confirmation on destructive actions, no mock
data in completed workflows. Feature-flagged screens hide their nav entry
when the tenant flag is off.

| ID | Screen | Route (existing shell) | Permissions | API deps | Components | Status |
|---|---|---|---|---|---|---|
| P3-01 | AI Content Studio | /design → AI tab (new) | content.create + ai flag | /ai/generate/text, /ai/localize, /ai/policies | prompt form, guardrail banner, version compare, approval handoff | pending |
| P3-02 | AI Variant Manager | /design → AI tab section | layouts.manage | /ai/generate/creative, /ai/requests | variant grid, dimension picker, approve/route | pending |
| P3-03 | Data Source Manager | /settings → Data sources (new section) or /data (new page) | settings.manage | /data-sources (+test/health), schemas | connector form, secret-once banner (2H pattern), health chips | pending |
| P3-04 | Dynamic Widget Designer | /design designer widget panel (EXT of 2D panel) | layouts.manage | /widgets bindings, /data-sources | source select, mapping/transform editor, fallback preview | pending |
| P3-05 | Decisioning Rules | /campaigns → Decisioning tab (new) | campaigns.manage | /decision-policies, /decision-rules/preview | rule rows, priority order, guardrails, preview panel | pending |
| P3-06 | Experiment Manager | /campaigns → Experiments tab (new) | campaigns.manage + experiments flag | /experiments | allocation sliders, cohort table, results | pending |
| P3-07 | Video Wall Manager | /devices → Walls tab (new) | devices.manage + video_wall flag | /video-walls (+members) | wall grid editor, device assignment, viewport map | pending |
| P3-08 | Wall Preview / Control | wall detail modal | devices.control | /video-walls/{id}/sync, state | member health, start/stop, degraded banner | pending |
| P3-09 | Ad Inventory | /ads (new page) → Inventory tab | advertising flag + ads.manage (new perm) | /ad-inventory | slot table, hours editor, rate-card ref | pending |
| P3-10 | Ad Campaign Manager | /ads → Bookings tab | ads.manage | /ad-campaigns | booking form, targeting, frequency, PoP link | pending |
| P3-11 | Ad Performance Report | /reports → Ads tab (EXT) | reports.view | /reports/ad-performance (+export) | booked-vs-delivered table, export buttons (2I pattern) | pending |
| P3-12 | Edge Delivery Dashboard | /monitoring → Edge tab (EXT) | monitoring.view | /edge/metrics | cache/bandwidth tiles, queued downloads | pending |
| P3-13 | Offline Bundle Manager | /devices → Bundles tab (new) | devices.manage + edge_bundles flag | /edge/bundles (+publish) | bundle builder, expiry, rollout state (2C pattern) | pending |
| P3-14 | Fleet Intelligence | /monitoring → Intelligence tab (EXT) | monitoring.view + fleet_ai flag | /fleet-intelligence/anomalies (+ack/remediate) | anomaly list w/ score + evidence drilldown, recommendation card | pending |
| P3-15 | AI Operations Rules | /monitoring → Intelligence settings | settings.manage | anomaly_rules CRUD | sensitivity sliders, guardrail toggles | pending |
| P3-16 | White-Label Settings | /settings → Branding section (EXT) | organization.manage + white_label flag | /organization branding, domain, email identity | theme editor, domain status, email preview | pending |
| P3-17 | Enterprise SSO | /settings → SSO section (new) | settings.manage + sso flag | /sso/providers (+test) | provider form, claim mapping, test connection | pending |
| P3-18 | Regional Platform Admin | /platform (new, superuser) | is_superuser | /platform/regions | tenant/region table, residency metadata | pending |
| P3-19 | Integration Catalog | /settings → Integrations (EXT of 2H section) | webhooks.manage | /connectors | catalogue cards, install/configure flow | pending |
| P3-20 | Event Bus / Subscriptions | /settings → Integrations (EXT) | webhooks.manage | /events, /subscriptions | event type picker, consumer status, delivery log (2H pattern) | pending |
| P3-21 | Security Center | /security (new page) | settings.manage | /security/* | identity table, rotation actions, violations, auth anomalies | pending |
| P3-22 | Analytics Data Export | /reports → Exports tab (EXT) | reports.export | /data-exports | dataset picker, schedule, destination, run state | pending |
| P3-23 | Developer Portal | /developer (new page) | api_keys.manage + developer_portal flag | /developer/openapi, api-keys (2H), sandbox | docs viewer, key management, contract versions, changelog | pending |
| P3-24 | Platform Operations | /platform → Operations tab (superuser) | is_superuser | /platform/regions, queues/health | service status, queue depth, worker health, incidents | pending |
