# Execution chain: 2026-04-28 (Tuesday morning)

**Created:** 2026-04-28 ~11:50 by claude.ai
**Target executor:** fresh Claude Code session (not the one that shipped last night's arc)
**Estimated wall time:** 6-9 hours including stop-and-discuss between sections
**Source:** session-end handoff from claude.ai conversation that shipped specs 1-4 last night

## Read me first

This file is a paste-ready execution chain. The fresh Claude Code session should:

1. Read `harness/state/latest-snapshot.md` first per `harness/CLAUDE.md` SESSION START PROTOCOL.
2. Read `harness/IMPERFECTIONS.md` and `harness/RESOLVED.md` to understand current state.
3. Read this file as the day's execution plan.
4. Process `harness/inbox/drift-pr--2026-04-28.md` as part of step 1 of the chain (it has Gemma's morning recommendations, which independently align with this chain's ordering).

## State carried forward from last night

Four specs SHIPPED 2026-04-28 (commits in mtg-sim repo):

- `parallel-launcher-cache-collision-fix` at `e4fae86` — RESOLVED
- `phase-3.5-stage-c-protection-cluster` at `186ee05` (C.1) + `18257b3` (C.4 empty validation commit) — SHIPPED as verified no-op against current 14-deck Modern field per Amendment A5 (tagger-load-path mismatch)
- `cache-collision-finding-doc-tightening` — SHIPPED (no commit; harness not git-tracked)
- `past-validation-numbers-audit` — SHIPPED (no commit; documentation-only via JSON recovery)

v1.4 lessons compounded to 15 total in `harness/knowledge/tech/spec-authoring-lessons.md`.

Three OPEN imperfections remain:

- `tagger-load-path-unification` (NEW; surfaced by Stage C A5; spec already on disk at `harness/specs/2026-04-28-tagger-load-path-unification.md`)
- `stage-1-7-event-bus-determinism` (long-standing; updated 2026-04-28 with empirical +0.6pp gauntlet-scale evidence per Stage C A6 + falsifiable production-scale validation gate)
- `phase-3.5-stage-a-menace-untested-empirically` (long-standing; closes via synthetic test)

## Execution chain

Stop and report between each section (quick wins, time-sensitive, foundational, medium-scope tooling) for go/no-go before proceeding. Within each section, complete all items before stopping.

### == QUICK WINS / CLEANUP ==

1. **Process `harness/inbox/`** — read `drift-pr--2026-04-27.md` and `drift-pr--2026-04-28.md`, surface anything that needs action, then move both to `harness/inbox/processed/`. Note: today's drift PR independently ranked tagger-fix #1, Stage 1.7 #2, menace test #3 — same as this chain's ordering. Yesterday's PR likely flagged the cache-collision finding which has since been resolved at `e4fae86`. ~10 min.

2. **Sanity-check `mtg-sim/ARCHITECTURE.md`** — verify the 100k canonical 65.8% headline (commit `6962649`) is still pinned and accurate. No changes unless drift is found. ~5 min.

3. **Write `tests/test_menace_combat.py`** per `harness/specs/2026-04-27-phase-3.5-stage-a-block-eligibility.md` Amendment 1 — 3/4 menace attacker, 2x 2/2 blockers, assert (a) damage accumulation correct via Amendment 1, (b) menace forces 2-blocker assignment, (c) attacker unblocked when only 1 blocker available. Move `phase-3.5-stage-a-menace-untested-empirically` from `IMPERFECTIONS.md` to `RESOLVED.md` on success. ~30 min.

4. **Standard `*_match.py` WIP triage** — 12 modified + 3 untracked files since 2026-04-23. Per file: commit (working), delete (dead), or stash to `apl/_research/` per the established convention. Reference: `engine/_research/README.md` for the stash convention. ~30 min.

5. **Stub registry cleanup** — 28 INFO-level orphan stubs in `data/stub_decks._DB_DECKS` with no APL_REGISTRY references. Per stub: delete (most likely; Phase 3.5 prep that didn't pan out) or wire to APL. ~20 min.

**[STOP — report quick-wins results before proceeding]**

### == TIME-SENSITIVE INSERTION ==

6. **PT Strixhaven pipeline dry run** — PT is Friday May 1 through Sunday May 3, 3 days from today. Decklists land Friday evening. Verify the meta-analyzer scraper + DB update + gauntlet refresh don't crash on existing data. Identify the actual scripts via `MEMORY.md` "post-PT pipeline" reference. If anything crashes, queue as P0 for next session. ~15 min.

**[STOP — report PT dry-run results before proceeding]**

### == FOUNDATIONAL ==

7. **Execute `harness/specs/2026-04-28-tagger-load-path-unification.md`** end-to-end. Spec is PROPOSED on disk with full T.0-T.4 sub-stages, 7 validation gates, per-matchup density predictions for the 3 stub-loaded opps (Izzet Prowess, Domain Zoo, Esper Blink), documentation cascade across Stage A/B/C specs. Key prediction to verify: variant Domain Zoo 99.8% → ~94.8-97.8% post-fix (4 Scion of Draco filtered as untargetable from BE damage spells). ~60-90 min.

**[STOP — report tagger-fix results, especially the 3-matchup comparison table and any Stage A/B/C cascade amendments needed, before proceeding to 1.7]**

8. **Write and execute Stage 1.7 spec** based on the in-progress draft at `harness/specs/2026-04-28-stage-1.7-event-bus-determinism.md` (if one exists) or write from the IMPERFECTIONS entry. Diagnostic-first: instrumentation, 5 sequential games seed=42, diff hashes, identify third mutation source, fix, validate.

   **Critical:** use the post-tagger-fix baseline (from step 7) as the C.0-equivalent reference for the falsifiable validation gate. Per Stage C A6 + the IMPERFECTIONS entry: re-run the C.0 + C.4 sequence (canonical + variant gauntlets at n=1000 seed=42 with a deliberately-inert change), expect ≈0.0pp aggregate drift on both decks (was +0.6pp variant / 0.0pp canonical pre-1.7). If drift collapses to ≈0.0pp, 1.7 is empirically verified at production gauntlet scale. ~30-90 min.

**[STOP — report 1.7 results, especially whether the validation gate hit ~0.0pp drift, before proceeding to medium-scope tooling]**

### == MEDIUM-SCOPE TOOLING ==

9. **Execute `harness/specs/2026-04-28-cache-key-audit-mtg-sim.md`** — audit-only; produces findings doc + new IMPERFECTIONS entries for any active or latent bugs. Should run before step 10 because step 10 validates against findings count. ~30-60 min.

10. **Execute `harness/specs/2026-04-28-drift-detect-8th-check-cache-key-audit.md`** — mechanical detection of the cache-collision bug class via heuristic in `drift-detect.ps1`. Validates against the audit findings from step 9 (Gate 2). ~45-75 min.

11. **Execute `harness/specs/2026-04-28-gexf-converter.md`** — single-frame GEXF output for Gephi force-layout rendering. ~45-60 min.

**[STOP — report final state, count of OPEN imperfections, any new findings, anything queued for next session]**

## Why this order

- **Inbox first** gives morning context before any other work
- **ARCHITECTURE check before WIP triage** — triage produces commits; verify baseline is clean first
- **Menace test before WIP triage** — they're independent; menace is the contained closeable
- **PT dry run before foundational** — clears time-sensitive risk before settling into bigger work
- **Tagger-fix before 1.7** — tagger-fix changes the gauntlet baseline (3 stub-loaded matchups shift); 1.7's diagnostic + validation gate uses the post-fix baseline. Reverse order would force re-baselining twice.
- **Cache-key audit before drift-detect 8th** — audit produces findings; 8th check mechanizes detection. Audit first means 8th has real findings to validate Gate 2 against.
- **GEXF converter last** — independent of everything else; pure capability addition.

## Stop conditions across the chain

- If quick-wins reveal anything bigger than expected (e.g., WIP triage uncovers a real bug, not just dead code): stop, surface, decide.
- If PT pipeline dry run crashes: stop, escalate as P0 for next session.
- If tagger-fix predictions miss by >5pp on any of the 3 stub-loaded matchups: stop and diagnose; could be additional tagger gaps OR APL responses to newly-tagged creatures behaving unexpectedly.
- If 1.7 diagnostic surfaces multiple bug-candidate components instead of one: fix one at a time per spec stop conditions, partial-ship if needed.
- If cache-key audit surfaces an active bug worse than the original cache-collision: stop, escalate, possibly re-prioritize remaining chain.

## Reporting expectations at each stop

- What got done (with commit hashes if applicable)
- Validation gate results
- Anything unexpected
- IMPERFECTIONS state delta (closed / opened / updated)
- Confidence on proceeding to the next section

## Changelog

- 2026-04-28 ~11:50: Chain authored by claude.ai for fresh Claude Code session handoff. Yesterday's `plan-2026-04-28.md` is stale (pre-execution priorities); this chain reflects the post-tonight-arc state.
