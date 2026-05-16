# Execution Chain — 2026-05-16 (Saturday)

**Authored:** 2026-05-15 evening (consolidating the original 5/15, 5/16,
and 5/17 chains after the 5/16 staged work shipped same-day on 5/15)
**Days to RC DC:** 13
**Total estimate:** 5-7h focused

The original 5/16 chain (crash logger / thread audit / responsiveness /
transparent overlay) shipped today on 5/15. What's left for tomorrow is
the items the original 5/15 chain skipped (SB plan validation, gauntlet,
EV refresh), the items deferred from 5/16 (Google Maps deeplink), and
the staged 5/17 work (real-MTGA endurance, QLockFile, missing SB plans).

---

## Section 0 — Session start (15min)

Per `harness/CLAUDE.md` SESSION START PROTOCOL:

1. Read `harness/state/latest-snapshot.md`.
2. Read `harness/inbox/drift-pr--2026-05-16.md` if present.
3. Read `harness/MEMORY.md` — 2026-05-15 evening entry (the shipped-
   same-day overlay run + thread audit + responsiveness + crash logger).
4. Check `harness/IMPERFECTIONS.md`.
5. Run DAILY RHYTHM CHECK below.

---

## Section 1 — Real-MTGA endurance test (1-2h)

**Goal:** put miles on the overlay before RC DC. Several fixes landed
yesterday evening AFTER the last user smoke pass: force-quit rewrite,
horizontal-compact revert, click-pip-expand, UIState truncating writes,
pre-push hook README skip-list. None of those were user-verified in
real MTGA — only headless Qt smoke. Crash logger should now catch
anything that fires.

### Tasks

- [ ] Launch GUI; verify auto-sync prints `[auto-sync] N matches`.
- [ ] Verify only ONE python process is alive in Task Manager (no
      zombies from yesterday's session).
- [ ] Press Ctrl+Shift+M while MTGA has focus → overlay appears
      middle-right.
- [ ] Press Ctrl+Shift+Q with analyzer focused → process exits cleanly
      (no zombie in Task Manager). The local QShortcut fallback is what
      should fire here since Win32 global registration is likely failing
      to claim Ctrl+Shift+Q (Discord / NVIDIA / etc. has it).
- [ ] Re-launch. Press Ctrl+Shift+Q while MTGA has focus → does
      anything happen? Expected: NO (global registration is blocked).
      If it works → great, the global path is open on your box.
- [ ] Play 5-10 ranked Bo3 matches end to end. After each match:
  - Overlay refreshes within 30s with the new opponent
  - Match History sub-tab gets the new row
  - Per-game stats / SB plan / opening hand all populated
  - Watch Replay popup opens with the transcript
- [ ] During matches, alt-tab to Chrome → overlay hides; alt-tab back
      → overlay re-appears. Repeat 5+ times.
- [ ] Cycle compact ↔ full during sideboarding. Click the compact pip
      anywhere → expand back.
- [ ] Switch matchup dropdown manually to preview a different plan.
- [ ] At end of session, check `logs/gui_crash_*.log` and
      `logs/qt_msgs_*.log`. Triage each as "fix on the spot" /
      "open IMPERFECTION" / "ignore as cosmetic".

---

## Section 2 — Tokyo Prowess SB plan validation (1-1.5h)

**Goal:** the original 5/15 chain wanted this; we pulled the data
earlier today but never closed the loop with team-canonical edits.

### Findings already on disk from 2026-05-15 morning data pull

- **3 matches misclassified to deck 17 (Tokyo Prowess)** but with
  cards from a different deck: m=59 vs Gruul Aggro (Dimir cards),
  m=72 vs Azorius (Esper cards), m=75 vs 4-Color Allies (empty SB).
  Need to fix `my_deck_id` on these rows.
- **Fuzzy archetype matcher gaps:** Azorius Control should match UW
  High Noon, Simic Rhythm has no canonical plan, "Deck" is too vague.
  Add a guild↔color-code lookup dict in `analysis/sb_plan_diff.py`.
- **Real canonical-vs-played divergences:**
  - m=60 vs Izzet Elementals (Izzet Prowess plan): IN 75% / OUT 38%.
    Missing IN: +1 Spell Pierce, +1 Abrade. Left Slickshots in
    (canonical wants -4 of them).
  - m=61 vs Golgari Control (Golgari Midrange plan): IN 67% / OUT 67%.
    Missed -2 Disdainful Stroke. Brought unplanned +2 Slagstorm
    +1 Bounce Off +1 Spell Pierce.

### Tasks

- [ ] **Decide on Slickshot cut discipline.** Canonical says cut all 4
      Slickshot vs control matchups; you kept 3 in vs Izzet Elementals.
      Either: (a) accept the canonical plan + adjust in-game discipline,
      OR (b) update the canonical plan to reflect what you actually want
      to do. Update `saved_sb_plans.id=53` (Izzet Prowess matchup) accordingly.
- [ ] **Decide on Golgari Slagstorm inclusion.** Canonical Golgari Midrange
      plan (id=39) doesn't include Slagstorm; you brought 2. Update plan
      or commit to skipping Slagstorm vs Golgari.
- [ ] **Fix 3 misclassified matches.** SQL:
      ```sql
      -- m=59 was probably Dimir Aggro id=18; verify by re-classifying
      UPDATE match_log SET my_deck_id = NULL WHERE id IN (59, 72, 75);
      -- Then run the orphan resolver from Match Log tab
      ```
- [ ] **Patch fuzzy archetype matcher** in
      `analysis/sb_plan_diff.py::_find_canonical_plan` — add a guild→
      color-code dict (Azorius↔UW, Simic↔UG, Dimir↔UB, Orzhov↔WB,
      Rakdos↔BR, Gruul↔RG, Selesnya↔WG, Izzet↔UR, Golgari↔BG, Boros↔WR)
      and try matching both directions before falling back to first-word.

---

## Section 3 — Single-instance enforcement (30min)

**Goal:** prevent the zombie-process accumulation we saw yesterday
(4 leftover python processes including 2 from previous-day pythonw3.13
running 18+ hours).

### Tasks

- [ ] At top of `run_gui.py:main()`, after `argparse` but before
      `QApplication`:
  ```python
  from PyQt6.QtCore import QLockFile
  import tempfile, os
  lock_path = os.path.join(tempfile.gettempdir(), "mtg-meta-analyzer.lock")
  lock = QLockFile(lock_path)
  lock.setStaleLockTime(30 * 1000)  # 30s
  if not lock.tryLock(100):
      print("MTG Meta Analyzer is already running. Check the system tray.")
      sys.exit(0)
  # Keep lock alive for the lifetime of the process
  _lock_keeper = lock  # bind to module-level so GC doesn't release it
  ```
- [ ] Verify with two consecutive `python run_gui.py` — second should
      print and exit.
- [ ] Stop existing GUI; relaunch — single instance OK.
- [ ] Optional polish: if user double-clicks the launcher and a previous
      instance exists, send a Win32 message to the existing instance to
      bring its window to focus instead of just exiting silently.

---

## Section 4 — Google Maps deeplink for events (30-45min)

**Goal:** deferred from 5/16. Right-click an event in My Events →
opens Google Maps to the venue.

### Tasks

- [ ] Find the event-row context-menu handler in
      `gui/tabs/event_finder_tab.py` or `gui/tabs/event_hub_tab.py`.
      Ask the user if ambiguous.
- [ ] Add action `📍 Open venue in Google Maps`.
- [ ] URL builder:
  ```python
  import urllib.parse
  from PyQt6.QtGui import QDesktopServices
  from PyQt6.QtCore import QUrl

  def open_event_in_maps(event_name: str, city: str = "", state: str = ""):
      parts = [p for p in (event_name, city, state) if p]
      query = " ".join(parts)
      encoded = urllib.parse.quote(query)
      url = f"https://www.google.com/maps/search/?api=1&query={encoded}"
      QDesktopServices.openUrl(QUrl(url))
  ```
- [ ] Skip / grey for MTGO online events.
- [ ] Test 3 real entries.

---

## Section 5 — Missing Tokyo SB plans (45-60min)

**Goal:** the matchup dropdown lists 17 plans, but yesterday's ranked
queue surfaced 5 archetypes with NO canonical plan: Simic Rhythm,
Boros Tremors, Gruul Aggro, 4-Color Allies, and generic Azorius (which
exists as UW High Noon but the fuzzy matcher doesn't find it -- the
Section 2 matcher patch should also help here).

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

## Section 6 — Gauntlet re-run + EV vs Field refresh (45-60min)

**Goal:** the original 5/15 chain wanted this. Now that match_log_sb_plans
captures real plans + canonical plans exist for the new matchups, the
gauntlet can be informed by data rather than blunt sideboarding.

### Tasks

- [ ] Run `python parallel_launcher.py --deck izzetprowessstandardtokyo
      --field rcdc` at N=1000. Verify the gauntlet picks up the latest
      mainboard from `saved_decks.id=17`.
- [ ] Capture the resulting FWR. Compare to the 2026-05-01 baseline
      of 68.4% canonical / 75.1% variant. Note any shift > 3pp.
- [ ] My Decks → Tokyo Prowess → EV vs Field sub-tab. Capture today's
      headline EV %. Compare to 5/01 53.6% baseline.
- [ ] If gauntlet OR EV shifted > 5pp, investigate: real meta shift?
      data quality (Untapped wide-window pull bringing stale)? Note
      findings in NEXT_STEPS.

---

## Section 7 — End of day (15min)

- [ ] Author `harness/plan-2026-05-17-execution-chain.md` (for Sunday).
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

13 days to RC DC. The big infrastructure pieces shipped on 5/15.
Tomorrow's work is durability + data-completeness + the original 5/15
plan items that got skipped when we pivoted to the 5/16 staged work.
