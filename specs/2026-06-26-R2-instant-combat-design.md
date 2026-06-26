---
title: R2 Instant-Speed Combat Windows - PROOF + NO-REGRESSION design (READ-ONLY, for review)
status: PROPOSED
created: 2026-06-26
project: mtg-sim
estimated_time: design only (no engine code written); implementation is M (~6-8h) once approved
related:
  - harness/specs/2026-06-26-modelability-ladder.md  (R2 rung -> Murktide tempo)
  - harness/specs/2026-06-26-R1-stack-priority-design.md  (the pattern this mirrors)
  - mtg-sim-r1/modelability_proofs/r1-stack-priority-2026-06-26.json  (red-pre/green-post + bit-identical discipline)
  - harness/IMPERFECTIONS.md  (sim-no-instant-speed-combat L297-308; sim-no-stack-priority)
  - mtg-sim-r1/engine/priority_stack.py  (R1 priority-pass loop -- REUSED, not re-mirrored)
worktree: E:/vscode ai project/mtg-sim-r1  (branch: modelability/r2-instant-combat, off the R1 branch)
depends_on: 2026-06-26-R1-stack-priority-design.md
supersedes:
superseded_by:
related_findings:
related_commits:
---

# R2 Instant-Speed Combat Windows - Implementation Design

READ-ONLY design. No engine code is written by this synthesis. This doc is the reviewable plan
(mirroring the R1 design) that must be approved before any R2 implementation. R2 REUSES R1's
priority-pass machinery and is gated behind a capability so non-tempo decks stay bit-identical,
built in the existing worktree branch, proven by replication + no-regression, merge held for the
user.

---

## 0. The one synthesis call that drives everything (a spec correction, surfaced by reading code)

The R2 rung in the ladder says: "step `match_runner._resolve_combat` (L613) into declare-attackers
-> priority window -> declare-blockers -> priority window -> damage." Reading the live code shows
that is the WRONG runner for the Murktide proof. The actual gauntlet routing
(`run_matchup.py:_run_fair`, verified) is:

- Path A (PRIMARY): if our deck has a sideboard plan (`get_sb_plan` non-empty -- every tempo deck
  with a `MATCHUP_SB_PLANS` does), the fair matchup runs through
  `engine/bo3_match.py:run_bo3_set` -> `engine/match_engine.py:run_match` and records
  `g1_source="bo3"`. THIS is the path Murktide's fair matchups execute.
- Path B (FALLBACK): no SB plan -> try DB cache (`get_real_matchup`, `g1_source="db"`, NO engine
  run at all) -> else `engine/match_runner.py:run_match_set` (the monolithic `_resolve_combat`,
  `g1_source="sim"`).

LINE-NUMBER CONVENTION: all `match_engine.py` citations below are R1-WORKTREE lines (where R2
builds), prefixed "R1 L...". R1's stack-priority wiring shifted these seams ~6 lines below base
`mtg-sim` (e.g. `pre_combat_instant` is base L287 -> R1 L293). `match_runner.py`, `match_state.py`,
and `stack.py` line numbers are identical in both trees (verified), so they carry no prefix.

Two combat code paths therefore exist, and they differ:

- `engine/match_engine.py:run_match` (the bo3 path Murktide runs) ALREADY has shallow combat hooks
  wired: `pre_combat_instant` (R1 L293-295), `declare_attackers` (R1 L310), `post_attackers_instant`
  (R1 L347-352), `declare_blockers` (R1 L355-356), and an attacker `combat_trick` hook (R1 L359-360) that
  fires ONLY `if hasattr(apl, 'combat_trick')`. `AwareMatchAPL` does NOT define `combat_trick`, so
  the attacker's instant-speed pump-after-blocks window is dead today. The defender hooks are
  one-shot calls into `resolve_interaction` (`_try_reactive_interaction` L79-145), NOT a priority
  pass: no back-and-forth, no stack, no ability to respond to the response.
- `engine/match_runner.py:_resolve_combat` (L613, the sim-fallback path) has NO windows at all --
  attackers auto-selected (all non-summoning-sick non-Defender, L636-656), blocker assignment
  biggest-on-biggest (L823-838), damage in one synchronous pass (`_resolve_strike_step`
  L852-942). This is the `sim-no-instant-speed-combat` IMPERFECTIONS entry verbatim (L300-301).

Consequence for the design:
1. The Murktide WR anchor + falsifier are LOAD-BEARING only on `match_engine.run_match`. Wiring the
   real window into `match_runner` alone would move nothing in the Murktide gauntlet.
2. Both paths must be touched so the gate behaves identically regardless of which one a matchup
   takes, but the PROOF runs against `match_engine.run_match` (deepening its shallow hooks into a
   real R1-reusing priority pass) -- that is where Murktide actually plays.
3. R1 already established that `cast_spell`-level counters fire on whatever runner is active (the
   gate lives in `game_state.cast_spell:1369`, not in a runner). R2 adds the combat-PHASE windows
   that R1 explicitly deferred ("Removal / burn / bounce / pump as on-stack responses are deferred
   to R2", priority_stack.py L26-31).

The architectural bet: ONE capability flag (`WANTS_INSTANT_COMBAT`, default False, opted-in on a
single tempo APL), guarding a real priority-pass combat window that REUSES R1's pass loop. Gate
OFF -> every existing combat code path (both runners, including match_engine's current shallow
hooks) executes byte-for-byte as today. Gate ON (Murktide only) -> the stepped window engages.

---

## 1. Exact engine changes (all ADDITIVE; gate-OFF path frozen)

### 1.1 REUSE R1's priority pass (extract the core; do NOT re-mirror it)

`run_priority_stack(caster_gs, card)` in `engine/priority_stack.py` is hardcoded to the cast path
(one original spell + counter-only responses). R2 needs the SAME pass loop with the response set
generalized to pump/removal/burn. Honest reuse = EXTRACT the engine of that loop into a shared
helper both windows call; do NOT copy-paste a parallel `combat_priority.py` (a reviewer would
correctly call that a mirror).

Extract from `priority_stack.py` (same module, no new file):

```python
# priority_stack.py -- factor the APNAP pass loop out of run_priority_stack
def run_priority_pass(sides, stack, *, first="opp", depth_cap=DEPTH_CAP,
                      ask=_ask_priority, resolve_top=_resolve_top):
    """Bounded APNAP pass/pass -> LIFO resolve loop. The loop body is exactly
    today's run_priority_stack while-loop (L149-195), parameterized on:
      - sides: {'caster': (gs, apl), 'opp': (gs, apl)}
      - stack: an engine.stack.Stack already seeded with the base object(s)
      - ask:   callable(apl, my_gs, their_gs, stack) -> action | None
      - resolve_top: callable(stack, sides, base, owner_gs) -> terminal | None
    Returns the terminal string from resolve_top. ZERO random() (unchanged)."""
```

TERMINATION must be generalized (load-bearing -- do not gloss). R1's loop condition is
`while not stack.is_empty()` (priority_stack.py:149) and it ends because `_resolve_top` returns a
TERMINAL once the original spell leaves the stack. A combat window seeds an EMPTY stack and has no
original spell, so that exact condition is False on entry -> the body never runs -> NO player is
ever offered priority -> the window is a silent no-op. The shared `run_priority_pass` therefore
generalizes the exit to: open by OFFERING priority (ask) even on an empty stack, and on
both-players-pass-in-succession do `if stack.is_empty(): break; else: resolve top`. On R1's path the
empty-break is UNREACHABLE (R1 returns a terminal before the stack ever drains to empty), so R1 is a
strict subset and stays byte-identical. Concretely: drive the pass loop on a "rounds since last
action" counter rather than on `not stack.is_empty()`, so an empty-stack window still solicits and
resolves responses. Proving "the generalized core keeps R1 TEST1/2/3 byte-identical" is the #1 spike
checkpoint (section 3 / NR-5), not an afterthought.

`run_priority_stack` becomes a thin caller of `run_priority_pass` with the counter-specific
`ask`/`resolve_top` it has today -> R1 behavior is byte-identical (its tests must still pass, NR-5).
R2's combat window is a SECOND caller with combat-specific `ask`/`resolve_top` that route responses
through `engine/stack.py:resolve_interaction` (the path R1 deferred). The shared `_other`,
`passed_in_succession`, `DEPTH_CAP`, and zero-RNG guarantees are reused verbatim.

### 1.2 `engine/stack.py` -- resolve_interaction (USE, do not rewrite)

`resolve_interaction` / `InteractionType` / `Resolution` / `StackItem` already exist and already
apply REMOVAL / BURN effects (used today by `match_engine._try_reactive_interaction` L132-139).
R2's combat `resolve_top` enqueues each instant as a `StackItem` with its `interaction_type` and
resolves it via `resolve_interaction(resolution, responder_gs, active_gs)`. A pump instant uses the
EXISTING, R1-unused `InteractionType.PUMP` branch (stack.py L355-359), which adds to the target
creature's `counters`, so `_safe_power`/`_safe_toughness` and `resolve_combat` read it -- consistent
with how match_engine prowess pump mutates `c.counters` at R1 L323. NO stack.py change is required:
the PUMP enum member (stack.py L29), its resolve_interaction branch (L355-359), AND the pump-card
mappings (L211-214: mutagenic growth / giant growth / might of old krosa / violent urge) ALL already
exist and were deliberately left unused by R1 -- R2 simply routes combat responses through them.
CAVEAT (R3, section 5.2): that branch hardcodes an APPROXIMATE +2/+2 (`targets[0].counters += 2`,
L359); card-accurate +X/+X magnitude is out of R2 scope, so every R2 proof must assume +2/+2.

### 1.3 Stepped combat (the windows), gated -- PRIMARY in match_engine, mirrored in match_runner

PRIMARY (`engine/match_engine.py:run_match`, the bo3 path Murktide runs):
- Extract the inline combat block (R1 L290-386: the "BEGIN COMBAT" comment through the prowess strip) into a function
  `_run_combat_phase(active, gs, opp_gs, mgs, apl, opp_apl)` -- a PURE refactor, byte-identical
  behavior, so it is unit-testable in isolation. (This extraction is itself covered by NR-1: with
  the gate OFF, `_run_combat_phase` must reproduce today's results exactly.)
- Inside `_run_combat_phase`, guard the NEW windows on `_instant_combat_enabled(gs, opp_gs)`:
  - WINDOW 1 (post-declare-attackers, PRE-declare-blockers): after `attackers = apl.declare_attackers(...)`
    (R1 L310) and the prowess/Slickshot pump (R1 L311-344), open a priority pass (APNAP: active player
    first). This is where attacker-side proactive removal of the sole blocker lives and where the
    defender may remove an attacker before committing blocks.
  - WINDOW 2 (post-declare-blockers, PRE-combat-damage): after `declare_blockers` (R1 L355-356) and
    BEFORE `resolve_combat` (R1 L363). This is the canonical combat-trick window: active player gets
    priority first (pump a blocked attacker), defender may respond, LIFO resolve, THEN damage.
  - When the gate is ON, the new windows SUPERSEDE the existing shallow one-shot hooks via a guard
    token (mirrors R1's `_skip_legacy_window`): the `if hasattr(opp_apl,'pre_combat_instant')`
    /`post_attackers_instant`/`combat_trick` one-shot calls are skipped so they cannot double-fire.
    When the gate is OFF, those shallow hooks run EXACTLY as today (frozen baseline).
- Window outputs feed the EXISTING math unchanged: pump mutates `counters` before `resolve_combat`
  reads power/toughness; removal moves the creature to graveyard so it is no longer in
  `gs.zones.battlefield`/`opp_gs.zones.battlefield` when blocks/damage compute.

SECONDARY (`engine/match_runner.py:_resolve_combat` L613, the sim-fallback path): step the same
two windows in, reusing the SAME helper, gated by the SAME `_instant_combat_enabled`. Insertion
points: WINDOW 1 after the attacker filter (L636-656) and before blocker assignment (L823);
WINDOW 2 after `assignments` is locked (L838) and before `_resolve_strike_step` runs (L935). Pump
mutates power/counters; removal removes the creature from `gs.bf_*` AND from `assignments` (so a
removed blocker frees its attacker). Gate OFF -> this block is unreached -> `_resolve_combat` is
byte-identical (the R1 bit-identical proof for non-control decks already relied on `match_runner`
being untouched on the gate-OFF path).

### 1.4 The gate (mirror R1 exactly)

```python
# shared helper used by both runners
def _instant_combat_enabled(gs, opp_gs) -> bool:
    self_apl = getattr(gs, '_self_apl', None) or getattr(gs, '_match_self_apl', None)
    opp_apl  = getattr(gs, '_match_opp_apl', None) or getattr(opp_gs, '_self_apl', None)
    return bool(getattr(self_apl, 'WANTS_INSTANT_COMBAT', False)
                or getattr(opp_apl, 'WANTS_INSTANT_COMBAT', False))
```

Fires when EITHER seat opts in (same scope-precision note as R1: a non-tempo deck FACING Murktide
correctly routes through the window -- feature, not regression -- but its usual fields never seat
Murktide, so normal gauntlets are unperturbed).

### 1.5 APL layer

- `apl/match_apl.py` base: `WANTS_INSTANT_COMBAT = False` + a default no-op
  `combat_priority_action(self, my_gs, their_gs, stack, window) -> (card, target) | None`
  (returns None -> pass). Mirrors R1's base `WANTS_PRIORITY_STACK=False` + default
  `priority_action`. All 38 Standard / Modern decks inherit False and are untouched.
- `apl/murktide_match.py:MurktideMatchAPL`: set `WANTS_INSTANT_COMBAT = True` and implement
  `combat_priority_action`: in WINDOW 2, if a blocked attacker would die to its blocker (or could
  kill it) and a pump in hand + untapped mana makes that true, cast it; in WINDOW 1, if a single
  declared-able blocker gates lethal, remove it. Reuse the existing `reserve_mana` /
  `_tap_for_response` accounting (R1 Seam D) so "held UU for permission" vs "spend on a trick"
  stays mutually exclusive. This is the ONE class that flips the gate on (narrowed scope, exactly
  like R1's UWControlModernMatchAPL). Registry already maps `murktide`/`dimirmurktide` ->
  `MurktideMatchAPL`.

### 1.6 Mutagenic Growth fold-in (ladder L107 + IMPERFECTIONS L308 requirement)

Fold the existing Mutagenic Growth / burst-turn carve-out into the general WINDOW-2 path so it
stops being a special case. With the gate ON it becomes one more `combat_priority_action` pump;
with the gate OFF the original carve-out code stays as-is (frozen). The fold-in is APL-side (grep
`Mutagenic` at implementation time -- it lives in a burst helper, not the runner), so it does not
alter the gate-OFF baseline.

### 1.7 Instrumentation (test-only, zero-RNG, mirror R1 COUNTERS_CAST)

Module-global `TRICKS_CAST` (+ `reset_fire_count()`) incremented only when a combat instant is
placed on the stack inside the WINDOW pass. The legacy gate-OFF path never reaches it, so any
nonzero value is direct evidence R2 fired in real play. Pure integer bookkeeping -> determinism
preserved.

---

## 2. The two windows: APNAP + rules-correctness (locked, do not drift)

- WINDOW 1 = after attackers declared, before blockers. WINDOW 2 = after blockers declared, before
  combat damage. Both use APNAP: the ACTIVE (attacking) player receives priority first, then the
  defender; the pass loop resolves LIFO when both pass in succession (reused R1 loop). Depth cap 3.
- RULES-CORRECT removal line lives in WINDOW 1, killing the SOLE declared-able blocker so the
  attacker is never blocked and damage connects. Killing a blocker AFTER blocks are declared
  (window 2) does NOT make damage go through without trample (CR 509.1h / 510.1c: once a creature
  is "blocked" it assigns no combat damage if its blocker leaves and it lacks trample). The design
  deliberately puts "make damage go through" in window 1.
- RULES-CORRECT pump line lives in WINDOW 2: the attacker is already blocked; a +X/+X instant
  changes the strike-step math. Pump mutates the creature's `counters` (match_engine) / power
  (match_runner) AFTER blocker assignment is locked and BEFORE the strike step reads it. The pump
  is read by `_safe_power`/`_safe_toughness` / `resolve_combat`, so combat math reflects it with no
  change to the damage routines.
- A window action fires only when the responder can pay from ACTUAL untapped mana (reuse R1
  `_pay_for_counter` / `reserve_mana`); a misjudged-affordability action is treated as a pass (R1
  behavior reused).

---

## 3. Build plan -- isolated worktree (mirror R1)

- `EnterWorktree` branch `modelability/r2-instant-combat`, branched off the R1 branch (R2 depends
  on R1's priority-pass core; build on the proven dependency, never re-implement it).
- Freeze branch-point baselines BEFORE any edit: capture Boros Energy mirror + Amulet goldfish +
  the Murktide gauntlet (gate-absent) + R1 control tests, all at seed=42, as the FROZEN reference
  to diff against (compare post-R2 against the frozen capture, not historical numbers).
- Internal order: 1.1 extract+reuse (re-green R1 tests) -> 1.3 match_engine stepped+gated -> proof
  tests RED-pre/GREEN-post -> 1.5 APL opt-in -> WR anchor+falsifier -> 1.3 match_runner mirror ->
  full no-regression. STOP before merge.

---

## 4. Proof + no-regression harness (acceptance gate)

R2 is PROVEN iff ALL of 4.1 AND 4.2 AND 4.3 hold.

### 4.1 PROOF-BY-REPLICATION (differential -- must be RED pre-R2, GREEN post-R2)

New file `tests/test_r2_instant_combat.py` (standalone, `sys.path.insert`, plain asserts,
ASCII-only, prints "ALL R2 PROOF TESTS PASS", exit 0/1; same conventions as the R1 test). Build the
match structures `_run_combat_phase` consumes (GameState `gs`/`opp_gs`, `MatchGameState mgs`) and
HAND-PLACE cards -- do NOT run a full match (mulligans make it fragile). Wire `_self_apl` /
`_match_opp_apl`, seed=42. The tempo APL used in-test sets `WANTS_INSTANT_COMBAT=True` (it IS a
tempo APL opting into R2, mirroring production MurktideMatchAPL); a per-instance `=False` toggle
captures the RED pre-state on the SAME structures (the R1-proven gate-toggle technique).

- TEST 1 -- COMBAT-TRICK PUMP LINE (the headline known line). Attacker controls a 2/2; defender a
  3/3. Attacker swings the 2/2; defender blocks with the 3/3; attacker holds Mutagenic Growth -- a
  REAL +2/+2 instant (free via Phyrexian pitch) that matches the engine's PUMP primitive exactly
  (stack.py:359 hardcodes +2/+2, see 1.2 CAVEAT). Assert post-window-2:
  (a) attacker creature ALIVE (not in graveyard) and now 4/4 (base 2/2 + the +2/+2 counters);
  (b) blocker 3/3 DEAD (in defender graveyard);
  (c) TRICKS_CAST > 0; (d) the pump actually paid its cost (Mutagenic Growth moved hand -> graveyard;
  if a mana-cost pump such as Giant Growth is substituted, assert the reserved land was tapped) --
  proves the response consumed a cost, not a free apply.
  RED pre (gate OFF -> no window-2 -> synchronous combat): the 2/2 takes 3 >= 2 -> DEAD; the 3/3
  takes 2 < 3 -> ALIVE. GREEN post: 4/4 takes 3 < 4 -> ALIVE; 3/3 takes 4 >= 3 -> DEAD. Both (a)
  and (b) FLIP. This is the discriminator.
- TEST 2 -- REMOVAL-MAKES-DAMAGE-GO-THROUGH LINE. Defender controls exactly one creature (a 2/2
  would-be blocker) and is at 20. Attacker swings a 3/3; in WINDOW 1 the attacker casts removal/
  burn on the 2/2. Assert: (a) 2/2 in defender graveyard BEFORE blocks; (b) attacker UNBLOCKED;
  (c) defender life == 17 (3 to face). RED pre (no window-1): defender blocks the 3/3 with the 2/2
  -> 0 to face (life 20), 2/2 dies in combat (not pre-combat), 3/3 survives. Life total (c) FLIPS
  20 -> 17.
- TEST 3 -- BILATERAL WINDOW (defender instant-speed removal kills the attacker pre-damage; proves
  the window is APNAP, not attacker-only, and that combat math zeroes the removed attacker's
  damage). Attacker swings a lone 4/4 into an empty board, defender at 20 holds removal. WINDOW 1:
  defender removes the 4/4. Assert defender life == 20 and the 4/4 in attacker graveyard. RED pre:
  unblocked 4/4 -> defender life 16.

GATE ON THE TEST ITSELF (Rule 5): TEST 1(a)/(b), TEST 2(c), TEST 3-life MUST FAIL on the
branch-point commit (gate forced OFF). If any passes pre-R2 the test is not discriminating -> fix
the test before any R2 claim. Record paired pre/post results in
`modelability_proofs/r2-instant-combat-2026-06-26.json`.

### 4.2 WR ANCHOR + FALSIFIER (Murktide tempo)

Anchor (re-pulled at build time from `mtg_meta.db.matchup_matrix`, modern; prefer fresher
`untapped_meta_archetypes` if newer -- NO `[needs source]` may remain at run time, Rule 5 / no
fabrication). Match whichever list the loaded deck mirrors:
- If the registered Murktide list is Dimir Frog / Dimir tempo (current `murktide` ->
  `dimir_oculus_modern.txt`): anchor = Dimir Frog 52.6% +/- 3pp (low-n n=643 -> wider band).
- If it mirrors Izzet Murktide / UR Prowess: anchor = Izzet Prowess 50.3% +/- 2pp (n=4165 ->
  normal band).
Gauntlet n >= 1000 (the formal Tier-1 gate; the R1 n=600 caveat is not repeated):
`python parallel_launcher.py --deck "<Murktide>" --format modern --n 1000 --seed 42`.

FALSIFIER (mandatory, ladder L116): turning combat windows OFF must MEASURABLY drop this deck's
MWR. Run the gauntlet twice -- `WANTS_INSTANT_COMBAT` ON vs OFF -- and assert
`MWR_on - MWR_off >= +2pp`, measured on the GENUINELY-SIMULATED subset only.
HONESTY SCOPING (generalizes R1's combo-sampler caveat using the runner trace in section 0): the
FWR mixes (i) `g1_source in {bo3, sim}` matchups that actually execute combat and CAN move, with
(ii) `g1_source=db` cached matchups and (iii) `ComboKillSampler` matchups that do NOT run the
engine and CANNOT move. Compute the falsifier delta over subset (i) and report the per-matchup
table with `g1_source` tags (exactly as the R1 artifact tabulated fair-vs-combo). If subset (i)
shows no delta, the combat model is not load-bearing on this deck -> the proof FAILS (do not paper
over it with the unmovable db/combo matchups inflating the headline).

### 4.3 NO-REGRESSION (sharp form: bit-identical; mirror R1)

- NR-1 (PRIMARY, non-tempo bit-identical via the BO3 path): Boros Energy mirror through the SAME
  bo3/match_engine path Murktide uses (`run_bo3_set` / `run_match`, n=1000, seed=42,
  mix_play_draw=True). Boros has `WANTS_INSTANT_COMBAT=False`; a_wins / b_wins / avg_turns must be
  IDENTICAL pre/post R2. Boros casts no combat tricks; any delta = leak into the gate-OFF path or
  RNG-stream perturbation (the `_run_combat_phase` extraction must be a true no-op refactor when the
  gate is off). Doubles as a determinism guard.
- NR-2 (non-tempo bit-identical via the SIM path): an Izzet-Prowess-vs-Dimir style non-tempo MATCH
  run via `run_match_set` DIRECTLY (avoids the meta-DB short-circuit that took different code paths
  per tree in R1 -- a DATA divergence, not engine; reuse R1's direct-call methodology). Both gates
  OFF -> `match_runner._resolve_combat` byte-identical. Pick a non-degenerate (not 0/100) matchup so
  the number is a real discriminator.
- NR-3: Amulet Titan goldfish bit-identical at seed=42; T-turn within +/- 0.05 of locked baselines
  (20-life 95.7% avg T7.11 / median T7; 17-life 95.9% avg T6.81 / median T6). (Amulet is the
  non-tempo combo control the task names.)
- NR-4: `python scripts/full_audit.py --formats standard` -> 4218/4218, all 17 sets at 0 remaining
  (R2 is control-flow, not handlers).
- NR-5 (R1 control tests STILL PASS -- R2 reuses R1's core): `python tests/test_r1_stack_priority.py`
  and `python tests/test_r1_control_exercises.py` both green AFTER the 1.1 extraction. The
  extraction must leave R1 byte-identical; the R1 artifact's TEST1/TEST2/TEST3 and the
  COUNTERS_CAST>0 real-play fire must reproduce.
- NR-6: `tests/test_match_engine.py`, `tests/test_determinism.py`, `tests/test_modern_apls.py`,
  `tests/test_standard_apls.py` all green (bands as in R1 NR-4).

Compare post-R2 against the FROZEN branch-point capture (section 3), not hardcoded historical
numbers.

---

## 5. Honest effort / risk + ABORT conditions

### 5.1 Effort and risk (highest first)
1. RNG-stream / call-order leakage breaking NR-1/NR-2 bit-identical -- the `_run_combat_phase`
   extraction is the dangerous edit (it touches the live bo3 path EVERY deck uses). Mitigated by
   "extract first, prove bit-identical with the gate unreachable, THEN add gated windows."
2. The 1.1 extraction silently changing R1 behavior (NR-5). Re-green R1 tests immediately after
   extraction, before touching combat.
3. Combat-trick zone/stat desync: pump mutating `counters` vs `power` inconsistently between the
   two runners, or removed creatures left dangling in `assignments` / `attackers` lists.
4. Falsifier delta hiding in unmovable db/combo matchups (the section-0 trap) -> scope to the
   simulated subset.

### 5.2 Intentionally DEFERRED beyond R2
- Full CR combat priority (first-strike-step priority window, combat-damage-step triggers, multiple
  combat phases). R2 = two windows (post-attackers, post-blockers) only.
- Fight / first-strike-order tricks, regeneration, protection re-evaluation mid-combat.
- Unifying match_engine and match_runner into one combat path (kept separate; both gated).
- Promoting any non-tempo deck to "modeled" off R2 (R2 unlocks the tempo cluster only).
- Stack depth beyond 3; split / multi-target combat stacks.
- Card-accurate +X/+X pump magnitude. R2 reuses the existing PUMP branch's hardcoded approximate
  +2/+2 (stack.py:359); reading each card's real boost (Giant Growth +3/+3, etc.) is an R3 increment.

### 5.3 ABORT conditions (discard the worktree, leave the item unmodelable; mirror R1 + ladder P5)
A. Proof not falsifying: any TEST 1/2/3 discriminator passes pre-R2 (gate OFF) -> fix the test, no
   R2 claim until red-pre / green-post.
B. WR out of band after the iteration budget: Murktide MWR outside the matched anchor's band at
   n>=1000. Do NOT widen the band to pass.
C. FALSIFIER FAILS: `MWR_on - MWR_off < +2pp` on the genuinely-simulated subset -> the combat model
   is not load-bearing -> proof fails (the spec's own teeth, L116).
D. No-regression broken: NR-1 / NR-2 / NR-3 not bit-identical (or Amulet T-turn drift > 0.05), OR
   any gauntlet matchup move whose SIGN contradicts the written prediction by > 0.5pp.
E. R1 REGRESSION: NR-5 fails (the 1.1 extraction changed R1 behavior) -> STOP; R2 may not break the
   dependency it builds on.
F. Coverage regression: full_audit < 4218/4218.
G. Determinism leak: the combat-window path mutates global random state (test_determinism fails) ->
   abort; RNG purity is non-negotiable (the R2 window must be zero-random like R1).
H. Known line not reproducible in the iteration budget -> write an IMPERFECTIONS update on
   `sim-no-instant-speed-combat`, leave the item unmodelable, revert.
I. Any `[needs source]` anchor band that cannot be pulled from `mtg_meta.db` -> HITL pause (no
   fabricated targets).

---

## 6. GO / NO-GO recommendation

NO-GO for autonomous implementation now. HOLD for user review (same framing as R1: design before
engine code; and the `_run_combat_phase` extraction is a sharp bit-identical edit on the live bo3
path that one does not start autonomously before approval).

Middle option (forward motion without committing to merge): a bounded, reversible SPIKE --
`EnterWorktree modelability/r2-instant-combat`, freeze baselines, do ONLY the 1.1 extraction +
re-green R1 tests + the match_engine WINDOW-2 pump path, prove `test_r2_instant_combat.py` goes
RED-pre / GREEN-post on TEST 1, run NR-1 bit-identical + NR-5 R1-still-green, and STOP. That
validates the core bet (reuse R1 loop + gated window + counters-driven pump read by existing math)
cheaply and is discardable via `ExitWorktree`.

Recommended: HOLD. On approval, spike first, then the full gate.

---

## Appendix -- file-change list (absolute paths)

- MOD  E:/vscode ai project/mtg-sim-r1/engine/priority_stack.py        (extract run_priority_pass core; run_priority_stack becomes a thin caller -- R1 byte-identical)
- KEEP E:/vscode ai project/mtg-sim-r1/engine/stack.py                  (UNCHANGED -- PUMP enum (L29), resolve_interaction PUMP branch (L355-359, approx +2/+2), AND pump-card mappings (L211-214: mutagenic/giant growth/etc.) ALL already exist, unused by R1; R2 routes combat responses through them. R3 owns card-accurate magnitude)
- MOD  E:/vscode ai project/mtg-sim-r1/engine/match_engine.py          (extract _run_combat_phase from R1 L290-386; add gated WINDOW 1 + WINDOW 2 + skip-shallow-hooks guard token; _instant_combat_enabled helper)
- MOD  E:/vscode ai project/mtg-sim-r1/engine/match_runner.py          (step _resolve_combat L613 into the same two gated windows; gate-OFF byte-identical)
- MOD  E:/vscode ai project/mtg-sim-r1/apl/match_apl.py                (base WANTS_INSTANT_COMBAT=False + default no-op combat_priority_action)
- MOD  E:/vscode ai project/mtg-sim-r1/apl/murktide_match.py           (WANTS_INSTANT_COMBAT=True + combat_priority_action: window-2 pump, window-1 remove sole blocker; Mutagenic Growth fold-in)
- KEEP E:/vscode ai project/mtg-sim-r1/engine/counter_resolver.py      (UNCHANGED -- R1 legacy default path)
- ADD  E:/vscode ai project/mtg-sim-r1/tests/test_r2_instant_combat.py
- ADD  E:/vscode ai project/mtg-sim-r1/modelability_proofs/r2-instant-combat-2026-06-26.json  (proof artifact: rung, anchor_wr, tolerance, wr_on, wr_off, falsifier_delta, line_reproduced, seed, log_excerpt, commit_hash, baseline_shift, g1_source_table)

## Pattern reference (XMage, cited as PATTERN only -- not copied)

- magefree/mage `Mage/src/main/java/mage/game/turn/CombatPhase.java`: combat is a STEPPED phase --
  BeginCombatStep -> DeclareAttackersStep -> DeclareBlockersStep -> CombatDamageStep (x2 for first
  strike) -> EndOfCombatStep. R2's two windows mirror the step boundaries after DeclareAttackers
  and after DeclareBlockers.
- `Mage/src/main/java/mage/game/turn/DeclareBlockersStep.java`: `beginStep` runs
  `combat.selectBlockers` then `acceptBlockers`; the priority pass that follows each step is driven
  by the phase loop (`Phase.playStep` -> `Game.playPriority`). R2's analog: declare blockers, then
  run the reused R1 priority pass before combat damage -- precisely WINDOW 2.
