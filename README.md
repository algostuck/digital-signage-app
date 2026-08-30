# Digital Signage Cloud Platform

Enterprise multi-tenant digital signage CMS: content, layouts, playlists,
campaigns, scheduling, asynchronous publishing, device management and a
manufacturer-neutral player gateway (LG webOS / Samsung Tizen / Android /
Windows players connect later via adapters).

- Requirements baseline: [docs/Digital_Signage_Cloud_SRS_FRD.md](docs/Digital_Signage_Cloud_SRS_FRD.md)
- Architecture: [docs/architecture.md](docs/architecture.md) · Decisions: [docs/decisions/](docs/decisions/)
- Domain model: [docs/domain-model.md](docs/domain-model.md)
- API conventions: [docs/api-guidelines.md](docs/api-guidelines.md)
- Plan/status: [docs/development-plan.md](docs/development-plan.md)

## Stack

Backend: Python / FastAPI / SQLAlchemy 2 (async) / PostgreSQL / Alembic /
Redis / Celery. Frontend: React / TypeScript / Vite / Tailwind /
React Router / TanStack Query. Storage: S3-compatible (MinIO in dev) + CDN.

## Development (Docker)

```bash
docker compose up --build
```

API: http://localhost:8000 (docs at /api/docs) · MinIO console: http://localhost:9001

## Development (local, no Docker)

Backend (needs a reachable PostgreSQL; Redis only for real worker mode —
see `.env.example`; URL-encode special characters in the DB password,
e.g. `@` → `%40`):

```bash
cd backend
python -m venv .venv
.venv/Scripts/pip install -e .[dev]     # Windows (Linux/mac: .venv/bin/pip)
copy ..\.env.example .env               # then edit values
.venv/Scripts/alembic upgrade head
.venv/Scripts/uvicorn app.main:app --reload
```

Tests run without any services (SQLite-backed):

```bash
cd backend
.venv/Scripts/python -m pytest
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

## Repository layout

```text
backend/
  app/
    api/v1/        # REST routers (no business logic)
    core/          # config, logging, errors, middleware, context
    db/            # engine/session, declarative base, portable types
    models/        # SQLAlchemy models
    schemas/       # Pydantic DTOs + response envelope
    services/      # business logic (added per module)
    repositories/  # data access (added per module)
    workers/       # Celery app + background jobs
  migrations/      # Alembic
  tests/
frontend/
  src/
    modules/       # feature modules (auth, locations, devices, ...)
    components/    # reusable UI
    lib/           # API client, utilities
docs/              # SRS/FRD, architecture, ADRs
```
