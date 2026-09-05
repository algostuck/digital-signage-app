# API Reference

The API is described by its OpenAPI document; this page is the map and
the conventions. Base path `/api/v1`, JSON only.

| | Where |
|---|---|
| Interactive docs (dev / UAT) | `http://<host>/api/docs` — disabled in production |
| OpenAPI JSON | `http://<host>/api/openapi.json` (dev / UAT); in production export it from a UAT build of the same version |
| Conventions (envelope, errors, paging, idempotency) | [api-guidelines.md](api-guidelines.md) |
| Device-facing contract (frozen) | [PLAYER_API_CONTRACT.md](PLAYER_API_CONTRACT.md) |
| Tenant switching, plans, entitlements, billing | [SAAS_CORE.md](SAAS_CORE.md) §6 |
| Platform (super admin) surface | [PLATFORM_CONSOLE.md](PLATFORM_CONSOLE.md) |
| Dashboard aggregate | [ORGANIZATION_ADMIN_DASHBOARD_DATA_MAP.md](ORGANIZATION_ADMIN_DASHBOARD_DATA_MAP.md) |

## Authentication

| Principal | How | Scope |
|---|---|---|
| Portal user | `POST /auth/login` → access token (30 min) + rotating refresh token (14 days); `Authorization: Bearer` | the user's permissions in the active tenant; `POST /auth/switch-tenant` for guests of several tenants |
| API key | `X-API-Key: dsk_…` (Settings › Integrations) | the key's tenant and explicit scopes; plan must include `api_access`; calls are metered |
| Player | `X-Device-Token` issued once by `POST /player/register` | exactly one device |
| Platform administrator | a user with `is_superuser` | `/platform/*` only via `require_superuser`; may switch into any active tenant |

Every response carries `meta.request_id` and the `X-Request-ID` header
([OBSERVABILITY.md](OBSERVABILITY.md)).

## Resource groups (339 routes)

| Group | Prefixes | Permission family |
|---|---|---|
| Auth & session | `/auth/*`, `/entitlements`, `/permissions`, `/plans` | — |
| Organization & members | `/organization`, `/organization/members`, `/organization/retention`, `/organization/white-label`, `/users`, `/roles` | `organization.*`, `users.*`, `roles.*`, `members.manage` |
| Locations | `/locations`, `/locations/tree`, `/location-types`, `/tags` | `locations.*` |
| Devices & fleet | `/devices`, `/device-groups`, `/video-walls`, `/edge/*`, `/monitoring/*`, `/incidents`, `/security/*`, `/player-releases`, `/rollouts`, `/fleet-intelligence/*` | `devices.*`, `monitoring.view`, `incidents.manage`, `releases.manage`, `settings.manage` |
| Content | `/assets`, `/assets/uploads`, `/folders`, `/asset-collections`, `/storage/local/*` (signed) | `content.*` |
| Design | `/layouts`, `/templates`, `/widgets`, `/data-sources`, `/data-variables`, `/ai/*` | `layouts.*`, `widgets.manage` |
| Playlists & campaigns | `/playlists`, `/campaigns`, `/campaigns/{id}/targets`, `/campaigns/{id}/variants`, `/experiments`, `/decision-policies`, `/decision-rules`, `/decision-log` | `playlists.*`, `campaigns.*` |
| Approvals & schedules | `/approvals/*`, `/approval-policies`, `/schedules`, `/schedules/calendar`, `/calendar` | `campaigns.approve`, `schedules.*` |
| Schedule workspace | `GET /schedules/calendar?from&to` (+ `location_id`, `group_id`, `device_id`, `campaign_id[]`, `status[]`, `kind`, `priority_min`, `priority_max`, `conflicts_only`) → events with status / recurrence / target counts / `live`, actionable `conflicts[]` graded high / medium / low on **shared screens**, `summary`, `timezone`, `now`; `POST /schedules/conflicts` dry-run. Contract: [SCHEDULE_UX_AUDIT.md](SCHEDULE_UX_AUDIT.md) §10 | `schedules.view` |
| Publishing | `/deployments` | `deployments.*`, `campaigns.publish` |
| Player (device-facing) | `/player/*` | device token |
| Reports & analytics | `/reports/*`, `/analytics/*`, `/data-exports`, `/dashboard/organization` | `reports.*` + plan entitlements |
| Advertising | `/ad-inventory`, `/ad-campaigns` | `ads.*` + `advertising` entitlement |
| Notifications & audit | `/notifications`, `/notification-rules`, `/notification-events`, `/notification-deliveries`, `/audit-logs`, `/events`, `/events/catalogue` | `notifications.view`, `audit.view` |
| Integrations | `/api-keys`, `/webhooks`, `/subscriptions` (event subscriptions), `/connectors`, `/sso/*`, `/developer/*` | `api_keys.manage`, `webhooks.manage`, `settings.manage` |
| Billing (tenant) | `/billing/*` | `billing.*` |
| Platform | `/platform/*` | superuser |
| Health | `/health`, `/health/ready` | public |

Two gates apply to every tenant route: the user's **permission**
([RBAC.md](RBAC.md)) and the tenant's **entitlement**
([SAAS_CORE.md](SAAS_CORE.md)); both are enforced server-side, the UI only
mirrors them.

## Versioning

`/api/v1` is stable. Additive changes (new optional fields, new routes)
ship without a version bump; any change of meaning ships under `/api/v2`
alongside `v1`. The player contract additionally carries
`manifest_version` inside its payload.
