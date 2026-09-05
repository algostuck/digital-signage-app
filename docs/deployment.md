# Deployment

How the product moves from a commit to a running environment, and how
DEV, UAT and PRODUCTION differ. The operational detail (backups, upgrades,
rollback, daily checks) is in [runbook.md](runbook.md); the security
go-live list is in [SECURITY_REVIEW.md](SECURITY_REVIEW.md).

## Pipeline

`.github/workflows/ci.yml`, on every push and pull request:

```text
Git push / PR
 ├─ backend      ruff check + format check → pytest (PostgreSQL) → alembic upgrade → downgrade → upgrade
 ├─ frontend     tsc → vite build (artifact: portal-dist)
 ├─ integration  (needs backend) alembic + system seed + demo dataset → API up →
 │               audit_tenant_isolation → audit_e2e_journey → audit_entitlements → audit_performance*
 ├─ images       (needs backend, frontend) build backend + frontend images; push to GHCR on main / tags
 └─ deploy       (needs integration, images) main → UAT · v* tag or dispatch → PRODUCTION (approval gate)
                 scp deploy/ → pull images → run migrate → up -d → health check
```

`*` performance runs informationally on shared runners (`continue-on-error`);
its report is uploaded with the other audit reports as a build artifact.

The three audits are the same scripts a developer runs locally
(`HARDENING_AUDIT.md`); a pull request cannot merge if tenant isolation,
the end-to-end journey or the entitlement rules regress.

### Deploy stage prerequisites

Two GitHub *environments*, `uat` and `production` (the latter with
required reviewers), each with the secrets `DEPLOY_HOST`, `DEPLOY_USER`,
`DEPLOY_SSH_KEY`, `DEPLOY_ENV_FILE` (the full contents of the
environment file below) and `HEALTH_URL`. The deploy host needs Docker
with Compose and a `~/signage` directory; images are pulled from GHCR.

## Environments

| | DEV | UAT | PRODUCTION |
|---|---|---|---|
| Config | `backend/.env` from `.env.example` (`deploy/env/dev.env.example` shows the column) | `deploy/env/uat.env` from `uat.env.example` | `deploy/env/prod.env` from `prod.env.example`, or the secret manager |
| `ENVIRONMENT` | `development` | `staging` | `production` (disables `/api/docs`, enables HSTS, refuses a weak `JWT_SECRET`, refuses the demo seeder) |
| Stack | native (`README.md`) or `docker compose up` at the repo root | `deploy/compose.prod.yml --profile selfhosted` (bundled PostgreSQL, Redis, MinIO) | `deploy/compose.prod.yml` with managed PostgreSQL, Redis and object storage + CDN |
| API processes | 1 uvicorn worker (`--reload`) | `WEB_CONCURRENCY=2` | `WEB_CONCURRENCY` ≈ CPU cores; scale replicas behind the load balancer |
| Storage / media | `STORAGE_BACKEND=local`, inline media processing and publishing | S3 (MinIO), worker mode | S3 + `CDN_URL`, worker mode |
| Data | demo tenants (`app.demo_seed`) | system seed + optional demo tenants for rehearsal | system seed only; tenants created from the Platform Console |
| Images | built locally | `:main` (every green main build) | `:vX.Y.Z` tags, pinned in `prod.env` |
| Logs | plain text | JSON | JSON, shipped, alert on `ERROR` and `job … failed` |
| TLS | none | terminator in front of `web` | terminator / load balancer in front of `web` |

## The production-shaped stack

`deploy/compose.prod.yml` defines the process types from the runbook:

| Service | Role |
|---|---|
| `migrate` | one-shot: `alembic upgrade head` + `SEED_DEMO=false python -m app.seed` (permissions, system roles, plans; the platform administrator only when `SEED_PLATFORM_PASSWORD` is set) |
| `api` | uvicorn with `WEB_CONCURRENCY` workers, `--proxy-headers`; healthcheck on `/api/v1/health/ready` |
| `worker` | Celery: media processing, deployment fan-out, maintenance sweeps |
| `beat` | Celery beat — exactly one replica |
| `web` | nginx: the built portal, history-mode fallback, `/api` proxied to `api` (same origin), security headers including `Content-Security-Policy`, long-lived caching for hashed assets |
| `postgres`, `redis`, `minio` | only with `--profile selfhosted` (UAT / single box) |

```bash
docker compose -f deploy/compose.prod.yml --env-file deploy/env/uat.env --profile selfhosted up -d
```

```bash
docker compose -f deploy/compose.prod.yml --env-file deploy/env/prod.env up -d
```

First run on a fresh database: put `SEED_PLATFORM_PASSWORD` in the env file
for the `migrate` job, sign in as `platform@signage.cloud`, change the
password, remove the variable. Everything after that — tenants, owners,
plans, subscriptions — is done from the Platform Console.

## Release and rollback

1. Tag `vX.Y.Z` on main → CI builds and pushes the images with that tag
   and opens the production deploy for approval.
2. The deploy runs `migrate` (forward-only, backward-compatible within a
   release window), then replaces the containers, then checks
   `/api/v1/health/ready`.
3. Rollback = point `BACKEND_IMAGE` / `FRONTEND_IMAGE` at the previous tag
   and `up -d` again. Schema rollback is restore-from-backup, never
   `alembic downgrade` in production (runbook §5).

## Local development

See `README.md` ("Development (local, no Docker)") — PostgreSQL is the
only dependency; the demo dataset and credentials are in
`DEMO_CREDENTIALS.md` and `DEMO_DATA_CATALOG.md`.
