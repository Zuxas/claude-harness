# ROADMAP.md — Path to PT-Level Competitive Tool

**Last updated:** 2026-04-30
**Source:** Strategic assessment session 2026-04-30 (ultrathink)
**Purpose:** Durable roadmap for what makes this tool worth using at the highest levels of MTG

---

## What the tool is right now

Reliable for:
- Field-weighted match WRs in proactive vs proactive matchups (N=100k+ baseline)
- Goldfish speed benchmarks and card A/B testing in aggressive mirrors
- Meta trend tracking across Modern / Standard / Pioneer
- 44 pilot-seat playbooks (hand-authored, sim-informed)
- Personal real-match calibration loop via MTGA log parsing (data accumulating)

**Not reliable for:**
- Any matchup involving meaningful countermagic — WRs are wrong in a structured way
- Post-board games where role-shifts and interaction change the game plan
- Decisions that depend on what's in the opponent's hand

The underlying reason for the second category is architectural, not a tuning gap. See IMPERFECTIONS entries `sim-no-stack-priority` and `sim-no-hidden-information`.

---

## Priority Roadmap

Ordered by impact-to-effort ratio, not impressiveness.

---

### Phase 0 — APL Quality Foundation (1–2 sessions, already started)

**0A: Mulligan parameter sweep** ← NEW (Nettle 2-1-2 finding)
- Parametrically sweep (min_lands, min_creatures, max_mulligans) for each deck archetype using parallel_launcher at N=50,000 per combination
- Validate against Nettle's empirical 2-1-2 finding (aggro baseline)
- Derive per-role optimal thresholds: aggro / ramp / midrange / combo
- Apply to 16 SHIM/SHALLOW APLs in `mulligan-logic-portfolio-gap`
- Spec: `harness/specs/2026-04-30-mulligan-parameter-sweep.md`
- Effort: 90 min scripting + overnight compute

**0B: LLM-as-judge APL evaluation** ← NEW (mtg-agents.com finding)
- 30-question ground-truth test set: oracle fidelity + strategic decisions + keep/mulligan
- Gemma 12B as judge (calibrated against human evaluation first)
- Scores each APL independently of sim WR% — catches reasoning errors WR% misses
- Reference finding: tools access > model quality for domain accuracy (25pp gap)
- Spec: `harness/specs/2026-04-30-llm-as-judge-apl-evaluation.md`
- Effort: 90 min

**0C: Hybrid vector search in card_embeddings.py** ← NEW (Karn architecture)
- Add `find_cards_for_slot(description, format, card_type, max_cmc, color_ids)` wrapping existing `find_similar_cards()` with hard attribute post-filters
- Filters: format legality (card_data.legalities) + card type + CMC range + color identity
- Powers the SB optimizer (Phase 4) precisely — "find cheap removal in Modern" currently returns illegal cards
- Spec: `harness/specs/2026-05-03-hybrid-vector-search.md` (deferred post-PT)
- Effort: 1–2 hours

---

### Phase 1 — Data Quality (2–4 weeks, high impact, low risk)

**1A: MTGO league + Challenge scraper**
- Add MTGGoldfish 5-0 scraper + MTGO Challenge Top 32 standings to meta-analyzer
- Why it matters: highest-volume, real-stakes data source not yet in the DB. Standard and Modern data quality doubles overnight.
- How: HTML scraper for mtggoldfish.com/format-staples (5-0 lists public); Top 32 from MTGO event pages
- Effort: 1–2 weeks

**1B: Pre-event field override**
- CLI/UI for specifying expected event field % before a major tournament; all gauntlet numbers recalculate against it
- Why it matters: MTGGoldfish trailing 30-day is wrong for PT/RC prep — adapted lists, skill-weighted opposition
- How: `--field-override "Boros Energy=25,Jeskai Blink=10,..."` flag to parallel_launcher + UI in meta-analyzer
- Effort: 2–3 days

**1C: List-level clustering within archetypes**
- Cluster decklists by card composition to surface which build variant is winning, not just which archetype
- Why it matters: "Jeskai Blink 52% WR" hides whether it's the 4-Solitude list or the Fable list winning
- How: cosine similarity / k-means on card presence vectors; per-cluster WR display in meta-analyzer GUI
- Effort: 1–2 weeks

---

### Phase 2 — Interactive Simulation (4–6 weeks, transformative)

**2A: Play against the APL**
- You play player A; the APL plays player B. See your hand, make decisions, sim animates the opponent.
- Why it matters: reps are the single most important prep variable at the highest level. Physical testing gives 20 reps; interactive sim gives 500. Nobody else has this.
- How: PyQt6 game view (consistent with meta-analyzer UI), decision prompts at each priority pass, APL runs opponent normally
- Effort: 4–6 weeks

**2B: Post-game divergence report**
- After each interactive game, show where your decisions diverged from what the APL would have played in your seat
- Why it matters: converts a rep machine into a learning tool
- Effort: 1 week, builds on 2A

---

### Phase 3 — Stack / Priority System (2–3 weeks, unlocks ~40% of matchups)

**3A: Wire engine/stack.py into match runner**
- Counterspells get evaluated at cast time. Control APL decides whether to counter based on mana + threat priority. Simplified model — "does this APL want to spend interaction here?" — is sufficient.
- Why it matters: ~40% of the competitive field involves meaningful countermagic. WR numbers for those matchups are currently wrong in a structured way regardless of APL quality. This is the ceiling that APL tuning cannot break through.
- How: `engine/stack.py` already exists with `InteractionType.COUNTER`. Wire priority pass loop into `_run_player_turn` so spells can be responded to before resolution.
- Effort: 2–3 weeks

---

### Phase 4 — Sideboard Optimizer (2–3 weeks, genuinely novel)

**4A: SB card optimizer**
- Given your deck + SB card pool + matchup WR deltas per card + expected field, solve for the 15 cards that maximize field-weighted match WR.
- Why it matters: SB construction is the highest-leverage pre-event decision. Nobody has built this with sim-backed WR deltas. Frank Karsten does mana math; nobody does SB optimization.
- How: A/B test each potential SB card vs each matchup (gauntlet run with/without card). Formulate as combinatorial optimization (greedy hill-climb over 15 slots). Output optimal 15 with per-matchup delta explanations.
- Effort: 2–3 weeks

---

### Phase 5 — Dynamic Playbooks (1–2 weeks, leverage existing work)

**5A: Auto-generate playbooks from APL + sim data**
- After each gauntlet run, auto-generate matchup summaries and decision-tree logic from APL priority lists and sim outputs. Publish to website automatically.
- Why it matters: Playbooks are hand-authored and go stale. APLs already encode the decision logic — extract it.
- How: APL introspection to pull priority lists and conditionals; template to HTML; CI/CD push to GitHub Pages
- Effort: 1–2 weeks

---

### Phase 6 — Calibration Loop (ongoing — the moat)

**6A: Personal WR calibration database**
- MTGA match results already parsed. The missing piece: surface calibration gaps prominently at session start. Matchups where real WR diverges from sim WR are the highest-priority APL fix targets.
- Why it matters: Nobody else has a personal real-match → sim prediction → delta loop. Over time this produces a calibrated model specific to your play style that no generic analysis can replicate.
- How: Mostly built. `match_log` DB exists, `calibrate.py` exists. Make the gaps actionable in SESSION START PROTOCOL.
- Effort: Ongoing

---

## Honest competitive positioning

The tool will never beat experienced intuition for complex board states, table reads, or metagame positioning. It beats every existing resource on:

1. **Speed of iteration** — card A/B testing in hours vs days
2. **Breadth** — 17 matchups in 1 hour; physically impossible at a table
3. **Reproducibility** — same seed, same result; statistical signal visible through variance
4. **Personal calibration** — MTGA feedback loop produces a dataset no public analysis has

Phase 2 (interactive sim) is the unlock that changes the category. Everything before it is better data and better analysis. Phase 2 is preparation infrastructure that doesn't exist anywhere else.

---

## Gaps tracked in IMPERFECTIONS.md

| Imperfection | Impact |
|---|---|
| `sim-no-stack-priority` | ~40% of competitive matchups unreliable |
| `sim-no-hidden-information` | All decisions assume perfect information |
| `sim-no-instant-speed-combat` | Combat tricks / pump spells not modeled |
| `meta-analyzer-no-mtgo-league-data` | Missing highest-volume data source |
| `meta-analyzer-archetype-only-tracking` | No list-level variant clustering |
| `website-static-playbooks` | Playbooks stale, hand-authored |
| `website-no-sideboard-optimizer` | Highest-leverage decision tool missing |
| `mulligan-threshold-not-empirically-validated` | All APL keep() thresholds are author intuition, not simulation-validated |
| `no-llm-as-judge-apl-evaluation` | No test for whether APLs make correct strategic decisions |
| `card-search-no-attribute-filter` | find_similar_cards() ignores format legality / CMC / type |

---

## External Research (2026-04-30)

Two sources surveyed and their transferable patterns incorporated:

**Chris Nettle MTG AI series (Medium, 2019):** Independent goldfish sim; 2-1-2 mulligan finding (1M games validated). Added as Phase 0A.

**mtg-agents.com:** Multi-agent system (Router → Nissa/Karn). LLM-as-judge evaluation (+25pp accuracy from tools vs no-tools). Hybrid vector search (semantic + keyword filter). Added as Phase 0B and 0C.

Full findings: `harness/knowledge/tech/external-research-mtg-ai-2026-04-30.md`

## Changelog

- 2026-04-30: Created from strategic assessment session. Mapped 6-phase roadmap, honest capability framing, competitive positioning.
- 2026-04-30 (session 2): Added Phase 0 (APL quality foundation) from external research. Nettle 2-1-2 mulligan + mtg-agents LLM-as-judge + hybrid vector search. New IMPERFECTIONS: mulligan-threshold, no-llm-judge, card-search-no-filter.
