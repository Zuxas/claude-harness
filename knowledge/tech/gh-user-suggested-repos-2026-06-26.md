---
title: User-Suggested GitHub Repos - Verdict (5 repos)
status: SURFACED
created: 2026-06-26
note: "source: user-suggested 2026-06-26"
dedup_against:
  - github-discovery-backlog-2026-06-26.md
  - ext-eval-mtg-engines-2026-06-26.md
  - ext-eval-mcp-composition-2026-06-26.md
  - ext-eval-ml-calibration-2026-06-26.md
  - thingstolookinto.md
---

# User-Suggested GitHub Repos - Verdict (5 repos)

Synthesis of 5 user-suggested repo evaluations (2026-06-26). All five carry **no
license** (verified `gh api .../license` -> 404, `license: null` on each) = all-rights-
reserved = ideas / clean-reimplement only, no code copying. None touches a real engine
gap (stack/priority, hidden info, instant-speed combat, Warp, planeswalker loyalty) in a
way we can adopt. Net: **0 folds, 5 skips.**

## 1. Verdict Table

| Repo | What it is | License | Layer | Verdict | First action |
|---|---|---|---|---|---|
| dmeza31/mtg-tournament-tracker | Python full-stack MTG tournament CRUD (Postgres + FastAPI/SQLAlchemy + 2 Streamlit UIs); logs matches/players/decks/standings. 1*, ~4.5mo stale. | NONE (all-rights-reserved) | Team Resolve event ops / meta-analyzer (record-keeping) | **skip** (reference-only at most) | None required. Optional/low-pri: WebFetch its `database/` standings + head-to-head view SQL as a schema sanity-check if/when building a Team Resolve match-record table. |
| ndalmasso/deck-confidant | Python (dbt + Streamlit per README) Modern deck *builder*/archetype-discovery portfolio piece; hierarchical k-means auto-archetypes + NLP play-style deck assembly. 1*, 1 commit, README oversells thin code. | NONE | meta-analyzer / deckbuild | **skip** (lean reference-only) | None required. Optional: one-line note in ext-eval-ml-calibration-2026-06-26.md re unsupervised archetype clustering as a sparse-label fallback. |
| oboyone/Modernligan | Python/Flask local paper-Modern-league standings app; Glicko-2 player ratings from manual YAML. 0*, dead ~2yr. NOT a metagame/decklist tool. | NONE | Team Resolve (leaderboard, marginal) | **skip** | None. If TR ever needs skill ratings, reimplement Glicko-2 from Glickman's published spec, not this repo. |
| FrancescoZese/MTGGraph | JS/D3 force-directed knowledge-graph of Modern meta (cards/archetypes as nodes); Python pipeline ingests MTGO lists, medoid/Jaccard clustering -> graph.json. 0*, live daily cron. | NONE | meta-analyzer (viz) | **skip** ( [known] -- already backlog line 118, reference-only) | None. Already catalogued; classifier weaker than our ModernBERT/KNN. Only latent value = graph.json -> D3 pattern for a public meta page on My-Website. |
| tjonestj3/mtg-engine | Rust from-scratch rules-engine scaffold (macroquad GUI, Scryfall stubs); has a real LIFO stack object + combat declare structs but NO priority loop, NO hidden info, NO card pool, NO AI/search. 0*, 1-day commit burst, dead. | NONE | engine (nominal) | **skip** | None. Optional: one-line "[skip]" note in ext-eval-mtg-engines-2026-06-26.md so it isn't re-surfaced. Dominated by MIT open-mtg already captured there. |

## 2. FOLD-IN-NOW Shortlist

**None.** No repo is fold-in-this-session. All five are no-license (cannot adopt code),
toy-scale (0-1 star), and either stale/dead or strictly dominated by artifacts we already
have. The single closest-to-actionable (tjonestj3/mtg-engine has the stack-object +
combat shapes we lack) is blocked by no-license + Rust-vs-Python + shallower-than-open-mtg.

## 3. Relation to Already-Catalogued Repos (dedup / complements)

- **dmeza31/mtg-tournament-tracker** -- NEW (not in backlog / ext-eval-* / thingstolookinto).
  Complements nothing; the Streamlit hits already in our docs are gareth-smith/17lands-
  Synergy-Browser (different repo). Its DB layer is subsumed by our meta-analyzer
  (SQLite + ModernBERT/KNN + MCP).
- **ndalmasso/deck-confidant** -- NEW. Its only mature capability (archetype
  classification) is already done better by mtg-meta-analyzer's ModernBERT/KNN. The
  unsupervised k-means angle is a weak counterpoint to LAYER-4 supervised classifiers
  (afreefaw/MTG-card2vec, TopDecked/MTGMeta-TS k-means++) already logged.
- **oboyone/Modernligan** -- NEW. No overlap with any catalogued repo; club-leaderboard
  bookkeeping, not metagame/sim. Glicko-2 is the only transferable concept.
- **FrancescoZese/MTGGraph** -- [KNOWN]. Already in github-discovery-backlog-2026-06-26.md
  LAYER 3 line 118 ("NONE | reference-only | Modern-metagame knowledge-graph
  visualization concept"). This eval confirms that grade and adds: classifier weaker than
  ours, no-license = reimplement-only.
- **tjonestj3/mtg-engine** -- NEW. Strictly dominated by MIT-licensed hlynurd/open-mtg
  (search-layer-bearing) already in ext-eval-mtg-engines-2026-06-26.md, and by the LAYER-1
  top pick magefree/mage (XMage) for any actual gap-closing reference.

## 4. Honest Skip List (one-line reasons)

- **dmeza31/mtg-tournament-tracker** -- 1*, no-license, 4mo-stale CRUD tracker; our
  meta-analyzer already owns the data layer; zero engine gaps touched.
- **ndalmasso/deck-confidant** -- thin 1-commit portfolio, no-license, Databricks/dbt
  stack mismatches our local SQLite/PyQt6; archetype classification we already do better.
- **oboyone/Modernligan** -- dead 0* solo club-league standings app, no-license; solves
  leaderboard bookkeeping, not meta analysis or sim.
- **FrancescoZese/MTGGraph** -- clean hobby viz but no-license + 0* + classifier we
  already beat; already catalogued reference-only.
- **tjonestj3/mtg-engine** -- 0* no-license one-day Rust scaffold, no rules enforcement /
  card coverage / search layer; dominated by MIT open-mtg, wrong language.

## Backlog impact

No edit to github-discovery-backlog-2026-06-26.md: zero repos qualify as a new real add
(four are skips, one -- MTGGraph -- is already line 118). The backlog stays as-is.

## Changelog
- 2026-06-26: Created (SURFACED). Synthesized 5 user-suggested repo evals into a verdict
  table + empty fold-in-now shortlist + dedup map + skip list. All 5 no-license, all skip;
  MTGGraph confirmed already [known] (backlog line 118). No backlog edit warranted.
