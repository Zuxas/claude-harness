---
title: GitHub Dig - Data / Deckbuilding / Meta / Classification (Cluster 3)
date: 2026-06-26
cluster: 3-data-meta
author: gh-discovery-subagent
method: gh search repos (stars + updated passes), 12 queries, READMEs + LICENSE verified via gh api
queries: ["mtg metagame","mtg deckbuilding","mtg deck optimizer","mtgjson","scryfall","mtg archetype classifier","mtg machine learning","mtg data analysis","mtg tournament data","melee gg mtg","17lands","mtg sideboard"]
unique_repos_seen: 260
deep_read: 12
dedup_against: ["thingstolookinto.md","ext-eval-*-2026-06-26.md"]
license_note: "blank license in gh search == NO LICENSE / all-rights-reserved == ideas & architecture only, clean re-implement, do NOT copy code"
north_star_layers: [engine, search-AI, data-meta, ML-classifier, MCP-tooling, productization]
---

# Cluster 3 - Data / Deckbuilding / Meta / Classification

Scope: data sources, deck-optimization algorithms, archetype-classification approaches,
sideboard tooling that could feed the meta-analyzer + ARL deck/SB optimizer.
260 unique repos surfaced; the long tail is overwhelmingly hobby Scryfall API wrappers,
proxy/print tools, MTGA collection trackers, and student data-analysis notebooks (low signal).
Below = NEW signal only. Repos already in thingstolookinto.md / ext-eval files are tagged [known].

Scoring: Value 1-5 / Effort S-M-L / Risk. GOLD = models one of our explicit gaps
(stack/priority, hidden info, archetype clustering, deck/SB optimizer, meta prediction, RAG card-Q&A).

---

## TIER A - GOLD (models our gaps; read first)

### 596428/mtg-draft-analyzer  [NEW]
- 0 stars | pushed 2026-01 | **NO LICENSE (ideas only)** | Python (uv) | data-meta + ML-classifier
- What: 17Lands-fed draft analyzer. **Wilson Score + Z-Score composite card ratings**, single-color
  & 2-color archetype win-rate/synergy ranking, format-speed stats, trophy-deck (7-x) composition
  mining, **automatic sleeper/trap (under/over-valued) detection**, multi-page HTML guide, Gemini LLM
  strategy insights, Markdown/JSON export. Has a METRICS_GUIDE.md.
- Value 5 / Effort M / Risk: no license (re-implement the stats from understanding, don't copy code).
- How we'd use it: the Wilson+Z composite scoring and sleeper/trap logic is a direct upgrade path
  for the meta-analyzer's "underplayed winners / popular traps" column (overlaps Warlord1986pl
  [known] but is statistically more rigorous). Steal the metric definitions, reimplement.

### danieljbrooks/statistical-drafting  [NEW]
- 5 stars | pushed 2026-05 (active, nightly GH Actions auto-retrain) | **MIT** | Python (PyTorch) | ML-classifier
- What: `DraftNet` neural pick model trained on 17Lands data for 20+ sets. Recommends pick order
  from current pool; **synergy adjustment accounts for color, archetype, speculation, splash**;
  <20 min train/dataset, <1ms/pick inference, portable .pt weights. Live site statisticaldrafting.com.
- Value 5 / Effort M / Risk: low (MIT, keep notice). Models limited not Constructed, but the
  pick-order-from-pool + synergy-adjustment architecture maps onto card-evaluation scoring.
- How we'd use it: reference architecture for a lightweight learned scorer; the synergy-adjustment
  feature design is reusable for our archetype/card-context signals.

### afreefaw/MTG-card2vec  [NEW]
- 6 stars | pushed 2026-04 | **NO LICENSE (ideas only)** | Jupyter | ML-classifier
- What: word2vec/gensim **vector embeddings of cards learned purely from decklists** (millions of
  decks scraped from 8 sites + 17Lands). Cards co-occurring in decks land near each other; supports
  "card math" (analogies). Receives NO card attributes - only name + co-occurrence.
- Value 4 / Effort M / Risk: no license (reimplement; gensim itself is LGPL-ok as a dependency).
- How we'd use it: **decklist-co-occurrence embeddings are a feature source our ModernBERT pipeline
  lacks** - ModernBERT reads card *text*; card2vec captures *what gets played together*. Concatenate
  as an extra feature vector for the archetype KNN/classifier, especially for low-text-signal lands/staples.

### Lejoon/MachineMeta  [NEW]
- 1 star | pushed 2020-01 (stale) | **NO LICENSE (ideas only)** | Python | data-meta + ML-classifier
- What: fetches tournament decklists -> builds a "metagame pool" of archetypes via **both K-means
  clustering AND Latent Dirichlet Allocation (LDA)**, then derives **optimal builds** per archetype.
- Value 4 / Effort M / Risk: stale + no license (concept reference only).
- How we'd use it: LDA-over-decklists is a topic-model alternative to our KNN for unsupervised
  archetype discovery; the "optimal build per cluster" step is exactly the ARL deck-optimizer goal.

### timtouch/mtg-deck-optimizer  [NEW]
- 0 stars | pushed 2026-03 | **NO LICENSE / no README** | data-meta | (concept only)
- What (from description): "analyzes a deck list and **recommends card swaps to improve consistency**."
- Value 3 / Effort S / Risk: empty repo, no license, unverified - concept flag only.
- How we'd use it: names the exact ARL SB/deck-optimizer concept (swap recommendation). Watch, do not depend.

### TopDecked/MTGMeta-TS  [NEW]
- 0 stars | pushed 2020-10 (stale) | **NO LICENSE (ideas only)** | TypeScript | ML-classifier
- What: determines the metagame via **k-means++ clustering** of decks (uses K-Means-TS submodule).
  Lineage: adapted from GoldinGuy/MTGMeta-PY <- StrikingLoo/MtGRecommender.
- Value 3 / Effort S / Risk: stale, no license (algorithm reference).
- How we'd use it: k-means++ seeding reference for clustering decks into archetypes; compare cluster
  quality vs our KNN on low-sample archetypes.

---

## TIER B - DATA SOURCES & INFRASTRUCTURE (foundational, safe)

### mtgjson/mtgjson  [NEW] (note: the j4th mtg-mcp-server [known] consumes it, but the data source itself was never listed)
- 471 stars | pushed 2026-06 (active) | **MIT** | Python | data-meta
- What: THE canonical bulk card-data build (AllPrintings, AtomicCards, prices, legalities, decks).
  Org also ships SDKs (python/go/rust/ts/r), mtgsqlive (SQL/Parquet export), AllDeckFiles archive.
- Value 5 / Effort S / Risk: low. Use as the authoritative offline card DB feeding sim + analyzer
  (complements Scryfall; MTGJSON has cleaner cross-set IDs, rulings, and preconstructed decklists).

### Investigamer/hexproof.io  [NEW]
- 5 stars | pushed 2026-05 (active) | **MPL-2.0** | Python (Django-Ninja) | data-meta
- What: REST API that **synthesizes MTGJSON + Scryfall + others into unified models** (snake_case,
  Scryfall-like), plus set symbol/watermark SVG endpoints other APIs miss. Live api.hexproof.io.
- Value 4 / Effort M / Risk: low (MPL-2.0 is file-level copyleft, fine as a service or dependency).
- How we'd use it: reference for a clean multi-source data-merge layer; or consume its API directly
  to avoid maintaining our own Scryfall+MTGJSON reconciliation.

### aayu3/mtg-vector-db  [NEW]
- 0 stars | pushed 2025-10 | **Apache-2.0** | Python | search-AI / RAG
- What: docker-compose **PGVector + Ollama embeddings** ingesting MTGJSON: ~30k card docs, ~2k
  comprehensive-rules entries, ~700 glossary terms, all 3 with HNSW-indexed embedding tables for
  semantic search. Uses embeddinggemma:300m.
- Value 4 / Effort M / Risk: low (Apache-2.0, keep NOTICE).
- How we'd use it: turnkey blueprint for a **local semantic card/rules search** backing the harness +
  sim oracle lookups and any RAG deck assistant - cards + rules + glossary already schema'd.

### oelarnes/spells  [NEW]
- 14 stars | pushed 2026-06 (active) | **MIT** | Python (Polars) | data-meta
- What: pip package `spells` - one-call `summon()` returns a Polars DataFrame of fully transformed
  **17Lands public datasets** (draft + game), auto-downloads, parquet-caches, merges mtgjson card
  data + set context. Blazing-fast, extensible aggregations.
- Value 4 / Effort S / Risk: low (MIT). Best-in-class 17Lands ETL.
- How we'd use it: drop-in 17Lands ingestion/ETL for any limited analysis; the Polars-parquet
  caching pattern is reusable for our Untapped/melee pipelines.

### jbylund/arcane_tutor  [NEW]
- 3 stars | pushed 2026-06 (active) | **ISC** | Python | search-AI
- What: open-source card search engine **implementing Scryfall's query language** server-side.
- Value 3 / Effort M / Risk: low (ISC permissive).
- How we'd use it: lets us run Scryfall-syntax queries against our own local card DB offline (no
  rate limits) - useful for sim/analyzer card filtering and for an MCP search tool.

### gabriel-ballesteros/mtg-metagame-scraper  [NEW]
- 8 stars | pushed 2021-07 (stale) | **MIT** | Python | data-meta
- What: web scraper for MTG decklists (metagame feed).
- Value 2 / Effort S / Risk: stale but MIT. Reference only; our Untapped/melee pipeline supersedes it.

### EskoSalaka/mtgtools  [NEW]
- 75 stars | pushed 2024-06 | **other (verify LICENSE)** | Python | data-meta
- What: collection of tools for handling MTG card data locally (Scryfall/MTGJSON ingestion, persistent
  ZODB storage, search).
- Value 3 / Effort S / Risk: med (non-standard license - read LICENSE before any reuse).
- How we'd use it: reference for local card-DB persistence patterns.

---

## TIER C - METHOD / NICHE REFERENCES

### gareth-smith-physics/17lands-Synergy-Browser  [NEW]
- 0 stars | 2026-04 | **NO LICENSE (ideas only)** | Python (Streamlit/Plotly) | data-meta
- Card-pair **synergy win-rate-lift** analysis from 17Lands; filter by sample size. Method reference
  for synergy lift; Streamlit pattern for a quick analyst UI. Value 3 / Effort S.

### Clivesay1/mtg-card-value-analysis  [NEW]
- 0 stars | 2026-06 | **NO LICENSE (ideas only)** | Jupyter | ML-classifier
- ML model + composite score to flag **undervalued cards** (finance angle, not gameplay). Value 2 / Effort S.
  Composite-scoring idea overlaps 596428's sleeper detection; reference only.

### swood456/MTGO-Metagame-Predictor  [NEW]
- 0 stars | 2019-07 (stale) | **MIT** | Python | data-meta
- Predicts an event's expected metagame from the **player list + their past deck choices**. Value 3 / Effort S.
- GOLD-ADJACENT: models field-prediction for RC prep (who's in the room -> what to expect). Stale but MIT - mine the idea.

### FrancescoZese/MTGGraph  [NEW]
- 0 stars | 2026-06 | **NO LICENSE** | JS | data-meta
- Interactive **knowledge graph of the Modern metagame**. Value 2 / Effort M. Visualization concept reference.

### youssefm/limited-grades  [NEW]
- 38 stars | 2026-06 (active) | **MIT** | TypeScript | data-meta
- Polished site visualizing 17Lands card win rates by limited grade. Value 2 / Effort M. UI/UX reference for grade tiers.

### ByronWilliamsCPA/MTG_AI  [NEW]
- 1 star | 2026-06 (very active, full CI/CD, PyPI, codecov) | **MIT** | Python 3.12 | search-AI / productization
- Self-hosted cEDH **deck-critique assistant: RAG over Scryfall/MTGJSON/meta + deterministic rules
  engine + swappable LLM backend**. Import a deck, get critique. Value 4 / Effort M / Risk low (MIT).
- How we'd use it: reference architecture for our "AI deck assistant" - the RAG + deterministic-rules +
  pluggable-model split mirrors the meta-analyzer/sim/harness combo. Strong engineering hygiene to copy.

---

## SIDEBOARD CLUSTER (all small/hobby; sepro/MtG-Sideboard-Guides [known] still the best)
- milkduds1001/matchupketchup (0, no-lic, 2026-04) - SB guide app
- NBrichta/mtg-sideboarder (0, MIT, 2025-05) - SB design+export web app  <- only permissive one
- croissancecomparee/mtg-sideboard-tool (0, no-lic, 2026-05) - SB generator
- Fureeish/MTG-Sideboard-Plan-Printer (0, no-lic, 2025-08, Kotlin) - PDF SB guides
- thinks/mtg_sideboard_map (1, MIT, 2019) - script to generate SB guides
None model SB *optimization* (only formatting/printing). Our ARL SB-optimizer is still greenfield -
no off-the-shelf algorithm found in this cluster; the optimization signal lives in TIER A
(596428 sleeper/trap, Lejoon optimal-builds, timtouch swap-recommendation concepts).

---

## GAP-COVERAGE NOTE
- **Archetype clustering**: Lejoon (K-means+LDA), TopDecked (k-means++), card2vec (decklist embeddings)
  give 3 distinct unsupervised approaches to compare against our ModernBERT+KNN hybrid.
- **Deck/SB optimizer**: no complete optimizer exists; assemble from Lejoon optimal-build + 596428
  composite scoring + timtouch swap concept. Build, don't borrow.
- **Meta/field prediction**: swood456 (player-history field prediction) is the only repo touching this -
  directly relevant to RC opponent-field prep.
- **Hidden info / stack-priority / Warp / planeswalker loyalty**: NOTHING in this data cluster touches
  these - they are engine concerns (see ext-eval-mtg-engines). Confirmed gap, no external solution here.
- **Card embeddings for classifier**: card2vec (decklist co-occurrence) + aayu3/mtg-vector-db (text/
  rules semantic) are two NEW embedding sources our pipeline doesn't currently use.

## Changelog
- 2026-06-26: Initial dig. 260 unique repos across 12 queries; 12 deep-read; licenses verified via gh api.
