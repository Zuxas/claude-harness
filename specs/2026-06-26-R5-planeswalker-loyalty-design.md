---
title: R5 Planeswalker Loyalty Over Turns - PROOF + NO-REGRESSION design (READ-ONLY, for review)
status: PROPOSED
created: 2026-06-26
project: mtg-sim
estimated_time: design only (no engine code written); implementation is L (~12h+) once approved
related:
  - harness/specs/2026-06-26-modelability-ladder.md  (R5 rung -> Eldrazi/Mono-G Tron)
  - harness/specs/2026-06-26-archetype-capability-profiles.md  (the fidelity gate this feeds)
  - harness/specs/2026-06-26-R1-stack-priority-design.md  (the pattern this mirrors)
  - harness/specs/2026-06-26-R2-instant-combat-design.md  (runner-correction pattern this reuses)
  - mtg-sim-r2/modelability_proofs/r1-stack-priority-2026-06-26.json  (red-pre/green-post + bit-identical discipline)
  - mtg-sim-r2/modelability_proofs/r2-instant-combat-2026-06-26.json  (falsifier + g1_source honesty-subset discipline)
  - harness/IMPERFECTIONS.md  (planeswalker-loyalty-not-tracked L512-518; planeswalker-loyalty-inert-in-match-mode L66-72)
  - mtg-sim/engine/planeswalkers.py  (PLANESWALKER_ABILITIES registry + activate_planeswalker_ability -- REUSED, not rebuilt)
worktree: E:/vscode ai project/mtg-sim-r5  (branch: modelability/r5-planeswalker-loyalty, OFF MAIN)
branch_point_commit: 2280dced3c859c1cc001269dcb1485b706089dac  (main: "feat(ml): win-prob calibration + retrain model under current sklearn")
depends_on: none (R5 is the independent, baseline-shifting rung; loyalty abilities are sorcery-speed so NO priority-stack/R1 or instant-combat/R2 dependency)
supersedes:
superseded_by:
related_findings:
related_commits:
---

# R5 Planeswalker Loyalty Over Turns - Implementation Design

READ-ONLY design. No engine code is written by this synthesis. This doc is the reviewable plan
(mirroring the R1 and R2 designs) that must be approved before any R5 implementation. R5 REUSES
the existing `planeswalkers.py` dispatch (registry + per-turn budget + 0-loyalty SBA), is gated
behind a capability so non-planeswalker decks stay bit-identical, is built in an isolated worktree
branched OFF MAIN (2280dce) -- R5 needs no priority stack (loyalty abilities are sorcery-speed and
resolve immediately) and no R2 combat windows, so it is mechanically independent and off-main gives
it a clean `_resolve_combat` with nothing to coexist with -- is proven by replication +
no-regression, and the merge is held for the user.

XMage (magefree/mage, MIT) is the PATTERN reference; we DESCRIBE the essence and CITE real file
paths, never copy. hlynurd/open-mtg was checked and has NO planeswalker model (verified via gh api:
no loyalty/planeswalker token in cards.py/game.py/player.py/phases.py), so XMage is the sole
external pattern source.

The R5 rung is L-sized and BASELINE-SHIFTING by design: making planeswalkers live WILL move every
canonical deck running a PW. The shift is the measurement, not a regression -- but only if it is
honest. Two correctness traps (sections 0.2, 0.3) decide whether the WR jump is trustworthy. Both
are designed out below.

---

## 0. The synthesis calls that drive everything (spec corrections surfaced by reading code)

### 0.1 [CORRECTED] match_runner, NOT match_engine, is the load-bearing path for Eldrazi Tron -- AND db-cache is the bigger honesty trap

EARLIER DRAFT ERROR (corrected here against the live code): an earlier version of this section claimed
`EldraziTronMatchAPL` "has MATCHUP_SB_PLANS" and therefore Tron runs the bo3/`match_engine` path. That
is FALSE and it conflated two different things: Tron's in-game **Karn SB-wish toolbox** (a main-phase
APL mechanic that fetches silver bullets from the sideboard during a game -- which Tron DOES have,
`eldrazi_tron_match.py` L167-174) with a **`get_sb_plan` / `MATCHUP_SB_PLANS` routing entry** (a
between-games sideboard plan that selects the bo3 code path -- which Tron does NOT have).

What `run_matchup.py` actually does (verified): Path A (`engine/bo3_match.py:run_bo3_set` ->
`engine/match_engine.py:run_match`, `g1_source="bo3"`) is entered ONLY `if has_our_sb:`, where
`has_our_sb = bool(get_sb_plan(our_deck, opp))`. `get_sb_plan` reads `MATCHUP_SB_PLANS`.
EMPIRICAL CHECK (run this session): `get_sb_plan("Eldrazi Tron", *)` returns `([], [])`. Only two
match APLs carry a non-empty `MATCHUP_SB_PLANS` at all (`izzet_prowess_nick_tokyo_standard_match.py`,
`izzet_looting_standard_match.py`). So for Tron-as-deck-under-test, Path A is SKIPPED, and routing
falls to Path B:

- Path B-cache: `meta_bridge.get_real_matchup(... min_matches=20)` non-None -> `g1_source="db"`, the
  engine NEVER RUNS (cached real-world WR returned directly).
- Path B-sim: else `engine/match_runner.py:run_match_set` -> the monolithic `_resolve_combat`,
  `g1_source="sim"`. THIS is the only engine path Tron executes in a gauntlet.

TWO consequences for the design:
1. PRIMARY engine wiring is `match_runner` (`_run_player_turn` L279, `_resolve_combat` L613, views via
   `_build_view` L153) -- exactly what the ladder R5 rung originally cited. `match_engine.run_match` +
   `engine/match_state.py:resolve_combat` are the SECONDARY mirror (they DO run when Tron is the
   OPPONENT of one of the two SB-plan decks, so both runners must be gated identically; but the Tron
   anchor/falsifier/proof are load-bearing on `match_runner`). The PROOF unit test is therefore built
   against `match_runner`'s FLAT `TwoPlayerGameState` (`bf_a`/`bf_b`/`life_a`/`life_b`), NOT the
   `match_state.py` `gs_a`/`gs_b` shape.
2. THE BIGGER TRAP (headline honesty issue, larger than which-runner): even Path B-sim only runs if
   the matchup is NOT db-cached. If Tron's fair matchups are served from `g1_source="db"`, NEITHER
   runner executes and the falsifier (loyalty ON vs OFF) moves ZERO regardless of how correct the
   engine code is -- the exact db/combo-sampler inflation R1/R2 flagged. THE PROOF AND FALSIFIER MUST
   THEREFORE USE R1's FORCED-ENGINE METHOD: call `engine.match_runner.run_match_set` DIRECTLY (cache
   bypassed), seed=42, and scope every delta to the genuinely-simulated `g1_source="sim"` subset
   (4.2). This is mandatory and independent of vehicle choice.

VEHICLE NOTE: Tron remains the proof vehicle (the ladder's named unlock). Switching to Golgari (Prof.
Dellian Fel) buys NOTHING on routing grounds -- the empirical check shows Golgari routes IDENTICALLY
(`get_sb_plan("Golgari Midrange", *) == ([], [])` -> match_runner/db). Golgari is worth a one-line
mention ONLY because Prof. Dellian Fel is the card the `planeswalker-loyalty-not-tracked` imperfection
(L512) names; it is not "more reliably engine-run."

LINE-NUMBER CONVENTION: ALL citations (`planeswalkers.py`, `card_handlers_verified.py`,
`match_runner.py`, `match_state.py`, `eldrazi_tron_match.py`) are MAIN-tree lines at 2280dce, verified
this session. Re-grep at implementation time.

### 0.2 CORRECTNESS TRAP A -- gauntlet opponents must actually ATTACK the walkers, or the WR is inflated

This is the R5 face of R1's combo-sampler honesty trap. Today both combat paths only ever deal
combat damage to the DEFENDING PLAYER -- PRIMARY `engine/match_runner.py:_resolve_combat` (L613;
result applied to `life_b`/`life_a` at `_run_player_turn` L342-345) and SECONDARY
`engine/match_state.py:resolve_combat` (L267, "all damage to defending player" L290). There is no
"attack the planeswalker" concept anywhere on the match path, and none of the 38 canonical opponent
APLs target a PW. If R5
ticks loyalty up + fires ultimates but a PW can only be attacked inside the hand-built unit test,
then in the GAUNTLET Tron's Karn/Ugin become immortal value engines. The mandatory re-baseline jump
would then be partly "PWs are now unkillable," which cannot be separated from "PWs generate value."

Therefore the attackable-PW path proven in the unit test MUST ALSO be ACTIVE in the gauntlet:
- a default "attack the walker when profitable" heuristic added to base
  `AwareMatchAPL.declare_attackers`, STRICTLY behind the R5 gate (gate-off = byte-identical for
  non-PW matchups; see 1.4),
- so that when Tron (gate ON) seats against the field, the opposing aggro/tempo decks route some
  attackers at the resolved planeswalkers, reducing loyalty / killing them.

This converts the re-baseline from "upside-only" to a real two-sided attrition number. Without it the
spec's `data_quality:high` claim for Tron is not earnable. ABORT D2 (section 5.3) enforces it: if the
simulated-subset MWR rises but combat-deaths-of-PWs is ~0, the model is upside-only and FAILS.

### 0.3 CORRECTNESS TRAP B -- "RED-pre = PW inert" is NOT literally true; pin the discriminator

Planeswalkers are already CAST in match mode and already fire ONE-SHOT effects with the gate off:
- `card_handlers_verified.py:_karn_liberated_etb` (L10724-36) exiles a card from the opp hand at ETB.
- `EldraziTronMatchAPL` hardcodes one-shot `Karn` SB-fetch (L167-174) and `Ugin` cast-exile
  (L188-200) inside `main_phase_match`.
- the imperfection `planeswalker-loyalty-inert-in-match-mode` (IMPERFECTIONS L66-72) confirms PWs are
  "cast in 100+/120 games yet contribute ~0" because loyalty never ticks and ultimates never fire.

So "PW inert" is shorthand for "loyalty does not change across turns, no ultimate, not attackable" --
NOT "the PW does nothing." This is exactly the R1 trap where the ">=2 untapped lands" assertion was
not discriminating against the actual legacy code (R1 abort A). The R5 proof RED/GREEN axis is pinned
NARROWLY to the layer R5 actually adds:

  (i)  loyalty CHANGES across turns (strictly increases on tick-up turns, persists), AND
  (ii) an ULTIMATE FIRES (Karn -6 / Ugin -X) and applies its board effect, AND
  (iii) the PW is ATTACKABLE and dies as an SBA when loyalty hits 0.

Gate-OFF preserves the existing one-shot ETB / hardcoded-APL behavior VERBATIM (that is Tron's
current-code no-regression, NR-3a). The differential is purely the loyalty-over-turns / ultimate /
attackability layer. Every RED assertion must be checked to NOT pass-or-fail for a one-shot-ETB
reason (proof self-gate, section 4.1).

### 0.4 What is FREE vs what needs wiring (per-turn budget asymmetry)

`engine/planeswalkers.py:activate_planeswalker_ability` (L109) already implements CR 606.3 (one
loyalty ability per PW per turn, via `gs._pw_activated_this_turn`) and CR 704.5i (0-loyalty SBA ->
graveyard, L168). Loyalty itself persists FREE on `card.loyalty`.

- In `match_runner` (the PRIMARY path for Tron), `_build_view` (L153-188) rebuilds a FRESH
  single-player `GameState` per window (main1, combat, main2, end step), so `_pw_activated_this_turn`
  is born empty at every rebuild -- the per-turn budget is LOST. This is the load-bearing fix: 1.3
  must move the budget state onto the persistent `TwoPlayerGameState` (per player:
  `_pw_activated_a`/`_pw_activated_b` + the activation-turn marker) and alias it onto the throwaway
  view in `_build_view`, exactly the pattern `_build_view` already uses for `spells_cast_this_turn`
  (L174-179). Without it, "one ability per PW per turn" (CR 606.3) cannot be enforced -- a PW could
  re-activate in main1 and again in main2.
- In `match_engine.run_match` (the SECONDARY mirror), `gs_a`/`gs_b` are PERSISTENT across the turn
  loop, so `_pw_activated_this_turn` and `card.loyalty` both persist for free there; the lazy
  turn-change reset in `activate_planeswalker_ability` (L140-143) suffices.
- `card.loyalty` is a DISTINCT integer (from card_db; set on transform at game_state.py L1520-1531),
  NOT `card.counters` (which Ajani's +1/+1-on-Cats handler and the Class-level mechanic mutate) -- so
  attack damage and ticks touch `card.loyalty` only. It persists free in both runners (shared Card
  objects on the shared `bf_a`/`bf_b`).

---

## 1. Exact engine changes (all ADDITIVE; gate-OFF path frozen)

### 1.1 REUSE the existing dispatch (registry + activate), do NOT rebuild it

`engine/planeswalkers.py` already provides:
- `PLANESWALKER_ABILITIES: dict[str, dict[int, Callable]]` (L100) -- keyed card name -> {loyalty
  change -> handler(card, gs)}.
- `activate_planeswalker_ability(card, gs, change) -> bool` (L109) -- pays the loyalty cost, enforces
  the per-turn budget, fires the handler, runs the 0-loyalty SBA.

R5 POPULATES the registry (additive data) and WIRES one call site per runner; it does not touch the
dispatch contract. Registry entries to add, following the existing `Ajani, Nacatl Avenger` template
(`{+N: handler, 0: handler, -N: handler}`):
- Eldrazi Tron payoffs (anchor deck): `Karn, the Great Creator` ({+1 art-lock, -2 SB-wish}),
  `Ugin, Eye of the Storms` ({+2 draw, 0 add mana, -X sweep colorless-spare}), `Karn Liberated`
  ({+4 hand-exile, -3 permanent-exile, -14 restart}), `Ugin, the Spirit Dragon` ({+2 ping, -X sweep}).
- Canonical Standard PWs already on the field with one-shot ETB handlers to convert (section 1.2):
  `Chandra, Spark Hunter`, `Chandra, Torch of Defiance`, and the rest enumerated by
  `planeswalker-loyalty-not-tracked` (IMPERFECTIONS L512-518).

### 1.2 Convert one-shot ETB handlers to "SET loyalty at ETB; registry drives ticks"

Per the ladder rung: existing one-shot PW ETB handlers (e.g. `_chandra_spark_hunter_etb`
card_handlers_verified.py L1669, `_karn_liberated_etb` L10724) currently DO the +ability inline at
ETB. Convert each to MERELY set `card.loyalty` to the printed starting value at ETB; the per-turn
registry tick then drives the +N/0/-N each turn. This conversion is GATED (1.4): with the gate OFF,
the original inline one-shot ETB runs verbatim (NR-3a frozen baseline); with the gate ON, ETB only
sets loyalty and `activate_planeswalker_ability` does the rest. The conversion is therefore an
additive branch, not a rewrite of the existing handler body.

### 1.3 Wire the activation call site + attackable-PW (PRIMARY match_runner, mirror match_engine)

PRIMARY (`engine/match_runner.py`, the path Tron actually runs -- see 0.1):
- ACTIVATION: in `_run_player_turn` (L279), after the main-phase deploy (`_simple_play_turn` L337,
  and again allowed in main2 via `_run_post_combat_phase` L410 but enforced once-per-PW by the
  persisted budget), gated on `_pw_loyalty_enabled(...)`, iterate the active player's battlefield for
  planeswalkers (`"Planeswalker" in (c.type_line or "")`) and call
  `activate_planeswalker_ability(pw, view, change)` ONCE per PW with
  `change = apl.choose_pw_ability(pw, view, opp_view)`. The per-turn budget (606.3) is enforced inside
  `activate_planeswalker_ability` -- but it MUST read/write the PERSISTED per-player budget set from
  0.4 (aliased onto the view by `_build_view`), not the throwaway one. Ultimate handlers
  (Karn -X exile/restart approximation, Ugin -X sweep, emblems) operate on `opp_view` zones.
- ATTACKABLE-PW (the one new combat concept): in `_resolve_combat` (L613), allow an attacker to be
  declared against an opposing planeswalker. REUSE THE IN-ENGINE PRECEDENT: `_RESTLESS_LANDS`
  (`engine/game_state.py` L819-883) already makes a NON-CREATURE permanent a legal combat participant
  (a manland that can attack/block); the attackable-PW branch is the dual of that pattern -- a
  non-creature permanent that is a legal combat-damage RECIPIENT. Same shape (gated branch that admits
  a non-creature permanent into the combat math), so the attackable-PW code follows the
  `_RESTLESS_LANDS` template rather than inventing a new combat-participant concept. Mirror XMage's
  defender model (section "Pattern reference"): an attacker's target is a player OR a permanent (PW).
  When the target is a PW, subtract
  `min(safe_power(attacker), pw.loyalty)` from `pw.loyalty` (XMage `doDamage`:
  `countersToRemove = min(damage, loyalty)`), then run the 0-loyalty SBA (a shared
  `_pw_zero_loyalty_sba` helper, the same one `activate_planeswalker_ability` L168-171 uses) and
  remove the dead PW from the working attacker/blocker lists. Damage routed to a PW does NOT reduce
  the player's life. A blocker on the PW-attacker stops it (PW takes 0) via the existing block math.
  GATED on `_pw_loyalty_enabled`: gate OFF -> `_resolve_combat` is byte-identical (no PW-target branch
  reached).
- WIN-SOURCE TAG: `match_runner` reports via `MatchResult` (no `win_method` field today); add a
  `win_reason` ('combat' / 'pw_ultimate' / 'board_lock') set when the win is produced. Precise
  `pw_ultimate` definition in 4.2 so it is falsifiable, not fuzzy.

SECONDARY mirror (`engine/match_engine.py` + `engine/match_state.py`, run when Tron is the OPPONENT of
an SB-plan deck -- gate must behave identically):
- ACTIVATION: after `apl.main_phase_match(gs, opp_gs)` (L271), same gated activation loop over
  `gs_a`/`gs_b`; the budget persists free there (0.4).
- ATTACKABLE-PW: same gated branch in `engine/match_state.py:resolve_combat` (L267); subtract from
  `pw.loyalty`, run the shared SBA. Here `match_state.py` already has a `win_method` field
  ('combat'/'combo'/'timeout', L34) -- tag `win_method='pw_ultimate'` for parity. Gate OFF ->
  byte-identical.

### 1.4 The gate (mirror R1 / R2 exactly)

```python
# shared helper used by both runners + the attack-the-walker heuristic
def _pw_loyalty_enabled(gs, opp_gs) -> bool:
    self_apl = getattr(gs, '_self_apl', None) or getattr(gs, '_match_self_apl', None)
    opp_apl  = getattr(gs, '_match_opp_apl', None) or getattr(opp_gs, '_self_apl', None)
    return bool(getattr(self_apl, 'WANTS_PW_LOYALTY', False)
                or getattr(opp_apl, 'WANTS_PW_LOYALTY', False))
```

Base `apl/match_apl.py`: `WANTS_PW_LOYALTY = False`. The ONE class that flips it on is
`apl/eldrazi_tron_match.py:EldraziTronMatchAPL` (narrowed scope, exactly like R1's
`UWControlModernMatchAPL` and R2's `MurktideMatchAPL`). Fires when EITHER seat opts in: the
attack-the-walker heuristic (0.2) and the loyalty ticks engage in any matchup that seats Tron, and
ONLY those matchups. Non-PW decks in non-Tron matchups are byte-identical (their fields do not seat
Tron in the normal gauntlet).

Scope-precision note (mirror R1/R2): a non-PW deck FACING Tron correctly routes its attackers at
Tron's walkers via the gated default heuristic (feature, not regression). Its usual gauntlet field
never seats Tron, so normal non-Tron gauntlets are unperturbed.

### 1.5 APL layer

- `apl/match_apl.py` base: `WANTS_PW_LOYALTY = False`; default
  `choose_pw_ability(self, pw, gs, opp) -> int` returning the safe default (tick UP when not under
  pressure; tick toward the minus/ultimate when lethal or when the board is stable). Default
  `declare_attackers` gains the gated "attack the walker when profitable" branch (0.2), no-op when
  the gate is off.
- `apl/eldrazi_tron_match.py:EldraziTronMatchAPL`: set `WANTS_PW_LOYALTY = True`; implement
  `choose_pw_ability` for Karn/Ugin (Karn -2 to wish when a needed silver bullet exists else +1;
  Ugin +2 to stabilize then -X sweep when behind; Karn Liberated -3 to exile the opp's best threat,
  +4 otherwise, -14 only when it wins). REPLACE the existing hardcoded one-shot Karn/Ugin inline
  blocks (L167-200) with registry-driven ticks (gated; gate-OFF keeps the old inline path -- NR-3a).

### 1.6 Instrumentation (test-only, zero-RNG, mirror R1 COUNTERS_CAST / R2 TRICKS_CAST)

Module-global counters in `engine/planeswalkers.py` (or a small instrumentation shim): `PW_ACTIVATIONS`
(incremented inside `activate_planeswalker_ability` on a successful fire), `PW_ULTIMATES` (incremented
when a negative ult resolves), `PW_COMBAT_DEATHS` (incremented in `resolve_combat`/`_resolve_combat`
when a PW dies to combat damage), each with `reset_fire_count()`. Pure integer bookkeeping -> no
`random()`, no game-state mutation -> determinism preserved. The legacy gate-OFF path never reaches
these increments, so any nonzero value is direct evidence R5 fired in real play. `PW_COMBAT_DEATHS`
is the specific instrument that defeats the immortal-PW trap (0.2 / ABORT D2).

---

## 2. Rules-correctness (locked, do not drift) -- CR + XMage-pattern-aligned

- LOYALTY ABILITY = sorcery-speed, one per planeswalker per turn (CR 606.3). Enforced by
  `activate_planeswalker_ability`'s `_pw_activated_this_turn` budget. Cost (the +N/0/-N) is PAID as
  the ability is announced, BEFORE the effect resolves (CR 606.3; already correct at planeswalkers.py
  L155-159). XMage models the same cost-first / sorcery-timing via `PayLoyaltyCost` + the
  `TimingRule.SORCERY` set in `LoyaltyAbility` (cited, not copied).
- 0-LOYALTY = state-based action -> graveyard (CR 704.5i). Already implemented (planeswalkers.py
  L168-171). The attackable-PW path reuses the SAME SBA so a walker dropped to 0 by combat dies the
  same way a walker dropped to 0 by its own minus ability does.
- ATTACKING A PLANESWALKER (CR 508.1, 306.5b): combat damage dealt to a planeswalker is dealt as
  loss of that many loyalty counters. v1 models the minimal case: an attacker is declared at one
  opposing PW; `safe_power(attacker)` is removed from `pw.loyalty`; the PW dies at <= 0 via the SBA.
  Blocking the attacker (defender protecting its own walker is N/A -- the walker is the DEFENDING
  side's; the ATTACKER's opponent's walker is the target) follows the normal block rules already in
  `resolve_combat`: if the PW-attacking creature is blocked, it deals no damage to the walker (CR
  509.1, consistent with the existing blocked-attacker math). Trample-over-planeswalkers is OUT of v1
  scope (deferred, 5.2) -- XMage's `hasTrampleOverPlaneswalkers` redirect is noted as the future path.
- LOYALTY PERSISTS and is shared on `card.loyalty`; tick-up turns strictly increase it; it carries
  across turns (free in match_engine; synced in match_runner).

---

## 3. Build plan -- isolated worktree (mirror R1 / R2)

- `EnterWorktree` branch `modelability/r5-planeswalker-loyalty`, branched OFF MAIN at 2280dce. R5 is
  the independent rung: loyalty abilities are sorcery-speed (no priority stack), and off main
  `_resolve_combat` (L613) is clean -- no R2 combat windows to coexist with. (Off main, R1's
  `priority_stack.py` + `tests/test_r1_stack_priority.py` happen to be present but R5 does not touch
  them; R2's `test_r2_instant_combat.py` is absent. There is no "R1/R2 in-tree" no-regression gate --
  R5 cannot break what it does not touch.)
- Freeze branch-point baselines BEFORE any edit, at seed=42, PYTHONHASHSEED=0, as the FROZEN reference:
  - Boros Energy goldfish (sim.py n=50) -- NOTE this path DOES load `planeswalkers.py` (Ajani, see
    NR-1), so it is a real additive-safety anchor, not a "module doesn't load" cross-check.
  - Amulet Titan goldfish (20-life + 17-life).
  - The FULL CANONICAL GAUNTLET pre-state (locked 64.5% / 78.8%, per the ladder R5 rung) -- the
    MANDATORY re-baseline reference; PWs going live WILL move it (the measurement).
  - Eldrazi Tron via DIRECT `run_match_set` (cache bypassed, `g1_source="sim"`), gate ABSENT
    (PW-inert) -- the forced-engine baseline the falsifier diffs against (0.1 db-cache trap).
- Internal order: 1.6/0.4 budget-persistence on TwoPlayerGameState -> 1.1 registry-populate -> 1.2
  ETB-set-loyalty (gated) -> 1.3 match_runner activation + attackable-PW in `_resolve_combat` -> proof
  tests RED-pre/GREEN-post (against match_runner's FLAT state) -> 1.5 Tron APL opt-in +
  attack-the-walker default -> behavior metric + WR anchor + falsifier (forced-engine) -> 1.3
  match_engine/match_state SECONDARY mirror -> full no-regression. STOP before merge.

PREDICT BEFORE RUNNING (Rule 5, written before the re-baseline): Tron's simulated-subset MWR RISES
(loyalty value + ultimates); Tron's `pw_ultimate` win-source share goes from ~0 to nonzero;
`PW_COMBAT_DEATHS` is nonzero (opponents kill some walkers); per-matchup, Tron IMPROVES most vs
grindy/fair decks (where ultimates dominate a long game) and LEAST vs fast combo (it dies before the
ult). Any per-matchup move whose SIGN contradicts "PWs now do something" (e.g. Tron gets WORSE in a
fair matchup) is a STOP-and-investigate (5.3 D).

---

## 4. Proof + no-regression harness (acceptance gate)

R5 is PROVEN iff ALL of 4.1 AND 4.2 AND 4.3 hold.

### 4.1 PROOF-BY-REPLICATION (differential -- must be RED pre-R5, GREEN post-R5)

New file `tests/test_r5_planeswalker_loyalty.py` (standalone, `sys.path.insert`, plain asserts,
ASCII-only, prints "ALL R5 PROOF TESTS PASS", exit 0/1; same conventions as the R1/R2 tests). Build
`match_runner`'s FLAT `TwoPlayerGameState` directly (the structures the PRIMARY path uses:
`bf_a`/`bf_b`, `life_a`/`life_b`, `gy_a`/`gy_b`, the per-player budget sets from 0.4) and HAND-PLACE
cards -- do NOT run a full match (mulligans make it fragile). Drive the gated activation via the same
helper the runner calls, and resolve combat via `_resolve_combat`. Wire `_self_apl` /
`_match_opp_apl`, seed=42. The in-test Tron-style APL sets `WANTS_PW_LOYALTY=True` (it IS a PW APL
opting into R5, mirroring production EldraziTronMatchAPL); a per-instance `=False` toggle captures the
RED pre-state on the SAME structures (the R1/R2-proven gate-toggle technique). The discriminator axis
is pinned per 0.3: loyalty-over-turns / ultimate-fires / attackable-dies -- NOT one-shot ETB.

- TEST 1 -- LOYALTY TICKS UP OVER TURNS + REACHES ULTIMATE (the headline known line).
  Place a `Karn Liberated` on the battlefield at starting loyalty 6 (or `Ugin, the Spirit Dragon` at
  7). Advance N simulated turns, each calling the gated activation with `choose_pw_ability` returning
  the +ability. Assert:
  (a) loyalty STRICTLY INCREASES on each tick-up turn and PERSISTS across the rebuilt turn (6 -> 10 ->
      14 ... for +4; or 7 -> 9 -> 11 for +2);
  (b) the per-turn budget holds (a SECOND activation attempt on the same PW in the same turn returns
      False -- CR 606.3);
  (c) when `choose_pw_ability` selects the ultimate (Karn -14 / Ugin -X) at sufficient loyalty, the
      ultimate handler FIRES and applies its board effect: Ugin -X removes opp NONLAND permanents
      (assert opp battlefield nonland count drops to 0 / by X); Karn restart/exile-all applies;
  (d) `PW_ACTIVATIONS > 0` and `PW_ULTIMATES > 0`.
  RED pre (gate OFF): loyalty does NOT change across turns (stays at the ETB value), no ultimate ever
  fires, `PW_ULTIMATES == 0`. (a) and (c) FLIP. This is the discriminator. SELF-GATE CHECK: confirm
  (a)/(c)/(d) FAIL on the gate-OFF toggle for a LOYALTY reason, not because a one-shot ETB happened
  to fire -- the one-shot Karn ETB exile is irrelevant to these assertions (0.3).

- TEST 2 -- OPPONENT ATTACKS THE PLANESWALKER / KILLS IT (the second mandated line).
  Place a `Karn Liberated` at loyalty 3 on the defending side; the attacking side has a 4/4 creature.
  The attacker declares the 4/4 at the planeswalker. Resolve combat. Assert:
  (a) `pw.loyalty == 3 - 4 <= 0` -> the PW is in the graveyard (0-loyalty SBA), NOT on the
      battlefield;
  (b) the DEFENDING PLAYER's life is UNCHANGED (the 4/4 hit the walker, not the face);
  (c) `PW_COMBAT_DEATHS > 0`.
  Sub-case (a-survive): a 2/2 attacker into a loyalty-6 PW -> loyalty 4, PW ALIVE on battlefield,
  defender life unchanged. (Proves the partial-damage path, not just lethal.)
  RED pre (gate OFF): there is no attack-the-walker target -> the creature either hits the player
  (defender life drops by 4) or cannot be declared at the PW at all; the PW's loyalty is UNCHANGED and
  it stays on the battlefield. (a) and (b) FLIP.

- TEST 3 -- LOYALTY-FROM-MINUS-ABILITY ALSO TRIGGERS THE 0-SBA (cross-check the SBA is shared).
  Place a PW at loyalty 2; `choose_pw_ability` selects a -3. Assert the cost is paid (loyalty -> -1),
  the 0-loyalty SBA fires, and the PW is in the graveyard -- proving the SBA used by the
  attack-the-walker path (TEST 2) is the SAME one used by self-minus (no divergent death code).
  RED pre: with the gate OFF the minus ability is never selected/applied -> PW stays at 2 on board.

GATE ON THE TEST ITSELF (Rule 5): TEST 1(a)/(c)/(d), TEST 2(a)/(b)/(c), TEST 3 MUST FAIL on the
gate-OFF toggle. If any passes pre-R5 the test is not discriminating -> fix the test before any R5
claim (R1 abort A precedent). Record paired pre/post results in
`modelability_proofs/r5-planeswalker-loyalty-2026-06-26.json`.

### 4.2 BEHAVIOR METRIC (headline) + WR ANCHOR + FALSIFIER (Eldrazi Tron)

The task demands the metric + tolerance and the ladder says acceptance is on win-SOURCE, not a faster
clock. Lead with the behavior floor; WR is the cross-check.

BEHAVIOR FLOOR (headline, the "generates measurably more" gate), forced-engine direct
`run_match_set` (cache bypassed), n>=1000, seed=42, Tron = gate ON, over the genuinely-simulated
`g1_source="sim"` subset only:
- `pw_ultimate` win-source share > 0 vs ~0 in the gate-OFF baseline. PRECISE TAG (falsifiable, not
  fuzzy): a game is tagged `win_reason='pw_ultimate'` (match_runner `MatchResult`; `win_method` on the
  match_state mirror) iff a negative loyalty ultimate (Karn -14 / Ugin -X / Karn Liberated -3
  board-defining) RESOLVED in that game AND removed >= X opposing nonland permanents (X>=3 for the
  sweep ults) OR restarted/exiled-all, AND the game was won by the PW controller. (A walker merely
  ticking up does NOT count as a pw_ultimate win.)
- PW activations per Tron game >= N (set N at build time from the gate-ON run; floor N>=1, i.e. PWs
  must be doing SOMETHING each game they resolve), and `PW_COMBAT_DEATHS` per 1000 games > 0 (the
  immortal-PW guard, ties to ABORT D2).

FALSIFIER (mandatory, mirror R2 L116): turning PW loyalty OFF must MEASURABLY drop Tron's MWR. RUN VIA
THE FORCED-ENGINE METHOD (0.1 db-cache trap, R1's methodology): call
`engine.match_runner.run_match_set` DIRECTLY (cache bypassed -- do NOT route through `run_matchup.py`,
whose `get_real_matchup` short-circuit would serve `g1_source="db"` and move nothing), twice --
`WANTS_PW_LOYALTY` ON vs OFF -- and assert `MWR_on - MWR_off >= +Xpp` (X set from the re-baseline;
floor +2pp) on the genuinely-simulated `g1_source="sim"` subset ONLY (for Tron-under-test there is no
`bo3` subset -- it has no SB plan, 0.1). HONESTY SCOPING (reuse R2's tagged table): a normal gauntlet
FWR mixes (i) `sim` matchups that run the engine and CAN move, (ii) `db` cached matchups and (iii)
`ComboKillSampler` matchups that do NOT run the engine and CANNOT move. Compute the falsifier delta
over subset (i) ONLY and report the per-matchup table with `g1_source` tags. If subset (i) shows no
delta, PW loyalty is not load-bearing on Tron -> the proof FAILS (do not paper over with unmovable
db/combo matchups).

WR ANCHOR (cross-check): real Eldrazi/Mono-G Tron WR +/- 2pp, pulled at build time from
`mtg_meta.db.matchup_matrix` (modern; prefer fresher `untapped_meta_archetypes` if newer). NO
`[needs source]` may remain at run time (Rule 5 / no fabrication; ABORT I). `data_quality:high` is
claimable ONLY because trap A (0.2) is designed out -- attackers DO kill walkers in the gauntlet, so
the anchor is a real two-sided number, not an immortal-PW inflation. If the user chooses NOT to wire
gated gauntlet PW-attacking (section 6 decision), the anchor downgrades to `data_quality:medium` and
the overshoot is logged as an imperfection.

MANDATORY RE-BASELINE: full canonical gauntlet pre/post (locked 64.5% / 78.8% WILL move). The expected
shift is the measurement; investigate any per-matchup move whose sign contradicts the section-3
prediction (>0.5pp/matchup wrong-sign -> STOP, 5.3 D).

### 4.3 NO-REGRESSION (sharp form: bit-identical; mirror R1 / R2)

- NR-1 (PRIMARY, and SHARPER than R1/R2's analog): Boros Energy GOLDFISH bit-identical pre/post R5
  (sim.py n=50, seed=42, PYTHONHASHSEED=0; baseline 100% / avg 4.58 / median 4). Critically,
  `engine/planeswalkers.py` DOES load on this path (`apl/boros_energy.py` L769/L844 activate Ajani),
  so this is NOT a "module doesn't load" cross-check -- it is a real test that R5's additive changes
  (registry fill, gated ETB conversion, the new activation orchestrator + instrumentation) leave the
  EXISTING goldfish PW handling byte-identical. Any delta = leak into the gate-OFF / goldfish path.
  Doubles as a determinism guard.
- NR-2 (non-PW bit-identical via the SIM path): an Izzet-Prowess-vs-Dimir style non-PW MATCH run via
  `run_match_set` DIRECTLY (avoids the meta-DB short-circuit that took different code paths per tree
  in R1 -- a DATA divergence, not engine). Both gates OFF -> `match_runner._resolve_combat`
  byte-identical. Pick a non-degenerate (not 0/100) matchup so the number is a real discriminator.
- NR-3 (Amulet Titan goldfish bit-identical): seed=42; T-turn within +/- 0.05 of locked baselines
  (20-life 95.7% avg T7.11 / median T7; 17-life 95.9% avg T6.81 / median T6). Amulet runs no PWs.
- NR-3a (Tron CURRENT-CODE behavior preserved gate-OFF): with `WANTS_PW_LOYALTY` forced OFF, the Tron
  match (its hardcoded one-shot Karn-fetch / Ugin-exile + Karn ETB exile) is BYTE-IDENTICAL to the
  frozen branch-point capture. This proves the 1.2 ETB conversion and 1.5 APL one-shot replacement
  are truly gated (the differential lives only in the gate-ON layer, 0.3).
- NR-4 (coverage): `python scripts/full_audit.py --formats standard` -> 4218/4218, all 17 sets at 0
  remaining (R5 is control-flow + registry data + ETB-set-loyalty, not new handlers; the converted
  ETB handlers must still register).
- NR-5 (Standard/Modern APL smoke): `tests/test_modern_apls.py`, `tests/test_standard_apls.py`,
  `tests/test_match_engine.py`, `tests/test_determinism.py` all green.
- (No "R1/R2 tests still green" gate: R5 branches off main and touches neither the priority stack nor
  any combat-window code, so there is nothing of R1/R2 for it to break. The off-main `_resolve_combat`
  is clean -- the attackable-PW branch is the only combat edit.)

Compare post-R5 against the FROZEN branch-point capture (section 3), not hardcoded historical numbers.

---

## 5. Honest effort / risk + ABORT conditions

### 5.1 Effort and risk (highest first)
1. The attackable-PW edit to `engine/match_runner.py:_resolve_combat` (L613) is the dangerous edit --
   it touches the live combat math EVERY sim matchup uses (and the `match_state.py:resolve_combat`
   mirror touches every bo3 matchup). Mitigated by "add a gated PW-target branch only; prove gate-OFF
   byte-identical (NR-1/NR-2) before relying on the gate-ON path."
2. The immortal-PW honesty trap (0.2): if the attack-the-walker default heuristic is too timid,
   `PW_COMBAT_DEATHS` ~ 0 and the WR jump is upside-only (ABORT D2). Tune the default to attack a
   walker when it threatens an imminent ultimate or when face damage is not lethal-relevant.
3. RNG-stream / call-order leakage breaking NR-1/NR-3a bit-identical -- the activation loop and the
   resolve_combat branch must be zero-`random()` and must not reorder existing calls on the gate-OFF
   path.
4. Baseline-shift mis-attribution: the re-baseline moves the locked 64.5%/78.8%; without the
   PREDICTED direction written first (section 3), a wrong-sign move could be rationalized post-hoc
   (5.3 D blocks this).
5. Ultimate approximations (Karn -14 restart, Ugin -X sweep) being too strong/weak and distorting the
   WR. Keep ults minimal and board-effect-accurate for v1; card-accurate emblem persistence is R-later.

### 5.2 Intentionally DEFERRED beyond R5
- Trample-over-planeswalkers damage redirect (XMage `hasTrampleOverPlaneswalkers`).
- Multiple attackers split across several PWs + player in one combat; choosing which walker to attack
  among several. v1 = one attacker -> one walker.
- Activated (non-loyalty) PW abilities, static abilities beyond the simple ones (Karn art-lock),
  emblem persistence across game restarts.
- Targeting a PW with removal/burn on the stack (that is the R1/R2 stack path applied to PWs -- a
  later increment; v1 attackability is combat-only).
- Card-accurate ultimate magnitude beyond the board-defining approximation.
- Promoting any non-Tron PW deck (UW Control superfriends, Golgari Prof. Dellian Fel) to "modeled"
  off R5 -- R5 unlocks the Tron payoff cluster; the others ride the same registry but each needs its
  own anchor proof.

### 5.3 ABORT conditions (discard the worktree, leave the item unmodelable; mirror R1/R2 + ladder P5)
A. Proof not falsifying: any TEST 1/2/3 discriminator passes pre-R5 (gate OFF), OR a RED assertion
   flips for a one-shot-ETB reason rather than a loyalty reason (0.3) -> fix the test, no R5 claim
   until a clean red-pre / green-post on the loyalty/ult/attackability axis.
B. WR out of band after the iteration budget: Tron MWR outside the matched anchor's +/-2pp band at
   n>=1000. Do NOT widen the band to pass.
C. FALSIFIER FAILS: `MWR_on - MWR_off < +2pp` on the genuinely-simulated subset -> PW loyalty is not
   load-bearing -> proof fails.
D. Re-baseline sign violation: any canonical-gauntlet per-matchup move whose SIGN contradicts the
   section-3 written prediction by > 0.5pp -> STOP, investigate; resume only with a documented
   amendment.
D2. IMMORTAL-PW (the trap-A teeth): simulated-subset MWR rises but `PW_COMBAT_DEATHS` per 1000 games
   is ~0 -> the model is upside-only -> ABORT (the WR jump is not a real two-sided number; do NOT
   claim data_quality:high).
E. NO-REGRESSION broken: NR-1 / NR-2 / NR-3 / NR-3a not bit-identical (or Amulet T-turn drift > 0.05).
F. Coverage regression: full_audit < 4218/4218.
G. Determinism leak: the activation loop or resolve_combat PW branch mutates global random state
   (test_determinism fails) -> abort; RNG purity is non-negotiable.
H. Known line not reproducible in the iteration budget -> write an IMPERFECTIONS update on
   `planeswalker-loyalty-not-tracked` / `planeswalker-loyalty-inert-in-match-mode`, leave the item
   unmodelable, revert.
I. Any `[needs source]` anchor band that cannot be pulled from `mtg_meta.db` -> HITL pause (no
   fabricated targets).

---

## 6. GO / NO-GO recommendation

NO-GO for autonomous implementation now. HOLD for user review (same framing as R1/R2: design before
engine code; the `match_runner._resolve_combat` attackable-PW edit is a sharp bit-identical edit on
the live sim combat path that one does not start autonomously before approval).

ONE DECISION the user must settle (it changes the doc's data_quality claim):
- DOES v1 wire gated gauntlet PW-attacking (section 0.2)? RECOMMENDED YES -- it is what makes the
  re-baseline a real two-sided attrition number and earns Tron `data_quality:high`. If NO, the anchor
  downgrades to `data_quality:medium` and the immortal-PW overshoot is logged as an open imperfection
  (do NOT claim a clean +/-2pp band with unkillable walkers).

Middle option (forward motion without committing to merge): a bounded, reversible SPIKE --
`EnterWorktree modelability/r5-planeswalker-loyalty` OFF MAIN, freeze baselines, do the 0.4 budget
persistence, populate the registry for Karn/Ugin, wire ONLY the match_runner activation loop + the
`_resolve_combat` attackable-PW branch, prove `test_r5_planeswalker_loyalty.py` (against match_runner's
FLAT state) goes RED-pre / GREEN-post on TESTs 1+2, run NR-1 Boros-goldfish bit-identical + NR-3a
Tron-gate-OFF-preserved, and STOP. That validates the core bet (reuse the planeswalkers.py dispatch +
gated activation + gated attackable-PW read by existing combat math) cheaply and is discardable via
`ExitWorktree`.

Recommended: HOLD. On approval, spike first, then the full gate + the mandatory re-baseline.

---

## Appendix -- file-change list (absolute paths, worktree mtg-sim-r5)

- MOD  E:/vscode ai project/mtg-sim-r5/engine/planeswalkers.py            (POPULATE PLANESWALKER_ABILITIES: Karn/Ugin + canonical PWs; add activate_pws_for_turn orchestrator + _pw_loyalty_enabled gate + shared _pw_zero_loyalty_sba + PW_ACTIVATIONS/PW_ULTIMATES/PW_COMBAT_DEATHS instrumentation + reset_fire_count; existing dispatch contract UNCHANGED)
- MOD  E:/vscode ai project/mtg-sim-r5/engine/match_runner.py            (PRIMARY -- the path Tron runs: persist per-player PW budget on TwoPlayerGameState + alias in _build_view L153; gated activation loop in _run_player_turn L279; gated attackable-PW in _resolve_combat L613 (subtract min(power,loyalty), shared SBA, drop dead PW); win_reason tag on MatchResult; gate-OFF byte-identical)
- MOD  E:/vscode ai project/mtg-sim-r5/engine/match_engine.py             (SECONDARY mirror -- runs when Tron is opponent of an SB-plan deck: gated PW-activation loop after main_phase_match L271; budget persists free over gs_a/gs_b)
- MOD  E:/vscode ai project/mtg-sim-r5/engine/match_state.py             (SECONDARY mirror: gated attackable-PW branch in resolve_combat L267, win_method='pw_ultimate' tag L34; gate-OFF byte-identical)
- MOD  E:/vscode ai project/mtg-sim-r5/engine/card_handlers_verified.py  (gated: convert one-shot PW ETB handlers -- _chandra_spark_hunter_etb L1669, _karn_liberated_etb L10724, _professor_dellian_fel_etb L28033, etc. -- to SET starting loyalty when gate ON; gate-OFF keeps inline one-shot verbatim, NR-3a)
- MOD  E:/vscode ai project/mtg-sim-r5/apl/match_apl.py                  (base WANTS_PW_LOYALTY=False + default choose_pw_ability + gated "attack the walker" default in declare_attackers)
- MOD  E:/vscode ai project/mtg-sim-r5/apl/eldrazi_tron_match.py         (WANTS_PW_LOYALTY=True + choose_pw_ability for Karn/Ugin; REPLACE hardcoded one-shot Karn L167-174 / Ugin L188-200 with registry ticks, gated)
- KEEP E:/vscode ai project/mtg-sim-r5/engine/counter_resolver.py        (UNCHANGED -- R5 does not touch counters/stack; loyalty is sorcery-speed)
- ADD  E:/vscode ai project/mtg-sim-r5/tests/test_r5_planeswalker_loyalty.py
- ADD  E:/vscode ai project/mtg-sim-r5/modelability_proofs/r5-planeswalker-loyalty-2026-06-26.json  (proof artifact: rung, anchor_wr, tolerance, wr_on, wr_off, falsifier_delta, pw_ultimate_share, pw_combat_deaths, line_reproduced, seed, log_excerpt, commit_hash, baseline_shift, g1_source_table)

## Pattern reference (cited as PATTERN only -- MIT, describe-don't-copy)

All XMage paths below were FETCHED this session (raw.githubusercontent.com / gh api) and the essence
verified; method/field names are quoted, not invented. Exact line numbers are given only where
captured directly.
- `Mage/src/main/java/mage/abilities/LoyaltyAbility.java`: `LoyaltyAbility(Effect, int loyalty)`
  super-constructs with cost `new PayLoyaltyCost(loyalty)`; the variable form uses
  `new PayVariableLoyaltyCost()`; both set `this.timing = TimingRule.SORCERY`. ESSENCE: +N / 0 / -N is
  ONE activated ability carrying a fixed loyalty cost, sorcery-speed. (Mirrors our
  `PLANESWALKER_ABILITIES[name][change]`.)
- `Mage/src/main/java/mage/abilities/costs/common/PayLoyaltyCost.java`: `pay()` -- `amount > 0 ->
  planeswalker.addCounters(CounterType.LOYALTY.createInstance(amount), ...)`; `amount < 0 ->
  planeswalker.removeCounters(CounterType.LOYALTY.getName(), Math.abs(amount), ...)`. `canPay()` ->
  `getCounters(game).getCount(CounterType.LOYALTY) + loyaltyCost >= 0` (a -N is illegal below N);
  after pay, `planeswalker.addLoyaltyUsed()`. ESSENCE: cost mutates loyalty at announce; minus gated by
  available loyalty. (Our `activate_planeswalker_ability` L155-159 applies the change before the
  handler; the heuristic only proposes an affordable minus.)
- `Mage/src/main/java/mage/game/permanent/PermanentImpl.java`: (a) ENTER -- `entersBattlefield`:
  `if (isPlaneswalker(game)) addCounters(CounterType.LOYALTY.createInstance(getStartingLoyalty()), ...)`.
  (b) ONCE-PER-TURN -- fields `protected int timesLoyaltyUsed = 0; protected int
  loyaltyActivationsAvailable = 1;`; `canLoyaltyBeUsed = loyaltyActivationsAvailable > timesLoyaltyUsed`;
  `addLoyaltyUsed()` increments; `reset()` sets `loyaltyActivationsAvailable = 1` (default ONE per
  turn). (c) DAMAGE -- `doDamage`: `if (isPlaneswalker(game)) { int loyalty =
  getCounters(game).getCount(CounterType.LOYALTY); int countersToRemove = Math.min(actualDamageDone,
  loyalty); removeCounters(CounterType.LOYALTY.getName(), countersToRemove, ...); }`. ESSENCE: loyalty
  on ETB; one activation/turn reset each turn; combat damage removes min(damage, loyalty).
- `Mage/src/main/java/mage/game/combat/CombatGroup.java`: `defenderDamage()` resolves
  `Permanent permanent = game.getPermanent(affectedDefenderId)`; if the defender is a permanent
  (planeswalker), damage routes via `permanent.markDamage(amount, attacker.getId(), null, game, true,
  true)`, else to the player; `unblockedDamage` / `blockerDamage` call `defenderDamage`. ESSENCE:
  attacking a PW = declaring it the defender; its damage is marked on the permanent, not the player.
  R5's analog: the attack-the-walker branch routes attacker power to `pw.loyalty` -- the same
  player-vs-permanent fork, kept minimal (trample-over-PW deferred, 5.2).
- `Mage/src/main/java/mage/game/GameImpl.java` `checkStateBasedActions` (~L2622-2630), CR 704.5i
  (captured verbatim this session):
  ```java
  if (perm.isPlaneswalker(this)) {
      //20091005 - 704.5i
      if (perm.getCounters(this).getCount(CounterType.LOYALTY) == 0) {
          if (movePermanentToGraveyardWithInfo(perm)) {
              somethingHappened = true;
              continue;
          }
      }
  }
  ```
  ESSENCE: a 0-loyalty planeswalker is put into its owner's graveyard as an SBA. (Our
  `planeswalkers.py` L168-171 already implements exactly this inline, citing CR 704.5i.)
- hlynurd/open-mtg (Python): inspected via `gh api` (cards.py, game.py, player.py, phases.py) -- NO
  `loyalty`/`planeswalker`/`walker` reference anywhere; it does NOT model planeswalkers, so it offers
  no usable PW pattern. Recorded to close the task's "open-mtg if it models PWs" branch.
- wanqizhu/mtg-python-engine (Python) `data/M15_cards.py`: planeswalker cards store loyalty abilities
  as PLAIN TEXT strings (no structured starting-loyalty attribute, no enforced once-per-turn, no
  tracked loyalty state). Cited as a contrast: even a rules-aspiring Python engine keeps loyalty
  shallow; mtg-sim's existing `PLANESWALKER_ABILITIES` registry (structured handlers + budget + SBA)
  is already STRICTLY MORE than this reference, which is why R5 populates/wires it rather than
  rebuilding a loyalty model from scratch.

## Changelog
- 2026-06-26: Authored as the R5 design (READ-ONLY), mirroring the R1/R2 proof + bit-identical
  discipline. Surfaced two correctness traps (gauntlet PWs must be attackable or the WR inflates;
  "PW inert" RED-state must be pinned to the loyalty/ult/attackability axis because one-shot ETBs
  already fire gate-OFF) and designed both out.
- 2026-06-26 (amendment, routing correction): VERIFIED against the live code that the original 0.1 was
  inverted. `get_sb_plan("Eldrazi Tron", *)` is empty (only izzet-prowess-tokyo + izzet-looting carry
  MATCHUP_SB_PLANS), so Tron-as-deck-under-test SKIPS the bo3/match_engine path and runs match_runner
  sim (or db-cache). FLIPPED PRIMARY -> match_runner (`_run_player_turn` L279 / `_resolve_combat` L613
  / `_build_view` L153) with match_engine+match_state as the SECONDARY mirror; proof unit test now
  targets match_runner's FLAT TwoPlayerGameState. Made the db-cache short-circuit the HEADLINE honesty
  issue: the proof/falsifier must use the forced-engine direct `run_match_set` (cache bypassed),
  scoped to `g1_source="sim"`. Re-pointed the branch base OFF MAIN (2280dce) -- R5 is sorcery-speed
  with no priority-stack/R2 dependency, so off-main `_resolve_combat` is clean; dropped the NR-6
  "R1/R2 in-tree" gate accordingly. Sharpened NR-1 (Boros goldfish DOES load planeswalkers.py via
  Ajani -> a real additive-safety anchor). Named that the earlier error conflated Karn's in-game
  SB-wish toolbox with a get_sb_plan routing entry. Preserved the two correctness traps (0.2/0.3).
  Grounded in real engine reads (main 2280dce) + XMage files fetched & verified this session;
  open-mtg confirmed (gh api) to have no PW model.
- 2026-06-26 (synthesis pass): Cited the in-engine `_RESTLESS_LANDS` (game_state.py L819-883)
  precedent in the 1.3 attackable-PW seam -- the attackable-PW branch is the dual of the manland
  pattern (a non-creature permanent admitted into combat as a damage RECIPIENT vs a participant), so
  it follows that template rather than inventing a new combat-participant concept. Confirms the
  counter-tracking reuse already present (0.4 card.loyalty-vs-card.counters distinction; 1.6
  instrumentation mirrors R1 COUNTERS_CAST / R2 TRICKS_CAST). No engine code written; doc remains
  READ-ONLY, status PROPOSED.
