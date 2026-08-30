# Digital Signage Cloud Platform

Phase 3 SRS / FRD \- Intelligent, Connected and Global Signage Platform

Version 1.0 | Prepared for implementation planning | Date: 29 August 2026

# **1\. Phase-3 Purpose and Boundary**

Phase 3 is the advanced productization stage. It turns the platform from an enterprise CMS and device-operations product into an intelligent, globally scalable signage ecosystem supporting dynamic data, AI-assisted operations, synchronized displays, advertising workflows, resilient edge delivery and multi-region SaaS capabilities.

| Phase-3 pillar | Business outcome |
| :---- | :---- |
| Intelligent content | Generate, adapt and optimize content for different contexts while keeping governance in control. |
| Connected data | Render trusted live data from APIs, feeds and enterprise systems with fallback behavior. |
| Advanced playback | Support synchronized displays, video walls and richer playback orchestration. |
| Commercial monetization | Support ad inventory, campaigns, proof-of-play and billing-ready reporting. |
| Global platform | Introduce regional resiliency, white-labeling, enterprise federation and advanced tenancy. |
| Operational intelligence | Detect anomalies and provide actionable recommendations for fleet/content issues. |

# **2\. Phase-3 Scope Summary**

| ID | Module | Scope |
| :---- | :---- | :---- |
| P3-M01 | AI Content Intelligence | AI-assisted copy, resizing, localization, creative variants, safety controls and approval. |
| P3-M02 | Dynamic Data & Widgets | Live API/JSON/RSS/IoT feeds, transformations, cache, schema validation and fallbacks. |
| P3-M03 | Decisioning & Optimization | Context-aware content selection, rule scoring and optional experimentation. |
| P3-M04 | Video Wall & Sync | Synchronized playback, multi-display canvases, grouping and clock discipline. |
| P3-M05 | Ad & Monetization | Inventory, ad slots, campaign booking, proof-of-play and billing-ready records. |
| P3-M06 | Edge & Resilience | Regional edge distribution, prefetch, bandwidth policy, offline bundles and recovery. |
| P3-M07 | Fleet AI Operations | Anomaly detection, predictive device health and recommended remediation. |
| P3-M08 | Global SaaS & White Label | Custom domains/branding, regional tenancy, SSO federation and enterprise controls. |
| P3-M09 | Advanced Integrations | ERP/POS/CRM/connectors, event bus and partner API ecosystem. |
| P3-M10 | Advanced Security | Device certificates, stronger key lifecycle, policy engine and security analytics. |
| P3-M11 | Data Platform | Lake/warehouse exports, semantic metrics and long-term analytics. |
| P3-M12 | Developer Platform | SDKs, player contract versions, sandbox/test tenant and API documentation. |

# **3\. Functional Requirements**

## **P3-M01 AI Content Intelligence**

| FR ID | Feature | Functional requirement |
| :---- | :---- | :---- |
| P3-AI-001 | AI copy assistant | Authorized users shall generate or transform text within approved content policies. |
| P3-AI-002 | Creative variants | System shall generate structured creative variants for approved dimensions/zones; human approval remains configurable. |
| P3-AI-003 | Localization | Generate localized content variants while preserving placeholders, formatting and brand rules. |
| P3-AI-004 | Safety & governance | AI output shall be tagged, versioned and optionally routed through approval before publication. |
| P3-AI-005 | Explainability | System shall record model/provider, prompt template version and output revision metadata without storing secrets. |

## **P3-M02 Dynamic Data & Widgets**

| FR ID | Feature | Functional requirement |
| :---- | :---- | :---- |
| P3-DAT-001 | Connector sources | Support REST/JSON, RSS/Atom and approved enterprise connectors. |
| P3-DAT-002 | Schema validation | Incoming data shall be validated against a declared schema before rendering. |
| P3-DAT-003 | Transformations | Provide safe mapping/filter/format transformations without arbitrary server-side code execution. |
| P3-DAT-004 | Caching | Support TTL, last-known-good data and stale-while-revalidate semantics. |
| P3-DAT-005 | Fallback | Widgets shall display a deterministic fallback when the source is unavailable or invalid. |

## **P3-M03 Decisioning & Optimization**

| FR ID | Feature | Functional requirement |
| :---- | :---- | :---- |
| P3-DEC-001 | Context inputs | Decision engine may use device, location, time, campaign, tag and approved external context. |
| P3-DEC-002 | Priority | Rules must resolve deterministically with auditable reasons. |
| P3-DEC-003 | Experimentation | Support configurable A/B allocation for eligible campaigns with controlled percentages. |
| P3-DEC-004 | Guardrails | Frequency caps, campaign windows and mandatory-content rules shall constrain optimization. |

## **P3-M04 Video Wall & Sync**

| FR ID | Feature | Functional requirement |
| :---- | :---- | :---- |
| P3-SYN-001 | Wall definition | Users shall define a logical wall as a set of synchronized displays. |
| P3-SYN-002 | Canvas mapping | Map each physical display to a viewport in a virtual canvas. |
| P3-SYN-003 | Sync protocol | Players shall use clock synchronization and scheduled start markers to align playback. |
| P3-SYN-004 | Degraded mode | If one member is unavailable, the wall shall enter a declared degraded state rather than silently corrupting the layout. |

## **P3-M05 Ad & Monetization**

| FR ID | Feature | Functional requirement |
| :---- | :---- | :---- |
| P3-ADS-001 | Inventory | Define sellable screen/zone inventory with operating hours and availability. |
| P3-ADS-002 | Ad campaigns | Book creatives against inventory, target, dates and frequency rules. |
| P3-ADS-003 | Proof-of-play | Associate playback evidence with ad booking, placement and device. |
| P3-ADS-004 | Billing-ready | Expose billable impression/playback aggregates; actual payment processing may remain external. |

## **P3-M06 Edge & Resilience**

| FR ID | Feature | Functional requirement |
| :---- | :---- | :---- |
| P3-EDG-001 | Regional edge | Media delivery may route through regional cache/CDN nodes. |
| P3-EDG-002 | Prefetch | Predictive or scheduled prefetch shall stage upcoming assets before playback. |
| P3-EDG-003 | Bandwidth policy | Tenant/device policies shall control download windows and concurrency. |
| P3-EDG-004 | Offline bundle | Player shall consume signed offline bundles with expiry and integrity verification. |

## **P3-M07 Fleet AI Operations**

| FR ID | Feature | Functional requirement |
| :---- | :---- | :---- |
| P3-OPS-001 | Anomaly detection | Detect unusual heartbeat, storage, error, playback and network patterns. |
| P3-OPS-002 | Recommended action | System shall suggest probable remediation with confidence and supporting evidence. |
| P3-OPS-003 | Human control | No automated destructive action without explicit policy and authorization. |

## **P3-M08 Global SaaS & White Label**

| FR ID | Feature | Functional requirement |
| :---- | :---- | :---- |
| P3-GLO-001 | White label | Tenant may configure branding, custom domain and customer-facing email identity. |
| P3-GLO-002 | SSO federation | Support enterprise OIDC/SAML federation with mapped roles/groups. |
| P3-GLO-003 | Regional tenancy | Support data residency/processing region assignment where infrastructure permits. |
| P3-GLO-004 | Platform admin | Global admin shall view tenant, region and service health without crossing tenant content boundaries. |

## **P3-M09 Advanced Integrations**

| FR ID | Feature | Functional requirement |
| :---- | :---- | :---- |
| P3-INT-101 | Integration catalog | Support connector registration, credentials, health and versioning. |
| P3-INT-102 | Event bus | Expose normalized domain events to downstream consumers. |
| P3-INT-103 | Partner API | Version public APIs and publish OpenAPI contracts with deprecation policy. |

## **P3-M10 Advanced Security**

| FR ID | Feature | Functional requirement |
| :---- | :---- | :---- |
| P3-SEC-101 | Device identity | Support certificate/device-identity based authentication where platform permits. |
| P3-SEC-102 | Key lifecycle | Automate key/certificate rotation, revocation and expiry alerts. |
| P3-SEC-103 | Policy engine | Evaluate device/network/content security policies centrally. |
| P3-SEC-104 | Security analytics | Track auth/device anomalies and sensitive administrative actions. |

## **P3-M11 Data Platform**

| FR ID | Feature | Functional requirement |
| :---- | :---- | :---- |
| P3-DWH-101 | Historical export | Publish normalized operational and playback data to analytics storage. |
| P3-DWH-102 | Semantic metrics | Standardize definitions for uptime, delivery, play count and campaign reach. |
| P3-DWH-103 | Long-term analytics | Support high-volume historical queries without overloading the transactional database. |

## **P3-M12 Developer Platform**

| FR ID | Feature | Functional requirement |
| :---- | :---- | :---- |
| P3-DEV-101 | SDK contracts | Publish player/API SDK guidance and versioned schemas. |
| P3-DEV-102 | Sandbox | Provide isolated test tenant/device simulator workflow. |
| P3-DEV-103 | API documentation | Publish interactive, versioned API documentation and changelog. |

# **4\. Exact Frontend Screen Inventory \- Phase 3**

| ID | Screen | Required capabilities |
| :---- | :---- | :---- |
| P3-01 | AI Content Studio | Prompt-assisted text/creative generation, brand guardrails, version compare and approval handoff. |
| P3-02 | AI Variant Manager | Generate/manage creative variants across dimensions and target contexts. |
| P3-03 | Data Source Manager | Connectors, credentials, schema, health and refresh policy. |
| P3-04 | Dynamic Widget Designer | Bind UI widgets to live data, transformations and fallbacks. |
| P3-05 | Decisioning Rules | Context inputs, rule priority, frequency caps and decision preview. |
| P3-06 | Experiment Manager | A/B allocation, cohorts, start/end windows and results. |
| P3-07 | Video Wall Manager | Create wall, assign displays, map viewports and sync policy. |
| P3-08 | Wall Preview / Control | Live wall state, member health, start/stop/sync and degraded state. |
| P3-09 | Ad Inventory | Define sellable zones/screens, availability and rate-card metadata. |
| P3-10 | Ad Campaign Manager | Booking, creative, targeting, frequency and proof-of-play. |
| P3-11 | Ad Performance Report | Booked vs delivered plays, device/location breakdown and export. |
| P3-12 | Edge Delivery Dashboard | Cache hit ratio, bandwidth, queued downloads, regional status. |
| P3-13 | Offline Bundle Manager | Create signed bundles, expiry, target groups and rollout state. |
| P3-14 | Fleet Intelligence | Anomalies, risk score, recommended remediation and evidence. |
| P3-15 | AI Operations Rules | Configure detection sensitivity and automation guardrails. |
| P3-16 | White-Label Settings | Custom domain, brand, emails and tenant theme. |
| P3-17 | Enterprise SSO | Federation setup, claims mapping, login policy and test connection. |
| P3-18 | Regional Platform Admin | Tenant region, residency metadata and service health. |
| P3-19 | Integration Catalog | Available connectors, versions, install/configure flow. |
| P3-20 | Event Bus / Subscriptions | Domain event subscriptions and consumer status. |
| P3-21 | Security Center | Device identity, certificates, policy violations and auth anomalies. |
| P3-22 | Analytics Data Export | Datasets, schedules, destinations, status and retention. |
| P3-23 | Developer Portal | API docs, keys, sandbox, player contract versions and changelog. |
| P3-24 | Platform Operations | Global service status, regions, queues, workers and incidents. |

# **5\. API Catalogue \- Phase 3**

| Method | Endpoint | Purpose |
| :---- | :---- | :---- |
| POST | /api/v1/ai/generate/text | Generate governed text variant |
| POST | /api/v1/ai/generate/creative | Generate structured creative variant |
| POST | /api/v1/ai/localize | Create localized variant |
| POST | /api/v1/data-sources | Create data source |
| POST | /api/v1/data-sources/{id}/test | Test source |
| GET | /api/v1/data-sources/{id}/health | Source health |
| POST | /api/v1/widgets/{id}/bindings | Bind widget to data source |
| POST | /api/v1/decision-rules/preview | Preview decision outcome |
| POST | /api/v1/experiments | Create experiment |
| POST | /api/v1/video-walls | Create wall |
| POST | /api/v1/video-walls/{id}/members | Assign member |
| POST | /api/v1/video-walls/{id}/sync | Start synchronized session |
| POST | /api/v1/ad-inventory | Create inventory slot |
| POST | /api/v1/ad-campaigns | Book ad campaign |
| GET | /api/v1/reports/ad-performance | Ad performance |
| POST | /api/v1/edge/bundles | Create offline bundle |
| POST | /api/v1/edge/bundles/{id}/publish | Publish bundle |
| GET | /api/v1/edge/metrics | Edge metrics |
| GET | /api/v1/fleet-intelligence/anomalies | List anomalies |
| POST | /api/v1/fleet-intelligence/{id}/acknowledge | Acknowledge anomaly |
| POST | /api/v1/fleet-intelligence/{id}/remediation | Execute approved remediation |
| POST | /api/v1/sso/providers | Configure SSO provider |
| POST | /api/v1/sso/providers/{id}/test | Test SSO |
| POST | /api/v1/connectors | Register connector |
| GET | /api/v1/events | List domain events |
| POST | /api/v1/subscriptions | Create event subscription |
| GET | /api/v1/security/devices/{id}/identity | Device identity |
| POST | /api/v1/security/certificates/rotate | Rotate certificates |
| GET | /api/v1/security/policy-violations | Security violations |
| POST | /api/v1/data-exports | Create dataset export |
| GET | /api/v1/platform/regions | Region/service health |
| GET | /api/v1/developer/openapi | Versioned OpenAPI metadata |

# **6\. Database ER Model \- Phase 3 Extensions**

tenant  
  |-- ai\_policies \--\< ai\_requests \--\< ai\_outputs  
  |-- data\_sources \--\< data\_source\_credentials  
  |                 |--\< data\_source\_schemas  
  |-- decision\_policies \--\< decision\_rules  
  |-- experiments \--\< experiment\_variants \--\< experiment\_assignments  
  |-- video\_walls \--\< video\_wall\_members  
  |-- ad\_inventory \--\< ad\_bookings \--\< ad\_playback\_links  
  |-- edge\_bundles \--\< edge\_bundle\_devices  
  |-- anomaly\_rules \--\< anomalies \--\< anomaly\_actions  
  |-- sso\_providers  
  |-- connectors \--\< connector\_instances  
  |-- event\_subscriptions \--\< event\_deliveries  
  |-- device\_identities \--\< identity\_credentials  
  |-- security\_policies \--\< policy\_violations  
  |-- data\_exports  
  |-- api\_products \--\< api\_versions

playback\_events \-\> ad\_playback\_links \-\> ad\_bookings  
device \-\> video\_wall\_members  
location \-\> ad\_inventory

| Entity | Key fields | Purpose |
| :---- | :---- | :---- |
| ai\_policies | tenant\_id, policy\_type, rules\_json, active | AI usage and safety controls. |
| ai\_requests | tenant\_id, actor\_id, provider, model\_ref, template\_version, status | AI operation record. |
| ai\_outputs | request\_id, output\_asset\_id, safety\_status, approved\_by | Generated output evidence. |
| data\_sources | tenant\_id, type, endpoint\_ref, schema\_id, cache\_policy, state | External/live data source. |
| data\_source\_credentials | data\_source\_id, secret\_ref, rotation\_state | Secret reference only. |
| data\_source\_schemas | data\_source\_id, schema\_json, version\_no | Validated source schema. |
| decision\_policies | tenant\_id, name, guardrails\_json, active | Decisioning policy header. |
| decision\_rules | policy\_id, priority, conditions\_json, actions\_json | Deterministic decision rules. |
| experiments | tenant\_id, campaign\_id, allocation\_json, start\_at, end\_at | Experiment container. |
| experiment\_variants | experiment\_id, variant\_id, allocation\_pct | Variant allocations. |
| experiment\_assignments | experiment\_id, device\_id, variant\_id | Stable assignment. |
| video\_walls | tenant\_id, name, canvas\_json, sync\_policy, status | Logical video wall. |
| video\_wall\_members | wall\_id, device\_id, viewport\_json, role | Physical display mapping. |
| ad\_inventory | tenant\_id, location\_id, device\_id, zone\_ref, slot\_type, rate\_card\_ref | Sellable slot. |
| ad\_bookings | inventory\_id, campaign\_id, booked\_units, rate\_card\_ref | Ad booking. |
| ad\_playback\_links | booking\_id, playback\_event\_id, billable, evidence\_json | Proof-of-play linkage. |
| edge\_bundles | tenant\_id, bundle\_version, manifest\_json, signature, expires\_at | Signed offline bundle. |
| edge\_bundle\_devices | bundle\_id, device\_id, state, synced\_at | Bundle rollout state. |
| anomaly\_rules | tenant\_id, signal\_type, threshold\_json, severity | Detection rule. |
| anomalies | tenant\_id, device\_id, rule\_id, score, state, evidence\_json | Detected operational anomaly. |
| anomaly\_actions | anomaly\_id, actor\_id, action, outcome, executed\_at | Remediation history. |
| sso\_providers | tenant\_id, protocol, metadata\_ref, claim\_mapping\_json, active | SSO federation config. |
| connectors | platform/tenant scope, name, version, contract\_ref | Connector catalogue. |
| connector\_instances | connector\_id, tenant\_id, config\_ref, state | Installed connector instance. |
| event\_subscriptions | tenant\_id, event\_type, destination\_ref, active | Domain event consumer. |
| event\_deliveries | subscription\_id, event\_id, state, attempt\_no | Event delivery evidence. |
| device\_identities | device\_id, identity\_type, status | Logical device identity. |
| identity\_credentials | identity\_id, credential\_ref, issued\_at, expires\_at, revoked\_at | Certificate/credential lifecycle. |
| security\_policies | tenant\_id, scope\_type, conditions\_json, actions\_json | Central security policy. |
| policy\_violations | policy\_id, entity\_type, entity\_id, severity, state | Violation record. |
| data\_exports | tenant\_id, dataset, destination, schedule\_json, state | Long-term analytics export. |
| api\_versions | api\_product\_id, version, lifecycle\_state, sunset\_at | Version lifecycle. |

# **7\. Advanced Architecture Requirements**

* Use a regional CDN/object-storage strategy for large media; transactional PostgreSQL remains system-of-record for metadata.  
* Use an event-driven data path for high-volume playback, device telemetry and integration events; transactional APIs remain synchronous for control-plane operations.  
* Player manifests and offline bundles must be signed and content hashes verified before activation.  
* Video wall synchronization should use monotonic scheduled markers and a declared tolerance budget rather than assuming perfect network timing.  
* AI features must remain optional and policy-governed. Core publishing must continue to work when AI providers are unavailable.  
* Long-term analytics should be separated from OLTP storage to prevent playback/event volume from degrading control-plane performance.

# **8\. Phase-3 Non-Functional Requirements**

| ID | Area | Requirement |
| :---- | :---- | :---- |
| NFR3-01 | Global availability | Design for 99.95% control-plane target with regional failover strategy where deployed. |
| NFR3-02 | Scale | Support 100,000+ registered devices as a target architecture; exact capacity validated by load tests. |
| NFR3-03 | Media delivery | Large asset delivery shall use CDN/edge caching and resumable download. |
| NFR3-04 | Event throughput | Telemetry/playback path shall be horizontally scalable and back-pressure aware. |
| NFR3-05 | Security | Certificate/key rotation and tenant isolation shall be continuously testable. |
| NFR3-06 | AI resilience | AI provider outage must not block normal CMS or playback operations. |
| NFR3-07 | Data residency | Region assignment and export policy shall be explicit per tenant where supported. |
| NFR3-08 | Compatibility | Player API contracts shall be versioned and backward-compatible within supported player versions. |

# **9\. Phase-3 Acceptance Scenarios**

* Generate a localized campaign variant with AI, route it through approval, publish to a targeted region, and preserve all generation/version metadata.  
* Disconnect a live data source; widget continues to render last-known-good content, then refreshes automatically when the source returns.  
* Create a 2x2 video wall, start synchronized playback, remove one device, verify degraded-state handling, restore device and resynchronize.  
* Book advertising inventory, run a scheduled campaign, collect playback evidence, and reconcile billable play aggregates.  
* Pre-stage an offline bundle to a group, disconnect Internet, verify signed bundle playback, expiry behavior and recovery after reconnect.  
* Trigger an anomaly for repeated device heartbeat failure; system generates recommendation, human acknowledges, and approved remediation is logged.  
* Configure enterprise SSO, map group claims to roles, test login, revoke provider access, and verify audit evidence.

# **10\. Phase-3 Entry / Exit Criteria**

Entry: Phase 2 is production-stable, event schemas are versioned, device/player contracts have compatibility tests, and enterprise monitoring/approval foundations are operational. Exit: target advanced capabilities pass functional, integration, security and scale tests; monetization is independently reconciled; synchronization is validated on supported hardware; AI features pass governance review; and regional/global operating runbooks exist.

# **11\. Recommended Phase-3 Sub-phases**

1. P3-A: Dynamic data \+ developer platform  
2. P3-B: AI content intelligence \+ decisioning  
3. P3-C: Video wall/synchronization \+ edge resilience  
4. P3-D: Ad/monetization \+ advanced analytics  
5. P3-E: Global SaaS, SSO, security and regional operations

# **12\. Phase-3 Out-of-Scope by Default**

* Building a proprietary TV operating system  
* Full ad-exchange / programmatic bidding infrastructure unless separately approved  
* Payments/merchant settlement processing inside the signage CMS  
* Unrestricted arbitrary code execution through third-party widgets  
* Autonomous AI actions that can create irreversible operational or financial consequences

# **13\. Product Direction After Phase 3**

                    Digital Signage Cloud Platform  
                               |  
       \+-----------------------+------------------------+  
       |                       |                        |  
   ENTERPRISE CMS         INTELLIGENCE            ECOSYSTEM  
   Content / Layout       AI / Decisioning         APIs / SDKs  
   Campaign / Schedule   Analytics / Anomaly      Connectors  
       |                       |                        |  
       \+-----------------------+------------------------+  
                               |  
                     GLOBAL DEVICE FABRIC  
               LG | Samsung | Android | Windows  
                               |  
                    Commercial Displays / Walls

# **14\. Final Phase Boundary**

Phase 2 should make the product enterprise-operable. Phase 3 should make it differentiated, intelligent and globally extensible. The core principle remains the same: the cloud defines portable signage intent, content, layout, targeting and policy; manufacturer-specific native players execute that intent through a versioned player contract.