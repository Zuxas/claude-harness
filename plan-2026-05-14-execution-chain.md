# Execution Chain — 2026-05-14 (Wednesday)

**Authored:** 2026-05-13 end-of-day
**Sub-project focus:** mtg-meta-analyzer (RC May 29 prep arc + GUI smoke)
**Days to RC Cincinnati:** 15

---

## Section 0 — Mandatory Session-Start (15min)

Per `harness/CLAUDE.md` SESSION START PROTOCOL:

1. Read `harness/state/latest-snapshot.md` (regenerated 04:30).
2. Read `harness/inbox/drift-pr--2026-05-14.md` if present (Gemma 04:50).
3. Read `harness/MEMORY.md` (today's full-day GUI shipping entry was added 2026-05-13).
4. Check `harness/IMPERFECTIONS.md` for new entries since 2026-05-13.
5. Run DAILY RHYTHM CHECK: present today's chain options A/B/C below; wait for user pick.

---

## Today's chain — pick one

### Option A — Full day (7-9h) — RC May 29 prep batch + GUI smoke

The right call if you have focus and the May 29 RC needs serious prep work.

1. **GUI smoke test of yesterday's Direction A ship** (~30min).
   - Launch `python run_gui.py` — verify clean startup (note: ~120ms card-registration latency expected, tracked as polish item).
   - Press **Ctrl+K** → palette opens. Verify each prefix: `>refresh`, `#dashboard`, `@izzet prowess`, `:tokyo`, `c:sheoldred`.
   - Set Dashboard timeframe to "4 weeks", switch to META tab, switch back → preserved.
   - Click Tokyo Prowess on My Decks, switch tabs and back → still selected.
   - Close app fully, relaunch → last active tab restored, Tokyo still pre-selected, Dashboard timeframe still "4 weeks".
   - From palette: `> Reset UI state` → confirm dialog → close + relaunch → defaults restored.
   - File any bugs to `harness/IMPERFECTIONS.md`. If any stop-the-world issue, that becomes priority 2 (push the rest of the chain back).

2. **Log May 11-12 RC results** (~1h). **TIME-SENSITIVE — skipped 4x already.**
   - Open Match Log tab. Log each round's match: opponent, archetype (use palette `@<name>` to find), W/L, play/draw, key cards seen, SB plan used.
   - Capture which SB plans worked / didn't. Note expected vs actual matchups.
   - This data feeds next month's RCQ + RC prep loop. Lose it now and you're flying blind.

3. **RC-realistic field model in `analysis/deck_ev.py`** (~2-3h).
   - Currently `deck_ev` uses a 14d paper-meta default. RC fields differ from MTGO (more aggro, less control, different archetype distribution).
   - Target: replace default field with a blend: recent RCQ top-8s (last 30d) weighted 0.5 + Untapped Mythic Bo3 share weighted 0.3 + paper meta 0.2.
   - New constant `RCQ_BLEND_FIELD` in `deck_ev.py`. EV vs Field sub-tab gets a "Field source" dropdown: "14d paper (current default)" / "RCQ blend (recommended for RC prep)".
   - Re-compute Tokyo Prowess EV under RCQ blend; compare to current 53.6%.

4. **Sideboard 1-page printout** for Tokyo Prowess (~2-3h).
   - Add "Print SB Reference Card" button to My Decks → Sideboard Plans sub-tab.
   - Renders the 12-matchup SB grid as a 1-page PDF (or PNG at 300dpi for printing).
   - Layout: matchup rows × IN/OUT columns, color-coded difficulty, Tokyo decklist mini-thumbnail in corner.
   - Reuse the `_summarize_notes` clip from yesterday's print fix to keep cells tight.

5. **End-of-day** (~30min) — author tomorrow's chain, update CLAUDE.md/NEXT_STEPS/ROADMAP if any new files shipped.

### Option B — Focused (~5h) — Just RC critical path

If energy is moderate. Ships the highest-leverage RC items, defers GUI smoke to a later day.

1. Section 0
2. **Smoke test ONLY the deck pre-select** on My Decks (5min — verify Tokyo Prowess loads on launch). Defer fuller palette smoke.
3. **Log May 11-12 RC results** (1h)
4. **RC-realistic field model in deck_ev.py** (2-3h)
5. End-of-day (15min)

### Option C — Conservative (~3h) — Catch up + smoke + log

If energy is low or there's external interruption (life stuff, RuneLite calls). Closes the most-decay-prone debt without committing to new code.

1. Section 0
2. **Full GUI smoke test** of yesterday's ship (30-45min) — be thorough, file imperfections
3. **Log May 11-12 RC results** (1h)
4. End-of-day (15min)

---

## Loose ends from 2026-05-13

Carry these forward in case they come up:

- **Voicemeeter startup shortcut deletion** — `Startup\Voicemeeter (VB-Audio).LNK` still exists. User deferred decision. Quick action available in any session: delete the LNK, or use Settings → Apps → Startup → Voicemeeter (VB-Audio) → Off.
- **Power plan stays on AMD Ryzen High Performance** (set 2026-05-13). If gaming feels off again, check `powercfg /getactivescheme` — Windows updates sometimes reset to Balanced.
- **Brainstorm visual-companion server** — cleaned up at end of 2026-05-13 session. If you trigger another brainstorm, `.superpowers/brainstorm/` artifacts persist between sessions per the skill's `--project-dir` flag.

---

## Open IMPERFECTIONS / spec backlog (lower priority for tomorrow)

Tracked in NEXT_STEPS.md:

- Defer card-registration in `register_card_entries` to `QTimer.singleShot(0, ...)` (~120ms startup) — small polish, do during a low-energy slot.
- Card-slug `[:60]` collision (5 known) — minor data-loss risk on recents only, fix when convenient.
- Direction C arc (design-language pass + tab reorganization) — DO NOT START YET. Plan was to wait one week of palette-recents data first (~2026-05-20). Spec authoring after that.

---

## Sub-project menu (per harness/SUBPROJECTS.md)

If user pivots away from mtg-meta-analyzer at morning DAILY RHYTHM CHECK, surface these as alternatives:

- **mtg-sim** — Phase 3.5 keyword coverage Stages D-K (no event pressure until post-RC); Standard match APLs (would unlock Standard sim matchup data).
- **harness** — Skill-system spec at `harness/specs/2026-05-01-skill-system-harness.md` (was scheduled to start 2026-05-05; never started; could pick up).
- **APLs** — Pioneer L1 backlog (57 cards, no event pressure).
- **website** — Latent. Could become a Friday-PT-watch dashboard or RC-prep memo publisher.
- **calibration** — Stable; revisits when sim quality surfaces a calibration gap.

---

## Standing-by note

Per Rule 7 of SPEC-FIRST EXECUTION PROTOCOL: after each chain item, surface options (continue / pivot / take a break / drift-detect snapshot) — do not nudge toward bedtime or toward continuing. User decides.
