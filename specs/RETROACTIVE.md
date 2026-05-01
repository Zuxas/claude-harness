# harness/specs/RETROACTIVE.md
# Created: 2026-04-27
# Purpose: capture the specs from the 2026-04-26/2026-04-27 mtg-sim
# session retroactively, since this specs/ directory didn't exist yet
# when those commits landed.

These specs landed without persistent files. Recording them here so
future sessions can see the pattern + reference the work.

Each entry has:
- Commit hash
- Date
- Spec summary (what the actual work was)
- Status: SHIPPED (all of these landed)
- Findings doc link

## 1e55791 -- Stage 1.6 APL state isolation (PARTIAL)
**Date:** 2026-04-26 morning
**Findings doc:** `harness/knowledge/tech/perf-within-matchup-parallelism-2026-04-26.md`
**Spec summary:** Per-game-mutable APL fields (BorosEnergy: `_cat_died_this_turn`,
`_treasures`, `_gained_life_this_turn`, `_tokens_entered_this_turn`,
`_roles_computed`) leaked between games. Fix: instantiate fresh APL per game in
`run_match_set`. Combined with Stage 1.5's Card deepcopy. Stage 1.7 (event_bus
suspected as third mutation source) remains fresh-session work.

## 7e213ea -- Foundation fix (load-bearing WIP committed)
**Date:** 2026-04-26 morning
**Findings doc:** `harness/knowledge/tech/load-bearing-wip-2026-04-26.md`
**Spec summary:** `engine/game_state.py:1097` imported `on_landfall` from
uncommitted `engine/card_effects.py` WIP. Stashing engine WIP crashed goldfish.
Committed 3 load-bearing files (card_effects.py, match_engine.py,
effect_primitives.py = ~903 lines). New canonical baseline T4.62 (was T4.45)
due to landfall trigger dispatch + ETB effects + spell-resolve handlers
beginning to fire correctly.

## 0c0f42c -- Engine script support
**Date:** 2026-04-26 morning
**Spec summary:** Companion commit to 7e213ea. Committed auto_handlers.py +
effect_family_registry.py (~295 lines). Required for the foundation files to
load.

## d14aa27 -- Re-baseline T4.62
**Date:** 2026-04-26 morning
**Spec summary:** Documentation commit that locked in the post-foundation-fix
baseline. ARCHITECTURE.md gauntlet entries updated.

## 5801804 -- sleeve_check.py tooling
**Date:** 2026-04-26 morning
**Spec summary:** New script `scripts/sleeve_check.py` for variant-vs-canonical
goldfish + gauntlet readout. `--gauntlet` flag runs both gauntlets, formatted
output, copy-to-clipboard.

## 8fc9b82 -- Voice + Guide double-firing fix
**Date:** 2026-04-26 morning
**Findings doc:** `harness/knowledge/tech/double-firing-handler-bugs-2026-04-26.md`
**Spec summary:** Two double-firing bugs in BE APL surfaced by Block 2 audit
+ Diagnostic E:
1. Voice Mobilize: APL handler added 2 dmg per Voice attack on top of engine
   combat-damage-step counting (4 dmg per Voice instead of 2).
2. Guide ETB: APL `_fire_guide_etb_trigger` added +1 life/energy per Guide on
   every ETB on top of engine `_apply_existing_board_etb` already firing the
   same trigger (2x life/energy per Guide ETB).
Fixed by deferring to engine handlers. Canonical T4.62 -> T4.72, variant
T4.33 -> T4.40, variant edge -0.29 -> -0.32 turn.

## 3d25a3d -- BE Modern gauntlet re-baseline post-Voice+Guide-fix
**Date:** 2026-04-26 morning
**Spec summary:** First real use of sleeve_check.py --gauntlet. 1k canonical
Modern: 71.7% (was 71.1% pre-fix). 1k variant Modern: 83.1% (was 82.5%).
Variant edge: +11.4pp -> +11.4pp (held). Surprising +0.6pp uniform shift led
to Diagnostic B which surfaced match-runner combat gap.

## f715c18 -- Match-runner combat-trigger gap surfaced
**Date:** 2026-04-26 morning
**Findings doc:** `harness/knowledge/tech/match-runner-combat-gap-2026-04-26.md`
**Spec summary:** Documentation commit. Diagnostic B confirmed engine ETBs fire
correctly in match mode but match-runner skips `main_phase2` + combat triggers
entirely. Fresh-session fix scoped at ~2.5-3.5 hours, three phases.

## a31f360 -- Phase 1 main_phase2 wiring
**Date:** 2026-04-26 morning
**Spec summary:** Wired `apl.main_phase2(view)` into match-runner via
`_run_post_combat_phase` helper. Mono Red gauntlet matchup corrected
99.9% -> 58.3% (artifact removed -- pre-fix Mono Red was creature-only goldfish
with burn package dead). Canonical 1k Modern 71.7% -> 69.1%. Variant edge over
canonical GREW +11.4pp -> +13.7pp.

## 61158bb -- Doc layers refresh
**Date:** 2026-04-27 morning
**Spec summary:** MASTERPLAN.md prepended CURRENT STATE section (preserved
2026-04-09 historical content). TODO.md prepended Active Priorities (marked
2026-04-23 MVP work as SUPERSEDED). ARCHITECTURE.md header date refreshed +
KNOWN ISSUES updated. Note: TODO.md WIP from earlier in session was discarded
by `git checkout --` during orphan-triage decision; not recoverable.

## 9721329 -- Phase 4 turn-order asymmetry fix
**Date:** 2026-04-27 morning
**Spec summary:** Two compounding bugs in `run_match`'s turn loop:
1. A always acted first per loop iteration regardless of on_play
2. B always drew on T1 regardless of on_play
Fixed by extracting `_run_player_turn` helper and refactoring loop to respect
on_play. BE mirror 57.4% -> 51.3%, Murktide mirror 55.6% -> 51.0%.
Canonical 1k 69.1% -> 68.4%. Variant 1k 82.8% -> 79.4%. Variant edge
contracted +13.7pp -> +11.0pp.

## 362b04c -- Canonical-deck registry alignment
**Date:** 2026-04-27 morning
**Findings doc:** `harness/knowledge/tech/canonical-deck-mismatch-2026-04-27.md`
**Spec summary:** "boros_energy" registry resolved to `data.stub_decks` (auto-
generated tournament scrape with phantom card "Static Prison" + zero sideboard)
NOT `decks/boros_energy_modern.txt` (hand-curated 75 with full SB). All session
measurements pre-362b04c were against the stub. Repointed registry. New
canonical: 100% WR, T4.50 (faster than stub T4.72 because stub had 3x dead-in-
goldfish Static Prison), 53.4% T4 share, 66.0% 1k Modern. Variant edge over
corrected canonical: +11.9pp.

## d05b918 -- Stub deck cleanup
**Date:** 2026-04-27 morning
**Spec summary:** Removed orphaned `boros_energy` entry from `data/stub_decks.py`
with explanatory comment.

## 972de04 -- Phase 3 keyword-aware combat (PARTIAL -- superseded by Phase 3.5)
**Date:** 2026-04-27 morning
**Spec summary:** Wrote keyword-aware `_resolve_combat`. Covered FLYING/REACH
(blocking), FIRST_STRIKE/DOUBLE_STRIKE (damage steps), DEATHTOUCH, LIFELINK
(attacker only), TRAMPLE, INDESTRUCTIBLE. **PARTIAL coverage -- superseded
by Phase 3.5 spec which covers all 42 keyword effects.**
Canonical 1k 65.6% (was 66.0%, -0.4pp). Variant 1k 78.4% (was 77.9%, +0.5pp).
Variant edge: +11.9pp -> +12.8pp. Notable: Variant Murktide 79.0% -> 69.1%
(Murktide Regent flying now properly unblockable).

---

## Lessons codified post-session

These are the patterns that emerged from running the session and are now
encoded in the spec template + CLAUDE.md:

1. **Spec-first execution.** Every commit started with a spec from Claude
   (in chat); now those go to harness/specs/ as files BEFORE Claude Code
   starts.

2. **Validation gates between stages.** Numeric thresholds with stop
   conditions caught issues mid-execution multiple times (Phase 1's Mono Red
   shift was outside the predicted direction; surfaced via stop condition,
   reframed as cleaner-than-expected fix).

3. **Findings docs as durable architectural memory.** Every architectural
   finding (load-bearing WIP, double-firing handlers, match-runner combat gap,
   canonical-deck mismatch) got a doc with discovery context, root cause,
   resolution, and remaining triage. Future sessions can reference these
   instead of re-deriving.

4. **No deferrals as escape hatches.** "Skip X because not BE-relevant" or
   "defer to fresh session" caused rework when X turned out to matter.
   Phase 3.5 spec explicitly forbids this pattern: every keyword fires or
   it's annotated with a concrete fix.

5. **Annotated imperfections beat silent gaps.** When 100% isn't reachable
   in one shot (rare), document the specific edge case + concrete next-session
   fix in IMPERFECTIONS.md. Future work picks up exactly where this work left
   off.

6. **Methodology caveats in numeric reporting.** When a measurement was made
   with a known limitation (e.g., the stub-canonical-vs-variant comparison),
   the limitation got documented inline so future readers wouldn't take the
   number out of context.

7. **Discipline against bedtime nudges.** When the user said "I'm not stopping
   yet," respect it. Standing-by-with-options is the correct default after
   commits land; pushing rest is the user's call, not Claude's.

8. **Real engineering > theatrical productivity.** 14 commits with discipline
   beat 30 commits with rework. Each commit shipped clean validation gates,
   findings docs, and follow-up specs.
