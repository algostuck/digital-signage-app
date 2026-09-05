# Production Security Review

Reviewed 2026-09-05 against the checklist in the hardening plan. Each
row says what was checked, what the code does, and what changed.

| Area | Finding | Status |
|---|---|---|
| **Secrets** | No `.env`, keys or certificates are tracked; `.env.example` lists names only. `JWT_SECRET` defaults to a dev value and production boot fails unless it is set and ≥ 32 characters. S3 credentials come from the environment. | OK |
| **Default credentials** | The demo tenant and its `admin@demo-org.com` are seeded only outside production (`SEED_DEMO`, `is_production`). The platform administrator, however, was seeded in every environment with the development password unless `SEED_PLATFORM_PASSWORD` was set. | **Fixed** — seeding refuses to run in production without `SEED_PLATFORM_PASSWORD`. `app.demo_seed` already refuses production. |
| **JWT / sessions** | HS256 access tokens (30 min) + rotating single-use refresh tokens (14 days) stored hashed; reuse of a rotated token revokes the whole session family; tenant switch re-issues the pair; tokens live in `localStorage` and are sent as bearer headers. | OK |
| **CORS** | Origins come from `CORS_ORIGINS` (default: the Vite dev origin only); credentials are bearer headers, so a permissive origin cannot ride a cookie. | OK — production must set `CORS_ORIGINS` to the portal's origin only |
| **CSRF** | No cookie-based authentication; nothing to forge. | N/A |
| **Rate limiting** | Login (per IP), player registration (per IP), heartbeats and events (per device), uploads and screenshots (per device/user); 429 with retry semantics documented in the player contract. | OK |
| **File uploads** | Declared MIME must match the allowed prefixes, size 1 byte – `MAX_UPLOAD_SIZE_MB` (512), upload goes to a signed URL, the local backend rejects oversize bodies, media processing validates images; storage keys are resolved and must stay under the storage root (no traversal). | OK |
| **Signed URLs** | Local storage: HMAC-SHA256 over method + key + expiry, 900 s TTL; S3: presigned. API responses are `no-store`; signed storage URLs stay cacheable by design. | OK — note: the local signature key is `JWT_SECRET`; rotating it invalidates in-flight upload/download URLs (15 min) |
| **SSRF** | Data sources and SSO discovery already went through the guarded fetcher (http(s) only, every resolved address must be globally routable, no redirects, 10 s, 1 MiB cap). **Webhook deliveries, notification-rule webhook channels and the SSO token exchange did not**: a tenant administrator could point them at `127.0.0.1:8000`, the cloud metadata address or anything on the private network. | **Fixed** — destinations are shape-checked when saved (http(s), no `localhost` / `.local` / `.internal` hosts, no private literal IPs; the form shows why) and resolve-checked again at send time; redirects are never followed. Test `test_webhook_destinations_must_be_public`. |
| **IDOR / tenant isolation** | Every route-level id is looked up within the caller's tenant; the isolation sweep (gate 3) found and fixed the one relational gap (campaign targets). | OK |
| **RBAC bypass** | Permissions are enforced by route dependencies and, for approvals, in the service; superusers are confined to `/platform` by `require_superuser`; entitlements are a second gate (gate 4). | OK |
| **API keys** | Random, shown once, stored as SHA-256, scoped per key, tenant-bound, metered and plan-gated (`api_access`). | OK |
| **Webhook signatures** | HMAC-SHA256 over the raw body with a per-subscription secret, rotatable; replay endpoint requires the permission. | OK |
| **SQL injection** | SQLAlchemy throughout; the only raw SQL in the application is the readiness `SELECT 1`. The demo seeder's table-name interpolation is from a fixed list and never runs in production. | OK |
| **XSS** | No `dangerouslySetInnerHTML` / `innerHTML` in the portal; ticker and widget text render as text; the API never returns HTML. | OK |
| **Security headers** | `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Cross-Origin-Opener-Policy`, `Cache-Control: no-store` on API responses, HSTS in production. | OK — a `Content-Security-Policy` belongs to the static host serving the portal (gate 12 deployment config) |
| **Error exposure** | Unhandled errors return `INTERNAL_ERROR` with a generic message and the request id; the traceback goes to the log only. Validation errors name the field, never the SQL. | OK |
| **Sensitive data in logs** | Passwords, tokens and secrets are never logged; the one token-related line logs the user id of a refresh-token reuse. Structured access lines carry ids only. | OK |
| **Debug settings** | API docs and the OpenAPI document are disabled in production; `DEBUG` has no effect on error bodies. | OK |
| **Demo data in production** | `demo_seed` refuses `ENVIRONMENT=production`; the main seed skips the demo tenant there; demo credentials exist only in `docs/DEMO_CREDENTIALS.md`. | OK |
| **Device credentials** | Device tokens are issued once, stored hashed, bound to one device id, revoked on decommission/rotation; the Security Center rotates them. | OK |

## Before go-live (checklist)

- `ENVIRONMENT=production`, `JWT_SECRET` ≥ 32 random characters,
  `SEED_PLATFORM_PASSWORD` set for the first seed then removed.
- `CORS_ORIGINS` = the portal origin(s) only.
- TLS termination in front; HSTS is emitted by the API in production.
- Static host for the portal sends a `Content-Security-Policy`
  (`default-src 'self'; img-src 'self' https://*.tile.openstreetmap.org data:; connect-src 'self'`).
- S3 (or equivalent) with a private bucket; presigned URLs only.
- Redis and PostgreSQL not reachable from the internet; the SSRF guard
  refuses private addresses, but network policy is the primary control.
- Log shipping in JSON (`LOG_JSON=true`) with retention; alert on
  `level=ERROR` and on `job … failed` lines.
