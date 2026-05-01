---
title: "MTG-Sim Quality Grades"
domain: "tech"
last_updated: "2026-04-27"
confidence: "high"
sources: ["session-2026-04-26-27", "ARCHITECTURE.md", "harness/knowledge/tech/*"]
---

## Summary

Per-domain quality grades for the mtg-sim project. Grades reflect maturity
relative to "perfect" -- a domain with grade A still has known imperfections
documented in IMPERFECTIONS.md but they're cosmetic or infrequent. Grade C
or below means the domain has structural issues that affect sim correctness.

This file updates with every commit that materially changes a graded
domain. Stale grades = drift; the harness drift-detect script flags grades
older than the latest finding for that domain.

## Grading scale

- **A**: Perfect modulo annotated imperfections. Confident in measurements.
- **A-**: Minor issues; accuracy within ~1pp on gauntlets.
- **B+**: Material gaps documented; results reliable for relative
  comparisons but not absolute headlines.
- **B**: Real architectural gaps; results need methodology caveats.
- **B-**: Multiple gaps; some matchups suspect.
- **C+**: Significant gaps; results indicative but not definitive.
- **C**: Major gaps; substantial rework needed.
- **D**: Architecturally broken; do not trust outputs.
- **F**: Doesn't function.

## Grades by domain

### Engine

| Component | Grade | Notes |
|---|---|---|
| game_state.py turn loop | A- | Stage 1.5 + 1.6 partial determinism shipped; Stage 1.7 (event_bus) pending. |
| ETB trigger dispatch | A | Phase 1 diagnostic confirmed firing correctly in match mode. |
| Combat (goldfish) | A- | Keyword logic exists but tangled with card-specific attack triggers; refactoring deferred. |
| Combat (match-runner) | B+ | Phase 3 partial (6 of 23 keywords); Phase 3.5 in progress to close all gaps. |
| Mana / land tap state | B | Match-runner doesn't model tap state; vigilance is no-op. Phase 3.5 Stage B adds minimal model. |
| Card transform (DFC) | A | T1.3+T1.4 arc complete (commits 68aae47-6a6d1fb). DFC fields, gs.transform, planeswalker dispatch, saga transform all working. |
| Foundation files | A | Committed at 7e213ea (was load-bearing WIP pre-fix). |
| Targeting model | C | No engine-level targeting model. Hexproof/ward/protection currently unenforced. Phase 3.5 Stage C adds it. |
| Priority / timing | C | No priority window. Flash creatures can't be cast at instant speed. Phase 3.5 Stage D adds flash response window. |

### APL layer

| Component | Grade | Notes |
|---|---|---|
| BorosEnergyAPL (canonical) | A- | Variant-adaptive role refactor complete. Voice + Guide ETB double-firing fixed. Guide attack-trigger double-firing pending (small impact). |
| BorosEnergyAPL (variant Jermey) | A- | Same APL handles both via _compute_roles. Validated for tournament play. |
| Modern other APLs | B | Most decks have stub or auto-APL; only BE is hand-tuned. IzzetProwess refactor pending (~3-4hr). |
| Standard APLs | B- | 12 modified + 3 untracked match-mode APL files sitting since 2026-04-23. Triage pending. |
| Pioneer APLs | C+ | 57-card L1 backlog. Most decks use GenericAPL stubs. |
| Legacy APLs | B+ | Humans hand-tuned and validated. Other decks use GenericAPL or auto-APLs. |
| Match-mode APLs (per-deck) | B | Hand-tuned for ~13 of 15 Modern decks; quality varies. None implement flash_response (Phase 3.5 Stage D adds). |

### Match-runner

| Component | Grade | Notes |
|---|---|---|
| Turn structure | A | Phase 4 fixed turn-order asymmetry. on_play respected, T1 draw skip correct. |
| main_phase invocation | A | Phase 1 wires main_phase + main_phase2 correctly. |
| Combat resolution | B+ | Phase 3 partial keyword coverage; Phase 3.5 in progress. |
| State sync (gs <-> view) | A- | view.damage_dealt + view.life sync correct; mana_pool resets fresh per phase (caveat documented). |
| Determinism | B | Stage 1.5 + 1.6 partial; full determinism blocked on Stage 1.7. |

### Goldfish runner

| Component | Grade | Notes |
|---|---|---|
| Engine integration | A | Bit-identical across all session changes (validation gate enforced). |
| Run-set parallelism | A | parallel_launcher.py works correctly. Within-matchup parallelism blocked on Stage 1.7. |
| Sample-size discipline | A | 1k preview held within +/-0.4pp of 100k truth across multiple runs. |

### Gauntlet methodology

| Component | Grade | Notes |
|---|---|---|
| 1k field-weighted | A- | Validated against 100k. Sample-size discipline confirmed. |
| 100k field-weighted | A- | Definitive headline scale. Wall ~30-45 min on 12-core. |
| DB-cached matchups | A | Real tournament data via mtg-meta-analyzer DB. |
| Sim-source matchups | B+ | Reliable for relative comparisons; absolute numbers reflect simplifications in match-runner combat (currently being addressed). |
| Variant edge measurement | A- | +11.9pp gauntlet edge robust across multiple session checkpoints (post-alignment). |

### Tooling

| Component | Grade | Notes |
|---|---|---|
| sleeve_check.py | A | Variant vs canonical readout, --gauntlet flag, copy-to-clipboard works. |
| parallel_launcher.py | A | ASCII fixes shipped. Wall time bottleneck on slowest matchup motivates Stage 1.7 work. |
| dashboard.py | A | Per-deck output formatted correctly. |
| Findings doc registry | A | Every architectural finding has a doc. Cross-linked via _index.md. |
| Spec-execution discipline | A | Codified in CLAUDE.md (Rule 1-8). Specs go in harness/specs/. |
| Drift detection | C | Manual currently. drift-detect.ps1 in progress. |
| Pre-commit lints | C | None. lint-mtg-sim.py in progress. |

### Format coverage

| Format | Grade | Notes |
|---|---|---|
| Modern | A- | 15 decks, hand-tuned BE, validated 1k + 100k. |
| Legacy | B+ | 15 decks, Humans hand-tuned, gauntlet runs. |
| Standard | B | 14 decks, most use generic APLs, RC prep active for May 29. |
| Pioneer | C+ | 15 decks, 57 cards in L1 backlog, 5 matchups have deck-name mapping issues. |

## Latest measurements (post-2026-04-27 mtg-sim session, pre-Phase-3.5)

| Metric | Canonical | Variant Jermey | Edge |
|---|---|---|---|
| Goldfish kill turn | T4.50 | T4.40 | -0.10 turn |
| Goldfish T4 share | 53.4% | 58.6% | +5.2pp |
| 1k Modern field-weighted | 65.6% | 78.4% | +12.8pp |

100k canonical headline pending (Task 2 in flight at time of writing).

## Highest-leverage upgrades (ranked)

These are the changes that would improve grades fastest:

1. **Phase 3.5 keyword coverage** (in progress) -- moves Combat (match-runner)
   from B+ to A, Targeting from C to A, Priority/timing from C to A-,
   Match-mode APLs from B to A- (after flash_response wiring).

2. **Stage 1.7 event_bus determinism** -- moves Determinism from B to A,
   unlocks within-matchup parallelism (3-5x gauntlet wall).

3. **IzzetProwess role refactor** -- moves Modern other APLs from B to A-.

4. **Pioneer L1 backlog** (waves of 8-12 cards) -- moves Pioneer from C+ to B-
   per wave.

5. **Standard *_match.py WIP triage** -- moves Standard from B- to B.

6. **Drift detection + lint scripts** -- moves Drift detection / Pre-commit
   lints from C to A. Catches the kinds of issues that surfaced last night
   (canonical-deck-mismatch, load-bearing WIP) automatically.

## Changelog

- 2026-04-27: Created. Snapshot of post-2026-04-26/2026-04-27-session state
  before Phase 3.5 starts. All grades reflect that session's commits.
