---
title: "Re-anchor: Boros Energy canonical 100k vs post-ban Modern field (2026-07-04)"
domain: "tech"
last_updated: "2026-07-04"
confidence: "high (headline); medium (per-cell attribution)"
sources:
  - "mtg-sim/data/reanchor_boros_canonical_100k.log"
  - "mtg-sim/data/parallel_results_20260704_194815.json (NEW anchor)"
  - "mtg-sim/data/parallel_results_20260501_021659.json (OLD anchor, full per-cell)"
  - "mtg-sim/ARCHITECTURE.md"
  - "mtg-sim/format_config.py (modern field block)"
  - "mtg-sim/mismodeled_matchups.py"
related_commits:
  - "ee83e45 (HEAD, branch modern-postban-arc) -- WP-B4 per-state RNG threading"
---

## 1. The new canonical anchor

**Boros Energy field-weighted MATCH win rate = 62.9% [62.8-62.9] (Wilson).**

- N = 100,000 games / matchup; 1,700,000 games total; 17 opponents.
- Branch `modern-postban-arc`, HEAD `ee83e45` (WP-B4 per-state RNG threading).
- Field = the post-ban Modern estimate in `format_config.py` (refreshed 2026-06-30).
- Wall 2001s / 17 cores. Saved: `data/parallel_results_20260704_194815.json`.
- The Wilson band is razor-tight at 100k/matchup; the 62.9% number is NOT
  noise-limited. Its real uncertainty is METHODOLOGICAL (which cells are
  mismodeled), not statistical -- see sections 4 and 5.

This is now **the NEW canonical field WR for Boros Energy at HEAD** -- the
post-WP-B4, post-ban-field baseline. It supersedes the 2026-05-01 68.4% anchor
(retained as historical).

Per-matchup (field% weight | match%):

```
Eldrazi Tron      3.7% | 86.8    Grixis Reanimator 2.4% | 76.9
Domain Zoo        3.2% | 84.7    Amulet Titan      4.8% | 75.3
Ruby Storm        4.1% | 72.8    Living End        6.5% | 72.4
Neobrand          2.0% | 72.4    Belcher           3.5% | 72.5
Goryo's Vengeance 3.5% | 72.5    Death and Taxes   5.5% | 70.0
Dimir Midrange    2.6% | 70.0    5C Humans         2.5% | 63.1
Jeskai Blink      3.0% | 56.7    Affinity          9.0% | 38.8
Izzet Prowess     1.7% | 32.7    Temur Crashcade   3.4% | 24.8
Eldrazi Ramp      1.8% | 16.5
```

Note: the field dict lists Boros Energy at 14.5%, but the gauntlet does NOT
play the mirror. The FWR renormalizes over the 17 non-mirror opponents (their
weights sum to 63.2%). Verified: sum(w*match)/63.2 = 62.87% ~= 62.9%.

## 2. Dataset impact -- what is now stale

- **68.4% (2026-05-01, `parallel_results_20260501_021659.json`) is SUPERSEDED
  and is now HISTORICAL.** It was an 18-deck-config / 17-opponent, PRE-ban field
  measured ~2 months and many engine commits ago. Do not quote it as current.
- The scattered post-2026-05-01 Boros numbers (post-ban 18-deck refresh figures,
  the ~76% affinity rebaseline pinned-run figure, the mulligan-falsification WR
  decomposition, the N=200 borosenergyjitte/fable smoke runs 2026-07-01) are
  NOT canonical 100k anchors and are superseded by this run for headline use.
- The `mtg-sim-quality-grades.md` STALENESS NOTE (2026-07-01) said "a formal
  regrade requires a gauntlet run on the post-ban field." **This run IS that
  awaited post-ban gauntlet.** That thread is now closed for the Boros headline
  (per-domain letter grades still need their own regrade pass).
- **62.9% is the post-WP-B4, post-ban-field baseline** and is the number future
  Boros deck-choice / EV work should anchor against.

## 3. Decomposition of the 68.4 -> 62.9 delta (-5.5pp)

This delta is MULTI-CAUSAL. It is NOT a WP-B4 regression. Both anchors were
re-derived cell-by-cell from their JSONs; the per-cell FWR-contribution deltas
sum to -5.55pp, reconciling exactly to the headline move.

### 3a. The mirror is NOT a driver (assumption killed)

Both anchors EXCLUDE the Boros mirror. Old field weights sum to 62.0% with no
Boros self-cell; new field weights sum to 63.2% with no self-cell. Each FWR is
renormalized over its ~17 non-mirror opponents. So the mirror-inclusion
hypothesis is falsified -- the two numbers are already apples-to-apples on the
mirror axis.

### 3b. The net is small because large per-cell moves OFFSET

The -5.5pp headline hides per-cell swings of +/-6-45pp. Top movers by
FWR-contribution (w*match/denominator, old vs new):

| Opponent          | Old cell (src) | New cell (src) | FWR-contrib delta | Primary cause |
|-------------------|----------------|----------------|-------------------|---------------|
| Affinity          | 83.2 (bo3)     | 38.8 (bo3)     | -6.55pp           | ENGINE fidelity |
| Jeskai Blink      | 66.1 @10.6%    | 56.7 @3.0%     | -8.61pp           | FIELD (share collapse) + cell |
| Living End        | 56.7 (db)@2.7% | 72.4 (com)@6.5%| +4.98pp           | FIELD (share up) + SOURCE change |
| Death and Taxes   | (not in field) | 70.0 @5.5%     | +6.09pp           | FIELD (new archetype) |
| Jeskai Control    | 69.5 @2.2%     | (retired)      | -2.47pp           | FIELD (removed) |
| Esper Blink       | 62.6 @1.8%     | (retired)      | -1.82pp           | FIELD (removed) |
| Temur Crashcade   | (not in field) | 24.8 @3.4%     | +1.33pp           | FIELD (new stub) |
| Eldrazi Ramp      | 49.2 (db)      | 16.5 (bo3)     | -0.80pp           | SOURCE (db->played-out) |
| combo cluster*    | ~55-65 (db)    | ~72-77 (com)   | net small +       | SOURCE (db hole->sampler) |

\* Amulet/Ruby/Goryo/Grixis moved from db-cached real matchup data (~55-65%) to
the combo kill-distribution sampler (`g1_source="com"`, ~72-77%) because the
post-ban DB has NO Modern data (CLAUDE.md: `mtg_meta.db` most-recent Modern
event is 2026-04-24, pre-ban). Belcher/Neobrand were already sampler-based in
the old run.

### 3c. Attribution buckets (as far as evidence allows)

- **ENGINE / APL fidelity (~2 months of work):** dominated by the **Affinity
  correction, -6.55pp -- larger than the entire net delta.** The old 83.2% was
  the known INFLATED never-develops-a-board bug; the affinity-offense-rebaseline
  arc (#3, commit ae9cb12) + the played-out cell now returns 38.8%. Eldrazi Ramp
  moving from a db anchor (~49%) to a played-out fair cell (16.5%) is a smaller
  fidelity/source shift. These are honest corrections that LOWER previously-high
  cells.
- **FIELD-COMPOSITION (post-ban refresh 2026-06-30):** net roughly neutral. The
  removals (Jeskai Control -2.47, Esper Blink -1.82) and the Jeskai Blink share
  collapse pull DOWN; the additions (Death and Taxes +6.09, Temur Crashcade
  +1.33) and the Living End share rise (+ Violent Outburst unban) pull UP. On
  aggregate the field change is a modest net POSITIVE, partially masking the
  Affinity fidelity drop.
- **SOURCE availability (post-ban DB hole):** combo cells rose ~+10-18pp each
  purely because their real-DB anchors are gone and they fell back to the race
  sampler. This is a DATA-AVAILABILITY ARTIFACT, not a real improvement in
  Boros's combo matchups. It masks part of the Affinity drop and should be
  treated as soft.

### 3d. What CANNOT be attributed

- **WP-B4's marginal effect is UNMEASURED.** There is no pre-WP-B4 100k run on
  this same post-ban field (the only other 2026-07-04 run, `..._191426.json`, is
  an N=10 smoke preview, band 62.4-76.1). WP-B4 is an RNG-plumbing / determinism
  commit (per-state RNG, P2-drift fix); assigning it any pp of the delta would be
  unfounded. Treat WP-B4 as headline-neutral absent an A/B.
- **Field vs engine are CONFOUNDED at the cell level.** Living End's move is BOTH
  more weight AND a db->com source change; the two cannot be cleanly separated
  from these two runs alone. The bucket sums above are directional, not exact
  orthogonal variance shares.

## 4. What we learned -- Boros's real field position

Boros Energy remains the clearly-favored deck of the post-ban field (62.9% FWR),
but the headline is propped up by soft combo-sampler cells and is dragged by its
single most-played opponent.

- **Worst cells:** Eldrazi Ramp 16.5%, Temur Crashcade 24.8%, Izzet Prowess
  32.7%, Affinity 38.8%. **Affinity is the largest single field share (9.0%) and
  is now a LOSING cell** -- the biggest structural change from the 68.4% era,
  where Affinity was a modeled 83.2% win. If the 38.8% is even close to real,
  Boros's field position is materially worse than the 68.4% headline implied.
- **Best cells:** Eldrazi Tron 86.8%, Domain Zoo 84.7%, Grixis Reanimator 76.9%,
  Amulet Titan 75.3%. (Grixis/Amulet are combo-sampler cells -- soft.)
- **Headline stability is partly coincidental.** The net -5.5pp is the residue of
  offsetting +/-6-9pp cell moves; 62.9% should be read as a band of methodology
  uncertainty, not a precise point estimate.

## 5. The two spotlight cells vs the mismodel flags

- **Affinity 38.8%** -- `mismodeled_matchups.py` key `izzet affinity`: direction
  INFLATED, sim ~76% Boros (n=300 pinned `run_match`), truth ~44% (direction-only,
  no post-ban DB). The 100k bo3-gauntlet cell (38.8%) sits BELOW BOTH the 76%
  pinned figure and the ~44% truth estimate. This is a **cross-method
  disagreement** (pinned run_match 76% vs bo3 gauntlet 38.8% -- different code
  paths), not evidence of a single truth. Because Affinity is 9.0% of the field,
  this one cell's uncertainty dominates the whole headline. **This cell needs its
  own dedicated re-anchor before 62.9% is trusted to the point.** Do not
  reverse-fit.
- **Izzet Prowess 32.7%** -- NOT in the mismodel registry, but it is the hardest
  fair cell and the IzzetProwess APL refactor is flagged PENDING in
  quality-grades ("Modern other APLs" B, ~3-4hr). Direction (Boros is a real dog
  here) is trustworthy across every anchor (41.1% -> 37.0% -> 32.7%); the exact
  magnitude is soft because the opponent APL is under-tuned. Treat as a genuine
  bad matchup, number approximate.

### Documentation-drift warning (found during this re-anchor)

The canonical gauntlet no longer uses the played-out path for several cells the
mismodel registry still describes for that path:

- Combo cells (Living End, Ruby Storm, Belcher, Neobrand, Goryo's, Grixis,
  Amulet) ran via the com-sampler at ~72-77%. Their registry flags (e.g. living
  end "INFLATED ~96%", ruby storm "~99.6% Boros", belcher/neobrand "~100%")
  describe the PLAYED-OUT run_match path. A reader comparing 72.4% to a
  "~96% INFLATED" flag will be confused. Sampler numbers are race-model
  estimates -- still direction-only, not calibrated.
- **Temur Crashcade** ran as a played-out FAIR cell at 24.8%, INVERTED from its
  registry flag ("INFLATED ~96% Boros", which describes the combo-sampler view).
  It is also a post-ban SYNTHETIC STUB deck (not primer-validated). Down-weight
  heavily; trust neither the flag nor the 24.8%.
- **Eldrazi Ramp 16.5%** is unflagged, but the sibling Tron flags
  (`urzatron`/`eldrazitron`) note ALL Tron cells are INFLATED for the Tron side
  because land-hate is unmodeled -- the OPPOSITE direction, i.e. Boros's real
  cell is probably BETTER than 16.5%.

Net: the 62.9% headline is reliable as "Boros is favored in this field," but
several of its constituent cells (Affinity, the combo cluster, the two stub
decks, Eldrazi Ramp) carry known model uncertainty pointing in DIFFERENT
directions. Trust the aggregate as an anchor; do not trust the exact per-cell
numbers listed as calibrated win rates.

## Changelog

- 2026-07-04: Created. Documents the post-WP-B4 post-ban-field 100k re-anchor
  (62.9% FWR at HEAD ee83e45), the full cell-by-cell decomposition of the
  68.4->62.9 delta (mirror falsified as a driver; Affinity fidelity correction
  is the largest single mover; field change net-modest; combo cells inflated by
  the post-ban DB hole; WP-B4 unmeasured), and the mismodel-flag reconciliation.

## Goldfish re-anchors (2026-07-04, N=100k, post-WP-B4)

Ran alongside the field re-anchor. KEY LEARNING: the small-gate (n=100) "shifts" in
docs/wpb4-documented-shifts-2026-07-04.md were SMALL-SAMPLE NOISE, not real WP-B4 effects --
at N=100k both settle at/near their pre-migration values:
- Amulet Titan goldfish (amulet_titan_modern.txt, seed=42): win 99.2%, avg_kill_turn 6.473,
  median 6.0. (n=100 had shown 6.14; the true 100k value ~6.47 is ~unchanged from pre-migration ~6.45.)
- Humans goldfish (humans_legacy.txt, seed=42): win 100%, avg_kill_turn 4.649, median 5,
  avg_mulligans 0.454 (mull 31.4%). (n=100 had shown 4.71; 100k settles at 4.65.)
Takeaway: goldfish kill-turn anchors are effectively UNCHANGED by WP-B4 at 100k; only the field
match FWR moved, and that move is the Affinity fidelity fix + combo data-hole artifact (see above),
not WP-B4.

## CORRECTION 2026-07-04 (paper-anchor evidence, WP-F#2 spec workflow)

The "Affinity fidelity fix (83.2 -> 38.8)" framing above is INCOMPLETE and partly FALSIFIED by real
paper data (melee, post-ban window, n=23, clears the trustworthy n>=20 gate):
- **Paper says Boros BEATS Izzet Affinity 72.7%** -- so the sim's current 38.8% cell is DEFLATED, not
  "the fix." The affinity-offense-rebaseline arc OVERCORRECTED from the old 83.2% INFLATED bug straight
  past the ~72.7% truth down to 38.8%. The sim's Affinity cell is wrong in BOTH the old and new versions,
  in opposite directions.
- Decomposing the -5.5pp field move with real anchors: the DOMINANT term is Affinity going UP +33.9pp
  (+4.83pp field-weighted at 9% weight), OFFSET by Eldrazi Tron -53.5pp, Goryo's -32.5pp, Amulet -20.8pp.
  Net ~-1.3pp -> FWR ~61.6%. So the direction (down) survives, but the "combo-sampler inflation masked the
  Affinity drop" story is FALSE -- it's Affinity-UP offsetting fair/combo-DOWN.
- Implication: 62.9% is ~right on NET but cell-level fidelity is off; the oracle-responses/Affinity engine
  work has more to do (38.8% is too low vs 72.7% paper truth). See WP-F#2 spec
  (2026-07-04-wp-f2-live-anchors-pipeline.md) Section 3a + imperfection #4.
