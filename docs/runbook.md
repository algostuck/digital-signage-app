# Production Runbook — Digital Signage Cloud

Covers deploy, upgrade, rollback, backup and daily operations for the
Phase-1 platform. Companion to [architecture.md](architecture.md).

## 1. Topology

| Process | Command | Notes |
|---|---|---|
| API | `uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4` | Stateless; scale horizontally behind a load balancer / TLS terminator |
| Worker | `celery -A app.workers.celery_app worker -Q default,media,publishing,maintenance` | Media processing + deployment fan-out |
| Beat | `celery -A app.workers.celery_app beat` | Offline detection sweep (every 120 s); run exactly one instance |
| PostgreSQL | managed instance recommended | Source of truth |
| Redis | managed instance recommended | Celery broker/result + future cache |
| Object storage | S3-compatible + CDN | Media binaries |

Frontend: `npm run build` → serve `frontend/dist/` from any static host/CDN;
proxy `/api` to the API service.

## 2. Environment checklist (fail-closed items in bold)

- **`JWT_SECRET`** — random, ≥32 chars. The API refuses to boot in
  production with the dev default or a short value.
- **`DATABASE_URL`** — `postgresql+asyncpg://user:pass@host:5432/db`.
  URL-encode special characters in the password (`@` → `%40`).
- **`ENVIRONMENT=production`** — disables /api/docs, enables HSTS.
- `REDIS_URL`, `STORAGE_BACKEND=s3`, `S3_*`, `CDN_URL`
- `MEDIA_PROCESSING_INLINE=false`, `PUBLISHING_INLINE=false` (worker mode)
- `CORS_ORIGINS` — the portal origin(s) only.
- Rate limits (`RATE_LIMIT_*`) — per-process; keep an edge limiter in front
  for multi-instance deployments.
- Never commit secrets; use the platform's secret manager.

## 3. First deployment

```bash
# 1. Provision PostgreSQL, Redis, bucket. Create the database.
# 2. Apply schema
alembic upgrade head
# 3. Seed system data only (permissions, system roles, plans; no demo tenant)
SEED_DEMO=false python -m app.seed
# 4. Create the Super Admin (one-off; the SaaS core gates /platform on
#    users.is_superuser). Pick any org code for the admin's home org, e.g.:
#      python - <<'EOF'
#      # create org 'platform' + superuser via app.services.platform.create_tenant
#      # then UPDATE users SET is_superuser=true for that owner
#      EOF
#    (or psql: INSERT organizations + users with is_superuser=true)
# 5. Onboard every real tenant from the Platform console (or API):
#    POST /platform/tenants (org + owner), then assign a plan via
#    POST /platform/tenants/{id}/subscription
# 6. Start api / worker / beat; verify health (section 6)
```

## 4. Upgrade procedure

1. **Backup first**: confirm the latest automated snapshot or run
   `pg_dump -Fc "$DATABASE_URL_PLAIN" > pre_upgrade.dump`.
2. Deploy the new backend image alongside the old one (do not switch traffic).
3. Run `alembic upgrade head` once (migrations are additive and ordered;
   CI validates the up/down/up cycle on PostgreSQL for every change).
4. Switch traffic to the new API; restart worker + beat on the new image.
5. Verify: section 6 checks + one end-to-end publish on a canary campaign.
6. Deploy the new frontend build.

## 5. Rollback

- **Application rollback** (no schema change involved): point traffic back
  at the previous image. Migrations are backward-compatible within one
  release window, so the old code runs against the new schema.
- **Schema rollback** (last resort): stop api/worker, restore the
  pre-upgrade dump (`pg_restore --clean`), start the previous image.
  Prefer restore over `alembic downgrade` in production — downgrades drop
  tables and lose data written since the upgrade.
- Frontend: redeploy the previous `dist/` artifact.

## 6. Health & verification

| Check | Expectation |
|---|---|
| `GET /api/v1/health` | `{"status": "ok"}` |
| `GET /api/v1/health/ready` | `database: ok` |
| Login via portal | succeeds; audit log records `USER_LOGIN` |
| `celery -A app.workers.celery_app inspect ping` | workers respond |
| Dashboard | device online counts move with heartbeats |

Logs are structured JSON with `request_id`; every API response echoes
`X-Request-ID` for correlation.

## 7. Backup & retention (NFR-008, NFR-013)

- PostgreSQL: managed automated backups + PITR; baseline targets
  RPO ≤ 15 min, RTO ≤ 2 h (SRS NFR-014).
- Object storage: enable bucket versioning + lifecycle policy.
- Telemetry growth: `device_heartbeats`, `device_events`,
  `playback_events` are append-only — the daily `prune_retention` beat task
  deletes rows past each tenant's retention policy
  (settings_json.retention_days, platform floors apply; audit ≥ 90 days) and
  leaves a RETENTION_PRUNED audit record.

## 7b. Phase-2 maintenance beat schedule (queue: maintenance)

| Task | Interval | Purpose |
|---|---|---|
| detect_offline_devices | 2 min | Offline incidents + notifications per tenant thresholds |
| push_rule_deliveries | 1 min | Notification-rule webhook channel deliveries (retries, max 3) |
| push_webhook_deliveries | 1 min | Signed subscription webhooks (backoff 1m→8m, dead-letter, replayable) |
| process_escalations | 5 min | Unread rule-matched alerts past their delay → critical ESCALATION |
| prune_retention | daily | Tenant retention pruning (audited) |
| subscription_lifecycle | hourly | SaaS core: trial expiry, renewals + invoices, dunning ladder past_due→grace→suspended (docs/SAAS_CORE.md) |
| snapshot_usage | 15 min | SaaS core: refresh usage_counters (devices/users/storage/locations) with effective limits |

All sweeps are idempotent with DB-backed state — worker restarts lose
nothing (NFR2-08). Watch the `maintenance` queue depth and the
webhook dead-letter count (`webhook_deliveries.state='dead'`).

## 7c. Testing policy

The automated suite runs exclusively on PostgreSQL (`digital_app_test`,
auto-provisioned by conftest; parity checks use `digital_app_parity`).
There is no SQLite anywhere in the toolchain.

## 8. Load smoke (run before major releases)

```bash
python scripts/load_smoke.py 100
```

Registers simulated devices against the running backend, storms heartbeats,
publishes a fleet-wide campaign, storms manifests + acks, prints latency
percentiles, and cleans up after itself. Baseline (dev laptop, single
uvicorn process, local PostgreSQL 18, 50 devices): fan-out 128 ms,
heartbeats ~40 req/s, deployment aggregates to `published 50/50` under
fully concurrent acknowledgements.

## 9. Incident quick reference

| Symptom | First moves |
|---|---|
| Devices offline en masse | Check API health + TLS expiry; devices retry with backoff and resume from cached manifests (offline-first by design) |
| Deployment stuck in `publishing` | `GET /deployments/{id}/devices` for per-device errors; `retry` failed rows; check worker logs by `request_id` |
| 429 storms | A NAT-heavy site may exceed per-IP register limits — raise `RATE_LIMIT_REGISTER_PER_MINUTE` or exempt the site at the edge |
| Media stuck `processing` | Worker down or storage unreachable; task retries with backoff — check `media` queue depth |
| Suspected credential leak | Device: `reset-token` (revokes immediately). User: deactivate (revokes all refresh tokens). Org enrollment key: rotate by clearing `organizations.enrollment_key` (re-minted on next admin view) |
