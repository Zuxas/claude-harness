# Day Report — 2026-04-28 (Tuesday)

**Project:** mtg-sim + harness (Magic: The Gathering match simulator + methodology layer)
**Wall time:** ~9 hours
**Headline:** 7 specs shipped, 8 commits, bit-stable baseline locked, ready for Friday's Pro Tour data

---

## TL;DR (for the friend)

Today shipped 7 well-scoped pieces of work across the Magic: The Gathering simulator. Three were foundational: a tagger-load-path bug fix that unblocked a whole class of feature work, a determinism fix that made gauntlet runs bit-stable across same-seed re-runs, and a wiring job that made the auto-pipeline (which auto-generates AI pilots for new tournament archetypes) actually feed its output into the next nightly retune. Two were validation infrastructure: an audit of all cache-write call sites surfaced 5 instances of a known bug class, and a new automated check in the methodology drift-detector now catches future regressions of that bug. The headline competitive-prep number — Boros Energy variant edge over the canonical version against the Modern field — settled at +14.3pp with zero drift on consecutive same-seed re-runs, the cleanest baseline state the project has had.

---

## Morning state (what was on the tasker)

The harness runs an automated 04:30 snapshot + 04:50 Gemma drift PR daily. This morning's artifacts said:

**04:30 snapshot pending work:**
- Phase 3.5 keyword coverage — stuck on a tagger load-path bug discovered yesterday
- Stage 1.7 event-bus determinism — known issue, gauntlet runs drifting ±0.6pp aggregate on same-seed re-runs
- Menace damage accumulation fix — code shipped yesterday, never tested
- Standard *_match.py WIP triage — 12 modified + 3 untracked files since 2026-04-23
- Drift detection: 1 cosmetic WARN (stale ARCHITECTURE.md), 0 errors

**04:50 Gemma drift PR (independently ranked recommendations):**
1. Tagger Load-Path Unification (~60-90 min) — blocking all keyword-effect work
2. Stage 1.7 Event Bus Determinism (~30-60 min) — measurable impact at gauntlet scale
3. Menace Combat Test Case (~30 min) — small, contained, tests recently-shipped Stage A code

Gemma also flagged a methodology lesson candidate: "tagger-load-path-dependency-is-a-feature-blocker" — features that depend on card tags (keywords, abilities) must validate execution path across all data loading mechanisms before being considered complete.

**Pre-authored execution chain (`harness/plan-2026-04-28-execution-chain.md`):** 11-step sequence covering the 3 Gemma items plus 8 follow-on items. Gemma's ranking independently aligned with the chain's first three items (positive validation signal — the methodology and the AI's pattern-recognition agreed on priorities).

---

## What got done today

### 7 specs shipped (in execution order)

| # | Spec | Commit | What it did |
|---|---|---|---|
| 1 | tagger-load-path-unification | `199d28e` | Made the keyword-tagging engine call work for both `.txt`-loaded decks AND dict-stub decks (previously only worked for `.txt`). Unblocks all keyword-effect features (Stages A, B, C now active against the full 14-deck Modern test corpus, not just 11). |
| 2 | stage-1.7-event-bus-determinism | `30c992a` | Identified and fixed the third mutation source breaking determinism: naked `random.foo()` calls across ~10 sites in engine code reading OS-entropy global state per subprocess. Fix: save/seed/restore global random state around `run_match_set` + `run_bo3_set`. **Result: bit-identical aggregate on same-seed re-runs (was ±0.6pp drift).** |
| 3 | auto-pipeline-nightly-integration | (harness, no commit) | Wired the `auto_pipeline.py` archetype-detection layer into the nightly harness behind `--enable-auto-pipeline` (default OFF for safety). Friday's Pro Tour data scrape will now feed into the auto-pipeline if the flag is flipped. |
| 4 | auto-pipeline-output-flow-to-retune | `1a4f97a` | The auto-pipeline can now actually produce output that flows into the next gauntlet retune: APL registry auto-registration, deck-file generation from the meta-analyzer DB, 50-game crash-only smoke gate, dedup. (Tested live; 0/3 of today's Gemma-generated AI pilots passed the smoke gate, but the infrastructure works — quality lift is tomorrow's spec.) |
| 5 | cache-key-audit-mtg-sim | (harness, no commit) | Read-only audit of all 27 cache-write call sites in mtg-sim. Found 5 instances of a known bug class (read-modify-write on shared JSON without atomicity). 17 sites safe by construction, 6 safe by convention, 2 latent, 3 active hazard. All 5 became tracked imperfections for tomorrow's fix spec. |
| 6 | drift-detect-7th-check-cache-key-audit | (harness, no commit) | Added an automated heuristic check that catches the FIRST subspecies of cache-collision bugs going forward. New `lint-cache-keys.py` AST walker + `Check-CacheKeys` step in `drift-detect.ps1`. 0 findings on current codebase (the bug it catches was fixed yesterday). |
| 7 | gexf-converter | (harness, no commit) | Project visualization: converts daily project graph snapshots to GEXF format for Gephi visualization. 3098 nodes, 2522 edges in today's snapshot, byte-stable across re-runs. |

### 8 mtg-sim commits

```
1a4f97a apl: auto-pipeline output flow -- registry fallback + auto-generated APLs/decks
19faed5 ARCH: bit-stable baseline post-Stage-1.7
30c992a engine: Stage 1.7 event_bus / global-random determinism
330d034 ARCH baseline post-tagger-fix
199d28e engine: tag_keywords in build_deck_from_dict
74e19a1 decks: .txt follow-up Standard meta refresh
bfe6e58 audit:fuzzy-fallback marker on stub_decks.py
2a2222e apl: Standard *_match.py meta refresh (15 files, +1268/-302)
```

### Headline competitive-prep numbers (the real point of the project)

The simulator's job is to predict win rates for Boros Energy (the user's competitive deck for Modern) against the field, and to compare a custom variant against the canonical version to validate the variant's edge before competitive use.

| Measurement | Value | Notes |
|---|---|---|
| Canonical Boros Energy vs Modern field | **64.5%** | n=1000, seed=42, post-Stage-1.7 baseline |
| Variant Boros Energy vs Modern field | **78.8%** | same |
| **Edge of variant over canonical** | **+14.3pp** | the headline competitive metric |
| Per-matchup max deviation on same-seed re-run | **0.00pp** | bit-stable contract holds |
| Aggregate deviation on same-seed re-run | **0.00pp** | same |

**Trust level:** highest the project has had. The bit-stable baseline at HEAD `30c992a` becomes the anchor for all subsequent Phase 3.5 keyword-effect work. Pro Tour Strixhaven on Friday May 1 introduces meta noise; running against this clean pre-PT baseline lets us measure post-PT meta shifts cleanly.

### 6 imperfections RESOLVED (closed)

Tracked items moved from `harness/IMPERFECTIONS.md` to `harness/RESOLVED.md`:

1. `phase-3.5-stage-a-menace-untested-empirically` — synthetic test fixture written, 3/3 pass
2. `phase-3.5-stage-c-re-execution` — Stage C verified as no-op against current 14-deck corpus
3. `tagger-load-path-unification` — closed by spec #1 above
4. `stage-1-7-event-bus-determinism` — closed by spec #2 above
5. `auto-pipeline-silent-feature-drift` — closed by spec #3 above
6. `auto-pipeline-output-not-yet-flowing-to-retune` — closed by spec #4 above

### 2 methodology lessons compounded

The methodology layer maintains a running list of generalizable lessons from spec amendments. Two new ones today (now 17 total in `harness/knowledge/tech/spec-authoring-lessons.md`):

1. **`parallel-entry-points-need-mirror-fix`** — when a fix is applied to one parallel entry point (e.g., `run_match_set`), the sibling entry point (`run_bo3_set`) needs the same fix or behavior diverges between them. Surfaced when Stage 1.7 fix's mirror was needed mid-validation.

2. **`stop-conditions-on-subsets-must-use-noise-floor-appropriate-aggregation`** — stop-condition thresholds calibrated for aggregate measurements misfire when applied to subsets where per-matchup noise is higher. Surfaced when a stop condition fired against per-matchup noise during S3.7.

---

## What surfaced today (new tracked items)

6 new imperfections opened (all with concrete next-session fix paths, all addressed by tomorrow's chain):

1. `oauth-vs-raw-v1-messages-compat-unverified` — auth question for auto-pipeline cost model. 60-second probe to settle.
2. `drift-detect-arch-staleness-false-positive-on-non-canonical-runs` — cosmetic WARN persists, risks lint blindness. 15-30 min teach-the-tool fix.
3. `sim-matchup-matrix-rmw-race` (active, MEDIUM) — 3 cache write sites can stomp each other under concurrent runs. Atomic-write fix.
4. `auto-apl-registry-rmw-race-latent` — same pattern, latent, foldable into #3's fix.
5. `optimization-memory-rmw-race-latent` — same pattern, latent, foldable into #3's fix.
6. `gemma-apl-quality-low-for-smoke-gate` — 0/3 of today's auto-generated AI pilots passed quality gate. ICL-exemplar-based prompt lift queued.

**Net delta:** 6 closed, 6 opened. The 6 opened are smaller and better-characterized than the 6 closed; backlog quality strictly improved.

---

## What's next (tomorrow, 2026-04-29)

Tomorrow's execution chain is on disk at `harness/plan-2026-04-29-execution-chain.md`. 9 specs scoped to fill ~9 hours, 3 sequencing options (full-day / Friday-leverage-focused / conservative).

**Recommended Option A order:**

| # | Spec | Effort | Resolves |
|---|---|---|---|
| 0 | Session start (read inbox, snapshot, priority check) | 15-30 min | n/a |
| 1 | OAuth-token compat probe | 5-10 min | 1 imperfection |
| 2 | Drift-detect ARCH-staleness fix | 15-30 min | 1 imperfection |
| 3 | RMW-race cluster fix | 45-75 min | 3 imperfections |
| 4 | Gemma APL quality lift | 45-90 min | 1 imperfection |
| 5 | Drift-detect 8th check (RMW pattern) | 45-75 min | mechanizes |
| 6 | Sibling 7th check (spec validation) | 60-90 min | mechanizes |
| 7 | Within-matchup parallelism (3-5x gauntlet wall reduction) | 60-90 min | infra compounding |
| 8 | Stage A/B 100k re-validation | 90-120 min | Pro Tour prep |
| 9 | Friday Pro Tour readiness verification | 30-45 min | proactive |

**End-of-tomorrow target:** 0 OPEN imperfections if Sections 1-2 ship.

---

## Stats summary

| Metric | Value |
|---|---|
| Wall time | ~9 hours |
| Specs shipped | 7 |
| Mtg-sim commits | 8 |
| Imperfections closed | 6 |
| Imperfections opened | 6 (smaller / better-characterized) |
| Methodology lessons compounded | 2 (now 17 total) |
| Lines changed (mtg-sim) | +2,178 / -515 across 32 files |
| Tests passing | 11/11 (3 menace + 5 protection + 3 determinism) |
| Drift-detect findings | 0 errors, 1 cosmetic WARN |
| Bit-stable baseline | locked at HEAD `30c992a` |
| Headline competitive metric (variant edge) | +14.3pp |

---

## Methodology context (for the friend)

This project uses a methodology layer called "the harness" wrapping the simulator. End-of-day artifacts:

- `harness/IMPERFECTIONS.md` — tracked open items, each with concrete fix path and effort estimate
- `harness/RESOLVED.md` — archive of closed items with commit hashes
- `harness/specs/<date>-<topic>.md` — every non-trivial change has a written spec on disk BEFORE code is written, with falsifiable validation gates and stop conditions
- `harness/knowledge/tech/spec-authoring-lessons.md` — running list of generalizable lessons compounded from spec amendments
- `harness/plan-<date>-execution-chain.md` — daily execution chain authored end-of-previous-day
- `harness/reports/day-report-<date>.md` — this file (new convention as of 2026-04-28)

The methodology overlaps with what production teams call "agile" or "DevOps" — daily stand-ups, backlog grooming, retrospectives, CI/CD, postmortems — adapted for solo work with Claude as collaborator. Specs ARE design docs. IMPERFECTIONS.md IS a backlog. Drift-detect IS CI. The morning chain-priority check IS a one-person async stand-up. Spec-authoring-lessons IS continuous retrospective compounding.

---

*Generated: 2026-04-28 ~end-of-day. Standing convention: `harness/reports/day-report-<date>.md`, authored end-of-day to consolidate the day's tasker (morning state) + accomplishments (specs/commits/imperfections) + next-day outlook into one presentable artifact.*
