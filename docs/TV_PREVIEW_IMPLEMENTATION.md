# TV Preview — Implementation

## Files

### Backend

| File | Change |
|---|---|
| `app/services/manifest.py` | `build_manifest(db, device, *, at=None)` — evaluate as of another instant; naive datetimes read as UTC |
| `app/api/v1/devices.py` | `GET /devices/{device_id}/preview-manifest` (`devices.view`) |
| `tests/test_publishing_api.py` | 3 tests + `ready_campaign(schedule=…)` |

### Frontend — `src/modules/preview/`

| File | Responsibility |
|---|---|
| `types.ts` | Manifest contract + the `PreviewSource` seam |
| `playback.ts` | Timeline state machine, rAF clock |
| `renderers.tsx` | Per-`content_type` zone renderers, media element handling |
| `TVScreen.tsx` | Two-axis fit, zone geometry, z-order, rotation |
| `TVPreviewModal.tsx` | Shell: controls, progress, queue, details |
| `DeviceTVPreview.tsx` | Manifest-backed mode + time picker |
| `CompositionTVPreview.tsx` | Editor-state mode |
| `usePreviewSource.ts` | Both data sources, URL resolution, screen geometry |
| `preview.css` | Marquee and transition keyframes |

Entry points wired into `DeviceDetailModal`, `PlaylistEditorPage`,
`DesignerPage`. Lazy-loaded with the pages that use them — it lands in its
own 17 kB chunk.

## Decisions worth knowing

**Modal, not a route.** Routes nest inside `AppLayout`; a TV framed by a
sidebar is wrong, and a route outside it would need its own nav-selection
handling (`config/navigation.tsx:313`).

**Assets resolved by id, never from a list.** `DesignerPage` reads
`/assets?page_size=100` and indexes page 1, so a zone referencing asset
101 silently renders a fallback. Composition preview calls
`/assets/{id}` + `/assets/{id}/download-url` per referenced id instead.

**URL refresh at 10 minutes.** `signed_url_ttl_seconds` is 900. Both modes
set `refetchInterval` to 10 minutes so a long session keeps playing.

**Manifest URLs are already inline.** `build_manifest` signs without a
filename, so no `Content-Disposition: attachment` — unlike
`/assets/{id}/download-url`, which passes one. Media elements ignore the
header either way, but the manifest path is the clean one.

## The demo-data bug this surfaced

The first device preview showed "no playable items" for every device. The
cause was in the demo seeder, not the preview: playlists and layouts were
marked `status='published'` but never given a `PlaylistVersion` /
`LayoutVersion`, so `current_version_id` stayed null. `build_manifest`
resolves content through that column, so all 258 seeded devices received
`layout: null, playlist: null` — a real player would have shown a black
screen.

Fixed in `app/demo_seed.py`: published playlists and layouts now get a
version snapshot mirroring `publish_playlist`, and published campaigns
draw only from versioned content. Three checks in `validate_demo` guard
the invariant. After reseeding, **239 of 263 devices resolve a playable
manifest** (the remainder correctly have no covering deployment).

## Verification

- `pytest tests/test_publishing_api.py` — 12 passed, including manifest
  parity, `at`-based schedule evaluation, and auth.
- `ruff check` clean; `tsc --noEmit` clean; `npm run build` clean.
- `app.demo_seed --validate` — 20/20 checks.
- Direct manifest check: 239/263 devices playable; sample device resolves
  a 3-zone layout and a 6-item playlist, and 5/5 signed URLs served bytes
  with correct content types.

## Remaining work

1. **Visual sign-off in the browser.** The modal, controls and queue were
   confirmed rendering; playback against reseeded content has not been
   watched end to end, because reseeding cleared the login session.
2. **Demo videos are placeholder bytes.** The seeder writes real poster
   thumbnails but not real MP4 payloads, so video zones show the
   "Video cannot be played" state on demo data. Images, text, tickers,
   clocks and widgets render fully. Worth generating small real clips if
   the demo needs to show video playing.
3. **Campaign and monitoring entry points** are not wired yet — the
   component takes a `Device`, so adding them is a button, not new logic.
4. Screenshot export, QR rendering and nested-layout items — see the
   limitations in [TV_PREVIEW_ARCHITECTURE.md](TV_PREVIEW_ARCHITECTURE.md).
