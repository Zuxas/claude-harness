---
title: Next Structural Build - Standard fair-deck calibration (Selesnya Landfall vs aggro overshoot)
status: PROPOSED
created: 2026-06-29
project: mtg-sim
related_findings:
  - harness/IMPERFECTIONS.md "standard-apl-goldfish-only-no-match-quality" (reclassified: build done, residual = calibration)
  - mtg-sim/CLAUDE.md "Known model limitations" (Izzet Lessons card-advantage inversion -- OUT of this spec's scope)
supersedes: none
superseded_by: none
estimated_time: 60-90 min diagnosis (bounded); 60-120 min fix IF localized (branch A)
---

# Next Structural Build - Standard fair-deck calibration

> Picked as the single best next-build out of the 4 triaged structural items because it is the
> ONLY one that (a) is genuinely tractable in a bounded session and (b) does NOT corrupt a locked
> baseline. The other three each fail one of those tests (see "Why not the others" below).
>
> This is a DIAGNOSIS-FIRST spec. Step 1 (the SIM_DEBUG trace) is bounded regardless of what the
> fix layer turns out to be. A hard stop (section "Stop conditions") routes a systemic-engine
> finding to a documented imperfection instead of a tuning rabbit hole.

---

## 0. Pre-flight reads (MANDATORY)

1. `harness/knowledge/tech/spec-authoring-lessons.md` (Rule 9 / Rule 5 prediction discipline)
2. `mtg-sim/CLAUDE.md` -- "Standard match APLs" + "Known model limitations" sections
3. `mtg-sim/apl/selesnya_landfall_standard_match.py` (475L, AwareMatchAPL)
4. `mtg-sim/apl/izzet_prowess_standard_match.py` (374L, AwareMatchAPL + IzzetProwessAPL; the aggro opponent)
5. `mtg-sim/apl/aware_match_apl.py` -- `declare_attackers` / `declare_blockers` / `_lethal_this_turn` / reach handling
6. This file's "Verified facts" section before forming any hypothesis

---

## 1. Goal

Reduce the Selesnya-Landfall-vs-Izzet-Prowess-Standard calibration error (sim over-rates the grindy
fair deck vs aggro) toward the PT SOS truth, OR -- if the trace proves the cause is engine-level
aggro-reach under-modeling -- ship the diagnosis and open a precise new imperfection. One sentence:
make the sim's fair-deck-vs-aggro Standard numbers move toward the PT anchor without touching any
locked baseline.

## 2. Verified facts (measured 2026-06-29, live code at main 506978e; n=60, seed=42, Path A Bo3)

| Matchup | sim (live) | PT SOS truth | error | confound? |
|---|---|---|---|---|
| Selesnya Landfall vs Izzet Prowess | **80.0%** | 62.9% | **+17pp** | NONE (two fair decks) -- THE TARGET |
| Izzet Lessons vs Izzet Prowess | 6.7% | 46.3% | -40pp | R6 card-advantage (Lessons can't convert) -- OUT OF SCOPE |
| Izzet Lessons vs Selesnya Landfall | 13.3% | ~75% | -62pp | R6 card-advantage inversion -- OUT OF SCOPE (item 2) |

Key separation: every Lessons matchup is poisoned by the documented card-advantage / inevitability
gap (R6 attrition fidelity, capped at 32.8% on branch `modelability/r6-phase2`, residual explicitly
OUTSIDE R6). Selesnya-vs-Prowess is the ONE large Standard error with NO card-advantage confound:
both are fair decks resolving via combat, so the overshoot is a combat/clock/reach calibration that
is actually diagnosable and fixable in isolation.

Also verified:
- The `reports/standard_gauntlet_full.json` matrix is STALE (2026-05-05; pre-dates the current match
  APLs). DO NOT trust its numbers. All targets above are live re-runs. Regenerating that matrix is a
  side-benefit of the validation step.
- NO locked Standard WR baseline exists (grep confirmed: only a "locked Store Champ decklist" and a
  "deck-lock date" reference -- neither is a gauntlet number). Standard WRs are calibration targets
  vs the PT matrix, NOT a byte-identical lock like Modern canonical 64.5/78.8. So tuning here cannot
  corrupt a locked baseline -- this is the property that makes it the eligible pick.

## 3. Scope

IN:
- Diagnose WHY Izzet Prowess (aggro) loses to Selesnya Landfall (fair midrange/ramp) at sim 80% when
  PT says 62.9%.
- IF the cause is localized to APL decision logic (branch A), fix it in
  `selesnya_landfall_standard_match.py` and/or `izzet_prowess_standard_match.py`.

OUT:
- Anything Izzet Lessons (all its matchups are R6 card-advantage -- item 2; do not touch here).
- Engine-level combat/reach refactor (if the trace points there -> STOP, document, do not build).
- Any Modern canonical deck (would touch the locked 64.5/78.8 baseline).
- Jeskai Blink Arena/Phlage (would touch the locked Boros baseline -- item 4).

## 4. Steps

1. **DIAGNOSE (the discriminator).** Run `SIM_DEBUG=1 python run_matchup.py selesnyalandfall
   izzetprowessstandard 10 8 42 standard fair 1` and read 5-8 full game logs. For each game Prowess
   LOSES, answer:
   - Does Prowess's evasive/burn damage actually reach the opponent's face (Slickshot flying, Burst
     Lightning to face, prowess pumps), or is it being absorbed/blocked?
   - Does Selesnya stabilize via lifegain / go-wide blockers / a fast Landfall clock that out-races
     the aggro deck?
   - What turn does Prowess's clock stall, and is it a sequencing miss (e.g. removal spent on the
     wrong target, attackers held back by `declare_attackers` trade-intelligence) or a raw
     damage-output shortfall?
   Capture the dominant pattern across the sampled losses. Write it to
   `harness/knowledge/tech/standard-selesnya-prowess-calibration-2026-06-29.md`.

2. **BRANCH on the finding:**
   - **Branch A (localized APL cause)** -- e.g. Prowess `declare_attackers` over-conservatively holds
     evasive attackers, OR Selesnya `declare_blockers` over-blocks/chumps too efficiently, OR Prowess
     burn is mis-targeted away from face when lethal-via-reach is available, OR a reach term in
     `_lethal_this_turn` is undercounting prowess pump. Fix the single dominant lever in the APL
     layer. Keep the diff minimal and named to the trace finding.
   - **Branch B (systemic engine cause)** -- e.g. the engine under-values aggro reach / over-values
     lifegain+blocking ACROSS all fair-vs-aggro Standard matchups (the MonoRed-too-weak-broadly
     signal hints at this). DO NOT build. STOP. Ship the diagnosis doc and open a new imperfection
     `standard-aggro-reach-calibration` with the concrete engine pointer the trace surfaced.

3. **VALIDATE (branch A only).** Re-run the target at n=300, seed=42:
   `python run_matchup.py selesnyalandfall izzetprowessstandard 10 300 42 standard fair 1`.
   Then re-run the no-regression set (below). Update the calibration doc with before/after.

4. **REGENERATE the stale matrix** as a side-benefit: re-run the Standard gauntlet so
   `reports/standard_gauntlet_full.json` reflects current code (it is 7 weeks stale).

## 5. Validation gates (falsifiable)

- **PRIMARY (branch A):** Selesnya-vs-Prowess moves from 80.0% toward PT 62.9% by >= half the gap,
  i.e. lands at **<= 71.5%** at n=300/seed=42. (Hitting exactly 62.9% is the calibration target, not
  the gate.)
- **NO-REGRESSION:** No other Standard matchup that is currently within +/-8pp of its PT truth may
  move OUTSIDE that band as a result of the fix. Specifically re-check, n>=200:
  - Selesnya vs Mono-Green Landfall (must stay de-inverted, ~65-74% range -- it was fixed; do not
    re-break it).
  - Izzet Prowess vs the control decks it already beats (must not collapse them; the fix must not
    simply nerf Prowess globally).
  - Prowess vs MonoRed / Gruul mirror-ish aggro (sanity that an aggro buff did not over-tilt aggro
    mirrors).
- **PREDICTION (Rule 5):** state, before running, WHERE the number should land and WHY, accounting
  for both decks' card density (per Stage B Amendment 4 lesson). If a buff to Prowess reach is the
  fix, predict it also nudges Prowess's OTHER fair-deck matchups -- and bound that.

## 6. Stop conditions (teeth)

- If the trace shows the cause is **engine-level** (branch B): STOP immediately. Do not edit any APL
  to force the number. Ship the diagnosis + open `standard-aggro-reach-calibration` imperfection.
  This is a SUCCESS outcome (a precise design-only handoff), not a failure.
- If a branch-A fix moves the PRIMARY gate the right way but regresses ANY no-regression matchup by
  >8pp: revert the fix, record the entanglement in the calibration doc, downgrade to design-only.
- If after the trace the dominant loss pattern is actually Lessons-style card-advantage leaking into
  the Selesnya side (unexpected): STOP -- that is item 2 (R6), out of scope.

## 7. Why not the other three (triage summary, for the record)

- **Item 2 hidden-info Phase 2:** the mechanism is ALREADY BUILT on `modelability/r6-phase2`
  (commit 73faedb) and proven to fire (+13pp, 20% -> 32.8%) but CANNOT de-invert: the residual is
  attrition fidelity (Lessons must actually REMOVE the Selesnya board -- R1 counters + combat
  resolution), explicitly OUT of R6 scope. Not a build; it is a user merge-decision on a documented
  honest partial (spec section 11 = NO-GO / HOLD). Defer-as-decision.
- **Item 3 cross-canonical oracle audit:** sprawling (16-32h), and EACH per-APL fix shifts the
  LOCKED Modern canonical 64.5/78.8 baseline -> corrupts a locked baseline by construction. The one
  named bug (goryos Solitude white-pitch) is already RESOLVED. Defer.
- **Item 4 jeskai-blink remaining 2/4 (Arena haste + Phlage attack-trigger):** both were SKIPPED in
  6429d63 precisely because they require a coordinated Boros re-baseline (Arena shim over-models +
  shifts Boros; a Phlage engine hook double-fires the 6/6 the Boros goldfish APL already self-fires)
  -> corrupts the locked Boros baseline by construction. Needs a deliberate Boros re-lock spec
  first. Defer.

## 8. Annotated imperfections (to register on ship)

- If branch B fires: `standard-aggro-reach-calibration` (engine under-models aggro reach / over-values
  lifegain+blocking vs aggro across Standard fair matchups).
- The Lessons-vs-everything inversion remains OPEN under item 2 (R6 attrition fidelity); this spec
  does not touch it -- cross-link only.
- `standard-apl-goldfish-only-no-match-quality` should be RE-WORDED on ship: the literal "build
  match APLs for top-4 Standard decks" ask is DONE (all four exist as AwareMatchAPL, registered,
  modeling interaction; Mono-Green de-inverted). The OPEN residual is calibration vs the PT matrix,
  of which this spec closes one slice.
