# Spec: Stage A/B 100k re-validation at post-Stage-1.7 baseline

**Status:** SHIPPED 2026-05-01 — Canonical 68.4% / Variant 75.1% at N=100k seed=42
**Created:** 2026-04-28 by claude.ai (for tomorrow execution)
**Target executor:** Claude Code
**Estimated effort:** 90-120 minutes (mostly gauntlet wall time; ~45 min canonical + ~45 min variant + 15-30 min cascade)
**Risk level:** LOW (read-mostly; produces new headline numbers; updates ARCHITECTURE.md and Stage A/B specs with full-precision numbers)
**Dependencies:**
- `30c992a` (Stage 1.7 fix; bit-stable baseline established)
- Bit-stable canonical 64.5% / variant 78.8% at n=1000 confirmed
**Resolves:** No OPEN imperfection (this was deferred follow-up from Stage A/B amendments under tagger-fix S3.7); this is the un-deferral

## Goal

Re-validate Boros Energy canonical + variant Modern field-weighted win rates at N=100k seed=42 against the post-Stage-1.7 bit-stable baseline. Today's measurements at n=1000 show canonical 64.5% / variant 78.8% / +14.3pp edge — but those are 1k-precision numbers. Pre-RC-DC competitive prep wants 100k-precision confidence intervals to anchor deck-choice decisions.

This is the un-deferral of Stage A/B "full-effect post-tagger-fix" re-validation that was explicitly deferred during S3.7 ("Stage A/B re-validation question deferred per spec 'Future work this enables'"). User signal during S3.7 close: defer until there's a real reason to need 100k precision — most likely after PT data settles when picking decks.

PT is Friday May 1; RC DC May 11-12. Tomorrow is Wednesday April 29. Running 100k re-validation now (vs Friday post-PT) means competitive numbers are anchored to a clean, post-1.7, pre-PT-meta-shift baseline before PT introduces meta noise.

After this ships:
- ARCHITECTURE.md gets a new headline section above the n=1k entry: "post-Stage-1.7 100k baseline, canonical X.X% +/- Y.Ypp, variant W.W% +/- Z.Zpp, edge ~+VV.Vpp"
- Stage A and Stage B spec amendments reference 100k numbers instead of 1k partial-effect numbers
- Future Phase 3.5 Stages D-K anchor on 100k baseline, not 1k

## Pre-flight reads

1. `harness/RESOLVED.md` — entry `tagger-load-path-unification` (current 1k baseline, partial-effect Stage A/B context)
2. `harness/RESOLVED.md` — entry `stage-1-7-event-bus-determinism` (bit-stable baseline confirmation)
3. `mtg-sim/ARCHITECTURE.md` — current baseline section (will be amended)
4. `harness/specs/2026-04-27-phase-3.5-stage-a-block-eligibility.md` Amendment 4 (will be re-amended with 100k numbers)
5. `harness/specs/2026-04-27-phase-3.5-stage-b-combat-modifiers.md` Amendment 5 (same)
6. The 100k canonical run procedure from prior 65.8% headline at commit `6962649` for command-shape reference

## Scope

### In scope
- Run canonical Boros Energy Modern gauntlet at N=100k seed=42
- Run variant Boros Energy Variant Jermey Modern gauntlet at N=100k seed=42
- Compute confidence intervals (binomial CI at N=100k is ±0.3pp at 95%)
- Compare against bit-stable n=1k baseline; expect within ±1pp aggregate (sample-size validation)
- Update ARCHITECTURE.md with new headline section
- Update Stage A spec Amendment 4 with 100k numbers as additional context (don't replace — preserve 1k partial-effect framing for traceability)
- Update Stage B spec Amendment 5 same treatment
- Update RESOLVED.md `tagger-load-path-unification` entry's "New trusted baseline" with 100k numbers

### Explicitly out of scope
- 100k re-validation against any deck other than Boros Energy + variant
- Stage C re-validation (no canonical 100k run for Stage C ever existed; out of scope)
- Pre-1.7 100k comparison (impossible — pre-1.7 wasn't bit-stable so re-runs would drift)

## Steps

### T.0 — Pre-flight: confirm bit-stable baseline still holds (~5 min)

Quick smoke test to confirm post-Stage-1.7 determinism hasn't regressed since `30c992a`:

```bash
cd "E:/vscode ai project/mtg-sim"
python parallel_launcher.py --deck "Boros Energy" --format modern --n 1000 --seed 42 2>&1 | tail -5
# Note the field-weighted aggregate
python parallel_launcher.py --deck "Boros Energy" --format modern --n 1000 --seed 42 2>&1 | tail -5
# Must match bit-identically (per Stage 1.7 contract)
```

If aggregates don't match: STOP, Stage 1.7 contract is broken, surface as P0.

### T.1 — Canonical 100k run (~45 min wall)

```bash
cd "E:/vscode ai project/mtg-sim"
date +"%H:%M:%S canonical-100k start"
python parallel_launcher.py --deck "Boros Energy" --format modern --n 100000 --seed 42 2>&1 | tee /tmp/canonical-100k.log
date +"%H:%M:%S canonical-100k end"
```

Capture: aggregate field-weighted, per-matchup table, wall time, JSON path.

### T.2 — Variant 100k run (~45 min wall)

Same shape:

```bash
date +"%H:%M:%S variant-100k start"
python parallel_launcher.py --deck "Boros Energy Variant Jermey" --format modern --n 100000 --seed 42 2>&1 | tee /tmp/variant-100k.log
date +"%H:%M:%S variant-100k end"
```

### T.3 — Confidence intervals + sample-size validation (~10 min)

For each matchup, compute 95% binomial CI at N=100k. Aggregate canonical/variant CI is ±~0.3pp.

Compare 100k aggregate to 1k aggregate. Expected: within ±1pp (sample noise at n=1k is roughly ±1.5pp, so ±1pp is well within).

If 100k differs from 1k by >2pp on either deck: STOP, surface — could be a real signal not captured at n=1k OR could be sample noise OR could indicate engine evolution between the 1k baseline and now.

### T.4 — Documentation cascade (~15-30 min)

- ARCHITECTURE.md: new section "Post-Stage-1.7 100k baseline" above current 1k section (preserve 1k for traceability)
- Stage A spec Amendment 4: append 100k numbers next to 1k numbers in the subset table
- Stage B spec Amendment 5: same
- RESOLVED.md `tagger-load-path-unification` "New trusted baseline" section: append 100k row
- RESOLVED.md `stage-1-7-event-bus-determinism` "Validation results" section: append 100k confirmation row (the same-seed-bit-identical contract should hold at n=100k too — that's a stronger claim than n=1k since more games means more opportunities for divergence)

### T.5 — Commit + spec status (~5 min)

Commit message:
```
docs: 100k re-validation at post-Stage-1.7 bit-stable baseline

Canonical Boros Energy: X.X% (95% CI +/- 0.3pp) at N=100k seed=42
Variant Boros Energy Variant Jermey: Y.Y% (95% CI +/- 0.3pp)
Edge: ~+Z.Zpp at 100k precision

Supersedes 1k preliminary numbers as the trusted anchor for
RC DC deck-choice decisions. Bit-identical re-runs across N=100k
gauntlets (Stage 1.7 contract holds at production scale).
```

## Validation gates

| Gate | Acceptance | Stop trigger |
|---|---|---|
| 1 — bit-stable smoke | T.0 two same-seed runs produce identical aggregate | drift — Stage 1.7 regression, P0 |
| 2 — canonical 100k completes | wall ~45 min, exit 0, JSON written, aggregate within ±1pp of 1k baseline | crash, JSON corruption, or >2pp deviation |
| 3 — variant 100k completes | same shape | same |
| 4 — CI computation | per-matchup CI written to log; aggregate CI ±~0.3pp | math error or unreasonable CI |
| 5 — documentation cascade landed | ARCHITECTURE + 2 spec amendments + 2 RESOLVED entries updated | any doc not updated |
| 6 — drift-detect clean | post-spec drift-detect: 0 errors, 0 warnings | new errors |

## Stop conditions

- **T.0 bit-stable smoke fails:** STOP, Stage 1.7 regression, escalate as P0
- **100k aggregate differs from 1k by >2pp on either deck:** STOP, surface, decide whether to investigate (could be sample noise, could be a real subset effect not visible at n=1k)
- **Per-matchup CI on any matchup is unreasonable (e.g., >5pp):** STOP, sample size issue, possibly need higher N for that specific matchup
- **Wall time on either gauntlet exceeds 75 min:** something's wrong, investigate (could be system load, could be engine slowdown)

## Reporting expectations

1. T.0 bit-stable confirmation
2. Per-matchup table at 100k, both decks, with CI
3. Aggregate canonical / variant / edge numbers with 95% CI
4. Comparison to 1k baseline (delta + within-noise assessment)
5. Wall time both runs
6. ARCHITECTURE + spec amendments landed
7. Spec status PROPOSED → SHIPPED
8. New trusted baseline value for downstream Phase 3.5 Stages D-K

## Future work this enables (NOT in scope)

- **Per-matchup confidence statements** for RC DC deck-choice memo (e.g., "BE vs Izzet Prowess: 41.3% +/- 0.7pp at 100k" — a competitive-prep statement, not just an engineering one)
- **Pre/post-PT comparison** Friday-night: same procedure run against post-PT meta will produce a delta showing which matchups shifted vs were stable
- **Stage 1.7 production-scale determinism confirmation** at N=100k specifically (today's bit-stable confirmation was at N=1k; running 100k bit-stable proves the contract holds at production scale)

## Changelog

- 2026-04-28: Created (PROPOSED) by claude.ai for tomorrow execution. Un-defer of Stage A/B 100k re-validation explicitly deferred during S3.7 "Future work this enables" with user signal "defer until real reason for 100k precision (likely after PT data settles when picking decks)." Now is the right time: bit-stable baseline at HEAD=30c992a is clean and pre-PT-noise; running 100k now anchors competitive numbers to a known-good state before PT.
