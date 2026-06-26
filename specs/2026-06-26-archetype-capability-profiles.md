---
title: Archetype Capability Profiles + Engine-Fidelity Data-Quality Gate
status: PROPOSED
created: 2026-06-26
project: mtg-sim (ARL)
estimated_time: 4-6h (profile builder + gate wiring + backfill for active archetypes)
related: harness/IMPERFECTIONS.md, mtg-sim/CLAUDE.md (ARL spec), 2026-06-26 ARL build
supersedes:
superseded_by:
---

## Goal
Every archetype the ARL touches must carry a full, explicit understanding of its
own **capabilities and limitations** before an APL is generated or its gauntlet
data is trusted. Without this, autonomously generated APLs play the deck wrong,
"pass" smoke, and feed false win-rates into `promoted` — bad data that compounds.

User principle (2026-06-26): "each archetype should have a full understanding of
its capabilities and limitations otherwise the APL won't work properly and we'll
have bad data."

## The two mechanisms

### 1. Archetype Capability Profile  (per deck, durable)
A structured profile written to `mtg-sim/docs/archetype_profiles/<slug>.md` (+ a
machine-readable `<slug>.json` sibling) BEFORE APL generation. It is the
"what this deck is trying to do" brief the generator and the human both read.

Profile schema (JSON):
```json
{
  "slug": "amulet_titan",
  "archetype": "Amulet Titan",
  "format": "modern",
  "win_conditions": ["Primeval Titan -> land toolbox -> combat", "Scapeshift OHKO"],
  "core_engine": ["Amulet of Vigor + bounce lands", "Titan ETB land fetch"],
  "key_cards": [{"name": "Primeval Titan", "role": "payoff"},
                {"name": "Amulet of Vigor", "role": "enabler"}],
  "sequencing_rules": ["T1 ramp before any cantrip", "hold Summoner's Pact for the turn you can pay"],
  "mana_profile": {"colors": "Gx", "ramp": "high", "interaction": "low"},
  "sideboard_intent": {"vs_aggro": "+lifegain/sweepers", "vs_combo": "+interaction"},
  "expected_kill_turn": [3, 4],
  "known_weaknesses": ["graveyard/land hate", "fast combo on the draw"],
  "engine_fidelity": {
    "modeled": ["land ramp", "combat", "Titan ETB"],
    "NOT_modeled": ["instant-speed Pact-into-bounce stack tricks"],
    "blocking_imperfections": [],
    "confidence": "high"        // high | medium | low | unmodelable
  }
}
```

How the profile is built (in priority order):
- Reuse existing oracle/card understanding: `card_handlers_verified.py` (L1 card
  text already 100% for Standard), oracle audits, and `auto_pipeline._classify_deck`
  for key-card extraction.
- LLM pass (qwen2.5-coder / Claude) over the decklist + card oracle text to draft
  win_conditions / core_engine / sequencing_rules / sideboard_intent. Grounded in
  real oracle text (never invent card abilities).
- `engine_fidelity` computed by matching the deck's mechanics against a
  MECHANIC -> IMPERFECTION map (see below). This is deterministic, not LLM.

### 2. Engine-Fidelity Data-Quality Gate  (in the ARL loop)
A mechanic-coverage check that decides whether the gauntlet FWR is trustworthy.

Build `mtg-sim/data/engine_fidelity_map.json` mapping unmodeled mechanics to the
IMPERFECTION that blocks them, e.g.:
```json
{
  "warp": "engine-fidelity-gaps-warp-mechanic-not-modeled",
  "counterspell_on_stack": "sim-no-stack-priority",
  "hidden_information": "sim-no-hidden-information",
  "instant_speed_combat_trick": "sim-no-instant-speed-combat",
  "planeswalker_loyalty": "planeswalker-loyalty-not-tracked"
}
```

Gate logic, applied at ARL loop step 10 (evaluate), using the profile's
`engine_fidelity.confidence`:
- **high**  -> normal promote/mutate/discard thresholds.
- **medium** -> may promote but tag result `data_quality:"medium"`; never auto-feed
  into playbooks without a [needs-validation] tag.
- **low**   -> DO NOT promote regardless of FWR; set `verdict="low_confidence"`,
  record the result with `data_quality:"low"` and the blocking imperfections.
- **unmodelable** (deck's primary win condition depends on an unmodeled mechanic)
  -> DO NOT publish a confident gauntlet number, BUT this is NOT a dead-end. Record
  `verdict="unmodelable"`, and ENQUEUE an engine-capability work item to the
  **modelability backlog** (`mtg-sim/data/modelability_backlog.json`) with: the
  mechanic, the blocking imperfection, the field-share x win-impact priority, AND
  the **real-world replication target** (the actual tournament WR + at least one
  known winning line this deck must be able to reproduce once modeled). The dynamic
  modelability workflow (see below) then works that item until the engine can model
  AND PROVE it. Set `hitl=true` only when human input is genuinely needed.

USER PRINCIPLE (2026-06-26): "unmodelable" is a temporary state. Everything is
quantifiable; these decks win in reality, so the model just has to replicate those
wins and PROVE it. The gate exists to stop bad data AND to generate the exact
engine-capability backlog that makes every deck modelable over time. The deeper we
model, the stronger the bot.

This means a deck like Izzet Lessons (inverted vs PT data because hand-advantage
isn't modeled) or any counterspell-heavy control deck is correctly flagged as
low/unmodelable instead of silently producing a wrong 9% or inflated 98% FWR
(both real past symptoms — see MEMORY.md / IMPERFECTIONS standard-apl-goldfish-only).

## Files
- NEW `mtg-sim/scripts/arl_profile.py` — `build_profile(deck_file, format) -> dict`;
  writes docs/archetype_profiles/<slug>.{md,json}. CLI for standalone use.
- NEW `mtg-sim/data/engine_fidelity_map.json` — mechanic -> imperfection map.
- EDIT `mtg-sim/scripts/arl_generate_apl.py` — consume the profile (win cons +
  sequencing rules) as grounding context in the generation prompt.
- EDIT `mtg-sim/scripts/arl_loop.py` — step 6.5: build/load profile before smoke;
  step 10: apply the fidelity gate to decide promote vs low_confidence vs
  unmodelable; carry `data_quality` + `confidence` into the result record.
- EDIT `mtg-sim/scripts/arl_state.py` — result schema gains `data_quality` +
  `confidence` + `blocking_imperfections`.
- EDIT `mtg-sim/scripts/arl_distill.py` — only distill heuristics from results with
  confidence in {high, medium}; never from low/unmodelable.

## Validation gates
- A control/combo deck whose core is unmodeled is flagged `unmodelable` and the
  loop pauses (does NOT promote) — verify with a counterspell-heavy Modern deck.
- A clean aggro/ramp deck (Boros Energy, Amulet Titan) profiles `high` and runs
  normally.
- No result with confidence in {low, unmodelable} ever lands in `promoted`.
- Profiles are grounded: spot-check that win_conditions/sequencing cite real cards
  from the decklist with real oracle abilities (no hallucinated lines).

## Stop conditions
- If the profile builder hallucinates card abilities (cites text not in oracle),
  stop and tighten the prompt to inject oracle text per key card.
- If many Modern archetypes flag `unmodelable`, that is not a failure — it is the
  prioritized work surfacing. Feed every one to the modelability backlog, rank by
  field-share x win-impact, and let the dynamic modelability workflow climb the
  ladder (model -> replicate -> prove) fastest-payoff first. Never paper over with
  bad data; never abandon a deck as permanently unmodelable.

## Why this matters to the north star
"Stockfish for MTG" is only as trustworthy as its evaluation. An eval that returns
confident numbers for positions the engine can't actually represent is worse than
no eval. This spec makes the loop *honest*: it quantifies what it can, and clearly
marks what it cannot yet — turning engine gaps into a prioritized backlog instead
of silent bad data.

## Changelog
- 2026-06-26: Authored from user requirement during autonomous session. Queued as
  ARL build wave 2 (wire after the base loop from the 2026-06-26 ARL build validates).
