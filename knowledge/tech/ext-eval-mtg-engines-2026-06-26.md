---
title: External MTG Rules-Engine / Simulation Repos vs Our Engine Gaps (Stockfish-for-MTG path)
status: SURFACED
created: 2026-06-26
---

# External MTG engines evaluated against our engine gaps

Read-only research + spec. Evaluates external open-source MTG rules engines for closing the
five structural gaps in `mtg-sim/engine/` and for the longer "perfect-play bot" goal. Every
repo below was fetched live (GitHub page / README / LICENSE) on 2026-06-26. Our side was
assessed by reading the actual code, not the prior audit.

## Our five known gaps (source: harness/IMPERFECTIONS.md)

| Gap | Where it lives | Status in our code (verified) |
|---|---|---|
| `sim-no-stack-priority` | `engine/match_runner.py` `_run_player_turn` / `_simple_play_turn` | `engine/stack.py` exists (LIFO `Stack`, `InteractionType`, `classify_card`, `resolve_interaction`) but is **NOT wired** into the two-player runner. Counters are declarative mana reservations. ~40% of competitive matchups affected. |
| `sim-no-hidden-information` | `engine/match_runner.py` (lines ~409/416) | `TwoPlayerGameState` exposes `hand_a`/`hand_b`; APLs get full `opp_view.zones.hand`. Perfect-information play. |
| `sim-no-instant-speed-combat` | `engine/match_runner.py` `_resolve_combat` | Synchronous one-pass combat; no declare/respond windows. Mutagenic Growth is a special-case carve-out. Coupled to stack-priority. |
| `planeswalker-loyalty-not-tracked` | `engine/planeswalkers.py`, `engine/match_runner.py` | **Partially built, dead in match path** (see note below). |
| `warp-mechanic-not-modeled` | `engine/keywords.py`, `gs.cast_spell` | No `KWTag.WARP`, no alternate-cost path, no delayed end-step return trigger. 26 warp copies across ~28% of canonical Modern field. |

### Planeswalker-loyalty: discrepancy resolved
Two of our files disagreed. `engine/planeswalkers.py` (2026-04-26, built for the Ajani
*transform* arc) implies loyalty is fully modeled; `IMPERFECTIONS.md` (2026-05-02, later)
says it "is not tracked" and sizes the fix at 3-4 hr. I verified both:
- `data/card.py:77` — `loyalty: int = 0` field **exists**, initialized from `card_db`.
- `engine/planeswalkers.py` — `activate_planeswalker_ability()` exists with CR 606.3 per-turn
  budget + CR 704.5i zero-loyalty SBA.
- **But** `grep activate_planeswalker_ability` finds **no caller** in the engine — it is never
  invoked from `_run_player_turn`. `PLANESWALKER_ABILITIES` holds **one** entry (Ajani, Nacatl
  Avenger). Standard PWs (Chandra Spark Hunter `card_handlers_verified.py:1670`, Prof. Dellian
  Fel) are modeled as **one-shot ETB handlers** that "just place her as a 4-loyalty PW" and
  never tick.

Reconciliation: the infra was built for one goldfish/transform deck and never reached the
two-player match path. The 3-4 hr IMPERFECTIONS estimate is correct, not "S / just wire it."
Closing it = (a) wire activation into `_run_player_turn`, (b) populate the registry for every
Standard-field PW, (c) convert ETB one-shots to loyalty-setting, (d) add a per-turn
which-ability AI choice. Effort **M**, not S.

---

## Repo-by-repo evaluation

### 1. hlynurd/open-mtg  — MIT · Python · stale (2019)
Fetched: github.com/hlynurd/open-mtg + HN thread. **MIT** (per prior audit + repo). ~Python.
- **Models our gaps?** Stepped combat with explicit Declare-Attackers / Declare-Blockers /
  damage steps and multiple decision points (relevant to `sim-no-instant-speed-combat`).
  Priority is pass-based: "the player with priority is the currently acting player," `Pass`
  is a legal move (weak proxy for `sim-no-stack-priority`). **No** planeswalkers, **no** real
  stack object, **no** hidden-information layer. Rules coverage partial (lands + sorcery-speed).
- **The valuable part:** the **search/eval layer**. `mcts.py` (MCTS), `minimax.py`, and
  `random_policy.py` sit on top of a `game.py` that exposes legal-move generation. This is the
  cleanest small reference for "search over a deterministic MTG forward model" — exactly the
  shape our perfect-play goal needs.
- **Adoptable?** Ideas + the search-layer API shape, reimplemented in our Python (MIT allows
  copying, but the code is 2019 and won't fit our `GameState`; reimplement and attribute).
  **Value 4 / Effort M (for the search-shape port) / Risk Low.** Touches: a new
  `engine/search/` package, not existing engine files.

### 2. wanqizhu/mtg-python-engine  — MIT · Python · incomplete
Fetched: github.com/wanqizhu/mtg-python-engine. **MIT**. Aims to replicate the Comprehensive
Rules but only **56 / 256** M15 cards implemented.
- **Models our gaps?** Has a real **triggered-ability framework**: `onETB`, `onAttack`,
  optional targets with criteria, and **intervening-if** clauses (e.g. Ajani's Pridemate via
  `triggerConditions['onControllerLifeGain']`). Spells are `Play()` objects that `apply()` if
  uncountered with legal targets; illegal actions **rewind via deepcopy**. **No** PW loyalty,
  **no** hidden info, **no** AI/search.
- **The valuable part:** the **delayed/triggered-ability + intervening-if data model** is the
  closest external reference for the infrastructure `warp` needs (an end-step delayed return
  trigger, counterable, broken by blink). The deepcopy-rewind is a (slow) precedent for the
  cheap-fork problem MCTS needs solved properly.
- **Adoptable?** Code is too incomplete to lift; use as a **design reference** only.
  **Value 2 / Effort S (read-only) / Risk Low.** Informs `engine/keywords.py` +
  delayed-trigger work; copies nothing.

### 3. csce585-mlsystems/MTG-game-engine  — NO LICENSE · Python · the effects.json pattern
Fetched: github.com/csce585-mlsystems/MTG-game-engine. **No license stated** (confirmed; prior
audit flagged the same). 1 star, 46 commits.
- **Models our gaps?** **None of the five.** Despite the "rules engine" name, the Monte Carlo
  core (`simulation.py`) computes **draw probability only** — mulligans, scry, tutors/fetches,
  cantrips, draw-modifiers. No stack, no priority, no combat, no PW, no hidden-info layer. It
  is a draw simulator, not a rules engine.
- **The effects.json pattern:** `effects.json` is a seed effect catalog; `effects.py` enriches
  new cards at runtime via OpenAI (`OPENAI_API_KEY`) with a **regex deterministic fallback**.
  This is relevant to our **Gemma APL auto-generation** (the auto_pipeline / next-card flow),
  **not** to any engine gap.
- **Adoptable?** **No code may be copied (no license).** The seed-catalog + LLM-enrich +
  regex-fallback *idea* can be reimplemented for APL/handler auto-gen. **Value 2 (and only for
  auto-gen, not gaps) / Effort M / Risk Medium (license — reimplement-from-understanding only).**
  Does not touch the engine gaps at all; do not let its "engine" label mislead prioritization.

### 4. wingedsheep/argentum-engine  — MIT · Kotlin · the architectural blueprint  (NEW FIND)
Fetched: github.com/wingedsheep/argentum-engine + LICENSE (confirmed **MIT**, Vincent Bons /
wingedsheep). 22 stars, **7,902 commits**, ~500 cards, Kotlin (91.7%).
- **Models our gaps?** **All of them, properly.** Full turn structure + **stack** + spell
  resolution; combat (attackers/blockers/damage); triggered/activated/static abilities; CR 613
  layer system; replacement effects; state-based actions; targeting legality; and crucially
  **hidden information** (opponent hand + library **masked by default in the gym observation**).
- **The perfect-play part:** a Gymnasium RL env with exactly the affordances "Stockfish for
  MTG" needs — **immutable state with O(1) `fork()`**, `reset/step/observe/legalActions` API,
  **snapshot/restore** for tree search, batch stepping, a built-in **PUCT MCTS + AlphaZero
  self-play loop** with temperature scheduling, and an HTTP transport so Python agents can
  drive it.
- **Adoptable?** It is **Kotlin** — cannot link into our Python engine, and reimplementing a
  7,902-commit engine is not on the table. What IS adoptable (MIT, with attribution) is a set
  of **named patterns** to reimplement in Python: (1) immutable-state + O(1) `fork()`;
  (2) observation-with-hidden-info-masking; (3) the `reset/step/observe/legalActions` API
  *shape*; (4) PUCT-MCTS-with-determinization. Note: only ~500 cards and no Standard metagame,
  so it **cannot serve as a live oracle** for our field. **Value 5 (as the blueprint) /
  Effort: pattern-borrow S to read, L+ to build our equivalents / Risk Low (MIT).**

### 5. Card-Forge/forge  — GPL-3.0 · Java · oracle-validation only
Fetched: github.com/Card-Forge/forge. **GPL-3.0**, Java, 2.5k stars, **74,075 commits**,
the most complete open MTG engine in existence (full rules + AI + Adventure/Quest/Draft modes,
near-complete card pool, scripted-card system).
- **Models our gaps?** Yes — essentially all of them, to a far higher fidelity than we will
  reach soon.
- **Adoptable?** **No.** GPL-3.0 is a copyleft trap — adapting its code forces our project to
  GPL; and it is Java. Two safe uses only: (a) read its scripted-card behavior to understand a
  card's correct interaction, then **reimplement from understanding** (don't copy); (b) use a
  Forge install as an **external ground-truth oracle** — run Forge AI vs AI games to validate
  our sim's WR / combat outcomes (data comparison, not code reuse). **Value 3 (validation
  oracle) / Effort M / Risk High if code is touched — keep at arm's length.**

### Also surfaced (web search), brief
- **arrdem/OpenSourcerer** — Python MTG impl + AI; older, niche; not fetched in depth, low priority.
- **OpenSpiel** (DeepMind) — general game-AI framework with MCTS/AlphaZero, **no MTG game**;
  could *host* a search algorithm but you must supply the MTG game model, so it doesn't shortcut
  any gap. Reference only.

---

## License discipline summary

| Repo | License | Verdict |
|---|---|---|
| hlynurd/open-mtg | MIT | Adopt ideas + search-shape; reimplement; attribute. |
| wanqizhu/mtg-python-engine | MIT | Design reference (trigger/intervening-if model); copy nothing material. |
| csce585 MTG-game-engine | **NO LICENSE** | Ideas only, clean-room reimplement; never copy. Doesn't touch the 5 gaps anyway. |
| wingedsheep/argentum-engine | MIT | Borrow **named patterns** (fork/mask/gym-API/PUCT); reimplement in Python; attribute. |
| Card-Forge/forge | **GPL-3.0** | Do NOT link/adapt code. Behavior reference + external validation oracle only. |

Net: **every recommendation is reimplement-from-ideas, with attribution in code comments /
commit messages.** No direct code copy is advised for any repo (the MIT ones are wrong-language
or stale; the useful-language one is unlicensed; the complete one is GPL/Java).

---

## Which gaps to close first — two axes

The flat backlog mixes two different goals. Sequence by whichever north star the user picks.

### Axis A — Engine fidelity (makes WR numbers trustworthy; orthogonal to the bot)
1. **planeswalker-loyalty** — V4 / Effort M (3-4 hr) / Risk Low. Infra exists; finish it
   (wire `activate_planeswalker_ability` into `_run_player_turn`, populate registry for
   Standard PWs, convert ETB one-shots, add per-turn ability choice). **Borrow: nothing — this
   is ours to finish.** Cheapest high-confidence fidelity win. Touches `engine/planeswalkers.py`,
   `engine/match_runner.py`, `engine/card_handlers_verified.py`.
2. **warp-mechanic** — V4 / Effort M-L / Risk Medium. ~28% of canonical Modern field. Reimplement
   using wanqizhu's delayed/intervening-if trigger model as reference. Touches `engine/keywords.py`,
   `gs.cast_spell`, a new delayed-trigger framework, per-deck APLs.
3. **instant-speed-combat correctness** — folds into stack-priority (below); don't do standalone.

### Axis B — Perfect-play bot enablement (prerequisites for any search layer)
These must happen *in order*; each is a hard dependency of the next.
1. **Legal-action enumeration + cheap state fork** — V5 / Effort L / Risk Medium. We have no
   `legal_actions(state)` and our `GameState` is heavy (`copy.copy(c)` per game). Borrow
   Argentum's **immutable-state + O(1) `fork()`** pattern (MIT, reimplement). Foundational —
   nothing else in Axis B works without it. Touches `engine/game_state.py` / a new state shim.
2. **stack-priority as a decision framework** — V5 / Effort L / Risk Medium. Wire our existing
   `engine/stack.py` into a priority-pass loop in `_run_player_turn`; add
   `MatchAPL.want_to_counter(spell, gs, opp)` (default `False`), first callers `uw_control` +
   `jeskai_control`. Borrow open-mtg's pass-loop shape. This is the keystone — it also delivers
   instant-speed combat (Axis A #3) for free, since both need the same priority windows.
3. **hidden-information / determinization** — V5 / Effort L / Risk Medium. Borrow Argentum's
   **observation-masking** pattern: add `revealed_to_opponent: set`, build `_opp_view(gs)` that
   filters `opp.zones.hand`. Required before search is meaningful — MTG is imperfect-information,
   so the search must determinize (ISMCTS), not assume full visibility.
4. **search / eval layer** — V5 / Effort XL / Risk High. Only after B1-B3. See sketch below.

**Recommendation:** if the goal is the bot, do **B1 → B2(+combat) → B3 → search**, and treat
PW-loyalty/warp as parallel fidelity work that improves the eval signal but isn't on the
critical path. If the goal this quarter is trustworthy WR numbers for RC prep, do
**A1 (PW) → A2 (warp) → B2 (stack/priority)** and defer the full search layer.

---

## Is a search/eval layer (minimax / MCTS) the path to "best move/sequence"?

**Yes — that is exactly the Stockfish analogy, and both open-mtg (`mcts.py`/`minimax.py`) and
Argentum (PUCT MCTS + AlphaZero) confirm it's the right shape.** But it sits *on top of*
prerequisites we don't yet have, and MTG breaks the naive minimax assumption:

- **MTG is imperfect-information + stochastic.** Plain minimax/alpha-beta assumes a perfect-
  information deterministic tree. The correct family is **ISMCTS (Information-Set MCTS) with
  determinization** — sample the opponent's hidden hand/library from a belief distribution,
  run MCTS on each determinization, aggregate. This is why B3 (hidden-info) is a hard
  prerequisite, not a nice-to-have.
- **We have no game tree to search.** Our engine is **APL-driven** — each archetype is a
  hand-coded policy (`apl/*.py`), not a `legal_actions(state)` generator. MCTS needs the
  triad `legal_actions(state)` + `apply(state, action) -> state'` + `clone(state)`. We have
  none cheaply. That is B1.
- **State fork is expensive today.** `run_match()` does `copy.copy(c)` per game. MCTS forks
  thousands of times per decision; we need Argentum's O(1) fork pattern (B1).

### Sketch — how the search layer sits on top of mtg-sim

```
                 +-------------------------------------------------+
                 |  SEARCH LAYER  (new: engine/search/)            |
                 |  ISMCTS(root_infoset):                          |
                 |    for k determinizations of opp hidden zones:  |  <- B3 belief sampler
                 |      node = clone(state)                        |  <- B1 O(1) fork
                 |      while not terminal and budget:             |
                 |        a = PUCT_select(node.legal_actions())    |  <- B1 legal-action API
                 |        node = node.apply(a)                     |  <- B2 stack/priority resolves a
                 |      backprop(reward = win? terminal eval)      |
                 |    return argmax visit_count over root actions  |
                 +-------------------------------------------------+
                              |  uses, does not replace
                              v
   +----------------------------------------------------------------------+
   |  DETERMINISTIC FORWARD MODEL  (existing engine/, hardened by B1-B3)   |
   |  GameState.legal_actions()  apply(action)  clone()  observe(player)   |
   |  stack.py priority-pass loop  |  hidden-info masking  |  combat windows|
   +----------------------------------------------------------------------+
                              |
                              v
   +----------------------------------------------------------------------+
   |  POLICY/EVAL SEED  (existing apl/*.py)                                |
   |  APLs become the rollout/default policy + action-prior for PUCT,      |
   |  not throwaway. "Best move" = search output; APL = warm start.        |
   +----------------------------------------------------------------------+
```

Two practical notes:
- **APLs are not wasted.** They become the **default rollout policy / action prior** that warms
  up PUCT (AlphaZero-style), turning years of hand-tuning into the bot's starting strength.
- **Terminal eval can reuse the gradient-boosting win-probability model** already in the repo as
  the leaf evaluator, avoiding full rollouts to game end.

The search layer is the correct north star and is genuinely "Stockfish for MTG," but it is an
**XL** effort gated on B1-B3. Build the forward-model triad first; the search code itself is the
small part (open-mtg's `mcts.py` is ~a few hundred lines) — the engine hardening underneath is
the real work.

---

## Changelog
- 2026-06-26: Created (SURFACED). Live-fetched open-mtg, mtg-python-engine, csce585 MTG-game-engine,
  argentum-engine (new find, the architectural blueprint), Card-Forge/forge; cross-referenced the
  five engine gaps in IMPERFECTIONS.md against our actual code; resolved the PW-loyalty file
  discrepancy by grep (infra exists, never called in match path); delivered two-axis prioritization
  + ISMCTS search-layer sketch.
