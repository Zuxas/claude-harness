# harness/specs/ -- Spec Index
# Last updated: 2026-07-01

Chronological list of all execution specs by status. Newest first within
each status. After a spec ships, it stays in this index forever.

## EXECUTING

- `2026-06-30-match-mulligan-keep-routing.md` -- Route run_match opening hands through each
  deck's real keep()/bottom() (London, seeded via gs.rng, both seats). First slice: boros+amulet
  lanes only. Amendment 1 (2026-06-30) shipped the engine routing (`_do_mulligan_runner` with
  crude/london_crude/keep modes + `_mull_mode` selector + per-call fallback), Gate 0 (12/13 cells
  byte-identical across 4 pinned launches; boros_vs_uw_control excluded = opponent id()-ordering)
  and Gate 1 (crude-both byte-identical). Steps 5 (5-mode WR decomposition) + 6 (trackers/findings/
  predecessor stub) OPEN. Full-field flip blocked on the id()-ordering stabilization predecessor.
  Code committed in mtg-sim (ea737ae + 4762ab9). Branch `modern-postban-arc`.
  **Amendment 2 (2026-07-01): Steps 5-6 DONE — HYPOTHESIS FALSIFIED.** The mulligan does NOT
  unstarve combo assembly (grixis +3pp iso, WR flat; yawgmoth assembly FELL). 5-mode decomposition:
  keep-quality self-help −0.17pp (negligible), but +1.89pp mechanic-only London-vs-Vancouver
  ARTIFACT = ~the entire shipped M2 gain. Shipped cells are M2 (+1.71pp), only Boros-vs-Amulet is
  M3. Findings: mull-routing-falsification-2026-07-01.md. Flags committed 002e9df. ONE open decision:
  keep vs revert the artifact-only slice (IMPERFECTION mull-routing-london-vancouver-asymmetry-artifact).

- `2026-06-30-modern-combo-interaction.md` -- Interaction-aware Modern combo opponents (handoff #2).
  SPINE increment executed 2026-06-30 (Mid-execution Amendment 1): Component 2 Site 1 (mp1
  `damage_dealt` gate generalized to `WANTS_STORM or WANTS_BURN`; mono_red flagged, 481->395 a_wins,
  +17pp to mono_red but below the [35,45] band -- honest residual, not tuned), Site 2 DROPPED (no
  end-step killer found), Component 1 inert `engine/combo_interaction.py` layer + `answer_combo`
  mixin (byte-identical everywhere). ruby_storm Step-2.0 diagnostic fired Stop condition 4
  (payoff-reachability, not the damage channel -> re-scoped to Component 3). Amendments 2-3 shipped
  yawgmoth (cf2cf32, stays FLAGGED DEFLATED -- combat over-credit) + grixis (stays FLAGGED
  INVERTED-improved 69.4->55.0%). **Component-3 RE-SCOPE (2026-07-01, COMPLETE structural version,
  amendment at EOF -- supersedes the earlier structurally-blind authoring in harness 8c6b15d): the
  mulligan lever is FALSIFIED (mull-routing-falsification-2026-07-01.md: isolated assembly ~+3pp not
  ~24pp, WR flat, yawgmoth assembly FELL); the old per-deck Leverage order is SUPERSEDED by
  shared-cause batches. NEW ranked sequence: I0 honesty flags -> F combat-over-credit CHARACTERIZE-only
  -> A cascade end_step seam -> GRIS-SPIKE Griselbrand kill-channel -> ruby -> goryos -> broodscale ->
  grixis-decklist -> belcher -> neobrand -> yawgmoth -> neoform -> temur_breach -> landless_belcher.
  Structural lens added: Component-1 interaction spine is DELIVERED + firing but deliberately
  NON-load-bearing at G1 (deferred to Bo3/future decks); the run_match sampler bypass is a CONFIRMED
  dead-end (rejected 2026-06-29, unblocks ZERO cells). Flag-forever split 3 ways: (A) has-a-band
  faithfully-unreachable = grixis ONLY; (B) no-primer-band direction-only = living_end/temur_crashcade/
  belcher/neobrand(+neoform/temur_breach/landless non-field); (C) out-of-scope band-binder = yawgmoth
  (falsifiable upgrade via BATCH F). broodscale is NOT flag-forever (best fixable_to_band candidate).
  Trustworthy-minimum unblocking arc #5 = BATCH I0 ALONE (flag belcher 3.5% + neobrand 2.0% +
  temur_crashcade 3.4% + ruby_storm 4.1% + register landlessbelcher).** 11 cells REMAIN (2
  fixable_to_band: ruby, goryos; 1 candidate: broodscale; rest improvable/flag-forever). Est ~10-11
  sessions remaining. Branch `modern-postban-arc`.

- `2026-04-27-phase-3-5-keywords.md` -- Full keyword coverage in match-runner.
  11 stages (A-K), every keyword in engine/keywords.py KWTag plus ~25 not-yet-tagged
  keywords. No deferrals. Estimated 200-350 min real work, may expand.
  **Status:** Stage A in queue, blocked on 100k canonical Task 2 completion.

## PROPOSED

- `2026-06-29-harness-orchestration-contract.md` — Adopt sandcastle's run()->RunResult domain model
  as the harness orchestration contract (IsolationStrategy enum, fork() distinct-key invariant,
  <promise>COMPLETE</promise> sentinel shared w/ Ralph, Output.object=Pydantic-retry). Build gated behind
  ralph_executor landing. Source: matt-pocock-ai-eng-roadmap (sandcastle).
- `2026-06-29-evalite-eval-harness.md` — evalite-shaped pytest eval harness (data->task->scorers[])
  extending apl_judge via its llm= seam; Monte Carlo sim as a 0-1 scorer + Anthropic LLM-judge; CI gate on
  mean(score). Anthropic half gated on the anthropic SDK install. Source: roadmap (evalite).
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

- `2026-07-01-affinity-offense-rebaseline.md` — Arc #3: implemented the missing Urza's Saga
  chapter/Construct engine (oracle-faithful) + Thoughtcast CA + Munitions WANTS_BURN fidelity +
  honest Mox-metalcraft mana in `apl/affinity_match.py` ONLY. mtg-sim commit `ae9cb12`. **SHIPPED
  PARTIAL:** mechanism moved (Constructs 0->~24%, board power up, kill T6->T5, all 3 Boros builds
  down comparably, non-Affinity byte-identical, no tuning) but the pinned lowcurve cell reached only
  ~76% Boros / ~24% Affinity (from ~85.7%), NOT the ~44-56 band. Residual honestly attributed to
  mana model / opponent overmodel + the construct being present in only ~24% of games (early-Saga/
  tight-mana; honest {2},{T} gate NOT relaxed); the `izzet affinity` cell stays flagged INFLATED
  (trust-direction). NOT tune-to-44. The first execution attempt was a NO-OP (superseded).

- `2026-06-26-modelability-ladder.md` — R1-R5+warp engine-capability ladder on
  mtg-sim main (priority_stack.py, game_state.py _WARP_CARDS, modelability_proofs/
  r1/r2/r4/r5 JSON). Reconciled 2026-06-27: status was stale after the ~2026-05-16
  cadence lapse. related_commits: 7b62092 (R4 trilogy merge), b1e757d (Izzet
  Affinity warp modeling).
- `2026-06-26-archetype-capability-profiles.md` — Capability-profile system built:
  scripts/arl_profile.py writes docs/archetype_profiles/*.{md,json} (boros_energy,
  amulet_titan, eldrazi_ramp, izzet_affinity, izzet_prowess, jeskai_control,
  domain_zoo present). Reconciled 2026-06-27: status was stale after the ~2026-05-16
  cadence lapse.
- `2026-06-26-harness-ollama-watcher-optimization.md` — C2 marked DONE in-spec;
  qwen2.5-coder:7b wired into auto_pipeline.py _APL_CODE_MODEL_PREFERENCE.
  Reconciled 2026-06-27: status was stale after the ~2026-05-16 cadence lapse.
  related_commits: f86f799.
- `2026-05-02-pt-sos-handler-batch.md` — 4 SOS handlers (Tablet of Discovery,
  Molten-Core Maestro, Professor Dellian Fel, Bloom Tender) in
  card_handlers_verified.py + registered; izzet_prowess_standard.txt has Flow State
  + Colorstorm Stallion. Reconciled 2026-06-27: status was stale after the
  ~2026-05-16 cadence lapse.
- `2026-04-30-event-hub.md` — Full Event Hub GUI for mtg-meta-analyzer: calendar,
  bookmarks, My Events, My Stores, .ics export. Session 2 features confirmed in
  gui/tabs/event_hub_tab.py (drive time L81, RC countdown L1428). Reconciled
  2026-06-27: status was stale after the ~2026-05-16 cadence lapse.
- `2026-05-12-mtg-strategy-knowledge-base-slice-a.md` — Shipped 2026-05-12 at
  commit a8d6bc9. 6 strategy blocks under harness/knowledge/mtg/strategy/:
  _overview, chapin-principles, role-theory, card-advantage,
  threat-answer-density, format-standard-spring-2026. Approach C
  (training-derived) with strict epistemic hygiene. 2 imperfections opened
  (slice-not-codebase-grounded, format-block-decays).
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
