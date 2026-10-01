---
title: "Strict simulation mode + label legacy engine output experimental (engine rebuild step 1-2)"
status: "SHIPPED"
created: "2026-09-30"
updated: "2026-09-30"
project: "mtg-sim (new engine/strict.py; 6 guarded sites in engine/; run_matchup.py, parallel_launcher.py, calibration/scoreboard.py; new fidelity.py)"
estimated_time: "M (~2 h)"
related_specs:
  - "harness/reports/codex-review-mtg-sim-2026-09-29.md (architecture review: migration steps 1-2)"
related_commits:
  - "mtg-sim 3494c17 (strict mode + labels + fidelity + tests), 240e53c (docs)"
supersedes: null
superseded_by: null
---

# Strict mode (user: "pivot to the engine rebuild, start with strict mode")

## Goal
A switch under which a published number is either a raw simulation from ONE engine with every card supported, or
an explicit error -- never a silently substituted, floored, fallen-back or half-resolved result. Default OFF, so
today's behaviour is byte-identical; plus every legacy output is labelled experimental.

## What silently alters results today (verified 2026-09-30, mtg-sim HEAD 5e8de84)
| Where | What happens | Strict behaviour |
|---|---|---|
| run_matchup `_run_fair` Path A | any Bo3 exception -> heuristic Path B on the OTHER engine (Esper Blink crash does this) | raise -> cell error |
| run_matchup `_apply_caps*` | our aggro deck floored to 25% (match and G1) | no floor |
| run_matchup `_real_match` (combo + Path B) | real match data substituted for the sim | off -> sim only (real data stays for the default mode) |
| run_matchup Path B / GoldfishAdapter / GenericMatchAPL | decks without a MatchAPL get a heuristic G1 + sb premium or a generic pilot | error: "no MatchAPL" |
| engine/card_effects ETB + spell dispatch | handler exception logged, game continues | raise |
| engine/effect_primitives dispatcher | primitive exception logged, game continues | raise |
| engine/bo3_match `_apply_sb` | sideboard failure -> pre-board deck | raise |
| engine/match_runner `_simple_play_turn`, post-combat | APL exception -> warning, turn continues (already raises under SIM_DEBUG) | raise |
| deck load | 54-card stubs, unresolved names, cards with NO handler silently do nothing | pre-flight refuses the deck (fidelity.py) |

## Change
- `engine/strict.py` (new, ~20 lines): `is_strict()` (env `MTG_SIM_STRICT=1`), `StrictModeError`,
  `reraise_if_strict(exc, where)`.
- 6 guarded sites in engine/ (card_effects x2, effect_primitives x1, bo3_match x1, match_runner x2): `if is_strict(): raise`
  inside the existing except blocks. Nothing else in engine/ changes.
- `fidelity.py` (root): `deck_fidelity(key, fmt)` -> per nonland card a tier: verified handler
  (engine.card_handlers_verified / engine.card_effects), AUTO (standard/sos_auto_handlers = parser approximation),
  family, keyword/vanilla (full_audit.is_vanilla), NONE. Strict pre-flight blocks: main != 60, sideboard > 15,
  unresolved card, any NONE-tier card, no registered MatchAPL (format-aware). AUTO/family are reported, not blocked
  (the per-deck fidelity manifest is migration step 6).
- run_matchup: strict branches per the table; result records `"strict"`, `"engine": "legacy:match_engine"`.
- parallel_launcher: `--strict` flag (sets MTG_SIM_STRICT for the subprocesses); saved JSON carries
  `"engine_status": "legacy-experimental"`, `"strict"`, and per-cell errors; the field WR is computed over OK cells
  only and reports coverage (% of field share that produced a result).
- calibration/scoreboard: markdown + JSON header `engine: legacy match_runner (EXPERIMENTAL)`.

## Blast radius
Default OFF: every existing command, test and number unchanged (gate T1 proves it). Strict ON: many launcher cells
will ERROR instead of producing a number -- that is the point; nothing downstream consumes strict output yet.
Risk: a guarded engine site placed wrong could raise in default mode -> T1 + full pytest catch it.

## Gates (pre-registered)
- T1 DEFAULT UNCHANGED: launcher Boros Energy (modern) and Selesnya Landfall (standard), n=1000, seed 42 -> every
  cell identical to the 2026-09-30 post-pilot runs (59.4 / 85.0); scoreboard cells identical; pytest 153/3/4 + new.
- T2 UNIT: strict raises at each guarded site (fault injected); run_matchup strict: no fallback, no floor, no real
  data, no generic pilot; fidelity blocks a 54-card deck, an unresolved card, a NONE-tier card.
- T3 STRICT BASELINE (the deliverable): fidelity report for every Modern + Standard field deck (tier counts, block
  reasons) and strict launcher runs for Boros Energy + Selesnya Landfall: cells OK / ERROR with reasons, coverage of
  field share. Prediction: Boros vs Esper Blink ERRORs (list.remove crash); >= 1 field deck blocked by fidelity;
  strict coverage < 100% in both formats.
- T4 LABELS: launcher JSON and scoreboard output carry the experimental label.

## Stop conditions
T1 any difference in default mode; a guarded site raising in default mode.

## Changelog
- 2026-09-30: PROPOSED; awaiting user sign-off for the engine/ edits (hot zone).
- 2026-09-30: user approved the engine/ edits as specced -> EXECUTING.
- 2026-09-30: SHIPPED (mtg-sim 3494c17, 240e53c; not pushed).

## Results
| Gate | Result |
|---|---|
| T1 DEFAULT UNCHANGED | PASS -- launcher Selesnya Landfall (17 cells) and Boros Energy (13 cells) identical cell-for-cell to the post-pilot runs (85.0 / 59.4); Standard scoreboard cells identical; matchup matrix content identical; pytest 161 passed (153 + 8) / same 3 failures / 4 errors |
| T2 UNIT | PASS -- tests/test_strict_mode.py 8 tests: each guarded site silent by default, raises under strict (fault injected); run_matchup strict: no floor, no real data, no Bo3 fallback; fidelity blocks 61-card, 54-card, no-handler and unresolved decks |
| T3 STRICT BASELINE | Izzet Prowess (modern): coverage 68.2%, FW over OK cells 85.3; errors: Esper Blink (list.remove crash), Golgari Yawgmoth (Walking Ballista ETB handler crash), Boros Energy / Amulet Titan / Ruby Storm (pre-flight). Selesnya Landfall (standard): coverage 69.3%, FW 84.8; errors: Four-Color Control (Resonating Lute ETB handler crash), Izzet Spellementals / Azorius Aggro / Jeskai Control / Izzet Control (unresolved cards). Boros Energy (modern): coverage 0% -- blocked by its own pre-flight (Umezawa's Jitte has no handler). Predictions: >= 1 deck blocked HIT (7 of 32); coverage < 100% in both formats HIT; "Boros vs Esper Blink errors" moot (Boros blocked first), the crash showed in the Prowess run instead |
| T4 LABELS | PASS -- launcher JSON engine_status "legacy-experimental" + strict + coverage_pct; scoreboard JSON/markdown "legacy match_runner (EXPERIMENTAL)" |

Fidelity pre-flight over the 32 Modern + Standard field decks: 25 OK, 7 blocked -- Boros Energy (Jitte: no handler),
Amulet Titan (61 cards), Ruby Storm (Pyromancer Ascension, Urabrask: no handler), Izzet Spellementals (Belion, the
Parched), Azorius Aggro (Abrupt Inquiry), Jeskai Control (Kinetic Hellion), Izzet Control (Avengers Disassembled;
Thor, God of Thunder -- main deck, also no handler).

## Mid-execution amendments
- A1: "unresolved" must mean an EXACT name match: CardDB.get fuzzy-matches, returning e.g. "_____", "Hellion",
  "Assemble" for cards the oracle DB lacks. `fidelity._resolves` accepts the full name, a DFC front face, or the
  single-slash split-card spelling ("Wear / Tear" -> "Wear // Tear", which CardDB resolves correctly).
- A2: test isolation -- other test modules set SIM_DEBUG=1 at import; the match_runner strict test clears it locally.

## Findings (all hidden in default mode)
- Missing oracle cards are silently replaced by fuzzy matches in EVERY mode: Izzet Control's main-deck Thor is played
  as the card "_____". Fix: refresh engine/card_db's Scryfall oracle file; make the loader refuse non-exact matches.
- Handler crashes swallowed by default mode: Resonating Lute ETB (ManaPool has no `floating`) -- 4C Control's Lute
  (cast ~500 times per 600 games) never worked; Walking Ballista ETB (`'int' object has no attribute 'get'`).
- Esper Blink APL crash (Codex #5) confirmed again; in default mode it silently falls back to the heuristic path.
- Boros Energy's Umezawa's Jitte does nothing (only two other decks' pilots implement Jitte).
- Next rebuild step (Codex migration 3): canonical turn / mulligan / mana / priority / stack / combat / SBA / win
  on small synthetic decks, replayable, with typed actions.
