---
title: "Oracle-driven priority responses — retire the counter/removal whitelists"
status: "PROPOSED"
created: "2026-07-01"
updated: "2026-07-01"
project: "mtg-sim"
estimated_time: "3-7 days (M-L); parallel-safe with B1 (different files, shared seam)"
related_findings:
  - "E:\\vscode ai project\\AUDIT-ENGINE-APL-2026-07-01.md (Part A #2)"
  - "harness/knowledge/tech/calibration-probe-2026-07-01.md (P1 inversion = empirical driver)"
related_commits: []
supersedes: null
superseded_by: null
---

# Spec: oracle-driven responses

## Goal
Replace the hardcoded response tables (engine/counter_resolver.py ~17 counters;
R1-path removal list ~60 cards) with predicates derived from oracle text, so ANY
counterspell/instant-removal in a decklist can act in priority windows. Empirical
driver: calibration probe P1 (Dimir 13.1% vs truth ~40%) shows interactive decks now
drown because their interaction under-fires while proactive combat is fully modeled.

## Scope
IN: generic classification of instants/flash spells into response kinds
(COUNTER_ANY / COUNTER_NONCREATURE / COUNTER_UNLESS_PAY_N / REMOVAL_DMG_N /
REMOVAL_DESTROY / BOUNCE) + cost payment via the existing honest-mana path.
OUT: modal spells beyond first mode, counter-abilities on permanents, replacement
effects; response POLICY quality (that is APL/search territory, not classification).

## Pre-flight reads (MANDATORY)
1. harness/knowledge/tech/spec-authoring-lessons.md
2. engine/counter_resolver.py in full (the predicate/cost table shape to preserve)
3. engine/priority_stack.py (where the whitelist is consulted)
4. engine/oracle_parser.py + card_handlers_verified.py header (existing oracle-text
   machinery — REUSE the parsing idioms; do not write a second parser dialect)
5. mismodeled_matchups.py (cells expected to move; NO reverse-fitting)

## Steps
1. **Classifier**: `engine/response_classifier.py::classify(card) -> ResponseSpec|None`
   from oracle text patterns ("counter target spell", "counter target ... unless ...
   pays {N}", "deals N damage to target creature", "destroy target creature",
   "return target ... to its owner's hand"), reusing oracle_parser normalization
   (// splits, em-dash stripping) verbatim.
2. **Golden test**: classifier must reproduce the EXISTING whitelist exactly — every
   currently-listed card classifies to the same predicate+cost the table encodes.
   This is the no-regression anchor.
3. **Coverage sweep**: run classifier over every instant/flash card in decks/ (158
   decks); emit data/response_coverage.csv (card, deck, classified-as, or UNHANDLED).
   Target: >=80% of instant-speed cards in competitive decklists classified.
4. **Swap consultation site**: priority_stack consults classifier first, static table
   as fallback; feature-gate `WANTS_ORACLE_RESPONSES` per R-ladder convention,
   gate-OFF byte-identical (their established pattern).
5. **Measure, don't tune**: re-run probe pairs P1/P2 (n=2000, same seeds) + Boros-vs-
   Affinity n=300 gate-OFF/gate-ON. Record movement; update mismodeled_matchups.py
   entries HONESTLY (direction language, no band-forcing).

## Validation gates (falsifiable)
- G1 golden: 100% of whitelist cards classify identically to the table.
- G2 gate-OFF: byte-identical same-seed runs (n=300 Boros-vs-Affinity).
- G3 coverage: >=80% of instant/flash cards across decks/ classified (report actual).
- G4 direction: gate-ON, P1 Dimir WR moves UP from 13.1% (any significant rise
  validates the mechanism; hitting ~40% is NOT required and must not be tuned for).
- G5 conservation: 10k-game gauntlet slice, zero new exceptions, card-count invariant.

## Stop conditions
- G1 golden mismatch on >2 cards: stop — the pattern grammar is wrong, fix grammar,
  never special-case the golden set.
- Classifier misfires causing illegal engine states (targeting something untargetable):
  stop, add the legality check at the CONSULTATION site (shared with B1's seam), resume.
- P1 moves DOWN under gate-ON: stop — model is wrong somewhere upstream; write findings,
  do not ship gate-ON as default.

## Annotated imperfections (known at authoring)
- Policy remains crude (respond-if-able heuristics) until search exists; this spec
  fixes CAPABILITY, not judgment.
- UNHANDLED tail (<20%) stays whitelist-covered or inert — listed in coverage CSV,
  not silently wrong.
