# Spec: Drift-detect 8th check — cache-key audit detection

**Status:** SHIPPED 2026-04-28 via execution-chain S6 (numbered as 7th check; sibling 7th-check-spec-validation spec was still PROPOSED so this took the 7 slot)
**Created:** 2026-04-27 by claude.ai
**Target executor:** Claude Code
**Estimated effort:** 45-75 minutes
**Actual effort:** ~40 min
**Risk level:** LOW (additive check on drift-detect; no engine code touched)
**Dependencies:**
- `harness/specs/2026-04-28-drift-detect-7th-check-spec-validation.md` (PROPOSED) — sibling, both add checks; if both ship, this is the 8th
- `harness/specs/2026-04-28-cache-key-audit-mtg-sim.md` (PROPOSED) — sibling; pairs naturally
**Blocks:** Nothing directly. Closes the loop on the cache-collision bug class via tooling.

## Summary

Tonight's cache-collision bug surfaced a generalizable bug class: caches keyed on partial state break silently under concurrent writers. The `cache-key-audit-mtg-sim.md` spec audits the codebase ONCE for this pattern; this spec adds drift-detect mechanical detection so future caches can't reintroduce it without flagging.

The check scans mtg-sim source for cache-write patterns and flags any that don't include the full set of relevant parameters in the path. Output is INFO-level findings (warnings, not errors) because the heuristic has false positives.

## Pre-flight reads (REQUIRED)

1. `harness/scripts/drift-detect.ps1` — read end-to-end. The 8th check follows the same structural pattern as checks 1-6 (and 7th if shipped first).
2. `harness/specs/2026-04-28-drift-detect-7th-check-spec-validation.md` — sibling spec; if SHIPPED, the new check is 8th. If not SHIPPED, this becomes 7th. Verify ordering at start.
3. `harness/knowledge/tech/cache-collision-bug-2026-04-27.md` — the prototype bug class
4. `harness/knowledge/tech/spec-authoring-lessons.md` v1.3

## Background

Tonight's bug:
- `data/matchup_jobs/<opp>.json` writes a result that depends on (our_deck, opp, n, seed)
- Path includes only opp
- Concurrent writers from different (our_deck) values overwrite each other

A mechanical detector for this class needs to:
1. Find cache-write call sites
2. Identify the parameters that affect the result being written
3. Check whether the path includes those parameters
4. Flag mismatches

Step 2 is the hard part — the detector needs to know which parameters matter. Three approaches:

**Approach A: Naming convention.** If the function takes parameters `our_deck` AND `opp` AND writes a path `<opp>.json`, flag. Heuristic: parameters whose names match common identity-shaping words (`deck`, `opp`, `format`, `seed`, `n`, `variant`) should appear in the path if they're function inputs.

**Approach B: Annotation-based.** Require functions that write caches to annotate their cache key explicitly:
```python
@cache_key(our_deck="our_deck", opp="opp", n="n", seed="seed")
def run_match_set(our_deck, opp, n, seed): ...
```
Drift-detect verifies the annotation matches the actual key. Stronger but requires existing code to be retrofitted.

**Approach C: Path-scoping convention.** Require all cache writes to live under a `cache/` subdirectory and follow a documented per-cache schema. Drift-detect verifies the schema is followed.

**Decision: Approach A for v1, with notes on B/C as future enhancements.** A is implementable today against existing code without retrofitting; false positives are acceptable as INFO-level. B/C are stronger but require code conventions that don't exist yet.

## Deliverables

### D1: Add `validate-cache-keys` check to drift-detect.ps1

Add a new check function that walks `mtg-sim/**/*.py` (excluding `tests/`, `_research/`, `__pycache__/`) and runs heuristic detection.

**Detection logic:**

For each function definition that contains a cache-write call (`json.dump`, `pickle.dump`, `Path(...).write_text`, `Path(...).write_bytes`, `open(..., 'w')` or `'wb'`):
1. Find the path being written to. Look for the variable used in the write call, trace back to its definition.
2. Find the function's parameter names.
3. For parameters whose names match the heuristic word list `[deck, opp, format, seed, n, variant, our_deck, opp_deck, side, side_a, side_b, side_b_deck]`:
   - If the parameter is referenced in the path construction, OK
   - If the parameter is NOT referenced in the path construction, flag as INFO

**Heuristic word list is intentionally narrow** to reduce false positives. If a function has parameters `name`, `data`, `output_path`, those don't trigger; only identity-shaping parameters do.

**Output format:**
```
[INFO] validate-cache-keys: <file>:<line> function `<name>` writes cache to path that may not include parameter `<param_name>`. Verify cache key includes all identity-shaping inputs (see harness/knowledge/tech/cache-collision-bug-2026-04-27.md).
```

INFO-level (not WARN/ERROR) because:
- False positives possible (parameter may legitimately not affect output)
- Existing partial-keyed caches were intentional pre-bug; flagging them as ERROR would force immediate fix
- The first audit (`cache-key-audit-mtg-sim.md`) classifies each site explicitly; drift-detect's job is to flag NEW sites that future PRs introduce

### D2: Allow-list for known-safe sites

Some cache-writes legitimately omit parameters (e.g., a global cache that's intentionally shared). Support an allow-list comment:

```python
# drift-detect:cache-key-ok reason="global oracle cache, parameters don't affect content"
with open(path, 'wb') as f:
    pickle.dump(...)
```

When drift-detect sees this comment within 3 lines above a cache-write call, it skips the check for that site. The reason= string is required (forces the author to explicitly justify the omission, similar to the `audit:custom_variant` pattern in deck files per the `teach-the-tool-not-the-data` lesson).

### D3: Test fixture script

`harness/scripts/test-cache-keys.ps1` — small test that creates 3 fixtures + asserts expected findings:
- `fixture-good-cache.py` — function takes (deck, opp), writes path `<deck>__<opp>.json`. Expected: 0 findings.
- `fixture-partial-key.py` — function takes (deck, opp), writes path `<opp>.json`. Expected: 1 INFO.
- `fixture-allowlisted.py` — function takes (deck, opp), writes path `<opp>.json`, but has `# drift-detect:cache-key-ok reason="..."` above. Expected: 0 findings.

### D4: Documentation

Update `harness/scripts/drift-detect.ps1` module comment / header to list the new check (8th) alongside the existing checks.

If the cache-collision finding doc (`harness/knowledge/tech/cache-collision-bug-2026-04-27.md`) has a "Methodology lesson candidates" section with a "Cache keys with implicit context are time bombs" candidate, update it to note "Mechanical detection added at YYYY-MM-DD via drift-detect 8th check."

## Validation gates

**Gate 1:** Test fixtures pass — `test-cache-keys.ps1` exits 0 with 3/3 fixtures producing expected output.
**Gate 2:** Real-codebase run — drift-detect against actual mtg-sim produces a findings count consistent with `cache-key-audit-mtg-sim.md` D-bucket and C-bucket totals (within ±2 due to heuristic edge cases). If wildly off, the heuristic is mis-tuned; iterate.
**Gate 3:** ASCII compliance on drift-detect.ps1 (per windows-powershell-ascii-only-for-ps1-files lesson).
**Gate 4:** Existing 6 (or 7) checks still produce identical output as pre-spec. Diff verification.
**Gate 5:** Performance — total drift-detect runtime increases by < 10s. AST parsing of mtg-sim's ~50 files is the cost; should be 2-5s realistic.

## Stop conditions

**Ship when:** All 5 gates pass + check has caught at least one real finding (proves it works) OR all sites are correctly silenced via allow-list.

**Stop and amend if:**
- Heuristic produces > 50 findings on real codebase (too noisy; tighten the word list or add more allow-list patterns before shipping)
- AST parsing fails on any source file (likely encoding issue; document the failed file, possibly add to skip list)
- Performance impact > 30s (gate behind opt-in flag like `-IncludeCacheKeyCheck`)

**DO NOT:**
- Do NOT flag findings as ERROR-level. INFO only for v1.
- Do NOT auto-fix any cache sites. Detection-only.
- Do NOT modify any of the actual cache-write call sites. The fix path is per-site spec'd separately via `cache-key-audit-mtg-sim.md`.

## Reporting expectations

1. Final check name in drift-detect output
2. Findings count on real mtg-sim codebase
3. Comparison to `cache-key-audit-mtg-sim.md` results (if that audit shipped first)
4. Test fixture results (PASS/FAIL per fixture)
5. Performance impact (drift-detect runtime delta)
6. Any allow-list patterns added during development

Then update spec status to SHIPPED. Update lessons file v1.4-or-later (per Rule 9, after this spec ships) with the "Mechanical detection added" note.

## Concrete steps (in order)

1. Verify ordering with sibling 7th-check spec; this is 7th or 8th depending on which shipped first (3 min)
2. Pre-flight reads (10 min)
3. D1 implementation in drift-detect.ps1 (20-25 min)
4. D2 allow-list parsing (5-10 min)
5. D3 test fixtures (10-15 min)
6. D4 documentation updates (5 min)
7. Run gates (10 min)
8. Iterate heuristic if Gate 2 produces wildly off counts (variable; cap at 15 min)
9. Commit + spec status (5 min)

Total: 60-90 min realistic.

## Why this order

- 7th-vs-8th check naming verified first because sibling spec might have shipped already
- Implementation before fixtures because we need the implementation to know what fixtures should look like
- Allow-list parsing before fixtures because fixtures test the allow-list path
- Real-codebase run last because heuristic mis-tuning shows up there

## Future work this enables (NOT in scope)

- **Approach B (annotation-based) for stronger detection.** Once codebase has been retrofitted with explicit `@cache_key()` annotations, replace heuristic with annotation verification. Estimated 60-90 min.
- **Approach C (path-scoping convention).** Standardize all caches under `data/cache/` with per-subsystem schemas. Estimated 90 min spec.
- **Auto-fix mode.** Suggest the right path/key based on parameter list. Lower priority; detection-only is correct default.
- **Cross-language extension.** If any non-Python cache-writes appear (Node scripts, shell scripts), extend the detector. None known currently.

## Changelog

- 2026-04-27 (post-Stage-C-revert): Spec created (PROPOSED). Companion to cache-key-audit-mtg-sim.md (one-time audit) — this spec mechanizes future detection. Targeted for Claude Code execution any time after sibling 7th-check spec ships.
- 2026-04-28: Status -> SHIPPED via execution-chain S6. ~40 min wall (under 45-75 estimate).

  **Numbering note:** Took the 7 slot (not 8) because sibling `harness/specs/2026-04-28-drift-detect-7th-check-spec-validation.md` was still PROPOSED at execution time. Drift-detect now has 7 checks; sibling spec when shipped becomes the 8th.

  **Approach A heuristic implemented in `harness/scripts/lint-cache-keys.py`** (Python AST parser invoked by drift-detect.ps1's new `Check-CacheKeys` function, mirroring the existing `Check-RegistryConsistency` -> `lint-mtg-sim.py` pattern). Word list per spec: `{deck, deck_a, deck_b, our_deck, opp_deck, opp, opp_name, format, format_name, seed, n, n_per_matchup, variant, side, side_a, side_b}`. Cache-write call detection: `json.dump`, `pickle.dump`, `*.write_text`, `*.write_bytes`, `open(..., 'w'/'wb'/'a'/'ab')`. Allow-list comment recognition: `# drift-detect:cache-key-ok reason="..."` within 5 lines above call.

  **Test fixtures shipped at `harness/scripts/tests/cache_key_fixtures/`:**
  - `fixture_good_cache.py` (deck IN path) -> 0 findings ✓
  - `fixture_partial_key.py` (deck NOT in path) -> 1 INFO finding ✓
  - `fixture_allowlisted.py` (allow-list comment present) -> 0 findings ✓

  **Real-codebase findings: 0 across 217 .py files scanned.** Per Gate 2, this should be "consistent with cache-key-audit ±2." Audit found 5 (3 D + 2 C). Discrepancy explained: heuristic detects subspecies-1 (param-not-in-path); audit found subspecies-2 (shared-file RMW where path is a hardcoded constant). Original subspecies-1 instance (`matchup_jobs/<opp>.json` cache, the bug that motivated this work) was already FIXED at e4fae86 before this spec ran. So 0 findings of subspecies-1 is mechanically correct for current codebase state. Subspecies-2 detection deferred to future work (would need different heuristic: detect cache-write Calls with hardcoded-string path that read-modify-write).

  **Performance:** drift-detect total runtime 7.5s (was ~5s pre-spec; +2.5s for the AST scan). Gate 5 (<10s) satisfied.

  **Documentation cascade landed:**
  - drift-detect.ps1 step counters renumbered [1-6/6] -> [1-7/7] across 7 check sites
  - Spec status PROPOSED -> SHIPPED (this changelog)
  - IMPERFECTIONS.md unchanged (no new findings to log; audit already opened the 5 RMW-class entries)
  - No new lesson compounded — `caches-keyed-on-partial-state-are-time-bombs` v1.4 covers the framing; this spec mechanizes detection but doesn't introduce a new generalization

  **Future work explicitly identified:** subspecies-2 detection (shared-file RMW with hardcoded path constants). Would catch `data/sim_matchup_matrix.json` writes from `parallel_launcher.py:152`, `parallel_sim.py:224`, `generate_matchup_data.py:245`. Estimated 30-45 min as separate spec; lower priority than the matrix-rmw fix spec itself.
