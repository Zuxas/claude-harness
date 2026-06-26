---
title: Meta-Analyzer / Playbooks as a Phone App — Feasibility + MVP Scope
status: PROPOSED
created: 2026-06-26
project: mtg-meta-analyzer
---

# Meta-Analyzer / Playbooks as a Phone App

## TL;DR

Ship it as an **installable PWA** built on the **My-Website** static site, fed by
**pruned JSON exported from the desktop DB** (the `scripts/generate_site_data.py`
pipeline already does this). The 206 MB SQLite DB never leaves the desktop; the
phone reads ~58 KB of JSON published to the host you already have. No always-on
server is needed for the read-only meta/playbook features. A small **FastAPI**
read endpoint is added later *only* for genuinely dynamic features, and the
**personal match log is captured device-local** (IndexedDB) — not served by the
read-only backend. If the in-hand feel of a PWA isn't good enough, wrap the same
codebase with **Capacitor** for a real App Store install with zero rewrite.

This is grounded in the actual repo, not assumptions:
- `scripts/generate_site_data.py` already queries `data/mtg_meta.db` and writes
  `modern-meta.json` / `modern-matchups.json` / `modern-guides.json` into
  `My-Website/data/`. Measured sizes today: **meta 3 KB, matchups 17 KB,
  guides 38 KB** (total ~58 KB) vs a **206 MB** DB. The hard part is already solved.
- `My-Website/` already has the consuming half: `matchup-data-loader.js`,
  `card-tooltips.js`, and ~40 playbook HTML pages under `standard/ modern/ pioneer/`.
- `scrapers/event_finder.py` hits WotC's **public GraphQL API** (no key) +
  OpenStreetMap Nominatim for zip->lat/lng. So "events near me" is a *client-side
  GPS + live API + Maps deeplink* concern, not a data-shipping problem.
- `mcp_server/` (FastMCP, 5 read-only tools) is real and reusable — but its HTTP
  transport targets **MCP/LLM clients, not REST clients** (verified on
  gofastmcp.com). So it stays the agent interface; the phone gets a thin REST/JSON
  surface instead.

---

## 1. Recommended Architecture

### Why a PWA (the "pick ONE", justified)

| Option | Verdict |
|---|---|
| **Installable PWA** | **CHOSEN.** Reuses the existing My-Website HTML/JS + JSON pipeline almost verbatim. One codebase, instant deploy to the host already in use, $0 hosting, no app-store gatekeeping, works on iOS + Android. Fastest path to "in the hand". |
| React Native | Rejected for v1. Would mean **re-deriving** the playbook/matchup UI you already have on the web as native components. No reuse of My-Website. Heavier toolchain for a solo, limited-coding owner. |
| Flutter | Rejected for v1. Same re-derivation cost as RN, plus a new language (Dart). Best-in-class feel, but the asset reuse argument dominates here. |
| **Capacitor (upgrade lever)** | Keep in pocket. Wraps the *same PWA codebase* in a native shell for a real App Store/Play install, push, and better feel — **no rewrite**. Pull this lever only if the PWA's in-hand feel disappoints. |

"Feels good in the hand" with a PWA — honest tradeoffs (all verified, June 2026):
- iOS install = manual **Share -> Add to Home Screen** (no install prompt). Once
  installed it runs full-screen with no browser chrome and feels app-like.
- **Web Push works on iOS 16.4+ but only after the PWA is added to the home
  screen** (open Safari tabs can't use PushManager). Android has full PWA support.
- iOS has **no Background Sync / Periodic Sync / Background Fetch** — a PWA can't
  refresh content in the background. Adopt a **"refresh on open"** freshness model
  (fetch latest JSON when the app is foregrounded; cache via service worker for
  offline). This fits a meta app fine — data changes daily, not by the second.
- All iOS browsers are WebKit; the limitations are uniform regardless of browser.

If those tradeoffs annoy you in practice, **Capacitor** removes them (native
install + reliable push) without throwing away the web code.

### Resolving the "read-only backend vs personal match log" tension

A read-only backend cannot deliver the compelling phone match log, because the
phone-native value is **capturing** a match between rounds at an event (a write).
Split the data by ownership so the backend stays read-only:

- **Shared meta data (read-only, static JSON, no server):** matchup win-rates,
  meta/field share, sideboard playbooks. This is the ~58 KB export.
- **Personal data (on-device):** the match log is **captured and stored in the
  PWA via IndexedDB/localStorage**. The phone is the source of truth for matches
  entered on the phone. Two clearly distinct options, named so scope is unambiguous:
  - **(a) View-only mirror** — desktop `match_log` rows exported to JSON like the
    meta data; phone displays but cannot add. Trivial, but low value.
  - **(b) On-device capture** — phone records matches locally; **optional
    sync-back to the desktop DB is a later phase** (needs the API + auth below).
  Recommend (b) for the value, starting local-only with no sync.

### Three data tiers (this is the whole sync story)

| Tier | Data | Mechanism | Server needed? |
|---|---|---|---|
| 1 | Matchup WR, meta/field share, playbooks | Scheduled JSON export -> static host (existing `generate_site_data.py` -> My-Website) | **No** |
| 2 | Event finder ("near me"), on-device match log | Client-side: phone GPS + live WotC GraphQL API + Maps deeplink; IndexedDB for the log | **No** (optional thin proxy only if CORS blocks the WotC call) |
| 3 | Match-log sync-back, auth'd personal/team data, live queries | Small **FastAPI** read/write service over the DB | Yes (phase 3) |

The spine: **the DB lives on a Windows desktop that is not a server**, and the
phone cannot reach `localhost`. The static-export model sidesteps this entirely —
no always-on machine, no auth, no hosting cost for Tiers 1-2. FastAPI only earns
its keep at Tier 3, so it is **phased after v0**, not on the critical path.

### How the JSON gets published (no new infra)

The desktop already runs scheduled Task Scheduler jobs (6 AM fill, 5 PM daily).
Add one step that runs `generate_site_data.py` after the daily fill and pushes the
`My-Website/data/*.json` to the host (the site is already published). Phone fetches
on open. That is the entire pipeline.

### FastAPI vs reusing FastMCP (when Tier 3 arrives)

Add a **thin FastAPI** app (`api/main.py`) that imports the same pure analysis
functions the MCP server wraps (`analysis/win_rates.py`, `mcp_server/tools.py`)
and exposes them as plain REST/JSON for the phone. Do **not** point the phone at
the FastMCP HTTP transport — that protocol targets LLM/MCP clients, not REST
consumers. FastMCP stays the agent interface; FastAPI is the human-app interface.
Both call the identical underlying logic, so there is no duplicated analysis code.

---

## 2. MVP Feature Set (all drawn from what already works)

Ordered by value/effort, every item maps to existing desktop functionality:

1. **Matchup win-rates** — verdict-coded (Favored/Even/Dog) per deck vs field.
   Source: `matchup_matrix` table via `generate_matchups()` (already exported).
2. **Meta / field share** — top-20 archetype share + has-playbook flag.
   Source: `generate_meta()` (already exported).
3. **Sideboard playbooks** — the ~40 existing playbook HTML pages render as-is in
   the PWA; this is the single highest-value "in the hand at an event" feature.
4. **Event finder + Maps deeplink** — phone GPS -> WotC GraphQL (live, no key) ->
   list RCQs/Store Champs/FNMs near me, each row a Google/Apple Maps deeplink.
   Source: `scrapers/event_finder.py` logic, ported to a client fetch.
5. **Personal match log (on-device capture)** — quick "round N vs <archetype>,
   result, play/draw" entry between rounds; stored in IndexedDB. Mirrors the
   desktop `match_log` schema (event, round, my_deck, opp_deck, result, play_draw,
   g1/g2/g3). Sync-back to desktop is a later phase.

Deliberately **out of MVP** (desktop-only / heavy): replay viewer, rank tracking
charts, deck analyzer (Blunder/Chapin), KNN classification, Ask-Claude. These need
the full DB, model weights, or a live LLM key and add no event-day value.

---

## 3. Data Sync Story

- **DB is 206 MB; the phone never receives it.** Server-side pruning produces
  ~58 KB of JSON — a **>3,500x** reduction. The exporter already exists.
- **Freshness:** "refresh on open" (iOS has no background sync). Service worker
  caches last-good JSON for offline use at the venue (venue Wi-Fi/cell is often
  bad — offline-first is a feature, not a fallback).
- **Event data** is fetched **live on the phone** (public WotC API), so it is
  always current and depends on nothing being shipped — except that geolocation +
  the third-party call must work from the browser (CORS check below).
- **Personal log** stays on the device; nothing to sync until Tier 3.

---

## 4. Effort / Phasing + Risks

### Phasing

| Phase | Scope | Effort | Touches (OUR files) |
|---|---|---|---|
| **v0 (weekend)** | PWA shell over existing My-Website + matchup/meta JSON; Add-to-Home-Screen; offline cache | **S** | `My-Website/` (new `manifest.webmanifest`, `sw.js`, mobile CSS); reuse `matchup-data-loader.js`, `data/*.json` |
| **MVP-1** | Playbooks mobile-tuned + event finder (GPS + WotC + Maps deeplink) | **M** | `My-Website/` (new `events.js`/page); port logic from `scrapers/event_finder.py` |
| **MVP-2** | On-device match log (IndexedDB capture, mirrors `match_log` fields) | **M** | `My-Website/` (new `matchlog.js` + page) |
| **Phase 3** | FastAPI read API + match-log sync-back + auth | **L** | new `api/main.py` reusing `analysis/win_rates.py`+`mcp_server/tools.py`; auth/secrets |
| **Phase 4 (optional)** | Capacitor wrap for App Store install + native push | **M** | wrap existing PWA; no app logic rewrite |

Generalization needed regardless: `generate_site_data.py` is **hardcoded to
`FORMAT="modern"` and a fixed `OUR_DECKS` dict** (Standard, the stated primary
format, isn't exported). Parameterize it over formats/decks — small but real
(**Value 4, Effort S**, touches `scripts/generate_site_data.py`).

### Biggest risks

- **No always-on server for Tier 3.** A write API needs a hosted, always-up
  machine — the desktop isn't one. (Mitigation: keep Tiers 1-2 serverless; only
  stand up FastAPI when sync-back is truly wanted; a small VPS or the existing host
  with a serverless function.)
- **Privacy/auth the moment personal/team data leaves the device.** Match log +
  any Team Resolve private guides need real auth before they touch a server. Keep
  personal data device-local until then. (Risk: medium; deferred by design.)
- **iOS PWA limits:** no background refresh (refresh-on-open model), push only
  after home-screen install, manual install gesture, WebKit-only. (Mitigation:
  document the install step in-app; Capacitor if feel/push matter.)
- **CORS on the live WotC/Nominatim calls from a browser.** If those endpoints
  reject browser-origin requests, the event finder needs a tiny serverless proxy
  (small Tier-2.5 effort). Verify with one fetch before committing the client path.
- **Static export is only as fresh as the cron.** If the desktop is off, JSON goes
  stale. Acceptable for a meta app; surface the `generated` timestamp (already in
  the JSON) in the UI so staleness is visible.

---

## 5. Simplest v0 ("this weekend" proof)

A PWA reading the already-exported pruned JSON — most of it already exists:

1. Add `My-Website/manifest.webmanifest` (name, icons from `gui/icons/`,
   `display: standalone`, theme color = Team Resolve navy/gold) and link it from
   the playbook/meta pages.
2. Add a service worker (`My-Website/sw.js`) that precaches the shell +
   `data/modern-meta.json` + `data/modern-matchups.json` and serves them offline.
3. Light mobile CSS pass on `meta.html` + one playbook so it reads well one-handed.
4. On a phone: open the site in Safari/Chrome -> Add to Home Screen -> launch
   full-screen, browse matchups + a playbook **offline**.

Deliverable of v0: a real, installable app icon on the phone showing live matchup
win-rates and a sideboard playbook, fully offline, with **zero backend** and
**zero new data plumbing** (the JSON is already published by
`generate_site_data.py`). That proves the whole architecture before any FastAPI or
Capacitor work.

---

## Appendix — Grounding references (files read)

- `mtg-meta-analyzer/scripts/generate_site_data.py` — existing prune-to-JSON exporter.
- `mtg-meta-analyzer/db/database.py` — schema (events/decks/deck_cards/card_data/guides...).
- `mtg-meta-analyzer/db/match_log.py` — `match_log` columns (event/round/my_deck/opp_deck/result/play_draw/g1-3).
- `mtg-meta-analyzer/db/event_hub_db.py` — event_bookmarks (lat/lng/event_url) + store_bookmarks.
- `mtg-meta-analyzer/scrapers/event_finder.py` — live WotC GraphQL + Nominatim, no key.
- `mtg-meta-analyzer/mcp_server/{tools,server}.py` — 5 read-only FastMCP tools over `analysis/win_rates.py`.
- `My-Website/` — playbook HTML, `matchup-data-loader.js`, `data/*.json`.
- Measured: DB 206 MB; meta 3 KB / matchups 17 KB / guides 38 KB JSON.
- gofastmcp.com — HTTP transport targets MCP clients, not REST.
- Web (June 2026) — iOS PWA: home-screen install, push on 16.4+ post-install, no background sync, WebKit-only.
