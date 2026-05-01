---
title: "Boros Energy vs Jeskai Blink APL maturity comparison"
domain: "tech"
created: "2026-04-29"
updated: "2026-04-29"
status: "COMPLETE"
sources: ["mtg-sim/apl/boros_energy.py (1115L)", "mtg-sim/apl/jeskai_blink_match.py (~600L post tonight's commits)"]
---

## Headline

Boros Energy APL (1115L canonical anchor at 22.1% field share) is structurally far more mature than Jeskai Blink match APL was at session start. Boros explicitly compensates at the APL level for engine-side oracle gaps that Jeskai Blink left unmodeled. This explains why JB had ~12 bugs surface-able tonight while Boros's locked baseline has been stable.

The implication: **APL maturity correlates with oracle fidelity. The remaining canonical APLs likely have similar bug densities to JB pre-tonight, weighted by their line counts.**

## Concrete examples of Boros APL-level oracle compensation

### Phlage hardcast sacrifice (oracle-correct in Boros, was wrong in JB engine path)

`apl/boros_energy.py:_handle_phlage` lines 700-703:
```python
# Sacrifice after ETB -- hardcast path didn't escape.
if card in gs.zones.battlefield:
    gs.zones.battlefield.remove(card)
    gs.zones.graveyard.append(card)
```

The code explicitly comments: "Handler explicitly comments 'sacrifice-unless-escaped clause [...] not modeled here'" — so Boros knows about the engine gap and patches it APL-side.

JB match APL similarly has manual sacrifice (line ~294 of jeskai_blink_match.py).

`apl/card_specs/phlage.py:hardcast` (Tier 1 POC tonight) does NOT sacrifice — relies on engine quirk. **This is a migration trap for Phase B**: if Boros migrates to use card_specs without preserving its sacrifice override, Phlage stays as 6/6 on Boros hardcast, shifting canonical baseline.

### Arena of Glory exert + haste (Boros has it, JB doesn't, engine doesn't)

`apl/boros_energy.py:_handle_arena_exert_haste` (lines 864-900) implements the full mechanic:
- Find untapped Arena
- Find non-haste creature in hand affordable with +2 mana
- Tap Arena, set `_exerted` flag (won't untap next turn — modeled)
- Add 2 R mana
- Cast creature, set `summoning_sickness = False` (HASTE from Arena)

JB match APL has NO equivalent — Phlage / Ragavan / Casey / Quantum cast on T4+ via Arena enter without haste. So JB's T4 Arena→Phlage→swing combo (the user mentioned earlier) physically can't fire.

`engine/card_handlers_verified.py:_arena_of_glory_etb` just logs "Arena of Glory: mass haste" — pure cosmetic, no actual mechanic.

### Other Boros APL-level oracle compensations

- **Guide of Souls energy + ETB triggers**: `_fire_guide_etb_trigger` dedicated handler. Energy counters on creature ETB, attack-time pump (2 +1/+1 + flying counter for {E}{E}{E}).
- **Ocelot lifegain → cat token (+ Ascend)**: `_simulate_end_step` + `_handle_ocelot_end_step`. End-step trigger respects lifegain flag, creates token, doubles tokens with city's blessing.
- **Ajani transform on cat death**: `_handle_ajani_etb` + transform tracking on cat death events.
- **Phlage escape from GY**: full implementation in `_handle_phlage`.
- **Goblin Bombardment + Phlage**: `_handle_bombardment_finish` chains the synergy.
- **The Legend of Roku saga**: registered in `engine/sagas.py:SAGA_EFFECTS` with three chapter handlers (one of only 2 sagas wired engine-wide).

## Why JB match APL was buggier (and what I fixed)

Tonight's 12 commits closed bugs in JB match APL that Boros would have caught:
- Phelia +1/+1 counter not applied (BE doesn't have Phelia, but Boros's mature APL would have caught the pattern)
- Solitude evoke pitch not white-only (BE doesn't have Solitude, same pattern)
- Ephemerate {W} not paid in stack play
- Casey discard accumulation (BE doesn't have Casey)
- March 2-pitch cap (added wrongly tonight, reverted in 8805e31)
- Phelia exile permanent vs end-step return
- Fable + Prismatic Ending never cast (Fable wasn't in deck file; Prismatic was unmodeled)
- Plus my Galvanic and Prismatic misreads tonight (Galvanic reverted by user; Prismatic still wrong, fixed by Phase A agent)

These 12 bugs accumulated because JB match APL has been less actively maintained than Boros.

## Implication for the canonical baseline

Boros's 64.5% / 78.8% canonical numbers reflect a Boros that already compensates for many engine-level gaps. JB's prior-tonight fallback to 24L SHIM goldfish was a worst-case opponent (lots of bugs + simple play). After tonight's fixes + the routing fix in 5452122, JB-as-opponent in canonical now plays at the level Boros has played for a while.

**Spec #8 100k re-validation tomorrow** measures this asymmetric upgrade: 6.4% of the canonical field (JB) leveled up significantly; 22.1% (Boros) unchanged. Other canonical decks (Amulet Titan 8.5%, Eldrazi Tron 4.3%, Goryo's 5.6%, etc.) likely sit somewhere between JB pre-tonight and Boros — possibly with bug counts proportional to their APL line counts.

## Maturity ranking by APL line count

| Deck | Match APL file | Lines | Field % | Bugs caught tonight |
|---|---|---|---|---|
| Amulet Titan | amulet_titan_match.py | 2723 | 8.5 | 0 (untouched) |
| Boros Energy | boros_energy.py | 1115 | 22.1 | 0 (untouched, locked) |
| Jeskai Blink | jeskai_blink_match.py | ~600 | 6.4 | 12 |
| Eldrazi Tron | eldrazi_tron_match.py | (check) | 4.3 | 0 |
| Goryo's Vengeance | goryos_match.py | (check) | 5.6 | 0 |
| Domain Zoo | domain_zoo_match.py | (check) | 5.0 | 0 |
| (etc.) | | | | |

The 12-bug delta in JB happened in 1 night of focused audit. **Probable bugs in untouched canonical APLs:**
- Amulet Titan: low (most-maintained APL in the project)
- Eldrazi Tron / Goryo's / Eldrazi Ramp: medium-likely (less tuning attention)
- Standard match APLs (Izzet Prowess, Mono Red, Dimir Murktide, etc.): possibly similar to JB (12-bug range each)

## Recommendation for next session

1. **Audit Eldrazi Tron, Goryo's Vengeance, Domain Zoo, Eldrazi Ramp match APLs** with the same oracle-vs-implementation pattern. Each is probably 3-8 hours of careful work.
2. **Pre-flight oracle verification**: codify as methodology lesson (this finding + the spec doc).
3. **Phase B migration of card_specs** must preserve APL-level oracle overrides: Boros's Phlage sacrifice, Boros's Arena exert+haste, etc. Cannot blindly replace inline logic with card_specs without copying the override.

## Changelog

- 2026-04-29: Created during background-agent-running window. Read-only audit of Boros Energy oracle vs implementation, comparing to JB match APL bug pattern.
