---
title: "B1 — Legal-action enumeration API + cheap state fork (the ISMCTS gate)"
status: "EXECUTING"
created: "2026-07-01"
updated: "2026-07-01"
project: "mtg-sim"
estimated_time: "1-2 weeks (L); Steps 1-3 are a shippable first slice (~2-3 days)"
related_findings:
  - "E:\\vscode ai project\\AUDIT-ENGINE-APL-2026-07-01.md (Part A #1, #3, #5)"
  - "harness/knowledge/tech/calibration-probe-2026-07-01.md"
  - "harness/reports/PRODUCTION-ROADMAP-2026-06-26.md (P3/B1)"
related_commits: []
supersedes: null
superseded_by: null
---

# Spec: B1 legal-action API + O(1)-ish fork

## Goal
Give the match engine the two capabilities ISMCTS requires and the audit verified are
absent: (a) enumerate every legal action from a state; (b) fork a state cheaply and
reproducibly. After B1, a search loop can drive games without any APL choosing moves.

## Scope
IN: new `engine/decision_api.py` with `reset/observe/legal_actions/step/fork`;
action dataclass; fork via structured copy (not per-card deepcopy); per-state RNG.
OUT: hidden-info masking (B3 exists via R6 gates), the search loop itself (P5),
oracle-driven responses (separate spec, parallel-safe).

## Pre-flight reads (MANDATORY)
1. harness/knowledge/tech/spec-authoring-lessons.md
2. AUDIT-ENGINE-APL-2026-07-01.md Part A (whitelist scope, deepcopy sites
   match_runner.py:106-107 + match_state.py:107, global-RNG consumers list)
3. engine/match_engine.py (priority pass integration, ~L152-230)
4. engine/priority_stack.py + engine/stack.py in full
5. apl/match_apl.py + apl/aware_match_apl.py (what APLs currently decide — the
   action vocabulary must cover everything they can do, or search is weaker than APLs)

## Steps
1. **Action vocabulary.** Enumerate every decision the APL layer currently makes by
   grepping the MatchAPL/AwareMatchAPL surface: play_land(choice), cast(card, targets),
   activate(ability, targets), attack(set), block(assignment), respond(counter/removal/
   pass) in priority windows, mulligan(keep/bottom). Emit `Action` dataclass
   (kind, card_uid, targets, seat). Deliverable: docs/action-vocabulary.md table
   mapping each APL decision site -> Action kind.
2. **`legal_actions(state, seat) -> list[Action]`** for main-phase actions first
   (land, casts by castability check, activations). Reuse existing castability/mana
   logic — do NOT reimplement payment rules.
3. **`step(state, action) -> state`** routing through the SAME code paths APLs use
   (gs.cast_spell, put_into_play, run_priority_pass) so engine fidelity is inherited,
   never re-derived.
4. **Priority-window actions**: legal responses during run_priority_pass (currently
   whitelist-bound; enumerate from the whitelist NOW, widen automatically when the
   oracle-driven-responses spec lands — design the seam, don't block on it).
5. **Combat actions**: attack sets (cap enumeration: singletons + all + APL-suggested
   set to bound branching), block assignments likewise.
6. **Fork**: replace per-card deepcopy with a copy strategy measured >=10x faster
   (immutable card objects shared, zone lists shallow-copied, mutable per-card state
   externalized to a dict). Thread a per-state `random.Random` and migrate the 13
   global-random consumers (zones.py:29, opponent.py:245, race.py:44, runner.py:189,
   ~9 handler sites) to receive it. THIS SUBSUMES the fork/RNG item — one refactor.
7. **Parity harness**: replay 3 recorded APL games action-by-action through step();
   final states must match the direct-run states field-for-field.

## Validation gates (falsifiable)
- G1 parity: 3 replayed games byte-identical final state vs direct run.
- G2 legality: 10k random legal_actions()->step() walks, zero engine exceptions,
  card-count conservation invariant holds every step.
- G3 fork cost: fork+step median <= 1/10 of current deepcopy path (measure both).
- G4 regression: same-seed Boros-vs-Affinity n=300 byte-identical pre/post refactor
  UNTIL the RNG migration step; after it, document the expected baseline shift and
  re-anchor (n=1000, record in ARCHITECTURE.md).
- G5 determinism: same seed + same action sequence -> identical states across 2 runs
  and across fork boundaries.

## Stop conditions
- Any G1 parity mismatch traceable to step() taking a DIFFERENT code path than APLs:
  stop, reroute through the shared path, never patch the parity harness.
- Fork speedup < 3x after externalizing card state: stop, profile, re-design before
  writing more (predicted hotspot: Card object graph; if it's elsewhere, model is wrong).
- Action vocabulary found to require >2 new kinds mid-build: stop, amend Step 1 doc first.

## Annotated imperfections (known at authoring)
- Priority-window enumeration inherits the counter/removal whitelist until the
  oracle-responses spec ships (seam designed in Step 4).
- Attack/block enumeration is capped, not exhaustive — sound for search-vs-APL
  comparison, documented as a widening lever later.

## Mid-execution Amendment 1 (2026-07-01)
Step 1 DELIVERED: `mtg-sim/docs/action-vocabulary.md` — 14 decision sites mapped to a
13-kind Action vocabulary, every engine->APL call site enumerated and verified by
source grep (agent survey cross-checked). Note: the file is uncommitted in mtg-sim
(Cowork sandbox is pre-history-rewrite); commit workstation-side. Steps 2-7 OPEN.
Finding folded in: respond_to_spell (match_apl.py:485, match_engine.py:105) is a
shallow pre-R1 hook — vocabulary folds it into the RESPOND family rather than
modeling it separately.

## Mid-execution Amendment 2 (2026-07-01) — PROTOTYPE LANDED
Steps 2/3 + a v0 of Step 6 shipped as a WORKING PROTOTYPE (files uncommitted in mtg-sim,
sandbox pre-rewrite — commit workstation-side):
- engine/decision_api.py: legal_main_actions / apply_action (canonical paths) / fork (deepcopy v0).
- apl/search_apl.py: SearchAPL(MatchAPL) — deck-agnostic pilot, 1-ply fork+greedy eval on
  main-phase-1; combat/priority/mulligan inherit MatchAPL defaults.
Measured (Boros deck vs Murktide, real engine, PYTHONHASHSEED=0): SearchAPL 30.8% (N=107)
vs GenericMatchAPL 39.2% (N=1159) vs hand-tuned Boros 45.7% (N=2471). Seam proven; skill is
future work. Remaining B1: Step 4/5 (priority+combat enumeration), real Step 6 (cheap fork),
Steps 2-7 formal gates. Report: E:\vscode ai project\PROTOTYPE-2026-07-01.md.
