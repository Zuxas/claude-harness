# Spec: parallel_launcher cache-collision fix

**Status:** SHIPPED 2026-04-28 at commit e4fae86
**Created:** 2026-04-27 by claude.ai (post-Stage-C-revert)
**Target executor:** Claude Code
**Estimated effort:** 60-90 minutes (30-45 min code change + 15-30 min regression test design + 15 min docs/migration)
**Risk level:** MEDIUM — touches a shared cache that every gauntlet run depends on; correctness verifiable via direct repro from finding doc; bug class is well-understood (last-writer-wins on partial-key cache).
**Dependencies:**
- Finding doc `harness/knowledge/tech/cache-collision-bug-2026-04-27.md` (REQUIRED reading)
- Stage C reverted at commit `de96593` (pre-existing state assumed)
**Blocks:** past-validation-numbers-audit (BLOCKED on this), phase-3.5-stage-c-re-execution (BLOCKED on audit), all future Phase 3.5 stages D-K

## Summary

Fix the cache-key collision in `parallel_launcher.py` where `data/matchup_jobs/<opp>.json` is keyed by opp-name only, not by `(our_deck, opp)` pair. Last-writer-wins between concurrent or close-sequential gauntlets corrupts displayed numbers in any deck-pair where both decks ran against the same opp without intermediate cache invalidation.

This spec ships only the fix + regression test + cache invalidation. Past-numbers re-validation and Stage C re-execution are separate blocked-on-this-spec items, NOT in scope here.

## Pre-flight reads (REQUIRED before starting)

1. **`harness/knowledge/tech/cache-collision-bug-2026-04-27.md`** — full root-cause + reproduction + blast radius. The single most important read for this spec.
2. **`harness/knowledge/tech/spec-authoring-lessons.md` v1.3** — 10 lessons. Especially relevant:
   - `verify-identifiers-before-spec-execution` (verify `parallel_launcher.py` actual cache read/write call sites before pasting paths in this spec)
   - `load-bearing-wip-detection-applies-to-every-commit` (any imports added must have their target files tracked in same commit)
3. **`mtg-sim/parallel_launcher.py`** — read the actual file end-to-end before designing the fix. The spec's "Key design choice" section below assumes specific call-site shapes; verify them in the file before committing to the design.
4. **`mtg-sim/data/matchup_jobs/`** — `ls` the directory. Note current files. They will be deleted as part of the migration step (sub-step 3); confirm no other code reads from them outside `parallel_launcher.py` first.
5. **`harness/CLAUDE.md`** Rule 1, Rule 4, Rule 5, Rule 9.

## Background (concise; full version in finding doc)

Cache file `data/matchup_jobs/<opp_slug>.json` includes `our_deck` field in its body but is KEYED on opp-slug alone. When variant + canonical gauntlets run in parallel:
- Both write to the same path on disk
- Last-finisher's content overwrites first-finisher's
- Either gauntlet that reads this cache after both have run gets the OTHER deck's numbers

Tonight's reproduction: variant vs Izzet Prowess at n=1000 seed=42 returns 93.8% via direct `run_match_set`, but gauntlet display showed 48.5% — the cached value from canonical's run. Gauntlet display reads the cache, not the live computation result.

## Key design choice: cache-key format

Three viable options. Pick ONE in this spec; do not leave open as runtime config.

### Option A (RECOMMENDED): Subdirectory per our_deck

Path: `data/matchup_jobs/<our_deck_slug>/<opp_slug>.json`

**Pros:**
- Each our_deck gets its own namespace; collisions impossible by construction
- Trivially diff-able across our_deck variants (compare two subdirectories)
- `find data/matchup_jobs/ -name "*.json"` still works for global scans
- Filesystem-natural: matches how a human would organize the data
- Migration is straightforward: existing files are suspect anyway, delete them

**Cons:**
- Slightly more complex globbing patterns in any code that scans the cache
- One extra mkdir per our_deck (cheap)

### Option B: Tuple-encoded flat path

Path: `data/matchup_jobs/<our_deck_slug>__<opp_slug>.json`

**Pros:**
- Flat directory, simpler globbing
- One-line change to existing path-construction code

**Cons:**
- Double-underscore is a fragile separator — if either slug ever contains `__`, parsing breaks
- Harder to enumerate "all opps for our_deck X" without parsing every filename
- Visually noisier in `ls` output

### Option C: Hash-based key

Path: `data/matchup_jobs/<sha256(our_deck + opp)[:16]>.json`

**Pros:**
- Truly opaque, no separator-collision risk

**Cons:**
- Filenames become un-human-readable (debug hostility)
- Migration requires hash-table lookup to find existing file for a given pair
- Solves a problem we don't have (slug collision is preventable via slug rules)

**Decision: Option A.** The subdirectory approach matches the conceptual structure (our_deck owns its matchup results), is debug-friendly, and the slightly-more-complex globbing is a one-time cost in the launcher. Option B's `__` separator fragility is a real future bug waiting to happen the first time someone names a deck `boros_energy__variant`.

If during implementation Option A reveals a downstream consumer that cannot handle subdirectories (e.g., a downstream script that does `os.listdir(matchup_jobs_dir)` and assumes flat files), STOP and surface the conflict in an A1 amendment. The decision can be revisited but only with the conflict documented; don't silently fall back to Option B.

## Deliverables

### D1: Cache key change in parallel_launcher.py

Change cache write/read paths from:
```python
cache_path = data_dir / "matchup_jobs" / f"{opp_slug}.json"
```
to:
```python
cache_path = data_dir / "matchup_jobs" / our_deck_slug / f"{opp_slug}.json"
cache_path.parent.mkdir(parents=True, exist_ok=True)  # before write
```

Verify by reading `parallel_launcher.py` first that:
- `our_deck_slug` is available at the call site (or derivable from `our_deck` via existing slugify logic)
- There are exactly N call sites to update (do not assume; count them)
- No other module reads `data/matchup_jobs/*.json` paths directly

If any other module reads the cache, that module must also be updated in the same commit (load-bearing-WIP discipline). Likely candidates to grep: `dashboard.py`, `meta_bridge.py`, anything in `harness/scripts/` that reads gauntlet results.

### D2: Cache invalidation (one-time migration)

Existing files in `data/matchup_jobs/*.json` are suspect — pollution direction unknown per session. Delete them.

```python
# In a one-shot migration script, OR commit message documenting the manual step:
import shutil
old_dir = Path("data/matchup_jobs")
for json_file in old_dir.glob("*.json"):
    json_file.unlink()
# Subdirectories stay; new layout will populate them.
```

If you write this as a script (`scripts/migrate_cache_layout.py` or similar), it's a runnable artifact. If you do it manually (delete the files, document in commit message), that's also acceptable — this is a one-time migration, not ongoing tooling.

**DO NOT** preserve the old files "in case we need them." They are known-suspect data; keeping them invites future confusion about which numbers are trustworthy.

### D3: Regression test

**This is the actually-hard part of the spec.** A drive-by test ("run two gauntlets, check the numbers") will be flaky and won't catch the original bug class.

The test must:
1. **Construct the race condition deterministically** — not rely on actual parallelism timing
2. **Verify isolation under both write-orders** — variant-then-canonical AND canonical-then-variant
3. **Be fast** (under 30 seconds) so it runs on every commit
4. **Be non-flaky** (deterministic seeds, no actual subprocess racing)

**Recommended test design (validate this works during implementation; if it doesn't, surface in amendment):**

```python
# tests/test_cache_isolation.py
def test_cache_keyed_by_our_deck_pair():
    """Two decks running the same opp must have isolated cache entries."""
    # Use the existing run_match_set or a thin wrapper, NOT subprocess parallelism
    deck_a = "boros_energy_modern"
    deck_b = "boros_energy_variant_jermey"
    opp = "izzet_prowess_modern"
    seed = 42
    n = 100  # small for speed, just need cache write to fire
    
    # Write order 1: A then B
    result_a1 = run_and_cache(deck_a, opp, n=n, seed=seed)
    result_b1 = run_and_cache(deck_b, opp, n=n, seed=seed)
    
    # Read both back; they must differ (different decks → different numbers)
    # AND each must match its own write
    assert read_cache(deck_a, opp) == result_a1
    assert read_cache(deck_b, opp) == result_b1
    
    # Write order 2: B then A (reverse)
    result_b2 = run_and_cache(deck_b, opp, n=n, seed=seed)
    result_a2 = run_and_cache(deck_a, opp, n=n, seed=seed)
    assert read_cache(deck_a, opp) == result_a2
    assert read_cache(deck_b, opp) == result_b2
    
    # Across runs same seed should produce same result
    assert result_a1 == result_a2
    assert result_b1 == result_b2
```

If `run_and_cache` and `read_cache` aren't existing functions, they're thin wrappers around the launcher's existing read/write logic. The test should not duplicate launcher logic — it should call the launcher's actual cache I/O functions to verify those functions are correctly keyed.

**If the launcher's cache I/O isn't factored into callable functions** (i.e., it's inline in a long `main()`), the regression test surfaces an actual refactor opportunity: extract `read_matchup_cache(our_deck, opp) -> dict` and `write_matchup_cache(our_deck, opp, data) -> None`. This is a small refactor that makes the test possible AND makes the launcher more maintainable. Do it as part of D1; don't punt.

**Anti-pattern to avoid:** subprocess-based test that actually launches two `parallel_launcher.py` invocations and checks file timing. That's the integration test, and it's flaky. The unit-level test described above is sufficient because the bug class is "two writers to same path" — proving the path-construction is keyed correctly is sufficient proof; we don't need to prove the OS handles file writes correctly.

### D4: Documentation

Update `parallel_launcher.py` module docstring (or add one if missing) noting:
- New cache layout: `data/matchup_jobs/<our_deck_slug>/<opp_slug>.json`
- Why the change happened (one-line reference to finding doc)
- Implications for callers: any external script reading the cache must traverse the subdirectory

If `parallel_launcher.py` has no module-level docstring currently, add one — this is the right moment.

## Validation gates

**Gate 1: Direct repro from finding doc still passes.**
```bash
cd "E:/vscode ai project/mtg-sim"
python -c "
import os
os.environ['MTG_SIM_NOCACHE'] = '0'  # ensure cache is being read/written
# (or whatever the launcher's cache-bypass flag is, if any)

# Run variant Jermey vs Izzet Prowess via direct call
from generate_matchup_data import run_match_set  # or whatever module exports this
result = run_match_set(
    our_deck='boros_energy_variant_jermey',
    opp='izzet_prowess_modern',
    n=1000, seed=42, format_name='modern'
)
print(f'Direct: {result}')
"
```
Must return ~93.8% (matching tonight's diagnostic baseline). If it doesn't, something else changed in the engine since tonight's diagnostic — STOP and re-investigate before touching the cache.

**Gate 2: Gauntlet display matches direct call.**
```bash
python parallel_launcher.py --deck "Boros Energy Variant Jermey" --format modern --n 1000 --seed 42
# Check displayed Izzet Prowess number
```
Must be within ±2pp of Gate 1's number (small variance acceptable due to any aggregation differences; large variance means cache is still polluted somehow).

**Gate 3: Stability across parallel runs.**
Run variant + canonical gauntlets concurrently 3 times. After each pair of runs, read both caches. Variant cache must contain variant numbers, canonical cache must contain canonical numbers. All 6 reads stable.

**Gate 4: Regression test passes.**
`pytest tests/test_cache_isolation.py` returns 0.

**Gate 5: No other module broken.**
Run drift-detect; should still exit at the same code as pre-spec. Run any quick smoke tests that touch the cache (dashboard.py if it reads cache, meta_bridge.py if it does). Specifically check that `harness/scripts/lint-mtg-sim.py` still runs clean against mtg-sim (it doesn't read this cache directly per current understanding, but verify).

**Gate 6: Migration completed.**
`ls data/matchup_jobs/` shows subdirectories per our_deck after a fresh gauntlet run, no top-level `.json` files left over.

## Stop conditions

**Stop and ship when:**
- All 6 gates pass
- Spec status updated to SHIPPED with commit hashes recorded
- IMPERFECTIONS.md `parallel-launcher-cache-collision-fix` moves to RESOLVED.md

**Stop and amend (do NOT improvise) if:**
- Pre-flight reading reveals the cache is read by 3+ modules outside `parallel_launcher.py` (scope creep — re-spec with full caller audit before proceeding)
- Gate 1 fails (direct call doesn't return ~93.8%) — engine state changed, the bug is no longer just cache-collision, escalate
- Gate 3 reveals a SECOND cache-collision class on a different file (e.g., `data/results_*.json` or similar) — document as separate finding before continuing
- Regression test design (D3) cannot be made non-flaky in under 60 minutes — fall back to integration-style test with explicit caveat in test docstring, but DO NOT ship without some regression coverage

**DO NOT do these things:**
- Do NOT preserve old cache files. They are known-suspect.
- Do NOT add a "compatibility shim" that reads from both old and new paths. Forces ambiguity into the codebase forever; we want a clean cutover.
- Do NOT touch any deck files, APL files, or engine logic. This spec is launcher-only.
- Do NOT bundle Stage C re-execution into this commit. That's a separate downstream item.
- Do NOT update past spec changelogs (Stage A, Stage B) with corrected numbers. That happens in past-validation-numbers-audit, the next blocked spec.
- Do NOT compound v1.4 lessons yet (Rule 9 — only after this spec ships and the lessons are validated by execution).

## Reporting expectations

After completion, report back with:

1. **Commit hash(es).** Single commit preferred; if D1+D2+D3+D4 split into multiple, list each.
2. **Cache-key call site count.** How many places in `parallel_launcher.py` (and other modules if any) needed updating. Confirms the design assumption.
3. **Gate results.** PASS/FAIL per gate with measured numbers.
4. **Regression test runtime.** Confirms it's fast enough for every-commit running.
5. **Migration outcome.** Number of old `.json` files deleted.
6. **Caller audit results.** Did any module outside `parallel_launcher.py` need updating? If so, which.
7. **Any deviations** from this spec (amendments A1-AN documented inline in the spec body).
8. **Confidence statement** on the fix: any remaining concern about pollution paths not addressed by this change?

Then update spec status to SHIPPED, add line to RESOLVED.md, summary in chat. Per Rule 9, queue the v1.4 lesson candidates for the next compound pass (do not compound them as part of this spec; they need post-execution validation).

## Mid-execution amendments

### A1: Bug class is subprocess output collision, not cache collision

**Pre-flight discovery (D1 step 1):** Reading `parallel_launcher.py` and `run_matchup.py` end-to-end revealed the actual mechanism. `data/matchup_jobs/<opp>.json` is NOT a cache (no skip-if-exists logic) — it's the per-matchup subprocess OUTPUT file. `run_matchup.py:266` writes it; `parallel_launcher.py:77` reads it after subprocess exits. The "cache" framing in the finding doc was conceptually wrong; the collision is between subprocess output writers when two launchers spawn `run_matchup.py "<deck-A>" "<opp>" ...` and `run_matchup.py "<deck-B>" "<opp>" ...` simultaneously. The fix is identical (key on (our_deck, opp)) but understanding affects the regression test design — the test verifies path-keying differentiates per (our_deck, opp), not anything cache-semantic.

**Resolves spec 1's "Open question" (Stage A/B JSON clean vs Stage C JSON polluted):** Same mechanism, different timing race. Whichever launcher polled-and-read its subprocess output AFTER all writes had occurred got the last-writer's content. Stage A/B variant launchers happened to poll-and-read BEFORE canonical's subprocess overwrote; Stage C variant launcher polled after. The fix eliminates the race by making subprocesses write to distinct paths.

### A2: New helper module is the natural extraction point

**During D1 implementation:** Extracting cache I/O into a callable helper (per spec recommendation) was clean — both `parallel_launcher.py` and `run_matchup.py` had identical inline slug logic. New module `matchup_jobs.py` at repo root holds `_slugify`, `matchup_job_path(our_deck, opp)`, and `ensure_parent`. Both files import from it. This also satisfies the load-bearing-WIP discipline (drift-detect caught the import in real time before commit and forced the helper to land in the same commit as its consumers).

## Concrete steps (in order)

1. **Pre-flight reads** — finding doc, lessons v1.3, `parallel_launcher.py` end-to-end (15 min)
2. **Caller audit** — grep all of mtg-sim + harness for `matchup_jobs` references; list every reader of the cache (5 min)
3. **Gate 1 baseline** — verify direct `run_match_set` call still returns ~93.8% before changing anything; confirms baseline (5 min)
4. **D1 implementation** — change cache-key construction in launcher + any other readers; refactor read/write into callable functions if needed for D3 (20-30 min)
5. **D2 migration** — delete old `data/matchup_jobs/*.json`; commit message documents the deletion (2 min)
6. **D3 regression test** — write `tests/test_cache_isolation.py`; iterate until non-flaky and under 30s runtime (15-25 min)
7. **D4 documentation** — module docstring update (5 min)
8. **Run all 6 gates** — each must pass before commit (15 min)
9. **Commit + update spec status to SHIPPED + IMPERFECTIONS → RESOLVED** (5 min)
10. **Confirm 2 BLOCKED imperfections (past-validation-numbers-audit, phase-3.5-stage-c-re-execution) are now unblocked** in IMPERFECTIONS.md status field (2 min)

Total: 80-100 minutes including testing.

## Why this order

- Pre-flight reads first because the cache-key change depends on understanding actual call-site shape; designing on assumed shape is the failure mode that produced the original bug.
- Gate 1 baseline before changing anything — if direct call doesn't return tonight's number, the engine drifted and this whole spec is built on stale evidence.
- D1 and D3 are entangled (regression test calls launcher's cache I/O functions; if those aren't factored, D3 forces D1 to refactor). Treat as a unit.
- Migration (D2) before regression test (D3) so the test runs against the new layout, not the legacy directory.
- All gates before commit because the cache change is invisible to most callers — the test must catch the regression class, not just spot-check.

## Future work this enables (NOT in scope)

- **past-validation-numbers-audit** (next blocked spec). Re-runs Stage A + Stage B variant gauntlets against fixed cache, compares to documented numbers, surfaces discrepancies.
- **phase-3.5-stage-c-re-execution** (blocked on audit). Re-applies C.1 helper code, runs C.4 validation against trustworthy pipeline.
- **v1.4 lesson compound** (Rule 9). After this spec ships and the past-audit confirms whether prior lessons need correction, compound the 3 candidate lessons from `cache-collision-bug-2026-04-27.md` into `spec-authoring-lessons.md` v1.4.
- **Cache-key audit across all of mtg-sim**. Tonight's surfacing was one cache. Are there others keyed on partial state? Worth a follow-up scan; not blocking.

## Changelog

- 2026-04-27 (post-Stage-C-revert): Spec created (PROPOSED) by claude.ai. Cache-key design choice locked to Option A (subdirectory). Regression test design specified as unit-level via factored cache I/O functions, NOT subprocess-based integration. Targeted for Claude Code execution as `plan-2026-04-28.md` step 3.
- 2026-04-28: SHIPPED at commit e4fae86 (Claude Code). Bundle includes new helper `matchup_jobs.py`, modified `parallel_launcher.py` + `run_matchup.py`, regression test `tests/test_cache_isolation.py`, and migration (65 old top-level *.json files deleted). Amendment A1 reframed bug class (subprocess output collision, not cache); A2 captured load-bearing-WIP catch-and-fix during the same commit. Caller audit confirmed only 2 modules touch `data/matchup_jobs/`. Gates 1-6 all pass. New IMPERFECTIONS unblocked: past-validation-numbers-audit (was BLOCKED on this), phase-3.5-stage-c-re-execution (chain-blocked).
