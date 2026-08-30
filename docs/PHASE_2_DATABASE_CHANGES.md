# Phase 2 — Database Changes

All migrations additive and reversible; every tenant-owned table carries
`organization_id`; UUID PKs, UTC timestamps, indexes per access pattern.
Migrations land per vertical slice (0011+), never edited after merge.

## Planned migrations

| Migration | Tables / changes | Slice |
|---|---|---|
| 0011 | approval_policies (org, name, entity_type, rules_json, active); approval_requests (org, entity_type, entity_id, state, requester_id, submitted_at, current_comment); approval_actions (request_id, actor_id, action, comments, from_state, to_state, created_at — append-only) | Approval engine — **applied** (SQLite + PostgreSQL, up/down/up verified) |
| 0012 | device_groups + group_type ('static'\|'dynamic'), rule_json; screenshots (org, device_id, object_key, captured_at, checksum); incidents (org, device_id, type, severity, state open/acknowledged/resolved, opened_at, acknowledged_by/at, resolved_at, payload_json) | Device ops — **applied** (SQLite + PostgreSQL, up/down/up verified) |
| 0013 | player_releases (org, version, package_asset_id, checksum, notes, state draft/active/rolled_back); rollout_batches (release_id, ring_no, percentage, state, failure_threshold_pct, started_at, completed_at); rollout_devices (batch_id, device_id, state pending/updating/succeeded/failed, failure_reason, unique(batch,device)) | OTA — **applied** (SQLite + PostgreSQL, up/down/up verified). Implementation notes: batch carries organization_id + failure_threshold_pct; percentages are cumulative; batch states pending/in_progress/completed/stopped; device states pending/updating/succeeded/failed |
| 0014 | templates + status/current_version_id; template_versions (template_id, version_no, canvas_json, published_at, created_by); widgets (org, type, name, status, fallback_json); widget_versions (widget_id, version_no, config_schema_json, defaults_json); asset_collections (org, name) + asset_collection_items (collection_id, asset_id, position) | Studio — **applied** (SQLite + PostgreSQL, up/down/up verified). Deviations: no template_zones table (zones live in canvas_json, consistent with Phase-1 layouts); widget schema is a field-list format, not JSON-Schema; new migration-parity test guards model/migration drift |
| 0015 | campaign_variants (campaign_id, name, layout_id, playlist_id, priority); campaign_variant_targets (variant_id, target_type, target_id, include_descendants); schedules + kind ('play'\|'blackout'), recurrence_json (+monthly day-of-month), exception_dates_json | Campaigns/scheduling — **applied** (SQLite + PostgreSQL, up/down/up verified) |
| 0016 | organizations + settings_json (tenant policy store; monitoring thresholds live at settings_json.monitoring) | Monitoring — **applied** (SQLite + PostgreSQL, up/down/up verified). Split from the original plan: notification_rules + notification_deliveries move to migration 0017+ with slice 2G |
| 0017 | notification_rules (org, event_type, condition_json, channels_json, escalation_minutes, active); notification_deliveries (rule_id, notification_id, recipient, channel, state, attempts, delivered_at) | Notifications (2G) — **applied** (SQLite + PostgreSQL, up/down/up verified). Implementation notes: deliveries also carry organization_id, last_error, updated_at; escalation tracked via ESCALATION notifications keyed by source_notification_id (no extra column) |
| 0018 | webhook_subscriptions (org, url, event_types_json, secret_hash, active, description); webhook_deliveries (subscription_id, event_type, event_id, payload_json, attempt_no, state pending/delivered/failed/dead, response_code, next_attempt_at); api_keys (org, name, key_hash unique, prefix, scopes_json, expires_at, revoked_at, last_used_at) | Integrations — **applied** (SQLite + PostgreSQL, up/down/up verified). Deviation: subscriptions store the signing `secret` (HMAC needs it) rather than a hash — never exposed after the one-time reveal; managed secret storage is a deployment concern |
| 0019 | saved_views (org, user_id, module, name, filter_json, columns_json) | Search — **applied** (SQLite + PostgreSQL, up/down/up verified) |

## Deliberate reuse (no new tables)

- deployment_attempts (SRS ER) → covered by deployment_devices.attempts +
  audit; documented deviation.
- device_events, playback_events, api-side audit → exist since 0010;
  playback status vocabulary extended in-place (string column).
- Blackouts are schedules with kind='blackout' (no separate table).

## Retention

Maintenance task prunes device_heartbeats, device_events, playback_events,
webhook_deliveries, notifications and audit_logs per tenant policy
(settings_json.retention_days.*, platform floor/ceiling enforced).
