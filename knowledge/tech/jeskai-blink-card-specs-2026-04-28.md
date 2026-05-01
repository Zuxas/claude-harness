---
title: "Jeskai Blink card-by-card decision specs"
domain: "tech"
created: "2026-04-28"
updated: "2026-04-28"
status: "DRAFT"
spec: "harness/specs/2026-04-29-card-specs-framework.md"
sources: ["mtg-sim/decks/jeskai_blink_modern.txt",
         "mtg-sim/apl/jeskai_blink_match.py (595L)",
         "mtg-sim/apl/boros_energy.py",
         "mtg-sim/apl/uw_blink.py + uw_blink_match.py"]
---

## Purpose

Per-card decision spec for Jeskai Blink (Modern). Each card describes:
- **Oracle (truncated):** what the card does mechanically
- **Role:** aggro/value/removal/finisher/disruption/utility
- **Goldfish viability:** HIGH (works without opponent), MED (works partially), DEAD (needs opponent state)
- **Decision priority:** when to cast / hold / sequence
- **Cross-refs:** existing implementations to extract from
- **Reuse footprint:** which other decks share this card

The user's insight (2026-04-28): "spec each card, get the main stat" — bottom-up build of `main_phase` from card primitives instead of top-down "play biggest creature." Cards shared across decks (Phlage, Galvanic, Phelia, Solitude, Ephemerate, Quantum, Ragavan) are reimplemented N times across `boros_energy.py`, `jeskai_blink_match.py`, `uw_blink_match.py`. A `apl/card_specs/` extraction would dedup ~70% of Jeskai Blink's nonland card logic.

## Decklist (mainboard 60 nonland card types = 14)

```
4 Ragavan, Nimble Pilferer
4 Phelia, Exuberant Shepherd
4 Phlage, Titan of Fire's Fury
4 Quantum Riddler
4 Solitude
2 Casey Jones, Vigilante
4 Consign to Memory
4 Galvanic Discharge
2 Ephemerate
2 Teferi, Time Raveler
2 Fable of the Mirror-Breaker
2 Prismatic Ending
1 March of Otherworldly Light
1 Wrath of the Skies
```

Lands omitted (no decision logic; just play one per turn).

## Per-card specs

### 1. Ragavan, Nimble Pilferer (4) — `{R}` 2/1 menace dash {1}{R}

**Oracle:** Whenever Ragavan deals combat damage to a player, create a Treasure token, then exile top of that player's library. Until end of turn, you may cast it. Dash {1}{R}.

**Role:** Aggro / mana-acceleration via treasures / card-advantage via exile-cast.
**Goldfish viability:** HIGH — 2 power haste-via-Arena-of-Glory T1 attacker, treasure tokens are real ramp even in goldfish.
**Decision priority:**
- T1 if untapped {R} source: cast or dash (dash if opponent will block else hardcast).
- Always attack when possible (treasure on hit; no downside in goldfish).
- Hold if no untapped {R} on T1 (rare given 4 Arid Mesa + 4 Scalding Tarn + 4 Flooded Strand).
**Cross-refs:** `boros_energy.py:RAGAVAN` constant + cast logic; `jeskai_blink_match.py:215-223`.
**Reuse:** Boros Energy (4), Jeskai Blink (4). Spec lives in `apl/card_specs/ragavan.py`.

### 2. Phelia, Exuberant Shepherd (4) — `{1}{W}` 1/1 flash

**Oracle:** Flash. Whenever Phelia attacks, exile up to one other target nonland permanent. At beginning of next end step, return it to the battlefield under its owner's control. Put a +1/+1 counter on Phelia if a permanent under your control was exiled this way.

**Role:** Value engine (blink own ETB creatures for re-trigger) + tempo (exile opp threats).
**Goldfish viability:** MED — own-ETB blink works (re-trigger Solitude/Phlage/Quantum/Casey ETB); opponent-exile path is dead in goldfish.
**Decision priority:**
- T2 cast if any ETB creature on board OR upcoming.
- On attack: blink best ETB creature (Phlage > Quantum > Casey priority for goldfish since Solitude has no target).
- Hold if no ETB targets in hand or board (rare).
**Cross-refs:** `jeskai_blink_match.py:466-484` (attack-trigger logic); `uw_blink.py:9` (constant) + `uw_blink_match.py` (full impl).
**Reuse:** Jeskai Blink (4), UW Blink (4). Spec lives in `apl/card_specs/phelia.py`.

### 3. Phlage, Titan of Fire's Fury (4) — `{1}{R}{W}` hardcast / `{R}{R}{W}{W}` escape

**Oracle:** Hardcast: When Phlage enters, it deals 3 damage to any target and you gain 3 life, then sacrifice it. Escape — `{R}{R}{W}{W}`, exile 5 cards from your graveyard. As a 6/6 permanent attacking creature, attack trigger deals 3 damage + 3 life.

**Role:** Removal + reach (hardcast) → Finisher (escape).
**Goldfish viability:** HIGH for hardcast (3 face dmg + 3 life). HIGH for escape (6/6 + ETB 3 dmg + 3 life). The mid-game pivot card.
**Decision priority:**
- T3+: hardcast IF (a) we have 3 mana AND (b) escape isn't online yet AND (c) hardcasting won't cost us tempo (i.e., we don't have a better creature to cast).
- T4+: hardcast IF we have spare 3 mana AND no other creature to cast — sets up GY for escape.
- Escape IF: 5+ non-Phlage GY cards AND 4 mana available AND Phlage in GY.
- Escape priority over hardcast once threshold met.
**Tricky in goldfish:** GY-fueling fast enough (no fetch sacs auto-modeled, no instants cast). Empirical: prior attempt to manually fuel via casting Galvanic/Consign/Prismatic for GY made kill clock SLOWER (T6.24 → T6.42). So hardcast-then-wait-for-natural-fuel.
**Cross-refs:** `boros_energy.py:PHLAGE`; `jeskai_blink_match.py:255-295` (full hardcast + escape logic).
**Reuse:** Boros Energy (4), Jeskai Blink (4). Spec lives in `apl/card_specs/phlage.py`. **POC extraction target.**

### 4. Quantum Riddler (4) — `{3}{U}{U}` 4/6 flying

**Oracle:** When Quantum Riddler enters, you may draw a card.

**Role:** Finisher / value (flying body + draw).
**Goldfish viability:** HIGH — 4/6 flying is a real clock (5 turns alone for kill); draw 1 ETB always live.
**Decision priority:**
- T5+: cast when 5 mana available with {U}{U} fixing.
- ALWAYS draw on ETB.
- Re-draw on Phelia attack-blink or Ephemerate.
**Cross-refs:** `jeskai_blink_match.py:227-231`; `uw_blink_match.py` similar.
**Reuse:** Jeskai Blink (4), UW Blink (3). Spec lives in `apl/card_specs/quantum_riddler.py`.

### 5. Solitude (4) — `{3}{W}{W}` 3/2 flash lifelink, evoke `{W}` + pitch white

**Oracle:** Flash. Lifelink. When Solitude enters, exile target creature an opponent controls; that player gains life equal to its power. Evoke — `{W}`, exile a white card from hand.

**Role:** Removal (instant-speed) + lifegain.
**Goldfish viability:** DEAD — both hardcast and evoke require opponent creature target. Solitude is a "card in hand" only in goldfish. Pitch fodder for March of Otherworldly Light at best.
**Decision priority (goldfish):** SKIP. Only useful as Ephemerate target if blinked (but blinking Solitude in goldfish does nothing — no ETB target).
**Decision priority (matchup):** Evoke when opp threat ≥ 2 power. Stack with Ephemerate for 2-for-0 (Solitude evoke → Ephemerate Solitude before sac → second exile + Solitude stays on board).
**Cross-refs:** `jeskai_blink_match.py:147-191` (full evoke + Ephemerate stack); `uw_blink_match.py` similar.
**Reuse:** Jeskai Blink (4), UW Blink (4), Esper Blink (4). Spec lives in `apl/card_specs/solitude.py`.

### 6. Casey Jones, Vigilante (2) — `{1}{R}{R}` (CMC 3)

**Oracle:** ETB: draw 3 cards. At your next upkeep, discard 3 random cards. (Effectively net 0 cards but cycles through deck.)

**Role:** Card-velocity / dig.
**Goldfish viability:** HIGH — draw 3 immediately is real. Random discard hurts but acceptable since it digs us to threats faster.
**Decision priority:**
- T3+: cast if hand has fewer than 4 actionable cards (need to dig).
- HOLD if hand is loaded — discarding 3 random would lose value.
- Blink with Phelia/Ephemerate to draw 3 again (huge swing).
**Cross-refs:** `jeskai_blink_match.py:124-138, 234-238, 386-388`.
**Reuse:** Jeskai Blink only (2). Spec lives in `apl/card_specs/casey_jones.py`. Lower-priority extraction.

### 7. Consign to Memory (4) — `{U}` instant, replicate `{1}`

**Oracle:** Counter target triggered ability or colorless spell. Replicate `{1}` (when cast, copy for each replicate cost paid).

**Role:** Disruption (counter critical triggers — Archon ETB, Pact upkeep, Storm copy).
**Goldfish viability:** DEAD — no triggers to counter without opponent.
**Decision priority (goldfish):** SKIP.
**Decision priority (matchup):** Counter Archon ETB / Pact upkeep / Summoner's Pact loss / Storm copy / Tron-piece ETB.
**Cross-refs:** `jeskai_blink_match.py:526-546` (respond_to_spell trigger handler).
**Reuse:** Jeskai Blink (4), UW Blink (1), Esper Blink (3). Spec lives in `apl/card_specs/consign_to_memory.py`. Sideboard pattern across blink decks.

### 8. Galvanic Discharge (4) — `{R}` instant

**Oracle:** Galvanic Discharge deals 1 damage to target creature or planeswalker, and you get {E}{E}{E}. You may pay any amount of {E}; for each {E} paid, Discharge deals additional 1 damage.

**Role:** Removal (energy-scaling).
**Goldfish viability:** DEAD — no target. Energy generation is useless without spells/Phlage to spend on.
**Decision priority (goldfish):** SKIP.
**Decision priority (matchup):** Cast for energy generation even with no target if Phlage on board needs energy fuel? No — Phlage doesn't use energy. Discharge is pure removal.
**Cross-refs:** `boros_energy.py:GALVANIC`; `jeskai_blink_match.py:194-213`.
**Reuse:** Boros Energy (4), Jeskai Blink (4). Spec lives in `apl/card_specs/galvanic_discharge.py`.

### 9. Ephemerate (2) — `{W}` instant, rebound

**Oracle:** Exile target creature you control, then return it to the battlefield under its owner's control. Rebound (if cast from hand, exile it; you may cast it from exile during your next upkeep without paying mana).

**Role:** Value engine (re-trigger ETB) + Solitude evoke save.
**Goldfish viability:** HIGH for blink-Phlage (3 dmg + 3 life on each blink) / Quantum (draw 1) / Casey (draw 3). DEAD for blink-Solitude.
**Decision priority:**
- Cast WHEN there's an ETB creature worth re-triggering on board.
- Priority: Phlage (3 dmg + 3 life) > Quantum (draw) > Casey (draw 3, only if hand isn't full).
- Skip in goldfish if only Solitude on board.
- Track rebound: at next upkeep, free re-cast → blink again.
**Cross-refs:** `jeskai_blink_match.py:298-306, 394-425` (blink_best_etb logic + rebound flag).
**Reuse:** Jeskai Blink (2), UW Blink (4), Esper Blink (3). Spec lives in `apl/card_specs/ephemerate.py`.

### 10. Teferi, Time Raveler (2) — `{1}{W}{U}` planeswalker, starts at 4 loyalty

**Oracle:** Each opponent can cast spells only any time they could cast a sorcery. +1: Until your next turn, you may cast sorcery spells as though they had flash. -3: Return up to one target artifact, creature, or enchantment to its owner's hand. Draw a card.

**Role:** Disruption (lock to sorcery speed) + bounce + draw.
**Goldfish viability:** MED — +1 ability is dead (no opp spells to lock); -3 bounce dead (no opp permanent); draw card from -3 is live.
**Decision priority (goldfish):** Cast if 3 mana available + nothing better. Use -3 for the draw (bounce a land we don't need? not really bounce-able to ourselves cleanly). +1 useless.
**Decision priority (matchup):** Cast pre-combat to lock counterspells. -3 bounce best opp threat + draw (always +card-advantage).
**Cross-refs:** `jeskai_blink_match.py:241-253`.
**Reuse:** Jeskai Blink (2), UW Blink (2), Esper Blink (2). Spec lives in `apl/card_specs/teferi_time_raveler.py`.

### 11. Fable of the Mirror-Breaker (2) — `{2}{R}` saga, 3 chapters

**Oracle:**
- Chapter 1: Discard a card, draw a card. If you discarded nonland, treasure.
- Chapter 2: Make a 2/2 red Goblin Shaman creature token with treasure-on-attack.
- Chapter 3: Transform — exile saga, return as Reflection of Kiki-Jiki (3/3 red creature, tap to copy nonlegendary creature).

**Role:** Card-velocity (Ch1) + body (Ch2) + ramp (treasures) + finisher (Ch3 transform → copy threats).
**Goldfish viability:** HIGH — Ch1 loots, Ch2 token attacks for 2/turn, Ch3 transform copies Phlage (escape clone) or Quantum (4/6 flying clone).
**Decision priority:** Cast T3+ on curve. Always.
**Cross-refs:** Not in current jeskai_blink_match.py. Would need new spec.
**Reuse:** Jeskai Blink (2). Likely Boros Energy variants. Spec lives in `apl/card_specs/fable_of_mirror_breaker.py`.

### 12. Prismatic Ending (2) — `{X}{W}` sorcery

**Oracle:** Exile target nonland permanent with mana value `X` or less.

**Role:** Removal (scaling cost).
**Goldfish viability:** DEAD — no target.
**Decision priority (goldfish):** SKIP.
**Decision priority (matchup):** Always available as cheap removal at X=1 (1-mana creature, 1-mana planeswalker like Ragavan/Ajani).
**Cross-refs:** `jeskai_blink_match.py:48` (constant); referenced but no full impl in match APL.
**Reuse:** Jeskai Blink (2), UW Blink (2). Spec lives in `apl/card_specs/prismatic_ending.py`.

### 13. March of Otherworldly Light (1) — `{X}{W}` instant

**Oracle:** Exile target creature, planeswalker, or enchantment with MV `X+1`. You may pitch white cards from hand to reduce X by 2 each.

**Role:** Removal (any permanent type, scaling).
**Goldfish viability:** DEAD — no target.
**Decision priority (goldfish):** SKIP.
**Decision priority (matchup):** Pitch Solitude/Ephemerate/Phlage from hand (any card we don't intend to cast soon) to reduce X. Exile the biggest opp threat.
**Cross-refs:** `jeskai_blink_match.py:333-358`.
**Reuse:** Jeskai Blink (1), UW Blink (1). Spec lives in `apl/card_specs/march_of_otherworldly_light.py`.

### 14. Wrath of the Skies (1) — `{X}{W}{W}` sorcery, energy-based wipe

**Oracle:** As you cast, get X energy. You may pay any amount of energy you have; destroy each artifact, creature, and enchantment with mana value less than or equal to that amount. (Effectively: pay X colored + spend X energy = wipe MV ≤ X.)

**Role:** Sweeper (board wipe).
**Goldfish viability:** DEAD — no targets.
**Decision priority (goldfish):** SKIP. Pitch fodder for March only.
**Decision priority (matchup):** Cast when behind on board (their creatures ≥ ours + 2) or against single huge threat we can't answer.
**Cross-refs:** `jeskai_blink_match.py:309-331, 564-584`.
**Reuse:** Jeskai Blink (1), Boros Energy sideboard (3), UW Blink sideboard. Spec lives in `apl/card_specs/wrath_of_the_skies.py`.

## Goldfish-viable subset (the actual playable cards in goldfish)

| Card | Goldfish viability | Notes |
|---|---|---|
| Ragavan | HIGH | T1 attacker |
| Phelia | MED | Re-trigger ETB only |
| Phlage hardcast | HIGH | 3 face dmg + 3 life |
| Phlage escape | HIGH | 6/6 finisher (when GY ready) |
| Quantum Riddler | HIGH | 4/6 flying + draw |
| Casey Jones | HIGH | Draw 3 cycle |
| Ephemerate | HIGH | Re-trigger Phlage/Quantum/Casey |
| Teferi (-3 draw only) | MED | Burn 3 mana for 1 card |
| Fable | HIGH | Loot + token + transform finisher |
| Solitude | DEAD | Skip |
| Consign | DEAD | Skip |
| Galvanic Discharge | DEAD | Skip |
| Prismatic Ending | DEAD | Skip |
| March of Otherworldly Light | DEAD | Skip |
| Wrath | DEAD | Skip |

**Goldfish-active cards: 9 of 14 types (53%).** Of 60 mainboard cards, ~38 nonland cards are goldfish-active (4+4+4+4+2+2+2+2+1=25 non-dead nonland * actual counts). The remaining 22 (16 nonland + 22 lands) are dead in goldfish — Solitude/Consign/Galvanic/Prismatic/March = 4+4+4+2+1 = 15 dead nonland cards. So ~25/38 = 66% of nonland cards are goldfish-live. Fits the bound: even a perfectly-tuned goldfish APL has ~T6 ceiling because a third of the deck is interaction-only.

## Cross-deck reuse footprint

| Card | Decks using it | Action when extracted |
|---|---|---|
| Phlage | Boros Energy, Jeskai Blink, multiple Modern decks | High-value extraction |
| Galvanic Discharge | Boros Energy, Jeskai Blink | High-value extraction |
| Ragavan | Boros Energy, Jeskai Blink | High-value extraction |
| Phelia | Jeskai Blink, UW Blink, Esper Blink | High-value extraction |
| Solitude | Jeskai Blink, UW Blink, Esper Blink | High-value extraction |
| Ephemerate | Jeskai Blink, UW Blink, Esper Blink | High-value extraction |
| Quantum Riddler | Jeskai Blink, UW Blink | Med-value extraction |
| Teferi TR | Jeskai Blink, UW Blink, Esper Blink | Med-value extraction |
| Consign | Jeskai Blink, UW Blink, Esper Blink | Med-value extraction (sideboard pattern) |
| Wrath of the Skies | Jeskai Blink, multiple sideboards | Med-value extraction |
| Casey Jones | Jeskai Blink only | Low-value (deck-specific) |
| Fable | Jeskai Blink, possibly Boros variants | Med-value |
| Prismatic Ending | Jeskai Blink, UW Blink | Med-value (sideboard pattern) |
| March | Jeskai Blink, UW Blink | Med-value |

**Tier 1 extraction (high reuse, durable):** Phlage, Galvanic, Ragavan, Phelia, Solitude, Ephemerate.
**Tier 2 extraction (moderate reuse):** Quantum, Teferi, Consign, Wrath.
**Tier 3 extraction (deck-specific):** Casey, Fable, Prismatic, March.

## Architecture: `apl/card_specs/` framework

Each spec module exports:

```python
# apl/card_specs/<card>.py
NAME = "Phlage, Titan of Fire's Fury"

def hardcast(gs, opponent=None) -> bool:
    """Try to hardcast Phlage from hand. Returns True if cast."""
    ...

def escape(gs, opponent=None) -> bool:
    """Try Phlage escape from GY. Returns True if escaped."""
    ...

def attack_trigger(gs, opponent=None) -> None:
    """3 dmg + 3 life on combat damage."""
    ...
```

APL composition becomes:
```python
from apl.card_specs import phlage, ragavan, phelia, ephemerate, quantum_riddler, casey_jones, fable

class JeskaiBlinkAPL(BaseAPL):
    def main_phase(self, gs):
        self._play_land(gs)
        gs.tap_lands()
        ragavan.cast(gs)
        phelia.cast(gs)
        if not phlage.escape(gs):
            phlage.hardcast(gs)
        casey_jones.cast(gs)
        quantum_riddler.cast(gs)
        fable.cast(gs)
        ephemerate.cast(gs)  # blinks best ETB on board
```

~30 lines of orchestration vs 595L bespoke. Better signal: APL author thinks in plays, not in mana payment / sacrifice mechanics.

## What's deferred to follow-up specs

- Migration of `boros_energy.py`, `jeskai_blink_match.py`, `uw_blink_match.py` to use `card_specs` (canonical-baseline-affecting; needs bit-stable validation gate)
- Match-context predicates (need_solitude, need_galvanic — for matchup decisions)
- Mulligan-keep parameterization via card_specs (separate from main_phase composition)
- Bo3 sideboarded compositions

## Next action

Phase 3 (build framework with Phlage as POC) → Phase 4 (rewrite jeskai_blink.py goldfish from specs) → Phase 5 (measure pre/post). Tonight. See `harness/specs/2026-04-29-card-specs-framework.md` for the durable spec covering full migration scope.
