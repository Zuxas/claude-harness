# Blitz Build Order -- 2026-06-28

Status: PLAN
Synthesized from: 4 spec impl-plans (scoping) + IMPERFECTIONS triage (READ-ONLY verification pass).
Hard constraint this blitz: mtg-sim is READ-ONLY for behavior edits; a concurrent workflow is
actively writing under mtg-sim/apl/. New files under mtg-sim are allowed but must gate on a re-run
state audit (do not clobber the apl/ writer). harness/ is fully disjoint and unconstrained.

---

## PART 1 -- SPEC BUILD SEQUENCE (by value / risk / deps)

Rank by leverage, then by "additive + no deps" (can land without touching locked baselines or
waiting on the apl/ writer). llm-as-judge is the highest-leverage build: once it exists, every later
APL change (new decks, mulligan apply, card-specs Phase B) can be graded for decision quality
independently of gauntlet WR%, which de-risks all the baseline-shifting work that follows.

| # | Spec | Recommendation | Value | Risk | Deps | Effort | Impl-plan path |
|---|------|----------------|-------|------|------|--------|----------------|
| 1 | llm-as-judge APL evaluation | build-now | HIGHEST (catches oracle/strategic errors WR cannot see) | NONE (all new files under harness/, no existing file edited) | none | 3-4h | E:/vscode ai project/harness/specs/2026-06-28-llm-as-judge-impl-plan.md |
| 2 | skill-system harness | build-now | MED-HIGH (context-load reduction for every future session) | LOW (additive; one careful full-content harness/CLAUDE.md edit, harness-only) | none | 2-3h | E:/vscode ai project/harness/specs/2026-06-28-skill-system-impl-plan.md |
| 3 | mulligan-parameter-sweep -- Track A only | build-now (A); build-after-deps (B/C) | MED (diagnostic harness; closes mulligan_sweep.py imperfection) | LOW (new mtg-sim/scripts/mulligan_sweep.py, additive, restored monkeypatches) | none for A; B blocked on engine B0 refactor (P0 human) | A: 2-3h build + 0.5-1h compute | E:/vscode ai project/harness/specs/2026-06-28-mulligan-sweep-impl-plan.md |
| 4 | card-specs framework -- additive Steps 1-4 only | build-now (1-4); build-after-deps (Phase B) | MED (closes 2 missing Tier-1 specs + test suite) | LOW for Steps 1-4 (new files; gate on apl/ writer audit) | concurrent apl/ writer (re-run Step 0 audit before each step; __init__.py is a likely merge point) | Steps 1-4: 90-120min | E:/vscode ai project/harness/specs/2026-06-28-card-specs-framework-impl-plan.md |

Parallelization of the spec lane:
- #1 and #2 are FULLY DISJOINT (apl_judge.py + harness/data/ vs harness/skills/ + harness/CLAUDE.md)
  and both harness-only -- run them in parallel on two agents.
- #3 Track A (mtg-sim/scripts/mulligan_sweep.py, new file) and #4 Steps 1-4 (mtg-sim/apl/card_specs/,
  new files) both touch mtg-sim. They do not collide with each other (scripts/ vs apl/card_specs/),
  but #4 collides with the concurrent apl/ writer on apl/card_specs/__init__.py -- gate #4 on a fresh
  audit and reconcile rather than clobber.

Build order within the sequence: 1 -> 2 (parallel) ; then 3A -> 4 (3A first since it has zero
mtg-sim collision risk; 4 needs the apl/ writer to settle).

---

## PART 2 -- IMPERFECTIONS-FIX BATCH (fixable_in_workflow == true)

Grouped into collision-free lanes by file ownership so parallel fixers never touch the same file.
Two shared-file hazards drive the grouping:
  (a) apl/__init__.py:245 (MATCH_APL_REGISTRY) -- every new-deck registration edits this one line
      region; it MUST be a single owner.
  (b) harness/IMPERFECTIONS.md -- every fixer marks its own entry done; treat as a serial ledger,
      single writer at merge (or each fixer edits only its own entry block, never the index).

### WAVE 1 -- parallel-safe, zero / low baseline risk (run concurrently)

LANE 1 -- New additive match APLs (OWNER of apl/__init__.py)
  - apl/temur_prowess_match.py (NEW)   -- extend IzzetProwessMatchAPL w/ Temur SB (~45-60min)
  - apl/grixis_midrange_match.py (NEW) -- clone Dimir Midrange, Psychic Frog->Orcish Bowmasters (~30-45min, lowest effort)
  - apl/sultai_midrange_match.py (NEW) -- Dimir-like + green (Subtlety/Abhorrent Oculus) (~45-60min)
  - apl/temur_breach_match.py (NEW)    -- replace the 27L SHIM fallback (~60-90min)
  - apl/__init__.py (EDIT :245)        -- register all four (single owner = this lane)
  Risk: LOW-MED, additive, no locked baseline shifted (improves opponent quality for ~8.6% combined
  field slice). Start with grixis (cheapest), reuse the template for sultai + temur-prowess.

LANE 2 -- Izzet Maestro Opus trigger (OWNER of the maestro files)
  - apl/izzet_maestro_standard.py:87-96 (EDIT) + apl/izzet_maestro_standard_match.py (EDIT)
  - Add _fire_opus_triggers(gs) mirroring Colorstorm Stallion's hook (the "deferred to APL" /
    "tracked by handlers" circularity = Maestro is still a static 2/2). ~20-30min.
  Risk: LOW-MED, re-validate Izzet Maestro WR only (NOT a locked canonical baseline).

LANE 3 -- Phlage 6/6 doc-only closure (OWNER of the phlage docstring region of card_handlers)
  - engine/card_handlers_verified.py:26474-26489 (EDIT, docstring only)
  - Document "Phlage 6/6 stays on board; sacrifice-unless-escaped + recurring attack trigger NOT
    modeled" as a known engine model gap. ~30min. (The engine sac-clause change is baseline-shifting
    -- deferred to Wave 2; do ONLY the doc here.)
  Risk: NONE (comment only). NOTE: this lane reserves the :26489 region, which Wave-2 engine-fidelity
  also touches (Phlage attack trigger) -- so engine-fidelity Phlage work must NOT run concurrently
  with this lane; sequence Lane 3 -> Wave-2 engine on that file.

SPEC-SUBSUMED (do NOT spin a separate fixer -- delivered by Part 1):
  - mulligan-threshold-not-empirically-validated  == scripts/mulligan_sweep.py  -> Spec #3 Track A
  - no-llm-as-judge-apl-evaluation                == harness/scripts/apl_judge.py -> Spec #1

### WAVE 2 -- fixable_in_workflow but BASELINE-SHIFTING (serial, each with its own bit-stable gauntlet)

These are real, verified, and in-scope, but each one moves a locked canonical number
(64.5%/78.8% Boros, or recorded FWR), so they cannot run as carefree parallel quick-wins. Run each
serially with a parallel_launcher bit-stable gauntlet (n=1000 seed=42, pre/post diff; stop > 0.5pp).
Distinct files -> no cross-collision, but each is its own re-baseline event.

  W2-a  warp-cost-unbraced-no-op -- engine/game_state.py:720-726
        Brace 7 legacy warp cost strings ('1U'->'{1}{U}', '1W'->'{1}{W}', '1G'->'{1}{G}', ...).
        HIGH value (legacy warp currently casts for FREE; ~28% of canonical Modern field warp-casts).
        Changes free->costed = non-byte-identical; re-validate every affected warp deck. Isolated file.

  W2-b  engine-fidelity-gaps-jeskai-blink-cards -- engine/sagas.py:127 + card_handlers_verified.py:8720/:17695/:26489
        Add Fable to SAGA_EFFECTS (chapters II loot / III transform), give Goblin Shaman token
        treasure-on-attack, wire Arena of Glory haste grant, wire Phlage attack trigger. Shifts
        Boros + JB baselines. Must run AFTER Lane 3 (shares the :26489 region). ~2-3h + gauntlets.

  W2-c  engine-apl-nondeterminism-id-based-ordering -- apl/amulet_titan.py + apl/boros_energy_match.py + tests/test_determinism.py
        Replace id()-based set/iteration ordering (12 sites amulet, 5 sites boros_match) with a stable
        sort key; add the missing cross-process same-seed regression test. boros_energy_match is a
        locked-baseline deck -> bit-stable required. ~1.5-2.5h.

---

## PART 3 -- DEFER (with reason)

Spec tails (deps not met this blitz):
  - mulligan-sweep Track B + Track C -- Track B blocked on engine prerequisite B0 (canonical FWR
    engine match_runner.run_match :1554-1575 never calls apl.keep, so a sweep through it returns
    identical WR for every cell = zero signal). B0 is a P0 human engine refactor and mtg-sim is
    READ-ONLY this workflow. Track C (apply thresholds) blocked on the concurrent apl/ writer AND on
    Track B results. Also G6 noise-floor warning: Affinity's analogous sweep found NO signal at n=300;
    plan for a possible null result before funding B0.
  - card-specs Phase B (migrate boros_energy / jeskai_blink_match / uw_blink_match / esper_blink_match
    to card_specs) -- NOT a pure refactor: 6 concrete divergences between card_specs/phlage.py and
    boros's inline _handle_phlage (opposite sacrifice disposition, color-blind vs colored escape gate,
    cmc-sorted vs GY-order exile, no P/T set, missing guide/life side effects). A naive swap moves the
    locked 64.5%/78.8% baseline. Requires a parameterize-first step + per-file bit-stable gauntlet, and
    is blocked on the concurrent apl/ writer. (Tracked as imperfection card-specs-phase-b-migration-pending,
    fixable_in_workflow=false.)

Engine baseline-shifters NOT in the blitz-parallel batch: moved to Wave 2 (serial+gauntlet) above
rather than deferred outright -- they are doable this blitz but only one-at-a-time with re-baselining.

Out-of-blitz (fixable_in_workflow == false):
  - cross-canonical-apl-shared-card-bug-pattern -- per-APL oracle audits across 8 match APLs, 16-32h,
    every fix baseline-shifting. Unbounded; needs apl_judge (Spec #1) as a force multiplier first.
  - standard-apl-goldfish-only-no-match-quality -- 12-16h for top-4; full hand-tracking/removal rebuild.
  - sim-no-hidden-information -- STRUCTURAL, 2-3 weeks, architecture-level + full re-baseline.
  - card-search-no-attribute-filter -- WRONG REPO: analysis/card_embeddings.py does not exist in
    mtg-sim (lives in mtg-meta-analyzer). Out of scope for this triage.
  - arl-generated-code-exec-unsandboxed -- code in harness/agents, not mtg-sim; deny-list gate already
    live, full subprocess sandbox is MED-HIGH separate effort.
  - mcp-rule-of-two / mtg-strategy-blocks-not-codebase-grounded / mtg-strategy-format-meta-block-decays
    -- policy/knowledge-doc items in harness/, not code; LOW-effort doc refreshes, not blitz code work.

Stale-entry corrections surfaced by the triage (apply when updating IMPERFECTIONS.md):
  - card-specs-phlage line ref 26044 is now 26474.
  - Orzhov Blink now routes to UWBlinkMatchAPL (:392), not EsperBlink.
  - Grinding Breach already deleted/resolved.
  - maestro-opus entry assumed the APL was deferred; apl/izzet_maestro_standard.py now EXISTS with the
    Opus pump still unwired (Lane 2 closes it).

---

## EXECUTION SUMMARY

1. Kick off Spec #1 (llm-as-judge) and Spec #2 (skill-system) in parallel -- harness-only, disjoint, no deps.
2. In parallel with the specs, run Wave-1 fixer lanes (Lane 1 new APLs / Lane 2 maestro / Lane 3 phlage doc) --
   collision-free; Lane 1 single-owns apl/__init__.py.
3. After Spec #1/#2 land: Spec #3 Track A, then Spec #4 Steps 1-4 (gate on apl/ writer audit).
4. Wave-2 baseline-shifters one at a time, each with a bit-stable gauntlet (Lane 3 -> W2-b ordering on
   card_handlers:26489).
5. Single writer reconciles harness/IMPERFECTIONS.md at the end (mark closed entries; apply stale-ref corrections).
