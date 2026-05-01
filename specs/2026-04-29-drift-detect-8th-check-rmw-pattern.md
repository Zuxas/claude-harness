# Spec: Drift-detect 8th check — RMW-with-hardcoded-paths heuristic (subspecies-2)

**Status:** SHIPPED
**Created:** 2026-04-28 by claude.ai (for tomorrow execution)
**Target executor:** Claude Code
**Estimated effort:** 45-75 minutes
**Risk level:** LOW (additive PS1 + Python lint helper; same pattern as today's S6 7th-check)
**Dependencies:**
- `harness/specs/2026-04-28-drift-detect-8th-check-cache-key-audit.md` SHIPPED 2026-04-28 via S6 (the 7th check; this spec adds the 8th)
- `harness/specs/2026-04-29-rmw-race-cluster-fix.md` PROPOSED (the fix; this detector catches future regressions OF that fix)
**Resolves:** No OPEN imperfection (mechanizes detection of a bug class; companion to RMW-race fix spec)

## Goal

Today's S6 shipped a 7th drift-detect check that catches **subspecies-1** of the cache-collision bug class: cache writes where an identity-shaping function parameter doesn't appear in the write path (`<opp>.json` instead of `<deck>__<opp>.json`). It correctly produces 0 findings on current codebase because subspecies-1 was fixed at `e4fae86`.

S5's audit found **subspecies-2** of the same class: cache writes that read-modify-write a shared file with a hardcoded path constant, where concurrent writers stomp each other's mutations. The 7th check doesn't catch this because the path doesn't have variables to test against. Different heuristic needed.

This spec adds an 8th check that detects subspecies-2: identifies cache-write functions that (a) read JSON from a hardcoded path, (b) mutate the dict in memory, (c) write JSON back to same hardcoded path. Without atomic-write or locking, this is a race candidate.

After this ships, drift-detect will catch future regressions of the RMW-race pattern, complementing the explicit fix in `2026-04-29-rmw-race-cluster-fix.md` which removes the current instances.

## Pre-flight reads

1. `harness/specs/2026-04-28-drift-detect-8th-check-cache-key-audit.md` (SHIPPED 2026-04-28; sibling 7th check) — the established pattern for AST-based heuristic detection
2. `harness/scripts/lint-cache-keys.py` — extend OR companion-file pattern (decide in T.0)
3. `harness/knowledge/tech/cache-key-audit-2026-04-28.md` — Findings 1, 4, 5 (the 3 known subspecies-2 instances)
4. `harness/scripts/drift-detect.ps1` — `Check-CacheKeys` function (model the new check after it)

## Scope

### In scope
- Heuristic detector for the RMW-with-hardcoded-path pattern. Detects functions that:
  1. Open a file via hardcoded string path AND read JSON
  2. Within the same function, mutate the loaded dict (any assignment to a key on the loaded variable)
  3. Open the same hardcoded path AND write JSON
  4. Without using `os.replace` for atomicity
- Allow-list comment: `# drift-detect:rmw-ok reason="..."` (parallel to today's `cache-key-ok` allow-list)
- Test fixtures in `harness/scripts/tests/rmw_fixtures/`:
  - `fixture_rmw_unsafe.py` — classic RMW, expect 1 INFO finding
  - `fixture_atomic_safe.py` — uses `os.replace`, expect 0 findings
  - `fixture_allowlisted.py` — RMW with allow-list comment, expect 0 findings
  - `fixture_write_only.py` — truncate-write (no read first), expect 0 findings
- Wire into `drift-detect.ps1` as a new check function `Check-RMWPattern` step `[8/8]`. Renumber existing checks to 8/8.

### Explicitly out of scope
- Detecting RMW patterns that use file-locking primitives (we're not blessing lock-based code; atomic-write is the recommended pattern)
- Cross-process detection (only same-function-scope RMW; cross-function flow analysis is out of scope)
- Auto-fix suggestions beyond pointing to `mtg-sim/utils/atomic_json.py` (when that ships per spec #1)

## Steps

### T.0 — Decide: extend lint-cache-keys.py or create lint-rmw-pattern.py? (~5 min)

Read `harness/scripts/lint-cache-keys.py`. If the AST-walking infrastructure is reusable, add a second pass to that file. If the heuristic is structurally different enough that it'd require significant refactor, create a separate `lint-rmw-pattern.py`.

Default recommendation: **separate file**. Different heuristic, different fixture set, different finding shape. Easier to maintain as parallel sibling than as merged complex multi-pass linter.

### T.1 — Implement detector (~20 min)

`harness/scripts/lint-rmw-pattern.py`:

```python
"""lint-rmw-pattern.py -- Stage S6+: heuristic detector for RMW-race bug class.

Subspecies-2 of cache-collision class: a function reads JSON from a
hardcoded path, mutates the dict, and writes back to the same path
without atomicity. Concurrent invocations stomp each other's mutations.

Detects:
  with open("data/foo.json") as f: data = json.load(f)
  data[key] = value  # mutation
  with open("data/foo.json", "w") as f: json.dump(data, f)

Allow-list:
  # drift-detect:rmw-ok reason="single-writer guaranteed by upstream lock"
"""
# AST walk:
# 1. Find functions
# 2. For each function, find json.load + json.dump call sites
# 3. For each pair, extract path arguments (hardcoded strings only)
# 4. If both calls reference same hardcoded path AND there's mutation between them
#    AND the write site doesn't use os.replace nearby
#    AND no allow-list comment → INFO finding
```

Key heuristic refinements:
- Path matching: same string literal at both load and dump sites
- Mutation detection: any `Assign` node with subscript on the loaded variable between load and dump
- Atomicity check: `os.replace` call within same function → safe; absence → unsafe
- False-positive allowance: INFO level (consistent with 7th check)

### T.2 — Build test fixtures (~10 min)

```
harness/scripts/tests/rmw_fixtures/
  fixture_rmw_unsafe.py       # classic: load + mutate + dump (no os.replace)
  fixture_atomic_safe.py      # load + mutate + tmp dump + os.replace
  fixture_allowlisted.py      # rmw_unsafe pattern with # drift-detect:rmw-ok
  fixture_write_only.py       # only writes (no load first); not RMW
  fixture_different_paths.py  # load from "a.json", dump to "b.json"; not RMW
```

### T.3 — Wire into drift-detect.ps1 (~10 min)

Add `Check-RMWPattern` function modeled after `Check-CacheKeys`. Renumber existing checks `[1-7/7]` → `[1-8/8]` across all 7 existing check sites.

```powershell
function Check-RMWPattern {
    Write-Color "[8/8] RMW-pattern heuristic audit..." "Cyan"
    # ... call lint-rmw-pattern.py, parse JSON output, add findings ...
}
```

### T.4 — Smoke test on real codebase (~5 min)

```bash
cd "E:/vscode ai project"
python harness/scripts/lint-rmw-pattern.py --json
```

Expected before RMW-race fix ships: 3-5 findings (matching today's audit Findings 1, 4, 5).
Expected after RMW-race fix ships: 0-1 findings (depending on whether `mtg-sim/utils/atomic_json.py` is correctly recognized as the atomicity primitive).

### T.5 — Validation gates + commit (~10-15 min)

## Validation gates

| Gate | Acceptance | Stop trigger |
|---|---|---|
| 1 — fixtures pass | unsafe=1, safe=0, allowlisted=0, write_only=0, different_paths=0 | any miscount |
| 2 — real codebase findings consistent | Pre-fix-ship: 3-5 findings (matches audit). Post-fix-ship: 0 findings (fix's atomic_json recognized) | wildly different count |
| 3 — drift-detect performance | Total runtime within ±2s of pre-spec (today's was ~7.5s; expect ~9-10s after this) | >5s regression |
| 4 — drift-detect step counters consistent | All 8 checks numbered [1-8/8] across PS1 file; no duplicates or skips | counter inconsistency |
| 5 — drift-detect clean | post-spec drift-detect exits with same outcome shape (0 errors, possibly INFO findings if pre-fix) | new ERROR/WARN level findings (would be hiding-bug bug) |

## Stop conditions

- **AST infrastructure from lint-cache-keys.py is too entangled:** STOP, separate-file path is correct, write `lint-rmw-pattern.py` standalone.
- **Real codebase produces >10 findings:** STOP, the heuristic is over-eager. Tighten.
- **Real codebase produces 0 findings before RMW-race fix ships:** STOP, the heuristic is missing the known-3 sites. Debug — likely a path-matching issue.
- **Renumbering check counters breaks something:** STOP, revert the renumber, ship as 8th-of-8 with mixed numbering documented.

## Reporting expectations

1. Implementation choice (extend vs separate file) and rationale
2. Fixture pass/fail table
3. Real-codebase finding count + comparison to audit Findings 1, 4, 5
4. Performance impact on drift-detect total runtime
5. Spec status PROPOSED → SHIPPED, no IMPERFECTIONS opened (this is mechanization, not new findings)

## Coordination with RMW-race fix spec

This spec and `2026-04-29-rmw-race-cluster-fix.md` are companions:
- The fix REMOVES current instances of the RMW-race pattern
- This detector CATCHES FUTURE instances

Recommended ordering: ship the fix FIRST (closes the actual bugs), then ship this detector (catches regressions). Reverse order is also fine — detector identifies fix targets the audit already enumerated. If shipped before the fix, the detector will produce 3+ findings on first run; that's expected, not a failure.

## Future work this enables (NOT in scope)

- A 9th check candidate could detect the parallel-entry-points pattern (find sibling `*_set` functions; flag if one was modified recently and the other wasn't)

## Changelog

- 2026-04-28: Created (PROPOSED) by claude.ai for tomorrow execution. Companion to `2026-04-29-rmw-race-cluster-fix.md`. Mechanizes detection of subspecies-2 (RMW-race) to catch future regressions of the fix.
