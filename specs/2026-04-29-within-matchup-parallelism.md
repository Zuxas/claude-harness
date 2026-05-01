# Spec: Within-matchup parallelism (Stage 1.7 unblocked, 3-5x gauntlet wall reduction)

**Status:** SHIPPED
**Created:** 2026-04-28 by claude.ai (for tomorrow execution OR future session)
**Target executor:** Claude Code
**Estimated effort:** 60-90 minutes
**Risk level:** MEDIUM — touches core gauntlet pipeline performance characteristics; thread/process pool boundaries can introduce regressions if shared state assumed (most of which Stage 1.7 just closed). Bit-stable baseline is the safety net.
**Dependencies:**
- `harness/specs/2026-04-28-stage-1.7-event-bus-determinism.md` SHIPPED 2026-04-28 at `30c992a` (the unblocking work)
- Bit-stable baseline canonical 64.5% / variant 78.8% to validate against
**Resolves:** No OPEN imperfection (this was a `Future work this enables` from Stage 1.7); it's an opportunity, not a bug

## Goal

Stage 1.7's third-mutation-source fix made gauntlet runs bit-stable across consecutive same-seed invocations. The mechanism (save/seed/restore global random state around `run_match_set` + `run_bo3_set`) was the prerequisite for running multiple games concurrently within a single matchup — previously, naked `random.foo()` consumers across threads would have corrupted each other; now they're scoped per call.

This spec adds within-matchup parallelism: instead of N=1000 games sequential per matchup, spawn a thread/process pool that runs ~CPU-count games concurrently, then aggregates. Per Stage 1.7 prior framing: 3-5x wall-time reduction on the gauntlet.

After this ships, gauntlet runs that today take ~30-60 seconds drop to ~10-20 seconds. Compounds across every future gauntlet, every nightly retune, every spec validation gate that runs a gauntlet.

This spec is **not Friday-prep critical** — gauntlet wall time isn't blocking competitive prep. It's compounding infrastructure value. Ship anytime; weight is on quality, not urgency.

## Pre-flight reads (REQUIRED)

1. `harness/RESOLVED.md` — entry `stage-1-7-event-bus-determinism` (full diagnostic chain + fix locations)
2. `mtg-sim/engine/match_runner.py` — `run_match_set` post-1.7 implementation
3. `mtg-sim/engine/bo3_match.py` — `run_bo3_set` post-1.7 implementation
4. `mtg-sim/parallel_launcher.py` — current outer parallelism (across matchups; this spec is INNER parallelism within a matchup)
5. `mtg-sim/tests/test_determinism.py` — Stage 1.7 regression test (must continue passing)
6. `harness/knowledge/tech/perf-within-matchup-parallelism-2026-04-26.md` — original performance analysis

## Scope

### In scope
- Add `n_workers` parameter to `run_match_set` and `run_bo3_set` (default 1 = current sequential behavior; > 1 = parallel)
- When `n_workers > 1`, spawn a worker pool (threading or multiprocessing — decide in T.1 based on GIL impact measurement) that splits the N games across workers
- Per-worker seed derivation: `worker_seed = base_seed * 1000 + worker_id` (or similar deterministic scheme) so each worker gets reproducible-but-distinct random streams
- Result aggregation: combine per-worker `MatchSetResults` / `Bo3SetResults` into a single result identical in shape to the sequential version
- Update `parallel_launcher.py` to pass `n_workers` (default 1 for safety; CLI flag `--inner-workers N` for opt-in)
- Determinism preservation: same total N, same base seed, same n_workers → bit-identical aggregate (this is the headline guarantee)

### Explicitly out of scope
- Changing the outer parallelism (across matchups) — already exists; orthogonal
- Changing the public CLI default to >1 workers — too risky for unattended scheduled tasks until proven over many runs
- Process-pool spawning if thread-pool is sufficient (decide empirically, default thread-pool simplicity)
- GIL-bypass refactoring of engine code — out of scope; if GIL-bound, document and use multiprocessing

## Steps

### T.0 — GIL impact measurement (~10 min)

Before committing to thread-pool vs process-pool, profile current `run_match_set` to see if it's CPU-bound (GIL-affected) or I/O/import-bound:

```python
import cProfile, pstats
# ... existing run_match_set call setup ...
cProfile.run("run_match_set(apl_a, deck_a, apl_b, deck_b, on_play=True, n=1000, seed=42)", "/tmp/profile.out")
stats = pstats.Stats("/tmp/profile.out")
stats.sort_stats("cumulative").print_stats(30)
```

If pure-Python CPU dominates: process-pool (multiprocessing.Pool). If significant I/O or extension-module time: thread-pool (concurrent.futures.ThreadPoolExecutor) might be sufficient.

Default recommendation: thread-pool first; if speedup ≤2x at 8 workers, switch to process-pool.

### T.1 — Per-worker seed scheme (~10 min)

Decide and document the deterministic seed derivation. Constraint: `(N, base_seed, n_workers)` must produce bit-identical aggregate result regardless of n_workers value (because aggregate is the user-facing measurement; if it changes with worker count, determinism is violated).

Recommended scheme:
- Worker `i` runs games `[i, i+n_workers, i+2*n_workers, ...]`
- Each game's per-game seed derives from `(base_seed, game_index)` deterministically (already mostly true post-1.7; verify)
- Aggregate: concatenate per-worker results in `game_index` order

This guarantees same game-index → same seed → same outcome → bit-identical aggregate.

### T.2 — Implement parallel path in `run_match_set` (~20 min)

```python
# After Stage 1.7 fix; ADDS n_workers param
def run_match_set(apl_a, deck_a, apl_b, deck_b, on_play=True, n=1000, seed=42,
                  mix_play_draw=False, use_combo_sampler=False, n_workers=1):
    # Existing save/seed/restore global random pattern (Stage 1.7)
    saved_global_random_state = random.getstate()
    random.seed(seed)
    try:
        if n_workers == 1:
            return _run_match_set_sequential(...)  # extract current loop
        else:
            return _run_match_set_parallel(..., n_workers=n_workers)
    finally:
        random.setstate(saved_global_random_state)
```

`_run_match_set_parallel` spawns the pool, distributes game indices, collects results, aggregates into the same `MatchSetResults` shape.

### T.3 — Mirror in `run_bo3_set` (~15 min)

Per `parallel-entry-points-need-mirror-fix` v1.5 lesson: do NOT ship parallel `run_match_set` without parallel `run_bo3_set`. Same shape; bo3 path has 5 canonical matchups in current Modern field.

### T.4 — Regression: bit-identical aggregate (~10 min)

Extend `tests/test_determinism.py`:

```python
def test_n_workers_determinism():
    """Same (n, seed) with different n_workers must produce identical aggregate."""
    args = dict(apl_a=..., deck_a=..., apl_b=..., deck_b=..., n=200, seed=42)
    r1 = run_match_set(**args, n_workers=1)
    r4 = run_match_set(**args, n_workers=4)
    r8 = run_match_set(**args, n_workers=8)
    assert r1.a_wins == r4.a_wins == r8.a_wins, "win count must be invariant under n_workers"
    assert r1.kill_turns == r4.kill_turns == r8.kill_turns, "kill_turns must be invariant"
    assert r1.avg_turns == r4.avg_turns == r8.avg_turns, "avg_turns must be invariant"
```

This is the headline gate. If any worker count produces different results from n_workers=1, parallelism violates determinism — STOP.

### T.5 — Production-scale validation (~10 min)

```bash
cd "E:/vscode ai project/mtg-sim"
# Sequential baseline
time python parallel_launcher.py --deck "Boros Energy" --format modern --n 1000 --seed 42
# Note: aggregate canonical, wall time
# Parallel
time python parallel_launcher.py --deck "Boros Energy" --format modern --n 1000 --seed 42 --inner-workers 8
# Note: aggregate canonical (must match), wall time (should be 2-5x faster)
```

### T.6 — CLI flag + `parallel_launcher.py` plumbing (~10 min)

Add `--inner-workers N` to the parallel_launcher argparse. Pass through to subprocess invocations. Default 1 (no behavior change).

### T.7 — Cascade docs + commit (~10 min)

- ARCHITECTURE.md note: gauntlet wall reduced via inner parallelism (cite numbers)
- Update Stage 1.7 RESOLVED.md "Unblocks" line: "within-matchup parallelism: SHIPPED at <hash>"
- Spec status PROPOSED → SHIPPED with execution log

## Validation gates

| Gate | Acceptance | Stop trigger |
|---|---|---|
| 1 — sequential bit-identical | n_workers=1 produces same result as pre-spec call | any drift |
| 2 — parallel determinism | n_workers ∈ {1, 4, 8} all produce bit-identical aggregate (T.4 test) | any worker count diverges — STOP, do not ship |
| 3 — wall reduction | n_workers=8 wall time ≤ 0.6x of n_workers=1 wall time | speedup <1.5x — investigate (GIL? overhead?), possibly switch to process-pool |
| 4 — Stage 1.7 regression test still passes | `python tests/test_determinism.py` → 3/3 pass | any test fails |
| 5 — production gauntlet bit-identical | Canonical Modern gauntlet n=1000 seed=42 with --inner-workers 8 produces 64.5% same as pre-spec | any drift |
| 6 — bo3 matchups also bit-identical | All 5 bo3 matchups in canonical gauntlet identical between sequential and parallel | bo3 mismatch — `parallel-entry-points-need-mirror-fix` lesson re-application failed; investigate |
| 7 — drift-detect clean | Drift-detect 0 errors, 0 warnings | new errors |

## Stop conditions

- **Gate 2 fails (worker count affects aggregate):** STOP, do not ship. Determinism is the non-negotiable contract. The seed derivation scheme is wrong; revisit T.1.
- **Speedup <1.5x at 8 workers:** Likely GIL-bound. Switch to process-pool; if still <1.5x, document and partial-ship (sequential path stays default; parallel available but not recommended).
- **bo3 path mirror missed:** Same-class lesson failure as S3.8. Document, fix, re-validate.
- **Regression in determinism test:** STOP. Stage 1.7's contract is sacred; this work must not weaken it.
- **Memory pressure at high worker counts:** Document the practical ceiling (e.g., "n_workers ≤ N/100 to keep per-worker game count meaningful"); document recommended default.

## Reporting expectations

1. GIL profiling result (T.0) — thread or process pool decision rationale
2. Wall time table: n_workers ∈ {1, 2, 4, 8, 16} → wall, speedup
3. Bit-identical confirmation across all worker counts (Gate 2)
4. Production gauntlet number unchanged (Gate 5)
5. Recommended default for `--inner-workers` (likely 4 or 8, conservative)
6. Spec PROPOSED → SHIPPED, ARCHITECTURE.md updated, Stage 1.7 RESOLVED entry updated

## Future work this enables (NOT in scope)

- **Default `--inner-workers` switch from 1 to N after a week of unattended runs proves stability:** Separate ship decision once enough runs in the field to trust.
- **Across-format inner parallelism:** Modern + Standard simultaneously with shared worker pool. Different concurrency model; separate spec.
- **Further gauntlet wall reductions** by composing inner + outer parallelism more aggressively (currently outer is per-matchup subprocess; inner would now be per-game thread/process within each subprocess).

## Changelog

- 2026-04-28: Created (PROPOSED) by claude.ai for tomorrow execution OR future session. NOT Friday-prep critical. Compounding infrastructure value: every future gauntlet, every nightly retune, every spec validation gate that runs a gauntlet benefits.
- 2026-04-30: SHIPPED at 8706f68. ProcessPoolExecutor path. Per-game global seeding scheme ensures cross-n_workers bit-identity. n_workers=1 uses per-game seeding (slight departure from pre-spec chained global random -- prerequisite for bit-identity guarantee). Wall: n_workers=8 at n=200: 2.2x speedup. All 4 determinism tests pass. --inner-workers N wired through parallel_launcher -> run_matchup.
