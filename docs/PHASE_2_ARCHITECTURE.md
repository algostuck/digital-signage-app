# Phase 2 — Architecture

Extends [architecture.md](architecture.md); ADR-001..005 remain in force.
Rule: extend/reuse/generalize — never duplicate Phase-1 business logic.

## Backend

Same modular monolith. New/extended domain modules (each with the standard
api → schemas → services → repositories layering):

```text
approvals      NEW  policies, requests (polymorphic), actions, maker-checker
device_ops     EXT  dynamic groups, bulk actions, screenshots, incidents
releases       NEW  player packages, rollout rings, rollback
studio         EXT  template versions, widget catalogue, bindings, collections
campaigns      EXT  variants, blackout schedules, target preview
scheduling     EXT  monthly recurrence, exception dates, blackout-aware engine
monitoring     EXT  fleet-health rollups, per-tenant thresholds, incidents
notifications  EXT  rules, escalation, channels (in-app, email, webhook)
integrations   NEW  webhook subscriptions/deliveries, API keys
search         NEW  global search, saved views, bulk edit
reports        EXT  uptime, PoP lifecycle, report builder, CSV/XLSX export
tenant_admin   EXT  quotas usage, policy defaults, retention
audit          EXT  evidence links, retention pruning, export
```

## Event dispatch (internal)

`app/core/events.py`: synchronous in-process emit from services
(`DEVICE_OFFLINE`, `DEVICE_RECOVERED`, `DEPLOYMENT_FAILED`,
`APPROVAL_REQUESTED`, `APPROVAL_DECIDED`, `CAMPAIGN_PUBLISHED`,
`PLAYBACK_BATCH`, `ROLLOUT_STOPPED` …). Each event:
1) evaluates tenant notification_rules → creates notifications /
   escalation timers / email jobs; 2) enqueues webhook deliveries for
   matching subscriptions. Both effects run inside the request transaction
   for the DB rows; outbound I/O (email, webhook POST) happens in workers.

## Background processing

| Queue | New tasks |
|---|---|
| integrations (new) | webhook delivery (HMAC signing, exponential backoff 1m→2m→4m… max N, dead-letter), email send |
| maintenance | escalation sweep, retention pruning (audit/heartbeats/events/playback per tenant policy), rollout ring advancement, scheduled report export (deferred) |
| publishing | unchanged; rollout batches reuse the pattern |

All tasks idempotent + retry-safe (NFR2-08); workers keep structured logs
with request/job correlation ids.

## Device communication (manufacturer-neutral, additive)

- Bulk actions & OTA reuse the existing pull command queue
  (`UPDATE_PLAYER {release_id, url, checksum}` command type).
- Screenshot flow: command `SCREENSHOT` → player POSTs
  `/player/{id}/screenshots` (signed storage PUT like uploads) → evidence row.
- Manifest additions (all optional fields): `variant`, `blackout_until`,
  `player_release` hint. Existing players ignore unknown fields.
- Playback event vocabulary extended: `scheduled|delivered|downloaded|
  started|completed|failed` (`delivered` derived from deployment ack).

## Database

New tables (see PHASE_2_DATABASE_CHANGES.md): approval_policies,
approval_requests, approval_actions, template_versions, widgets,
widget_versions, asset_collections(+items), campaign_variants(+targets),
player_releases, rollout_batches, rollout_devices, notification_rules,
notification_deliveries, webhook_subscriptions, webhook_deliveries,
api_keys, saved_views, screenshots, incidents.
Altered (additive only): device_groups (+group_type, rule_json),
schedules (+kind, recurrence extension, exception_dates),
organizations (+settings_json policy defaults), templates (+status,
current_version_id), playback_events (+status vocabulary already stringly).

## Security

- API keys: `sgk_<random>` shown once; SHA-256 hash stored; scopes are
  permission-code subsets; expiry + revocation + last_used_at; audited.
- Webhooks: per-subscription secret (shown once), `X-Signature:
  sha256=HMAC(body)`, allow-list of event types, no internal errors leaked.
- Approval engine enforces maker≠checker server-side when policy demands.
- All new tables tenant-scoped; repository pattern unchanged; cross-tenant
  access returns 404. New permission codes extend the catalogue
  (releases.manage, templates.approve, widgets.manage, webhooks.manage,
  api_keys.manage, incidents.manage, saved_views implicit, reports.export).

## Frontend

Same React/TS structure; new modules: `approvals`, `releases`, `widgets`,
`monitoring` (fleet/incidents), `integrations`, `search`, `reportsplus`.
Existing pages extended in place (Devices, Campaigns, Schedules, Templates
within Design, Reports, Notifications, Settings). Shared additions: rule
builder control, saved-view bar, export button, severity/status badges.
22 Phase-2 screens map onto ~14 routes (several are tabs/drawers of
existing pages) — see PHASE_2_SCREEN_IMPLEMENTATION_MATRIX.md.

## Observability

Structured logs unchanged; every worker task logs job id/status/attempts.
Fleet-health and webhook delivery stats exposed via APIs (metrics endpoint
export deferred to Phase 3 as before).

## Explicit non-goals (per SRS §10)

No microservice split, no external search engine, no message broker beyond
Redis/Celery, no PDF rendering engine (CSV/XLSX only, PDF documented as
deferred), no SSO federation, no video-wall sync.
