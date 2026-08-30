# Phase 3 — Architecture

Governing rule (project directive): **extend the existing modular monolith;
introduce infrastructure only where the Phase-3 workload genuinely requires
it.** No Kafka, no Kubernetes, no microservices split, no vector database,
no separate warehouse engine in this phase. Every decision below names the
existing mechanism it reuses.

## 1. Layered target (SRS + master prompt)

```
                 DIGITAL SIGNAGE CLOUD (FastAPI modular monolith)
                                   │
     CONTENT (1D/1F/1G/2D)   DEVICES (1E/2B/2C/2F)   CAMPAIGNS (1H/1I/2E)
                                   │
                          INTELLIGENCE LAYER (new)
        ai/ (providers+governance) · decisioning · anomaly (fleet AI)
        data_platform (aggregates/exports) — all Celery-async, flag-gated
                                   │
                          DISTRIBUTION LAYER (existing, extended)
        pull-based player contract v2 · signed manifests/bundles · adapters
                 LG / Samsung / Android / Windows via capabilities
```

## 2. Module plan (extend > duplicate)

| Concern | Home | Kind |
|---|---|---|
| Feature flags | **SaaS core entitlement engine** (`app/services/entitlements.py`): plan/subscription-driven `require_feature(db, org, key)` — see `docs/SAAS_CORE.md`. Phase-3 features map to entitlement keys (`ai_features`, `dynamic_data`, `experiments`, `video_wall`, `advertising`, `fleet_ai`, `sso`, `white_label`, `developer_portal`, `edge_bundles`) | implemented (pre-Phase-3) |
| Domain event bus | `app/services/events.py` + `domain_events`/`event_subscriptions`/`event_deliveries`; delivery worker clones the proven 2H signed/retry/dead-letter pattern | extension of 2H |
| Data sources | `app/services/data_sources.py` + guarded fetch in `app/integrations/fetch.py`; refresh in maintenance worker | new service, existing worker |
| Dynamic widgets | extend 2D `studio.py` bindings: a widget binding may reference a data source; manifest ships the latest valid snapshot | extension of 2D |
| AI | `app/services/ai/` (provider adapter, governance, operations); `app/integrations/ai_providers.py` (LocalDeterministicProvider default) | new package |
| Decisioning | `app/services/decisioning.py` reusing scheduling context + targeting; hooks into manifest build | new service over 1H/2E |
| Experiments | `app/services/experiments.py`; assignment = stable hash(device_id, experiment_id) honoring allocation | new service over 2E variants |
| Video walls | `app/services/video_walls.py`; sync markers injected by manifest builder | new service over 1E/1I |
| Edge bundles | `app/services/edge.py`; bundle = signed manifest package on the storage adapter; Range support added to local storage | new service over 1D/1I |
| Ads | `app/services/ads.py` (inventory/booking/linkage) + report rows in 2I engine; approval adapter for bookings | new service over 1I/2A/2I |
| Fleet anomalies | `app/services/anomaly.py` beat detector over existing telemetry | new service over 2B/2F |
| SSO | `app/services/sso.py` (OIDC code flow, claim mapping) issuing the existing JWT pair — RBAC untouched | new service beside 1B |
| White label | extend `organization.py` branding + real SMTP provider behind the 2G email adapter | extension |
| Security | `app/services/security_center.py` (identities, rotation sweeps, policies, violations) | new service over 1E/2H |
| Data platform | `app/services/analytics.py` (aggregates) + `data_exports` runner reusing 2I renderers | extension of 2I/2K |
| Developer platform | portal UI over existing api-keys + OpenAPI versions + sandbox provisioning in seed machinery | extension of 2H/1B |

## 3. Async rule
Anything that calls an external system (AI provider, data source, SSO
metadata, event/webhook delivery, exports, aggregation, anomaly scans,
bundle building) runs in Celery or is served from a cached snapshot.
HTTP request paths stay synchronous-control-plane only (SRS §7).

## 4. Data path (SRS §7 separation without a second database)
```
OLTP tables (playback_events, heartbeats, events)
      │  beat aggregation (analytics.py)          │ retention pruning (2K)
      ▼                                           ▼
analytics_aggregates (daily grain)          bounded raw history
      │
      ├── reports/dashboards read aggregates (never raw at scale)
      └── data_exports → files on object storage → external warehouse (customer's)
```
`playback_events` gets a partition-ready key design; actual PostgreSQL
partitioning is applied when measured volume justifies it (documented gate).

## 5. Degradation ladders (never a blank screen)
```
AI:        provider ok → use · low confidence → rules · provider down → deterministic (NFR3-06)
Decision:  decision rules → scheduled resolver (1H) → default playlist/fallback (1G)
Data:      fresh fetch → TTL cache → last-known-good → widget fallback_json (2D)
Wall:      full sync → declared degraded state (+incident) → standalone playback
Bundle:    live manifest → valid unexpired bundle → cached prior manifest
```

## 6. Tenant isolation & flags
Every new table carries organization_id (platform-scoped rows use NULL org
with explicit checks); every endpoint resolves tenant from the principal
(Phase-1 rule); features gate per tenant:
`ai, dynamic_data, experiments, video_wall, advertising, fleet_ai, sso, white_label, developer_portal, edge_bundles`.

## 7. Player contract v2 (additive)
Existing v1 verbs unchanged. Manifest adds optional blocks:
`sync{wall_id, viewport, session, start_epoch_ms, tolerance_ms}`,
`bundle{id, url, signature, expires_at}`, `data{binding_id: snapshot}`,
`ad_slots[…]`, `bandwidth{windows, concurrency}`, `prefetch[…]`.
Players report `contract_version`; v1 players ignore unknown blocks.

## 8. Explicit non-goals this phase (SRS §12)
No proprietary TV OS, no programmatic ad exchange, no payment settlement,
no arbitrary third-party code execution, no autonomous destructive AI
actions, no physical multi-region deployment (residency = metadata + export
policy until infrastructure exists).
