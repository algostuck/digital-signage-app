# Phase 3 — Gap Analysis (requirement matrix)

Chain per row: Requirement → SRS ref → Existing implementation → P1/P2
dependency → Gap → Required change → New implementation → Acceptance.
Gap legend: **NONE** (supported today) · **EXT** (extend existing) ·
**NEW** (build new on existing foundations).

## P3-M01 AI Content Intelligence
| FR | Existing | Depends on | Gap | Required change / new implementation | Acceptance |
|---|---|---|---|---|---|
| P3-AI-001 copy assistant | none | 2A approvals, 1D content | NEW | `ai` service package: provider adapter (`generate_text`), governed by `ai_policies`; deterministic LocalAIProvider in dev/test | Text generated within policy; recorded in ai_requests/outputs |
| P3-AI-002 creative variants | 2E campaign variants (creative-per-audience), 1F canvas | 2D templates | NEW | `generate_creative` produces structured canvas/text variants for approved dimensions; outputs are draft assets/templates | Variant lands as draft; approval configurable |
| P3-AI-003 localization | org locale field | 2D binding placeholders | NEW | `localize` preserves `{{placeholders}}`/format/brand rules; per-locale variants | Placeholders intact post-localization (tested) |
| P3-AI-004 safety & governance | 2A approval engine (entity adapters) | 2A | EXT | Register `ai_output` approval adapter; ai_policies gate (allowed ops, require_approval); safety_status on outputs | AI output routed through approval when policy says so |
| P3-AI-005 explainability | audit trail | 1J audit | NEW | ai_requests stores provider/model_ref/template_version/status; outputs store revision + confidence; no secrets | Admin can trace any AI artifact to its request record |

## P3-M02 Dynamic Data & Widgets
| FR | Existing | Depends on | Gap | Required change / new implementation | Acceptance |
|---|---|---|---|---|---|
| P3-DAT-001 connector sources | httpx outbound (2H webhooks) | 2H | NEW | `data_sources` (REST/JSON, RSS/Atom types) + guarded fetch util (SSRF-safe) | Source created, tested, fetched |
| P3-DAT-002 schema validation | 2D widget field-schema validator | 2D | EXT | `data_source_schemas` (declared JSON shape, versioned); payload validated before snapshot accepted | Invalid payload → rejected, last-known-good kept |
| P3-DAT-003 transformations | none | — | NEW | Safe declarative ops: pick/rename/filter/format/limit — no code execution | Transform pipeline covered by unit tests |
| P3-DAT-004 caching | webhook worker pattern | 2G/2H workers | NEW | Snapshot cache w/ TTL + stale-while-revalidate; fetch in beat worker, never in request path | TTL honored; stale served during refresh |
| P3-DAT-005 fallback | widget fallback_json (2D) | 2D | EXT | Widget binding falls back deterministically when source invalid/absent; manifest ships snapshot or fallback | SRS acceptance #2 (disconnect → last-known-good → auto-recover) |

## P3-M03 Decisioning & Optimization
| FR | Existing | Depends on | Gap | Required change | Acceptance |
|---|---|---|---|---|---|
| P3-DEC-001 context inputs | device/location/time/tag context in targeting + scheduling | 1H/1I/2E | EXT | decision_rules conditions over existing context + data-source values | Preview shows context → decision |
| P3-DEC-002 deterministic priority + reasons | priority resolver (campaign>schedule>recency) | 1H | EXT | Rule evaluation returns ordered reasons; decision recorded (auditable) | Same input → same output; reason trail |
| P3-DEC-003 experimentation | campaign variants (2E) | 2E | NEW | experiments/variants/assignments; deterministic per-device assignment (hash), allocation %; manifest picks assigned variant | Stable assignment; allocation within tolerance |
| P3-DEC-004 guardrails | blackouts (2E), mandatory schedules | 2E | EXT | Frequency caps + campaign windows + mandatory-content constraints in decision_policies.guardrails_json | Guardrail blocks optimization override |

## P3-M04 Video Wall & Sync
| FR | Existing | Depends on | Gap | Required change | Acceptance |
|---|---|---|---|---|---|
| P3-SYN-001 wall definition | device groups | 1E | NEW | video_walls (canvas_json, sync_policy) | Wall CRUD |
| P3-SYN-002 canvas mapping | layout canvas schema | 1F | NEW | video_wall_members (viewport_json, role) | Each member maps to viewport |
| P3-SYN-003 sync protocol | server time in heartbeat; manifest | 1E/1I | NEW | Manifest `sync` block: session id, epoch start marker, tolerance; player contract v2 | 2x2 wall starts on shared marker (SRS acceptance #3) |
| P3-SYN-004 degraded mode | incident engine | 2B/2F | EXT | Member-offline ⇒ wall state degraded + incident; declared degraded content behavior | Remove member → degraded; restore → resync |

## P3-M05 Ad & Monetization
| FR | Existing | Depends on | Gap | Required change | Acceptance |
|---|---|---|---|---|---|
| P3-ADS-001 inventory | locations/devices/zones | 1C/1E/1F | NEW | ad_inventory (location/device/zone_ref, slot_type, hours, rate_card_ref) | Slot defined w/ availability |
| P3-ADS-002 ad campaigns | campaign machinery + approval engine | 1I/2A | NEW | ad_bookings against inventory w/ dates/frequency; delivery via existing campaign/playlist primitives | Booking publishes and plays |
| P3-ADS-003 proof-of-play | playback_events + PoP reports | 1J/2I | EXT | ad_playback_links (unique per playback event) joining evidence to booking | Every ad play linked once |
| P3-ADS-004 billing-ready | report/export engine | 2I | EXT | Billable aggregates endpoint + ad-performance report/export; payments stay external (SRS §12) | SRS acceptance #4 reconciliation |

## P3-M06 Edge & Resilience
| FR | Existing | Depends on | Gap | Required change | Acceptance |
|---|---|---|---|---|---|
| P3-EDG-001 regional edge | storage adapter + signed URLs | 1D | EXT | CDN/base-URL indirection per region in storage config (deployment concern; metadata support) | URLs route via configured edge base |
| P3-EDG-002 prefetch | manifest assets list | 1I | EXT | Manifest `prefetch` window (upcoming schedule horizon); player stages ahead | Assets staged before window |
| P3-EDG-003 bandwidth policy | tenant settings_json | 2K | NEW | Download windows/concurrency policy per tenant/device; shipped in manifest | Policy visible to player; honored in sim |
| P3-EDG-004 offline bundle | signed URLs, sha256 manifest, HMAC util | 1D/1I/2H | NEW | edge_bundles: signed manifest package (signature, expiry) + per-device rollout state + resumable download (Range support in local storage) | SRS acceptance #5 (offline playback, expiry, recovery) |

## P3-M07 Fleet AI Operations
| FR | Existing | Depends on | Gap | Required change | Acceptance |
|---|---|---|---|---|---|
| P3-OPS-001 anomaly detection | heartbeats/events/incidents/thresholds | 2B/2F | NEW | anomaly_rules (signal, threshold/window, severity) + beat detector over existing telemetry; score + evidence_json | SRS acceptance #6 (repeated heartbeat failure → anomaly) |
| P3-OPS-002 recommended action | incident UI patterns | 2F | NEW | Recommendation w/ confidence + evidence rows (deterministic heuristics first; provider-pluggable) | Recommendation shows evidence |
| P3-OPS-003 human control | commands + RBAC | 1E | EXT | Remediation executes only whitelisted commands after explicit acknowledge + permission; logged in anomaly_actions | No destructive auto-action (tested) |

## P3-M08 Global SaaS & White Label
| FR | Existing | Depends on | Gap | Required change | Acceptance |
|---|---|---|---|---|---|
| P3-GLO-001 white label | branding_json + PATCH /organization | 2K | EXT | Branding schema (logo/colors/email identity/custom domain metadata); frontend theme application; real SMTP adapter | Tenant A theme ≠ tenant B |
| P3-GLO-002 SSO federation | JWT auth, roles | 1B | NEW | sso_providers (OIDC first; SAML documented as deployment option), claim→role/tenant mapping, login flow; RBAC unchanged after login | SRS acceptance #7 |
| P3-GLO-003 regional tenancy | single-region infra | — | NEW (metadata) | Region/residency fields per org + export policy; physical multi-region = deployment concern, documented | Region visible + policy enforced on exports |
| P3-GLO-004 platform admin | is_superuser + monitoring | 1B/2F | EXT | Platform ops view (tenants/regions/queues/health) without tenant-content access | Superuser sees health, not content |

## P3-M09 Advanced Integrations
| FR | Existing | Depends on | Gap | Required change | Acceptance |
|---|---|---|---|---|---|
| P3-INT-101 catalog | webhook subscriptions | 2H | NEW | connectors + connector_instances (config-ref, health, version) | Connector installed/configured/health-checked |
| P3-INT-102 event bus | notifications + webhook delivery machinery | 2G/2H | EXT | domain_events (normalized envelope) emitted by services; event_subscriptions + deliveries reuse the signed/retry/dead-letter pattern | Consumer receives normalized events |
| P3-INT-103 partner API | FastAPI OpenAPI | 1A | EXT | Versioned OpenAPI publication + deprecation metadata (api_versions) | /developer/openapi serves versioned contract |

## P3-M10 Advanced Security
| FR | Existing | Depends on | Gap | Required change | Acceptance |
|---|---|---|---|---|---|
| P3-SEC-101 device identity | opaque device tokens (hash-stored, revocable) | 1E | NEW | device_identities + identity_credentials (cert-ready lifecycle; mTLS is deployment-layer, platform stores/rotates/validates fingerprints) | Identity issued/rotated/revoked |
| P3-SEC-102 key lifecycle | token reset, webhook secret rotation | 1E/2H | EXT | Expiry alerts + rotation sweeps for device credentials, API keys, webhook secrets | Expiring creds alert before expiry |
| P3-SEC-103 policy engine | thresholds/approval/retention policies | 2F/2K | NEW | security_policies (conditions/actions) evaluated centrally; violations recorded | Violation created on breach |
| P3-SEC-104 security analytics | audit + notifications | 1J/2G | EXT | Auth/device anomaly signals into Security Center; sensitive-action tracking | Anomalous logins surfaced |

## P3-M11 Data Platform
| FR | Existing | Depends on | Gap | Required change | Acceptance |
|---|---|---|---|---|---|
| P3-DWH-101 historical export | CSV/XLSX export engine | 2I | EXT | data_exports (dataset, destination=storage path, schedule) run by beat; closes 2I "scheduled exports" deferral | Export lands on schedule with state |
| P3-DWH-102 semantic metrics | uptime/PoP/delivery reports | 2I | EXT | Documented canonical metric definitions + shared computation module used by all reports | Same number from every surface |
| P3-DWH-103 long-term analytics | retention pruning | 2K | NEW | analytics_aggregates (daily rollups by tenant/device/campaign) filled by beat; reports read aggregates; partition-ready playback_events design | Heavy queries hit aggregates, not raw events |

## P3-M12 Developer Platform
| FR | Existing | Depends on | Gap | Required change | Acceptance |
|---|---|---|---|---|---|
| P3-DEV-101 SDK contracts | player contract (implicit) | 1E/1I | EXT | Versioned player-contract document + contract_version negotiation | v1 player unaffected by v2 fields |
| P3-DEV-102 sandbox | seed machinery, demo tenant | 1B | EXT | Isolated sandbox tenant provisioning + device simulator script (exists as load/E2E scripts → productized) | Sandbox flow end-to-end |
| P3-DEV-103 API docs | FastAPI /docs | 1A | EXT | Developer Portal screen: keys (2H), OpenAPI versions, changelog | Interactive versioned docs reachable |
