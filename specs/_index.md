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

- `2026-07-01-b1-legal-action-api.md` — **EXECUTING** (Step 1 shipped 2026-07-01:
  mtg-sim/docs/action-vocabulary.md, 13-kind Action vocabulary, all call sites verified;
  Steps 2-7 open). THE ISMCTS gate: `reset/observe/legal_actions/
  step/fork` decision API on the match engine + cheap fork + per-state RNG (subsumes the
  fork/RNG-threading item — one refactor, one baseline re-anchor). 5 falsifiable gates
  incl. action-replay parity and 10k random-walk conservation. Steps 1-3 = shippable
  first slice. Source: AUDIT-ENGINE-APL-2026-07-01 Part A.
- `2026-07-01-oracle-driven-responses.md` — retire the counter/removal whitelists via
  oracle-text classification (golden-tested against the existing table, feature-gated
  gate-OFF-byte-identical, measure-don't-tune). Empirical driver: calibration probe
  2026-07-01 — P2 prowess cell CURED (1.4%→62.0% vs truth ~53) but P1 dimir cell
  INVERTED (64.6%→13.1% vs truth ~40): interaction under-modeling is now the measured
  binding constraint. Parallel-safe with B1.
- `2026-06-29-harness-orchestration-contract.md` — Adopt sandcastle's run()->RunResult domain model
  as the harness orchestration contract (IsolationStrategy enum, fork() distinct-key invariant,
  <promise>COMPLETE</promise> sentinel shared w/ Ralph, Output.object=Pydantic-retry). Build gated behind
  ralph_executor landing. Source: matt-pocock-ai-eng-roadmap (sandcastle).
- `2026-06-29-evalite-eval-harness.md` — evalite-shaped pytest eval harness (data->task->scorers[])
  extending apl_judge via its llm= seam; Monte Carlo sim as a 0-1 scorer + Anthropic LLM-judge; CI gate on
  mean(score). Anthropic half gated on the anthropic SDK install. Source: roadmap (evalite).
- `2026-04-30-mulligan-parameter-sweep.md` — Empirically derive optimal keep()
  thresholds for each deck archetype role via large-N goldfish simulation.
  27 combinations x 4 reference decks at N=50,000. Validates against Nettle 2-1-2.
  **Status:** Spec drafted 2026-04-30. NOTE (2026-07-01 reconciliation): premise weakened
  by mull-routing falsification (keep-quality self-help −0.17pp in match mode); an impl
  plan exists (2026-06-28-mulligan-sweep-impl-plan.md) and scripts/mulligan_sweep.py is
  on disk. Re-assess value before executing.

- `2026-04-29-card-specs-framework.md` — Extract per-card decision logic into
  `apl/card_specs/` parallel to `engine/card_handlers_verified.py`. Tier 1+2 landed.
  **Status:** Spec drafted 2026-04-29. POC scope shipped. Full migration pending.
  Impl plan: 2026-06-28-card-specs-framework-impl-plan.md (PROPOSED).

## SHIPPED

(retroactively populated -- see harness/specs/RETROACTIVE.md for the 14
commits from 2026-04-26/2026-04-27 session that pre-date this directory)

- `2026-04-29-jeskai-blink-oracle-fidelity-audit.md` — Per-card oracle re-read for JB.
  Reconciled 2026-07-01: Phases A+B shipped 2026-04-29/30 (13 commits); Phase C engine
  gaps deferred to IMPERFECTIONS and later addressed by the R1-R6 modelability ladder.
- `2026-04-30-github-actions-runner-setup.md` — Runners registered + CI live 2026-05-01;
  Node 24 action updates landed 2026-05-03 (last open item). Reconciled 2026-07-01.
- `2026-06-28-skill-system-impl-plan.md` — Skill system implemented: harness/skills/ tree
  (4 skills + _index.md), CLAUDE.md v1.6 skill-menu gate. Reconciled 2026-07-01 (frontmatter
  had stayed PROPOSED after the work landed).
- `2026-06-28-llm-as-judge-impl-plan.md` — apl_judge.py + question/calibration data live
  under harness/agents/scripts + harness/data; evalite spec (2026-06-29) extends its llm=
  seam. Reconciled 2026-07-01 (frontmatter had stayed PLAN after the work landed).

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
  threat-an