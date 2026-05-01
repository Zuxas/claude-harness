---
title: "APL Architecture — mtg-sim"
domain: "tech"
last_updated: "2026-04-23"
confidence: "high"
sources: ["code-inspection"]
---

## Summary
Action Priority Lists (APLs) encode each MTG archetype's game plan
as a Python class. Inherits from a small hierarchy that splits
single-player goldfish vs two-player match-aware logic. Registration
via `apl/__init__.py:APL_REGISTRY` is mandatory — forgetting to
register a deck causes silent gauntlet failure (learned 2026-04-23
when Izzet Lessons / Superior Doomsday / Azorius Aggro all had .py
files but no registry entries, collapsing a narrow gauntlet).

## Class hierarchy

### `BaseAPL` (`apl/base_apl.py`)
Single-player goldfish baseline. Exposes:
- `keep(hand, mulligans, on_play)` — mulligan decision
- `bottom(hand, n)` — London mulligan bottom-N
- `main_phase(gs: GameState)` — precombat sequencing
- `main_phase2(gs: GameState)` — postcombat mana dump
- `run_game(...)` — full goldfish game loop
- Helpers: `_cheapest_castable`, `_best_land`, `_play_land_if_able`,
  `_cast_all_castable`

Cantrip helpers (Brainstorm / Ponder) live here too.

### Role archetype parents (inherit from BaseAPL)
- `ControlAPL` (`control_base.py`) — override `main_phase` +
  `main_phase2` with hand-attack → wipe → threat → value
  sequencing, mana-reservation logic for reactive spells.
  Subclasses: `JeskaiControlAPL`, `IzzetLessonAPL`, etc.
- `AggroAPL` — fast clock, prioritize damage, evaluate threats
- `ComboAPL` — kill-turn-driven, sacrifice board presence for combo
- `MidrangeAPL` — balance threats and answers

### `MatchAPL` (`apl/match_apl.py`)
Two-player aware. Extends BaseAPL with:
- `main_phase_match(gs, opponent)` — opp-aware precombat
- `declare_attackers(gs, opponent)` — combat attack selection
- `declare_blockers(gs, opponent, attackers)` — block assignment
- `respond_to_spell(gs, opponent, spell)` — counter / redirect
- `end_step_actions(gs, opponent)` — EOT plays
- `combat_trick(gs, opponent, ...)` — pump / protection timing
- Helpers: `_opp_creature_count`, `_opp_hand_size`,
  `_opp_untapped_lands`, `_opp_likely_has_counter`

### `GoldfishAdapter` (in `match_apl.py`)
Wraps any BaseAPL to present MatchAPL interface. Defaults
`main_phase_match` to goldfish `main_phase` plus stashing
`_opp_gs` for base-class hooks to read. Fallback for decks
without hand-tuned MatchAPLs.

### `GenericMatchAPL`
Baseline two-player APL for decks without archetype-specific logic.

## The registration problem

`apl/__init__.py` has two dicts:
- `APL_REGISTRY` — (deck key → module, class, stub key/decklist path)
  for `get_apl()` lookups
- `MATCH_APL_REGISTRY` — same shape for `get_match_apl()`;
  falls back to `GoldfishAdapter` wrapping registered goldfish APL

**Writing the APL file is not enough.** Without a registry entry,
`get_apl(deck_name)` returns None, and the calling code fails with
"Could not load deck for X." Example: 2026-04-23 narrow gauntlet
had 100% matchup failure rate on first run because Izzet Lessons,
Superior Doomsday, and Azorius Aggro had APL files but zero registry
presence. Commit `a91733b` added the missing entries.

## Adding a new APL

1. Write the class in `apl/<slug>.py` or `apl/<slug>_standard.py`
   inheriting the appropriate role parent
2. Make sure the decklist exists at `decks/<slug>_<format>.txt`
3. Register in `APL_REGISTRY`:
   ```python
   "decknamekey": ("apl.slug_standard", "DeckNameAPL",
                   "decks/slug_standard.txt"),
   ```
4. For match-aware play, also register in `MATCH_APL_REGISTRY`
   (optional — falls back to `GoldfishAdapter`)
5. Test: `python -c "from apl import get_apl; print(get_apl('Deck Name'))"`
6. For full match load, also:
   ```python
   from generate_matchup_data import load_deck_and_apl
   main, side, apl = load_deck_and_apl('Deck Name', 'standard')
   assert main and apl
   ```

## How `_simple_play_turn` consumes APLs (post-MVP)

Pre-2026-04-23: `_simple_play_turn(gs, player, apl=None)` ignores
`apl`, plays heuristic. See [[match-runner-bug-2026-04-23]].

Post-MVP: builds a `GameState` view over `TwoPlayerGameState`'s
per-player flat fields (list aliasing makes mutations propagate),
calls `apl.main_phase(view)` + `apl.main_phase2(view)`, syncs back
`land_played` flag. Colorless-mana approximation, goldfish not
opp-aware — see bug note for limitations.

## Stub / shim APL pattern

For decks that need coverage but don't warrant hand-tuned logic:

```python
# apl/<slug>_standard.py
from apl.generic_apl import GenericAPL

class <Name>APL(GenericAPL):
    name = "<Name>"
    def __init__(self):
        super().__init__(deck_name="<Name>", role="<aggro|midrange|control>")
```

Used on 2026-04-23 for Izzet Control, Roaming Elementals, Mono Green
Aggro when the narrow gauntlet needed them as opponent-side decks.

## Cross-links
- [[sim-framework]] — what the sim is for
- [[match-runner-bug-2026-04-23]] — why matchup sims don't call APLs yet
- [[harness-architecture]] — broader harness context

## Changelog
- 2026-04-23: Created after the registration gap + match-runner bug
  made APL plumbing load-bearing for RC prep.
