# harness/RESOLVED.md -- Resolved Imperfections Archive

Created: 2026-04-27
Last updated: 2026-04-27

This file is the durable archive of imperfections that have been
resolved. When an imperfection in `IMPERFECTIONS.md` reaches RESOLVED
status, its entry is moved here (not deleted) so the resolution
history is queryable.

Format matches IMPERFECTIONS.md exactly.

---

## Resolved imperfections

### auto-pipeline-output-not-yet-flowing-to-retune

**Source spec:** `harness/specs/2026-04-28-auto-pipeline-output-flow-to-retune.md`
**Resolved:** 2026-04-28 via execution-chain S4. All 5 sub-bullets addressed in single spec per scope discipline.

**What was not perfect:** S3.9 wired auto_pipeline into nightly_harness but its OUTPUT didn't reach nightly retune. Generated APL files sat in `data/auto_apls/<slug>.py`; no APL_REGISTRY entry, no deck file, retune SKIPped them. Same partial-effect-at-SHIP shape as tagger-fix's pre-activation state.

**Architectural decisions made in spec body (each defended in pre-flight + risk register):**
- **Decklist source:** "most recent top-finish per archetype in format" from meta-analyzer DB (`SELECT d.id FROM decks d JOIN events e ON e.id=d.event_id WHERE d.archetype=? AND e.format=? ORDER BY e.date DESC, d.placement ASC LIMIT 1` — format values lowercase per T.0 verification). Cards JOIN'd via `cards` table (T.7 surfaced schema mismatch — `deck_cards` has `(deck_id, card_id, quantity, is_sideboard)` not `(deck_id, card_name, quantity, sideboard)`; corrected in T.7 retry).
- **Auto-registry:** separate JSON sidecar at `mtg-sim/data/auto_apl_registry.json` merged at lookup time in `apl/__init__.py:get_apl_entry`. Canonical APL_REGISTRY never mutated. Per `parallel-entry-points-need-mirror-fix` v1.5 lesson, `get_apl_entry` is the single fallback site that `get_apl` and `get_match_apl` both transit (refactor moved canonical lookup from `get_apl` body into `get_apl_entry` so the auto fallback applies uniformly).
- **Auto-APL location:** moved from `data/auto_apls/` to `apl/auto_apls/` (with `__init__.py`) so files are normally importable as `apl.auto_apls.<slug>`.
- **Deck-file location:** `decks/auto/<slug>_<format>.txt` subdir with `// audit:auto-generated:<archetype>:<date>` marker on line 1. Lint orphan-deck check extended to (a) consult `data/auto_apl_registry.json`, (b) honor the marker as backstop.
- **Quality gate:** `_smoke_test_apl` runs `engine.runner.run_simulation(apl, mainboard, n=50, seed=42)`. Crash-only gate (no win-rate threshold) — Gemma APLs aren't tuned, just need "doesn't break gauntlet". Failed-smoke APLs stay on disk for manual review but don't enter auto registry.
- **Dedup:** `_already_generated()` checks both APL file existence AND `optimization_memory.json` entry. `--force` CLI flag bypasses.
- **Top-N:** `--top-n` CLI arg, default 3 for safety; nightly can pass higher for post-PT meta with many new archetypes.

**T.7 live test outcome — infrastructure works, Gemma quality is the gap:**
- ✓ Deck files generated for all 3 archetypes (Landless Belcher 60-card mainboard / 15 SB; Cutter Affinity 60/15; Jeskai Phelia 60/15 — all sum correctly to 60 main + 15 SB)
- ✓ Smoke gate fired for all 3
- ✗ All 3 smoke failed: Landless Belcher (`'GameState' object has no attribute 'get'` — Gemma API misuse), Cutter Affinity (`no_apl_class` — Gemma didn't define a class with name ending in "APL"), Jeskai Phelia (`SyntaxError at line 137` — Gemma generated invalid Python)
- 0 APLs registered → `auto_apl_registry.json` not created → retune behavior unchanged (still SKIPs these archetypes)
- Per spec stop-condition for "all smoke fail," shipped infrastructure with documented outcome. Wire works for FUTURE archetypes if Gemma quality improves or Claude path verified.

**Two new IMPERFECTIONS entries opened to track the residual gaps:**
- `gemma-apl-quality-low-for-smoke-gate` (4 fix-candidate paths, 30-60 min)
- `oauth-vs-raw-v1-messages-compat-unverified` (60-second probe, low priority — Gemma default sidesteps)

**All 9 validation gates passed:**
- Gate 1 (T.0 pre-flight): all 3 archetypes had decks in meta-analyzer DB
- Gate 2 (T.2 file move): `apl/auto_apls/` exists with __init__.py + 3 relocated APL files
- Gate 3 (T.3 deck-file write): all 3 deck files created with marker; mainboard quantities sum to 60
- Gate 4 (T.4 smoke gate): clear crash diagnostics for all 3 (so failure surface is documented)
- Gate 5 (T.5 registry insertion): no `auto_apl_registry.json` written because no APL passed; canonical APL_REGISTRY pristine
- Gate 6 (T.5 lookup integration): `get_apl_entry("Boros Energy")` returns canonical tuple; `get_apl_entry("Landless Belcher")` returns None (auto registry empty); auto-fallback path verified working via `_load_auto_registry()` returning `{}`
- Gate 7 (T.7 retune visibility): N/A this run (no APLs registered); fallback path verified via Gate 6 will work as soon as a smoke passes
- Gate 8 (drift-detect + lint): drift 0 errors / 0 warnings / 0 findings; lint orphan-deck count for `decks/auto/*` = 0 (marker working); total lint INFOs dropped 44 → 40
- Gate 9 (no canonical regression): 3 test files all pass (menace 3/3, protection 5/5, determinism 3/3); canonical Boros Energy n=200 seed=42 bit-stable across 2 runs (64.3% / 64.3%); Stage 1.7 invariant preserved post-spec

**Files touched (all unversioned):**
- `harness/agents/scripts/auto_pipeline.py` (3 new helpers + STEP 2.5 + dedup + top-N + force)
- `mtg-sim/apl/__init__.py` (auto-registry fallback in `get_apl_entry`; refactored `get_apl` to consume `get_apl_entry`)
- `mtg-sim/apl/auto_apls/__init__.py` (new package marker)
- `harness/scripts/lint-mtg-sim.py` (`audit:auto-generated` marker recognition + `auto_apl_registry.json` consultation in orphan-deck check)
- `harness/HARNESS_STATUS.md` (Layer 5 wire status updated with output-flow + Gemma quality measurement)
- `harness/specs/2026-04-28-auto-pipeline-output-flow-to-retune.md` (PROPOSED → SHIPPED with full T.0-T.8 changelog)

**Estimated effort actual:** ~75 min including spec authoring (15 min), T.0 pre-flight (5 min), T.1-T.6 patches (30 min), T.7 live runs including 2 retries for schema mismatch + dedup-gating fix (15 min), T.8 cascade (10 min).

---

### auto-pipeline-silent-feature-drift

**Source finding:** Execution-chain S3.7 post-task audit (2026-04-28).
**Source spec:** `harness/specs/2026-04-28-auto-pipeline-nightly-integration.md`
**Resolved:** 2026-04-28 via execution-chain S3.9.

**What was not perfect:** Layer 5 `auto_pipeline.py` was claimed OPERATIONAL since 2026-04-16 in HARNESS_STATUS.md, with a manual-trigger PowerShell wrapper (`harness/scripts/auto-pipeline.ps1`). But no scheduled task invoked the wrapper, and `nightly_harness.py` did not call `auto_pipeline.run_pipeline()`. Result: `harness/agents/optimization_memory.json` was NEVER written; no APL generation against any meta shifts had ever occurred in production. Friday PT-watch risk was HIGH because PT-emergent archetypes would all SKIP at retune.

Same `load-path-dependent-setup-creates-silent-no-op-features` class as tagger-load-path: feature exists, has tests, has docs claiming OPERATIONAL, but no automation invokes it against real workload.

**Why not fixed earlier:** No empirical signal had triggered the gap. Layer 5 was assumed OPERATIONAL based on the manual dry-run from 2026-04-16 (per MEMORY.md). The "wired into automation" check was never explicit.

**T.0 auth-path probe result:** `apl/auto_apl.py:_get_api_token` resolved successfully from Claude Code OAuth credentials (`~/.claude/.credentials.json`); token prefix `sk-ant-o...`, length 108. Whether this OAuth token works for raw `api.anthropic.com/v1/messages` calls is unverified; Gemma default sidesteps the question for Friday safety.

**Concrete fix shipped:**
1. Added `--enable-auto-pipeline` flag to `nightly_harness.py` (default OFF). Inserts new STEP 1.5 between meta detection and retune; calls `auto_pipeline.run_pipeline()` with `use_claude=False` (Gemma) by default. Wrapped in try/except so auto_pipeline failure doesn't block other nightly steps.
2. Added `--auto-pipeline-use-claude` flag (default OFF). Both flags required to invoke Claude path — two opt-ins prevent accidental console billing.
3. Added matching `-EnableAutoPipeline` / `-AutoPipelineUseClaude` switches to `harness/scripts/nightly-harness.ps1` wrapper for clean scheduled-task command-line flip.
4. T.3 verified Gate 6 (default-off behavior unchanged from pre-spec; Friday scheduled task safe). Verified Gate 3 (opt-in adds STEP 1.5 with expected dry-run output).
5. T.4 live test (auto_pipeline standalone with --use-gemma against current Modern meta): 8 new archetypes detected, top 3 (Landless Belcher 18.7%, Cutter Affinity 7.5%, Jeskai Phelia 4.7%) generated via Gemma in 499s wall, $0.00 cost. Wrote `optimization_memory.json` for first time (3 APLs + 3 playbooks logged). Generated APL files: `mtg-sim/data/auto_apls/{cutter_affinity, jeskai_phelia, landless_belcher}.py`.
6. T.5 idempotency: second run completed cleanly; playbooks correctly short-circuit ("All decks with sim data already have playbook drafts"); APLs re-generate (memory now has 6 entries, append-only, not deduped). Wasteful but not broken — refinement deferred.

**Friday-safety statement:** `harness/scripts/register-harness-tasks.ps1` invokes `nightly-harness.ps1 -Format <fmt>` (no flag). PowerShell wrapper does not pass `--enable-auto-pipeline` to the Python script unless `-EnableAutoPipeline` switch is present. Verified via dry-run that default-off behavior is byte-equivalent to pre-spec for STEPS 1-7 (only addition: STEP 1.5 "SKIPPED" log line).

**Known follow-ups (NOT in scope, deferred to separate specs):**
- APL re-generation deduplication (T.5 surfaced this — second run regenerates same 3 APLs)
- Auto-registration of generated APLs into `apl/__init__.py:APL_REGISTRY` (currently APL files exist on disk but retune still SKIPs because no registry entry)
- Validation gauntlet for generated APLs (small-N gauntlet, only promote if WR within sanity bands)
- Bump top-N cap from 3 to user-configurable (Friday's PT could surface 30+ new archetypes)
- OAuth token vs raw v1/messages compatibility verification

**Estimated effort actual:** ~50 min including spec authoring (15 min), T.0 auth probe (3 min), T.1 patch + wrapper update (10 min), T.3 dry-run verification (3 min), T.4 live run wall time (8 min auto_pipeline runtime), T.5 idempotency (4 min runtime), T.6 docs cascade (10 min).

---

### stage-1-7-event-bus-determinism

**Source finding:** `harness/knowledge/tech/perf-within-matchup-parallelism-2026-04-26.md`
**Additional empirical evidence (Stage C A6):** `harness/specs/2026-04-28-phase-3.5-stage-c-protection-cluster.md` Amendment A6 (+0.6pp variant aggregate drift between C.0 and C.4 with mechanically-inert C.1 patch).
**Source spec:** `harness/specs/2026-04-28-stage-1.7-event-bus-determinism.md`
**Source commit:** 30c992a
**Resolved:** 2026-04-28 via execution-chain S3.8.

**What was not perfect:** n=200 same-seed mtg-sim runs had 2-3 game delta after Stages 1.5 and 1.6 closed Card-state and APL-state leakage. Third mutation source unidentified. At production gauntlet scale (n=1000 over 14 matchups), the same gap manifested as +0.6pp aggregate drift between same-seed runs and ±2.5pp per-matchup variance.

**Diagnostic findings:** Naked `random.foo()` consumers in engine code read from the GLOBAL `random` module instead of passed-in `random.Random` instances:
- `engine/zones.py:29` — `random.shuffle(self.library)` (every library shuffle on game start)
- `engine/opponent.py:245` — `random.random() * 100` (race rolls)
- `engine/race.py:44` — same race roll pattern
- `engine/card_handlers_verified.py` — ~10 sites using `random.choice/shuffle` for handlers like discard, mill, hand reveal, library shuffle effects

`engine/runner.py:156` (the goldfish runner) calls `random.seed(seed)` once at gauntlet start. `engine/match_runner.py:run_match_set` (the match path) and `engine/bo3_match.py:run_bo3_set` (the bo3 wrapper) did NOT, so each subprocess invocation started with OS-entropy-initialized global random state and produced different outcomes for naked-random consumers.

**Hypothesis confirmation (probe):** Two BE mirror n=10 seed=42 runs in the same process without `random.seed` reset between them produced `avg_turns` 5.500 vs 5.800 (0.3 turn drift). Same probe with `random.seed(0)` reset between runs produced bit-identical results.

**Concrete fix shipped:** Save/seed/restore the global random module state around the loop body in both `run_match_set` and `run_bo3_set`. Save with `random.getstate()`, seed deterministically with `random.seed(seed)`, run loop, restore with `random.setstate(saved)` in `finally:` block. Pattern preserves caller's expectations about global random module beyond function scope. No other engine code or APLs touched.

**Refined validation gate (per S3.7 noise-floor characterization, stronger than original n=200 game-delta gate):** Post-1.7 same-seed re-run should produce per-matchup max-deviation ≈0pp AND aggregate ≈0pp on both canonical and variant Modern gauntlets at n=1000.

**Validation results:**
- Canonical Modern gauntlet n=1000 seed=42, two runs: 64.5% → 64.5% (Δ +0.00pp); per-matchup max dev: 0.00pp; all 14 matchups bit-identical.
- Variant Modern gauntlet n=1000 seed=42, two runs: 78.8% → 78.8% (Δ +0.00pp); per-matchup max dev: 0.00pp; all 15 matchups bit-identical.
- Pre-fix per-matchup variance: ±2.5pp; pre-fix aggregate variance: ±0.6pp. Both collapse to 0.00pp post-fix.

**Mid-execution refinement:** Initial fix touched only `run_match_set` and validation showed canonical aggregate +0.10pp / per-matchup max-dev 1.80pp on `bo3` matchups (Domain Zoo, Izzet Affinity, Izzet Prowess, Eldrazi Tron, Jeskai Blink). Investigation: `engine/bo3_match.py:run_bo3_set` is a parallel entry point not routed through `run_match_set`; same fix needed at the bo3 entry. Mirror fix applied. Re-validation: 0.00pp.

**Generalizable lesson candidate (now compounded into v1.5):** "code that relies on a fix at one entry point must be checked for parallel entry points that need the same fix" — generalization of `load-path-dependent-setup-creates-silent-no-op-features` from setup functions to fixes themselves.

**Regression test:** `mtg-sim/tests/test_determinism.py` (3 tests, all pass): consecutive-call determinism, global-state preservation, determinism-under-polluted-global-random.

**Resolves Stage C A6:** The +0.6pp variant aggregate drift between C.0 and C.4 measured 2026-04-28 with mechanically-inert C.1 patch is now empirically explained AND fixed. Stage C A6's hypothesis ("residual non-determinism from third mutation source") confirmed.

**Unblocks:** Within-matchup parallelism implementation (separate spec — engine can now run N games concurrently within a single matchup using thread-pool or process-pool parallelism without contaminating each other). Estimated 60-90 min when picked up.

**Estimated effort actual:** ~60 min including pre-flight grep + minimal probes (in lieu of full D1-D3 diagnostic harness because grep + same-process probe was conclusive evidence), D4 fix (two files), D5 validation including bo3-fix re-validation, D6 regression test, full cascade.

---

### tagger-load-path-unification

**Source finding:** `harness/specs/2026-04-28-phase-3.5-stage-c-protection-cluster.md` Amendment A5
**Source spec:** `harness/specs/2026-04-28-tagger-load-path-unification.md`
**Source commit:** 199d28e
**Resolved:** 2026-04-28 via execution-chain S3.7.

**What was not perfect:** `engine/keywords.py:tag_keywords` was called only from the .txt load path (`data/deck.py:176`). The dict-based load path used by stub-loaded decks (`build_deck_from_dict` in `generate_matchup_data.py`) did NOT call the tagger. Engine never re-tagged at game-setup. Of 14 Modern field opps, 3 used stub path (Izzet Prowess, Domain Zoo, Esper Blink) and their cards entered the battlefield without keyword tags from oracle text scanning. Stages A/B/C keyword filters were silent no-ops against this subset.

**Why not fixed in source spec:** Foundational change requiring its own first-class spec to preserve `spec-prediction-model-must-be-falsifiable` (Stage C validation gates needed to isolate "is C.1 working" from "is tagger-fix working" — bundling would conflate them).

**Concrete fix shipped:** Single-line addition in `generate_matchup_data.build_deck_from_dict` calls `tag_keywords(card)` on every constructed Card before append. Plus the import. Patch refactored the existing `deck.append(Card(...))` inline pattern into `card = Card(...); tag_keywords(card); deck.append(card)` for both the data-found and fallback branches.

**T.0 idempotency verified empirically:** `tag_keywords` skips already-tagged keywords (line 195 of `engine/keywords.py`); second call adds no new tags.

**T.0.5 vs T.2 measurement (apples-to-apples, n=1000 seed=42, same session same HEAD-modulo-T.1-patch):**

| Subset | Canonical pre→post Δ | Variant pre→post Δ |
|---|---|---|
| 11 .txt-loaded (control) | -0.51pp (noise) | -0.05pp (noise) |
| 3 stub-loaded (active) | **-4.52pp** | +0.05pp (variant ceiling) |

**Per-matchup canonical (the matchups where leverage materialized):**
- Izzet Prowess: 49.4% → 41.3% (Δ -8.1pp) — Stage B HASTE on opp's Swiftspear/Slickshot dominant. Aligns with real tournament data showing Prowess favored vs BE.
- Domain Zoo: 89.9% → 87.1% (Δ -2.8pp) — Stage C HEXPROOF on Scion of Draco x4 per Stage C A5 prediction.
- Esper Blink: 62.6% → 62.6% (Δ 0.0pp) — no measurable shift, non-blocking.

**Per-matchup .txt-loaded shifts (ETron canonical -5.1pp, Mono Red -2.0pp, Boros mirror variant -2.1pp) appeared to violate spec stop condition #2** but were confirmed as Stage 1.7 non-determinism residual via same-seed re-run showing per-matchup variance ±2.5pp that mostly cancels in subset-aggregate. Real signal lives at the subset-aggregate level. Generalizable lesson queued for v1.5 compounding (post Stage 1.7 fix validates).

**New trusted baseline (supersedes 2026-04-27 65.8% post-Phase-3 headline as anchor for Phase 3.5 Stages D-K):**
- Canonical Boros Energy: 64.5% field-weighted (`data/parallel_results_20260428_125005.json`)
- Variant Boros Energy Variant Jermey: 78.7% field-weighted (`data/parallel_results_20260428_125019.json`)
- Variant edge: ~+14.2pp (was +12.0pp at Stage A SHIP, partial-effect)

**Documentation cascade landed:**
- Stage A spec Amendment 4 (tagger-fix activation reveals partial-effect at SHIP)
- Stage B spec Amendment 5 (HASTE filter activation on Izzet Prowess as dominant single contributor)
- Stage C spec Amendment A7 (latent → active transition; A5 Domain Zoo prediction landed; A6 non-determinism characterization refined)
- mtg-sim/ARCHITECTURE.md (new baseline section above the prior 65.8% headline)
- This RESOLVED.md entry + IMPERFECTIONS.md "Resolved this week" pointer

**Estimated effort actual:** ~50 min including pre-flight, T.0 idempotency, T.0.5 pre-fix baseline, T.1 patch + commit, T.2 post-fix baseline, T.3 partition analysis, T.4 cascade.

---

### phase-3.5-stage-a-menace-untested-empirically

**Source spec:** `harness/specs/2026-04-27-phase-3.5-stage-a-block-eligibility.md`
**Source commit:** 99037a9
**Resolved:** 2026-04-28 via `mtg-sim/tests/test_menace_combat.py` (3 synthetic tests, all pass <1s).
**What was not perfect:** Stage A wired menace block-eligibility (2+ blocker requirement) and Amendment 1 fixed multi-blocker damage accumulation to attacker (CR 510.1: blocker damage sums on attacker before lethality). Neither had been empirically validated against a live menace creature in match-runner -- the 14-deck Modern gauntlet has no menace creatures (Bloodtithe Harvester etc. are in Rakdos Aggro, not in registered field).
**Why not fixed in source spec:** Registering Rakdos Aggro would have required a deck file + APL stub + verification (its own arc). Spec Amendment 2 downgraded the menace spot-check from gating validation to this imperfection.
**Concrete fix shipped:** `tests/test_menace_combat.py` constructs a `TwoPlayerGameState` with synthetic creatures pushed directly onto `bf_a` / `bf_b`, calls `_resolve_combat` directly. Three tests cover:
- `test_menace_damage_accumulates_kills_attacker` -- 3/4 menace vs 2x 2/2: blocker damage sums to 4 -> attacker dies (Amendment 1 fix verified). Pre-fix bug would have left attacker alive.
- `test_menace_forces_two_blocker_requirement` -- 3/4 menace vs 1x 2/2: only 1 legal blocker, can't satisfy menace -> attacker goes unblocked, deals 3 damage to defender.
- `test_non_menace_only_takes_one_blocker` -- 3/4 plain attacker vs 2x 2/2: confirms `needed = 2 if MENACE else 1` branch is the menace-specific path (only 1 blocker assigned, attacker survives 2 damage).
Pattern follows `tests/test_protection_keywords.py` (Stage C synthetic test scaffolding).
**Estimated effort actual:** ~25 min including spec read, fixture setup, three test cases, and IMPERFECTIONS/RESOLVED moves.

---

### phase-3.5-stage-c-re-execution

**Source finding:** `harness/knowledge/tech/cache-collision-bug-2026-04-27.md`
**Source spec:** `harness/specs/2026-04-28-phase-3.5-stage-c-protection-cluster.md`
**Source revert (parent):** de96593
**What was not perfect:** Stage C C.1 helper code was reverted at de96593
because C.4 validation fired stop conditions that turned out to be cache-
collision artifacts. Once cache-fix shipped (e4fae86) and past-validation-
numbers-audit verified Stage A/B baselines clean, Stage C re-execution
became unblocked.
**Concrete fix shipped:**
- C.0 (added by Amendment A4): Fresh baseline captured at HEAD=e4fae86
  via 2 sequential gauntlets. Canonical 65.1%, variant 77.9%. Drift
  from Stage A/B documented numbers (-0.7/-0.2pp canonical, +0.1/-0.3pp
  variant) attributed to cf75e1a Guide attack-trigger fix engine
  evolution; symmetric and explainable.
- C.1 (commit 186ee05): Cherry-picked f2eb4d7 (helpers + chokepoint
  patch) cleanly. Added `tests/test_protection_keywords.py` (5 unit
  tests, all pass <1s).
- C.2 (verification, no commit): Confirmed BE APL has zero direct opp
  targeting at HEAD; A1 chokepoint claim still holds.
- C.3 (verification, no commit): Confirmed 220 inline non-helper
  handlers in `card_handlers_verified.py` don't need patching for
  current field per A3 reasoning (BE has 0 spells from those handler
  classes; opp self-targets have no asymmetry restriction).
- C.4 (commit 18257b3, empty): Validation gauntlet results.
  Canonical 65.1% (0.0pp drift from C.0), variant 78.5% (+0.6pp drift,
  within A5 ±1pp band). Domain Zoo variant 99.8 -> 99.8 = 0.0pp drift
  (key validation: A5's predicted no-op confirmed empirically).

**Mid-execution Amendment A5** surfaced foundational finding:
`engine/keywords.py:tag_keywords` is called only from `data/deck.py:176`
(.txt load path). Stub-loaded decks never get tagged at runtime.
Engine never re-tags at game-setup. C.1 chokepoint patch is therefore
a true no-op for current 14-deck Modern field (3 stub-loaded opps
including Domain Zoo's 4 Scion of Draco never receive HEXPROOF tag;
11 .txt-loaded opps have 0 protection-cluster creatures). Same
mismatch implicates Stages A and B (MENACE / HASTE / DEFENDER /
VIGILANCE filters silent on stub-loaded opps) — those stages'
shipped impact is partial.

Stage C ships as **latent infrastructure**: helpers are correct
(5/5 synthetic tests pass), chokepoint patched, immediately active
once any future card or matchup includes target.tags with HEXPROOF /
SHROUD / PROTECTION. Currently inert against tested field. New
first-class spec written: `harness/specs/2026-04-28-tagger-load-
path-unification.md` (foundational fix unlocks Stage A/B/C full
impact).

**Estimated effort:** 30-45 min (actual: ~80 min including A5
investigation, density scans, load-path survey, A5 documentation,
new tagger-fix spec authorship)
**Status:** RESOLVED 2026-04-28 at commits 186ee05 (C.1) + 18257b3 (C.4)
**Created:** 2026-04-27 (during C.4 cache-collision discovery)
**Resolved:** 2026-04-28

**Validation impact (n=1000 seed=42):**

| Side | C.0 baseline | C.4 measured | Drift | A5-predicted band |
|---|---|---|---|---|
| Canonical aggregate | 65.1% | 65.1% | 0.0pp | 64.1-66.1% (PASS) |
| Variant aggregate | 77.9% | 78.5% | +0.6pp | 76.9-78.9% (PASS) |
| Variant edge | +12.8pp | +13.4pp | +0.6pp | within band |
| Variant Domain Zoo | 99.8% (sim) | 99.8% (sim) | 0.0pp | exact A5 prediction |

Per-matchup max swings: Mono Red canonical +2.6pp, BE-mirror variant
+3.3pp, Mono Red variant -2.4pp — all under 8pp stop trigger; mechanism
not identified for those matchups (no protection-cluster creatures
involved). At n=1000 sample noise CAN produce ±2-3pp on a single fair
matchup, but with same seed=42 and mechanically-inert patch the
expected per-matchup drift is also ≈0pp. See A6 below for the
likely explanation.

**Amendment A6 (post-SHIP, recorded for future-1.7 calibration):**
The +0.6pp variant aggregate drift between C.0 and C.4 is NOT sample
noise in the usual sense. Both runs used identical seed=42, n=1000,
same HEAD-plus-mechanically-inert-C.1-patch. Expected drift ≈0.0pp.
The +0.6pp is empirical evidence of residual non-determinism — the
same third-mutation-source the long-standing
`stage-1-7-event-bus-determinism` IMPERFECTIONS entry tracks at
n=200 with 2-3 game delta. At gauntlet scale (n=1000 over 14
matchups), it manifests as +0.6pp aggregate drift. This is more
urgent than the IMPERFECTIONS entry framing suggested (production-
scale impact, not just sample-size curiosity).

When Stage 1.7 ships and the third mutation source is fixed,
re-running the C.0 + C.4 sequence should produce ≈0.0pp aggregate
drift. That measurement becomes a falsifiable production-scale
validation gate for 1.7 — stronger than the existing n=200 same-seed
game-delta evidence because it's at the gauntlet scale users
actually measure.

**Unblocks (latent infrastructure activates with):**
`tagger-load-path-unification` (now OPEN imperfection / new first-class
spec)

---

### past-validation-numbers-audit

**Source finding:** `harness/knowledge/tech/cache-collision-bug-2026-04-27.md`
**Source spec:** `harness/specs/2026-04-28-past-validation-numbers-audit.md`
**Source revert (that surfaced parent bug):** de96593
**Path-narrowed by:** spec 2026-04-28-cache-collision-finding-doc-tightening
**What was not perfect:** Variant gauntlet field-weighted numbers across
Phase 3.5 Stages A and B (commits 99037a9, c95ea55) were measured during
mixed-run sessions where the parallel-launcher cache-collision bug was
active. Both stages had concurrent variant + canonical gauntlets within
14 seconds, fitting the cache-collision pollution pattern.
**Concrete fix shipped (documentation-only path):** Recovery via
parallel_results_*.json files written by parallel_launcher.py per-deck.
Those files preserve trustworthy gauntlet measurements independently of
the cache file + display layer pollution. Spec 1's investigation
established the recovery mechanism; spec 3 executed the documentation
cascade:

- `harness/specs/2026-04-27-phase-3.5-stage-a-block-eligibility.md`:
  filled `<X.X>` placeholders in commit message template (canonical
  65.6 -> 65.8, variant 78.4 -> 77.8, edge ~+12.0pp); added changelog
  entry citing recovery sources.
- `harness/specs/2026-04-27-phase-3.5-stage-b-combat-modifiers.md`:
  filled `<X.X>` placeholders (canonical 65.8 -> 65.3, variant 77.8 ->
  78.2, edge +12.0 -> +12.9pp); added changelog entry citing recovery
  sources.
- `harness/knowledge/tech/cache-collision-bug-2026-04-27.md`: added
  "Re-validation results (2026-04-28, post-cache-fix at e4fae86)"
  section with comparison table + bonus belt-and-suspenders verification.
- `harness/IMPERFECTIONS.md`: marked entry RESOLVED + status of
  phase-3.5-stage-c-re-execution flipped from BLOCKED to OPEN.

ARCHITECTURE.md update NOT NEEDED — no Stage A/B variant numbers were
pinned there (only the 100k canonical 65.8% headline, which was
canonical-only and clean by construction).

**Estimated effort:** 15-30 min documentation-only (actual: ~25 min
including Stage A and B spec backfill + finding doc cascade)
**Status:** RESOLVED 2026-04-28 (no commit; harness/ is not git-tracked)
**Created:** 2026-04-27
**Resolved:** 2026-04-28

**Validation impact (drift table from finding doc Re-validation
results section):**

| Stage | Side | Documented | Recovered (JSON) | Drift |
|---|---|---|---|---|
| A | canonical | 65.8% | 65.8% | 0.0pp |
| A | variant | 77.8% | 77.8% | 0.0pp |
| A | edge | +12.0pp | +12.0pp | 0.0pp |
| B | canonical | 65.3% | 65.3% | 0.0pp |
| B | variant | 78.2% | 78.2% | 0.0pp |
| B | edge | +12.9pp | +12.9pp | 0.0pp |

No drift > 2pp on any number. Bonus post-fix re-run (spec 2 Gate 2):
fresh variant gauntlet at 78.5% field-weighted, +0.3-0.7pp drift vs
documented (engine-evolution, well within ±2pp tolerance).

**Unblocks:** phase-3.5-stage-c-re-execution (was BLOCKED on this).

---

### parallel-launcher-cache-collision-fix

**Source finding:** `harness/knowledge/tech/cache-collision-bug-2026-04-27.md`
**Source spec:** `harness/specs/2026-04-28-parallel-launcher-cache-collision-fix.md`
**Source revert (that surfaced bug):** de96593
**What was not perfect:** `data/matchup_jobs/<opp>.json` files were keyed
on opp name only. Two parallel launchers (variant + canonical) spawned
`run_matchup.py` subprocesses that all wrote the same path; last writer
won. Variant gauntlet displays could read canonical's overwritten output.
Spec 2 amendment A1 reframed the bug class: this is subprocess output
file collision, not cache collision (no skip-if-exists logic involved).
**Concrete fix shipped:** New helper module `matchup_jobs.py` (single
source of truth for `_slugify` + `matchup_job_path` + `ensure_parent`).
Both `parallel_launcher.py` (read site) and `run_matchup.py` (write
site) import from it. Path layout changed to
`data/matchup_jobs/<our_deck_slug>/<opp_slug>.json`. Migration: deleted
65 old top-level *.json files. Regression test
`tests/test_cache_isolation.py` covers path keying, slug derivation,
subdirectory layout, and isolated-write/read under both write orders.
**Estimated effort:** 60-90 min (actual: ~75 min including caller audit
+ Gate 2 full gauntlet + Gate 3 concurrent-run isolation verification)
**Status:** RESOLVED 2026-04-28 at commit e4fae86
**Created:** 2026-04-27 (during Stage C C.4 validation)
**Resolved:** 2026-04-28

**Validation impact (n=1000 seed=42):**
- Direct `run_match_set` baseline (Gate 1): variant vs Izzet = 94.0% (matches tonight diagnostic 93.8%)
- Gauntlet display (Gate 2): variant vs Izzet G1=93.9% / Match=99.7% (pre-fix display was 48.5% — canonical's polluted value). Field-weighted aggregate 78.5% matches Stage A 77.8% / Stage B 78.2% pattern.
- Concurrent run isolation (Gate 3): variant + canonical gauntlets run simultaneously produce two distinct subdirectories, each containing the correct deck's data. Spot-check: Eldrazi Ramp variant 92.4 vs canonical 49.2 (43pp gap, no pollution); Orzhov Blink variant 99.8 vs canonical 68.4 (31pp gap, no pollution).
- Regression test (Gate 4): all 5 tests pass in <1 second.
- Drift-detect (Gate 5): exits 0 with only the unchanged stale-ARCHITECTURE WARN.
- Layout verification (Gate 6): `ls data/matchup_jobs/` shows subdirectories per our_deck, no top-level *.json files.

**Unblocks:** past-validation-numbers-audit (was BLOCKED on this);
phase-3.5-stage-c-re-execution unblocks once past-validation-numbers-
audit ships.

---

### guide-attack-trigger-double-firing

**Source finding:** `harness/knowledge/tech/double-firing-handler-bugs-2026-04-26.md`
**Source spec:** `harness/specs/2026-04-27-guide-attack-trigger-fix.md`
**What was not perfect:** Engine `_do_combat` (~line 474) pumped
Guide-itself for 3 energy AND APL `_simulate_guide_attack_trigger`
pumped best attacker for 3 energy (both fired with 6+ energy).
Engine version was wrong per oracle (target should be attacking
creature, not Guide itself) and double-fired with the APL version.
**Concrete fix:** Removed engine `_do_combat` self-pump block;
kept APL handler which targets best attacker correctly. Same
pattern as 8fc9b82 (Voice + Guide-ETB).
**Estimated effort:** 30 min (actual: ~30 min spec + execution)
**Status:** RESOLVED 2026-04-27 at commit cf75e1a
**Created:** 2026-04-26 (retroactive)
**Resolved:** 2026-04-27

**Validation impact (n=1000 seed=42):**
- Canonical goldfish: T4.50 -> T4.51 (+0.01 turn)
- BE mirror n=2000:   49.1% -> 51.9% (+2.8pp, within 47-53% band)
- 1k Modern gauntlet: 65.3% -> 65.5% (+0.2pp, within 64-67% band)

All gates passed cleanly per spec stop conditions. The validation
chain is now `scripts/sleeve_check.py` (goldfish) -> `run_matchup.py`
(single matchup) -> `parallel_launcher.py` (full gauntlet).

---

### no-apl-deck-count-mismatches

**Source:** drift-detect.ps1 run 2026-04-27-1204 surfaced 3 deck-count WARNs
**What was not perfect:** Three Modern deck files (glockulous_modern.txt 58 main,
yawgmoth_modern.txt 58 main, living_end_modern.txt 61 main) had non-60
mainboard counts. Drift-detect flagged as WARN.

**Investigation revealed:** All three were already triaged on 2026-04-25
(see `mtg-sim/data/deck_triage_2026-04-25.md`). Each file has a header
comment marker (`audit:custom_variant`) explaining the diff vs canonical
and the source-attribution rationale for keeping as-is. The triage doc
explicitly chose CUSTOM_VARIANT (preserve) over BUG (replace) for these
three -- replacing would destroy the variant content.

**Why surfaced as WARN despite being triaged:** lint-mtg-sim.py didn't
recognize the audit-marker comments. The `verify_deck_load` audit script
mentioned in deck_triage_2026-04-25.md was already taught to recognize
these markers, but lint-mtg-sim.py is a different tool (the harness
linter, not the in-repo audit) and hadn't been updated.

**Concrete fix:** Added `_deck_is_audit_triaged(path)` helper to
`harness/scripts/lint-mtg-sim.py` that scans the first 10 lines of a
deck file for `audit:intentional` or `audit:custom_variant` markers.
When present, the count check downgrades from WARN to INFO with an
explanatory note pointing at the triage doc. No deck files modified.
**Estimated effort:** 30 min estimated (actual: ~15 min, since the
triage doc had pre-resolved all the canonical-deck-id research)
**Status:** RESOLVED 2026-04-27 (harness file edit, no commit since
harness isn't a git repo; lint-mtg-sim.py change persists on disk)
**Created:** 2026-04-27
**Resolved:** 2026-04-27

**Validation impact:**
- Pre-fix: lint output had 3 WARN entries, drift-detect exit code 1
- Post-fix: lint output has 3 INFO entries, drift-detect exit code 1
  (only stale-ARCHITECTURE.md WARN remains)
- Total findings unchanged at 31; severity downgraded for 3 entries

**Methodology note:** This was the cleaner path than replacing the
deck files. The 2026-04-25 triage explicitly chose to preserve
variant content, and a downstream lint tool was incorrectly
overruling that decision via false-positive WARN. The fix taught
the lint tool about the triage convention rather than going around
it. Anti-pattern would have been wholesale replacing the deck files
based on the WARN, destroying variant work.

---

### orphan-engine-files

**Source finding:** `harness/knowledge/tech/load-bearing-wip-2026-04-26.md`
**What was not perfect:** Two engine files (`engine/card_priority.py`
357 lines, `engine/card_telemetry.py` 261 lines) were untracked in
mtg-sim git AND had no importers in tracked code. Decision needed:
wire up, finish, or delete.

(Third orphan, `engine/oracle_parser.py`, was RESOLVED earlier on
2026-04-27 at commit `4f62331` -- drift-detect surfaced it as
load-bearing for tracked `engine/auto_handlers.py`.)

**Investigation revealed:** Both files together formed a deliberate
research pipeline -- a handler-priority-queue system that ranks
which cards need handlers next based on meta share, telemetry
events (cast/resolve/zone-transition), and effect severity. Five
companion scripts (build_priority_queue, build_meta_shares,
cast_weighted_coverage, summarize_telemetry,
smoke_test_priority_pipeline) also exist as untracked files in
`scripts/`. Real research, not scratch code -- but never wired
into the live simulator (no smoke-test pass on record, no entry
point hook in the sim loop).

**Concrete fix:** Stashed both engine files to
`mtg-sim/engine/_research/` with a comprehensive README documenting:
- What's in each file (card_priority.py and card_telemetry.py public surface)
- What's NOT here (the 5 untracked companion scripts, still in scripts/)
- Why it was moved (research-in-progress, not ready to commit, not safe to delete)
- Revival path (concrete steps to wire it up: 60-90 min cold pickup)
- Lint/drift handling (no changes needed; load-bearing-WIP check still works)
- Convention going forward (`_research/` subdirs under any module for
  similar research-in-progress stashes)

**Estimated effort:** 10 min estimated (actual: ~25 min including
README, IMPERFECTIONS update, RESOLVED entry)
**Status:** RESOLVED 2026-04-27 (filesystem move, no git commit since
files were untracked anyway; new `engine/_research/` is also untracked
until the pipeline gets wired up in a future session)
**Created:** 2026-04-26 (retroactive)
**Resolved:** 2026-04-27

**Validation impact:**
- Pre-fix: `git status` showed 2 orphan engine files at top level
- Post-fix: `git status` shows `engine/_research/` directory (3 files
  including README); top-level `engine/` is clean of orphans
- Drift-detect: load-bearing-WIP check still passes (no tracked imports
  reference _research/ files)
- IMPERFECTIONS open count: 5 -> 2 (orphan-engine, no-apl-deck-count,
  guide-attack-trigger all closed in this session)

**Methodology note:** This was the cleaner path than the binary
"delete vs commit" framing of the original imperfection. Three things
about it worth compounding:

1. **Research-in-progress is a real third option** alongside dead-code
   and ready-to-ship. Stash-rather-than-delete preserves work without
   pretending it's done.
2. **Filesystem location communicates status** -- `_research/` makes
   "not yet wired" explicit at the path level, no need for a status
   comment that goes stale.
3. **The README revival path matters** -- without it, future Claude
   (or future Jermey) opening `_research/` cold has to reverse-engineer
   what the files do and whether they're worth reviving. With it, the
   revival decision is a 10-minute read.

This convention becomes the pattern for future stashes:
`engine/_research/`, `apl/_research/`, `scripts/_research/`, etc.

---

### project-visualization-mvp-d1-gource-renders

**Source spec:** `harness/specs/2026-04-28-d1-gource-renders.md`
**Parent spec:** `harness/specs/2026-04-28-project-visualization-mvp.md`
**What was needed:** Two Gource time-lapse MP4s for `mtg-sim` and
`mtg-meta-analyzer` git repos, plus optional Gephi install for
future time-lapse animation work (~2026-05-12 once daily JSON
snapshots accumulate). D2 (graph-snapshot.py) and D3
(session-snapshot.ps1 integration) had already shipped 2026-04-27
~21:45 via claude.ai; D1 was queued for Claude Code execution.
**Concrete fix:** Pre-execution check found ffmpeg installed,
gource missing. Installed via winget (correct ID `acaudwell.Gource`,
not the spec's guess `Gource.Gource`). Rendered both MP4s with
spec's Gource flags + ffmpeg pipe. Installed Gephi 0.10.1 as bonus
prep. All validation gates passed.
**Estimated effort:** 30-45 min (actual: ~3 min including 2 winget
installs, both MP4 renders ran in parallel with ffmpeg piping in
real-time)
**Status:** RESOLVED 2026-04-27 evening (no commit hash -- harness
docs are flat-file, not git-tracked; spec updates ARE the audit
trail)
**Created:** 2026-04-27 ~22:15 (claude.ai)
**Resolved:** 2026-04-27 evening (Claude Code)

**Validation impact:**
- D1.1: gource-mtg-sim.mp4 14.66 MB / 45.57s ffprobe duration / 47s wall
- D1.2: gource-mtg-meta-analyzer.mp4 7.67 MB / 57.23s duration / 57s wall
- D1.3: Gephi 0.10.1 installed (winget list confirms)
- Gate 1 (file size + duration bands), Gate 2 (same for second mp4),
  Gate 3 (exactly 2 mp4s in directory): all PASSED

**Methodology notes (from amendments A1-A3):**
1. winget package IDs vary in publisher.name format; spec authors
   should `winget search` to confirm canonical ID before drafting
   install steps. `Gource.Gource` was an intuitive guess that
   doesn't match winget's `acaudwell.Gource`.
2. Gource's MSI installer puts files at
   `C:\Users\jerme\AppData\Local\Gource\` and does NOT add itself
   to user PATH. Future invocations need PATH augment OR the
   binary's full path. Worth documenting in
   `harness/knowledge/tech/infrastructure.md`.
3. `gource --help` opens an interactive viewer that blocks waiting
   for keypress in non-tty PowerShell. Skip help-check in
   pre-execution; render commands themselves don't need a tty.

---

## How this file relates to IMPERFECTIONS.md

- `IMPERFECTIONS.md` holds OPEN entries -- known limits not yet fixed
- `RESOLVED.md` (this file) holds entries that have been closed
- Move from IMPERFECTIONS -> RESOLVED when status reaches RESOLVED
  with a commit hash and a brief validation impact summary
- The original IMPERFECTIONS entry can also remain in place with
  status RESOLVED if there's value in having both pointers
  available; the move-vs-leave decision is per-entry judgment

When an entry moves here:
1. Source spec is referenced (so the spec doc stays the canonical
   source of truth for what shipped)
2. Validation results are summarized (so future Claude can see at a
   glance whether the resolution held)
3. Commit hash is locked in (so the resolution can be reverted or
   inspected via git)

---

### oauth-vs-raw-v1-messages-compat-unverified

**Source:** S3.9 T.0 + S4 deferred follow-up.
**Resolved:** 2026-04-28 via 60-second probe (NEGATIVE result).

**What was not perfect:** Unknown whether the Claude Code OAuth token (`sk-ant-oat...`, length 108) at `~/.claude/.credentials.json` would work against raw `https://api.anthropic.com/v1/messages`. If yes, auto-pipeline Claude path absorbs into Claude Max subscription; if no, a separate console API key would be needed.

**Probe procedure:** Loaded token via `apl.auto_apl._get_api_token`, formed a minimal POST to `api.anthropic.com/v1/messages` with `model=claude-haiku-4-5`, `max_tokens=5`, `messages=[{role: user, content: "hi"}]`, Bearer auth header.

**Result:** HTTP 401, body `{"type":"error","error":{"type":"authentication_error","message":"OAuth authentication is currently not supported."},"request_id":"req_011CaXWvnsWaSexHKwTGv5aK"}`.

**Implication:** Claude Max OAuth tokens do NOT work for raw v1/messages. To enable auto-pipeline Claude path, user must obtain a console API key from console.anthropic.com and set `ANTHROPIC_API_KEY` env var. Cost ~$0.05/deck billed to console account. Gemma stays the default for nightly.

**Downstream updates:**
- `gemma-apl-quality-low-for-smoke-gate` IMPERFECTION updated to note option 2 (Claude path) is billable, narrowing cheap-first candidates to options 1, 3, 4.
- HARNESS_STATUS.md auth-path topology section updated.

**No code changes** — resolution is documentation only.

---

### drift-detect-arch-staleness-false-positive-on-non-canonical-runs

**Source:** S1.2 morning sanity-check + every drift-detect run during 2026-04-28 chain.
**Resolved:** 2026-04-28.

**What was not perfect:** `harness/scripts/drift-detect.ps1:Check-StaleArchitecture` flagged ARCHITECTURE.md as stale whenever any `parallel_results_*.json` had a newer mtime, regardless of run size. ARCH baselines anchor on N=100k canonical runs (rare); most parallel_results JSONs are N=1k variant or experimental (frequent), creating a persistent WARN that desensitizes future readers.

**Fix:** Added `[int]$CanonicalNThreshold = 10000` parameter. `Check-StaleArchitecture` now walks `parallel_results_*.json` newest-first, reads `n_per_matchup` from each JSON via `ConvertFrom-Json`, and compares ARCH mtime only against the most recent run with N >= threshold. If no canonical run exists, emits an INFO finding (not WARN) and skips the check.

**Validation:**
- Pre-fix: drift-detect emitted 1 WARN ("ARCH is 1.7h older than parallel_results_20260428_165027.json [N=200]")
- Post-fix: drift-detect emits 0 WARN, message "ARCHITECTURE.md is current vs canonical (N>=10000) baseline" (latest canonical = parallel_results_20260427_083442.json N=100000)
- Edge-case test (`-CanonicalNThreshold 1000000`): SKIP path produces INFO finding "No canonical (N>=1000000) parallel_results files found across 75 candidates"

**No regression** in other drift-detect checks (1/7 through 7/7 all OK after fix).

---

### sim-matchup-matrix-rmw-race + auto-apl-registry-rmw-race-latent + optimization-memory-rmw-race-latent

**Source spec:** `harness/specs/2026-04-28-cache-key-audit-mtg-sim.md` (SHIPPED 2026-04-28 via S5)
**Source finding:** `harness/knowledge/tech/cache-key-audit-2026-04-28.md` Findings 1, 4, 5
**Resolved:** 2026-04-28 (single fix spec covers all 3 entries per IMPERFECTION cross-references).

**What was not perfect:** Three JSON files used the read-modify-write pattern without serialization across 5 call sites:
1. `data/sim_matchup_matrix.json` x 3 sites — concurrent canonical+variant gauntlets could lose per-deck rows
2. `data/auto_apl_registry.json` x 1 site (`auto_pipeline.py:_register_auto_apl`) — latent, no current concurrent caller
3. `harness/agents/optimization_memory.json` x 1 site (`auto_pipeline.py:save_memory`) — latent, no current concurrent caller

**Fix:** New `mtg-sim/engine/atomic_json.py` with two functions:
- `atomic_write_json(path, data)` — tempfile + os.replace for crash safety (no torn writes)
- `atomic_rmw_json(path, mutator, default_factory, ...)` — sentinel-lockfile (`<path>.lock` via `O_CREAT|O_EXCL`) + tempfile + os.replace under lock. Cross-platform (works on Windows where `fcntl.flock` does not). Stale locks (>60s) reclaimed for crash recovery. Spins on contention with exponential backoff capped at 0.5s, up to 30s timeout.

**Sites refactored:**
1. `mtg-sim/generate_matchup_data.py:update_real_matrix` — switched to `atomic_rmw_json`. Bonus: previous code was full-overwrite (silently erased other-deck rows in the matrix). Now correctly RMW-merges, matching the other two matrix-write sites.
2. `mtg-sim/parallel_launcher.py:144` — `atomic_rmw_json`
3. `mtg-sim/parallel_sim.py:217` — `atomic_rmw_json`
4. `harness/agents/scripts/auto_pipeline.py:_register_auto_apl` — `atomic_rmw_json`
5. `harness/agents/scripts/auto_pipeline.py:save_memory` — `atomic_write_json` only (latent; full RMW protection for the `load_memory→mutate→save_memory` triple deferred until a concurrent caller emerges; documented in code comment)

**Validation:** New regression test `mtg-sim/tests/test_atomic_json.py` with 3 cases:
- `test_atomic_write_json_basic` — write/read round-trip
- `test_atomic_rmw_json_sequential_merge` — two updates merge into final state
- `test_atomic_rmw_json_concurrent_writers` — 8 threads x 25 RMW ops = 200 unique entries, all preserved (pre-fix: ~50% loss under same load)
All 3 tests pass; took ~3.3s for the concurrent case (16ms/op under serialization).

**Imports verified:** `generate_matchup_data`, `parallel_launcher`, `parallel_sim`, `auto_pipeline` all import cleanly post-refactor. The harness-side import works because `auto_pipeline.py` already does `sys.path.insert(0, str(SIM_ROOT))`.

**Known residual gap:** `auto_pipeline.py` `load_memory→mutate→save_memory` is still a logical RMW that's only atomic-write-safe at the save step. Currently no concurrent violator (sequential nightly per format). If `auto_pipeline.py --format modern` and `--format standard` ever run concurrently, the memory file write would last-writer-wins. Documented in `save_memory` docstring.
