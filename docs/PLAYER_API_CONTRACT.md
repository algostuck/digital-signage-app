# Player API Contract (v1) — frozen

The device-facing surface every native player (LG webOS, Samsung Tizen,
Android, Windows) and the in-browser Player Simulator implement. It is the
contract the cloud already serves under `/api/v1/player`; this document
freezes its shape so client work can start without waiting on the cloud.

Changes to anything below are **breaking** and need a `/api/v2/player`
prefix, a new `manifest_version`, or an additive optional field with a
default — never a changed meaning.

## Conceptual lifecycle

```text
Register ─▶ (pending) ─▶ approved by an administrator ─▶ Register again ─▶ token
   │
   ▼
Bootstrap: capabilities ─▶ Manifest ─▶ Download assets ─▶ Play
   │
   ├─ every heartbeat_interval_seconds: Heartbeat ─▶ sync_required? ─▶ Manifest again
   ├─ pending_deployments in the manifest ─▶ Acknowledge each deployment
   ├─ Poll commands ─▶ execute ─▶ Acknowledge command
   ├─ Report events (playback + operational) in batches
   ├─ Screenshot on request
   └─ Update offer in the heartbeat ─▶ download ─▶ Acknowledge release
```

Everything is **pull-based**: the cloud never connects to a device. The
player decides when to poll; the cloud tells it how often.

## Authentication

| Call | Credential |
|---|---|
| `POST /player/register` | none — carries the tenant's **enrollment key** in the body; rate-limited per IP |
| every other call | header `X-Device-Token: <token>` — issued once, at the first `register` after approval |

A token authenticates exactly one device: every path carries `{device_id}`
and the cloud answers `404 Device not found` when the token's device does
not match, so a stolen token cannot read another screen's manifest. A token
stops working the moment the device is not `active` (rejected,
decommissioned, rotated from the Security Center): `401 Device is not
active` — the player must go back to `register`.

Players store the token in secure storage and never log it.

## Envelope and errors

Every response is `{"data": …, "meta": {"request_id": …}, "errors": []}`.
Errors carry `errors[0].code` and a human message:

| Status | Code | Player behaviour |
|---|---|---|
| 401 | `UNAUTHENTICATED` | re-register (token revoked / device not active) |
| 404 | `NOT_FOUND` | wrong device id for this token; re-register |
| 422 | `BUSINESS_RULE_VIOLATION` | read the message; do not retry blindly |
| 429 | `RATE_LIMITED` | back off; the limits below are per device |
| 5xx | — | keep playing cached content; retry with exponential back-off |

Quote `meta.request_id` in any support report.

## Endpoints

### 1. Register — `POST /player/register`

Public, rate-limited (`rate_limit_register_per_minute`, default 120/min per IP).
Idempotent per `(tenant, serial_no)`.

```json
{
  "enrollment_key": "…", "serial_no": "LG-55-0001",
  "name": "Lobby Screen", "manufacturer": "LG", "model": "55UH5J", "platform": "webos",
  "os_version": "6.0", "player_version": "1.0.0", "mac_address": "…",
  "screen_width": 1920, "screen_height": 1080
}
```

Response `data`: `{"device_id", "status": "pending" | "active" | …, "device_token": string | null}`.

- First call creates the device as **pending**; `device_token` is `null`.
- An administrator approves it (or rejects it) in Devices.
- The next call after approval returns `status: "active"` **and the token,
  exactly once**. Poll `register` while pending (every 30–60 s).
- If the token is lost the administrator resets it (Devices → Reset token
  / Security Center → Rotate) and the next `register` issues a new one.

### 2. Capabilities — `POST /player/{device_id}/capabilities`

Sent once after bootstrap and whenever they change.

```json
{"capabilities": [{"code": "video_h265", "supported": true, "value": {"max_bitrate_kbps": 20000}}]}
```

### 3. Manifest — `GET /player/{device_id}/manifest`

The single source of truth for what the screen shows. The cloud has already
resolved targeting, schedules, priorities, decision policies, experiments
and variants; the player renders, it does not decide.

```json
{
  "device_id": "…", "manifest_version": 12, "generated_at": "2026-09-05T10:00:00+00:00",
  "timezone": "Asia/Kolkata",
  "active_campaign": "<campaign id>" | null, "campaign_active_now": true,
  "campaign": {"id", "name", "priority"} | null,
  "variant": {"id", "name"} | null,
  "experiment": {"id", "arm"},          // optional
  "decision": {"reasons": []},          // optional
  "schedules": [{"kind", "start_date", "end_date", "start_time", "end_time", "days_of_week", "recurrence", "exception_dates", "timezone", "priority"}],
  "layout": {"id", "version", "canvas": {"canvas": {"width", "height", "background"}, "zones": [...]}} | null,
  "playlist": {"id", "version", "loop", "items": [{"position", "item_type": "asset" | "layout", "duration_ms", "transition", "asset_id", "asset_type", "layout_id", "name"}]} | null,
  "fallback": <playlist> | null,
  "assets": [{"id", "name", "type", "sha256", "size", "mime_type", "url"}],
  "data": {…},                          // resolved dynamic-data values, optional
  "pending_deployments": ["<deployment id>", …]
}
```

Rules:

- `manifest_version` increases whenever the content changes; a player that
  sees the same version keeps what it has.
- `assets[].url` is a **signed URL valid for `signed_url_ttl_seconds`
  (default 900 s)**. Download soon after fetching the manifest; verify
  `sha256` and `size`; cache by asset id + sha256. For a single fresh URL
  later, call `GET /player/{device_id}/assets/{asset_id}/url`.
- `duration_ms: null` on a playlist item means "natural length" (video /
  audio) — the player measures it.
- `active_campaign: null` → play `fallback` if present, otherwise the
  tenant's blank/idle screen. **Never blank a screen because the network
  is down** — keep the last good manifest and cached assets.
- Layout zones are in canvas coordinates; letterbox the canvas into the
  physical screen (the simulator shows the reference behaviour).

### 4. Deployment acknowledgement — `POST /player/{device_id}/deployments/{deployment_id}/ack`

For every id in `pending_deployments`, after the assets are downloaded and
the new manifest is live on screen:

```json
{"success": true}            // or {"success": false, "error": "asset 3 checksum mismatch"}
```

This is what turns a deployment from *pending* to *published* (or
*partial* / *failed*) for the operator.

### 5. Heartbeat — `POST /player/{device_id}/heartbeat`

Every `heartbeat_interval_seconds` (returned by the cloud, default 60).
Rate limit: `rate_limit_heartbeat_per_minute` (default 60) per device. A
device with no heartbeat for `device_offline_after_seconds` (default 300)
is shown **offline**.

```json
{
  "timestamp": "…", "player_version": "1.0.0", "os_version": "6.0",
  "status": "online",
  "storage": {"used_percent": 41, "free_bytes": …},
  "network": {"type": "ethernet", "rssi": null},
  "current": {"campaign_id": "…", "asset_id": "…", "manifest_version": 12}
}
```

Response `data`:

```json
{"acknowledged": true, "heartbeat_interval_seconds": 60, "pending_commands": 1,
 "sync_required": true, "update": {"release_id", "version", "package_url", "sha256", "size"} | null}
```

- `sync_required: true` → fetch the manifest now.
- `pending_commands > 0` → poll commands now.
- `update` → download the package, verify, install, then acknowledge (§8).

### 6. Commands — `GET /player/{device_id}/commands` and `POST …/commands/{command_id}/ack`

Poll returns queued commands `[{"id", "command_type", "payload", "status", "created_at"}]`.
Known `command_type`s: `reboot`, `restart_player`, `clear_cache`,
`refresh_content` (re-fetch manifest), `screenshot` (then §7), `set_volume`,
`display_on`, `display_off`, `update_player`. Unknown types are acknowledged
with `success: false` and a `result.error`, never ignored silently.

```json
{"success": true, "result": {"duration_ms": 1200}}
```

### 7. Screenshot — `POST /player/{device_id}/screenshots`

Raw `image/png` or `image/jpeg` body, ≤ 5 MB, ≤ 10 per minute. Usually in
response to a `screenshot` command; shown in the device's Screenshots tab.

### 8. Player update — `POST /player/{device_id}/releases/{release_id}/ack`

`{"status": "updating" | "succeeded" | "failed", "error": null}` — report
`updating` before installing and the final state after. A `succeeded`
report also records the new `player_version`.

### 9. Events — `POST /player/{device_id}/events`

Batches of ≤ 500, rate limit `rate_limit_events_per_minute` (default 120)
per device. Buffer offline and replay in order; the cloud tolerates replays.

```json
{"events": [
  {"type": "playback", "campaign_id": "…", "playlist_id": "…", "asset_id": "…",
   "started_at": "2026-09-05T10:00:00+05:30", "ended_at": "2026-09-05T10:00:08+05:30", "result": "completed"},
  {"type": "APP_STARTED", "timestamp": "…", "payload": {"version": "1.0.0"}},
  {"type": "PLAYBACK_ERROR", "timestamp": "…", "payload": {"asset_id": "…", "reason": "decode"}}
]}
```

- `type: "playback"` rows are **proof of play**: one per item actually
  shown, `result` ∈ `completed` | `skipped` | `error` | `interrupted`.
  `started_at` is mandatory; rows without it are dropped.
- Any other `type` is an operational event (`APP_STARTED`, `NETWORK_DOWN`,
  `NETWORK_UP`, `STORAGE_LOW`, `PLAYBACK_ERROR`, `DISPLAY_ERROR`, …) with a
  free-form `payload`; `STORAGE_LOW` and repeated `PLAYBACK_ERROR`s feed
  monitoring incidents and fleet intelligence.
- Response: `{"stored_events": n, "stored_playback": m}`.

### 10. Prefetch bundle — `GET /player/{device_id}/bundles/{bundle_id}`

Only when the tenant uses edge bundles: a signed, range-resumable set of
assets to pre-stage before a scheduled window. Fetching it marks the
device synced for that bundle.

## Timing summary

| What | Default |
|---|---|
| Heartbeat interval | 60 s (`heartbeat_interval_seconds` in the heartbeat response) |
| Offline threshold | 300 s without a heartbeat |
| Signed asset URL lifetime | 900 s |
| Register poll while pending | 30–60 s |
| Command poll | on `pending_commands > 0`, and at least every 5 min |
| Event flush | every 30 s or 50 events, whichever first |

## Offline behaviour (normative)

1. Keep the last good manifest and every cached asset on disk.
2. Keep playing on network loss; queue events; retry heartbeats with
   back-off (max 5 min).
3. On reconnect: heartbeat → manifest if `sync_required` → flush events →
   acknowledge anything pending.
4. A `401` is the only response that stops playback logic — the device
   must re-register; content stays on screen until a new manifest arrives.

## Reference implementation

`frontend` → **Devices › Player Simulator** implements this contract in the
browser (register, token, manifest, render, heartbeat, sync, commands,
proof-of-play events) and is the executable specification for the native
clients. `backend/scripts/audit_e2e_journey.py` exercises the same sequence
from a script.
