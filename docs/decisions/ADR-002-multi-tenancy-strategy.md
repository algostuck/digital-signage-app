# ADR-002: Multi-tenancy — shared schema with organization_id scoping

Status: Accepted · Date: 2026-08-29

## Context
FR-AUTH-007 mandates tenant isolation on every protected query. Options:
database-per-tenant, schema-per-tenant, shared schema with tenant column.
Expected tenant count is moderate-to-large with widely varying sizes;
operational simplicity and cross-tenant platform administration matter.

## Decision
Single PostgreSQL database, shared schema. Every tenant-owned table carries
`organization_id` (directly or via a provable FK chain). Enforcement layers:
1. Tenant context resolved server-side from the authenticated principal only.
2. Repositories require tenant context; base repository applies the scope to
   every query — no unscoped accessors for tenant-owned entities.
3. Services re-validate ownership of any cross-entity reference.
4. Mandatory tenant-isolation tests per module.
Cross-tenant lookups return 404 to avoid existence disclosure.

## Consequences
- Simple migrations/operations; efficient pooled connections.
- Isolation is application-enforced — hence the mandatory test suite.
  PostgreSQL row-level security can be layered on later without model change.
