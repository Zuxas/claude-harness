---
title: "WP-F#2 -- Live current-window matchup-WR anchors pipeline (melee + untapped -> sim calibration)"
status: "PROPOSED"
created: "2026-07-04"
updated: "2026-07-04"
project: "mtg-meta-analyzer"
estimated_time: "M -- ~1 session build (~3-4 hr analyzer-side + sim-side wiring) + ~0.5-1 hr sim validation runtime (G4 gauntlet). Excludes any hot-zone new-table variant (adds a sign-off + backup step)."
related_findings:
  - "harness/knowledge/tech/reanchor-boros-canonical-2026-07-04.md (the 62.9% FWR anchor + the com-sampler combo-cell inflation this pipeline replaces)"
  - "BLUEPRINT-2026-07-03.md WP-F#2 (lines ~232-235: build an anchors pipeline replacing hand-carried anchors)"
  - "ASSESSMENT 2026-07-04 (melee=LIVE-BUT-DRY, untapped=HEALTHY, modern_anchor_availability=HOLE PARTIALLY OPEN, verdict=PARTIAL) -- inline in this spec"
related_specs:
  - "harness/specs/2026-07-04-oracle-driven-responses-execution.md (Affinity/Prowess cell fidelity -- this pipeline supplies the PAPER truth-anchor that spec's engine work is judged against)"
related_commits: []
supersedes: []
superseded_by: null
---

# Spec: WP-F#2 -- Live current-window matchup-WR anchors pipeline

**GOAL (one sentence):** Publish a current-window (post-ban) Modern matchup-WR
anchor table -- derived from real melee.gg paper matches (primary) + untapped
Arena Bo3 (gap-fill) -- that the sim's gauntlet READS for per-cell calibration,
replacing the hand-carried 2026-04-24 `matchup_matrix` anchors and the
`com`-sampler fallbacks for every field cell that now clears a live-sample gate,
while leaving the structurally-rare combo cells honestly flagged.

This is a SPEC ONLY (house rule #1: spec before code). No code is written here.

---

## 0. Assessment grounding (verdict: PARTIAL -- build the pipeline, flag the holes)

The four-axis assessment this spec is built on:

- **melee = LIVE-BUT-DRY.** The 2026-07-02 paging fix
  (`scrapers/mtgmelee_scraper.py:128-134`) is real and running daily via
  `background_fill.bat` (Task Scheduler 6 AM, `scripts/run_fill_from_prefs.py`,
  the `-- MTGMelee -- modern --` block) -- NOT `run_daily.bat` (Standard-only).
  Root cause it fixed: Melee `TournamentSearch` ignores `ordering` and returns
  OLDEST-first, so paging from start=0 never passed 2023 -> matches went dry
  after 2026-03-21. The fix probes `recordsTotal` and reads the LAST pages
  (newest events). BUT Modern accrual is sparse/stalled by lack of new COMPLETED
  paper Modern events (the daily run emits "already stored" / "No started rounds"
  / "Saved 0 matches"); matches Modern max event_date = 2026-06-26; June = 628
  rows vs May 1874; 0 rows in July. Scraper fixed and running; accrual is a
  supply problem, not a wiring problem.
- **untapped = HEALTHY / CURRENT.** M/W/F throttle confirmed; last real fill Fri
  2026-07-03. `untapped_matchup_snapshots` max captured_at 2026-07-03T14:17:58Z;
  `untapped_matchups` 5649 rows; `untapped_premium_matchups` 507 rows. Caveat:
  Arena/ladder scope -- does NOT cover paper Modern combo; Ruby Storm / Belcher /
  Neobrand barely exist on Arena Modern, so untapped cannot backfill the inflated
  combo cells.
- **modern_anchor_availability = HOLE PARTIALLY OPEN.** Measured live below
  (Section 3). The materialized `matchup_matrix` anchor table is frozen
  (fetched_at max 2026-04-24T10:47:41Z) -- exactly the "hand-carried anchors
  stale to 2026-04-24" the blueprint calls out.
- **db_write_hotzone = NO mutating hot-zone write required.** The sim reads the
  same canonical DB via `mtg-sim/db_bridge.py:_resolve_meta_db`
  (MTG_META_DB env > analyzer config.ini > legacy) -> `E:\mtg-data\mtg_meta.db`,
  and pulls matchup WR through `analysis/win_rates.get_real_matchup_winrates`
  (reads `matches`) + `db/untapped_queries.get_untapped_matchup_matrix`. The
  anchor table can be published as a NEW sidecar file (or a NEW derived table,
  the `matchup_matrix` materialized-table precedent) -- additive, no modification
  of existing live rows. This is DISTINCT from the melee scraper's pre-existing
  writes to the `matches` table (`db/matches_queries.save_matches`, called from
  `mtgmelee_scraper.py:423/501/474/580`) -- that is ingestion, not a WP-F#2 write.

**Verdict PARTIAL, not BLOCKED:** the pipeline CAN be built now and re-anchors
~8-9 of the 17 Modern field cells (Section 3) with real paper data -- including
the two highest-uncertainty spotlight cells (Affinity, Izzet Prowess) at the
trustworthy n>=20 gate. Three structurally-rare combos (Ruby Storm, Belcher,
Neobrand) have ZERO paper cells and CANNOT be rescued by scraper accrual or by
Arena/untapped; they stay flagged with an honest note. Scope this as "build the
pipeline; flag the 3 empty combos" -- NOT "unblock data first."

---

## 1. Scope

**In scope**
- An analyzer-side publisher that computes the current-window Modern matchup-WR
  table from `matches` (paper, primary) + untapped (gap-fill) and writes it to a
  NEW additive location (sidecar file preferred; new table = hot-zone variant).
- A sim-side reader (a new `db_bridge` function) + a wiring change at the
  gauntlet's per-cell matchup-source seam so a live anchor is consulted BEFORE
  the `com`-sampler fallback.
- A two-tier min-sample rule (trustworthy vs provisional vs no-anchor) with
  honest per-cell flags and Wilson bands.
- Falsifiable gates including a DECOMPOSED Boros field-WR re-computation.

**Out of scope**
- Refreshing the frozen `matchup_matrix` table (that is fed by
  `scrapers/matchup_scraper.py` = MTGDecks /winrates, which is AUTO-PULL DISABLED
  2026-06-04 -- see Open Questions; this pipeline SUPERSEDES `matchup_matrix` for
  the cells it covers rather than un-freezing it).
- Any engine/APL fidelity change (the Affinity/Prowess sim cells are re-anchored
  by the SEPARATE oracle-responses spec; this pipeline only supplies the paper
  TRUTH the sim is judged against).
- Standard / Pioneer / other formats (Modern only; the pipeline is
  format-parameterized so WP-G can reuse it, but only Modern is validated here).
- Increasing paper accrual (a supply problem; not solvable by a pipeline).

---

## 2. Pre-flight reads (MANDATORY -- house rule #3)

Read BEFORE any Step. Per `spec-authoring-lessons.md`
(`verify-identifiers-before-spec-execution`), Step 1 VERIFIES every identifier
below on disk before it is used.

1. `harness/knowledge/tech/spec-authoring-lessons.md` -- esp.
   `spec-prediction-model-must-be-falsifiable` (G4 must be a written expression),
   `sim-vs-db-source-gates-engine-shifts` (annotate each cell's source),
   `caches-keyed-on-partial-state-are-time-bombs` (the anchor file/table key MUST
   include format + window), `verify-identifiers-before-spec-execution`.
2. `harness/knowledge/tech/reanchor-boros-canonical-2026-07-04.md` -- the 62.9%
   FWR anchor, the per-matchup field weights (Section 1), and the com-sampler
   inflation this pipeline replaces (Sections 3b-3d, 5).
3. `mtg-meta-analyzer/analysis/win_rates.py` around L949-1010 --
   `get_real_matchup_winrates(format_name, since, min_matches=20,
   min_arch_appearances=10)`. NOTE the `since` arg is a DATE object, not a string
   (`_dt_to_db_str` calls `.strftime`); passing a str raises AttributeError.
4. `mtg-meta-analyzer/analysis/deck_ev.py` L60-73 -- the existing paper+untapped
   PRIORITY-not-blend precedent; it already calls `get_real_matchup_winrates(...,
   min_matches=10)`. This is the operative gate (see Section 5).
5. `mtg-meta-analyzer/db/untapped_queries.py` L78 --
   `get_untapped_matchup_matrix(...)`. DO NOT conflate with the `matchup_matrix`
   TABLE: different population (untapped Bo3 Arena vs MTGDecks paper).
6. `mtg-sim/db_bridge.py` L32-49 -- `_resolve_meta_db()` resolution ladder; the
   new reader co-locates the sidecar relative to the resolved DB path.
7. Sim-side seam (grep, do NOT read the whole gauntlet now): in `mtg-sim/`,
   `grep -rn "g1_source" apl/ engine/ *.py` and locate the matchup-source
   selection among `db` / `com` / `sim` / `bo3`. Candidate drivers named in
   `mtg-sim/CLAUDE.md`: `full_field_gauntlet`, `bo3_gauntlet`,
   `gauntlet_any_deck`, plus `mismodeled_matchups.py`. Record the exact
   file:function where `g1_source` is chosen. STOP-CONDITION S4 fires if that
   seam lives in an mtg-sim hot zone (`engine/match_runner.py`,
   `engine/game_state.py`, stack/priority/combat, `apl/__init__.py`).

---

## 3. Measured reality (the empirical spine -- run 2026-07-04, live DB E:\mtg-data)

`get_real_matchup_winrates("modern", since=date(2026,5,1), min_matches=G)`,
Boros Energy row (win rate = Boros's WR vs opp; n = recorded games):

**At G=10 (deck_ev's gate) -- 13 Boros cells:**

```
opp                       paper_wr   n     current sim cell (source)      cell delta (paper - sim)
Izzet Affinity            0.727      23    38.8  (bo3 played-out)         +33.9pp
Izzet Prowess             0.545      22    32.7  (bo3 played-out)         +21.8pp
Boros Energy (MIRROR)     0.444      18    -- (gauntlet skips mirror)     n/a (excluded)
Boros Aggro               0.533      15    -- (not a field opp)           n/a
Eldrazi Tron              0.333      15    86.8  (played-out)             -53.5pp
Jeskai Blink              0.533      15    56.7  (played-out)             -3.4pp
Living End                0.667      15    72.4  (com-sampler)            -5.7pp
Dimir Midrange            0.833      12    70.0  (played-out)             +13.3pp
5C Ramp                   0.636      11    -- (map? see OQ)               n/a
Amulet Titan              0.545      11    75.3  (com-sampler)            -20.8pp
Domain Ramp               0.455      11    84.7? (Domain Zoo -- map? OQ)  ambiguous
Esper Blink               0.455      11    -- (retired from field)       n/a
W-U-B-G Goryo's           0.400      10    72.5  (com-sampler)            -32.5pp
```

**At G=20 (win_rates default) -- only 2 Boros cells survive:** Izzet Affinity
(23), Izzet Prowess (22). Format-wide only 3 pairs clear 20; NONE are combo.

**Ruby Storm / Mono Blue Belcher / Neobrand: ABSENT from the Boros row at any
gate.** Confirmed structurally empty -- no scraper accrual or Arena source will
fill them. They stay `com`-sampler + flagged.

### 3a. What this reframes (READ BEFORE writing G4)

The task hypothesized "FWR lower than 62.9%, predicting the honest combo
DEFLATION." The paper data only PARTIALLY supports that, and for a DIFFERENT
reason than the combo cluster:

- The single LARGEST live-anchor move is **Affinity INFLATING +33.9pp at 9.0%
  field weight** -- paper says Boros BEATS Izzet Affinity 72.7% (n=23, clears the
  trustworthy gate), contradicting BOTH the 38.8% bo3 gauntlet cell AND the
  re-anchor doc's fear that 38.8% might be real. This is the headline finding:
  paper evidence that the sim's Affinity cell is DEFLATED, not that the combo
  sampler was the main distortion.
- The largest DEFLATION is **Eldrazi Tron -53.5pp** (a FAIR cell, n=15) and
  **Goryo's -32.5pp** / **Amulet -20.8pp** (combo, com-sampler). So the combo
  deflation is real (Goryo's, Amulet, Living End) but is NOT the dominant term.
- Net (decomposed in G4) lands slightly BELOW 62.9% (~61-62%), so the task's
  DIRECTION survives -- but the spec MUST state the real composition, not the
  "combo sampler inflation masked the Affinity drop" story, which paper
  FALSIFIES. Do NOT reverse-fit to the hypothesized rationale
  (`goldfish-vs-match-gap-conflates-channels` anti-pattern: attributing a move to
  the lever you already wanted).

---

## 4. Design

### (a) Data source query + current-window definition

- **Window:** post-ban, `event_date >= 2026-05-01` (the May-2026 B&R is the
  meaningful cutpoint; the pre-ban field is a different metagame). Define a single
  module constant `CURRENT_WINDOW_START = date(2026,5,1)` (NOT a rolling
  today-minus-N, so the anchor is reproducible run-to-run; revisit only on the
  next B&R). This is the cache-key dimension per
  `caches-keyed-on-partial-state-are-time-bombs`.
- **Primary source (paper):** `get_real_matchup_winrates("modern",
  since=CURRENT_WINDOW_START, min_matches=10)` -- pass a `date`, not a str
  (pre-flight #3). min_matches=10 is FORCED by the goal: at 20 the pipeline is a
  no-op on every cell it aims to fix (Section 3). See Section 5 for the tiering
  that keeps 20 honest.
- **Gap-fill source (untapped Arena Bo3):** `get_untapped_matchup_matrix(...)`
  for FAIR field cells the paper row lacks. Tagged `source="untapped-arena"` and
  flagged scope-mismatched. Will NOT rescue Ruby/Belcher/Neobrand.
- **NEVER blend** (`deck_ev.py` precedent): sources are PRIORITY-ORDERED
  alternatives per cell (paper first; untapped only where paper is absent), never
  averaged into one number. Every published cell carries its `source`.

### (b) Anchors storage -- WHERE it lives

**PRIMARY (recommended, NON-hot-zone): a sidecar JSON file.** Path co-located
with the resolved DB so it follows the DB wherever `_resolve_meta_db` points:
`<dirname(resolved_db)>/anchors/current_window_modern.json` (i.e.
`E:\mtg-data\anchors\current_window_modern.json`). A NEW file in a NEW subdir
touches ZERO existing DB rows and ZERO schema. Shape:

```
{ "format": "modern",
  "window_start": "2026-05-01",
  "generated_at_utc": "<iso>",
  "source_provenance": {"paper_max_event_date": "2026-06-26", "untapped_max_captured_at": "..."},
  "cells": {
     "<deck_archetype>": {
        "<opp_archetype_norm>": {
           "win_rate": 0.727, "n": 23, "wilson_lo": .., "wilson_hi": ..,
           "source": "paper" | "untapped-arena",
           "tier": "trustworthy" | "provisional",
           "note": "..." } } } }
```

**ALTERNATE (HOT ZONE -- requires sign-off + backup): a new derived table**
`sim_anchor_matchups` in `mtg_meta.db` (the `matchup_matrix` materialized-table
precedent). A `CREATE TABLE` is a SCHEMA CHANGE to the live `E:\mtg-data` DB =
mtg-meta-analyzer hot zone. If chosen: back up `mtg_meta.db` first, ASK before
running, keep the same keyed shape (`format, deck, opp, win_rate, n, wilson_lo,
wilson_hi, source, tier, generated_at`). The sidecar is preferred precisely to
avoid this; only take the table route if a consumer needs SQL-side joins.

### (c) Sim-side read + consumption seam

- New reader `db_bridge.get_current_window_anchors(format_name, deck_archetype)
  -> dict {opp_norm: {win_rate, n, wilson_lo, wilson_hi, source, tier, note}}`.
  Reads the sidecar (path derived off `_resolve_meta_db`). Returns `{}` if the
  file is ABSENT -> gauntlet behavior is BYTE-IDENTICAL without the file
  (additive; this is Gate G3's no-file invariant).
- Wiring at the seam found in pre-flight #7: when selecting a cell's g1 source,
  consult the live anchor BEFORE `com`. New source label `"live"` (or
  `"live-anchor"`). Priority order becomes:
  `db(real cached) > live(current-window paper, tier>=provisional) > com(sampler) > sim/bo3`.
  A trustworthy-tier live anchor un-flags the cell; a provisional-tier anchor
  replaces the point estimate but KEEPS the flag (honest, wide band); no anchor
  -> unchanged (`com` + existing `[!MISMODEL]` flag).

### (d) Min-sample rule (two-tier, honest)

- `n >= 20` -> **trustworthy**: live anchor replaces the sampler and un-flags the
  cell (still carries its Wilson band). Only Affinity (23) + Izzet Prowess (22)
  reach this today.
- `10 <= n < 20` -> **provisional**: live anchor replaces the point estimate but
  the cell STAYS flagged with a "low-n live paper, wide band" note (Living End 15,
  Eldrazi Tron 15, Jeskai Blink 15, Dimir 12, Amulet 11, Goryo's 10, ...).
- `n < 10` -> **no live anchor**: stays `com`-sampler + flagged exactly as today
  (Ruby Storm, Belcher, Neobrand, Grixis-vs-Boros).

Because NO combo cell reaches 20, the deflated FWR is itself PROVISIONAL and is
NOT a new canonical anchor. State this in the published note and in G4.

---

## 5. Steps (ordered, mechanical)

1. **Verify identifiers.** Confirm on disk: `get_real_matchup_winrates`
   signature + `since` is a date (win_rates.py ~L949); `get_untapped_matchup_matrix`
   (untapped_queries.py:78); `_resolve_meta_db` (db_bridge.py:32); the g1-source
   seam file:function (pre-flight #7 grep). Record the seam location; if it is in
   an mtg-sim hot zone -> S4.
2. **Publisher (analyzer side).** New script `scripts/build_sim_anchors.py`
   (verify name is free first): compute the paper cells for the deck(s) of
   interest (start with `boros_energy`), attach Wilson [lo,hi] via
   `analysis/wilson.py`, tag tier by the two-tier rule, gap-fill fair cells from
   untapped tagged `untapped-arena`, write the sidecar (Section 4b). Print a
   `--counts`-style summary (per analyzer rule #3): cells emitted per tier per
   source. Idempotent overwrite.
3. **Sim reader.** Add `get_current_window_anchors` to `db_bridge.py` (additive
   function; returns `{}` when file absent).
4. **Wire the seam.** At the g1-source selection point, insert the `live` source
   ahead of `com` per Section 4c. Guard behind file-presence so absent-file ==
   today's behavior. If the seam is a driver (not engine core), no hot-zone
   sign-off needed; if S4 fired, STOP and get sign-off.
5. **Gate G1-G3** (below). 
6. **Gate G4:** run the Boros field gauntlet WITH the anchor file present. Reuse
   the canonical runner used for the 62.9% anchor (verify its exact invocation
   from `reanchor-boros-canonical-2026-07-04.md` sources: the
   `parallel_launcher` / gauntlet entry that produced
   `data/parallel_results_20260704_194815.json`). A cheaper N (e.g. N=10k) is
   acceptable for the direction/decomposition check; note runtime.
7. **Document + flag.** Write the provisional-FWR finding, update
   `mismodeled_matchups.py` notes for cells now live-anchored, add the 3
   empty-combo honest flags, open the imperfections in Section 8.

---

## 6. Validation gates (falsifiable, with written predictions)

Annotate every cell's source `(PAPER)` / `(UNTAPPED)` / `(COM)` per
`sim-vs-db-source-gates-engine-shifts`.

**G1 -- pipeline reproduces the measured Boros row.** The published sidecar for
`boros_energy` at G=10 contains EXACTLY the 13 cells in Section 3 (Living End
0.667/15, Amulet 0.545/11, Goryo's 0.400/10, Affinity 0.727/23, Prowess
0.545/22, ...), and Ruby Storm / Belcher / Neobrand are ABSENT.
PASS = row matches Section 3 to +/-0 cells and +/-1 in n (accrual may add a
game). FALSIFIED if a "structurally empty" combo appears (window/normalization
bug) or a Section-3 cell is missing (query/date-type bug -- see pre-flight #3).

**G2 -- min-sample honesty.** Exactly 2 cells tier=trustworthy (Affinity 23,
Prowess 22); the rest of Section 3's field cells tier=provisional; 0 cells with
n<10 emitted. Every cell carries n + Wilson [lo,hi]. FALSIFIED if any n<10 cell
is emitted as a live anchor, or a trustworthy tag appears on an n<20 cell.

**G3 -- additive read, no-file invariant.** With the anchor file ABSENT, a fixed
seed gauntlet is BYTE-IDENTICAL to pre-change HEAD. With the file PRESENT, the
Boros-vs-Living-End g1_source flips `com`->`live`; Boros-vs-Ruby-Storm stays
`com` + flagged. FALSIFIED if absent-file output differs (integration not
additive -> S3) or a flip does not occur where a provisional+ anchor exists.

**G4 -- decomposed field-WR re-computation (the load-bearing gate).**
Re-computing Boros FWR with live anchors REPLACING the current cells lands
BELOW 62.9%, and the per-cell decomposition reconciles. Prediction, computed from
the re-anchor doc's field weights (renormalized over 0.632) x the measured paper
cells (Section 3), FWR-contribution delta = (paper_wr - sim_cell) x (weight/0.632):

```
opp             weight  paper - sim         FWR-contrib delta
Izzet Affinity  9.0%    .727-.388=+.339     +4.83pp   <- dominant, INFLATION
Eldrazi Tron    3.7%    .333-.868=-.535     -3.13pp
W-U-B-G Goryo's 3.5%    .400-.725=-.325     -1.80pp
Amulet Titan    4.8%    .545-.753=-.208     -1.58pp
Living End      6.5%    .667-.724=-.057     -0.59pp
Izzet Prowess   1.7%    .545-.327=+.218     +0.59pp
Dimir Midrange  2.6%    .833-.700=+.133     +0.55pp
Jeskai Blink    3.0%    .533-.567=-.034     -0.16pp
                                     NET  ~ -1.29pp  -> FWR ~ 61.6%
```

PASS band: recomputed FWR in **[59.5%, 62.5%]** (below 62.9%), AND the two
largest single movers are Affinity (UP) and Eldrazi Tron (DOWN), AND the
per-cell contributions sum to within +/-0.5pp of the observed headline move.
Weak sub-gate (sanity floor only, per advisor -- bands are +/-25-30pp at n=10-18
so almost anything passes it): each live-anchored combo cell reads within its own
Wilson band. FALSIFIED if FWR >= 62.9% (either the anchors did not fire -> wiring
bug, or paper combo cells are NOT below sampler -> re-derive), or if the
decomposition does not reconcile to the headline (mapping error: which paper
label maps to which field deck -- see Open Questions).

Do NOT claim the -1.3pp is "combo deflation." It is Affinity-up (+4.83) largely
offsetting Tron/Goryo's/Amulet-down. State the composition.

---

## 7. Stop conditions (teeth, per house rule #4)

- **S1 (BLOCKED sub-case):** if the current-window Boros paper row returns ZERO
  cells at n>=10 (paging fix regressed / accrual fully stalled), STOP -- there is
  nothing to publish. Re-scope to "unblock the data supply first." (Section 3
  shows this is NOT the case today; S1 is the guard for a future dry run.)
- **S2:** if the sim-side seam (pre-flight #7) is NOT found or `g1_source` does
  not exist by that name, STOP and re-locate before wiring (do not invent a
  source label; `verify-identifiers` lesson).
- **S3:** if the absent-file gauntlet is NOT byte-identical (G3), STOP -- the read
  is not additive; fix before proceeding.
- **S4 (HOT ZONE):** if the seam lives in an mtg-sim hot zone
  (`engine/match_runner.py`, `game_state.py`, stack/priority/combat,
  `apl/__init__.py`), STOP and get sign-off + state blast radius before editing.
- **S5:** if G4 FWR comes back >= 62.9% (UP or flat), STOP and investigate:
  either the anchors did not wire (check g1_source flips) or the paper cells are
  not below sampler (re-derive; do not force the direction).

---

## 8. Hot-zone flags

- **PRIMARY design = NO hot zone.** Sidecar file = a NEW file in a NEW
  `anchors/` subdir alongside `mtg_meta.db`; touches no existing DB row/schema.
  Producer = new analyzer script; consumer = new `db_bridge` function. Low blast
  radius: worst case a malformed file -> reader returns `{}` -> gauntlet falls
  back to today's `com` behavior.
- **ALTERNATE design = HOT ZONE (needs sign-off + backup).** A `sim_anchor_matchups`
  TABLE is a schema change to the live `E:\mtg-data\mtg_meta.db` (analyzer hot
  zone: "the live mtg_meta.db schema and write paths"). Back up `mtg_meta.db`
  before `CREATE TABLE`; ASK first. Only if a SQL-side consumer needs it.
- **Sim-side wiring:** the g1-source seam is expected in a gauntlet DRIVER
  (`full_field_gauntlet` / `bo3_gauntlet` / `gauntlet_any_deck`), which is NOT an
  mtg-sim hot zone. S4 covers the case where it turns out to be in engine core.
- **Publisher cadence (unresolved -- pick one, both have a flag):** (i) a NEW
  Task Scheduler task = a harness/scheduled-tasks hot zone (sign-off); (ii)
  piggyback the existing 6 AM `background_fill.bat` after the melee block = a
  modification to the live fill pipeline (lower blast, but still an edit to a
  running scheduled path -- announce it). Or (iii) run the publisher on-demand
  only (zero cadence hot-zone; anchor refreshes when a human runs it). Recommend
  (iii) for v0, promote to (ii) once G1-G4 pass. This choice is REQUIRED before
  the pipeline is "live"; flag it to the user.
- **No write to `matches`.** The scraper's `save_matches` writes are pre-existing
  ingestion, untouched by this spec.

---

## 9. Estimated time

M -- ~1 session. Publisher + Wilson tiering ~1.5-2 hr; `db_bridge` reader ~0.5
hr; seam wiring + G3 byte-identity ~1 hr; G4 validation gauntlet ~0.5-1 hr sim
runtime (33 min at 100k/17-core per the re-anchor run; a cheaper N=10k is minutes).
The hot-zone new-table variant adds a backup + sign-off step (do not include in
the M estimate).

---

## 10. Annotated imperfections (known limits of this spec's scope)

1. **Provisional, not canonical.** No combo cell reaches n>=20; the deflated FWR
   is a provisional read with +/-25-30pp per-cell Wilson bands. It updates the
   direction, NOT the 62.9% headline's precision. -> IMPERFECTIONS entry.
2. **Archetype-label noise.** 225 Modern archetypes with 20+ matches are still
   UNCLASSIFIED (`data/unclassified_archetypes.csv`); "Domain Ramp" vs field
   "Domain Zoo", "5C Ramp" mapping, and possible Ruby/Poison/Storm variant
   aliases mean exact cell counts are approximate. Eldrazi Tron 33.3% (n=15) is
   shocking vs sim 86.8% and may be partly a naming artifact -- flag, do not treat
   the -53.5pp as calibrated.
3. **The 3 empty combos stay flagged forever via this pipeline.** Ruby Storm /
   Belcher / Neobrand have no paper cells and no Arena coverage; a different
   anchor source (hand-curated primer WRs, or a dedicated combo-cell re-anchor)
   is the only path -- out of scope. -> IMPERFECTIONS entry.
4. **Affinity/Prowess cross-method disagreement is SURFACED, not resolved.** This
   pipeline gives paper truth (Affinity 72.7%, Prowess 54.5%) that contradicts the
   sim cells (38.8%, 32.7%); resolving the engine cells is the oracle-responses
   spec's job. This spec only makes the disagreement measurable.
   **Note (2026-07-10, method-decomposed -- partially advances, does not resolve):**
   decomposing by METHOD (not just source) shows the bo3 `_run_fair` Affinity cell
   (base 42.7 / lowcurve 48.0 g1) reads ~15-25pp BELOW two non-bo3 measurements --
   current-engine `run_match` MATCH (63.0%, POST-WP-B4, n=300 seed42) and this
   section's live paper anchor (72.7%, n=23) -- both Boros-FAVORED. Corroborates the
   Section 3a DEFLATED call along a second axis and narrows the disagreement toward a
   bo3-`_run_fair`-specific under-rating. See `mtg-sim/mismodeled_matchups.py['izzet
   affinity'] note_2026_07_10` and `harness/IMPERFECTIONS.md
   bo3-run_fair-underrates-vs-run_match` (OPEN). Still NOT resolved: n=23 is too small
   to close the ~10pp run_match-vs-paper gap, and generality beyond Affinity is untested.
5. **Single-deck v0.** The publisher is specified for `boros_energy` first;
   generalizing to every field deck's row is a mechanical follow-on (same query,
   loop the deck list).

---

## 11. Open questions (for the user / council before execution)

1. **matchup_matrix premise in the blueprint is likely FALSE.** WP-F#2 step 2
   says "verify `matchup_matrix` refreshes via the fixed M/W/F untapped fill."
   But `matchup_matrix` is populated by `scrapers/matchup_scraper.py`
   (`save_matchup_data` -> MTGDecks.net /winrates), and MTGDecks auto-pull was
   DISABLED 2026-06-04 (analyzer CLAUDE.md). That is why it is frozen at
   2026-04-24 -- untapped never fed it. Confirm: do we (a) leave `matchup_matrix`
   frozen and let this pipeline supersede it, or (b) re-enable the MTGDecks
   scraper? This spec assumes (a).
2. **min_matches threshold:** accept the two-tier 10/20 rule, or prefer a single
   gate? 10 is forced to touch the combo cells at all; 20 would make the pipeline
   a no-op on them.
3. **Storage:** sidecar file (recommended, non-hot-zone) vs new
   `sim_anchor_matchups` table (hot-zone, needs sign-off + backup)?
4. **Publisher cadence:** on-demand v0 / piggyback 6 AM fill / new scheduled task
   (Section 8)?
5. **Label mapping:** confirm "W-U-B-G Goryo's" == field "Goryo's Vengeance",
   "Izzet Affinity" == field "Affinity", "Domain Ramp" vs "Domain Zoo",
   "5C Ramp" -> which field deck. G4's decomposition reconciliation depends on it.

---

## Changelog

- 2026-07-04: Created (PROPOSED). Grounded in the 2026-07-04 assessment (verdict
  PARTIAL). Empirical spine = a live query of the Boros Energy Modern post-ban
  row (13 cells at n>=10; Affinity 72.7%/n=23 and Prowess 54.5%/n=22 clear n>=20;
  Ruby/Belcher/Neobrand absent). G4 decomposed from the re-anchor doc's field
  weights x measured paper cells (net ~-1.3pp -> FWR ~61.6%, DOWN but driven by
  Affinity UP offsetting Tron/Goryo's/Amulet DOWN -- NOT the hypothesized combo
  deflation story). Flagged the matchup_matrix/MTGDecks-disabled premise error in
  the blueprint as Open Question #1.

---

## 12. Resolutions 2026-07-04 (user-answered; supersedes Section 11)

- **OQ#1 -- data source: RESOLVED = keep melee(paper) + untapped(Arena); MTGGoldfish is NOT viable.**
  User directed "use recent MTGGoldfish data." Verified (read-only, live DB, workflow agent): there is
  NO MTGGoldfish scraper (roadmap-only, ROADMAP.md:63), no MTGGoldfish table, nothing flowing in either
  fill path; AND MTGGoldfish publishes only metagame-shares + decklists, never a head-to-head WR grid
  (2026-06-26-modern-data-acquisition.md:88,99-104; decklist download robots-disallowed). So it can
  neither replace nor supplement the MATCHUP source. matchup_matrix stays frozen; the Section 4a
  melee+untapped pipeline supersedes it (spec assumption (a), confirmed). MTGGoldfish's only possible
  future role = FIELD-WEIGHT refresh (a separate roadmap scraper, robots-restricted) -- FLAGGED as a
  follow-on, NOT a WP-F#2 dependency. (Honest correction of the user premise, evidence-backed.)
- **OQ#2 -- min_matches: RESOLVED = the two-tier 10/20 rule (Section 4d).** Trustworthy n>=20, provisional
  10<=n<20 (stays flagged), no-anchor n<10. Accepted.
- **OQ#3 -- storage: RESOLVED = sidecar JSON file (Section 4b PRIMARY, non-hot-zone).** No new DB table;
  `<dirname(resolved_db)>/anchors/current_window_modern.json`. The hot-zone table variant is dropped.
- **OQ#4 -- cadence: RESOLVED = on-demand for v0, then PIGGYBACK the 6 AM background_fill.bat after the
  melee block once G1-G4 pass.** No new scheduled task. (The piggyback is a modification to a running
  scheduled path -- announce it when promoting from on-demand to piggyback.)
- **OQ#5 -- label mapping: RESOLVED = confirm in Step 1** (Goryo's Vengeance / Izzet Affinity / Domain
  Zoo / 5C Ramp -> field decks); G4's decomposition reconciliation depends on it. Accepted as a Step-1 gate.

Status: OQs resolved; spec is council-check-ready. Execution still gated on the council-check + (for the
piggyback promotion) a scheduled-path announcement.

---

## 13. Council-check NEEDS-FIXES 2026-07-04 (apply before execution -- cross-vendor, Codex-corroborated)

Council-check (workflow wcyhvbzhd; 2 blind Claude seats + Codex gpt-5.5, all NEEDS-FIXES, chair verified
the two decisive claims against source). Design FOUNDATION is SOUND (sidecar additive/non-hot-zone,
byte-identity reversible via G3, paper source works). These 7 corrections are REQUIRED before execution
and OVERRIDE the relevant sections:

1. **Consumption seam is under-modeled (load-bearing).** `run_matchup.py` has TWO g1-source paths:
   `_run_combo` (L84-100; db-then-com at L100) feeds ONLY the provisional COMBO cells; `_run_fair` Path A
   (L162-210) short-circuits to `g1_source="bo3"` at L202 with NO db/live lookup and feeds the TRUSTWORTHY
   Affinity/Prowess cells (the spec's own "(bo3 played-out)" labels in Section 3). "Insert live before com"
   (Section 4c) would re-anchor combo cells but SILENTLY NO-OP on Affinity -- the +4.83pp G4 dominant term.
   FIX: name BOTH insertion points -- (a) live-before-com in `_run_combo`, AND (b) a live/db lookup ABOVE
   the Path A bo3 branch at L162, overriding a played-out bo3 with paper.

2. **Untapped is INERT for Modern.** `get_untapped_matchup_matrix` returns `{}` for modern (`_FORMAT_MAP`
   untapped_queries.py:69-75 omits modern; L94-96 -> {}). MTGA has no Modern format. FIX: mark untapped
   inert-for-v0 / PAPER-ONLY for Modern in Section 4a + Step 2 (don't wire a silently-empty source). OQ#1's
   "keep untapped" is vacuous for Modern.

3. **G4 is NOT an accuracy test.** It validates arithmetic re-derived from the same sparse anchors it wires
   in (-1.29pp -> ~61.6%). FIX: relabel G4 a WIRING/REPRODUCTION check, not a "load-bearing accuracy gate";
   the ~61.6% FWR is DIRECTION-ONLY and must NOT be quoted as a headline.

4. **Provisional tier under-guarded.** n=10-18 point estimates (Wilson +/-25-30pp) can be NOISIER than the
   com-sampler they replace, with zero gate proving the swap improves calibration. FIX: provisional cells
   are FLAGGED / SHRUNK-toward-prior, NOT hard-replaced; only n>=20 (trustworthy) hard-replaces + unflags.
   (Codex core rec + Seat B.)

5. **Eldrazi Tron in G4.** The required-movers criterion hard-requires Eldrazi Tron DOWN (-53.5pp), but
   imperfection #2 says that number is uncalibrated / possibly a naming artifact and OQ#5 defers its mapping
   to Step 1. FIX: remove Tron from the required-movers criterion, or gate it behind OQ#5 resolving clean.

6. **Field-weight dependency (connects to the MTGGoldfish gap).** G4 multiplies every re-anchored cell by an
   ESTIMATED field weight (mtg-sim format_config = "documented best-estimate, not a pulled snapshot"; a
   field-share shift alone moved one cell's FWR contribution 8.61pp). So OQ#1's "field refresh is NOT a
   WP-F#2 dependency" CONTRADICTS G4's actual dependence on those weights. FIX: add a field-weight
   sensitivity note / stop-condition to G4, and acknowledge current field WEIGHTS have no live refresh source
   (MTGGoldfish field-share scraper is unbuilt, ROADMAP.md:63) -- this is the real gap the user's MTGGoldfish
   instinct pointed at (weights, not matchups). Consider building that scraper as a paired follow-on.

7. **Minor.** G4 dead-band [62.5%, 62.9%) is neither PASS nor FALSIFIED -- add a tiebreak. Correct the named
   seam candidates (full_field_gauntlet/bo3_gauntlet/gauntlet_any_deck) to the ACTUAL seam (run_matchup.py).

Verdict: SOUND foundation, execution-ready AFTER fixes 1-7. Not a redesign -- prose/wiring/gate corrections.
