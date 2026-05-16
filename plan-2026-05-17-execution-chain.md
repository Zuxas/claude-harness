# Execution Chain — 2026-05-17 (Sunday)

**Authored:** 2026-05-15 evening (after the 5/16 chain shipped same-day)
**Days to RC DC:** 12
**Total estimate:** 4-6h focused

The 5/16 staged chain landed today (5/15) instead of tomorrow:
crash logger, thread audit (4 real bugs), 3 responsiveness hot spots,
and the transparent matchup overlay end-to-end with 13 features.
That puts us a day ahead. Tomorrow's chain is lighter and more about
durability + missing data than new features.

---

## Section 0 — Session start (15min)

Per `harness/CLAUDE.md` SESSION START PROTOCOL:

1. Read `harness/state/latest-snapshot.md`.
2. Read `harness/inbox/drift-pr--2026-05-17.md` if present.
3. Read `harness/MEMORY.md` — 2026-05-15 evening entry (the
   shipped-same-day overlay run).
4. Check `harness/IMPERFECTIONS.md`.
5. Run DAILY RHYTHM CHECK below.

---

## Section 1 — Real-MTGA endurance test (1-2h)

**Goal:** put miles on the overlay before it ships to RC DC. Crash
logger from 5/15 should now catch anything that fires.

### Tasks

- [ ] Launch GUI; verify auto-sync prints `[auto-sync] N matches`.
- [ ] Press Ctrl+Shift+M while MTGA has focus → overlay appears
      middle-right.
- [ ] Play 5-10 ranked Bo3 matches end to end.
- [ ] After each match, verify within 30s:
  - Overlay refreshes with the new opponent
  - Match History sub-tab gets the new row
  - Per-game stats / SB plan / opening hand all populated
  - Watch Replay popup opens with the transcript
- [ ] During a match, alt-tab to Chrome → overlay hides; alt-tab back
      → overlay re-appears. Repeat 5+ times.
- [ ] Cycle compact ↔ full a few times during sideboarding.
- [ ] Switch matchup dropdown manually to preview a different plan.
- [ ] At end of session, check `logs/gui_crash_*.log` and
      `logs/qt_msgs_*.log` for anything new. Triage each as
      "fix on the spot" / "open IMPERFECTION" / "ignore as cosmetic".

---

## Section 2 — Single-instance enforcement (30min)

**Goal:** prevent the zombie-process accumulation we saw yesterday
(4 leftover python processes). Use `QLockFile` with stale-lock detection
so a second `python run_gui.py` invocation refuses to start (or wakes
the existing instance).

### Tasks

- [ ] At top of `run_gui.py:main()`, before `QApplication`:
  ```python
  from PyQt6.QtCore import QLockFile, QStandardPaths
  import tempfile, os
  lock_path = os.path.join(tempfile.gettempdir(), "mtg-meta-analyzer.lock")
  lock = QLockFile(lock_path)
  lock.setStaleLockTime(30 * 1000)  # 30s
  if not lock.tryLock(100):
      print("MTG Meta Analyzer is already running. Check the system tray.")
      sys.exit(0)
  ```
- [ ] Verify with two consecutive `python run_gui.py` -- second
      should print and exit.
- [ ] Stop existing GUI; relaunch -- single instance OK.

---

## Section 3 — Google Maps deeplink for events (30-45min)

**Goal:** deferred from 5/16. Right-click an event in My Events →
opens Google Maps to the venue.

### Tasks

- [ ] Find the event-row context-menu handler in
      `gui/tabs/event_finder_tab.py` or `gui/tabs/event_hub_tab.py`.
- [ ] Add action `📍 Open venue in Google Maps`.
- [ ] URL: `https://www.google.com/maps/search/?api=1&query=<urlencoded>`
- [ ] Skip / grey for MTGO online events.
- [ ] Test 3 real entries.

---

## Section 4 — Missing Tokyo SB plans (45-60min)

**Goal:** the matchup dropdown lists 17 plans, but yesterday's ranked
queue surfaced 5 archetypes with NO canonical plan: Simic Rhythm,
Boros Tremors, Gruul Aggro, 4-Color Allies, generic Azorius. Add
canonical SB plans for each so the overlay shows IN/OUT during those
matches.

### Tasks

For each of the 5 missing matchups:
- [ ] Pull recent Untapped Bo3 / Mythic decklists for the archetype
      to understand the metagame baseline build.
- [ ] Sketch Tokyo Prowess SB plan vs that archetype using the same
      shape as the 17 existing plans (play_in / play_out / draw_in /
      draw_out + notes).
- [ ] Save via My Decks → Sideboard Plans tab.
- [ ] Re-launch GUI, verify the dropdown now includes them.

---

## Section 5 — EV vs Field projection refresh (30min)

**Goal:** capture today's number after the all-formats fix +
Untapped data refresh; compare to 5/01 53.6% baseline.

### Tasks

- [ ] My Decks → Tokyo Prowess (id=17) → EV vs Field sub-tab.
- [ ] Capture headline EV %.
- [ ] Compare against 53.6% from 5/01 baseline.
- [ ] If shifted >5pp, investigate the cause: real meta shift?
      data quality issue? Untapped wide-window pull bringing in
      stale data? Note findings in NEXT_STEPS.

---

## Section 6 — End of day (15min)

- [ ] Author `harness/plan-2026-05-18-execution-chain.md`.
- [ ] Update mtg-meta-analyzer CLAUDE.md / NEXT_STEPS / ROADMAP.
- [ ] Commit + push all repos.

---

## Backlog (defer if time runs short)

- Visual board replay viewer v0.7 (6-10h, post-RC)
- Damage breakdown per source (~45min)
- Cards-played-on-curve analysis (~45-60min)
- Hover-to-fade on overlay (low ROI; only works unlocked)
- Per-archetype overlay defaults (fiddly UX; low ROI)
- PyInstaller .exe packaging (post-RC)
- Decklist diff vs canonical SB on overlay (medium effort, useful for
  post-G1 review)

---

## Sub-project menu (per harness/SUBPROJECTS.md)

If user pivots away from mtg-meta-analyzer at the morning DAILY
RHYTHM CHECK:

- **mtg-sim** — Phase 3.5 keyword coverage Stages D-K; Standard
  match APLs (IMPERFECTION standard-apl-goldfish-only-no-match-quality).
- **harness** — skill-system spec at
  `harness/specs/2026-05-01-skill-system-harness.md` (16d stale).
- **APLs** — Pioneer L1 backlog (57 cards in waves of 8-12).
- **website** — Latent.
- **calibration** — Stable.

---

## Standing-by note

Per Rule 7 of SPEC-FIRST EXECUTION PROTOCOL: after each section,
surface options (continue / pivot / break / drift-detect snapshot).
Don't nudge.

12 days to RC DC. The big pieces are shipped. Remaining work is
durability + filling data gaps.
