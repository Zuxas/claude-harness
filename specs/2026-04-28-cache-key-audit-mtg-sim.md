# Spec: Cache-key audit across mtg-sim

**Status:** SHIPPED 2026-04-28 via execution-chain S5
**Created:** 2026-04-27 by claude.ai
**Target executor:** Claude Code
**Estimated effort:** 30-60 minutes
**Actual effort:** ~25 min
**Risk level:** LOW (read-only audit; outputs findings + new IMPERFECTIONS entries; no code change in scope)
**Dependencies:** None (can run before or after parallel-launcher-cache-collision-fix; pairs naturally with drift-detect-8th-check spec)
**Blocks:** Nothing directly. Surfaces the actual scope of cache-key risk so future specs can address it.

## Summary

Tonight's surfaced bug was one cache (`data/matchup_jobs/`) keyed on partial state. The methodology lesson "cache keys with implicit context are time bombs" deserves to be tested against the actual codebase, not just codified in v1.4. This spec audits all cache-write paths in mtg-sim for the same bug class.

Output: a finding doc listing every cache that's keyed on partial state, with risk classification (definitely-broken / probably-fine / depends-on-usage). Each broken or probably-broken cache becomes a new IMPERFECTIONS entry for fix prioritization.

## Pre-flight reads (REQUIRED)

1. `harness/knowledge/tech/cache-collision-bug-2026-04-27.md` — the prototype bug class
2. `harness/knowledge/tech/spec-authoring-lessons.md` v1.3
3. `harness/CLAUDE.md` Rule 1, Rule 4

## Background

The cache-collision bug is one instance of a more general pattern:
- A function takes parameters (P1, P2, ..., Pn)
- The function caches its result based on a key derived from a SUBSET of parameters (P1, P2 only, say)
- Under convention, P3..Pn are "stable enough" that they're not part of the key
- Under concurrent execution where P3..Pn vary, the cache silently returns wrong results

This audit looks for that pattern across mtg-sim's cache-write paths.

## Audit methodology

### Step 1: Enumerate cache-write call sites

Grep for cache-write patterns in mtg-sim:

```bash
cd "E:/vscode ai project/mtg-sim"
grep -rn "json.dump\|pickle.dump" --include="*.py" .
grep -rn "\.write_text\|\.write_bytes" --include="*.py" .
grep -rn "with open.*'w'" --include="*.py" .
```

For each match, note: (file, line, what's being written, where it's being written to).

### Step 2: Classify each call site

For each cache-write call site, determine:

1. **Does it write to a path that varies with input parameters?** If the path includes ALL parameters that affect the output, it's safe.
2. **If the path includes only SOME parameters, what governs whether the omitted parameters are stable?** Document the convention. If the convention can be violated (concurrency, sequential reuse with different params), it's a bug candidate.
3. **Are there callers that violate the convention?** Even if the convention exists, if any current caller violates it, the bug is active. If no caller violates it, the bug is latent.

### Step 3: Build the finding doc

For each cache-write site, classify into one of four buckets:

**A. Safe by construction.** Path includes all relevant parameters (e.g., includes a hash of all inputs, or has nested directories per parameter).

**B. Safe by convention, no violators.** Path is partial-keyed but no caller violates the convention. Document the convention so future callers can check.

**C. Latent bug.** Path is partial-keyed AND there's a plausible future caller that would violate the convention. Document as IMPERFECTIONS entry with severity rating.

**D. Active bug.** Path is partial-keyed AND a current caller violates the convention. Document as IMPERFECTIONS entry with HIGH severity; spec a fix.

### Step 4: Write finding doc

`harness/knowledge/tech/cache-key-audit-2026-04-27.md`

Include:
- Methodology used
- Per-site classification table
- Active bug list (D bucket) with proposed fixes
- Latent bug list (C bucket) with risk assessment
- Safe sites (A, B buckets) for completeness

### Step 5: Update IMPERFECTIONS.md

For each D-bucket bug: add an OPEN imperfection with severity HIGH.
For each C-bucket latent bug: add an OPEN imperfection with severity MEDIUM, status "latent — fix when convention is at risk of violation."

### Step 6: Update IMPERFECTIONS for the audit itself

Once the audit is shipped, the audit itself doesn't become an imperfection — it's complete. But the FINDINGS from the audit do.

## Specific paths to audit (high-priority candidates)

These are the directories most likely to contain partial-keyed caches based on naming:

- `data/matchup_jobs/` — KNOWN BUG (don't re-audit, just note)
- `data/parallel_results_*.json` — high suspicion (similar pattern)
- `data/results/` (if exists)
- `data/cache/` (if exists)
- `data/decks_cache/` (if exists)
- `data/oracle_cache/` (if exists, used by oracle_parser)
- Any `__pycache__` directory containing pickle files (not `.pyc` — actual data caches)
- Any `.cache/` subdirectory anywhere in the tree

## Validation gates

**Gate 1:** Every cache-write call site identified by Step 1 is classified into A/B/C/D. No "TBD" entries in the finding doc.
**Gate 2:** Finding doc landed at expected path with all sections populated.
**Gate 3:** IMPERFECTIONS.md updated with new entries for D and C buckets.
**Gate 4:** No code changed (audit is read-only). Drift-detect should still exit at the same code as pre-spec.

## Stop conditions

**Ship when:** All 4 gates pass.

**Stop and amend if:**
- The number of cache-write sites is > 30 (large audit; partial-ship after first 30 with a follow-up spec for the rest)
- An active bug (D bucket) is identified that's worse than the original cache-collision (e.g., affects production data integrity, not just gauntlet displays) — escalate, possibly re-prioritize the day's plan
- Step 1's grep produces too many false positives (test fixtures, etc.) — refine the search to data/ subtrees only and document the narrowing

**DO NOT:**
- Do NOT fix any of the bugs you find. This spec is audit-only. Each bug becomes a separate fix spec.
- Do NOT compound v1.4 lessons. Rule 9 — wait for cache-fix to ship and audit findings to validate the lesson.
- Do NOT modify production code paths to "make caches safer" speculatively. That's spec creep.

## Reporting expectations

1. Total cache-write call sites identified
2. Bucket counts (A/B/C/D)
3. Active bug list with proposed-fix-spec names
4. Latent bug list with risk assessment
5. Top 3 most-concerning findings, even if not active bugs (worth user attention)

Then update spec status to SHIPPED, move audit IMPERFECTIONS entry to RESOLVED if one exists.

## Concrete steps (in order)

1. Pre-flight reads (5 min)
2. Step 1: grep enumeration (5 min)
3. Step 2: per-site classification (15-25 min, scales with site count)
4. Step 3: build finding doc (10-15 min)
5. Step 4: write finding doc to disk
6. Step 5: update IMPERFECTIONS.md (5-10 min)
7. Run gates (3 min)
8. Commit + spec status (5 min)

Total: 45-70 min realistic.

## Why this order

- Audit before fix because we don't know how big the bug-class is. Speccing fixes individually before knowing the count is wasteful if there are 5 of them; speccing one umbrella audit first lets you decide whether to fix individually or batch.
- Post-cache-fix is fine but not required, because audit is read-only and doesn't depend on the fix being in place.

## Future work this enables (NOT in scope)

- **Per-bug fix specs** for each D-bucket finding
- **Convention-documenting comments** added to source files for B-bucket sites (so future readers know the convention)
- **Drift-detect 8th check** (separate spec) to mechanize detection of the bug class going forward

## Changelog

- 2026-04-27 (post-Stage-C-revert): Spec created (PROPOSED). Targeted for Claude Code execution as part of methodology compounding from cache-collision finding. Pairs with drift-detect-8th-check spec.
- 2026-04-28: Status -> SHIPPED via execution-chain S5. ~25 min wall (faster than 30-60 estimate because grep + classification was efficient on a 27-site corpus). Output: `harness/knowledge/tech/cache-key-audit-2026-04-28.md` (10 sections, per-site classification table, 5 findings). Bucket counts: A=17 (safe), B=6 (safe-by-convention), C=2 (latent), D=3 (active — all the same root finding: `data/sim_matchup_matrix.json` RMW race across 3 call sites). Three new IMPERFECTIONS opened: `sim-matchup-matrix-rmw-race` (active, MEDIUM severity, fix spec recommended), `auto-apl-registry-rmw-race-latent` (latent, foldable into the main fix), `optimization-memory-rmw-race-latent` (latent, lowest-impact). All 4 validation gates passed. **No new lessons compounded** — audit confirmed `caches-keyed-on-partial-state-are-time-bombs` v1.4 against the codebase (5 instances of the anti-pattern), but that's a confirming case not a new generalization. Per Rule 9, hold compounding for now; if the fix spec surfaces a new pattern (e.g., POSIX vs Windows divergence on file-locking), that becomes a new lesson candidate.
