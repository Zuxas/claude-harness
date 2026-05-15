# Execution Chain — 2026-05-16 (Saturday)

**Authored:** 2026-05-15 end-of-day
**Sub-project focus:** Polish + new overlay feature
**Days to RC DC:** 13
**Estimate:** 6-9h focused (1-2h log QA + 1-2h stability/responsiveness + 3-4h overlay + 30-45min Google Maps).

## Session start (15min)

1. Read `harness/state/latest-snapshot.md`.
2. Read `harness/inbox/drift-pr--2026-05-16.md` if present.
3. Read `harness/MEMORY.md` — 2026-05-14 / 2026-05-15 entries:
   massive build days. End-state of the MTGA log pipeline includes:
   live tail, Sync MTGA button, auto-sync on launch, 3-layer
   import latency. Per-match Watch Replay popup w/ full annotation
   stream (cards, abilities, targets, scry top/bottom, counterspell
   attribution by lookahead, opening hand, mulligans). Per-deck
   mulligan analysis, SB plan diff vs canonical, rank progression
   chart, Match History defaults to Ranked-only.
4. Check `harness/IMPERFECTIONS.md`.
5. GUI smoke is mandatory section 1 below.

---

## Section 1 — MTGA log tool QA (1-2h)

User's explicit ask: "make sure the mtga log tool works flawlessly".

Two days of features shipped without GUI smoke. Walk every surface,
catch rendering bugs, fix on the spot. Test plan:

### 1.1 Launch + auto-sync
- [ ] Close any open GUI. `python run_gui.py`.
- [ ] Watch the statusbar — within ~2-3s, "[auto-sync] N new
      matches imported" should print to console (or 0 if up to date).
- [ ] Confirm Dashboard's rank label shows current rank (Platinum 2
      29-29 as of 5/15 evening, will have shifted by Saturday).

### 1.2 Live tail
- [ ] Play one MTGA ranked Bo3 match (any deck).
- [ ] Within 30s of match end, statusbar should flash "MTGA watcher:
      1 new match imported".
- [ ] Open Match Log tab — row should appear.
- [ ] Open My Decks → relevant deck → Match History — row appears
      under Recent Matches with ranked default filter.

### 1.3 Sync buttons
- [ ] Match Log tab → click "↻ Sync MTGA" → should run; status shows
      "MTGA sync complete: N new matches imported".
- [ ] Match Log tab → click "↻ Sync Untapped" → should still work
      (covers untapped writer not broken by today's changes).

### 1.4 Rank progression
- [ ] Click rank label on Dashboard toolbar → progression chart opens.
- [ ] If rank changed since last snapshot, snapshot added → chart
      shows 2+ points.
- [ ] Format dropdown switches Constructed / Limited correctly.

### 1.5 Match History sub-tab
- [ ] My Decks → Tokyo Prowess → Match History tab.
- [ ] Default filter = "Ranked (any)". Verify dropdown is set correctly.
- [ ] Recent matches table populates with ranked-only games.
- [ ] Click a Bo3 match row → Match Detail panel populates on the right:
  - Per-game W/L + close/blowout class
  - Per-game T# / mull-to / life endpoints
  - SB plan G1→G2 (and G2→G3 if Bo3 went to 3)
  - "vs canonical plan" section if matchup exists in saved_sb_plans
- [ ] Mulligan analysis section shows ranked-only data (not all matches).
- [ ] Click "▶ Watch replay" → popup opens with turn-by-turn
      transcript: opening hand, draws, plays, casts, counterspells,
      targets, scry top/bottom, declare attackers, damage, life
      changes.

### 1.6 Auto-created deck flow
- [ ] If you've played an archetype you don't have saved yet, verify:
      after the live-tail tick, a new saved_decks row exists named
      "<Archetype> (auto-imported YYYY-MM-DD)" with mainboard + SB.
- [ ] My Decks → that new auto-deck → Match History → match links
      correctly.

### 1.7 Bug fixes on the spot
- [ ] Any rendering issues / wrong widths / cut-off text → fix.
- [ ] Any classifier misclassifications surfaced today (Goblinslayer
      5c Lute was opp_deck="Deck") → add archetype seed if quick.

---

## Section 1.5 — Stability + responsiveness sweep (1-2h)

User's explicit ask: "make the gui less buggy where it closes
randomly and maybe make it more responsive".

"Closes randomly" needs forensics first -- without repro steps we
can't fix blind. Three concrete actions:

### 1.5a Crash instrumentation (~30min)

- Install a global `sys.excepthook` in `run_gui.py` that:
  - Logs uncaught exceptions to `logs/gui_crash_YYYY-MM-DD.log`
  - Shows the traceback in a QMessageBox (or non-blocking notification)
    so the user knows what happened instead of silent death
- Install a `QtCore.qInstallMessageHandler` to capture Qt-side
  warnings/errors (segfaults from C++ side, deleted-object access,
  etc.) into the same log
- Add `try/except` wrappers around the main event loop entry so
  exceptions on close don't silently terminate

### 1.5b Thread lifecycle audit (~30min)

The live-tail QThread (added 2026-05-14) could be a closes-randomly
culprit. Audit:

- `MtgaLogWatcher.stop()` -- does it actually join cleanly when
  the user clicks the X? Test: close GUI mid-parse, confirm no
  zombie thread + no segfault
- Workers in tabs (DataLoadWorker instances) -- many tabs hold a
  worker ref but don't cancel on tab teardown. Possible crash on
  app-close if a worker is mid-flight against a torn-down DB
  connection
- Add `worker.wait(timeout=3000)` to all close paths
- Add the watcher's signal connections to `Qt.QueuedConnection`
  to ensure they fire on the GUI thread, not the worker thread

### 1.5c Responsiveness profiling (~45-60min)

Common Qt slow-paint causes to check:

- **Big QTableWidget repaints** (~ Match History recent-matches
  table, palette card list): use `setUpdatesEnabled(False)` /
  `setSortingEnabled(False)` during populate, re-enable after
- **DB queries on the UI thread**: any tab that calls `get_*()`
  in a button handler without a worker. Grep `gui/tabs/` for
  `get_matches\|get_decks\|get_meta_standings` outside `_do` /
  `DataLoadWorker._run`. Move to workers.
- **Synchronous match log re-parse** -- the Match Log "Sync MTGA"
  button is worker-threaded (good), but `_refresh_orphan_banner`
  fires `_ensure_table` + a synchronous COUNT(*) on every tab
  show. Cache the count or move to a worker
- **Replay transcript build is sync on the UI thread** (clicking
  Watch Replay can hang ~1-2s on first build). Already cached
  per match in `data/match_replays/`, but the FIRST click for an
  unseen match is the slow path -- run in a worker, show
  "Loading..." until ready

Pick the top 2-3 hot spots. Don't refactor everything; we have a
working app.

---

## Section 2 — Matchup notes overlay (3-4h)

User's explicit ask: "build an overlay or something with notes".

### 2.1 Scope decision (15min)

Two flavors -- present visually if needed:

**A. In-game floating overlay** (Qt frameless window):
- Always-on-top, semi-transparent, click-through optional
- Sits on top of Arena while you play
- Shows current matchup SB plan + notes for the opponent's
  archetype based on most-recent match_log row
- Hotkey to show/hide (e.g. Ctrl+Shift+M)

**B. Companion window** (regular Qt window):
- Lives next to Arena on second monitor (or windowed Arena)
- Same content; doesn't try to overlay
- Easier to build, no transparency / click-through complexity

Recommend B for v0.1 — gets the SB plan + notes surface working
without fighting Windows window-management edge cases. A as v0.2.

### 2.2 Build matchup_notes_overlay.py (~2h)

- New `gui/widgets/matchup_overlay.py`:
  - QWidget with `Qt.WindowStaysOnTopHint` flag (B mode)
  - Or `Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool`
    (A mode)
  - Reads most-recent `match_log` row for the user's selected
    saved_deck (or the auto-classified my_deck_id from the latest
    match)
  - Pulls canonical SB plan from `saved_sb_plans` (deck_id +
    opp_archetype). Reuses `analysis.sb_plan_diff._find_canonical_plan`.
  - Displays:
    - Opponent archetype + difficulty
    - "Bring IN" list with quantities
    - "Bring OUT" list with quantities
    - Matchup notes from `matchup_notes` table (free-text per pair)
    - Auto-refresh when live-tail watcher imports a new match

### 2.3 Wire to MainWindow + hotkey (~30min)

- Add toolbar button or palette command "Open matchup overlay"
- Ctrl+Shift+M global hotkey to toggle visibility
- Save show/hide state to `ui_state.overlay_visible`

### 2.4 Smoke test (~30min)

- Open overlay → verify SB plan + notes for current matchup
- Play a match → verify auto-refresh on new match
- Test position persistence (drag, close, reopen)

---

## Section 3 — End of day (15min)

- Author 2026-05-17 chain
- Update CLAUDE.md / NEXT_STEPS / ROADMAP
- Commit + push

---

## Section 4 — My Events Google Maps deeplink (~30-45min)

User's explicit ask: "in the my events portion id like to open a
google maps of whatever store ive clicked on".

- Find the relevant tab (Event Finder / Event Hub / Tournament
  Prep -> Scout?) -- "My Events" UI label TBD on inspection.
- Identify the store/venue field on each event row (likely
  `event_name` + location columns from `events` table).
- Add a right-click context-menu action "📍 Open in Google Maps"
  or a small button per row.
- Build URL: `https://www.google.com/maps/search/?api=1&query={encoded_venue_query}`.
  For best results, use the venue name + city + state if available;
  fall back to just venue name otherwise.
- Open via `QDesktopServices.openUrl(QUrl(...))` (same pattern
  as the existing Untapped deck-URL handler in ladder_meta.py).
- Confirm URL works for a handful of real entries.

---

## Backlog (lower priority, defer if needed)

- 5c Lute archetype seed in archetypes.py (~20min)
- Tokyo Prowess canonical SB plans for missing matchups (~45min)
- EV vs Field projection refresh + baseline check (~30min)
- Damage breakdown per source (~45min)
- Cards-played-on-curve analysis (~45-60min)
- Visual board replay viewer (6-10h, deferred until post-RC)

---

## Sub-project menu (per harness/SUBPROJECTS.md)

If user pivots away from mtg-meta-analyzer:
- mtg-sim — Phase 3.5 Stages D-K (no event pressure)
- harness — skill-system spec, 15d stale
- APLs — Pioneer L1 backlog
- website — Latent
- calibration — Stable

---

## Standing-by note

Per Rule 7 of SPEC-FIRST EXECUTION PROTOCOL: after each chain item,
surface options (continue / pivot / take a break / drift-detect
snapshot). User decides. 13 days to RC DC.
