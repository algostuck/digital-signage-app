# ADR-005: Publishing & device synchronization — async pull-based manifest model

Status: Accepted · Date: 2026-08-29

## Context
Publishing must fan out to up to 100K devices, be retryable/idempotent/
observable (NFR-005), and support offline-first players (NFR-006) across
manufacturers with very different runtime constraints.

## Decision
- Publish creates a `deployment` with a **frozen target snapshot**
  (`deployment_devices`) resolved at publish time (resolve -> dedupe ->
  exclusions -> validate status). The snapshot never silently changes.
- Distribution is queue-driven (Celery/Redis): workers mark per-device state;
  the API never performs device I/O synchronously.
- Devices **pull**: the player contract is HTTPS REST — manifest endpoint
  returns the full effective state (layout JSON, playlist, schedules, asset
  list with sha256/size/signed URLs, manifest_version). Heartbeat responses
  and (later) WebSocket/MQTT nudges only signal "sync now"; correctness never
  depends on push delivery.
- Devices acknowledge deployments explicitly; deployment status aggregates
  per-device acks (PUBLISHING -> PARTIAL/PUBLISHED/FAILED).
- All player-facing writes (events, acks, heartbeats) are idempotent so
  offline players can safely retry after reconnect.

## Consequences
- Works identically for LG/Tizen/Android/Windows adapters; core stays
  manufacturer-neutral (capability registry handles differences).
- Offline model is trivial: cache last manifest + assets, replay uploads.
- Real-time push is an optimization layer, added later without contract change.
