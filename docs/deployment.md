One doc improvement worth making while answering — the runbook's "first deployment" step predates the SaaS core (tenants are now created from the Platform console). Updating it:

Also adding the missing `beat` service to docker-compose (the subscription lifecycle and monitoring sweeps need it):

Everything you need is in place. Here's the complete guide for both:

## Development

**Option A — native on this machine (what we've been running).** Requires: local PostgreSQL running (`digital_app_dev` with the settings already in [backend/.env](backend/.env)) and Node. Redis/Celery are *not* needed in dev — media processing and publishing run inline.

After pulling changes, apply migrations and reseed (both idempotent):

```bash
cd backend && .venv/Scripts/python -m alembic upgrade head && .venv/Scripts/python -m app.seed
```

Then start the two processes (two terminals):

```bash
cd backend && .venv/Scripts/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

```bash
cd frontend && npm run dev
```

Portal: http://localhost:5173 · API docs: http://localhost:8000/api/docs. Logins: `admin@demo-org.com` / `Admin@12345` (tenant), `platform@signage.cloud` / `Platform@12345` (Super Admin). If you want the background sweeps (offline detection, subscription lifecycle/dunning, usage snapshots) locally, you'd additionally need Redis plus `celery -A app.workers.celery_app worker -Q default,media,publishing,maintenance -P solo` and `celery -A app.workers.celery_app beat` (`-P solo` is required on Windows) — otherwise those features simply stay quiet in dev.

Tests (PostgreSQL-only; auto-provisions `digital_app_test`):

```bash
cd backend && .venv/Scripts/python -m pytest tests -q
```

**Option B — Docker Compose (full stack: Postgres + Redis + MinIO + API + worker + beat).** I just added the missing `beat` service to [docker-compose.yml](docker-compose.yml). Note it uses its own database (`signage`), separate from your local `digital_app_dev`:

```bash
docker compose up --build
```

Then seed once (`docker compose exec api python -m app.seed`) and run the frontend natively with `npm run dev` (compose doesn't serve the frontend).

## Production

Full detail is in [docs/runbook.md](docs/runbook.md) — the short version:

1. **Provision**: managed PostgreSQL, managed Redis, S3-compatible bucket + CDN.
2. **Environment** (fail-closed items): `ENVIRONMENT=production` (disables /api/docs, enables HSTS), a random ≥32-char `JWT_SECRET` (the API refuses to boot with a weak one), `DATABASE_URL`, `REDIS_URL`, `STORAGE_BACKEND=s3` + `S3_*` + `CDN_URL`, `MEDIA_PROCESSING_INLINE=false`, `PUBLISHING_INLINE=false`, `CORS_ORIGINS` set to your portal origin only. Secrets via your platform's secret manager, never committed. Future payment-gateway keys (Stripe/Razorpay) also go here, never in the DB.
3. **Schema + system seed**: `alembic upgrade head`, then `SEED_DEMO=false python -m app.seed` — seeds permissions, system roles and the four plans; no demo tenant, no demo passwords.
4. **Create the Super Admin once** (one-off script/psql: an org + a user with `is_superuser=true`) — after that, all tenant onboarding happens from the Platform console: create tenant + owner, assign plan, manage subscriptions/payments.
5. **Run three process types**:
   - API: `uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4` — stateless, scale horizontally behind TLS/load balancer
   - Worker: `celery -A app.workers.celery_app worker -Q default,media,publishing,maintenance` — scale as needed
   - Beat: `celery -A app.workers.celery_app beat` — **exactly one instance** (runs dunning, renewals, offline detection, retention pruning, usage snapshots)
6. **Frontend**: `npm run build`, serve `frontend/dist/` from any static host/CDN, proxy `/api` to the API service.
7. **Verify**: `GET /api/v1/health/ready` → `database: ok`, portal login works, `celery inspect ping` responds.

Upgrades: backup → deploy new image alongside old → `alembic upgrade head` once → switch traffic → restart worker/beat → deploy frontend. Rollback prefers pointing traffic back at the previous image (migrations are backward-compatible within a release window); schema rollback is restore-from-dump, never `alembic downgrade` in production.