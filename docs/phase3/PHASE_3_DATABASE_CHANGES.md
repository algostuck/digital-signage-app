# Phase 3 — Database Changes

Rules unchanged from Phases 1–2: additive + reversible migrations, tenant
`organization_id` on every tenant-owned table, UUID PKs, UTC timestamps,
indexes per access pattern, model↔migration drift guarded by the parity
test (now on PostgreSQL). Secrets: never raw — hash or secret-ref columns.

> **Note (Aug 2026):** migration `0020` is now taken by the SaaS core
> (`0020_saas_core`: tenant_users, plans, plan_entitlements, subscriptions,
> subscription_items, subscription_events, usage_counters, usage_events,
> invoices, payments — see `docs/SAAS_CORE.md`). Phase-3 migrations start at
> **0021**; shift every planned number below by +1.

## Planned migrations (0021+, one per slice; numbers may shift with actual slicing)

| Migration | Tables / changes | Sub-phase |
|---|---|---|
| 0021 | ~~features namespace~~ (superseded: feature gating is the SaaS-core entitlement engine); `domain_events` (org, event_type, entity_type, entity_id, payload_json, occurred_at, request_id); `event_subscriptions` (org, event_types_json, destination_ref/url, secret, active); `event_deliveries` (subscription_id, event_id, state, attempt_no, response_code, next_attempt_at) — clones the proven 2H delivery shape | P3-A |
| 0021 | `data_sources` (org, name, type rest_json/rss, endpoint, auth_ref, cache_ttl_seconds, refresh_seconds, state, last_ok_at); `data_source_schemas` (source_id, version_no, schema_json); `data_source_snapshots` (source_id, fetched_at, valid, payload_json — bounded history, last-known-good); widget binding extension: `widgets`/zone binding may carry data_source_id + transform_json | P3-A |
| 0022 | `api_products` (name, description) + `api_versions` (product_id, version, lifecycle_state, sunset_at) — developer platform metadata | P3-A |
| 0023 | `ai_policies` (org, policy_type, rules_json, active); `ai_requests` (org, actor_id, operation, provider, model_ref, template_version, status, created_at); `ai_outputs` (request_id, output_kind, output_ref/asset_id, content_json, confidence, safety_status, approved_by, revision_no) | P3-B |
| 0024 | `decision_policies` (org, name, guardrails_json, active); `decision_rules` (policy_id, priority, conditions_json, actions_json); `decision_log` (org, device_id, campaign_id, reason_json, decided_at — bounded/retained) | P3-B |
| 0025 | `experiments` (org, campaign_id, name, allocation_json, start_at, end_at, status); `experiment_variants` (experiment_id, variant_ref, allocation_pct); `experiment_assignments` (experiment_id, device_id, variant_ref, unique(experiment,device)) | P3-B |
| 0026 | `video_walls` (org, name, canvas_json, sync_policy_json, status); `video_wall_members` (wall_id, device_id, viewport_json, role, unique(wall,device)) | P3-C |
| 0027 | `edge_bundles` (org, bundle_version, manifest_json, signature, expires_at, state); `edge_bundle_devices` (bundle_id, device_id, state, synced_at); org/device bandwidth policy in settings_json (no DDL) | P3-C |
| 0028 | `ad_inventory` (org, location_id, device_id, zone_ref, slot_type, operating_hours_json, rate_card_ref, active); `ad_bookings` (inventory_id, campaign_id, advertiser_ref, booked_units, start/end, frequency_json, status); `ad_playback_links` (booking_id, playback_event_id unique, billable, evidence_json) | P3-D |
| 0029 | `anomaly_rules` (org, signal_type, threshold_json, window, severity, active); `anomalies` (org, device_id, rule_id, score, state, evidence_json, opened_at); `anomaly_actions` (anomaly_id, actor_id, action, outcome, executed_at) | P3-D |
| 0030 | `analytics_aggregates` (org, grain_date, dimension_type, dimension_id, metrics_json, unique(org,date,dim)); `data_exports` (org, dataset, destination, schedule_json, state, last_run_at) | P3-D |
| 0031 | `sso_providers` (org, protocol oidc/saml, issuer, client_ref, metadata_json, claim_mapping_json, active); organizations + region/residency columns; branding schema documented (existing branding_json) | P3-E |
| 0032 | `device_identities` (device_id, identity_type, status); `identity_credentials` (identity_id, credential_ref/fingerprint, issued_at, expires_at, revoked_at); `security_policies` (org, scope_type, conditions_json, actions_json, active); `policy_violations` (policy_id, org, entity_type, entity_id, severity, state, detected_at) | P3-E |

## Deliberate reuse (no new tables)
- Ad campaign delivery/creatives → existing campaigns/playlists/assets (bookings reference campaign_id; SRS keeps payments external).
- Connector instances → `connectors` catalogue may live with `event_subscriptions` + `data_sources` covering the concrete integrations; add a thin `connectors`/`connector_instances` pair only if the catalogue UX requires it (decide in P3-E, documented).
- AI creative outputs → stored as normal draft assets/templates (governed by ai_outputs linkage), not a parallel content store.
- Fleet signals → existing device_heartbeats/device_events/incidents; anomalies reference, never duplicate.
- Bundle assets → existing asset versions + storage keys; the bundle stores a signed manifest, not copies.

## Growth / scale design
- `playback_events`, `domain_events`, `decision_log`, `data_source_snapshots`: retention-pruned (2K engine — new keys added to RETENTION_POLICY) and aggregate-fed; `playback_events` keyed to be PostgreSQL-partitionable by month when measured volume justifies (gate documented in analytics architecture).
- All *_deliveries tables reuse the 2H indexes shape (state, next_attempt_at).
