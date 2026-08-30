# Phase 3 — Implementation Status

Method unchanged from Phases 1–2: vertical slices
(migration → models → services → APIs → tests → frontend → live E2E → docs),
full PostgreSQL regression green after every slice, feature-flag gated,
per-slice security checklist (PHASE_3_SECURITY_MODEL.md §9).

Foundation verified before start: Phase-2 final sign-off **240/240 on
PostgreSQL** (2026-08-29); initiation audit in PHASE_3_INITIATION_REPORT.md.

| # | Slice | SRS modules | Status |
|---|---|---|---|
| 3A-1 | Foundation: ~~tenant feature flags~~ (done pre-Phase-3 by the SaaS-core entitlement engine, `docs/SAAS_CORE.md`), domain event bus (events + subscriptions + signed deliveries), retention keys for new streams | P3-M09 (part) | **Done** (2026-08-30; migration 0022 up/down/up on PG; `app/services/events.py` with 10-type catalogue, emissions wired into devices/monitoring/content/publishing/incidents/subscriptions; delivery beat 60 s; retention keys domain_events 90 d / event_deliveries 30 d; APIs `/events`, `/events/catalogue`, `/subscriptions*`; Event Bus UI in Settings→Integrations; 6 tests in test_event_bus.py incl. signature verify, filter, retry→dead→replay, RBAC, isolation, retention; live E2E verified) |
| 3A-2 | Dynamic data: sources + schemas + guarded fetch + snapshots/cache + transforms + widget bindings + manifest data block; Data Source Manager + widget-designer extension | P3-M02 | Pending |
| 3A-3 | Developer platform: versioned OpenAPI publication, sandbox tenant flow, Developer Portal screen | P3-M12, P3-INT-103 | Pending |
| 3B-1 | AI foundation: provider adapter + local deterministic provider, policies/requests/outputs governance, approval adapter, AI Content Studio + Variant Manager | P3-M01 | Pending |
| 3B-2 | Decisioning: policies/rules/guardrails, manifest integration with degradation ladder, decision preview + log; Decisioning Rules screen | P3-M03 (part) | Pending |
| 3B-3 | Experimentation: experiments/variants/stable assignments, results; Experiment Manager | P3-DEC-003 | Pending |
| 3C-1 | Video walls: walls/members/viewports, sync sessions (markers + tolerance), degraded state + incidents, contract v2 sync block; Wall Manager + Control | P3-M04 | Pending |
| 3C-2 | Edge: signed offline bundles + rollout, prefetch + bandwidth policy manifest blocks, resumable (Range) download; Bundle Manager + Edge dashboard | P3-M06 | Pending |
| 3D-1 | Ads: inventory/bookings/playback links, billing-ready aggregates + ad performance report/export, `ads.manage` permission; Ads screens | P3-M05 | Pending |
| 3D-2 | Analytics platform: daily aggregates + semantic metrics module + reconciliation, scheduled data exports; Exports tab | P3-M11 | Pending |
| 3D-3 | Fleet intelligence: anomaly rules/detector/evidence, recommendations, ack + whitelisted remediation; Fleet Intelligence + AI Ops Rules screens | P3-M07 | Pending |
| 3E-1 | Enterprise SSO (OIDC) + claim mapping + audit; SSO screen | P3-GLO-002 | Pending |
| 3E-2 | White label: branding theme + custom-domain metadata + email identity (real SMTP adapter); regional tenancy metadata + platform admin views | P3-GLO-001/003/004 | Pending |
| 3E-3 | Advanced security: device identities + credential lifecycle sweeps, policy engine + violations, security analytics; Security Center | P3-M10 | Pending |
| 3E-4 | Integration catalogue (connectors/instances) + event-bus UI consolidation | P3-INT-101/102 | Pending |
| 3E-5 | Hardening: all 7 SRS §9 acceptance flows, failure-mode matrix (STEP 34), extended load smoke, security review, full regression sign-off | NFR3, §9, §10 | Pending |

Dependency notes: 3A-1 precedes everything (flags + events); 3A-2 precedes
3B-2 (external context) and feeds widgets; 3B-2 precedes 3B-3; 3C-1 sync
block precedes 3C-2 bundle block only in manifest-versioning order; 3D-1
depends on 1I campaigns + 2I PoP; 3D-2 closes 2I deferrals; 3E-2 email
work also closes the Phase-1 password-reset deferral.
