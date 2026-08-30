**DIGITAL SIGNAGE CLOUD PLATFORM**  
Software Requirements Specification / Functional Requirements Document

Implementation-ready baseline for enterprise Digital Signage CMS

LG webOS / Samsung Tizen / Android / Windows player-ready architecture

Version 1.0 \| 29 August 2026

| **Document control**   | **Value**                                                                    |
|------------------------|------------------------------------------------------------------------------|
| Document               | SRS / FRD - Digital Signage Cloud Platform                                   |
| Version                | 1.0                                                                          |
| Status                 | Baseline for design and Phase-1 development                                  |
| Primary audience       | Product, UX, Frontend, Backend, QA, DevOps, Solution Architecture            |
| Architecture principle | Device-agnostic cloud core with manufacturer-specific native player adapters |

## Key architectural decision

The cloud platform MUST remain manufacturer-neutral. LG webOS, Samsung
Tizen and future player technologies consume a common Player API and
report into the same Device, Content, Layout, Campaign, Scheduling and
Playback model. Manufacturer differences belong in native-client
adapters and capability mappings, not in the core CMS data model.

# 1. Document Purpose and Scope

This SRS/FRD converts the business requirements into an implementation
baseline for the cloud backend and web administration portal. The native
LG/Samsung player applications are intentionally outside Phase-1
implementation, but the cloud contracts must be player-ready from Day 1.

## 1.1 In scope

- Multi-tenant organization administration

- Unlimited/deep location hierarchy with inheritance and overrides

- User, role and permission management

- Device registry, grouping, capabilities and health state

- Media/content library with metadata, versions and processing states

- Reusable layouts, zones and templates

- Playlists and playlist items

- Campaigns, targeting and schedules

- Asynchronous publishing and deployment tracking

- Player synchronization and heartbeat APIs

- Audit trail, notifications and operational dashboards

- REST API foundation and WebSocket/MQTT-ready event model

- Object storage/CDN integration for media assets

## 1.2 Out of scope for Phase-1

- Native LG webOS player application

- Native Samsung Tizen player application

- Advanced video-wall synchronization

- Ad billing and revenue management

- AI-generated content

- Advanced IoT/device telemetry

- Full digital-out-of-home advertising marketplace

- Complex third-party workflow integrations beyond API/webhook
  foundation

# 2. Product Goals and Success Criteria

| **Goal**                       | **Phase-1 success measure**                                                                    |
|--------------------------------|------------------------------------------------------------------------------------------------|
| Centralized content management | Users can upload, organize, version and retire supported media assets.                         |
| Flexible location targeting    | Any campaign can target a node, subtree, device group or individual device.                    |
| Flexible screen composition    | A layout can contain 1..N independently positioned zones.                                      |
| Reliable publishing            | Publishing is asynchronous, retryable and observable per target device.                        |
| Offline-ready player model     | A future native player can download a complete content manifest and continue from local cache. |
| Enterprise access control      | Tenant isolation, RBAC and audit logging exist from first release.                             |
| Vendor-neutral architecture    | The core APIs contain no LG/Samsung-specific business rules.                                   |

# 3. Product Scope / Module Map

| **ID** | **Module**              | **Functional responsibility**                                     |
|--------|-------------------------|-------------------------------------------------------------------|
| M01    | Identity & Access       | Login, sessions/tokens, RBAC, permissions, user lifecycle         |
| M02    | Tenant / Organization   | Organizations, settings, branding, quotas, time zone              |
| M03    | Location Hierarchy      | Unlimited nodes, types, metadata, inheritance, tags               |
| M04    | Device Management       | Registration, approval, grouping, capabilities, assignment        |
| M05    | Content / Asset CMS     | Upload, metadata, folders, tags, versions, lifecycle              |
| M06    | Media Processing        | Validation, scan hook, thumbnails, transcode state, CDN URL       |
| M07    | Layout & Zone Designer  | Canvas, zones, properties, templates, versions                    |
| M08    | Playlist Management     | Ordered assets/layouts, duration, transitions, fallback           |
| M09    | Campaign Management     | Campaign package, priority, approval, targeting                   |
| M10    | Scheduling              | Date/time windows, recurrence, timezone-aware rules               |
| M11    | Publishing / Deployment | Jobs, device fan-out, retries, acknowledgements                   |
| M12    | Player Gateway          | Registration, sync manifest, heartbeat, capability and event APIs |
| M13    | Monitoring              | Device health, deployments, errors, content sync status           |
| M14    | Reports / Playback      | Playback event model, proof-of-play foundation                    |
| M15    | Notifications           | In-app/email-ready operational notifications                      |
| M16    | Audit & Governance      | Immutable-style action history, actor/entity/result               |
| M17    | Platform Settings       | System dictionaries, upload policies, retention and defaults      |
| M18    | Integration API         | API keys/service accounts, webhooks, external identifiers         |

# 4. Detailed Functional Requirements

## M01 Identity & Access

- FR-AUTH-001 User login/logout

- FR-AUTH-002 Token/session lifecycle

- FR-AUTH-003 Password reset / account recovery

- FR-AUTH-004 RBAC with permission-level checks

- FR-AUTH-005 User activation/deactivation

- FR-AUTH-006 Service account/API key lifecycle

- FR-AUTH-007 Tenant isolation on every protected query

## M02 Tenant / Organization

- FR-ORG-001 Create/read/update organization

- FR-ORG-002 Organization timezone and locale

- FR-ORG-003 Organization branding assets

- FR-ORG-004 Usage quotas: devices/storage/users

- FR-ORG-005 Organization lifecycle status

## M03 Location Hierarchy

- FR-LOC-001 Arbitrary-depth parent/child nodes

- FR-LOC-002 Node type dictionary

- FR-LOC-003 Address/GPS/timezone metadata

- FR-LOC-004 Tagging

- FR-LOC-005 Descendant/subtree targeting

- FR-LOC-006 Inheritance and child override

- FR-LOC-007 Move/merge validation to prevent cycles

## M04 Device Management

- FR-DEV-001 Device registration request

- FR-DEV-002 Approval/rejection

- FR-DEV-003 Assign location

- FR-DEV-004 Device groups and tags

- FR-DEV-005 Capability registry

- FR-DEV-006 Online/offline state based on heartbeat

- FR-DEV-007 Device decommissioning

- FR-DEV-008 Remote command queue

## M05 Content / Asset CMS

- FR-CNT-001 Upload asset

- FR-CNT-002 Resume/retry upload

- FR-CNT-003 Asset metadata

- FR-CNT-004 Folder/tag organization

- FR-CNT-005 Preview/thumbnail

- FR-CNT-006 Versioning

- FR-CNT-007 Draft/published/archived lifecycle

- FR-CNT-008 Soft delete/restore

## M06 Media Processing

- FR-MED-001 Validate MIME/size

- FR-MED-002 Processing state machine

- FR-MED-003 Generate thumbnail/poster

- FR-MED-004 Video metadata extraction

- FR-MED-005 Optional transcode profiles

- FR-MED-006 CDN delivery URL

## M07 Layout Designer

- FR-LYT-001 Create layout canvas

- FR-LYT-002 Add/edit/delete zones

- FR-LYT-003 Absolute position and size

- FR-LYT-004 Background/border/padding/layering

- FR-LYT-005 Bind content/widget to zone

- FR-LYT-006 Preview

- FR-LYT-007 Layout versioning

- FR-LYT-008 Reusable templates

## M08 Playlist

- FR-PLY-001 Create playlist

- FR-PLY-002 Add/reorder items

- FR-PLY-003 Item duration/transition

- FR-PLY-004 Loop behavior

- FR-PLY-005 Fallback playlist

- FR-PLY-006 Version and publish state

## M09 Campaign

- FR-CMP-001 Campaign lifecycle

- FR-CMP-002 Bind layout + playlist/content

- FR-CMP-003 Priority

- FR-CMP-004 Target devices/groups/locations/tags

- FR-CMP-005 Approval workflow

- FR-CMP-006 Preview before publish

## M10 Scheduling

- FR-SCH-001 Effective start/end

- FR-SCH-002 Daily time windows

- FR-SCH-003 Recurrence

- FR-SCH-004 Target timezone handling

- FR-SCH-005 Priority resolution

- FR-SCH-006 Conflict validation

- FR-SCH-007 Expiry/auto-retirement

## M11 Publishing

- FR-PUB-001 Create deployment

- FR-PUB-002 Materialize target device set

- FR-PUB-003 Generate deployment manifest

- FR-PUB-004 Queue delivery

- FR-PUB-005 Retry transient failures

- FR-PUB-006 Device acknowledgement

- FR-PUB-007 Partial success status

- FR-PUB-008 Cancel/redeploy

## M12 Player Gateway

- FR-PLYR-001 Player registration

- FR-PLYR-002 Authentication/bootstrap

- FR-PLYR-003 Sync manifest

- FR-PLYR-004 Asset download authorization

- FR-PLYR-005 Heartbeat

- FR-PLYR-006 Playback/event ingestion

- FR-PLYR-007 Capability reporting

- FR-PLYR-008 Command polling/acknowledgement

## M13 Monitoring

- FR-MON-001 Device dashboard

- FR-MON-002 Last heartbeat

- FR-MON-003 Storage/network status

- FR-MON-004 Deployment status

- FR-MON-005 Device event history

- FR-MON-006 Offline threshold

## M14 Reports

- FR-RPT-001 Deployment summary

- FR-RPT-002 Playback event foundation

- FR-RPT-003 Device uptime foundation

- FR-RPT-004 Location-wise status summary

- FR-RPT-005 Export-ready reporting endpoints

## M15 Notifications

- FR-NOT-001 Notification inbox

- FR-NOT-002 Device offline alerts

- FR-NOT-003 Deployment failure alerts

- FR-NOT-004 Low storage alerts

- FR-NOT-005 Approval alerts

## M16 Audit

- FR-AUD-001 Record create/update/delete/publish

- FR-AUD-002 Record actor and timestamp

- FR-AUD-003 Entity before/after summary

- FR-AUD-004 Search/filter audit trail

## M17 Settings

- FR-SET-001 Supported MIME policies

- FR-SET-002 Default device heartbeat interval

- FR-SET-003 Retention configuration

- FR-SET-004 System dictionaries

- FR-SET-005 Branding defaults

## M18 Integration API

- FR-INT-001 API key/service account

- FR-INT-002 Webhook subscriptions

- FR-INT-003 External entity identifiers

- FR-INT-004 Idempotency keys for mutating APIs

# 5. Frontend Information Architecture and Exact Screen List

The Phase-1 web portal should expose 25 operational screens. The list
below is the baseline; screens may be implemented as route-level pages
with drawers/modals without changing the functional scope.

| **Screen** | **Name**                         | **Primary data / actions**                                        |
|------------|----------------------------------|-------------------------------------------------------------------|
| SCR-01     | Login / Authentication           | Sign in, recovery, organization-aware session start               |
| SCR-02     | Dashboard                        | Device health, deployment status, content counts, recent activity |
| SCR-03     | Organizations / Tenant Settings  | Organization profile, branding, timezone, quotas                  |
| SCR-04     | Users                            | User search, invite/create, status, role assignment               |
| SCR-05     | Roles & Permissions              | Permission matrix and role management                             |
| SCR-06     | Location Tree                    | Unlimited hierarchy tree, create/edit/move, map/address metadata  |
| SCR-07     | Location Details                 | Subtree summary, devices, campaigns, tags, inherited assignments  |
| SCR-08     | Device List                      | Search/filter/group devices and status                            |
| SCR-09     | Device Details                   | Health, capabilities, assignments, sync and commands              |
| SCR-10     | Device Groups                    | Create/manage logical groups and tags                             |
| SCR-11     | Content Library                  | Folders, filters, tags, grid/list, lifecycle                      |
| SCR-12     | Upload Content                   | Upload, metadata, tags, processing progress                       |
| SCR-13     | Content Details                  | Preview, versions, metadata, usage and archive                    |
| SCR-14     | Templates                        | Reusable layout templates library                                 |
| SCR-15     | Layout List                      | Create/edit/archive layouts and version state                     |
| SCR-16     | Screen Designer                  | Canvas, zone editor, component palette, properties panel          |
| SCR-17     | Playlists                        | Playlist list and item sequencing                                 |
| SCR-18     | Playlist Editor                  | Add/reorder assets/layouts, duration and fallback                 |
| SCR-19     | Campaigns                        | Campaign list, filters, state, priority, publish status           |
| SCR-20     | Campaign Editor                  | Content/layout/playlist/target/schedule configuration             |
| SCR-21     | Schedule Calendar                | Calendar/time-window overview and conflicts                       |
| SCR-22     | Publishing / Deployments         | Deployment jobs, progress, retry and target status                |
| SCR-23     | Monitoring                       | Live device map/list, offline/warning/critical views              |
| SCR-24     | Reports                          | Deployment, device, location and playback foundation              |
| SCR-25     | Audit / Settings / Notifications | Operational governance views and configurable defaults            |

## 5.1 Screen Designer functional specification

- Canvas supports arbitrary aspect ratio and portrait/landscape modes.

- Zone model is generic: x, y, width, height, z-index, rotation and
  style properties.

- Zone content types are pluggable: image, video, text, ticker/marquee,
  clock, web/HTML placeholder, QR, widget placeholder.

- Properties panel controls dimensions, typography, colors, media fit,
  padding, border and behavior.

- Designer saves JSON layout definition plus server-side version
  metadata.

- Preview uses the same normalized layout JSON that future native
  clients will receive.

# 6. UX Navigation and Screen-Level Acceptance Criteria

| **Area**          | **Acceptance baseline**                                                                   |
|-------------------|-------------------------------------------------------------------------------------------|
| Dashboard         | All critical health information is visible without drilling into devices.                 |
| Content Library   | User can locate an asset using folder, type, tag, status or text search.                  |
| Upload Content    | User sees processing state and cannot publish an asset until it is READY.                 |
| Layout List       | User can see draft/published/archive versions and last updated user/time.                 |
| Screen Designer   | User can build 1, 2, 3, 4, 6 or fully custom zone layouts without a separate screen type. |
| Playlist Editor   | User can reorder items and set duration/transition/fallback.                              |
| Campaign Editor   | User can select target locations/devices/groups and preview effective scope.              |
| Schedule Calendar | User can see time conflicts before publishing.                                            |
| Deployment        | User sees total targets, success, pending, failed and retryable counts.                   |
| Monitoring        | User can filter online/offline/warning/critical and open device details.                  |
| Audit             | User can filter by actor, entity, action and date range.                                  |

# 7. API Standards and Conventions

Base path: /api/v1. JSON is the default representation. APIs must be
tenant-scoped and authenticated unless explicitly marked as
public/player-bootstrap endpoints.

> Headers:  
> Authorization: Bearer \<token\>  
> X-Tenant-ID: \<tenant_uuid\>  
> Idempotency-Key: \<uuid\> \# required for selected create/publish
> operations  
> Content-Type: application/json

## 7.1 Standard response envelope

> {  
> "data": {...},  
> "meta": {"request_id": "..."},  
> "errors": \[\]  
> }

## 7.2 Standard error codes

| **HTTP** | **Meaning**             | **Example code**        |
|----------|-------------------------|-------------------------|
| 400      | Validation error        | VALIDATION_ERROR        |
| 401      | Unauthenticated         | UNAUTHENTICATED         |
| 403      | Not authorized          | FORBIDDEN               |
| 404      | Entity not found        | NOT_FOUND               |
| 409      | Conflict/idempotency    | CONFLICT                |
| 422      | Business rule failure   | BUSINESS_RULE_VIOLATION |
| 429      | Rate limit              | RATE_LIMITED            |
| 500      | Unexpected server error | INTERNAL_ERROR          |

# 8. API Catalogue

## Authentication & Users

| **Method** | **Endpoint**          | **Purpose**              |
|------------|-----------------------|--------------------------|
| POST       | /auth/login           | Authenticate portal user |
| POST       | /auth/refresh         | Refresh access token     |
| POST       | /auth/logout          | Revoke session/token     |
| POST       | /auth/forgot-password | Start recovery           |
| GET        | /users                | List users               |
| POST       | /users                | Create/invite user       |
| GET        | /users/{id}           | Get user                 |
| PATCH      | /users/{id}           | Update user              |
| DELETE     | /users/{id}           | Deactivate user          |
| GET        | /roles                | List roles               |
| POST       | /roles                | Create role              |
| PATCH      | /roles/{id}           | Update role              |
| GET        | /permissions          | Permission catalogue     |

## Organization & Locations

| **Method** | **Endpoint**                | **Purpose**           |
|------------|-----------------------------|-----------------------|
| GET        | /organization               | Get current tenant    |
| PATCH      | /organization               | Update tenant         |
| GET        | /locations/tree             | Get hierarchical tree |
| GET        | /locations                  | List/search nodes     |
| POST       | /locations                  | Create node           |
| GET        | /locations/{id}             | Get node              |
| PATCH      | /locations/{id}             | Update node           |
| POST       | /locations/{id}/move        | Move node             |
| DELETE     | /locations/{id}             | Archive node          |
| GET        | /locations/{id}/children    | Direct children       |
| GET        | /locations/{id}/descendants | Descendant scope      |
| POST       | /locations/{id}/tags        | Assign tags           |

## Devices

| **Method** | **Endpoint**                   | **Purpose**                   |
|------------|--------------------------------|-------------------------------|
| GET        | /devices                       | List/filter devices           |
| POST       | /devices/registration-requests | Register/request registration |
| GET        | /devices/{id}                  | Device detail                 |
| PATCH      | /devices/{id}                  | Update device                 |
| POST       | /devices/{id}/approve          | Approve device                |
| POST       | /devices/{id}/decommission     | Decommission                  |
| POST       | /devices/{id}/assign-location  | Assign location               |
| GET        | /devices/{id}/capabilities     | Get capabilities              |
| POST       | /devices/{id}/commands         | Queue command                 |
| GET        | /devices/{id}/events           | Device events                 |
| GET        | /device-groups                 | List groups                   |
| POST       | /device-groups                 | Create group                  |
| PATCH      | /device-groups/{id}            | Update group                  |
| DELETE     | /device-groups/{id}            | Delete group                  |
| POST       | /device-groups/{id}/members    | Bulk assign devices           |

## Content / Assets

| **Method** | **Endpoint**                  | **Purpose**             |
|------------|-------------------------------|-------------------------|
| GET        | /assets                       | List/search assets      |
| POST       | /assets/uploads               | Create upload session   |
| POST       | /assets/uploads/{id}/complete | Complete upload         |
| GET        | /assets/{id}                  | Get asset metadata      |
| PATCH      | /assets/{id}                  | Update metadata         |
| GET        | /assets/{id}/download-url     | Get signed download URL |
| GET        | /assets/{id}/versions         | List versions           |
| POST       | /assets/{id}/versions         | Create new version      |
| POST       | /assets/{id}/archive          | Archive asset           |
| POST       | /assets/{id}/restore          | Restore asset           |
| GET        | /folders                      | List folders            |
| POST       | /folders                      | Create folder           |
| PATCH      | /folders/{id}                 | Update folder           |
| DELETE     | /folders/{id}                 | Archive folder          |

## Layouts / Templates

| **Method** | **Endpoint**           | **Purpose**            |
|------------|------------------------|------------------------|
| GET        | /layouts               | List layouts           |
| POST       | /layouts               | Create layout          |
| GET        | /layouts/{id}          | Get layout             |
| PATCH      | /layouts/{id}          | Update layout          |
| POST       | /layouts/{id}/versions | Create version         |
| GET        | /layouts/{id}/versions | List versions          |
| POST       | /layouts/{id}/publish  | Publish layout version |
| POST       | /layouts/{id}/preview  | Generate preview       |
| GET        | /templates             | List templates         |
| POST       | /templates             | Create template        |
| POST       | /templates/{id}/clone  | Clone template         |

## Playlists

| **Method** | **Endpoint**                    | **Purpose**              |
|------------|---------------------------------|--------------------------|
| GET        | /playlists                      | List playlists           |
| POST       | /playlists                      | Create playlist          |
| GET        | /playlists/{id}                 | Get playlist             |
| PATCH      | /playlists/{id}                 | Update playlist          |
| PUT        | /playlists/{id}/items           | Replace ordered item set |
| POST       | /playlists/{id}/items           | Add item                 |
| PATCH      | /playlists/{id}/items/{item_id} | Update item              |
| DELETE     | /playlists/{id}/items/{item_id} | Remove item              |
| POST       | /playlists/{id}/publish         | Publish playlist version |

## Campaigns / Scheduling

| **Method** | **Endpoint**                      | **Purpose**            |
|------------|-----------------------------------|------------------------|
| GET        | /campaigns                        | List campaigns         |
| POST       | /campaigns                        | Create campaign        |
| GET        | /campaigns/{id}                   | Get campaign           |
| PATCH      | /campaigns/{id}                   | Update campaign        |
| POST       | /campaigns/{id}/targets           | Set targets            |
| GET        | /campaigns/{id}/effective-targets | Resolve target devices |
| POST       | /campaigns/{id}/submit-approval   | Submit approval        |
| POST       | /campaigns/{id}/approve           | Approve                |
| POST       | /campaigns/{id}/reject            | Reject                 |
| POST       | /campaigns/{id}/publish           | Publish campaign       |
| GET        | /schedules                        | List schedules         |
| POST       | /schedules                        | Create schedule        |
| PATCH      | /schedules/{id}                   | Update schedule        |
| DELETE     | /schedules/{id}                   | Delete schedule        |
| GET        | /calendar                         | Get calendar view      |

## Publishing / Monitoring

| **Method** | **Endpoint**              | **Purpose**                  |
|------------|---------------------------|------------------------------|
| GET        | /deployments              | List deployments             |
| GET        | /deployments/{id}         | Deployment detail            |
| POST       | /deployments/{id}/retry   | Retry failed targets         |
| POST       | /deployments/{id}/cancel  | Cancel deployment            |
| GET        | /deployments/{id}/devices | Per-device deployment status |
| GET        | /monitoring/summary       | Health summary               |
| GET        | /monitoring/devices       | Device health feed           |
| GET        | /reports/deployments      | Deployment report            |
| GET        | /reports/playback         | Playback report              |
| GET        | /reports/locations        | Location report              |
| GET        | /audit-logs               | Audit search                 |
| GET        | /notifications            | Notification inbox           |

## Player Gateway

| **Method** | **Endpoint**                              | **Purpose**                          |
|------------|-------------------------------------------|--------------------------------------|
| POST       | /player/register                          | Native player registration/bootstrap |
| POST       | /player/token                             | Issue player token                   |
| GET        | /player/{device_id}/manifest              | Get effective content manifest       |
| GET        | /player/{device_id}/assets/{asset_id}/url | Get asset delivery URL               |
| POST       | /player/{device_id}/heartbeat             | Heartbeat/health update              |
| POST       | /player/{device_id}/events                | Playback/device events               |
| GET        | /player/{device_id}/commands              | Poll queued commands                 |
| POST       | /player/{device_id}/commands/{id}/ack     | Acknowledge command                  |
| POST       | /player/{device_id}/capabilities          | Register/update capabilities         |
| POST       | /player/{device_id}/deployments/{id}/ack  | Acknowledge deployment               |

## Integration

| **Method** | **Endpoint**          | **Purpose**                |
|------------|-----------------------|----------------------------|
| GET        | /api-keys             | List keys                  |
| POST       | /api-keys             | Create key                 |
| POST       | /api-keys/{id}/rotate | Rotate key                 |
| DELETE     | /api-keys/{id}        | Revoke key                 |
| GET        | /webhooks             | List webhook subscriptions |
| POST       | /webhooks             | Create webhook             |
| PATCH      | /webhooks/{id}        | Update webhook             |
| DELETE     | /webhooks/{id}        | Delete webhook             |

# 9. API Payload Contracts - Key Objects

## 9.1 Player manifest

> {  
> "device_id": "...",  
> "manifest_version": 42,  
> "generated_at": "2026-08-29T10:00:00Z",  
> "timezone": "Asia/Kolkata",  
> "active_campaign": "...",  
> "layout": {"id":"...","version":3,"zones":\[...\]},  
> "playlist": {"id":"...","version":8,"items":\[...\]},  
> "fallback": {"playlist_id":"..."},  
> "assets": \[{"id":"...","sha256":"...","size":12345,"url":"..."}\]  
> }

## 9.2 Device heartbeat

> {  
> "timestamp":"2026-08-29T10:02:00Z",  
> "player_version":"1.0.0",  
> "os_version":"...",  
> "status":"online",  
> "storage":{"used_percent":62},  
> "network":{"type":"wifi","quality":"good"},  
> "current":{"campaign_id":"...","playlist_id":"...","asset_id":"..."}  
> }

## 9.3 Campaign target definition

> {  
> "locations":\[{"location_id":"...","include_descendants":true}\],  
> "devices":\[\],  
> "device_groups":\["..."\],  
> "tags":\[{"key":"store_type","value":"premium"}\],  
> "exclusions":{"devices":\["..."\]}  
> }

# 10. Database ER Model

PostgreSQL is recommended as the source of truth. Media binaries belong
in object storage; the database stores metadata, versions,
relationships, deployment state and audit information.

> ORGANIZATION 1---N USERS  
> ORGANIZATION 1---N LOCATIONS  
> LOCATION 1---N LOCATIONS (self-referencing tree)  
> LOCATION 1---N DEVICES  
> ORGANIZATION 1---N ASSETS  
> ASSET 1---N ASSET_VERSIONS  
> ASSET N---N TAGS  
> LAYOUT 1---N LAYOUT_VERSIONS  
> LAYOUT_VERSION 1---N LAYOUT_ZONES  
> ZONE N---1 ASSET / WIDGET / TEXT CONFIG  
> PLAYLIST 1---N PLAYLIST_ITEMS  
> PLAYLIST_ITEM N---1 ASSET / LAYOUT  
> CAMPAIGN N---1 LAYOUT  
> CAMPAIGN N---1 PLAYLIST  
> CAMPAIGN 1---N SCHEDULES  
> CAMPAIGN 1---N CAMPAIGN_TARGETS  
> DEPLOYMENT N---1 CAMPAIGN  
> DEPLOYMENT 1---N DEPLOYMENT_DEVICES  
> DEVICE 1---N HEARTBEATS  
> DEVICE 1---N DEVICE_EVENTS  
> DEVICE 1---N PLAYBACK_EVENTS  
> ORGANIZATION 1---N AUDIT_LOGS

## 10.1 Core entity catalogue

| **Entity**          | **Key attributes**                                                                                                    |
|---------------------|-----------------------------------------------------------------------------------------------------------------------|
| organizations       | id, name, code, status, timezone, locale, branding, quotas                                                            |
| users               | id, organization_id, email, name, status, auth fields, last_login_at                                                  |
| roles               | id, organization_id nullable, name, scope                                                                             |
| permissions         | id, code, description                                                                                                 |
| user_roles          | user_id, role_id                                                                                                      |
| role_permissions    | role_id, permission_id                                                                                                |
| location_types      | id, organization_id, code, name                                                                                       |
| locations           | id, organization_id, parent_id, type_id, name, code, address, lat, lng, timezone, status                              |
| tags                | id, organization_id, key, value                                                                                       |
| location_tags       | location_id, tag_id                                                                                                   |
| devices             | id, organization_id, location_id, group_id, name, manufacturer, model, platform, serial_no, status, last_heartbeat_at |
| device_capabilities | id, device_id, capability_code, supported, value_json                                                                 |
| device_groups       | id, organization_id, name, description                                                                                |
| device_tags         | device_id, tag_id                                                                                                     |
| folders             | id, organization_id, parent_id, name                                                                                  |
| assets              | id, organization_id, folder_id, type, name, status, checksum, current_version_id                                      |
| asset_versions      | id, asset_id, version_no, object_key, size_bytes, mime_type, width, height, duration_ms, processing_status            |
| layouts             | id, organization_id, name, status, current_version_id                                                                 |
| layout_versions     | id, layout_id, version_no, canvas_json, published_at                                                                  |
| layout_zones        | id, layout_version_id, zone_key, zone_json                                                                            |
| templates           | id, organization_id, layout_id, name, metadata_json                                                                   |
| playlists           | id, organization_id, name, status, fallback_playlist_id                                                               |
| playlist_items      | id, playlist_id, position, asset_id, layout_id, duration_ms, transition_json                                          |
| campaigns           | id, organization_id, name, status, priority, playlist_id, layout_id                                                   |
| campaign_targets    | id, campaign_id, target_type, target_id, include_descendants, conditions_json                                         |
| schedules           | id, campaign_id, start_at, end_at, recurrence_json, timezone, priority                                                |
| deployments         | id, organization_id, campaign_id, version, status, created_by, started_at, completed_at                               |
| deployment_devices  | id, deployment_id, device_id, status, attempts, last_error, acknowledged_at                                           |
| device_heartbeats   | id, device_id, observed_at, payload_json                                                                              |
| device_events       | id, device_id, event_type, event_at, payload_json                                                                     |
| playback_events     | id, device_id, campaign_id, playlist_id, asset_id, started_at, ended_at, result                                       |
| notifications       | id, organization_id, user_id, type, severity, read_at, payload_json                                                   |
| audit_logs          | id, organization_id, user_id, action, entity_type, entity_id, before_json, after_json, created_at                     |
| api_keys            | id, organization_id, name, key_hash, expires_at, revoked_at                                                           |
| webhooks            | id, organization_id, event_type, endpoint, secret_ref, status                                                         |

# 11. Data Model Rules and Indexing

- Every tenant-owned table MUST carry organization_id directly or
  through a provable parent relationship; service-layer authorization
  must prevent cross-tenant access.

- Use UUID/ULID-style globally unique primary identifiers.

- Timestamps MUST be stored in UTC; rendering/scheduling uses the device
  or location timezone.

- Never store large media binaries in PostgreSQL.

- Use soft-delete/status transitions for business entities that can be
  referenced historically.

- Use immutable version rows for published asset/layout/playlist
  versions.

- All deployment and player event writes should be idempotent where the
  client can retry.

## 11.1 Critical indexes

| **Table**          | **Index / constraint**                                                                      |
|--------------------|---------------------------------------------------------------------------------------------|
| locations          | organization_id, parent_id; unique(organization_id, parent_id, code)                        |
| devices            | organization_id, status; location_id; last_heartbeat_at; unique(organization_id, serial_no) |
| assets             | organization_id, type, status; checksum; folder_id                                          |
| asset_versions     | asset_id, version_no unique                                                                 |
| campaign_targets   | campaign_id, target_type, target_id                                                         |
| schedules          | campaign_id, start_at, end_at                                                               |
| deployments        | organization_id, created_at; status                                                         |
| deployment_devices | deployment_id, device_id unique                                                             |
| playback_events    | device_id, started_at; campaign_id, started_at                                              |
| audit_logs         | organization_id, created_at; entity_type, entity_id                                         |

# 12. Location Resolution and Targeting Logic

Campaign targeting must resolve to a deterministic device set at publish
time, while retaining the original logical target definition for future
audits. The resulting deployment snapshot should not silently change
after publication.

> Campaign Target  
> \|  
> +-- Device IDs  
> +-- Device Groups  
> +-- Location IDs (+ descendants flag)  
> +-- Tags / conditions  
> +-- Explicit exclusions  
> \|  
> Resolve -\> Deduplicate -\> Apply exclusions -\> Validate device
> status  
> \|  
> Deployment Target Snapshot -\> Queue delivery

## 12.1 Inheritance rule

Child locations inherit parent campaigns only when the campaign target
includes descendants. An explicit child-level campaign can override the
inherited campaign based on priority and schedule rules. Exclusions
always win over inclusion for the same deployment evaluation.

# 13. Scheduling and Playback Resolution

At runtime, the future native player should receive a deterministic
schedule/manifest rather than requiring complex business logic on the
TV. The cloud resolves campaign priority and effective schedules as far
as practical; the player handles local time windows and cache
availability.

> Effective Content = highest-priority active campaign  
> -\> within matching schedule window  
> -\> after exclusions  
> -\> with valid content/layout/playlist versions  
> -\> otherwise fallback playlist  
> -\> otherwise emergency/default fallback

# 14. Publishing / Deployment State Machine

> DRAFT -\> READY -\> QUEUED -\> PUBLISHING -\> PUBLISHED  
> \| \|  
> \| +-\> PARTIAL  
> \| +-\> FAILED -\> RETRY  
> +-\> CANCELLED

| **State**  | **Meaning**                                               |
|------------|-----------------------------------------------------------|
| READY      | All references validated; publishable                     |
| QUEUED     | Deployment job accepted                                   |
| PUBLISHING | Worker distributing manifest/assets                       |
| PARTIAL    | Some targets succeeded while others remain failed/pending |
| PUBLISHED  | Required publication threshold achieved                   |
| FAILED     | No further automatic progress                             |
| CANCELLED  | Stopped by operator                                       |

# 15. Non-Functional Requirements

| **ID**  | **Area**          | **Requirement**                                                                                                                       |
|---------|-------------------|---------------------------------------------------------------------------------------------------------------------------------------|
| NFR-001 | Availability      | Target \>=99.9% for cloud control plane excluding planned maintenance.                                                                |
| NFR-002 | Scalability       | Data model and queue architecture should support 1K -\> 10K -\> 100K devices without redesigning core entities.                       |
| NFR-003 | API latency       | Typical metadata CRUD APIs target p95 \<=300 ms under normal load; long operations must be asynchronous.                              |
| NFR-004 | Security          | TLS, secure secrets, hashed credentials, tenant isolation, RBAC, audit logging and signed object URLs.                                |
| NFR-005 | Reliability       | Publishing retries transient failures with bounded backoff; duplicate requests are safe with idempotency keys.                        |
| NFR-006 | Offline playback  | Future players cache the last valid manifest and required assets locally.                                                             |
| NFR-007 | Observability     | Structured logs, request IDs, metrics, health checks, worker queue metrics and deployment tracing.                                    |
| NFR-008 | Backup            | Managed PostgreSQL backups plus point-in-time recovery; object storage versioning/lifecycle policy recommended.                       |
| NFR-009 | Auditability      | Business-critical actions are traceable to user/service account and timestamp.                                                        |
| NFR-010 | Accessibility     | Admin portal should target WCAG 2.1 AA-compatible patterns for core workflows.                                                        |
| NFR-011 | Browser support   | Current Chromium, Firefox and Safari enterprise versions.                                                                             |
| NFR-012 | Time              | UTC persistence; explicit IANA timezone identifiers at organization/location/device level.                                            |
| NFR-013 | Retention         | Configurable retention for heartbeat, device event and playback telemetry.                                                            |
| NFR-014 | Disaster recovery | Document RPO/RTO targets before production; recommended initial baseline RPO \<=15 min, RTO \<=2 hr subject to infrastructure budget. |

# 16. Security Requirements

- Tenant isolation is mandatory at repository/service level, not only at
  UI level.

- Passwords, refresh tokens and API secrets are never stored in
  plaintext.

- Object storage downloads use short-lived signed URLs or equivalent
  access control.

- Device credentials are independently revocable.

- Publishing and remote-control APIs require explicit permissions.

- Upload validation must enforce MIME/size policies and reject
  unsupported executable content.

- Audit events must be generated server-side, not trusted from frontend
  input.

- Rate-limit login, player registration/bootstrap, upload creation and
  event ingestion endpoints.

- Use OWASP-aligned input validation, output encoding and secure headers
  for web UI/API.

# 17. Integration and Infrastructure Architecture

> React + TypeScript Admin Portal  
> \|  
> HTTPS REST / WebSocket  
> \|  
> FastAPI Application  
> \|  
> +-------+---------+-----------------+  
> \| \| \|  
> PostgreSQL Redis Object Storage  
> \| \| \|  
> Metadata Queue/Cache Media  
> \|  
> Workers  
> \|  
> Publishing / Processing  
> \|  
> CDN / Player API  
> \|  
> LG / Samsung / Android / Windows

## 17.1 Recommended logical services in Phase-1

- API application: Auth, tenant, locations, devices, content, layouts,
  playlists, campaigns, schedules, deployments, audit.

- Worker process: media processing, thumbnail generation, deployment
  fan-out, notification jobs.

- Scheduler: periodic jobs for offline detection, expiry, campaign
  activation and cleanup.

- Redis: queue broker/cache/short-lived locks.

- PostgreSQL: transactional source of truth.

- S3-compatible object storage + CDN: media delivery.

# 18. Phase-1 Development Scope

Phase-1 is intentionally limited to the minimum complete cloud product
that can be tested with a simulated player. The objective is not to
build the native TV client; it is to establish the production-grade
cloud control plane and player contract.

| **ID** | **Workstream**          | **Deliverables**                                                                                       |
|--------|-------------------------|--------------------------------------------------------------------------------------------------------|
| P1-01  | Foundation              | Project skeleton, environments, Docker, CI/CD, DB migrations, config/secrets, logging, API conventions |
| P1-02  | Authentication/RBAC     | Login, token lifecycle, users, roles, permissions, tenant isolation                                    |
| P1-03  | Organization/Locations  | Tenant settings, unlimited location tree, tags, subtree resolution                                     |
| P1-04  | Devices                 | Device registration/approval, location assignment, groups, capabilities, status                        |
| P1-05  | Content CMS             | Upload session, asset metadata, folders/tags, thumbnail, versions, lifecycle                           |
| P1-06  | Layout Engine           | Layout CRUD, versions, generic zones, JSON schema, preview                                             |
| P1-07  | Playlist                | Playlist CRUD, ordered items, duration/transition, fallback                                            |
| P1-08  | Campaign/Schedule       | Campaign CRUD, target resolution, priority, schedule windows, recurrence foundation                    |
| P1-09  | Publishing              | Deployment creation, target snapshot, queue, per-device status, retries                                |
| P1-10  | Player Gateway          | Registration, token, manifest, asset URL, heartbeat, events, ACKs                                      |
| P1-11  | Monitoring/Audit        | Dashboard, deployment monitoring, device health, audit logs, notifications foundation                  |
| P1-12  | QA/Performance/Security | Unit/integration/API tests, seed data, permission tests, load smoke, security checks, UAT support      |

## 18.1 Phase-1 screens

- SCR-01 Login / SCR-02 Dashboard

- SCR-04 Users / SCR-05 Roles

- SCR-06 Location Tree / SCR-07 Location Details

- SCR-08 Device List / SCR-09 Device Details / SCR-10 Device Groups

- SCR-11 Content Library / SCR-12 Upload / SCR-13 Content Details

- SCR-15 Layout List / SCR-16 Screen Designer

- SCR-17 Playlist / SCR-18 Playlist Editor

- SCR-19 Campaigns / SCR-20 Campaign Editor / SCR-21 Schedule Calendar

- SCR-22 Publishing / SCR-23 Monitoring / SCR-24 Reports / SCR-25 Audit
  & Settings

# 19. Phase-1 Exclusions and Deferred Backlog

| **Deferred feature**                            | **Why deferred**                                                                           |
|-------------------------------------------------|--------------------------------------------------------------------------------------------|
| Native LG/Samsung clients                       | Cloud APIs must stabilize first; implement adapters after player contract testing.         |
| Advanced widget marketplace                     | Requires widget SDK/runtime and security sandbox decisions.                                |
| AI/NLP content generation                       | Business value can be added after core content/campaign workflows stabilize.               |
| Ad billing / revenue                            | Separate financial and contract model.                                                     |
| Video wall synchronization                      | Requires precise player timing and specialized hardware capabilities.                      |
| Full remote TV power control across all vendors | Capability varies by manufacturer/model; expose capability-driven command framework first. |
| Complex workflow designer                       | Start with one approval path; generalize later.                                            |
| Large-scale analytics warehouse                 | Keep operational events in PostgreSQL initially; extract to warehouse when scale requires. |

# 20. QA Strategy and Acceptance Testing

## 20.1 Test layers

- Unit tests for permission, targeting, scheduling, state transitions
  and serializers.

- Integration tests for PostgreSQL, object storage, queues and player
  APIs.

- API contract tests for all player gateway endpoints.

- Frontend component/page tests for critical workflows.

- End-to-end test: upload -\> process -\> layout -\> playlist -\>
  campaign -\> schedule -\> publish -\> simulated player sync -\>
  heartbeat -\> playback event.

- Security tests for tenant isolation and authorization bypass attempts.

- Load smoke test for concurrent device heartbeats and deployment
  fan-out.

## 20.2 Golden end-to-end scenario

> 1\. Create Organization  
> 2. Create hierarchy: Country \> State \> City \> Store \> Floor  
> 3. Register 10 simulated devices across stores  
> 4. Upload image + MP4 + text configuration  
> 5. Build 3-zone layout  
> 6. Create playlist  
> 7. Create campaign targeted at City with descendants=true  
> 8. Schedule 09:00-18:00 Asia/Kolkata  
> 9. Publish campaign  
> 10. Verify deployment fan-out and per-device acknowledgement  
> 11. Simulated player fetches manifest and signed asset URLs  
> 12. Player sends heartbeat and playback event  
> 13. Dashboard reflects online state and deployment success  
> 14. Audit log records creation, publishing and device acknowledgement

# 21. Definition of Done for Phase-1

- All Phase-1 APIs documented and tested.

- All critical pages are permission-aware and tenant-scoped.

- Database migrations are repeatable and seeded with demo data.

- Upload and media processing states are observable.

- Deployment can be retried without duplicate device assignments.

- Simulated player can complete registration -\> manifest sync -\> asset
  download -\> heartbeat -\> playback event.

- Audit records exist for authentication-sensitive and publish-sensitive
  actions.

- Automated CI runs lint, tests and migration validation.

- Production deployment runbook and rollback procedure are written.

# 22. Recommended Repository Structure

> backend/  
> app/  
> api/ \# REST routers  
> core/ \# config, security, logging  
> models/ \# SQLAlchemy models  
> schemas/ \# Pydantic DTOs  
> services/ \# business logic  
> repositories/ \# DB access  
> workers/ \# async/background jobs  
> integrations/ \# storage, email, webhooks  
> player/ \# player gateway contracts  
> migrations/  
> tests/  
> frontend/  
> src/  
> modules/  
> auth/ organization/ locations/ devices/ content/  
> designer/ playlists/ campaigns/ schedules/  
> deployments/ monitoring/ reports/ audit/  
> components/  
> services/ \# API clients  
> routes/  
> infra/  
> docker/  
> ci/  
> terraform-or-ansible/

# 23. Implementation Decisions to Freeze Before Coding

| **Decision**     | **Recommended baseline**                           |
|------------------|----------------------------------------------------|
| Primary DB       | PostgreSQL                                         |
| Backend          | FastAPI + Python                                   |
| Frontend         | React + TypeScript + Vite                          |
| Cache/queue      | Redis + worker framework                           |
| Object storage   | S3-compatible                                      |
| CDN              | CloudFront or equivalent                           |
| Media processing | FFmpeg worker pipeline                             |
| Auth             | JWT/OIDC-ready with RBAC                           |
| Identifiers      | UUID/ULID                                          |
| API versioning   | /api/v1                                            |
| Player protocol  | HTTPS REST + optional WebSocket/MQTT event channel |
| Layout format    | Versioned JSON schema with generic zones           |
| Time storage     | UTC + IANA timezone                                |
| Deployment model | Asynchronous queued fan-out                        |
| Observability    | Structured logs + metrics + health endpoints       |

# 24. Phase-1 Delivery Sequence

> Sprint 1  
> Foundation -\> Auth/RBAC -\> Organization -\> DB baseline  
>   
> Sprint 2  
> Location tree -\> Device registry -\> Groups/capabilities  
>   
> Sprint 3  
> Content library -\> Upload -\> Media processing -\> Versions  
>   
> Sprint 4  
> Layout JSON -\> Designer -\> Templates -\> Playlist  
>   
> Sprint 5  
> Campaign -\> Target resolution -\> Scheduling -\> Conflict
> validation  
>   
> Sprint 6  
> Publishing -\> Worker fan-out -\> Player gateway -\> Simulated
> player  
>   
> Sprint 7  
> Monitoring -\> Audit -\> Notifications -\> Reports foundation  
>   
> Sprint 8  
> Hardening -\> Security -\> Performance -\> UAT -\> Release

# 25. Final Product Boundary

The Phase-1 release is successful when a business user can log in,
create an unlimited location hierarchy, register a simulated commercial
display, upload media, create a custom multi-zone screen, create a
playlist, schedule a targeted campaign, publish it asynchronously, see
per-device deployment status, and have a simulated player download and
acknowledge the resulting manifest. This boundary provides the stable
cloud foundation needed for later LG webOS and Samsung Tizen native
client development.
