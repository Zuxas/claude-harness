---
title: "Engine v2 milestone three: real-gameplay comparison + experimental launcher option"
status: "SHIPPED"
created: "2026-10-01"
updated: "2026-10-01"
project: "mtg-sim"
estimated_time: "one session"
related_findings:
  - "harness/specs/2026-09-30-v2-m2-burn-mirror-proposal.md"
related_commits:
  - "mtg-sim 055a373 (anonymized gameplay comparison + launcher option)"
supersedes: null
superseded_by: null
---

# Engine v2 milestone three

Brief (user, 2026-10-01): compare v2 with real Burn gameplay from local MTGO data; only engine-rules or
card bugs may change the engine; then, if the comparison gate passes, add v2 to the launcher as an explicit
experimental option (default unchanged, no fallback, refusal with exact names, seeds, replayable records,
distinct result classes, no floors / substitution / swallowed exceptions, single game + Bo3).

## Phase 1 -- real-gameplay comparison (gate PASS)

Data: the analyzer's MTGO import snapshot (461 Match_GameLog_*.dat files; 371 distinct matches with
episodes). Burn coverage is thin: 9 matches (16 games) have a Burn player, always the opponent, each on a
different list with cards v2 does not support (Boltwave, Seal of Fire, Arena of Glory, Chandra's
Incinerator, ...), so no complete Burn game can be replayed end to end; the comparison is episode-level.
Episodes come from all logs whenever the cards involved are supported (e.g. Swiftspear in Prowess decks,
Boros Charm / Helix in Boros Energy). Fixtures normalize each observed episode into a supported synthetic
pre-state; they are a conformance corpus for supported mechanic shapes, not full-game parity evidence.
Committed fixtures replace account names with `PlayerA` / `PlayerB` and raw match ids with deterministic
12-character hashes while retaining source line numbers for local traceability.

| Mechanic | Fixtures | Pass | Notes |
|---|---|---|---|
| mulligan (London bottoming) | 480 | 480 | MTGO bottoms at the keep; CR 103.5 (pinned) and v2 bottom as part of each mulligan -- same observables |
| play/draw chooser (CR 103.1) | 470 | 469 | 1 not reconstructable (previous result not determinable) |
| prowess (noncreature spell) | 450 | 450 | unsupported spells replaced by a noncreature stand-in (recorded) |
| prowess vs creature spells | 14 | 13 | 1 parser ambiguity (trigger listed after a creature spell belongs to the chain's noncreature spell) |
| fetch activation | 331 | 331 | the searched card and life payment are not logged |
| Lightning Bolt targets | 163 | 155 | 8 unsupported (planeswalker / token targets) |
| Lightning Helix targets | 45 | 44 | 1 unsupported (token target) |
| Boros Charm modes | 53 | 53 | all three modes observed |
| Roiling Vortex | 17 | 17 | upkeep triggers + 2 no-mana-cast triggers (evoke / free cast; tested with a suspend stand-in) |
| Rift Bolt suspend | 11 | 11 | special action, counter removal at upkeep, free cast |
| Goblin Guide attacks | 12 | 12 | one trigger + reveal per attacking Guide |
| Searing Blaze | 7 | 7 | player + creature that player controls; landfall from the caster's own land this turn |
| Skewer spectacle | 13 | 13 | precondition logged in some cases; MTGO enforces it otherwise |
| Lava Spike / Skullcrack targets | 12 | 12 | players only |

Totals: 2,078 fixtures, 2,067 pass (416 with recorded stand-ins), 11 explained non-passes (9 unsupported
mechanics, 2 parser/data ambiguities), 0 engine-rules bugs, 0 card-implementation bugs -> no engine change.
Harness / parser issues found and fixed on the comparison side only: digit-bearing player names in turn
lines, duplicated mulligan lines, match-level player list, arranged lands counting as landfall, a runner
counting two upkeeps, a runner conceding off-turn.

Observation (not changed): CR 104.3a lets a player concede at any time; v2 offers Concede only to the
player with the pending decision (milestone-one design).

## Phase 2 -- experimental launcher option

`parallel_launcher.py --engine v2 ...` (see mtg-sim CLAUDE.md). Legacy default unchanged; both decks must be
explicit; counts and turn limits must be positive; missing or malformed deck/sideboard files are refused before play;
pilots separate from the engine; seeds; replayable records; refusal before play with exact names; distinct
result classes incl. ENGINE ERRORS (exit 1); no fallback. tests/v2/test_launcher_v2.py proves each item.

## Verification

v2 suite 164 passed; full suite 331 passed with the same 3 pre-existing failures and 4 collection errors;
launcher smoke through the real entry point (game, Bo3, refusals, replay). M7 ~20 g/s this session while a
stuck harness graph-snapshot.py process (since 04:30) consumed a core; the engine code is identical to the
24.29 g/s in-process measurement (only decklists.py path handling changed).

## Remaining unsupported

Only decks/mono_red_aggro_modern.txt is fully supported (none other within 3 cards). Most common missing
cards: Swamp, Multiversal Passage, Steam Vents, Starting Town, Spirebluff Canal, Hallowed Fountain,
Watery Grave, Flooded Strand, Spell Snare, Riverpyre Verge, Llanowar Elves, Quantum Riddler. Unsupported
mechanics: planeswalkers, tokens, counters beyond time counters, copy effects, transform / MDFC, layers
beyond until-end-of-turn P/T, X costs, most replacement effects, flash / evoke / other alternative costs.
