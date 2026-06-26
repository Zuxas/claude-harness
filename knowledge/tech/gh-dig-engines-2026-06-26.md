---
title: GitHub Dig - MTG Rules Engines / Simulators / Clients (Cluster 1, vs our engine gaps)
status: SURFACED
created: 2026-06-26
---

# GitHub dig: full-rules MTG engines for closing our engine gaps

Read-only breadth+depth dig of GitHub for rules engines / simulators / game implementations,
scored against the five structural gaps in `mtg-sim/engine/` (stack/priority, hidden info,
instant-speed combat, planeswalker loyalty, warp). Companion to and dedup'd against
`ext-eval-mtg-engines-2026-06-26.md` (the prior deep eval). Every repo below was hit live via
`gh api` on 2026-06-26; licenses verified from the actual LICENSE file, not the description.

## Headline finding

**XMage (`magefree/mage`) is MIT-licensed, not GPL.** It is the second-most-complete open MTG
engine in existence (31,000 unique cards, 91,000+ reprints, *full rules enforcement* incl.
stack, priority, layers, replacement effects, hidden info), 2,293 stars, actively maintained
(pushed 2026-06-25). **It even implements both of our "gold" gaps: planeswalker loyalty
(core since 2007) and Warp** -- verified `WarpAbility.java` (6.7 KB) plus the Edge of Eternities
warp cards (FullBore, Starwinder, NovaHellkite, StarbreachWhale, ...). The prior eval covered
GPL Forge as a "behavior + oracle only" reference. XMage is the SAME tier of completeness but
**MIT**.

License precision (load-bearing): MIT-vs-GPL changes exactly ONE of the three uses. Running an
install as an AI-vs-AI **oracle**, and **clean-room reimplementing from understanding**, were
*already* fine under Forge's GPL (running and independent reimplementation are not restricted by
copyleft) -- on those two, XMage and Forge are license-equal. XMage's unique, real advantage is
narrow: **we may translate its actual Java source into our Python with attribution, with zero
copyleft contamination** -- something GPL forbade with Forge. It is still Java (no direct
linking). This is the one genuinely high-value new find in Cluster 1.

## Dedup note

Already evaluated in `ext-eval-mtg-engines-2026-06-26.md` (NOT re-listed): hlynurd/open-mtg [known],
wanqizhu/mtg-python-engine [known], csce585-mlsystems/MTG-game-engine [known],
wingedsheep/argentum-engine [known, the Kotlin blueprint], Card-Forge/forge [known, GPL oracle],
arrdem/OpenSourcerer [known], OpenSpiel [known]. Everything below is NEW signal.

---

## NEW finds worth listing

### 1. magefree/mage (XMage) -- MIT . Java . 2293* . pushed 2026-06-25  *** TOP NEW FIND ***
- What: Full-rules MTG engine + online client. 31k unique cards, full rules enforcement
  (stack, priority, the layer system, replacement effects, SBAs, hidden information, multiplayer,
  AI opponents). Effectively a complete CR implementation. Repo is ~971 MB (entire card pool).
- License: **MIT** (verified: LICENSE file = "MIT License, Copyright (c) 2010 betasteward").
- Layer served: **engine** (behavior reference) + **data-meta** (ground-truth oracle).
- Models our gaps? **All five, at very high fidelity** -- the two we most lack (real
  stack/priority loop, hidden-info masking), layers + replacement effects we haven't touched,
  AND both gold gaps: planeswalker loyalty + Warp (`WarpAbility.java` verified, EOE warp cards
  present).
- Value 5 / Effort: S to read a card's behavior, M to stand up as an oracle harness, L+ to
  port/translate a subsystem / Risk **Low** (MIT; just don't link Java into Python).
- How we'd use it: (a) authoritative behavior reference -- e.g. read `WarpAbility.java` + an EOE
  warp card to learn the correct delayed-return / alternate-cost interaction before we build our
  `KWTag.WARP` path; (b) the ONE MIT-unique move -- translate its loyalty / warp / priority code
  into our Python with attribution (forbidden under Forge's GPL); (c) external oracle -- run XMage
  AI-vs-AI for a matchup and compare combat outcomes / WR to catch our fidelity bugs (this use
  was already GPL-legal with Forge, so it is not the differentiator).

### 2. nymann/open-gathering -- NO LICENSE . Python . 0* . pushed 2026-05-10
- What: "An open-source gym for MTG -- a rules engine + game-state representation built for RL and
  search-based agents (minimax, MCTS, ISMCTS)." Explicitly chess-engine-architected: build state
  rep first, then move generator, then validate with `perft`, then layer search/learning.
  **Status per its own README: "Scaffolding only. No rules implemented yet."**
- License: NONE (all-rights-reserved; cannot copy -- though there is nothing to copy yet).
- Layer served: **search-AI** (architecture companion).
- Models our gaps? Aspirationally targets exactly Axis B (legal-action move-gen + ISMCTS), but
  has no implementation. Value is as **independent confirmation that our roadmap is the consensus
  shape**: it is a Python-native statement of the same "state-rep -> move-gen -> perft -> search"
  sequence Argentum encodes in Kotlin. The `perft` (move-generation correctness count, from chess)
  idea is a concrete testing technique we could adopt to validate a future `legal_actions(state)`.
- Value 2 / Effort S (read-only) / Risk Low. How we'd use it: borrow the **perft validation
  discipline** for our B1 legal-action enumerator; otherwise watch, don't depend.

### 3. fregaham/manaclash -- GPL-3.0 . Python . 3* . pushed 2015-07-14 (abandoned)
- What: A genuine, fairly complete Python MTG engine. Source tree shows real architecture:
  `game.py`, `rules.py`, `process.py` (turn/priority loop), `effects.py`, `abilities.py`,
  `conditions.py`, `selectors.py`, `cost.py`, `oracle.py`, plus `ai.py` AND `mc.py`/`mcai.py`
  (a Monte-Carlo AI). It is the closest thing to "what we are building" in pure Python.
- License: **GPL-3.0** (copyleft -- same trap as Forge; no code reuse).
- Layer served: **engine** + **search-AI** (design reference only).
- Models our gaps? Has a priority/process loop and a Monte-Carlo AI in Python -- directly
  relevant in shape to B2 (stack/priority) and the search layer -- but GPL + a decade stale.
- Value 2 / Effort S (read-only) / Risk High if code touched. How we'd use it: a free **Python**
  design reference for how to wire a priority `process` loop and a Monte-Carlo agent over an MTG
  state; reimplement from understanding only, never copy (GPL).

### 4. all-yall/autoarcana -- NO LICENSE . Rust . 0* . pushed 2024-02-22 (abandoned)
- What: "A Magic: The Gathering engine written in Rust." 133 KB of code; abandoned 2024.
- License: NONE. Layer: engine (curiosity only).
- Value 1 / Effort - / Risk High (no license). The only Rust full-engine attempt surfaced;
  Rust is interesting for a fast forking forward model, but with no license, 0 stars, and an
  abandoned tiny codebase there is nothing adoptable. Note and move on.

### 5. misprit7/magician -- NO LICENSE . Jupyter . 1* . pushed 2024-02-26
- What: "Neural-net-based Magic the Gathering AI." Notebook-scale experiment.
- License: NONE. Layer: ML-classifier / search-AI (curiosity).
- Value 1. Too small and unlicensed to use; logged only as evidence that the NN-policy-for-MTG
  space is thin and amateur outside Argentum's AlphaZero loop.

### Low-signal cluster (logged, not worth deep-read)
All 0-1 stars, stale, or no-license toy projects -- none model our gaps; listed so a future dig
does not re-spend cycles on them:
- marthinwurer/MTGEngine (MIT, Java, 2016, "creature-only engine for AI research" -- too narrow)
- segfaultec/MTGLib (C#, WIP, no license, 2020)
- kurokikaze/mtg-engine (JS, no license, 2014)
- masselin/Simulator (Python, no license, 2016, 20* but only 14 KB -- a goldfish/draw sim, not rules)
- therearedoors/mtg-rules-engine, snebel29/..., americoperez49/..., baabeln/hve-mtg (all empty/stub)
- heyhaigh/mtg-ai-match, zacharyelston/mtg-ai-suite, ladensbrand/NoN-MTG-AI-BoT, oglantz/MTG-Judge
  (2026 but LLM-wrapper / app-shell, not rules engines)
- theElandor/psim, michaelschuff/MTGSim, nikhilghosh75/project-planeswalker, rapolastrazdas/magic-sim,
  kenzo-bt/MTG2D (student/hobby sims, partial rules at best)
- JeremyGagnier/ElementalsTCG, robotaro/ygo_engine (other-TCG engines -- architecture-only curiosity)
- Cockatrice (excluded by design) -- popular client but a *no-rules-enforcement* tabletop sandbox;
  not a rules engine, never a behavior reference. Do not re-surface in a future dig.

---

## License + adoptability summary (new finds)

| Repo | License | Lang | Completeness | Verdict |
|---|---|---|---|---|
| magefree/mage (XMage) | **MIT** | Java | full (31k cards) | **Behavior reference + oracle; port patterns w/ attribution. Beats Forge (MIT vs GPL).** |
| nymann/open-gathering | NONE | Python | scaffolding only | Architecture companion; borrow `perft` validation idea; no code to use. |
| fregaham/manaclash | GPL-3.0 | Python | medium, stale | Python design reference for priority loop + MC AI; reimplement only, no copy (GPL). |
| all-yall/autoarcana | NONE | Rust | small, abandoned | Curiosity (only Rust engine); unusable (no license). |
| misprit7/magician | NONE | Jupyter | tiny | Curiosity (NN policy); unusable. |

## Net assessment

The Cluster-1 landscape is bimodal: two heavyweight, fully-correct engines (Forge GPL/Java,
**XMage MIT/Java**) plus the Kotlin Argentum blueprint already on file -- and then a long tail of
0-1-star hobby sims that model none of our five gaps. The actionable delta from this dig is
**one item**: XMage's MIT license unlocks the one thing Forge's GPL forbade -- **legally
translating its actual source (loyalty, warp, priority) into our Python with attribution**.
(Oracle use and clean-room reimplementation were already GPL-fine with Forge; XMage ties on
those.) It also implements both gold gaps (loyalty + Warp), so it is a concrete reference for the
exact subsystems we still owe. open-gathering and manaclash add minor Python
design-reference value (perft testing; a priority-loop + Monte-Carlo-AI shape) but no adoptable
code. No new engine changes the build plan: B1 (legal-action enum + O(1) fork) -> B2 (stack/
priority) -> B3 (hidden-info determinization) -> search remains the path, with XMage now the
oracle that can prove each step's output is correct.

## Changelog
- 2026-06-26: Created (SURFACED). Ran ~18 gh search passes (stars + updated) across engine/
  simulator/rules-engine/ai/rust/gym/tcg query variants; ~50 repos surfaced, deep-read the
  serious candidates. Key result: XMage verified **MIT** (LICENSE file), reclassifying it above
  Forge. Logged open-gathering (Python gym scaffolding, our roadmap), manaclash (GPL Python
  engine w/ MC AI), autoarcana (Rust, no license), magician (NN, no license); dedup'd against
  the prior ext-eval engines doc.
