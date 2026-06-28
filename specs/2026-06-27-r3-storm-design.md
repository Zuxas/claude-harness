---
title: R3 Storm Mechanic Increment - Implementation Design
status: PROPOSED
created: 2026-06-27
project: mtg-sim
related:
  - harness/specs/2026-06-26-modelability-ladder.md  (R3 rung definition)
  - harness/specs/2026-06-26-archetype-capability-profiles.md  (fidelity gate / backlog)
  - harness/specs/2026-06-26-R4-warp-design.md  (closest precedent: gate spine + per-APL narrowing + match-path-only differential)
  - harness/specs/2026-06-26-R1-stack-priority-design.md  (NARROWING lesson)
  - mtg-sim/engine/game_state.py  (cast_spell L1438; spells_cast_this_turn increment L1470; reset L290)
  - mtg-sim/engine/match_runner.py  (_simple_play_turn sync-back L261-268; _run_post_combat_phase damage sync L554-558; _warp_match_gate L674; _run_end_step seam L1372)
  - mtg-sim/engine/card_handlers_verified.py  (_grapeshot_spell L9797; _empty_the_warrens L8303; _galvanic_relay L9449; _damage_any_helper L396)
  - mtg-sim/scripts/arl_profile.py  (_detect_mechanics L242; _severity_for_counts L298; _apl_modeled_capabilities L344)
  - mtg-sim/decks/ruby_storm_modern.txt  (the canonical storm deck)
  - mtg-sim/apl/ruby_storm_match.py  (RubyStormMatchAPL; AUTO_GENERATED=True L23 -- the load-bearing defect)
  - mtg-sim/data/engine_fidelity_map.json  (mechanic -> imperfection id; single source of truth)
supersedes:
superseded_by:
---

# R3 Storm Mechanic Increment - Implementation Design

> A reviewable DESIGN, not engine code and not a proof.json. It states the SMALLEST
> increment that makes the STORM mechanic MODELED-AND-CREDITED on the match path, behind a
> per-APL WANTS_STORM flag that is byte-identical when OFF, composing with the verified
> R1+R2+R4+R5 gates as an independent 5th gate. ASCII-only. See section 6 for GO/NO-GO.

## 0. The synthesis call that drives everything (the surprise that reframes R3)

R3 is NOT like R1/R2/R4/R5. Those four each modeled a mechanic that was GENUINELY ABSENT
from the engine. Storm is HALF-BUILT already, and that fact is the entire design.

Three load-bearing facts, all verified on the tree this session:

1. **Storm count + copy-on-resolve ALREADY EXIST at the handler layer.** `_grapeshot_spell`
   (card_handlers_verified.py L9800) computes `storm = max(0, gs.spells_cast_this_turn - 1)`
   and `copies = 1 + storm`, then deals 1 damage `copies` times. Empty the Warrens (L8305)
   and Galvanic Relay (L9451) do the same. `gs.spells_cast_this_turn` is incremented inside
   `cast_spell` (game_state.py L1470), gate-independently, and reset per turn (L290). So the
   storm-count primitive is engine-resident and works in GOLDFISH today.

2. **Storm is INVISIBLE to the fidelity gate.** `arl_profile._detect_mechanics` (L242-295)
   detects only counterspell_on_stack / planeswalker_loyalty / warp /
   instant_speed_combat_trick. There is NO storm key. Ruby Storm therefore scores
   confidence `high` (a FALSE-high) -- the gate believes the deck is fully modeled when its
   combo turn is not. The FRONT's "storm decks are unmodelable" is half-right: the truth is
   worse than unmodelable -- it is mis-graded as modeled. `engine_fidelity_map.json` has no
   `storm` entry either.

3. **Storm is BROKEN on the MATCH path for two compounding reasons:**
   - **(3a) The Ruby Storm match-APL bypasses `cast_spell`.** `RubyStormMatchAPL`
     (ruby_storm_match.py, `AUTO_GENERATED = True` L23) casts noncreature spells by hand:
     `gs.mana_pool.pay(...)` + `gs.zones.hand.remove(c)` + `gs.zones.graveyard.append(c)` +
     `gs.damage_dealt += 2` (L90-93). It NEVER calls `gs.cast_spell(c)`. So
     `spells_cast_this_turn` never increments, `on_spell_resolve` never fires, and
     `_grapeshot_spell` is NEVER reached. Grapeshot deals a flat "2 face", not storm copies.
   - **(3b) Main-phase-1 spell damage is dropped on the match path even WHEN routed
     correctly.** `_damage_any_helper` (card_handlers_verified.py L427-429) writes
     `gs.damage_dealt += dmg` and `opp.life -= dmg` on the ACTIVE VIEW. But
     `_simple_play_turn`'s post-`main_phase` sync-back (match_runner.py L261-268) propagates
     ONLY `land_played` + spell counts back to `TwoPlayerGameState` -- NOT `view.damage_dealt`
     and NOT `opp_view.life`. So a Grapeshot resolving in main phase 1 writes the throwaway
     view and is discarded before the win check. Contrast `_run_post_combat_phase` (main
     phase 2), which DOES sync damage via `delta_damage = view.damage_dealt - prev_damage`
     (L554-558). This is a GENERAL match-path gap (any main1 burn-to-face is lost), not
     storm-specific -- exactly parallel to R4's general gap (match-path `_tick_warp` never
     ran for any of 3 warp decks).

**Decision (authoritative for R3): gate the NEW behavior behind a single per-APL flag
`WANTS_STORM`, default False, narrowed to ONE opt-in APL (the rewritten Ruby Storm
match-APL).** The "new behavior" is precisely (3b)'s fix -- gated propagation of
active-player main-phase-1 spell damage back to `TwoPlayerGameState` -- plus the
companion APL rewrite (3a) so storm count actually accrues, plus the fidelity-gate wiring
(fact 2) so storm is detected, severity-mapped, and credited. The goldfish handlers (fact
1) are LEFT UNTOUCHED.

Why this framing and not the obvious alternatives:

- **Reject "invent a generic Storm-keyword copy primitive behind WANTS_STORM."** Storm
  copy already happens in the handler, reading `spells_cast_this_turn` unconditionally.
  A second, gated copy path would either DOUBLE-COUNT against the existing handler or be a
  fake gate whose ON and OFF produce identical Grapeshot output. Do NOT manufacture an
  engine gate where the engine already does the work. (Generic Storm-keyword coverage for
  handler-less cards is a real future item -- section 5.4 -- but it is NOT R3's gate.)
- **Reject "fix the main1 damage-sync UNGATED."** It is a general match-path gap; wiring
  it ungated changes the shared turn path for EVERY deck (any main1 face burn now lands) ->
  breaks Class-A bit-identical. It must be gated, exactly as R4 gated the match-path warp
  tick that was also a general gap.
- **Reject "just move the Grapeshot cast to main_phase2 (already synced) and ship ZERO
  engine change."** This is the honest fallback (section 5.6) and it WOULD work for a
  creatureless storm deck (nothing happens between main1 and main2 for it). But it is a
  workaround that hides a real engine gap, and it makes WANTS_STORM a pure fidelity-credit
  flag with no engine teeth. Adopt it ONLY if the gated main1-sync (1.2) proves intractable
  inside the spike budget. Primary path = the real fix.

This one decision makes every required property fall out of the same gate, mirroring R4:

1. **Bit-identical (non-storm + non-opted-in decks):** gate defaults OFF -> the
   `_simple_play_turn` sync-back is byte-identical (no main1 damage propagation, exactly as
   today), zero new `random()`, goldfish handlers untouched. (Deliverable 3.)
2. **Proof differential (MATCH path only):** the rewritten Ruby Storm APL flips
   `WANTS_STORM=True` and routes through `cast_spell`; main1 Grapeshot storm damage reaches
   `gs.life_b` only post-R3 (gate ON). RED pre = storm count 0 and/or damage dropped; GREEN
   post = damage == spells-cast-this-turn landing on opponent life. (Deliverable 1.)
3. **Ladder composition:** R3 is a 5th independent gate beside WANTS_PRIORITY_STACK /
   WANTS_INSTANT_COMBAT / WANTS_PW_LOYALTY / WANTS_WARP. (Deliverable 3, trilogy+R4 suites.)

RECONCILING THE LADDER SPEC. If the modelability-ladder R3 line reads as "add a storm
copy primitive to the engine," do NOT silently follow it -- the primitive already exists
(fact 1). REINTERPRET (record the amendment): R3 = "make the EXISTING storm-count primitive
reachable, correct, and CREDITED on the match path, gated." The clean fixes for the OTHER
main1-damage consumers (general burn) and for handler-less storm cards are tracked
IMPERFECTIONS (section 5.4), not part of R3's proof.

---

## 1. Exact engine changes (smallest increment)

### 1.1 Storm count + copy-on-resolve -- ALREADY EXISTS, reuse, DO NOT TOUCH

`_grapeshot_spell` (L9797-9804), `_empty_the_warrens` (L8303-8307), `_galvanic_relay`
(L9449-9454) already read `gs.spells_cast_this_turn` and apply `copies = 1 + storm`.
`spells_cast_this_turn` is incremented in `cast_spell` (L1470) and reset in `run_turn`
(L290). NO new copy primitive. NO edit to these handlers. R3 must NOT change goldfish
output for these cards (Class-A guard, section 4.3).

NOTE on the storm-count convention (load-bearing for the proof): the count is read at
RESOLVE time, and `cast_spell` increments `spells_cast_this_turn` BEFORE resolution, so the
payoff spell counts ITSELF; the handlers subtract 1 (`storm = spells_cast_this_turn - 1`)
to get "spells cast before this one." Net: a Grapeshot cast as the Nth spell of the turn
deals N instances of 1 damage (copies = 1 + (N-1) = N). The proof asserts exactly this.

### 1.2 Match-path main-phase-1 spell-damage propagation -- the one GENUINELY NEW, GATED surface

Add a gate helper and a gated sync block; mirror the verified R4/R5 pattern exactly.

(a) `match_runner._storm_match_gate(gs)` -- a near-clone of `_warp_match_gate` (L674):
```
def _storm_match_gate(gs) -> bool:
    return bool(getattr(getattr(gs, "apl_a", None), "WANTS_STORM", False)
                or getattr(getattr(gs, "apl_b", None), "WANTS_STORM", False))
```
`getattr`-based, defaults False. The combo-sampler / goldfish paths never set apl_a/apl_b,
so it is OFF there.

(b) In `_simple_play_turn`, inside the existing `if player == "a": ... else: ...`
sync-back (L261-268), add a GATED branch that propagates the active view's main1 spell
damage, mirroring `_run_post_combat_phase`'s sync (L554-558). The active `view` is a fresh
`GameState` (so `view.damage_dealt == 0` at entry); after `main_phase_match` it holds
exactly this main1's spell damage. Apply cumulatively and decrement the defender's life:
```
if getattr(apl, "WANTS_STORM", False):   # ACTIVE player's flag, not either-seat
    if player == "a":
        gs.damage_to_b += view.damage_dealt
        gs.life_b      -= view.damage_dealt
    else:
        gs.damage_to_a += view.damage_dealt
        gs.life_a      -= view.damage_dealt
```
- ACTIVE-PLAYER GATE (deliberate; differs from `_storm_match_gate`): the main1 sync only
  ever propagates the ACTIVE player's OWN spell damage (`apl` is in `_simple_play_turn`'s
  scope as the active pilot). Gating on the active `apl`'s `WANTS_STORM` -- NOT the
  either-seat `_storm_match_gate` -- means that in a Ruby-Storm-vs-Boros match the
  OPPONENT's turn stays byte-identical (Boros's own main1 face burn is still dropped,
  exactly as pre-R3). An either-seat gate would silently start landing the opponent's main1
  burn inside the matchup -- a real, unwanted opponent-behavior change. `_storm_match_gate`
  is retained ONLY for fidelity-wiring symmetry / any future either-seat need; the engine
  sync itself uses the active-only check. Record this either-seat-vs-active distinction as
  the deliberate choice it is.
- NON-DOUBLE-COUNTING: `view.damage_dealt` starts at 0 each main1 call (fresh view, not
  seeded from `gs.damage_to_b`), so it is ONLY this main1's increment; `+=` onto the
  cumulative match total is correct. `opp_view.life` (which `_damage_any_helper` also
  decremented) is the throwaway view and is intentionally NOT read -- identical to how
  `_run_post_combat_phase` ignores `opp_view.life` and uses `delta_damage`.
- WIN REGISTRATION: the existing post-main2 win check (`_run_player_turn` L440-455) reads
  `gs.life_b`/`gs.damage_to_b`, so a main1 storm kill is caught at end of the SAME
  player-turn. A creatureless storm deck has no combat between main1 and main2, so the
  one-step delay is behaviorally inert. (OPTIONAL, deferred: a gated early win-check right
  after the sync; not needed for the proof -- section 5.4.)
- BIT-IDENTICAL BY CONSTRUCTION: gate OFF -> the whole `if _storm_match_gate(gs): ...` block
  is a pure no-op -> `_simple_play_turn` is byte-identical to today (main1 damage dropped,
  exactly as the trilogy+R4 baseline). Zero new `random()`. This is the R4 guard-token
  proof reused verbatim.

NO new scheduler, NO change to `cast_spell`, NO change to the goldfish path, NO change to
`_resolve_combat`, NO change to `counter_resolver.py`.

### 1.3 Companion APL rewrite (REQUIRED -- without it the gate has nothing to propagate)

`RubyStormMatchAPL` (ruby_storm_match.py) is `AUTO_GENERATED = True` (L23) and is the
load-bearing defect. Rewrite its `main_phase_match` cast loop so EVERY spell is cast via
`gs.cast_spell(c)` (not manual `mana_pool.pay` + graveyard + `damage_dealt += 2`). This is
what makes `spells_cast_this_turn` accrue and `_grapeshot_spell` fire. Set
`WANTS_STORM = True` on the class. Keep the rewrite minimal and faithful: cast accelerants
/ cantrips first (rituals, Wrenn's Resolve, Reckless Impulse), hold the storm payoff
(Grapeshot) for last so its storm count is maximal. This is a per-deck pilot change, not a
shared-path change -- it cannot affect any other deck.

NOTE: the goldfish `RubyStormAPL` (apl/ruby_storm.py) is OUT OF SCOPE -- the goldfish path
already routes through `cast_spell` and the handlers already fire there; do not touch it.

---

## 2. The capability gate (so ONLY storm decks change)

Mirrors the gate discipline of R1 (WANTS_PRIORITY_STACK), R2 (WANTS_INSTANT_COMBAT), R5
(WANTS_PW_LOYALTY), R4 (WANTS_WARP), all defined in apl/match_apl.py L44-80.

- Base `MatchAPL`: add class attr `WANTS_STORM = False` (alongside the existing four).
  Every existing deck inherits False -> exact current match path, no main1 damage sync.
- Rewritten `RubyStormMatchAPL`: `WANTS_STORM = True` + cast-through-`cast_spell` loop (1.3).
- `match_runner._storm_match_gate(gs)`: the read site (1.2), `getattr`-based, defaults
  False. No per-card auto-enable -- per-APL opt-in only (section 0 rationale, R1 NARROWING
  lesson).

Net: a deck that does not opt in never reaches the new sync block; bit-identical follows.

---

## 3. The fidelity-gate wiring (the BULK of R3; arl_profile + data only; no engine behavior)

This is what actually flips Ruby Storm from FALSE-high to correctly-credited. None of it
touches `engine/`; it changes only the deterministic profiler and its data map. The
"byte-identical-when-OFF" claim here is about the GATE VERDICT, not literal JSON bytes:
every NON-storm deck's `confidence` + `blocking_imperfections` are UNCHANGED; the only
JSON-shape change is a new `"storm": 0` key in `mechanic_counts`/`evidence` (a value of 0
trips nothing). State this honestly in the proof; it is not an engine byte-identical claim.

### 3.1 `arl_profile._detect_mechanics` (L242) -- detect storm

- Add `"storm": 0` to the `counts` dict (L248) and the `evidence` map (L254).
- Detection signature (mirror `_WARP_RE` L227): a card has storm iff `"storm"` is in its
  keyword list OR the printed keyword ability "Storm" appears in oracle text. Add
  `_STORM_RE = re.compile(r"\bStorm\b")` and, in the per-card loop, increment by `qty` when
  `"storm" in keywords or _STORM_RE.search(oracle)`.
- GOTCHA (false positives): "Storm" appears in many card NAMES (Elspeth, Storm Slayer;
  Disruptive Stormbrood; Stormchaser's Talent; Stormscale Scion). Detection scans
  oracle_text + keywords ONLY (never the name), so a name match alone will not trip --
  BUT a card whose oracle quotes another spell or whose reminder text says "...copy it for
  each spell cast before it this turn" could. PREFER the keyword list (`db.keywords(name)`)
  as the primary signal and treat the oracle regex as a fallback; document the residual
  risk. Validate on the Ruby Storm mainboard: Grapeshot must trip; Ral / Wrenn's Resolve /
  Reckless Impulse / rituals must NOT.

### 3.2 `arl_profile._severity_for_counts` (L298) -- map storm severity

Add a storm rule mirroring WARP exactly (storm is binary-central like warp, NOT
density-tiered like counterspells -- see GOTCHA below):
```
if "storm" in modeled:
    sev["storm"] = "high"
else:
    sev["storm"] = "unmodelable" if counts["storm"] >= 1 else "high"
```
GOTCHA (why not the counterspell `>=4` tier): Ruby Storm's MAINBOARD has ~1 storm-KEYWORD
payoff (Grapeshot; Empty the Warrens + the 2nd Grapeshot are SIDEBOARD, and
`_detect_mechanics` scans mainboard only, L257). A copy-count threshold would never trip.
Storm decks are defined by ENABLER density (rituals, cost reducers, cantrips), which R3
does NOT detect -- so any single storm-keyword payoff present means the combo turn is the
plan -> `unmodelable` unless credited. Record this as a known detection limitation.

### 3.3 `arl_profile._apl_modeled_capabilities` (L344) -- credit WANTS_STORM + proof

Add, alongside the warp/stack branches (L379-382):
```
if getattr(cls, "WANTS_STORM", False) and _proof("r3-"):
    modeled.add("storm")
```
`_proof("r3-")` checks `modelability_proofs/` for a file starting `r3-` (the proof JSON,
section 5.5). This ties the credit to BOTH the pilot flag AND a shipped proof, exactly like
warp (`_proof("r4-warp")`) and stack (`_proof("r1-")`). Pre-proof, Ruby Storm reads
`unmodelable`; post-proof-and-opt-in, `high`.

### 3.4 `data/engine_fidelity_map.json` -- add the imperfection id

Add `"storm": "engine-fidelity-gaps-storm-mechanic-match-path"` (or the existing id if one
is later minted). `assess_engine_fidelity` (L388) reads this map for `blocking_imperfections`
when storm trips at medium-or-worse; without the entry the block would be empty for a
tripped storm deck.

---

## 4. Proof + no-regression harness (acceptance gate)

R3 is PROVEN iff ALL of the following hold. Comparison reference = the current main /
trilogy+R4 tree (the gate is OFF there by construction).

### 4.1 DELIVERABLE 1 -- proof-by-replication (the storm-count match-path line)

New `tests/test_r3_storm_lifecycle.py` (standalone, `sys.path.insert`, plain asserts,
ASCII, prints "ALL R3 PROOF TESTS PASS", exit 0/1; same conventions as
`tests/test_r4_warp_lifecycle.py`). Construct `TwoPlayerGameState` DIRECTLY and HAND-PLACE
cards (do NOT run a full match -- mulligans make it fragile, per the R4 lesson). The test
self-declares `WANTS_STORM` per phase (False for RED, True for GREEN) and routes casts
through `cast_spell`.

Card: Grapeshot (`{1}{R}` Sorcery, "1 damage to any target. Storm.", handler L9797) as the
storm-count discriminator -- it is to R3 what Quantum Riddler was to R4.

Sequence (active player, opp at 20, no opp creatures so all damage is face): cast K cheap
spells that route through `cast_spell` (use mana-neutral cantrips / hand-placed mana), then
cast Grapeshot LAST as the (K+1)th spell. Expected storm copies = K+1 -> K+1 face damage.

ASSERT ON THE SHARED STATE, NOT THE VIEW (the discriminator IS the sync seam). The test
MUST drive `_simple_play_turn(gs, "a", apl)` (or `_run_player_turn`) with `gs.apl_a`/`apl`
wired so the active-player gate can read `WANTS_STORM`, and MUST assert on the
`TwoPlayerGameState` (`gs.life_b` / `gs.damage_to_b`) IMMEDIATELY AFTER the main1 call --
NEVER on `view.damage_dealt`. Shortcutting to `view.cast_spell(grapeshot)` + checking the
view is GREEN both pre and post (the handler always copies on the view) -> non-discriminating
-> fails the "gate the test itself" clause. Assert right after main1 to isolate the sync
(post-full-turn, pre-R3 also leaves `life_b==20` because main2 seeds delta=0, but the
right-after-main1 assertion makes the discriminator unambiguous).

- RED-pre (gate OFF == current behavior, MATCH path): even with the APL routing correctly,
  `_simple_play_turn` does NOT sync `view.damage_dealt` -> assert (must hold pre):
  `gs.life_b == 20` and `gs.damage_to_b == 0` on the TwoPlayerGameState right after
  `_simple_play_turn`. The storm damage is computed on the throwaway view and DROPPED. The
  lifecycle is absent -> the differential is real. (Also assert the AUTO_GENERATED-style
  manual cast path yields flat damage, not storm scaling, to document defect 3a.)
- GREEN-post (gate ON): after the same sequence, on the TwoPlayerGameState
  `gs.life_b == 20 - (K+1)` and `gs.damage_to_b == K+1`. The storm count SCALED with spells
  cast (not flat 1), and the damage PROPAGATED to the match life total.
- DISCRIMINATORS: (i) propagation happened (gs.life_b dropped on the match state, not just
  the view); (ii) damage == spells-cast-this-turn (K+1), proving storm COUNT, not a flat
  hit; (iii) gate OFF leaves gs.life_b at 20 (byte-identical drop = nothing).
- GATE ON THE TEST ITSELF: the GREEN assertions MUST FAIL on the frozen pre-R3 tree. If
  they pass pre-R3 the test is non-discriminating -> fix the test before any R3 claim.
  (This is why the proof lives on the MATCH path: a goldfish storm test would be GREEN
  pre-R3 because the goldfish handler already copies -- fact 1.)

### 4.2 DELIVERABLE 2 -- behavior / exercise (storm fires and scales in real matches)

- PRIMARY metric (a count gate, not a WR delta; mirror R4's WARP_CAST/RECAST_FROM_EXILE):
  add module-global pure-integer counters in card_handlers_verified.py (or game_state.py),
  e.g. `STORM_COPIES_DEALT` and `STORM_PAYOFFS_RESOLVED`, incremented inside the storm
  handlers, plus a `reset_storm_count()` (analog of `reset_fire_count`). Pure bookkeeping:
  zero `random()`, no state mutation -> determinism preserved. EXISTENCE GATE over a
  single-process `run_match_set` (n_workers=1 so in-process counters are visible) of the
  rewritten Ruby Storm (`WANTS_STORM=True`) vs a real engine-running FAIR opponent (e.g.
  Boros Energy / Izzet Prowess), n=60, seed=42: `STORM_PAYOFFS_RESOLVED > 0` AND the
  average copies-per-payoff `> 1` (proving scaling, not flat 1). Gate OFF -> payoffs may
  still resolve via the handler but main1 damage does not propagate, so the match-level
  effect is 0; assert gate-ON > gate-OFF on opponent-life delta.
- WR ANCHOR (SOURCED, SECONDARY): pull `mtg_meta.db.matchup_matrix`, format=modern,
  archetype='Ruby Storm' -> match-weighted aggregate, tagged `data_quality:medium`. Band:
  +/- 2pp at n >= 1000. Do NOT promote on WR alone. R3 is fidelity-first; a LARGE WR jump
  is an ABORT signal (likely the free-ritual-mana quirk, section 5.4), not a win.
- CURVE-SHIFT prediction (written BEFORE the run): crediting storm damage shifts modeled
  `rubystorm` kill mass EARLIER (toward T4-5, the real combo-turn window) vs the pre-R3
  never-kills-via-storm shape. A run whose sign CONTRADICTS this (slower / no kills) is a
  STOP condition.

### 4.3 DELIVERABLE 3 -- no-regression (two classes + all gates)

- CLASS A -- bit-identical, MUST hold: Boros Energy (goldfish, seed 42, n>=50) and Amulet
  Titan (goldfish, seed 42, n>=50) byte-identical pre/post (win%, avg/median kill turn,
  win-by-Tn, mulligans). Plus a non-storm modern gauntlet (seed 42) FWR byte-identical.
  These never set WANTS_STORM -> `_storm_match_gate` False -> the new sync block is a no-op.
- CLASS A' -- GOLDFISH STORM byte-identical: run `sim.py` on `ruby_storm_modern` (goldfish,
  seed 42, n>=50) pre/post. R3 does NOT touch the goldfish path or the storm handlers, so
  goldfish storm numbers MUST be byte-identical. (This guards fact 1 from accidental edits.)
- CLASS B -- the storm deck on the MATCH path with gate OFF: before the APL flips
  WANTS_STORM, the match path is unchanged (storm damage still dropped). "No regression"
  for the pre-opt-in state = unchanged, NOT "storm now lands" (mirrors R4 Class B).
- ALL GATE SUITES still green on the R3 branch: `test_r1_stack_priority.py`,
  `test_r1_control_exercises.py`, `test_r2_instant_combat.py`,
  `test_r5_planeswalker_loyalty.py`, `test_r4_warp_lifecycle.py`,
  `test_trilogy_cross_gate.py`, `test_determinism.py` -- all exit 0. R3 adds a 5th gate; it
  must not perturb R1/R2/R4/R5.
- FIDELITY-GATE no-regression: re-run `arl_profile.build_profile` on a non-storm deck (e.g.
  Boros Energy) pre/post -> `confidence` + `blocking_imperfections` UNCHANGED (only a new
  `storm:0` key appears in mechanic_counts). Run it on Ruby Storm: pre-R3-credit ->
  `unmodelable` (storm trips); with WANTS_STORM=True + proof present -> `high`.
- DETERMINISM: re-run the gate-ON Ruby Storm exercise twice at seed 42 -> byte-identical
  (same per-matchup %, same STORM_* counts).
- ISOLATION: `counter_resolver.py`, `priority_stack.py`, `planeswalkers.py`,
  `_resolve_combat`, the goldfish `cast_spell` HAND path, and the three storm handlers
  byte-identical.

### 4.4 DELIVERABLE 4 -- ABORT / STOP conditions (teeth)

- Lifecycle line not reproducible within the rung budget -> ABORT, IMPERFECTIONS entry,
  item stays `unmodelable`.
- `STORM_PAYOFFS_RESOLVED == 0` over the seeded exercise -> ABORT; mechanism not
  load-bearing (likely the APL rewrite still bypasses `cast_spell` somewhere).
- Average copies-per-payoff == 1 (no scaling) -> ABORT; `spells_cast_this_turn` is not
  accruing (the storm count is not real).
- Class A / A' bit-identical BREAKS for ANY non-storm OR goldfish-storm deck -> ABORT
  immediately -- `WANTS_STORM` leaked off the single opt-in, OR a goldfish/handler edit
  crept in. Re-narrow.
- Any gate suite (R1/R2/R4/R5/cross-gate/determinism) goes red -> ABORT (R3 broke
  composition).
- A non-storm deck's fidelity `confidence` changes -> ABORT (detection false-positive;
  tighten `_STORM_RE` / prefer keyword list).
- Determinism leak: global random state mutated by the R3 path -> ABORT.
- WR jump far above the anchor band -> STOP, investigate the free-ritual-mana quirk before
  any promote.

---

## 5. Honest effort / risk + deferred scope

### 5.1 Effort and risk

R3 is LOW-to-MEDIUM effort. The engine change (1.2) is ~6 lines mirroring an existing,
verified sync (`_run_post_combat_phase`). The fidelity wiring (section 3) is the bulk but
is mechanical (four small edits mirroring the warp branch). The APL rewrite (1.3) is the
fiddliest piece (getting the cast order right so storm count is maximal). Highest risks, in
order:
1. Detection false-positive on a non-storm deck (the "Storm" substring problem) -> Class-A
   fidelity regression. Mitigated by keyword-list-primary detection + the no-regression
   profile diff (4.3).
2. Bit-identical leak: `WANTS_STORM` placed on the base class instead of the one opt-in ->
   Class A breaks. Mitigated by per-APL narrowing + the no-op-when-off guard (1.2).
3. Double-count on the damage sync (seeding `view.damage_dealt` from the cumulative total)
   -> over-kill. Mitigated by the fresh-view invariant (view.damage_dealt starts at 0) and
   the proof's exact-equality assertion (damage == K+1).
4. APL rewrite leaves a residual manual-cast path -> storm count silently 0. Caught by the
   `STORM_PAYOFFS_RESOLVED > 0` exercise gate (4.4).

### 5.2 What R3 PROVES

The MECHANISM (storm count == spells cast this turn; copy-on-resolve; the result PROPAGATES
to opponent life on the match path) on Grapeshot, gated and composable with R1/R2/R4/R5.
NOT the full Ruby Storm combo turn (see 5.4).

### 5.3 What R3 does NOT prove (be honest)

The storm-count primitive was ALREADY engine-resident for goldfish; R3 does not "add storm
to the engine." R3 makes it REACHABLE + CORRECT + CREDITED on the match path. The headline
must say so plainly (the discovery that storm is half-built is the finding, not something to
paper over).

### 5.4 Intentionally DEFERRED (later rungs / IMPERFECTIONS)

- **Ritual net-mana**: Desperate Ritual / Pyretic Ritual / Manamorphose must produce
  NET-POSITIVE mana for the chain to reach lethal storm count. Verify the mana model gives
  net mana; if not, the storm count in real matches will be capped low. Tracked imperfection
  (the WR will under-read until rituals ramp correctly). Do NOT fake it.
- **Ruby Medallion cost reduction**: not in `_COST_REDUCTIONS` (game_state.py L74). Red
  spells should cost {1} less; without it the chain is shorter than reality.
- **Past in Flames recursion**: flashback-all-I/S-in-GY for a second storm chain (handler
  L12877 only grants flashback; the APL must replay). Deferred.
- **Pyromancer Ascension**: 2-quest-counter spell-doubling. Deferred.
- **Generic Storm-keyword coverage**: storm copy is hand-coded per card (Grapeshot, Empty
  the Warrens, Galvanic Relay). A handler-less storm card copies nothing. A generic
  keyword primitive (read storm count, copy the spell's effect) is a real future item but
  is NOT R3's gate (section 0 -- it would double-count the existing handlers). Extend
  per-card, or build the generic primitive as its own gated rung later.
- **General main1-damage-sync gap**: 1.2 opens the fix ONLY for storm-opted decks. Every
  other deck's main-phase-1 face burn is still dropped on the match path. The clean
  ungated fix (sync main1 damage for all decks) is a separate, broader change requiring its
  own full Class-A re-proof. Tracked imperfection.
- **Optional gated early win-check** after the main1 sync (1.2) so a main1 storm kill
  registers without waiting for the post-main2 check. Inert for creatureless storm; deferred.

### 5.5 P6 proof artifact (written ONLY after green; mirror the R4 JSON)

On a green pass, write `mtg-sim/modelability_proofs/r3-storm-2026-06-27.json` mirroring
`r4-warp-2026-06-26.json`: `branch_point_commit`, `reference_tree`, `design_doc:(this
file)`, `narrowing:(WANTS_STORM on the rewritten Ruby Storm APL only)`, `pass_fail_table`
(LIFECYCLE / NR_boros_bit_identical / NR_amulet_bit_identical / NR_goldfish_storm_identical
/ STORM_PAYOFFS_RESOLVED_fires / fidelity_gate_credits / all_gate_suites_green),
`storm_exercises:(STORM_PAYOFFS_RESOLVED + avg copies)`, `wr_anchor:(band,
data_quality:medium)`, `risks_and_imperfections` (the 5.4 list), `honest_caveats`
(storm was half-built; engine change is the match-path damage sync, not a copy primitive;
arl_profile JSON gains a storm:0 key so it is gate-verdict-identical, not byte-identical),
`stop_status:"STOPPED before merge"`. MERGE HELD FOR USER. `_proof("r3-")` keys off this
file's existence -- so write it as the LAST step (the credit and the proof land together).

### 5.6 Honest fallback (if 1.2 proves intractable in the spike budget)

Ship R3 with ZERO engine change: rewrite the Ruby Storm APL to (a) route through
`cast_spell` and (b) cast the storm PAYOFF in `main_phase2_match` (which already syncs
damage via `_run_post_combat_phase`, L554-558). Storm then works + propagates with no
shared-path edit; byte-identical-OFF is trivial (no engine change at all); WANTS_STORM
becomes a pure fidelity-credit flag. This is strictly less faithful (real storm kills in
main1) and hides the general main1-damage gap, so it is the FALLBACK, not the plan. If
taken, the proof headline must state the engine was unchanged and the gap remains open.

---

## 6. GO / NO-GO recommendation

**NO-GO for autonomous implementation now. HOLD for user review.**

Rationale: this is a design "for review BEFORE any engine code" (the explicit framing).
R3 edits a shared-path file (`match_runner._simple_play_turn`) and rides the same sharp
bit-identical gate as R4; the merge target is the verified R1+R2+R4+R5 stack, so a leak
would damage proven work. R3 is also UNUSUAL (storm is half-built), so the user should
confirm the framing -- engine fix (1.2) vs honest fallback (5.6) -- before any code.

Middle option (forward motion, fully reversible): a bounded SPIKE off the current
trilogy+R4 HEAD -- `EnterWorktree modelability/r3-storm`, freeze baselines, implement just
`_storm_match_gate` + the gated main1 sync (1.2) + base `WANTS_STORM=False` + the Ruby
Storm APL rewrite (1.3) + the four fidelity edits (section 3), prove
`test_r3_storm_lifecycle.py` RED-pre / GREEN-post + Class-A/A' bit-identical + all gate
suites green, then STOP before merge. Discardable via `ExitWorktree`.

Recommended: HOLD. On approval, run the spike (engine path 1.2 first; fall back to 5.6 only
if 1.2 is intractable), then the full acceptance gate.

---

## Appendix - file-change list (absolute paths)

- MOD   E:/vscode ai project/mtg-sim/engine/match_runner.py  (NEW `_storm_match_gate` mirroring `_warp_match_gate` L674; GATED main1 spell-damage sync inside `_simple_play_turn` L261-268)
- MOD   E:/vscode ai project/mtg-sim/apl/match_apl.py  (base `WANTS_STORM = False`, alongside the existing four WANTS_* flags L44-80)
- MOD   E:/vscode ai project/mtg-sim/apl/ruby_storm_match.py  (REWRITE `main_phase_match` to cast via `gs.cast_spell`; payoff cast last; `WANTS_STORM = True`; drop the `AUTO_GENERATED` manual-cast path)
- MOD   E:/vscode ai project/mtg-sim/scripts/arl_profile.py  (`_detect_mechanics` storm key + `_STORM_RE`; `_severity_for_counts` storm rule; `_apl_modeled_capabilities` WANTS_STORM + `_proof("r3-")`; NOT_modeled phrasing in `assess_engine_fidelity`)
- MOD   E:/vscode ai project/mtg-sim/data/engine_fidelity_map.json  (add `"storm": "engine-fidelity-gaps-storm-mechanic-match-path"`)
- MOD   E:/vscode ai project/mtg-sim/engine/card_handlers_verified.py  (OPTIONAL: module-global `STORM_COPIES_DEALT`/`STORM_PAYOFFS_RESOLVED` counters + `reset_storm_count()` for the exercise gate -- pure bookkeeping, zero RNG)
- KEEP  E:/vscode ai project/mtg-sim/engine/game_state.py  (`cast_spell` HAND path, `spells_cast_this_turn` increment/reset, goldfish tick) UNCHANGED
- KEEP  E:/vscode ai project/mtg-sim/engine/card_handlers_verified.py storm handlers (`_grapeshot_spell` L9797, `_empty_the_warrens` L8303, `_galvanic_relay` L9449) UNCHANGED (except the optional counters above)
- KEEP  E:/vscode ai project/mtg-sim/apl/ruby_storm.py (goldfish) UNCHANGED
- KEEP  E:/vscode ai project/mtg-sim/engine/counter_resolver.py UNCHANGED
- ADD   E:/vscode ai project/mtg-sim/tests/test_r3_storm_lifecycle.py
- ADD   E:/vscode ai project/mtg-sim/tests/test_r3_storm_exercises.py
- ADD   E:/vscode ai project/mtg-sim/modelability_proofs/r3-storm-2026-06-27.json  (written ONLY after green; `_proof("r3-")` keys off it)
- UPDATE (on approval, not now)  E:/vscode ai project/harness/specs/_index.md  (register this spec)

## Changelog

- 2026-06-27: Authored. KEY DISCOVERY: storm is HALF-BUILT -- storm count
  (`spells_cast_this_turn`) + copy-on-resolve already exist at the handler layer and work
  in goldfish (`_grapeshot_spell` L9800), so R3 is fundamentally unlike R1/R2/R4/R5. The
  real walls are (a) storm is invisible to the fidelity gate (false-high), (b) the
  AUTO_GENERATED Ruby Storm match-APL bypasses `cast_spell` so storm count never accrues on
  the match path, and (c) main-phase-1 spell damage is dropped on the match path
  (`_simple_play_turn` syncs no damage; `_run_post_combat_phase` does). Resolved the gate
  scope in favor of a per-APL `WANTS_STORM` narrowed to one opt-in APL, gating the genuine
  new surface (match-path main1 damage propagation, mirroring R4's gated match-tick),
  REJECTING a fabricated generic-copy primitive (would double-count the existing handler).
  Bulk of R3 = fidelity-gate wiring (detect/severity/credit/map). Honest fallback (5.6):
  zero-engine-change via casting the payoff in main_phase2 if the gated main1 sync proves
  intractable. NO-GO autonomous / HOLD; spike-first on approval.
