# TV Preview — Architecture

See [TV_PREVIEW_AUDIT.md](TV_PREVIEW_AUDIT.md) for what existed before this
was built and why these choices were forced.

## The one rule

The preview never decides *what* plays. It only decides *how to draw it*.

Campaign resolution, schedule windows, blackouts, targeting, decisioning
rules, experiment arms and audience variants all stay in
`app/services/manifest.py::build_manifest`, which is the same function the
real player calls. The frontend receives the answer and renders it.

The moment the preview starts evaluating a schedule in JavaScript, it can
disagree with the device — and a preview that disagrees with the device is
worse than no preview.

## Data flow

```
                      ┌──────────────────────────────┐
  device preview ────▶│ GET /devices/{id}/preview-   │
                      │     manifest?at=…            │
                      │   → build_manifest(db, dev)  │
                      └──────────────┬───────────────┘
                                     │  PreviewManifest
                                     ▼
  composition   ┌──────────────┐   ┌──────────────┐   ┌───────────────┐
  preview ─────▶│ canvas +     │──▶│ PreviewSource│──▶│ TVScreen      │
                │ playlist +   │   │  (normalised)│   │  → ZoneContent│
                │ signed URLs  │   └──────┬───────┘   └───────┬───────┘
                └──────────────┘          │                   │
                                          ▼                   ▼
                                    usePlayback         per-zone renderers
```

`PreviewSource` is the seam. Both modes normalise into it, so there is one
renderer stack and one playback engine regardless of origin.

## Two modes, kept distinct

| | Device preview | Composition preview |
|---|---|---|
| Component | `DeviceTVPreview` | `CompositionTVPreview` |
| Source | `preview-manifest` | in-memory editor state |
| `authoritative` | `true` | `false` |
| Resolves schedule/targeting | Yes, server-side | No |
| Asset URLs | inline in the manifest | `/assets/{id}/download-url` per id |
| Shown as | published badge | "Draft composition" + an explanatory alert |

Blurring these would be the easy mistake: a designer preview that looks
authoritative invites someone to conclude a screen is fine when no
deployment covers it at all.

## Backend changes

Two, both additive and read-only.

1. **`GET /devices/{device_id}/preview-manifest`** (`devices.view`) —
   returns `build_manifest(...)` for a console user. The player endpoint
   is device-token authenticated, so the portal could not reach it.
2. **`build_manifest(db, device, *, at=None)`** — evaluates as of another
   instant. Naive datetimes are read as UTC. This is what keeps
   schedule-aware preview server-side.

Neither queues a command, writes a deployment, nor mutates a device.
`test_publishing_api.py` asserts parity with the player's own manifest,
that `at` moves the schedule window, and that auth is required.

## Playback engine

`playback.ts` drives one timeline via `requestAnimationFrame`, accumulating
real deltas so pause genuinely stops time and a throttled background tab
does not fast-forward on return.

- States: `idle | playing | paused | completed`. `loop` is configuration,
  not a state — a looping playlist wraps and never completes.
- `duration_ms` is authoritative. `null` means natural length, reported up
  by the `<video>` element on `loadedmetadata`.
- A clip shorter than its configured duration repeats (`loop` on the
  element); a longer one is cut when the clock says so. The playback clock,
  not the media, decides advancement.
- Explicit skip past the end wraps even when loop is off, because the
  operator asked for it. Only *automatic* advancement completes.

## Zone rendering

`TVScreen` fits the screen on both axes (`min(boxW/w, boxH/h)`) — the
Screen Designer's width-only scale overflows tall canvases. Zones are
absolutely positioned, z-sorted, rotation applied, and each gets
`container-type: size` so text can scale against its zone.

`ZoneContent` dispatches on `content_type`. The zone typed `playlist` is
where the campaign's playlist plays; every other zone runs independently
and is never reset when the playlist advances. With no layout resolved,
the playlist takes the whole screen — which is what a device does when its
campaign has a playlist but no layout.

Coverage of the ten declared types:

| Type | Renders |
|---|---|
| `playlist` | current item, with fade/slide transition |
| `image` | signed URL, `object-fit: cover` |
| `video` | `<video>`, muted, autoplay-refusal surfaced |
| `text` | `content_config.text` |
| `ticker` | seamless CSS marquee, pauses with playback |
| `clock` | live, in the device's timezone |
| `web` | sandboxed iframe, no referrer |
| `widget` | the manifest `data` snapshot (transform already applied) |
| `qr` | the target value, labelled — see limitations |
| `placeholder` | neutral tile |

## Failure and cleanup

Every failure is scoped to its zone: a codec the browser cannot play shows
an error tile while the rest of the screen keeps running. Nothing blanks
the whole screen.

On close, media is paused, `src` removed and `load()` called, the rAF loop
is cancelled, intervals are cleared, and fullscreen is exited so the
browser is not left holding a detached fullscreen element.

## Known limitations

- **QR zones show the target value, not a scannable code.** The app ships
  no QR encoder; rendering a fake one would be worse than being explicit.
- **Nested layout playlist items are not composited.** The manifest pins
  `layout_version_no` but does not inline that layout's canvas.
- **Web zones depend on the remote site allowing framing.** Many send
  `X-Frame-Options`; the zone falls back to a labelled tile.
- **No screenshot export.** Compositing the DOM needs a library the app
  does not ship, and a partial capture would misrepresent the screen.
- **Device capability warnings are not surfaced** — most demo devices have
  no `device_capabilities` rows, so any warning would be noise.
