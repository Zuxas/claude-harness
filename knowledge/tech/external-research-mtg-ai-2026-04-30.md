---
name: External MTG AI Research Findings
description: Transferable technical patterns from Nettle MTG AI series and mtg-agents.com — mulligan thresholds, LLM-as-judge evaluation, hybrid vector search
type: tech
---

# External MTG AI Research Findings (2026-04-30)

## Source 1: Chris Nettle MTG AI Series (Medium, 2019)

Three-part series + one opinion piece. A goldfish simulation project that independently
built the same approach as mtg-sim, 7 years earlier. One genuinely useful empirical finding.

### The 2-1-2 Mulligan Finding

Nettle ran 1 million simulated games across 7 mulligan heuristics on a 40-creature 20-land mono-red deck.
Strategy naming: `[min_lands]-[min_creatures]-[max_mulligans]`.

| Strategy | Description | Result |
|---|---|---|
| 1-1-1 | 1 land + 1 creature, 1 mulligan | Too loose |
| 1-1-2 | 1 land + 1 creature, 2 mulligans | Slightly better |
| 2-1-2 | 2 lands + 1 creature, 2 mulligans | **Optimal** |
| 2-2-2 | 2 lands + 2 creatures, 2 mulligans | Too strict |

**Finding: 2-1-2 is the empirically optimal mulligan strategy for aggro decks.**
- Mulligan frequency: ~4.8% (loose strategies)
- Used Paris mulligan (no scry) — matches current mtg-sim behavior
- Validated for mono-aggro; other roles (control/combo/ramp) have different optimal thresholds

**Application to mtg-sim:** The `mulligan-logic-portfolio-gap` IMPERFECTION tracks 16/52 APLs
with inadequate keep() logic. Boros Energy and Izzet Prowess should target `len(lands) >= 2 and len(threats) >= 1`
with max 2 mulligans. APLs using `len(lands) >= 2` without threat checks are running 2-0-2 effectively,
which Nettle's data shows is suboptimal (floods/removal-heavy hands kept too often).

**Methodology note:** The parameter sweep approach (vary thresholds, run large-N sim, measure kill turn
distribution) is directly replicable with parallel_launcher. Spec 2026-04-30-mulligan-parameter-sweep.md
defines the implementation.

### Series Scope
- Part 1: Introduction (no technical content)
- Part 2: MVP — greedy goldfish sim, kill turn measurement (same as mtg-sim's goldfish)
- Part 3: Mulligan optimization — the 2-1-2 finding
- "Mana Screw" article: opinion piece proposing a homebrew rule, no data
- No GitHub repo ever published. Series stopped at Part 3.

---

## Source 2: mtg-agents.com + Independent Evaluation Paper

A production multi-agent web app (Next.js + GPT-4.1, European team, unrelated to Nettle).
Three specialized agents behind a router. Evaluated independently by Florian Krempl.

### Architecture

```
User message
    │
    ▼
Orchestrator Agent
  - Intent classification: rules | deck | trivia | guardrail
  - Routes to appropriate specialist
  - Handles off-topic rejection
    │
    ├─ Rules question ──► Nissa
    │                      - RAG over Comprehensive Rules
    │                      - Scryfall card lookups + rulings
    │                      - Stack Exchange + RulesGuru search
    │                      - Verification buddy (extracts sources)
    │
    └─ Deck question ───► Karn
                           - Hybrid vector search (semantic + keyword filter)
                           - Scryfall 40k card database
                           - Deck list reader/statistics
                           - Single-card swap proposer
```

### Evaluation Results (from independent paper, 45-question test set)

| Setup | Accuracy |
|---|---|
| GPT-4o, no tools, basic prompt | 65% |
| GPT-4.1, no tools, better prompt | ~67% |
| GPT-4.1, full tool access | **~90%** |

**Key finding: tools matter more than model.** The 25pp gap comes entirely from retrieval access,
not model quality. Swapping GPT-4o for GPT-4.1 without tools barely moves accuracy.

**Application:** Confirms that Claude Code + mtg MCP server (69 tools, Scryfall live) is the
right architecture. Upgrading from Claude Sonnet to Claude Opus matters less than having better
retrieval infrastructure.

### LLM-as-Judge Evaluation Methodology

The evaluation paper describes a repeatable methodology:

1. Build a ground-truth test set (45 questions across 3 categories: rules, card search, guardrails)
2. For each question: expected answer (human-written ground truth)
3. Run system on each question, collect output
4. LLM judge evaluates: "does this output contain all facts from the expected answer?"
5. Score = correct / total questions

**Critical finding:** Iterate on the judge prompt until it matches human evaluation scores. Early judge
prompts disagreed with human judgment — calibrate on 5-10 known cases before trusting automated scores.

**Application to mtg-sim:** Build a 30-50 question APL decision test set. Questions:
- Type 1 (oracle fidelity): "Given oracle text X, does the APL implement the effect correctly?"
- Type 2 (strategic decisions): "Given board state X, the playbook says Y. Does the APL do Y?"
- Type 3 (keep/mulligan): "Given hand X for deck Y, keep or mulligan?"

Gemma 12B as judge — calibrate on 5 known-correct and 5 known-incorrect APL decisions first.
Spec 2026-04-30-llm-as-judge-apl-evaluation.md defines the full implementation.

### Karn's Hybrid Vector Search Pattern

Pure semantic vector search returns conceptually similar cards but ignores hard constraints
(format legality, card type, CMC, color identity). Karn adds a filter layer:

```
Step 1: Semantic embedding search → candidate pool (large n, e.g. 100 cards)
Step 2: Hard-filter by:
         - Format legality (is this card legal in Modern/Standard/etc.)
         - Card type (Instant, Creature, Sorcery, etc.)
         - CMC <= max_cmc (budget constraint)
         - Color identity (within deck's color restriction)
Step 3: Return top-n from filtered set
```

**Application to mtg-meta-analyzer:** `analysis/card_embeddings.py:find_similar_cards()` does pure
vector search. Add `find_cards_for_slot(description, format, card_type, max_cmc, color_ids)` wrapper.
Filter uses `card_data.legalities` JSON column + `card_data.type_line` + `card_data.cmc`.
Powers the SB optimizer (ROADMAP Phase 4) precisely. Spec 2026-05-03-hybrid-vector-search.md.

### Context Loading Pattern

Karn's quality improves significantly when given full context upfront:
`deck + statistics + description + constraints` before any question.

For Claude Code deck analysis: always prepend:
- Current decklist (full 75)
- Format
- Field-weighted WR from last gauntlet
- Known weaknesses (from IMPERFECTIONS or sim data)
- Target event and field
- Recent calibration (real match WR from savecraft vs sim prediction)

This mirrors the 25pp tools-vs-no-tools gap — context provision is data access, same principle.

---

## Summary: What's Transferable

| Finding | Source | Priority | Status |
|---|---|---|---|
| 2-1-2 mulligan optimal for aggro | Nettle Part 3 | HIGH | Spec written, unimplemented |
| LLM-as-judge APL evaluation | mtg-agents.com eval paper | HIGH | Spec written, unimplemented |
| Hybrid vector search for card slot analysis | Karn architecture | MED | Spec written, deferred post-PT |
| Tools > model for domain accuracy | Eval paper finding | INFO | Architecture already correct |
| Context loading pattern for deck analysis | Karn blog post | LOW | Protocol note in harness CLAUDE.md |

## Changelog

- 2026-04-30: Created from ultrathink deep research session.
