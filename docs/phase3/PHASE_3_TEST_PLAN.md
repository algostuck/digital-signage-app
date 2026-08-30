# Phase 3 — Test Plan

Infrastructure (from 2L): pytest on **PostgreSQL only** (`digital_app_test`,
truncate isolation, ~2s/test), migration-parity guard on `digital_app_parity`,
full-suite regression gate per slice (currently 240 tests, ~10 min), lint
incl. ruff-S, frontend build gate, live E2E per slice against the dev stack.
Phase-1+2 regression = the same 240 tests staying green every slice
(STEP 35), plus per-slice additions below.

## Per-module coverage

| Module | Unit / API tests | Failure-mode tests (STEP 34) |
|---|---|---|
| Feature flags | flag off ⇒ 404/absent surface; per-tenant scope; isolation | flag flips mid-session |
| Event bus | normalized envelope; subscription filter; signed delivery; retry→dead-letter; replay | consumer down, oversized payload |
| Data sources | SSRF hostile fixtures; schema validation reject; transform ops; TTL + stale-while-revalidate; last-known-good; fallback render | source down (acceptance #2), invalid payload, slow source (timeout), credential rotation |
| AI | policy gating; governance records complete; placeholder-preserving localization; approval routing; deterministic provider repeatability | provider timeout/down ⇒ deterministic fallback (NFR3-06); low confidence path; flagged output quarantine |
| Decisioning | deterministic same-in→same-out with reason trail; guardrails (frequency caps, windows, mandatory) override optimization; preview | decision service error ⇒ scheduled resolver ⇒ default playlist (never blank) |
| Experiments | stable hash assignment; allocation tolerance; start/end windows; results math | device joins mid-experiment; experiment ends |
| Video walls | canvas/viewport validation; sync session marker + tolerance; member uniqueness | member offline ⇒ degraded (acceptance #3); clock drift beyond tolerance; restore ⇒ resync |
| Edge bundles | signature + sha256 verification; expiry; rollout state; Range/resumable download; bandwidth policy in manifest | offline playback, expired bundle, partial download resume (acceptance #5) |
| Ads | inventory availability math; booking conflicts; unique playback link (no double count); billing aggregates reconcile vs raw (acceptance #4) | expired campaign, conflicting bookings, missing evidence |
| Fleet anomalies | rule windows over synthetic telemetry; score + evidence rows; ack; remediation whitelist + authorization | repeated-heartbeat scenario (acceptance #6); no auto-destructive action |
| SSO | id-token validation (issuer/aud/sig/nonce/expiry via test JWKS); claim→role mapping; RBAC still enforced post-SSO; provider revocation; audit evidence (acceptance #7) | bad signature, expired token, unmapped claims |
| White label | branding isolation A≠B; email identity; custom-domain metadata | — |
| Security center | identity lifecycle (issue/rotate/expiry alert/revoke); policy violation creation; auth anomaly signal | — |
| Analytics | aggregate idempotent recompute; reconciliation vs raw; semantic metrics single-source; scheduled export runs + state | export destination unavailable, late events self-heal |
| Developer platform | sandbox isolation; versioned OpenAPI serves; keys unchanged from 2H | invalid API key (existing) |

## E2E flows (master-prompt STEP 33, mapped to SRS §9)
1. AI: generate localized variant → approval → publish to targeted region → metadata preserved.
2. Dynamic data: source → widget → layout → campaign → intelligent selection → approve → publish → device sync → playback → PoP → analytics (with source-outage fallback in the middle).
3. Video wall: create 2x2 → map viewports → publish sync content → members align → remove one → degraded → restore → resync.
4. Advertising: inventory → booking → publish → plays → PoP links → billable aggregates reconcile.
5. Edge: bundle → pre-stage to group → offline playback → expiry → reconnect recovery.
6. Fleet: induced heartbeat failures → anomaly + recommendation → ack → approved remediation logged.
7. Enterprise: SSO configure → login → role mapping → revoke → audit.

Each automated where the harness allows (simulated players, local OIDC
stub, local data-source server — same technique as the 2H webhook
receiver) AND demonstrated live per the Phase-2 discipline.

## Sign-off
Phase 3 done only when: every FR row in the gap analysis has a final
status; all seven acceptance flows pass; full regression (P1+P2+P3) green
on PostgreSQL; security checklist per slice complete; load smoke extended
with data-source + decisioning hot paths shows no fan-out regression;
docs current.
