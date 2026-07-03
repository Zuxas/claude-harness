---
title: "Puzzle trainer v0 -- outs-math drills + sim-mined single-turn KILL puzzles + Glicko-2 ratings"
status: "EXECUTING (user-directed 2026-07-03)"
created: "2026-07-03"
updated: "2026-07-03"
project: "mtg-meta-analyzer + mtg-sim (T2 mining side)"
estimated_time: "L overall; v0 = 1-2 Opus sessions per BLUEPRINT WP-D D7 (no WP-B dependency)"
related_specs:
  - "harness/specs/2026-07-01-b1-legal-action-api.md (decision_api seam T2 consumes; multi-turn rollout WP-B#5 is ITS territory, explicitly NOT v0)"
related_findings:
  - "E:\\vscode ai project\\BLUEPRINT-2026-07-03.md (WP-D -- source scope; D7 build order defines this v0)"
  - "Willis 'Calculating Outs' doc (cited in BLUEPRINT WP-D D1d -- hypergeometric drill pedagogy)"
related_commits:
  - "mtg-meta-analyzer 6f46c19 (T1 SHIPPED 2026-07-03: outs-math drills + grade_number)"
supersedes: null
superseded_by: null
branch: "mtg-sim work on modern-postban-arc; analyzer on its default branch"
---

# Puzzle trainer v0 (BLUEPRINT WP-D, scoped per D7 build order)

## Product intent (Jermey's words, from WP-D)

Game-driven training: "what the fuck do I do now", "how can I win from this
position", "how do I slow my opponent down and still progress my gamestate".
v0 delivers the two no-dependency pipelines (outs-math drills, sim-mined
single-turn KILL) plus the rating loop, on top of the ALREADY-SHIPPED
Puzzles tab scaffolding. Everything below is scoped against recon facts
verified 2026-07-03 -- no aspirational claims.

## Verified current state (recon 2026-07-03 -- cite, don't re-derive)

**Analyzer side (exists, reuse):**
- `gui/tabs/puzzles.py` (374 lines): Solve + Inbox sub-tabs;
  `puzzle_scene.py` MTGA-style board renderer; free-text answer entry.
- Grader chain in `analysis/puzzles/graders.py`: keyword rapidfuzz>=80
  first, Haiku LLM fallback.
- `db/puzzles.py:17-64` schema: `puzzles` (16 cols incl. category,
  difficulty, scene_json, grading_mode), `puzzle_attempts`, `puzzle_inbox`.
- `analysis/ratings.py`: Glicko-2 with reusable `_update_rating` (line 92).
- Scanner `analysis/puzzles/scanner.py` over 22 cached transcripts.
- Current inventory: 8 puzzles / 2 attempts / 0 inbox rows.

**Sim side (exists, with hard limits that BOUND v0):**
- `decision_api.py`: `legal_main_actions` (PLAY_LAND / CAST / PASS,
  generic-mana costing only) + `apply_action` + deepcopy fork.
- NO GameState<->JSON serialization exists (T2 must build a one-way
  Scene-compatible export; full round-trip is NOT in scope).
- `engine/evaluator.py` has clock / turns-to-lethal; the lethal check is
  naive `our_power >= opp_life` (no blocker math) -- T2 gates account for
  this honestly rather than pretending otherwise.

## v0 tracks

### T1: outs-math drill generator (analyzer) [D1d]

New category `drill_outs`. Generator produces hypergeometric scenarios per
the Willis "Calculating Outs" doc cited in the blueprint: looks-vs-outs
("N looks at M outs -- odds of hitting?") and keep-or-bottom scry
decisions. Deck contents are sampled from REAL decklists in mtg_meta.db
(house rule 8: never fabricate; attribute the source decklist). Grading
uses exact-number / keyword mode through the existing grader chain (no LLM
needed for pure-math answers). Difficulty tiers assigned by scenario
complexity (single-draw < multi-look < scry-with-bottoming < compound).

**Deliverables:**
1. `analysis/puzzles/drill_generator.py` (or house-consistent module name):
   scenario sampler + hypergeometric solver + explanation text that teaches
   the looks*outs shorthand explicitly (WP-D D1d).
2. Seeding run: 30+ drills inserted into `puzzles` with category
   `drill_outs`, scene_json rendering via existing puzzle_scene, difficulty
   tiers populated, decklist attribution stored.
3. Unit tests incl. the math-verification harness (gate below).

**Gates (pre-registered, falsifiable):**
- T1-G1 MATH: generate 100 random drills; every stated probability matches
  `scipy.stats.hypergeom` to within float tolerance. ZERO mismatches.
  Any mismatch: STOP, fix the solver, never fudge the tolerance.
- T1-G2 SEED: >=30 drills in `puzzles`, all grading as exact-number/keyword
  (no Haiku fallback needed for a well-formed numeric answer), each with a
  real-decklist attribution row.

### T2: sim-mined single-turn KILL puzzles (mtg-sim + export) [D1a]

Instrument the gauntlet at main phase: fork the state (deepcopy fork,
as-is), enumerate `legal_main_actions` orderings (BOUNDED -- cap the
enumeration; document the cap), and flag positions where lethal-this-turn
exists under SOME casting order but NOT under the APL's default line
(i.e. even our bot gets it wrong = interesting, per WP-D D1a). For each
candidate, serialize a Scene-compatible dict (names / life / lands /
creatures / hand) to JSON -- this is a new one-way exporter; no
GameState<->JSON round-trip exists or is built here. Export candidates into
the analyzer `puzzle_inbox` with evidence: the winning cast order + eval
delta from engine/evaluator.py. Lethal detection inherits the engine's
naive `our_power >= opp_life` check -- v0 mines main-phase CAST/PLAY_LAND
sequencing lethality, and the known blocker-math blindness is carried as an
honest limitation in every exported evidence blob.

**Deliverables:**
1. Mining harness in mtg-sim (script or gauntlet flag) that forks at main
   phase, enumerates bounded orderings, and detects APL-missed lethal.
2. Scene-export serializer: GameState -> Scene-compatible dict -> JSON.
3. Inbox bridge: candidates land in analyzer `puzzle_inbox` with
   solution line, eval delta, seed, and source-game provenance.

**Gates (pre-registered, falsifiable):**
- T2-G1 LEGALITY (WP-D D6#1): 100% of exported solutions REPLAY via
  `apply_action` from the forked state to lethal, zero illegal steps,
  zero failures on the shipped batch. Any failure: STOP, findings.
- T2-G2 YIELD: >=20 candidates into puzzle_inbox from a 500-game mining
  run. If yield is lower, report the real number -- do not loosen the
  eval-gap/missed-line criteria to hit 20.
- T2-G3 DETERMINISM: seed pinned (house protocol seed=42,
  PYTHONHASHSEED=0); same mining run twice yields identical candidate
  sets. Note: P1-style byte-identity instrument applies; known P2
  same-seed drift is pre-existing (13 global-random sites, WP-B
  territory) -- mine on configurations demonstrated byte-stable.

### T3: puzzle rating loop (analyzer) [D4]

New table `puzzle_ratings` carrying user_rating, per-puzzle rating, RD,
and volatility. Every attempt (win/loss vs the puzzle) calls the existing
`_update_rating` (analysis/ratings.py line 92) -- reuse, do not reimplement
Glicko-2. Cold-start each puzzle's rating from its difficulty stars.
Surface the user's current rating in the Solve tab.

**Deliverables:**
1. Schema migration adding `puzzle_ratings` alongside db/puzzles.py tables.
2. Attempt hook: puzzle_attempts insert triggers a `_update_rating` call
   for both user and puzzle ratings.
3. Solve-tab rating display (minimal: current rating + delta after solve).

**Gates (pre-registered, falsifiable):**
- T3-G1 MATH: rating updates validated against analysis/ratings.py
  reference cases -- identical outputs for identical inputs (it IS the
  same function; the gate proves the wiring, not the math).
- T3-G2 PERSISTENCE: ratings survive app restart (write-through to
  puzzle_ratings, re-read on launch; test asserts round-trip).

## Boundaries -- explicitly OUT for v0

- NO legal-action picker UI -- free-text answers + existing grader chain
  stay. (D5's decision_api-as-input-widget is a later slice.)
- NO multi-turn puzzles (NAVIGATE/TEMPO) -- hard dependency on WP-B#5
  resumable step()/rollout; v2 per D7.
- NO personal-puzzle mining from the user's own games (D1b) -- v1.
- NO historic/classics pack (D1c) -- v3.
- NO spaced repetition / daily feed (D4 re-queue) -- v0.1.

## Git discipline

File-scoped adds ONLY (house rule 5 -- never `git add -A`; other
agents/sessions share these repos). mtg-sim work lands on
`modern-postban-arc`. Analyzer + harness commits name their exact files.
Post-commit graphify hook output is normal.

## Evidence citations

- BLUEPRINT-2026-07-03.md WP-D (D1a, D1d, D4, D6, D7) -- scope source.
- Recon 2026-07-03 (this spec's "Verified current state") -- file:line
  facts: gui/tabs/puzzles.py (374L), analysis/puzzles/graders.py,
  db/puzzles.py:17-64, analysis/ratings.py:92, analysis/puzzles/scanner.py,
  decision_api.py legal_main_actions/apply_action/fork, engine/evaluator.py
  clock + naive lethal.
- Willis "Calculating Outs" doc (per blueprint citation) -- T1 pedagogy.

## Changelog

- 2026-07-03: Created, status EXECUTING (user-directed 2026-07-03).
  WP-D scoped to v0 per D7: T1 drills + T2 sim-mined single-turn KILL +
  T3 Glicko-2 ratings. Boundaries pinned; gates pre-registered before any
  build work.
- 2026-07-03: **T1 SHIPPED** (mtg-meta-analyzer 6f46c19, committed local;
  push blocked by git-guardrail, user to push). Delivered: `drill_outs`
  category; `analysis/puzzles/drill_generator.py` (raw / scry-keep-or-bottom
  / compound templates, all 5 tiers, real-decklist sampler
  deck_cards->cards->card_data with attribution in notes); NEW
  `graders.py::grade_number` + `grading_mode="number"` accepting the
  [exact, looks*outs-shorthand] band +/-3pp (fixes fuzzy-numeric
  false-positive — the spec's stated "exact-number" grader that did not
  previously exist); `scripts/seed_drills.py` (40 seeded); Solve-tab
  "Outs math" filter. GATES: **T1-G1 PASS** (solver vs independent
  sequential-product oracle AND scipy, 100 cases, 0 mismatch — oracle is
  math.comb-independent per advisor); **T1-G2 PASS** (30 drills
  well-formed, grounded, deterministic; difficulty spread 1-5). Headless
  render smoke PASS (boardless drill scene renders in PuzzleSceneWidget).
  29/29 puzzle-suite tests green.
  MID-EXEC AMENDMENT (methodology): advisor caught that the outs-math drill
  would fight its own lesson if graded exact-only (the taught shorthand
  overshoots exact) -> grader accepts the whole band. Lesson candidate for
  spec-authoring-lessons: "when a drill teaches an approximation, the grader
  must accept the approximation it teaches."
  ALSO FIXED (ops, out of original scope): machine-level MTG_META_DB /
  MTG_META_ARCHIVE_DB pointed at the dead D:\mtg-data (temp movie drive,
  now gone; live DBs are on E:\mtg-data, config.ini agrees). Added
  User-scope override -> E:; Machine-level vars still need an elevated
  `setx /M` to clear (documented in analyzer NEXT_STEPS.md). This was
  blocking the T1-G2 seed gate.
  STILL OPEN: T2 (sim-mined positional puzzles — the headline
  "what do I do from here" track) and T3 (Glicko-2 ratings). Spec stays
  EXECUTING.
