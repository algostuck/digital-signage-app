# API Guidelines

Base path: `/api/v1`. JSON only. All endpoints are authenticated and
tenant-scoped unless explicitly public (login, player bootstrap, health).

## Headers

```text
Authorization: Bearer <token>
X-Tenant-ID: <org_uuid>        # optional selector among the principal's orgs; never trusted as authorization
Idempotency-Key: <uuid>        # required on selected create/publish operations
X-Request-ID: <uuid>           # optional; generated when absent, always echoed back
Content-Type: application/json
```

## Response envelope

Every response uses:

```json
{
  "data": { },
  "meta": { "request_id": "..." },
  "errors": []
}
```

- Success: `data` populated, `errors` empty.
- Failure: `data` null, `errors` = `[{"code": "...", "message": "...", "field": "optional"}]`.
- List endpoints: `data` is the item array; `meta` adds
  `{"page": 1, "page_size": 50, "total": 123}`.

## Error codes

| HTTP | Code | Meaning |
|---|---|---|
| 400 | VALIDATION_ERROR | Malformed input (each field error listed in `errors`) |
| 401 | UNAUTHENTICATED | Missing/invalid credentials |
| 403 | FORBIDDEN | Authenticated but not authorized (incl. cross-tenant access) |
| 404 | NOT_FOUND | Entity not found *within the caller's tenant scope* |
| 409 | CONFLICT | Uniqueness/idempotency conflict |
| 422 | BUSINESS_RULE_VIOLATION | Valid input, invalid business state transition |
| 429 | RATE_LIMITED | Rate limit exceeded |
| 500 | INTERNAL_ERROR | Unexpected; details logged, never leaked to client |

Cross-tenant lookups return 404 (not 403) to avoid existence disclosure.

## Collections

- Pagination is mandatory: `?page=1&page_size=50` (max page_size enforced,
  default 50). No unlimited listings.
- Filtering: exact-match query params named after fields (`?status=active`).
- Search: `?q=` free-text where supported.
- Sorting: `?sort=-created_at,name` (leading `-` = descending).

## Mutations

- POST create, PATCH partial update, DELETE archive/deactivate (soft) unless
  documented otherwise.
- State transitions are explicit sub-resources (`POST .../publish`,
  `POST .../approve`), never magic status PATCHes.
- Long operations return `202` with a job/deployment id; never hold requests
  open for fan-out.
- `Idempotency-Key` required on: publish, deployment retry, upload complete,
  player event batches.

## Implementation notes

- Routers hold no business logic — delegate to services.
- Pydantic schemas per module in `schemas/`; never return ORM objects raw.
- All handlers receive tenant context via dependency injection
  (`CurrentTenant`), resolved from the token server-side.
- Every request gets a request ID (middleware) included in logs and `meta`.
