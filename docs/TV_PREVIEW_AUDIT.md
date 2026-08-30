# TV Preview / Signage Simulator — Repository Audit

Date: 2026-08-30. Read-only audit performed before any implementation, per
the brief. Everything below is verified against the actual code, not assumed.

## 1. The central finding

**The backend already answers "what will this TV show".** It is
`app/services/manifest.py::build_manifest(db, device)` — the exact payload
a real player fetches and renders. It resolves, in order:

```
candidate campaigns (published + covered by a live deployment)
  → schedule window resolution        (scheduling.resolve_active_campaign)
  → decisioning rules  pin/boost/exclude, guardrailed to eligible windows
  → experiment arm     (stable per-device assignment)  … else
  → audience variant   (2E targeting)
  → effective layout + playlist
  → live data snapshots for data-bound zones
  → signed URLs for every referenced asset
```

So the simulator must **consume the manifest**, not re-derive any of it.
That single decision satisfies the brief's §51 (use real application data)
and §52 (zero business-logic duplication) outright.

### Manifest shape (verified)

```jsonc
{
  "device_id": "…", "manifest_version": 3, "generated_at": "…",
  "timezone": "Asia/Kolkata",
  "active_campaign": "…", "campaign_active_now": true,
  "campaign":  { "id", "name", "priority" },
  "variant":   { "id", "name" } | null,
  "experiment":{ "id", "arm" },            // additive
  "decision":  { "reasons": [...] },       // additive, auditable
  "schedules": [ … ],
  "layout":    { "id", "version", "canvas": { canvas:{width,height,background},
                                              zones:[ ZoneDef … ] } },
  "playlist":  { "id", "version", "loop": true,
                 "items": [ { position, item_type, duration_ms,
                              transition, asset_id|layout_id, … } ] },
  "fallback":  { …same shape… } | null,
  "assets":    [ { id, name, type, mime_type, sha256, size, url } ],
  "data":      { "<zone_key>": <transformed snapshot> },   // additive
  "sync":      { … },   // video-wall member
  "bundle" / "prefetch" / "bandwidth": { … }               // edge
}
```

Everything the simulator needs — geometry, order, per-item duration, loop
flag, transitions, playable signed URLs, live widget data — is already
there.

## 2. Existing capability

| Capability | Where | Reusable for preview? |
|---|---|---|
| Effective-content resolution | `manifest.build_manifest` | **Yes — this is the engine** |
| Schedule evaluation | `services/scheduling.resolve_active_campaign(campaigns, now, tz)` | Yes; already takes `now` + timezone as parameters |
| Decisioning dry-run | `POST /decision-rules/preview` (`services/decisioning.preview`) | Explains *why* a campaign won |
| Campaign target preview | `POST /campaigns/{id}/targets/preview` | Resolves a target set without saving |
| Device-group rule preview | `POST /device-groups/preview` | Not needed here |
| Layout canvas rendering | `DesignerPage.tsx` (zones positioned by `x/y/width/height * scale`) | Partially — it is an *editor* canvas, not a player |
| Signed media URL (admin) | `GET /assets/{id}/download-url` (`content.view`) | Yes — for design-time preview |
| Signed media URL (player) | inside the manifest `assets[].url` | Yes — for device preview |
| Playlist item durations | `playlist_items.duration_ms`, snapshotted into `items_json` | Yes |
| Per-item transitions | `playlist_items.transition_json` | Yes |
| Playlist loop flag | `playlists.loop_enabled` → `items_json.loop` | Yes |
| Per-playlist fallback | `playlists.fallback_playlist_id` → manifest `fallback` | Yes |
| Device geometry | `devices.screen_width/height`, `orientation`, `platform` | Yes |
| Device capabilities | `device_capabilities` table (`capability_code`, `supported`) | Yes — drives §22 warnings |
| Widget config schema | `widget_versions.config_schema_json` | Yes |
| Live data for zones | manifest `data` block (last-known-good, already transformed) | Yes — preview needs no external API |

## 3. Missing capability

| # | Gap | Proposed resolution |
|---|---|---|
| M1 | **No admin-facing manifest endpoint.** `GET /player/{id}/manifest` authenticates with a *device token*, so the portal cannot call it. | Add `GET /devices/{device_id}/preview-manifest`, permission `devices.view`, returning `build_manifest(...)`. Read-only, zero side effects. |
| M2 | **`build_manifest` hardcodes `now = datetime.now(UTC)`.** Schedule-aware preview ("what shows at 19:30 Saturday?") is impossible. | Thread an optional `at: datetime \| None` through `build_manifest` and into `resolve_active_campaign`/decisioning, defaulting to now. Keeps *all* schedule rules in one place — no frontend duplication. |
| M3 | **No batch asset-URL resolution.** Design-time preview of an N-item playlist needs N calls to `/assets/{id}/download-url`. | Acceptable for v1 (N is small and calls are parallel). Documented as a candidate batch endpoint if it becomes slow. |
| M4 | **Unsaved Screen Designer state has no manifest** (it is not persisted, so no layout version exists). | Design-time preview renders the in-memory canvas directly — same renderers, no backend round-trip. Documented as an explicit second preview mode. |
| M5 | **No media playback anywhere in the frontend today.** A repo-wide grep for `<video`/`<audio`/`<iframe`/`new Audio` returns exactly one hit — `URL.createObjectURL` in `lib/api.ts:155`, for file *downloads*. Every "media" surface today is a static `<img>` bound to `thumbnail_url`. | Build the renderer layer from scratch (this is the bulk of the work). |
| M6 | **Device capability rows are not seeded/populated** for most devices. | Capability warnings degrade to "unknown" rather than false alarms; documented limitation. |
| M7 | **The frontend only ever receives `draft_canvas_json`.** `LayoutDetail` exposes no published version canvas, so a composition preview shows the *draft*, not what a device would play. | Device preview sidesteps this (the manifest carries the published canvas). Composition preview must label itself "Draft" so the two are never confused. |
| M8 | **`download_url` signs with `filename`**, which makes the storage endpoint emit `Content-Disposition: attachment`. Media elements ignore it, but relying on that is fragile on real S3. | Preview should request an inline variant, or accept the documented dependency on element behaviour. |
| M9 | **Asset list ceiling.** `DesignerPage` loads `/assets?page_size=100` and indexes page 1 only, so a zone referencing an asset outside that window silently renders a fallback label. | The preview must resolve assets by id on demand, never from a paged list. |

## 4. Two preview modes (deliberate)

The brief asks for both a design-time preview and "what will Store-KOL-014
show at 7:30 PM". Those need different data sources, so the architecture
names them explicitly rather than blurring them:

| | **Device preview** | **Composition preview** |
|---|---|---|
| Question | "What will *this screen* show?" | "What does *this configuration* look like?" |
| Source | `preview-manifest` (authoritative) | In-memory layout canvas + playlist |
| Entry points | Device detail, Campaign, Monitoring | Screen Designer, Layout, Playlist, Content |
| Resolves schedule/targeting? | Yes — backend | No, and it must not pretend to |
| Requires save/publish? | Requires deployment to exist | No — previews unsaved edits |

Both feed the *same* renderer stack; only the data source differs.

## 5. Frontend state of play

### 5.1 What exists — `modules/design/DesignerPage.tsx`

The canvas *geometry* is solid and reusable. Scale is width-only and
applied by multiplying every coordinate (not a CSS transform), with zones
absolutely positioned and painted in `z_index` order:

```ts
const CANVAS_DISPLAY_WIDTH = 820;
const scale = canvas ? CANVAS_DISPLAY_WIDTH / canvas.canvas.width : 1;
// per zone: left: zone.x * scale, top: zone.y * scale,
//           width: zone.width * scale, height: zone.height * scale
```

The *rendering* is where the gap is. `ZONE_CONTENT_TYPES` declares ten
types — `placeholder, image, video, playlist, text, ticker, clock, web,
widget, qr` — and a three-branch ladder handles all of them:

1. `asset?.thumbnail_url` → `<img>`. This is the branch for `image`
   **and** `video`: a video zone shows a static poster and never plays.
2. `text` / `ticker` → a plain `<span>`. No marquee animation, and no
   font, size, colour or alignment read from `zone.style`.
3. everything else → the literal text `{zone.name} · {zone.content_type}`.

So `video, web, widget, clock, qr, playlist` — six of ten — do not render
at all today. `zone.rotation` is stored but never applied, and
`canvas.orientation` is never read at render time.

There is **no extractable `<ZoneRenderer>`**; the logic is inlined in the
editor's JSX. The simulator must introduce that primitive. Refactoring
the designer onto it afterwards is optional but removes the duplication.

### 5.2 Reusable as-is

`LayoutCanvas` / `ZoneDef` / `PlaylistDetail` / `Device` types;
`formatDuration`; the `assetById` map and ready-filter idiom;
`PageHeader`, `StatusBadge`, `EmptyState`/`ErrorState`/`LoadingState`,
`EntitlementGuard`; `useThemeMode` for the surrounding chrome; the `api`
client (envelope + auto-refresh); and the `lazy` + `withSuspense` route
idiom in `routes/index.tsx`. antd is genuinely universal here — 76 of 79
`.tsx` files import from `"antd"` — so §38 costs nothing.

### 5.3 Timing facts that constrain the engine

- `PlaylistItem.duration_ms` is **nullable**, and `null` means "natural
  duration" — resolve from `asset.current_version.duration_ms` or from
  the `<video>` element's own metadata. The editor already renders that
  case as the word "natural".
- `transition_json.type` ∈ `none | fade | slide`; `none` is stored as `{}`.
- Items carry `enabled` and `ready` flags; both must be honoured.
- Signed URL TTL is **900s** (`signed_url_ttl_seconds`). A session longer
  than 15 minutes must refetch, so the URL cache needs expiry tracking.
- The dev storage endpoint sets `Accept-Ranges: bytes` and honours single
  ranges, so `<video>` seeking works locally.

### 5.4 Theme and naming

The *screen* being simulated is not theme-aware — a TV canvas is whatever
`canvas.background ?? "#000"` says, in both modes. Only the chrome around
it follows the theme. Note that `DesignerPage` hardcodes a light surround
(`styles={{ body: { background: "#f1f5f9" } }}`), which is a theme bug to
avoid inheriting; use `colorBgLayout`.

Naming: **"Preview" alone and "Device Simulator" are both already taken.**
`DeveloperPage` has `SimulatedDevice` (the P3-23 API device simulator),
and three unrelated dry-run features use the word preview. Use
**"TV Preview"** / **"Screen Preview"** throughout.

### 5.5 Routing

Every route is a lazy default inside `AppLayout`. A preview route added
as a sibling inherits the sidebar and header, which is wrong for a
full-bleed TV. Options: a sibling under `ProtectedRoute` but *outside*
`AppLayout`, or a modal/fullscreen overlay. Either way,
`config/navigation.tsx:313` documents that detail routes must map back to
a parent nav entry or the sidebar deselects.

## 6. Playback engine requirements

- Deterministic state machine — `IDLE | PLAYING | PAUSED | COMPLETED`,
  with `loop` as *configuration*, not a state (§41).
- Per-zone timelines. The manifest's playlist drives the **main** zone;
  other zones (ticker, widget, static image) run independently and must
  not be reset by main-zone advancement (§18).
- Duration rules (§11): item `duration_ms` is authoritative. A 30s video
  with a 15s configured duration is cut at 15s; a 10s video with a 20s
  duration repeats to fill. Images simply hold for their duration.
- Cleanup on close (§42): clear timers, pause and detach media elements,
  cancel rAF, drop object URLs.
- Autoplay policy (§43/§44): start muted; if `play()` rejects, surface a
  "Start preview" affordance rather than appearing broken.

## 7. Device compatibility

Aspect ratio comes from `screen_width × screen_height` (portrait devices
are seeded 1080×1920). Falls back to generic 1920×1080. Capability
warnings read `device_capabilities`; when a device has no capability rows
the preview says "capabilities unknown" instead of asserting failure.

## 8. Risks

| Risk | Mitigation |
|---|---|
| Preview accidentally causing a deployment | Preview only ever issues GETs. `preview-manifest` is read-only; no write path is reachable from the preview UI (§23). |
| Signed URLs expiring mid-preview | TTL is `signed_url_ttl_seconds`; long sessions re-fetch the manifest rather than failing a zone. |
| Large 4K media stalling the browser | Preload current + next item only (§48); never all items. |
| Re-deriving schedule rules in JS | Explicitly forbidden — the `at` parameter (M2) keeps evaluation server-side. |
| Video codecs the browser cannot play | Per-zone error state with Retry (§49); other zones keep playing. |
| Demo video assets are placeholder payloads | The demo seeder writes real poster thumbnails but placeholder `.mp4` bytes, so video zones will show the error state on demo data. Images, text, tickers and widgets render fully. Documented, not hidden. |

## 9. Implementation order (adjusted to this repo)

1. `build_manifest(at=…)` + `GET /devices/{id}/preview-manifest` (+ tests)
2. Preview data contract (TS types mirroring the manifest)
3. `TVPreviewFrame` (aspect-correct, `contain`-fit, subtle bezel)
4. Content renderers (image, video, text, ticker, widget, html, fallback)
5. `ZoneRenderer` driven by the real canvas
6. Playback engine (state machine + per-zone timelines)
7. Controls, timeline, queue, info panel
8. Entry points: Device → Campaign → Playlist → Screen Designer
9. Schedule-aware ("preview at date/time") mode
10. Fullscreen, screenshot, accessibility, responsive, performance
