# Spec: Drift-Detect 7th Check — Spec Reference Validation

**Status:** SHIPPED
**Created:** 2026-04-27 by claude.ai
**Target executor:** Claude Code
**Estimated effort:** 60-90 minutes
**Risk level:** Low (additive check on existing drift-detect; no engine changes; harness-only)
**Motivating lessons:** `verify-identifiers-before-spec-execution` and `prefer-version-over-help-for-preflight-probes` (both in `harness/knowledge/tech/spec-authoring-lessons.md` v1.3)

## Summary

Add a 7th check to `drift-detect.ps1` that validates the contents of `harness/specs/*.md` files BEFORE they ship. Catch fictional script paths, fictional CLI flags, and `--help` pre-flight probes at spec-write time instead of at spec-execute time.

This closes the loop on three real amendments from the past two days:
- Guide spec referenced fictional `goldfish_canonical.py` (caught at execute time, cost ~10 min)
- Guide spec referenced fictional `parallel_launcher.py --opponent` flag (caught at execute time, cost ~5 min)
- D1 Gource spec used `gource --help` as pre-flight check (blocked in non-tty PowerShell, cost ~5 min)

The pattern across all three: spec author guessed an identifier or chose the wrong probe type; reader-Claude-Code couldn't have known until execution. A static check that runs `drift-detect.ps1` at spec-write time would have caught all three in seconds.

## Pre-flight reads (REQUIRED before starting)

1. `harness/CLAUDE.md` -- session start protocol
2. `harness/state/latest-snapshot.md` -- current project state
3. `harness/knowledge/tech/spec-authoring-lessons.md` -- the two motivating lessons:
   - `verify-identifiers-before-spec-execution`
   - `prefer-version-over-help-for-preflight-probes`
4. `harness/scripts/drift-detect.ps1` -- read end-to-end, especially the existing 6 checks (load-bearing-WIP, registry, stale ARCH, stale findings, spec status drift, imperfections registry health). The 7th check follows the same structural pattern.
5. `harness/scripts/lint-mtg-sim.py` -- reference implementation of static analysis. The new check is conceptually similar but operates on .md files instead of .py files.
6. Sample 2-3 specs in `harness/specs/` to understand the actual content patterns (especially the two SHIPPED specs from 2026-04-27: Guide attack-trigger fix and Phase 3.5 Stage A).

## Background

Two lessons from 2026-04-27 both end with a "Detection rule for drift-detect (future enhancement)" note:

> **From `verify-identifiers-before-spec-execution`:**
> Add a 7th drift-detect check that scans `harness/specs/*.md` for `python <path>` patterns and verifies each path exists in the mtg-sim repo. Flag missing scripts as ERROR in newly-written specs. Stop the bug before the spec ships.

> **From `prefer-version-over-help-for-preflight-probes`:**
> Drift-detect could scan `harness/specs/*.md` for `<tool> --help` patterns inside pre-flight or pre-execution sections and flag as INFO. Low priority -- most specs don't have pre-flight CLI checks; this is a niche detection.

These are the same enhancement at different fidelities -- both describe a check that walks `harness/specs/*.md` and validates command/identifier references. This spec ships them as a unified 7th check with three sub-detections (one as ERROR, two as INFO).

## Deliverables

### Deliverable 1: Add `validate-spec-references` check to drift-detect.ps1

**File:** `harness/scripts/drift-detect.ps1`

Add a new check function `Test-SpecReferences` that walks `harness/specs/*.md` (excluding `_template.md`, `RETROACTIVE.md`, and `README.md`) and runs three sub-detections per spec.

**Important:** ASCII-only per the encoding-only-for-ps1 lesson. Verify after editing.

#### Sub-detection 1.1: Fictional script paths (ERROR)

Pattern to detect: `python <path>` or `python3 <path>` where `<path>` is a relative or absolute path ending in `.py`, found anywhere in the spec body (code blocks included, comments excluded).

For each match:
- Resolve the path: if relative, try resolving against `mtg-sim/` and `harness/` roots. If absolute (starts with `E:\`), use as-is.
- If the resolved path doesn't exist on disk, emit an ERROR finding:
  ```
  [ERROR] validate-spec-references: spec '<spec-name>' references python script '<path>' which doesn't exist
  ```
- If the path resolves to a real file, no finding.

Skip patterns:
- `python -c "..."` (inline code, no script path)
- `python -m <module>` (module-style invocation, would need import-graph traversal -- defer to future)
- `python` followed by a non-path argument (e.g., `python script_name.py` where script_name has no extension would not match)

#### Sub-detection 1.2: Fictional winget package IDs (INFO)

Pattern to detect: `winget install <PackageId>` where `<PackageId>` follows the `Publisher.Product` shape.

For each match:
- Run `winget search <PackageId>` (with a 5-second timeout) and check the output for an exact ID match in the first column.
- If no exact match found, emit an INFO finding:
  ```
  [INFO] validate-spec-references: spec '<spec-name>' references winget package '<id>' but `winget search <id>` returned no exact match. Verify ID via canonical search before executing.
  ```
- If winget itself isn't on PATH, skip this sub-detection silently with a warning logged once per drift-detect run.

This is INFO not ERROR because (a) winget search has false negatives (offline cache, package renames), and (b) the spec executor will catch a real mismatch immediately on `winget install` failure.

#### Sub-detection 1.3: `--help` in pre-flight contexts (INFO)

Pattern to detect: `<tool> --help` appearing inside a markdown section whose heading contains "pre-flight", "preflight", "pre-execution", or "verify" (case-insensitive).

For each match:
- Emit an INFO finding:
  ```
  [INFO] validate-spec-references: spec '<spec-name>' uses '<tool> --help' as pre-flight probe; --help may invoke an interactive pager in non-tty contexts. Prefer '<tool> --version' or 'Get-Command <tool>' (see prefer-version-over-help-for-preflight-probes lesson).
  ```

This is INFO not ERROR because some tools' `--help` is genuinely non-blocking.

#### Output format

Follow the existing drift-detect convention:
- Each finding is one line: `[<SEVERITY>] <check-name>: <detail>`
- Optional second line indented with `       fix: <suggestion>`
- Findings rolled into the standard summary at the end (Errors / Warnings / Total findings)

The new check is the 6th invocation in the main check sequence (currently 5/6 -> 6/7 after adding):

```
[7/7] Spec reference validation...
       OK -- N specs checked, 0 issues
```

### Deliverable 2: Test harness for the new check

**File:** `harness/scripts/test-spec-references.ps1` (new)

A small test script that creates 3 fixture spec files in a temp dir, runs the check against them, asserts the expected findings, then cleans up.

Fixtures:
- `fixture-good-spec.md` -- references real paths and real winget IDs. Expected: 0 findings.
- `fixture-fictional-script.md` -- references `python harness/scripts/nonexistent_helper.py`. Expected: 1 ERROR.
- `fixture-help-preflight.md` -- has a "Pre-flight reads" section with `gource --help`. Expected: 1 INFO.

The test script reports PASS/FAIL per fixture and exit-codes 0 (all pass) / 1 (any fail).

### Deliverable 3: Documentation update

**File:** `harness/knowledge/tech/spec-authoring-lessons.md`

Update both relevant lessons to mark the "future enhancement" notes as RESOLVED:

In `verify-identifiers-before-spec-execution`:
- Change "Prevention via tooling (future enhancement):" to "Prevention via tooling (SHIPPED 2026-04-28 at <commit>):"

In `prefer-version-over-help-for-preflight-probes`:
- Change "Tooling implication:" to "Tooling implication (SHIPPED 2026-04-28 at <commit>):"

Add v1.4 changelog entry noting the future-enhancement notes are now actual code.

## Validation gates

**Gate 1: New check passes the test fixture script.**
- `powershell -ExecutionPolicy Bypass -File harness/scripts/test-spec-references.ps1` exits 0
- All 3 fixtures produce expected findings

**Gate 2: New check runs cleanly on the real specs directory.**
- `drift-detect.ps1` exits with the same exit code as before the change OR a higher one (i.e., the new check finds real issues we should know about)
- Output includes the new `[7/7] Spec reference validation...` line
- If the new check fires real findings on existing specs, those are valid findings -- document them in the parent spec's amendments and either fix or accept as known-issues

**Gate 3: ASCII compliance on drift-detect.ps1.**
- `python -c "print(any(ord(c) > 127 for c in open(r'E:\vscode ai project\harness\scripts\drift-detect.ps1', encoding='utf-8').read()))"` returns `False`

**Gate 4: Existing 6 checks still pass.**
- The new check is purely additive; the existing 6 must produce identical output as before this change. Diff the pre/post outputs to confirm.

**Gate 5: Performance.**
- Drift-detect total runtime increases by less than 10 seconds. The new check operates on ~10 spec files; should complete in 1-2 seconds. Winget queries (sub-detection 1.2) are the slowest -- if they push runtime over budget, gate them behind a `-IncludeWingetCheck` flag and default-off.

## Stop conditions

**Stop and ship when:**
- All 5 gates pass
- New check has caught at least one real finding (proves the check works) OR has 0 findings on all real specs (proves the specs are clean)

**Stop and report (do NOT improvise) if:**
- Existing drift-detect output changes for the existing 6 checks (would indicate accidental regression)
- Gate 5 fails (performance budget) -- report and let user decide whether to gate winget checks
- Any spec is found to have multiple ERROR-level findings (might indicate a systemic issue worth investigating before shipping the check)

**Do NOT do these things:**
- Do NOT extend the check to scan `python -m <module>` patterns -- requires import-graph traversal, separate spec
- Do NOT extend to other shell commands (`node <path>`, `bash <path>`) -- single-language scope keeps the check tight
- Do NOT add auto-fix functionality -- check is detection-only; fixing is human work
- Do NOT add Gephi/visualization-related checks -- that's separate work, separate spec
- Do NOT modify the existing 6 checks -- additive only

## Reporting expectations

After completion, report back with:
1. **New check output on real specs:** how many findings, what severities, what specs
2. **Test fixture results:** PASS/FAIL per fixture
3. **Performance impact:** drift-detect runtime before vs after the change
4. **Any deviations** from this spec (amendments, gates that needed adjustment)
5. **Lesson updates:** confirm both motivating lessons updated to "SHIPPED" status

Then update this spec to status SHIPPED, add line to RESOLVED.md, summary in chat.

## Mid-execution amendments

(Document any amendments here as work proceeds. Format: `### A1: <title>` then explanation.)

## Concrete steps (in order)

1. Pre-flight reads (10 min)
2. Build Sub-detection 1.1 (script-path check) first -- highest-value, simplest implementation (15 min)
3. Build test fixtures + test-spec-references.ps1 (15 min)
4. Run the test fixtures, confirm 1.1 works correctly (5 min)
5. Build Sub-detection 1.3 (--help in pre-flight) -- pure regex, no external commands (10 min)
6. Build Sub-detection 1.2 (winget search) -- gate behind a flag if performance is bad (15 min)
7. Run all 5 validation gates (10 min)
8. Update lessons file v1.4 with SHIPPED marker (5 min)
9. Update spec status, RESOLVED.md, summary (5 min)

Total estimated wall time: 90 minutes including testing.

## Why this order

Sub-detection 1.1 is the highest-value piece (caught the Guide spec amendments, ~10 min direct cost saved). Ship it first so even if 1.2 or 1.3 hit problems, the most valuable check is in place.

Sub-detection 1.3 is pure regex with no external dependencies -- low risk, ships next.

Sub-detection 1.2 is the riskiest because it shells out to winget (timing, false negatives, requires winget on PATH). Gate it behind a flag if needed; the check still ships value without it.

## Why this is meta-recursive

This spec is itself a spec that creates a check that validates specs. That recursion is intentional -- the check operates on `harness/specs/*.md` including itself. After it ships, running drift-detect on this spec should produce 0 findings against its own body. If it produces findings, that's a real bug in the new check (false positives on legitimate spec content).

Self-validation test: after Gate 2, manually verify that running drift-detect against `harness/specs/2026-04-28-drift-detect-7th-check-spec-validation.md` (this file) produces 0 findings.

## Future work this enables (NOT in scope)

Listed for context, NOT to be built in this spec:

- **Module-style invocation check** (`python -m <module>`) -- requires Python import-graph awareness. Lower priority; most specs use file paths.
- **Cross-language extension** -- Node, Ruby, Bash, etc. Single-language scope keeps initial check tight.
- **Auto-fix mode** -- could suggest the right path/ID via fuzzy matching against the project tree. Detection-only is the right default; auto-fix adds risk.
- **Per-spec lint config** -- some specs may legitimately reference paths that don't exist yet (forward-looking specs). Frontmatter flag like `validate-references: false` could opt out. Not needed yet; revisit if false positives become a pattern.
- **CI integration** -- run drift-detect (including this check) in a pre-commit hook or GitHub Actions. The harness already has a pre-commit hook installed for mtg-sim; extending to harness-side specs is logical follow-up.

## Changelog

- 2026-04-27 ~22:30: Spec created (PROPOSED). Drafted by claude.ai during late-evening planning session. Combines the two "future enhancement" notes from spec-authoring-lessons.md v1.3 (verify-identifiers and prefer-version-over-help) into a single deliverable. Targeted for Claude Code execution whenever (no urgency; tomorrow's plan has higher-priority items first).
