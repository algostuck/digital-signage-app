# Client Demo Guide

One controlled tenant, one scripted story, told in the order a customer
thinks: *what is on my screens right now* → *how did it get there* → *how do
I know it played*. Twenty minutes, no random screens.

## The tenant

**Reliance Retail Digital Experience** (`RRL-DEMO`, Enterprise plan) —
130 displays across six states:

```text
India
 ├── West Bengal   Kolkata (Salt Lake, Park Street, New Town, Rajarhat), Durgapur
 ├── Maharashtra   Mumbai (Andheri, Bandra, Lower Parel, Powai), Pune
 ├── Karnataka     Bengaluru (Whitefield, Koramangala, Electronic City, Indiranagar), Mysuru
 ├── Telangana     Hyderabad (Banjara Hills, HITEC City, Gachibowli, Secunderabad)
 ├── Tamil Nadu    Chennai (T Nagar, OMR, Anna Nagar), Coimbatore
 └── Delhi NCR     New Delhi, Gurugram, Noida, Ghaziabad
```

Every locality has real coordinates, a synthetic commercial address and
2–4 screen zones (Main Entrance, Billing Area, Food Court, …). Nothing in
it is a real customer or a real person; see `DEMO_DATA_CATALOG.md`.

| Presenter signs in as | Why |
|---|---|
| **Arjun Mehta** — `arjun.mehta@rrl-demo.signage.cloud` | Organization Administrator: the whole story |
| **Sneha Iyer** — `sneha.iyer@rrl-demo.signage.cloud` | Campaign Approver: the four-eyes moment (Reliance has maker-checker on, so Arjun cannot approve his own campaign) |
| **Platform admin** — `platform@signage.cloud` | Only if the customer asks about tenants and plans |

All demo passwords are in `DEMO_CREDENTIALS.md`. Keep a second browser
profile signed in as Sneha so the approval takes one click.

## Before the demo (10 minutes, the day before)

```bash
cd backend && .venv/Scripts/python -m app.demo_seed --refresh
```

re-stamps heartbeats and the last 30 days of playback, incidents and
snapshots so the dashboard reads *now*, not *when the database was seeded*.
Then:

1. Start the API and the portal (`README.md`) and sign in as Arjun.
2. Run the three audit scripts (`HARDENING_AUDIT.md`); all must be green.
3. **Prepare the live screen.** Open *Devices › Player Simulator* in a
   second window, start a player with serial `DEMO-LIVE-1`, approve it
   from the page, and assign it to *Kolkata › Salt Lake* (Devices › the
   new row › Assign location). Leave that window open on a second monitor
   or a projector input: it is the "real screen" of the story.
4. Have one banner image ready to upload (any 1920×1080 PNG).
5. Check *Approvals* is empty and *Publishing* shows no *publishing* job
   left over from a rehearsal (delete rehearsal campaigns; they are named
   after this guide).

## The story (20 minutes)

### 1. Dashboard — "this is your network, right now" (2 min)

Open **Dashboard**. Point at, in this order: 130 displays and the online
percentage; the *Needs attention* list (offline screens, the pending
approvals, a failed deployment); the health trend for the last 7 days;
the map. Everything is live data from this tenant — the *Updated 12 s
ago* badge and the range picker prove it. Switch to *Last 30 days* once.

### 2. Map → Device — "drill down to one screen" (2 min)

On the map click **Kolkata**, then **Salt Lake**. Open *All Devices*
filtered to that store (the map link does it). Open one screen: heartbeat,
storage, player version, its events, and **TV preview** — "what is this
screen showing right now" comes from the server's own resolver, so the
preview cannot lie. Close it.

### 3. Content — "bring in a creative" (2 min)

**Content › Upload content**: drop the banner, watch it process inline,
publish it. Mention folders, versions and the archive/restore lifecycle;
show the 30 existing business-titled assets.

### 4. Designer — "compose the screen" (3 min)

**Design › New layout** → `Demo Layout <date>` → the artboard fills the
card (no scrolling): add a zone for the new banner and a ticker zone with
`Weekend sale — 20% off electronics`. Save, **Publish**. Show *Templates*
and *Widgets* tabs briefly (reusable compositions, live widgets).

### 5. Playlist — "sequence it" (1 min)

**Playlists › New playlist** → `Demo Playlist <date>`: add the layout
(15 s) and two existing assets (8 s each). Publish.

### 6. Campaign, targeting, schedule — "decide where and when" (3 min)

**Campaigns › New campaign** → `Demo Campaign <date>`, playlist + layout,
priority 90. **Targets**: the *Kolkata* subtree, include descendants —
show the *preview* resolving to N screens (the live simulator screen is
among them). **Schedule**: every day 09:00–21:00 Asia/Kolkata; show the
conflict check. **Submit for approval.**

### 7. Approval — "governance" (1 min)

As Sneha: **Approvals** shows the request; approve with a comment. Back as
Arjun the campaign reads *Approved*. (If asked: Arjun trying to approve
his own request is refused — maker-checker.)

### 8. Preview → Publish — "ship it" (2 min)

**TV preview** on the live simulator screen shows what it will play once
published (choose a time inside the window). **Publish**. **Publishing**
shows the job: total screens, acknowledged count climbing as players sync.

### 9. The real screen — "it is on the wall" (2 min)

Switch to the simulator window: within ten seconds the heartbeat reports
*sync required*, the manifest arrives, the deployment is acknowledged, the
banner and ticker are on screen, and the log shows the player reporting
plays. Back in **Publishing** the job reads *published, n/n acknowledged*.
Queue a **Reboot** command from the device row and show it acknowledged in
the simulator log.

### 10. Monitoring → Proof of play → Analytics — "prove it" (2 min)

**Monitoring**: fleet health, the incident for an offline store, anomaly
intelligence. **Reports › Proof of play**, filtered to the demo campaign:
the plays the simulator just reported, per screen, with completion rate.
**Campaign analytics** and **Exports** (CSV/XLSX) close the loop.

Finish on the **Dashboard**: the new campaign is in *Live campaigns* and
the deployment in the strip.

## If something goes wrong

| Symptom | Do |
|---|---|
| Simulator shows *no active campaign* after publish | The screen was added after a campaign was published; publishing snapshots the device set. Publish (or republish) — it is in the demo flow anyway. |
| *Campaign needs at least one schedule / a playlist or layout* on publish | Step 5 or 6 was skipped. |
| Approve is refused for Arjun | Expected — maker-checker. Use Sneha. |
| Dashboard reads stale | `demo_seed --refresh` was not run today. |
| Simulator heartbeat 401 | The device was decommissioned or its token rotated; *Forget token* and start again. |

## After the demo (2 minutes)

Delete the demo campaign (Campaigns › Archive/Delete), playlist and
layout, archive the uploaded banner, decommission `DEMO-LIVE-1` — or keep
them if the next demo is soon; they are all named `Demo … <date>`. Never
run `demo_seed --reset` on a database another demo is using.
