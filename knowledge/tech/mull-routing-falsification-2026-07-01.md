---
title: "Match Mulligan Keep-Routing — 5-mode attribution + combo re-measure (FALSIFICATION)"
domain: "tech"
created: "2026-07-01"
source_spec: "harness/specs/2026-06-30-match-mulligan-keep-routing.md (Steps 5-6)"
source_commits: ["ea737ae (engine)", "002e9df (mismodel flags)"]
raw_data: "mtg-sim/data/mull_5mode_captures_2026-07-01/ (M0,M0b,M1,M2,M3,Mmech_spec,Mmech_both @ n=500 seed=42 PYTHONHASHSEED=0)"
confidence: "high"
---

## Summary (the headline)

The mulligan keep-routing pivot was premised on: *"the crude `<2 lands` mulligan
STARVES combo assembly, so routing decks through their real `keep()` will unstarve it and
pull the flagged Modern combo cells toward band."* **Steps 5-6 (the 5-mode WR decomposition
+ grixis/yawgmoth re-measure) FALSIFY that premise.** The isolated mulligan contribution to
combo assembly is ~+3pp, not the ~24pp the goldfish-vs-match gap implied. The shipped
Boros+Amulet slice is faithful and safe, but its only measured effect is a **modeling
artifact**, not a real edge, and it does **not** move the combo cells.

This is an honest negative result. Nothing was tuned. It redirects arc #2's remaining cells
away from "mulligan will fix them."

## What "shipped" actually is: M2, not M3

`_KEEP_ROUTED_APLS = {"BorosEnergyMatchAPL","AmuletTitanMatchAPL"}` (match_runner.py:1601),
and `_mull_mode` returns `keep` only for those. So in production:
- Every **Boros-vs-opponent** cell is `{a:keep, b:crude}` = **M2** (opponent is NOT keep-routed).
- Only **Boros-vs-Amulet** is a genuine `{keep,keep}` = **M3** cell.

Therefore the number live in shipped Boros right now is **M2 − M0 = +1.71pp**. The **+2.40pp**
figure (M3 − M0) is the *blocked full-field-flip projection*, NOT shipped reality. Do not cite
+2.40pp as "production."

## The 5-mode matrix (7 tier-A Boros cells, n=3500, PYTHONHASHSEED=0, seed=42)

| Mode | seats {a,b} | Aggregate Boros WR | vs M0 |
|---|---|---|---|
| M0 | crude, crude | 56.60% | baseline |
| Mmech_spec | london_crude, crude | 58.49% | **+1.89pp (mechanic-only self-help)** |
| M1 | crude, keep | 58.46% | +1.86pp (opp-help) |
| M2 | keep, crude | 58.31% | +1.71pp (**= shipped Boros-vs-opponent**) |
| M3 | keep, keep | 59.00% | +2.40pp (blocked full-field projection) |
| Mmech_both | london_crude, london_crude | 57.51% | (task-literal variant, reported for completeness) |

Per-cell M0 a_wins/500: eldrazi 192, murktide 344, humans 131, sultai 287, izzet_prowess 368,
amulet 384, grixis 275. (uw_control 446 EXCLUDED — opponent-side id()-ordering nondeterminism.)
Raw captures: `mtg-sim/data/mull_5mode_captures_2026-07-01/`.

### Attribution arithmetic
- **keep-quality self-help = M2 − Mmech_spec = −0.17pp** → NEGLIGIBLE. Boros's tuned keep ≈
  crude `lands≥2`; per-cell signs +2/−4/0 = noise. **Spec prediction (near-zero self-help for
  an aggro 2-land deck) CONFIRMED.**
- **mechanic-only self-help = Mmech_spec − M0 = +1.89pp** → SYSTEMATIC (6/7 cells positive).
  This is the **London-vs-Vancouver asymmetry**: in production Boros gets the London mulligan
  (see-7, bottom-N, cap-4) while its tier-A opponents stay on crude Vancouver (cap-3). That is
  asymmetric mulligan *sophistication* — a modeling edge, the mirror of number-forcing.
- The +1.89pp mechanic artifact ≈ the entire +1.71pp shipped M2 gain. **So the shipped slice's
  only real effect is the artifact; the keep-quality benefit is ~zero.** It MUST be attributed,
  not banked.
- **opp-help = M1 − M0 = +1.86pp** → ran **OPPOSITE to prediction**. The spec predicted
  opponents routing keep would *lower* Boros WR (harder opponents); it slightly *raised* it,
  with mixed per-cell signs (+4/−3). The WR change is not explained by "opponents become
  harder" either.

Gates 0/1 PASS (byte-identical). Gate 7 CLEAN (gains on match-tuned opponents, not goldfish-tier).
Gate 8: no routing regression (borosenergy_vs_affinity crude 82.4%→keep 84.3%). Verdict PARTIAL.

## Combo re-measure — the load-bearing falsification (n=500, pinned)

| Cell | assemble before | assemble after (keep) | WR before | WR after | gate |
|---|---|---|---|---|---|
| grixis (Archon-online) | 32.4% | 35.4% (+3.0pp, ~1 SE) | 55.0% | 55.0% (flat) | **NOT met** (needed ≥42% AND ≤48%) |
| yawgmoth | 9.8% | 6.8% (**LOWER**) | 49.0% | 54.6% | **NOT met** (assembly fell) |

- **Grixis:** isolating the mulligan (hold Boros=keep, flip grixis crude→keep) moves assembly
  only +3pp and WR **zero**. The "match 32% vs goldfish 56% ⇒ crude mulligan starves assembly"
  premise was a **MISATTRIBUTION** — goldfish-vs-match conflates the mulligan with the *entire*
  opponent-pressure channel. Isolated mulligan ≈ +3pp; the ~24pp residual is legit Boros
  pressure (racing/removing before assembly) + the 66-card audit:stub decklist. Both out of
  scope. Cell stays INVERTED/flagged.
- **Yawgmoth:** keep-routing went the OPPOSITE way — its keep mulls away combo pieces, so
  assembly FELL (9.8%→6.8%). The WR rise (49→54.6%) is NOT a real edge and NOT from assembly;
  it's yawgmoth mulliganing into weaker boards (less combat pressure), which CONFIRMS the
  binding constraint is the **over-credited combat model**, not assembly.
- **Production caveat:** both opponents are seat B, NOT in `_KEEP_ROUTED_APLS`, so in the
  shipped slice they stay crude and neither cell materially moves. The "after" numbers are only
  reachable under the full-field flip (blocked on the id()-ordering predecessor).

Spec Gate 2 stop-trigger ("P_assemble does not rise → routing not effective") effectively fired
for BOTH cells. Flags updated + committed `002e9df`. Nothing tuned (Stop condition 2 respected).

## Implications for the arc

1. **The mulligan lever does not unstarve the flagged #2 cells.** Remaining #2 work must target
   the real causes: grixis = 66-card stub list + legit Boros pressure; yawgmoth = combat
   over-credit. (goryo's/broodscale/ruby_storm etc. should NOT be approached as "mulligan will
   help.")
2. **The shipped Boros+Amulet slice now delivers ~zero real benefit and one live artifact.**
   Whether to keep it enabled or revert is a real decision (see IMPERFECTIONS
   `mull-routing-london-vancouver-asymmetry-artifact`).
3. **Downstream #5 (gauntlet) and #6 (Boros build) are contaminated** while keep-mode is on:
   Boros's absolute field WR is inflated ~1.7pp by the artifact. #6's *relative* build ranking is
   ~common-mode (likely fine); #5's field WR is not. Consumers must discount.

## Methodology lesson (see spec-authoring-lessons.md `goldfish-vs-match-gap-conflates-channels`)

Any "crude mulligan starves X" (or more generally "sim feature Y starves X") inferred from a
**goldfish-vs-match gap** is suspect: that gap bundles the ENTIRE opponent-pressure channel, not
just the one feature. Isolate the feature with a controlled A/B (hold everything else, flip only
the feature) BEFORE attributing the whole gap to it. Here the goldfish-vs-match 32%-vs-56% gap
was 79% opponent-pressure + stub, only ~3pp mulligan.
