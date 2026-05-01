# Perf: Within-Matchup Parallelism for Gauntlet Runs

**Date:** 2026-04-26
**Status:** Stage 0 COMPLETE, Stage 1 PARKED, Stage 1.5 SHIPPED (partial),
Stage 1.6 SHIPPED (partial), Stage 1.7 SPECCED for fresh session
**Estimated payoff:** 3-5x wall-time reduction on Modern gauntlet
**Bonus finding:** Stage 1 validation surfaced ~3-5pp gauntlet result
inflation from Card + APL state leakage (see Stage 1.5)

## The bottleneck

`parallel_launcher.py` parallelizes ACROSS matchups (one subprocess per
opponent), but the n-game loop INSIDE each matchup runs single-threaded.

Empirical evidence from 2026-04-26 100k Modern run (BE vs 14 archetypes):
- 8 of 14 matchups finish in ~10s (DB-cached G1 lookups, no real sim)
- 6 matchups grind serially in the long tail:
  - Mono Red Aggro: 180s
  - Izzet Affinity: 1964s (33 min)
  - Domain Zoo: 2066s
  - Eldrazi Tron: 2175s
  - Izzet Prowess: 2199s
  - Jeskai Blink: 2418s (40 min, == total wall time)
- Total wall: 2419s (~40 min)
- Observed CPU during long tail: ~37% on Ryzen 9 3900XT (12 cores / 24 LP)
  = ~9 of 24 logical processors active, ~15 idle

Wall time = slowest matchup's wall, regardless of how many cores are
idle. Six matchups finish at very different points but only one of
them is the bottleneck for total wall.

## The fix (3-stage spec)

### Stage 0 — verification (~10 min, READ-ONLY)
1. `python -c "import multiprocessing as mp; print(mp.cpu_count())"` -- confirm 24
2. `grep -rn "run_match_set" --include="*.py"` -- enumerate callers
3. `grep -rn "run_bo3_set" --include="*.py"` -- enumerate callers
4. `head -120 parallel_sim.py` -- proves ProcessPoolExecutor pattern works
5. `grep -n "open(\|sqlite\|connect\|@lru_cache" engine/match_runner.py`
   -- check for non-picklable state in hot path

Stop condition: Card objects fail to pickle -> fall back to deck-by-name
passing pattern (slower per-worker startup but works).

### Stage 1 — opt-in parallel `run_match_set` (~60-90 min)

Add `workers: int = 1` parameter to `engine/match_runner.run_match_set`.
Default 1 = current serial behavior, no regression. When `workers > 1`
and `n >= 100`: split the n-game loop across worker processes via
`ProcessPoolExecutor`. Each worker gets a unique seed offset
(`seed + w * 1_000_000`) to avoid correlated draws.

Worker entry must be top-level for picklability:
```python
def _match_worker(task: dict) -> MatchSetResults:
    from apl import get_apl
    apl_a = get_apl(task["apl_a_name"])
    apl_b = get_apl(task["apl_b_name"])
    return run_match_set(
        apl_a, task["deck_a"], apl_b, task["deck_b"],
        n=task["n"], on_play=task["on_play"],
        seed=task["seed"], mix_play_draw=task["mix_play_draw"],
        workers=1,  # CRITICAL: no recursion
    )
```

Validation:
- workers=1 path identical to current (deterministic at fixed seed)
- workers=4 within +/-2% of workers=1 result at n=10k
- workers=8 produces 4-7x speedup vs workers=1 (process startup +
  Card pickle eat some of the theoretical 8x)

### Stage 2 — wire `workers` through to `run_matchup.py` (~30 min)

`parallel_launcher.py` adds `--workers-per-matchup N` flag (default `auto`).
Auto computes `cores // total_matchups` (floor 1):
- Modern field, 14 matchups, 12 cores: `12 // 14 = 0 -> floor 1` (no-op)
- Pioneer field, 6 matchups, 12 cores: `12 // 6 = 2` (2-way parallel
  per matchup)
- Standard field, 8 matchups, 12 cores: `12 // 8 = 1` (1-way, no-op)

For long-tail scenarios where total_matchups exceeds cores but final
matchups grind alone, Stage 2 doesn't help. Dynamic re-balancing would
-- out of scope; track as follow-up if long-tail persists.

### Stage 3 — same pattern for `run_bo3_set` (~30 min)

`engine/bo3_match.run_bo3_set` is the more sophisticated runner used
by the real-Bo3-with-sideboarding path. Same parallelization approach.
If Bo3 has shared state across games (sideboard plan mutation), surface
differences before Stage 3 implementation.

## Stop conditions
- Stage 0: Card pickle fails -> fall back to deck-by-name workers
- Stage 1: workers=4 diverges >2% from workers=1 -> seed offset issue
  or shared state pollution, investigate
- Stage 2: --workers-per-matchup auto crashes -> surface, don't
  silently fall back
- Engine surface area expands beyond match_runner / bo3_match /
  run_matchup / parallel_launcher -> STOP, narrow scope
- Total wall INCREASES with workers > 1 -> profiling needed (Card
  pickle overhead probably dominating at small n)

## Expected impact
- Modern 100k gauntlet: 40 min -> 10-15 min wall (3-4x speedup)
- Pioneer 100k gauntlet: comparable improvement
- Every IzzetProwess refactor validation, every Pioneer drain, every
  Standard tier shake-up benefits

## Implementation log

### Stage 0 — verification (2026-04-26, COMPLETE)
- `mp.cpu_count()` = 24 (Ryzen 9 3900XT logical processors, as expected)
- `run_match_set` callers (8): engine/match_runner.py (def),
  engine/match_engine.py, generate_matchup_data.py,
  tests/test_match_engine.py, run_matchup.py (Stage 2 wire point),
  api/sim_api.py, engine/variant.py, parallel_sim.py
- `run_bo3_set` callers (3): run_matchup.py, api/sim_api.py,
  engine/bo3_match.py (def)
- engine/match_runner.py: zero matches for `open(`, `sqlite`,
  `connect(`, `@lru_cache`. **No non-picklable state in hot path.**
- data/card.py:47-48: `Card` is `@dataclass`. Pickle-friendly by
  default; fallback to deck-by-name passing not needed.
- parallel_sim.py: already implements the spec's exact pattern at
  the cross-matchup level (`_worker(task: dict)` at module scope,
  `sys.path.insert`, decks reloaded per-worker via `load_deck_and_apl`).
  Stage 1's `_match_worker` is essentially a copy of `_worker` adapted
  for within-matchup chunks instead of cross-matchup tasks.
- **No stop conditions triggered.** Stage 1 risk surface is lower
  than spec assumed.

### Stage 1 — opt-in parallel `run_match_set` (PARKED)

Implementation drafted (workers parameter, `_match_worker` top-level
function, ProcessPoolExecutor branch with seed offsets) but REVERTED
during validation -- the determinism stop condition fired and exposed
a bigger problem (Stage 1.5). Resume after Stage 1.6 fully fixes
non-determinism.

Drafted code was reverted in-place before commit; not in git history.
Re-implementation needed from the Stage 1 spec section above. The
spec is complete enough to re-build cold.

Validation script `tests/test_run_match_set_workers.py` exists as
untracked file -- usable infrastructure for fresh session, depends on
the workers parameter so it'll error until Stage 1 re-lands. Tests
all three validation criteria (determinism, statistical equivalence,
speedup). Delete or keep based on fresh-session preference.

### Stage 1.5 — Card state leakage fix (COMPLETE, PARTIAL)
Commit: `63d0c75` (2026-04-26)

Diagnosis: `TwoPlayerGameState.__init__` shallow-copied deck lists
(`self.lib_a = list(deck_a)`). Card object instances were SHARED across
games in `run_match_set`. Mutations during game N
(`summoning_sickness`, `lore_counters`, `is_transformed`, +1/+1
counters, tap state) persisted into game N+1.

Fix: deepcopy each Card per game in `TwoPlayerGameState.__init__`.

Effect on BE vs Domain Zoo at n=200 seed=42:
- Pre-fix:  98.5% / 99.5% win rate (Card state leak inflated +5pp)
- Post-fix: 94.5% / 93.5% win rate (closer to true value)

Effect on tonight's 71.5% Modern field-weighted headline (commit
`0bc20bf`): not re-measured, but extrapolating from BE vs Domain Zoo's
~5pp shift, likely drops to **67-69%** when re-run on fixed engine.
Aggressive matchups (BE vs Mono Red, Izzet Affinity, Domain Zoo)
were the most inflated; close matchups (Eldrazi Ramp, Izzet Prowess)
likely shifted <1pp because Card mutation matters less when neither
side dominates.

PARTIAL fix -- determinism still not bit-identical at fixed seed.
Diagnostic at n=200:

| Test | APL                | Decks              | Delta |
|------|--------------------|--------------------|-------|
| A    | reused             | reused             | 6     |
| B    | fresh-per-call     | fresh-per-call     | 2     |
| C    | reused             | fresh-per-call     | 4     |

APL instance state mutation accounts for ~4 of 6 delta. Some residual
~2-game noise from another mutation path (possibly token Cards
appended to bf during play, possibly something in `_build_view`'s
`mana_pool.add_land` chain).

### Stage 1.6 — APL state isolation (COMPLETE, PARTIAL)
Commit: `1e55791` (2026-04-26)

Diagnosis: APL instance state leaked across games in `run_match_set`
inner loop. Per-game-mutable APL fields not reset between games:
BorosEnergyAPL has `_cat_died_this_turn`, `_treasures`,
`_gained_life_this_turn`, `_tokens_entered_this_turn`, `_roles_computed`
cache; similar patterns in other APLs.

Fix: instantiate fresh APL per game via `type(apl)()` at the top of
each game iteration in `run_match_set`. Pre-flight verified all 72
registered APLs construct cleanly with no-arg ctor.

Effect (stacks on Stage 1.5 Card deepcopy) at n=200 BE vs Domain Zoo
same seed:

| State                   | Delta (games) | Win Pct  |
|-------------------------|---------------|----------|
| Pre-Stage-1.5           | 6             | 98.5/99.5|
| Post-Stage-1.5          | 2-3           | 94.5/93.5|
| Post-Stage-1.5 + 1.6    | 2-3           | 95.0/93.5|

Marginal narrowing at n=200 because Stage 1.5 already removed the
biggest leakage source on this matchup. APLs with more per-game
state (or matchups with more APL-state-driven decisions) will
benefit more.

PARTIAL FIX -- residual ~2-3 game noise persists. Third mutation
source remains; see Stage 1.7.

### Stage 1.7 — Third mutation source (FRESH SESSION)

Stage 1.5 + Stage 1.6 together eliminated Card and APL state leakage
but determinism check still fails at n=200 same seed (delta=2-3 games
residual). A third mutation source exists.

Investigation order (highest to lowest suspicion):

(a) **Event bus state.** `engine/runner.py:178` (goldfish runner)
    explicitly resets event_bus per game. `engine/match_runner.py`
    does NOT appear to reset event_bus in the inner loop. If listeners
    or queued events persist across games, that's the leak.
    Check `engine/match_runner.py` for event_bus references; if none
    exist, check whether event_bus is accessed via global state or
    imported from a module that retains state across games.

(b) **Token Card singletons.** Some token-creating handlers may
    construct Card objects from module-level templates rather than
    fresh-per-trigger. Goblin Bombardment, Voice of Victory,
    Ocelot Pride are candidates. Trace `_make_token` in
    `engine/game_state.py`; verify each call constructs a fresh Card.

(c) **`gs.transform()` shared state.** The transform mechanic mutates
    a Card in place; if multiple games reference the same Card
    instance via module-level reference (back_face dict shared
    across copies?), state could leak.

(d) **Static class-level mutables on APL classes.** Even though
    Stage 1.6 instantiates fresh APLs per game, class-level dicts/sets
    (e.g., `SPECIAL_MECHANICS` as class attribute, `DEAD_IN_GOLDFISH`
    set) could be mutated and persist across instances. Check
    `BorosEnergyAPL` class body for any mutable class attribute.

**Recommended approach:** instrument `engine/match_runner.run_match`
with hash logging at game start and end of mutable state (event bus
listener count, sum of all token Card ids, BorosEnergyAPL class
attribute states). Run 5 games sequentially, diff hashes between
games. The mutation source will reveal itself.

Validation after Stage 1.7 lands:
1. Determinism check: `workers=1`, same seed twice -> identical
2. BE goldfish baseline regression check (T4.45, 100% WR, T4 median
   should be stable; if shifts >0.10 turn surface).
3. BE Modern 1k gauntlet sanity check -> expected 67-69%
   field-weighted (Stage 1.5+1.6+1.7 combined deflation).

Then resume Stage 1 perf work (workers param + ProcessPoolExecutor
+ seed-offset chunks). Stage 1 implementation drafted earlier in
this session but reverted; spec section above has full detail for
re-build.

Estimated: 30-60 min Stage 1.7 + 30 min Stage 1 resume + 30 min
Stage 2 + 30 min Stage 3 = ~2-2.5 hours fresh session.

### Stage 2 — wire workers through to `run_matchup.py`
[Pending Stage 1.6 -> Stage 1 resume]

### Stage 3 — same pattern for `run_bo3_set`
[Pending Stage 1.6 -> Stage 1 -> Stage 2]
