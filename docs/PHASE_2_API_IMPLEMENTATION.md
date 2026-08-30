# Phase 2 — API Implementation

All endpoints follow the Phase-1 conventions ([api-guidelines.md](api-guidelines.md)):
`/api/v1`, standard envelope, tenant scoping from the principal, 404 for
cross-tenant, pagination on collections, explicit sub-resource transitions,
Idempotency-Key on selected mutating calls. This file is updated per slice
with request/response/validation detail; the table below is the committed
surface mapped from the SRS catalogue.

| Method | Endpoint | Permission | Notes | Status |
|---|---|---|---|---|
| POST/PATCH | /device-groups(/{id}) | devices.manage | + group_type (`static`\|`dynamic`), rule_json `{match: all\|any, conditions:[{field, operator, value}]}`; fields manufacturer/platform/model/status/tag/location, ops eq/ne/contains/in/in_subtree, ≤20 conditions; static ignores rules | **done** |
| GET | /device-groups | devices.view | + member_count (live for dynamic, membership for static) | **done** |
| POST | /device-groups/preview | devices.view | rule → {count, sample[≤10]} without saving | **done** |
| POST | /device-groups/{id}/actions | devices.control | queues one command per active member (≤1000, 422 above); returns {queued, skipped}; audited DEVICE_BULK_COMMAND | **done** |
| POST | /devices/bulk | devices.manage | device_ids + set group/location, add_tags/remove_tags; active devices only | **done** |
| GET/POST | /player-releases(/{id}) | releases.manage | package = uploaded asset ref (must have a ready version; checksum/size copied); version unique per org (409); detail embeds rollout ring progress | **done** |
| POST | /player-releases/{id}/rollouts | releases.manage | {group_id?, rings? (default [10,50,100], strictly increasing to 100, ≤6), failure_threshold_pct 0..100}; one rollout per release (422); target must resolve to ≥1 active device; activates release | **done** |
| POST | /player-releases/{id}/rollback | releases.manage | active only (422 otherwise); halts pending/in-progress rings, withdraws offer; ROLLOUT_ROLLED_BACK notification; downgrade = roll out a new release of the older package | **done** |
| GET | /rollouts /rollouts/{id} | releases.manage | list = releases with rings; {id} = per-device states + failure reasons for one ring | **done** |
| POST | /player/{id}/releases/{rid}/ack | device token | player progress: updating/succeeded/failed (+error ≤500); only accepted from the in-progress ring (404 otherwise); success sets device.player_version; heartbeat response carries the offer as `update` {release_id, version, url, sha256, size_bytes} | **done** |
| POST/PUT/PATCH | /templates, /templates/{id} | layouts.manage | create from scratch (blank WxH) or layout_id; edit only draft/rejected (422 otherwise; editing rejected returns it to draft); DELETE archives; GET /templates/{id}/versions lists immutable snapshots | **done** |
| POST | /templates/{id}/submit | layouts.manage | validates canvas + widget configs + {{bindings}} whitelist, then enters approval engine (entity "template", approve perm layouts.manage); approval snapshots TemplateVersion; auto-approves when tenant policy off | **done** |
| GET | /approvals/inbox | any *.approve | pending/returned/decided queues; ?state, ?entity_type, paginated | **done** |
| GET | /approvals/{id} | any *.approve | detail with action trail | **done** |
| POST | /approvals/{id}/approve\|reject | entity-specific approve perm | maker≠checker enforced (422); comments ≤2000; idempotence: decided requests reject re-decision (422) | **done** |
| GET/PUT | /approval-policies(/{entity_type}) | settings.manage | require_approval + maker_checker per entity type; audited | **done** |
| GET/POST/PATCH | /widgets (+/{id}/versions) | layouts.view (read) / widgets.manage (write) | field-list config schema {fields:[{key,label,type,required,options,default}]}, types string/number/boolean/select/url/color, ≤30 fields; defaults validated against schema; versions immutable; fallback_json; name unique per org (409) | **done** |
| GET | /data-variables | layouts.view | approved binding catalogue (date/time/datetime/device.name/device.location/org.name/weather.temp/weather.condition) | **done** |
| GET/POST/PATCH/DELETE | /asset-collections (+PUT /{id}/items, POST /{id}/add-to-playlist) | content.view/edit; playlists.manage for reuse | ordered replace-set items (dupes 400, assets tenant-checked); add-to-playlist appends collection assets as playlist items in order | **done** |
| GET/POST/DELETE | /campaigns/{id}/variants(/{vid}) | campaigns.view/manage | name unique per campaign, ≤20 variants; must override layout and/or playlist; ≥1 target (location/device/group/tag, shared resolver, no exclusions); manifest applies highest-priority matching variant per device | **done** |
| POST | /campaigns/{id}/targets/preview | campaigns.view | resolves a proposed target set (incl. exclusions) without saving → {count, sample[≤10]} | **done** |
| GET | /schedules/calendar | schedules.view | alias of /calendar; events now carry kind; blackouts excluded from conflict detection | **done** |
| POST | /schedules/conflicts | schedules.view | dry-run: proposed schedule expanded vs whole calendar (≤62 days) → overlaps with winner + reason; equal campaign priority ⇒ conflict=true; winner rule mirrors runtime resolution (campaign priority → schedule priority → recency) | **done** |
| POST/PATCH | /schedules (ext) | schedules.manage | +kind (play\|blackout), recurrence_json {days_of_month:[1..31]}, exception_dates_json (≤100 ISO dates); validated; manifest ships all fields for offline evaluation | **done** |
| GET | /monitoring/fleet-health | monitoring.view | org rollup (+open_incidents, outdated_players) + location subtree rollups (materialized path) + group rollups (incl. dynamic); evaluated against tenant thresholds | **done** |
| GET/PUT | /monitoring/thresholds | monitoring.view / settings.manage | per-tenant warning/offline seconds (30..86400, warning<offline), storage_alert_percent (50..100), min_player_version; stored in organizations.settings_json.monitoring; audited; enforced by connection_status, offline sweep and heartbeat storage check | **done** |
| GET | /devices/{id}/events | devices.view | merged timeline: player events + incident opens + recoveries, newest first, ?limit≤200 | **done** |
| GET/POST | /devices/{id}/screenshots, /player/{id}/screenshots | devices.view / device token | player uploads raw PNG/JPEG body (Content-Type header, 5 MB cap, 10/min per device); stored via storage adapter under tenant/{org}/screenshots/, sha256 recorded; admin GET returns signed URLs, newest first | **done** |
| GET/POST | /incidents, /incidents/{id}/acknowledge\|resolve | monitoring.view (list) / incidents.manage (transitions) | open→acknowledged→resolved; device_offline incidents deduped per episode and auto-resolved on heartbeat (DEVICE_RECOVERED notification) | **done** |
| GET | /reports/proof-of-play | reports.view | ?group_by=campaign\|asset\|device\|location, ?date_from/to, ?campaign_id, ?location_id (subtree); rows: plays, completed, completion_rate, devices_reached, first/last play | **done** |
| GET | /reports/campaign-performance | reports.view | delivery KPI (acked/pending/failed) merged with playback KPI (plays, completed, completion rate, devices_played) per campaign; ?date_from/to on playback side | **done** |
| GET | /reports/device-uptime | reports.view | heartbeat windows: beat covers min(gap, tenant offline threshold); ?date_from/to (default last 7 days); covered/window seconds + uptime % | **done** |
| POST | /reports/export | reports.export | {report: one of 6 catalogue reports, format: csv\|xlsx, filters}; CSV = UTF-8 BOM; XLSX = dependency-free OOXML; Content-Disposition filename; audited REPORT_EXPORTED; PDF out of scope | **done** |
| GET/POST/PATCH/DELETE | /notification-rules | notifications.view (read) / settings.manage (write) | name unique per org (409); event_type from catalogue or `*`; condition {severity:[...]}; channels 1..10 (in_app / email w/ address / webhook w/ http(s) URL); escalation_minutes 1..1440; audited | **done** |
| GET | /notification-events | notifications.view | event catalogue for the rule builder | **done** |
| GET | /notification-deliveries | notifications.view | delivery evidence (?rule_id filter, paginated): channel, recipient, state pending/delivered/failed, attempts, last_error, source notification | **done** |
| GET/POST/PATCH/DELETE | /webhooks(/{id}) (+POST /{id}/rotate-secret) | webhooks.manage | http(s) URL + event-type list from catalogue (≤20 subs/org); secret `whsec_` revealed only in create/rotate responses; HMAC-SHA256 body signature in X-Webhook-Signature | **done** |
| GET | /webhooks/{id}/deliveries (+POST /webhooks/deliveries/{id}/replay) | webhooks.manage | states pending/delivered/failed/dead, attempt_no, response_code, last_error, next_attempt_at; replay re-queues dead letters | **done** |
| GET/POST/DELETE | /api-keys(/{id}) | api_keys.manage | raw `dsk_` key shown once (SHA-256 stored, NFR2-05); scopes = permission codes; expires_at future-dated; DELETE = revoke (audited); X-API-Key header authenticates as a tenant-locked scoped principal, last_used tracked | **done** |
| GET | /audit-logs (P1 name kept) | audit.view | filters by actor/entity/action/date since Phase 1; UI adds evidence deep-links per entity type | **done** |
| GET | /organization/usage | organization.view | live device/user/storage usage vs quotas_json limits | **done** |
| PATCH | /organization/quotas | organization.manage | max_devices/max_users/max_storage_mb (positive int or null = unlimited); audited; enforced at registration/user-create/upload | **done** |
| GET/PUT | /organization/retention | settings.manage | per-table retention days with platform floors/ceilings (audit_logs ≥ 90); audited; applied by prune_retention sweep (RETENTION_PRUNED evidence) | **done** |
| POST | /reports/export {report:"audit"} | reports.export + audit.view | audit trail as CSV/XLSX with action/entity_type/user/date filters | **done** |
| GET/POST/DELETE | /saved-views(/{id}) | authenticated | personal (owner-only, even same-org); module whitelist; name unique per owner+module (409); filter_json + columns_json | **done** |
| GET | /search | authenticated | ?q= (min 2 chars) across devices/content/locations/campaigns/playlists/schedules/users; each module present only when the caller holds its .view permission; ≤10 rows per module | **done** |

Backward compatibility: every Phase-1 endpoint remains unchanged;
campaign approval endpoints delegate into the approval engine.
