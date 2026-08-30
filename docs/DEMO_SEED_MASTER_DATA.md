# Demo Seeding — System Master vs Demo Data

The classification that makes the demo dataset safe to wipe and rebuild.
Derived from the actual models in `backend/app/models/`, not assumed.

## 1. The safety rule

The demo seeder (`backend/app/demo_seed.py`) only ever considers
organizations whose `code` is one of:

```
RRL-DEMO   Reliance Retail Digital Experience
BMR-DEMO   BharatMart Retail Network
USP-DEMO   UrbanSquare Properties
```

Everything it deletes is scoped by `organization_id IN (those three)`.
There is no unscoped `TRUNCATE`, no "delete everything that isn't
system" heuristic, and no assumption that non-system rows are disposable.
Any other tenant — including a real customer or UAT tenant — is invisible
to the reset by construction.

There is **no `is_demo` column anywhere in the schema** (verified across
all 30 model files), so the org-code convention *is* the demo marker.
Each demo tenant additionally carries `settings_json.demo = true` for
identification in the UI/API.

## 2. Preserved: system master data

Never written or deleted by the demo seeder. These stay the
responsibility of `app/seed.py`, which remains the bootstrap seeder.

| Table | Why it is master data |
|---|---|
| `permissions` | Platform permission catalogue (43 codes) |
| `roles` where `organization_id IS NULL` | The four system roles (`is_system=true`) |
| `role_permissions` | System role → permission grants |
| `plans`, `plan_entitlements` | Subscription plan definitions and their feature/limit entitlements |
| `api_products`, `api_versions` | Platform API catalogue (Phase 3 developer portal) |
| `location_types` | Per tenant, but re-seeded from the platform default list |

## 3. Preserved: the `demo` organization

`demo` / `admin@demo-org.com` is **deliberately excluded** from the demo
reset even though it is a demo-ish tenant, for two concrete reasons:

1. It homes **`platform@signage.cloud`**, the Super Admin. `User` is
   tenant-scoped, so deleting the org would delete the platform
   administrator.
2. The entire automated test suite authenticates as
   `admin@demo-org.com` in that org (`backend/tests/conftest.py`).
   Removing it would break every test.

## 4. Rebuilt: demo tenant/business data

Everything below is deleted and recreated on each seeder run, scoped to
the three demo organizations. Tenant-scoped tables are cleared by
`organization_id`; their children are removed by `ON DELETE CASCADE`.

**Tenant-scoped (have `organization_id`)** — organizations, users,
tenant_users, roles (tenant-owned), subscriptions, subscription_events,
plan_change_requests, usage_counters, usage_events, invoices, payments,
location_types, tags, locations, device_groups, devices, device_commands,
incidents, screenshots, folders, assets, upload_sessions, layouts,
templates, widgets, asset_collections, playlists, campaigns, schedules,
deployments, player_releases, rollout_batches, approval_policies,
approval_requests, audit_logs, notifications, playback_events,
webhook_subscriptions, webhook_deliveries, api_keys, notification_rules,
notification_deliveries, saved_views, ad_inventory, ad_bookings,
ai_policies, ai_requests, ai_outputs, analytics_aggregates, data_exports,
anomaly_rules, anomalies, data_sources, decision_policies, decision_log,
edge_bundles, domain_events, event_subscriptions, event_deliveries,
experiments, device_identities, security_policies, policy_violations,
sso_providers, video_walls.

**Child rows removed by cascade** — user_roles, refresh_tokens,
subscription_items, asset_versions, layout_versions, layout_zones,
template_versions, widget_versions, asset_collection_items,
playlist_items, playlist_versions, campaign_variants,
campaign_variant_targets, campaign_targets, deployment_devices,
rollout_devices, approval_actions, ad_playback_links, anomaly_actions,
data_source_schemas, data_source_snapshots, decision_rules,
edge_bundle_devices, experiment_variants, experiment_assignments,
identity_credentials, video_wall_members, device_capabilities,
device_heartbeats, device_events, location_tags, device_tags, asset_tags.

## 5. Deletion order

Two constraints shape the teardown:

1. `TenantMixin` FKs to `organizations` are **`ON DELETE RESTRICT`**, so
   every tenant-scoped child must go before the organization row. The
   seeder walks `Base.metadata.sorted_tables` in reverse (children first)
   and issues one scoped `DELETE` per table that has an
   `organization_id`.
2. `locations.parent_id` and `folders.parent_id` are **self-referential
   RESTRICT**. PostgreSQL enforces RESTRICT per row even within a single
   statement, so deleting a whole tree in one sweep fails. Those two
   tables are peeled leaf-first in a loop
   (`_delete_self_referential`) before the general pass.

## 6. Commands

```bash
python -m app.seed              # system master data (+ the `demo` fixture org)
python -m app.demo_seed         # reset + rebuild the three Indian demo tenants
python -m app.demo_seed --reset # remove the demo tenants only
python -m app.demo_seed --validate  # run the 17 integrity checks, change nothing
```

`app.demo_seed` refuses to run when `ENVIRONMENT=production`.
