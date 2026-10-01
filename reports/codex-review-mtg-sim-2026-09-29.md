# Codex review of mtg-sim -- 2026-09-29 (recorded, not yet acted on)

Source: Codex (Tom's CLI seat) review pasted by the user on 2026-09-29, while the 70% cap removal was requested.
Codex changed no files. Status column: what this Claude session had independently seen by then; everything else is
UNVERIFIED -- re-check each claim against the code before fixing (line numbers are Codex's, at mtg-sim ~47d5fba).

**Codex verdict:** Modern and Standard decks mostly load and run, but matchup percentages are not reliable enough for
serious deck evaluation: combo matchups, sideboarding, several APLs and parts of the mana model do not faithfully
simulate the chosen decks. Pioneer and Legacy are substantially incomplete.

| # | Sev | Finding (Codex) | Where (Codex) | Status 2026-09-29 |
|---|---|---|---|---|
| 1 | P0 | Combo matchups ignore the selected deck: `run_combo_matchup()` is called without our deck/format; the combo model simulates a hard-coded Humans list + kill distribution. ~21% of the normalised Modern field takes this route | run_matchup.py:96; engine/combo_model.py:67, :259 | **FIXED 2026-09-29 (mtg-sim fd0013f, spec 2026-09-30-combo-routing-fix)** -- was CONFIRMED in code. (consistent with launcher cells labelled `com`, e.g. Sultai Reanimator / Izzet Lessons 63.4 G1 for BOTH Landfall and Lessons in the Standard reruns -- identical G1 for two different decks is a strong hint it's true) |
| 2 | P0 | Sideboarding largely fictitious: runner uses the global playbook parser, ignores APL `SB_PLANS`; any non-empty plan labelled `"real"`. Modern: 70 non-empty plans, 0 real card swaps ("5.0%", "Hard" parsed as card names). Standard: 23 plans, 10 change the deck, every changed deck ends at 57/59/62 cards. Unknown cards silently skipped | run_matchup.py:142, :203; engine/sideboard.py:95 | **CONFIRMED + FIXED (validation) 2026-09-29** -- audit reproduced 70/0 and 23/10-illegal exactly; only validated plans are used now and 0 validate, so G2/G3 are preboard until real plans are written |
| 3 | P1 | Two active Standard decks use unrelated pilots: Four-Color Control -> Jeskai Control MatchAPL; Boros Dragons -> Azorius Momo MatchAPL (probe: 8 Mountains + Nova Hellkite stuck in hand) | apl/__init__.py:474, :485 | **FIXED 2026-09-30** (own pilots, spec 2026-09-30-proxy-pilots) |
| 4 | P1 | Control APLs waste counterspells proactively: Jeskai uses the generic cast-everything helper, which doesn't exclude counters; Three Steps Ahead cast into an empty stack in its own main phase | apl/jeskai_control_standard_match.py:161; apl/base_apl.py:291 | **CONFIRMED** (Jeskai proxy: ~930 empty-stack counters in 600 games); fixed for the 3 new pilots only -- Jeskai Control's own pilot still does it |
| 5 | P1 | Esper Blink deterministic crash: seed 124009, on the draw vs Boros Energy -> `ValueError: list.remove(x)`; spell resolution removes the target, APL removes it again. run_matchup's broad except can hide it by falling back to heuristic results | apl/esper_blink_match.py:142; run_matchup.py:211 | **CONFIRMED 2026-09-29; strict mode (2026-09-30) now errors the cell instead of falling back** (Boros vs Esper Blink launcher log: `Bo3 failed ... list.remove(x)`; falls to the fallback path) (note: Esper Blink re-entered the Modern field today) |
| 6 | P1 | Pioneer + Legacy fields unusable: Pioneer 6 missing decks, 3 undersized generic lists, several entries load Modern/Standard decks; Legacy 6 missing, 5 undersized, the rest load other formats' decks. Alias fallback in the registry | apl/__init__.py:563 | PARTLY CONFIRMED (Pioneer "Izzet Prowess" loads the Modern deck; Legacy "Dimir Tempo" = 54-card stub) |
| 7 | P2 | Mana banked across turns: match engine intentionally doesn't empty pools at cleanup; favours interactive decks, distorts hold-up-mana decisions | engine/match_engine.py:356 | UNVERIFIED (check whether match_runner, the path decisions use, shares it) |
| 8 | P2 | bo3_gauntlet.py doesn't play two-player games (goldfish-clock race model); real APL play is parallel_launcher -> run_matchup -> match engine, fair opponents only | bo3_gauntlet.py:127 | CONFIRMED (already labelled "RACE MODEL" 2026-09-29) |

**Coverage/tests (Codex):** all 14 Modern + 18 Standard field entries load a match class; most sampled games complete,
but running is not correct piloting. `test_apls.py` accepts undersized 59/54-card decks. `test_response_capability.py`
fails because `Dismember` was added to apl/gruul_broodscale_match.py:94 without updating the pinned whitelist (this is
one of the 3 "baseline" pytest failures).

**Codex's recommended repair order:** combo routing -> sideboard integration + validation -> wrong Standard APL
mappings -> counterspell handling -> Esper Blink double-removal.

**Interaction with today's work:** the 70% cap removal (spec 2026-09-30-remove-credibility-cap) only touches the fair
paths; combo cells (#1) and the sideboard plans (#2) are unchanged by it, and both bias every launcher number.

## Additional findings (Codex, pasted by the user 2026-09-30) -- recorded, not yet acted on (all UNVERIFIED unless noted)
Codex's updated conclusion: fixing individual APLs alone will not make outputs trustworthy; the production Bo3
route must first be consolidated onto ONE tested engine, then mulligan, life sync, combat, turn lifecycle and
per-game state isolation.

| # | Sev | Finding (Codex) | Where (Codex) | Status |
|---|---|---|---|---|
| A1 | P0 | Production "real Bo3" imports `match_engine.py`; newer systems + tests (e.g. menace) target `match_runner.py` -> the tests don't cover the production Bo3 combat path | engine/bo3_match.py:28; tests/test_menace_combat.py:18 | **CONFIRMED 2026-09-30** (bo3_match imports match_engine.run_match) -- if true, the scoreboard (run_match = match_runner) and the launcher (run_bo3_set = match_engine) measure DIFFERENT engines |
| A2 | P0 | London mulligan double-penalised: after a mulligan draws 6 then bottoms 1 (one mull kept 5; two can leave 3) | engine/match_engine.py:35 | UNVERIFIED |
| A3 | P0 | APL direct damage via `gs.damage_dealt` never reaches opponent life in match_engine (the WANTS_BURN sync exists only in match_runner:276); Mono Red Bolt probe: tracker 3, opponent still 20. Affects Mono Red, Affinity, Izzet Prowess, Broodscale, Yawgmoth, Boros Energy ... | engine/match_runner.py:276 vs match_engine.py | UNVERIFIED |
| A4 | P1 | Attackers are never tapped (free vigilance) | engine/match_engine.py:461 | UNVERIFIED |
| A5 | P1 | First strike wrong: blockers deal damage in every strike pass (2/2 first striker vs 2/2 both die) | engine/match_state.py:352 | UNVERIFIED |
| A6 | P1 | Noncreature permanents can attack/block (filter is "not a land", not Tag.CREATURE) | apl/match_apl.py:385, :474 | UNVERIFIED |
| A7 | P1 | Menace ignored by production blocking; indestructible dies to combat damage; generic interaction resolver removes hexproof/ward creatures without legality checks | engine/stack.py:277 | UNVERIFIED |
| A8 | P1 | Turn lifecycle bypassed: match_engine rebuilds turns without GameState.run_turn()/_end() (upkeep, sagas, resets, impending/warp/dash/token cleanup) -> each APL must reimplement | engine/game_state.py:315, :695 | UNVERIFIED (note: the 2026-09-29 Dash fix went into match_runner's end step) |
| A9 | P1 | APL state leaks between games/matches: G1-G3 reuse APL instances; reset clears few attributes (Ajani transform, Blink energy/Fable, Prowess Cori flag) | engine/bo3_match.py:126; match_engine.py:320 | UNVERIFIED |
| A10 | P1 | Wrong play/draw status in half the games: A always built on_play=True, B False | engine/match_state.py:103 | UNVERIFIED |
| A11 | P1 | More stale pilots: Modern Dimir Midrange -> Izzet Murktide proxy (ignores Frog, Push, Bowmasters, Thoughtseize, Kaito, Subtlety, Riddler); Modern Mono Red is a Boros Burn list but BURN_FACE excludes Boros Charm / Helix / Roiling Vortex / Skewer (Boros Charm left in hand with 3 mana) | apl/__init__.py:370; apl/mono_red_match.py:31 | PARTLY CONFIRMED (refresh spec: Dimir -> MurktideMatchAPL; Mono Red old list = Boros Burn) |
| A12 | P1 | Sorceries castable on the opponent's turn (reactive interaction admits sorceries) | engine/match_engine.py:96 | UNVERIFIED |
| A13 | P2 | Decking skipped (draw from empty library ignored); equal-life timeouts always award B (20-20 zero-turn probe -> B wins) | engine/match_engine.py:396, :597 | UNVERIFIED |
| A14 | P2 | Published % post-processed: aggro decks floored to 25% | run_matchup.py:251 | CONFIRMED; disabled under strict mode (2026-09-30); still on by default |

## Architecture review (Codex, pasted by the user 2026-09-30) -- recorded, not acted on
Verdict: model legal games first, then let players choose among legal actions. Today APLs act as player, rules
engine and card implementation at once, so matchup percentages cannot be interpreted cleanly. Stop tuning win rates
and APL thresholds until there is ONE authoritative engine.
Acknowledged fixed: combo routing, sideboard validation, own pilots for 4C / Dragons / Modern Dimir, credibility cap.
Critical blockers:
1. Two incompatible engines (match_engine.py:292 Bo3, match_runner.py:1750 fallback) with different state + mechanics.
2. run_matchup.py:214 catches any Bo3 exception and silently falls back to the other engine (Esper Blink crash,
   esper_blink_match.py:142, still deterministic).
3. match_engine turn loop bypasses GameState.run_turn / _end (sagas, dash, warp, impending, temporary effects).
4. Rules wrong: London mulligan (match_engine:35), mana carries across turns (:356), attackers never tapped (:461),
   first-strike blockers damage twice (match_state:352), on_play hard-coded (match_state:103), empty-library draws
   do not lose; hexproof/ward/protection/indestructible/menace/targeting/timing incomplete.
5. APLs mutate game state directly (remove permanents, change life, make mana, move cards) -> the engine cannot
   guarantee legality. (Includes the 3 new pilots.)
6. Card "coverage" is often approximation (oracle_parser.py:792 turns free casting into draws; effect_primitives.py
   fails silently). rules_engine.py is a rules-text index/codegen, not a runtime referee.
Also: the 25% aggro floor (run_matchup.py:245) still post-processes results.
Recommended architecture: one canonical Game -> legal_actions(seat) -> Policy chooses a typed Action -> engine
validates + applies -> events/triggers/priority/SBAs. Engine owns every zone change, payment, target, trigger, combat
assignment and life change; policies get observations, never mutable state; stable object IDs; priority + stack
always on; unsupported effects fail loudly in strict mode; per-game RNG + append-only event log (replay);
hidden-info observations; fresh policy per Bo3 game.
Player skill in the policy layer only: ScriptedPolicy (current APL knowledge), SearchPolicy, HumanSkillPolicy
(calibrated error), OptimalReferencePolicy. Skill changes decisions, never rules.
Migration order: (1) freeze both engines as legacy, label outputs experimental; (2) strict mode: no fallback, no
floors, no silent exceptions, no unsupported effects; (3) canonical turn/mulligan/mana/priority/stack/combat/SBA/win
on small synthetic decks; (4) typed action interface replacing APL mutation (engine/decision_api.py:26 is a
prototype; legality checks need replacing); (5) one real matchup end to end, then Bo3 + sideboarding; (6) per-deck
fidelity manifest; (7) only then APL tuning, search, skill calibration, matchup matrices.
Immediate goal: one fully replayable, rules-correct game between two small decks with zero policy mutation and zero
fallback.

### Migration progress
- 2026-09-30: steps 1-2 DONE -- legacy outputs labelled experimental; strict mode (no fallback, floors, real-data
  substitution, swallowed exceptions, unsupported/unresolved cards). Spec specs/2026-09-30-strict-mode.md.
- 2026-09-30: card identity gate DONE (Codex's card-data-first step) -- exact names in every mode, versioned
  Scryfall snapshot; spec specs/2026-09-30-card-identity-gate.md. Next: canonical-engine design spec.
