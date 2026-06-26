---
title: R1 Stack-Priority Counterspell Increment - Implementation Design
status: PROPOSED
created: 2026-06-26
project: mtg-sim
---

# R1 Stack-Priority Counterspell Increment - Implementation Design

> Synthesis of three read-only reports (engine map / XMage-ref / proof-plan).
> This is the multi-week LONG POLE. R1 is scoped to the MINIMAL counterspell
> interaction increment, NOT full CR priority. See section 6 for the GO/NO-GO.

## 0. The one synthesis call that drives everything

The three reports quietly disagree on one point, and resolving it is the spine
of this design:

- Report 1 (engine map), Seam A, recommends *folding* the existing
  `try_counter_spell` into a new unified priority loop "as one legal response
  type."
- Report 3 (proof-plan), NR-1, demands the Boros Energy path be **bit-identical**
  pre/post R1.

These pull against each other: ANY refactor of the legacy counter window risks
perturbing call order or the RNG draw order and breaking bit-identical.

**Decision (authoritative for R1): do NOT fold or unify.** Keep the existing
synchronous counter window (`game_state.py:1353-1369`) and the existing resolve
block (`game_state.py:1370-1396`) literally untouched as the DEFAULT path. Add
the real-stack priority path as a PARALLEL branch that executes ONLY under an
opt-in capability gate. Unifying the two paths is deferred to R2+.

This single decision makes three required properties fall out of the same gate:

1. Back-compat / NR-1 bit-identical: gate defaults OFF -> non-control decks run
   the exact existing lines, with zero new `random()` draws on the shared path.
2. Proof differential (Report 3 TEST 1c): the control APL flips the gate ON ->
   true untapped-mana accounting is reachable post-R1, and NOT reachable pre-R1
   (legacy tap-agnostic pool) -> 1c is RED pre / GREEN post.
3. Counter-the-counter (Report 3 TEST 2): the gate is checked for BOTH the
   caster's APL and the opponent's APL, so the control deck gets priority back
   to counter a counter.

---

## 1. Exact engine changes

All seams below are verified against HEAD on 2026-06-26.

### 1.1 New module: `engine/priority_stack.py` (ADD)

The whole R1 mechanism lives here, isolated from the synchronous path.

```
run_priority_stack(caster_gs, card) -> str   # 'countered' | 'resolved'
```

Behavior:
- Instantiate the dormant `engine.stack.Stack` (stack.py:52) and push the
  original spell as a `StackItem` (caster tagged 'self'). The card stays in
  `caster_gs.zones.hand`; the StackItem only references it. (See 1.3 for why
  this matters for reuse of the legacy resolve block.)
- Run a bounded pass loop (XMage `playPriority` reduced to 2 players; see
  Report 2). State machine: `priority in {opp, caster}`, `passed_in_succession
  in {0,1,2}`, `depth_cap = 3` (counter / counter-the-counter / hard stop).
  - Opponent priority first: call `opp_apl.priority_action(opp_gs, caster_gs,
    stack)` -> returns `(counter_card, target_uid)` or `None` (pass).
  - On a cast: pay mana from the responder's ACTUAL untapped lands via the
    existing `tap_lands` machinery honoring `mana_reserve` (game_state.py:976;
    Seam D), remove the counter card from the responder hand, push it as a
    `StackItem`, reset `passed_in_succession = 0`, hand priority to the other
    player (this is the counter-the-counter window).
  - On pass: `passed_in_succession += 1`; when it reaches 2, resolve the top
    item via `stack.resolve_one()` (stack.py:91), then reset to 0.
- Resolution dispatch (R1 handles only two item kinds):
  - Top item is a COUNTER: mark its target item countered BY ID via the new
    `Stack.counter(uid)` (1.2), append the counter card to its caster's
    graveyard. (Mirrors XMage `Spell.counter()` / check-before-effect.)
  - Top item is the ORIGINAL spell and survived: STOP the loop and return
    `'resolved'`. `cast_spell` then falls through to the UNCHANGED legacy
    resolve block to do the real zone move + effects.
  - Top item is the ORIGINAL spell and is `countered`: move card to
    `caster_gs.zones.graveyard`, run `caster_gs.check_state_based_actions()`,
    log `[COUNTERED]`, return `'countered'`.
- HARD CONSTRAINT: this module performs ZERO `random()` calls. The decision is
  fully driven by APL heuristics and board state. (Abort condition G.)

R1 intentionally handles ONLY counterspell responses + original-spell
resolution. Removal / burn / bounce as on-stack responses are deferred to R2
(they would route through `resolve_interaction`, stack.py:227).

### 1.2 `engine/stack.py` (MODIFY - additive, surgical)

- Add `StackItem.uid: int` (monotonic, assigned in `Stack.cast`). The current
  `counter_top` (stack.py:86-89) marks `items[-2]` POSITIONALLY - correct only
  while exactly one spell is ever on the stack. With depth >= 2 it is wrong.
- Add `Stack.counter(uid)`: set `.countered = True` on the item with that uid
  (counter BY ID, per Report 2's one genuine correctness fix and XMage
  `getStack().counter(targetId)`). Keep `counter_top` for back-compat; do not
  call it from the new path.
- (Optional, for proof) Add a `max_depth` probe field updated on push, so
  TEST 2 can assert the stack reached depth >= 2.
- These are additive; nothing currently imports/uses this class on the live
  path, so there is no back-compat surface to break.

### 1.3 `engine/game_state.py` `cast_spell` (MODIFY - minimal, one guard token)

Insert the parallel branch immediately BEFORE the existing counter window
(before line 1353), and guard the existing window's `if` with a skip flag:

```
# R1 priority-stack path (opt-in; defaults OFF). Parallel to legacy.
_skip_legacy_window = False
if _priority_stack_enabled(self) and not getattr(self, '_in_counter_window', False):
    from engine.priority_stack import run_priority_stack
    result = run_priority_stack(self, card)      # 'countered' | 'resolved'
    if result == 'countered':
        return True                              # graveyard + SBA done inside
    _skip_legacy_window = True                    # opp already had the window

# EXISTING counter window - ONLY edit is the leading guard token:
if not _skip_legacy_window and not getattr(self, '_in_counter_window', False):
    ...                                          # lines 1353-1369 UNCHANGED
```

Then the existing resolve block (1370-1396: instant/sorcery -> graveyard +
effects; permanent -> `play_from_hand` + `_fire_etb_triggers`) is reused
VERBATIM for the surviving original spell. No `_resolve_spell_effect()` helper
is extracted - extraction would touch the legacy path and weaken the
bit-identical guarantee. (Advisor item 2.)

Bit-identical proof of the edit: for a deck with the gate OFF,
`_priority_stack_enabled` is False, the new block is skipped entirely (no calls,
no RNG), `_skip_legacy_window` stays False, and `if not False and not
_in_counter_window:` is logically identical to the original `if not
_in_counter_window:`. Same call order, same RNG stream. (Advisor item 4.)

`_priority_stack_enabled(gs)` (new helper, game_state.py): returns True iff
EITHER the caster's own APL OR the opponent's APL declares
`WANTS_PRIORITY_STACK = True`. Checking both directions is required for TEST 2:
in `cast_spell`, `self` is the caster, so a control deck casting its own
must-resolve spell must still open the window to counter the opponent's counter.
(Advisor item 3.)

### 1.4 `engine/match_engine.py` (MODIFY - additive wiring only)

Today (228-229) wires only the opponent APL onto each GameState
(`gs._match_opp_apl = opp_apl`). The both-directions gate also needs each gs to
know its OWN apl. Add, right beside the existing lines:

```
gs._self_apl = apl
opp_gs._self_apl = opp_apl
```

Additive new attribute; does not alter the legacy path's order or RNG. Applied
to the canonical interaction path (`match_engine.run_match`, the Bo3 / Path A
engine) ONLY. The SB-less fallback (`match_runner.py`) is NOT extended in R1;
R1 proves on the Bo3 path. (Unifying the two two-player runners is deferred.)

### 1.5 `apl/match_apl.py` base class + control APL (MODIFY)

- Base `MatchAPL` (match_apl.py:26): add class attr `WANTS_PRIORITY_STACK =
  False` and a default `priority_action(self, my_gs, opp_gs, stack) -> None`
  (always pass). This keeps every existing deck inert and the gate OFF for them.
- Control APL (`apl/aware_match_apl.py`, the UW/Jeskai-capable APL): set
  `WANTS_PRIORITY_STACK = True` and implement `priority_action`. The decision
  logic is LIFTED (copied, not deleted) from the existing
  `counter_resolver.COUNTER_VALIDITY` (counter_resolver.py:42), `_spell_value`
  (:92), and `_PRIORITY_COUNTER_TARGETS` (:71): given the top stack item, if it
  is a flagged must-answer threat and a legal/affordable counter is in hand,
  return `(counter_card, top_item.uid)`; else pass.

### 1.6 `engine/counter_resolver.py` (UNCHANGED in R1)

Left byte-for-byte intact - it IS the legacy default path that must stay
bit-identical. Its heuristics are referenced/copied into `priority_action`, not
removed. Deleting or unifying counter_resolver into the stack path is deferred
to R2. (Resolves the Report 1 vs Report 3 conflict in favor of bit-identical.)

### 1.7 How counter_resolver "upgrades" without breaking the synchronous path

It does not get edited. The UPGRADE is structural, not in-place: the same
intent (opponent may counter a spell) is now served by TWO implementations
selected by the gate -

- gate OFF -> `try_counter_spell` declarative reserve (unchanged, default), and
- gate ON  -> `run_priority_stack` real on-stack LIFO interaction.

A deck that does not need the stack never touches the new code. A control deck
opts in and gets a real stack. This is the minimal, reversible upgrade.

---

## 2. Mana-hold (reserve_mana) feeding the response window

The mechanism that lets a control deck hold UU and spend it to counter already
exists in pieces (Seam D); R1 wires them into the window instead of using
counter_resolver's synthetic back-fill.

1. `AwareMatchAPL.reserve_mana` (aware_match_apl.py:555) sets
   `gs.mana_reserve = N` before passing the turn / during its own main, marking
   N lands to be held up.
2. `GameState.tap_lands` (game_state.py:976) HONORS `mana_reserve`: it taps
   basics first and physically LEAVES `mana_reserve` lands untapped (holding
   duals). Because this sim has no untap step, those reserved lands stay
   physically untapped into the opponent's turn.
3. When the opponent casts a threat, `run_priority_stack` gives the control APL
   priority. `priority_action` decides to counter and pays UU by tapping the
   control deck's ACTUAL untapped lands via `tap_lands` - real tap-state spend,
   competing with nothing synthetic.
4. After paying UU, any lands reserved beyond the counter's cost remain
   physically untapped. This is exactly what makes Report 3 TEST 1(c) ("after
   the counter resolves, controller has >= 2 lands STILL untapped") assertable
   - and it is NOT assertable pre-R1, where
   `counter_resolver._tap_lands_for_response` (counter_resolver.py:100) fills
   the response pool from EVERY land tap-agnostically once per turn.

So the proof differential and the mana-hold mechanism are the same fact: R1
spends real held mana; the legacy path synthesizes it.

---

## 3. Build plan - isolated git worktree

Main `mtg-sim` is never touched until green.

1. `EnterWorktree` branch `modelability/r1-stack-priority` (per task; note Report
   3 used a divergent name `modelability/R1-jeskai_control` - the TASK name is
   authoritative, the report name is noted only so a future reader is not
   confused).
2. FREEZE baselines at the branch-point commit FIRST (Report 3 P4): capture
   NR-1 / NR-2 reference aggregates and the pre-R1 proof-test result on this
   exact commit before writing any engine code.
3. Implement in dependency order: (a) `stack.py` uid + `counter(uid)`; (b)
   `priority_stack.py`; (c) base `MatchAPL` default hook; (d) control APL
   `priority_action`; (e) `match_engine` `_self_apl` wiring; (f) `cast_spell`
   parallel branch + guard token.
4. Write `tests/test_r1_stack_priority.py` (section 4) and run the RED-pre check
   against the frozen branch-point commit.
5. Integrate-and-prove: run the full acceptance gate (section 4) inside the
   worktree.
6. Merge to main ONLY IF every gate is green. On any abort condition (section 5),
   `ExitWorktree` and discard the branch; leave the backlog item `unmodelable`
   with an IMPERFECTIONS note. Merge-only-if-green.

---

## 4. Proof + no-regression harness (acceptance gate)

R1 is PROVEN iff ALL of the following hold. (Report 3, verbatim intent.)

### 4.1 Proof (differential - must be RED pre-R1, GREEN post-R1)

New file `tests/test_r1_stack_priority.py` (standalone, `sys.path.insert`,
plain asserts, ASCII-only, prints "ALL R1 PROOF TESTS PASS", exit 0/1; same
conventions as `tests/test_determinism.py`). Construct `TwoPlayerGameState`
directly and HAND-PLACE cards (do NOT run a full match - mulligans make it
fragile). Wire `_match_opp` / `_match_opp_apl` / `_self_apl`, seed=42.

- TEST 1 - counter fires WITH mana-hold proven (kills the L3 differential):
  opp casts a flagged threat; assert (a) threat in opp graveyard not
  battlefield, (b) counter moved control hand -> graveyard, (c) AFTER resolve,
  control has >= 2 lands with `not c.tapped`. (c) FAILS pre-R1, PASSES post-R1.
- TEST 2 - depth-2 counter war (kills the L2 differential): control casts a
  must-resolve spell; opp counters; control counters the counter; assert stack
  reached depth >= 2 AND the original spell RESOLVES. FAILS pre-R1 (one-shot
  heuristic cannot reach depth 2), PASSES post-R1.
- TEST 3 - countered spell takes ZERO effect (check-before-effect): a countered
  burn/removal leaves opp life / target creature unchanged.

GATE ON THE TEST ITSELF: TEST 1(c) and TEST 2 MUST FAIL on the branch-point
commit. If they pass pre-R1 the test is not discriminating -> fix the test
before any R1 claim. Record paired pre/post results in
`modelability_proofs/r1-stack-priority-2026-06-26.json` (create dir).

### 4.2 WR anchor (statistical, two-tier)

- TIER 1 (the real WR GATE) - UW Control: field-weighted gauntlet MWR
  49.2% +/- 3pp at n >= 1000. R1 fully models this deck (minimal PW / hidden-info
  dependence). `python parallel_launcher.py --deck "UW Control" --format modern
  --n 1000 --seed 42`.
- TIER 2 (SANITY band, NOT a promotion gate) - Jeskai Control: 47.2% +/- 7pp.
  Jeskai carries two more blocking imperfections (PW loyalty R5, hidden info
  R6); R1 does NOT promote jeskai_control to "modeled". Only Tier 1 + the 1A
  line is the R1 acceptance event.

### 4.3 No-regression (sharp form: bit-identical)

- NR-1 (PRIMARY): Boros Energy mirror `run_match_set(..., n=1000, seed=42,
  mix_play_draw=True)` -> a_wins / b_wins / avg_turns IDENTICAL pre/post R1.
  Boros casts no permission; any delta = leak into the non-interactive path or
  RNG-stream perturbation. Doubles as a determinism guard.
- NR-2: Amulet Titan goldfish bit-identical at seed=42; T-turn within +/- 0.05
  of locked baselines (20-life 95.7% avg T7.11 / median T7; 17-life 95.9% avg
  T6.81 / median T6).
- NR-3: `python scripts/full_audit.py --formats standard` -> 4218/4218, all 17
  sets at 0 remaining (R1 is control-flow, not handlers).
- NR-4: `tests/test_modern_apls.py`, `test_all_modern_apls.py`,
  `test_standard_apls.py`, `test_determinism.py`, `test_match_engine.py`,
  `test_api.py` (bands 25<=a<=75, 20<=b<=80) all green.

Compare post-R1 against the FROZEN branch-point capture, not hardcoded
historical numbers.

---

## 5. Honest effort / risk + ABORT conditions

### 5.1 Effort and risk

This is the multi-week long pole, not a one-sitting change. The loop itself is
small; the real cost (per Report 2) is the APL decision interface and getting
on-stack mana payment + zone moves correct without disturbing the synchronous
path. Highest risks, in order:

1. RNG-stream / call-order leakage into the shared path breaking NR-1
   bit-identical (mitigated by the parallel-branch + zero-random discipline,
   but must be continuously checked).
2. The counter card's zone movement (hand -> stack -> graveyard) double-moving
   or desyncing with the legacy resolve block.
3. Counter-by-id correctness at depth >= 2 (the genuine bug being fixed).
4. Reserved-mana accounting not actually leaving lands untapped in practice,
   so TEST 1(c) cannot be made green honestly.

### 5.2 Intentionally DEFERRED to R2+ (R1 is the minimal increment)

- Full CR priority (every step/phase, APNAP, triggered-ability ordering).
- Removal / burn / bounce / pump as on-stack responses (R1 = counterspell
  responses + original-spell resolution only).
- Unifying / deleting `counter_resolver` and folding it into the stack path.
- Extending the SB-less `match_runner.py` fallback path.
- Promoting `jeskai_control` to "modeled" (needs R5 PW loyalty + R6 hidden
  info).
- Stack depth beyond 3; multi-target / split stacks.

### 5.3 ABORT conditions (discard the worktree, leave item unmodelable)

A. Proof not falsifying: TEST 1(c) or TEST 2 passes pre-R1 -> fix the test, no
   R1 claim until red-pre / green-post.
B. WR out of band after the iteration budget: UW != 49.2 +/- 3pp, or Jeskai
   outside 47.2 +/- 7pp. Do NOT widen the band to pass.
C. No-regression broken: NR-1 or NR-2 not bit-identical, OR Amulet T-turn drift
   > 0.05, OR any gauntlet matchup move whose SIGN contradicts the written
   prediction by > 0.5pp.
D. Coverage regression: full_audit < 4218/4218.
E. LIFO stack cannot reach depth 2 (TEST 2 unreproducible) -> counter-war
   capability not built; abort the rung.
F. Line not reproducible in budget: write an IMPERFECTIONS entry, item stays
   unmodelable, revert.
G. Determinism leak: global random state mutated by the R1 path
   (test_determinism preserve/pollution tests fail) -> abort; RNG purity is
   non-negotiable.

---

## 6. GO / NO-GO recommendation

**NO-GO for autonomous implementation now. HOLD for user review.**

Rationale: the user explicitly framed this as a design "for my review BEFORE any
engine code." A GO-autonomous call would contradict the request. Independent of
that framing, the technical profile - multi-week long pole, surgery on
shared-path files (`game_state.cast_spell`), and a sharp bit-identical gate that
is easy to violate silently - is exactly the class of work one does NOT start
autonomously before the design is approved.

Middle option (if the user wants forward motion without committing to merge): a
bounded, fully reversible SPIKE - `EnterWorktree modelability/r1-stack-priority`,
freeze baselines, implement just enough to prove `test_r1_stack_priority.py`
goes RED pre-R1 / GREEN post-R1 on TEST 1 and TEST 2, run NR-1 bit-identical,
and STOP before merge. This validates the core architectural bet (parallel gate
+ real LIFO + held-mana spend) cheaply and is discardable via `ExitWorktree`.

Recommended: HOLD. On approval, proceed with the spike first, then the full gate.

---

## Appendix - file-change list (absolute paths)

- ADD   E:/vscode ai project/mtg-sim/engine/priority_stack.py
- MOD   E:/vscode ai project/mtg-sim/engine/stack.py (StackItem.uid; Stack.counter(uid); depth probe)
- MOD   E:/vscode ai project/mtg-sim/engine/game_state.py (cast_spell parallel branch + _skip_legacy_window guard; _priority_stack_enabled helper)
- MOD   E:/vscode ai project/mtg-sim/engine/match_engine.py (additive _self_apl wiring near 228-229)
- MOD   E:/vscode ai project/mtg-sim/apl/match_apl.py (base WANTS_PRIORITY_STACK=False + default priority_action)
- MOD   E:/vscode ai project/mtg-sim/apl/aware_match_apl.py (WANTS_PRIORITY_STACK=True + priority_action lifting counter_resolver heuristics)
- KEEP  E:/vscode ai project/mtg-sim/engine/counter_resolver.py (UNCHANGED - legacy default path)
- ADD   E:/vscode ai project/mtg-sim/tests/test_r1_stack_priority.py
- ADD   E:/vscode ai project/mtg-sim/modelability_proofs/r1-stack-priority-2026-06-26.json (proof artifact)
