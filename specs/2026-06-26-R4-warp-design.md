---
title: R4 Warp Cast-from-Exile Increment - Implementation Design
status: PROPOSED
created: 2026-06-26
project: mtg-sim
related:
  - harness/specs/2026-06-26-modelability-ladder.md  (R4 rung definition)
  - harness/specs/2026-06-26-archetype-capability-profiles.md  (fidelity gate / backlog)
  - harness/specs/2026-06-26-R1-stack-priority-design.md  (gate + narrowing precedent; synthesis format)
  - harness/specs/2026-06-26-R2-instant-combat-design.md
  - harness/specs/2026-06-26-R5-planeswalker-loyalty-design.md
  - mtg-sim/engine/game_state.py  (cast_spell_warp L711, _tick_warp L757, _WARP_CARDS L700, cast_spell L1344, put_into_play L1476)
  - mtg-sim/engine/match_runner.py  (_run_end_step L1058, called L1232/L1240)
  - mtg-sim/engine/match_engine.py  (run_match L148)
supersedes:
  - harness/specs/2026-06-26-R4-warp-mechanic-design.md  (xmage-report draft; folded in here)
superseded_by:
---

# R4 Warp Cast-from-Exile Increment - Implementation Design

> Synthesis of three read-only reports (engine seam map / XMage pattern-ref / proof
> plan). This is a reviewable DESIGN, not engine code and not a proof.json. It states
> the SMALLEST increment that models Warp -- warp-cost cast from hand, delayed end-step
> exile, later cast-from-exile -- layered on the existing engine so that non-Warp decks
> are BIT-IDENTICAL when the gate is off, and so that R4 composes with the verified
> R1+R2+R5 trilogy as a 4th independent gate. ASCII-only. See section 6 for GO/NO-GO.

## 0. The one synthesis call that drives everything (the gate spine)

The three reports quietly disagree on ONE point -- the gate scope -- and resolving it is
the spine of this design (same shape as the R1 synthesis call).

- **Engine report**: gate everything "by `_WARP_CARDS` membership," i.e. auto-enable for
  any deck holding a warp card, mirroring `_priority_stack_enabled`.
- **XMage report**: gate ONLY the recast (`WANTS_WARP_RECAST`); leave warp-cast and the
  end-step exile ungated, because goldfish already exiles correctly.
- **Proof report**: gate the ENTIRE new R4 behavior behind a single per-APL `WANTS_WARP`,
  narrowed to ONE opt-in APL (Jeskai Blink) for the spike.

These cannot all hold, because of one load-bearing engine fact all three reports confirm:

> The end-step exile tick `_tick_warp` (game_state.py L757) FIRES in the goldfish loop
> (driven from `next_turn`, L628) but is NEVER called on the match path -- there is no
> `_tick_warp` reference anywhere in `match_runner.py` or `match_engine.py`. So the three
> match decks that already call `cast_spell_warp` (izzet_looting, azorius_high_noon
> L428, dimir_midrange_jermey L1077) get a permanent body for the cheap cost FOREVER --
> a silent inflation bug. Cast-from-exile does not exist anywhere.

So two of Warp's three sub-mechanics already ship (warp-cast + goldfish exile); only
cast-from-exile is genuinely absent, and the match-path exile tick is unreachable.

**Decision (authoritative for R4): gate the NEW behavior** -- match-path end-step tick
wiring + cast-from-exile -- **behind a single per-APL flag `WANTS_WARP`, default False,
narrowed to ONE opt-in APL** (the Jeskai Blink representative running 4x Quantum Riddler).
The existing goldfish tick (L628) is left untouched.

Why each rival framing is rejected:

- **Reject XMage's "gate only the recast."** The match-path exile tick is ALSO new
  behavior (it does not run today). Wire it ungated and the 3 current match warp-casters
  exile their creatures at end step with NO recast path -> they strictly lose tempo
  overnight -> a WR regression, not a bugfix. The tick must be gated too.
- **Reject the engine report's literal "auto-enable by `_WARP_CARDS` membership."** That
  would flip those same 3 buggy decks ON automatically and regress them. (Note: the
  engine report's chosen analog, `_priority_stack_enabled`, actually keys off the APL's
  `WANTS_*` flag, not card membership -- so its own intent backs the per-APL flag even
  though its "by membership" phrasing does not. This is not a real conflict.)
- **Adopt the proof report's per-APL narrowing.** It is the direct application of the R1
  NARROWING lesson: the R1 spike first put its gate on the base class, flipped all ~38
  decks, and broke bit-identical; the fix moved the opt-in onto one subclass. R4 reuses
  that precedent verbatim.

This single decision makes every required property fall out of the same gate:

1. **Bit-identical (non-Warp + non-opted-in decks):** gate defaults OFF -> they run the
   exact trilogy lines, zero new `random()` on the shared path, no exile tick in match,
   no recast. (Deliverable 3.)
2. **Proof differential:** the Jeskai Blink APL flips `WANTS_WARP=True` -> the end-step
   exile + cast-from-exile path is reachable post-R4 and NOT reachable pre (gate OFF =
   today's persist-forever match path) -> RED pre / GREEN post. (Deliverable 1.)
3. **Trilogy composition:** R4 is a 4th independent gate beside `WANTS_PRIORITY_STACK` /
   `WANTS_INSTANT_COMBAT` / `WANTS_PW_LOYALTY`; with R1 also on, the (optionally
   stack-promoted) return can be Consign'd -- so R4 COMPOSES rather than replaces.

RECONCILING THE LADDER SPEC. The modelability-ladder R4 line ("wire `_tick_warp` into the
match path; re-run Izzet Affinity + Goryo's, no regression now that `_tick_warp` actually
runs") reads as if ungated wiring were intended. Do NOT silently follow it -- it
contradicts bit-identical. REINTERPRET (record the amendment): for non-opted-in warp
decks, "no regression" means **gate OFF -> no crash + behavior unchanged from the trilogy
baseline** (the buggy-but-stable persist-forever path), NOT "`_tick_warp` runs for them."
The clean fix for those 3 decks (opt each in + add cast-from-exile-aware APL logic, then
re-prove) is a tracked IMPERFECTION (section 5.4), not part of R4's proof.

---

## 1. Exact engine changes (smallest increment; XMage cited as PATTERN, not copied)

Pattern reference (MIT, github-discovery flagged): XMage `WarpAbility.java`
(magefree/mage, `Mage/src/main/java/mage/abilities/keyword/WarpAbility.java`) composes
Warp from three separable objects -- `WarpAbility extends SpellAbility`
(`spellAbilityType = BASE_ALTERNATE`, replaces mana costs with `ManaCostsImpl<>(...)`);
`WarpAbilityWatcher` + `AtTheBeginOfNextEndStepDelayedTriggeredAbility` (schedules the
exile on a warped ETB); `WarpExileEffect.apply()` + `CardUtil.makeCardPlayable(...)` under
a `WarpCondition` (exile into a tracked zone, grant cast-from-exile only on a LATER turn).
DESCRIBE-DO-NOT-COPY mapping onto our seams (all line numbers verified on main 2026-06-26):

| XMage concept | Our existing hook | R4 action |
|---|---|---|
| BASE_ALTERNATE cost / ManaCostsImpl(manaString) | `cast_spell_warp` pays `warp_cost_str` (game_state.py L711-755) | EXISTS -- reuse |
| checkIfPermanentWarped flag | `card._warp_cast = True` (L746) | EXISTS -- reuse |
| WarpAbilityWatcher + AtTheBeginOfNextEndStepDelayedTriggeredAbility | `_tick_warp` end-step flag-scan (L757-767), already run in goldfish (L628) | WIRE into the match end-step seam, GATED (1.2) |
| WarpExileEffect.apply() + makeCardPlayable() + WarpCondition | (does not exist) | NEW: per-card markers + cast-from-exile via `cast_spell` (1.3) |

### 1.1 Alternate-cost cast from hand -- ALREADY EXISTS, reuse

`cast_spell_warp` (game_state.py L711-755) looks up `_WARP_CARDS` (L700-709, a 7-entry
`{name: (warp_cost_str, warp_cmc)}` dict), pays the cheaper cost via the existing
`ManaPool.can_cast/pay` (mana.py L148-186), plays the card, fires ETB, and sets
`card._warp_cast = True` (L746). NO new alt-cost system is needed for the increment.

Anti-pattern noted (do NOT propagate): `cast_spell_warp` currently DUPLICATES the High
Noon / Voice / Cosmogrand legality checks that `cast_spell` already has. The recast (1.3)
must NOT duplicate them again -- it routes through `cast_spell`. (A later cleanup can route
warp-cast through `cast_spell` too; out of scope for the minimal increment.)

### 1.2 Delayed end-step exile -- the tick EXISTS; wire it into the match path (gated)

There is NO general delayed-triggered-ability queue in the engine. The pattern is a
per-card flag scanned by a fixed end-step routine (`_warp_cast`, like
`_sacrifice_at_eot` / `time_counters`). Per the task's "reuse existing trigger infra if
any, else minimal new scheduler" -- the flag-scan `_tick_warp` IS the mechanism. The
minimal move is to wire it into the match end step, gated. NO new scheduler.

- Add, at the match end-step seam `match_runner._run_end_step` (L1058; called for each
  player at L1232 / L1240): `if _warp_match_gate(gs): gs._tick_warp_player(active_player)`.
- `_warp_match_gate(gs)` mirrors the trilogy's `_pw_match_gate` (the `getattr(apl_a/apl_b,
  "WANTS_*", False)` pattern R5 added): True iff `apl_a` OR `apl_b` declares `WANTS_WARP`.
- BIT-IDENTICAL BY CONSTRUCTION: when the gate is off, `if _warp_match_gate(gs): ...` is a
  pure no-op -> the end-step code path is byte-identical to the trilogy baseline (same
  call order, zero new `random()`). This is the R1 guard-token proof reused.
- PER-PLAYER, not global. `_tick_warp` (L763) scans a single `self.zones.battlefield`;
  match has TWO states. Exile is a FLAT, SHARED list (Plot / removal / blink all land
  there), so warped cards are tracked by PER-CARD markers, not a named zone (XMage uses a
  named per-player exile zone; we collapse it to markers -- see 1.3). The match tick must
  scan the active player's battlefield only.
- Goldfish path (game_state `next_turn` L628) is UNTOUCHED.

OPTIONAL composability upgrade (DEFERRED, not core): promote the return from an inline
exile to a stack-identified trigger on `engine/stack.py` so R1's priority pass can let an
opponent Consign it. This is scope creep for the minimal increment -- keep the core as
flag-scan; the stack-trigger promotion + Consign + Ephemerate are bonus (section 5.3).

### 1.3 Cast-from-exile -- the one GENUINELY NEW engine surface

This is the only piece absent everywhere. `cast_spell` (L1344) plays from `zones.hand`;
`put_into_play(from_zone="exile")` (L1476) exists but is a free cheat-in -- it skips cost
payment AND the counter/stack window. Neither is the recast. Do NOT use `put_into_play`
(both engine + proof reports flag this; it would bypass cost, the counter window, and any
"when you cast" trigger e.g. Warped Tusker, contradicting trilogy composition).

Design (sibling-method precedent: `cast_spell_impending` at L769 is the exact
registry-dict + parallel-method shape -- the recast should mirror it):

1. On warp-exile (the gated tick, 1.2): set `card._warp_recastable = True` and
   `card._warp_exiled_turn = gs.turn`; clear `card._warp_cast`. (XMage `makeCardPlayable`
   + `WarpCondition` collapsed into two markers, because exile is a flat shared list.)
2. Add a gate-guarded recast path `cast_spell_from_warp_exile(card)` that, for a
   `_warp_recastable` card in `gs.zones.exile`, pays the card's **FULL `card.mana_cost`**
   (NOT the warp cost) by REUSING `cast_spell`'s payment + counter window + (R1) stack
   routing -- do not duplicate them. It then clears `_warp_recastable` / `_warp_exiled_turn`
   so the card cannot loop. BIT-IDENTICAL BY CONSTRUCTION: this is reached only when the
   opted-in APL's cast loop considers exile cards under `WANTS_WARP`; `cast_spell`'s HAND
   path is not edited.
3. WarpCondition analog: recast is legal only on a LATER turn --
   `gs.turn > card._warp_exiled_turn`. Illegal on the exile turn itself.

The integration seam the proof report found: `put_into_play` (L1476) has no `'exile'`
REMOVAL branch despite its docstring listing exile -- so the recast must explicitly remove
the card from `gs.zones.exile` before it enters the battlefield (no double-presence).

---

## 2. The capability gate (so ONLY warp decks change)

Mirrors the trilogy gate discipline exactly (R1 `WANTS_PRIORITY_STACK`, R2
`WANTS_INSTANT_COMBAT`, R5 `WANTS_PW_LOYALTY`).

- Base `MatchAPL` / `AwareMatchAPL`: add class attr `WANTS_WARP = False`. Every existing
  deck (and the 3 buggy warp-casters) inherits False -> exact current path, no exile tick
  in match, no recast.
- Jeskai Blink representative APL (the opt-in for the spike): set `WANTS_WARP = True` and
  add exile-recast consideration to its cast loop (consider `_warp_recastable` cards in
  `gs.zones.exile`, pay full cost via `cast_spell_from_warp_exile`).
- `match_runner._warp_match_gate(gs)`: the read site (1.2), `getattr`-based, defaults
  False. No per-card auto-enable -- per-APL opt-in only (section 0 rationale).

Net: a deck that does not opt in never touches any new code; bit-identical follows.

---

## 3. Build plan -- isolated git worktree off the trilogy branch

Main `mtg-sim` and the trilogy branch are never mutated until green; merge held for user.

1. `EnterWorktree` branch **`modelability/r4-warp`** (mirrors R1's
   `modelability/r1-stack-priority`), worktree dir
   **`E:/vscode ai project/mtg-sim-r4`**, branched off `modelability/trilogy-integration`.
2. PIN + RECORD the branch point. Task cites `deee281` ("Integrate R1+R2+R5 trilogy");
   the trilogy HEAD is one commit further, `e882937` ("cross-gate SUBTEST D"), part of the
   same verified trilogy proof. Pin the R4 branch point at the trilogy HEAD so the
   no-regression diff runs against the FULL verified trilogy. Record both
   (`branch_point_commit = e882937`, includes deee281) and
   `reference_tree = mtg-sim @ modelability/trilogy-integration`. The no-regression
   comparison is **against the trilogy branch, NOT main.**
3. FREEZE baselines at the branch point FIRST (before any engine code): capture the
   Class-A bit-identical aggregates + the RED-pre result of the new proof test on this
   exact commit.
4. Implement in dependency order: (a) per-card markers + `cast_spell_from_warp_exile`
   (game_state.py); (b) gated `_warp_match_gate` + tick wiring (match_runner.py);
   (c) base `WANTS_WARP=False`; (d) Jeskai Blink APL `WANTS_WARP=True` + exile-recast cast
   loop.
5. Write `tests/test_r4_warp_lifecycle.py` + `test_r4_warp_exercises.py`; run RED-pre
   against the frozen branch point.
6. Integrate-and-prove the full acceptance gate (section 4) inside the worktree.
7. Merge to the trilogy branch ONLY IF every gate is green. On any abort (5.3),
   `ExitWorktree` + discard; leave the backlog item with an IMPERFECTIONS note.
   Merge-only-if-green.

---

## 4. Proof + no-regression harness (acceptance gate, from report 3)

R4 is PROVEN iff ALL of the following hold.

### 4.1 DELIVERABLE 1 -- proof-by-replication (the warp lifecycle line)

New `tests/test_r4_warp_lifecycle.py` (standalone, `sys.path.insert`, plain asserts,
ASCII, prints "ALL R4 PROOF TESTS PASS", exit 0/1; same conventions as
`tests/test_determinism.py`). Construct `TwoPlayerGameState` directly and HAND-PLACE
cards (do not run a full match -- mulligans make it fragile). The test self-declares
`WANTS_WARP` per phase (False for RED, True for GREEN).

Card: Quantum Riddler (`_WARP_CARDS` L702: warp `{1}{U}` = 2 mana; full `{3}{U}{U}` = 5
mana; ETB draws).

- RED-pre (gate OFF == current trilogy behavior): on the MATCH path the warp creature is
  cast for 2, ETB fires, and then NEVER exiles -- it persists as a permanent 5-mana body;
  no cast-from-exile path exists; the value leg is entirely absent. Assert (must hold
  pre): after end step the creature is STILL on battlefield; `gs.zones.exile` does not
  contain it; no second ETB. These FAIL to show the lifecycle -> the differential is real.
- GREEN-post (gate ON): (1) warp-cast pays exactly 2, ETB fires, `_warp_cast=True`;
  (2) end step -> gated `_tick_warp` moves it to `gs.zones.exile`, `_warp_recastable=True`,
  `_warp_exiled_turn=T`; (3) a LATER turn -> recast FROM EXILE pays the FULL 5
  (`{3}{U}{U}`), ETB fires AGAIN, markers cleared.
- DISCRIMINATORS: (i) exile happened (battlefield-absent + exile-present after end step);
  (ii) `first_cast_cost == 2` AND `second_cast_cost == 5` -- DIFFERENT costs prove "used
  twice for full value," not merely "exiled"; (iii) ETB fired TWICE; (iv) recast NOT legal
  on the exile turn, legal from the next turn.
- GATE ON THE TEST ITSELF: the GREEN assertions MUST FAIL on the frozen branch point. If
  they pass pre-R4 the test is not discriminating -> fix the test before any R4 claim.

### 4.2 DELIVERABLE 2 -- behavior / WR anchor (warp cards used twice)

- PRIMARY metric (the load-bearing gate, not a WR delta): module-global pure-integer
  counters `WARP_CAST` + `RECAST_FROM_EXILE` (+ `reset_fire_count()`), analog of R1's
  `COUNTERS_CAST`. Pure bookkeeping: zero `random()`, no state mutation -> determinism
  preserved. EXISTENCE GATE: `RECAST_FROM_EXILE > 0` and
  `WARP_CAST > RECAST_FROM_EXILE >= 1` over `run_match_set` (single process, `n_workers=1`
  so in-process counters are visible) of Jeskai Blink (`WANTS_WARP=True`) vs a real
  engine-running FAIR opponent (e.g. Boros Energy / Izzet Prowess), n=60, seed=42.
- WR ANCHOR (SOURCED): `mtg_meta.db.matchup_matrix`, format=modern, archetype='Jeskai
  Blink' -> match-weighted aggregate 49% across 30 matchups / 6420 matches (mirror 50%,
  n=960), pulled 2026-06-26. Band: 49% +/- 2pp at n >= 1000, tagged `data_quality:medium`
  (until R1 models the counterspell mirror). WR is the SECONDARY anchor; the COUNT gate is
  primary. Do NOT promote on WR alone.
- CURVE-SHIFT prediction (Rule 5, written BEFORE the run): warp tempo + later recast value
  shifts modeled `jeskaiblink` clock mass from ~T7 toward T5-6 (direction DOWN). A run
  whose sign CONTRADICTS this (clock slower / mass to T8+) is a STOP condition.
- HONEST MAGNITUDE: R4 is LOW-WR by design -- 4-of consistency means a fresh copy is
  usually drawn anyway, so the recast leg fires occasionally, not every game. The value is
  fidelity + composability, not a WR jump. A LARGE WR delta is an ABORT signal, not a win.

### 4.3 DELIVERABLE 3 -- no-regression (two classes + trilogy)

Comparison reference = the trilogy tree at `e882937` (NOT main).

- CLASS A -- bit-identical, MUST hold: Boros Energy (goldfish, seed 42, n>=50) and Amulet
  Titan (goldfish, seed 42, n>=50) byte-identical between the trilogy reference tree and
  the R4 worktree (win%, avg/median kill turn, win-by-Tn, mulligans). Plus a non-warp
  modern gauntlet (seed 42) FWR byte-identical pre/post. These never touch warp code.
- CLASS B -- non-opted-in warp decks (azorius_high_noon, dimir_midrange_jermey, goryo's):
  gate OFF -> NO CRASH + behavior unchanged from the trilogy baseline (the persist-forever
  path). "No regression" for these = unchanged, NOT "`_tick_warp` runs" (section 0).
- TRILOGY SUITES still green on the R4 branch: `test_r1_stack_priority.py`,
  `test_r1_control_exercises.py`, `test_r2_instant_combat.py`,
  `test_r5_planeswalker_loyalty.py`, `test_trilogy_cross_gate.py`, `test_determinism.py`
  -- all exit 0. R4 adds a 4th gate; it must not perturb R1/R2/R5.
- DETERMINISM: re-run the gate-ON Jeskai Blink exercise twice at seed 42 -> byte-identical
  (same FWR, per-matchup %, WARP_CAST / RECAST_FROM_EXILE counts).
- ISOLATION: `counter_resolver.py` byte-identical UNLESS the Consign bonus sub-line (5.3)
  is in scope -- in which case the proof.json `isolation_note` must declare that edit.

### 4.4 DELIVERABLE 4 -- ABORT / STOP conditions (Rule 4, teeth)

- Lifecycle line not reproducible within the rung budget -> ABORT, IMPERFECTIONS entry,
  item stays `unmodelable`.
- `RECAST_FROM_EXILE == 0` over the seeded exercise -> ABORT; mechanism not load-bearing.
- WR cannot reach 49% +/- 2pp at n>=1000 -> record as APL-TUNING-TODO, do NOT promote, do
  NOT widen the band.
- Curve-shift sign CONTRADICTS the written prediction -> STOP, investigate, resume only
  with a documented amendment.
- R4-SPECIFIC (the R1-narrowing failure mode): bit-identical BREAKS for ANY non-warp deck
  (Class A) -> ABORT immediately -- `WANTS_WARP` leaked off the single opt-in. Re-narrow.
- Any trilogy suite goes red on the R4 branch -> ABORT (R4 broke composition).
- Determinism leak: global random state mutated by the R4 path -> ABORT; RNG purity is
  non-negotiable.

---

## 5. Honest effort / risk + deferred scope

### 5.1 Effort and risk

R4 is LOW effort relative to the R1 long pole -- two of three sub-mechanics already ship;
the only genuinely new code is `cast_spell_from_warp_exile` plus wiring an existing tick
into the match end step. This is a one-to-few-sitting change, not a multi-week pole.
Highest risks, in order:

1. Bit-identical leak: `WANTS_WARP` placed on the base class instead of the one opt-in
   subclass (the exact R1 spike regression) -> Class A breaks. Mitigated by per-APL
   narrowing + the no-op-when-off guard tokens (1.2, 1.3).
2. Flat-exile trackability: exile is a shared list (Plot / removal / blink land there); a
   marker collision or a missed clear could recast a non-warp exiled card or loop a warp
   card forever. Mitigated by `_warp_recastable` + explicit clear on recast + the
   `gs.turn > _warp_exiled_turn` guard.
3. Cast-from-exile zone move: must remove the card from `gs.zones.exile` before it enters
   battlefield (no `'exile'` removal branch in `put_into_play` today) -> double-presence
   if missed.
4. Recast must NOT re-arm `_warp_cast`, or the creature re-exiles next end step (loop).

### 5.2 What R4 PROVES

The MECHANISM (warp-cast tempo now -> delayed exile -> later recast for full value) on
Quantum Riddler, gated and composable with the trilogy. Not full-field warp coverage.

### 5.3 Bonus / optional (composes with R1; defer if it threatens the core)

- Stack-trigger promotion of the return (1.2 optional) so the return has a stack identity.
- Consign to Memory on the return trigger (requires R1 gate ON + a `counter_resolver.py`
  edit -> declare in `isolation_note`).
- Ephemerate / Phelia blink of a warped creature -> new object, clear `_warp_cast`,
  creature stays permanent (linkage broken; `ephemerate.py` already special-cases Quantum
  Riddler).

### 5.4 Intentionally DEFERRED (later rungs / IMPERFECTIONS)

- The 3 current match warp-casters keep the persist-forever bug until each is opted in +
  given cast-from-exile-aware APL logic and re-proven (the clean fix; IMPERFECTIONS item).
- `_WARP_CARDS` registry expansion: only 7 entries today; ~20+ warp cards are documented
  in handler oracle text (Anticausal Vestige, Pinnacle Emissary, Susurian Voidborn, etc.).
  R4 proves the mechanism, not full coverage. Extend per-card later, then per-deck reprove.
- COMPLEX warp cards (Void / "warped this turn" payoffs: Alpharael, Roving Actuator,
  Temporal Intervention, Full Bore) -> later.
- REPLACEMENT-EFFECT interactions with the exile move (replacement/redirection effects) ->
  later.
- Routing warp-cast itself through `cast_spell` to delete its duplicated High Noon / Voice
  / Cosmogrand checks (cleanup, not behavior).
- Extending the second runner (`match_engine.run_match`) if the spike proves only on the
  runner the Jeskai Blink APL actually executes (verify during the spike; default to the
  canonical R1 path discipline).

### 5.5 P6 proof artifact (written ONLY after green; mirror the R1 JSON)

On a green pass, write `mtg-sim/modelability_proofs/r4-warp-<date>.json` mirroring
`r1-stack-priority-2026-06-26.json`: `branch_point_commit:e882937`, `reference_tree`,
`design_doc:(this file)`, `narrowing:(WANTS_WARP on Jeskai Blink only)`, `pass_fail_table`
(LIFECYCLE / NR_boros_bit_identical / NR_amulet_bit_identical / RECAST_FROM_EXILE_fires /
WR_anchor_jeskai_blink / trilogy_suites_green), `warp_exercises:(WARP_CAST +
RECAST_FROM_EXILE)`, `wr_anchor:(49% band, data_quality:medium)`,
`risks_and_imperfections`, `stop_status:"STOPPED before merge"`. MERGE HELD FOR USER.

---

## 6. GO / NO-GO recommendation

**NO-GO for autonomous implementation now. HOLD for user review.**

Rationale: the user explicitly framed this as a design "for review BEFORE any engine
code." A GO-autonomous call would contradict the request. Independent of framing, R4
edits a shared-path file (`game_state.py`) and rides a sharp bit-identical gate that is
easy to violate silently -- exactly the class one does not start autonomously before the
design is approved. (R4 is lower-risk than R1, but the merge target is the verified
trilogy branch, so a leak would damage proven work.)

Middle option (forward motion without committing to merge): a bounded, fully reversible
SPIKE off the trilogy HEAD `e882937` -- `EnterWorktree modelability/r4-warp`, freeze
baselines, implement just the markers + gated `cast_spell_from_warp_exile` + the gated
match-tick wiring + the one opt-in APL, prove `test_r4_warp_lifecycle.py` goes RED-pre /
GREEN-post + Class-A bit-identical + trilogy suites green, then STOP before merge.
Discardable via `ExitWorktree`.

Recommended: HOLD. On approval, run the spike first, then the full acceptance gate.

---

## Appendix - file-change list (absolute paths)

- MOD   E:/vscode ai project/mtg-sim/engine/game_state.py  (per-card `_warp_recastable`/`_warp_exiled_turn` markers set in tick; NEW `cast_spell_from_warp_exile` reusing cast_spell payment/counter/stack; explicit exile-zone removal; mirrors `cast_spell_impending` L769)
- MOD   E:/vscode ai project/mtg-sim/engine/match_runner.py  (`_warp_match_gate` helper; gated `_tick_warp` call at the `_run_end_step` seam L1058, per-player)
- MOD   E:/vscode ai project/mtg-sim/apl/match_apl.py  (base `WANTS_WARP = False`)
- MOD   E:/vscode ai project/mtg-sim/apl/<jeskai_blink representative APL>.py  (`WANTS_WARP = True` + exile-recast consideration in the cast loop)
- KEEP  E:/vscode ai project/mtg-sim/engine/game_state.py goldfish tick (L628) and `cast_spell` HAND path (L1344) UNCHANGED
- KEEP  E:/vscode ai project/mtg-sim/engine/counter_resolver.py  (UNCHANGED unless the Consign bonus 5.3 is in scope -> then declare in isolation_note)
- ADD   E:/vscode ai project/mtg-sim/tests/test_r4_warp_lifecycle.py
- ADD   E:/vscode ai project/mtg-sim/tests/test_r4_warp_exercises.py
- ADD   E:/vscode ai project/mtg-sim/modelability_proofs/r4-warp-2026-06-26.json  (proof artifact, written ONLY after green)
- SUPERSEDE  E:/vscode ai project/harness/specs/2026-06-26-R4-warp-mechanic-design.md  (xmage-report draft folded into this canonical doc; mark status SUPERSEDED)
- UPDATE (on approval, not now)  E:/vscode ai project/harness/specs/_index.md  (register this spec)

## Changelog

- 2026-06-26: Authored as the THREE-report synthesis (engine seam map / XMage pattern /
  proof plan). Resolved the three-way gate disagreement in favor of a per-APL `WANTS_WARP`
  narrowed to one opt-in APL (rejecting auto-enable-by-`_WARP_CARDS` and gate-only-recast).
  Smallest increment: reuse existing warp-cast + flag-scan tick (wired into the match end
  step, gated); the only new surface is cast-from-exile via `cast_spell` (NOT
  put_into_play). Bit-identical proven by no-op-when-off guard tokens. Branch point pinned
  to trilogy HEAD e882937. WR anchor sourced (Jeskai Blink modern 49%, n=6420). NO-GO
  autonomous / HOLD; spike-first on approval. Supersedes the xmage-report draft.
</content>
</invoke>
