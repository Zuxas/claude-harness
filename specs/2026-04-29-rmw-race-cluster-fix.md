# Spec: RMW-race cluster fix (atomic-write + retry loop, 3 sites)

**Status:** SHIPPED
**Created:** 2026-04-28 by claude.ai (for tomorrow execution)
**Target executor:** Claude Code
**Estimated effort:** 45-75 minutes
**Risk level:** MEDIUM — touches 3 cache-write sites that affect gauntlet pipeline integrity. Fix is well-understood (atomic-write pattern is standard), but the consumer surface is wide; regression risk on any reader that assumes mid-write file is readable.
**Dependencies:**
- `harness/specs/2026-04-28-cache-key-audit-mtg-sim.md` SHIPPED 2026-04-28 (audit produced the 3 findings this fixes)
- `harness/knowledge/tech/cache-key-audit-2026-04-28.md` (Findings 1, 4, 5)
**Resolves:** 3 OPEN imperfections (`sim-matchup-matrix-rmw-race`, `auto-apl-registry-rmw-race-latent`, `optimization-memory-rmw-race-latent`)

## Goal

Close the entire RMW-race cluster surfaced by S5 cache-key audit in one fix. All three sites use the same anti-pattern (read JSON → mutate Python dict → write JSON) without atomicity, and all three need the same fix (atomic-write via `os.replace` + retry loop on the read-mutate-write critical section). Fixing them as a cluster is ~45-75 min total; fixing individually would be ~90+ min and the fix code would be near-duplicated three times.

After this ships:
- `data/sim_matchup_matrix.json` is safe under concurrent canonical+variant gauntlet runs (current active hazard)
- `data/auto_apl_registry.json` is safe under concurrent `--format modern` + `--format standard` auto-pipeline runs (currently latent)
- `harness/agents/optimization_memory.json` is safe under any concurrent auto-pipeline invocations (currently latent)

## Pre-flight reads (REQUIRED)

1. `harness/knowledge/tech/cache-key-audit-2026-04-28.md` — Findings 1, 4, 5 with concrete site enumeration
2. `harness/IMPERFECTIONS.md` — entries `sim-matchup-matrix-rmw-race`, `auto-apl-registry-rmw-race-latent`, `optimization-memory-rmw-race-latent`
3. `harness/knowledge/tech/spec-authoring-lessons.md` Rule 9 (compounding discipline) + `parallel-entry-points-need-mirror-fix` v1.5 (this fix is exactly that pattern)
4. The 5 affected source files:
   - `mtg-sim/generate_matchup_data.py` (line ~245, sim_matchup_matrix.json write)
   - `mtg-sim/parallel_launcher.py` (line ~152, sim_matchup_matrix.json write)
   - `mtg-sim/parallel_sim.py` (line ~224, sim_matchup_matrix.json write)
   - `mtg-sim/apl/__init__.py` or sidecar (auto_apl_registry.json writer; verify exact path)
   - `harness/agents/scripts/auto_pipeline.py` (optimization_memory.json writer)

## Scope

### In scope
- Build a shared utility function `atomic_json_update(path, mutator_fn, max_retries=5)` in `mtg-sim/utils/atomic_json.py` (new file). Function: read current JSON (or `{}` if missing), call `mutator_fn(data)` to get new dict, write to temp file, `os.replace` over original. Retry on concurrent-write conflict detected via mtime comparison.
- Wire all 3 mtg-sim sites to use the utility. Identical fix pattern at each site.
- Wire the harness `auto_pipeline.py` site to use the utility (import path differs because cross-repo; either copy the utility or import from mtg-sim if mtg-sim is on sys.path; decide in T.1).
- Regression test: `mtg-sim/tests/test_atomic_json.py` (concurrent-write probe — spawn 2 threads doing simultaneous mutator updates, assert both updates land).

### Explicitly out of scope
- File-locking (`fcntl.flock` — POSIX-only, Windows-broken). Per audit finding, rejected.
- Per-deck file split (option 2 from audit). Larger architectural change; defer unless atomic-write proves insufficient.
- Conversion of `parallel_results_<timestamp>.json` writes (those are timestamp-keyed, no RMW pattern, already safe per audit's A-bucket).

## Steps

### T.0 — Verify site locations + current behavior (~5 min)

```bash
cd "E:/vscode ai project/mtg-sim"
grep -n "sim_matchup_matrix.json" --include="*.py" -r .
grep -n "auto_apl_registry.json" --include="*.py" -r .
cd "E:/vscode ai project/harness"
grep -n "optimization_memory.json" --include="*.py" -r .
```

Confirm each site is RMW (read-mutate-write), not just write. If any site is write-only-truncate (e.g., dashboard writing fresh state), it's not in scope.

### T.1 — Build shared utility (~15 min)

Create `mtg-sim/utils/atomic_json.py`:

```python
"""atomic_json.py — atomic JSON read-modify-write helpers.

Solves the RMW-race cluster surfaced by cache-key-audit-2026-04-28
(Findings 1, 4, 5). Pre-fix: concurrent writers stomp each other's
mutations. Post-fix: writers retry on conflict; final state contains
all mutations.
"""
import json
import os
import tempfile
import time
from pathlib import Path


def atomic_json_update(path, mutator_fn, max_retries=5, retry_delay=0.05):
    """Read JSON at path, apply mutator_fn(data) -> new_data, write atomically.

    Retries on concurrent-write conflict (detected via mtime comparison).
    Returns the final data after successful write.

    mutator_fn receives a dict (or {} if file missing); must return a dict.
    Errors in mutator_fn propagate; partial writes never persist.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    last_error = None
    for attempt in range(max_retries):
        try:
            mtime_before = path.stat().st_mtime if path.exists() else 0
            data = {}
            if path.exists():
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    # Mid-write read; retry
                    time.sleep(retry_delay)
                    continue
            new_data = mutator_fn(data)
            # Atomic write: temp file + os.replace
            tmp = tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=str(path.parent),
                prefix=f".{path.name}.",
                suffix=".tmp",
                delete=False,
            )
            try:
                json.dump(new_data, tmp, indent=2)
                tmp.flush()
                os.fsync(tmp.fileno())
            finally:
                tmp.close()
            # Conflict check: if mtime changed during our read+mutate, retry
            mtime_now = path.stat().st_mtime if path.exists() else 0
            if mtime_now != mtime_before and attempt < max_retries - 1:
                os.unlink(tmp.name)
                time.sleep(retry_delay * (attempt + 1))  # backoff
                continue
            os.replace(tmp.name, path)
            return new_data
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                time.sleep(retry_delay * (attempt + 1))
                continue
            raise
    raise RuntimeError(
        f"atomic_json_update failed after {max_retries} retries: {last_error}"
    )
```

### T.2 — Wire sim_matchup_matrix.json sites (~10 min)

For each of the 3 sites (`generate_matchup_data.py:245`, `parallel_launcher.py:152`, `parallel_sim.py:224`):

Replace the existing read-mutate-write block with:

```python
from utils.atomic_json import atomic_json_update

def _update_matchup_matrix(deck_slug, opp_results):
    def mutator(matrix):
        matrix[deck_slug] = opp_results
        return matrix
    atomic_json_update("data/sim_matchup_matrix.json", mutator)
```

Pre-existing code shape varies per site. Refactor per site to call the helper; the per-site mutator captures the local update logic.

### T.3 — Wire auto_apl_registry.json site (~5 min)

Locate the writer (probably in S4's auto-pipeline-output-flow work, possibly `apl/__init__.py` or a sidecar). Same wire-up pattern as T.2.

### T.4 — Wire optimization_memory.json site (~5 min)

`harness/agents/scripts/auto_pipeline.py` writer. Cross-repo: simplest path is to inline the utility (copy `atomic_json_update` into a small `harness/agents/scripts/_atomic_json.py` module) since the harness shouldn't import from mtg-sim. Decision in T.1: copy vs import. Recommend **copy** — small function, decouples harness from mtg-sim layout changes.

### T.5 — Regression test (~10 min)

`mtg-sim/tests/test_atomic_json.py`:

```python
"""test_atomic_json.py — regression test for atomic_json_update.

Pre-fix (RMW without atomicity), two concurrent writers each updating
a different key would lose one update. Post-fix, both updates land.
"""
import json
import threading
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.atomic_json import atomic_json_update


def test_concurrent_writers_no_loss(tmp_path):
    target = tmp_path / "shared.json"
    target.write_text("{}")

    def writer(key, value):
        atomic_json_update(target, lambda d: {**d, key: value})

    threads = [
        threading.Thread(target=writer, args=(f"key_{i}", i))
        for i in range(10)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    final = json.loads(target.read_text())
    # All 10 writes should have landed
    assert len(final) == 10, f"Expected 10 keys, got {len(final)}: {sorted(final.keys())}"
    for i in range(10):
        assert final[f"key_{i}"] == i


def test_mutator_can_read_existing_state(tmp_path):
    target = tmp_path / "shared.json"
    atomic_json_update(target, lambda d: {**d, "first": 1})
    atomic_json_update(target, lambda d: {**d, "second": d.get("first", 0) + 1})
    final = json.loads(target.read_text())
    assert final == {"first": 1, "second": 2}


def test_missing_file_treated_as_empty(tmp_path):
    target = tmp_path / "does_not_exist.json"
    atomic_json_update(target, lambda d: {**d, "k": "v"})
    final = json.loads(target.read_text())
    assert final == {"k": "v"}


if __name__ == "__main__":
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        tmp_path = Path(td)
        test_concurrent_writers_no_loss(tmp_path)
        test_mutator_can_read_existing_state(tmp_path)
        test_missing_file_treated_as_empty(tmp_path)
        print("ALL 3 TESTS PASS")
```

### T.6 — Validation gates + commit (~10 min)

Run all gates. If pass, commit. If fail, debug per stop conditions.

## Validation gates

| Gate | Acceptance | Stop trigger |
|---|---|---|
| 1 — utility tests pass | `python tests/test_atomic_json.py` → ALL 3 TESTS PASS | any test fails |
| 2 — single-process gauntlet unchanged | `parallel_launcher.py --deck "Boros Energy" --format modern --n 1000 --seed 42` → canonical 64.5% (matches bit-stable baseline within 0.1pp) | gauntlet number drifts >0.5pp |
| 3 — concurrent gauntlet test | Run canonical + variant gauntlets in parallel (background processes); after both complete, `sim_matchup_matrix.json` contains both decks' rows | matrix missing either deck's row |
| 4 — auto-pipeline still works | `python harness/agents/scripts/auto_pipeline.py --format modern --use-gemma` completes without crash; `optimization_memory.json` updates correctly | crash or no update |
| 5 — drift-detect clean | Drift-detect exits 0 errors, 0 warnings, 0 findings | new errors/warnings introduced |
| 6 — existing tests still pass | `python tests/test_determinism.py && python tests/test_menace_combat.py && python tests/test_protection_keywords.py` → all pass | any regression |

## Stop conditions

- **Mutator function semantics ambiguous at any site:** STOP. Document the ambiguity in a comment, surface the question. Don't guess at intent.
- **Atomic-write breaks Windows file semantics:** STOP. `os.replace` is supposed to be atomic on Windows for same-volume moves; if it isn't on this system, fall back to retry-on-conflict-only without rename. Surface for review.
- **Concurrent gauntlet test (Gate 3) shows missing rows:** STOP. The retry loop isn't catching all conflicts. Increase max_retries or add explicit lock-file pattern.
- **Any RMW site is actually NOT RMW (e.g., write-only):** STOP. Don't refactor; remove from spec scope, document why in changelog.

## Reporting expectations

1. Sites confirmed RMW vs not (T.0 output)
2. Utility test results (Gate 1)
3. Single-process gauntlet number (Gate 2)
4. Concurrent gauntlet test outcome (Gate 3, the headline)
5. Number of `os.replace` retries observed in Gate 3 (signals contention level)
6. Commit hash + IMPERFECTIONS → RESOLVED for all 3 entries

## Future work this enables (NOT in scope)

- Per-deck file split if atomic-write proves insufficient under heavier concurrency
- Drift-detect heuristic for "RMW pattern not using atomic_json_update" — would be a 9th check candidate

## Changelog

- 2026-04-28: Created (PROPOSED) by claude.ai for tomorrow execution. Bundles 3 IMPERFECTIONS into one fix spec per audit recommendation. Atomic-write + retry loop pattern recommended (option 3) over file-locking (option 1, Windows-broken) and per-deck split (option 2, scope creep).
