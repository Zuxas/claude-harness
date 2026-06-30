# Modern APL Fidelity Audit — Synthesis (handoff #1)

**Status:** PARTIAL — diagnosis complete; fixes deferred to handoff #2 (combo) and #3 (Izzet Affinity).
**Created:** 2026-06-30
**Source:** 7 read-only audit agents (clusters: big-mana-zoo, aggro-tempo, affinity-artifacts, dimir-control, combo-reanimator, combo-storm-belcher, blink-midrange). Each: our deck `boros_energy_lowcurve_modern` as SEAT A vs the audited deck as SEAT B, `engine.match_runner.run_match`, n=50/deck, alternating on_play, oracle DB warmed locally (0 network). Nothing under `mtg-sim/` was modified.
**Cross-ref:** `mtg-sim/mismodeled_matchups.py`, `harness/IMPERFECTIONS.md`.

## Headline counts

| Classification | Count |
|---|---|
| CRASH | 1 |
| ERROR (uncovered) | 1 |
| DEGRADED | 24 |
| PASS | 8 |
| **Total decks audited** | **34** |

Zero decks crash-per-turn at scale: the Grixis "crashes-every-turn" template is now essentially gone from the field — only **esper_blink** still carries one unguarded site (1/50 games). The dominant failure mode is **silent under-firing**: APLs run clean (0 exceptions, 0 fallback) but do not assemble/execute their archetype's real gameplan, so the matchup numbers are wrong with no error signal.

## Two structural root causes (cluster-wide)

1. **Match mode never calls combat/reaction hooks.** `match_runner.run_match` only invokes `main_phase_match` / `main_phase2(_match)` / `end_step_actions`. It NEVER calls `declare_attackers`, `declare_blockers`, or `respond_to_spell`. Combat is resolved by the engine reading battlefield bodies. Consequence: every attack-trigger value engine (Titan land-fetch, Phlage recurring burn, Phelia exile loop, Ulamog exile-20) and every reactive counter (Stubborn Denial, Consign, Force of Negation, Subtlety) is dead or fired proactively into an empty stack. This is the residual of the R1/R2 work (SUPERSEDED entries `sim-no-stack-priority`, `sim-no-instant-speed-combat`) — engine support exists but these decks don't opt in via `WANTS_*`.
2. **`main_phase1` direct-damage is discarded by the engine.** Decks that deal face damage via `gs.damage_dealt` inside `main_phase_match` lose it unless `WANTS_STORM=True` (gate at `match_runner.py:276`); the inherited base `main_phase2` then finds an empty burn hand, and `_run_end_step` never propagates `damage_dealt` at all. This is a NEW engine-level finding (clearest in Mono Red: mean 6.1 face dmg computed-then-dropped/game). Every non-storm deck that burns to the face in mp1/end-step loses that damage.

A third recurring cause is **no `main_phase2_match`** across the combo clusters → `_run_post_combat_phase` falls back to `BaseAPL._cast_all_castable`, which blind-casts combo enablers cheapest-first outside the APL's sequencing gate (hardcasts Living End at sorcery speed; blind-casts Persist/Goryo's).

## Ranked triage table (CRASH → DEGRADED by severity → PASS)

| # | Deck | Class | Sev | Crash site | fires_sig / fallback | avg kill T | One-line evidence |
|---|---|---|---|---|---|---|---|
| 1 | esper_blink_modern | CRASH | low | esper_blink_match.py:142 (ValueError) | yes / 0.001 | 8.16 | Unguarded value-based `battlefield.remove(target)` in Ephemerate+Solitude double-ETB branch (twin of guarded L178); 1/50 games. Otherwise fires everything. Deck retired from live field 2026-06-30 — small blast radius. |
| 2 | mono_red_aggro_modern | DEGRADED | high | none | yes / 0 | 10 (n=1) | Engine discards all mp1 `damage_dealt` burn (no WANTS_STORM/mp2); mean 6.1 face dmg dropped/game. B wins 2%. WANTS_STORM=True monkeypatch lifts 2%→12%, T10→T7.83. NEW + engine-level. |
| 3 | cutter_affinity_modern | DEGRADED | high | none | yes / 0 | 6.84 | NO dedicated APL — GoldfishAdapter over auto-gen CutterAffinityAPL (AUTO_GENERATED, flagged for rewrite). Casts 1 threat/turn; mp2 removal block never invoked; Cori-Steel/Rebuke unmodeled. We win 96%. |
| 4 | glockulous_modern | DEGRADED | high | none | no / 0 | 7.88 | Auto-gen MatchAPL; reanimator payoff never fires (Archon 0/50, Troll 0/50). Persist/Unearth treated as removal or +2 burn, never routed through cast_spell. Content-match to registry-INVERTED Grixis Reanimator. We win 90%. |
| 5 | jeskai_control_modern | DEGRADED | high | none (latent jeskai_control_match.py:136 ValueError in unreachable jeskaimodern APL) | no / 0 | 9 (n=1) | Routes to a STANDARD APL piloting a Modern deck. Massively under-fires key interaction: Solitude 3/50, Phlage 4/50, Counterspell 6/50. B wins 2%. Would-be Modern pilot is itself crash-broken (16/50). |
| 6 | living_end_modern | DEGRADED | high | none | no / 0 | 9 (n=1) | No mp2_match → `_cast_all_castable` HARDCASTS CMC-0 Living End at sorcery speed on near-empty GY, burning all 3 before cyclers load. Combo fires 1/50. We win 98%. |
| 7 | yawgmoth_modern | DEGRADED | high | none | no / 0 | 8.9 | Infinite combo fires 0/50: deck is the Cauldron/Ballista variant with ZERO Blood Artist/Zulaport but APL `DRAINS={Blood Artist,Zulaport}` → `_check_combo_kill` early-returns. Plays as fair -1/-1 grinder. NEW + UNDOCUMENTED. |
| 8 | belcher_modern | DEGRADED | high | none | no / 0 | 0 | Landless stub leaves match mana pool empty; cast_spell True = 0 across all 50; Charbelcher kill has no code path. B wins 0/50 (we win 100%). ~50pp inflation. |
| 9 | neobrand_modern | DEGRADED | high | none | no / 0 | 0 | Only `_play_land + _cast_all_castable`; Summoner's Pact→Shepherd→Neoform→Griselbrand never assembles. 0/50 signature; B wins 0/50. Real Neobrand kills T1-2. |
| 10 | neoform_modern | DEGRADED | high | none | yes / 0 | 10 (n=1) | AUTO_GENERATED (flagged for rewrite); fires pieces 24/50 but deploys by CMC + flat +2 face, no Neoform→Griselbrand kill. B wins 1/50 at T10 vs real T1-3. |
| 11 | ruby_storm_modern | DEGRADED | high | none | yes / 0 | 0 | Best-modeled storm (R3 rewrite, WANTS_STORM): genuinely storms (539 casts, sig 45/50) but gated mp1 spell-damage sync never reaches 20 → wins 0/50. Fires gameplan, under-converts payoff. |
| 12 | temur_breach_modern | DEGRADED | high | none | yes / 0 | 0 | NO dedicated match APL — GoldfishAdapter over GenericAPL combo SHIM. Casts Past in Flames/Ral but Grapeshot/Empty are SB/Wish-only, no WANTS_STORM, no ritual→storm sequencing. B wins 0/50. |
| 13 | jeskai_phelia_modern | DEGRADED | high | none | yes / 0 | 8.45 | NO dedicated APL — GoldfishAdapter over auto-gen JeskaiPheliaAPL plays solitaire, never spends mana interacting. We win 38% here vs 64% vs the dedicated jeskai_blink APL at near-identical clock → cell low-fidelity in UNKNOWN direction. |
| 14 | landless_belcher_modern | ERROR | medium | none | no / n/a | 0 | NO MATCH APL reachable: `get_match_apl('landlessbelcher')`=None, auto APL absent from `auto_apl_registry.json` (failed smoke gate). load_pair→None → slice silently skipped. Archetype uncovered. |
| 15 | amulet_titan_modern | DEGRADED | medium | none | yes / 0 | 6.89 | Titan attack-trigger land-fetch (the combo engine) lives in dead declare_attackers; resolves as a lone 6/6 fair beater at T6.89 not real T3-4 combo. Our WR shown 82% vs realistic ~55%. |
| 16 | domain_zoo_modern | DEGRADED | medium | none | yes / 0 | 7.29 | ALL non-body output (Phlage burn, Kavu card-adv, Frog draws, Scion lifegain) + Stubborn Denial counter in dead declare_attackers/respond_to_spell. Bodies still attack; burn-reach + card engine gone. |
| 17 | eldrazi_ramp_modern | DEGRADED | medium | none | yes / 0 | 8.38 | Support spells fire but a big-Eldrazi payoff lands only 29/50; mana heavily fudged (`mana_pool.flex`); Emrakul often not re-cast. Slow T8.38 vs real T3-5. |
| 18 | dimir_oculus_modern | DEGRADED | medium | none | yes / 0 | 7.25 | Cross-format STANDARD APL on Modern deck. Oculus lands 37/50 but resolves as vanilla 2/2 flyer — its "manifest dread at each opp upkeep" engine unmodeled; Murktide secondary 0/50. |
| 19 | dimir_midrange_modern | DEGRADED | medium | none | yes / 0 | 10.44 | Proxied to MurktideMatchAPL (tempo vocab absent) → generic caster. Goodstuff deploys but Kaito (marquee PW) resolves 1/50 and does nothing (WANTS_PW_LOYALTY off). No inevitability modeling. |
| 20 | goryos_vengeance_modern | DEGRADED | medium | none | no / 0 | 6.8 | Core Goryo's reanimation fires 2/50 — target rarely in GY (no discard/mill setup). Plays fair Solitude/Frog beatdown. Shares no-mp2_match blind-cast issue. |
| 21 | gruul_broodscale_modern | DEGRADED | medium | none | no / 0 | 11 | DOCUMENTED stub by design — APL does not model the infinite Broodscale loop; fills field row as fair creature deck. T11 vs real T3-5. |
| 22 | uw_blink_modern | DEGRADED | medium | none | yes / 0 | 9 | Dedicated APL but AUTO_GENERATED; end_step_actions is bare `pass`, no flash window, no attack-blink loop. We win 78% — highest cell in cluster, almost certainly inflated for a grindy value deck. |
| 23 | orzhov_blink_modern | DEGRADED | medium | none | yes / 0 | 9.5 | Wrong APL: `MATCH_APL_REGISTRY['orzhovblink']` → white-based AUTO_GENERATED UWBlinkMatchAPL. Black cards cast via generic fill, no Orzhov sequencing, no targeting. Uncalibrated. |
| 24 | jeskai_blink_modern | DEGRADED | medium | none | yes / 0 | 9.39 | Dedicated APL runs clean but #1 cast is Consign to Memory (56x) dumped into empty stack (respond_to_spell never called); Phelia attack-exile loop (jeskai_blink_match.py:786) structurally dead. We win 64%, likely inflated. |
| 25 | sultai_midrange_modern | DEGRADED | medium | none | yes / 0 | 7.71 | Best-modeled blink-cluster deck (dedicated AwareMatchAPL); offense/removal fires clean, tightest clock, we LOSE 44%. DEGRADED only because free counters (FoN 8x, Flare of Denial 21x, Subtlety) dumped proactively into empty stack. Mild over-estimate of our edge. |
| 26 | humans_modern | DEGRADED | low | none | yes / 0 | 6.24 | Lord ETB snowball works (in main_phase); only dead pieces are Jirina anthem + Hierarch exalted in declare_attackers. Coherent T6.24 aggro clock. Lowest-impact DEGRADED. |
| 27 | eldrazi_tron_modern | PASS | low | none | yes / 0 | 8.19 | Executes real plan clean (Tron mana, Map, Talismans, removal, TKS exile, Karn/Ugin ETB, WANTS_PW_LOYALTY). Only Ulamog attack-exile + TKS LtB drawback are minor dead pieces. |
| 28 | izzet_affinity_modern | PASS | **high** | none | yes / 0 | 5.86 | APL runs CLEAN and fires gameplan — but matchup is registry-INFLATED (sim ~85-88% vs truth ~44%, a SIGN INVERSION; we are the dog in reality). Measured 80% corroborates. PASS on behavior, distorted cell. **Feeds #3.** |
| 29 | izzet_prowess_modern | PASS | low | none | yes / 0 | 4.96 | Realistic prowess clock; wins via combat (`_resolve_combat` applies prowess pumps correctly). Shares latent mp1-burn-discard but only 0.7 dmg/game dropped (creature-based). |
| 30 | boros_energy_modern | PASS | low | none | yes / 0 | 7.6 | Clean; all signature cards fire; combat-based wins. Latent damage-discard on Phlage/Bombardment non-combat dmg, but combat carries. Sim clock slightly slow vs real ~T5-6. |
| 31 | boros_energy_lowcurve_modern | PASS | none | none | yes / 0 | 8.93 | OUR deck (mirror baseline). 0 crashes over 436 mp calls — clean seat-A baseline check. Balanced mirror 54%. |
| 32 | uw_control_modern | PASS | low | none | yes / 0 | 11 | Faithful UWControlModernMatchAPL; fires control plan (wraths, Teferi, Narset, Jace, counters); slow inevitability wins are CORRECT for control. B winrate 10% vs aggro, plausible. |
| 33 | dimir_murktide_modern | PASS | none | none | yes / 0 | 7.86 | Faithful MurktideMatchAPL; full tempo plan fires (Murktide 21/50, Ragavan, DRC, Ledger Shredder, counters). Executes real plan. |
| 34 | grixis_reanimator_modern | PASS | low | none | yes / 0 | 7.11 | Crash template FIXED (test PASS 50/50 under SIM_DEBUG=1); fires gameplan 41/50. Residual is a known modeling gap (no GY-hate model; Oculus slow 2/2 clock), not APL fidelity. Registry still INVERTED. |

## Corroboration vs `mismodeled_matchups.py`

The registry currently flags 5 cells. The audit **corroborates all 5** and adds **many NEW findings**.

### Corroborates existing flagged cells (5)

| Registry key | Registry direction | Audit measurement | Verdict |
|---|---|---|---|
| grixis reanimator | INVERTED (sim ~75% vs truth ~38%) | we win ~64% (crash now fixed), still inverted vs primer | CORROBORATES direction |
| goryos vengeance | INFLATED (sim ~84-92% vs ~73%) | we win ~90%, combo fires 2/50 | CORROBORATES |
| living end | INFLATED (~96%) | we win ~98%, combo fires 1/50 | CORROBORATES |
| gruul broodscale | INFLATED/STUB (~89% vs ~55%) | we win ~92%, 0 combo by design | CORROBORATES (documented stub) |
| izzet affinity | INFLATED (sim ~85-88% vs ~44%) | we win 80%, clean APL | CORROBORATES (sign inversion) |

### NEW findings (not in the registry)

- **Engine-level (highest leverage):** `mono_red_aggro` — mp1/end-step `damage_dealt` discarded for every non-storm deck (NEW, engine-wide). This is not a per-deck bug; it silently nerfs every direct-damage-to-face plan that isn't a storm deck.
- **Combo cluster, undocumented:** `yawgmoth` (combo can never assemble — wrong drain list vs deck variant), `belcher` (landless stub, empty mana pool), `neobrand`, `neoform`, `ruby_storm` (storms but never closes), `temur_breach` (GenericAPL shim), `landless_belcher` (ERROR — uncovered), `glockulous` (reanimator payoff never fires).
- **Coverage / routing gaps:** `cutter_affinity` (no dedicated APL, auto-gen inert), `jeskai_phelia` (no dedicated APL, goldfish solitaire), `orzhov_blink` (wrong/white APL routed), `dimir_oculus` + `dimir_midrange` + `jeskai_control` (cross-format STANDARD/proxy APLs on Modern decks).
- **Dead-combat-hook structural under-fire:** `amulet_titan`, `domain_zoo`, `eldrazi_ramp`, `humans`, `jeskai_blink`, `uw_blink`, `sultai_midrange`, `esper_blink` — all under-fire attack-triggers and/or fire reactive counters proactively. Corroborates the SUPERSEDED structural entries (`sim-no-instant-speed-combat` R2, `sim-no-stack-priority` R1) — engine supports it, decks haven't opted in via `WANTS_*`.
- **Lingering crash template:** `esper_blink` (the last unguarded `.remove()` twin of the Grixis pattern).

## Recommended fix priority for #2 / #3

### Handoff #2 (combo) — these audited decks feed it

Listed worst-distortion first. All are clean-but-inert / under-converting.

1. **belcher** (DEGRADED high, ~50pp inflation, 0 casts) — needs Spirit Guide mana + Charbelcher activated-ability kill path. Currently inert.
2. **neobrand** (DEGRADED high, 0/50, inverts a T1-2 combo to 100% for us) — needs Pact→Shepherd→Neoform→Griselbrand sequencing.
3. **temur_breach** (DEGRADED high, GenericAPL shim, 0/50) — needs a dedicated match APL + WANTS_STORM + ritual→storm-count sequencing; SB/Wish Grapeshot unreachable.
4. **ruby_storm** (DEGRADED high, fires but never closes) — CLOSEST to working; fix the gated mp1 spell-damage→20 sync (overlaps the Mono Red engine discard finding).
5. **neoform** (DEGRADED high, AUTO_GENERATED) — replace flat +2-face approximation with real Neoform→Griselbrand line.
6. **living_end** (DEGRADED high) — add `main_phase2_match` so `_cast_all_castable` stops hardcasting Living End at sorcery speed; gate cascade properly.
7. **goryos_vengeance** (DEGRADED medium) — set up reanimation target in GY (discard/mill) before firing; add mp2_match gate.
8. **gruul_broodscale** (DEGRADED medium) — acknowledged stub; model the Broodscale infinite loop or keep flagged.
9. **grixis_reanimator** (PASS, crash fixed) — calibration target only; residual is the interaction-aware-combo modeling gap, not APL fidelity. Keep flagged INVERTED.

**NEW combo deck to ADD to #2 scope:** `yawgmoth` — DEGRADED high, combo fires 0/50 because the APL's `DRAINS`/`UNDYING` lists don't match the actual deck variant (Cauldron/Ballista, zero Blood Artist/Zulaport). Fix is cheap (align lists / add Ballista-lethal branch) and it is currently UNDOCUMENTED. Recommend folding into #2.

**Cross-cutting engine fix that helps #2 AND aggro:** the mp1/end-step `damage_dealt` discard (root cause of Mono Red, partial Ruby Storm under-conversion). Highest leverage single change — fixes burn-to-face for every non-storm deck and unblocks Ruby Storm's closing step.

### Handoff #3 (Izzet Affinity) — these feed it

1. **izzet_affinity** (PASS behavior, severity HIGH) — the cell is a SIGN INVERSION (sim ~80-88% for us vs truth ~44%). Cause is engine-side undermodeling (Galvanic Blast reach, Thoughtcast card-advantage, artifact clock), NOT an APL crash. This is the primary #3 target.
2. **cutter_affinity** (DEGRADED high) — affinity-adjacent; no dedicated APL (auto-gen inert, one-threat-per-turn, mp2 removal never invoked). Recommend authoring a real Cutter Affinity match APL alongside the Izzet Affinity clock work.
3. **glockulous** (DEGRADED high) — artifact/reanimator hybrid whose reanimation payoff never fires; lower priority but shares the "payoff never routed through cast_spell" pattern.

## Changelog

- 2026-06-30: Created. Synthesis of 7-cluster Modern APL fidelity audit (handoff #1). 34 decks: 1 CRASH, 1 ERROR, 24 DEGRADED, 8 PASS. All 5 registry-flagged cells corroborated; many NEW findings (engine mp1-damage discard, yawgmoth combo mis-list, storm cluster, routing/coverage gaps). Prioritization input for handoff #2 (combo) and #3 (Izzet Affinity) written.
