# Digital Signage Cloud Platform

Enterprise multi-tenant digital signage CMS: content, layouts, playlists,
campaigns, scheduling, asynchronous publishing, device management and a
manufacturer-neutral player gateway (LG webOS / Samsung Tizen / Android /
Windows players connect later via adapters).

- Requirements baseline: [docs/Digital_Signage_Cloud_SRS_FRD.md](docs/Digital_Signage_Cloud_SRS_FRD.md)
- Architecture: [docs/architecture.md](docs/architecture.md) · Decisions: [docs/decisions/](docs/decisions/)
- Domain model: [docs/domain-model.md](docs/domain-model.md)
- API conventions: [docs/api-guidelines.md](docs/api-guidelines.md)
- Documentation: [docs/README.md](docs/README.md) (architecture, API, database, deployment, security, RBAC, subscription, device protocol, admin and demo guides)
- Plan/status: [docs/development-plan.md](docs/development-plan.md)

## Stack

Backend: Python / FastAPI / SQLAlchemy 2 (async) / PostgreSQL / Alembic /
Redis / Celery. Frontend: React / TypeScript / Vite / Ant Design / Tailwind /
React Router / TanStack Query. Storage: S3-compatible + CDN in production
(MinIO under Docker); local dev writes to disk and signs its own URLs.

## Development (Docker)

```bash
docker compose up --build
```

API: http://localhost:8000 (docs at /api/docs) · MinIO console: http://localhost:9001

## Development (local, no Docker)

Backend. PostgreSQL is the only service you need: by default storage, media
processing and publishing all run in-process, so Redis, Celery and MinIO are
only required if you switch to worker mode (`STORAGE_BACKEND`,
`MEDIA_PROCESSING_INLINE`, `PUBLISHING_INLINE` — see `.env.example`).
URL-encode special characters in the DB password, e.g. `@` → `%40`.

```bash
cd backend
python -m venv .venv
.venv/Scripts/pip install -e .[dev]     # Windows (Linux/mac: .venv/bin/pip)
copy ..\.env.example .env               # then edit values
.venv/Scripts/alembic upgrade head
.venv/Scripts/uvicorn app.main:app --reload
```

Frontend. Vite proxies `/api` to the backend, so the portal is the only port
you open:

```bash
cd frontend
npm install
npm run dev                             # http://localhost:5173
```

Optionally load the demo dataset — three Indian retail tenants, ~260
devices, content and campaigns across the full lifecycle. Credentials are in
[docs/DEMO_CREDENTIALS.md](docs/DEMO_CREDENTIALS.md); it refuses to run when
`ENVIRONMENT=production`.

```bash
cd backend
.venv/Scripts/python -m app.demo_seed --reset    # remove a previous run
.venv/Scripts/python -m app.demo_seed            # seed, then validate
.venv/Scripts/python -m app.demo_seed --refresh  # bump heartbeats only
.venv/Scripts/python -m app.demo_seed --validate # check it without reseeding
```

## Tests

Tests run on **PostgreSQL**, not SQLite — the same engine as production, so
tenant isolation, RESTRICT semantics and JSON behaviour are all exercised
for real. Point `TEST_DATABASE_URL` at your server via `backend/.env.test`
(git-ignored); the `digital_app_test` database is created automatically if
it does not exist.

```bash
cd backend
.venv/Scripts/python -m pytest
```

> **Never run two pytest sessions against the same test database at once.**
> They share one database and each run rebuilds the schema, so a second run
> tears down the first one's tables mid-test. The failures look like real
> bugs — spurious 401s, missing rows — and they are not.

## Repository layout

```text
backend/
  app/
    api/v1/        # REST routers (no business logic)
    core/          # config, logging, errors, middleware, context
    db/            # engine/session, declarative base, portable types
    models/        # SQLAlchemy models
    schemas/       # Pydantic DTOs + response envelope
    services/      # business logic
    repositories/  # data access
    workers/       # Celery app + background jobs
  migrations/      # Alembic
  tests/
frontend/
  src/
    modules/       # feature modules (auth, devices, campaigns, preview, ...)
    components/    # layout shell + reusable UI primitives
    config/        # navigation tree (RBAC-aware)
    theme/         # Ant Design tokens, light/dark provider
    routes/        # lazy route table
    lib/           # API client, auth, entitlements
docs/              # SRS/FRD, architecture, ADRs
```
