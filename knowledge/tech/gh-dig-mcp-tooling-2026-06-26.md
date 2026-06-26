---
title: "GitHub Dig - Cluster 4: MCP servers / APIs / tooling / productization"
date: 2026-06-26
author: gh-discovery-subagent
scope: "MCP composition targets, MTG APIs/SDKs, and phone/web client references for the meta-analyzer app idea"
method: "gh search repos (--sort stars) across 18 queries; README+LICENSE deep-read of 13 candidates via gh api"
dedup_against:
  - thingstolookinto.md (2026-06-21)
  - harness/knowledge/tech/ext-eval-mcp-composition-2026-06-26.md
status: read-only survey
note: "gh search API rate-limited at ~30/min mid-run; freshness (--sort updated) pass and several gap queries were throttled. README fetches (separate 5000/hr limit) completed fine."
---

# Cluster 4 - MCP / APIs / Tooling / Productization

North-star layers in play here: **MCP-tooling** (servers to compose with ours) and
**productization** (phone/web client references). Secondary: **data-meta** (API/SDK access to card data).

## 0. Already known (dedup - do NOT re-add)

| Repo | Where seen | Verdict carried forward |
|---|---|---|
| j4th/mtg-mcp-server | ext-eval-mcp-composition | MIT, TOP composition target (Scryfall/17Lands/EDHREC tools) |
| artillect/mtg-mcp-servers | ext-eval + this search (14*) | NO LICENSE -> reference-only (sim+meta two-server pattern) |
| KaminaDuck/scryfall-mcp | ext-eval + this search (2*) | Apache-2.0 (corrected), optional |
| jlowin/fastmcp | ext-eval-mcp-composition | Apache-2.0, the engine we build on |
| modelcontextprotocol/python-sdk | thingstolookinto | the base SDK |

Everything below is NEW signal not in those files.

---

## 1. MCP composition targets (compose alongside OUR server)

These expose MCP tools we could federate with, or fork patterns from. Ranked by fit.

### bmurdock/scryfall-mcp -- MIT -- **GOLD (models our gaps)**
- Stars 1, updated 2026-05-13. TypeScript. stdio + local Streamable HTTP.
- Exposes **14 tools, 2 resources, 2 prompts**. Standouts that map directly to OUR gaps:
  `build_scryfall_query` (natural-language -> explainable Scryfall query),
  `suggest_mana_base` (land counts + fixing from color reqs),
  `find_synergistic_cards`, `analyze_deck_composition` (curve/colors/structure),
  `search_format_staples`, `batch_card_analysis`, local `query_rules` over comprehensive rules.
- Value 5 / Effort M / Risk Low. How we'd use it: fork the tool *contracts* (NL->query, mana-base,
  deck-composition) as the API shape for our own MCP tools; the search-AI + deckbuild layer we lack.

### gregario/mtg-oracle -- MIT -- **GOLD (composition target)**
- Stars 3, updated 2026-05-02. Node >=18, on npm + glama.ai registry. **14 tools.**
- "Not just another Scryfall wrapper": downloads cards + comprehensive rules + **combo DB into local
  SQLite** for offline queries; ships curated knowledge (archetypes, format primers, commander
  strategy, mana-base guidelines).
- Value 5 / Effort S / Risk Low. How we'd use it: drop-in composition server (npx, Claude Desktop
  config given) for rules/combo/synergy lookups; study its SQLite+curated-knowledge packaging as the
  template for shipping OUR meta knowledge to an LLM.

### cryppadotta/scryfall-mcp -- NO LICENSE -> reference-only -- highest-star scryfall MCP
- Stars 33, updated 2026-06-21. Node. **Most-starred Scryfall MCP found.**
- Tools: search_cards, get_card_by_id/name, random_card, get_rulings, get_prices_by_id/name.
  Runs stdio OR **SSE mode** (HTTP endpoints at :3000/sse + /messages) - good remote-transport ref.
- Value 3 / Effort S / Risk Med (no license = cannot reuse code, patterns only).
  How we'd use it: SSE transport reference for a hosted/remote MCP; do not vendor code.

### nathanmartins/mtg-mcp -- MIT -- Commander, Go
- Stars 10, updated recent. Go. Scryfall card data (7 tools) + rulings + pricing + **deck validation
  + multi-platform deck importing** (Moxfield/Archidekt-style). CI/CD, releases.
- Value 4 / Effort M / Risk Low. How we'd use it: deck-import tool surface reference; the only
  mature Go MCP here if we ever want a single static binary server.

### heffrey78/mtg-mcp -- NO LICENSE -> reference-only -- ambitious scope
- Stars 0, updated 2026-07-26(? recent). TypeScript, STDIO. Foundation done; planned card DB, deck
  building w/ format validation, **full game-state simulation (combat, stack, priority)**, tutorials.
- Value 2 / Effort L / Risk Med (no license, mostly roadmap). Watch only; overlaps mtg-sim's engine.

### Other Scryfall MCP servers (MIT unless noted) - thin wrappers, npm-publish references
- pipeworx-io/mcp-scryfall (MIT, 2026-06-04), reonyanarticle/scryfall-mcp (MIT, Rust),
  jakemingolla/scryfall-mcp (MIT), Frezz146/scryfall-mcp-server (MIT), Elnop/scryfall_mcp (MIT),
  bmbowdish n/a. Also: GustavoLima93/mcp-magic-the-gathering, mpsteele28/scryfall-mcp,
  WilliamBCampbell/scryfall-mcp, zeroish/scryfall-mcp (EDH), colinhauch/, jeeyoungk/mcp-scryfall,
  rpg2014/, dbeltra/, JoeMoCode/Scryfall-MCP.
- Value 1-2 / Effort S / Risk Low. Use: cross-check tool naming conventions; pick MIT ones if we
  want a ready npx server for a quick demo. None exceed bmurdock/mtg-oracle.

---

## 2. MTG APIs / SDKs (data-meta access layer)

### NandaScott/Scrython -- MIT -- **TOP SDK (we are Python)**
- Stars 160, updated 2026-06-11. **Most-starred repo in the whole cluster.** PyPI `pip install scrython`.
- PEP 561 typed (ships py.typed; mypy/pyright clean). **Scrython 2.0 has built-in tiered rate
  limiting** (10 req/s normal, 2 req/s for Search/Named/Random/Collection) - matches Scryfall policy.
- Value 5 / Effort S / Risk Low. How we'd use it: the Scryfall client for our Python MCP server /
  meta-analyzer; the built-in rate-limiter removes a chunk of our own throttling code.

### gwax/aioscryfall -- MIT -- async Python Scryfall
- Stars 3, updated 2026-04-02. asyncio-first (sync client too), Python 3.11+, extensively typed,
  paginated lists exposed as generators. Docs sparse.
- Value 4 / Effort S / Risk Low. How we'd use it: if our MCP/server goes async (FastMCP is async),
  this fits better than Scrython's sync core; good for high-throughput bulk pulls.

### MagicTheGathering/mtg-api (magicthegathering.io) -- NO LICENSE on repo -- the classic REST API
- Stars 42, updated 2026-02-24. The magicthegathering.io REST service, data backed by **mtgjson**.
  Many community SDKs (Python/JS/etc.) exist. Author explicitly wants SDK contributions.
- Value 3 / Effort S / Risk Med. Use: fallback/secondary card API; mtgjson is the real data source
  to pull from directly (bulk) rather than this hosted endpoint.

### Native-platform Scryfall SDKs (phone-client enablers)
- **JacobHearst/ScryfallKit** -- MIT, 11*, 2026-06-07. Swift Package (SwiftPM, DocC). -> iOS/macOS
  native client. Value 4 if we go native iOS / Value 2 otherwise. Effort S.
- BlueMonday/go-scryfall (MIT, 27*), bmbowdish/Swiftfall (MIT, 21*, older), kadahlin/Skryfall
  (Apache-2.0, Kotlin -> Android native), aroningruber/scryfall_api (MIT, Dart -> **Flutter**),
  scryfall/api-types (MIT, 42*, official TS types -> any TS/React/RN client).
- ninesl/scryball -- no license, Go Scryfall with **SQLite persistent caching** (caching pattern ref).

---

## 3. Phone / web client references (productization)

### olaservo/scryfall-mcp-app -- NO LICENSE shown -> reference-only -- **GOLD (MCP + UI fusion)**
- Updated recent. Uses **modelcontextprotocol/ext-apps "MCP App" UI** that renders card images,
  mana symbols, oracle text, and pricing **inside Claude Desktop**. Ships as **MCPB one-click
  install** + npm (@olaservo/scryfall-mcp-server).
- Value 5 / Effort M / Risk Med (license unclear - study, don't vendor). How we'd use it: this is
  the reference for giving OUR MCP a rich card-rendering UI in MCP hosts, and MCPB packaging for
  one-click distribution. Closest thing to "phone/web client backed by MCP" found.

### Danmoreng/mtg-pwa -- MIT -- **strong PWA reference**
- Stars 0, updated 2026-10-12(? recent), Vite/Vue PWA. Collection value tracker: **offline PWA,
  responsive desktop+mobile**, importers for Cardmarket CSV / ManaBox / Moxfield, historical price
  charts, transform-card image flipping, has ai_docs/ARCHITECTURE + ROADMAP.
- Value 4 / Effort M / Risk Low. How we'd use it: the architecture template for a PWA meta-analyzer
  (offline-first, importer patterns, price-history charts) - cheaper than native, installable on phone.

### danbro96/LupiraMtgApi -- MIT -- **GOLD for card-scanning phone app**
- Stars 1, updated 2026-06-23 (freshest serious backend). Self-hostable REST backend: serves
  Scryfall-sourced metadata, **recognizes physical cards from a photo via perceptual-hash + OCR
  fusion** (POST /scans -> confidence-ranked printings), per-user collections, nightly Scryfall bulk
  sync + art into object storage, presigned image URLs, OpenAPI + Swagger UI. REST only (no MCP).
- Value 4 / Effort L / Risk Low. How we'd use it: blueprint for the "scan a card with your phone"
  feature; pHash+OCR fusion + bulk-sync pipeline is exactly the hidden-info/data layer a companion
  app needs. Could be wrapped behind an MCP tool.

### Other client references (mostly low signal)
- jorenrui/mtg-companion (PWA, life/match), Bdazzle/mtgsearchapp-react-native, dmshikoff/mtg-react-native,
  jdylanmc/mtg-flutter, marcoskichel/mtg_companion (MIT, Flutter), MadMaxMcKinney/raycast-lotus-mtg-companion
  (Raycast extension), GrimbiXcode/mtgscan (GPL-3.0, card scanner). Mostly hobby/stale; use only as
  framework boilerplate if picking that stack. Value 1-2.
- Card-recognition note: LupiraMtgApi (MIT) >> GrimbiXcode/mtgscan (GPL-3.0, copyleft risk) for reuse.

---

## 4. Gap coverage (the "gold" flags)

- **stack/priority modeling**: only heffrey78/mtg-mcp *plans* stack+priority (no license, roadmap) -
  no off-the-shelf win here; stays mtg-sim's problem.
- **hidden info**: LupiraMtgApi's scan/recognition (physical->digital) is the closest real artifact;
  no MCP exposes hidden-info game state.
- **Warp / planeswalker loyalty**: nothing in this cluster models these mechanics. Confirmed gap;
  must come from our own engine, not external MCP/API.
- **NL -> query / deck analysis**: bmurdock/scryfall-mcp + gregario/mtg-oracle directly cover this
  search-AI gap and are MIT - the most reusable finds in the cluster.

---

## 5. License ledger (verified via gh api .../license today)

| Repo | License (verified) | Reuse |
|---|---|---|
| NandaScott/Scrython | MIT | yes - vendor/dep |
| gwax/aioscryfall | MIT | yes |
| bmurdock/scryfall-mcp | MIT | yes - fork contracts |
| gregario/mtg-oracle | MIT | yes - compose |
| nathanmartins/mtg-mcp | MIT | yes |
| Danmoreng/mtg-pwa | MIT | yes - template |
| danbro96/LupiraMtgApi | MIT | yes - blueprint |
| JacobHearst/ScryfallKit | MIT | yes (iOS) |
| cryppadotta/scryfall-mcp | NONE | patterns only |
| heffrey78/mtg-mcp | NONE | watch only |
| olaservo/scryfall-mcp-app | NONE shown | study only |
| MagicTheGathering/mtg-api | NONE on repo | use hosted API, prefer mtgjson |

## 6. Recommended next actions
1. Adopt **NandaScott/Scrython** (or aioscryfall if async) as our Scryfall client - kills our
   throttling code.
2. Stand up **gregario/mtg-oracle** as a composed MCP next to ours (npx, MIT) for rules/combo/synergy.
3. Mine **bmurdock/scryfall-mcp** tool contracts to design OUR NL->query / mana-base / deck-comp tools.
4. For productization: prototype as a **PWA (Danmoreng pattern)**; wrap **LupiraMtgApi** scan pipeline
   behind an MCP tool; study **olaservo/scryfall-mcp-app** for in-host card-render UI + MCPB packaging.

## Changelog
- 2026-06-26: Created. 18 gh queries (search API throttled mid-run), 13 READMEs+licenses deep-read.
