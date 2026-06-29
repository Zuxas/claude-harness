---
title: Mulligan parameter sweep -- IMPLEMENTATION PLAN (grounded)
status: PROPOSED
created: 2026-06-28
updated: 2026-06-28
project: mtg-sim
scopes_spec: harness/specs/2026-04-30-mulligan-parameter-sweep.md
related_imperfections:
  - mulligan-threshold-not-empirically-validated (IMPERFECTIONS.md:365)
  - mulligan-logic-portfolio-gap (IMPERFECTIONS.md:116)
estimated_time: see Effort section
recommendation: build-after-deps
---

# Implementation Plan: Mulligan Parameter Sweep

This is an execution plan that SCOPES the 2026-04-30 spec against the real code as it
exists on 2026-06-28. It is grounded in line-cited reads of the engine, APLs, and the
existing gauntlet harnesses. It does NOT edit any code under `mtg-sim/` (that tree is
READ-ONLY for this workflow; a concurrent workflow is writing under `mtg-sim/apl/`).
It records exactly what a careful engineer must build, in what order, and the
non-obvious traps the real code reveals.

The headline finding (Gotcha G1 below) materially changes the spec: **the canonical
WR engine does not call `keep()` at all**, so the spec's "measure WR" goal cannot be
satisfied through the canonical gauntlet until an engine prerequisite lands. The plan
is written around that reality.

---

## Goal (one sentence)

Build a parametric mulligan-threshold sweep that varies `(min_lands, min_keep_cards,
max_mulligans)` for an archetype and measures the resulting win rate -- mirroring the
Affinity `COUNTER_COST` env-var sweep pattern -- then apply the winning thresholds to the
SHIM/SHALLOW APLs, with a no-regression guarantee.

---

## What the spec said vs. what the code actually supports

The 2026-04-30 spec (`harness/specs/2026-04-30-mulligan-parameter-sweep.md`) proposes
a 27-combo x 4-deck x 50,000-goldfish-game design measuring **avg kill turn**. Two of
its load-bearing assumptions are wrong against the current tree:

1. It calls the runner `run_goldfish_set()`. **No such function exists.** The goldfish
   entry point is `run_simulation()` in `engine/runner.py:123`.
2. It measures mulligan quality by **goldfish avg kill turn**. The orchestrator
   directive for this plan ("measure WR; mirror the Affinity COUNTER_COST sweep") and
   the Nettle 2-1-2 finding are both about **win rate against opponents**, which goldfish
   (no opponent, no interaction, no aggro clock) structurally cannot represent. Goldfish
   rewards loose keeps (more cards kept -> faster goldfish kill) -- the opposite of what
   real mulligan discipline optimizes. See Gotcha G2.

This plan therefore: keeps goldfish as a **cheap calibration/pre-filter**, and makes the
**primary metric field-weighted match WR** via the real two-player engine -- the genuine
Affinity mirror. That convergence is also cheaper than the spec's 5.4M-game goldfish grid.

---

## The Affinity COUNTER_COST pattern (the thing we are told to mirror)

Ground truth, from `apl/affinity_match.py:58-60`:

```python
COUNTER_COST = int(os.environ.get("AFFINITY_COUNTER_COST", "2"))  # Phase-2 sweep winner (n=300:
                  # 0->42.0 1->42.0 2->42.3 3->41.9; all within noise, no regression vs 41% baseline).
```

The pattern, decoded:
- A single tunable is read from an **environment variable** with a default, as a
  module-level constant.
- A driver runs the **existing two-player gauntlet** (`engine.match_runner.run_match`,
  the canonical FWR engine) at small N (n=300/matchup) once per env value.
- The resulting field WR per value is recorded in a code comment, and the winner becomes
  the new default.
- **Crucial detail:** `COUNTER_COST` flows into `reserve_mana()` (`affinity_match.py:296-303`)
  -- it changes *in-game play*, which the match engine fully executes. That is why the
  sweep produced (small) signal. A mulligan-keep knob does NOT flow into in-game play; it
  flows into `keep()`, which the canonical engine never calls (Gotcha G1). This is the
  single most important difference between the thing we are told to mirror and the thing
  we are asked to build.

Also note the honest outcome the Affinity comment records: at n=300 **all four values were
within noise**. A mulligan WR sweep is at real risk of the same null result, and match
games are far slower than goldfish. Plan for "no signal" as a likely Gate-1 result and
size N accordingly (Gotcha G6).

---

## The three divergent mulligan code paths (read these before writing anything)

There are THREE independent mulligan implementations. They disagree on whether `keep()`
is consulted, on the mulligan cap, and on draw mechanics. This is the crux of the plan.

| Path | Location | Calls `apl.keep()`? | Cap | Draw mechanic |
|---|---|---|---|---|
| Goldfish | `apl/mulligan.py:39 take_opening_hand`, invoked by `apl/base_apl.py:81` | YES (`self.keep`, or `self.keep_vs` if opp set) | param `max_mulligans` default 4 -- but `run_game` never passes it, so always 4 | London: redraw 7 each time, bottom N on keep |
| Match-engine | `engine/match_engine.py:35 _do_mulligan` | YES (`apl.keep`) | hardcoded `range(3)` (mull to 4) | Paris-ish: draw `7 - mulligans` |
| **Match-runner (CANONICAL FWR)** | `engine/match_runner.py:1554-1575` (inline in `run_match`) | **NO -- keep() is dead code here** | hardcoded `range(3)` | draws `max(4, 7 - mulls - 1)`, mulls only if `lands < 2` |

Confirmed canonical path: `scripts/full_field_gauntlet.py:56`, every `rc_*`/`hill_climb_*`
script, and `scripts/ab_counterspells.py:39` all import `from engine.match_runner import
run_match`. The Affinity sweep used this engine. `engine/match_engine.run_match` is the
minority/legacy path (used by `api/sim_api.py`, `engine/variant.py`, `engine/meta_solver.py`,
`engine/bo3_match.py`, `engine/parallel_match.py`).

### Gotcha G1 (BLOCKER): the canonical WR engine ignores keep()

`engine/match_runner.py:1554-1575` mulligans with a hardcoded inline rule (`lands < 2`,
cap 3) and **never calls `apl.keep`, `apl.bottom`, `keep_vs`, or any threshold**. Therefore
a mulligan-threshold sweep run through the canonical gauntlet (`full_field_gauntlet` /
`run_match` from `match_runner`) will return **identical WR for every threshold combination**
-- pure noise, zero signal -- because the swept variable is not on the code path.

Consequence: a true Affinity-style WR sweep is **blocked on an engine prerequisite**:
the inline mulligan block in `match_runner.run_match` must first be refactored to consult
`apl.keep`/`apl.bottom` (ideally extracted into a single overridable
`_do_mulligan_runner(gs, side, apl, result)` function so the sweep can monkeypatch it,
mirroring how the Affinity knob was injectable). That is an `engine/` change = P0 human
work per the ARL contract ("Does not modify engine/ files"). It is READ-ONLY for this
workflow and out of scope for the concurrent `apl/` workflow.

### Gotcha G2: goldfish is a weak proxy for mulligan WR

`engine/runner.py:run_simulation` -> `base_apl.run_game` has no opponent. A flooded or
spell-only keep is punished only by self-inflicted mana screw/flood, never by an opponent's
clock or interaction. The Nettle 2-1-2 result is a WR result; goldfish cannot reproduce its
*ranking* logic (looser keeps tend to goldfish faster). Use goldfish only to (a) validate the
sweep harness mechanically and (b) cheaply prune obviously broken combos -- not to choose the
final threshold.

### Gotcha G3: `max_mulligans` is not reachable from `run_simulation`

`apl/base_apl.py:81` calls `take_opening_hand(...)` WITHOUT `max_mulligans`, so the goldfish
path is pinned to the function default 4 (`apl/mulligan.py:46`). To sweep the cap on the
goldfish path you must monkeypatch the module global `apl.base_apl.take_opening_hand`
(it is imported by name at `apl/base_apl.py:19`, so `run_game` resolves the module global).
Bind a partial: `base_apl.take_opening_hand = functools.partial(orig, max_mulligans=mm)`.
On the match-engine path the cap is the literal `range(3)` in `_do_mulligan`; on the
match-runner path it is `range(3)` inline. Neither can be varied without a code edit /
monkeypatch of those exact sites.

### Gotcha G4: the three paths give the SAME threshold different behavior

Goldfish redraws a full 7 each mulligan and bottoms N (London); both match paths draw a
shrinking hand (`7 - mulls`). A `(2,1,2)` threshold therefore selects different hand-size
distributions per path, so a "winner" found on goldfish does NOT transfer 1:1 to a match
engine. Any threshold validated on one path must be re-confirmed on the path it will run in.

### Gotcha G5: "min_creatures" must be derived from card type, not name constants

The spec proposes scraping module-level `CARD_NAME` constants for KEY_CARDS. That is fragile
and inconsistent across APLs (e.g. `affinity_match.py` uses a hand-built `ARTIFACTS`/threats
set; many SHIMs define no constants). Use the Card API instead: `Card.is_land()`
(`data/card.py:142`) and `Tag.CREATURE` (`data/card.py:21`, set in `_populate_tags`
`data/card.py:110-117`). A robust parametric keep = `min_lands` lands AND `min_keep_cards`
non-land cards of a chosen role (default: creatures via `c.has(Tag.CREATURE)`; allow a
`--key-tag` override for ramp/combo where the "keepable" card is a payoff, not a creature).

### Gotcha G6: noise floor and N

Detecting a ~2pp WR difference near p=0.5 needs roughly n >= 1,500-2,500 games per cell per
matchup (binomial SE ~ 1.1-1.3pp at n=1,500). The Affinity comment shows even real
in-game knobs sat inside noise at n=300. Match games are ~10-50x slower than goldfish, and
the grid is 27 cells. Budget accordingly and gate hard on Boros calibration before scaling.

### Gotcha G7: SHIM/SHALLOW target list is GOLDFISH APLs, not match APLs

`IMPERFECTIONS.md:119` explicitly corrects this: the 16 SHIM/SHALLOW APLs are the
**goldfish** APLs (used by `sim.py` + `apl_tuner.py`), NOT the canonical
`MATCH_APL_REGISTRY` variants the FWR gauntlets use. So "sweep the 16 APLs and measure WR"
is internally contradictory: those 16 have no WR (they don't play two-player games). The
apply targets and the WR-measurement targets are DIFFERENT objects. Decide per-track
(below) and state it in the executed spec.

### Gotcha G8: cached real_matrix masks engine changes

`bo3_gauntlet.py:88-145` builds G1 WR from `MetaBridge.real_matchup_matrix()` (cached real
data) when available, else from a goldfish kill-dist race vs static `ARCHETYPE_CLOCKS`. It
does NOT run two-player games for G1. So **do not** use `bo3_gauntlet.py` as the sweep
harness: keep changes can't move cached matchups at all, and only nudge the goldfish race
otherwise. Use `engine.match_runner.run_match` / `run_match_set` directly (after the G1
prerequisite lands), wrapping the field-weighting math from `full_field_gauntlet.py:145-172`.

### Gotcha G9: ASCII-only + env conventions

Per `mtg-sim/CONVENTIONS.md` and project CLAUDE.md: all terminal output ASCII-only (the
existing `runner.py` summary uses box-drawing chars in file strings only, never in the new
script's `print`s); run python with `PYTHONIOENCODING=utf-8`; set `sys.path` from repo root
(`SIM_ROOT = dirname(dirname(abspath(__file__)))`), matching `scripts/arl_profile.py:92-98`.

---

## Files to change

Nothing in this workflow (READ-ONLY tree). The plan below is what the FUTURE executor
(running inside `mtg-sim/` once the concurrent `apl/` work settles) will create/edit:

- NEW `mtg-sim/scripts/mulligan_sweep.py` -- the sweep harness (no conflict; new file).
- PREREQUISITE EDIT `mtg-sim/engine/match_runner.py` -- extract the inline mulligan block
  (lines ~1554-1575) into an overridable `_do_mulligan_runner(...)` that consults
  `apl.keep`/`apl.bottom`; P0 human/engine work, must precede the WR track. (Out of scope
  for the concurrent apl/ workflow.)
- APPLY-PHASE EDITS `mtg-sim/apl/<deck>.py` and/or `apl/<deck>_match.py` -- write validated
  thresholds. MUST wait for the concurrent `apl/` workflow to finish to avoid collisions.
- NEW findings doc `harness/knowledge/tech/mulligan-thresholds-2026-06-28.md` (harness tree;
  this workflow MAY write under harness/, but defer until results exist).
- UPDATE `harness/IMPERFECTIONS.md` entries 116 + 365 on completion.

---

## Approach (build order)

### Track A -- Goldfish sweep harness + calibration (buildable now; no deps)

A1. Create `scripts/mulligan_sweep.py` with `sys.path` + `PYTHONIOENCODING` setup per G9.

A2. Resolve the APL via `apl.get_apl(deck_name)` (the goldfish registry; same resolution
    `sim.py:_resolve_apl_from_deck` uses) and load the deck via
    `data.deck.load_deck_from_file`.

A3. Parametric keep injection (per G5):
    ```python
    def make_keep(min_l, min_k, key_tag):
        def keep(hand, mulligans, on_play):
            if len(hand) <= 4:
                return True
            lands = sum(1 for c in hand if c.is_land())
            keepers = sum(1 for c in hand
                          if not c.is_land() and c.has(key_tag))
            return lands >= min_l and keepers >= min_k
        return keep
    apl_instance.keep = make_keep(min_l, min_k, Tag.CREATURE)
    ```
    (Override the *instance* attribute; `base_apl.run_game:80` reads `self.keep` when no
    opp_archetype is set, which is the goldfish case.)

A4. max_mulligans injection (per G3): monkeypatch `apl.base_apl.take_opening_hand` with a
    `functools.partial(orig, max_mulligans=mm)` for the duration of each cell; restore after.

A5. For each cell in the grid run `run_simulation(apl, deck, n=N, on_play=..., seed=fixed)`.
    Record from `SimulationResults`: `win_rate()` (goldfish "win" = reached lethal within
    max_turns), `avg_kill_turn()`, `median_kill_turn()`, `win_by_turn(3/4/5)`,
    `avg_mulligans()`, `mull_rate()`. Note goldfish `win_rate` is "did it goldfish-kill in
    time", NOT match WR -- label columns honestly.

A6. Grid + output: grid `min_lands in {1,2,3} x min_keep in {0,1,2} x max_mulls in {1,2,3}`
    (27 cells). Sort by the chosen objective; emit a `--csv` (mirror the comment-table style
    of the Affinity sweep) and an ASCII ranking table.

A7. **Gate 1 (calibration), per spec:** run Boros Energy first. The deck's existing keep
    (`apl/boros_energy.py`) is the known-good reference. Acceptance: a `(2,1,2)`-style aggro
    threshold lands near the top of the goldfish ranking AND looser/stricter rows degrade as
    predicted. Stop trigger: 2-1-2 not near top -> harness bug, investigate before scaling.
    Treat "all rows within noise" as an expected, reportable outcome (G6), not a pass.

### Track B -- True WR sweep (BLOCKED on engine prerequisite)

B-pre (signal test, buildable NOW, no B0 needed): `engine.match_engine.run_match_set`
    runs REAL two-player games AND honors `apl.keep` (`match_engine.py:45` calls `apl.keep`;
    `:330-331` calls `_do_mulligan` from `run_match`). It is the minority/legacy engine, so
    its absolute FWR will NOT match canonical (`match_runner`) numbers and results are NOT
    production-applicable until B0 -- but it is the correct cheap gate to answer "is the
    mulligan-threshold WR signal real enough to fund the B0 refactor?" (strictly better than
    goldfish for that decision, since it has a real opponent + interaction). Run the Boros
    grid through `match_engine.run_match_set` first; only fund B0 if a relative WR spread
    above noise appears here.

B0. PREREQUISITE (engine/P0): refactor `match_runner.run_match` mulligan (lines ~1554-1575)
    to call `apl.keep`/`apl.bottom` via an overridable `_do_mulligan_runner(...)`. Without
    this, Track B measures nothing (G1). This is human-approved engine work.

B1. After B0: in `mulligan_sweep.py` add a `--mode match` that, per cell, monkeypatches
    `engine.match_runner._do_mulligan_runner` (or sets the parametric keep on the match APL
    instance via `apl.get_match_apl(key)`), then runs the field via `run_match` /
    `run_match_set` and computes field-weighted WR by reusing the weighting math at
    `full_field_gauntlet.py:145-172` (field shares from `MetaBridge`/`get_field`). Parallelize
    with `ProcessPoolExecutor` exactly like `full_field_gauntlet._run_matchup_job`.

B2. Pin seeds across cells (same opponents, same on_play split) so WR deltas are attributable
    to the threshold, not seed variance -- this is what made the Affinity n=300 comparison
    legitimate.

B3. Size N per G6 (>= 1,500/matchup); start with the Boros calibration deck only, confirm
    signal exceeds the noise band before running the full grid x field.

### Track C -- Apply + no-regression (BLOCKED on concurrent apl/ workflow + Track A/B results)

C1. Wait for the concurrent `mtg-sim/apl/` workflow to finish (file-collision risk).

C2. For each target APL, replace the SHIM/SHALLOW keep with the validated threshold. Per G7,
    keep the two tracks separate: goldfish-APL thresholds (the 16 SHIM/SHALLOW from
    `mulligan-logic-portfolio-gap`) validated on Track A; match-APL thresholds validated on
    Track B. Do not cross-apply a goldfish-validated number to a match APL without
    re-confirming on the match path (G4).

C3. **Affinity-style invariant + no-regression gate:** when the new threshold equals the
    APL's prior threshold, the harness MUST reproduce the prior baseline byte-for-byte at the
    same seed/N (proves the injection path is faithful). For changed thresholds, require
    goldfish `avg_kill_turn` within 0.1 turns (spec Gate 3) AND, for match APLs, FW WR no
    worse than baseline beyond noise. Commit per deck in batches of 3-4 (spec T.5).

C4. Run `harness/scripts/drift-detect.ps1` -> 0 new errors (spec Gate 4). Update
    IMPERFECTIONS 116 + 365; write the findings doc.

---

## Validation gates (grounded)

| Gate | Metric source | Acceptance | Stop trigger |
|---|---|---|---|
| 1 calibration | Track A, Boros, `run_simulation` | 2-1-2 near top of goldfish ranking OR documented "within noise" | 2-1-2 demonstrably bad -> harness bug |
| 2 signal check | Track B, Boros, `run_match_set` FWR | WR spread across grid > noise band at chosen N | no spread -> sweep is null; STOP, do not scale (record like Affinity) |
| 3 no-regression | Track C per-APL | goldfish avg_kill_turn within 0.1t; match FW WR not worse beyond noise | regression -> revert that APL, defer |
| 4 drift clean | `drift-detect.ps1` | 0 new errors | new errors -> investigate |
| Invariant | Track C | threshold==old reproduces baseline at same seed | mismatch -> injection path is wrong, fix before trusting any cell |

---

## Byte-identical / no-regression concerns

- The sweep script is purely additive (new file) and uses temporary, restored monkeypatches;
  it changes no on-disk APL during measurement. No byte-identical concern for Track A/B infra.
- The engine prerequisite (B0) is intentionally behavior-changing for the match mulligan: it
  must be landed behind its own no-regression check (FWR of the existing canonical field
  unchanged beyond noise when the *current* hardcoded rule is expressed through the new
  overridable function with default thresholds). This is a real regression surface -- changing
  how the canonical engine mulligans will shift every FWR number on record.
- The apply phase (C) is *deliberately* behavior-changing; the byte-identical guard is the
  "threshold==old reproduces baseline" invariant (C3), exactly the discipline the Affinity
  comment encodes ("no regression vs 41% baseline").

---

## Effort

- Track A (goldfish harness + Boros calibration): ~2-3 hrs build + ~0.5-1 hr compute.
- Track B prerequisite B0 (engine refactor, P0 human + its own validation): ~2-4 hrs.
- Track B sweep (after B0): ~1-2 hrs build + multi-hour compute (27 cells x field x N>=1500;
  parallelized).
- Track C apply + no-regression batches: ~0.5-1 hr per affected deck, batched in nightly.
- Total to a real, WR-grounded result: ~8-12 hrs engineering across tracks + significant
  compute, gated by the engine prerequisite and the concurrent apl/ workflow.

---

## Do / Defer recommendation: BUILD-AFTER-DEPS

- **Track A is buildable now** and is genuinely useful: it delivers the harness, the Boros
  calibration (spec Gate 1), and a cheap pre-filter. Recommend building it first; it has no
  dependency on the concurrent apl/ workflow (new file in `scripts/`).
- **Track B (the actual "measure WR, mirror Affinity" goal) is BLOCKED** on the engine
  prerequisite B0 (canonical mulligan must call keep -- Gotcha G1). Until B0 lands, any WR
  sweep is measuring a dead code path. B0 is P0 human/engine work and cannot be done by the
  concurrent apl/ workflow.
- **Track C (apply) is BLOCKED** on (a) Track A/B results and (b) the concurrent apl/
  workflow finishing (collision risk in `apl/`).
- There is also a real chance (per the Affinity n=300 null result, G6) that the WR sweep
  finds no signal above noise -- in which case the correct outcome is to record that, like
  Affinity did, and NOT churn the APLs. Build Track A, gate on Boros, decide whether B0 is
  worth funding based on the Track B-pre signal test (`match_engine.run_match_set`, real
  two-player games that honor keep) -- a far better fund/don't-fund gate than goldfish, and
  runnable today without the B0 engine refactor.

---

## Pre-flight reads for the executor

1. This plan.
2. `harness/specs/2026-04-30-mulligan-parameter-sweep.md` (original spec).
3. `apl/mulligan.py` (goldfish keep path), `apl/base_apl.py:60-148` (run_game wiring).
4. `engine/match_runner.py:1529-1624` (canonical match; the inline mulligan to refactor).
5. `engine/match_engine.py:35-64` + `292-331` (legacy match path that DOES call keep).
6. `apl/affinity_match.py:56-60, 296-303` (the pattern to mirror) + `scripts/ab_counterspells.py`.
7. `scripts/full_field_gauntlet.py` (canonical FWR harness + field-weighting to reuse).
8. `harness/IMPERFECTIONS.md` entries 116 + 365.
9. `harness/knowledge/tech/spec-authoring-lessons.md` (Rule 5: gate predictions must account
   for SIM-vs-DB source per matchup -- directly relevant to G8).

## Changelog
- 2026-06-28: Created. Grounded scoping of the 2026-04-30 spec; surfaced G1 (canonical WR
  engine ignores keep) as a blocker, demoted goldfish to pre-filter, split into A/B/C tracks,
  recommendation build-after-deps.
