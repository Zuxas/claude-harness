---
title: "Engine v2 milestone two: real-matchup selection and Burn mirror implementation"
status: "SHIPPED"
created: "2026-09-30"
updated: "2026-10-01"
project: "mtg-sim"
estimated_time: "subsystem-by-subsystem; see slices"
related_findings:
  - "harness/specs/2026-09-30-rules-engine-v2-design.md (approved architecture; NOT revised here)"
related_commits:
  - "mtg-sim c083785 (effect slice 1: Lava Spike, Lightning Helix -- in-scope, no new subsystem)"
supersedes: null
superseded_by: null
---

# Engine v2 milestone two: real-matchup selection and Burn mirror implementation

## Why milestone two was needed

The milestone-one v2 spec (section 1, OUT list) excluded "triggered abilities, non-mana activated
abilities, tokens, planeswalkers, replacement effects" and search, and section 5 calls a staged
resolution-time choice "milestone-two design". The milestone-two task asked for a real repository
matchup playable with the listed effect primitives (damage, life, draw, counters, P/T until end of
turn, destroy, counter, simple token, simple static) and to avoid "mechanics that would require a
second architecture project".

A mechanics survey of all 155 parseable 60-card lists in `mtg-sim/decks/` (including `decks/auto/`)
found **no deck without triggered abilities** (0 / 155), and no same-format pair whose cards fit
the listed primitives. Every real matchup needed several subsystems outside milestone one. The user
approved S1-S7 as one milestone-two block; this document records the selection, implementation,
validation evidence, and remaining limitations.

## Phase 1 note: matchup selection

**Selected: Modern Burn mirror** -- `decks/mono_red_aggro_modern.txt` vs itself
(Burn, Dictator_4_Life, MTGO Challenge 96, 10th). Both seats play the same 60; Bo3 sideboards are
milestone-three work.

Ranking method: each card classified by the engine subsystems it needs (trigger queue, non-mana
activated abilities + costs, library search, enters-the-battlefield replacements, rule-changing
continuous effects, alternative costs, modal spells, multiple / dependent targets, counters, tokens,
hidden-zone actions, auras/equipment, static continuous effects). Hard-excluded: planeswalkers,
sagas, battles, copy effects, any non-normal layout (transform, MDFC, adventure, class, split).

| Rank | Pair | New subsystems | Unique non-basic cards | Note |
|---|---|---|---|---|
| 1 | Simic Rhythm mirror (Standard) | 8 (by regex) | 14 | REJECTED on inspection: earthbend turns lands into creatures (type-changing continuous effect -> layers beyond the spec), X spells + search to battlefield, replacement draw (Quantum Riddler), countering triggered abilities (Spider-Sense) |
| 2 | **Burn mirror (Modern)** | 10 | 17 | every card is classic, fully specified text; no layers, X, copy, tokens, counters (except suspend's time counters) |
| - | Goryo's Reanimator vs Burn | 12 | 37 | cheapest non-mirror Burn pairing: adds counters, discard, more graveyard interaction |
| - | Izzet Prowess (auto) vs Burn | 13 | 28 | adds equipment, tokens, static continuous |

A mirror is weaker validation than a two-archetype matchup (symmetric strategies hide asymmetric
rules bugs). Recommended follow-on after the mirror passes: Burn vs Goryo's Reanimator.

### Burn main deck (60) -- support status at selection time

| Card | Qty | Before M2 | Needs |
|---|---|---|---|
| Mountain | 3 | supported | -- |
| Lightning Bolt | 4 | supported | -- |
| Lava Spike | 4 | **supported (slice 0, c083785)** | -- (planeswalker targets vacuous: none supported; guard test) |
| Lightning Helix | 2 | **supported (slice 0, c083785)** | -- |
| Monastery Swiftspear | 4 | no | S1 triggers (prowess, CR 702.108a); haste exists |
| Goblin Guide | 4 | no | S1 triggers (attack trigger); reveal (CR 701.20) of library top, conditional move to hand |
| Roiling Vortex | 4 | no | S1 triggers (each upkeep; cast trigger with intervening-if, CR 603.4); S2 activated ability; S5 "can't gain life" (CR 119.7) |
| Arid Mesa / Bloodstained Mire | 4 / 2 | no | S2 activated ability with {T}, pay 1 life (CR 119.4), sacrifice costs; S3 library search (CR 701.23a) for a land with a basic type (Sacred Foundry qualifies), shuffle |
| Sunbaked Canyon | 4 | no | S2 mana ability with a life cost (CR 605.1a, 119.4); S2 activated draw ability ({1}, {T}, sacrifice) |
| Fiery Islet | 1 | no | as Sunbaked Canyon |
| Inspiring Vantage | 4 | no | S4 enters-tapped-unless replacement (CR 614.1d), no choice |
| Sacred Foundry | 2 | no | S4 "as this land enters, you may pay 2 life" replacement with a choice (CR 614.1c, 614.12); land types Mountain Plains |
| Searing Blaze | 4 | no | S7 two dependent targets (player; creature that player controls) (CR 115.1, 601.2c); per-turn "land entered under your control" record for its landfall condition |
| Skewer the Critics | 4 | no | S6 alternative cost: spectacle (CR 702.137a, 118.9); per-turn "opponent lost life" record |
| Rift Bolt | 4 | no | S6 suspend (CR 702.62a/b): special action exiling with time counters; S1 upkeep trigger; cast without paying its mana cost during resolution |
| Boros Charm | 4 | no | S7 modal spell (CR 700.2, 700.2a); S5 indestructible until end of turn (CR 702.12b); S5 double strike until end of turn (CR 702.4b) |
| Skullcrack | 2 | no | S5 "players can't gain life this turn" (CR 119.7) and "damage can't be prevented this turn" (CR 615.12; vacuous in this matchup: no prevention effects exist, recorded anyway) |

At selection time, every card in a "no" row was outside milestone one's approved scope. Rift Bolt
(suspend) was the costliest: it needed triggers, exile with counters, and casting during a
resolution, so it was scheduled last.

## Approved milestone-two subsystems

Each slice: narrow implementation, tests first citing the pinned CR (2026-09-25, verified through
`tests/v2/cr_index.py`), reducer-only mutation via new ops (journaled, each emitting an event),
typed actions through `legal_actions()`, staged decisions for any choice, observation updates
limited to public info and the deciding player's own choices, shadow-failure fuzz coverage of every
new op, randomized games with invariants + exact replay, M7 re-measured.

- **S1 Triggered abilities (CR 603).** Trigger detection from committed events (603.2); pending
  triggers held in state; put on the stack the next time a player would receive priority (603.3),
  APNAP with the controller ordering their own (603.3b) as a staged decision; targets chosen as for
  spells (603.3d) with the existing staged target model; intervening-if checked on trigger and
  resolution (603.4); ability StackEntry kind (an object that is not a card), countered/fizzled per
  608.2b. Cards unlocked with S2-S7: Swiftspear, Goblin Guide, Roiling Vortex upkeep/cast triggers.
- **S2 Activated abilities and costs (CR 602, 605).** `ActivateAbility(source, ability_index)`
  typed action; costs {T}, mana, pay N life (119.4, 118.3), sacrifice; ability StackEntry; mana
  abilities with life costs remain non-stack (605.3a) and extend the payment enumerator.
- **S3 Library search (CR 701.23).** Staged `ChooseSearchResult` decision visible only to the
  searching player (hidden zone), may fail to find; then shuffle (game RNG). Fetchlands.
- **S4 Enters-the-battlefield replacements (CR 614.1c-d, 614.12).** Applied atomically with the
  zone change: conditional enters-tapped (fastland) and an optional life payment chosen by the
  controller as a staged decision before the move commits (shockland).
- **S5 Duration-scoped rule effects.** A per-turn effect list in state expiring in cleanup (514.2):
  player can't gain life (119.7), damage can't be prevented (615.12), indestructible (702.12b),
  double strike (702.4b, both damage steps).
- **S6 Alternative costs (CR 118.9, 601.2b/f).** Spectacle (per-turn life-loss record). Suspend
  (702.62) last: special action to exile with time counters, upkeep trigger (needs S1), cast without
  paying during resolution (a resolution-time cast -- the spec's milestone-two design question).
- **S7 Modal spells and multiple targets (CR 700.2, 115.1, 601.2c).** Mode chosen at 601.2b;
  dependent second target (Searing Blaze); per-turn landfall record.

Execution order: S1 -> S2 -> S4 -> S3 -> S5 -> S7 -> S6. The user approved the entire block on
2026-10-01; no per-slice approval was required.

## Acceptance gates for the matchup (unchanged from the task)

All 60 cards explicitly supported; unsupported cards refuse game creation; legal-action-only
pilots; >= 10,000 seeded games with 0 crashes / 0 invariant violations / 0 illegal actions;
deterministic repeats; representative exact replay; manual log inspection; M7 reported against
the 200 target / 20 floor. Win rates diagnostic only.

## Slice 0 (done, in scope today)

mtg-sim c083785: Lava Spike + Lightning Helix (shared damage helper, `gain_life` op), 8 tests,
1,000 randomized games with a test-only synthetic deck (BURN_TEST) -- 0 errors, 200/200 replays.

## Changelog
- 2026-09-30: Created (PROPOSED) during the overnight autonomous run; stop rule applied
  ("approved spec ... cannot be resolved conservatively": the required subsystems are outside
  the approved scope and reserved for design review).
- 2026-10-01: APPROVED by the user as ONE implementation block covering S1-S7 (no per-subsystem
  approval needed). The milestone-one architecture spec is NOT revised; this approval expands scope
  for milestone two. Order: S1 triggers -> S2 activated abilities/costs -> S4 ETB replacements ->
  S3 library search -> S5 duration-scoped rule effects -> S7 modes + multiple/dependent targets ->
  S6 alternative costs + suspend -> full Burn mirror validation -> Bo3 only after the exact 60-card
  main deck passes. Binding requirements from the approval (summarised): typed trigger-relevant
  occurrences from reducer commits (never parse the event log); SBAs before triggers go on the
  stack; APNAP with an ordering decision for one player's simultaneous triggers; targets on
  stacking; intervening-if at trigger and resolution; ability entries never enter card zones;
  prowess = reducer-controlled +1/+1 until cleanup. Typed activation actions validated before
  costs; costs (mana, tap, life, sacrifice) paid atomically; sacrificed source's ability stays on
  the stack; mana abilities skip the stack; no player-facing undo. Replacements inside the zone-
  change transaction (Vantage counts OTHER lands before entering; Foundry choice before the move;
  a player unable to pay 2 life gets the tapped result). Search choices private; fetchlands may
  fail to find (not a universal rule); chosen card validated against the exact predicate; shuffle
  even on failure with the game RNG; no post-shuffle order leaked into observations or logs.
  Typed duration effects only (can't gain life, damage can't be prevented, indestructible, double
  strike, numeric P/T) expiring deterministically at cleanup. Boros Charm mode before targets;
  Searing Blaze target relationship + partial-legality resolution + per-controller landfall.
  Spectacle before suspend; record opponent life loss and actual mana spent; suspend as a typed
  special action; resolution-time cast via a typed, serializable, checksummed continuation (no
  callbacks / direct pilot calls); CR outcome when it cannot be cast. Planeswalkers stay
  unsupported (Lava Spike restriction explicit).
- 2026-10-01: SHIPPED (S1-S7 + full Burn-mirror validation + Bo3). See results below. Not connected to the
  launcher (later milestone); legacy engines untouched.

## Milestone-two results (2026-10-01, mtg-sim)

The implementation is published on `origin/modern-postban-arc` through `60cd745`.

| Slice | Commit | Cards fully supported | Tests |
|---|---|---|---|
| 0 | c083785 | Lava Spike, Lightning Helix | test_effects_burn.py (8) |
| S1 triggers | 5a32c05 | Monastery Swiftspear, Goblin Guide | test_triggers.py (10) |
| S2 activated + costs | 8a8c927, 5697fef | Sunbaked Canyon, Fiery Islet | test_activated.py (11) |
| S4 ETB replacements | 7870aae | Inspiring Vantage, Sacred Foundry | test_replacement.py (6) |
| S3 search | 8617cad | Arid Mesa, Bloodstained Mire | test_search.py (8) |
| S5 duration effects | acec96e | Skullcrack, Roiling Vortex | test_duration.py (9) |
| S7 modes / targets | 1fd99ec | Boros Charm, Searing Blaze | test_modes_targets.py (12) |
| S6 alt costs / suspend | db3b572 | Skewer the Critics, Rift Bolt | test_alt_costs.py (12) |
| deck loader + mana fixes | 22fff01, a981f7a | the real 60-card list (18 unique) | test_burn_deck.py (4) |
| perf | d9246e3, 7b95978 | -- | -- |
| validation | c5a80c4, c1b6f60 | -- | scripts/v2_burn_validation.py |
| Bo3 | c6571d8, 7118248 | -- | test_match.py (6), scripts/v2_bo3_validation.py |
| reruns + docs | 4d3965d, 46dfe6c | -- | -- |
| suite timing fix | 2828c4b | -- | lazy deck load in test_match |
| review fixes | 9cae86c, 98c7b0f, 3c0c0bf | -- | tuple legal actions, MatchObservation, deck_rules, cross-seed replay |

Every new reducer op is covered by the shadow-failure transaction test (card tests re-run under shadow);
every cited rule is quoted verbatim from the pinned 2026-09-25 CR (test_rule_citations).

Burn mirror (decks/mono_red_aggro_modern.txt main deck, 60 cards, invariants ON in every game):

| Gate | 1,000 games | 10,000 games |
|---|---|---|
| crashes / invariant violations | 0 | 0 |
| dead ends (only Concede legal) | 0 | 0 (62 in the first 10k run: bug found and fixed, a981f7a) |
| illegal actions accepted | 0 / 40,199 probes | 0 / 395,274 probes |
| exact replay (through JSON) | 200 / 200 | 1,000 / 1,000 |
| repeated seeds identical | -- | 300 / 300 |
| unsupported-card fallbacks | 0 (deck validated; one-card swap refused) | 0 |
| turn-limit draws | 0 | 0 (10,000 explicit wins) |
| throughput | -- | 99 g/s wall (20 workers, invariants on); 37 g/s single core (invariants off) |

Win rates diagnostic only: seats 5,004 / 4,996; the untuned aggro pilot beat the random pilot 3,269-65.
Manual inspection (data/v2_burn_logs/, regenerated by every rerun from the same seeds): logs 0, 4 and 5
read in full (5 up to the final turns), logs 1-3 checked by targeted search for suspend / Charm / Guide /
blocking sequences; one oddity in log 5 (the random player never played a land) was verified against the
state -- it kept a land-less hand and drew no land. Sequences seen: shock-land payments, fetch -> search ->
shuffle, Searing Blaze with landfall killing Swiftspear, prowess from Roiling Vortex, APNAP Vortex upkeep
pings, spectacle Skewer paid with pain-land mana, suspended Rift Bolt (counter removal, cast / decline),
Boros Charm modes, Goblin Guide reveals, blocks and trades, cleanup discard, games ending at 0 life by SBA.

Cross-hash-seed replay: 200 Burn-mirror records (random / aggro / mixed pilots) and 30 Bo3 match records
(62 sideboard swaps) replayed exactly in fresh processes with PYTHONHASHSEED unset / 31337 / 7; a smaller
version is a permanent test (tests/v2/test_determinism.py). Full suite on the final code: 317 passed (167
non-v2 + 150 v2), the same 3 pre-existing failures and 4 collection errors. Legacy engine diff since f888595:
empty.

Bo3: 500 Burn-mirror matches (supported test sideboard; the real sideboard's cards are unsupported and are
refused), invariants ON: 0 errors, 500/500 match replays exact, 1,669 sideboard swaps in 450 matches,
50/50 repeated seeds identical.

M7 (milestone-one benchmark, RG/WU random games, single core): 24.29 g/s CPU in the acceptance process on the
final code (3c0c0bf rerun); 22.61 after
7b95978 (self-verified dirty-flag SBA skip + mana fast paths); it had fallen to 15.9 after S2, 18.4 after S7
and 18.77 in-process before that commit. The machine was ~20% slower during this run (the milestone-one code
itself measured ~21.5-22 g/s standalone vs 26-27 earlier). Still reported-only; thin margin. Milestone-one
acceptance M2 / M3 / M4 outcomes are identical to milestone one (same seeds, same results).

## Implementation decisions taken during execution (conservative, recorded)

- D1 Cast-time mana is limited to activations after which the announced cost stays payable (a choice that
  strands the cost would make the cast illegal and be rewound under CR 733; spec 7.4 offers only actions
  with a legal completion; no player undo). Found as dead ends in the first smoke run.
- D2 Mana-ability life costs share one life budget (CR 119.4): found as 62 dead ends in the first 10k run.
- D3 Shuffled events carry a digest keyed by the secret RNG state instead of the post-shuffle order
  (milestone one logged the order: a hidden-information leak in the log).
- D4 Non-mana activations pay mana from the pool (mana abilities first, then ActivateAbility with an exact
  pool assignment); spells keep the staged 601.2g flow.
- D5 Ability stack entries are A<n> objects carrying the source card ciid for naming and the source
  ObjectId for last-known information; they never enter card zones (invariant).
- D6 Trigger ordering is staged one OrderTrigger at a time (every order reachable, linear options).
- D7 Bo3 ends at 2 game wins; drawn games count for neither; conservative cap of 5 games, then match draw.
- D8 A 75 with an unsupported sideboard card is refused (strict); the real Burn sideboard is entirely
  unsupported, so Bo3 validation uses a supported test sideboard.
- D9 SimpleAggroPolicy (validation logs only) reads public card types from card definitions; untuned.
- D10 Behaviour-preserving performance work: interned frozen action values, cached priority / pending ops
  and events, per-decision castability memo, per-game mana-option cache.
- D12 Review fixes before the report: legal_actions() returns an immutable tuple (a policy could append an
  illegal action to the cached list and have it accepted -- test proven red on the old code); match policies
  get a frozen MatchObservation (own 75 only) instead of the Match; Game.new(deck_rules='constructed' default
  | 'test') -- CR 100.2a enforced unless the explicit, recorded test exception is used by the synthetic decks;
  ENGINE_VERSION v2-m2.1. (v2-m2.0 itself spanned S1..S7 with event / action format changes; no records were
  saved in between, so no record is misclassified.)
- D11 SBA checks are skipped only when no transition since the last empty check contained an op that can
  create an SBA condition; with invariants on, the skipped check is computed anyway and must find nothing
  (never fired in 11,100 invariant-on validation games plus the M2/M4 runs).

## Known limitations

- Planeswalkers unsupported (Lava Spike / Skullcrack / Boros Charm / Searing Blaze target players only;
  guard test). No prevention effects exist, so "damage can't be prevented" is recorded but vacuous.
- No destroy effect is supported, so indestructible is exercised only against lethal damage.
- Triggered-ability targeting exists but no supported card uses it (tested via a patched spec).
- Searing Blaze's "player target illegal" case is reachable in two-player Magic only when that player has
  left the game; tested by invoking resolution before the SBA.
- The real Burn sideboard (Chalice of the Void, Deflecting Palm, Exquisite Firecraft, Hallowed Moonlight,
  Sanctifier en-Vec, Smash to Smithereens, Wear // Tear) is unsupported.
- v2 is not wired to the launcher; legacy engines unchanged.
