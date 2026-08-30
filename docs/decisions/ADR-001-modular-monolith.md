# ADR-001: Modular monolith, not microservices

Status: Accepted · Date: 2026-08-29

## Context
Phase 1 must deliver a complete cloud control plane (18 modules) with a small
team, while NFR-002 demands a data model that scales 1K -> 100K devices without
redesign. Premature service decomposition would multiply operational cost and
slow the domain model down while it is still settling.

## Decision
One FastAPI application with strictly separated domain modules
(api/schemas/services/repositories/models per module), plus a Celery worker and
beat scheduler sharing the codebase. Redis as broker/cache. Module boundaries
are enforced by convention and review: modules interact through services, not
each other's tables.

## Consequences
- Single deployable; simple dev environment; transactions span modules safely.
- High-load components (player gateway, media processing) remain extractable
  later because they already sit behind service interfaces and queues.
- Discipline required: no cross-module model imports outside the shared base.
