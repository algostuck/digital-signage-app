# Phase 3 — Hardening Report (slice 3E-5)

Date: 2026-08-30. Scope: SRS §9 acceptance flows, failure-mode matrix,
extended load smoke, security review, full regression sign-off.

## 1. SRS §9 acceptance scenarios — all 7 automated and passing

`backend/tests/test_phase3_acceptance.py` (7/7 green on PostgreSQL):

| # | Scenario | Evidence |
|---|---|---|
| S1 | AI-localized variant → approval → publish, metadata preserved | pending→approved via 2A inbox; provider/template-version recorded; placeholders intact; campaign published |
| S2 | Data source outage → last-known-good → automatic recovery | state error + LKG served; refresh restores active |
| S3 | 2×2 wall sync → member removed → degraded → restore → resync | degraded + healthy members still serve; heartbeat restores syncing |
| S4 | Book inventory → run campaign → collect PoP → reconcile billables | 4/4 delivered, fill rate 100%, links idempotent |
| S5 | Pre-staged signed bundle → expiry → recovery | signed manifest + staged assets; expired bundle leaves manifests; fresh bundle restores |
| S6 | Heartbeat/playback anomaly → recommendation → ack → logged remediation | evidence-backed anomaly; whitelisted restart queued via 1E; full action trail |
| S7 | SSO configure → claim mapping → login → revoke → audit | group→role mapping; revocation refuses flow; USER_LOGIN_SSO audit row |

## 2. Failure-mode matrix (STEP 34)

| Failure | Behavior | Ladder end-state | Verified by |
|---|---|---|---|
| AI provider down/failed | deterministic local result marked `fallback` | content still generated | test_ai_api (ladder), provider design |
| AI guardrail violation | output `flagged`, never published silently | human action required | test_ai_api |
| Data source down | serve last-known-good with `stale` flag | widget fallback_json (player) | S2, test_data_sources |
| Data source schema violation | invalid snapshot recorded, LKG untouched | as above | test_data_sources |
| Decision engine error | try/except → 1H scheduler result | 1G fallback chain | manifest hook, test_decisioning |
| All candidates excluded by rules | explicit fallback reason, scheduler kept | never blank | test_decisioning |
| Decision flapping | switch budget counts actual changes | scheduler kept + reason | test_decisioning cap test |
| Experiment failure/stop | normal 2E variant resolution | base creative | test_experiments |
| Wall member offline | wall DEGRADED + incident; members standalone | cached playback | S3, test_video_walls |
| Bundle expired | bundle block absent; player uses cached manifest | live manifest on reconnect | S5, test_edge |
| Bundle download interrupted | HTTP Range resume (206/416) | full retry | test_edge range test |
| Event consumer down | backoff 1m→8m → replayable dead-letter | manual replay | test_event_bus |
| Ad reconciliation re-run | unique playback link guard | no double billing | test_ads idempotency |
| Aggregate drift (late events) | reconciliation detects; recompute heals | consistent | test_analytics self-heal |
| Anomaly signal clears | auto-resolve with trail entry | closed with evidence | test_fleet_intelligence |
| Credential over-age | violation surfaced, never auto-enforced | human rotate → self-resolve | test_security_center |
| SSO IdP unreachable | discovery/test fails cleanly; password login unaffected | classic login | sso test + design |
| SMTP failure | delivery evidence records failure | notification retained in-app | email adapter design |

## 3. Extended load smoke (dev, PostgreSQL, alongside a full test run)

50 devices registered+approved (3.3 s) · 250-heartbeat storm at concurrency
50 (60 req/s) · **campaign fan-out to 50 devices: 122 ms** (Phase-1
baseline 128 ms, Phase-2 135 ms — no regression) · 50 concurrent manifest
fetches (now carrying data/sync/bundle/decision blocks) all served ·
50/50 acks → deployment PUBLISHED. Latency percentiles were measured while
the 300+-test regression ran on the same machine; they bound the worst
case, not the norm.

## 4. Security review (per-slice checklist, PHASE_3_SECURITY_MODEL §9)

- Secrets: no new raw secrets at rest — data-source tokens, SSO client
  secrets and SMTP credentials are env-var references; event/webhook/bundle
  signing uses server-side HMAC; device credentials remain hash-only with
  fingerprint-only lifecycle records.
- SSRF: all outbound tenant-configured fetches (data sources, SSO
  discovery) go through the guarded fetcher (public-IP-only resolution, no
  redirects, size cap); verified live against 169.254.169.254.
- Tenant isolation: every new table carries organization_id (platform
  catalogues documented as exceptions); every new suite includes an
  isolation test; cross-tenant reads return empty/404.
- Entitlement + permission dual gates on every flagged surface
  (ai_features, dynamic_data, experiments, video_wall, edge_bundles,
  advertising, fleet_ai, sso, white_label, developer_portal).
- No autonomous destructive actions: AI outputs and ad bookings ride the
  2A approval engine; anomaly remediation is whitelisted and human-
  triggered; violations/degradations are surfaced, never auto-enforced.
- Auth surface additions (SSO callback, password reset) are rate-limited or
  state-signed, single-use, and revoke sessions on password change.

## 5. Regression sign-off

Full PostgreSQL suite at Phase-3 completion: **330 passed, 0 failed** in
56m47s (single worker, serialized against `digital_app_test`). Migrations
0022–0035 each verified up/down/up; migration parity green on the frozen
repo.

## 6. Known deviations (documented)

- Edge metrics tiles live with the Bundle Manager (P3-12) instead of a
  separate /monitoring tab.
- Password-reset portal UI deferred; API flow complete and tested.
- Widget→source bindings are per-zone canvas JSON (richer than the SRS's
  widget-global binding endpoint).
- Regional tenancy is metadata + platform-admin controls (multi-region
  infrastructure is out of scope per SRS §12).
- Bundle signatures are server-side HMAC; asymmetric player-side
  verification is the documented next hardening step.
