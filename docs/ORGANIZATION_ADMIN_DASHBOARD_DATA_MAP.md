# Organization Administrator Dashboard — Data Map

Every number on the dashboard, where it comes from, and what would make
it wrong. Nothing on the page is hard-coded; every value below is a query
against the tenant's own rows.

## KPI strip

| Tile | Value | Source | Notes |
|---|---|---|---|
| Devices | `kpis.devices.total` | `monitoring.summary` | all lifecycle states |
| Online | `devices.online`, % of `active` | derived per read from `last_heartbeat_at` vs tenant thresholds | point-in-time; ignores the range |
| Offline | `devices.offline` | same | |
| Active campaigns | `campaigns.published` | `campaigns` grouped by status | pending-approval count as context |
| Playback | `playback.plays`, completion % | `playback_events` in range | `completed` = `result == "completed"`, `failed` = `error`/`failed` |
| Deployments | `publishing + partial` | `deployments` grouped by status | failed count as context |

Reconciliation rules (tested): `devices.total == online + warning + offline + na`;
`sum(playback.series.plays) == kpis.playback.plays`; `kpis.devices` equals
`/monitoring/summary.devices` exactly.

## Device health

- Current mix: `monitoring.summary` counts; `na` = devices not `active`.
- Trend: `device_health_snapshots` in range — hourly points for ≤ 3 days,
  otherwise the last capture per local day (tenant timezone).
- Thresholds shown are the tenant's `settings_json.monitoring` values.

## Signage network map

- Anchors: active locations with coordinates that have ≥ 1 active device
  in their subtree (`_geo`); counts by connection status; `campaigns` =
  distinct published campaigns reaching the anchor's devices via
  deployment membership.
- City/state: nearest ancestor whose `location_types.code` is `city` /
  `state`.
- Health label: online share ≥ 90 % and no offline → Healthy; ≥ 70 % →
  Degraded; else Critical.

## Campaigns

- By status: all campaigns grouped (archived included, so totals agree
  with the Campaigns page's "All").
- Top: published/approved/paused campaigns ranked by plays in range, with
  the delivery counts of each campaign's latest deployment.

## Playback / proof of play

- Series: `playback_events` bucketed by local day (`timezone(tz, started_at)`).
- Most played: top five assets by plays in range with distinct devices.
- Gated client-side by the `proof_of_play` entitlement.

## Deployments

- By status: all deployments grouped.
- History: `deployment_devices` outcomes bucketed by the deployment's
  local creation day, in range.
- Recent: newest six with per-device counts.

## Content

- By type / by status: `assets` grouped (archived excluded from the type
  mix, included in status).
- Recent: newest five with presigned thumbnails.

## Top locations

Anchors (excluding city-level) with ≥ 2 devices, ranked by share online.
Revenue and engagement are not shown because no such data exists.

## Needs attention

| Row | Condition | Severity | Leads to |
|---|---|---|---|
| Displays offline | offline > 0 | critical if ≥ 25 % of active, else high | `/devices?connection_status=offline` |
| Not reporting reliably | warning > 0 | medium | `/devices?connection_status=warning` |
| Open incidents | open + acknowledged > 0 | high | `/monitoring` |
| Deployments failed | status failed > 0 | high | `/deployments?status=failed` |
| Partially delivered | partial deployments with ≥ 1 failed device | medium | `/deployments?status=partial` |
| Awaiting approval | pending approval requests | medium | `/approvals?state=pending` |
| Critical alerts | unread critical notifications for the caller | critical | `/notifications?severity=critical` |
| Campaigns ending | published campaigns with a schedule ending within 7 days | info | `/schedules` |
| Usage | any limit ≥ 80 % (high at ≥ 95 %) | medium / high | `/settings` |
| Outdated players | below `min_player_version` | info | `/releases` |
| Abnormal behaviour | open anomalies (`fleet_ai`) | high | `/devices?tab=intelligence` |

## Activity

Newest ten `audit_logs` rows excluding bookkeeping actions
(`USER_LOGIN`, `TENANT_SWITCHED`, `LOCATION_CREATED`, `REPORT_EXPORTED`),
with the actor's name and the entity name from `after_json`.

## Approvals

Five oldest pending `approval_requests` with requester and, for campaigns,
the campaign name.

## Today's schedule

`scheduling.expand_calendar` over published campaigns for today in the
tenant timezone; `live` = the current minute falls inside the window;
`conflict` from `detect_conflicts`.

## Now playing

See the architecture doc: reported rows from the last 30 minutes of
`playback_events`, scheduled rows resolved by `resolve_active_campaign`.

## Usage

`tenant_admin.get_usage` (live counts) + `entitlements.get_effective`
(plan, status, `max_locations`) + `current_subscription` (period end,
cycle). Warning at 80 %, blocking at 95 % — the platform's own
notification threshold and refusal point.

## Insights

Open `anomalies` ordered by score with rule name, signal, the evidence
JSON rendered as text, and the recommendation verbatim.

## Demo data caveats

- The seed is a snapshot: heartbeats, playback and history are stamped
  relative to seed time. Run `python -m app.demo_seed --refresh` before a
  demo to slide everything to now.
- Video assets are placeholder bytes; thumbnails are real.
- Deployments are all `partial` by design (a few failed screens each), so
  the status mix is one colour.
