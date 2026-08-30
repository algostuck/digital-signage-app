# Phase 3 — Security Model

Baseline inherited from Phases 1–2 (all verified by tests): tenant context
from principal only, cross-tenant = 404, RBAC guard on every endpoint,
hashed device tokens/API keys, one-time secret reveals, signed webhooks,
rate limits, security headers, ruff-S (bandit) CI gate, audit trail.
Phase 3 adds the following, each with tests in its slice.

## 1. Outbound fetch (SSRF) — data sources, connectors, event bus
Central `app/integrations/fetch.py` used by every outbound feature:
- scheme allowlist (https; http only for explicitly-allowed dev hosts)
- DNS-resolved IP checked against private/link-local/metadata ranges
  (RFC1918, 169.254.0.0/16, ::1, etc.) — re-checked on redirect (redirects
  capped, cross-host redirect to private space rejected)
- response size + time budgets; content-type checks per source type
- per-tenant destination allowlist policy (settings_json.security)
Hostile-fixture tests: localhost, 169.254.169.254, redirect-to-private,
oversized body, wrong content type.

## 2. Secrets
- data_source_credentials / connector configs: secret-ref or encrypted-at-
  rest column, never echoed by any API (2H one-time-reveal pattern where a
  secret must be shown at all).
- SSO client secrets: env/secret-store refs in metadata, never in API
  output or audit rows (2H audit discipline).
- AI: provider keys via env only; ai_requests never persist secrets.

## 3. SSO (P3-GLO-002) — AuthN vs AuthZ kept separate
- **Authentication answers: who is this user?** (OIDC id-token validation:
  issuer, audience, signature via JWKS, nonce, expiry.)
- **Authorization answers: what may they do here?** (Existing RBAC roles,
  mapped from claims by tenant-configured rules, evaluated exactly like
  password-login sessions — SSO never bypasses require_permissions,
  approval policies, quotas or flags.)
- Sessions: SSO logins mint the same short-lived access + rotating refresh
  pair; provider revocation test + audit evidence per SRS acceptance #7.

## 4. Device identity (P3-SEC-101/102)
identity_credentials store fingerprints/refs only; issuance, rotation,
expiry alerts and revocation via sweeps (2H rotation pattern). mTLS
termination is deployment-layer; the platform validates presented identity
against stored fingerprints where the transport provides them. Existing
opaque-token auth remains the floor for platforms without cert support.

## 5. Policy engine + security analytics (P3-SEC-103/104)
security_policies evaluated centrally (beat + at relevant control points);
violations recorded with severity/state and surfaced in the Security
Center; auth anomalies (impossible travel-lite: burst failures, new-IP
admin logins) raise notifications through the 2G rules engine.

## 6. AI-specific
Tenant data isolation in prompts (only the requesting tenant's content is
ever provided as context); output validation before persistence (placeholder
integrity, size, safety status); no autonomous destructive actions (SRS
§12); flagged outputs quarantined pending approval.

## 7. Ads & tenant boundaries
Advertiser/booking data is tenant-owned like everything else; billing
aggregates expose no cross-tenant data; platform-admin views (P3-18/24)
are health-only by construction (queries never join tenant content).

## 8. Media & bundles
Signed URLs (existing) + bundle signatures (HMAC with platform key,
rotatable) + sha256 verification before activation; expiry enforced on
both ends.

## 9. Per-slice security checklist (gate)
[] tenant probes for every new table/endpoint  [] RBAC + flag checks
[] secrets never in responses/audit  [] outbound calls through guarded fetch
[] rate limits on public/hot surfaces  [] ruff-S clean  [] failure-mode tests
