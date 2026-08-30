# Business Requirements Document (BRD)

## Enterprise Digital Signage Cloud Platform

### 1. Document Purpose

The objective is to develop a cloud-based, enterprise-grade **Digital Signage Management Platform** that allows organizations to centrally create, upload, organize, schedule, publish, monitor and manage digital content across commercial display devices such as:

* LG webOS Signage
* Samsung Tizen / commercial displays
* Android-based signage players
* Windows signage players
* Future supported TV/display platforms

The platform will provide a common cloud layer while platform-specific native applications/players will handle actual content playback on devices.

### 2. Product Vision

The platform should follow this model:

```text
                         DIGITAL SIGNAGE CLOUD
                                  │
        ┌─────────────────────────┼─────────────────────────┐
        │                         │                         │
   CONTENT CMS              EXPERIENCE CMS            DEVICE CMS
        │                         │                         │
 Images / Video             Layout Designer          Device Registry
 Text / HTML                Templates                Monitoring
 Documents                  Widgets                  Configuration
 URLs / Streams             Split Screens            Health
 Fonts / Audio              Playlists                Commands
        │                         │                         │
        └─────────────────────────┼─────────────────────────┘
                                  │
                           Publishing Engine
                                  │
                         Scheduling Engine
                                  │
                         Delivery / Sync API
                                  │
               ┌──────────────────┼─────────────────┐
               │                  │                 │
             LG                 Samsung          Android/
           webOS                Tizen             Windows
          Player                Player             Player
```

The cloud should **not be tightly coupled to LG or Samsung**.

That is one of the most important architectural decisions.

The backend should expose a **device-independent Digital Signage API**, while native clients implement a platform adapter.

LG's own cloud architecture similarly separates cloud management from the player/device layer, supporting LG webOS displays and other platforms through a player. ([LG Electronics][1])

---

# 3. Business Objectives

The system should enable an enterprise customer to:

1. Manage thousands of displays from one cloud platform.
2. Organize displays using unlimited hierarchical locations.
3. Upload and manage different media types.
4. Design complex screen compositions.
5. Create reusable playlists and templates.
6. Schedule different content at different times.
7. Publish content to individual devices, groups or locations.
8. Manage displays remotely.
9. Monitor device health and playback status.
10. Track what content actually played.
11. Support multiple organizations/tenants.
12. Support multiple administrators and permissions.
13. Support multiple display manufacturers.
14. Operate with intermittent device connectivity.
15. Provide APIs for integration with external enterprise systems.

---

# 4. Target Users

## 4.1 Super Administrator

Platform owner.

Responsibilities:

* Tenant management
* Subscription/license management
* Platform configuration
* System monitoring
* Global settings
* User administration
* Audit logs

---

## 4.2 Organization Administrator

Customer-level administrator.

Responsibilities:

* Manage locations
* Manage users
* Manage devices
* Manage content
* Create playlists
* Create layouts
* Schedule content
* View reports

---

## 4.3 Content Manager

Responsible mainly for content.

Permissions:

* Upload assets
* Create content
* Edit content
* Create playlists
* Create templates
* Schedule campaigns

---

## 4.4 Location Manager

Responsible for a particular geographical/business hierarchy.

For example:

```text
India
 ├── West Bengal
 │    ├── Kolkata
 │    │    ├── Salt Lake Store
 │    │    ├── Park Street Store
 │    │    └── Airport Store
 │    └── Durgapur
 │
 └── Maharashtra
      ├── Mumbai
      └── Pune
```

The hierarchy should be **unlimited/deep**, rather than hard-coded as Location → Sub Location → Sub-sub Location.

Use a generic:

```text
Organization
   └── Location Node
         └── Location Node
               └── Location Node
                     └── ...
```

---

# 5. Core Functional Scope

## Module 1 — Organization / Tenant Management

The platform should support multi-tenancy.

```text
Platform
 ├── Organization A
 ├── Organization B
 └── Organization C
```

Each organization should have isolated:

* Users
* Locations
* Devices
* Content
* Playlists
* Layouts
* Schedules
* Reports
* Configurations

### Scope

* Create organization
* Edit organization
* Activate/deactivate
* Organization settings
* Branding
* Time zone
* Default language
* Subscription/license
* Storage quota
* Device quota

---

# 6. Module 2 — Unlimited Location Hierarchy

This should be a first-class concept in your platform.

### Example

```text
Company
 └── Country
      └── State
           └── City
                └── Area
                     └── Building
                          └── Floor
                               └── Department
                                    └── Room
                                         └── Display
```

But the system should not assume those levels.

Instead:

```text
Location Node
 ├── parent_id
 ├── name
 ├── type
 ├── code
 ├── address
 ├── latitude
 ├── longitude
 ├── timezone
 ├── metadata
 └── children
```

This enables practically unlimited hierarchy.

### Example location types

* Country
* Region
* State
* City
* Zone
* Store
* Mall
* Building
* Floor
* Department
* Room
* Outdoor
* Custom

---

# 7. Module 3 — Device Management

The device layer is one of the most important modules.

### Device registration

A device should contain:

```text
Device
 ├── Device ID
 ├── Device Name
 ├── Device Type
 ├── Manufacturer
 ├── Model
 ├── Platform
 ├── OS Version
 ├── Player Version
 ├── Serial Number
 ├── MAC Address
 ├── IP Address
 ├── Location
 ├── Orientation
 ├── Resolution
 ├── Screen Size
 ├── Timezone
 ├── Status
 ├── Last Heartbeat
 └── Last Content Sync
```

### Device platforms

Initially:

```text
LG webOS
Samsung Tizen
Android
Windows
```

Later:

```text
Linux
Raspberry Pi
BrightSign
ChromeOS
etc.
```

### Device lifecycle

```text
Discovered
   ↓
Pending Registration
   ↓
Registered
   ↓
Authorized
   ↓
Active
   ↓
Offline
   ↓
Decommissioned
```

---

# 8. Module 4 — Content Management System

This is the central CMS.

### Content types

Your content engine should not restrict itself to only image/video/text.

Recommended:

| Type         | Examples                       |
| ------------ | ------------------------------ |
| Image        | JPG, PNG, WebP, GIF            |
| Video        | MP4, WebM                      |
| Audio        | MP3, AAC                       |
| Text         | Headline, ticker, announcement |
| HTML         | Custom HTML5                   |
| Web Page     | URL                            |
| Streaming    | HLS, RTSP where supported      |
| Document     | PDF                            |
| Presentation | PPT/PPTX conversion workflow   |
| SVG          | Vector graphics                |
| Widget       | Weather, clock, RSS            |
| Data Feed    | JSON/API                       |
| Playlist     | Multiple assets                |
| Template     | Reusable design                |
| Live Feed    | External stream                |

LG's own SuperSign Cloud supports content creation, templates, widgets, external sources and web content, while Samsung MagicINFO Cloud emphasizes creation, scheduling and distribution. ([LG Electronics][2])

---

# 9. Asset Library

The Content Library should support:

```text
All Content
├── Images
├── Videos
├── Audio
├── Documents
├── HTML
├── Templates
├── Playlists
├── Widgets
└── Archived
```

### Asset metadata

```text
Asset
 ├── ID
 ├── Organization
 ├── File Name
 ├── MIME Type
 ├── Size
 ├── Duration
 ├── Resolution
 ├── Aspect Ratio
 ├── Thumbnail
 ├── Storage URL
 ├── Version
 ├── Tags
 ├── Folder
 ├── Created By
 ├── Created At
 └── Updated At
```

---

# 10. Content Versioning

Enterprise-grade CMS should not overwrite content blindly.

Example:

```text
Summer Sale
   v1
   v2
   v3
   v4
```

Capabilities:

* Version history
* Restore previous version
* Draft
* Approved
* Published
* Archived

---

# 11. Module 5 — Screen Designer / Layout Designer

This is one of your most important differentiators.

The user should be able to visually create:

```text
┌─────────────────────────────────┐
│             HEADER              │
├─────────────────┬───────────────┤
│                 │               │
│     VIDEO       │     IMAGE     │
│                 │               │
├─────────────────┼───────────────┤
│       TICKER / MARQUEE          │
└─────────────────────────────────┘
```

Or:

```text
┌────────────┬────────────┬────────────┐
│  Content 1 │  Content 2 │  Content 3 │
├────────────┼────────────┼────────────┤
│  Content 4 │  Content 5 │  Content 6 │
└────────────┴────────────┴────────────┘
```

The user should be able to:

* Drag
* Resize
* Move
* Duplicate
* Delete
* Lock
* Align
* Layer
* Crop
* Configure background
* Configure border
* Configure padding
* Configure animation
* Configure transition

---

# 12. Screen Zones

Do not model the UI as only predefined 1/2/3/4/6 layouts.

Create a generic **Zone** concept.

```text
Screen
 ├── Zone A
 ├── Zone B
 ├── Zone C
 ├── Zone D
 └── Zone E
```

Each zone has:

```text
x
y
width
height
z-index
rotation
background
border
content
```

Thus the system can support:

```text
1 Zone
2 Zones
3 Zones
4 Zones
6 Zones
8 Zones
Custom Grid
Free-form layout
```

This is much more scalable.

---

# 13. Marquee / Ticker Engine

You specifically mentioned marquee content.

Support:

* Horizontal ticker
* Vertical ticker
* News ticker
* Announcement bar
* Scrolling text
* Speed
* Direction
* Font
* Font size
* Font weight
* Text color
* Background
* Padding
* Animation
* Loop
* Start/end schedule

Example:

```text
┌───────────────────────────────────────┐
│ BREAKING NEWS → Today's announcement │
└───────────────────────────────────────┘
```

---

# 14. Widgets

For enterprise capability, add a widget framework.

Examples:

```text
Clock
Date
Weather
RSS
News
Stock
Temperature
Calendar
Countdown
QR Code
Social Media
Web Page
API Data
Custom HTML
```

The widget should have:

```text
Widget
 ├── type
 ├── configuration
 ├── refresh interval
 ├── data source
 ├── zone
 └── fallback content
```

---

# 15. Module 6 — Playlist Management

Content should be grouped into playlists.

Example:

```text
Morning Playlist
 ├── Company Video
 ├── Product Image
 ├── Announcement
 └── Weather

Afternoon Playlist
 ├── Advertisement
 ├── Product Video
 └── Promotion
```

Playlist properties:

* Sequence
* Duration
* Transition
* Loop
* Priority
* Content type
* Fallback
* Effective date
* Expiry date

---

# 16. Module 7 — Scheduling Engine

This should be a separate backend service.

Support:

### Date scheduling

```text
01 Sep → 30 Sep
```

### Time scheduling

```text
09:00 → 12:00
12:00 → 15:00
15:00 → 18:00
```

### Recurring

```text
Every Monday
Every weekday
Every weekend
Every month
```

### Event-based

```text
Festival
Promotion
Emergency
Campaign
```

### Priority

```text
Normal
High
Urgent
Emergency
```

Example:

```text
08:00–10:00 → Breakfast Content
10:00–13:00 → Advertisement
13:00–15:00 → Lunch Promotion
15:00–18:00 → Product Promotion
18:00–22:00 → Evening Content
```

---

# 17. Targeting Engine

This is critical for your hierarchical architecture.

Content should be publishable to:

```text
Organization
Location
Location subtree
Device Group
Device
Screen
Tag
```

Example:

```text
India
 └── West Bengal
      └── Kolkata
           ├── Store A
           ├── Store B
           └── Store C
```

Publish:

```text
Campaign → West Bengal
```

automatically applies to eligible child locations.

Or:

```text
Campaign → Store B
```

only applies to Store B.

---

# 18. Tags

Tags should complement hierarchy.

Example:

```text
Location:
Kolkata

Tags:
premium
mall
east-zone
large-screen
outdoor
promotion
```

Then content can use:

```text
Target:
tag = premium
AND
city = Kolkata
```

LG's enterprise signage products also use tag-based selective content distribution, which is a useful model for this capability. ([LG Electronics][2])

---

# 19. Publishing Engine

Publishing should not mean simply:

```text
Upload → Device
```

Instead:

```text
Content
   ↓
Layout
   ↓
Playlist
   ↓
Schedule
   ↓
Target
   ↓
Publishing Job
   ↓
Distribution
   ↓
Device Sync
   ↓
Playback
```

Each publish should create a deployment/version.

Example:

```text
Campaign #123
Version 7
Target: Kolkata Stores
Status: Publishing
        ↓
       92%
        ↓
Published
```

---

# 20. Offline Playback

This is mandatory for commercial signage.

The device should cache:

* Content
* Playlists
* Layout definitions
* Schedules
* Fonts
* Widgets
* Configuration

Then:

```text
Cloud
   ↓
Sync
   ↓
Local Storage
   ↓
Playback
```

If Internet goes down:

```text
Internet OFF
     ↓
Continue Playback
     ↓
Internet RESTORED
     ↓
Sync Changes
```

A cloud-only playback architecture would make the platform unreliable.

---

# 21. Device Communication

Use a combination of:

### HTTPS REST API

For:

* Registration
* Configuration
* Content metadata
* Sync
* Commands

### WebSocket / MQTT

For:

* Real-time commands
* Status
* Heartbeat
* Publish notification
* Remote control

Example:

```text
Cloud
  │
  ├── REST API
  │
  └── WebSocket / MQTT
            │
            ▼
       Native Player
```

---

# 22. Device Heartbeat

Every device should periodically report:

```text
device_id
timestamp
online_status
app_version
os_version
cpu
memory
storage
temperature
network
current_content
current_playlist
current_campaign
```

You can then create:

```text
Online
Offline
Warning
Critical
```

---

# 23. Device Monitoring

Dashboard:

```text
Total Displays       1,250
Online                1,184
Offline                  44
Warning                 17
Critical                 5
```

Device details:

```text
Device: Kolkata-Store-04

Status: Online
Last Heartbeat: 12 sec ago
Current Content: Summer Sale
Player Version: 2.4.1
Storage: 72%
CPU: 34%
Memory: 61%
Network: Good
```

LG's enterprise management products similarly expose real-time monitoring, map/list views, remote settings and operational status. ([LG Electronics][2])

---

# 24. Remote Device Control

Depending on what the native platform exposes:

```text
Power ON/OFF
Restart Player
Restart Device
Volume
Mute
Brightness
Screenshot
Sync
Refresh
Clear Cache
Update Playlist
Update Content
Update Application
```

Not every command will be supported on every manufacturer/model, so your backend should use a capability model:

```text
Device Capability

POWER_CONTROL       ✓
BRIGHTNESS_CONTROL  ✓
REMOTE_RESTART      ✓
SCREENSHOT          ✕
```

---

# 25. Device Groups

Support groups such as:

```text
All Kolkata Displays

Premium Stores

West Bengal Displays

Samsung Displays

Outdoor Displays

24x7 Displays
```

This enables bulk operations.

---

# 26. Screenshot / Proof of Display

Native clients should periodically capture:

```text
Current screen screenshot
```

and upload it.

This enables:

```text
Cloud expected:
Summer Sale

Device actual:
Summer Sale
```

This becomes the basis for **Proof of Display / Proof of Play**.

---

# 27. Proof of Play

Enterprise customers will eventually need this.

Record:

```text
Device
Content
Playlist
Campaign
Start Time
End Time
Duration
Playback Status
```

Example:

```text
Device: Store-001
Campaign: Diwali Campaign
Content: Diwali Video
Played: 14:00–14:01
Status: Completed
```

This can later power advertising reports.

---

# 28. Analytics & Reporting

Recommended reports:

### Device

* Online/offline
* Uptime
* Device failures
* Connectivity
* Storage
* Application version

### Content

* Play count
* Playback duration
* Devices reached
* Failed distribution

### Campaign

* Target devices
* Successful deployments
* Playback percentage
* Failed devices

### Location

```text
Country
 → State
 → City
 → Store
 → Device
```

Analytics should follow the hierarchy.

---

# 29. User & RBAC

Use granular permissions.

Example:

```text
Super Admin

Organization Admin

Content Manager

Campaign Manager

Location Manager

Device Manager

Viewer
```

Permissions:

```text
content.create
content.edit
content.delete
content.publish

device.view
device.manage
device.control

playlist.create
playlist.publish

schedule.create
schedule.publish

report.view
```

---

# 30. Approval Workflow

For enterprise organizations:

```text
Draft
  ↓
Submitted
  ↓
Approval Pending
  ↓
Approved
  ↓
Published
```

Optional:

```text
Rejected
Revision Required
Expired
Archived
```

This becomes important when marketing/content teams are separate from operations.

---

# 31. Audit Trail

Every sensitive action should be recorded.

Example:

```text
User
Action
Entity
Old Value
New Value
IP
Timestamp
Device
```

Example:

```text
Atanu
Updated Campaign #245
Schedule changed
10:00 → 11:00
29-Aug-2026 10:45
```

---

# 32. Notification System

Notifications:

```text
Device Offline
Device Recovered
Publishing Failed
Content Expired
Storage Low
Device Error
License Expiring
Campaign Ending
Approval Required
```

Channels:

```text
In-app
Email
Webhook
```

Later:

```text
SMS
WhatsApp
```

---

# 33. Search

Global search should search:

```text
Devices
Locations
Users
Content
Playlists
Campaigns
Layouts
Schedules
```

Support:

```text
Name
Code
Tag
Serial
Location
Status
Manufacturer
```

---

# 34. API / Integration Layer

This should be designed from Day 1.

External systems should be able to:

```text
Create Content
Create Location
Register Device
Publish Campaign
Create Schedule
Get Playback Data
Get Device Status
```

This enables future integrations with:

* ERP
* CRM
* POS
* Retail systems
* Advertisement systems
* IoT
* Weather APIs
* Social platforms

---

# 35. Multi-Manufacturer Architecture

This is extremely important for your planned LG/Samsung approach.

Do **not** create:

```text
LG backend
Samsung backend
```

Create:

```text
Digital Signage Core

       │
       ├── LG Adapter
       ├── Samsung Adapter
       ├── Android Adapter
       └── Windows Adapter
```

And define a common player contract:

```text
Player API

register()
authenticate()
heartbeat()
sync()
downloadContent()
getSchedule()
acknowledgeDeployment()
reportPlayback()
reportError()
getCapabilities()
executeCommand()
```

Then:

```text
LG Native App
       ↓
LG Player Adapter
       ↓
Common Player API

Samsung Native App
       ↓
Samsung Player Adapter
       ↓
Common Player API
```

That will save you enormous effort when you add manufacturers.

---

# 36. Recommended Backend Architecture

For an enterprise implementation, I would start with a **modular monolith**, not 20 microservices.

For example:

```text
                 API Gateway
                      │
               Application API
                      │
 ┌────────────────────┼──────────────────────┐
 │                    │                      │
Auth Module       Content Module       Device Module
 │                    │                      │
User/RBAC          Asset Manager        Device Registry
 │                 Playlist              Monitoring
 │                 Layout                Commands
 │                 Scheduling
 │
 ├────────────── Organization
 ├────────────── Location
 ├────────────── Publishing
 ├────────────── Notification
 ├────────────── Analytics
 └────────────── Audit
                      │
              Background Workers
                      │
       ┌──────────────┼───────────────┐
       │              │               │
     Redis          Queue          Scheduler
       │
       └──────────────┬───────────────
                      │
                Object Storage
                S3 Compatible
                      │
                PostgreSQL
```

Later, high-load components can be extracted.

---

# 37. Recommended Data Architecture

Core entities:

```text
organizations
users
roles
permissions

locations
location_types

devices
device_capabilities
device_groups
device_tags

assets
asset_versions
asset_tags
folders

layouts
layout_zones
templates
widgets

playlists
playlist_items

campaigns
campaign_targets

schedules
schedule_rules

deployments
deployment_devices
device_sync_status

playback_logs
proof_of_play

device_heartbeats
device_events

notifications
audit_logs

licenses
subscriptions
```

---

# 38. Storage Architecture

Do **not** store videos/images directly in PostgreSQL.

Use:

```text
PostgreSQL
     │
     └── Metadata

Object Storage
     │
     ├── Images
     ├── Videos
     ├── Documents
     ├── Audio
     ├── Thumbnails
     ├── Screenshots
     └── Application packages
```

For example:

```text
S3
 └── tenant/
      └── content/
           └── asset-id/
                ├── original
                ├── optimized
                └── thumbnail
```

Use CDN for global delivery.

---

# 39. Video Processing

Uploaded videos should go through:

```text
Upload
 ↓
Validation
 ↓
Virus/Malware Scan
 ↓
Metadata Extraction
 ↓
Transcoding
 ↓
Optimization
 ↓
Thumbnail Generation
 ↓
Ready
```

Potential outputs:

```text
1080p
720p
480p
```

depending on device requirements.

---

# 40. Security Requirements

Enterprise platform should include:

### Authentication

* OAuth/OIDC-ready
* JWT/session handling
* MFA-ready
* Password policies

### Authorization

* RBAC
* Scope-based permissions
* Tenant isolation

### API

* Rate limiting
* API keys
* Token rotation
* Request validation

### Storage

* Signed URLs
* Encryption at rest
* Encryption in transit

### Device

* Device credentials
* Certificate-ready authentication
* Device revocation

---

# 41. Content Security

Every uploaded asset should go through:

```text
Upload
 ↓
Validation
 ↓
Security Scan
 ↓
Processing
 ↓
Storage
```

Never allow arbitrary uploaded HTML/scripts to execute in the cloud application context.

Native player execution should also be sandboxed as far as the platform permits.

---

# 42. Frontend Application

Recommended primary navigation:

```text
Dashboard

Content
 ├── Media Library
 ├── Images
 ├── Videos
 ├── Documents
 ├── Templates
 └── Widgets

Design
 ├── Layouts
 ├── Templates
 └── Screen Designer

Playlists

Campaigns

Schedule

Devices
 ├── All Devices
 ├── Device Groups
 ├── Offline
 └── Monitoring

Locations

Reports

Users & Roles

Audit Logs

Settings
```

---

# 43. Dashboard

Example:

```text
Digital Signage Dashboard

Total Devices       2,485
Online               2,321
Offline                 98
Warning                 52
Critical                14

Active Campaigns        41
Scheduled Campaigns     86
Failed Deployments       7
Storage                 62%
```

Then:

```text
Device Health
Campaign Performance
Recent Activity
Location Status
Playback Summary
```

---

# 44. Screen Designer UI

The key UX should be:

```text
┌──────────────────────────────────────────────┐
│ Toolbar                                      │
├────────────┬─────────────────────┬───────────┤
│            │                     │           │
│ Components │     Screen Canvas   │ Properties│
│            │                     │           │
│ Image      │   ┌───────────────┐ │ Width     │
│ Video      │   │               │ │ Height    │
│ Text       │   │    Zone       │ │ Position  │
│ Ticker     │   │               │ │ Animation │
│ Clock      │   └───────────────┘ │           │
│ Widget     │                     │           │
├────────────┴─────────────────────┴───────────┤
│ Layers / Timeline                             │
└──────────────────────────────────────────────┘
```

This is much better than building six separate hard-coded screen templates.

---

# 45. Campaign Model

A campaign should combine:

```text
Campaign
 ├── Content
 ├── Layout
 ├── Playlist
 ├── Schedule
 ├── Target Audience
 ├── Locations
 ├── Devices
 ├── Tags
 ├── Priority
 ├── Approval
 └── Deployment
```

That gives you a very powerful model.

---

# 46. Important Enterprise Feature: Overrides

Suppose:

```text
West Bengal
   → Campaign A
```

but one store needs a special message.

Allow:

```text
West Bengal → Campaign A

Kolkata Store 4 → Campaign B
```

Hierarchy inheritance + overrides is essential.

---

# 47. Important Enterprise Feature: Fallback Content

Suppose:

```text
Campaign A
```

cannot be loaded.

The player should fall back to:

```text
Default Playlist
```

Therefore:

```text
Primary Content
      ↓
If unavailable
      ↓
Fallback Playlist
      ↓
Default Emergency Content
```

This protects the display from showing a blank screen.

---

# 48. Emergency / Priority Broadcasting

Add an emergency channel.

Example:

```text
NORMAL
   ↓
Emergency Message
   ↓
Immediately displayed
   ↓
Emergency Ends
   ↓
Return to Previous Schedule
```

Examples:

* Fire
* Emergency
* Security message
* Public announcement
* Critical company communication

---

# 49. Multi-Timezone

Each location/device should support timezone.

Example:

```text
New York → EST
London   → GMT
Dubai    → GST
Kolkata  → IST
```

Scheduling must execute according to the target timezone.

---

# 50. Localization

Support:

```text
English
Hindi
Bengali
Tamil
etc.
```

Content itself should also support Unicode properly.

---

# 51. Accessibility

Admin portal should follow common enterprise accessibility expectations:

* Keyboard navigation
* Proper labels
* Contrast
* Scalable UI
* Screen-reader compatible controls

---

# 52. Auditability

Every important event should have:

```text
Who
What
When
Where
Before
After
Result
```

Example:

```text
User:
Admin

Action:
Published Campaign

Target:
Kolkata → Store A/B/C

Time:
29-Aug-2026 11:32 IST

Result:
143 devices targeted
138 successful
5 pending
```

---

# 53. Non-Functional Requirements

The system should target:

### Availability

```text
99.9%+ platform availability
```

### Scalability

Architecture should support:

```text
1K devices
10K devices
100K+ devices
```

without redesigning the data model.

### Performance

Typical APIs:

```text
< 300 ms target
```

where practical for normal backend operations.

### Reliability

Content distribution must be:

```text
retryable
idempotent
resumable
observable
```

---

# 54. Important Backend Principle

Do not make content publishing synchronous.

Bad:

```text
POST /publish
    ↓
wait for 5,000 devices
```

Instead:

```text
POST /publish
      ↓
Create Deployment
      ↓
Queue Job
      ↓
Return Deployment ID
      ↓
Workers distribute
      ↓
Devices acknowledge
```

This will be essential at scale.

---

# 55. Deployment State Machine

Use something like:

```text
DRAFT
  ↓
READY
  ↓
QUEUED
  ↓
PUBLISHING
  ↓
PARTIAL
  ↓
PUBLISHED
```

Failure:

```text
FAILED
  ↓
RETRY
  ↓
PUBLISHING
```

---

# 56. Recommended MVP

Do **not** try to build everything on Day 1.

### Phase 1 — Core Platform

```text
Authentication
Organization
Users/RBAC
Location hierarchy
Device registration
Content upload
Asset library
Playlist
Basic layout
Scheduling
Publishing
Device heartbeat
Device sync
Dashboard
```

### Phase 2 — Enterprise

```text
Advanced layout editor
Templates
Tags
Device groups
Campaigns
Approval
Audit
Analytics
Proof of Play
Notifications
Remote control
```

### Phase 3 — Advanced

```text
Widgets
Dynamic API content
Emergency broadcasting
AI content generation
Advanced analytics
Advertisement management
Ad campaign management
Screen synchronization
Video wall
```

---

# 57. Recommended MVP Screens

I would start frontend development with approximately these screens:

```text
01 Login

02 Dashboard

03 Organization Settings

04 Location Management

05 Device Management

06 Device Details

07 Content Library

08 Upload Content

09 Content Details

10 Playlist Management

11 Layout Management

12 Screen Designer

13 Schedule Management

14 Campaign Management

15 Publishing / Deployment

16 Device Monitoring

17 Reports

18 Users & Roles

19 Notifications

20 Audit Logs

21 System Settings
```

---

# 58. Core Backend Services

Initially I recommend these logical modules:

```text
Auth
Organization
User/RBAC
Location
Content
Asset
Layout
Playlist
Schedule
Campaign
Publishing
Device
Device Communication
Monitoring
Analytics
Notification
Audit
Storage
```

Not necessarily separate microservices.

Start as one deployable application with clean module boundaries.

---

# 59. Technology Recommendation

Given the type of software you are building, a strong architecture could be:

### Frontend

```text
React
TypeScript
Vite
Tailwind
```

### Backend

```text
FastAPI
Python
SQLAlchemy
PostgreSQL
Redis
Celery
```

### Storage

```text
AWS S3
CloudFront
```

### Real-time

```text
WebSocket
MQTT
```

### Video processing

```text
FFmpeg
```

### Infrastructure

```text
Docker
AWS
Load Balancer
Object Storage
CDN
PostgreSQL
Redis
Worker nodes
```

This also leaves the backend clean for your future LG/Samsung native applications.

---

# 60. High-Level Final Architecture

The complete product should look like:

```text
                         CLOUD DIGITAL SIGNAGE PLATFORM

 ┌─────────────────────────────────────────────────────────────┐
 │                     WEB ADMIN PORTAL                        │
 │                                                             │
 │ Dashboard | Content | Designer | Playlist | Campaign       │
 │ Locations | Devices | Schedule | Reports | Users           │
 └──────────────────────────────┬──────────────────────────────┘
                                │
                         API / WebSocket
                                │
 ┌──────────────────────────────▼──────────────────────────────┐
 │                    CLOUD APPLICATION                         │
 │                                                             │
 │ Auth / RBAC                                                 │
 │ Organization / Tenant                                       │
 │ Location Hierarchy                                          │
 │ Content Management                                          │
 │ Layout / Zone Engine                                        │
 │ Playlist Engine                                             │
 │ Scheduling Engine                                           │
 │ Campaign Engine                                             │
 │ Publishing Engine                                           │
 │ Device Management                                           │
 │ Monitoring                                                  │
 │ Analytics                                                   │
 │ Notification                                                │
 │ Audit                                                       │
 └───────────────┬──────────────────────────────┬───────────────┘
                 │                              │
          ┌──────▼──────┐                ┌──────▼───────┐
          │ PostgreSQL  │                │ S3 + CDN     │
          │ Metadata    │                │ Media        │
          └─────────────┘                └──────────────┘

                                │
                       Distribution Layer
                                │
          ┌─────────────────────┼─────────────────────┐
          │                     │                     │
    ┌─────▼─────┐        ┌──────▼─────┐       ┌──────▼─────┐
    │ LG Player │        │ Samsung    │       │ Android /  │
    │ webOS     │        │ Tizen      │       │ Windows    │
    └───────────┘        └────────────┘       └────────────┘
          │                     │                     │
          └─────────────────────┼─────────────────────┘
                                │
                         Commercial TVs
```

## The most important design decision

Build the cloud around **five core abstractions**:

```text
LOCATION
   ↓
DEVICE
   ↓
CONTENT
   ↓
LAYOUT
   ↓
CAMPAIGN / SCHEDULE
```

Everything else should operate around those.

And particularly:

> **Do not build the backend specifically for LG or Samsung. Build a Digital Signage Cloud Standard of your own, and make LG/Samsung native clients adapters to that standard.**

That will let you develop the cloud backend/frontend **now**, while your native LG/Samsung clients can be developed later without having to redesign the core system.

The scope above also deliberately goes beyond basic CMS functionality: LG's current enterprise cloud offering includes remote display control, content creation, templates, widgets, scheduling and playback history, while Samsung MagicINFO Cloud similarly positions cloud content creation/distribution and endpoint management as core capabilities. ([LG Electronics][2])