---
title: "Sim Framework — mtg-sim Role in Team Resolve Workflow"
domain: "tech"
last_updated: "2026-04-23"
confidence: "high"
sources: ["code-inspection", "conversation"]
---

## Summary
The mtg-sim repo is a competitive Magic simulator used by Team
Resolve for brew validation and sideboard construction. Its role
is **complement to [[meta-analyzer]]'s tournament matchup_matrix,
not replacement.** Tournament data answers "what wins now"; the
sim answers "how does my deck play vs a brew with no tournament
sample size."

## Purpose in the workflow
- **Primary use:** evaluate matchups for new or uncovered archetypes
  where the meta-analyzer DB has no data (e.g., the ~25% of current
  Standard meta that's Strixhaven-new).
- **Secondary use:** sideboard plan validation — try IN/OUT changes,
  re-run the matchup, compare WRs.
- **Not for:** predicting real-world tournament win rates when
  tournament data already exists. The matchup_matrix is always
  stronger evidence than any sim output.

## Architecture
- **APL-driven** (Action Priority List, SimulationCraft-style).
  Each archetype has a class encoding its game plan. See
  [[apl-architecture]].
- **Two execution modes:**
  - Goldfish — single deck vs a kill-turn distribution for
    opponents. Fast, used for APL tuning.
  - Match — two decks play against each other with full game state.
    Slower, used for real matchup WRs.
- **Handler registry** — `ETB_EFFECTS`, `SPELL_EFFECTS` etc. hold
  per-card effect functions invoked on cast/ETB resolution. 2,009
  handlers registered as of 2026-04-23.

## Current state (2026-04-23)
- Handler coverage: **99.32% Standard, 99.25% Modern** cast-weighted
- Match runner: **broken** — `_simple_play_turn` ignores the `apl`
  param, plays "cheapest creature" heuristic for both sides. See
  [[match-runner-bug-2026-04-23]]. MVP wiring deferred to 2026-04-24.
- Goldfish paths: believed working (used by apl_tuner nightly runs)
- Priority queue pipeline: built but saturated at top 50 for both
  formats
- Telemetry into GameState: not wired (deferred pre-handler-loop work)

## Known limitations
Even after the match-runner MVP lands:
1. **Colorless-mana approximation** — no color-aware mana in the
   two-player view (MVP limitation). Deferred refinement.
2. **Goldfish sequencing vs two-player awareness** — APL plays as if
   alone; opp-aware `main_phase_match` + `declare_attackers` /
   `declare_blockers` / `respond_to_spell` exist but aren't wired.
   See [[apl-architecture]] for the upgrade path.
3. **No priority/stack modeling** — spells resolve immediately on
   cast. Counterspells, split second, timing-sensitive interactions
   not modeled.
4. **Triggers unverified** end-to-end in match mode.

## Why these limitations are acceptable for RC prep
- The matchup_matrix covers 75% of meta with real data (see
  [[rc-prep-izzet-lessons-may29]]) — sim isn't load-bearing there.
- For the 25% sim-only territory, directional answers (does Lessons
  go >40% vs brew X, or <30%?) are enough to guide sideboard work.
- Paper testing is the final calibration regardless of sim output.

## Not for (explicit)
- Claiming "the sim says deck X wins at N% against the field."
  Sim WRs are not tournament WRs.
- Overriding matchup_matrix data where it exists.
- Replacing paper testing for RC lock-in decisions.

## Cross-links
- [[apl-architecture]] — class hierarchy and methods
- [[match-runner-bug-2026-04-23]] — active bug blocking match mode
- [[meta-analyzer]] — tournament data source
- [[harness-architecture]] — how the sim fits the broader harness
- [[rc-prep-path-forward]] — active roadmap

## Changelog
- 2026-04-23: Created after the match-runner bug reframed sim's
  role in RC prep.
