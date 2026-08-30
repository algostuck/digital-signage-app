# Digital Signage Cloud Platform

Phase 2 Enterprise SRS / FRD \- Advanced Operations, Governance and Analytics

Version 1.0 | Prepared for implementation planning | Date: 29 August 2026

# **1\. Phase-2 Purpose and Boundary**

Phase 2 evolves the Phase-1 core signage platform into an enterprise operating system for large fleets, distributed teams and controlled publishing. It assumes Phase 1 already provides identity, tenant/location hierarchy, device registration, asset library, basic layouts, playlists, campaigns, scheduling, publishing, player gateway, monitoring and audit foundations.

| Phase-2 objective | Expected business outcome |
| :---- | :---- |
| Scale operations | Manage large device fleets and content operations without manual per-device work. |
| Govern publishing | Introduce maker-checker approvals, content lifecycle control and role-scoped publishing. |
| Improve observability | Provide operational dashboards, device diagnostics, deployment health and evidence. |
| Improve reuse | Reusable templates, dynamic widgets, smart targeting, bulk actions and saved views. |
| Enable enterprise reporting | Operational, content, campaign and proof-of-play reports with exports. |

# **2\. Phase-2 Scope Summary**

| ID | Module | Scope |
| :---- | :---- | :---- |
| P2-M01 | Advanced Device Operations | Bulk onboarding, groups, tags, remote commands, OTA player updates, diagnostics. |
| P2-M02 | Advanced Content Studio | Template library, dynamic text, multi-zone widgets, HTML5 packages, reusable components. |
| P2-M03 | Approval & Governance | Maker-checker, approval policies, version governance, publish windows. |
| P2-M04 | Advanced Campaigns | Campaign variants, audience rules, inheritance/override, priority and blackout windows. |
| P2-M05 | Enterprise Scheduling | Calendar views, recurrence exceptions, blackout periods, timezone-safe scheduling. |
| P2-M06 | Monitoring & Observability | Health dashboards, alarms, diagnostics, device screenshots, evidence. |
| P2-M07 | Analytics & Reporting | Proof of play, delivery reports, device uptime, campaign analytics, exports. |
| P2-M08 | Notifications | Alert rules, escalation, digest notifications, email/webhook channels. |
| P2-M09 | Enterprise Search | Global search, saved views, advanced filters, bulk operations. |
| P2-M10 | Integration & Webhooks | Outbound events, inbound APIs, API keys, webhook subscriptions. |
| P2-M11 | Tenant Administration | Branding, quotas, policies, storage controls, configurable defaults. |
| P2-M12 | Audit & Compliance | Enhanced audit views, export, retention policy, evidence linkage. |

# **3\. Functional Requirements**

## **P2-M01 Advanced Device Operations**

| FR ID | Feature | Functional requirement |
| :---- | :---- | :---- |
| P2-DEV-001 | Device groups | Admin shall create static and dynamic groups using tags, location, manufacturer, model and status rules. |
| P2-DEV-002 | Bulk actions | Admin shall reboot, sync, refresh, capture screenshot and change supported settings for multiple devices. |
| P2-DEV-003 | Diagnostics | System shall expose last heartbeat, sync state, storage, memory, CPU, app version and recent errors. |
| P2-DEV-004 | OTA player update | Authorized users shall upload/select a player package and deploy it to a group using staged rollout. |
| P2-DEV-005 | Rollout rings | System shall support pilot \-\> 10% \-\> 50% \-\> 100% rollout with stop-on-failure threshold. |

## **P2-M02 Advanced Content Studio**

| FR ID | Feature | Functional requirement |
| :---- | :---- | :---- |
| P2-CNT-001 | Template library | Users shall create reusable full-screen and multi-zone templates with versioning. |
| P2-CNT-002 | Dynamic fields | Text/image widgets may bind to approved data variables such as date, weather or API response. |
| P2-CNT-003 | Widget configuration | Widgets shall have schema-driven configuration and fallback content. |
| P2-CNT-004 | Asset collections | Users shall assemble reusable collections for campaigns and playlists. |

## **P2-M03 Approval & Governance**

| FR ID | Feature | Functional requirement |
| :---- | :---- | :---- |
| P2-APP-001 | Approval policy | Tenant admin shall configure which content/campaign types require approval. |
| P2-APP-002 | Maker-checker | The creator of an item shall not be the sole approver when maker-checker is enabled. |
| P2-APP-003 | Revision cycle | Rejected submissions shall return with comments and revision history. |
| P2-APP-004 | Publish permission | Publishing shall require both functional permission and policy-compliant status. |

## **P2-M04 Advanced Campaigns**

| FR ID | Feature | Functional requirement |
| :---- | :---- | :---- |
| P2-CAM-001 | Variants | Campaigns shall support different creatives/layouts by location, device class or tag. |
| P2-CAM-002 | Inheritance | Parent target assignments shall flow to descendants unless an explicit override exists. |
| P2-CAM-003 | Priority | Campaigns shall have deterministic priority; emergency remains a separate higher-priority channel. |
| P2-CAM-004 | Blackout | Scheduled exclusions shall suppress otherwise eligible campaigns for a defined window. |

## **P2-M05 Enterprise Scheduling**

| FR ID | Feature | Functional requirement |
| :---- | :---- | :---- |
| P2-SCH-001 | Calendar | Users shall see campaign schedules by day/week/month with conflict indicators. |
| P2-SCH-002 | Recurrence | Support daily, weekly, monthly, date range and exception dates. |
| P2-SCH-003 | Timezone | Execution shall resolve against target location/device timezone with explicit DST-safe storage. |
| P2-SCH-004 | Conflict detection | System shall detect schedule overlap and report the winning rule. |

## **P2-M06 Monitoring & Observability**

| FR ID | Feature | Functional requirement |
| :---- | :---- | :---- |
| P2-MON-001 | Fleet health | Dashboard shall show health by organization, location, group and device. |
| P2-MON-002 | Thresholds | Admins shall configure offline, storage, heartbeat and application-version thresholds. |
| P2-MON-003 | Evidence | Users shall view latest screenshot and deployment evidence for a device. |
| P2-MON-004 | Incident timeline | Device page shall show chronological device events, errors and recoveries. |

## **P2-M07 Analytics & Reporting**

| FR ID | Feature | Functional requirement |
| :---- | :---- | :---- |
| P2-RPT-001 | Proof of play | System shall retain playback events sufficient to report content/campaign play status. |
| P2-RPT-002 | Delivery analytics | Report deployment success, pending, retry and failed device counts. |
| P2-RPT-003 | Uptime | Report device availability using heartbeat windows and maintenance exclusions. |
| P2-RPT-004 | Exports | CSV/XLSX/PDF export for supported operational reports. |

## **P2-M08 Notifications**

| FR ID | Feature | Functional requirement |
| :---- | :---- | :---- |
| P2-NTF-001 | Rules | Users shall configure event-to-notification rules. |
| P2-NTF-002 | Escalation | Critical alerts shall support escalation after a configurable delay. |
| P2-NTF-003 | Channels | Support in-app, email and webhook delivery in Phase 2\. |

## **P2-M09 Enterprise Search**

| FR ID | Feature | Functional requirement |
| :---- | :---- | :---- |
| P2-SRC-001 | Global search | Search devices, content, locations, campaigns, playlists, schedules and users. |
| P2-SRC-002 | Saved views | Users shall save filters and columns per module. |
| P2-SRC-003 | Bulk edit | Authorized users shall bulk update tags, groups, location assignments and metadata. |

## **P2-M10 Integration & Webhooks**

| FR ID | Feature | Functional requirement |
| :---- | :---- | :---- |
| P2-INT-001 | Webhooks | Tenant admins shall create subscriptions for deployment, device and playback events. |
| P2-INT-002 | API keys | System shall issue scoped API credentials with expiry/revocation. |
| P2-INT-003 | Retries | Webhook delivery shall retry with exponential backoff and a dead-letter state. |

## **P2-M11 Tenant Administration**

| FR ID | Feature | Functional requirement |
| :---- | :---- | :---- |
| P2-TNT-001 | Branding | Logo, colors, email branding and default locale/timezone. |
| P2-TNT-002 | Quota | Storage/device/user quotas and usage visibility. |
| P2-TNT-003 | Defaults | Default playback, approval, retention and notification policies. |

## **P2-M12 Audit & Compliance**

| FR ID | Feature | Functional requirement |
| :---- | :---- | :---- |
| P2-AUD-001 | Audit explorer | Filter audit events by actor, entity, action, location, date and result. |
| P2-AUD-002 | Evidence link | Audit records shall link to the deployment/campaign/device record where applicable. |
| P2-AUD-003 | Retention | Tenant policy shall control audit retention within platform-supported limits. |

# **4\. Exact Frontend Screen Inventory \- Phase 2**

| ID | Screen | Required capabilities |
| :---- | :---- | :---- |
| P2-01 | Enterprise Dashboard | Fleet health, active campaigns, approvals, recent incidents, deployment KPI. |
| P2-02 | Device Fleet | Advanced filters, groups, tags, bulk actions, rollout status. |
| P2-03 | Device Detail | Health, screenshot, commands, events, deployments, software version. |
| P2-04 | Device Group Builder | Static/dynamic group rules and preview count. |
| P2-05 | Player Update Center | Package management, rollout rings, progress and rollback state. |
| P2-06 | Template Library | Template cards, versions, tags, approval status, usage. |
| P2-07 | Template Designer | Reusable zones, bindings, data variables and preview. |
| P2-08 | Widget Library | Built-in/custom widgets, schema, version, configuration. |
| P2-09 | Content Approval Inbox | Pending, returned, approved, rejected items. |
| P2-10 | Campaign Builder | Variants, target rules, priority, exclusions and preview. |
| P2-11 | Schedule Calendar | Calendar, conflicts, recurrence and timezone display. |
| P2-12 | Deployment Center | Rollout job status, retry, failure reasons and device drilldown. |
| P2-13 | Fleet Monitoring | Map/list, health state, alert filters and thresholds. |
| P2-14 | Incident Center | Open incidents, severity, acknowledgements and resolution. |
| P2-15 | Proof-of-Play Report | Play events, campaign reach, device execution and export. |
| P2-16 | Campaign Analytics | Delivery and playback KPI by location/device/tag. |
| P2-17 | Report Builder | Select dimensions, filters, columns and schedule export. |
| P2-18 | Notification Rules | Event, condition, recipients, channel, escalation. |
| P2-19 | Webhook Integrations | Subscriptions, secret rotation, delivery logs and retry state. |
| P2-20 | API Key Management | Create/revoke keys, scopes, expiry, usage. |
| P2-21 | Tenant Settings | Branding, quotas, defaults, retention and policy settings. |
| P2-22 | Audit Explorer | Advanced audit search, evidence and export. |

# **5\. API Catalogue \- Phase 2**

| Method | Endpoint | Purpose |
| :---- | :---- | :---- |
| POST | /api/v1/device-groups | Create group |
| GET | /api/v1/device-groups | List/filter groups |
| POST | /api/v1/device-groups/{id}/actions | Bulk action |
| POST | /api/v1/player-releases | Create player release |
| POST | /api/v1/player-releases/{id}/rollouts | Start rollout |
| POST | /api/v1/player-releases/{id}/rollback | Rollback release |
| POST | /api/v1/templates | Create template |
| PUT | /api/v1/templates/{id} | Update template |
| POST | /api/v1/templates/{id}/submit | Submit for approval |
| GET | /api/v1/approvals/inbox | Approval queue |
| POST | /api/v1/approvals/{id}/approve | Approve |
| POST | /api/v1/approvals/{id}/reject | Reject |
| POST | /api/v1/campaigns/{id}/variants | Create variant |
| POST | /api/v1/campaigns/{id}/targets/preview | Preview target resolution |
| GET | /api/v1/schedules/calendar | Calendar |
| POST | /api/v1/schedules/conflicts | Conflict check |
| GET | /api/v1/monitoring/fleet-health | Fleet health |
| GET | /api/v1/devices/{id}/events | Device event timeline |
| GET | /api/v1/reports/proof-of-play | Proof of play |
| GET | /api/v1/reports/campaign-performance | Campaign performance |
| GET | /api/v1/reports/device-uptime | Device uptime |
| POST | /api/v1/reports/export | Export report |
| POST | /api/v1/notification-rules | Create alert rule |
| POST | /api/v1/webhooks | Create webhook |
| GET | /api/v1/webhooks/{id}/deliveries | Delivery logs |
| POST | /api/v1/api-keys | Create scoped key |
| DELETE | /api/v1/api-keys/{id} | Revoke key |
| GET | /api/v1/audit | Search audit events |

# **6\. Database ER Model \- Phase 2 Extensions**

tenant  
  |-- approval\_policies  
  |-- approval\_requests \--\< approval\_actions  
  |-- templates \--\< template\_versions  
  |                 |--\< template\_zones  
  |-- widgets \--\< widget\_versions  
  |-- device\_groups \--\< device\_group\_rules  
  |-- player\_releases \--\< rollout\_batches \--\< rollout\_devices  
  |-- notification\_rules \--\< notification\_deliveries  
  |-- webhook\_subscriptions \--\< webhook\_deliveries  
  |-- api\_keys  
  |-- saved\_views  
  |-- reports

campaign \--\< campaign\_variants \--\< campaign\_variant\_targets  
device \--\< device\_events  
device \--\< screenshots  
device \--\< playback\_events  
deployment \--\< deployment\_attempts

| Entity | Key fields | Purpose |
| :---- | :---- | :---- |
| approval\_policies | tenant\_id, name, entity\_type, rules\_json, active | Controls which objects require approval. |
| approval\_requests | tenant\_id, entity\_type, entity\_id, state, requester\_id, submitted\_at | Approval workflow header. |
| approval\_actions | approval\_request\_id, actor\_id, action, comments, created\_at | Immutable approval decisions. |
| templates | tenant\_id, name, status, current\_version\_id | Reusable design asset. |
| template\_versions | template\_id, version\_no, schema\_json, created\_by | Versioned layout/template definition. |
| template\_zones | template\_version\_id, zone\_key, geometry\_json, binding\_json | Zone definition. |
| widgets | tenant\_id, type, name, status | Widget catalogue. |
| widget\_versions | widget\_id, version\_no, schema\_json, renderer\_contract | Widget configuration contract. |
| device\_groups | tenant\_id, name, group\_type, rule\_json | Static or dynamic group. |
| device\_group\_rules | group\_id, field, operator, value\_json | Normalized rule records if required. |
| player\_releases | tenant\_id, version, package\_asset\_id, checksum, state | Player package registry. |
| rollout\_batches | release\_id, ring\_no, percentage, state | Staged rollout definition. |
| rollout\_devices | batch\_id, device\_id, state, failure\_reason | Device rollout status. |
| notification\_rules | tenant\_id, event\_type, condition\_json, channels\_json | Alert policy. |
| notification\_deliveries | rule\_id, recipient, channel, state, delivered\_at | Delivery evidence. |
| webhook\_subscriptions | tenant\_id, url, events, secret\_ref, active | Outbound event subscription. |
| webhook\_deliveries | subscription\_id, event\_id, attempt\_no, state, response\_code | Retryable webhook delivery. |
| api\_keys | tenant\_id, name, key\_hash, scopes, expires\_at, revoked\_at | Machine-to-machine credentials. |
| saved\_views | tenant\_id, user\_id, module, filter\_json, columns\_json | Saved UI views. |
| device\_events | device\_id, event\_type, severity, payload\_json, occurred\_at | Operational event history. |
| screenshots | device\_id, asset\_id, captured\_at, checksum | Device display evidence. |
| playback\_events | device\_id, content\_id, campaign\_id, started\_at, ended\_at, status | Proof of play records. |

# **7\. Phase-2 Non-Functional Requirements**

| ID | Area | Requirement |
| :---- | :---- | :---- |
| NFR2-01 | Availability | Target 99.9% for cloud control plane excluding planned maintenance. |
| NFR2-02 | Scale | Support at least 10,000 registered devices without architectural redesign. |
| NFR2-03 | Bulk operations | Bulk device/content actions shall be asynchronous and resumable. |
| NFR2-04 | Observability | All workers and API requests shall emit structured logs and metrics. |
| NFR2-05 | Security | Secrets stored using managed secret storage; no raw API keys stored. |
| NFR2-06 | Data retention | Playback/operational retention shall be configurable by tenant policy. |
| NFR2-07 | Accessibility | Admin UI shall meet practical WCAG 2.1 AA patterns for core workflows. |
| NFR2-08 | Recovery | Deployments and webhooks shall survive worker restarts and retry safely. |

# **8\. Phase-2 Acceptance Scenarios**

* Create a dynamic device group for all Samsung devices in a location subtree; preview count; publish a campaign to the group.  
* Submit a campaign for approval; creator cannot self-approve under maker-checker; approver approves; deployment begins.  
* Deploy a player release to a 10-device pilot ring; force one failure; rollout stops according to threshold and exposes evidence.  
* Schedule two overlapping campaigns; system shows conflict and deterministic winner before publish.  
* A device goes offline; threshold triggers notification; device recovers; incident automatically transitions to recovered.  
* Generate proof-of-play report by location and campaign, export it, and reconcile counts with raw playback events.

# **9\. Phase-2 Entry / Exit Criteria**

Entry: Phase-1 APIs, database, authentication, device registration and basic publishing are stable in UAT. Exit: all Phase-2 P1 requirements pass functional/UAT tests, zero open Sev-1 defects, audit and security tests pass, rollback procedures are documented, and load tests meet the stated device-scale target.

# **10\. Phase-2 Exclusions / Deferred to Phase 3**

* AI-generated creatives and automatic campaign optimization  
* Advanced external data/IoT orchestration at large scale  
* Video wall synchronization and frame-accurate multi-screen composition  
* Ad inventory, programmatic advertising and revenue billing  
* Edge caching architecture beyond standard player-local cache  
* Advanced computer-vision verification  
* White-label multi-region SaaS control plane and enterprise SSO federation hardening

# **11\. Phase-2 Delivery Sequence**

1. P2-A: Governance \+ device operations foundations  
2. P2-B: Templates \+ widgets \+ advanced campaigns  
3. P2-C: Monitoring \+ notifications \+ reporting  
4. P2-D: APIs/webhooks \+ enterprise administration  
5. P2-E: Performance, security, UAT and production hardening