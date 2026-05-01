# harness/IMPERFECTIONS.md -- Annotated Imperfections Registry

Created: 2026-04-27 Last updated: 2026-04-28

This file is the durable list of "we tried, here's what's left, here's how to fix it next." Every entry is a concrete next-session-implementable spec fragment, NOT a vague TODO.

When a spec ships but doesn't reach 100% on every aspect, the surviving imperfections move from the spec's "Annotated imperfections" section into this file. They stay here until they're fixed, then move to `RESOLVED.md`.

## Format

Each imperfection has:

```
### imperfection-name

Source spec: harness/specs/YYYY-MM-DD-<spec>.md
Source commit: <hash>
What is not perfect: <specific>
Why not fixed in source spec: <reason>
Concrete fix: <next-session implementable steps>
Estimated effort: Status: OPEN | EXECUTING | RESOLVED Created: YYYY-MM-DD
```

## Resolved this week

These have been resolved and moved to `harness/RESOLVED.md`. Listed here for at-a-glance visibility:

- `oauth-vs-raw-v1-messages-compat-unverified` -- RESOLVED 2026-04-29 (re-probe). **CORRECTED: OAuth WORKS.** 2026-04-29 probe returned HTTP 200 with valid completion (model=claude-haiku-4-5-20251001) using `sk-ant-oat01...` OAuth token, no `ANTHROPIC_API_KEY` set. Prior 2026-04-28 finding (HTTP 401 "OAuth authentication is currently not supported") appears to have been a transient Anthropic policy state — policy changed between the two probes. Implication: Claude path in auto-pipeline is free under Claude Max; no console API key required. This unblocks Option 2 in `gemma-apl-quality-low-for-smoke-gate` as a zero-cost fix candidate.
- `drift-detect-arch-staleness-false-positive-on-non-canonical-runs` -- RESOLVED 2026-04-28. `Check-StaleArchitecture` now reads `n_per_matchup` from each `parallel_results_*.json` and only considers runs with N >= `CanonicalNThreshold` (default 10000) as baseline-shifting. Sub-threshold experimental runs (N=200/500/1000) are skipped. Verified clean on current state: drift-detect returns 0 errors / 0 warnings (was 1 WARN every run on the experimental gauntlet from 16:50 today).
- `sim-matchup-matrix-rmw-race` -- RESOLVED 2026-04-28. New `engine/atomic_json.py` provides cross-platform sentinel-lockfile RMW (works on Windows where fcntl.flock does not). Applied at all 3 sites: `generate_matchup_data.py:update_real_matrix` (also corrected from full-overwrite to RMW-merge — was silently erasing other-deck rows), `parallel_launcher.py:144`, `parallel_sim.py:217`. Regression test: `tests/test_atomic_json.py` (8 threads x 25 ops = 200 entries, all preserved).
- `auto-apl-registry-rmw-race-latent` -- RESOLVED 2026-04-28. `_register_auto_apl` now uses `atomic_rmw_json` (same helper / same test).
- `optimization-memory-rmw-race-latent` -- RESOLVED 2026-04-28. `save_memory` now uses `atomic_write_json` (atomic-write only — load_memory/mutate/save_memory triple is still a logical RMW under concurrent callers, but currently sequential; full RMW protection deferred until a concurrent caller emerges).
- `auto-pipeline-output-not-yet-flowing-to-retune` -- RESOLVED 2026-04-28 (spec: 2026-04-28-auto-pipeline-output-flow-to-retune.md). All 5 sub-bullets addressed: APL_REGISTRY auto-registration via sidecar JSON + lookup-time merge in apl/__init__.py; deck-file generation from meta-analyzer DB (most recent top-finish per archetype); quality gate (50-game goldfish smoke; crash-only); APL re-generation dedup via existence + memory check; --top-n CLI arg (default 3 for safety; nightly can pass higher). Auto_apls relocated from data/auto_apls/ to apl/auto_apls/ for normal Python imports. Deck files in decks/auto/ with audit:auto-generated marker; lint orphan-deck check honors marker (37 orphans remain, none of them auto). T.7 live: infrastructure works, but 0/3 of today's Gemma APLs passed smoke gate (API misuse / no class / SyntaxError). Per spec stop-condition for "all smoke fail", shipped infrastructure with documented "no APLs registered today" outcome — wire works for FUTURE archetypes if Gemma quality improves or Claude path verified.
- `auto-pipeline-silent-feature-drift` -- RESOLVED 2026-04-28 (spec: 2026-04-28-auto-pipeline-nightly-integration.md). Layer 5 auto_pipeline.py existed since 2026-04-16 but no automation invoked it; `optimization_memory.json` was never written. Wired into nightly_harness.py as STEP 1.5 behind `--enable-auto-pipeline` flag (default OFF for Friday-safety). Default Gemma path; Claude requires both `--enable-auto-pipeline` AND `--auto-pipeline-use-claude` (two opt-ins to bill console). PowerShell wrapper updated to expose `-EnableAutoPipeline` and `-AutoPipelineUseClaude` switches. T.4 live test wrote optimization_memory.json (3 APLs + 3 playbooks) and 3 Gemma-generated APL files (cutter_affinity.py, jeskai_phelia.py, landless_belcher.py); $0.00 cost. T.5 idempotency check passed (no crash, playbooks short-circuit, APLs re-generate on second run — refinement deferred). Friday's scheduled task command line unchanged; user flips flag manually when ready.
- `stage-1-7-event-bus-determinism` -- RESOLVED 2026-04-28 at commit 30c992a (spec: 2026-04-28-stage-1.7-event-bus-determinism.md). Third mutation source identified: global `random` module state across subprocess invocations consumed by naked `random.foo()` sites in `engine/zones.py:29`, `engine/opponent.py:245`, `engine/race.py:44`, and ~10 sites in `engine/card_handlers_verified.py`. Fix: save/seed/restore the global random state around `run_match_set` (engine/match_runner.py) and `run_bo3_set` (engine/bo3_match.py). Refined validation gate hit cleanly: post-1.7 same-seed re-run produces per-matchup max-dev 0.00pp AND aggregate 0.00pp on both canonical and variant Modern gauntlets at n=1000 (was per-matchup ±2.5pp, aggregate ±0.6pp pre-fix). Resolves Stage C A6. Regression test: `tests/test_determinism.py` (3/3 pass). Unblocks within-matchup parallelism (separate spec).
- `tagger-load-path-unification` -- RESOLVED 2026-04-28 at commit 199d28e (spec: 2026-04-28-tagger-load-path-unification.md). Patch: one-line `tag_keywords(card)` call in `generate_matchup_data.build_deck_from_dict` + import. Stages A/B/C keyword filters now active against all 14 Modern field opps (not just the 11 .txt-loaded). Subset-aggregate canonical: -4.52pp on stub-loaded subset (Izzet Prowess HASTE -8.1pp dominant; Domain Zoo HEXPROOF -2.8pp), -0.51pp on .txt-loaded (control = noise). New baseline canonical 64.5% / variant 78.7%.
- `phase-3.5-stage-a-menace-untested-empirically` -- RESOLVED 2026-04-28 via `tests/test_menace_combat.py` (3 synthetic tests, all pass). Validates Amendment 1 damage accumulation (3/4 menace dies to 2x 2/2), menace 2-blocker requirement (1 blocker -> attacker unblocked), and non-menace single-blocker baseline.
- `phase-3.5-stage-c-re-execution` -- RESOLVED 2026-04-28 at commits 186ee05 + 18257b3 (spec: 2026-04-28-phase-3.5-stage-c-protection-cluster.md). Stage C SHIPPED as verified no-op against current 14-deck Modern field per A5 load-path discovery; latent infrastructure activates once tagger-fix spec lands.
- `past-validation-numbers-audit` -- RESOLVED 2026-04-28 (documentation-only path via JSON recovery; spec: 2026-04-28-past-validation-numbers-audit.md). All Stage A/B numbers verified clean (0.0pp drift); +0.3-0.7pp engine-evolution drift on bonus post-fix re-run, well within ±2pp tolerance.
- `parallel-launcher-cache-collision-fix` -- RESOLVED 2026-04-28 at commit e4fae86 (spec: 2026-04-28-parallel-launcher-cache-collision-fix.md)
- `guide-attack-trigger-double-firing` -- RESOLVED 2026-04-27 at commit cf75e1a (spec: [2026-04-27-guide-attack-trigger-fix.md](http://2026-04-27-guide-attack-trigger-fix.md))
- `oracle-parser-orphan-fix` -- RESOLVED 2026-04-27 at commit 4f62331
- `no-apl-deck-count-mismatches` -- RESOLVED 2026-04-27 ([lint-mtg-sim.py](http://lint-mtg-sim.py) now recognizes audit:custom_variant markers; no deck files changed)
- `orphan-engine-files` -- RESOLVED 2026-04-27 (card_priority.py + card_telemetry.py stashed to engine/\_research/ with revival README)

## Open imperfections

### gemma-apl-quality-low-for-smoke-gate (NEW 2026-04-28; surfaced by S4 T.7; updated 2026-04-28 post-OAuth-probe)

**Source spec:** `harness/specs/2026-04-28-auto-pipeline-output-flow-to-retune.md` (SHIPPED 2026-04-28)
**What's not perfect:** Gemma's APL generation produces code that fails the 50-game smoke gate. Today's measurement: 3/3 failures across Landless Belcher (API misuse: calling `gs.get(...)` which doesn't exist on GameState), Cutter Affinity (no class with name ending in "APL" defined), Jeskai Phelia (SyntaxError at line 137). The output-flow infrastructure works; nothing reaches the auto registry because every smoke fails. **Update 2026-04-28:** Claude path (option 2) previously recorded as billable (HTTP 401 on OAuth probe). **Update 2026-04-29 CORRECTION:** Re-probe returned HTTP 200 — OAuth tokens now work against raw v1/messages. Claude path is FREE under Claude Max. Option 2 (Claude via `--auto-pipeline-use-claude`) is now the cheapest high-ROI fix alongside Option 4 (ICL examples). No console key needed.
**Why not fixed in source spec:** S4's scope was wiring the output flow, not improving Gemma quality. Per spec stop-condition for "all smoke fail," shipped the infrastructure with documented outcome.
**Concrete fix candidates (pick one or combine):**
1. Improve Gemma prompt — add more explicit GameState API documentation, examples from existing APLs, post-validation step (Gemma re-checks its own output against API). Low cost, uncertain payoff.
2. Try Claude path (via `--enable-auto-pipeline --auto-pipeline-use-claude`) — REQUIRES separate console API key (NOT Claude Max OAuth; verified 2026-04-28 via probe: HTTP 401 "OAuth authentication is currently not supported"). User must obtain console API key from console.anthropic.com and set `ANTHROPIC_API_KEY` env var; ~$0.05/deck billed there.
3. Auto-fix common errors post-generation — strip `.get()` calls, add missing class definitions, ast.parse retry loop. Mechanical, but specific.
4. Use a few existing canonical APLs as ICL examples in the Gemma prompt. Cheap, likely best ROI.
**Estimated effort:** 30-60 min for option 1 (prompt iteration + measure pass rate).
**Update 2026-04-29 (spec execution):** ICL exemplar + API reference + class-name rule + ast.parse retry loop added to prompt. Re-ran 3 archetypes: all 3 now produce syntactically valid APLs with correct class-name suffix and correct method signatures (was 0/3 structural). Smoke gate still fails with "No deck file found" — deck-file infrastructure gap, not APL quality. Structural root causes RESOLVED. Remaining blocker: deck file must exist before smoke can execute.
**Update 2026-04-30 (Option C execution):** Root cause of hallucinated card names identified — `_get_decklist_from_db` was calling `db_bridge.load_saved_deck` which fails silently for all archetypes; prompt always ran with "No decklist available." Fixed by replacing with direct SQL query to `mtg_meta.db`. Refactored to backend-agnostic `_build_apl_prompt` + `_generate_via_claude_v2` (same prompt, Claude Sonnet via OAuth, 60s rate-limit retry). Semantic gate added to `_smoke_test_apl`: win_rate >= 10% AND avg_kill_turn in [3, 20]. Re-ran 3 test archetypes: Cutter Affinity PASS (60% WR, T11.5), Jeskai Phelia PASS (98% WR, T7.2), Landless Belcher FAIL (0% WR — combo deck, Belcher activation not modelable by APL). 2/3 registered. Landless Belcher failure is structural (engine can't model activated-ability kill) not APL quality — expected, documented separately. Gemma fallback now includes real decklists (65-94% card name hit rate vs 0% before). 4 additional PT-watch Standard archetypes generated.
**Status:** PARTIALLY RESOLVED — 2/3 test archetypes registered; combo-kill decks remain unsupported at APL level
**Created:** 2026-04-28

### mulligan-logic-portfolio-gap (NEW 2026-04-28; surfaced by user note + cross-APL audit)

**Source:** User observation 2026-04-28 ("boros energy is the only APL that feels close to right; mulligan logic could be better"). Cross-APL audit at `harness/knowledge/tech/mulligan-audit-2026-04-28.md`.
**What's not perfect:** 16 of 52 primary APLs (31%) have inadequate keep() logic — 9 SHIMs falling back to `apl/mulligan.py:generic_keep` (pure land count) and 7 SHALLOW (1-3 ifs, no named-card awareness). **CORRECTION 2026-04-28 post-investigation:** initial claim that this skews canonical 64.5%/78.8% baseline was WRONG — canonical gauntlets use `MATCH_APL_REGISTRY` (matchup-aware variants `apl/<deck>_match.py`), NOT the goldfish APLs audited. So Jeskai Blink/Temur Breach/Esper Blink SHIM/SHALLOW classifications affect goldfish-only diagnostic flows (sim.py + apl_tuner.py), not canonical. Match APL inventory needs a separate audit before this IMPERFECTION can claim canonical impact. Additionally, all 4 role-base classes (`aggro_base`, `combo_base`, `control_base`, `ramp_base`) accept `on_play` parameter but never branch on it — play-vs-draw distinction is silently lost (this part still applies to whichever APLs use the role bases). Combo decks lack must-have-card logic. Also surfaced during investigation: **`sim.py:50` is hardcoded to `HumansAPL()` regardless of `--deck` arg** — separate bug, makes sim.py misleading for any deck except Humans.
**Why not fixed:** Most SHIMs are documented Stage A 2026-04-26 triage outputs ("registered for gauntlet coverage, hand-tune later"). Framework-wide fix wasn't yet specced because the role-base parameterization was already on disk and the gap wasn't quantified until today's audit.
**Concrete fix:** Three-phase spec.
1. Universal framework (3-4 hrs): add play-vs-draw branch + `MUST_HAVE_FROM` to role bases; migrate 9 SHIMs to role bases with card-set declarations; audit 10 NO_KEEP APLs' card sets; audit 7 SHALLOW APLs.
2. Bo3 sideboarded keep (1-2 hrs): add `MULL_POST_BOARD_*` thresholds; thread through `take_opening_hand`.
3. A/B measurement (1 hr per affected deck): goldfish before/after each migration; document deltas.
**Estimated effort:** 5-8 hrs framework work + batched A/B in nightly.
**Tonight's partial:** tuning Jeskai Blink directly captures a SHIM-to-real-keep migration as a worked example; observations inform the framework spec.
**Status:** OPEN
**Created:** 2026-04-28

### card-specs-tier-2-extraction-pending (RESOLVED -- all 4 files exist with complete content + exported in __init__.py; goldfish APL imports QR + Teferi; imperfection was already resolved by fdbf153)

**Source spec:** `harness/specs/2026-04-29-card-specs-framework.md` (POC SHIPPED 2026-04-29)
**Source finding:** `harness/knowledge/tech/jeskai-blink-card-specs-2026-04-28.md`
**What's not perfect:** Phase 3 of card_specs framework only extracted Tier 1 cards (Phlage, Ragavan, Phelia, Ephemerate). Tier 2 cards (Quantum Riddler, Teferi Time Raveler, Consign to Memory, Wrath of the Skies) are still inlined in `apl/jeskai_blink.py` and `apl/jeskai_blink_match.py`. Reuse footprint: Quantum (JB+UWB), Teferi TR (JB+UWB+EsperBlink), Consign (JB+UWB+EsperBlink), Wrath (JB+Boros sideboard). Tier 3 (Casey Jones, Fable, Prismatic, March) is deck-specific enough that staying inline is fine.
**Why not fixed in source spec:** POC scope was limited to ADDITIVE Phlage + 3 friends (Ragavan, Phelia, Ephemerate) for shape validation. Tier 2 batch deferred to keep POC scope manageable.
**Concrete fix:** ~60-90 min to extract 4 Tier 2 cards into `apl/card_specs/quantum_riddler.py`, `teferi_time_raveler.py`, `consign_to_memory.py`, `wrath_of_the_skies.py`. Each follows the Phlage template: NAME constant + cast/special-action functions + opponent-aware skips.
**Estimated effort:** 60-90 min.
**Status:** OPEN
**Created:** 2026-04-29

### card-specs-phase-b-migration-pending (NEW 2026-04-29; from card_specs POC)

**Source spec:** `harness/specs/2026-04-29-card-specs-framework.md` (POC SHIPPED 2026-04-29; full spec PROPOSED)
**What's not perfect:** Phase B migration of existing APLs (`apl/boros_energy.py`, `apl/jeskai_blink_match.py`, `apl/uw_blink.py`/`uw_blink_match.py`, `apl/esper_blink.py`/`esper_blink_match.py`) to call `apl/card_specs/` is NOT done. POC was deliberately ADDITIVE — current APLs still have inline Phlage/Galvanic/Phelia/Solitude/Ephemerate logic duplicated across 4-5 files. Migration would dedup ~70% of nonland card logic but requires bit-stable canonical gauntlet validation (Boros Energy is locked at canonical 64.5%/78.8% baseline; touching its inline Phlage code risks shifting that number). Until migration, every Phlage rules update has to be applied in 3+ places.
**Why not fixed in POC:** Scope discipline — POC's value is shape-validation + Jeskai Blink goldfish. Migration is its own spec (Phase B in 2026-04-29-card-specs-framework.md).
**Concrete fix:** Per Phase B steps (~120-180 min total): refactor each APL site to import `card_specs.<card>` and call its functions in place of inline blocks. After each APL migration, run `parallel_launcher.py --deck "<APL>" --format modern --n 1000 --seed 42` pre/post and verify bit-identical (or <0.1pp deviation). Stop trigger >0.5pp deviation per matchup.
**Estimated effort:** 120-180 min for full migration. Blocks on a focused session with bit-stable gauntlet capture.
**Status:** OPEN
**Created:** 2026-04-29

### card-specs-phlage-engine-no-sacrifice-quirk (NEW 2026-04-29; surfaced during POC)

**Source:** `engine/card_handlers_verified.py:_phlage_titan_etb` (line 26044) explicit comment.
**What's not perfect:** Engine's Phlage handler models the ETB damage + life gain but explicitly does NOT model the sacrifice-unless-escaped clause. So a Phlage cast normally STAYS on the battlefield as a 6/6 forever (rather than being sacrificed per oracle text). This is a known engine simplification ("attack trigger not wired" comment), and changing it would shift the canonical baseline (Boros Energy + Jeskai Blink + Amulet Titan all run Phlage; their 6/6-stays-on-board behavior is in the locked numbers). Until engine catches up, card_specs/phlage.py:hardcast just calls gs.cast_spell (lets engine handle ETB) and does NOT manually sacrifice — that path was tested and made the goldfish 1 turn slower (T6.43 vs T7.51).
**Why not fixed:** Mid-engine refactor would touch every deck. Should be folded into a future engine-model-fidelity spec.
**Concrete fix candidates:**
1. Add Phlage sacrifice clause to `_phlage_titan_etb`. Side effect: Phlage no longer a 6/6 attacker; goldfish kill turn likely worsens for Boros Energy + Jeskai Blink. Canonical baseline shifts. Requires re-baseline.
2. Leave engine as-is; document that "Phlage 6/6 stays" is a known model gap. Card_specs already accommodates this.
3. Flag at engine level via card.persistent flag, with sacrifice-aware path conditional on flag. Slower path for goldfish, faster path for matchup.
**Estimated effort:** 30 min for option 2 (documentation only). 60-120 min for option 1 (engine change + re-baseline). Defer until engine-model-fidelity is a focus area.
**Status:** OPEN
**Created:** 2026-04-29

### canonical-field-missing-match-apl-entries (NEW 2026-04-29; investigated + Jeskai Blink fixed in same session)

**Source:** `harness/knowledge/tech/match-apl-mulligan-audit-2026-04-29.md`; investigation traced apl/__init__.py:get_match_apl + tested resolution against all 15 canonical Modern field decks.

**Investigation finding:** `get_match_apl()` falls back to `GoldfishAdapter(get_apl(deck))` when MATCH_APL_REGISTRY misses. So no canonical matchup is silently skipped — but the *quality* of the opponent APL drops to whatever the goldfish APL provides. Resolution table:

| Canonical deck | Field % | Resolves to | Quality |
|---|---|---|---|
| Jeskai Blink | 6.4 | ~~GoldfishAdapter(JeskaiBlinkAPL 24L SHIM)~~ -> JeskaiBlinkMatchAPL (595L tuned) | **FIXED 2026-04-29** via 1-line registry add (`"jeskaiblink"` alias added to MATCH_APL_REGISTRY pointing at `apl.jeskai_blink_match.JeskaiBlinkMatchAPL`) |
| Grinding Breach | 6.4 | GoldfishAdapter(GrindingBreachAPL 93L tuned) | mid-tier; decent goldfish but match APL would be better |
| Orzhov Blink | 6.1 | GoldfishAdapter(EsperBlinkAPL) | wrong deck routed (apl/__init__.py:91 has `"orzhovblink"` -> EsperBlinkAPL with comment "orzhov_blink_modern.txt is misnamed"). Effectively double-counts Esper Blink in the canonical field. |
| Temur Breach | 3.8 | GoldfishAdapter(TemurBreachAPL 26L SHIM) | **TERRIBLE** — pure GenericAPL midrange shim; this 3.8% slice is being measured against generic "play biggest creature" play. |

**Net:** Jeskai Blink's 6.4% canonical share is now correctly using the tuned 595L match APL. Spec #8 (100k re-validation) tomorrow will measure the new baseline; expect a non-trivial shift since Phelia attack-blink + Phlage escape + Solitude evoke chains are now live as opponent plays for that 6.4% slice (vs prior "GenericAPL midrange" goldfish play).

**Why not fully fixed:** 3 remaining (Grinding Breach, Orzhov Blink, Temur Breach) need either match APL authoring or registry routing decisions. Temur Breach 3.8% on SHIM is the highest-impact remaining gap.

**Concrete fix candidates (remaining 3):**
1. Author Temur Breach match APL (~60-90 min). Highest impact.
2. Investigate Orzhov Blink deck file — is it actually Esper Blink as the comment says, or genuine Orzhov? If genuine, author Orzhov-specific match APL. If Esper-mislabeled, remove from canonical field (avoids double-count).
3. Grinding Breach: 93L goldfish is decent; could author match APL or alias to existing goryos_match (both reanimator-flavored). 30 min.
**Status:** PARTIALLY RESOLVED (1 of 4 decks fixed); 3 remaining
**Created:** 2026-04-29
**Updated:** 2026-04-29 with investigation results + Jeskai Blink fix

### engine-fidelity-gaps-has-keyword-attribute-mismatch (RESOLVED 2026-04-29 at b4384dc)

**Source:** Phase A background agent's Solitude lifelink probe; doc at `harness/knowledge/tech/has-keyword-broken-2026-04-29.md`.
**What's not perfect:** `engine/match_state.py:has_keyword(card, kw)` checks `card.keywords` — an attribute that does NOT exist on the Card dataclass. The function always returns False. Affects ALL keyword checks routed through this path: lifelink, deathtouch, flying, vigilance, first-strike, etc., wherever they're queried via `has_keyword` instead of `KWTag.X in card.tags`.

**Affected callers (per agent probe):**
- `engine.match_engine.run_match`
- `engine.bo3_match`
- `engine.meta_solver`
- `engine.parallel_match`
- `engine.combo_model`
- `engine.variant`

**NOT affected:** `engine.match_runner.run_match_set` (used by `run_matchup.py`) — directly checks `KWTag.X in card.tags` (correct path). So canonical gauntlets via parallel_launcher likely use the working path; some derivative tools use the broken one.

**Why not fixed in Phase A:** Out of scope for Phase A (APL-only). Engine-level change. Defer to Phase C.
**Concrete fix:** Replace `card.keywords` lookup in `has_keyword` with `card.tags` (the attribute actually populated by `tag_keywords()` at deck load). Preserve oracle-text fallback for cards loaded outside the tag pass. ~5-line edit.
**Estimated effort:** 30 min (5-line fix + bit-stable validation across the 6 affected callers, since they may all be silently miscomputing combat outcomes).
**Severity:** HIGH (silently wrong combat results in 6+ engine paths).
**Status:** OPEN
**Created:** 2026-04-29

### cross-canonical-apl-shared-card-bug-pattern (NEW 2026-04-29; partially resolved 2026-04-29)

**Source:** `harness/knowledge/tech/boros-energy-vs-jb-apl-maturity-2026-04-29.md` + opportunistic grep of canonical match APLs while background agent worked Phase A.
**What's not perfect:** The 12 oracle-bugs surfaced in `apl/jeskai_blink_match.py` tonight (Solitude white-pitch, Ephemerate {W} payment, Phelia counter application, Phelia exile end-step return, etc.) follow patterns that are likely present in **other less-mature canonical match APLs**. Specifically:

1. **Goryo's Vengeance match APL (canonical 5.6%, 248L)**: line 101 `white_cards = [x for x in gs.zones.hand if x != c and not x.is_land()]` — same Solitude evoke white-pitch bug as JB pre-ce492dc (no `'W' in colors` filter). Line 213-219 Solitude blink is missing the `opponent.life += safe_power(t)` lifegain-to-opponent oracle clause that JB has. Casey Jones / Phelia / Ephemerate not present (different deck) but Solitude + Ephemerate combo IS used.

2. **UW Blink match APL (123L, fringe)**: stub-quality auto-generated; doesn't model Phelia/Solitude/Ephemerate plays at all. Major coverage gap (the actual Phelia+Solitude+Ephemerate engine of UW Blink isn't modeled).

3. **Esper Blink match APL (215L, canonical 2.8%)**: HAS at least 1 white-filter check (so partial protection vs the bug class). Worth full audit to confirm coverage.

4. **Domain Zoo (canonical 5.0%, 395L)**: 8 Phlage refs but no shared blink-engine cards. Could have Phlage hardcast bugs similar to JB (need oracle audit).

The pattern: **maturity correlates with oracle fidelity**. Boros Energy (1115L, 22.1%) has explicit APL-level compensation for engine gaps (Phlage sacrifice, Arena exert+haste). JB (~600L) had less coverage and yielded ~12 bugs in one session of audit. APLs in the 200-400L range likely have proportionally similar bug counts waiting.

**Why not fixed:** All canonical-baseline-affecting; needs per-APL bit-stable validation per fix; deferred from tonight's session.

**Concrete fix candidates:**
1. Run the same JB-style oracle audit on Goryo's, Domain Zoo, Eldrazi Ramp, Eldrazi Tron, Murktide, Izzet Affinity, Esper Blink, UW Blink. Each is 2-4 hrs of careful work. Each likely yields 3-12 bug commits.
2. **Apply the `oracle-text-verify-before-touching-card-mechanics` methodology lesson** (spec-authoring-lessons.md v1.6) for every commit — quote oracle text in commit body.
3. Bit-stable canonical gauntlet validation per APL per commit; surface deviations >5pp.

**Estimated effort:** 16-32 hours total across all canonical match APLs. Compounding ROI: each fix improves canonical opponent quality, which makes the 64.5%/78.8% baseline more accurate.

**Status:** OPEN
**Created:** 2026-04-29

### engine-fidelity-gaps-warp-mechanic-not-modeled (NEW 2026-04-29 session-late; surfaced by user advanced-play teaching)

**Source:** User feedback identifying advanced JB plays the APL doesn't make: warp Quantum Riddler + Consign the end-step return trigger, warp Quantum + Ephemerate breaks the delayed trigger linkage, T4 Arena-of-Glory-haste Phlage hardcast + Consign sacrifice trigger.
**What's not perfect:** **Warp is a real alternate-cost mechanic that the engine has zero infrastructure for.** Cards' oracle text in `data/rules_reference/scryfall_oracle_cards.json` includes `Warp {X}{Y}` lines (e.g., Quantum Riddler `Warp {1}{U}`, Nova Hellkite `Warp {2}{R}`), but:
- No `KWTag.WARP` in `engine/keywords.py`
- No alternate-cost path in `gs.cast_spell()` to pay warp cost instead of mana cost
- No tracking of "warped" creatures (need state to know which permanents have a return-to-hand delayed trigger pending)
- No end-step delayed trigger framework that returns warped creatures
- Counterability of the return trigger via Consign-style "counter triggered ability" not modeled
- Blink-breaks-warp-linkage interaction (Ephemerate makes the warped creature a "new object" with no return trigger) not modeled

**Scope of impact:** **6 of 15 canonical Modern field decks (~28% combined field share)** run Warp cards:
- Jeskai Blink (6.4%): 4× Quantum Riddler
- Izzet Affinity (6.8%): 4× Pinnacle Emissary
- Goryo's Vengeance (5.6%): 4× Quantum Riddler
- Esper Blink (2.8%): 4× Quantum Riddler
- UW Blink (fringe): 3× Starfield Shepherd + 3× Quantum Riddler
- Orzhov Blink (6.1% phantom of Esper): 4× Quantum Riddler

26 total Warp-card copies across canonical. All currently cast at full mana cost on T5+ instead of T2 via Warp. This is a HUGE quality drop in canonical opponent play — makes 28% of the field measurably slower than reality.

**Why not fixed:** Engine-level mechanic add. Needs:
1. Parse Warp cost from oracle text into `card.warp_cost` attribute
2. Add WARP cast path in `gs.cast_spell` (alternate cost)
3. Add `gs.warped_permanents` tracker
4. Add end-step delayed trigger framework (or specific WARP_RETURN trigger)
5. Make Consign-style counters apply to the return trigger
6. Make blink break the warped state (Ephemerate / Phelia)

**Estimated effort:** 3-4 hours engine + per-deck APL update + bit-stable validation per affected APL. Probably a 2-day spec given the scope.
**Status:** OPEN
**Created:** 2026-04-29

### engine-fidelity-gaps-jeskai-blink-cards (NEW 2026-04-29; surfaced by 8-combo audit)

**Source:** Per-card 2-card-combo audit during late 2026-04-29 night session.
**What's not perfect:** Three Jeskai Blink card mechanics that need engine-level work (the match APL can't model these in isolation):

1. **Fable of the Mirror-Breaker chapters II + III not wired.** `engine/sagas.py:SAGA_EFFECTS` only has Kumano + Roku entries. Fable's `_fable_mirror_breaker_etb` at `card_handlers_verified.py:8401` fires "Chapter I" (creates Goblin Shaman 2/2 token) on cast — note: oracle Chapter I is actually loot, oracle Chapter II is the Goblin token, so the engine is also chapter-mislabeled. Chapter III (transform to Reflection of Kiki-Jiki, tap-to-copy nonlegendary creature) is fully unmodeled. Quantum Riddler (likely non-legendary) could be copied for 2× 4/6 flying + double draw — never happens.

2. **Goblin Shaman token from Fable lacks "treasure on attack" trigger.** `_make_token("Goblin Shaman", "2", "2", "Token Creature — Goblin Shaman")` creates a vanilla 2/2 with no abilities. Oracle: "When this creature attacks, create a Treasure token." JB loses real ramp (each Goblin attack = +1 mana next turn, accelerates Quantum / Solitude hardcast).

3. **Arena of Glory haste grant not wired.** `_arena_of_glory_etb` at `card_handlers_verified.py:17322` just logs `"Arena of Glory: mass haste"` with no actual haste-granting logic. Oracle: `{R}{R}{R}, {T}, Sacrifice: Creatures you cast this turn gain haste until end of turn.` Ragavan T1 cast still summoning-sick → no T1 attack → no T1 treasure. Major loss for Boros Energy + Jeskai Blink that both run Arena.

**Why not fixed:** Engine-level changes shift canonical baselines for every deck running these cards (Boros Energy + Jeskai Blink for Arena/Fable, JB only for Goblin token). Should be a deliberate engine-fidelity spec with bit-stable validation per affected APL.
**Concrete fix candidates:**
1. Wire Fable chapters II + III into engine/sagas.py SAGA_EFFECTS. Chapter II = make Goblin Shaman 2/2 token (already done at ETB but needs to MOVE there). Chapter III = transform mechanic (gs.transform pattern from Kumano/Roku) + add tap-to-copy ability (or shim it as "tap for free 4/6 flying" if Quantum is on board). 60-90 min.
2. Add treasure-on-attack trigger to Goblin Shaman token via combat-damage hook (engine-level, may need infra). 30-45 min.
3. Wire Arena of Glory haste-grant via a per-turn flag on cast. Activated ability tracking. 30-45 min.
**Estimated effort:** 2-3 hours for full engine pass. Each is bit-stable-test-required.
**Status:** OPEN
**Created:** 2026-04-29

### duplicate-deck-files-in-canonical-field (RESOLVED 2026-04-29 at 74b4f33)

**Source:** SHA-256 scan of `decks/*_modern.txt` (see `harness/knowledge/tech/canonical-field-integrity-2026-04-29.md`).
**What's not perfect:** Two pairs of canonical Modern decklist files are bit-identical:
- `decks/esper_blink_modern.txt` ≡ `decks/orzhov_blink_modern.txt` (both contain "Esper Blink - botje_" by header)
- `decks/grinding_breach_modern.txt` ≡ `decks/temur_breach_modern.txt` (both contain "Teg - Arets77" — Temur Breach storm-ritual deck)

Combined, this is **12.5pp of phantom canonical field share** (Orzhov Blink 6.1% + Grinding Breach 6.4%). The "field" double-counts Esper Blink and Temur Breach under different names. Plus the Grinding Breach APL expects Underworld Breach + Grinding Station combo cards that are NOT in the file (it's actually Teg storm-ritual cards), so the canonical 6.4% "Grinding Breach" slice plays an APL fundamentally mismatched to its card pool.

**Net baseline integrity impact:** 25.5% of total canonical field share (12.5% phantom + 6.4% APL mismatch + 6.4% Jeskai Blink misroute already fixed today) was being measured incorrectly. Current 64.5%/78.8% locked baseline reflects this distorted measurement.

**Why not fixed:** Canonical-shifting fix; should be done as a deliberate spec with bit-stable validation gate. Spec #8 (100k re-validation) tomorrow is the right venue; baseline shift IS the measurement.

**Concrete fix candidates:**
1. Remove `"Orzhov Blink"` and `"Grinding Breach"` from `format_config.py:31-39` Modern field (drops the field from 100% to 87.5% weight; renormalize or accept). Cleanest data integrity fix. ~10 min.
2. Source actual Orzhov Blink + Grinding Breach decklists from MTGTop8/MTGGoldfish, replace the duplicate files. Restores intended field diversity. Needs human input on which lists to source. ~30-60 min.
3. Combination: source real Grinding Breach (it's a real Modern archetype with hand-tuned APL waiting); remove Orzhov Blink (it's effectively a duplicate of Esper Blink with no separate identity in the repo).
**Estimated effort:** 10 min for fix 1; 30-60 min for fix 2.
**Status:** OPEN
**Created:** 2026-04-29

---

## Structural architectural gaps (from strategic assessment 2026-04-30)

These are not spec-derived imperfections — they are architectural limits of the current engine that APL tuning cannot fix. They set the ceiling on which matchups the sim can give reliable WR numbers for. Tracked here so future sessions don't waste time tuning APLs in these areas before the engine is ready.

---

### sim-no-stack-priority (STRUCTURAL — affects ~40% of competitive matchups)

**Source:** Strategic assessment 2026-04-30; `harness/ROADMAP.md` Phase 3
**What's not perfect:** Counterspells in the sim are declarative mana reservations, not actual gameplay interventions. `engine/stack.py` exists with `InteractionType.COUNTER` but is NOT wired into the two-player match runner. `_simple_play_turn` and `_run_player_turn` call APLs but have no mechanism for reactive counterspell interruption. A spell cast into open mana always resolves. The control player can never counter a key spell at the right moment. WR numbers for any matchup involving meaningful permission are wrong in a structured way — not noisy, directionally incorrect.
**Why not fixed:** Requires wiring a priority pass loop into the match runner. Scope is 2–3 weeks. Every existing APL would need a "do I want to counter this?" decision point added.
**Concrete fix:** Wire `engine/stack.py` into `_run_player_turn`. Before each spell resolves: check if opponent APL has open mana + counterspell in hand; if yes, call `apl.want_to_counter(spell, gs, opp)` (new method on MatchAPL base class with default `return False`). Start with `apl/uw_control.py` + `apl/jeskai_control.py` as the first two callers; all other APLs inherit default `False`. This makes the system correct for the most important cases immediately without requiring all 38 APLs to implement the method upfront.
**Affected matchups:** UW Control, Jeskai Control, Jeskai Blink, Amulet Titan (post-board Pact), any modern matchup where one player holds up interaction. Roughly 40% of competitive Modern field.
**Estimated effort:** 2–3 weeks (engine wiring + control APL implementation + bit-stable re-baseline for all affected matchups).
**Status:** OPEN
**Created:** 2026-04-30

---

### sim-no-hidden-information (STRUCTURAL — affects all decision quality)

**Source:** Strategic assessment 2026-04-30; `harness/ROADMAP.md` Phase 3
**What's not perfect:** `TwoPlayerGameState` exposes `hand_a` and `hand_b` as public lists. APLs receive `opp_view` with full `zones.hand` visibility (`engine/match_runner.py` lines 409, 416). Both players play with perfect information. This means:
- APLs can sequence plays to avoid known counters in opponent's hand — real players can't
- APLs can decide to race vs stabilize based on knowing whether opponent has removal — real players make probabilistic reads
- Win rates systematically favor the "correct" line in a way that isn't achievable in real play
The consequence is a model of "perfect play under full information," not "skilled play under normal information." WR numbers are correct for the model but overestimate how much better strategy matters in practice.
**Why not fixed:** Requires an information-hiding layer over `TwoPlayerGameState`. APLs would need to work from a filtered `opp_view` that only shows cards revealed through play (cards they've played, discarded, or you've seen). Architecturally significant change.
**Concrete fix:** Add `revealed_to_opponent: set` attribute to player state. Build `_opp_view(gs)` that returns a filtered game state where `opp.zones.hand` only contains cards in `revealed_to_opponent`. Pass filtered view to APL decision methods. Gradual migration: start with `want_to_counter` and `_use_removal_sparingly` as the first callers that benefit from information restriction.
**Estimated effort:** 2–3 weeks (architecture + APL migration + re-baseline).
**Status:** OPEN
**Created:** 2026-04-30

---

### sim-no-instant-speed-combat (STRUCTURAL — affects combat trick and pump modeling)

**Source:** Strategic assessment 2026-04-30; `harness/ROADMAP.md` Phase 3
**What's not perfect:** `_resolve_combat` in `engine/match_runner.py` is fully synchronous. It calculates blockers, assigns damage, and resolves lethal in one pass with no opportunity for either player to respond. Consequences:
- Opponent cannot kill your attacker in response to combat (instant-speed removal at instant speed)
- You cannot pump your attacker/blocker (Giant Growth, Mutagenic Growth outside of specific coded paths)
- First-strike damage and second-strike damage are both calculated in one pass
- "Holding back a blocker because opponent might have a trick" is not a concept the sim has
- "Attacking into possible chump + trick" lines are never considered
The current Mutagenic Growth implementation is a special-case carve-out in burst turns, not a general instant-speed system.
**Why not fixed:** Requires a proper priority system during the combat phase (declare-attackers window, declare-blockers window, combat-damage-assignment window). Architecturally coupled to sim-no-stack-priority above — both need a priority pass framework.
**Concrete fix:** Build `CombatPhase` as a stepped process with explicit priority windows: (1) declare attackers + immediate ETB/trigger window, (2) declare blockers + priority window for instant-speed interaction, (3) combat damage + priority window. Fold existing Mutagenic Growth burst-turn code into the general instant-speed system. Best done as a single spec alongside sim-no-stack-priority since both need the same priority-pass infrastructure.
**Estimated effort:** Part of the 2–3 week stack/priority project (harness/ROADMAP.md Phase 3).
**Status:** OPEN
**Created:** 2026-04-30

---

## APL quality gaps (from external research 2026-04-30)

Three new imperfections surfaced by deep research into Nettle MTG AI series and mtg-agents.com.
These are design gaps, not bugs — the code works but the quality ceiling is lower than it needs to be.

---

### mulligan-threshold-not-empirically-validated (NEW 2026-04-30)

**Source:** Chris Nettle Part 3 + `harness/knowledge/tech/external-research-mtg-ai-2026-04-30.md`; `harness/specs/2026-04-30-mulligan-parameter-sweep.md`
**What's not perfect:** No APL's keep() threshold has been validated through large-N simulation parameter sweep. Current thresholds are author intuition. Nettle's external study (1M games, 7 strategies) showed the optimal aggro threshold is 2 lands + 1 creature + max 2 mulligans (2-1-2). The mtg-sim APLs have not been calibrated to this or any other empirically-derived baseline. APLs currently running `len(lands) >= 2` without creature/threat checks are systematically keeping floods and removal-heavy hands that lose more games than they should.
**Affected APLs:** All 16 SHIM/SHALLOW APLs in `mulligan-logic-portfolio-gap` + potentially others with threshold author-intuition
**Why not fixed:** The parameter sweep infrastructure doesn't exist yet; building it is the fix.
**Concrete fix:** Build `scripts/mulligan_sweep.py` per `harness/specs/2026-04-30-mulligan-parameter-sweep.md`. Run 50k-game sweep across (min_lands, min_creatures, max_mulligans) parameter space per deck archetype. Apply optimal thresholds to affected APLs.
**Estimated effort:** 90 min scripting + 2-4 hours compute + 30 min APL updates.
**Status:** OPEN
**Created:** 2026-04-30

---

### no-llm-as-judge-apl-evaluation (NEW 2026-04-30)

**Source:** mtg-agents.com evaluation methodology + `harness/knowledge/tech/external-research-mtg-ai-2026-04-30.md`; `harness/specs/2026-04-30-llm-as-judge-apl-evaluation.md`
**What's not perfect:** APL quality is evaluated exclusively by sim WR% and oracle-verify (code-level correctness check). There is no test for whether APLs make strategically correct decisions given a board state. An APL can pass oracle-verify and achieve acceptable WR while: (a) systematically attacking into unfavorable blocks, (b) holding removal when the playbook says to use it, (c) keeping opening hands that lose to specific opponent openers. The mtg-agents.com evaluation paper found that LLM-as-judge with a 45-question ground-truth test set catches decision-level errors that WR% misses — and that calibrating the judge prompt against human evaluation is critical before trusting scores.
**Why not fixed:** No question set exists; no judge infrastructure exists. The oracle-verify script addresses code correctness, not decision correctness.
**Concrete fix:** Build `harness/scripts/apl_judge.py` + 30-question test set per `harness/specs/2026-04-30-llm-as-judge-apl-evaluation.md`. Three question types: oracle fidelity, strategic decisions, keep/mulligan. Gemma 12B judge calibrated on known-correct/incorrect examples. Reference score: Boros Energy >85%.
**Estimated effort:** 90-120 min.
**Status:** OPEN
**Created:** 2026-04-30

---

### card-search-no-attribute-filter (NEW 2026-04-30)

**Source:** Karn (mtg-agents.com) hybrid vector search pattern + `harness/knowledge/tech/external-research-mtg-ai-2026-04-30.md`
**What's not perfect:** `analysis/card_embeddings.py:find_similar_cards()` returns pure semantic embedding matches with no hard attribute filtering. Queries like "cheap interaction for Modern" return format-illegal cards, wrong card types (legendary creatures returned for an instant slot), and cards with incorrect CMC. The SB optimizer (ROADMAP Phase 4) requires attribute-filtered search to function — recommending format-illegal SB cards is worse than useless. The slot analysis and card recommendation features have the same problem.
**Why not fixed:** The attribute-filter layer hasn't been built on top of the existing embedding infrastructure.
**Concrete fix:** Add `find_cards_for_slot(description, format_name, card_type, max_cmc, color_ids, n)` to `analysis/card_embeddings.py`. Implementation: call `find_similar_cards(description, n=n*5)` for candidates, then filter by `card_data.legalities` JSON column + `card_data.type_line` + `card_data.cmc`. Per spec `harness/specs/2026-05-03-hybrid-vector-search.md`.
**Estimated effort:** 1-2 hours.
**Status:** OPEN
**Created:** 2026-04-30

---

### apl-deck-mismatch-grinding-breach (RESOLVED 2026-04-29 at 74b4f33 -- removed from canonical field)

**Source:** Investigation following duplicate-deck-files finding.
**What's not perfect:** `apl/grinding_breach.py` is a 93L hand-tuned APL that expects `COMBO_PIECES = {"Underworld Breach", "Grinding Station"}`, ENABLERS including Emry, Mox Opal, etc. But `decks/grinding_breach_modern.txt` (mislabeled as duplicate of temur_breach) contains zero of those cards — it's a Storm-ritual deck (Desperate Ritual, Past in Flames, Ral Monsoon Mage). The APL searches for cards it'll never find; main_phase logic falls through to default behavior. Effectively, the canonical 6.4% "Grinding Breach" gauntlet slice runs an APL grasping at non-existent combo pieces.
**Why not fixed:** Compounds with `duplicate-deck-files-in-canonical-field`; same fix applies (source real decklist).
**Concrete fix:** Same as duplicate-deck-files fix 2 — source actual Underworld Breach + Grinding Station decklist (any recent Modern Top 8) and replace the file. ~15 min.
**Status:** OPEN
**Created:** 2026-04-29

### jeskaicontrol-key-mismapping (RESOLVED 2026-04-29 at 908b617)

**Source:** `apl/__init__.py:151` (existing pre-fix line) + investigation 2026-04-29.
**What's not perfect:** Pre-fix MATCH_APL_REGISTRY had `"jeskaicontrol" -> JeskaiBlinkMatchAPL`. Jeskai Control is a real Modern deck (different from Jeskai Blink); routing Jeskai Control matchups through Jeskai Blink's match APL produces wrong card-decision behavior (Phlage hardcast vs control's Solitude/Subtlety/Wandering Emperor). Today's Jeskai Blink fix kept this entry for backward compat (left a comment), but it should be either removed or pointed at a real Jeskai Control match APL when one exists.
**Why not fixed:** Removing the wrong entry could break any caller that's relying on the pre-fix routing (unlikely but possible). Adding a new JeskaiControl match APL is a separate spec.
**Concrete fix:** Either (1) remove the `"jeskaicontrol"` entry from MATCH_APL_REGISTRY (forces proper fallback to goldfish JeskaiControlAPL); or (2) author `apl/jeskai_control_match.py` and route there.
**Estimated effort:** 5 min for option 1; 60-90 min for option 2.
**Status:** RESOLVED 2026-04-29 at 938cb18 (JeskaiControlMatchAPL written + registered; `jeskaicontrol` entry points correctly in MATCH_APL_REGISTRY)
**Created:** 2026-04-29

### sim-py-hardcoded-humans-apl (RESOLVED -- auto-resolve already implemented in sim.py:_resolve_apl_from_deck; imperfection was stale)

**Source:** Investigation 2026-04-28 of why sim.py output didn't reflect changes to `apl/jeskai_blink.py`.
**What's not perfect:** `mtg-sim/sim.py:50` is hardcoded to `apl=HumansAPL()` regardless of the `--deck` argument. Output is "HumansAPL piloting whatever-deck's-cards", not "the deck's actual APL piloting its cards". Makes sim.py misleading for any deck except Humans. All goldfish "kill turn" measurements via sim.py for non-Humans decks are noise.
**Why not fixed in source:** Latent since the script's creation. Not surfaced before because most goldfish testing went through `apl_tuner.py` (which DOES use the deck's APL via APL_REGISTRY).
**Concrete fix:** Add `--apl` arg OR auto-resolve from `APL_REGISTRY` based on `--deck` filename. Roughly:
```python
from apl import APL_REGISTRY, _normalize_key, _load_class
deck_basename = os.path.basename(args.deck).replace('_modern.txt','').replace('_legacy.txt','')...
key = _normalize_key(deck_basename)
if key in APL_REGISTRY:
    module_path, class_name, _ = APL_REGISTRY[key]
    apl_cls = _load_class(module_path, class_name)
else:
    apl_cls = HumansAPL  # fallback
```
**Estimated effort:** 15-20 min (auto-resolve + fallback + smoke test).
**Status:** OPEN
**Created:** 2026-04-28

### affinity-never-blocks (NEW 2026-04-29; real-meta field audit)

**Source:** `apl/affinity_match.py:156` — `declare_blockers` returns `{}`.
**What's not perfect:** Affinity (9.0% real meta, #3 deck) never assigns blockers as opponent. Results in 96.9% BE win rate which is clearly inflated — Kappa Cannoneer (ward 4, grows every artifact ETB) and Arcbound Ravager should be difficult blockers. No blocking means every attacking creature hits for free.
**Why not fixed:** Affinity match APL was thin (180L) and blocking logic was deferred.
**Concrete fix:** Implement `declare_blockers` to assign Kappa (ward 4, 4/4+) and large Ravager targets. ~30-60 min.
**Estimated effort:** 30-60 min.
**Status:** OPEN
**Created:** 2026-04-29

### goryo-solitude-white-pitch-bug (RESOLVED 2026-04-29 -- same fix as JB ce492dc)

**Source:** `apl/goryos_match.py:101` — same Solitude evoke white-pitch bug as pre-fix Jeskai Blink.
**Fix:** Added `'W' in (getattr(x, 'colors', []) or [])` filter. 1-line fix, same pattern as JB.
**Status:** RESOLVED 2026-04-29
**Created:** 2026-04-29

### no-apl-belcher (NEW 2026-04-29; real-meta field audit)

**Source:** MTGGoldfish 30-day Modern meta 2026-04-29. Belcher 3.5% (82 decks), not in canonical field.
**What's not perfect:** No APL or match APL for Goblin Charbelcher / Landless Belcher. Key cards: Goblin Charbelcher, Sea Gate Restoration, Disrupting Shoal. Combo kill T2-3 via Belcher activation with 0 lands in deck. Not in canonical field, missing 3.5% coverage.
**Concrete fix:** Combo-kill-sampler match APL (same pattern as Neobrand/Goryo's). Kill distribution T2: 20%, T3: 50%, T4: 30%. ~45-60 min to write + register.
**Estimated effort:** 45-60 min.
**Status:** OPEN
**Created:** 2026-04-29

### no-apl-neobrand (NEW 2026-04-29; real-meta field audit)

**Source:** MTGGoldfish 30-day Modern meta 2026-04-29. Neobrand 3.2% (76 decks), not in canonical field.
**What's not perfect:** No APL for Neobrand (Griselbrand + Summoner's Pact + Neoform combo). Key: Neoform into Griselbrand T1 on play, draw 14, win. Kill T1: 30%, T2: 50%, T3: 20%. Summoner's Pact upkeep loss is a real failure mode Consign counters. Not in field, missing 3.2% coverage.
**Concrete fix:** Combo-kill-sampler match APL. ~45-60 min. Key interaction to model: Summoner's Pact upkeep trigger (opponent can Consign to counter it → Neobrand loses the game).
**Estimated effort:** 45-60 min.
**Status:** OPEN
**Created:** 2026-04-29

### no-apl-grixis-reanimator (NEW 2026-04-29; real-meta field audit)

**Source:** MTGGoldfish 30-day Modern meta 2026-04-29. Grixis Reanimator 2.3% (55 decks), not in canonical field.
**What's not perfect:** No APL for Grixis Reanimator (Abhorrent Oculus / Archon of Cruelty via Unmarked Grave + Persist). Kill T2-3. Not in field, missing 2.3% coverage.
**Concrete fix:** Match APL similar to Goryo's (both cheat large creatures). ~45-60 min. Differentiate: no Solitude, different reanimation targets (Oculus, Archon).
**Estimated effort:** 45-60 min.
**Status:** OPEN
**Created:** 2026-04-29

### no-match-apl-jeskai-control (RESOLVED 2026-04-29 at 938cb18)

**Source:** MTGGoldfish 30-day Modern meta 2026-04-29. Jeskai Control 2.2% (52 decks). Has GoldfishAdapter fallback only.
**What's not perfect:** Jeskai Control (Teferi, Orim's Chant, Narset, Solitude) uses GoldfishAdapter — plays like an aggro deck instead of a tap-out control deck. Critical oracle failure: Orim's Chant can stop attacks entirely; Narset prevents drawing; Teferi locks sorcery-speed. None of this is modeled in goldfish fallback.
**Concrete fix:** Write JeskaiControlMatchAPL (~150-200L). Key behaviors: Teferi lock, Narset anti-draw, Orim's Chant in declare-blockers to prevent attacks, Solitude removal with white-pitch filter. ~60-90 min.
**Estimated effort:** 60-90 min.
**Status:** OPEN
**Created:** 2026-04-29

### no-apl-temur-prowess (NEW 2026-04-29; real-meta field audit)

**Source:** MTGGoldfish 30-day Modern meta 2026-04-29. Temur Prowess 1.7% (40 decks), not in canonical field.
**What's not perfect:** No APL for Temur Prowess (Slickshot Show-Off, Cori-Steel Cutter, DRC). Different from Izzet Prowess — adds green for Questing Druid / Become Immense. Missing 1.7% coverage. Our Izzet Prowess APL does not map to this deck.
**Concrete fix:** New match APL or extend IzzetProwessMatchAPL with Temur sideboard. ~45-60 min.
**Estimated effort:** 45-60 min.
**Status:** OPEN
**Created:** 2026-04-29

### no-apl-sultai-midrange (NEW 2026-04-29; real-meta field audit)

**Source:** MTGGoldfish 30-day Modern meta 2026-04-29. Sultai Midrange 1.6% (38 decks), not in canonical field.
**What's not perfect:** No APL for Sultai Midrange (Abhorrent Oculus, Subtlety, Sink into Stupor). Missing 1.6% coverage.
**Concrete fix:** Match APL similar to Dimir Midrange but with green (Subtlety + Oculus as key threats). ~45-60 min.
**Estimated effort:** 45-60 min.
**Status:** OPEN
**Created:** 2026-04-29

### no-apl-grixis-midrange (NEW 2026-04-29; real-meta field audit)

**Source:** MTGGoldfish 30-day Modern meta 2026-04-29. Grixis Midrange 1.5% (36 decks), not in canonical field.
**What's not perfect:** No APL for Grixis Midrange (Orcish Bowmasters, Subtlety, Thoughtseize). Missing 1.5% coverage.
**Concrete fix:** Match APL. Likely shares most logic with Dimir Midrange (swap Psychic Frog for Orcish Bowmasters + red interaction). ~30-45 min once Dimir Midrange match APL is audited as a template.
**Estimated effort:** 30-45 min.
**Status:** OPEN
**Created:** 2026-04-29

## How to use this file

When picking up a session:

1. Check this file for any OPEN imperfections you can knock out cheaply
2. Quick wins (5-30 min) are good warmup work
3. Bigger items (60+ min) plan a dedicated spec

When closing an imperfection:

1. Mark Status: RESOLVED with date + commit hash
2. Move the entry to `harness/RESOLVED.md` (create if needed)
3. The findings doc that originated the imperfection gets a "Resolved" note with link to commit
4. Add a "Resolved this week" line at the top of THIS file with a pointer to the [RESOLVED.md](http://RESOLVED.md) entry, for at-a-glance visibility [RESOLVED.md](http://RESOLVED.md) entry, for at-a-glance visibility
