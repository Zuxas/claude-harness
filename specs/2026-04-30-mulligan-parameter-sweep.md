---
title: Mulligan parameter sweep — empirically derive optimal keep() thresholds
status: PROPOSED
created: 2026-04-30
updated: 2026-04-30
project: mtg-sim
estimated_time: 90-120 min scripting + 2-4 hours compute
related_findings: harness/knowledge/tech/external-research-mtg-ai-2026-04-30.md
related_commits:
supersedes:
superseded_by:
---

# Spec: Mulligan Parameter Sweep

## Goal

Replace author-intuition keep() thresholds across the APL portfolio with simulation-validated
ones derived by parameter sweep. Chris Nettle's 2-1-2 finding (2 lands + 1 creature + 2 max
mulligans = optimal for aggro mono-red) provides the external validation baseline. This spec
implements the same methodology at scale using parallel_launcher, covers multiple deck roles,
and directly addresses the `mulligan-logic-portfolio-gap` IMPERFECTION.

## Pre-flight reads

1. `harness/knowledge/tech/external-research-mtg-ai-2026-04-30.md` — Nettle 2-1-2 finding
2. `harness/IMPERFECTIONS.md:mulligan-logic-portfolio-gap` — current scope of the gap
3. `apl/boros_energy.py` — reference aggro APL with good keep() logic
4. `harness/knowledge/tech/spec-authoring-lessons.md`

## Scope

### In scope
- Build `scripts/mulligan_sweep.py` — sweeps (min_lands, min_creatures, max_mulligans)
  for a given APL, runs N=50,000 goldfish games per combination
- Sweep on 4 reference decks: Boros Energy (aggro), Amulet Titan (ramp), Jeskai Blink (midrange),
  Goryo's Vengeance (combo)
- Output: per-combination avg kill turn, std dev, p25/p50/p75
- Compile per-role optimal thresholds
- Update the 16 SHIM/SHALLOW APLs with validated thresholds per role

### Explicitly out of scope
- London Mulligan scry optimization (the sim uses Paris mulligan)
- Play-vs-draw threshold differentiation (deferred — complex, separate spec)
- Post-board keep criteria (deferred)

## Steps

### T.0 — Pre-flight (~10 min)
Read all pre-flight files. Confirm Nettle 2-1-2 finding and current IMPERFECTIONS scope.

### T.1 — Build mulligan_sweep.py (~30 min)

```python
# scripts/mulligan_sweep.py
"""
Parametric mulligan threshold sweep.

Varies (min_lands, min_creatures, max_mulligans) and runs N goldfish games per combination.
Reports avg kill turn distribution per combination to find the optimal keep() threshold.

Usage:
    python scripts/mulligan_sweep.py --deck "Boros Energy" --format modern --n 50000
    python scripts/mulligan_sweep.py --deck "Boros Energy" --n 50000 --csv mulligan_sweep.csv
"""
```

Key implementation:
- Patch the APL's keep() method at runtime for each combination
  (override with parametric `lambda hand, mulls, on_play: len([c for c in hand if c.is_land()]) >= min_l and len([c for c in hand if c.name in KEY_CARDS]) >= min_c`)
- KEY_CARDS extracted from APL module constants (the card name constants defined at top of each APL)
- Run goldfish sim via `run_goldfish_set()` for each combination
- Track: avg_kill_turn, kill_turn_p25/p50/p75/p90, mulligan_rate
- Output: sorted by avg_kill_turn ascending (lower = better)

Parameter space:
- min_lands: [1, 2, 3]
- min_creatures: [0, 1, 2]  (or "key cards" for non-aggro)
- max_mulligans: [1, 2, 3]
- Total combinations: 27 per deck × 4 reference decks = 108 runs
- At N=50,000 per run: ~5.4M total games (expect 15-30 min runtime with parallel workers)

### T.2 — Calibration run: Boros Energy (~15 min + compute)

Run sweep on Boros Energy first. Expected outcome per Nettle finding:
- 2-1-2 should be near-optimal for aggro
- 1-x-x combinations should show higher avg kill turn (too loose, hands without plays)
- 3-x-x combinations should show higher avg kill turn (too strict, too many mulligans)

**Stop condition:** If 2-1-2 is NOT near the top of the Boros Energy ranking, investigate before proceeding.
The calibration run validates the methodology. If Boros Energy's known-good keep logic
benchmarks differently, the sweep has a bug.

### T.3 — Full sweep: all 4 reference decks (~compute time)

Run in parallel (background) for Amulet Titan, Jeskai Blink, Goryo's Vengeance.
While compute runs, proceed to T.4.

### T.4 — Compile per-role optimal thresholds (~15 min)

From sweep results, derive:
- Aggro optimal: likely 2-1-2 (Nettle-confirmed)
- Ramp optimal: likely 3-0-2 (need mana, threats less critical early)
- Midrange optimal: likely 2-1-2 or 3-1-2
- Combo optimal: likely 2-0-2 or 2-1-2 with must_have key piece

Write findings to `harness/knowledge/tech/mulligan-thresholds-2026-04-30.md`.

### T.5 — Update SHIM/SHALLOW APLs (~30 min)

Apply validated thresholds to the 16 APLs identified in `mulligan-logic-portfolio-gap`.
Each update:
- Replace SHIM (generic_keep) with role-appropriate keep() using validated threshold
- Bit-stable goldfish test before/after (N=1000) — verify kill turn doesn't regress
- Commit per deck in batches of 3-4

### T.6 — Update IMPERFECTIONS and spec status

## Validation gates

| Gate | Acceptance | Stop trigger |
|---|---|---|
| 1 — calibration | Boros Energy 2-1-2 in top 3 of sweep rankings | 2-1-2 not near top — sweep bug |
| 2 — per-deck coverage | All 4 reference decks swept and optimal found | Any sweep failure |
| 3 — SHIM updates | Each updated APL: goldfish avg_kill_turn within 0.1 turns of pre-update | Regression > 0.1 turns |
| 4 — drift clean | drift-detect 0 errors after all updates | New errors |

## Stop conditions

- **Calibration fails** (Gate 1): stop, investigate sweep implementation
- **Any SHIM update regresses goldfish > 0.1 turns**: revert, investigate, defer that APL
- **Compute time > 4 hours**: reduce N to 20,000 per combination (still statistically significant)

## Changelog

- 2026-04-30: Created (PROPOSED). Based on Nettle 2-1-2 finding + mulligan-logic-portfolio-gap.
