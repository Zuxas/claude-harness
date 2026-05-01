# Spec: Drift-detect ARCH-staleness false-positive on non-canonical runs

**Status:** SHIPPED
**Created:** 2026-04-28 by claude.ai (for tomorrow execution)
**Target executor:** Claude Code
**Estimated effort:** 15-30 minutes
**Risk level:** LOW (additive PS1 logic; falls back to current behavior on any error reading JSON)
**Dependencies:** None
**Resolves:** 1 OPEN imperfection (`drift-detect-arch-staleness-false-positive-on-non-canonical-runs`)

## Goal

Stop drift-detect's `Check-StaleArchitecture` from firing a false-positive WARN every time a sub-canonical (N=1k variant or experimental) gauntlet run lands. Currently the check naively compares `ARCHITECTURE.md` mtime against the latest `parallel_results_*.json` mtime; it doesn't distinguish baseline-shifting canonical runs (N=100k, deliberate, rare) from throwaway experimental runs (N=1k, frequent). The persistent WARN risks lint blindness — future readers will tune out drift-detect output once they're used to ignoring this one.

After this ships, drift-detect WARNs on stale ARCH only when a genuinely-baseline-shifting canonical run has landed and ARCH hasn't been updated to reflect it. Same `teach-the-tool-not-the-data` v1.3 pattern as the stub_decks fuzzy-fallback fix (S1.5).

## Pre-flight reads (REQUIRED)

1. `harness/IMPERFECTIONS.md` — entry `drift-detect-arch-staleness-false-positive-on-non-canonical-runs`
2. `harness/scripts/drift-detect.ps1` — current `Check-StaleArchitecture` function
3. Sample `data/parallel_results_*.json` files to confirm `n_per_matchup` field exists and naming conventions
4. `harness/knowledge/tech/spec-authoring-lessons.md` v1.3 lesson `teach-the-tool-not-the-data` (this is a re-application)

## Scope

### In scope
- Modify `Check-StaleArchitecture` in `drift-detect.ps1` to read `n_per_matchup` (or equivalent) from candidate JSON files
- Threshold: only consider runs with N >= 10000 as baseline-shifting candidates (sub-threshold runs are experimental)
- Fallback: if JSON is unparseable or field missing, use current mtime-only behavior (don't break on edge cases)
- Test fixture in `harness/scripts/tests/arch_staleness_fixtures/` with one N=1k JSON (should NOT trigger WARN) and one N=100k JSON (SHOULD trigger WARN if ARCH older)

### Explicitly out of scope
- Upstream `parallel_launcher.py` change to add `canonical_*` vs `experimental_*` filename prefixes — larger change with regression surface; rejected per audit unless this spec proves insufficient
- Generalizing to other drift-detect checks — only `Check-StaleArchitecture` exhibits this false-positive pattern

## Steps

### T.0 — Verify field name + sample JSONs (~3 min)

```powershell
cd "E:\vscode ai project\mtg-sim"
$samples = Get-ChildItem data\parallel_results_*.json | Select-Object -First 3
foreach ($f in $samples) {
    $obj = Get-Content $f | ConvertFrom-Json
    Write-Host "$($f.Name): n_per_matchup = $($obj.n_per_matchup)"
}
```

Confirm field name (`n_per_matchup` per audit; verify on disk). Note sample N values to calibrate threshold.

### T.1 — Patch `Check-StaleArchitecture` (~10 min)

Replace mtime-only comparison with N-threshold filter. Pseudo-code:

```powershell
function Check-StaleArchitecture {
    Write-Color "[3/7] Stale ARCHITECTURE.md detection..." "Cyan"
    # ... existing setup ...

    $threshold = 10000  # N below this is experimental, not baseline-shifting
    $candidates = Get-ChildItem "$mtgSimRoot\data\parallel_results_*.json" -ErrorAction SilentlyContinue
    $baselineCandidates = @()
    foreach ($f in $candidates) {
        try {
            $obj = Get-Content $f.FullName -Raw | ConvertFrom-Json
            $n = $obj.n_per_matchup
            if ($n -ge $threshold) {
                $baselineCandidates += $f
            }
        } catch {
            # Unparseable; fall through to mtime-only on this file as fallback
            $baselineCandidates += $f
        }
    }

    if ($baselineCandidates.Count -eq 0) {
        Write-Color "       OK -- no canonical (N>=$threshold) runs newer than ARCH" "Green"
        return
    }

    $latest = $baselineCandidates | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    # ... existing comparison logic against ARCH mtime ...
}
```

Write the actual patch reading `Check-StaleArchitecture`'s current shape. Preserve all existing log-message formatting.

### T.2 — Build test fixtures (~5 min)

```
harness/scripts/tests/arch_staleness_fixtures/
  fixture_n1k.json      # {"n_per_matchup": 1000, ...}
  fixture_n100k.json    # {"n_per_matchup": 100000, ...}
  fixture_no_n_field.json  # {"results": [...]} (no n_per_matchup)
```

These are minimal stubs — just enough to validate the threshold logic.

### T.3 — Test against current state (~5 min)

```bash
cd "E:/vscode ai project"
powershell -ExecutionPolicy Bypass -File harness/scripts/drift-detect.ps1
```

Expected: stale-architecture WARN should disappear (current state has only N=1k JSONs newer than ARCH; the latest N=100k is the 2026-04-27 65.8% headline run, which is older than the post-tagger-fix ARCH update).

### T.4 — Commit + update IMPERFECTIONS (~5 min)

## Validation gates

| Gate | Acceptance | Stop trigger |
|---|---|---|
| 1 — fixtures parse | `Check-StaleArchitecture` reads N field from each fixture without error | parse error |
| 2 — false positive cleared | Drift-detect on current state produces 0 ERRORS, 0 WARNS (was 1 cosmetic WARN) | WARN persists |
| 3 — threshold respected | Synthetic test: drop a fake `parallel_results_FAKE.json` with `n_per_matchup: 100000` newer than ARCH; drift-detect MUST WARN | WARN doesn't fire when it should |
| 4 — fallback robust | Fixture `fixture_no_n_field.json` doesn't crash drift-detect | crash or unhandled exception |
| 5 — performance unchanged | drift-detect total runtime within ±1s of pre-spec (currently ~7.5s) | >1s regression |

## Stop conditions

- **Field name is not `n_per_matchup`:** STOP, find actual name from sample JSON, update spec, proceed.
- **Some real canonical runs lack the field:** STOP. Either widen detection (threshold by `kill_turns` array length as fallback) or document the limitation.
- **Synthetic Gate 3 test doesn't trigger WARN even after threshold fix:** STOP. The mtime comparison is also broken; debug separately.

## Reporting expectations

1. Field name confirmed (T.0 output)
2. Threshold chosen + rationale
3. Drift-detect output before vs after (Gate 2)
4. IMPERFECTIONS → RESOLVED entry

## Future work this enables (NOT in scope)

- Same teach-the-tool pattern could apply to any drift-detect check that uses naive mtime comparison; revisit if another such WARN ever causes lint blindness
- If `parallel_launcher.py` ever gains explicit canonical/experimental tagging in the JSON output, this check could become more semantic (e.g., `is_canonical: true` field)

## Changelog

- 2026-04-28: Created (PROPOSED) by claude.ai for tomorrow execution. Quick-win fix for the cosmetic WARN that's been firing all day.
