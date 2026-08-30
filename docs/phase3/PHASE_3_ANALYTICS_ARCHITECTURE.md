# Phase 3 — Analytics / Data Platform Architecture

Decision (per SRS §7 + anti-over-engineering directive): analytics/OLTP
separation is achieved **by workload and table design inside the existing
PostgreSQL**, not by introducing a warehouse engine. A physical warehouse is
the customer's/deployment's choice, fed by `data_exports`.

## 1. Data flow

```
producers (player events API, workers)
   │  append-only
   ▼
raw tables: playback_events · device_heartbeats · device_events · domain_events
   │  beat: analytics.aggregate_daily (idempotent per (org, day, dimension))
   ▼
analytics_aggregates  — daily grain metrics_json per dimension
   │
   ├── reports & dashboards & AI read AGGREGATES (raw only for bounded drilldowns)
   ├── data_exports beat → CSV/XLSX/JSONL files on object storage (2I renderers)
   └── retention pruning (2K) bounds the raw tables
```

## 2. Semantic metrics (P3-DWH-102)
One shared computation module (`services/analytics.py`) defines the
canonical formulas used by every surface:
- **uptime** = covered heartbeat windows / wall-clock window (2I algorithm,
  tenant thresholds) — maintenance exclusions added here when modeled.
- **play count** = playback_events rows; **completed** = result=completed.
- **delivery** = acknowledged / total deployment devices (1I states).
- **campaign reach** = distinct devices with ≥1 play in range.
- **billable impressions** = ad_playback_links where billable, unique per
  playback event (double-count impossible by unique constraint).

## 3. Aggregation mechanics
- Idempotent recompute window (default: today + N trailing days) so late
  events self-heal; unique (org, grain_date, dimension_type, dimension_id).
- Dimensions: org total, device, location, campaign, ad_booking.
- A reconciliation test recomputes one day from raw and diffs against the
  aggregate (drift guard, mirrors the SRS ad reconciliation scenario).

## 4. Scale gates (measured, not speculative)
| Trigger | Action |
|---|---|
| playback_events > ~50M rows or aggregate job > 5 min | apply native monthly partitioning (schema is keyed for it) |
| report latency on aggregates > 2 s | add covering indexes / pre-computed report tables |
| export files > storage comfort | archive tier via storage lifecycle (deployment) |

## 5. Exports (P3-DWH-101)
`data_exports`: dataset (aggregates, playback raw window, audit, ad
performance), schedule (cron-ish beat), destination = object-storage
prefix (regional per tenant residency policy), state + last_run + audit.
This also closes the Phase-2 "scheduled exports" deferral.
