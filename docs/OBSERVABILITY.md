# Observability

The question this answers: **"Something failed. What exactly failed?"**

## One id ties everything together

Every API response carries the request id twice — in the `X-Request-ID`
header and in `meta.request_id` of the envelope. A client may supply its
own `X-Request-ID`; otherwise the server mints one. When an unexpected
failure (5xx) reaches the portal, the error toast shows it as
`… (ref 1a2b3c4d)` — the first eight characters — so a screenshot from a
user is enough to find the server-side story.

Background jobs use the same field: inside a Celery task, `request_id`
is the task id, so one search finds either kind of work.

## What every log line carries

Logs are JSON when `LOG_JSON=true` (production) and single-line text in
development. The JSON formatter (`app/core/logging.py`) adds, from the
request context:

| Field | Set by | Present on |
|---|---|---|
| `timestamp`, `level`, `logger`, `message` | formatter | every line |
| `request_id` | `RequestContextMiddleware` / `job_context` | every line inside a request or a job |
| `tenant_id` | the auth dependency (`get_current_user`) / `job_context` | every line after authentication, including the access line |
| `user_id` | the auth dependency | every authenticated request |
| `exception` | formatter | any line logged with `exc_info` |
| `extra_fields` (flattened) | the call site | see below |

`RequestContextMiddleware` is a pure ASGI middleware so that it sees the
tenant and user the dependency resolved in the same task; the access line
it writes at the end of every request has `method`, `path`, `status`,
`duration_ms`, `tenant_id` and `user_id`.

### Access line

```json
{"timestamp":"…","level":"INFO","logger":"app.request","message":"POST /api/v1/campaigns/…/publish -> 200 (84.2ms)",
 "request_id":"1a2b3c4d-…","tenant_id":"33da38ba-…","user_id":"5480c84d-…",
 "method":"POST","path":"/api/v1/campaigns/…/publish","status":200,"duration_ms":84.2}
```

### Background job lines (`app.jobs`)

`app/workers/instrumentation.py::job_context` wraps every task:

```json
{"logger":"app.jobs","message":"job publishing.process_deployment started","request_id":"<celery task id>",
 "job":"publishing.process_deployment","task_id":"…","deployment_id":"94b6b973-…","attempt":"0","phase":"start"}
{"logger":"app.jobs","message":"job publishing.process_deployment finished", … "phase":"finished","duration_ms":412.7}
{"logger":"app.jobs","level":"ERROR","message":"job media.process_asset_version failed: …","phase":"failed","error":"…","exception":"Traceback …"}
```

Jobs covered: deployment fan-out (`deployment_id`), media processing
(`version_id`), and every maintenance beat (offline detection, health
snapshots, rule/webhook/event deliveries, escalations, retention pruning,
data-source refresh, ad reconciliation, analytics aggregation, data
exports, anomaly detection, security sweep, subscription lifecycle) with
its returned counts flattened into the *finished* line.

### Domain events with ids

| What | Logger | Ids on the line |
|---|---|---|
| Publish, deployment materialised, ack | `app.publishing` | campaign, deployment, device counts |
| Device registered / approved / heartbeat anomalies | `app.devices` | device, organisation |
| Webhook delivery attempt and outcome | `app.webhooks` | subscription, delivery, status code |
| Media processing | `app.media` / job line | asset version |
| AI request | `app.ai` | request id, provider |
| Data-source refresh | `app.data_sources` | source |
| Audit trail (who did what) | `audit_logs` table, not logs | actor, entity, before/after, request id, IP |

## Where to look, in order

1. **The toast or the API client's error** → `ref` / `request_id`.
2. `grep <request_id>` in the API log → the access line (tenant, user,
   status, duration) plus every line the handler logged.
3. If the request enqueued work, the audit entry names the deployment or
   asset version → `grep <deployment_id>` in the worker log → the job's
   start / finished / failed lines with duration and error.
4. **Audit Logs** in the portal (Administration › Audit Logs) for the
   business view of the same request: actor, entity, before → after.
5. For a device: Devices › the screen › *Events* (what the player
   reported) and the Security Center (credential lifecycle).

## Health and readiness

`GET /api/v1/health` (liveness, no dependencies) and
`GET /api/v1/health/ready` (database round-trip). Both return the envelope
with `meta.request_id`.

## Performance baseline

`backend/scripts/audit_performance.py` measures the demo-critical
endpoints against the seeded data (results in `HARDENING_AUDIT.md`,
gate 9). Run it after schema or query changes; budgets are 300 ms p95 for
lists and details and 800 ms for aggregates.
