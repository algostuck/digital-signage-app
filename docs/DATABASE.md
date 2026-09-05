# Database

PostgreSQL 16, SQLAlchemy 2 (async, asyncpg), Alembic migrations. One
database, one schema, every tenant-owned row carries `organization_id`.

| | Where |
|---|---|
| Entity model and per-migration table catalogue | [domain-model.md](domain-model.md) |
| Multi-tenancy strategy (shared schema, `organization_id` everywhere) | [decisions/ADR-002-multi-tenancy-strategy.md](decisions/ADR-002-multi-tenancy-strategy.md) |
| Location hierarchy (materialised path) | [decisions/ADR-003-location-hierarchy.md](decisions/ADR-003-location-hierarchy.md) |
| Publishing snapshots | [decisions/ADR-005-device-sync-and-publishing.md](decisions/ADR-005-device-sync-and-publishing.md) |
| Phase-2 / Phase-3 additions | [PHASE_2_DATABASE_CHANGES.md](PHASE_2_DATABASE_CHANGES.md), [SAAS_CORE.md](SAAS_CORE.md) §9 |

## Migrations

37 revisions, `backend/migrations/versions/0001…0036` (plus the
Phase-3 set), applied with `alembic upgrade head`. Rules:

- Forward-only in shared environments; every migration must be
  backward-compatible with the previous application version for the
  length of a deploy (add column → deploy code → drop old column later).
- CI runs `upgrade head → downgrade base → upgrade head` on every change
  and a model/migration parity test (`tests/test_migration_parity.py`).
- Production rollback is restore-from-backup, never `alembic downgrade`
  ([runbook.md](runbook.md) §5).

## Tenancy at the data layer

- Repositories take `organization_id` as their first filter; no query on
  a tenant-owned table exists without it. Cross-tenant ids therefore
  read as *not found* (audited in [HARDENING_AUDIT.md](HARDENING_AUDIT.md) §3).
- Users are unique per `(organization_id, email)`, not globally; a
  person with access to several tenants has a membership row per tenant.
- Platform-level tables (`plans`, `plan_entitlements`, `permissions`,
  system `roles` with `organization_id IS NULL`) are shared and read-only
  for tenants.

## Retention and growth

| Table family | Growth driver | Retention |
|---|---|---|
| `playback_events` (proof of play) | one row per item shown per screen | per-tenant retention policy (Settings › Quotas & retention; default 90 days), pruned by the `prune_retention` beat |
| `device_heartbeats`, `device_events` | every heartbeat / reported event | policy, default 30 days |
| `device_health_snapshots` | one row per tenant per hour | 400 days |
| `audit_logs` | every consequential action | append-only, never pruned automatically |
| `notification_deliveries`, `webhook_deliveries` | each attempt | policy |
| `usage_snapshots` | hourly usage per tenant | kept for billing history |

Indexes follow the SRS §11 list (`domain-model.md` "Critical indexes");
the hot paths measured in [HARDENING_AUDIT.md](HARDENING_AUDIT.md) §9 all
stay under 60 ms on the seeded data.

## Backups

Managed PostgreSQL with point-in-time recovery in production; nightly
logical dumps in UAT. Object storage holds the media binaries; the
database holds only keys and checksums, so a database restore plus the
bucket is a complete restore.
