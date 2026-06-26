---
title: GitHub Dig - AI / RL / Search / Solvers for MTG and Adjacent TCGs (search-layer / best-move path)
status: SURFACED
created: 2026-06-26
cluster: 2 (AI/RL/search/solvers/bots)
north_star_layer: search-AI (best-move quantification on mtg-sim)
related: ext-eval-mtg-engines-2026-06-26.md (engine/fidelity cluster - dedup source)
---

# GitHub dig: search/eval/self-play architectures for MTG + adjacent TCGs

Read-only discovery. Goal: find MCTS / ISMCTS / minimax / AlphaZero / determinization / Deep-MC
architectures we can adapt onto `mtg-sim/` to compute best move/sequence ("Stockfish for MTG").
Every NEW repo below was fetched live (GitHub API: repo meta + README + LICENSE file) on
2026-06-26. Licenses VERIFIED against the actual LICENSE file, not the description or the API
SPDX guess (two were wrong - see License discipline).

## Strategic delta vs the prior engine cluster
The prior cluster (`ext-eval-mtg-engines`) was all *reimplement-from-ideas* - the useful repos
were wrong-language (Kotlin/Java) or unlicensed; the complete one (Forge) is GPL/Java. **This
cluster is different: it surfaces actually-adoptable, permissively-licensed Python** that
implements the exact search-layer contract our Axis-B backlog needs. None of these close the
MTG *fidelity* gaps (warp, planeswalker loyalty, stack-priority) - only full engines do that.
This cluster serves the **search layer that sits on top of** a hardened forward model. Keep that
boundary clean.

---

## Dedup - already evaluated (prior doc), marked [known]
- **hlynurd/open-mtg** [known] - MIT, Python; `mcts.py`/`minimax.py` over a deterministic MTG
  forward model. Cleanest *small* search-shape reference. (Prior doc, repo #1.)
- **wanqizhu/mtg-python-engine** [known] - MIT; trigger/intervening-if model. (Prior #2.)
- **csce585-mlsystems/MTG-game-engine** [known] - NO LICENSE; draw simulator, not search. (#3.)
- **wingedsheep/argentum-engine** [known] - MIT, Kotlin; PUCT-MCTS + AlphaZero self-play +
  O(1) fork + hidden-info masking. The architectural blueprint. (Prior #4.)
- **Card-Forge/forge** [known] - GPL-3.0, Java; full engine + AI, validation-oracle only. (#5.)
- **DeepMind OpenSpiel** [known] - framework w/ MCTS/AlphaZero, no MTG game. Reference. (Prior, brief.)
- **arrdem/OpenSourcerer** [known] - older Python MTG+AI, low priority. (Prior, brief.)

None of the repos below appear in `thingstolookinto.md` or the prior eval docs - all NEW signal.

---

## NEW finds - deep-read top candidates

### 1. WillWroble/MageZero (+ mirror toastblademaster-arch/mtg-rl, + fork WillWroble/mage)  *** GOLD ***
- Stars 38 | updated 2026-06-19 | **MIT (verified)** | Python (framework) + Java (engine fork)
- **What:** "A Deck-Local AI Framework for MTG." Trains *per-deck* RL agents instead of one
  monolithic model. Uses XMage (complete MTG rules engine) as a gym env; Learning-MCTS in Java,
  PyTorch training, local python inference server. v0.1.0-alpha shipped (precompiled XMage + `mz` CLI).
- **Technique:** Learning-MCTS (MCTS guided by a learned value/policy net) + self-play. The real
  code is in the `WillWroble/mage` fork: `Mage.Player.AI.RL/` (`ComputerPlayerMCTS2.java`,
  `MCTSNode2.java`, `RemoteModelEvaluator.java` = the Java->python model bridge). State
  vectorization + remote NN leaf eval.
- **Reported results:** on punishing tempo decks, MCTS-only WR 16% -> RL 66%; avg ~48% vs a
  minimax pool (human est ~61%). Honest, small-scale, active alpha.
- **Layer:** search-AI. **Models our gap:** *deck-local decomposition == our APL-per-archetype
  structure.* This is the strongest transfer insight in the cluster: it validates that "each
  archetype is its own tractable subgame with its own policy/value net" is a real, working design
  - exactly what our `apl/*.py` already implies. Our APLs become per-deck warm-start policies.
- **V5 / Effort M (read+borrow design; engine is Java so no code lift) / Risk Low (MIT).**
- **How we'd use it:** adopt the deck-local framing - one lightweight search+net *per archetype*
  seeded by that archetype's existing APL, rather than one universal MTG bot. Read the fork's
  `RemoteModelEvaluator` for the Java/Python inference-bridge pattern if we ever wrap an engine.

### 2. suragnair/alpha-zero-general  *** the interface contract ***
- Stars 4471 | updated 2025-01-01 | **MIT (verified)** | Python (PyTorch + Keras)
- **What:** the canonical, minimal, well-commented AlphaZero template. "Any game, any framework."
  Subclass `Game.py` + `NeuralNet.py`; `Coach.py` = self-play loop, `MCTS.py` = the search.
- **Technique:** AlphaGo-Zero self-play (PUCT MCTS + policy/value net). Perfect-information by
  default (two-player turn-based), but the abstraction is the value.
- **Layer:** search-AI. **Why it matters:** `Game.py`'s interface (`getValidMoves`,
  `getNextState`, `getGameEnded`, `stringRepresentation`) *is exactly the contract our Axis-B1
  must satisfy* - `legal_actions(state)` + `apply(state,a)->state'` + `clone`. This is the spec
  to implement against, not a thing to fork wholesale.
- **V5 / Effort S (read; the API shape is the deliverable) / Risk Low (MIT).**
- **How we'd use it:** make `GameState` conform to this interface; then `MCTS.py`/`Coach.py` are
  ~300 lines of nearly-drop-in search+self-play on top. It is the reference skeleton for our
  `engine/search/`.

### 3. sirmammingtonham/alphastone  *** proof ISMCTS+AZ works on an imperfect-info card game ***
- Stars 30 | updated (older) | **Unlicense = public domain (verified)** | Python (PyTorch)
- **What:** AlphaZero applied to Hearthstone on the `fireplace` simulator. Built directly on
  suragnair/alpha-zero-general.
- **Technique:** **Information-Set MCTS** - randomizes all hidden info (opp hand+deck) before
  every search, runs MCTS on the current player's information set; small ResNet leaf eval
  (action-prob matrix + outcome). This is the concrete determinization recipe for hidden info.
- **Layer:** search-AI. **Maturity:** toy (author was a high-schooler; ~150-card basic set,
  priest-vs-rogue, beats random ~80%). Clean *reference*, not production. But it is the cleanest
  Python example of "alpha-zero-general + determinization for hidden info" = our B3 path made real.
- **V4 / Effort S (read; public domain so copyable) / Risk Low.**
- **How we'd use it:** the bridge example - how you bolt ISMCTS determinization onto the
  alpha-zero-general skeleton for an imperfect-info game. Direct template for B3.

### 4. datamllab/rlcard  *** the imperfect-info card-game RL toolkit ***
- Stars 3508 | updated 2026-06-26 (active) | **MIT (verified)** | Python
- **What:** mature toolkit "to bridge RL and imperfect-information games." Ships DouDizhu, Leduc,
  Texas, UNO, Mahjong, etc. with DQN, NFSP, CFR, and **DMC (Deep Monte Carlo)**. PettingZoo-compatible.
- **Technique:** standard env API (`step`/`reset`/legal-action mask) + a menu of imperfect-info
  RL algos including counterfactual regret (CFR) and DMC. Battle-tested, packaged on PyPI.
- **Layer:** search-AI / ML-classifier. **Why it matters:** reference implementations of the
  algorithm family that MTG needs (imperfect-info, large action space), in clean Python, MIT.
  Its env interface is another model for our `legal_actions`/observation contract.
- **V4 / Effort S-M / Risk Low (MIT).**
- **How we'd use it:** algorithm cookbook + interface reference; potentially wrap mtg-sim as an
  rlcard-style env to reuse its DMC/NFSP trainers instead of writing our own.

### 5. kwai/DouZero  *** the large-action-space fallback (DMC) ***
- Stars 4598 | updated 2026-06-26 (active) | **Apache-2.0 (verified)** | Python (PyTorch)
- **What:** ICML 2021. Masters DouDizhu (a large imperfect-info card game with a *huge,
  combinatorial action space*) via self-play **Deep Monte Carlo (DMC)** - no explicit game tree.
- **Technique:** DMC = sampled-action Monte Carlo + deep value net over (state, action) pairs.
  Crucially it sidesteps tree explosion, which is *the* risk for MTG (where a turn can branch on
  mana/targets/ordering into an enormous action space).
- **Layer:** search-AI. **Why it matters / NEW SIGNAL:** if MTG's per-decision action space is
  too large for explicit ISMCTS tree search, DMC is the proven alternative - learn Q(s,a) and act
  greedily/sampled rather than build a tree. Flag this as the search-layer Plan B.
- **V4 / Effort M / Risk Low (Apache-2.0).**
- **How we'd use it:** keep DMC in our back pocket; if `engine/search/` ISMCTS chokes on MTG's
  branching factor, pivot to DMC over (state, encoded-action) using the same APL-seeded data.

### 6. peter1591/hearthstone-ai  (architecture reference only - NO license)
- Stars 334 | **NO LICENSE FILE (verified - GitHub license API 404)** = all-rights-reserved | C++
- **What:** mature MCTS + deep-NN Hearthstone AI, explicitly modeled on AlphaGo, header-only C++
  engine + judge framework + MCTS agent.
- **Technique:** **Multiple-Observer MCTS** for hidden info; shares tree nodes for identical
  boards; NN as policy net + early-cutoff result estimator. High-quality ISMCTS-for-card-games design.
- **Layer:** search-AI. **License/transfer:** NO LICENSE = same trap as csce585; **reference
  only, copy nothing**, and it is C++ regardless. Read it to understand MO-MCTS + node-sharing
  + NN-early-cutoff, then clean-room reimplement in Python.
- **V3 (design reference) / Effort M (read) / Risk High if code touched - keep at arm's length.**
- **How we'd use it:** behavior/architecture reference for node-sharing and NN early-cutoff in
  an ISMCTS; informs B3+search design. No code reuse.

### 7. sbl1996/ygo-agent (+ predecessor sbl1996/yugioh-ai)
- ygo-agent: Stars 148 | updated 2024-08 | **NOASSERTION / "Other" (verify before any reuse)** | Python (JAX)
- yugioh-ai: **MIT (verified - API said NOASSERTION but the LICENSE file is plain MIT, (c) 2024 Hastur)**
- **What:** production-grade Yu-Gi-Oh RL. `ygoenv` (high-perf C++ env over ygopro-core) + `ygoai`
  (RL agents). Switched to **JAX**; PPO-style training + **LSTM** for sequence/history; self-play;
  human-vs-AI deployed in a real client (Neos). Predecessor `yugioh-ai` (MIT) was LLM+RL, now deprecated.
- **Technique:** large-scale self-play deep RL (policy-gradient/PPO + recurrent state) on a fast
  native env - the "wrap a real rules engine as a fast gym + train a recurrent policy" pattern.
- **Layer:** search-AI / MCP-tooling-adjacent. **Maturity:** production. **Transfer:** the env
  wrapper + distributed self-play architecture is the most production-mature in the cluster;
  recurrent policy is relevant because MTG decisions depend on game history. Resolve the ygo-agent
  license before lifting any code; the design is freely studyable.
- **V3 / Effort M-L / Risk Medium (license unresolved on ygo-agent) / Risk Low on yugioh-ai (MIT).**
- **How we'd use it:** template for "wrap mtg-sim as a fast env + distributed self-play"; LSTM
  policy idea if history-dependence matters.

### 8. crispy-chiken/YugiohAi
- Stars 50 | updated 2026-05-27 | **GPL-3.0 (verified)** | C# (game AI) + Python (deckbuild)
- **What:** learning bot on EdoPro/WindBot that aims to both build the best deck and play
  optimally. Two AIs: python deck-builder + C# in-game player.
- **Technique:** learning bot over a real client; notable for the **joint deck-selection +
  in-game-play** loop (most projects do only one). GPL-3.0 = copyleft, don't link/adapt code.
- **Layer:** search-AI. **V2 / Effort M / Risk High (GPL).**
- **How we'd use it:** idea reference only - the deckbuild+pilot joint-optimization loop mirrors
  our gauntlet+APL tuning; reimplement from concept, never copy.

### 9. Adjacent / minor (breadth, low priority)
- **robkinyon/mtg-solver** - 0 stars, 2025-11, no license, Python. Brute-force *goldfish* solver:
  enumerates every unique card-draw combination, plays vs a basic-land goldfish, emits a
  wins-by-turn histogram with combination-reduction to minimize games. Exhaustive enumeration,
  not best-move search; mildly relevant to validating our goldfish kill-turn distributions. V2/S/Low.
- **Alayers2804/Yugioh-MCTS-AI-Python-Program** - 0 stars, MCTS for Yu-Gi-Oh in Python; tiny,
  student-grade. Reference only.
- **jamestjw/rusty-duke** - Coup engine + **ISMCTS** in Rust; tiny but a clean compact ISMCTS
  example for a hidden-info game. Reference only.
- **Pokemon-TCG Kaggle cluster** (wmh/ptcg-abc, ronniepiku/pokemon-tcg-ai-battle-agent [Apache-2.0],
  liamw5265/ptcg-ai-battle-sim, ...) - active 2026 Kaggle "TCG AI Battle" agents; mostly rule-based
  + light RL, immature, but a live community building TCG agents worth a periodic re-scan. Low value now.

---

## License discipline summary (verified against actual LICENSE files)
| Repo | API said | Actual (verified) | Verdict |
|---|---|---|---|
| WillWroble/MageZero | MIT | **MIT** | Design borrow (engine is Java); attribute. |
| suragnair/alpha-zero-general | MIT | **MIT** | Interface contract; copyable. |
| sirmammingtonham/alphastone | Unlicense | **Public domain** | Fully copyable reference. |
| datamllab/rlcard | MIT | **MIT** | Copyable / wrap as env. |
| kwai/DouZero | Apache-2.0 | **Apache-2.0** | Copyable w/ notice. |
| peter1591/hearthstone-ai | (404) | **NO LICENSE = all rights reserved** | Reference ONLY, copy nothing. |
| sbl1996/yugioh-ai | NOASSERTION | **MIT** (file inspected) | Copyable; attribute. |
| sbl1996/ygo-agent | NOASSERTION/Other | **Unresolved (Other)** | Study only until license read in full. |
| crispy-chiken/YugiohAi | GPL-3.0 | **GPL-3.0** | Idea reference only; never link/copy. |

Genuinely code-adoptable (permissive, Python): **alpha-zero-general (MIT), rlcard (MIT),
DouZero (Apache), alphastone (public domain), sbl1996/yugioh-ai (MIT).**

---

## Technique -> our-layer map (the search path)
- **Interface/contract (B1):** alpha-zero-general's `Game.py`/`NeuralNet.py` defines the
  `legal_actions`/`apply`/`clone` contract our `GameState` must satisfy. Implement against it.
- **Hidden info (B3):** ISMCTS determinization (alphastone, hearthstone-ai MO-MCTS) - sample
  opp hidden zones, run MCTS per determinization, aggregate. alphastone is the copyable template.
- **Search core (B4):** PUCT-MCTS + small value/policy net (alpha-zero-general + Argentum[known]).
  APLs become the action-prior / rollout policy (warm start).
- **Large-action-space Plan B:** **DMC** (DouZero / rlcard) - learn Q(s,a), skip the explicit
  tree. The new signal this dig adds; keep as fallback if MTG branching breaks ISMCTS.
- **Deck-local framing (GOLD):** MageZero - one tractable search+net **per archetype**, seeded by
  that archetype's APL. Matches our existing structure; lowers the problem from "solve MTG" to
  "solve this deck," which is what our codebase is already shaped for.

## Honest boundaries
- None of these close fidelity gaps (warp, PW loyalty, stack-priority) - only full engines
  (XMage, Forge[known]) do. This cluster is the *search layer*, gated on our Axis-B1-B3 forward-model
  triad existing first.
- Maturity is uneven: alphastone = toy reference; MageZero = active alpha; rlcard/DouZero/ygo-agent
  = production. Grade accordingly when borrowing.

## Changelog
- 2026-06-26: Created (SURFACED). Cluster-2 dig. Live-fetched + license-verified MageZero
  (+fork +mirror), alpha-zero-general, alphastone, rlcard, DouZero, hearthstone-ai, ygo-agent,
  yugioh-ai, crispy-chiken/YugiohAi, mtg-solver, plus adjacent. Corrected two API license
  mislabels (yugioh-ai actually MIT; hearthstone-ai actually unlicensed). Deduped vs
  ext-eval-mtg-engines (7 known) and thingstolookinto.md (no overlap).
