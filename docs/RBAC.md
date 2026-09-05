# Roles and Permissions (RBAC)

Two gates protect every tenant action: the user's **permission** (this
page) and the tenant's **entitlement** ([SAAS_CORE.md](SAAS_CORE.md)).
Both are enforced by the API; the portal reads the same permission list
from `/auth/me` to decide what to show, and the UI pass in
[HARDENING_AUDIT.md](HARDENING_AUDIT.md) §2 verified they agree.

## Model

- **Permissions** are fixed codes, `<area>.<action>` (43 today, listed
  below). New features add codes through a migration + `app/seed.py`.
- **System roles** are shared by every tenant and cannot be edited:
  Organization Administrator, Content Manager, Device Manager, Viewer.
- **Custom roles** are per tenant (Users & Roles › Roles): any set of
  permission codes, e.g. the demo tenants' *Campaign Approver*
  (`campaigns.approve` only, for maker-checker), *Regional Operations
  Manager* and *Report Viewer*.
- A user holds one or more roles in the tenant that owns their account;
  a **guest membership** in another tenant carries its own role there
  (tenant switching, [SAAS_CORE.md](SAAS_CORE.md) §1).
- The **Platform Administrator** (`is_superuser`) is not a tenant role: it
  reaches `/platform/*`, bypasses permission checks inside a tenant it has
  switched into, and is confined to active tenants by membership rules.

## System roles × permissions

| Permission | Content Manager | Device Manager | Organization Administrator | Viewer |
|---|:-:|:-:|:-:|:-:|
| `ads.manage` |  |  | ✓ |  |
| `ads.view` | ✓ | ✓ | ✓ | ✓ |
| `api_keys.manage` |  |  | ✓ |  |
| `audit.view` | ✓ | ✓ | ✓ | ✓ |
| `billing.manage` |  |  | ✓ |  |
| `billing.view` | ✓ | ✓ | ✓ | ✓ |
| `campaigns.approve` |  |  | ✓ |  |
| `campaigns.manage` | ✓ |  | ✓ |  |
| `campaigns.publish` | ✓ |  | ✓ |  |
| `campaigns.view` | ✓ | ✓ | ✓ | ✓ |
| `content.create` | ✓ |  | ✓ |  |
| `content.delete` | ✓ |  | ✓ |  |
| `content.edit` | ✓ |  | ✓ |  |
| `content.view` | ✓ | ✓ | ✓ | ✓ |
| `deployments.manage` |  | ✓ | ✓ |  |
| `deployments.view` | ✓ | ✓ | ✓ | ✓ |
| `devices.control` |  | ✓ | ✓ |  |
| `devices.manage` |  | ✓ | ✓ |  |
| `devices.view` | ✓ | ✓ | ✓ | ✓ |
| `incidents.manage` |  | ✓ | ✓ |  |
| `layouts.manage` | ✓ |  | ✓ |  |
| `layouts.view` | ✓ | ✓ | ✓ | ✓ |
| `locations.manage` |  |  | ✓ |  |
| `locations.view` | ✓ | ✓ | ✓ | ✓ |
| `members.manage` |  |  | ✓ |  |
| `monitoring.view` | ✓ | ✓ | ✓ | ✓ |
| `notifications.view` | ✓ | ✓ | ✓ | ✓ |
| `organization.manage` |  |  | ✓ |  |
| `organization.view` | ✓ | ✓ | ✓ | ✓ |
| `playlists.manage` | ✓ |  | ✓ |  |
| `playlists.view` | ✓ | ✓ | ✓ | ✓ |
| `releases.manage` |  | ✓ | ✓ |  |
| `reports.export` | ✓ |  | ✓ |  |
| `reports.view` | ✓ | ✓ | ✓ | ✓ |
| `roles.manage` |  |  | ✓ |  |
| `roles.view` | ✓ | ✓ | ✓ | ✓ |
| `schedules.manage` | ✓ |  | ✓ |  |
| `schedules.view` | ✓ | ✓ | ✓ | ✓ |
| `settings.manage` |  |  | ✓ |  |
| `users.manage` |  |  | ✓ |  |
| `users.view` | ✓ | ✓ | ✓ | ✓ |
| `webhooks.manage` |  |  | ✓ |  |
| `widgets.manage` | ✓ |  | ✓ |  |

- **Organization Administrator** — every permission (43).
- **Content Manager** — content, layouts, widgets, playlists, campaigns
  (create, publish), schedules, exports; read everywhere else (27).
- **Device Manager** — devices, groups, control commands, deployments,
  incidents, player releases; read everywhere else (22).
- **Viewer** — read-only across every module (17).

## How it is enforced

| Layer | Mechanism |
|---|---|
| Route | `dependencies=[require_permissions("campaigns.manage")]` on the router (all codes listed must be held; superusers bypass) |
| Service | maker-checker and approval decisions check the *approver* inside the service (the submitter cannot approve their own request even with `campaigns.approve`) |
| Platform surface | `require_superuser` on every `/platform` route; tenant roles never reach it whatever they hold |
| API keys | scopes are a subset of permission codes chosen at key creation; the key's principal has exactly those |
| Navigation and buttons | `hasPermission(code)` / `canManage` in the portal; pages a role may open without the page permission show a "requires X" state |
| Tests | `tests/test_rbac.py`, per-module `*_rbac_and_isolation` tests, and the role checks in `scripts/audit_e2e_journey.py` |

Denials answer `403 FORBIDDEN` with `Missing permission: <code>`; ids the
caller's tenant does not own answer `404` (no existence disclosure).

## Changing roles safely

- Add a permission: migration + seed entry + route dependency + the
  navigation/permission map in the portal; give it to the system roles
  that should have it in `app/seed.py` — existing custom roles do not
  gain it automatically.
- Editing a custom role takes effect on the user's next request (the
  permission set is read on every request, not cached in the token).
- Deactivating a user (Users › Deactivate) ends their sessions at the
  next token refresh; revoking is immediate for API keys and devices.
