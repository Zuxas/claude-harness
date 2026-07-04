---
title: "Oracle-driven priority responses -- EXECUTION spec (retire the counter/removal whitelists)"
status: "PROPOSED"
created: "2026-07-04"
updated: "2026-07-04"
project: "mtg-sim"
branch: "modern-postban-arc"
estimated_time: "M, ~1.5-2 working sessions for Stages 3-4 (Stages 0-2 already SHIPPED @ 452923a). ~6-9 hr work + ~1.5-2 hr sim runtime. Excludes the mandated 100k canonical re-anchor, a separate gated hot-zone step."
related_findings:
  - "harness/knowledge/mtg/sim-calibration-2026-07-01.md (the n=5000 battery -- Gate 1 anchors)"
  - "harness/knowledge/tech/calibration-probe-2026-07-01.md (earlier same-direction n=2000 probe; P1 13.1%)"
  - "E:\\vscode ai project\\AUDIT-ENGINE-APL-2026-07-01.md (Part A #2 whitelists; A.5 the 13 global-random sites)"
  - "2026-07-01 decision_api MCTS-readiness audit (fork x counter-window hidden-hand leak)"
related_specs:
  - "harness/specs/2026-07-01-b1-legal-action-api.md (RESUME-TRIGGERED PROPOSED remainder; Step 6 RNG-threading co-owns the baseline re-anchor -- see Sequencing)"
related_commits: ["452923a (Stages 0-2: classifier + golden + coverage, gated OFF)"]
supersedes:
  - "harness/specs/2026-07-01-oracle-driven-responses.md"
  - "harness/specs/2026-07-02-oracle-driven-responses.md"
superseded_by: null
---

# Spec: oracle-driven priority responses -- EXECUTION plan

**GOAL (one sentence):** Retire whitelist MEMBERSHIP as the response-legality source
by wiring the already-landed oracle-text CAPABILITY classifier into the engine's
priority/response windows behind `WANTS_ORACLE_RESPONSES`, then flipping the gate ON,
for the derivable v1 subset (instant/flash counters + instant-speed spot removal).

This is the single executable plan. It CONSOLIDATES and SUPERSEDES the two prior
PROPOSED specs:
- 2026-07-01 supplies the classifier pattern grammar, golden-test-against-the-table
  discipline, and stop-condition philosophy.
- 2026-07-02 supplies the n=5000 battery evidence, the hard Gate-1 calibration band,
  the determinism / no-decision-change gates, the capability-vs-policy seam, the cache
  design, and the risk register.

Stages 0-2 of that combined plan ALREADY SHIPPED at mtg-sim `452923a`. This spec executes
the REMAINDER: Stage 3 (gated consultation swap) and Stage 4 (gate battery + honest
write-up + gate flip). Nothing below re-derives the classifier; it is a finished, tested,
GATED-OFF module and this spec turns it on behind `WANTS_ORACLE_RESPONSES`.

---

## LANDED ARTIFACT (where execution resumes FROM)

Stages 0-2 SHIPPED at mtg-sim `452923a` on `modern-postban-arc` (executed @ `3ed5d98`):

- **Module:** `mtg-sim/engine/response_capability.py` -- pure
  `capabilities(card) -> tuple[ResponseCapability, ...]`; 9 kinds (COUNTER_ANY /
  COUNTER_NONCREATURE / COUNTER_CREATURE / COUNTER_CMC_COND / COUNTER_UNLESS_PAY_N /
  REMOVAL_DMG_N / REMOVAL_DESTROY / REMOVAL_EXILE / BOUNCE). oracle_id-keyed
  process-lifetime cache; RNG-free; ZERO game-state access. Consumption helpers
  `counter_matches(cap, spell)` and `removal_spec_from(caps)` also live here (the
  Stage-3 surface; do not re-implement them).
- **Gate switch:** `GATE_ATTR = "WANTS_ORACLE_RESPONSES"` + gate function
  `oracle_responses_enabled(self_apl, opp_apl)` (module lines ~67-77), mirroring the
  `WANTS_PRIORITY_STACK` / `WANTS_INSTANT_COMBAT` gate shape. Default OFF.
- **How it is switched OFF today:** structurally, not by a flag branch. NO live engine
  path imports `response_capability`, so gate-OFF byte-identity holds BY CONSTRUCTION.
  `mtg-sim/tests/test_response_capability.py` (lines ~30-31) asserts that no-live-import
  guarantee exhaustively alongside the golden whitelist reproduction. Flipping ON means:
  add the Stage-3 consultation imports behind `oracle_responses_enabled(...)`, then set
  the gate attr True on the target APLs.
- **Stage-0 pin:** `mtg-sim/data/response_baseline_2026-07-02.json` (P1 5.3%, normalized
  P1-cell sha256 `b76c3711...`, byte-stable across 3 runs). Raw battery JSON/logs
  gitignored/local-only. Coverage tail: `mtg-sim/data/response_coverage.csv`.

---

## Scope

### In scope (v1) -- counters + instant-speed spot removal ONLY
- Counterspells at instant speed (COUNTER_* family) -- capability legality sourced from
  `capabilities(card)` instead of `c.name in COUNTER_VALIDITY`, behind the gate.
- Spot removal (damage / destroy / exile / bounce) at instant OR flash speed --
  `(cmc, max_tgh)` spec derived via `removal_spec_from(caps)` instead of read from
  MATCH_REMOVAL, behind the gate, for instant/flash cards only.
- The gated consultation swap at the site families named in Step 3, then the gate flip.
- The gate battery (Step 4) and an honest findings write-up.

### Explicitly OUT of scope
- **Replacement effects** -- different rules machinery; nothing in the response windows
  consults them today. Follow-up spec only if calibration debt survives v1.
- **Trigger ordering** -- infrastructure exists but has no engine call site; wiring it is
  not response work.
- Board wipes / sorcery-speed removal -- stay MATCH_REMOVAL-table-driven; the main-phase
  `_match_cast_removal` sorcery path is untouched.
- Modal spells beyond first mode, counter-abilities on permanents, alt/pitch costs, {X}
  costs, cost-reduction statics -- classifier already leaves these NOT-DERIVED and they
  keep their whitelist entries (golden test pins each so nothing drifts). v1 therefore
  does NOT fully retire the whitelists -- the derivable subset moves to capability, the
  tail stays whitelisted as fallback. Full retirement is the arc, not v1.
- Response POLICY quality (value gates, `_PRIORITY_COUNTER_TARGETS` eagerness, mana
  hold-up) -- APL/search territory (B1). This spec changes CAPABILITY, not judgment.
- The 13 global-random sites themselves -- B1 Step 6 territory; this spec must add ZERO
  new ones (Risk 1).

---

## Pre-flight reads (MANDATORY -- read before Step 1)

The two consolidated specs' combined eight, still current:
1. `harness/knowledge/tech/spec-authoring-lessons.md` (SPEC-FIRST Rule 1/9; the
   re-execution-baseline, load-path, parallel-entry-point, density-asymmetry, and
   stop-condition-aggregation lessons all bind here -- see "Lessons applied").
2. `mtg-sim/engine/response_capability.py` IN FULL (the SHIPPED classifier:
   `capabilities()`, `counter_matches()`, `removal_spec_from()`,
   `oracle_responses_enabled()` -- the Stage-3 consumption surface; do not re-implement).
3. `mtg-sim/engine/counter_resolver.py` IN FULL (COUNTER_VALIDITY L42;
   `_PRIORITY_COUNTER_TARGETS` L75 = POLICY, untouched; `try_counter_spell` L126,
   candidate-discovery loop L142-168).
4. `mtg-sim/apl/match_apl.py` L160-280 (MATCH_REMOVAL L165 semantics; `_match_cast_removal`
   L228, the `spec = self.MATCH_REMOVAL.get(card.name)` lookup at L247 -- the sorcery path
   stays; only instant/flash cards divert to the derived spec).
5. `mtg-sim/apl/aware_match_apl.py` `_kill_with_removal` L317 (MATCH_REMOVAL lookups at
   L332 and the end-step path L445).
6. `mtg-sim/engine/priority_stack.py` (run_priority_stack L294; the ZERO-RANDOMNESS hard
   constraint at L29-31 -- classification is pure load-time string work, so it holds).
7. `mtg-sim/engine/match_engine.py` WINDOW 1 (L497) / WINDOW 2 (L521); `WANTS_INSTANT_COMBAT`
   gate L190. PLUS `mtg-sim/engine/match_runner.py` (`run_match_set`) AND
   `mtg-sim/engine/bo3_match.py` (`run_bo3_set`) -- the parallel entry points that BOTH
   need the swap (parallel-entry-point lesson).
8. `harness/knowledge/mtg/sim-calibration-2026-07-01.md` (the Gate-1 anchors: P1 5.3%/47.6%,
   P2 71.5%/52.2%) + `mtg-sim/docs/action-vocabulary.md` #9/#10/#13 (RESPOND_* kinds the
   capability kinds map onto; #13 folds into #9).

PLUS, new for this execution spec:
9. `harness/specs/2026-07-01-b1-legal-action-api.md` -- READ THE 2026-07-04 DISPOSITION
   HEADER. B1's formal-API remainder (incl. Step 6 per-state RNG-threading) is now
   RESUME-TRIGGERED PROPOSED. Its Step 6 re-anchors every seeded baseline; so does gate-ON
   here. See "Sequencing vs B1" -- the re-baselines MUST be ordered.
10. `mtg-sim/data/response_baseline_2026-07-02.json` (Stage-0 pin `b76c3711...`) +
    `mtg-sim/data/response_coverage.csv` (SHIPPED coverage tail).

Verify-identifiers-before-execution (spec-authoring lesson): before pasting any run command
in Step 4, confirm the battery runner's real name/flags (the 07-02 battery used
`seed=42 PYTHONHASHSEED=0 n=5000`). The actual driver is
`tmp/calibration_rerun_2026-07-01.py` -- GITIGNORED/untracked, so a `git clean` LOSES it
and no committed path references it. Locate it via
`grep -rn "calibration_rerun\|n=5000" tmp mtg-sim/scripts` (NOT `sim_calibration`, which
does not name this driver) and read its argparse -- do NOT infer a filename. Per S3.0 this
driver MUST be PROMOTED + git-tracked into `mtg-sim/scripts/` before Stage 3 lands, so the
battery has a durable, committed invoker. Record the verified command in the Stage-3 first
commit message.

---

## Steps (ordered; resume from the gated-OFF classifier @ 452923a)

### Stage 3 -- gated consultation swap (M, ~3-4 hr)

The classifier and its consumption helpers already exist and are tested. Stage 3 wires the
live engine to consult them ONLY when `WANTS_ORACLE_RESPONSES` is set on either APL. Gate
OFF = legacy tables, byte-identical (holds by construction today because no live path
imports the module; Step 3.x must PRESERVE that under gate-OFF).

**S3.0.a -- Promote the battery driver (day-1 blocker, do FIRST).** The gate battery's
driver is `tmp/calibration_rerun_2026-07-01.py`, currently GITIGNORED/untracked -- a
`git clean` would lose it and no Stage-4 recipe can cite a committed path. Before any Stage-3
code lands: move/copy it to `mtg-sim/scripts/` (e.g. `mtg-sim/scripts/calibration_rerun.py`),
git-track it, and confirm its argparse (seed / PYTHONHASHSEED / n / cell selectors). All
Stage-3/Stage-4 run recipes reference the PROMOTED, tracked path -- never the `tmp/` copy.

**S3.0 -- Fresh baseline re-capture (MANDATORY, re-execution-baseline lesson).**
Re-run the Stage-0 pin at the CURRENT execution HEAD (not the 07-02 commit): P1 + P2,
n=5000, seed=42, PYTHONHASHSEED=0, gate default (OFF). Hash the normalized P1 cell; compare
to `response_baseline_2026-07-02.json` (`b76c3711...`). Small drift = engine evolution since
452923a (continue, record the delta); large drift = investigate before proceeding. This
fresh baseline -- not the 07-02 documented numbers -- is Gate 2/3's byte-identity anchor and
Gate 1's `baseline +/- shift` reference. Also re-confirm the P2 pre-existing same-seed drift
(07-02 FINDING: 71.4/72.0/71.6) still reproduces -- it determines whether P2 is a
byte-identity or statistical-only instrument (it is statistical-only; see the byte-stability
carve-out).

**S3.1 -- Legacy counter window** (`game_state.py::cast_spell`, the try_counter call at
L1599-1600 -> `counter_resolver.try_counter_spell`). In `try_counter_spell`'s candidate loop
(L142-168): when `oracle_responses_enabled(self_apl, opp_apl)`, replace the
`c.name not in COUNTER_VALIDITY` skip and the `validity_fn, base_cmc = COUNTER_VALIDITY[c.name]`
lookup with `capabilities(c)` + `counter_matches(cap, spell)` for legality and `cap.cost` for
the base cmc. EVERYTHING else in `try_counter_spell` (mana affordability via
`_tap_lands_for_response`, cheapest-first ordering, the `_spell_value` value gate,
`_PRIORITY_COUNTER_TARGETS` eagerness at L99/L168) is POLICY and stays byte-unchanged.
Consultation is EITHER/OR per gate -- never both the table AND the classifier for the same
card (no double-counting).

**S3.2 -- Instant-speed removal lookups** (`match_apl.py::_match_cast_removal` L247;
`aware_match_apl.py::_kill_with_removal` L332 and end-step path L445). For a card whose
`type_line` is Instant OR that has Flash, when the gate is on: derive the spec via
`removal_spec_from(capabilities(card))` -> `(cost, max_tgh, conditions)` instead of
`self.MATCH_REMOVAL.get(card.name)`. REMOVAL_DMG_N -> `(cmc, N)` (exactly the existing
`(cmc, max_tgh)` toughness semantics); DESTROY/EXILE/BOUNCE -> `(cmc, None)` + conditions.
Sorcery-speed entries and board wipes stay table-driven (the non-instant branch is
untouched). Where a derived condition is present (e.g. "nonartifact", "mana value <= N"),
apply it via a SINGLE shared helper -- do NOT hand-roll condition enforcement at each site.
Implement a conservative `removal_matches(spec, target)` in
`mtg-sim/engine/response_capability.py` mirroring `counter_matches`'s unknown->False
semantics (any token/rider the grammar does not understand returns False, so the classifier
never makes something legal it does not understand). All THREE removal consultation sites
(`match_apl.py::_match_cast_removal` L247, `aware_match_apl.py::_kill_with_removal` L332, and
its end-step path L445) MUST call `removal_matches(spec, target)` for target legality instead
of each re-implementing the toughness/condition checks. Centralizing here removes the
false-positive illegal-target hazard of three divergent hand-rolled filters in a hot zone.

**S3.3 -- R1/R2 priority legality** (`priority_stack.py::run_priority_stack` L294, opt-in via
`WANTS_PRIORITY_STACK`; `match_engine.py` WINDOW 1 L497 / WINDOW 2 L521, gated by
`WANTS_INSTANT_COMBAT`). Where these windows decide whether a held card is a legal response,
consult the same capability table for LEGALITY only. priority_stack's ZERO-RANDOMNESS
constraint is preserved because classification is pure load-time string work (no random(),
no game-state read). Do NOT change what these windows CHOOSE (policy) -- only what they
consider legal.

**S3.4 -- Parallel-entry-point sweep** (parallel-entry-point lesson). Before declaring
Stage 3 done, grep for sibling call sites that also consult COUNTER_VALIDITY / MATCH_REMOVAL
by name and were NOT covered by S3.1-S3.3, AND confirm the swap lands in BOTH
`match_runner.run_match_set` and `bo3_match.run_bo3_set` loop bodies:
`grep -rn "COUNTER_VALIDITY\|MATCH_REMOVAL\|_PRIORITY_COUNTER_TARGETS" mtg-sim/engine mtg-sim/apl`.
Run the grep at HEAD -- expect ~39 files, mostly Standard-format APLs OUT of the Modern-arc
scope; triage each for in-scope wiring. Do NOT assume a fixed consumer list (a prior draft
named a `murktide_match.py` that does not exist). For each in-scope hit: EITHER wire the gated
swap (if it is a response-legality site) OR document why it stays table-only (if it is policy /
sorcery / archetype-specific / out-of-arc Standard). A partial swap that leaves one response
site on the table produces the "mostly-fixed with structured residual" symptom -- enumerate
every in-scope site.

**S3.5 -- Load-path check + production-path test** (load-path-dependent-setup lesson). The
classifier reads oracle text from the CardDB singleton keyed by oracle_id/name; confirm both
deck load paths (.txt via `data/deck.py` and the dict/stub path via `build_deck_from_dict`)
yield cards whose name/oracle_id resolves in CardDB so `capabilities()` is non-empty for the
whitelisted answers on BOTH paths. If stub-loaded opps resolve to empty capabilities, the
gate-ON effect is silently inert against that fraction of the field (3 of the Modern field
load via stub). Add a PRODUCTION-PATH test (not just synthetic) asserting a known answer
(e.g. a Dimir counterspell) derives its capability via EACH load path.

**S3.6 -- Relax the structural no-import test + mark the hidden-info leak.** Update
`test_response_capability.py` so the "no live path imports this module" assertion becomes
"no live path imports it WITH THE GATE OFF" (Gate 2 byte-identity by construction must still
hold). AND, at the counter-window read of `opp_gs.zones.hand` inside the caster's
`cast_spell` (Risk 2), add a `# HIDDEN-INFO READ (b1 observe() fence target)` marker + a
lightweight assert hook so B1's `observe()` work can find and fence it; record in
action-vocabulary #13's fold-in note. `capabilities()` itself is state-free (no leak added).

### Stage 4 -- gate battery + flip + honest findings (S-M, ~1-2 hr + sim runtime)

**S4.1** Set `WANTS_ORACLE_RESPONSES = True` on the P1/P2 target APLs; run the full gate
battery (Gates 1-9) at the execution HEAD, gate-OFF and gate-ON, seed=42, PYTHONHASHSEED=0,
n=5000 for the calibration cells AND for the Gate-9 field-wide no-regress cells S3.4 wired
(UW Control, Affinity, combo, + the flagged mismodeled cells the triage touched).
**S4.2** Update `mismodeled_matchups.py` entries HONESTLY using direction language -- NO
band-forcing, NO tuning classifier constants toward the band (measure, don't tune).
**S4.3** Write findings `harness/knowledge/mtg/oracle-responses-battery-2026-07-04.md` (or
nearest date): actual P1/P2 numbers, which gates passed, and -- if P1 lands a large rise but
misses the band -- WHICH residual (policy? mana? threat model?) owns the rest.
**S4.4** Gate flips ON as DEFAULT only if Gate 1 passes AND the ENGINE HOT-ZONE sign-off +
100k canonical re-anchor (below) are satisfied; otherwise ship gate-OFF-default with a
partial-confirm findings doc. Then update both superseded specs to SHIPPED with the commit
hash; add any methodology lesson per Rule 9; update IMPERFECTIONS.md, `harness/MEMORY.md`,
and `harness/specs/_index.md` (mark the two priors SUPERSEDED).

---

## Validation gates (FALSIFIABLE; predicted landing + why)

All calibration cells: n=5000, seed=42, PYTHONHASHSEED=0, on the execution HEAD, per S3.0
fresh baseline. Anchors from sim-calibration-2026-07-01.md.

> **BYTE-STABILITY CARVE-OUT (READ FIRST -- applies to Gates 2 and 3).** The 07-02
> execution FOUND that P2 (Izzet Prowess vs Mono Green Landfall) has PRE-EXISTING same-seed
> drift at HEAD with ZERO changes (71.4 / 72.0 / 71.6), traceable to the 13 global-random /
> id()-ordering sites -- it cannot byte-verify gate-OFF OR gate-ON, independent of this
> feature. Therefore the byte-stability INSTRUMENT for both Gate 2 and Gate 3 is the **P1
> cell only**; P2 is CARVED OUT as unsatisfiable-until-B1-Step-6-RNG-threading-lands. P2's
> Gate-1 no-regress is a statistical mean over 2+ runs vs the S3.0 fresh baseline, not
> byte-equality. This is a known limitation, not a gate failure.

### Gate 1 -- Calibration P1 (primary) + P2 no-regress [gate ON]
- **Where it should land + why:** P1 (Dimir Midrange vs Izzet Prowess), gate-ON, moves from
  **5.3% into [37.6%, 57.6%]** (+/-10pp of the 47.6% ladder anchor) WITHOUT P2 (Izzet
  Prowess vs Mono Green Landfall, same protocol) regressing past **+19.3pp over its 52.2%
  ladder truth** (nominal 71.5%). WHY: capability widening is SYMMETRIC across cards but
  shifts asymmetrically by INTERACTION DENSITY (density-asymmetry lesson) -- interaction-
  dense Dimir was simulated with a fraction of its real answer suite, so widening moves P1
  UP toward truth; interaction-light proactive Prowess is already fully modeled, so P2
  barely moves. That one mechanism justifies both predictions. Start P1 from the n=5000
  figure 5.3% (the 13.1% figure is the older n=2000 probe).
- **P2 no-regress is FRESH-BASELINE-RELATIVE, not a fixed cutoff:** gate-ON P2 mean must not
  exceed the S3.0 fresh-baseline P2 mean by more than its measured same-seed spread
  (~0.6pp per the 71.4-72.0 pre-existing-drift runs). A fixed <=71.5% threshold would
  false-positive-STOP on a run that merely reproduces baseline, because the pre-existing
  drift (mean ~71.67%) already straddles 71.5% (noise-floor-appropriate-aggregation lesson).
- **Partial-confirm rule:** the mechanism claim is "the whitelist is THE binding constraint
  on interactive-deck fidelity." A large P1 rise that MISSES the band is a PARTIAL-CONFIRM:
  ship gate-OFF (do not default gate-ON), and the findings doc names which residual owns the
  rest. NEVER tune classifier constants toward the band.

### Gate 2 -- Gate-OFF byte-identity (flag off => bit-identical to today) [gate OFF]
- **Where it should land + why:** with the gate OFF, the P1 cell (instrument) result JSON +
  normalized (timestamp-stripped) logs are byte-identical to the S3.0 fresh baseline. WHY:
  no live path consults the classifier when the gate is off (all Stage-3 imports sit behind
  `oracle_responses_enabled`), so the engine executes exactly the pre-change code. P2 carved
  out per the banner.

### Gate 3 -- Seeded-replay byte-stability WITH the gate ON [gate ON]
- **Where it should land + why:** the SAME gate-ON config run TWICE at the same seed
  produces byte-identical result JSON + normalized logs on the P1 cell. This is REPLAY
  determinism of the feature -- NOT gate-ON vs gate-OFF (those SHOULD differ; that difference
  is the feature working). WHY: classification is pure, cached, RNG-free string work; turning
  it on must not introduce a new RNG draw or id()-ordering. P2 carved out per the banner (its
  Gate-1 no-regress is statistical, not byte).

### Gate 4 -- Per-decision LOCALITY on NON-response code paths [gate ON]
- **Where it should land + why:** this is a PER-DECISION (per-node) check, NOT whole-trace
  equality. Whole-trace identity is UNSATISFIABLE by design: gate-ON legitimately fires more
  responses, so the game state diverges and downstream land/cast/attack lines differ by
  CORRECT propagation, not by leak. The falsifiable claim instead: for every non-response
  decision node -- action kinds MULL_*, RESERVE_MANA, PLAY_LAND, main-phase CAST,
  PUT_INTO_PLAY, ACTIVATE, ACTIVATE_PW, ATTACK, BLOCK, DISCARD -- given IDENTICAL input
  game-state at that node, the chosen action is IDENTICAL gate-ON vs gate-OFF. Instrument on a
  fixed 300-game trace slice by comparing decisions keyed on (normalized input game-state ->
  chosen action); only RESPOND_* / PASS_PRIORITY nodes are exempt. WHY: the capability swap is
  scoped to response windows; if the SAME proactive input yields a DIFFERENT proactive choice,
  the swap leaked into non-response logic. Divergent downstream states reached via a legitimate
  extra response are EXPECTED and are not a violation.

### Carried BY REFERENCE (07-01 gates -- SHIPPED at stages 0-2, re-confirm after wiring)

### Gate 5 -- Golden (whitelist reproduction; = 07-01 G1)
100% of currently-whitelisted cards classify to the same predicate + cost the tables encode
(ALREADY GREEN @ 452923a: 18 COUNTER_VALIDITY + 36 base + 15 ext, zero grammar-attributable
mismatches; 4 documented table-side deviations). RE-RUN after Stage-3 wiring to confirm no
regression.

### Gate 6 -- Coverage (= 07-01 G3)
>= 80% of instant/flash cards across decks/ ACCOUNTED (derived + whitelist-fallback + inert);
UNHANDLED tail listed in response_coverage.csv, never silently wrong (SHIPPED @ 452923a:
80.8% accounted, 31.7% strict-derived). Report the actual number honestly; a DROP in
accounted-% after wiring signals a load-path regression (S3.5).

### Gate 7 -- Conservation (= 07-01 G5)
10k-game gauntlet slice gate-ON: zero new exceptions, card-count invariant holds.

### Gate 8 -- Runtime budget
gate-ON P1 cell runtime <= baseline + 10% (baseline ~27.0-27.5s at 452923a; classification is
load-time + cached; design-2 cache-hit assert guards the inner loop).

### New for this execution spec (field-wide safety net)

### Gate 9 -- Field-wide no-regress over the cells S3.4 actually wires [gate ON]
- **Where it should land + why:** Gate 1 calibrates only P1 (rise) and P2 (flat), but flipping
  `WANTS_ORACLE_RESPONSES` changes counter/removal legality FIELD-WIDE, so any cell whose APLs
  S3.4 wires can move. Over the wired cells -- UW Control, Affinity, combo, PLUS every cell
  flagged in `mismodeled_matchups.py` that the S3.4 triage touches -- each cell's gate-ON mean
  must be NO WORSE than its S3.0 fresh-baseline mean by more than that cell's measured
  same-seed spread (no-regress band, fresh-baseline-relative, same construction as Gate 1's P2
  no-regress). "Worse" = a move AWAY from the cell's ladder/tournament truth where one is
  anchored; where no truth anchor exists, "worse" = any out-of-spread swing that is UNEXPLAINED
  (a widening-consistent move toward a documented direction is allowed and recorded, not
  failed). WHY: capability widening should move interaction-dense cells toward truth (like P1)
  and leave interaction-light cells roughly flat (like P2); a cell that regresses signals the
  swap mis-fires there. Report every wired cell's before/after honestly; do NOT tune classifier
  constants to hold a band (measure, don't tune). Gate-1's P1 signal is a full-cell
aggregate at n=5000 (Wilson half-width ~+/-0.7pp); the band is 10pp wide, so cell-level
aggregation is correct. Do NOT re-derive the stop at per-game or per-matchup granularity --
the signal lives at the cell aggregate.

---

## Stop conditions (with teeth -- STOP means STOP, per SPEC-FIRST Rule 4)

- **Gate-1 P1 outside [37.6%, 57.6%] gate-ON:** STOP. Below-but-risen = partial-confirm
  (ship gate-OFF, name the residual). Moved DOWN = mechanism falsified (findings, never ship
  gate-ON default). Never tune classifier constants toward the band.
- **Gate-1 P2 mean exceeds the S3.0 fresh-baseline P2 mean by more than its ~0.6pp same-seed
  spread, gate-ON:** STOP -- interaction widening must not make the proactive cell HOTTER;
  something is mismodeled; findings. (Fresh-baseline-relative, NOT a fixed 71.5% cutoff.)
- **Gate-2 P1 byte diff (gate OFF):** STOP -- a Stage-3 import leaked outside the gate; the
  gate-OFF path must be inert.
- **Gate-3 P1 byte diff (gate ON, replay):** STOP -- a new RNG draw / id()-ordering entered a
  path that must be deterministic. Do not ship a nondeterministic response path.
- **Gate-4 per-decision divergence gate-ON** (a non-RESPOND node choosing a DIFFERENT action
  from IDENTICAL input game-state): STOP -- the swap leaked into proactive decision logic; find
  the coupling before proceeding. Downstream game-state divergence reached via a legitimate
  extra response is NOT a stop trigger (whole-trace equality is not the instrument).
- **Gate-5 golden mismatch on >2 cards:** STOP -- pattern grammar is wrong; fix grammar,
  never special-case the golden set.
- **Classifier misfire -> illegal engine state** (targeting untargetable, wrong-timing cast):
  STOP; add the legality check at the CONSULTATION site (shared with B1's seam), then resume.
- **Parallel-entry-point residual** (S3.4: a structured same-seed residual isolated to one
  archetype/site after the swap): STOP -- an uncovered consultation site, not noise; wire or
  document it before Stage 4.
- **Gate-8 runtime > baseline +10%:** STOP -- the cache is not hitting; profile before ship.
- **Gate-9 any wired cell regresses gate-ON** (moves AWAY from its truth anchor, or takes an
  UNEXPLAINED out-of-spread swing, beyond that cell's same-seed spread vs the S3.0 fresh
  baseline): STOP -- the swap mis-fires in a field cell; find and document the cause before
  Stage 4. A widening-consistent move toward a documented direction is recorded, not a stop.

---

## ENGINE HOT ZONE -- sign-off + 100k re-anchor required (READ PROMINENTLY)

**This spec touches priority / response / combat-window decision logic in
`mtg-sim/engine`.** Per both CLAUDE.md hot-zone protocols, the following are HOT ZONES and
this work needs EXPLICIT USER SIGN-OFF before Stage 3 code lands and before the gate flips
ON as default:

- `engine/game_state.py::cast_spell` (S3.1 -- the counter window)
- `engine/counter_resolver.py::try_counter_spell` (S3.1)
- `engine/priority_stack.py` + `engine/match_engine.py` WINDOWS (S3.3)
- `engine/match_runner.py::run_match_set` + `engine/bo3_match.py::run_bo3_set` (S3.4)
- `apl/match_apl.py` / `apl/aware_match_apl.py` removal lookups (S3.2)

**Blast radius:** the counter window and removal lookups fire on EVERY game where either APL
opts in; a wrong capability derivation (false-positive answer, wrong cost, illegal target)
shifts every downstream goldfish/gauntlet/deck-choice cell for interactive decks. Reach is
the whole calibration battery and every mismodeled-matchup flag. Bounding mitigations:
(a) the gate defaults OFF -- Gate 2 gate-OFF byte-identity proves zero effect until a deck
opts in; (b) Gate 5 golden proves the whitelisted cards behave exactly as before;
(c) conservative unknown-token handling (`counter_matches` returns False on anything it does
not understand) makes the failure mode UNDER-firing (a known, measurable deficiency), not
illegal engine states.

**Documented 100k canonical baseline re-anchor (REQUIRED before merge of gate-ON default).**
This is SEPARATE from the n=5000 P1/P2 calibration instrument. The n=5000 cells prove the
calibration hypothesis; the 100k canonical re-anchor is the merge-gating evidence that the
field-wide seeded numbers are re-based against the new default. gate-ON changes HOW OFTEN
response code runs, which shifts the shared-RNG consumption pattern (Risk 1) -> same-seed
movement in unrelated cells is EXPECTED and is not a bug. Capture, hash, and commit the 100k
re-anchor artifact and cite it in the merge commit.

**PASS/FAIL (this is a gate, not descriptive re-basing).**
- **PASS requires BOTH:** (a) every KNOWN-GOOD cell (the calibration-anchored cells P1/P2 plus
  any cell already in-band at the S3.0 fresh baseline) stays IN-BAND at 100k -- no known-good
  cell falls out of its band; AND (b) NO cell shows an unexplained LARGE swing -- every cell
  that moves beyond its same-seed spread has a written attribution (shared-RNG re-consumption
  per Risk 1, or a widening-consistent move toward a documented direction). "Expected re-basing"
  is only a PASS when it is NAMED; a large swing with no attribution is a FAIL.
- **FAIL (any of):** a known-good cell drops out of band at 100k; OR any cell takes a large
  same-seed swing that cannot be attributed to shared-RNG re-consumption or documented widening.
  On FAIL, STOP -- do NOT merge gate-ON default; investigate the swing (RNG-threading confound
  vs a real capability mis-fire), document, and either amend or ship gate-OFF-default.

Until BOTH the sign-off AND a PASSING 100k re-anchor are satisfied, the gate stays OFF by
default and the work ships as a gate-OFF-default feature with a findings doc.

---

## Risk register (from the decision_api / B1 audit + 07-02)

1. **The 13 global-random sites** (AUDIT-ENGINE-APL A.5). Classification adds ZERO draws, but
   gate-ON changes how often response code executes -> shifts the shared RNG stream ->
   same-seed drift in unrelated cells. This is why P2 is statistical-only (byte-stability
   carve-out) and why S3.0 re-anchors. The real fix (per-state RNG) is B1 Step 6 -- FOLD INTO
   IT, do not duplicate here. Mitigation: Gate-2 gate-OFF byte-identity proves the OFF path
   untouched; Gate-3 keeps P1 as a clean byte instrument.
2. **Fork x counter-window hidden-hand information leak** (2026-07-01 decision_api
   MCTS-readiness audit). `try_counter_spell` reads `opp_gs.zones.hand` synchronously from
   inside the caster's `cast_spell`; `decision_api.fork()` clones both states, so a search
   expanding through a cast can read the opponent's REAL hand via this window, poisoning
   ISMCTS determinization. THIS SPEC WIDENS the window's firing surface (more cards classify
   as answers) -> an unwarded counter-response can leak more hidden information, more often.
   Mitigation: v1 keeps the window's SHAPE (leak no worse in KIND, only in frequency);
   `capabilities()` is state-free; S3.6 adds the `# HIDDEN-INFO READ` marker + assert hook
   for B1's `observe()` to fence; record in action-vocabulary #13. This is a KNOWN leak the
   spec FLAGS for B1, not one it closes.
3. **Capability widening under crude policy overshoots** -- with legality no longer scarce,
   respond-if-able heuristics may counter everything cheap and P1 blows past the band top.
   That is a POLICY finding (Gate-1 stop), NOT a license to narrow capability. Findings doc
   + policy follow-up spec (B1 search consuming `capabilities()` via `legal_actions()`).
4. **Grammar false positives** -- "counter target spell you control", damage-to-PLAYER-only
   misread as answers. Golden catches table cards only; mitigate with negative fixtures in
   the classifier test + the coverage-CSV eyeball pass. `counter_matches`/`removal_spec_from`
   conservative-unknown handling is the backstop.
5. **Load-path cache-warming under-classification** (load-path-dependent-setup lesson). If
   the classifier's inputs come from a per-card setup (tag_keywords / CardDB resolution) that
   runs on the .txt load path but SKIPS the dict/stub path, gate-ON silently UNDER-classifies
   stub-loaded opponents (3 of the Modern field). Mitigation: S3.5 production-path test.
6. **Perf** -- 164MB CardDB already resident; classification is load-time + cached. Guard:
   Gate 8 (+10% budget) + the design-2 cache-hit assert.

---

## Sequencing vs B1 (both re-anchor the seeded 100k baseline -- ORDER the re-baselines)

B1's formal-API remainder (2026-07-01-b1-legal-action-api.md, RESUME-TRIGGERED PROPOSED per
the 2026-07-04 council disposition) includes **Step 6: thread per-state RNG through the ~13
global-random consumers**, which per B1 gate G4 invalidates and forces a re-anchor of every
seeded baseline, and is itself an ENGINE HOT ZONE requiring separate sign-off.

Both this spec (gate-ON, Risk 1) and B1 Step 6 re-anchor the same seeded 100k baseline. They
MUST NOT run interleaved on the same baseline -- concurrent re-anchors produce CONFLATED
deltas that cannot be attributed to either change. Sequencing rule (the re-baselines MUST be
sequenced, one at a time):

- **This spec does NOT block on B1.** B1's remainder is parked behind a resume trigger and
  nothing consumes B1 today; this spec ships independently using **P1 as the byte-identity
  instrument** and **P2 as statistical-only**. It does NOT attempt to make P2 byte-stable --
  that is precisely B1 Step 6's job.
- **Order is a SIGN-OFF decision, not a verdict here.** Tradeoff: B1-FIRST un-confounds this
  spec's byte gates (B1's RNG-threading fixes the P2 drift, removing the carve-out) at the
  cost of landing the larger hot-zone change first; RESPONSES-FIRST lands the calibration win
  sooner but leaves Gate 2/3 P1-only and the hidden-hand leak (Risk 2) open for B1 to fence
  afterward.
- **Whoever re-anchors LAST owns the canonical seeded baseline.** If this spec ships first
  (expected), record its gate-ON 100k baseline as the current anchor and note that a future
  B1 Step 6 landing SUPERSEDES it. If B1 Step 6 lands first, S3.0's fresh baseline
  automatically captures the post-B1 RNG behavior -- no conflict, because S3.0 always
  re-anchors at execution HEAD.
- **Do NOT co-commit the two.** Bundling the RNG-threading refactor with the capability swap
  would make it impossible to attribute a calibration shift to either change
  (spec-prediction-model-must-be-falsifiable). Separate commits, separate re-anchors,
  separate sign-offs.

---

## Lessons applied (from spec-authoring-lessons.md, per Rule 9)

- **re-execution-specs-require-fresh-baseline-capture** -> S3.0 mandatory fresh baseline at
  HEAD; Gate-1 stated as `baseline +/- shift`; Gate 2/3 anchor to S3.0, not the 07-02 numbers.
- **keyword-density-asymmetry-shifts-direction** -> Gate-1's "why": capability widening is
  symmetric across cards but shifts by interaction density (P1 up, P2 flat).
- **parallel-entry-points-need-mirror-fix** -> S3.4 grep sweep + run_match_set/run_bo3_set
  mirror before declaring Stage 3 done.
- **load-path-dependent-setup-creates-silent-no-op-features** -> S3.5 both-load-path check +
  production-path test so gate-ON is not inert against stub-loaded opps.
- **stop-conditions-on-subsets-must-use-noise-floor-appropriate-aggregation** -> Gate-1 P1
  stop is a full-cell aggregate at n=5000; P2 no-regress checked against the ~0.6pp same-seed
  spread, not a fixed cutoff.
- **spec-prediction-model-must-be-falsifiable** -> Gate-1 numeric band + partial-confirm
  branch that names the residual; do-not-co-commit-with-B1 keeps attribution clean.
- **verify-identifiers-before-spec-execution** -> Pre-flight #9/#10 + battery-runner argparse
  verification before pasting any Stage-4 run command.

---

## Estimated time

Stages 0-2 already SHIPPED (452923a). REMAINDER:
- Stage 3 (S3.0-S3.6): ~3-4 hr work + ~45 min baseline runtime.
- Stage 4 (S4.1-S4.4): ~1-2 hr work + ~1-1.5 hr battery runtime (gate-OFF + gate-ON, two
  cells, two runs each at n=5000 ~= 27s/run + the 10k conservation slice).
- Total: **~6-9 hr, ~1.5-2 working sessions**, M. Parallel-safe with B1 in FILES (different
  modules, shared seam) but NOT in baseline re-anchoring (see Sequencing). The mandated 100k
  canonical re-anchor is a SEPARATE gated hot-zone step and is NOT in the above estimate.

---

## Annotated imperfections (known limits of v1 scope)

- **whitelist-not-fully-retired-in-v1:** v1 replaces whitelist MEMBERSHIP only for the
  DERIVABLE subset (instant counters + spot removal). Alt/pitch cost (FoW / Force of Negation
  / Daze / Disrupting Shoal), {X} costs, cost-reduction statics (Mystical Dispute), and
  unknown target riders stay whitelisted; the golden test keeps each honest. Full "retire the
  whitelists" is the arc; v1 is the first and largest slice. Fix: ALT_COST + X-cost + rider
  capability kinds in follow-up specs (S-M each).
- **p2-byte-stability-carved-out:** the 13 global-random sites leave P2 same-seed-drifty; P2
  is statistical-only here (Gate 2/3 verify on P1 only). Fix: B1 Step 6 per-state RNG
  threading, then re-add P2 to the byte gates (~30 min re-score once B1 lands).
- **hidden-hand-leak-flagged-not-closed:** the counter window reads opp hidden hand; v1
  widens its firing frequency and only MARKS the site, it does not fence the leak. Fix: B1
  wraps the read behind `observe()`; assert hook already placed (owned by B1).
- **ladder-anchor-methodology-deviation:** Gate-1 anchors to the 47.6% Arena-ladder number,
  not tournament truth (Standard round-level matches dry after 2026-03-21). Band is
  deliberately 10pp wide partly for this. Fix: re-score against a >=400-decided-game
  tournament window when the matches backfill lands (~30 min).
- **policy-still-crude:** respond-if-able heuristics + `_PRIORITY_COUNTER_TARGETS` eagerness
  remain; this spec fixes CAPABILITY, not judgment. Fix: B1 `legal_actions()` consuming
  `capabilities()`; search picks (owned by B1).

## Changelog

- 2026-07-04: Created (PROPOSED, execution-ready). Consolidates and SUPERSEDES 2026-07-01
  (classifier grammar + golden discipline) and 2026-07-02 (n=5000 evidence + hard Gate-1
  band + determinism/no-decision-change gates + risk register) into one executable plan that
  resumes from the SHIPPED gated-OFF classifier @ 452923a (Stages 0-2). Gate scheme aligned
  to the KEYSTONE task: Gate 1 = P1 calibration + P2 no-regress; Gate 2 = gate-OFF
  byte-identity; Gate 3 = seeded-replay byte-stability gate-ON; Gate 4 = no-decision-change
  on non-response paths; Gates 5-8 = golden / coverage / conservation / runtime by reference.
  Adds verified consultation-site line refs (game_state.py:1599-1600, counter_resolver:142-168,
  match_apl:247, aware_match_apl:332/445, priority_stack:294, match_engine:497/521), the
  ENGINE HOT-ZONE flag + 100k canonical re-anchor requirement, the 13-random-sites +
  hidden-hand-leak risk register, and the explicit B1-sequencing rule for the shared 100k
  baseline re-anchor.
- 2026-07-04: Applied the 5 council-required fixes (Council Review now FIXES APPLIED):
  (1) added Gate 9 field-wide no-regress + stop condition, ran it in S4.1, and gave the 100k
  re-anchor a PASS/FAIL block; (2) re-specified Gate 4 as per-decision LOCALITY + matching
  stop condition; (3) added `removal_matches()` to S3.2 with all three removal sites calling
  it; (4) corrected the battery-driver reference to `tmp/calibration_rerun_2026-07-01.py`,
  fixed the grep recipe, and added S3.0.a to promote+git-track the driver into
  `mtg-sim/scripts/`; (5) removed the fabricated `murktide_match.py` from S3.4 in favor of a
  run-the-grep-at-HEAD (~39 files) triage. Spec body now reflects each fix.

---

## Council Review 2026-07-04 (FIXES APPLIED 2026-07-04)

Blind 3-seat council. All three seats: **NEEDS-FIXES** (foundation SOUND -- gates falsifiable, wiring sites
verified line-accurate against the live tree, engine hot-zone honestly flagged, B1 serialization correct).
The five REQUIRED fixes below were APPLIED to the spec body on 2026-07-04; the list is retained as a record.

1. **[applied] Field-wide no-regress gate (Seat 0).** Gate 1 calibrates only P1 (rise) + P2 (flat), but flipping
   `WANTS_ORACLE_RESPONSES` changes counter/removal legality FIELD-WIDE. Add a no-regress gate over the cells
   S3.4 actually wires (UW Control, Affinity, combo + the flagged mismodeled cells) with a no-worse-than-fresh
   -baseline band. AND give the 100k re-anchor PASS/FAIL teeth -- it is currently descriptive-only ("expected
   re-basing"), so a field regression can ride in unflagged.
   APPLIED: new **Gate 9 -- Field-wide no-regress** + matching stop condition; S4.1 now runs Gates 1-9 over the
   wired cells; the "Documented 100k canonical baseline re-anchor" section gained an explicit PASS/FAIL block
   (known-good cells stay in-band; no unexplained large swing; unattributed swing = FAIL/STOP).

2. **[applied] Re-specify Gate 4 (Seat 1 -- the most likely false-STOP).** "Whole-trace identity for non-response paths"
   is UNSATISFIABLE: gate-ON legitimately fires more responses -> game state diverges -> downstream land/cast/
   attack differ by correct propagation, not leak. Restate Gate 4 as per-decision LOCALITY: given IDENTICAL
   input game-state, the chosen non-response action is identical gate-ON vs gate-OFF (per-node check), NOT
   whole-trace equality. Fix the matching stop condition.
   APPLIED: Gate 4 retitled "Per-decision LOCALITY" and restated as a per-node (identical-input -> identical
   choice) check with downstream state divergence explicitly EXEMPT; the Gate-4 stop condition now fires only on
   a per-decision-input divergence, not on downstream game-state divergence.

3. **[applied] Add a conservative `removal_matches(spec, target)` helper (Seat 0).** `counter_matches` is conservative-
   by-construction, but there is no removal analogue -- condition enforcement is hand-rolled at THREE sites
   (match_apl:247, aware_match_apl:332/445), a false-positive illegal-target hazard in a hot zone. Centralize
   in `response_capability.py` mirroring counter_matches's unknown->False semantics.
   APPLIED: S3.2 now specifies implementing `removal_matches(spec, target)` in
   `engine/response_capability.py` (unknown->False like `counter_matches`) and has all THREE removal sites
   (match_apl:247, aware_match_apl:332/445) call it instead of hand-rolling the filter.

4. **[applied] Fix the battery-driver dependency (Seat 2 -- day-1 blocker).** The gate battery hard-depends on
   `tmp/calibration_rerun_2026-07-01.py`, which is GITIGNORED/untracked (a `git clean` loses it), and the
   spec's own `grep sim_calibration` recipe mis-targets it. Correct the recipe (point at
   `tmp/calibration_rerun_*.py`) and PROMOTE + git-track the driver into `scripts/` before Stage 3.
   APPLIED: the Pre-flight verify-identifiers paragraph now names `tmp/calibration_rerun_2026-07-01.py`, drops
   the mis-targeted `sim_calibration` grep, and new step **S3.0.a** promotes + git-tracks the driver into
   `mtg-sim/scripts/` before any Stage-3 code lands; all recipes reference the promoted path.

5. **[applied] Correct the S3.4 consumer list (Seat 2 -- factual error).** `murktide_match.py` does NOT exist
   (fabricated); the real grep for COUNTER_VALIDITY|MATCH_REMOVAL|_PRIORITY_COUNTER_TARGETS hits ~39 files
   (mostly Standard APLs out of Modern-arc scope). Drop the fabricated name; replace with "run the grep at
   HEAD, expect ~39 hits, triage each for in-scope wiring."
   APPLIED: S3.4 drops the fabricated `murktide_match.py` and the fixed consumer list; it now says to run the
   grep at HEAD, expect ~39 files (mostly out-of-scope Standard APLs), and triage each for in-scope wiring.

Minors (not blocking): P2's ~0.6pp tolerance is from n=3 -- widen or mark provisional; add a pre-flight check
that no live gauntlet/goldfish path forks through `cast_spell`; note the anchor tension (37.2% tournament
truth sits 0.4pp below the 47.6%-ladder band floor -- the band is tuned to the friendliest anchor).

**Verdict: SOUND foundation, execution-ready AFTER fixes 1-5.** Expected most-likely outcome is a
PARTIAL-CONFIRM (P1 rises, may miss the band, ship gate-OFF) -- treat that as success, not failure.

---

## Council Round-2 Conditions 2026-07-04 (WP-A gate -- cross-vendor, Codex-corroborated)

Cross-vendor WP-A gate council (workflow w22bnjznl; one blind Claude gate-gameability seat + a genuine
Codex gpt-5.5 seat that cited line numbers; chair re-verified every citation). **Verdict:
EXECUTE-WITH-CONDITIONS + PULL-WPB4-FORWARD.** WP-A may run GATE-OFF-DEFAULT now (that path is inert-safe
by Gate 2 byte-identity); the following must be satisfied BEFORE the default is flipped ON or the battery
is called "field-safe". (These REFINE Gates 1/5/9 + the 100k step from the round-1 fixes -- a future
executor must fold them into those gate texts.)

1. **Pre-register Gate 9.** Gate 9's "documented direction" escape hatch is post-hoc-authorable for the
   anchorless field cells it must protect (flagged by BOTH the blind Claude seat AND Codex -- strongest
   corroborated hit). REQUIRE: before any gate-ON run, commit to disk a manifest of the per-cell direction
   list + each cell's truth anchor + its measured gate-OFF same-seed spread. A gate-ON move must match the
   pre-registered direction/magnitude or it FAILS. Remove the author-the-pass-later loophole.

2. **Tighten the 100k re-anchor (F1, Claude-only, sharpest).** The FAIL clause currently accepts
   "shared-RNG re-consumption per Risk 1" as a blanket universal attribution, so a real capability misfire
   is always "attributable" and rides in as PASS. REQUIRE a pre-registered, QUANTIFIED expected
   RNG-reshuffle envelope per moved cell; FAIL any swing beyond it even if nominally attributed. (Only
   "known-good cells stay in-band" has teeth today; give the field-wide clause real teeth.)

3. **Gate 1 symmetric partial-confirm (F3).** Today only P1 UNDERSHOOT is partial-confirm. A P1 landing
   ABOVE the 47.6% ladder anchor (past the 37.2% tournament truth) is ALSO partial-confirm + named
   residual, NOT a clean PASS (Risk 3 predicts crude-policy overshoot).

4. **Pre-name Gate 5 allowances.** The <=2 golden-mismatch tolerance is a soft escape hatch unless the two
   allowed cases are named on disk before runs. REQUIRE pre-naming.

5. **Scope discipline (explicit).** WP-A ships GATE-OFF-DEFAULT ONLY. Do NOT flip the default ON or claim
   the battery is field-safe until BOTH (a) the tightened 100k re-anchor passes AND (b) per-state RNG
   threading (WP-B4 / B1 Step 6) has landed so P2 is a genuine byte-gate, not a statistical carve-out.

**b1 decision recorded:** WP-B4 (RNG threading only) is PULLED FORWARD as a WP-A default-ON prerequisite
(see 2026-07-01-b1-legal-action-api.md UPDATE 2026-07-04). Note F4 (Gate 4 coverage front-loads / shrinks
after the first fired response) is a coverage limitation, not a blocker -- Codex endorsed Gate 4's
per-decision locality as the correct falsifiable shape.

_NOTE: recorded via direct append (the round-2 folding agent hit the account session limit mid-run); a
future session should fold conditions 1-5 into the Gate 1/5/9 + 100k texts proper._
