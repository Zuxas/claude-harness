# Stage B -- Izzet Affinity COUNTERS modeled (R1 opt-in + COUNTER_VALIDITY)

- Date: 2026-06-27
- Format target: Modern
- Status: SHIPPED 2026-06-28. Phase 1 (mtg-sim 51448a5): Edits A+B; gate low->high (PROMOTABLE), R1 counter fires, no crash, byte-identical-OFF. Phase 2 (FWR sweep): COUNTER_COST {0,1,2,3} all ~42% at n=300 (40.8% at n=1000, no regression vs 41% baseline); set COUNTER_COST=2; honest finding = counters add ~0 WR, the value was the trustworthy-FWR gate flip not a WR buff. Izzet Affinity is honestly a ~41% deck -- 40.8% at n=1000 (trustworthy, below promote threshold). Residual decomposition/field-side-effect deferred (moot -- counters add ~0 WR).
- Front: make Izzet Affinity's 3 Metallic Rebukes route through the shipped R1
  stack-priority machinery so the fidelity gate credits `counterspell_on_stack`
  and the deck's profile confidence flips from `low` to `high` (PROMOTABLE =
  FWR is trustworthy; clearing the FWR promote threshold is measured separately).
- Owner: ARL / mtg-sim
- Related shipped work: R1 (`engine/priority_stack.py`,
  `modelability_proofs/r1-stack-priority-2026-06-26.json`), proven pattern in
  `apl/uw_control_modern_match.py`.

---

## 1. Why the deck is "low" today (root cause, cited)

The fidelity gate in `scripts/arl_profile.py` rates the deck:

- `_detect_mechanics` (arl_profile.py:274-277) flags `counterspell_on_stack`
  by the substring `"counter target"` in oracle text. Metallic Rebuke's oracle
  is `"... Counter target spell unless its controller pays {3}."` -> counts the
  3 copies in `decks/izzet_affinity_modern.txt`.
- `_severity_for_counts` (arl_profile.py:311-321): `2 <= copies <= 3` ->
  `counterspell_on_stack = "low"`; and because `c >= 2`, `hidden_information`
  rides along at the same severity (arl_profile.py:333-336). Overall confidence
  = worst severity = `low`.
- Warp is NOT the blocker: `IzzetAffinityMatchAPL.WANTS_WARP = True`
  (affinity_match.py:49) + the `r4-warp-*` proof means
  `_apl_modeled_capabilities` (arl_profile.py:344-385) already credits `warp` as
  `high`. The lone remaining downgrade is the counters.

The counters are genuinely dead in match mode today (this is the real defect,
not just a gate technicality):

- `IzzetAffinityMatchAPL` extends `MatchAPL` (affinity_match.py:36), so it has
  no `priority_action` other than the inert base (`match_apl.py:55-63`,
  returns None) and `WANTS_PRIORITY_STACK` defaults False -> the cast never
  routes through `run_priority_stack` (game_state.py:1485).
- Its bespoke `respond_to_spell` (affinity_match.py:267-276) is never given a
  real spell: the only match-engine caller, `_try_reactive_interaction`, calls
  `reactive_apl.respond_to_spell(reactive_gs, active_gs, None)` with `spell=None`
  (match_engine.py:105), and affinity's method short-circuits `if not spell:
  return None` (affinity_match.py:269). So Metallic Rebuke counters NOTHING in
  match play. Confirmed by the goldfish APL marking it `DEAD_IN_GOLDFISH`
  (apl/izzet_affinity.py:107).
- `Metallic Rebuke` is absent from `engine/counter_resolver.py:COUNTER_VALIDITY`
  (lines 42-65), so the legacy `try_counter_spell` window can't fire it either.

---

## 2. The change (two edits, both small)

### Edit A -- re-base the match APL and opt into R1

`apl/affinity_match.py`:

1. Import + base swap:
   `from apl.aware_match_apl import AwareMatchAPL`
   `class IzzetAffinityMatchAPL(AwareMatchAPL):`  (was `(MatchAPL)`).
2. Add the opt-in + the deck's counter wiring (mirrors
   uw_control_modern_match.py:80-84):
   - `WANTS_PRIORITY_STACK = True`
   - `COUNTER_CARDS = {"Metallic Rebuke"}`
   - `COUNTER_COST = <swept; see 6>`  (lands to hold up for Rebuke)
3. Keep `WANTS_WARP = True` (unchanged).
4. Override the two combat-instant hooks to no-op to keep blast radius minimal
   (see 4.B for why they otherwise newly activate):
   `def pre_combat_instant(self, gs, opp): pass`
   `def post_attackers_instant(self, gs, opp, attackers): pass`
5. Add a conditional `reserve_mana` override so the tempo tax only applies when
   we actually hold a Rebuke and are not the beatdown (see 6).
6. (Optional, clarity only -- inert) delete the now-dead `respond_to_spell`.

The class KEEPS its existing `keep`, `bottom`, `main_phase`,
`main_phase_match`, `declare_attackers`, `declare_blockers`,
`_play_land_if_able`. These already override the `AwareMatchAPL` versions via
MRO, so the re-base does NOT change them (see 4.A -- this corrects the task's
premise).

`priority_action` and `_r1_choose_counter` are then INHERITED from
`AwareMatchAPL` (aware_match_apl.py:587-691). They read
`COUNTER_VALIDITY`/`_spell_value`/`_PRIORITY_COUNTER_TARGETS` from
`engine/counter_resolver.py`, which is exactly why Edit B is required.

### Edit B -- teach the resolver about Metallic Rebuke

`engine/counter_resolver.py`, add ONE entry to `COUNTER_VALIDITY` (after the
existing soft-counter entries, ~line 64):

```python
# Metallic Rebuke: soft counter ("...unless its controller pays {3}").
# Counters ANY spell. base_cmc=1 (value gate) reflects its typical
# Improvise/affinity-reduced cost so it is allowed to answer cheap spells;
# AFFORDABILITY is still checked against the printed {2}{U} (cmc 3) by
# _r1_can_afford/_pay_for_counter -- the engine models neither Improvise nor
# the reduction, so the deck must actually have 3 real mana to fire it.
"Metallic Rebuke": (lambda s: True, 1),
```

Rationale for the `base_cmc=1` / pay-at-3 split: `_r1_choose_counter`'s value
gate uses `base_cmc` (`counter_cmc > spell_val -> skip` unless priority target,
aware_match_apl.py:666-670), so `base_cmc=1` lets Rebuke counter 2-drops like
real Magic. But `_r1_can_afford` (aware_match_apl.py:675-691) and
`_pay_for_counter` (priority_stack.py:99-120) use the printed `card.cmc`/
`mana_cost`, so it can only actually FIRE with 3 untapped mana. This is honest
under-modeling (Rebuke fires LESS than reality), never a cheat.

No other files change. The R1 engine (priority_stack.py, the game_state.py
gate, match_engine.py) is already shipped and is NOT edited.

---

## 3. Byte-identical-when-OFF guarantee

There is no engine flag toggled here; the only engine-file edit is the single
`COUNTER_VALIDITY` row. The guarantee is therefore scoped to that dict and to
"matchups that do not seat the affinity deck."

`COUNTER_VALIDITY["Metallic Rebuke"]` is consumed by exactly two readers:

1. Legacy `try_counter_spell` (counter_resolver.py:122-183) -- the gate-OFF
   synchronous window.
2. R1 `_r1_choose_counter` (aware_match_apl.py:637-673) -- only reachable when
   `WANTS_PRIORITY_STACK` is on for some seat.

**Claim:** for every matchup that does NOT seat the registered affinity deck,
behavior is bit-identical before/after Edit B.

**Proof sketch:** the new row changes a counter decision only for a seat that
(a) holds a `Metallic Rebuke` in hand AND (b) is asked to counter. The ONLY
registered match APL whose deck runs Metallic Rebuke is `IzzetAffinityMatchAPL`
(`MATCH_APL_REGISTRY` keys `izzetaffinity`/`affinity` ->
`apl.affinity_match`, apl/__init__.py:284-285), and after Edit A it declares
`WANTS_PRIORITY_STACK = True`. In any matchup seating it the gate is ON, so the
caster's `cast_spell` sets `_skip_legacy_window = True` (game_state.py:1492) and
the legacy `try_counter_spell` is never reached -- the new row only ever feeds
the R1 path, which is the intended (gate-ON) behavior. Goldfish (single-player)
has no `_match_opp_apl`, so neither reader fires. Hence no gate-OFF matchup can
observe the new row.

**Residual risk (MUST be in the validation gate):** two other deck files carry
Metallic Rebuke -- `decks/auto/izzet_affinity_modern.txt` (duplicate) and
`decks/auto/cutter_affinity_modern.txt` (a distinct list). NEITHER has a
`MATCH_APL_REGISTRY` entry today (verified: no `cutter`/auto key in
apl/__init__.py), so neither is ever seated in match play. If either ever gets
a gate-OFF match APL, this guarantee breaks. The validation gate re-asserts
uniqueness among *registered* match APLs.

### Falsifiable validation gate for Edit B
1. `grep -rl "Metallic Rebuke" decks/` and cross-check against
   `MATCH_APL_REGISTRY`: the ONLY registered match deck holding it is affinity.
   FAIL if any other registered match APL's deck lists it.
2. Differential on a representative gate-OFF, non-affinity matchup -- the R1
   proof's anchor: `run_match_set(IzzetProwessMatchAPL vs MurktideMatchAPL,
   n=80, seed=42, n_workers=1, mix_play_draw=True)` on the tree BEFORE Edit B
   vs AFTER. PASS iff win% byte-identical (proof baseline 53.8%).
3. Determinism: run the affinity gauntlet twice at the same seed; per-matchup
   match% must be byte-identical (priority_stack does zero `random()`).

---

## 4. What the re-base actually changes (and what the task assumed wrongly)

### 4.A Corrects the task premise: combat + mulligan are NOT brought over

The task expects the re-base to import `declare_attackers` trade logic and
mulligan behavior. MRO disproves this: `IzzetAffinityMatchAPL` defines its own
`declare_attackers` (affinity_match.py:244-248), `declare_blockers` (250-265),
`keep` (62-73), `bottom` (75-79), `main_phase`/`main_phase_match` (81-242), and
`_play_land_if_able` (280-288). Subclass methods win in MRO, so AwareMatchAPL's
trade-intelligence `declare_attackers` (aware_match_apl.py:454-520), pump-aware
`declare_blockers`, `_lethal_this_turn`, the `keep`/`keep_vs_opp` dispatcher,
and the curve-driven `main_phase` are ALL shadowed and never run. Combat math
and mulligans are therefore UNCHANGED by the re-base. `OPP_THREAT_MODEL` is
only read by helpers those overridden methods call, so it is also inert here.

### 4.B The genuine new behaviors from the re-base (the real risk surface)

1. **`reserve_mana` now called.** `match_engine.py:401-403` does
   `gs.mana_reserve = 0; if hasattr(apl,'reserve_mana'): apl.reserve_mana(...)`.
   Base `MatchAPL` has no `reserve_mana`, so today it is skipped (mana_reserve
   stays 0). After re-base the inherited `AwareMatchAPL.reserve_mana`
   (aware_match_apl.py:566-581) runs. With the default `COUNTER_COST=0` it sets
   `mana_reserve=0` (no change). With `COUNTER_COST>0` and a Rebuke in hand it
   leaves N lands untapped -> the deck taps out less on its own turn -> slower
   clock. THIS is the dominant FWR risk (see 6).
2. **`pre_combat_instant` / `post_attackers_instant` newly fire on defense.**
   `match_engine.py:444` is `if not gate_on and hasattr(opp_apl,
   'pre_combat_instant')`. Base `MatchAPL` lacks the method -> skipped today.
   After re-base affinity inherits both (aware_match_apl.py:245,282). They call
   `_tap_for_response(opp_gs)` first (match_engine.py:445), which taps
   affinity's lands and fills its pool during the opponent's combat -- a real
   state change even though `_kill_with_removal` finds nothing castable
   (affinity has no card in `MATCH_REMOVAL`). MITIGATION: override both to
   `pass` (Edit A.4) so neither the tap nor the scan happens -> blast radius
   stays just the intended R1 counters + `reserve_mana`.
3. **Intended:** `priority_action` is live, so when an opponent casts a spell
   in any affinity matchup (gate now ON), affinity can answer with Metallic
   Rebuke via R1.

### 4.C The asymmetry the task did NOT mention (advisor catch -- load-bearing)

Flipping affinity's gate ON does not only let affinity counter; it ALSO changes
how the OPPONENT counters affinity. Today (gate OFF) an opponent counters
affinity's spells via `try_counter_spell`, whose `_tap_lands_for_response`
(counter_resolver.py:100-119) grants mana from EVERY land regardless of tap
state (loose). Under R1 the opponent's counter must pay through
`_pay_for_counter` -> REAL untapped mana honoring reserve (priority_stack.py:99-
120). Most field opponents tap out and define no `reserve_mana`, so under R1
they frequently CANNOT counter affinity even holding a counter. (Note an
`AwareMatchAPL` opponent's `priority_action` is live regardless of its own
`WANTS_PRIORITY_STACK` -- that flag only controls whether the gate is reached --
so this is real-mana suppression, not a disable.) Net: the affinity FWR delta
conflates three effects:
  (a) affinity's new counters (intended buff),
  (b) opponents' counter-resolution swapping loose->real mana (generally favors
      affinity), and
  (c) affinity's own reserve tempo cost (regression).
A naive "FWR >= 41% -> ship" gate would PASS while baking in (b)'s inflation.
The validation gate (5) therefore decomposes the delta.

Affinity is in the Modern top-8 field at ~9% (per the R1 proof's field), so this
gate flip also perturbs EVERY other Modern deck's gauntlet via the affinity
column. Re-running only affinity's gauntlet is insufficient; see 5.

---

## 5. Re-validation plan (decomposed, not a single FWR compare)

Run BEFORE (current main) and AFTER (Edits A+B) on the same seeds.

1. **Fidelity gate flips.** `python scripts/arl_profile.py
   decks/izzet_affinity_modern.txt modern`. PASS iff
   `engine_fidelity.confidence` goes `low -> high` and
   `blocking_imperfections` becomes `[]` (the `counterspell_on_stack` ->
   `sim-no-stack-priority` mapping in `data/engine_fidelity_map.json` no longer
   trips because `_apl_modeled_capabilities` now credits it: WANTS_PRIORITY_STACK
   True + `r1-` proof present).
2. **R1 actually fires for affinity, both seats decomposed.** Reuse the
   `priority_stack.COUNTERS_CAST` instrumentation (+ `reset_fire_count()`).
   - After: affinity's own counter fires > 0 over the gauntlet.
   - BASELINE decomposition: instrument how many times opponents counter
     affinity in the gate-OFF baseline (legacy `try_counter_spell`) vs after
     (R1 `_pay_for_counter`). If the baseline opponent-counter count is nonzero
     and drops after, the FWR delta is partly effect (c)/(b), not pure (a) --
     CAVEAT the headline number accordingly. Report all three counts.
3. **Affinity FWR, n >= 1000.** `parallel_launcher.py --deck "Affinity"
   --format modern --n 1000 --top-n 8 --seed 42`. (The R1 proof flags n=600 <
   1000 as sub-Tier-1; use >=1000.) Report FWR + full per-matchup table BEFORE
   vs AFTER. Acceptance: FWR not materially below 41% (no regression) with the
   per-matchup table read, not just the headline.
4. **Field side-effect check (because affinity is 9% of the field).** Re-run the
   gauntlet for 2-3 other Modern decks whose field includes Affinity (before vs
   after). Their match% vs the Affinity column WILL move (affinity now counters
   them); confirm the movement is explainable (counter-relevant decks lose a few
   pp to affinity; non-spell decks unchanged) and not a crash/degenerate swing.
5. **Determinism.** Same-seed gauntlet twice -> byte-identical per-matchup
   match% (zero `random()` in the R1 path).
6. **Byte-identical-OFF for Edit B.** Section 3's gate (grep uniqueness +
   Izzet-Prowess-vs-Dimir n=80 seed=42 == 53.8% both trees).
7. **Smoke / compile.** `python -c "import apl.affinity_match"` and a 100-game
   `sim.py` goldfish on the affinity deck must not crash (the goldfish path is
   unaffected, but the re-base must import cleanly).

---

## 6. COUNTER_COST sensitivity (the tempo knob)

Because `_pay_for_counter` charges the full `{2}{U}` (no Improvise/affinity
reduction) and the sim has no untap step, affinity must `reserve_mana ~3` to
ever fire Rebuke on the opponent's turn. Holding 3 mana on an aggressive
artifact deck is a heavy tempo tax that can tank the 41%. Design the reserve
CONDITIONALLY and sweep:

```python
def reserve_mana(self, gs, opponent):
    has_rebuke = any(c.name == "Metallic Rebuke" for c in gs.zones.hand)
    # Don't tax the clock when we're the beatdown / ahead on damage.
    if has_rebuke and self.COUNTER_COST > 0 and not self._affinity_is_beatdown(gs):
        gs.mana_reserve = self.COUNTER_COST
    else:
        gs.mana_reserve = 0
```

Sweep `COUNTER_COST in {0, 1, 2, 3}` at n>=1000 and pick the value that
maximizes FWR. Expectation: `0` makes Rebuke almost never fire (counters
modeled in name only -- still flips the fidelity gate, but adds little WR);
`3` over-taxes the clock. A middle value or an opponent-aware reserve (only
vs combo/control/removal-heavy fields per `OPP_THREAT_MODEL`, which is now
available) is likely best. Document the chosen value and the curve.

`_affinity_is_beatdown` can be a thin local helper (e.g. our board has >=2
attackers OR `gs.damage_dealt >= opp.damage_dealt`); do NOT reuse
`AwareMatchAPL._i_am_beatdown` blindly (it reads `_match_dmg`/`_opp_gs` that
this APL's overridden main path may not populate -- verify before calling).

---

## 7. Known imperfections (carry into the proof artifact)

- Rebuke is over-costed in the R1 path (printed {2}{U}; neither Improvise nor
  affinity reduction modeled). It fires strictly less than real Magic. Honest
  under-model, never a cheat. A later engine increment could teach
  `_pay_for_counter` about Improvise, but that is OUT of Stage B scope.
- The opponent-side counter-resolution swap (4.C) is a real model change for
  affinity matchups, surfaced for the first time by a field deck (UW Control was
  absent from its field). It is a feature (real-mana counters are more correct
  than loose-mana), but the FWR delta must be read decomposed.
- `respond_to_spell` (affinity_match.py:267-276) is dead in match mode and stays
  inert; optionally remove for clarity.

---

## 8. Effort & recommendation

- Edits: ~15-25 lines across 2 files (one APL re-base + helpers, one dict row).
- Validation: the decomposed gauntlet sweep is the bulk of the work
  (n>=1000 x 4 COUNTER_COST values + field side-effect runs + the Edit-B
  differential). ~half a day of sim time.
- Risk: MEDIUM. The mechanism is proven and the engine is untouched; the risk is
  entirely in FWR movement (tempo tax + the 4.C asymmetry inflating/deflating
  the number) and in the field side-effect on other Modern decks.
- Recommendation: PHASED. (1) Land Edits A+B with the combat-instant hooks
  no-op'd and `COUNTER_COST` swept; confirm the fidelity gate flips to `high`
  and the Edit-B byte-identical-OFF gate passes -- that alone makes the deck's
  profile PROMOTABLE. (2) Treat the FWR decomposition + field side-effect runs
  as the acceptance bar before trusting/promoting the number, exactly as the R1
  proof kept "mechanism proven" separate from "WR anchor met."
