---
title: "Puzzle trainer v0 -- outs-math drills + sim-mined single-turn KILL puzzles + Glicko-2 ratings"
status: "SHIPPED (v0 complete 2026-07-03: T1 + T2 goldfish + T3)"
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
  - "mtg-sim 7eb405f + mtg-meta-analyzer b8e70b6/307ebf5 (T2 goldfish SHIPPED 2026-07-03)"
  - "mtg-meta-analyzer 1367176 (T3 SHIPPED 2026-07-03: Glicko-2 puzzle ratings)"
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
- 2026-07-03 (cont.): **T2 built — goldfish slice** (user picked "1"=build T2;
  environment decision surfaced via AskUserQuestion, user away, proceeded on
  the recommended goldfish-first path per advisor de-risk). SCOPE HONESTY: v0
  T2 covers only the "how do I win from here" third — NOT the "slow them down /
  grind" stabilize third (later track). Environment = GOLDFISH not gauntlet
  (deviation from spec's gauntlet target, recorded here): rationale — goldfish
  has an INDEPENDENT lethal oracle (`gs.run_combat()` + `has_won`, engine's own
  combat, not the miner's power-sum → kills the T2-G1 circularity the advisor
  flagged) and single-APL determinism; the SAME pipeline (search → Scene export
  → JSONL bridge → replay gate) drops onto the gauntlet next by swapping the
  driver + adding a no-untapped-blocker filter (advisor's "both worlds" plan).
  DELIVERED: `mtg-sim/scripts/mine_lethal_puzzles.py` (hooks a deck APL's
  main_phase in goldfish; per position: skip trivial on-board lethal, bounded
  DFS [500-node budget] for a PLAY-DEPENDENT lethal line — "the winning line
  isn't obvious", the advisor's APL-bug filter; self-verifies each line replays
  to engine-lethal before recording = T2-G1 by construction; one-way GameState
  → analyzer-Scene dict serializer; JSONL out) +
  `mtg-meta-analyzer/scripts/import_lethal_puzzles.py` (JSONL → puzzle_inbox via
  save_inbox_candidates; scene+line+caveats in evidence) +
  `mtg-sim/tests/test_lethal_miner.py`. TINY-RUN DE-RISK (advisor: prove one
  before 500) on Boros Energy 20 games seed 42: 2 candidates (10% → ~50/500
  projected), 1 requires non-obvious sequencing; **T2-G3 determinism
  byte-identical across 2 runs**; cross-repo Scene.from_dict round-trip OK;
  import bridge → 2 rows in puzzle_inbox. HONEST CAVEAT carried in every
  candidate: puzzle "truth" is ENGINE truth (inherits the sim's known
  card-fidelity limits) + goldfish = open board (no blockers / no opp
  instant-speed interaction). T2-G2 (>=20/500) run in progress at time of
  writing. NOT YET: promote-from-synthetic-inbox GUI path (the inbox→author
  path currently rebuilds scene from a cached replay; synthetic goldfish
  candidates carry an embedded scene in evidence for a later small analyzer
  slice) — out of T2's spec deliverables, flagged as next.
- 2026-07-03 (cont.): T2-G2 PASSED + playability CLOSED. 500-game run
  (Boros Energy, seed 42): 42 candidates (>=20 gate; 5 non-obvious sequencing,
  37 cheapest-first), imported -> 42 find_lethal rows in puzzle_inbox. mtg-sim
  tests/test_lethal_miner.py green (determinism + structural T2-G1 + yield).
  Committed: mtg-sim 7eb405f (miner+test+CLAUDE), analyzer b8e70b6 (import
  bridge+docs). PLAYABILITY: Promote->Author now prefers an embedded scene
  (_prefill_from_evidence + optional pre-fill kwargs on PuzzleAuthorDialog);
  synthetic candidates promote into solvable Solve-tab puzzles (pre-filled
  question/solution/difficulty/keywords, human reviews+saves). Verified
  headless end-to-end (saved puzzle #49 renders); 21 existing puzzle tests +
  4 new promote tests green. T2 v0 (goldfish) is now mined AND playable.
  STILL OPEN: gauntlet (real-opponent) T2 slice + no-untapped-blocker filter
  (same pipeline); T3 Glicko-2 ratings.
- 2026-07-03 (cont.): **T3 SHIPPED -- Glicko-2 puzzle ratings** (analyzer-only;
  user picked track B to close v0). Each attempt is a one-game Glicko-2 match:
  correct = user win, incorrect = loss, partial = draw. DELIVERED:
  (1) new `puzzle_ratings` table (entity_type user|puzzle, mu/phi/sigma/matches,
  REAL cols for bit-exact round-trip) + `get_rating`/`upsert_rating` in
  `db/puzzles.py`; (2) `analysis/puzzles/rating_loop.py` -- REUSES
  `analysis.ratings._update_rating` (no reimplementation), cold-starts each
  puzzle's mu from difficulty stars (`1500 + (d-3)*150`, keeps default phi/sig),
  snapshots BOTH opponents' glicko2 coords before updating either (simultaneous,
  not sequential); (3) Solve-tab wiring in `gui/tabs/puzzles.py::_record_and_next`
  (best-effort try/except so a rating bug can't block "next puzzle"), user
  rating + last-attempt delta rendered in the session stats line.
  GATES: **T3-G1 PASS** (user AND puzzle updates match a hand-built
  single-game `_update_rating` call with LITERAL score/cold-start inputs --
  pins scale conversion + score direction + opponent identity, not just
  determinism); **T3-G2 PASS** (write-through + fresh-read round-trip bit-exact;
  next attempt continues from the persisted rating). Tests:
  `tests/test_puzzle_ratings.py` (11) + GUI smoke in `tests/test_puzzles_tab.py`
  (co-located with other Qt tests to dodge the offscreen-Qt Windows teardown
  crash). Full analyzer suite **412 passed, 2 skipped**.
  MID-EXEC AMENDMENT (advisor): T3-G1 was at risk of being vacuous if "expected"
  were computed via the same production wiring -> test now hand-constructs the
  opponent tuple with a literal score. Lesson candidate: "a wiring gate that
  reuses the production path to build its own expected value proves only
  determinism; construct the reference from literal inputs."
  KNOWN LIMIT (tracked, not hidden): rating farming -- re-solving an easy puzzle
  repeatedly still updates (spec directive: every attempt updates). Glicko damps
  it hard (a sunk puzzle yields ~0 and drops each loss) but it's not fully
  farm-proof. IMPERFECTIONS entry `puzzle-rating-farmable-on-reattempt` opened.
  **v0 COMPLETE** -> status SHIPPED. Follow-on tracks (NOT v0 gates): T2 gauntlet
  real-opponent slice + no-untapped-blocker filter; grind/stabilize puzzles.
