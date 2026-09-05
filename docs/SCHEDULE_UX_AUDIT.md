# Schedule Workspace — UX and API Audit

Status: audit written 2026-09-05 before any change; the implementation
that followed is recorded in §11 at the end (2026-09-06).
Scope: **Campaigns › Schedule** (`/schedules`,
`frontend/src/modules/campaigns/SchedulesPage.tsx`), the scheduling
services (`backend/app/services/scheduling.py`), the schedule, calendar
and conflict routes (`backend/app/api/v1/campaigns.py`) and the seeded
Indian demo data. Every number below was measured against the live API
with the seeded Reliance tenant unless stated otherwise.

Related: [API.md](API.md), [DATABASE.md](DATABASE.md),
[DEMO_DATA_CATALOG.md](DEMO_DATA_CATALOG.md),
[ORGANIZATION_ADMIN_DASHBOARD_DATA_MAP.md](ORGANIZATION_ADMIN_DASHBOARD_DATA_MAP.md)
(the dashboard already computes "today" and "now playing" with the same
service).

---

## 1. Current problems

| # | Problem | Evidence |
|---|---|---|
| P1 | **The conflict alert is noise, not information.** The banner says "486 scheduling conflicts in this range" for a single month. | The API's `conflict_count` is the number of *overlapping event pairs* (September: 867 events, 569 pairs). A week of the seeded tenant produces 222 events, 159 pairs and 141 events flagged `conflict`. Nobody can act on 486 items. |
| P2 | **Most "conflicts" are not conflicts.** Two campaigns that never share a screen are flagged because they play at the same time with the same priority. | `detect_conflicts` compares campaigns by *time and priority only*; targets are never consulted. The seed gives 8 of 18 campaigns priority 50 or 55 and every campaign a morning/afternoon/evening window, so almost everything overlaps something. |
| P3 | **The calendar cannot answer "what plays where".** No location, device, group or tag data reaches the page. | `CalendarEventOut` has no target fields; effective targets exist only per campaign (`GET /campaigns/{id}/effective-targets`), which is an N+1 call from the calendar. |
| P4 | **Draft, expired and paused campaigns look identical to live ones.** | `campaigns_with_schedules` returns every non-archived campaign; the event carries no campaign status and the chip has one "processing" tone for every play window. |
| P5 | **Week and month look the same.** Week view is the month grid with times printed in the chips; there is no time axis, no duration, no "now". | One `grid-cols-7` of `Card`s serves both views; events are text chips regardless of length. |
| P6 | **No day view, no agenda, no timeline.** Clicking a day does nothing. | The page has `view: "week" | "month"` only. |
| P7 | **No filters.** Location, group, campaign, status, priority, kind and conflict state cannot be narrowed. | The only inputs are ‹ › and the Week/Month segmented control; the calendar endpoint takes `from`/`to` only. |
| P8 | **Blackouts are indistinguishable from play windows** apart from a grey tone, and there are none in the demo data to show. | `kind === "blackout"` → `tone="default"`; the seeder creates no blackout schedule (`demo_seed.py` ~L884–928). |
| P9 | **Recurrence is invisible on the calendar.** A weekday-only schedule and an every-day schedule render the same chip; the rule is only visible in the table ("Mon, Wed, Fri"). | No recurrence data on `CalendarEventOut`; the table's "Recurrence" column is the only place. |
| P10 | **Timezone is fragile.** `isoDate()` formats with `toISOString()`, i.e. UTC, so the visible week can shift by a day for users east of UTC and the month grid starts on the wrong date after 18:30 UTC. | `types.ts::isoDate`. Events are wall-clock minutes in the schedule's IANA zone (Asia/Kolkata for all seeded data) but nothing states that on screen. |
| P11 | **The creation form is a bare data-entry modal.** Month days and exception dates are comma-separated text, timezone is a free-text `Input`, and the conflict check result is a raw list. | `CreateScheduleModal` in `SchedulesPage.tsx`. |
| P12 | **No campaign context.** A chip cannot be opened; the campaign, its targets, its status and its other windows are on a different page. | No Popover, no Drawer; `CampaignDetailModal` (already an antd `Drawer`) is not reused here. |
| P13 | **Mobile is a horizontal scroll.** The grid is `min-w-[560px] overflow-x-auto`; on a phone the user pans a 7-column table. | Measured in the responsive pass (gate 8) and left as a known gap. |
| P14 | **Everything is fetched twice.** The page loads the calendar, the whole schedule list and 100 campaigns on mount and refetches all three after any change. | Query keys `["calendar", …]`, `["schedules"]`, `["campaigns"]`. |

## 2. Current data available

### Schedule row (`schedules` table, `ScheduleOut`)

| Field | Type | Meaning |
|---|---|---|
| `campaign_id`, `name`, `kind` | uuid, text, `play` \| `blackout` | a blackout suppresses the campaign inside its window |
| `start_date`, `end_date` | date, nullable | active range; NULL = open-ended |
| `start_time`, `end_time` | time | daily window `[start, end)`; `end <= start` wraps overnight |
| `days_of_week` | int[] (0 = Mon … 6 = Sun), nullable | NULL = every day |
| `recurrence_json` | `{ "days_of_month": [int] }` | optional narrowing |
| `exception_dates_json` | date[] | skipped dates |
| `timezone` | IANA, nullable | NULL inherits device → location → organization |
| `priority` | int 1–100, default 50 | tie-break *within* a campaign priority |
| `expired` (computed) | bool | `end_date < today` |

### Campaign (`CampaignSummary` / `CampaignDetailOut`)

`id, name, description, status, priority, playlist_id, layout_id,
schedule_count, created_at, updated_at`; the detail endpoint adds
`schedules`, `targets` (`target_type` location / device / group / tag,
`target_id`, `include_descendants`, `is_exclusion`) and `variants`.
Statuses: `draft, pending_approval, approved, published, paused, expired,
archived`. There is **no** "scheduled / active / completed" status; that
state has to be derived from status + window + clock.

### Calendar event (`CalendarEventOut`)

`schedule_id, campaign_id, campaign_name, schedule_name, date,
start_minute, end_minute, priority, campaign_priority, timezone, kind,
overnight, conflict` — one row per schedule per active day, first segment
only (an overnight window's morning tail is not emitted as a second row).

### Seeded demo data (Reliance tenant, Asia/Kolkata)

| Item | Value |
|---|---|
| Campaigns with schedules | 18 non-archived (8 published, 4 "scheduled-like" published, 2 approved, 2 pending approval, 3 draft, 1 paused, 2 expired, 1 archived across the distribution) |
| Campaign priorities | random from 40 / 50 / 55 / 60 / 70 / 80 |
| Schedules per campaign | morning / afternoon / evening windows, 60 % every day, 40 % five random weekdays; one deliberate "Overlapping Midday Window (demo conflict)" |
| Blackouts | **none** |
| `days_of_month` / exception dates | **none** |
| Timezones | all `Asia/Kolkata` (schedule level); organisation timezone also `Asia/Kolkata` |
| Targets in use | location 11, group 11, tag 5, device 3 (with descendants) |
| Events, week of 2026-08-31 | 222 events, 159 overlap pairs, 141 events flagged |
| Events, September 2026 | 867 events, 569 overlap pairs |

The dataset is realistic for *volume*; it is unrealistic for
*conflicts* because priorities repeat and targets are ignored by the
conflict rule. That is a rule problem, not a data problem.

## 3. Current API capabilities

| Endpoint | What it does | Notes |
|---|---|---|
| `GET /schedules` | all schedules of the tenant (`campaign_id` filter) | no range filter; used for the table |
| `POST /schedules`, `PATCH /schedules/{id}`, `DELETE /schedules/{id}` | CRUD | PATCH accepts every `ScheduleCreate` field, so drag-and-drop persistence is possible today |
| `POST /schedules/conflicts` | dry-run: a proposed schedule against existing ones, returns `overlaps[]` (date, window, campaigns, winner, `conflict`, reason) + `conflict_count` | range defaults to 31 days; the only place *winners* are reported |
| `GET /schedules/calendar`, `GET /calendar` | expanded events for `from`–`to` (max 62 days) + pair count | no filters, no targets, no status, no reasons, no summary |
| `GET /campaigns`, `GET /campaigns/{id}` | list / detail incl. schedules and targets | list is paginated (page_size ≤ 100) |
| `GET /campaigns/{id}/effective-targets` | resolved device list (id, name, serial, platform) | per campaign, no location roll-up |
| `GET /locations/tree` | `{node, children}` hierarchy | ready for a `TreeSelect` |
| `GET /device-groups`, `GET /tags` | filter dictionaries | ready for `Select` |
| `GET /dashboard` (`schedule_today`, `now_playing`) | today's events with `live` and `conflict`, current winner | proves NOW / NEXT can be computed server-side with the existing service |

Service-level rules that exist and must stay the single engine:
`expand_calendar`, `detect_conflicts`, `overlap_report`,
`_resolution_key` (campaign priority → schedule priority → newest
campaign), `resolve_active_campaign`, `is_blacked_out`,
`is_schedule_active` (overnight-aware, evaluated in the schedule's zone).

## 4. Calendar limitations

- **Presentation** — a hand-built grid of `Card`s; antd `Calendar` is not
  used, so keyboard navigation, month/year pickers, `cellRender` and
  locale handling are all missing or re-implemented.
- **Density** — every event is a full chip; a seeded weekday holds ~31
  events, so month cells overflow and week columns become lists.
- **No time axis** — durations, overlaps and gaps are not visible; the
  chip for a 30-minute window and a 12-hour window are the same size.
- **No day view** and no selected-day panel.
- **No current-time indicator**, no "today" emphasis beyond the header
  text.
- **Range cap** — 62 days is enough for month and week; a six-week month
  grid (42 days) fits, a year view would not.
- **Timezone** — `isoDate` is UTC-based (P10); the page never states the
  zone it displays.
- **Refetch scope** — any mutation refetches the calendar, the schedule
  list and the campaign list.

## 5. Conflict limitations

1. **Definition is too coarse.** A conflict is "two *different* campaigns
   with *equal* campaign priority overlapping on the same day". It ignores
   whether the campaigns share a single screen, so campaigns for Mumbai
   and Kolkata conflict with each other (P2).
2. **Count is pairs, not problems.** `conflict_count` is the number of
   pairs; a three-way overlap is three conflicts, a daily overlap for a
   month is thirty.
3. **No severity, no reason, no resolution hint.** The event carries a
   boolean; the *why* ("same priority 50, both target Andheri West") and
   the *fix* ("raise one priority", "move the window") are not returned.
4. **Priority overlaps are silent.** When priorities differ the overlap is
   *resolved* (the winner plays) but the loser is still scheduled and
   never told it will not play. `overlap_report` computes exactly this but
   is only used by the dry-run endpoint.
5. **Blackouts are not conflicts.** A play window that falls entirely
   inside a blackout is a "silent" schedule; nothing reports it.
6. **Draft / expired campaigns take part.** They are expanded like live
   ones and generate conflicts against published campaigns.
7. **No conflict list.** There is no endpoint that returns *actionable
   conflicts* (grouped by campaign pair and window with affected screens),
   only per-event flags and the total.

## 6. Recurring schedule limitations

- Recurrence is stored as three independent narrowings (`days_of_week`,
  `days_of_month`, `exception_dates`) with no human summary in the API;
  the UI builds "Mon, Wed, Fri" itself and cannot say "Every weekday until
  30 Sep, except 15 Aug".
- The calendar event does not say that it *is* a recurrence, so a ↻
  badge cannot be drawn without joining `GET /schedules` on the client.
- Editing one occurrence is not modelled (there are no per-occurrence
  overrides; the nearest tool is an exception date + a new schedule).
- Overnight windows are emitted as one event on the start day only, so
  the 00:00–02:00 tail of a 22:00–02:00 window is invisible on the next
  day.
- No monthly or exception recurrences exist in the seeded data, so the
  demo cannot show them.

## 7. Responsive problems

| Width | Behaviour today |
|---|---|
| ≥ 1280 | Fine, but chips wrap and the month grid grows to the tallest cell of the row. |
| 768–1279 | Seven columns at ~100 px; week chips truncate to the time only. |
| < 768 | Horizontal scroll of a 560 px grid; the header's Segmented, ‹ ›, range text and CTA wrap into three rows; the table needs its own horizontal scroll. |

Ant Design responsive tokens are used elsewhere (dashboard header,
tables) but not here.

## 8. Recommended UX

**Command-centre layout** (all antd, all existing tokens):

1. **Header** — `PageHeader` title *Schedule* + subtitle with the
   displayed timezone ("Asia/Kolkata"); `Button.Group` ‹ Today ›; a human
   range ("31 Aug – 6 Sep 2026"); `Segmented` Day / Week / Month;
   `Button` *Filters* with a `Badge` count opening a `Drawer`; primary
   *Schedule campaign*.
2. **Filters drawer** — `TreeSelect` (locations from `/locations/tree`,
   include descendants), `Select` device group, campaign, status,
   priority band, kind (play / blackout), conflict state (all / conflicts
   only / silent). Filters are applied **server-side** (see §10) and
   persisted in the URL query so links are shareable.
3. **Summary strip** — `Statistic` cards from the calendar summary:
   scheduled campaigns, screens covered, play windows, blackout windows,
   **actionable conflicts**. Only these five; nothing invented.
4. **Schedule Health panel** replaces the red alert: a `Card` with
   `Progress` (share of windows conflict-free), the actionable conflict
   count with severity `Tag`s (high = live campaigns on shared screens
   with equal priority; medium = resolved-by-priority overlaps where a
   published campaign never plays; low = draft/pending involvement) and
   *Review conflicts*, which opens a `Drawer` listing each conflict with
   the campaigns, window, affected screens, reason and inline actions
   (*Open campaign*, *Adjust priority*, *Move window*).
5. **Month view** — antd `Calendar` with `cellRender`: up to three compact
   chips per cell (campaign colour from a deterministic palette, blackout
   = striped muted chip with a lock icon, conflict = warning dot), then
   *+N more* opening a `Popover` list; selecting a day switches the side
   panel.
6. **Week view** — a time grid (00–24, 30-minute rows) with one column per
   day, events as blocks spanning their duration, overlapping blocks laid
   out side by side, the current-time line in the today column.
7. **Day view** — the same grid for one day with more room, next to the
   side panel.
8. **Selected-day side panel** (≈ 62 / 38 split, `Row`/`Col`): NOW
   PLAYING, NEXT, LATER (from the server's `now` block), then the day's
   full list with `List` + `Tag`s. Only real events; empty states say
   "Nothing scheduled".
9. **Cards / chips** — `Popover` on hover/focus with campaign name,
   status, window, recurrence text, target summary (n locations, n
   screens), priority, and *Open*; click opens the campaign `Drawer`
   (reuse `CampaignDetailModal`).
10. **Quick schedule** — clicking an empty slot in week/day view opens the
    create modal pre-filled with the date and time; the modal keeps the
    existing *Check conflicts* dry-run but renders it as a list with
    winners and reasons. Month days and exception dates become
    `DatePicker` multiples; timezone becomes a `Select` of IANA zones.
11. **Drag and drop** — allowed by the backend (`PATCH /schedules/{id}`
    accepts date and times). Implement as: drag → dry-run
    `POST /schedules/conflicts` with the proposed window → `Popconfirm`
    showing the result → `PATCH` → refetch. Blackouts and expired
    campaigns are not draggable.
12. **Mobile** (< 768) — date strip (`Segmented`-style horizontal scroll
    of days) + agenda `List`; filters stay in the drawer; the side panel
    becomes the agenda itself.
13. **Accessibility** — every chip is a `button` with an accessible name
    ("Diwali Offers, 10:00–13:00, conflict"); views are `role="grid"`
    with roving focus; colour is never the only signal (icons + text for
    blackout, conflict, recurrence); AA contrast on the existing palette.

## 9. Required frontend changes

| Area | Change |
|---|---|
| `modules/campaigns/types.ts` | extend `CalendarEvent`/`CalendarData` with the new contract (§10); replace `isoDate` with a timezone-aware formatter (dayjs `utc` + `timezone` plugins, already shipped with antd's dayjs). |
| `modules/campaigns/schedule/` (new folder) | split `SchedulesPage.tsx` into `ScheduleWorkspace.tsx` (state, queries, URL sync), `ScheduleHeader.tsx`, `FiltersDrawer.tsx`, `SummaryStrip.tsx`, `HealthPanel.tsx`, `ConflictsDrawer.tsx`, `MonthView.tsx` (antd `Calendar`), `TimeGrid.tsx` (week + day), `DayPanel.tsx` (now / next / later), `EventChip.tsx` + `EventPopover.tsx`, `MobileAgenda.tsx`, `ScheduleFormModal.tsx` (existing modal, upgraded inputs), `useScheduleQueries.ts`, `useNow.ts` (tenant-zone clock, 60 s tick), `palette.ts` (deterministic campaign colours, AA-checked). |
| Queries | one calendar query per (view, range, filters) with `keepPreviousData`; schedule list only when the table/agenda needs it; campaign list only for the filter `Select`; invalidate the calendar range only after mutations. |
| Reuse | `CampaignDetailModal` Drawer for campaign detail; `ToneTag`; `PageHeader`; dashboard's `EmptyState`. |
| Navigation | label stays *Schedule*; no new route. |
| Tests | Vitest for the time-grid layout algorithm (overlap columns) and the recurrence text; a Playwright-free smoke via the existing audit journey (create → check conflicts → calendar shows it). |

## 10. Required API changes

The backend stays the only conflict engine. The minimum extension is one
richer calendar response plus filters; everything else is derivable.

### 10.1 `GET /schedules/calendar` — filters

`from`, `to` (unchanged, ≤ 62 days) plus optional `location_id` (with
descendants), `group_id`, `campaign_id`, `status` (multi), `kind`,
`priority_min`, `priority_max`, `conflicts_only`. Filtering by location
or group resolves through the existing targeting service so the calendar
shows only campaigns that reach at least one screen in that scope.

### 10.2 `GET /schedules/calendar` — event fields

Add to each event: `campaign_status`, `schedule_kind` (already `kind`),
`recurrence` (`{type: "once"|"daily"|"weekly"|"monthly", text: "Every
Mon, Wed, Fri until 30 Sep"}`), `target_summary` (`{locations: n,
screens: n, groups: n}`), `conflict_ids` (ids into `conflicts[]`), `live`
(true when the window covers the server's now), `expired`.

### 10.3 `GET /schedules/calendar` — response blocks

- `summary`: `{campaigns, screens, play_windows, blackout_windows,
  conflicts_actionable, conflicts_pairs}`.
- `conflicts[]`: **actionable** conflicts, one per (campaign A, campaign
  B, daily window, date range) with `severity` (high / medium / low),
  `reason` (`equal_priority_shared_screens`, `shadowed_by_priority`,
  `inside_blackout`), `screens_affected` (count + up to five names),
  `dates` (first, last, count), `winner_campaign_id`, and
  `suggestions[]` (text). Computed from `overlap_report` plus effective
  targets, deduplicated across days.
- `now`: `{at, date, minute}` — the server clock in the tenant zone;
  with the per-event `live` flag the side panel groups NOW PLAYING
  (`live`), NEXT (starts after `now.minute` today) and LATER without
  computing winners or reading the browser clock.
- `timezone`: the zone all minutes are expressed in (organisation zone;
  per-event `timezone` stays for schedules that override it).

*Implemented 2026-09-05* in `backend/app/services/schedule_calendar.py`
(`build_calendar`, filters, device-set resolution) and
`scheduling.py` (`recurrence_summary`, `analyse_conflicts`); the
dashboard's today panel uses the same engine. Measured on the seeded
Reliance tenant: the week of 31 Aug now reports **10 actionable
conflicts (2 high, 8 medium)** instead of 159 pairs; a 42-day month
grid answers in ~0.4 s, a week in ~0.1 s.

### 10.4 Conflict rule change (service)

`detect_conflicts` / `overlap_report` gain a *screen-intersection* test:
two campaigns overlap only if their effective device sets intersect
(computed once per campaign per request, cached for the request). Equal
priority on shared screens = **high**; resolved-by-priority where the
loser is published = **medium**; involvement of a draft / pending /
expired campaign = **low** and excluded from the actionable count. A
play window fully inside a blackout of the same campaign is reported as
`inside_blackout` (medium). The dashboard's conflict count should use the
same actionable number so the two screens agree.

### 10.5 Seed

Add two or three blackout windows (e.g. store-closure hours, a public
holiday exception) and one `days_of_month` schedule to
`demo_seed.py`, using the existing generator and the same Indian
context, so the demo can show blackouts, exceptions and recurrence
badges with legitimate seeded data. No other data changes.

### 10.6 Out of scope (documented gaps)

Per-occurrence overrides, calendar exports (ICS), multi-timezone
estates on one calendar (the workspace displays the organisation zone
and labels overrides), and a year view (would exceed the 62-day cap).

---

## Implementation order (from the brief, mapped to this audit)

1. Data contract (§10.1–10.4, seed §10.5) with tests.
2. Header, navigation, timezone-safe dates.
3. Filters drawer (server-side).
4. Summary strip + Health panel + Conflicts drawer.
5. Month view (antd `Calendar`), then week/day time grid.
6. Chips, recurrence badges, blackout styling, conflict markers.
7. Popover and campaign drawer; day panel with NOW / NEXT / LATER;
   current-time line.
8. Quick schedule, drag-and-drop with dry-run confirmation.
9. Mobile agenda, accessibility, performance, QA against the seeded
   tenant.


---

## 11. Implementation status (2026-09-06)

Delivered in the order of §84 of the brief. Everything below was verified
against the live API and in the browser pane with the seeded Reliance
tenant (owner Arjun Mehta), in light and dark themes, at desktop and
phone widths.

### Backend — the single conflict engine

| Piece | Where | What changed |
|---|---|---|
| Recurrence wording | `scheduling.recurrence_summary` | `(type, text)` per schedule: "Every weekday until 30 Sep, except 1 date"; carried on every calendar event and used by chips, popovers and the day panel. |
| Conflict analysis | `scheduling.analyse_conflicts` | Replaces time-only pairs with **shared-screen** conflicts, grouped per (reason, schedule pair) across the range, graded high / medium / low, with dates, affected screens, winner and suggestions. Only the side needing attention is flagged (`event.conflict`); every side carries `conflict_ids`. |
| Calendar service | `services/schedule_calendar.py` | `build_calendar`: campaigns with targets, one target resolution per distinct target, event enrichment (`campaign_status`, `screens`, `locations`, `live` — never inside a blackout, `expired`), server-side filters, summary, tenant clock. |
| Route | `GET /schedules/calendar` | Filters `location_id`, `group_id`, `device_id`, `campaign_id[]`, `status[]`, `kind`, `priority_min/max`, `conflicts_only`; response adds `timezone`, `now`, `conflicts[]`, `summary`; `conflict_count` is now the actionable count. |
| Dry-run | `POST /schedules/conflicts` | Same engine: returns `conflicts[]` + `actionable_count` next to the legacy `overlaps`; `schedule_id` excludes the window being edited. |
| Dashboard | `dashboard._schedule_today` | Uses the same engine, so the dashboard and the workspace agree on "in conflict". |
| Seed | `demo_seed.py` | Two blackouts (Gandhi Jayanti closure, nightly store-closed 22:30–07:00), a monthly 1st/15th window, a weekday window with an exception date, and one deliberate window inside a blackout. |
| Tests | `test_scheduling_engine.py`, `test_campaigns_api.py`, `test_advanced_campaigns_api.py` | Recurrence wording; shared-screen / shadowed / blackout / low-severity grading; API grading, summary and every filter. |

Measured on the seeded tenant after reseeding: the week of 31 Aug reports
**11 actionable conflicts (2 high, 9 medium)** plus 20 informational,
against 159 pairs before; a week answers in ~0.1 s, the 42-day month
grid in ~0.4 s.

### Frontend — `frontend/src/modules/campaigns/schedule/`

| File | Role |
|---|---|
| `ScheduleWorkspace.tsx` | The page: header, summary strip, health panel, 15 / 9 split (calendar / day panel), drawers, form modal, drag-and-drop confirmation, collapsible "all windows" table. |
| `useScheduleWorkspace.ts` | View, anchor and filters in the URL (shareable links), one calendar query per range + filters with `keepPreviousData`, tenant-zone clock corrected to the server time. |
| `dates.ts` | Civil-date helpers; `tenantNow` via `Intl` in the tenant zone; `isoDate` in `types.ts` no longer uses UTC. |
| `palette.ts` | Deterministic campaign hues (Tailwind 100/900 pairs, ≥ 9:1 text), striped blackout style, status / severity / reason vocabulary. |
| `MonthView.tsx` | Ant Design `Calendar` with `cellRender`: three compact chips per day, "+N more" popover, day selection. |
| `TimeGrid.tsx` | Week and day: 24-hour grid, interval-partitioned lanes with a width-aware cap and "+N" overflow, current-time line, click-to-schedule, drag-to-move that only hands back a proposal. |
| `DayPanel.tsx` | NOW PLAYING / NEXT / LATER / EARLIER / BLACKOUTS for today, "Scheduled" or "Played" otherwise; empty states. |
| `EventChip.tsx` | Chip, block styling, accessible names, icons, the hover/focus popover (status, time, recurrence, reach, priority, conflicts from this window's point of view, actions). |
| `HealthPanel.tsx` | Summary strip (five real counts) and Schedule Health (clean share, decisions needed by severity, conflicts-only toggle, *Review conflicts*). |
| `ConflictsDrawer.tsx` | Actionable list with severity filter, campaigns, window, dates, screens, suggestions, *Show on calendar*, *Open campaign*. |
| `FiltersDrawer.tsx` | `TreeSelect` locations, group, campaigns, status, priority band, type, conflict-only; Apply / Reset. |
| `ScheduleFormModal.tsx` | Create / edit with pickers (month days `Select`, exception dates `DatePicker multiple`, timezone `Select`), prefilled from a slot, dry-run graded by the engine. |
| `MobileAgenda.tsx` | Date strip + agenda under 768 px; no horizontal page scroll. |

### Accessibility and performance

Every chip and block is a `button` whose name says what the colour and
icons say ("Diwali Offers, 10:00–13:00, Published, conflict, recurring");
popovers open on focus as well as hover; the grid header, columns and the
mobile strip carry roles and pressed / selected state; colour is never
the only signal (lock, warning, repeat and play icons, dashed outlines,
stripes). Text on chips measures ≥ 9:1 in both themes by construction.
One request per visible range; filters and navigation keep the previous
data on screen while the next range loads.

### Known gaps (unchanged from §10.6)

Per-occurrence overrides, ICS export, mixed-timezone estates on one
calendar (the workspace displays the tenant zone and labels overrides),
a year view. `antd` warns that `List` is deprecated in favour of `Listy`
in 6.6; the drawers still use `List` until the replacement is adopted
app-wide.
