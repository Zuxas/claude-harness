---
title: "Rules engine v2 -- design spec, milestone one (one canonical, replayable, rules-correct game between two small decks)"
status: "SHIPPED"
created: "2026-09-30"
updated: "2026-09-30"
project: "mtg-sim (NEW engine/v2/ package + tests/v2/; NO edits to existing engine/ files). DESIGN ONLY -- no code until the user approves."
estimated_time: "L-XL (milestone one ~3-5 sessions)"
related_specs:
  - "harness/reports/codex-review-mtg-sim-2026-09-29.md (architecture review + migration order)"
  - "harness/specs/2026-09-30-strict-mode.md (steps 1-2)"
  - "harness/specs/2026-09-30-card-identity-gate.md (exact card identity)"
  - "harness/specs/2026-07-01-b1-legal-action-api.md (earlier legal-action prototype, engine/decision_api.py)"
related_commits:
  - "mtg-sim 45755d5 (engine/v2 + tests/v2 + M0), 64d56c5 (M7 perf + untap fix), 8dce033 (results + docs), 7ecc9ef (review-gap fixes), final results commit after it"
supersedes: null
superseded_by: null
---

# Rules engine v2 -- milestone one design (revision 4)

## 0. Status and approval
DESIGN ONLY. No engine/ change until the user approves this revision. Revision 1 (harness 1b8ecdc): not approved,
8 findings -> revision 2 (harness 5157acc): not approved, 5 findings + 1 minor -> revision 3 (harness 6f66589):
not approved, 2 findings -> revision 4 addresses them (section 18). Rule texts cited here were checked against the repo CR (April 17, 2026); the reviewer confirmed the
rev-2 rules updates agree with the September 25, 2026 CR.
Approval asked for: (a) namespace (section 2), (b) scope + card set (sections 1, 9), (c) gates (section 12).
`engine/v2/` sits under the engine hot zone; creating it needs the same sign-off. No existing engine file changes.

## 0.1 Rules baseline (pinned authority)
- The repo's rules text is `mtg-sim/data/comp_rules.txt`, "effective as of April 17, 2026" (verified). The review
  reports Wizards now publishes rules effective September 25, 2026. BEFORE M1, the current Comprehensive Rules text
  is downloaded from Wizards' official rules page (download needs the user's explicit permission at that time:
  filename, source, size), stored as `data/rules_reference/MagicCompRules-<YYYYMMDD>.txt`, and pinned in
  `data/rules_reference/RULES.json` {effective_date, source_url, sha256, bytes}.
- Every rule citation in this spec and in the v2 tests is checked against the pinned text in a first
  implementation step: `tests/v2/cr_index.py` verifies the pinned file's sha256 against RULES.json, then PARSES the
  file into exact numbered entries {rule id -> full entry text} (e.g. "608.3a", "733.1"); `test_rule_citations.py`
  asserts every cited rule id exists as an entry and that each recorded quotation is a verbatim substring of THAT
  entry (not of the whole file). Where the pinned text differs from this spec, the rules win and the spec is amended.
- The rules version + sha256 are part of every `GameRecord` (section 8).
- Citations below were verified against the April 17, 2026 text (103.5, 104.4a, 106.4, 117, 400.7, 500.4, 508.1,
  510.1c, 510.4, 514, 601.2a-i, 605.3a, 608.2b, 608.2n, 608.3a/b, 302.6, 110.2, 701.6a, 704.5a/b/f/g, 733.1-733.2);
  they will be re-verified against the pinned September text.

## 1. Goal and scope
One canonical two-player state machine in which the ENGINE owns every rule and every state change; players
(policies) only choose among typed legal actions from observations. Milestone one proves this on two small
synthetic decks: rules-correct for the supported card set, exactly replayable from a `GameRecord`, fail-closed on
anything unsupported.
IN: one state machine; typed `Action`s from `legal_actions()`; observation-only policies; correct mulligan, turn
structure, mana (incl. emptying), priority, stack, casting, combat (incl. first strike), SBAs, zone changes,
deck-out, win/draw; card-instance + object identity; game-owned RNG; append-only event log; exact replay; explicit
unsupported-card failures; invariants.
OUT: sideboarding / Bo3, search, human-skill modelling, oracle parsing, broad card coverage, layers beyond
"until end of turn" P/T modifications, triggered abilities, non-mana activated abilities, tokens, planeswalkers,
replacement effects, calibration, launcher/scoreboard integration.

## 2. Namespace decision: in-place consolidation vs isolated `engine/v2`
| Criterion | In-place consolidation | Isolated `engine/v2/` + adapters |
|---|---|---|
| Blast radius | 251 non-engine modules import `engine.*`; every APL mutates `GameState` | Zero until a deck is migrated |
| Engine-owns-all-changes boundary | Retrofit against ~40 mutating APLs | Designed in from line one |
| Card model | `data.card.Card` mixes definition + per-game state (tapped, counters) -> breaks CR 400.7 | Immutable `CardDefinition`, `CardInstance`, per-incarnation `GameObject` |
| Legacy numbers during rebuild | Drift continuously | Frozen, labelled experimental (strict mode) |
| Proof of correctness | Old tests encode old behaviour | New suite written against the pinned CR |
| Migration | Big-bang | Per deck, behind a flag, gated by a fidelity manifest |
**Decision (user preference, recommended): isolated `engine/v2/`**; legacy frozen. Only `engine.card_db.CardDB`
(exact, read-only printed data) is reused; enforced by an import-lint gate (M6).

## 3. Package layout (engine/v2/)
| Module | Responsibility |
|---|---|
| `ids.py` | `CardInstanceId`, `ObjectId`, `StackEntryId`, `PlayerId` allocators (monotonic per game) |
| `cards.py` | `CardDefinition` (frozen printed data + `effect_key`), `SUPPORTED` registry, `UnsupportedCardError` |
| `objects.py` | `CardInstance` (persistent physical card), `GameObject` (current incarnation), `StackEntry` |
| `state.py` | `GameState` -- mutated ONLY by `reducer.py` |
| `ops.py` | frozen engine operations (MoveObject, Tap, AddMana, SpendMana, DealDamage, LoseLife, Draw, Shuffle, ModifyPTUntilEOT, CounterStackEntry, MarkDrawFailed, LoseGame, ...) |
| `reducer.py` | the only code that applies ops to state; validates each op; emits events; groups ops into atomic transitions |
| `actions.py` | frozen player `Action`s (section 6) |
| `decisions.py` | `PendingDecision` kinds + who must decide |
| `events.py` | frozen `Event`s, `Transition` (atomic batch), chained SHA-256 log |
| `rules/` | `mulligan.py`, `turn.py`, `priority.py`, `casting.py`, `stack.py`, `mana.py`, `combat.py`, `sba.py` -- read state, return ops/decisions; never mutate |
| `effects/` | resolution functions for the card set: `(EffectContext) -> list[Op]` |
| `observation.py` | per-seat frozen `Observation` |
| `game.py` | `Game.new(config)`, `pending()`, `legal_actions(seat)`, `observe(seat)`, `apply(action)`, `run(policies)` |
| `record.py` / `replay.py` | `GameRecord` + exact replay |
| `invariants.py` | invariant checks after every atomic transition (section 11) |
| `policies/` | `RandomLegalPolicy`, `BasicScriptedPolicy` (milestone-level) |

## 4. Identity model (CR 400.7)
- `CardInstance` (id = `CardInstanceId`): one per physical card in a deck; immutable fields `definition`, `owner`;
  PERSISTS across all zones for the whole game. It is the unit of conservation.
- `GameObject` (id = `ObjectId`): the card's current rules incarnation in one zone; mutable status (tapped, marked
  damage, controller, controlled-since, "until EOT" modifications) lives here and is DISCARDED on a zone change.
  Every zone change retires the old `ObjectId` and allocates a new one for the same `CardInstanceId` (CR 400.7);
  anything referring to the old ObjectId (targets, blocks, EOT effects) no longer applies.
- `StackEntry` (id = `StackEntryId`): the spell on the stack -- `object_id`, `card_instance_id`, `controller`,
  `targets` (ObjectIds / PlayerIds, as chosen), `cast_state` (proposed / cast), chosen modes / X (none in the
  milestone set), `paid_cost`.
- Zones are ordered lists of ObjectIds; the object table maps ObjectId -> GameObject (-> CardInstanceId).
- Casting is an OPEN TRANSACTION (section 7.4). While it is open, the source ObjectId is SUSPENDED (neither live in
  its old zone nor retired) and the spell on the stack has a `ProvisionalStackId` (a separate id space, never an
  ObjectId). Only when the spell becomes cast (601.2i) is the source ObjectId retired and a new stack ObjectId
  allocated; on a CR 733 rollback the suspended ObjectId is restored to its exact prior zone position and the
  provisional id is discarded.
- Two state hashes, both canonical serialisations:
  `rules_state_hash` = the rules-visible state only (per-zone ordered ObjectIds, each object's CardInstanceId and
  status, stack entries, life totals, mana pools, turn / step / active player / priority holder, land drops used,
  mulligan counts, pending decision kind + owner, game result); and
  `full_state_hash` = rules_state_hash + engine internals (id allocator counters, RNG state, open transaction,
  provisional ids). Replay compares full_state_hash and the event-log hash; rollback compares rules_state_hash.

## 5. Engine-owned mutation (effects and rules never touch state)
- `rules/*` and `effects/*` are pure: they read an immutable view and return `Op`s and/or a `PendingDecision`.
- An effect at resolution receives an `EffectContext` (read-only view of the relevant objects, the StackEntry's
  targets after the CR 608.2b legality re-check, and the controller) and returns `Op`s. It cannot see `GameState`.
  Milestone one has NO resolution-time choices (none of its cards need one), so EffectContext has no choice hook;
  a staged resolution transaction for choices during resolution is milestone-two design. A resolution is therefore
  always one atomic transition.
- `reducer.apply(transition_ops)` validates every op against the current state (object exists, in the expected
  zone, payment legal, target legal, life change sourced) and applies it; any invalid op is an engine bug ->
  `EngineInvariantError` (never silently skipped).

## 6. Actions (frozen; every action names its `player`)
`DeclareKeep`, `DeclareMulligan`, `BottomCards(ordered_ids)`, `PassPriority`, `PlayLand(obj)`,
`ActivateManaAbility(source_obj)`, `ProposeCast(obj)`, `ChooseTargets(targets)`, `PayCost(assignment)`,
`DeclareAttackers(attackers)`, `DeclareBlockers(pairs)`, `AssignCombatDamage(attacker, division)`,
`DiscardToHandSize(ids)`, `Concede`.
- Mana (CR 605): `ActivateManaAbility(source)` is legal whenever the player has priority or is in step 601.2g of
  casting; mana floats in the pool until spent or emptied at the end of the step/phase (CR 106.4, 500.4). Excess
  mana simply empties (no mana burn).
- `PayCost(assignment)`: which pool mana (by colour) pays which cost symbol; the engine enumerates distinct
  assignments up to colour equivalence (two floating {R} are interchangeable). No implicit tapping inside PayCost.
- `legal_actions()` returns the COMPLETE legal action set with NO collapsing of objects: two untapped Mountains
  are two distinct `ActivateManaAbility` actions (which one taps is observable in state and replay). Symmetry
  reduction is optional and lives in policies (e.g. RandomLegalPolicy may group rules-identical options and sample
  a group, then a member, using the policy RNG); the engine never chooses on a player's behalf.
- Mana in a pool is not an object: units of the same type (colour / colourless, no restrictions in milestone one)
  are indistinguishable by the rules, so `PayCost` assignments are enumerated by type counts -- this is exact, not
  a collapse.
- `AssignCombatDamage(attacker, division)`: one atomic choice of the full damage division among the blockers
  (CR 510.1c -- no damage assignment order); emitted only when a choice exists (2+ blockers).

## 7. Game flow
1. Setup (CR 103): `GameConfig` fixes decks, seed, rules/card versions, turn limit and STARTING PLAYER MODE:
   `explicit(p)` (default for tests) or `random` (game RNG, logged). Libraries shuffled by the game RNG; each player
   draws 7.
2. Mulligans (CR 103.5, declaration rounds), staged so every decision is made on information the player actually
   has:
   a. DECLARE: players who have not kept declare in turn order (starting player first): `DeclareKeep` /
      `DeclareMulligan` (public). Keeping ends that player's mulligans.
   b. EXECUTE (one committed transition for all mulliganing players, simultaneously): each shuffles the hand into the
      library and draws 7 -> a PROVISIONAL hand (private: the owner sees it, the opponent sees only its count).
   c. BOTTOM (hidden decisions): each mulliganing player chooses an ORDERED `BottomCards` of exactly N cards from the
      provisional hand (N = that player's mulligan count). Decisions are collected in turn order but are not revealed
      to the other player until commit; neither player's observation changes between the two collections.
   d. COMMIT (one transition): all chosen cards go to the bottoms of their owners' libraries in the chosen order,
      simultaneously. Then the next declaration round (a) begins with the players who have not kept.
   A player may not mulligan once the opening hand would be 0 cards. Invariants run after stages b and d (the
   provisional hand is a consistent committed state).
3. Turn structure (CR 500-514): untap; upkeep; draw (starting player skips the first draw, CR 103.8a); precombat
   main; combat (beginning, declare attackers, declare blockers, first-strike damage step only when a first/double
   striker is in combat, combat damage, end of combat); postcombat main; end; cleanup (discard to 7, then damage
   removal and "until end of turn" effects end simultaneously, CR 514.1-514.2). Mana empties at the end of every step
   and phase (CR 500.4).
4. Casting (CR 601.2) as an open transaction: `ProposeCast` moves the card to the stack FIRST (601.2a) -- in the
   rules-visible state it is on the stack, represented by a StackEntry in state `proposed` with a
   `ProvisionalStackId`; the source ObjectId is suspended, not retired (section 4); then targets (601.2c, `ChooseTargets` from enumerated legal targets); then total cost
   determined (601.2f); then mana abilities may be activated (601.2g); then `PayCost` (601.2h); then the spell
   `becomes cast` (601.2i): the transaction commits -- the source ObjectId is retired, a new stack ObjectId is
   allocated for the StackEntry, and its controller receives priority.
   - `ProposeCast` is offered by `legal_actions()` ONLY when a legal completion exists (a legal target set and a
     payable cost from the pool plus untapped mana sources). There is NO voluntary cancellation action -- Magic has no
     rule for taking back a legally completable cast, so none is modelled.
   - CR 733 rollback is a separate, defensive path for an illegal or uncompletable proposal (reachable in milestone one
     only through fault-injection tests): the proposal is reversed and payments cancelled (733.1); the spell returns
     to the zone it came from; mana abilities activated during the proposal are reversed only as 733.1 permits (each
     player MAY reverse their own, unless that mana was spent on a mana ability that isn't reversed -- in milestone
     one all such abilities are basic-land taps and the controller reverses them; this is recorded as the
     player's choice); nothing that moved or revealed library cards or shuffled a library is reversed (733.1); the
     player who had priority keeps it (733.2).
   - Rollback restores the suspended source ObjectId to its prior zone position, discards the provisional stack
     identity, untaps / un-adds reversed mana abilities, and closes the transaction. Afterwards the
     `rules_state_hash` equals its pre-proposal value exactly (same ObjectIds, zones, pools, tapped states,
     priority); `full_state_hash` and the event-log hash may advance (allocator counters, a `ProposalReverted`
     event) and do so reproducibly. No ObjectId is reused or rewound.
5. Priority (CR 117): as revision 1 (active player first; action -> same player gets priority; both pass on an empty
   stack -> advance; both pass on a non-empty stack -> resolve top, then active player gets priority; SBAs before
   priority, CR 117.5). Timing restrictions for lands / sorcery-speed spells unchanged (CR 305.2, 307.1).
6. Resolution (CR 608), by card type, always one atomic transition:
   - Instant / sorcery: targets re-checked (608.2b); all illegal -> doesn't resolve, removed from the stack to its
     owner's graveyard (`SpellFizzled`); otherwise the effect returns ops for the legal targets, then the spell goes
     to its owner's graveyard as the final part of resolution (608.2n). Each move is a new ObjectId.
   - Permanent spell (the milestone set's creatures; none has targets): it becomes a permanent and enters the
     battlefield under the control of the SPELL'S CONTROLLER (608.3a, 110.2) as a NEW ObjectId (same CardInstanceId),
     untapped, with `controlled_since_turn` = the current turn, so it cannot attack or be tapped for a {T} cost until
     its controller's next turn unless it has haste (302.6).
   - Countered spell (Counterspell): removed from the stack to its owner's graveyard (701.6a), no effects.
7. Combat (CR 506-511): attacker eligibility + tapping (508.1a/508.1f, vigilance), flying/reach blocking (702.9b),
   first strike (510.4), damage division (510.1c). Each combat damage step is ONE atomic transition (all damage
   simultaneous, CR 510.2), followed by SBAs.
8. SBAs (CR 704): computed on the state as a whole and applied as ONE atomic transition (all SBAs simultaneous):
   player at <= 0 life (704.5a); player with the `attempted_draw_from_empty` flag (set by a `DrawFailed` event when a
   draw from an empty library is attempted, CR 704.5b; cleared after the check); creature toughness <= 0 (704.5f);
   lethal damage (704.5g). Repeated until no SBA applies. If all players would lose in the same transition the game
   is a DRAW (104.4a) -- no winner is decided mid-batch.
9. End: `GameResult` = WIN(p, reason) / DRAW(reason); `turn_limit` (config, default 50) -> DRAW('turn_limit').

## 8. Events, transitions, record, replay
- Every `Op` applied produces an `Event`; ops are applied in `Transition`s (atomic batches with an id and a kind:
  action, turn-based action, combat damage, SBA check, mulligan round, resolution, rollback). The log is append-only
  and each transition is hashed (canonical serialisation, chained SHA-256).
- `GameRecord` = {engine version, rules version + sha256, card-data identity (see below), RNG algorithm id (e.g. "python-mt19937/3.13"), game seed, starting-player mode + result,
  turn limit, decks (card names in order), actions applied (with player and transition index)}.
- Card-data identity (what the engine actually loaded, not a manifest): `definitions_hash` = SHA-256 of the
  canonical serialisation (sorted by name; UTF-8; fixed field order) of EVERY `CardDefinition` in `SUPPORTED` --
  all printed fields the engine reads (name, mana cost, mana value, colours, types, subtypes, power, toughness,
  keywords) plus its `effect_key` and the effect implementation's version string. Also recorded:
  `oracle_file_sha256` = SHA-256 of the installed converted `scryfall_oracle_cards.json` the definitions were built
  from (computed at load; M0 adds it to SNAPSHOT.json as `installed_sha256`, and `Game.new` refuses to start when
  the installed file's hash differs from SNAPSHOT.json). `replay()` refuses a record whose `definitions_hash`
  differs from the current engine's (`CardDataMismatch`), since untracked bulk files can change under an unchanged
  manifest.
- Policies get their OWN seeded RNG (derived from a policy seed, recorded separately); the game RNG is never
  exposed to policies, so policy sampling cannot perturb shuffles or other game randomness.
- `replay(record)` re-applies the recorded actions without consulting policies and must reproduce the identical
  transition hashes and final state hash; divergence -> `ReplayMismatch` naming the first differing transition.

## 9. Milestone card set and synthetic decks (deliberately limited)
| Card | Exercises |
|---|---|
| Plains, Island, Mountain, Forest | mana abilities, floating mana, emptying, land drop |
| Grizzly Bears (2/2, {1}{G}) | vanilla creature, summoning sickness |
| Hill Giant (3/3, {3}{R}) | generic + coloured payment |
| Raging Goblin (1/1 haste, {R}) | haste |
| Youthful Knight (2/1 first strike, {1}{W}) | first-strike damage step |
| Wind Drake (2/2 flying, {2}{U}) | flying / blocking restriction |
| Serra Angel (4/4 flying, vigilance, {3}{W}{W}) | vigilance, damage division when double-blocked |
| Lightning Bolt (instant: 3 damage to any target) | targeting, 608.2b fizzle, player damage |
| Giant Growth (instant: +3/+3 until EOT) | EOT effect, cleanup wear-off, new-object rule |
| Counterspell (instant: counter target spell) | stack interaction, counter a counter |
| Divination (sorcery: draw two) | sorcery timing, draws, deck-out (DrawFailed) |
Deck A "RG" (40): 12 Mountain, 8 Forest, 4 Raging Goblin, 4 Grizzly Bears, 4 Hill Giant, 4 Lightning Bolt,
4 Giant Growth. Deck B "WU" (40): 10 Plains, 10 Island, 4 Youthful Knight, 4 Wind Drake, 4 Serra Angel,
4 Counterspell, 4 Divination. Fixture `DECKOUT` (10 cards) forces library exhaustion. Lists pinned in
`tests/v2/decks.py`; deck-construction legality is not a milestone-one rule.

## 10. Unsupported-card behaviour
`Game.new` validates both decks: every name resolves exactly in CardDB AND is in `SUPPORTED`, else
`UnsupportedCardError(names)`. Every `SUPPORTED` entry has an effect implementation (registry completeness test at
import). No runtime "unknown effect" path exists.

## 11. Invariants (checked after every atomic transition, never mid-transition)
- I1 Card conservation: for each player the SET of CardInstanceIds across library, hand, battlefield, graveyard,
  exile and the stack equals the deck's CardInstanceIds exactly, with unchanged definition and owner per instance.
- I2 Identity + zones: every live ObjectId is in exactly one zone and maps to exactly one CardInstance; each
  CardInstance has exactly one live-or-suspended ObjectId (suspended only while its casting transaction is open,
  and then it has a ProvisionalStackId on the stack); retired ObjectIds never reappear; ProvisionalStackIds are never
  ObjectIds; every committed ZoneChanged event allocates a new ObjectId; no transaction is open at a transition
  boundary other than an in-progress casting.
- I3 Payments: every cast's `PayCost` assignment covers the locked-in total cost exactly (colour requirements, mana
  value) from pool mana the payer owns; mana was produced only by the payer's untapped mana sources; pools are empty
  at every step/phase boundary.
- I4 Targets: targets legal when chosen; at resolution illegal targets are ignored; all-illegal -> fizzle, no ops.
- I5 Priority/timing: only the decision owner acts; no sorcery-speed action with a non-empty stack or outside the
  player's own main phase; <= 1 land per turn; step advances only after two consecutive passes on an empty stack;
  no StackEntry remains in state `proposed` after its transition.
- I6 Combat: attackers eligible and tapped unless vigilance; blocks respect flying; first strikers deal damage only in
  the first-strike step; each attacker's division sums to its power among its blockers.
- I7 Hand <= 7 after cleanup; life changes only via LifeChanged events; the game result is decided only in an SBA
  transition, concession, or turn limit.
- I8 Determinism: replay reproduces all transition hashes; no global `random` / time / unordered iteration in
  engine code (guard + lint).
- I9 Policy isolation: policies receive only `Observation` + legal actions + their own RNG; observations are frozen;
  a mutating test policy fails.

## 12. Acceptance gates (pre-registered)
- M0 RULES BASELINE: current CR downloaded (with permission), pinned in RULES.json; the file hash matches; the parser
  yields exact numbered entries; every cited rule id exists and every recorded quotation is verbatim within its own
  entry.
- M1 RULES UNIT TESTS (each cites a pinned CR rule): London mulligan stages (declaration order; simultaneous
  execute; BottomCards chosen only after seeing the provisional 7, hidden from the opponent until commit, ordered, N
  exact; simultaneous commit; repeated rounds; zero-card floor); creature spell resolves onto the battlefield under
  the spell's controller with a new ObjectId, same CardInstanceId, and cannot attack that turn (Grizzly Bears) while
  Raging Goblin can (haste); instant/sorcery to its owner's graveyard after resolving; countered spell to graveyard;
  two untapped Mountains produce two distinct legal ActivateManaAbility actions and the chosen one is the one tapped
  (visible in state and replay); starting player skips first draw; floating mana empties
  between steps; ActivateManaAbility outside casting; one land per turn; sorcery/land timing; summoning sickness vs
  haste; attackers tap, Serra Angel does not; flying block restriction; 2/1 first striker vs 2/2 blocker: blocker
  dies, first striker survives; first strike vs first strike; Serra Angel double-blocked by Grizzly Bears + Raging
  Goblin: every division 4/0, 3/1, 2/2, 1/3, 0/4 legal and applied atomically; Bolt fizzles when its target left
  the battlefield (new object); Bolt at a player; Giant Growth saves from Bolt and wears off in cleanup; Giant
  Growth on a creature that changed zones does not affect the new object; Counterspell counters; counter-the-counter
  lets the original resolve; ProposeCast is NOT offered when no legal completion exists (Giant Growth with no
  creature on the battlefield; Counterspell with an empty stack; unpayable cost) -- Lightning Bolt stays castable
  with no creatures because players are legal targets; fault-injected
  illegal proposal -> CR 733 rollback: `rules_state_hash` equals the pre-proposal value, the source card is back
  under its ORIGINAL ObjectId in its original zone position, no ObjectId was reused, `full_state_hash` / event-log
  hash advance reproducibly (ProposalReverted), the player who had priority keeps it; a completed cast retires the
  source ObjectId and gives the stack entry a new one; drawing from an empty library -> DrawFailed -> loss at the next SBA
  transition; both players at <= 0 in one combat damage transition -> DRAW; turn limit -> DRAW; discard to 7.
- M2 FUZZ: 10,000 games RandomLegalPolicy vs RandomLegalPolicy (RG vs WU, explicit starting player alternating,
  game seeds 0..9,999, policy seeds recorded): 0 invariant violations, 0 exceptions, every game ends with a result
  and reason.
- M3 REPLAY: every M2 record replays with identical transition hashes and final state hash (100%); plus 100 records
  replayed after re-shuffling policy seeds to prove policy RNG does not affect game RNG streams.
- M4 SCRIPTED: 1,000 games BasicScriptedPolicy RG vs WU complete; outcome distribution + mean length reported only.
- M5 UNSUPPORTED + CARD DATA: non-registry card -> UnsupportedCardError naming it; misspelled card -> card-identity
  error; neither starts a game. `definitions_hash` is stable across two processes; changing one printed field of one
  supported card in a test fixture changes it; replay of a record with a different `definitions_hash` raises
  CardDataMismatch; an installed oracle file whose sha256 differs from SNAPSHOT.json `installed_sha256` blocks
  `Game.new`.
- M6 ISOLATION: `engine/v2` imports nothing from legacy engine modules except `engine.card_db` (import-lint test);
  existing suite unchanged (pytest 167 passed / 3 failed / 4 errors + new v2 tests).
- M7 PERFORMANCE (reported): games/s single core for random policies on the synthetic decks; target >= 200,
  blocker only if < 20.

## 13. Adapters and gradual migration (designed now, built after milestone one)
Unchanged from revision 1: `adapters/legacy_deck.py` loads legacy decklists only when every card is SUPPORTED;
real-deck policies are written against Observation/Action (porting today's APL priorities, not wrapping mutating
APL code); launcher integration later behind `--engine v2`; a per-deck fidelity manifest gates each migrated deck.
Post-M1 order: effect library by mechanic family with rules tests; one real matchup end to end; Bo3 +
sideboarding; search / skill policies; calibration against the scoreboard.

## 14. Expected behavioural changes vs legacy (NOT compatibility requirements)
Old seeded win rates are not preserved; reproducibility is via `GameRecord` replay. v2 keeps 7-N after N
mulligans with correct declaration rounds; empties mana between steps; taps attackers; resolves first strike
correctly; divides multi-block damage freely (no assignment order); loses on deck-out; draws on turn limit and on
simultaneous loss; forbids sorcery-speed actions on the opponent's turn; counters only stack entries; rejects any
action outside `legal_actions()`; refuses unsupported cards. Matchup numbers will move and are not comparable with
legacy numbers.

## 15. Risks / open questions
- Payment enumeration size is bounded by the basic-lands-only milestone and colour-equivalence; nonbasic sources are
  milestone-two design.
- Atomic transitions: the reducer applies a whole batch or none (copy-on-write of touched objects during a
  transition, committed at the end) -- needed for CR 733 rollback and for invariant timing.
- Performance vs immutability: state mutated only inside the reducer; observations are frozen snapshots; profile
  before redesigning if M7 is badly missed.
- Continuous effects limited to "until end of turn" P/T; layers are milestone two.
- The synthetic decks are for rules coverage, not balance; M4 distributions are reported only.

## 16. Revision 2 -- review findings addressed (review 2026-09-30, "not approved yet")
| # | Finding | Resolution |
|---|---|---|
| P1 | Pin the current rules baseline (repo text is April 17, 2026; Wizards publishes Sept 25, 2026) | Section 0.1 + gate M0; rules version/hash in GameRecord (section 8). Repo date verified; the September text is downloaded only with user permission at M0 |
| P1 | Separate card and object identity | Section 4: CardInstanceId (persistent) vs ObjectId (per incarnation) vs StackEntryId; I1 checks the exact CardInstanceId set + definitions + owners; I2 identity rules |
| P1 | Correct the mulligan sequence | Section 7.2: declaration rounds, simultaneous mulligans, immediate ordered BottomCards per mulligan, repeated rounds, zero-card floor (verified against CR 103.5 text); M1 tests |
| P1 | Stack + effect boundaries | Section 7.4: ProposeCast moves to the stack first (601.2a), StackEntry with targets/cast state/paid cost, CR 733 rollback; section 5: effects get an EffectContext and return ops; only the reducer mutates |
| P1 | Atomic simultaneous changes | Sections 7.7-7.8, 8, 11: atomic Transitions for combat damage, SBAs, mulligan rounds, resolutions, rollback; invariants after transitions only; DrawFailed event + attempted_draw_from_empty flag (704.5b); simultaneous loss -> DRAW |
| P1 | Remove damage assignment order | OrderBlockers removed; AssignCombatDamage(attacker, division) is one atomic choice (verified against CR 510.1c text); M1 tests all divisions of a double block |
| P2 | Explicit play/draw + RNG | Section 7.1 starting-player mode (explicit default, random optional); GameRecord records mode, turn limit, rules/card hashes, RNG algorithm; separate policy RNG (section 8, M3) |
| P2 | Complete the mana action surface | Section 6: ActivateManaAbility(source) with floating/excess mana; PayCost pays from the pool; legal_actions is the complete set except one documented canonicalisation (identical objects -> lowest ObjectId) -- SUPERSEDED in rev 3: no collapsing (section 17) |

## 17. Revision 3 -- review of revision 2 addressed (review 2026-09-30, "not approved yet")
| # | Finding | Resolution |
|---|---|---|
| P1 | Permanent spells resolve to the battlefield | Section 7.6 by type: creatures enter under the spell's controller as a new ObjectId, summoning-sick (608.3a, 110.2, 302.6); instants/sorceries 608.2n; countered 701.6a; M1 tests |
| P1 | Mulligans need a staged decision boundary | Section 7.2: declare -> execute (provisional private hand) -> hidden ordered BottomCards -> simultaneous commit -> next round; invariants after execute and commit; M1 tests |
| P1 | Rollback state vs log hashes | Section 7.4: gameplay-state hash returns to its prior value, event-log hash advances by ProposalReverted; no voluntary cancellation (ProposeCast offered only when completable); CR 733.1/733.2 semantics incl. conditional mana-ability reversal and irreversible library actions; M1 tests |
| P1 | Pending choices break atomic resolution | Section 5: EffectContext has no choice hook in milestone one (no card needs one); resolution always one atomic transition; staged resolution = milestone two |
| P1 | Preserve distinct legal object choices | Section 6: legal_actions exhaustive (two Mountains = two actions); symmetry reduction only inside policies; pool mana enumerated by type because mana is not an object; M1 test |
| minor | Rule-citation check | Section 0.1 / M0: parse exact numbered entries from the hash-verified pinned file; quotations must be verbatim within their own entry |

## 18. Revision 4 -- review of revision 3 addressed (review 2026-09-30, "not approved yet", 2 findings)
| # | Finding | Resolution |
|---|---|---|
| P1 | Rollback conflicts with identity invariants (monotonic ids, retired ids never reappear) | Casting is an open transaction: source ObjectId suspended (not retired), ProvisionalStackId on the stack, retire + allocate only at 601.2i, restore the suspended id on rollback (sections 4, 7.4); rollback compares `rules_state_hash`, while `full_state_hash` and the event log may advance (sections 4, 7.4, 12); I2 amended |
| P2 | Card-data hash pins the manifest, not the loaded definitions | `definitions_hash` over the canonical serialisation of every supported CardDefinition + effect key + implementation version, plus `oracle_file_sha256` of the installed file checked against SNAPSHOT.json `installed_sha256`; replay refuses mismatches (section 8, M5) |

## Changelog
- 2026-09-30: PROPOSED revision 1 (harness 1b8ecdc).
- 2026-09-30: review -- not approved yet (8 findings). Revision 2 addresses all 8 (section 16); rule texts for
  103.5, 510.1c, 601.2a-i, 704.5b, 733 checked against the repo's April 17, 2026 CR before revising.
- 2026-09-30: review of revision 2 -- not approved yet (5 P1 + 1 minor). Revision 3 addresses them (section 17);
  608.2b/608.2n/608.3a-b/302.6/110.2/701.6a/733.1-733.2 texts checked against the repo CR first.
- 2026-09-30: review of revision 3 -- not approved yet (1 P1 + 1 P2); prior findings confirmed resolved. Revision 4
  addresses both (section 18).
- 2026-09-30: revision 4 APPROVED for implementation (user); rules download approved -> EXECUTING.
- 2026-09-30: milestone one SHIPPED (mtg-sim 45755d5, 64d56c5, 8dce033; not pushed).

## Milestone-one results
| Gate | Result | Evidence |
|---|---|---|
| M0 RULES BASELINE | PASS | CR effective 2026-09-25 downloaded with permission (977,752 bytes), sha256 8d860e45... pinned in data/rules_reference/RULES.json; parser -> 3,312 numbered entries; 50 citations verbatim within their own entry; every "CR x" in engine/v2 is cited (tests/v2/test_rule_citations.py, 4 tests) |
| M1 RULES UNIT TESTS | PASS | tests/v2/test_m1_rules.py: 28 tests (mulligan stages x4, first draw skip, untap step, mana floating/emptying, two identical lands, land drop + timing, instants-only on opponent's turn, creature resolution identity, haste, vigilance, flying, first strike x2, damage division (all 4 splits, atomic), Bolt fizzle, Bolt face, Giant Growth save + wear-off, new-object rule, Counterspell + counter-the-counter, ProposeCast completability, CR 733 rollback, deck-out, simultaneous loss, turn limit, discard to 7) |
| M2 FUZZ | PASS | 10,000 RandomLegal games, invariants after every transition: 0 exceptions, 0 violations; 9,756 win:life, 244 draw:turn_limit; mean 932 actions (data/v2_acceptance.json) |
| M3 REPLAY | PASS | 10,000 / 10,000 records replay with identical transition hashes + full state hash (in-worker, final run on 7ecc9ef); 300 stored JSON records (39 turn-limit draws, 228 with mulligans) replay exactly in fresh processes with PYTHONHASHSEED unset and =31337; tests/v2/test_determinism.py replays stored JSON in fresh processes (unset / 4242 / 7); records now carry the resolved starting player and each action's transition index, both verified on replay |
| M4 SCRIPTED | PASS (reported) | 1,000 BasicScripted games complete, 0 errors; WU won 897, RG 103; mean 18.1 turns (lopsided by design, not calibrated) |
| I8 DETERMINISM | PASS | AST lint (no global random / time / datetime in engine/v2); guard test makes the global random functions raise over full random + scripted games; policy-RNG isolation: noisy vs plain scripted policies give identical logs and RNG state across 20 seeds covering 6 post-decision (mulligan) shuffles |
| M5 UNSUPPORTED + CARD DATA | PASS | tests/v2/test_m5_m6.py: unsupported (Llanowar Elves) and misspelled cards refused before start; definitions_hash stable across processes, changes with one printed field; replay refuses a different definitions_hash; installed-oracle sha mismatch blocks Game.new |
| M6 ISOLATION | PASS | import-lint: engine/v2 imports only engine.v2.*, engine.card_db and stdlib; no legacy engine file changed; pytest 222 passed (167 baseline + 55 v2) / same 3 failed / 4 errors |
| M7 PERFORMANCE | reported: 20.55 and 22.42 games/s CPU in final implementation runs; independent review 21.62 | above the 20 blocker with a thin margin, below the 200 target; excludes observation building for RandomLegalPolicy (A5), uses lazy hash-chain computation (A6), invariants off, card data preloaded |

Pre-existing failures (unchanged, not v2): tests/test_api.py::test_list_decks, ::test_meta_solve,
tests/test_response_capability.py::test_removal_golden_apl_extensions; 4 collection errors (DB-less APL suites).

## Implementation amendments (documented deviations; no gate changed)
- A1 Rules citation: mana emptying at the end of a step/phase is CR 500.5 (and 106.4) in the pinned 2026-09-25 text;
  500.4 (this spec) is about effects expiring as a step begins. Code cites 500.5/106.4.
- A2 M1 damage-division test: Serra Angel cannot be double-blocked by Grizzly Bears + Raging Goblin (702.9b flying);
  the test uses Hill Giant (3 power) blocked by Youthful Knight + Wind Drake -> divisions 3/0, 2/1, 1/2, 0/3.
- A3 M1 simultaneous loss: no milestone card damages both players in one transition; the test arranges both at 0
  life (reducer ops in a test_arrange transition) and the next SBA transition must yield DRAW (104.4a).
- A4 Attacker / blocker declarations are staged per creature (ChooseAttack / ChooseBlock) and committed atomically;
  every legal declaration is reachable and the full cartesian set is never enumerated (no cross-creature block
  requirements exist in the card set).
- A5 Policies may declare `uses_observation = False` (RandomLegalPolicy); the observation is then not built. Policies
  that read the game always receive the full frozen Observation.
- A6 Event-log hash chain is computed lazily and incrementally on first request; values identical to an eager chain
  (verified by identical heads per seed and by M3).
- A7 Step end (pool emptying, CR 500.5) and the next step's start commit as ONE atomic transition (invariants after
  it). Found and fixed during M7 work: merging the turn change into the untap step captured the previous active
  player; the reducer now reads the active player at apply time; new M1 test (CR 502.3) proven red on the bug.
- A8 Isolation note: engine/v2 lives inside the `engine` package, so importing it runs legacy `engine/__init__.py`
  (imports GameState / Zones / ManaPool) as a side effect; v2 code itself imports only engine.card_db (M6 lint).

- A9 CR 733 mana-ability reversal is an engine parameter of the (fault-injection-only) rollback path, not a recorded player
  decision as section 7.4 describes; milestone one reverses them (733.1 permits it for basic-land taps). A player choice is
  milestone-two work if the path becomes reachable.
- A10 Review-gap fixes before the report: GameState builds its zones (Game.new no longer assigns them); GameRecord adds
  the resolved starting player and per-action transition indices (verified by replay); citation scan extended to tests/v2.
- A11 Registry size: 14 cards, exactly the approved section-9 table (4 basic lands, 6 creatures, 4 spells); earlier
  summaries saying "15" were wrong.
- Regression note: one M7 optimisation (A7) introduced the wrong-player untap; it was caught by comparing per-seed game
  lengths against the committed engine, not by a gate; a CR 502.3 test proven red on the bug now covers it.

## Findings / follow-ups (not milestone one)
- M7 is 23 games/s vs the 200 target: the per-transition cost (op objects, event records, frozen Action lists) is
  the floor in pure Python; options for later: batch priority passes, precompiled legal-action tables, or a
  compiled core once the state machine stabilises.
- Next per section 13: effect library by mechanic family with rules tests; one real matchup end to end with a
  fidelity manifest; Bo3 + sideboarding; search / skill policies; calibration.
