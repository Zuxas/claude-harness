---
title: "card_specs framework: extract per-card decision logic from APLs"
status: "PROPOSED"
created: "2026-04-29"
updated: "2026-04-29"
project: "mtg-sim"
estimated_time: "240-360 min (full); 60-90 min (POC only — Phase 3 below)"
related_findings:
  - "harness/knowledge/tech/jeskai-blink-card-specs-2026-04-28.md"
  - "harness/knowledge/tech/mulligan-audit-2026-04-28.md"
related_commits: []
supersedes: null
superseded_by: null
---

# card_specs framework: extract per-card decision logic from APLs

## Goal

Establish `apl/card_specs/` as a parallel layer to `engine/card_handlers_verified.py`. Where `card_handlers_verified` covers RESOLUTION (what happens when a card resolves on the stack), `card_specs` covers DECISION (when an APL chooses to play it, what targeting to pick, sequencing). Cards shared across multiple APLs (Phlage, Galvanic Discharge, Phelia, Solitude, Ephemerate, Quantum Riddler, Ragavan, Teferi TR) get one canonical implementation that all APLs import. Result:

1. **Dedup ~70% of nonland card logic** across `boros_energy.py`, `jeskai_blink_match.py`, `uw_blink_match.py`, `esper_blink_match.py`, and several other APLs.
2. **APL files become orchestration**, ~30-80 lines vs current 200-595L. Author thinks in plays, not in mana payment / state mutation.
3. **Auto-pipeline (spec #4 from 2026-04-29 chain) Gemma quality lift becomes "compose specs"** instead of "generate Python from scratch." Smoke gate pass rate should improve significantly.
4. **Future card additions to a deck** become "import the card_spec, add to orchestration list" — minutes vs hours.

## Scope

### In scope (full spec)

Phase A — Framework + Tier 1 cards (Phlage, Galvanic, Ragavan, Phelia, Solitude, Ephemerate). High reuse across 3+ decks each. ~120-180 min.

Phase B — Migration of `boros_energy.py`, `jeskai_blink_match.py`, `uw_blink_match.py`, `esper_blink_match.py` to call card_specs. Pure refactor; bit-stable canonical gauntlet must hold (64.5% / 78.8% within 0.0pp). ~120-180 min.

Phase C — Tier 2 cards (Quantum, Teferi, Consign, Wrath). Lower reuse, but still 2-3 decks each. ~60-90 min.

### In scope (POC only — Phase 3 of 2026-04-28 night session)

Just Phlage extraction + new `apl/jeskai_blink.py` (goldfish only) using card_specs. ADDITIVE: don't touch `boros_energy.py` or `jeskai_blink_match.py` — they keep their inline implementations. ~60-90 min.

This POC validates the framework shape. Full migration is Phase A + B.

### Explicitly out of scope

- **Mulligan-keep parameterization via card_specs.** Separate concern; spec covered by `mulligan-logic-portfolio-gap` IMPERFECTION (2026-04-28). Card_specs are for `main_phase` orchestration; `keep()` parameterization stays with `aggro_base` / `combo_base` / `control_base` / `ramp_base`.
- **Match-context predicates inside card_specs.** Card_specs accept `opponent` argument but stay agnostic; matchup-specific logic (need_solitude_for_aggro, etc.) stays in MatchAPL subclass.
- **Bo3 sideboarded compositions.** Future spec.
- **Engine-level changes.** card_specs only call existing engine APIs (`gs.cast_spell`, `gs.tap_lands`, `gs.zones.*`, `gs.mana_pool.*`).
- **Tier 3 cards (Casey Jones, Fable, Prismatic, March).** Lower reuse; can stay inline in their respective APLs.

## Pre-flight reads

- `harness/knowledge/tech/jeskai-blink-card-specs-2026-04-28.md` — per-card decision specs, oracle text, decision priority, cross-refs.
- `mtg-sim/apl/jeskai_blink_match.py` — 595L source-of-truth for many cards' inline impls.
- `mtg-sim/apl/boros_energy.py` — Phlage / Galvanic / Ragavan source.
- `mtg-sim/apl/uw_blink_match.py` — Phelia / Solitude / Ephemerate source.
- `harness/knowledge/tech/spec-authoring-lessons.md` — methodology lessons (esp. v1.5 `parallel-entry-points-need-mirror-fix` — applies here: any APL touched by Phase B must have its goldfish AND match variant updated together).
- `mtg-sim/CLAUDE.md` — note that Boros Energy is locked at canonical 64.5% baseline; bit-stable gate is mandatory for any boros_energy.py touch.

## Steps

### Step 1 — Framework skeleton (~10 min)

Create `apl/card_specs/__init__.py`:

```python
"""apl/card_specs/ — per-card decision logic shared across APLs.

Where engine/card_handlers_verified.py covers RESOLUTION (what happens
when a card resolves on the stack), card_specs covers DECISION (when an
APL chooses to play it, what targeting to pick, sequencing).

Each spec module exports:
  NAME: str         -- exact oracle name
  cast(gs, opponent=None, **kwargs) -> bool  -- main decision/resolution
  Optional: hardcast/escape/evoke/attack_trigger sub-actions

Specs are agnostic about MatchAPL vs goldfish — opponent=None signals
goldfish; predicates internally check for None and skip dead-in-goldfish
branches (e.g., Solitude evoke without a target).
"""
from . import phlage, ragavan, phelia, solitude, ephemerate, galvanic_discharge

__all__ = ["phlage", "ragavan", "phelia", "solitude", "ephemerate",
           "galvanic_discharge"]
```

Tests directory: `tests/test_card_specs.py` — one test class per spec module.

### Step 2 — Tier 1 spec extraction (~60-90 min)

Per-card module template:

```python
# apl/card_specs/phlage.py
"""Phlage, Titan of Fire's Fury — `{1}{R}{W}` hardcast / `{R}{R}{W}{W}` escape.

Oracle:
  When Phlage enters, deal 3 damage to any target, you gain 3 life,
  then sacrifice it. Escape — `{R}{R}{W}{W}`, exile 5 cards from GY.
  As a 6/6 escaped permanent, attack trigger deals 3 + life 3.

Decks using this spec: Boros Energy, Jeskai Blink, multiple Modern.
"""
from data.card import Card, Tag

NAME = "Phlage, Titan of Fire's Fury"
HARDCAST_CMC = 3
ESCAPE_CMC = 4
ESCAPE_GY_EXILE = 5

def hardcast(gs, opponent=None) -> bool:
    """Hardcast Phlage from hand. Deals 3 face dmg + 3 life, sacs to GY.
    Returns True if cast."""
    for c in list(gs.zones.hand):
        if c.name == NAME and gs.mana_pool.can_cast(c.mana_cost, c.cmc):
            gs.mana_pool.pay(c.mana_cost, c.cmc)
            gs.zones.hand.remove(c)
            gs.damage_dealt += 3
            gs.life += 3
            gs.zones.graveyard.append(c)  # sacrifice
            gs._log(f"  Phlage hardcast: 3 face + 3 life (sac)")
            return True
    return False

def escape(gs, opponent=None) -> bool:
    """Escape Phlage from GY. Returns True if escaped."""
    gy_phlages = [c for c in gs.zones.graveyard if c.name == NAME]
    non_phlage_gy = [c for c in gs.zones.graveyard if c.name != NAME]
    if not gy_phlages or len(non_phlage_gy) < ESCAPE_GY_EXILE:
        return False
    if gs.mana_pool.total() < ESCAPE_CMC:
        return False
    phlage = gy_phlages[0]
    non_phlage_gy.sort(key=lambda c: getattr(c, 'cmc', 0))
    for c in non_phlage_gy[:ESCAPE_GY_EXILE]:
        gs.zones.graveyard.remove(c)
        gs.zones.exile.append(c)
    gs.zones.graveyard.remove(phlage)
    gs.zones.battlefield.append(phlage)
    phlage.turn_entered = gs.turn
    phlage.summoning_sickness = True
    gs.damage_dealt += 3
    gs.life += 3
    try:
        gs.mana_pool.pay("{R}{R}{W}{W}", ESCAPE_CMC)
    except Exception:
        pass
    gs._log(f"  PHLAGE ESCAPE: 6/6 + 3 dmg + 3 life")
    return True

def attack_trigger(gs, opponent=None) -> None:
    """Phlage's combat damage trigger: 3 dmg + 3 life on each attack."""
    if opponent:
        gs.damage_dealt += 3
    gs.life += 3
```

Each card gets:
- `NAME` constant
- Per-action functions (cast / hardcast / escape / evoke / attack_trigger)
- Goldfish-aware: `opponent=None` skips dead branches
- Returns `bool` from "did I do anything?" functions for orchestration

Tier 1 cards: Phlage, Galvanic Discharge, Ragavan, Phelia, Solitude, Ephemerate.

### Step 3 — Test each spec module (~30 min)

`tests/test_card_specs.py`:

```python
def test_phlage_hardcast_pays_mana_adds_damage():
    gs = _stub_game_state(hand=[Phlage], mana=3)
    assert phlage.hardcast(gs) is True
    assert gs.damage_dealt == 3
    assert gs.life == 23  # 20 + 3
    assert Phlage not in gs.zones.hand
    assert Phlage in gs.zones.graveyard

def test_phlage_escape_requires_5_gy_and_4_mana():
    gs = _stub_game_state(gy=[Phlage] + [_filler]*4, mana=4)
    assert phlage.escape(gs) is False  # only 4 GY non-Phlage; need 5
    gs.zones.graveyard.append(_filler)  # now 5 non-Phlage
    assert phlage.escape(gs) is True
    assert Phlage in gs.zones.battlefield
    assert gs.damage_dealt == 3
```

### Step 4 — POC: rewrite `apl/jeskai_blink.py` to compose specs (~30 min)

```python
# apl/jeskai_blink.py
"""Jeskai Blink (Modern) goldfish APL composing apl/card_specs/."""
from apl.base_apl import BaseAPL
from apl.card_specs import phlage, ragavan, phelia, ephemerate
# (Solitude / Galvanic skipped — DEAD in goldfish)

class JeskaiBlinkAPL(BaseAPL):
    name = "Jeskai Blink"
    win_condition_damage = 20
    max_turns = 12

    def keep(self, hand, mulligans, on_play):
        # Tighter than match-keep: goldfish needs creature curve, not interaction
        if len(hand) <= 4: return True
        lands = sum(1 for c in hand if c.is_land())
        cheap_creatures = sum(1 for c in hand if not c.is_land() and getattr(c, 'cmc', 99) <= 3)
        if lands == 0 or lands > 5: return False
        if lands >= 2 and cheap_creatures >= 2: return True
        return mulligans >= 2

    def bottom(self, hand, n):
        lands = sorted([c for c in hand if c.is_land()], key=lambda c: c.name)
        spells = sorted([c for c in hand if not c.is_land()],
                        key=lambda c: -getattr(c, 'cmc', 0))
        return (lands[4:] + spells)[:n]

    def main_phase(self, gs):
        self._play_land(gs)
        gs.tap_lands()
        # Cheap creatures first (curve)
        ragavan.cast(gs)
        phelia.cast(gs)
        # Phlage: prefer escape > hardcast (escape = 6/6 vs hardcast = one-time 3 dmg)
        if not phlage.escape(gs):
            phlage.hardcast(gs)
        # Ephemerate on best ETB if available
        ephemerate.cast(gs)  # internally picks best ETB target
```

### Step 5 — Validation gate: goldfish kill turn (~5 min)

Run direct (NOT sim.py — bug at line 50):

```python
from data.deck import load_deck_from_file
from apl.jeskai_blink import JeskaiBlinkAPL
from engine.runner import run_simulation

main, _ = load_deck_from_file('decks/jeskai_blink_modern.txt')
res = run_simulation(JeskaiBlinkAPL(), main, n=2000, seed=42, on_play=True)
print(f"Avg kill turn: {res.avg_kill_turn():.2f}")
print(f"Win rate: {len(res.kill_turns)/2000*100:.1f}%")
```

**Acceptance:** kill turn at or below T6.43 (the SHIM baseline) at n=2000 seed=42.
**Stop trigger:** kill turn >T6.50 → composition has a bug; investigate before proceeding to Phase B migration.

### Step 6 (Phase B only) — Migrate boros_energy.py to use card_specs

Pure refactor: replace inline Phlage/Galvanic/Ragavan code with `from apl.card_specs import phlage, galvanic_discharge, ragavan` calls. Behavior must be byte-identical.

Validation: bit-stable canonical gauntlet:

```bash
cd mtg-sim
python parallel_launcher.py --deck "Boros Energy" --format modern --n 1000 --seed 42  # pre
# (refactor)
python parallel_launcher.py --deck "Boros Energy" --format modern --n 1000 --seed 42  # post
diff <(jq -S . data/parallel_results_<pre>.json) <(jq -S . data/parallel_results_<post>.json)
```

Acceptance: bit-identical OR per-matchup max-dev <0.1pp (rounding noise from float order). Stop trigger: any matchup deviation >0.5pp.

### Step 7 (Phase B continued) — Migrate jeskai_blink_match.py + uw_blink_match.py + esper_blink_match.py

Same pure-refactor pattern. Bit-stable check after each.

### Step 8 (Phase C) — Tier 2 extraction

Quantum Riddler, Teferi TR, Consign to Memory, Wrath of the Skies. Same pattern.

## Validation gates

| Gate | Acceptance | Stop trigger |
|---|---|---|
| 1.1 (POC) Goldfish kill turn | T6.43 ± 0.05 at n=2000 seed=42 | >T6.50 |
| 1.2 (POC) New Jeskai Blink wins ≥97% in 2000 games | ≥97% | <97% |
| 2.1 (Phase B) Boros Energy canonical | bit-identical or <0.1pp deviation | >0.5pp matchup deviation |
| 2.2 (Phase B) Variant Boros canonical | <0.1pp aggregate deviation | >0.5pp |
| 2.3 (Phase B) Jeskai Blink match in 14-deck field | <0.1pp deviation | >0.5pp |
| 3.1 (Phase C) Quantum / Teferi etc. unit tests | all pass | any fail |
| 4.1 (Auto-pipeline test) Gemma generates spec composition | smoke gate pass rate ≥1 of 3 | 0/3 still fail (no improvement) |

## Stop conditions

- Step 1-2 reveals card_specs interface doesn't fit (e.g., engine API too coupled to APL state): STOP, redesign interface, surface to user.
- Step 4 Phase B reveals Boros Energy bit-deviation >0.5pp: STOP, the refactor has a behavioral bug. Diff inline-code-vs-spec carefully; common cause is mana-payment-order differences or zone-list iteration order.
- Step 5 validation gate fails: STOP. Goldfish kill turn ceiling for Jeskai Blink is bounded by deck design (33% dead cards). If Phase 4 produces T7+, the framework is fine but the deck inherently can't goldfish faster.

## Connection to 2026-04-29 chain

This spec ALIGNS with chain spec #4 (Gemma APL quality lift). Phase A (framework + Tier 1) provides material for Gemma to compose, lifting smoke pass rate. Recommended ordering for tomorrow's chain:

1. Spec #1 (OAuth probe) — already done 2026-04-28
2. Spec #2 (drift-detect ARCH fix) — already done 2026-04-28
3. Spec #3 (RMW-race cluster fix) — already done 2026-04-28
4. **NEW: Phase A of this spec (framework + Tier 1)** — 2-3 hrs
5. Spec #4 (Gemma APL quality lift) — incorporates spec composition
6. Spec #5 (drift-detect 8th check)
7. Spec #6 (sibling 7th check)
8. Phase B of this spec (migration) — 2-3 hrs
9. Spec #7 (within-matchup parallelism)
10. Spec #8 (Stage A/B 100k re-validation) — runs over Phase B baseline-stable result
11. Spec #9 (Friday PT-readiness)

Total chain reshapes from 8 specs (~7-9 hr) to 9 specs (~9-11 hr) but chain items 1-3 already done saves ~2 hours. Net: similar wall time, more landed.

## Annotated imperfections (after POC ships)

These move to `harness/IMPERFECTIONS.md` after POC commit:

- `card-specs-tier-2-extraction-pending` — Quantum, Teferi, Consign, Wrath not yet extracted. ~60-90 min when scheduled.
- `card-specs-mulligan-keep-not-parameterized` — keep() still per-APL hand-rolled; spec assumes keep() parameterization is a separate refactor (covered by `mulligan-logic-portfolio-gap`).
- `card-specs-no-bo3-sideboard-handling` — match-context predicates accept opponent= but no sideboard-game flag. Future spec.

## Commit message template (POC)

```
apl: card_specs framework + Phlage POC + Jeskai Blink composition

Adds apl/card_specs/ as parallel layer to engine/card_handlers_verified.
Each spec module owns one card's decision logic (cast/hardcast/escape/
attack_trigger), shared across APLs.

POC: apl/card_specs/phlage.py + apl/jeskai_blink.py rewritten as ~30L
orchestration calling phlage.hardcast / phlage.escape / phelia.cast etc.

Validation:
  Goldfish kill turn (jeskai_blink, n=2000 seed=42): T6.43 -> T<X>
  All card_spec unit tests pass

Out of scope: migrating boros_energy.py / jeskai_blink_match.py /
uw_blink_match.py to use card_specs (Phase B; bit-stable canonical gate
required, deferred to follow-up).

Findings doc: harness/knowledge/tech/jeskai-blink-card-specs-2026-04-28.md
Spec: harness/specs/2026-04-29-card-specs-framework.md
```

## Changelog

- 2026-04-29: Created (status PROPOSED). POC scope clarified (ADDITIVE — no canonical risk). Phase A/B/C structure defined. Tier 1/2/3 priority laid out.
