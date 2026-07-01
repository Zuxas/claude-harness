# Harness Reconciliation — 2026-07-01

One-page record of the reconciliation pass (Cowork session). Companion docs:
`DIAGNOSTIC-REPORT-2026-07-01.md` + `AUDIT-ENGINE-APL-2026-07-01.md` at workspace root.

## Spec triage (drift warnings cleared on disk evidence)

| Spec | Old status | New status | Evidence |
|---|---|---|---|
| 2026-04-29-jeskai-blink-oracle-fidelity-audit | PROPOSED 63d | SHIPPED | Phases A+B: 13 commits 2026-04-29/30; Phase C → IMPERFECTIONS → R-ladder |
| 2026-04-30-github-actions-runner-setup | PROPOSED 62d | SHIPPED | Runners+CI live 05-01; Node 24 updates landed 05-03 |
| 2026-05-01-skill-system-harness | PROPOSED 61d | SUPERSEDED | by 2026-06-28-skill-system-impl-plan (shipped: skills/ tree + CLAUDE.md v1.6) |
| 2026-04-30-llm-as-judge-apl-evaluation | PROPOSED 62d | SUPERSEDED | by 2026-06-28-llm-as-judge-impl-plan (shipped: apl_judge.py + data) |
| 2026-06-28-skill-system-impl-plan | PROPOSED (stale) | SHIPPED | harness/skills/ live |
| 2026-06-28-llm-as-judge-impl-plan | PLAN (stale) | SHIPPED | apl_judge.py + questions/calibration JSON live |

Left PROPOSED deliberately: 2026-04-30-mulligan-parameter-sweep (premise weakened by the
2026-07-01 mull-routing falsification — re-assess before executing; noted in _index.md) and
2026-04-29-card-specs-framework (decision already recorded: POC shipped, migration pending).

## Stale findings docs (5) — closed with RESOLVED notes

cache-key-audit, perf-within-matchup-parallelism, jeskai-blink-card-specs,
canonical-field-integrity, be-apl-content-gaps — each appended a dated RESOLVED
note with pointers to the shipped successor work. Drift-detect's stale-findings
check keys on the RESOLVED token, so tomorrow's drift PR should drop all 5 warnings.

## Quality grades

NOT regenerated (needs a post-ban gauntlet run). Staleness note appended to
mtg-sim-quality-grades.md redirecting current-field decisions to
mismodeled_matchups.py flags + EXECUTING spec amendments. A formal regrade is a
good candidate to pair with BATCH I0, since I0 changes which cells carry flags.

## Also this session (workspace level, outside harness git)

Worktree cleanup (5 removed, verified merged), root cleanup + _archive-2026-07-01/,
handoffs/postmortems relocated into harness/, Team Resolve git-initialized
(main @ ae6db30, 280 files). Details in MEMORY.md 2026-07-01 entry.

## Open decisions for Jermey

1. Daily execution chains: resume authoring, or retire the convention and let the
   drift PR be the sole daily artifact? (Lapsed since 2026-05-16; half-state = noise.)
2. mulligan-parameter-sweep spec: execute for goldfish thresholds anyway, or abandon
   given the falsification?
3. The keep-vs-revert decision on the London-artifact slice (IMPERFECTION
   mull-routing-london-vancouver-asymmetry-artifact) — flagged in the EXECUTING spec.
