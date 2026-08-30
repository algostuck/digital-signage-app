# Phase 3 — Module Matrix

| SRS module | Sub-phase | Backend home (new/EXT) | Reuses | Feature flag | Status |
|---|---|---|---|---|---|
| P3-M02 Dynamic Data & Widgets | P3-A | services/data_sources.py (new), studio.py bindings (EXT), integrations/fetch.py (new, SSRF-guarded) | 2D widgets, 2H httpx/worker pattern, 2K settings | dynamic_data | pending |
| P3-M09 Advanced Integrations (event bus first) | P3-A | services/events.py (new) | 2G/2H delivery machinery, notifications stream | (platform) | pending |
| P3-M12 Developer Platform | P3-A | api/v1/developer.py (new), seed sandbox (EXT) | 2H api-keys, FastAPI OpenAPI | developer_portal | pending |
| P3-M01 AI Content Intelligence | P3-B | services/ai/ (new), integrations/ai_providers.py (new) | 2A approval adapters, 1D assets, 2D templates | ai | pending |
| P3-M03 Decisioning & Optimization | P3-B | services/decisioning.py + experiments.py (new) | 1H scheduling, 2E variants/targeting, 1I manifest | experiments (for A/B) | pending |
| P3-M04 Video Wall & Sync | P3-C | services/video_walls.py (new), manifest EXT | 1E devices, 1F canvas, 1I manifest, 2B incidents | video_wall | pending |
| P3-M06 Edge & Resilience | P3-C | services/edge.py (new), storage Range support (EXT) | 1D storage adapter, 1I manifest, 2C rollout-state pattern | edge_bundles | pending |
| P3-M05 Ad & Monetization | P3-D | services/ads.py (new) | 1I campaigns, 2A approvals, 1J playback_events, 2I reports | advertising | pending |
| P3-M07 Fleet AI Operations | P3-D | services/anomaly.py (new) | 2B/2F telemetry + incidents, 1E commands (remediation) | fleet_ai | pending |
| P3-M11 Data Platform | P3-D | services/analytics.py (new), data_exports runner (EXT of 2I) | 2I export engine, 2K retention, maintenance worker | (platform) | pending |
| P3-M08 Global SaaS & White Label | P3-E | services/sso.py (new), organization.py branding (EXT), email SMTP adapter (EXT) | 1B auth, 2G email adapter, 2K settings | sso, white_label | pending |
| P3-M10 Advanced Security | P3-E | services/security_center.py (new) | 1E device credentials, 2H secret handling, 1J audit, 2G notifications | (platform) | pending |
