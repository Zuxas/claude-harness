# harness/specs/ -- Spec Index
# Last updated: 2026-05-01

Chronological list of all execution specs by status. Newest first within
each status. After a spec ships, it stays in this index forever.

## EXECUTING

- `2026-04-27-phase-3-5-keywords.md` -- Full keyword coverage in match-runner.
  11 stages (A-K), every keyword in engine/keywords.py KWTag plus ~25 not-yet-tagged
  keywords. No deferrals. Estimated 200-350 min real work, may expand.
  **Status:** Stage A in queue, blocked on 100k canonical Task 2 completion.

## PROPOSED

- `2026-05-01-skill-system-harness.md` — Dynamic capability loading for the harness.
  Bundle knowledge + scripts + behavior rules into loadable skills (mtg-sim-quality,
  meta-analysis, apl-generation, harness-ops). ~78% context reduction per turn.
  Source: nexu-io/harness-engineering-guide skill-system.md.
  **Scheduled:** post-PT, earliest 2026-05-05.

- `2026-04-30-mulligan-parameter-sweep.md` — Empirically derive optimal keep()
  thresholds for each deck archetype role via large-N goldfish simulation.
  27 combinations x 4 reference decks at N=50,000. Validates against Nettle 2-1-2.
  **Status:** Spec drafted 2026-04-30. Scheduled post-PT.

- `2026-04-30-llm-as-judge-apl-evaluation.md` — 30-question test set + Gemma judge
  scoring APL decision correctness independently of sim WR%. Three question types:
  oracle fidelity, strategic decisions, keep/mulligan.
  **Status:** Spec drafted 2026-04-30. Scheduled post-PT.

- `2026-04-30-event-hub.md` — Full Event Hub GUI for mtg-meta-analyzer: calendar,
  bookmarks, My Events, My Stores, .ics export, MTGO calendar, premier events 2026.
  **Status:** Session 1 shipped (calendar + bookmarks + MTGO). Session 2 pending
  (RC countdown, drive time, conflict detection, post-event enrichment).

- `2026-04-29-jeskai-blink-oracle-fidelity-audit.md` — Per-card oracle re-read for
  every nonland in `decks/jeskai_blink_modern.txt`. Found 3 prior-commit misreads.
  Plus 11 engine-level gaps.
  **Status:** Phase A + B shipped. Phase C (engine framework) deferred to IMPERFECTIONS.

- `2026-04-29-card-specs-framework.md` — Extract per-card decision logic into
  `apl/card_specs/` parallel to `engine/card_handlers_verified.py`. Tier 1+2 landed.
  **Status:** Spec drafted 2026-04-29. POC scope shipped. Full migration pending.

- `2026-04-30-github-actions-runner-setup.md` — Self-hosted runner registration +
  CI/CD pipeline design. Both runners live (JERMEY on mtg-sim + mtg-meta-analyzer).
  **Status:** Runners registered, CI live, all initial issues resolved. DONE except
  Node 24 action version update (needed before 2026-06-02).

## SHIPPED

(retroactively populated -- see harness/specs/RETROACTIVE.md for the 14
commits from 2026-04-26/2026-04-27 session that pre-date this directory)

- `2026-04-27-guide-attack-trigger-fix.md` — Shipped.
- `2026-04-27-oracle-parser-orphan-fix.md` — Shipped.
- `2026-04-27-phase-3.5-stage-a-block-eligibility.md` — Shipped.
- `2026-04-27-phase-3.5-stage-b-combat-modifiers.md` — Shipped.
- `2026-04-28-phase-3.5-stage-c-protection-cluster.md` — Shipped.
- `2026-04-28-cache-collision-finding-doc-tightening.md` — Shipped.
- `2026-04-28-parallel-launcher-cache-collision-fix.md` — Shipped.
- `2026-04-28-cache-key-audit-mtg-sim.md` — Shipped.
- `2026-04-28-drift-detect-7th-check-spec-validation.md` — Shipped.
- `2026-04-28-drift-detect-8th-check-cache-key-audit.md` — Shipped.
- `2026-04-29-gemma-apl-quality-lift.md` — Shipped.
- `2026-04-29-drift-detect-8th-check-rmw-pattern.md` — Shipped.
- `2026-04-29-rmw-race-cluster-fix.md` — Shipped.
- `2026-04-29-within-matchup-parallelism.md` — Shipped (8706f68).
- `2026-04-29-stage-ab-100k-revalidation.md` — Shipped 2026-05-01. Canonical 68.4% / Variant 75.1% at N=100k seed=42.
- `2026-04-29-friday-pt-readiness.md` — Shipped.

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
