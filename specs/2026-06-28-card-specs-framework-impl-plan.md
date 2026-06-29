---
title: "card_specs framework -- implementation plan (state-grounded, 2026-06-28)"
status: "PROPOSED"
created: "2026-06-28"
updated: "2026-06-28"
project: "mtg-sim"
estimated_time: "Tier-1 gap-fill + tests: 90-120 min. Phase B migration: 240-360 min (NOT the 120-180 the source spec claims -- see gotchas)."
related_findings:
  - "harness/knowledge/tech/jeskai-blink-card-specs-2026-04-28.md"
  - "harness/knowledge/tech/mulligan-audit-2026-04-28.md"
scopes_spec: "harness/specs/2026-04-29-card-specs-framework.md"
related_commits: []
supersedes: null
superseded_by: null
---

# card_specs framework -- implementation plan (state-grounded)

This is an EXECUTION plan for the remaining work in
`harness/specs/2026-04-29-card-specs-framework.md`, written after reading the
ACTUAL current state of `mtg-sim/apl/card_specs/` and the APLs the source
spec wants migrated. It corrects two factual errors in the source spec's
prose: (1) the source spec's "pure refactor / byte-identical" claim for Phase
B is wrong -- the card_specs primitives and the inline APL code are NOT
behaviorally equivalent today (proof below); (2) most of Phase A and all of
Phase C are already shipped, so the real remaining work is narrower and
differently shaped than the source spec's Step list.

## READ-ONLY / concurrency constraint (mandatory pre-flight)

A separate workflow is CONCURRENTLY writing new files under
`E:/vscode ai project/mtg-sim/apl/`. During the authoring of THIS plan,
nothing under `mtg-sim/` may be edited. Before an executor acts on any step
below, it MUST re-run the "Current state audit" commands (Step 0) because the
concurrent writer may have already created `solitude.py`,
`galvanic_discharge.py`, `tests/test_card_specs.py`, or begun Phase B. Treat
every "create file X" step as "create X if and only if the audit shows it
still absent; otherwise diff against the concurrent writer's version and
reconcile."

## Current state (audited 2026-06-28, ground truth)

DONE (do not redo):
- Framework skeleton `apl/card_specs/__init__.py` -- exists, imports 35+
  modules (Tier 1 + Tier 2 + all Standard sets). Far beyond source spec scope.
- Tier 1 specs present: `phlage.py`, `ragavan.py`, `phelia.py`,
  `ephemerate.py`.
- Tier 2 specs present: `quantum_riddler.py`, `teferi_time_raveler.py`,
  `consign_to_memory.py`, `wrath_of_the_skies.py`.
- POC `apl/jeskai_blink.py` -- exists (189L), imports and composes
  `card_specs` (phlage/ragavan/phelia/ephemerate/quantum_riddler/teferi).
  This is the source spec's Step 4 deliverable; it shipped.
- IMPERFECTIONS already tracks the gaps: `card-specs-phase-b-migration-pending`
  (OPEN), `card-specs-phlage-engine-no-sacrifice-quirk` (OPEN). Source-spec
  `_index.md` line 38 says "Tier 1+2 landed."

NOT DONE (the real remaining work):
1. Tier 1 spec `solitude.py` -- MISSING. (Listed in source spec Step 1 / Step 2
   Tier-1 list; never created. Inline impl lives in `esper_blink_match.py`
   and `uw_blink_match.py`.)
2. Tier 1 spec `galvanic_discharge.py` -- MISSING. (Listed in the source
   spec's original `__init__.py` import line; never created. Inline impl
   lives in `boros_energy.py` as a name-keyed +3-energy cast.)
3. `tests/test_card_specs.py` -- MISSING. No file under `tests/` references
   `card_specs` at all (verified via grep). The source spec's Step 3 test
   harness was never written.
4. Phase B migration -- NOT DONE. None of `boros_energy.py`,
   `jeskai_blink_match.py`, `uw_blink_match.py`, `esper_blink_match.py`
   import `card_specs` (verified via grep: zero hits in all four). They all
   still carry inline Phlage/Ragavan/Galvanic/Phelia/Solitude/Ephemerate
   logic.

## Goal

Close the three additive gaps (solitude spec, galvanic spec, test suite) and
provide a CORRECT, behavior-preserving migration path for Phase B that the
source spec's "pure refactor" framing does not support.

## Files to change (for the executor; ALL under mtg-sim, which is read-only
for the PLAN author -- the executor runs later, after the concurrent writer
settles)

- CREATE `mtg-sim/apl/card_specs/solitude.py`
- CREATE `mtg-sim/apl/card_specs/galvanic_discharge.py`
- EDIT  `mtg-sim/apl/card_specs/__init__.py` (add the two imports + __all__)
- CREATE `mtg-sim/tests/test_card_specs.py`
- EDIT (Phase B, deferred) `mtg-sim/apl/card_specs/phlage.py` -- parameterize
  before any migration (see gotcha #1).
- EDIT (Phase B, deferred) `mtg-sim/apl/boros_energy.py`,
  `apl/jeskai_blink_match.py`, `apl/uw_blink_match.py`,
  `apl/esper_blink_match.py`.
- No engine files. No driver files.

## Step 0 -- Current state audit (run first, every time)

```bash
cd "E:/vscode ai project/mtg-sim"
export PYTHONIOENCODING=utf-8
ls apl/card_specs/solitude.py apl/card_specs/galvanic_discharge.py 2>/dev/null
ls tests/test_card_specs.py 2>/dev/null
grep -ln card_specs apl/boros_energy.py apl/jeskai_blink_match.py \
    apl/uw_blink_match.py apl/esper_blink_match.py
```
If the concurrent workflow already produced any of these, STOP and reconcile
against its version rather than overwriting.

## Step 1 -- Tier 1 gap-fill: solitude.py (~30 min, ADDITIVE, low risk)

Source of truth for behavior: `esper_blink_match.py` (SOLITUDE constant +
"Solitude pitch on big threats" block ~line 96) and `uw_blink_match.py`.
Solitude = `{3}{W}` 3/2 flash flier; Evoke by exiling a white card from hand
-> ETB exiles target creature an opponent controls until Solitude leaves.

Module shape (mirror the existing Tier 1 modules' contract exactly --
`from __future__ import annotations`, module docstring with Oracle + "Decks
using this spec" + reference-impl file:line + `Spec:` line, a `NAME`
constant, action functions returning `bool`):

```python
NAME = "Solitude"
HARDCAST_CMC = 4   # {3}{W}
def cast(gs, opponent=None) -> bool: ...        # hardcast 3/2 flash flier
def evoke(gs, opponent=None) -> bool: ...        # pitch a white card; ETB-exile
def best_exile_target(gs, opponent) -> object | None: ...
```

CRITICAL goldfish-awareness rule (this is why the source spec excluded
Solitude from the goldfish POC import): evoke and the exile ETB are DEAD with
`opponent=None`. `evoke()` and `cast()`'s removal value MUST early-return
`False` when `opponent is None` (there is nothing to exile). Match the
existing `ragavan.dash` pattern (line 43: `if opponent is None: return
False`). Do NOT make Solitude do anything in goldfish.

## Step 2 -- Tier 1 gap-fill: galvanic_discharge.py (~30 min, ADDITIVE)

Source of truth: `boros_energy.py` -- GALVANIC constant (line 47) + the
"6. Galvanic Discharge" block (~line 366) where it casts ALL copies for +3
energy each (`gs._log("  Galvanic: +3 energy ..., 0 dmg to own creature")`).
Galvanic = `{R}` instant: get {E}{E}{E}, then pay any {E} to deal that much
damage to any target. In the boros line it is cast purely for the +3 net
energy (0 damage). The card_spec must expose BOTH modes:

```python
NAME = "Galvanic Discharge"
def cast_for_energy(gs, opponent=None) -> bool:   # +3 net energy, 0 dmg
def cast_for_damage(gs, opponent=None, amount=None) -> bool:  # opp-only; dead in goldfish
```

Goldfish-aware: `cast_for_damage` early-returns `False` on `opponent is None`.
`cast_for_energy` is goldfish-safe (energy accrues regardless). Reproduce
boros's exact energy bookkeeping field name (`gs.energy`) so a later Phase B
swap is mechanical.

## Step 3 -- Wire the two new modules into __init__.py (~5 min)

Add to `apl/card_specs/__init__.py`: an import line and two `__all__`
entries, in the "Tier 1 -- Modern core" group. Keep the existing comment-
grouped block layout. Watch for a name collision: the concurrent writer may
have added these already (Step 0 catches it).

## Step 4 -- Test suite tests/test_card_specs.py (~30 min, ADDITIVE)

Stand-alone script per CONVENTIONS.md (NOT pytest-required): sets
`sys.path` to repo root via `dirname(dirname(abspath(__file__)))`, ASCII-only
output, exit code 0/1, runnable as `python tests/test_card_specs.py` with
`PYTHONIOENCODING=utf-8`.

Needs a `_stub_game_state()` builder. The card_specs functions touch this
real surface (verified against engine):
- `gs.zones.hand` / `.graveyard` / `.battlefield` / `.exile` -- list-like with
  `.remove`/`.append`; `gs.zones.draw(n)`; `gs.zones.creatures_on_battlefield()`.
- `gs.mana_pool.can_cast(mana_cost, cmc)` (engine/mana.py:148),
  `.pay(mana_cost, cmc)` (mana.py:154), `.total()` (mana.py:58),
  `.can_pay(cost, cmc)` (used by boros).
- `gs.cast_spell(card)` (game_state.py:1438), `gs.damage_dealt`, `gs.life`,
  `gs.turn`, `gs._log(str)`.
- `data.card.Card` / `data.card.Tag` (ephemerate/phelia import Tag; cards use
  `c.has(Tag.CREATURE)`, `c.is_land()`, `c.name`, `c.cmc`, `c.mana_cost`).

Prefer building a tiny in-test fake that satisfies exactly this surface over
spinning a real GameState (faster, no deck-load). Cover, at minimum, the
source spec's named cases plus the new modules:
- phlage: hardcast pays mana + adds 3 dmg + 3 life; escape requires 5 non-
  Phlage GY cards AND 4 mana (test the boundary at 4 vs 5 GY cards -- matches
  source spec Step 3 example).
- ragavan: cast from hand True; dash returns False when `opponent is None`.
- phelia: `attack_blink_target` priority order Phlage > Quantum > Casey;
  returns None on empty board.
- ephemerate: `cast` no-ops (returns False) when no ETB creature on board;
  `_retrigger_etb` for Phlage moves it BF->GY and adds 3 dmg + 3 life.
- solitude / galvanic: evoke / cast_for_damage both return False on
  `opponent is None` (the goldfish-dead guard).

## Phase B migration (DEFERRED -- see recommendation). Steps 5-8.

### THE load-bearing gotcha: card_specs != inline behavior today

The source spec (line 251, 263, 289) calls Phase B a "pure refactor" that
must be "byte-identical." That is FALSE against the current code. The
card_specs primitives were tuned for the Jeskai goldfish and DIVERGE from the
boros inline logic that produced the locked 64.5%/78.8% canonical baseline.
Swapping them in as-is WILL move the baseline and trip the >0.5pp stop
trigger. Concrete divergences between `card_specs/phlage.py` and
`boros_energy.py:_handle_phlage` (read both):

1. HARDCAST disposition is OPPOSITE.
   - boros (`boros_energy.py:700-703`): after `cast_spell`, it MANUALLY
     SACRIFICES Phlage (removes from battlefield, appends to graveyard) --
     per oracle "sacrifice unless escaped."
   - card_specs (`phlage.py:27-39`, docstring): deliberately does NOT
     sacrifice; leaves Phlage on battlefield as a 6/6 because that helps the
     goldfish clock (it tested 1 turn faster, T6.43 vs T7.51).
   These are contradictory. A naive swap changes whether boros's hardcast
   Phlage is a 6/6 attacker or a GY card available for escape -- a large
   behavioral change. (This quirk is itself tracked as
   `card-specs-phlage-engine-no-sacrifice-quirk`.)

2. ESCAPE mana gate differs.
   - boros (`:713`): `gs.mana_pool.can_pay("{R}{R}{W}{W}", 4)` -- COLORED
     check.
   - card_specs (`phlage.py:51`): `gs.mana_pool.total() < ESCAPE_CMC` --
     GENERIC total check, color-blind. Different hands qualify to escape.

3. ESCAPE exile selection differs.
   - boros (`:715`): exiles `other_gy_cards[:5]` in graveyard ORDER.
   - card_specs (`phlage.py:56`): SORTS non-Phlage GY by cmc ascending, then
     exiles cheapest 5. Different cards leave the GY -> different future
     escapes / Bombardment fuel / board.

4. ESCAPE power/toughness.
   - boros (`:722-723`): sets `phlage.power = "6"`, `.toughness = "6"`.
   - card_specs: does NOT set P/T. Combat-damage output diverges.

5. APL-specific side effects card_specs omits.
   - boros sets `self._gained_life_this_turn = True` (drives Ocelot end-step
     Cat trigger) and calls `self._fire_guide_etb_trigger(gs, card)` on both
     hardcast and escape. card_specs does neither. Dropping these silently
     changes downstream boros triggers.

6. Architectural mismatch. boros orchestration is a name-keyed
   `SPECIAL_MECHANICS` dispatch (`:94` maps the Phlage name to
   `_handle_phlage`) with an energy/treasure/Bombardment economy; Phelia /
   Solitude / Galvanic are name-keyed there too. The card_specs contract is
   free functions. Migration is not a 1:1 line swap; it is a re-wiring of the
   dispatch table to call the free functions, preserving every side effect.

CONCLUSION: Phase B is only safe if the card_specs functions are first
PARAMETERIZED to reproduce each call site's exact behavior, e.g.
`phlage.hardcast(gs, sacrifice=False)`, `phlage.escape(gs,
exile_order="gy"|"cmc", set_pt=True, colored_gate=True,
on_etb=<callback for guide trigger + life flag>)`. Only then can a call site
be swapped and pass bit-stable. This is real design work, NOT a refactor.

### Step 5 -- Parameterize card_specs primitives (Phase B prerequisite, ~60-90 min)

Add behavior-selecting kwargs to `phlage.hardcast` / `phlage.escape` (and
similarly for galvanic / phelia / solitude) so the existing default behavior
(the goldfish-tuned one used by `jeskai_blink.py`) is UNCHANGED when called
with no kwargs, but each migrating APL can request its current exact
behavior. Verify the jeskai_blink goldfish gate still holds first (T6.43 +/-
0.05, n=2000 seed=42) to prove the defaults didn't move.

### Step 6 -- Migrate boros_energy.py (~60-90 min, HIGH RISK, bit-stable gate)

boros_energy.py is LOCKED at canonical 64.5%/78.8% (mtg-sim/CLAUDE.md;
IMPERFECTIONS `card-specs-phase-b-migration-pending`). Replace the bodies of
`_handle_phlage` / the Galvanic block / Ragavan block with calls to the
parameterized card_specs, passing the kwargs that reproduce boros's exact
behavior (sacrifice=True, exile_order="gy", set_pt=True, colored_gate=True,
plus the guide-trigger + `_gained_life_this_turn` side effects as callbacks
or as wrapper lines retained in boros). Validate bit-stable:

```bash
cd "E:/vscode ai project/mtg-sim"
export PYTHONIOENCODING=utf-8
python parallel_launcher.py --deck "Boros Energy" --format modern --n 1000 --seed 42  # PRE (capture json)
# (apply migration)
python parallel_launcher.py --deck "Boros Energy" --format modern --n 1000 --seed 42  # POST
diff <(jq -S . data/parallel_results_<pre>.json) <(jq -S . data/parallel_results_<post>.json)
```
Acceptance: bit-identical OR per-matchup max-dev <0.1pp. STOP trigger: any
matchup >0.5pp -- the parameterization is not faithful; diff inline-vs-spec.

### Step 7 -- Migrate jeskai_blink_match.py, uw_blink_match.py,
esper_blink_match.py (~90-120 min). Same parameterize-then-swap-then-bit-
stable pattern, one file at a time. Per spec-authoring-lesson v1.5
("parallel-entry-points-need-mirror-fix"): the goldfish and match variants of
a deck share card logic; when you migrate the match file, re-verify the
goldfish variant still passes its gate too. Solitude lives in
esper/uw_blink_match -- migrate it via the new `solitude.py` from Step 1.

### Step 8 -- Tier 2/3 already extracted; no Phase C work remains. Confirm via
Step 0 audit that quantum/teferi/consign/wrath specs still exist and are
imported, then close.

## Validation gates

| Gate | Acceptance | Stop trigger |
|---|---|---|
| Step 4 unit tests (incl. solitude/galvanic) | all pass, exit 0 | any fail |
| Step 5 jeskai_blink goldfish (defaults unmoved) | T6.43 +/- 0.05, n=2000 seed=42 | >T6.50 |
| Step 6 Boros Energy canonical | bit-identical or <0.1pp | >0.5pp matchup dev |
| Step 7 each match APL in field | <0.1pp aggregate dev | >0.5pp |

Run sims via `parallel_launcher.py` / `run_simulation`, NOT `sim.py` (source
spec Step 5 notes a `sim.py` bug at line 50).

## Gotchas (real-code, beyond gate #1 above)

- `mana_pool` exposes BOTH `can_cast(cost, cmc)` (card_specs uses it) and
  `can_pay(cost, cmc)` (boros escape uses it). They are not interchangeable in
  the color-gate sense; keep each call site's original method during migration.
- Phlage historically had a Scryfall `cmc=0` kludge; boros comment
  (`:678-681`) says card_db now reports `cmc=3.0` and standard `cast_spell`
  fires `_phlage_titan_etb`. Don't reintroduce the kludge.
- `uw_blink_match.py` is thin (124L): `main_phase` delegates to
  `main_phase_match(gs, None)` (`:45-47`). The `None` opponent means Solitude
  evoke is already dead there -- the new solitude spec's goldfish guard makes
  the swap safe, but verify the delegation still passes `None`.
- Adding to `card_specs/__init__.py` is itself a (small) edit to a file the
  concurrent writer may also be touching -- expect a merge/reconcile, not a
  clean create.
- ASCII-only in all `print`/`_log` calls (CONVENTIONS.md); em-dash/arrows only
  in comments/docstrings. Set `PYTHONIOENCODING=utf-8` for every python run.

## Byte-identical / no-regression concern (summary)

There is NO byte-identical path for Phase B via a naive swap: the card_specs
defaults encode goldfish-tuned choices (no-sacrifice hardcast, cmc-sorted
exile, color-blind escape gate, no P/T set, no guide/life side effects) that
contradict the inline logic baked into boros's locked 64.5%/78.8% numbers.
Byte-identical is achievable ONLY after Step 5 parameterization makes each
call site reproducible, validated by the per-file bit-stable gauntlet. The
additive work (Steps 1-4) carries no baseline risk because it adds new files /
tests and never changes an existing call site.

## Effort

- Additive (Steps 1-4: solitude + galvanic + __init__ wire + tests): 90-120 min,
  low risk.
- Phase B (Steps 5-7: parameterize + 4 migrations + bit-stable gauntlets):
  240-360 min, high risk. (The source spec's 120-180 min estimate assumed a
  pure refactor that the code does not support.)

## Recommendation: build-after-deps

- Steps 1-4 (additive Tier-1 gap-fill + test suite) are safe to build, BUT
  only after the concurrent apl/ writer settles and Step 0 confirms the files
  are still absent -- otherwise you clobber its work. Build these first; they
  unblock honest validation and close two stale Tier-1 omissions.
- Phase B (Steps 5-7) should be DEFERRED to a dedicated session: it edits the
  locked boros_energy.py, requires the Step 5 parameterization design that
  does not exist yet, and needs uninterrupted bit-stable gauntlet capture.
  Do not attempt it while another workflow is writing under apl/. Keep
  IMPERFECTIONS `card-specs-phase-b-migration-pending` OPEN and append the
  "not a pure refactor -- parameterize first" finding to it.

## Changelog
- 2026-06-28: Created. Audited live card_specs state; corrected the source
  spec's "pure refactor / byte-identical" Phase B framing against the actual
  divergence between card_specs/phlage.py and boros_energy.py:_handle_phlage.
