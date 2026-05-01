# harness/specs/ -- Spec Index
# Last updated: 2026-04-29

Chronological list of all execution specs by status. Newest first within
each status. After a spec ships, it stays in this index forever.

## EXECUTING

- `2026-04-27-phase-3-5-keywords.md` -- Full keyword coverage in match-runner.
  11 stages (A-K), every keyword in engine/keywords.py KWTag plus ~25 not-yet-tagged
  keywords. No deferrals. Estimated 200-350 min real work, may expand.
  **Status:** Stage A in queue, blocked on 100k canonical Task 2 completion.

## PROPOSED

- `2026-04-29-jeskai-blink-oracle-fidelity-audit.md` — Per-card oracle re-read for
  every nonland in `decks/jeskai_blink_modern.txt`. Found 3 prior-commit misreads
  (March 2-pitch cap should be uncapped per oracle "any number"; Prismatic Ending
  uses CONVERGE not MV-scaling; Galvanic damage = energy paid not 1+energy).
  Plus 11 engine-level gaps (Warp, Dash, Saga ch II/III, surveil, converge,
  Teferi static, combat-damage triggers, Phlage sacrifice clause, etc.).
  Three-phase fix path: A (match APL fidelity quick wins), B (combo additions),
  C (engine framework — out of tonight scope, IMPERFECTIONS opened).
  **Status:** Spec drafted 2026-04-29. Phase A includes a revert of the
  March 2-pitch cap (commit 46e6160) — that was a misread.

- `2026-04-29-card-specs-framework.md` — Extract per-card decision logic into
  `apl/card_specs/` parallel to `engine/card_handlers_verified.py`. Tier 1
  (Phlage, Galvanic, Ragavan, Phelia, Solitude, Ephemerate) covers ~70% of
  Jeskai Blink / UW Blink / Esper Blink / Boros Energy nonland reuse. POC
  scope (ADDITIVE, no canonical risk): Phlage spec + new
  `apl/jeskai_blink.py` composition + unit tests, ~60-90 min. Full migration
  scope (Phases A+B+C, ~4-6 hrs): touches `boros_energy.py` and
  `*_match.py` — needs bit-stable canonical gate.
  **Status:** Spec drafted 2026-04-29; finding doc at
  `harness/knowledge/tech/jeskai-blink-card-specs-2026-04-28.md`.
  Recommended slot: 2026-04-29 chain spec #4 (Gemma APL quality lift)
  becomes "compose specs from this framework" instead of generating
  freeform Python.

## SHIPPED

(retroactively populated -- see harness/specs/RETROACTIVE.md for the 14
commits from 2026-04-26/2026-04-27 session that pre-date this directory)

## SUPERSEDED

(none)

## ABANDONED

(none)

## BLOCKED

(none)

## How to use this index

When picking up a session:
1. Read EXECUTING entries first -- there's active work
2. Then PROPOSED -- spec written, ready to start
3. SHIPPED entries are reference material; don't re-execute

When writing a new spec:
1. Copy `_template.md` to `YYYY-MM-DD-<topic>.md`
2. Fill in frontmatter with status: PROPOSED
3. Add a line to the PROPOSED section above
4. After execution starts, move to EXECUTING
5. After commit lands, move to SHIPPED with commit hash
