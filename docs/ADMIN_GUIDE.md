# Administrator Guide

For the people who run a tenant day to day. Platform (multi-tenant)
operations are in [PLATFORM_CONSOLE.md](PLATFORM_CONSOLE.md); the
device-side contract in [PLAYER_API_CONTRACT.md](PLAYER_API_CONTRACT.md).
Menu items appear only for roles that hold the matching permission
([RBAC.md](RBAC.md)).

## Signing in and switching tenants

Sign in with your email and password; the session refreshes itself and
ends after 14 days without use or when an administrator deactivates you.
People invited into more than one tenant switch with the tenant selector
in the header; each tenant has its own role for you.

## Dashboard

The executive view of the tenant: live KPIs, what needs attention, health
trend, map, campaigns, playback, deployments, content, top locations,
what is playing now, recent activity, approvals, today's schedule, plan
usage and insights. Every number links to the filtered list behind it.
Change the range with the presets or a custom window; *Customise* hides
and reorders sections per user. The page polls every 30 s and says when
it last succeeded; if a refresh fails the last good data stays with a
warning banner. See [ORGANIZATION_ADMIN_DASHBOARD_DATA_MAP.md](ORGANIZATION_ADMIN_DASHBOARD_DATA_MAP.md).

## Locations

Build the estate as a hierarchy (region → city → site → zone) with
*Add root location* and per-node actions. Coordinates place a node on the
dashboard map; devices attach to the lowest node (a store or a zone).
Moving a subtree keeps its devices; deleting is refused while devices or
campaigns still reference it.

## Devices

- **Enrol**: *Show enrollment key* (or rotate it), enter it in the player
  (or the Player Simulator); the device appears as *pending* — approve or
  reject it, then assign its location.
- **Operate**: search and filter (online / warning / offline are derived
  from heartbeat age against the thresholds in Monitoring), open a device
  for heartbeat, telemetry, events, screenshots and *TV preview* (what it
  shows now, or at a chosen time), send commands (reboot, refresh,
  screenshot, display on/off), reset its token, decommission it.
- **Groups**: static or rule-based groups for targeting and bulk actions.
- **Video walls** and **edge bundles** are plan features (Professional and
  above).
- **Player Simulator**: a real player in the browser for testing and
  demos — register, approve, and it plays whatever is published to it.

## Content

Upload images, video and documents (up to 512 MB each, storage counted
against the plan); organise them in folders and tags; each upload of an
existing asset becomes a new version. Publish before use, archive when
retired (restore is possible). *Collections* group assets for playlists.

## Design

- **Layouts**: the Screen Designer — canvas of a chosen resolution,
  zones (image, video, playlist, ticker, HTML/web, widgets, data-bound
  text), drag/resize, properties, *Preview*, *Save draft*, *Publish*
  (creates a version players use). The artboard always fits the card.
- **Templates**: reusable compositions; *Submit* sends one through
  approval, *Clone* starts a layout from it.
- **Widgets** (weather, clock, RSS, data-bound) and **AI Studio**
  (copy, creative and localisation — plan feature).

## Playlists

Ordered items (assets and layouts) with durations and transitions;
*Publish* freezes a version. Playlists are what campaigns bind to.

## Campaigns

1. Create with a playlist and/or a layout and a priority.
2. **Targets**: locations (with descendants), devices, groups or tags,
   with exclusions; *Preview* resolves the exact screens.
3. **Schedule**: play windows and blackout windows, recurrence, time
   zone. *Campaigns › Schedule* is the scheduling workspace: day / week /
   month views, filters by location, group, campaign, status, priority
   and type, a health panel whose conflict count is *actionable* (two
   windows only conflict when they overlap on the same screens), a
   *Review conflicts* list with the reason and how to resolve it, and the
   selected day's NOW PLAYING / NEXT / LATER beside the calendar. Click an
   empty slot to schedule, drag a window to move it (you confirm after a
   conflict check), hover or focus a window for its details.
4. **Approval**: submit; an approver (someone with `campaigns.approve`
   who is not the submitter when maker-checker is on) approves or returns
   it with a comment.
5. **Publish**: creates a deployment for the resolved screens; players
   acknowledge as they sync. *Pause*, *Resume*, *Archive* later.

Variants, experiments and decision policies are the advanced tabs.

## Publishing

Every deployment with per-device delivery status; *Retry failed* and
*Cancel*. A screen added to a location **after** a campaign was published
is not in that deployment — republish, or target the device.

## Monitoring, incidents and intelligence

Fleet health roll-ups, per-device status, incidents (acknowledge / resolve)
and anomaly detection with recommended actions (plan feature). Thresholds
for *warning* and *offline* are per tenant (Monitoring › Edit).

## Reports and analytics

Proof of play (per campaign, device, location, with completion rate),
playback, uptime, campaign performance, ads, and CSV/XLSX exports; the
Exports tab schedules recurring extracts. Proof of play and analytics
are plan features.

## Users, roles and members

Add users with roles; deactivate rather than delete (audit history stays).
Create custom roles from permission codes. *Members* manages guest access
for people who belong to another tenant.

## Notifications and audit

In-app inbox with severities; rules route events to email, webhooks and
escalations. *Audit Logs* records every consequential action with actor,
entity and before/after — the first place to look when something changed
unexpectedly ([OBSERVABILITY.md](OBSERVABILITY.md)).

## Settings

Organisation profile, **Plan & usage** (plan, entitlements, limits vs
usage, plan-change requests), quotas & retention, integrations (API keys,
webhooks, connectors, SSO — some plan-gated), branding / white label.
When something is unavailable the page says why: the plan that lacks it,
the limit that is reached, or the subscription state.

## Security Center

Device credential lifecycle (rotate, revoke), age policies and policy
violations.

## What to check when…

| Symptom | Look at |
|---|---|
| A screen shows old content | Publishing (was it in the deployment?), the device's manifest version in its detail, TV preview |
| A screen is offline | Devices › detail › events and heartbeat age; Monitoring thresholds |
| A button is missing | your role's permissions (RBAC) or the plan (Settings › Plan & usage) |
| An upload was refused | storage limit or file type; the message names the limit |
| Something changed and nobody knows who | Audit Logs |
