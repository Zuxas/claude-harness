# Post-Ban Boros Energy validation + calibration re-measure (2026-06-29)

Resolves the two in-flight workflows from `harness/HANDOFF_2026-06-29.md` (A = Selesnya-Prowess
calibration, B = Low Curve Energy encode/fidelity). Ultracode workflow `wf_84ff24e7-aa2` ran the
fidelity audit + 7-opponent gauntlet; its two load-bearing verify streams (calibration,
engine-regression) died "Response stalled mid-stream", so the calibration was RE-MEASURED directly
(scratchpad `calib_remeasure.py`, `engine.match_engine.run_match`, fresh APL/game, alt on_play,
seed=42+i).

## The change under test (4 coupled code files + additive artifacts)
- `apl/aware_match_apl.py` -- declare_attackers rewrite (per-blocker subtraction; never drops
  evasive/unblocked attackers; knob DEAD_TRADE_HOLD_MARGIN=0, hook PROTECT_FROM_TRADE).
- `apl/selesnya_landfall_standard_match.py` -- replaced duplicate buggy loop with super() delegation.
- `engine/game_state.py` + `engine/card_effects.py` -- battle cry in `_do_combat` (CHANGE 1) +
  fetch->on_landfall doubling (CHANGE 2, a real bug-fix: fetches previously fired ZERO landfall).
- Additive: `apl/__init__.py` registry line `borosenergylowcurve`, `decks/boros_energy_lowcurve_modern.txt`,
  `tests/test_pyrosurfer_battlecry_package.py`.

## CORRECTION (2026-06-29, post-commit seat-symmetric re-measure)
The headline 65.3% below was measured with Selesnya ALWAYS in seat A. A seat-symmetric re-measure
(Selesnya as A half the games, B half; engine.match_engine, global RNG seeded) gives the HONEST
bias-cancelled number: **Selesnya-vs-Prowess = 60.7% +/- 1.5pp (n=1000, 95% CI [57.7, 63.7])**
(Sel=A 59.0, Sel=B 62.4). This is still IN BAND [60,71.5] (just above the floor) and PT 62.9 sits
inside the CI -- so the calibration gate HOLDS -- but the committed "65.3%" was seat-A-only and
~4-5pp optimistic; the fix is conservative-to-accurate, not comfortably mid-band. Separately, the
"mirror seat-bias" flag (58.5 at n=200) was NOISE: Prowess mirror = 51.0% at n=500 seeded -> no
structural seat bias, no engine change needed. Treat 60.7% as the calibration number of record.

## Calibration RE-MEASURE (current full tree, all 4 code files live)
| Matchup | Re-measured | Target / handoff claim | Verdict |
|---|---|---|---|
| Selesnya(A) vs Prowess(B) | **65.3%** (196/300) | [60,71.5], PT 62.9 | IN BAND (headline PASS) |
| Selesnya(A) vs MonoGreen(B) | 87.0% (174/200) | de-inversion (~97 claimed) | de-inverted, -10pp (CHANGE 2 narrowing) |
| Prowess mirror | 58.5% (117/200) | ~50 (47.3 claimed) | near-50, mild seat-A bias |
| Prowess(A) vs Jeskai(B) | 85.5% (171/200) | 70 "unchanged" claimed | +15.5pp -- fix makes aggro beat control |
| Prowess(A) vs MonoGreen(B) | 77.0% (154/200) | 84.3 flag | within noise of the flag |

Headline gate PASSES: 65.3% in band, replacing the known-wrong ~77% overshoot. The no-regression
numbers MOVED from the handoff's claims (none inverted); movements are directionally consistent with
the declare_attackers fix (aggro now attacks -> beats control harder) and CHANGE 2 (Mono-Green's 4
Fabled Passage now trigger landfall). Handoff's "unchanged" regression claims were optimistic.

## Fidelity audit: PASS (zero defects)
test_pyrosurfer_battlecry_package.py passes 3/3. Verified rules-correct: 2 landfall/successful fetch
(1 on whiff), static battle-cry set {Signal Pest, Sanguine Evangelist} complete, power-restore unwinds
to true original across slickshot nesting + multi-combat + death, self-pump excluded. Locked Modern
baseline (boros_energy_modern) PROVABLY byte-identical: runs none of the battle-cry creatures and no
landfall payoffs, so both engine changes are structural no-ops there.

## FINDING (now FIXED) -- battle cry (CHANGE 1) was GOLDFISH-ONLY, dead in match mode
ORIGINAL FINDING: the two-player match engine routes combat through
`engine/match_runner.py::_resolve_combat`, NOT through `GameState._do_combat` where the battle-cry
block lives. Verified by call-counter probes (docombat=0 over match games; match_runner never read
`_battle_cry_instances` / `_STATIC_BATTLE_CRY`). CHANGE 2 (on_landfall) DID fire in matches (via the
per-turn GameState view, whose battlefield aliases bf_a/bf_b) and SET `_battle_cry_instances`, but
nothing CONSUMED it -- so the Low Curve deck's signature payoff (Voice mobilize -> Pyrosurfer
"11-damage line") was modeled in goldfish but DEAD in every gauntlet/match.

FIX (2026-06-29, this commit): wired battle cry into `match_runner._resolve_combat` (mirrors the
`_do_combat` block; pump each OTHER attacker +1/+0 per instance, restored post-combat next to
Slickshot) + a faithful per-turn reset of `_battle_cry_instances` in `_run_player_turn`. New test
`tests/test_pyrosurfer_battlecry_match.py` pins the 11-damage line at the match-combat interface
(RED at 5 dmg pre-fix -> GREEN at 11). Also closed the registry gap: `borosenergylowcurve` added to
MATCH_APL_REGISTRY (real BorosEnergyMatchAPL pilot, not the under-piloting GoldfishAdapter).
A/B (vs Goryo's, n=150, identical seeds, on_landfall instrumented): instances DO accumulate in match
play (59-64 grants/150 games) and battle cry contributes **+1.3pp WR** (89.3 vs 88.0) -- small but
real; Pyrosurfer often isn't attacking on its instance-turns, so the pump fires modestly. The
registry fix is the bigger mover (Eldrazi Tron 35.5 -> 53.5).

## POST-FIX gauntlet (borosenergylowcurve, n=200 G1, match_runner.run_match, both fixes live)
| Opp | Pre-fix G1 | POST-fix G1 | Primer real | Note |
|---|---|---|---|---|
| Eldrazi Tron | 35.5% | 53.5% | ~55% | now ON-TARGET (registry/real-pilot fix) |
| Izzet Affinity | 75.5% | 83.5% | ~44% | opponent (Affinity) undermodeled |
| Izzet Prowess (Modern) | 60.0% | 61.5% | ~50% | stable; SB not modeled |
| Goryo's Vengeance | 79% | 84.0% | ~73% | combo clock under-fires |
| Grixis Reanimator | ~70% | 81.0% | ~25-38% DOG | INVERTED -- GrixisReanimatorMatchAPL crashes (imperfection) |
| Living End | 90.5% | 96.0% | (no cell) | out-races a sim-weak combo |
0 crashes across 1200 games. Our deck reads stronger across the board (real pilot); residual
divergences are OPPONENT-side undermodeling, not the code under test. Gauntlet still cannot fully
validate the primer until opponent APLs (esp. Grixis crash, Affinity clock) are improved.

## Gauntlet vs primer (borosenergylowcurve, n=200 G1, real run_match)
| Opp | Sim G1 | Primer real | Note |
|---|---|---|---|
| Izzet Affinity | 75.5% | ~44% | opponent (Affinity) undermodeled (+31pp) |
| Izzet Prowess (Modern) | 60.0% | ~50% | +10pp; SB not modeled |
| Goryo's Vengeance | 79-80% | ~73% | combo clock under-fires (earliest kill T5 vs paper T2-4) |
| Grixis Reanimator | ~70% | ~25-38% DOG | INVERTED -- GrixisReanimatorMatchAPL crashes every turn |
| Eldrazi Tron | 35.5% | ~55% | our seat under-piloted via GoldfishAdapter |
| Living End | 90.5% | (no cell) | out-races a sim-weak combo |
| Gruul Broodscale | -- | ~55% | MISSING: no deck file, no registry key |

Divergences are dominated by OPPONENT-side undermodeling, not the code under test. Per "do not tune
toward the primer", these are findings, not gates.

## Open items / imperfections
1. FIXED (this commit): CHANGE 1 (battle cry) now consumed in match_runner._resolve_combat; new match
   test added. +1.3pp WR impact (modest).
2. FIXED (this commit): `borosenergylowcurve` added to MATCH_APL_REGISTRY -> real BorosEnergyMatchAPL
   pilot (Eldrazi Tron 35.5 -> 53.5 confirms it took effect).
3. OPEN: GrixisReanimatorMatchAPL crashes every turn (`list.remove(x): x not in list`, post-copy
   card-identity drift) -> degraded play, inverts a known-DOG matchup. Pre-existing, independent of
   this change. Tracked: IMPERFECTIONS.md `grixis-reanimator-match-apl-crashes-every-turn`.
4. OPEN: Gruul Broodscale (deck + APL) and the Mirror have no gauntlet row -- coverage gaps.
5. NOTE: No-regression numbers shifted from handoff claims (mirror 47.3->58.5, Jeskai 70->85.5,
   Selesnya-MonoG ~97->87); none inverted. Mirror 58.5 vs ideal 50 is a mild seat-bias flag worth a
   re-seed check.
6. OPEN (fidelity): opponent-side undermodeling inflates several lowcurve matchups (Affinity clock,
   Goryo's/Living End combos under-fire). The gauntlet cannot fully validate the primer until these
   improve. Lower priority than the Grixis crash (which inverts rather than inflates).

## Commit recommendation (EXPANDED after the match-engine fix)
COMMIT as one unit -- the calibration + engine-fidelity work is coupled:
  CODE: apl/aware_match_apl.py, apl/selesnya_landfall_standard_match.py, engine/game_state.py,
        engine/card_effects.py, engine/match_runner.py (battle-cry-in-match fix), apl/__init__.py
        (APL_REGISTRY + MATCH_APL_REGISTRY lowcurve lines)
  ARTIFACTS: decks/boros_energy_lowcurve_modern.txt, tests/test_pyrosurfer_battlecry_package.py
             (goldfish), tests/test_pyrosurfer_battlecry_match.py (match)
EXCLUDE run-cache (`data/sim_matchup_matrix.json`, `data/auto_apl_registry.json`,
`.claude/settings.local.json`) and `data/ab_counters_*` scraps. Do NOT push (user gates pushes).
Rationale: calibration gate in band (65.3%), both battle-cry tests GREEN, locked Modern baseline
provably untouched, gauntlet 0-crash over 1200 games, no-regression structurally proven (battle-cry
block is `if total_bc:` -> no-op for every non-Pyrosurfer/non-Signal-Pest deck).

## FOLLOW-UP FIXES (2026-06-29, second pass -- separate commit)
1. GRIXIS CRASH FIXED (apl/grixis_reanimator_match.py + tests/test_grixis_reanimator_no_crash.py).
   Root cause = APL double-implemented Persist (engine _persist_spell already reanimates; APL re-removed
   the already-pulled card -> list.remove crash -> turn aborted). Fix lets the engine own the move, fires
   ETB identity-guarded. VERIFIED the ETB targets the right creature: engine `_persist_spell` and the APL
   both `max(nonleg GY creatures, key=cmc)` over gs.zones.graveyard in identical order -> same object incl.
   ties (static equivalence). Crashes 29/200->0; matchup 81%->75.0%. STILL inverted vs primer 25-38% --
   the real cause is the new imperfection `combo-decks-not-sampled-in-gauntlet-run_match` (gauntlet's
   singular run_match never routes combo decks through ComboKillSampler), which also drives Goryo's/Living
   End inflation. Deferred as a gated shared-engine pass.
2. GRUUL BROODSCALE ADDED (decks/gruul_broodscale_modern.txt + apl/gruul_broodscale_match.py + registry).
   Fills the missing gauntlet row; loads 60/15, resolves, runs 0-crash. The 89% WR is a SYNTHETIC STUB
   (creature-deck APL, no infinite combo) -- NOT primer-validated; flagged in the deck header + APL docstring.
3. MIRROR SEAT-BIAS = NON-ISSUE. Prowess mirror = 51.0% at n=500 seeded (the 58.5 was small-n noise). No
   engine change. SEPARATELY, the seat-symmetric re-measure corrected the calibration number of record to
   60.7% (see CORRECTION at top).
4. PRIOR COMMIT 5f016c0 PROVEN INNOCENT on the Modern baseline: borosenergy-vs-izzetaffinity = 88.5% at
   BOTH parent 4151e86 AND 5f016c0 (identical) -> byte-identical, no regression. The historical "63.5% lock"
   does not reproduce (pre-existing Affinity-undermodeling); tracked as `locked-modern-boros-affinity-
   baseline-stale-63.5`. Lesson: re-measure "empirical" subagent claims; the first workflow's "63.5=63.5
   empirical" was fiction.
