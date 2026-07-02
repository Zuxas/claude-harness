---
title: "Spec triage — stale-status reconciliation (verdict proposals)"
status: "RATIFIED + APPLIED 2026-07-01 — all verdicts user-ratified and executed (spec status lines + _index.md updated); keep-routing additionally CLOSED-FALSIFIED (open decision resolved by sim 6052de6)"
created: "2026-07-01"
updated: "2026-07-01"
project: "harness"
related_findings:
  - "harness/reports/reconciliation-2026-07-01.md"
  - "E:/vscode ai project/ANALYZER-FIXES-2026-07-01.md"
related_commits: []
supersedes: null
superseded_by: null
---

# Spec triage 2026-07-01 (workstation reconciliation pass)

Scope: every spec carrying a non-terminal status (PROPOSED / EXECUTING / PLAN)
older than 30 days, cross-checked against read-only git log in mtg-sim and
mtg-meta-analyzer since 2026-05-15 plus on-disk artifacts. These are VERDICT
PROPOSALS for the spec owner — per conservative rules, no spec's own status
line was edited and nothing is marked ABANDONED.

NOTE: mtg-sim hashes cited from before the 2026-07-01 history rewrite
(e.g. d5603bb) are historical labels; the work is verifiable on disk even
where `git show` no longer resolves the hash.

## Verdict proposals

### 1. `2026-04-27-phase-3-5-keywords` (index: EXECUTING, "Stage A in queue")
**Proposed verdict: SUPERSEDED (partially) — by the R1-R6 modelability ladder; remaining Stages D-K STALLED-RECOMMEND-CLOSE.**
- The spec FILE does not exist in specs/ — only the `_index.md` entry does
  (the stage-A/B/C child specs exist and are all SHIPPED). Index references a
  missing file; fix candidate for the next index sync.
- Evidence of supersession: the capability gaps Stages D+ targeted are now
  addressed structurally — R1 priority stack / flash windows (sim 0f98db3),
  R2 instant-speed combat, R3 storm (e648e3f), R6 hidden-info (e6c60c9) all
  landed 2026-06-26..28. The index entry's blocker ("100k canonical Task 2")
  completed 2026-05-01 per `2026-04-29-stage-ab-100k-revalidation.md`.
- Recommend: close the index entry with a pointer to the modelability ladder.

### 2. `2026-04-28-gource-rerender-optional.md` (PROPOSED, 64 days)
**Proposed verdict: STALLED-RECOMMEND-CLOSE.**
- Execute-only-on-user-request by its own terms; no request in 64 days.
  Trivially re-openable (5-10 min task); keeping it open adds only index noise.

### 3. `2026-04-28-time-lapse-animation-prep.md` (PROPOSED, 64 days)
**Proposed verdict: STALLED-RECOMMEND-CLOSE.**
- Its own wake condition ("2+ weeks of daily JSONs", target 2026-05-12) was
  met ~7 weeks ago; `scripts/json-to-gexf-timelapse.py` was never built
  (single-frame `json-to-gexf.py` exists). Nobody has wanted the animation.
- Re-open on renewed visualization interest; the design doc keeps its value.

### 4. `2026-04-29-card-specs-framework.md` (index: PROPOSED / "full migration pending")
**Proposed verdict: COMPLETE (POC scope), remainder SUPERSEDED by `2026-06-28-card-specs-framework-impl-plan.md`.**
- On-disk frontmatter already says: "STEPS 1-4 SHIPPED 2026-06-28 (mtg-sim
  d5603bb, apl/card_specs/solitude.py + galvanic_discharge.py +
  test_card_specs PASS); Phase B deferred". The _index.md entry is the stale
  artifact here, not the spec.
- Recommend: flip to SHIPPED (POC) and let the 06-28 impl plan carry Phase B.

### 5. `2026-04-30-mulligan-parameter-sweep.md` (index: PROPOSED)
**Proposed verdict: COMPLETE (Track A); Tracks B/C STALLED-RECOMMEND-CLOSE.**
- Track A shipped 2026-06-28 (scripts/mulligan_sweep.py, historical d5603bb) —
  again the _index.md entry lags the spec's own frontmatter.
- Tracks B/C premise is now empirically weak: the 2026-07-01 mull-routing
  falsification measured keep-quality self-help at −0.17pp in match mode, and
  the engine production mull default was reverted to crude (sim 6052de6).
  Recommend closing B/C unless a future spec re-establishes the lever.

### Checked, not stale — noted for the owner
- `2026-06-30-match-mulligan-keep-routing.md` (EXECUTING, 1 day): hypothesis
  FALSIFIED per Amendment 2 and the one open decision (keep vs revert the
  artifact-only slice) appears RESOLVED by sim commit 6052de6 (revert to
  crude). Candidate for a terminal CLOSED-FALSIFIED status at owner's call.
- `2026-06-30-modern-combo-interaction.md`, `2026-07-01-b1-legal-action-api.md`:
  STILL-LIVE (active amendments within 48h; B1 Step-1 artifacts committed
  workstation-side in c1fe5a3).
- June PROPOSED batch (R-design docs, impl plans, roadmap specs, GUI
  Basic/Pro, oracle-driven responses): all under 30 days; not triaged.
