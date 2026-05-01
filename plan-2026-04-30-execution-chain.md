# Execution chain: 2026-04-30 (Thursday)

**Created:** 2026-04-29 night by Claude Code (in-session, after 13 commits + Phase A background agent)
**Target executor:** fresh Claude Code session
**Estimated wall time:** 8-10 hours full chain; subsections sized for partial days
**Source:** session-end handoff from 2026-04-29 night session that shipped 13 mtg-sim commits to Jeskai Blink + scoped a major engine-fidelity audit

## Read me first

This chain is fuller than usual because last night's session expanded scope significantly. The chain absorbs:
- Carryover from 2026-04-29 chain (specs #4-9 didn't run; specs #1-3 completed early)
- New Phase B/C work from JB oracle-fidelity audit (`harness/specs/2026-04-29-jeskai-blink-oracle-fidelity-audit.md`)
- Cross-canonical-apl bug-pattern audit (`harness/IMPERFECTIONS.md:cross-canonical-apl-shared-card-bug-pattern`)
- Spec #8 (100k re-validation) — now MUCH more important because JB canonical play shifted significantly

Fresh session should:

1. Read `harness/state/latest-snapshot.md` per `harness/CLAUDE.md` SESSION START PROTOCOL
2. **Read `harness/state/phase-a-completion-2026-04-29.md`** — the background agent's report from last night's Phase A run. Status of items 2-4 (Prismatic CONVERGE, Quantum static, Solitude lifelink). May have stopped early; may have shipped commits.
3. Read `harness/inbox/drift-pr--2026-04-30.md` — Gemma's overnight drift PR, lands ~04:50.
4. Read `harness/IMPERFECTIONS.md` — 9 OPEN entries at session-end of 2026-04-29.
5. Check `harness/specs/2026-04-29-jeskai-blink-oracle-fidelity-audit.md` for Phase A/B/C item details.
6. Read this file as the day's plan.

## State carried forward from 2026-04-29

**13 mtg-sim commits shipped:** atomic_json (RMW), card_specs framework + Tier 1 + Tier 2, sim.py auto-resolve, JB canonical routing fix, 8 JB match-APL bug fixes (Phelia counter, blink fall-through, Solitude white-pitch, March 2-cap revert, Ephemerate {W} payment, Casey accumulation + Phelia exile end-step return, Fable + Prismatic Ending). Cumulative JB vs Boros Energy n=1000 seed=42: 45.4% -> 47.0% (+1.6pp net of multiple oracle-correctness inflations being removed).

**5 finding docs landed (filesystem only — harness/ isn't git-tracked):**
- `harness/specs/2026-04-29-card-specs-framework.md`
- `harness/specs/2026-04-29-jeskai-blink-oracle-fidelity-audit.md`
- `harness/knowledge/tech/jeskai-blink-card-specs-2026-04-28.md`
- `harness/knowledge/tech/match-apl-mulligan-audit-2026-04-29.md`
- `harness/knowledge/tech/canonical-field-integrity-2026-04-29.md`
- `harness/knowledge/tech/boros-energy-vs-jb-apl-maturity-2026-04-29.md`

**18 lessons in spec-authoring-lessons.md** (v1.6: added `oracle-text-verify-before-touching-card-mechanics`).

**10 OPEN imperfections** at session end:
1. `gemma-apl-quality-low-for-smoke-gate`
2. `mulligan-logic-portfolio-gap` (corrected scope)
3. `canonical-field-missing-match-apl-entries` (Jeskai Blink fixed; Breach decks banned per user — Orzhov Blink phantom remains)
4. `card-specs-phase-b-migration-pending`
5. `card-specs-phlage-engine-no-sacrifice-quirk`
6. `jeskaicontrol-key-mismapping`
7. `engine-fidelity-gaps-warp-mechanic-not-modeled` (28% canonical field affected)
8. `engine-fidelity-gaps-jeskai-blink-cards` (Fable Saga ch II/III, Goblin treasure trigger, Arena haste)
9. `cross-canonical-apl-shared-card-bug-pattern` (Goryo's confirmed has same Solitude bug; others likely)
10. **`engine-fidelity-gaps-has-keyword-attribute-mismatch`** (HIGH severity — surfaced by Phase A agent. `engine/match_state.py:has_keyword` checks non-existent `card.keywords`, always returns False. Affects 6+ engine paths but NOT match_runner. ~5-line fix + bit-stable validation.)

## Specs PROPOSED for 2026-04-30

| # | Spec | Path | Effort | Risk | Resolves |
|---|---|---|---|---|---|
| 0 | Session start (snapshot + inbox + Phase A completion review) | (procedural) | 15-30 min | n/a | — |
| 1 | **Spec #8 carryover: Stage A/B 100k re-validation** | `2026-04-29-stage-ab-100k-revalidation.md` | 90-120 min | LOW | None (anchor numbers) |
| 2 | ~~JB Phase A finish~~ — DONE 2026-04-29 night (commit 990d639) | n/a | n/a | n/a | Phase A spec SHIPPED |
| 3 | JB Phase B: Wrath optimal X selection | new spec | 30-45 min | LOW | 1 IMPERFECTION amendment |
| 4 | JB Phase B: Phlage hardcast + Consign sacrifice trigger combo | new spec | 30-45 min | LOW | (advanced play) |
| 5 | JB Phase B: Consign Replicate {1} cost path | new spec | 30-45 min | LOW | (combo upgrade) |
| 6 | Cross-APL audit: Goryo's Vengeance (canonical 5.6%) | new spec | 60-90 min | MED | 1 IMPERFECTION (per APL) |
| 7 | Gemma APL quality lift (carryover from 2026-04-29) | `2026-04-29-gemma-apl-quality-lift.md` | 45-90 min | MED | 1 IMPERFECTION |
| 8 | Drift-detect 8th check (RMW pattern detector, carryover) | `2026-04-29-drift-detect-8th-check-rmw-pattern.md` | 45-75 min | LOW | None (mechanizes) |
| 9 | Within-matchup parallelism (carryover) | `2026-04-29-within-matchup-parallelism.md` | 60-90 min | MED | None (Stage 1.7 unblock) |
| 10 | Friday PT-readiness verification (carryover) | `2026-04-29-friday-pt-readiness.md` | 30-45 min | MIN | None (proactive) |

**Parked for a focused future session (NOT in chain):**
- Phase C engine-framework work: Warp mechanic, Dash mechanic, Saga ch II/III, Surveil, Converge, Combat-damage triggers, Arena exert+haste, Static abilities (Teferi). Each is its own spec, 2-4 hours. Total scope ~16-30 hrs across all engine items. **These are CANONICAL-SHIFTING and need bit-stable validation per APL** — not for parallel/casual execution.
- Cross-APL audits beyond Goryo's: Domain Zoo (5.0%), Eldrazi Ramp (7.4%), Eldrazi Tron (4.3%), Murktide (3.5%), Affinity (6.8%), Esper Blink (2.8%), UW Blink (fringe). Each ~2-4 hours. Schedule incrementally.
- card_specs Phase B migration (boros_energy.py + match APLs): 120-180 min, canonical-shifting; needs bit-stable gate.

## Recommended execution chain (Option A — Full 9-hour day)

### Section 0 — Session start (~15-30 min)

- Read snapshot + inbox + `phase-a-completion-2026-04-29.md`
- Process Phase A agent's report:
  - If agent shipped clean Phase A commits: continue
  - If agent stopped early: pick up where it stopped or skip the remaining items
  - If agent introduced regressions: investigate first
- Read CLAUDE.md DAILY RHYTHM CHECK; surface options to user

**[STOP — confirm baseline; surface Phase A outcome; confirm proceed to spec #8]**

### Section 1 — Anchor canonical numbers (~90-120 min)

1. **Spec #8 (100k re-validation)** — runs the canonical Boros Energy + variant gauntlet at n=100,000. This anchors the new baseline AFTER the Jeskai Blink overhaul. Mostly wall-time (parallel_launcher), partial-attention compatible. Output: new 64.5%/78.8% replacement numbers.

**[STOP — review new baseline; document delta from prior 64.5%/78.8% in `harness/knowledge/tech/`]**

### Section 2 — JB Phase B match-APL combos (~90-135 min)

2. **Wrath optimal X** (#3) — asymmetrical wipe heuristic. ~30-45 min.
3. **Phlage hardcast + Consign sacrifice trigger** (#4) — counter own Phlage's "sacrifice unless escaped" trigger. APL-level workaround for engine no-sac quirk. ~30-45 min.
4. **Consign Replicate {1}** (#5) — multi-trigger counter via replicate cost. ~30-45 min.

Each item: oracle-text-verify FIRST (per `oracle-text-verify-before-touching-card-mechanics` v1.6 lesson). Quote oracle in commit. Bit-stable JB vs canonical opps after each.

**[STOP — JB done; aggregate WR delta from session start]**

### Section 3 — Tooling + cross-APL audit (~120-180 min)

5. **Cross-APL audit: Goryo's Vengeance** (#6) — same JB-style audit on `apl/goryos_match.py`. Already-confirmed Solitude white-pitch bug + missing lifegain. Likely 4-8 commits. Apply oracle-verify methodology rigorously.
6. **Drift-detect 8th check (RMW pattern)** (#8) — mechanizes detection of cache-key-class bugs going forward.

**[STOP — tooling expansion shipped; audit pattern confirmed]**

### Section 4 — Wrap or pivot (~120-165 min)

7. **Gemma APL quality lift** (#7) — incorporates spec composition from card_specs framework.
8. **Within-matchup parallelism** (#9) — Stage 1.7 unblock. SKIPPABLE if time-pressured.
9. **Friday PT-readiness verification** (#10) — pre-flight Friday's data ingestion + scheduled tasks.

## Recommended execution chain (Option B — 4-5 hour focused)

If shorter day:

1. Section 0 (mandatory)
2. **Spec #8 100k re-validation** (#1) — non-negotiable; anchors new baseline
3. **Wrath optimal X** (#3) — quickest Phase B win
4. **Phlage + Consign combo** (#4) — high-leverage advanced play
5. **Friday PT-readiness** (#10) — small but critical for Friday

Defers: Goryo's audit, Gemma quality, drift-detect 8th check, parallelism.

## Recommended execution chain (Option C — 1-2 hour minimum)

If disrupted day:

1. Section 0 (mandatory)
2. Phase A completion review (decide whether agent's work is mergeable)
3. **Spec #8 100k re-validation** (#1) — must happen so the JB shifts are properly anchored

Everything else defers.

## Stop conditions across the chain

- **Phase A agent introduced canonical regression**: STOP, investigate, possibly revert before Spec #8
- **Spec #8 shows >10pp baseline shift**: STOP, surface; this is too much movement to absorb without checkpoint discussion
- **Goryo's audit yields any commit that shifts WR >5pp**: STOP, validate, surface
- **`engine/` change required by any item**: STOP, that's Phase C territory; defer
- **Phase B Phlage+Consign + Replicate combos shift JB WR >+10pp vs Boros**: STOP, JB might be over-tuned now; calibrate

## Methodology notes for tomorrow

- **`oracle-text-verify-before-touching-card-mechanics` v1.6 is mandatory.** Pull oracle from local DB before any card-mechanic commit. Quote verbatim in commit message body. The 3 misreads tonight (Galvanic, March, Prismatic) are the most-recent example of the cost.
- **The user explicitly noted Breach decks are banned** — `duplicate-deck-files-in-canonical-field` IMPERFECTION around Grinding/Temur Breach is moot for canonical. Orzhov Blink (phantom of Esper) is still real but lower priority.
- **`canonical-field-missing-match-apl-entries`**: 1 of 4 fixed (Jeskai Blink in 5452122). Temur Breach 26L SHIM is no longer relevant (banned). Orzhov Blink phantom remains.
- **Cross-APL bug-pattern**: maturity correlates with oracle fidelity. Plan for incremental audit per APL; don't try to do all at once.

## Coverage of OPEN imperfections at end of chain

| Imperfection | Resolved by | Notes |
|---|---|---|
| `gemma-apl-quality-low-for-smoke-gate` | #7 | Gemma quality lift |
| `mulligan-logic-portfolio-gap` | (deferred) | Match APL audit largely OK; remaining gap is `on_play` branching |
| `canonical-field-missing-match-apl-entries` | (mostly resolved) | Only Orzhov Blink phantom remains |
| `card-specs-phase-b-migration-pending` | (deferred to focused session) | Needs bit-stable per APL |
| `card-specs-phlage-engine-no-sacrifice-quirk` | (accepted as model gap) | Documented |
| `jeskaicontrol-key-mismapping` | (5 min cleanup) | Should fold into chain spec |
| `engine-fidelity-gaps-warp-mechanic-not-modeled` | (Phase C, parked) | 28% canonical impact; deferred |
| `engine-fidelity-gaps-jeskai-blink-cards` | (Phase C, parked) | Saga ch II/III, Goblin treasure, Arena haste |
| `cross-canonical-apl-shared-card-bug-pattern` | #6 (partial — Goryo's) | Multi-APL incremental |

End-of-chain target: **2-3 OPEN imperfections** if Sections 1-3 land. Phase C work is the durable backlog.

## Changelog

- 2026-04-29 night: Created in-session by Claude Code after 13 mtg-sim commits + spec doc + Phase A agent dispatch. Reflects realistic state of work that needs to happen next.
