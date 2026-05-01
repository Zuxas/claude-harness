# Spec: Past-validation-numbers audit

**Status:** SHIPPED 2026-04-28 (documentation-only path; no commit, harness not git-tracked)
**Created:** 2026-04-27 by claude.ai
**Target executor:** Claude Code
**Estimated effort:** 30-60 minutes
**Risk level:** LOW (read-only re-validation; no code change; updates documentation only)
**Dependencies:**
- `harness/specs/2026-04-28-parallel-launcher-cache-collision-fix.md` MUST be SHIPPED first
- `harness/specs/2026-04-28-cache-collision-finding-doc-tightening.md` SHOULD be shipped first (narrows scope)
- Cache must be invalidated (deleted) per cache-fix spec D2
**Blocks:** phase-3.5-stage-c-re-execution (currently BLOCKED on this audit)

## Summary

After the cache-collision-fix lands, every variant gauntlet number cited in past Phase 3.5 specs is suspect. This spec re-runs Stage A and Stage B variant gauntlets against the fixed pipeline, compares to the documented numbers, and updates documentation cascade if any numbers shifted. Output is a trustworthy baseline before Stage C re-executes.

## Pre-flight reads (REQUIRED)

1. `harness/knowledge/tech/cache-collision-bug-2026-04-27.md` (root cause + classification of which past sessions are suspect)
2. `harness/specs/2026-04-28-parallel-launcher-cache-collision-fix.md` (verify this is SHIPPED before starting; if not, STOP)
3. `harness/specs/2026-04-27-phase-3.5-stage-a-block-eligibility.md` (the cited Stage A numbers)
4. `harness/specs/2026-04-27-phase-3.5-stage-b-combat-modifiers.md` (the cited Stage B numbers)
5. `harness/RESOLVED.md` (entries for both stages)
6. `mtg-sim/ARCHITECTURE.md` (any pinned headlines from those stages)
7. `harness/knowledge/tech/spec-authoring-lessons.md` v1.3 (Rule 1, Rule 5)

## Background

Per the cache-collision finding doc, variant gauntlet numbers cited in Stages A and B may be cache-polluted. Specifically suspect:
- Stage A canonical 65.8% / variant 77.8% / edge +12.0pp
- Stage B canonical 65.3% / variant 78.2% / edge +12.9pp

Tonight's diagnostic showed variant vs Izzet Prowess at 93.8% via direct call but 48.5% via gauntlet — a 45pp pollution magnitude on a single matchup. Aggregate-level pollution of 5-10pp is plausible across 14-deck gauntlets.

If the past-validation re-runs land within ±2pp of cited numbers, the cited numbers are accepted as-is with a documentation note. If they land outside ±2pp, a documentation cascade fires.

## Deliverables

### D1: Re-run Stage A variant gauntlet

```bash
cd "E:/vscode ai project/mtg-sim"
python parallel_launcher.py --deck "Boros Energy Variant Jermey" --format modern --n 1000 --seed 42
```

Capture: aggregate field-weighted win rate, per-matchup table.

### D2: Re-run Stage A canonical gauntlet (only if Stage A finding-doc-tightening flagged it as mixed-run)

If the finding-doc-tightening spec classified Stage A's session as canonical-only, the canonical 65.8% number is clean by construction and doesn't need re-validation. If classified as mixed-run or undetermined, re-run:

```bash
python parallel_launcher.py --deck "Boros Energy" --format modern --n 1000 --seed 42
```

### D3: Re-run Stage B variant + canonical (same logic as D1+D2)

### D4: Comparison table

For each re-run, produce:

| Stage | Side | Documented | Re-validated | Delta | Status |
|---|---|---|---|---|---|
| A | canonical | 65.8% | X.X% | +/- Ypp | OK / DRIFT |
| A | variant | 77.8% | X.X% | +/- Ypp | OK / DRIFT |
| A | edge | +12.0pp | +/-Z.Zpp | +/- Wpp | OK / DRIFT |
| B | canonical | 65.3% | X.X% | +/- Ypp | OK / DRIFT |
| B | variant | 78.2% | X.X% | +/- Ypp | OK / DRIFT |
| B | edge | +12.9pp | +/-Z.Zpp | +/- Wpp | OK / DRIFT |

**Drift threshold: ±2pp.** Anything within is OK; anything outside triggers documentation cascade.

### D5: Documentation cascade (only if drift > 2pp)

For each DRIFT row:
1. **Update `mtg-sim/ARCHITECTURE.md`** gauntlet entry with corrected number + footnote referencing this spec
2. **Update `harness/specs/<stage>.md`** with a Mid-execution Amendment (style: "AN: Re-validated post-cache-fix at YYYY-MM-DD; original X%, corrected Y%, delta Z pp.")
3. **Update `harness/RESOLVED.md`** stage entry with corrected number
4. **Update `harness/knowledge/_index.md`** if either stage's entry mentions specific numbers

Document the cascade as a single commit per stage so the diff shows the full propagation.

### D6: If NO drift > 2pp

Document the audit completion in:
1. `harness/knowledge/tech/cache-collision-bug-2026-04-27.md` (add a "Re-validation results" section listing the audit dates, deltas, and conclusion)
2. The Stage A and B specs (single line: "Re-validated post-cache-fix at YYYY-MM-DD: numbers hold within ±2pp tolerance.")
3. The IMPERFECTIONS entry moves to RESOLVED.md

## Validation gates

**Gate 1:** All re-runs completed and recorded.
**Gate 2:** Comparison table populated with measured numbers, not estimates.
**Gate 3:** Documentation cascade (D5 or D6) executed and committed.
**Gate 4:** `phase-3.5-stage-c-re-execution` IMPERFECTIONS entry status flips from BLOCKED to OPEN (now executable).
**Gate 5:** Drift-detect runs clean post-cascade (no stale-doc warnings on the updated files).

## Stop conditions

**Ship when:** All 5 gates pass.

**Stop and amend if:**
- Re-validation reveals drift > 5pp on any number — that's not just cache-pollution magnitude, it implies an additional bug class. Document as new finding before continuing.
- Cache invalidation didn't fully take (re-run shows same suspect number as documented) — investigate whether cache-fix spec actually shipped correctly.
- A re-run hits a different bug entirely (e.g., new runtime error from un-related drift) — surface separately, do not bundle.

**DO NOT:**
- Do NOT re-execute Stage C as part of this spec. That's the next blocked spec.
- Do NOT touch any engine code, APL code, deck files. This is read-only re-validation + doc updates.
- Do NOT compound v1.4 lessons (Rule 9; lessons compound after Stage C re-execution validates them).
- Do NOT skip D2/D3 canonical re-runs if finding-doc-tightening classified them as suspect.

## Reporting expectations

1. Comparison table with all measured numbers
2. Total drift detected (number of rows outside ±2pp)
3. Files modified in the documentation cascade
4. Confirmation that phase-3.5-stage-c-re-execution is now unblocked
5. Any deviations or surprises

Then update spec status to SHIPPED, move to RESOLVED.md.

## Concrete steps (in order)

1. Verify cache-fix is SHIPPED + cache invalidated (3 min)
2. Pre-flight reads (10 min)
3. D1: Stage A variant re-run (~10 min wall time including launcher overhead)
4. D2: Stage A canonical re-run if needed (~10 min)
5. D3: Stage B re-runs (~10-20 min)
6. D4: Build comparison table (5 min)
7. D5 or D6: Documentation cascade (10-20 min depending on drift)
8. Run gates (5 min)
9. Update IMPERFECTIONS entries + spec status (3 min)

Total: 50-80 min realistic.

## Why this order

- Cache-fix shipped before re-runs because re-runs against polluted pipeline reproduce the bug, not the fix
- D1 and D3 (variant runs) before D2 (canonical) because variant is the higher-suspicion side
- Comparison table before cascade because cascade can't fire without measured deltas
- Cascade as single-commit-per-stage so diff is reviewable

## Changelog

- 2026-04-27 (post-Stage-C-revert): Spec created (PROPOSED, BLOCKED). Targeted for Claude Code execution after cache-fix ships.
- 2026-04-28: Scope narrowed by sibling spec cache-collision-finding-doc-tightening (recovery path discovered: parallel_results JSON files preserve clean per-deck data). D1/D2/D3 gauntlet re-runs SKIPPED via JSON recovery; D4 comparison table populated from recovery (0.0pp drift on all rows); D6 documentation-only cascade executed. Bonus post-cache-fix re-run from spec 2 Gate 2 confirmed +0.3-0.7pp engine-evolution drift only, well within ±2pp tolerance. Files updated: Stage A spec (commit msg backfill + changelog), Stage B spec (commit msg backfill + changelog), cache-collision finding doc (Re-validation results section), IMPERFECTIONS.md (this entry RESOLVED + Stage C re-execution UNBLOCKED), RESOLVED.md (full audit entry). Status -> SHIPPED.
