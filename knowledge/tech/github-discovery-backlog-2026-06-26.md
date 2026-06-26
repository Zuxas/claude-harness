---
title: GitHub Integration Backlog (synthesized from 4 discovery digs)
status: SURFACED
created: 2026-06-26
sources:
  - gh-dig-engines-2026-06-26.md (Cluster 1 - engines/sims)
  - gh-dig-ai-search-2026-06-26.md (Cluster 2 - AI/RL/search)
  - gh-dig-data-meta-2026-06-26.md (Cluster 3 - data/deck/meta/classify)
  - gh-dig-mcp-tooling-2026-06-26.md (Cluster 4 - MCP/APIs/productization)
dedup_against:
  - thingstolookinto.md (2026-06-21)
  - ext-eval-mtg-engines-2026-06-26.md
  - ext-eval-mcp-composition-2026-06-26.md
  - ext-eval-ml-calibration-2026-06-26.md
north_star_layers: [engine, search-AI, data-meta, ML-classifier, MCP-tooling, productization]
verdict_legend: "adopt | reference-only | reimplement-with-attribution | skip-GPL | skip-stale"
---

# GitHub Integration Backlog - one ranked list across all four digs

Single ranked backlog merging the four 2026-06-26 GitHub discovery digs. Grouped by
north-star layer; within each layer ranked by Value/Effort. Every repo carries a
**license** and a **verdict**. `[known]` = already in thingstolookinto.md or an ext-eval
doc; logged for completeness, not new signal. License verdicts are carried from the source
digs (each verified against the actual LICENSE file on 2026-06-26).

Within a layer, rows are ranked by Value/Effort, with ties broken toward adoptable
(permissive-license) repos - this is an integration backlog, so a usable MIT/Apache repo
outranks an equally-valuable no-license study-only one.

Verdict legend: **adopt** (permissive, use/vendor/compose directly) | **reference-only**
(no license or wrong language - study, copy nothing) | **reimplement-with-attribution**
(no license but the *idea* is the value - clean re-implement, credit author) | **skip-GPL**
(copyleft trap - concept reference at most, never link/copy) | **skip-stale** (superseded
by what we already have).

---

## TOP 3 "DO NEXT" (overall, highest leverage)

### 1. magefree/mage (XMage) - engine - MIT - **adopt (reference + port-with-attribution)**
The single highest-value find across all four digs and the **only** adoptable artifact that
touches our engine-fidelity gaps. Full CR implementation (31k cards: stack, priority, layers,
replacement effects, hidden info) and it implements **both gold gaps** - planeswalker loyalty
and Warp. MIT (not GPL) means we may legally translate its Java into our Python *with
attribution* - the one thing Forge's GPL forbade. Value 5 / Effort S-read, L-port / Risk Low.
- **First action:** `git clone https://github.com/magefree/mage; open Mage.Sets warp cards +
  WarpAbility.java (Mage/.../abilities/keyword/WarpAbility.java) and one loyalty card, and read
  the priority loop, to spec our `KWTag.WARP` + planeswalker-loyalty subsystems before coding.`

### 2. suragnair/alpha-zero-general - search-AI - MIT - **adopt (the B1 interface contract)**
The canonical AlphaZero template. Its `Game.py` (`getValidMoves`/`getNextState`/`getGameEnded`/
`stringRepresentation`) **is exactly the contract our Axis-B1 forward model must satisfy**
(`legal_actions`/`apply`/`clone`). Implement against it and `MCTS.py`/`Coach.py` become ~300
near-drop-in lines for `engine/search/`. Lowest-effort unblock of the entire search layer.
Value 5 / Effort S / Risk Low.
- **First action:** `Copy Game.py + NeuralNet.py as the abstract base in mtg-sim/engine/search/;
  write a stub GameState adapter and confirm legal_actions/apply/clone type-check against it.`

### 3. NandaScott/Scrython - MCP-tooling/data - MIT - **adopt (drop-in Scryfall client)**
Most-starred repo in the entire survey (160*), PEP-561 typed, and **Scrython 2.0 ships built-in
tiered rate limiting matching Scryfall policy** - it deletes a chunk of our own throttling code
for zero design cost. Pure infra win, certain payoff. Value 5 / Effort S / Risk Low. (Use
gwax/aioscryfall if we go async under FastMCP.)
- **First action:** `pip install scrython; replace our hand-rolled Scryfall fetch+throttle path
  with Scrython 2.0's client + built-in limiter; delete the now-dead throttle code.`

> Why these three: they hit the three binding constraints in order - engine fidelity (XMage is
> the only adoptable closer of the unmodelable gaps), the search contract that gates everything
> downstream (alpha-zero-general), and an immediate zero-risk infra win (Scrython). Runners-up
> for the 4th slot: **WillWroble/MageZero** (validates the APL-per-archetype bet) and
> **gregario/mtg-oracle** (MIT compose-now MCP).

---

## LAYER 1 - ENGINE (forward-model fidelity; the gap-closers live here)

| Rank | Repo | License | V/Eff | Verdict | Note |
|---|---|---|---|---|---|
| 1 | **magefree/mage (XMage)** | MIT | 5 / S-L | **adopt + port-w/-attribution** | Closes ALL engine gaps; contamination-free oracle. TOP PICK. |
| 2 | nymann/open-gathering | NONE | 2 / S | reference-only | Python "MTG gym" scaffolding; borrow the `perft` move-gen validation idea for our B1 enumerator. No code yet. |
| 3 | fregaham/manaclash | GPL-3.0 | 2 / S | skip-GPL | Real Python priority-loop (`process.py`) + Monte-Carlo AI; design reference only, decade stale. |
| 4 | heffrey78/mtg-mcp | NONE | 2 / L | reference-only (watch) | Only external project that even *plans* stack/priority+combat (roadmap, no code). Overlaps our engine. |
| - | all-yall/autoarcana | NONE | 1 / - | skip | Only Rust full-engine attempt; abandoned, unlicensed. Logged so future digs skip it. |
| - | misprit7/magician | NONE | 1 / - | skip | NN-policy notebook toy. Logged-and-skip. |
| - | Forge, argentum-engine, open-mtg, wanqizhu, csce585 | mixed | - | [known] | Prior ext-eval/thingstolookinto. Forge=GPL oracle; Argentum=Kotlin blueprint. |

## LAYER 2 - SEARCH-AI (best-move on top of a hardened forward model)

| Rank | Repo | License | V/Eff | Verdict | Note |
|---|---|---|---|---|---|
| 1 | **suragnair/alpha-zero-general** | MIT | 5 / S | **adopt** | B1 interface contract. TOP PICK #2. |
| 2 | WillWroble/MageZero (+ fork WillWroble/mage) | MIT | 5 / M | reimplement-w/-attribution | **Deck-local RL == our APL-per-archetype structure**; validates "solve this deck" not "solve MTG". Engine is Java so borrow the design, not the code. Runner-up for do-next #4. |
| 3 | sirmammingtonham/alphastone | Public domain | 4 / S | **adopt (copyable)** | alpha-zero-general + ISMCTS determinization on Hearthstone = our **B3 hidden-info** template made real. |
| 4 | datamllab/rlcard | MIT | 4 / S-M | **adopt** | Imperfect-info card-game RL toolkit (DQN/NFSP/CFR/DMC); wrap mtg-sim as an rlcard env to reuse trainers. |
| 5 | kwai/DouZero | Apache-2.0 | 4 / M | **adopt (Plan B)** | Deep Monte Carlo, no explicit tree - the escape hatch if MTG branching breaks ISMCTS. |
| 6 | aayu3/mtg-vector-db | Apache-2.0 | 4 / M | **adopt** | PGVector+Ollama RAG over cards+rules+glossary; turnkey local semantic-search/oracle backing. |
| 7 | ByronWilliamsCPA/MTG_AI | MIT | 4 / M | reference | RAG + deterministic-rules + swappable-LLM split mirrors our analyzer/sim/harness; strong hygiene to copy. |
| 8 | jbylund/arcane_tutor | ISC | 3 / M | **adopt** | Offline server-side Scryfall-query-language engine (also data-meta) - run Scryfall syntax on our local DB, no rate limits. |
| 9 | sbl1996/yugioh-ai | MIT | 3 / M | reference/adopt | "Wrap a real engine as a fast gym + self-play" template (predecessor; ygo-agent successor is JAX). |
| 10 | sbl1996/ygo-agent | Other (unresolved) | 3 / M-L | reference-only | Production env-wrapper + distributed self-play + LSTM policy. Resolve license before any code lift. |
| 11 | peter1591/hearthstone-ai | NONE | 3 / M | reference-only | MO-MCTS + node-sharing + NN early-cutoff. C++, unlicensed - study, reimplement. |
| 12 | robkinyon/mtg-solver | NONE | 2 / S | reference-only | Brute-force goldfish solver; useful only to validate our kill-turn distributions. |
| 13 | crispy-chiken/YugiohAi | GPL-3.0 | 2 / M | skip-GPL | Joint deckbuild+pilot loop (mirrors our gauntlet+APL tuning); concept only. |
| - | open-mtg, argentum, Forge, OpenSpiel, arrdem | mixed | - | [known] | Prior docs. |

## LAYER 3 - DATA-META (sources, meta/field prediction, infra)

| Rank | Repo | License | V/Eff | Verdict | Note |
|---|---|---|---|---|---|
| 1 | **mtgjson/mtgjson** | MIT | 5 / S | **adopt** | Canonical bulk card data + preconstructed decklists + cross-set IDs/rulings. Authoritative offline DB. |
| 2 | oelarnes/spells | MIT | 4 / S | **adopt** | Best-in-class 17Lands ETL (one-call `summon()` -> Polars/parquet); reuse its caching pattern for Untapped/melee. |
| 3 | Investigamer/hexproof.io | MPL-2.0 | 4 / M | **adopt** | Unified MTGJSON+Scryfall REST models (+ set-symbol SVGs); consume as a service or as a merge-layer reference. |
| 4 | swood456/MTGO-Metagame-Predictor | MIT | 3 / S | reimplement-w/-attribution | **Only repo touching field prediction** (event meta from player roster + past decks) -> RC opponent-field prep. Stale; mine the idea. |
| 5 | EskoSalaka/mtgtools | non-standard | 3 / S | reference-only | Local card-DB persistence patterns; read LICENSE before any reuse. |
| - | gareth-smith/17lands-Synergy-Browser | NONE | 3 / S | reference-only | Card-pair synergy win-rate-lift method + Streamlit analyst-UI pattern. |
| - | youssefm/limited-grades | MIT | 2 / M | reference-only | UI/UX reference for grade-tier visualization. |
| - | FrancescoZese/MTGGraph | NONE | 2 / M | reference-only | Modern-metagame knowledge-graph visualization concept. |
| - | gabriel-ballesteros/mtg-metagame-scraper | MIT | 2 / S | skip-stale | Superseded by our Untapped/melee pipeline. |

## LAYER 4 - ML-CLASSIFIER (archetype clustering, card scoring, embeddings)

| Rank | Repo | License | V/Eff | Verdict | Note |
|---|---|---|---|---|---|
| 1 | **afreefaw/MTG-card2vec** | NONE | 4 / M | reimplement-w/-attribution | **Decklist-co-occurrence embeddings = a feature source our text-only ModernBERT lacks** ("what's played together"). Concatenate into the archetype KNN, esp. for low-text-signal lands/staples. |
| 2 | danieljbrooks/statistical-drafting | MIT | 4 / M | **adopt/reference** | DraftNet learned pick-model w/ color+archetype+splash synergy adjustment; reference architecture for a lightweight learned card scorer. |
| 3 | 596428/mtg-draft-analyzer | NONE | 4 / M | reimplement-w/-attribution | Wilson+Z composite card scoring + auto sleeper/trap detection; upgrades the analyzer's "underplayed winner / popular trap" column (more rigorous than Warlord1986pl [known]). |
| 4 | Lejoon/MachineMeta | NONE | 4 / M | reimplement-w/-attribution | K-means+LDA archetype clustering **+ optimal-build-per-cluster** = the ARL deck-optimizer seed. Stale. |
| 5 | TopDecked/MTGMeta-TS | NONE | 3 / S | reimplement-w/-attribution | k-means++ deck clustering; benchmark cluster quality vs our KNN on low-sample archetypes. |
| - | Clivesay1/mtg-card-value-analysis | NONE | 2 / S | reference-only | Composite under/over-valued scoring (finance angle); overlaps 596428. |
| - | timtouch/mtg-deck-optimizer | NONE | 3 / S | reference-only (watch) | Names the exact "recommend card swaps" concept; empty repo, concept flag only. |
| - | zkrytobojca/MTG_Card_Classification | NONE | - | [known] | Prior thingstolookinto (504-feature RF). |

## LAYER 5 - MCP-TOOLING (compose alongside our server / SDKs)

| Rank | Repo | License | V/Eff | Verdict | Note |
|---|---|---|---|---|---|
| 1 | **NandaScott/Scrython** | MIT | 5 / S | **adopt** | Typed Scryfall client w/ built-in rate limiting. TOP PICK #3. |
| 2 | gregario/mtg-oracle | MIT | 5 / S | **adopt (compose)** | npx-installable; local SQLite cards+rules+combo DB + curated MTG knowledge. Compose next to ours now. |
| 3 | bmurdock/scryfall-mcp | MIT | 5 / M | **adopt (fork contracts)** | 14 tools incl `build_scryfall_query` (NL->query), `suggest_mana_base`, `find_synergistic_cards`, `analyze_deck_composition` - the search-AI/deckbuild tool surface we lack. |
| 4 | nathanmartins/mtg-mcp | MIT | 4 / M | **adopt/reference** | Deck validation + multi-platform deck import (Moxfield/Archidekt); only mature Go MCP (single-binary option). |
| 5 | gwax/aioscryfall | MIT | 4 / S | **adopt (async alt)** | asyncio-first Scryfall client; better fit if MCP server goes async under FastMCP. |
| - | cryppadotta/scryfall-mcp | NONE | 3 / S | reference-only | Highest-star Scryfall MCP; SSE remote-transport reference. |
| - | MagicTheGathering/mtg-api | NONE | 3 / S | reference-only | Secondary REST API (mtgjson-backed); prefer pulling mtgjson bulk directly. |
| - | thin Scryfall-MCP wrappers (pipeworx-io, reonyanarticle, jakemingolla, ...) | mostly MIT | 1-2 / S | reference-only | Tool-naming cross-check only; none exceed bmurdock/mtg-oracle. |
| - | j4th/mtg-mcp-server, artillect, KaminaDuck, fastmcp, python-sdk | mixed | - | [known] | Prior ext-eval-mcp-composition / thingstolookinto. j4th=TOP composition target (69 tools). |

## LAYER 6 - PRODUCTIZATION (phone/web client + companion app)

| Rank | Repo | License | V/Eff | Verdict | Note |
|---|---|---|---|---|---|
| 1 | **Danmoreng/mtg-pwa** | MIT | 4 / M | **adopt (template)** | Offline-first responsive PWA; importers (ManaBox/Moxfield/Cardmarket) + price-history charts. Architecture template for a PWA meta-analyzer - cheaper than native, phone-installable. |
| 2 | danbro96/LupiraMtgApi | MIT | 4 / L | **adopt (blueprint)** | Freshest serious backend (2026-06-23): perceptual-hash + OCR fusion card recognition (POST /scans), nightly Scryfall bulk sync, OpenAPI. The "scan a card with your phone" feature; wrap behind an MCP tool. |
| 3 | olaservo/scryfall-mcp-app | NONE | 5 / M | reference-only | MCP App UI renders card images/mana symbols in Claude Desktop + MCPB one-click install. **The** MCP+UI fusion + packaging reference; study, don't vendor. |
| 4 | JacobHearst/ScryfallKit (+ Skryfall, scryfall_api, go-scryfall, api-types) | MIT/Apache | 2-4 / S | **adopt/reference** | Native client SDKs (Swift/Kotlin/Dart/Go/TS) - only relevant if we go native instead of PWA. |
| - | GrimbiXcode/mtgscan | GPL-3.0 | - | skip-GPL | Card scanner; LupiraMtgApi (MIT) >> this for reuse. |

---

## UNMODELABLE-GAP CLOSURE MAP (the load-bearing column)

Our five engine-fidelity gaps - **stack/priority, hidden info, instant-speed combat,
planeswalker loyalty, Warp** - plus three product gaps. What each dig actually closes:

- **All five engine gaps -> only `magefree/mage` (XMage)** closes them, and only as a
  *reference + MIT-port-with-attribution*, not a drop-in (it's Java). It is the unique adoptable
  closer. Every other cluster explicitly confirmed it touches NONE of these (engine concerns).
- **Hidden info (search side, B3)** -> `sirmammingtonham/alphastone` (copyable ISMCTS
  determinization template) + `peter1591/hearthstone-ai` (MO-MCTS, reference). These close the
  *search-over-hidden-info* half; the *modeling* half still needs XMage/our engine.
- **Search contract enabling best-move over the model (B1)** -> `suragnair/alpha-zero-general`
  (interface) + `WillWroble/MageZero` (deck-local framing = our APL structure).
- **Large action space / instant-speed combat branching (search risk)** -> `kwai/DouZero` +
  `datamllab/rlcard` (Deep Monte Carlo Plan B if ISMCTS chokes).
- **Deck/SB optimizer (greenfield - no off-the-shelf solution found)** -> ASSEMBLE from
  `Lejoon/MachineMeta` (optimal-build-per-cluster) + `596428/mtg-draft-analyzer` (composite
  scoring + sleeper/trap) + `timtouch` (swap concept). Build, don't borrow.
- **Meta/field prediction (RC opponent-field prep)** -> `swood456/MTGO-Metagame-Predictor` is
  the only repo touching it; reimplement the idea.
- **Card embeddings the classifier lacks** -> `afreefaw/MTG-card2vec` (decklist co-occurrence)
  + `aayu3/mtg-vector-db` (text/rules semantic).

**Confirmed NOT closeable from external repos:** the *modeling* of Warp + planeswalker loyalty
+ stack/priority + instant-speed combat remains an mtg-sim engine task. XMage is the only
behavior oracle/reference; everything else sits above a forward model that must exist first.

## NET ASSESSMENT

The four digs converge on a clean dependency order. The binding constraint is engine fidelity,
and there is exactly one adoptable lever (XMage, MIT). On top of a hardened forward model the
search layer is well-supplied with permissive Python (alpha-zero-general contract -> alphastone
ISMCTS -> APL-seeded PUCT, DouZero as fallback) and the deck-local framing (MageZero) matches our
existing per-archetype structure. The data/MCP/product layers are immediately actionable and
low-risk (Scrython, mtgjson, spells, mtg-oracle, bmurdock contracts, Danmoreng PWA). The only
greenfield builds with no off-the-shelf solution are the deck/SB optimizer and field prediction.
Sequence: **XMage (read warp/loyalty/priority) -> conform GameState to alpha-zero-general (B1) ->
bolt ISMCTS per alphastone (B3) -> seed PUCT with APLs (B4), DMC in reserve**; in parallel adopt
Scrython + mtgjson + spells and compose mtg-oracle for zero-risk wins.

## Changelog
- 2026-06-26: Created (SURFACED). Synthesized the four 2026-06-26 gh digs into one ranked,
  layer-grouped backlog with license + verdict per repo, top-3 do-next picks, and an
  unmodelable-gap closure map. Deduped against thingstolookinto.md + ext-eval docs ([known] tags).
</content>
</invoke>
