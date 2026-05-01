# Match-Runner Combat-Trigger Gap

**Date:** 2026-04-26 morning (Diagnostic B follow-up)
**Status:** SURFACED, deferred for fresh-session fix

## Discovery context

Diagnostic E (commit `8fc9b82`) fixed two double-firing handler bugs:
Voice Mobilize damage and Guide ETB life/energy. Goldfish baseline
shifted by expected magnitude (+0.10 turn canonical, +0.07 variant).
1k Modern gauntlet shifted only +0.6pp uniformly -- surprising
under-shift.

Diagnostic B investigated whether engine ETBs fire in match mode.
Answer: ETBs fire correctly (`GameState` view is aliased to
`TwoPlayerGameState` fields, so `view.cast_spell` ->
`_fire_etb_triggers` fires normally). The 0.6pp uniform shift is
noise.

But the investigation surfaced a much bigger gap: the match-runner
is missing combat-trigger dispatch AND `main_phase2` entirely.

## Architecture

`engine/match_runner.run_match` flow:
- For each turn: untap, draw, `_simple_play_turn(player_a, apl_a)`
- `_simple_play_turn` calls: `match_apl.main_phase_match(view, opp_view)`
  ONLY (single phase call).
- Then `_resolve_combat(gs, "a")` computes damage via raw power sum
  vs blocker toughness. No trigger dispatch.
- Then `_simple_play_turn(gs, "b", apl_b)`. Same single-phase call.
- Then `_resolve_combat(gs, "b")`.
- Repeat next turn.

**No call to `apl.main_phase2(view)`. No call to
`apl._simulate_combat_triggers`. No call to
`apl._dispatch_special_mechanics`. No combat keyword handling**
(lifelink, first strike, double strike, trample, deathtouch, flying
vs blocker eligibility).

## What this means BE is missing in match mode

**Combat phase (entirely missing):**
- Voice of Victory Mobilize tokens + damage
- Phlage attack trigger (3 dmg + 3 life per Phlage attacking)
- Ragavan treasure generation on hit
- Ocelot lifelink → `_gained_life_this_turn` flag
- Guide of Souls attack pump (+2/+2 flying for 3 energy)
- Avatar Roku firebending (4R per attack)
- First strike / double strike / deathtouch / trample / flying
  blocker rules

**Main_phase2 (entirely missing):**
- Phlage hardcast ETB (3 dmg + 3 life)
- Phlage escape from GY (4-mana 6/6 reanimate)
- Pyromancer ETB loot (discard 2, draw 2, +Elemental tokens)
- Pyromancer GY activation (5-mana, +2 Elementals)
- Lightning Bolt face burn
- Ocelot end-step Cat tokens (the engine that snowballs BE)
- Ocelot city's blessing token copies (T2.4)
- Bombardment lethal sac (closer)
- Bombardment T2.3 pre-lethal Phlage GY-fill
- Ajani transform check + Avenger ability dispatch
- Saga casts (Roku, Kumano front faces)
- face_burn role iteration (any deck-detected burn spells)

## Implication for measurements

The 71.5% Modern gauntlet headline (commit `0bc20bf`) reflects
heavily truncated BE vs heavily truncated opponents. BE specifically
suffers from this gap because its design depends heavily on
main_phase2 sequencing + combat triggers. Decks that play out of
main_phase only (deploy haste + creature ETBs) suffer less.

Real-tournament BE is probably MORE potent than the gauntlet
suggests. The 71.5% number is a methodology floor, not a ceiling.

Variant-vs-canonical comparison still holds -- both decks share the
same simplification, both lose the same effects. Edge of +11.4pp at
1k field-weighted is robust as a relative measurement.

Goldfish numbers (T4.40 variant vs T4.72 canonical) are the more
trustworthy "how does this deck actually play" measurement, since
goldfish DOES call main_phase2 + dispatch combat triggers via
`_simulate_combat_triggers`.

## Fix scope (fresh-session work)

Two missing pieces in `engine/match_runner.run_match`:

1. **Call `apl._simulate_combat_triggers(view, num_attackers)`** before
   OR after `_resolve_combat`. Decision: probably after combat damage
   resolves, since combat triggers in real Magic happen after damage
   step.

   Issue: `_simulate_combat_triggers` is BorosEnergyAPL-specific
   (not on `BaseAPL`). Other APLs may have their own combat-trigger
   methods or none at all. Need an APL-method protocol.

2. **Call `apl.main_phase2(view)` AFTER `_resolve_combat`** resolves.
   This fires all main_phase2 work (Phlage hardcast/escape, Ocelot
   end-step, Bombardment finish, etc.).

   Issue: not all match APLs have main_phase2 hooks; some only have
   `main_phase_match`. Need to either:
   - (a) add `main_phase2_match` to MatchAPL protocol
   - (b) call `apl.main_phase2(view)` when present, fall back to
         no-op when absent
   - (c) require all match APLs to call `_simulate_combat_triggers`
         + `main_phase2` themselves from `main_phase_match`

   Path (b) is least invasive. Adapter pattern.

3. **Engine combat keywords** (first strike, lifelink, etc.) need
   wiring into `_resolve_combat`. The goldfish `_do_combat` already
   handles these; could refactor to share a combat resolver between
   goldfish and match modes. Bigger architectural change.

## Estimated effort

**Phase 1:** wire main_phase2 into match-runner. ~30-45 min. Validate
that other APLs don't break (they should be no-op if they don't have
a main_phase2 method).

**Phase 2:** wire combat triggers. ~45-60 min. Add a
`combat_triggers()` protocol method on `BaseAPL` that dispatches the
combat-phase SPECIAL_MECHANICS handlers. BE already has
`_simulate_combat_triggers` -- just rename and standardize.

**Phase 3:** combat keywords (lifelink, first strike, etc.) in
`_resolve_combat`. ~60-90 min. Refactor to share resolver with
goldfish `_do_combat`.

Total: 2.5-3.5 hours. Real fresh-session arc. Re-baseline gauntlets
after each phase to measure impact.

## Re-baseline expectations

Phase 1 alone (main_phase2 wired): BE gauntlet probably +5-10pp
(Phlage hardcast cycles, Ocelot snowball, Bombardment lethal finally
fire). 71.5% -> 76-81%? Speculative.

All phases: gauntlet would converge toward goldfish-on-goldfish
equivalent for BE. Closest matchups (Eldrazi Ramp 49.2%) would shift
most.

## Affected commits

All Modern gauntlet measurements in tonight's session and earlier:
- `0bc20bf`: 100k 71.5%
- `ea5e196`: 1k 71.1%
- `29f528d`: variant 1k 82.5% (subsequent re-runs)
- `3d25a3d`: 1k 71.7% canonical, 83.1% variant (latest)
- 2026-04-09 100k baseline 65.3%

None of these need re-running tonight. Variant edge holds. Sleeve-up
read unchanged.

## Phase 1 implementation (2026-04-26 morning)

**Status:** SHIPPED at commit (see git log).

**Implementation:** new `_run_post_combat_phase` helper in
`match_runner.py` called after each player's combat damage
application. Builds GameState view aliasing `TwoPlayerGameState`
fields, seeds `view.damage_dealt` + `view.life`, dispatches
`main_phase2_match` -> `main_phase2` -> no-op fallback chain, syncs
back to gs.

**Caveats (Phase 2/3 fixes):**
- `view.mana_pool` resets fresh per call (over-inflates main_phase2
  mana availability)
- `view.energy` resets to 0 (loses pre-existing energy from
  main_phase)
- Combat triggers still missing (Voice/Phlage attack triggers,
  Ragavan treasures, Guide attack pump, Ocelot lifelink, Avatar Roku
  firebending) -- Phase 2
- Combat keywords still raw power calc (first strike, lifelink,
  deathtouch) -- Phase 3
- APL flag persistence works (flags live on APL instance, not view)

### Empirical results

**Per-matchup gauntlet shifts (canonical 1k seed=42):**

| Opponent         | Pre     | Post    | Delta    |
|------------------|---------|---------|----------|
| Mono Red Aggro   | 99.9%   | 58.3%   | **-41.6pp**  |
| Eldrazi Tron     | 79.2%   | 80.5%   |  +1.3pp  |
| Domain Zoo       | 96.5%   | 95.9%   |  -0.6pp  |
| Izzet Affinity   | 99.1%   | 99.0%   |  -0.1pp  |
| Izzet Prowess    | 57.3%   | 56.5%   |  -0.8pp  |
| Jeskai Blink     | 65.4%   | 65.8%   |  +0.4pp  |
| (DB-cached)      | unchanged                    |

**Field-weighted: 71.7% -> 69.1% (-2.6pp).**

**Variant gauntlet shifts (1k seed=42):**

| Opponent         | Pre     | Post    | Delta    |
|------------------|---------|---------|----------|
| Mono Red Aggro   | 99.9%   | 65.9%   | -34.0pp  |
| Eldrazi Ramp     | 64.5%   | 90.5%   | **+26.0pp**  |
| Boros mirror     | 74.3%   | 70.7%   |  -3.6pp  |
| Murktide         | 86.9%   | 86.0%   |  -0.9pp  |
| Others           | held within +/-1pp           |

**Field-weighted: 83.1% -> 82.8% (-0.3pp).**

**Variant edge over canonical: +11.4pp -> +13.7pp (GREW +2.3pp).**

The Mono Red shift is the headline finding: pre-Phase-1, MonoRedAPL
deployed creatures via `main_phase_match` but `main_phase2` (where
Lightning Bolt, Lava Spike, Searing Blaze fire) was never called.
Mono Red was effectively a creature-only goldfish racing BE, which
BE auto-wins. Post-fix, Mono Red deploys real burn damage and the
matchup becomes a real race.

The Eldrazi Ramp shift on variant (but not canonical, which is
DB-cached) shows variant's redundant 3-mana threats (Voice + Phlage
+ Pyromancer) winning close races once Phlage hardcast face damage
and Bombardment lethal sac can finally fire.

**Cross-matchup pattern:**
- Burn-reliant decks shifted: Mono Red has main_phase2 face damage
- Creature-deployment decks held: Affinity/Zoo/Tron rely on
  main_phase combat, no major main_phase2 face pressure
- Counterspell/draw decks held: Murktide/Blink main_phase2 is
  reactive, not face-pressing

This is the cleanest possible validation that the match-runner gap
was real and material.

### Mirror asymmetry finding (incidental)

BE mirror smoke test n=1000: 57.4% A wins.
Murktide mirror n=500: 55.6% A wins.

Two different APLs land within 1.8pp of each other in mirror
matches, both above 55%, indicating structural turn-order priority
in `run_match`: Player A's main_phase + combat + win check fires
BEFORE Player B's same sequence each turn. When both players race
to 20 damage, Player A wins ties from acting first. Pre-existing,
independent of Phase 1.

Cleanest fix: simultaneous turn-end win check, or split damage/
win-check into a separate beat AFTER both players resolve combat.
~30-45 min fresh-session work. Track as Phase 4 (after combat
keywords).

Effect on aggregate measurements: ~3pp inflation on Player A's
field-weighted gauntlet number for fast aggro decks. BE Modern
69.1% headline includes this; cleanest interpretation is "BE
field-weighted is somewhere in 65-69%" until fixed.

Phase 2 (combat trigger dispatch) and Phase 3 (combat keywords +
mana persistence) remain fresh-session work.

## Phase 4 implementation (2026-04-27 morning)

**Status:** SHIPPED.

Pre-Phase-4: `run_match`'s turn loop had A always acting first per
loop iteration AND B always drawing on T1 regardless of `on_play`.
Compounded into structural ~6pp player-A advantage in mirrors
(BE 57.4% / Murktide 55.6%). Phase 4 surfaced incidentally during
Phase 1 mirror smoke tests.

**Implementation:** extracted `_run_player_turn` helper from inline
turn handling (draw / main / combat / main2 / win-check). Refactored
loop to determine first/second player based on `on_play` and call
helper twice with correct skip-draw flag (T1-first-player skips
draw per Magic rules).

**Validation:**
- Goldfish path bit-identical (T4.72 canonical, T4.40 variant)
- BE mirror n=1000: 57.4% -> 51.3% (within +/-3.1pp of 50% null)
- Murktide mirror n=500: 55.6% -> 51.0% (within +/-4.4pp of 50%)
- Cross-deck convergence confirms structural fix, not deck-specific

**Empirical gauntlet results (1k seed=42):**

| Deck      | Pre-Phase-4 | Post-Phase-4 | Delta   |
|-----------|-------------|--------------|---------|
| Canonical | 69.1%       | **68.4%**    | -0.7pp  |
| Variant   | 82.8%       | **79.4%**    | -3.4pp  |
| Edge      | +13.7pp     | **+11.0pp**  | -2.7pp  |

Canonical shift is small because most canonical matchups are
DB-cached (no sim re-run). Variant shift is bigger because all 15
variant matchups are sim-source (no DB cache for variant deck name);
Phase 4's correction applied broadly.

Notable per-matchup shifts (sim-source, both decks):
- **Mono Red Aggro**: canonical 58.3% -> 47.8% (-10.5pp), variant
  65.9% -> 55.2% (-10.7pp). Mono Red was always apl_b and previously
  disadvantaged by always-second turn order; now fairly alternates.
- **Boros mirror (variant only)**: 70.7% -> 61.5% (-9.2pp). Variant
  was previously over-rated against canonical via player-A bonus.
- **Dimir Murktide (variant)**: 86.0% -> 78.7% (-7.3pp).
- **Eldrazi Ramp (variant)**: 90.5% -> 85.1% (-5.4pp).

Sleeve-up read for variant Jermey: still meaningfully faster
(goldfish T0.32 + gauntlet +11pp), but the +13.7pp post-Phase-1
inflation has been corrected to a more honest +11.0pp.

Phase 2 (combat trigger dispatch) and Phase 3 (combat keywords +
mana persistence) remain the only outstanding match-runner phases.

## Phase 2 investigation (2026-04-27 morning)

**Status:** NO-OP -- work already shipped via Phase 1.

Phase 2 was originally specced as wiring `_simulate_combat_triggers`
into match-runner so Phlage attack trigger, Ragavan treasures, Guide
attack pump, Avatar Roku firebending fire in match mode.

Investigation found these triggers ALREADY fire post-Phase-1.
Dispatch chain: Phase 1's `_run_post_combat_phase` calls
`apl.main_phase2(view)`, and BE's `main_phase2` already invokes
`_simulate_combat_triggers`, which dispatches all combat-phase
SPECIAL_MECHANICS handlers via `_dispatch_special_mechanics('combat')`.

**Trace verification (50 games BE-vs-Murktide post-Phase-4):**
- Phlage attack trigger fired 55x
- Ragavan treasure trigger fired 54x
- Voice Mobilize fired 87x
- Ocelot lifelink fired 29x

Phase 2 needs no implementation. Phase 3 (combat keywords -- first
strike, lifelink-as-keyword, deathtouch, trample, flying-vs-blocker
rules) remains the only outstanding match-runner phase that needs
real engineering.

**Bonus finding from this investigation:** the "Boros Energy"
registry key resolves to `data.stub_decks` not to
`decks/boros_energy_modern.txt`. The two decks differ materially
(stub has 3x Voice + 3x Static Prison; .txt has Roku MB + Blood Moon
+ RangerCap). All tonight's "canonical" measurements were against
the stub. See `canonical-deck-mismatch-2026-04-27.md` for full diff
and decision options.

## Phase 3 implementation (2026-04-27)

**Status:** SHIPPED. Closes the match-runner combat-gap arc.

**Path chosen:** Path B (port keyword logic directly into match-
runner `_resolve_combat`). Path A (extract goldfish helper) ruled
out -- goldfish `_do_combat` is 200 lines tangled with card-specific
attack triggers, only 50 lines are keyword logic, and goldfish has
no blockers (different problem). Path C (use `engine/combat.py`)
ruled out -- that file is a tournament-data stub simulator with no
keyword logic.

**Implementation:** rewrote `_resolve_combat` (~50 lines -> ~110
lines) with:
- Flying/Reach blocking restriction in blocker assignment
- First-strike + double-strike resolved as two damage sub-steps
- Deathtouch (any damage = lethal to blocker)
- Lifelink (attacking player gains life equal to attacker damage;
  bounded by trample math when present)
- Trample (excess damage over blocker toughness goes to player)
- Indestructible (skipped in death tracking)
- Vigilance no-op (match-runner doesn't model tap state)
- Menace deferred (not BE-relevant)

Signature change: `(damage, atk_losses, blk_losses)` ->
`(damage, atk_losses, blk_losses, lifelink_gain)`. Both callers
(`_run_player_turn`, `_run_match_with_combo`) updated to apply
lifelink to attacker's life total.

**Validation gates (all passed):**

| Metric              | Pre-Phase-3 | Post-Phase-3 |
|---------------------|-------------|--------------|
| Canonical goldfish  | T4.50       | T4.50        |
| BE mirror n=1000    | 51.3%       | **49.4%**    |
| Murktide mirror n=500 | 51.0%     | **54.2%**    |
| Canonical 1k Modern | 66.0%       | **65.6%**    |
| Variant 1k Modern   | 77.9%       | **78.4%**    |
| Variant edge        | +11.9pp     | **+12.8pp**  |

**Notable per-matchup shift:** Variant vs Dimir Murktide 79.0% ->
69.1% (-9.9pp). Murktide Regent (6/6 Flying) now correctly requires
flying/reach to block; BE has zero flyers/reach so Regent is
effectively unblockable. Real keyword-driven matchup correction.

Other shifts within +/-2pp -- Phase 3's keyword effects don't
dramatically change BE-vs-field because BE's lifelink/first-strike
abilities mostly fire via APL handler dispatch
(`_gained_life_this_turn` flag for Ocelot, etc.), not via the
keyword-tag system in `_resolve_combat`.

**Known limitation:** blocker lifelink not tracked (only attacker
lifelink applied to attacker's life). Asymmetric across all decks,
so doesn't bias variant-vs-canonical comparison. Defer for fresh
session if matters.

**Match-runner combat-gap arc COMPLETE.** All four phases shipped:
- Phase 1 (commit a31f360): main_phase2 wired
- Phase 2 (no-op): work covered by Phase 1's dispatch chain
- Phase 3 (this commit): combat keywords
- Phase 4 (commit 9721329): turn-order asymmetry fixed

## Phase 3.5 Stage A implementation (2026-04-27)

**Status:** SHIPPED. Block-eligibility full coverage.

**Spec:** `harness/specs/2026-04-27-phase-3.5-stage-a-block-eligibility.md`

**Scope:** wired remaining 6 evasion keywords into match-runner
`_resolve_combat`: MENACE, UNBLOCKABLE, SHADOW, HORSEMANSHIP, FEAR,
INTIMIDATE. Phase 3 covered FLYING + REACH only. Stage A's data-
structure refactor (assignments dict from `id(atk) -> blk` to
`id(atk) -> list[blk]`) is the foundation for Stage B's blocker-side
lifelink iteration.

**New helper:** `_legal_blockers(atk, blockers)` -- per-attacker
filter based on evasion keywords. Single source of truth for
block-eligibility.

**Mid-execution amendments:**
- **Amendment 1 (bug fix):** Stage A first-pass had per-blocker
  death check on attacker. CR 510.1 says blocker damage SUMS on
  the attacker before lethality check. Two 2/2s vs 3/4 menace
  attacker should kill it (4 >= 4). Pre-fix code kept it alive.
  Hidden in BE/Murktide mirrors (no menace creatures). Fix:
  restructured `_resolve_strike_step` per-attacker block into two
  sequential passes over `live_blockers` -- Pass 1 accumulates
  total damage to attacker + deathtouch flag, applies combined
  death check; Pass 2 keeps existing per-blocker damage assignment
  from attacker (lifelink + trample math unchanged).
- **Amendment 2:** A.4 spot-check (BE vs Rakdos with menace) downgraded
  to IMPERFECTIONS entry -- Rakdos Aggro not in registered 14-deck
  Modern gauntlet. Synthetic test deferred to fresh-session work.
- **Amendment 3:** BE mirror gate re-run at n=2000 (CI ±2.2pp) after
  first-pass at n=1000 hit 46.3% (just below 47% acceptance floor,
  consistent with sample noise per overlap of CIs). n=2000 result
  49.6% confirmed sample noise.

**Validation results (all gates passed):**

| Gate | Pre-Stage-A | Post-Stage-A | Acceptance |
|---|---|---|---|
| A.1 Goldfish | T4.50 | T4.50 | bit-identical ✓ |
| A.2 BE mirror n=2000 | 49.4% (n=1k) | 49.6% | 47-54% ✓ |
| A.3 Murktide mirror n=1000 | 54.2% (n=500) | 51.5% | 45-55% ✓ |
| A.4 Canonical 1k Modern | 65.6% | 65.8% | 60-70% ✓ |
| A.5 Variant 1k Modern | 78.4% | 77.8% | within ±5pp ✓ |

**Variant edge:** +12.8pp -> +12.0pp (-0.8pp narrowed).

**Notable per-matchup canonical shift:** Eldrazi Tron 68.0% -> 71.2%
(+3.2pp). Stage A's two-pass combat math benefits BE-vs-large-creature
matchups -- under the per-blocker bug, BE blockers contributing damage
to large attackers had each contribution checked individually; Pass-1
accumulation now correctly sums BE blocker damage when 2 blockers
gang up on a Walking Ballista or Devoted Druid.

**Open imperfection (logged in `harness/IMPERFECTIONS.md`):**
- Menace damage accumulation untested empirically in 14-deck gauntlet
  (no menace creatures in field). Synthetic test deferred.

**Stage B next:** combat modifiers + tap-state for vigilance + haste
filter fix + DEFENDER + blocker-side LIFELINK activation (uses
Stage A's list-of-blockers structure).

## Phase 3.5 Stage B implementation (2026-04-27)

**Status:** SHIPPED.

**Spec:** `harness/specs/2026-04-27-phase-3.5-stage-b-combat-modifiers.md`

**Scope:** 4 combat-modifier keyword effects:
- HASTE filter fix (D9): attacker filter ORs with `KWTag.HASTE` so
  Ragavan cast T1 attacks T1
- DEFENDER filter (D7): excluded from attackers
- VIGILANCE tap-state (D8): `tapped_from_attack` flag, set after
  attack unless vigilant, cleared at start of each player's turn,
  filters blocker selection
- Blocker-side LIFELINK (D4 completion): Stage A's `pass` activated
  via `defender_lifelink_gain` accumulator threaded through 5-tuple
  return + both callers

**Validation results (n=1000 unless noted):**

| Gate | Pre-Stage-B | Post-Stage-B | Acceptance |
|---|---|---|---|
| B.1 Goldfish | T4.50 | T4.50 | bit-identical ✓ |
| B.2 BE mirror n=2000 | 49.6% | 49.1% | 47-54% ✓ |
| B.3 Murktide mirror n=1000 | 51.5% | 50.6% | 45-55% ✓ |
| B.4 Canonical 1k Modern | 65.8% | 65.3% | 65-69% (in band, see Amendment 4) |
| B.5 Variant 1k Modern | 77.8% | 78.2% | within ±5pp ✓ |

**Variant edge:** +12.0pp -> +12.9pp (GREW +0.9pp).

**Notable per-matchup canonical:** Mono Red 52.8% -> 46.3% (-6.5pp).
**Honest model correction, not regression.** Mechanical verification:
Mono Red Modern has 8 HASTE creatures (4 Goblin Guide + 4 Monastery
Swiftspear) vs BE's 4 (Ragavan only). Symmetric haste-fix favors
Mono Red proportionally to its 2x haste density. Pre-Stage-B
Mono Red was over-rated for BE because Mono Red's T1 hastes couldn't
attack either.

**Methodology lesson (Amendment 4):** future stage specs must predict
per-matchup shifts accounting for keyword density asymmetry across
decks AND SIM-vs-DB source per matchup. Direction-of-shift stop
conditions based on BE-side keyword count alone produce false
positives when symmetric fix benefits opponents more.

**B.6 spot check (Eldrazi Ramp) resolution:** canonical held at 49.2%
because matchup is DB-cached, not sim-source. Variant Eldrazi Ramp
at 91.9% [SIM] confirms engine working -- variant runs through the
engine path while canonical pulls from DB cache.

**Stage C next:** protection cluster (HEXPROOF/WARD/PROTECTION/
SHROUD). Highest-risk stage of Phase 3.5 per spec -- requires APL
targeting integration across ~15 hand-tuned APLs. Sub-commits within
the stage. Best done with full focus in fresh session.
