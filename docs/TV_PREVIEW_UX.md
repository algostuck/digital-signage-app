# TV Preview — UX

## Where it is

| Entry point | Mode | Why there |
|---|---|---|
| Device details drawer → **TV preview** | Device | The only place that can answer "what is *this* screen showing" |
| Playlist editor → **Preview** | Composition | Check sequencing and durations before publishing |
| Screen Designer → **Preview** | Composition | See the canvas play, not just sit still |

Preview is read-only, so it is **not** gated behind manage permissions —
a viewer who can see a playlist can watch it. The device preview needs
`devices.view`, which anyone reaching the device drawer already holds.

It opens as a modal rather than a route. A route inside `AppLayout` would
frame a TV with a sidebar; a route outside it would need its own nav
handling and lose the context the operator came from.

## What the operator sees

```
┌─ TV preview — Indiranagar Store · Food Court ──── [published] ─┐
│  Preview as of [ Now ▾ ]   Device timezone Asia/Kolkata        │
│ ┌───────────────────────────────┐  ┌─────────────────────────┐ │
│ │ ╔═══════════════════════════╗ │  │ Queue (6) │ Details     │ │
│ │ ║                           ║ │  │                         │ │
│ │ ║    the screen, in its     ║ │  │ 01 Store Directory  30s │ │
│ │ ║    real aspect ratio      ║ │  │ 02 Membership       30s │ │
│ │ ║                           ║ │  │ 03 Product Teaser   12s │ │
│ │ ╚═══════════════════════════╝ │  │ …                       │ │
│ │ ▓▓▓▓▓▓▓░░░░░░░░░░░░░░░░░░░░░░ │  │                         │ │
│ │ 2/6 · Membership      0:14/0:30│ │                         │ │
│ │ [◀] [▮▮] [▶] [↻]      [🔇] [⛶]│  │                         │ │
│ └───────────────────────────────┘  └─────────────────────────┘ │
└────────────────────────────────────────────────────────────────┘
```

The bezel is a shadow ring, not a decorative TV illustration — enough to
read as a screen, not enough to compete with the content.

## Honesty in the interface

A preview's whole value is that it can be trusted, so the UI states what
it is rather than implying more:

- Composition previews carry a **"Draft composition"** tag and an alert:
  *"Schedules, targeting and decisioning are not applied here."*
- Device previews show **"In a schedule window"** or **"Outside every
  window"**. A campaign resolved but out of window still plays — that is
  what the device does, since the player re-evaluates windows locally —
  and the badge says so instead of hiding it.
- A zone that cannot render says why ("Video cannot be played", "Autoplay
  blocked", "Widget — no data snapshot") rather than showing black.

## Controls

| Control | Keyboard | Notes |
|---|---|---|
| Play / pause | `Space` | Also pauses tickers and the clock |
| Previous / next | `←` `→` | Wraps, even with loop off |
| Restart | — | Back to item 1, loop count reset |
| Mute | `m` | Starts muted; browsers require it for autoplay |
| Fullscreen | `f` | The stage only — controls stay reachable |
| Jump to item | click a queue row | |

Keyboard handling ignores events from inputs, so typing in the date picker
does not trigger playback.

## Schedule-aware preview

The **Preview as of** picker asks the server what the screen shows at that
moment. "Back to now" clears it. The device's timezone is shown beside it,
because "7:30 PM" means the screen's local evening, not the operator's.

## Accessibility

- The screen carries `role="img"` with its dimensions; the live description
  of what is playing sits in the controls, where it can be read as text.
- Every icon button has an `aria-label`; the active queue row is marked
  `aria-current`.
- `prefers-reduced-motion` disables the marquee and transitions. Content
  still advances — that is the point of the preview — but nothing slides.
- Focus stays inside the modal; `Esc` closes it (antd default).
- Contrast on the surrounding chrome follows the app's AA/AAA tokens. The
  screen itself is exempt: it renders the layout's own colours, which is
  what the display will show.

## Responsive

Above `lg` the screen and the queue sit side by side (16/8). Below, the
queue moves under the screen. The screen fits its box on both axes at any
size, so a portrait 1080×1920 canvas is fully visible rather than cropped.
