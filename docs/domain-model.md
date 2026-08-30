# Domain Model — Digital Signage Cloud Platform

Source of truth for requirements: SRS/FRD §10–§12. This file tracks the
implemented model; update it with every migration.

## Conventions

- Primary keys: UUIDv4 (`id`).
- Every tenant-owned table carries `organization_id` (or a provable parent
  chain to one) — enforced at repository level, never trusted from clients.
- Timestamps: `created_at` / `updated_at`, UTC (`TIMESTAMPTZ`).
- Status fields: string enums validated in the application layer.
- Soft delete via status transitions (`archived`, `deactivated`) for
  historically-referenced business entities; hard delete only for pure
  association rows.
- Published versions (asset/layout/playlist) are immutable rows.

## Entity relationship overview

```text
organizations 1--N users, locations, devices, assets, layouts, playlists,
              campaigns, deployments, notifications, audit_logs, api_keys, webhooks

users N--N roles (user_roles); roles N--N permissions (role_permissions)

locations: self-referencing tree (parent_id + materialized path)
locations 1--N devices
tags N--N locations / devices / assets

devices 1--N device_capabilities, device_heartbeats, device_events,
            playback_events, device_commands
device_groups 1--N devices (membership)

folders: self-referencing tree; folders 1--N assets
assets 1--N asset_versions (immutable, processing state machine)

layouts 1--N layout_versions (immutable canvas_json); version 1--N zones (JSON)
templates N--1 layouts

playlists 1--N playlist_items (item -> asset | layout)
playlists N--1 playlists (fallback)

campaigns N--1 layout, N--1 playlist
campaigns 1--N campaign_targets (location/subtree | device | group | tag, exclusions)
campaigns 1--N schedules (UTC window + recurrence + IANA timezone + priority)

deployments N--1 campaign; deployments 1--N deployment_devices (frozen target
snapshot, per-device status/attempts/ack)
```

## Implemented tables

### Migration 0001 — auth/tenant baseline

| Table | Key attributes | Notes |
|---|---|---|
| organizations | id, name, code (unique), status, timezone, locale, branding_json, quotas_json | Tenant root. status: active/suspended/archived |
| users | id, organization_id FK, email, full_name, password_hash, status, is_superuser, last_login_at | unique(organization_id, email). status: invited/active/deactivated |
| roles | id, organization_id FK nullable, name, description, is_system | org NULL = platform-level role. unique(organization_id, name) |
| permissions | id, code (unique), description | e.g. content.create, device.control |
| user_roles | user_id FK, role_id FK (composite PK) | |
| role_permissions | role_id FK, permission_id FK (composite PK) | |

### Migration 0002 — refresh tokens

| Table | Key attributes | Notes |
|---|---|---|
| refresh_tokens | id, user_id FK, jti (unique), token_hash (sha256, indexed), expires_at, revoked_at | Rotation: each refresh revokes the old row. Reuse of a revoked token revokes the user's whole session family. Tokens never stored in plaintext |

### Migration 0003 — location hierarchy

| Table | Key attributes | Notes |
|---|---|---|
| location_types | id, organization_id, code, name | Per-tenant dictionary; defaults seeded at org creation. unique(org, code) |
| locations | id, organization_id, parent_id, type_id, name, code, **path**, address, lat/lng, timezone, status, metadata_json | Materialized path `/<ancestors>/<id>/` (ADR-003). unique(org, parent, code); indexes (org, parent), (org, path). Archive is status-based; requires no active children. Timezone inherits: node → nearest ancestor → organization |
| tags | id, organization_id, key, value | unique(org, key, value); shared dictionary for locations (devices/assets later) |
| location_tags | location_id, tag_id | Replace-set assignment via POST /locations/{id}/tags |

### Migration 0004 — content CMS

| Table | Key attributes | Notes |
|---|---|---|
| folders | id, organization_id, parent_id, name, status | unique(org, parent, name); archive requires empty |
| assets | id, organization_id, folder_id, type, name, description, status, checksum, current_version_id | type derived from MIME; status draft/published/archived; current_version_id has no FK (circular) — maintained by content service |
| asset_versions | id, asset_id, version_no, object_key, thumbnail_key, mime_type, size_bytes, checksum, width/height/duration_ms, processing_status, processing_error | Immutable; unique(asset_id, version_no); state machine processing → ready/failed |
| asset_tags | asset_id, tag_id | Shares the org tag dictionary |
| upload_sessions | id, organization_id, asset_id (pre-generated), is_new_asset, filename, mime_type, size_bytes, object_key, version_no, status, expires_at | Policy validated at creation; object key `tenant/<org>/content/<asset>/v<n>/original/<file>` (ADR-004) |

### Migration 0005 — devices

| Table | Key attributes | Notes |
|---|---|---|
| organizations (+) | enrollment_key (unique) | Secret devices present to enroll; minted lazily |
| devices | id, organization_id, location_id, group_id, name, manufacturer/model/platform/os/player versions, serial_no, mac/ip, orientation, screen w/h, timezone, status, token_hash, token_issued_at, approved_at, last_heartbeat_at, last_heartbeat_json | unique(org, serial_no); lifecycle pending/active/rejected/decommissioned; online/warning/offline derived from last_heartbeat_at (never stored); opaque credential stored as SHA-256, issued once, revocable |
| device_groups | id, organization_id, name, description | unique(org, name); delete requires empty |
| device_tags | device_id, tag_id | Shares the org tag dictionary |
| device_capabilities | id, device_id, capability_code, supported, value_json | unique(device, code); replace-set via player API |
| device_commands | id, organization_id, device_id, command_type, payload_json, status, sent_at, acknowledged_at, result_json | queued → sent (on poll) → acknowledged/failed |
| device_heartbeats | id, device_id, observed_at, payload_json | Append-only history, retention-managed later |

### Migration 0006 — layout engine

| Table | Key attributes | Notes |
|---|---|---|
| layouts | id, organization_id, name, description, status, draft_canvas_json, current_version_id | Designer edits the draft; status draft/published/archived; current_version_id has no FK (circular) |
| layout_versions | id, layout_id, version_no, canvas_json, published_at | Immutable snapshots; unique(layout, no); what player manifests embed |
| layout_zones | id, layout_version_id, zone_key, zone_json | Normalized per version for future content-usage queries; unique(version, key) |
| templates | id, organization_id, layout_id (provenance, nullable), name, description, canvas_json, metadata_json | unique(org, name); carries its own canvas copy; 3 starters seeded per org |

Canvas JSON contract (schemas/canvas.py): `{schema_version: 1, canvas: {width, height, background, orientation}, zones: [{key, name, x, y, width, height, z_index, rotation, style, content_type, content_config}]}` — generic zones, unique keys, ≤50 zones, content types: placeholder/image/video/playlist/text/ticker/clock/web/widget/qr. Asset bindings validated at publish (tenant-owned + READY).

### Migration 0007 — playlists

| Table | Key attributes | Notes |
|---|---|---|
| playlists | id, organization_id, name, description, status, loop_enabled, fallback_playlist_id (self-FK, cycle-checked), current_version_id | Playlist = WHAT plays; schedule/target live elsewhere. current_version_id has no FK (circular) |
| playlist_items | id, playlist_id, position, item_type (asset\|layout), asset_id, layout_id, duration_ms (NULL = natural length, video/audio only), transition_json, enabled | Draft rows; exactly one reference set; positions compacted on delete |
| playlist_versions | id, playlist_id, version_no, items_json, published_at | Immutable snapshot of enabled items with layout versions pinned; unique(playlist, no) |

### Migration 0008 — campaigns (minimal) & schedules

| Table | Key attributes | Notes |
|---|---|---|
| campaigns | id, organization_id, name, description, status, priority (1-100), playlist_id, layout_id | Status enum covers the full FR-CMP-001 lifecycle; 1H uses draft/archived, approval/publish transitions wired in 1I |
| schedules | id, organization_id, campaign_id, name, start_date/end_date (inclusive, NULL = open), start_time/end_time (daily wall-clock window, end exclusive, end < start wraps midnight), days_of_week (JSON, 0=Mon..6=Sun, NULL = all), timezone (NULL = inherit device→location→org), priority | Decomposes SRS start_at/end_at + recurrence_json into typed columns; evaluated by services/scheduling.py (pure engine, also used by 1I manifests) |

### Migration 0009 — publishing

| Table | Key attributes | Notes |
|---|---|---|
| campaign_targets | id, campaign_id, target_type (location\|device\|group\|tag), target_id, include_descendants, is_exclusion, conditions_json | Logical definition; exclusions win (SRS §12.1); resolution in services/targeting.py |
| deployments | id, organization_id, campaign_id, version, status, target_snapshot_json, error, started_at, completed_at | States queued→publishing→partial/published/failed/cancelled (§14); republish supersedes prior active deployments; snapshot never silently changes |
| deployment_devices | id, deployment_id, device_id, status (pending\|acknowledged\|failed), attempts, last_error, acknowledged_at | Frozen at materialization; unique(deployment, device); player acks are idempotent |

### Migration 0010 — operations

| Table | Key attributes | Notes |
|---|---|---|
| audit_logs | id, organization_id, user_id, action, entity_type, entity_id, before/after_json, ip_address, request_id, created_at | Server-side only (SRS §16); actor/IP/request-id captured from request context |
| notifications | id, organization_id, user_id (NULL = org broadcast), type, severity, title, message, payload_json, read_at | Types: DEVICE_REGISTRATION, APPROVAL_REQUESTED, DEPLOYMENT_DEVICE_FAILED, DEVICE_OFFLINE (beat task, deduped per offline episode) |
| device_events | id, device_id, event_type, event_at, payload_json | Player-reported operational events (batch ingest, ≤500) |
| playback_events | id, organization_id, device_id, campaign_id, playlist_id, asset_id, started_at, ended_at, result | Proof-of-play foundation; aggregated by /reports/playback |

### Planned (per Phase-1 slice; see SRS §10.1 for full attribute catalogue)
- 1J/monitoring: device_heartbeats, device_events, playback_events, notifications, audit_logs, api_keys, webhooks

## Critical indexes (from SRS §11.1)

Applied as tables are created:

- locations: (organization_id, parent_id); unique(organization_id, parent_id, code); path pattern index
- devices: (organization_id, status); (location_id); (last_heartbeat_at); unique(organization_id, serial_no)
- assets: (organization_id, type, status); (checksum); (folder_id)
- asset_versions: unique(asset_id, version_no)
- campaign_targets: (campaign_id, target_type, target_id)
- schedules: (campaign_id, start_at, end_at)
- deployments: (organization_id, created_at); (status)
- deployment_devices: unique(deployment_id, device_id)
- playback_events: (device_id, started_at); (campaign_id, started_at)
- audit_logs: (organization_id, created_at); (entity_type, entity_id)
