---
title: "Oracle-driven responses v2 -- calibration-evidenced replacement of the counter/removal whitelists"
status: "SUPERSEDED"
superseded_by: "2026-07-04-oracle-driven-responses-execution.md"
created: "2026-07-02"
updated: "2026-07-02"
project: "mtg-sim"
estimated_time: "M-L, ~2-3 sessions (per-stage table below); parallel-safe with B1 (different files, shared seam)"
related_specs:
  - "harness/specs/2026-07-01-oracle-driven-responses.md (EXTENDS -- classifier design + golden-test discipline adopted BY REFERENCE, not duplicated)"
  - "harness/specs/2026-07-01-b1-legal-action-api.md (RESPOND_* vocabulary; fork/observe seam; RNG-threading is ITS territory)"
related_findings:
  - "harness/knowledge/mtg/sim-calibration-2026-07-01.md (n=5000 battery re-run -- THE empirical driver)"
  - "harness/knowledge/tech/calibration-probe-2026-07-01.md (earlier same-direction probe the 07-01 spec was written against)"
  - "E:\\vscode ai project\\AUDIT-ENGINE-APL-2026-07-01.md (Part A #2 whitelists; A.5 the 13 global-random sites)"
  - "mtg-sim/data/sim_calibration_2026-07-01.json + mtg-sim/calibration-rerun-2026-07-01.log (battery artifacts)"
related_commits: []
supersedes: null
superseded_by: null
branch: "modern-postban-arc"
---

# Oracle-driven responses v2 (battery-evidenced)

## Relationship to 2026-07-01-oracle-driven-responses.md (READ FIRST)

A PROPOSED spec for this work already exists and stays authoritative for the
classifier core: pattern grammar, golden-test-against-the-table discipline
(its G1), gate-OFF byte-identity (G2), coverage sweep (G3), and its stop
conditions. Those are incorporated **by reference** and NOT restated here.

This spec adds what the 07-01 authoring predates or left soft:

1. **Evidence upgrade** -- 07-01 cites the probe figure (P1 13.1%); the full
   n=5000 battery re-run measured **5.3%**, inverted, and WORSE against
   fresher anchors. The problem statement below supersedes 07-01's.
2. **Hard calibration gate** -- 07-01's G4 was direction-only ("moves UP").
   Gate #1 here is a numeric band against the current-meta anchor.
3. **Capability-vs-policy seam** made explicit (design section 4).
4. **Classification cache** design (design section 2).
5. **Counter-window consultation contract** naming exact sites/lines.
6. **Per-stage size estimates** and a **risk register** (13 global-random
   sites; fork x counter-window hidden-hand leak from the 2026-07-01
   decision_api MCTS-readiness audit).

On execution, both files move status together; amendments land HERE.

## Problem statement (evidence from the 2026-07-01 battery re-run)

The engine's interaction model is whitelist MEMBERSHIP, not card behavior:

- `engine/counter_resolver.py::COUNTER_VALIDITY` -- 18 hand-maintained
  counterspell entries (validity predicate, base cmc) plus the
  `_PRIORITY_COUNTER_TARGETS` name set (~35 names, eagerness policy).
- `apl/match_apl.py::MATCH_REMOVAL` -- 37 removal entries in base MatchAPL
  (~60 counting per-APL extensions), keyed by card NAME -> (cmc, max_tgh).
- `engine/interaction.py` -- archetype-level probability tables (legacy
  distribution path; not a card model at all).

A card absent from these tables does not exist as interaction, regardless of
its oracle text. New sets require manual table maintenance forever.

2026-07-01 battery (n=5000/pairing, seed=42, PYTHONHASHSEED=0,
`modern-postban-arc` @ d9b708a, first run measuring the REAL Dimir APL after
the dimirmidrangestd registry fix; full note:
sim-calibration-2026-07-01.md):

| Pairing | Sim | Apr truth | Tourn (pre-SOS) | Ladder (current) |
|---|---|---|---|---|
| Dimir Midrange vs Izzet Prowess | **5.3%** (+/-0.6) | 40.0% (-34.7) | 37.2% (-31.9) | **47.6% (-42.3)** |
| Izzet Prowess vs Mono Green Landfall | **71.5%** (+/-1.3) | 53.0% (+18.5) | 52.5% (+19.0) | **52.2% (+19.3)** |

Reading: the April catastrophic class (P2 at 1.4%) is CURED by R1-R6 -- P2
now runs ~+19pp HOT against all three anchors. The surviving failure isolates
the interaction model: Dimir Midrange's game plan is interaction-dense, and
with its real APL finally measured it wins 5.3% because most of its answers
either aren't in the whitelists or under-fire through the crude value gates
-- the deck is simulated with a fraction of its actual deck. Izzet Prowess
(proactive, whitelist-light) is fully modeled and overshoots. The inversion
gets WORSE against fresher anchors (-42.3 vs the current ladder). Every
anchor tells the same story; this is the binding constraint on sim
credibility (calibration note verdict, verbatim: "Remaining calibration debt
points at the interaction model").

Anchor caveat, carried honestly: the 47.6% figure is an Arena-ladder anchor
(untapped, meta period 701, N=1,284, +/-2.7pp) -- a methodology deviation,
because round-level Standard tournament `matches` end 2026-03-21 and the
current-window tournament N=0. It is the only CURRENT anchor; Gate #1's band
is deliberately wide (10pp) partly for that reason.

## Goal

Replace whitelist MEMBERSHIP with oracle-text-derived response CAPABILITY:
for every card in either decklist, derive from the already-loaded oracle DB
(`engine/card_db.py::CardDB` -- the 164MB `scryfall_oracle_cards.json` +
75k rulings, process-lifetime cached singleton, `oracle_text()` accessor
already handles DFC/split faces) whether it can counter / remove / interact,
at what timing (instant / flash), and at what cost -- so ANY answer a
decklist actually plays can fire in the response windows the engine already
has. Response POLICY (whether firing is smart) stays in the APL layer and is
explicitly NOT changed by this spec.

## Design sketch

### 1. Derivation rules (capability, not policy)

`engine/response_capability.py` (new): pure function
`capabilities(card) -> tuple[ResponseCapability, ...]` where
`ResponseCapability = (kind, timing, cost, condition)`:

- **kind**: COUNTER_ANY / COUNTER_NONCREATURE / COUNTER_CREATURE /
  COUNTER_CMC_COND / COUNTER_UNLESS_PAY_N / REMOVAL_DMG_N /
  REMOVAL_DESTROY / REMOVAL_EXILE / BOUNCE. These map 1:1 onto the existing
  `RESPOND_COUNTER` / `RESPOND_REMOVAL` action kinds in
  `mtg-sim/docs/action-vocabulary.md` (#9/#10) -- the 13-kind B1 vocabulary
  does NOT grow.
- **timing**: from type_line ("Instant") or oracle keyword ("Flash").
- **cost**: printed mana_cost/cmc via the honest-mana path. Alt/pitch costs
  (Force of Will, Disrupting Shoal, Daze) are NOT derived in v1 -- those
  cards keep their whitelist entries (golden test keeps them honest).
- **condition**: compiled from oracle-text patterns, REUSING
  `engine/oracle_parser.py` normalization idioms verbatim (`//` face splits,
  em-dash stripping; per 07-01 pre-flight #4 -- do not write a second parser
  dialect): "counter target spell" -> ANY; "counter target noncreature
  spell" -> NONCREATURE; "unless its controller pays {N}" -> UNLESS_PAY_N;
  "deals N damage to target creature" -> DMG_N (kills toughness <= N,
  exactly the `(cmc, max_tgh)` semantics MATCH_REMOVAL already encodes);
  "destroy target creature" + rider restrictions (nonartifact,
  non-legendary, mana value <= N); "exile target ..."; "return target ...
  to its owner's hand" -> BOUNCE.

### 2. Caching

Classify once per unique card name at deck load: module-level dict keyed by
`oracle_id` (name fallback), process lifetime -- the same pattern as
CardDB's own `_db_instance` singleton. Zero per-cast parsing; zero RNG;
cache size = deck-union (~75 names/match). Parallel workers each warm their
own copy (read-only afterward; no cross-process invalidation). A test
asserts cache-hit on second lookup so classification can never silently
enter the inner loop.

### 3. Consultation contract (where the windows ask)

- **Legacy counter window** -- `game_state.py::cast_spell` fires it at
  L1557-1579 -> `counter_resolver.try_counter_spell`. Candidate discovery
  swaps `c.name in COUNTER_VALIDITY` for `capabilities(c)`; everything else
  in `try_counter_spell` (mana affordability via `_tap_lands_for_response`,
  cheapest-first ordering, value gate vs `_spell_value`) is UNCHANGED --
  that is policy.
- **R1 priority stack** (`priority_stack.py::run_priority_stack`, opt-in via
  `WANTS_PRIORITY_STACK`) and **R2 combat windows** (`match_engine.py`
  WINDOW 1/2, gated by `WANTS_INSTANT_COMBAT`): `priority_action` /
  `combat_priority_action` consult the same capability table for legality.
  priority_stack.py's ZERO-RANDOMNESS hard constraint is preserved --
  classification is pure string work done at load time.
- **Instant-speed removal lookups** -- `match_apl.py::_match_cast_removal`
  (L247) and `aware_match_apl.py::_kill_with_removal` (L332) /
  end-step path (L445): for instant/flash cards, the `(cmc, max_tgh)` spec
  is derived (REMOVAL_DMG_N -> `(cmc, N)`; DESTROY/EXILE -> `(cmc, None)` +
  condition) instead of read from MATCH_REMOVAL. Sorcery-speed entries and
  wipes stay table-driven (out of scope v1).
- **Feature gate**: `WANTS_ORACLE_RESPONSES` per the R-ladder convention.
  Gate OFF = legacy tables consulted, byte-identical. Consultation is
  either/or per gate -- NEVER both paths for the same card (no
  double-counting).

### 4. CAPABILITY vs POLICY separation (the load-bearing seam)

- **CAPABILITY (this spec)**: what a card CAN legally do in a response
  window -- oracle-derived, cached, deterministic, APL-independent, zero
  game-state access (`capabilities(card)` is a pure function of the card).
- **POLICY (explicitly not this spec)**: whether/when to fire -- the value
  gates, `_PRIORITY_COUNTER_TARGETS` eagerness, mana hold-up
  (`reserve_mana`), APL `priority_action` heuristics. All policy code keeps
  its current logic and constants. B1's search layer will eventually replace
  POLICY by consuming this same capability table through `legal_actions()`;
  that is exactly why the seam must stay state-free. Widening capability
  under unchanged policy is the measured experiment -- if results overshoot,
  that is a finding about policy, not a license to tune capability.

## Scope

### In scope (v1)
- Counterspells at instant speed (COUNTER_* family), replacing
  COUNTER_VALIDITY membership as the legality source.
- Spot removal (damage / destroy / exile / bounce) at instant or flash
  speed, replacing MATCH_REMOVAL membership for those cards.
- The classification cache + golden/coverage tests + gated consultation
  swap at the sites named above.

### Explicitly out of scope
- **Replacement effects** -- different rules machinery entirely; nothing in
  the response windows consults them today. Follow-up spec if calibration
  debt survives v1.
- **Trigger ordering** -- infrastructure exists but has no engine call site
  (action-vocabulary.md completeness note); wiring it is not response work.
- Board wipes / sorcery-speed removal -- stay in MATCH_REMOVAL; the
  main-phase `_match_cast_removal` sorcery path is untouched.
- Modal spells beyond first mode, counter-abilities on permanents, alt/pitch
  costs -- per the 07-01 spec; whitelist fallback covers the tail.
- Response POLICY quality -- APL/search territory (B1), see design 4.
- The 13 global-random sites themselves -- B1's fork/RNG-threading refactor
  territory; this spec must merely add ZERO new ones (Risk 1).

## Pre-flight reads (MANDATORY)

The 07-01 spec's five (spec-authoring-lessons.md; counter_resolver.py in
full; priority_stack.py; oracle_parser.py + card_handlers_verified.py
header; mismodeled_matchups.py), PLUS:
6. harness/knowledge/mtg/sim-calibration-2026-07-01.md (the gate anchors)
7. mtg-sim/docs/action-vocabulary.md (#9/#10/#13 -- RESPOND_* kinds this
   must map onto; #13 legacy respond_to_spell folds into #9, do not model
   it separately)
8. mtg-sim/apl/match_apl.py L160-280 (MATCH_REMOVAL semantics to preserve)

## Stages + size estimates

| Stage | Deliverable | Size | Est |
|---|---|---|---|
| 0 | Baseline pin: P1+P2 @ n=5000 seed=42 PYTHONHASHSEED=0 on the execution commit; hash result JSON + normalized logs | S | ~45 min (runtime-dominated) |
| 1 | `engine/response_capability.py` classifier + kinds + cache | M | ~3-4 hr |
| 2 | Golden test (whitelist reproduction, 07-01 Step 2) + coverage sweep -> `data/response_coverage.csv` (07-01 Step 3) | S-M | ~1-2 hr |
| 3 | Gated consultation swap at the 3 site families (legacy window, R1/R2 priority, removal lookups) | M | ~3-4 hr |
| 4 | Gate battery (below) + honest findings write-up + mismodeled_matchups.py updates (direction language, no band-forcing) | S-M | ~1-2 hr + sim runtime |

Total: **M-L, ~2-3 working sessions.** Stages 0-2 are a shippable first
slice (no behavior change, pure additive tests).

## Acceptance gates (falsifiable; every gate must pass before SHIPPED)

| # | Gate | Acceptance | Stop trigger |
|---|---|---|---|
| 1 | **Calibration P1 (primary)** | The P1 calibration cell (Dimir Midrange vs Izzet Prowess, n=5000, seed=42, PYTHONHASHSEED=0, gate-ON) moves from 5.3% to **within 10pp of the current-meta anchor (~47.6% ladder)**, i.e. into [37.6%, 57.6%], **without P2 (Izzet Prowess vs Mono Green Landfall, same protocol) regressing beyond its current +19pp hot** (P2 stays <= 71.5%, i.e. <= +19.3pp vs its 52.2% ladder anchor). | P1 outside band, or P2 > 71.5%: STOP, write findings. NEVER tune classifier constants toward the band -- measure, don't tune. |
| 2 | **Determinism (seeded replays byte-stable)** | Each battery cell run twice at the same seed, gate-OFF and gate-ON separately: byte-identical result JSON and normalized logs (timestamp-stripped, per the Stage-1.7 convention). | Any byte diff: STOP -- a new RNG draw or id()-ordering crept in (cross-ref mull-routing spec Gate-0 finding). |
| 3 | **No-decision-logic-change (non-response paths)** | Gate-OFF: full byte-identity vs the Stage-0 baseline hash. Gate-ON: on a fixed 300-game trace slice, decision traces for all non-response action kinds (MULL_*, RESERVE_MANA, PLAY_LAND, main-phase CAST, PUT_INTO_PLAY, ACTIVATE, ACTIVATE_PW, ATTACK, BLOCK, DISCARD) are identical -- only RESPOND_* / PASS_PRIORITY lines may differ. | Any non-RESPOND divergence: STOP -- the capability swap leaked into proactive decision logic. |
| 4 | **Golden (BY REFERENCE = 07-01 G1)** | 100% of currently-whitelisted cards classify to the same predicate + cost the tables encode. | >2 mismatches: grammar is wrong; fix grammar, never special-case the golden set. |
| 5 | **Coverage (BY REFERENCE = 07-01 G3)** | >=80% of instant/flash cards across decks/ classified; UNHANDLED tail listed in response_coverage.csv, whitelist-covered or inert -- never silently wrong. | Report the actual number honestly whatever it is. |
| 6 | **Conservation (BY REFERENCE = 07-01 G5)** | 10k-game gauntlet slice gate-ON: zero new exceptions, card-count invariant holds. | Any exception / invariant break. |

Gate #1 note: 07-01's G4 said "any significant rise validates the mechanism;
hitting ~40 is NOT required." This spec RAISES that bar deliberately: the
mechanism claim ("the whitelist is THE binding constraint") is falsifiable
only if fixing the whitelist moves the cell most of the way to truth. If v1
lands a large rise but misses the band, that is a partial-confirm: ship
gate-OFF, write which residual (policy? mana? threat model?) owns the rest.

## Risks

1. **The 13 global-random sites** (AUDIT-ENGINE-APL-2026-07-01 A.5: 13
   naked global-`random` consumers). Classification adds zero draws, but
   gate-ON changes HOW OFTEN response code executes, which shifts the shared
   RNG stream's consumption pattern -> same-seed drift in unrelated cells.
   Mitigation: Gate 2 proves gate-OFF untouched; gate-ON re-anchors against
   the Stage-0 pin; the real fix (per-state RNG) is B1's fork/RNG-threading
   refactor -- fold into it, do not duplicate it here.
2. **Fork x counter-window hidden-hand leak** (2026-07-01 decision_api
   MCTS-readiness audit). `try_counter_spell` iterates `opp_gs.zones.hand`
   synchronously from INSIDE the caster's `cast_spell` -- the cast path
   touches hidden information. `decision_api.fork()` clones both states, so
   a search that expands through a cast can read the opponent's REAL hand
   via this window, poisoning ISMCTS determinization. This spec WIDENS the
   window's firing surface (more cards classify as answers). Mitigation:
   v1 keeps the window's shape (leak no worse in KIND, only frequency);
   `capabilities()` itself is state-free; add a `# HIDDEN-INFO READ` marker
   + assert hook at the site so B1's `observe()` work can find and fence it;
   record in action-vocabulary #13's fold-in.
3. **Capability widening under crude policy overshoots** -- with legality no
   longer scarce, respond-if-able heuristics may counter everything cheap
   and P1 could blow past the band's top. That is a POLICY finding (Gate 1
   stop trigger), not a reason to narrow capability. Findings doc, then a
   policy follow-up spec.
4. **Grammar false positives** -- oracle text like "counter target spell
   you control" or damage-to-PLAYER-only misclassified as answers. The
   golden gate catches table cards only; mitigate with negative fixtures in
   the classifier test (Gate 4 extension) and the coverage CSV eyeball pass.
5. **Perf** -- the 164MB CardDB is already resident; classification is
   load-time only. Guard: cache-hit assert (design 2); runtime budget +10%
   max on the n=5000 cell (30.5s baseline).

## Stop conditions

- The 07-01 spec's three (golden mismatch >2; classifier-induced illegal
  engine state -> add legality check at the CONSULTATION site, shared with
  B1's seam; P1 moves DOWN gate-ON -> findings, never ship gate-ON default).
- Gate 2 byte-diff (see table) -- do not ship a nondeterministic response
  path under any circumstances.
- Gate 3 non-RESPOND trace divergence -- the swap leaked outside the
  response paths; find the coupling before proceeding.
- P2 exceeds 71.5% gate-ON -- interaction widening should not make the
  proactive-deck cell HOTTER; something is mismodeled; STOP + findings.

## Commit message template

```
feat: oracle-driven response capability (WANTS_ORACLE_RESPONSES, gate-OFF default)

Replace counter/removal whitelist MEMBERSHIP with oracle-text-derived
capability (engine/response_capability.py), consulted by the legacy
counter window, R1/R2 priority, and instant-speed removal lookups.

Validation results:
  Gate 1 P1:  5.3% -> <X>% (band [37.6, 57.6] vs 47.6 ladder anchor)
  Gate 1 P2:  71.5% -> <Y>% (must stay <= 71.5%)
  Gate 2 determinism: byte-stable ON+OFF
  Gate 3 non-response traces: identical / gate-OFF byte-identical
  Gate 4 golden: <N>/<N> | Gate 5 coverage: <Z>% | Gate 6: clean

Findings doc updated: harness/knowledge/mtg/<...>
Related specs: 2026-07-02-oracle-driven-responses.md (+ 2026-07-01 parent)
```

## Annotated imperfections (known at authoring)

```
## ladder-anchor-methodology-deviation

**What's not perfect:** Gate 1 anchors to an Arena-ladder number (47.6%),
not tournament truth -- Standard round-level matches are dry after
2026-03-21 (task: investigate + fix dry matches table).
**Why not fixed in this spec:** no current tournament anchor exists; the
calibration note chose honest deviation over manufactured truth.
**Concrete fix:** when the matches backfill lands, re-score Gate 1 against
a >=400-decided-game tournament window and tighten the band.
**Estimated effort:** ~30 min re-score once data exists.

## alt-cost-counters-stay-whitelisted

**What's not perfect:** FoW / Shoal / Daze pitch costs remain table entries.
**Why not fixed in this spec:** alt-cost derivation is its own grammar; low
Standard relevance; golden test keeps entries honest.
**Concrete fix:** ALT_COST capability kind + pitch-payment predicate.
**Estimated effort:** S (~1-2 hr).

## policy-still-crude

**What's not perfect:** respond-if-able heuristics + name-set eagerness
remain; this spec fixes CAPABILITY, not judgment.
**Why not fixed in this spec:** policy is B1/search territory by design.
**Concrete fix:** B1 legal_actions() consuming capabilities(); search picks.
**Estimated effort:** owned by B1.
```

## Changelog

- 2026-07-02 (later): **Stages 0-2 SHIPPED** (mtg-sim `452923a` on
  modern-postban-arc, executed @ `3ed5d98`). Stage 3 (consultation swap) and
  Stage 4 (gate battery) NOT started; gate `WANTS_ORACLE_RESPONSES` exists but
  no live path consults the classifier yet (test-asserted).
  - **Stage 0 pin** (n=5000, seed=42, PYTHONHASHSEED=0, the 07-01 driver):
    P1 5.3% -- byte-stable, normalized P1-cell sha256 `b76c3711...` identical
    across THREE runs (2 pre-change, 1 post-change) = the gate-OFF
    byte-identity demonstration. Hash manifest committed as
    `mtg-sim/data/response_baseline_2026-07-02.json` (raw battery JSONs/logs
    local-only; `.gitignore` excludes `data/sim_calibration_*.json`/`*.log`).
  - **FINDING (Gate-2 blocker for Stages 3-4):** P2 (Izzet Prowess vs Mono
    Green Landfall) has PRE-EXISTING same-seed drift at HEAD with ZERO
    changes: 71.4 / 72.0 / 71.6 (+ 71.5 on 07-01 @ d9b708a). Reproduced
    SAME-PROCESS with fresh deck loads (n=1000 seed=42 consecutive: 728 vs
    725 a_wins) -- outside the Stage-1.7-tested mirrors, consistent with the
    13 naked global-random sites / id()-ordering class (Risk 1). Gate 2
    ("byte-identical result JSON per cell") is UNSATISFIABLE for P2 until
    that is fixed (B1 RNG-threading territory). P1 remains a valid
    byte-identity instrument.
  - **Stage 1:** `engine/response_capability.py` -- 9 kinds, printed-cost
    honest-mana, oracle_id-keyed process-lifetime cache (design 2), RNG-free.
  - **Stage 2 golden (Gate 4):** all whitelist members pinned exhaustively
    (18 COUNTER_VALIDITY + 36 base MATCH_REMOVAL + 15 per-APL extension
    entries). ZERO grammar-attributable mismatches (07-01 G1 stop NOT
    triggered). Four table-side deviations documented with oracle quotes in
    the test: Get Out / Metallic Rebuke policy costs (the table's own
    comments declare them), Requiting Hex (table jams mv<=2 into the
    max-toughness slot), Sear (table (2,3) vs card's actual 4 damage --
    stale table entry). v1 not-derived fallbacks behave exactly as spec'd
    (alt/pitch, {X}, cost-reduction statics, Spree/Tiered, unknown riders).
  - **Stage 2 coverage (Gate 5):** 125 decks swept, 208 unique instant/flash
    cards: 31.7% DERIVED, 5.8% whitelist-fallback, 43.3% inert, 19.2%
    UNHANDLED (tail listed in `data/response_coverage.csv`; 07-01's
    "<20% tail, whitelist-covered or inert, never silently wrong" holds at
    80.8% accounted). Strict "derived" reading is 31.7% -- reported honestly;
    the tail is dominated by modal charms, conditional/X effects, and
    color/subtype filters (v1-excluded by design).
  - **Verify:** 38 tests green (repo determinism suite 6/6 incl.
    cross-process, R1 stack, match_engine, +26 new). P1 cell runtime 27.0s
    (baseline 27.0-27.5s; +10% budget met).
- 2026-07-02: Created (status PROPOSED). Extends
  2026-07-01-oracle-driven-responses.md with the n=5000 battery evidence
  (P1 5.3% inverted vs all anchors), the hard Gate-1 calibration band,
  determinism + no-decision-logic-change gates, capability/policy seam,
  cache design, stage sizes, and the risk register.
