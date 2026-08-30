# Phase 3 — Device / Player Architecture

The pull-based, manufacturer-neutral contract (ADR-005) is unchanged in
philosophy. Phase 3 adds **contract v2** — strictly additive manifest
blocks negotiated by `contract_version`; a v1 player ignores unknown blocks
and keeps working (NFR3-08).

## 1. Player contract (v1 verbs, unchanged)
register · authenticate (X-Device-Token) · heartbeat · manifest ·
asset download (signed URLs) · deployment ack · command poll/ack ·
event/playback reporting · capabilities · release ack (2C).

## 2. v2 additive manifest blocks

```jsonc
{
  "contract_version": 2,
  "sync":      {"wall_id","viewport","session_id","start_epoch_ms","tolerance_ms","role"},
  "bundle":    {"id","url","signature","sha256","expires_at"},
  "data":      {"<binding_id>": {"snapshot":…,"fetched_at","stale":bool}},
  "ad_slots":  [{"slot_id","booking_id","creative_ref","window","frequency"}],
  "bandwidth": {"windows":[…],"max_concurrent":n},
  "prefetch":  [{"asset_id","url","sha256","needed_by"}]
}
```

Player-side v2 obligations (documented in the SDK contract, simulated by
our test players): honor start markers within tolerance; verify bundle
signature + hashes before activation; report sync/bundle/ad playback via
the existing event channel (`type: sync_status|bundle_applied|ad_play`).

## 3. Synchronization (P3-SYN-003, honest scope)
- Clock discipline: heartbeat response already carries server time; v2 adds
  round-trip offset estimation fields. Devices compute offset; the cloud
  never assumes zero latency.
- Start markers: wall sync sessions publish an epoch-ms start plus a
  declared `tolerance_ms` from the wall's sync policy. We validate
  tolerance adherence in simulation; **frame-accuracy is not claimed**
  (SRS §7) — real-hardware validation is an exit-criteria activity.
- Degraded mode: member missing acks/heartbeats ⇒ wall state `degraded`
  (+incident, 2B engine); policy decides blank-viewport vs standalone.

## 4. Edge/offline (P3-M06)
Bundle = signed manifest package referencing existing asset objects
(no duplication); expiry enforced player-side and server-side; delta sync
on reconnect reuses idempotent acks + event replay (1I/1J foundations).
Resumable download = HTTP Range support (added to local storage adapter;
S3/CDN support it natively).

## 5. Manufacturer neutrality (unchanged rule)
All v2 behavior is expressed through capabilities
(`sync_playback`, `bundle_storage`, `range_download`, …) reported by the
player. Zero LG/Samsung/Android branches in core services; platform quirks
live in the player SDK layer outside this repository.
