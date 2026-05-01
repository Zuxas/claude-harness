# Gemma APL failure analysis — 2026-04-29

Source: T.0 analysis for spec `2026-04-29-gemma-apl-quality-lift.md`
Files examined: `apl/auto_apls/{landless_belcher,cutter_affinity,jeskai_phelia}.py`

## Failure modes by file

### landless_belcher.py (LandlessBelcherAPL)

- Class name suffix CORRECT (LandlessBelcherAPL ends in APL)
- `keep()` signature wrong: `on_play: List['Card']` instead of `on_play: bool`
- Uses invented card names ("Belcher's Moon", "Mana Drain") — wrong for Modern Landless Belcher
- Deeper in file: likely `gs.get(...)` API misuse per prior smoke failure log
- Card API: `card.is_land()` used correctly (method call). No `card.mana_cost <= int` issue.

### cutter_affinity.py (CutterAffinity)

- **Class name MISSING APL suffix** — smoke gate rejects before execution
- `card.mana_cost <= 2` — mana_cost is a string, not int. Correct: `card.cmc <= 2`
- `card.is_removal` — attribute does not exist on Card. No such API.
- `card.is_utility` — attribute does not exist on Card. No such API.
- `card.is_land` without `()` — should be `card.is_land()` (method call, not property)

### jeskai_phelia.py (JeskaiPhelia)

- **Class name MISSING APL suffix** — smoke gate rejects before execution
- `card.is_spell()` — does not exist on Card (use `not card.is_land()`)
- `card.is_interaction()` — does not exist on Card. No such API.
- `mulligans: List[str]` — wrong type; should be `mulligans: int`

## Root cause summary

Three root causes, in frequency order:

1. **Invented Card API** (all 3 files) — Gemma hallucinates methods like `is_removal`,
   `is_utility`, `is_interaction()`, `is_spell()`. The prompt gives no API reference.

2. **Missing "APL" class name suffix** (2 of 3) — prompt says "Extend BaseAPL" but doesn't
   say the class name must end in "APL". Smoke gate checks for this suffix.

3. **Wrong method signatures** (all 3) — `on_play` typed as `List` not `bool`;
   `mulligans` typed as `List[str]` not `int`. Prompt only says "implement keep(hand, mulligans, on_play)".

## Fix confidence

All three root causes are fixable via prompt engineering alone:
- Give the actual method signatures with correct types
- Provide an API reference listing real Card attributes/methods
- State the class name rule explicitly with an example
- Include a working exemplar showing the pattern

Claude path alternative is also available (OAuth confirmed working 2026-04-29).
