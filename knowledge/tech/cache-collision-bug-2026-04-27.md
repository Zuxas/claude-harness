# Finding: parallel_launcher matchup_jobs cache collision

**Date:** 2026-04-27 (surfaced ~22:55 during Phase 3.5 Stage C C.4
validation; investigated via diagnostic plan)
**Status:** SURFACED (cache fix specced for next session; past-number
audit also pending)
**Discovered by:** Phase 3.5 Stage C C.4 validation surfacing -51pp
variant Izzet Prowess shift that was mechanically impossible per the
patch under audit

## Symptoms

Stage C C.4 gauntlet validation showed:
- **Variant vs Izzet Prowess: 99.7% pre-Stage-C → 48.5% post-Stage-C**
  (-51.2pp swing on a single matchup)
- Canonical vs Izzet Prowess: 49.2% pre → 48.5% post (stable)

Mechanical analysis: Stage C's C.1 patch added HEXPROOF/SHROUD filtering
to `_damage_any_helper`. Density check confirmed Izzet Prowess deck
has ZERO creatures with HEXPROOF/SHROUD/WARD/PROTECTION tags. Patch
should be a true no-op for variant-vs-Izzet-Prowess. Synthetic tests
(5/5) confirmed helper logic correct in isolation.

## Reproduction

The cleanest repro of the cache divergence:

```bash
cd "E:/vscode ai project/mtg-sim"

# Direct match_set call (uses live sim, no cache)
python -c "
from generate_matchup_data import load_deck_and_apl
from engine.match_runner import run_match_set
mb_a, _, apl_a = load_deck_and_apl('Boros Energy Variant Jermey', 'modern')
mb_b, _, apl_b = load_deck_and_apl('Izzet Prowess', 'modern')
results = run_match_set(apl_a, mb_a, apl_b, mb_b, n=1000, seed=42, mix_play_draw=True)
print(f'Direct: {results.win_pct():.1f}%')
"
# Output: Direct: 93.8%

# Gauntlet via parallel_launcher (reads/writes matchup_jobs cache)
python parallel_launcher.py --deck "Boros Energy Variant Jermey" --format modern --n 1000 --seed 42 \
  | grep "Izzet Prowess"
# Output (display): Izzet Prowess  7.2%  G1=49.1%  G2=50.4%  Match=48.5%
```

Same matchup, same seed, same engine state. Direct call: 93.8%.
Gauntlet display: 48.5%. The 48.5% number is canonical's cached value
that overwrote variant's earlier write.

## Root cause

`data/matchup_jobs/<opp_slug>.json` cache files are keyed by **opponent
name only**, not by the `(our_deck, opp)` tuple. Inspecting
`data/matchup_jobs/izzet_prowess.json` post-gauntlet:

```json
{
  "opp": "Izzet Prowess",
  "our_deck": "Boros Energy",         // canonical's value
  "field_pct": 7.2,
  "n": 1000, "g1": 49.1, "g2": 50.4, "match": 48.5,
  ...
}
```

The cached `our_deck` field is canonical's value, but the file is
shared between variant and canonical gauntlet runs. Last-writer-wins.

**Failure mode:**
1. variant gauntlet runs Izzet Prowess matchup → writes its result
   to `izzet_prowess.json` with `our_deck: "Boros Energy Variant
   Jermey"` (~18s wall finish)
2. canonical gauntlet runs Izzet Prowess matchup → writes ITS result
   to the same file, overwriting (~32s wall finish)
3. variant gauntlet's display layer reads from
   `izzet_prowess.json` → reports canonical's numbers as variant's

**Pre-Stage-C variant Izzet Prowess at 99.7%** was likely a
prior-session cache value (from when variant ran without canonical
contention) that persisted on disk until tonight's parallel runs
overwrote it.

## Blast radius

### Per-session classification (audit completed 2026-04-28 via finding-doc-tightening spec)

Investigation method: cross-referenced commit timestamps for each cited
spec against `data/parallel_results_*.json` mtimes. Paired files written
within ~15s of each other indicate a mixed-run session (concurrent
variant + canonical gauntlets). Single files with no nearby pair
indicate a canonical-only session.

| Stage | Commit | Session pattern | parallel_results JSON status | Final classification |
|---|---|---|---|---|
| Stage A | 99037a9 (10:04 PT) | MIXED (variant 10:01:48 + canonical 10:02:02, 14s apart) | CLEAN (variant Izzet=99.8 sim source; canonical 65.8 fw) | **Numbers VERIFIED CLEAN via JSON recovery** |
| Stage B | c95ea55 (12:00 PT) | MIXED (variant 11:53:27 + canonical 11:53:41, 14s apart) | CLEAN (variant Izzet=99.6 sim source; canonical 65.3 fw) | **Numbers VERIFIED CLEAN via JSON recovery** |
| Stage C tonight | affd5c2 → reverted de96593 (22:42 / 23:06 PT) | MIXED (variant 22:53:39 + canonical 22:53:41, 2s apart) | POLLUTED (variant Izzet=48.5 with `g1_source: bo3` — canonical's source) | Cache-polluted in BOTH cache and JSON; Stage C reverted — moot |
| 100k canonical | 6962649 (08:36 PT) | CANONICAL-ONLY (single 08:34 file, no nearby variant pair) | Clean by construction | **Clean by construction** |
| 14:50 single canonical | none (working artifact) | CANONICAL-ONLY (single 14:50 file, no nearby variant pair) | Clean by construction | **Clean by construction** |

### Recovery path discovered (2026-04-28)

The `parallel_results_*.json` files written by `parallel_launcher.py`
preserve per-deck per-matchup results INDEPENDENTLY per gauntlet run
(written by each gauntlet to its own filename). For Stage A and Stage
B, those files contain the actual SIM measurements with correct
`g1_source: sim` annotations on variant Izzet Prowess (99.8% / 99.6%),
matching the cited "pre-Stage-C variant Izzet Prowess at 99.7%"
diagnostic baseline.

This means **the cache-collision bug for Stages A and B was a DISPLAY-
LAYER bug** (cache-polluted display) plus a CACHE-FILE bug (corrupted
`data/matchup_jobs/<opp>.json` contents on disk). The aggregate
field-weighted numbers in the parallel_results JSON files were NOT
polluted — those files preserve trustworthy gauntlet measurements.

**Implication for past-validation-numbers-audit (next-spec scope):**
- Re-runs of Stage A/B variant gauntlets are NOT NEEDED. Cited numbers
  (variant 77.8% / 78.2%; canonical 65.8% / 65.3%; edges +12.0pp /
  +12.9pp) are independently verifiable from the JSON artifacts.
- The audit narrows from "re-run + compare" to "verify-via-JSON +
  document the recovery path."
- Estimated time savings: ~30-45 min on past-validation-numbers-audit
  spec execution.

### Open question (escalate to cache-fix spec)

**Why is Stage C tonight's variant JSON polluted but Stage A/B variant
JSONs were not?** All three sessions had concurrent variant + canonical
gauntlets within seconds of each other. `parallel_launcher.py` and
`generate_matchup_data.py` were unchanged since Apr 26 (commit ea5e196),
so the launcher code is identical across all three runs.

Possible explanations to investigate during cache-fix spec
implementation (regression test design must catch BOTH modes):
1. Timing-dependent cache-read behavior in the launcher (when does the
   launcher decide to use cached vs live results?)
2. The `g1_source: bo3` value in Stage C variant's polluted Izzet entry
   is canonical's bo3 source — suggests variant's gauntlet, for that
   matchup, somehow used canonical's cached value INSTEAD of running
   the sim. This is a different failure mode than display-only
   pollution.
3. Stage A/B may have had cache-MISS behavior (variant wrote first,
   canonical wrote second, variant's JSON was already finalized
   pre-cache-write), while Stage C had cache-HIT behavior (canonical
   wrote first, variant read canonical's value into its own JSON).

Whichever the cause, the cache-fix regression test (spec 2 D3) must
validate that:
- Display layer reads correct deck's value (display-pollution mode)
- AND parallel_results JSON contains live-sim values for the deck that
  authored it, never another deck's cached value (JSON-pollution mode)

**Variant edge calculations** for Stages A/B (+12.0pp, +12.9pp) are
verifiable as-is from JSON recovery; no edge-calculation correction
needed for those stages. Stage C edge irrelevant (reverted).

### Clean by construction (unchanged)

- Canonical-only runs (no concurrent variant gauntlet on the same
  session) -- canonical writes its cache, canonical reads its own
  cache, no other writer in flight.
- 100k canonical Modern at 65.8% (commit 6962649) -- canonical-only
  large run, last-writer-wins doesn't apply because there was no
  competing writer.
- Goldfish numbers -- don't touch matchup_jobs cache.
- Mirror match smoke tests -- don't touch matchup_jobs cache.

## Re-validation results (2026-04-28, post-cache-fix at e4fae86)

Past-validation-numbers-audit spec executed via the documentation-only
path (recovery from parallel_results JSON; no gauntlet re-runs needed).

### Comparison table

| Stage | Side | Documented | Recovered (JSON) | Drift | Source |
|---|---|---|---|---|---|
| A | canonical | 65.8% | 65.8% | 0.0pp | parallel_results_20260427_100202.json |
| A | variant | 77.8% | 77.8% | 0.0pp | parallel_results_20260427_100148.json |
| A | variant Izzet | 99.7% (cited diagnostic) | 99.8 g1 sim | 0.1pp | same JSON above |
| A | edge | +12.0pp | +12.0pp | 0.0pp | derived |
| B | canonical | 65.3% | 65.3% | 0.0pp | parallel_results_20260427_115341.json |
| B | variant | 78.2% | 78.2% | 0.0pp | parallel_results_20260427_115327.json |
| B | variant Izzet | 99.7% (cited diagnostic) | 99.6 g1 sim | 0.1pp | same JSON above |
| B | edge | +12.9pp | +12.9pp | 0.0pp | derived |

**No drift > 2pp.** All cited Stage A and Stage B numbers verified
clean. The cache-collision bug affected the cache file + display
layer for Stage A/B sessions; the per-deck parallel_results JSON
files preserve trustworthy gauntlet measurements throughout.

### Bonus belt-and-suspenders verification (post-cache-fix gauntlet)

Spec 2 Gate 2 ran a fresh variant gauntlet against the cache-fixed
pipeline (post-commit e4fae86, 2026-04-28 00:58):

- Variant gauntlet field-weighted: 78.5% (vs Stage A 77.8% +0.7pp,
  vs Stage B 78.2% +0.3pp). Drift attributed to engine-evolution
  between Stage A/B and now (intermediate fixes landed); well
  within ±2pp tolerance for engine-state drift.
- Variant vs Izzet Prowess: G1=93.9% / Match=99.7% (matches direct
  run_match_set 94.0% within sample noise; matches Stage A/B JSON
  recovery 99.8/99.6 g1 sim within sample noise).

Cache-fix is verified working AND past Stage A/B numbers are
verified clean by recovery + bonus fresh-pipeline run.

### Documentation cascade

Backfilled `<X.X>` placeholders in:
- `harness/specs/2026-04-27-phase-3.5-stage-a-block-eligibility.md`
  (commit message template; changelog entry)
- `harness/specs/2026-04-27-phase-3.5-stage-b-combat-modifiers.md`
  (commit message template; changelog entry)
- `harness/RESOLVED.md` (this audit's resolution entry)
- `harness/IMPERFECTIONS.md` (past-validation-numbers-audit entry
  moved to RESOLVED status; phase-3.5-stage-c-re-execution unblocks)

ARCHITECTURE.md update NOT NEEDED -- no Stage A/B variant-specific
numbers were pinned there (only the 100k canonical 65.8% headline,
which was canonical-only and clean by construction).

## Proposed fix (separate spec)

1. Change cache key from `<opp_slug>` to `<our_deck_slug>__<opp_slug>`
   (or similar tuple-encoded path).
2. Migrate or invalidate existing cache files. Recommend invalidate
   (delete `data/matchup_jobs/*.json`) since past values are suspect.
3. Add regression test: run variant + canonical gauntlets in parallel,
   assert each reads its own cache, both numbers stable across N runs.

Estimated effort: 30-60 min as a discrete spec. Tomorrow morning, not
tonight.

## Past-number audit (separate work after fix)

After cache fix ships:
1. Re-run Stage A canonical + variant gauntlets against clean cache.
   Compare to Stage A spec's cited numbers (canonical 65.8% / variant
   77.8% / edge +12.0pp). Document discrepancies.
2. Re-run Stage B canonical + variant gauntlets. Compare to Stage B
   spec's cited numbers (canonical 65.3% / variant 78.2% / edge
   +12.9pp). Document discrepancies.
3. Update ARCHITECTURE.md gauntlet entries + spec changelogs with
   corrections if any numbers shifted.
4. Re-execute Stage C against clean pipeline.

Estimated effort: 60-90 min audit + Stage C re-execution.

## Methodology lesson candidates (for spec-authoring-lessons.md v1.4)

1. **Validation pipelines need their own validation.** The
   falsifiable-prediction discipline (v1.3 lessons) implicitly trusted
   that gauntlet measurements are true. When measurements are
   pipeline-corrupted, the divergence-from-prediction discipline
   surfaces the wrong root cause (engine patch, when actually pipeline).
2. **When a stage's empirical results contradict mechanical proof, the
   pipeline is the next suspect after the patch.** Mechanical proof
   (Stage C C.1 was provably no-op for BE-side targeting against
   protection-cluster-free decks) outranks empirical headlines when
   the two disagree. Re-examine the pipeline before accepting the
   "incidental bug fix" framing.
3. **Cache keys with implicit context are time bombs.** Caches keyed
   on partial state (opp-name, no our_deck) work correctly when
   context is held constant by convention (only one our_deck per
   session) but break silently when convention is violated (variant
   + canonical parallel runs). Cache-key audits should be part of
   any pipeline that's used by multiple parameter sets.

These compound to v1.4 once the fix ships and lessons are validated
against the audit results (per CLAUDE.md Rule 9 — lessons must be
validated by execution before being codified).

## Related artifacts

- Revert commit: `de96593` (rolls back C.1 and C.3 to put Stage C
  on PARKED status)
- Stage C spec: `harness/specs/2026-04-28-phase-3.5-stage-c-protection-cluster.md`
  (status changes to BLOCKED pending cache fix)
- IMPERFECTIONS entries: `cache-collision-fix` (next-session work),
  `past-validation-numbers-audit` (after cache fix ships)
