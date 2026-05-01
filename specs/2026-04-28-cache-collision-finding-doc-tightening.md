# Spec: Cache-collision finding doc tightening pass

**Status:** SHIPPED 2026-04-28
**Created:** 2026-04-27 by claude.ai
**Target executor:** Claude Code
**Estimated effort:** 5-15 minutes
**Risk level:** Trivial (documentation-only; harness/knowledge/tech edit)
**Dependencies:** None
**Blocks:** Sharpens past-validation-numbers-audit (which uses this doc as its source of truth for which past sessions are suspect)

## Summary

The finding doc `harness/knowledge/tech/cache-collision-bug-2026-04-27.md` currently flags Stage A and Stage B variant numbers as "suspect" but says "if Stage A session ran both decks; check timestamps on Stage A artifacts" — the timestamp check hasn't actually been done. This spec does that audit and tightens the doc to say definitively which past sessions were mixed-run (cache-vulnerable) vs canonical-only (cache-safe).

The output is a sharper finding doc that makes tomorrow's past-validation-numbers-audit faster and more focused — it can run only against confirmed-suspect sessions instead of conservatively re-validating everything.

## Pre-flight reads (REQUIRED)

1. `harness/knowledge/tech/cache-collision-bug-2026-04-27.md` (the doc being tightened)
2. `harness/knowledge/tech/spec-authoring-lessons.md` v1.3 (Rule 1)

## Steps

1. **Identify candidate sessions.** For each spec that cites variant numbers (currently: `harness/specs/2026-04-27-phase-3.5-stage-a-block-eligibility.md` and `harness/specs/2026-04-27-phase-3.5-stage-b-combat-modifiers.md`), find the commit that shipped the spec. Check the commit timestamps of any `data/parallel_results_*.json` files referenced or created near that time.
2. **Cross-reference with shell history if possible.** PowerShell history at `C:\Users\jerme\AppData\Roaming\Microsoft\Windows\PowerShell\PSReadLine\ConsoleHost_history.txt` may show when both `--deck "Boros Energy"` and `--deck "Boros Energy Variant Jermey"` invocations happened in proximity. If the commands fired within the same hour, treat that session as mixed-run (cache-vulnerable). If only canonical or only variant fired in a given session, treat as cache-safe.
3. **Check git log for `data/matchup_jobs/` invalidation events.** If at any point those files were deleted and re-created, that's a cache-reset boundary. Sessions on opposite sides of a reset can't pollute each other.
4. **Update the finding doc.** Replace the "if Stage A session ran both decks" hedging with definitive statements: "Stage A: mixed-run, both numbers suspect" or "Stage A: canonical-only, numbers clean" or "Stage A: cannot determine from available evidence, treat as suspect."
5. **Update the IMPERFECTIONS.md `past-validation-numbers-audit` entry** with the narrowed scope: "re-run only Stage X and Stage Y" instead of "re-run Stages A and B."

## Validation gates

**Gate 1:** Finding doc no longer contains conditional language like "if Stage A session ran both decks" — every past session is classified either suspect, clean, or undetermined.

**Gate 2:** IMPERFECTIONS.md `past-validation-numbers-audit` entry reflects the narrowed scope.

**Gate 3:** No code changed; this is documentation-only. Drift-detect should still exit at the same code as pre-spec.

## Stop conditions

**Stop and ship when:** All 3 gates pass.

**Stop and amend if:** The audit reveals a session where mixed-run pollution is provable but the polluted direction is also recoverable from commit-time artifacts (e.g., the `parallel_results_*.json` from that session preserves the actual numbers separately from the cache). If recoverable, document the recovery path in the doc — past-validation-numbers-audit may be partially skippable.

**Do NOT:**
- Do NOT re-run any gauntlets as part of this spec. That's the next spec.
- Do NOT update past spec changelogs with corrected numbers. That's the next spec.
- Do NOT touch any engine code, APL code, or test code.

## Reporting expectations

After completion, report back with:
1. Per-session classification table (Stage A, Stage B, others if found)
2. Updated finding doc location
3. Narrowed scope for past-validation-numbers-audit
4. Any deviations or surprises

Then update spec status to SHIPPED, move to RESOLVED.md.

## Concrete steps (in order)

1. Pre-flight reads (3 min)
2. Steps 1-3 from "Steps" section: timestamp + history audit (5-8 min)
3. Steps 4-5: doc updates (3-5 min)
4. Run gates (1 min)
5. Commit + spec status update (2 min)

Total: 15 min realistic.

## Changelog

- 2026-04-27 (post-Stage-C-revert): Spec created (PROPOSED) by claude.ai. Output sharpens past-validation-numbers-audit scope.
- 2026-04-28: SHIPPED by Claude Code. Bonus finding beyond spec scope: parallel_results_*.json files preserve clean per-deck per-matchup data for Stage A/B variants (Izzet=99.8/99.6 sim source) — past-validation-numbers-audit narrows from "re-run + compare" to "documentation-only verification via JSON recovery." Stage C tonight's variant JSON IS polluted (variant Izzet=48.5 with `g1_source: bo3`), unlike Stage A/B JSONs — open question added to finding doc for spec 2 (cache-fix) regression test design to investigate the asymmetry.
