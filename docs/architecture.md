# Technical Architecture — Digital Signage Cloud Platform

Status: Phase-1 baseline, still the shape of the system. Phases 2 and 3
added modules on top of it without changing it — see
[PHASE_2_ARCHITECTURE.md](PHASE_2_ARCHITECTURE.md), [SAAS_CORE.md](SAAS_CORE.md)
(multi-tenancy, plans, entitlements), [TV_PREVIEW_ARCHITECTURE.md](TV_PREVIEW_ARCHITECTURE.md),
[ORGANIZATION_ADMIN_DASHBOARD_ARCHITECTURE.md](ORGANIZATION_ADMIN_DASHBOARD_ARCHITECTURE.md)
and [PLAYER_API_CONTRACT.md](PLAYER_API_CONTRACT.md). Source of truth for
requirements: [Digital_Signage_Cloud_SRS_FRD.md](Digital_Signage_Cloud_SRS_FRD.md).
Architecture changes must be recorded as ADRs in [decisions/](decisions/).
The full documentation set is indexed in [README.md](README.md).

## 1. System overview

Modular monolith backend + enterprise admin SPA + background workers, designed
manufacturer-neutral so future LG webOS / Samsung Tizen / Android / Windows
players consume one common Player Gateway API.

```text
React + TypeScript Admin Portal (frontend/)
        |
   HTTPS REST /api/v1  (WebSocket-ready)
        |
FastAPI Application (backend/app)
        |
+-------+----------+----------------+
|                  |                |
PostgreSQL       Redis         S3-compatible Object Storage
(metadata,     (queue/cache/       (media binaries, thumbnails)
source of       locks)                  |
truth)            |                   CDN
                Workers (Celery)
                  |
     media processing, deployment fan-out,
     offline detection, notifications
        |
   Player Gateway  /api/v1/player/*
        |
  Platform adapters (future native clients)
```

## 2. Backend architecture

- **Style**: modular monolith (ADR-001). One deployable API app + worker
  process + beat scheduler sharing the same codebase.
- **Stack**: Python / FastAPI / SQLAlchemy 2.x (async) / PostgreSQL / Alembic /
  Redis / Celery / Pydantic v2.
- **Layering** (per module, no business logic in route handlers):

```text
api (routers)  ->  schemas (Pydantic DTO)  ->  services (business logic)
                                               |
                                          repositories (DB access)
                                               |
                                          models (SQLAlchemy)
workers (background jobs)  reuse services/repositories
```

- **Domain modules** (`backend/app/` packages, grown per vertical slice):
  `auth, organization, users, roles, locations, devices, content, assets,
  layouts, playlists, campaigns, schedules, publishing, player (gateway),
  monitoring, analytics, notifications, audit, storage, settings, integration`.

## 3. Multi-tenancy (ADR-002)

- Single database, shared schema; every tenant-owned row carries
  `organization_id` (directly or via provable parent).
- Tenant context is resolved server-side from the authenticated principal —
  never trusted from the client. `X-Tenant-ID` may only *select among* the
  principal's authorized organizations.
- All repository queries are tenant-scoped; service layer re-validates
  ownership on any cross-entity reference (e.g. campaign -> playlist).
- Tenant-isolation tests are mandatory for every module.

## 4. Location hierarchy (ADR-003)

- Single generic `locations` table, adjacency list (`parent_id`) +
  **materialized path** column for efficient subtree/ancestor queries.
  No fixed-depth tables (no country/state/city tables).
- `location_types` is a per-tenant dictionary, not a schema concept.
- Move operations rewrite the subtree path within a transaction and validate
  against cycles.

## 5. Content & storage (ADR-004)

- Binaries live in S3-compatible object storage under
  `tenant/<org_id>/content/<asset_id>/...`; PostgreSQL stores metadata only.
- Upload flow: create upload session -> client uploads (presigned) ->
  complete -> async pipeline: VALIDATE -> SCAN-HOOK -> METADATA -> PROCESS ->
  THUMBNAIL -> READY (state machine on `asset_versions.processing_status`).
- Delivery via short-lived signed URLs / CDN.

## 6. Layout engine

- Generic `Layout -> LayoutVersion -> Zones` model. Zones are JSON
  (x, y, width, height, z_index, rotation, style, content_binding).
  No hard-coded 1/2/3/6-screen types.
- Published layout versions are immutable; the designer saves a versioned
  JSON document that is exactly what the player manifest embeds.

## 7. Campaign / schedule / publishing (ADR-005)

- Playlist = WHAT, Schedule = WHEN, Target = WHERE, Campaign binds them with
  priority + approval state.
- Publishing is asynchronous: publish -> deployment row (target snapshot
  materialized and frozen) -> queue -> worker fan-out -> per-device status ->
  device acknowledgement. States: DRAFT, READY, QUEUED, PUBLISHING, PARTIAL,
  PUBLISHED, FAILED, CANCELLED. Retryable, idempotent (Idempotency-Key),
  observable, resumable.
- Scheduling stores UTC + IANA timezone; evaluation happens in the target
  device/location timezone.

## 8. Player Gateway

Manufacturer-neutral contract under `/api/v1/player/*`:
register, token, manifest, asset URL, heartbeat, events, commands + ack,
capabilities, deployment ack. Capability-based device model — no LG/Samsung
logic in core. Offline-first: manifest + assets are cacheable; players resume
with heartbeat -> sync -> download -> ack -> upload events.

## 9. Cross-cutting

- **API conventions**: see [api-guidelines.md](api-guidelines.md).
- **Security**: JWT auth, RBAC permission checks per endpoint, tenant scoping
  at repository level, hashed credentials, signed storage URLs, server-side
  audit events, rate-limit-ready. Never trust tenant/user/ownership from the
  client.
- **Observability**: structured JSON logs with request/correlation ID
  (middleware + contextvar), health endpoints (`/health`, `/health/ready`),
  worker job metadata (id, status, timings, retries), metrics-ready.
- **Time**: UTC persistence everywhere; IANA timezone identifiers on
  organization/location/device.
- **Identifiers**: UUIDv4 primary keys.
- **Config**: 12-factor environment configuration (`.env` locally, secrets
  never committed; `.env.example` documents keys).

## 10. Deployment topology (dev)

`docker-compose.yml` runs: postgres, redis, api (uvicorn), worker (celery).
Local non-Docker dev: venv + uvicorn against local/containerized Postgres;
tests run against SQLite (aiosqlite) with the same models via a portable
type layer (GUID/JSON type decorators).

## 11. Scale posture (1K -> 100K devices)

- Heartbeats/events are append-only, retention-configurable, index-covered.
- Deployment fan-out is queued and batched; no synchronous device I/O in API.
- Pagination mandatory on collections; N+1 avoided via explicit loading.
- Redis caching for hot reads (manifests, dictionaries) when justified.
- Modules with independent load (player gateway, media processing) are
  extractable later without data-model redesign.
