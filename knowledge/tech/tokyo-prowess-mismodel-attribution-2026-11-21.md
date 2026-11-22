---
title: "Tokyo Prowess field-weighted WR: mismodel attribution (pre-#104)"
domain: "tech"
created: "2026-11-21"
updated: "2026-11-21"
status: "PROVISIONAL — defer re-baseline until #104 + pending gameplay PRs merge"
sources: ["mtg-sim/scripts/test_tokyo_prowess_bo3.py", "mtg-sim/engine/bo3_match.py",
          "mtg-sim/mismodeled_matchups.py", "mtg-sim PR #104 (unmerged Standard mismodel entries)"]
---

## Headline

The documented Tokyo Prowess Bo3 benchmark (CLAUDE.md: 67.8–68.0% field-weighted
match WR vs the 15-archetype Standard field) is **stale, not a demonstrated
regression**. Re-run on current main with the dedicated match APL, the **raw**
field-weighted number is **79.5% (N=200)**, but **18.6% of the field weight sits
in mismodeled cells** that all read as near-auto-wins. With those excluded and the
remaining weights renormalized, the honest **validated-only estimate is ~74.9%**
over **81.4% validated field coverage**.

**Treat 74.9% as a provisional validated-field estimate, not a new benchmark.**
Do not write it into CLAUDE.md's calibration section. When #104 and the pending
gameplay PRs (#108–#111) merge, rerun the dedicated driver and promote a fresh
result into the baseline.

## Numbers

Driver: `scripts/test_tokyo_prowess_bo3.py` (dedicated `izzetprowessstandardtokyo`
match APL, true Bo3, `mix_play_draw=True`, `run_bo3_set` default `seed=42`). Field
weights are the FIELD list baked into that script. Mismodel exclusion set applied
**manually** (the registry on main only carries the Modern cells; the Standard
entries — Izzet Lessons, Jeskai Lute — live in the unmerged #104; Sultai
Reanimator is an incomplete-deck stub).

| Measure | N=200 | N=120 |
|---|---|---|
| (A) Raw full-field FW match WR | **79.5%** | 79.8% |
| (B) Excluding Izzet Lessons only | 76.7% | 77.0% |
| (C) Validated-only (excl Lessons + Jeskai Lute + Sultai stub) | **74.9%** | 75.2% |
| Validated field coverage | 81.4% (18.6% excluded) | same |

### Excluded opponents (and why)

| Opponent | Field weight | Cell WR (N=200) | Why excluded |
|---|---|---|---|
| Izzet Lessons | 12.4% of covered field | 99.5% | Hand-size / card-advantage inevitability not modeled; #104 flags UNUSABLE. Biggest single lever (A→B = −2.8 pts). |
| Jeskai Lute | 3.1% | 100.0% | #104 mismodel entry. |
| Sultai Reanimator | 3.0% | 100.0% | Incomplete decklist stub — engine prints `[!INCOMPLETE DECK] ... do not treat its results as validated`. |

### Retained but flagged for investigation

- **Jeskai Control — 100.0% WR.** Not in the #104 mismodel set or the registry,
  so it was **not** excluded (excluding unflagged cells would be cherry-picking).
  A 100% cell is suspicious; flag for a look, don't silently drop.

## Methodology corrections (supersede the round-58 chat claims)

Two claims I made in the round-58 discussion were wrong and are retracted here:

1. **"N-sensitivity ~5 pts" is retracted.** `run_bo3_set` builds
   `match_seeds = [rng.randint(...) for _ in range(n)]` from a single
   `random.Random(42)`, so the first 120 match seeds are **nested** inside the
   200. Running the dedicated driver at both N gives **79.8% (N=120) vs 79.5%
   (N=200)** — a 0.3-pt difference, i.e. **stable**. The earlier "74.7% at
   N=120" figure came from a **different invocation** (this script hardcodes
   N=200), so it is not seed-nested with these runs and must not be compared to
   them as if it were the same measurement. Separate seed sensitivity from
   sample-size sensitivity before attributing any delta; here, with seeds held
   nested, there is essentially no sample-size effect.

2. **"Sultai 12.6% → 100% instability" was cross-driver, not within-driver.**
   With the dedicated driver, Sultai Reanimator reads a **stable 100% at both
   N=120 and N=200**. The 12.6% came from the other (round-58) invocation. The
   cell is still invalid (incomplete deck), but the apparent variance was a
   driver/method difference, not stochastic noise.

General lesson: **only compare field-weighted WRs produced by the same driver at
the same field state.** Cross-driver comparisons (generic-playbook APL vs
dedicated match APL, different seed bases, different `--n-games` entry points)
conflate method with signal. The documented 67.8% baseline predates the #103
Lessons fix and may itself be a different driver/state; a clean "did it go up?"
answer requires rerunning the old baseline with this driver.

## Decision

Save these findings now; **defer re-baselining**. This preserves the evidence —
specifically how much of the headline depends on invalid cells — without
prematurely treating unstable numbers as calibrated performance. Re-baseline
after #104 (excludes Lessons/Lute) and #108–#111 merge: rerun
`scripts/test_tokyo_prowess_bo3.py`, apply validated-only weighting via the
then-updated `mismodeled_matchups.py`, and promote the result into CLAUDE.md with
the excluded-field-weight percentage stated alongside.

## Reproduce

```
python scripts/test_tokyo_prowess_bo3.py        # N=200, prints per-cell WR + raw FW
```
Validated-only is computed by dropping the three excluded cells from the FIELD
list and renormalizing over the remaining shares.
