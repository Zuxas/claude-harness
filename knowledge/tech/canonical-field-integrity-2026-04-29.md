---
title: "Canonical Modern field integrity audit"
domain: "tech"
created: "2026-04-29"
updated: "2026-04-29"
status: "COMPLETE"
sources: ["mtg-sim/decks/*_modern.txt", "mtg-sim/format_config.py",
         "mtg-sim/apl/__init__.py", "harness/knowledge/tech/match-apl-mulligan-audit-2026-04-29.md"]
---

## Headline

Canonical Modern field has **3 separate data integrity issues** affecting **25.5% of total field share**:

1. **Duplicate decklists (19.1% phantom share):** Two pairs of `_modern.txt` files are SHA-256-identical to each other. Field is double-counting two decks under different names.
2. **Mislabeled decklist (6.4% wrong-deck-against-APL):** The "Grinding Breach" decklist file actually contains a Temur Breach / Teg storm-ritual deck. The Grinding Breach APL (expecting Underworld Breach + Grinding Station combo) has no compatible cards in the file.
3. **Missing match APLs (covered separately):** 4 of 15 canonical decks fall back to GoldfishAdapter; one (Jeskai Blink) was fixed via 1-line registry add today (commit `5452122`); 3 remain (Temur Breach, Grinding Breach, Orzhov Blink, plus the misnamed file issue overlaps here).

These findings emerged from following the Jeskai Blink registry-fallback investigation downstream.

## Issue 1: duplicate decklists

| File A | File B | SHA-256 prefix | Same content? |
|---|---|---|---|
| `decks/esper_blink_modern.txt` | `decks/orzhov_blink_modern.txt` | `77540f97...` | YES (bit-identical) |
| `decks/grinding_breach_modern.txt` | `decks/temur_breach_modern.txt` | `91163752...` | YES (bit-identical) |

Both pairs share the same `// header comment` ("Esper Blink - botje_" and "Teg - Arets77" respectively).

**Field share impact:**

| "Deck" | format_config.py share | Actual deck (per file) | Phantom? |
|---|---|---|---|
| Esper Blink | 2.8 | Esper Blink | NO (real) |
| Orzhov Blink | 6.1 | Esper Blink (mislabeled) | YES |
| Temur Breach | 3.8 | Teg (Temur Breach storm) | NO (real) |
| Grinding Breach | 6.4 | Teg (Temur Breach storm — mislabeled!) | YES |

**Net: 6.1 + 6.4 = 12.5 percentage points are phantom share.** When the canonical gauntlet samples opponents per format_config field weights, 12.5% of opponent draws ARE the same deck under another name (Esper Blink twice, Teg twice).

But because the APLs differ per name (Orzhov Blink uses GoldfishAdapter(EsperBlinkAPL); Esper Blink uses EsperBlinkMatchAPL; Grinding Breach uses GoldfishAdapter(GrindingBreachAPL — wrong cards in deck!); Temur Breach uses GoldfishAdapter(TemurBreachAPL — 26L SHIM)), the EFFECTIVE play differs slice-to-slice. The phantom share is contributing real but distorted gauntlet data.

## Issue 2: Grinding Breach APL plays wrong cards

`apl/grinding_breach.py` (93L hand-tuned APL) defines:
```python
COMBO_PIECES = {"Underworld Breach", "Grinding Station"}
ENABLERS = {"Emry, Lurker of the Loch", "Mox Opal", "Mox Amber", "Urza's Saga", ...}
```

But `decks/grinding_breach_modern.txt` actually contains:
```
4 Desperate Ritual         <- ritual storm, not breach combo
4 Pyretic Ritual           <- ritual storm
4 Past in Flames           <- storm staple
4 Glimpse the Impossible
4 Manamorphose
4 Ruby Medallion
4 Ral, Monsoon Mage
4 Wrenn's Resolve
4 Reckless Impulse
2 Wish
... (NO Underworld Breach. NO Grinding Station. NO Mox Opal. NO Emry.)
```

The APL searches for combo pieces it'll never find. Its `keep()` heuristic and main_phase logic are useless against this card pool. Effectively, the canonical 6.4% "Grinding Breach" slice plays as an APL grasping at non-existent combo cards, falling through to whatever default behavior the engine provides for unhandled combo APLs.

This is a worst-case integrity issue: the deck is being measured but the APL is fundamentally mismatched to the cards.

## Issue 3: cross-reference to existing IMPERFECTIONS

This audit's findings unify with:
- `canonical-field-missing-match-apl-entries` (filed 2026-04-29; partial fix shipped for Jeskai Blink)
- `card-specs-phlage-engine-no-sacrifice-quirk` (independent finding; same baseline-integrity theme)

## Recommended fixes

### Quick wins (low canonical risk)

1. **Remove mislabeled aliases from format_config.py modern field** — drop `"Orzhov Blink"` and `"Grinding Breach"` entries (they're phantom). Re-distribute the 12.5% phantom share to other decks proportionally OR accept a 12.5% drop in total field weight and renormalize. Cleaner data; baseline shift is the desired direction (less phantom counting).

2. **Rename or delete the duplicate deck files** — `decks/orzhov_blink_modern.txt` and `decks/grinding_breach_modern.txt` should either be deleted (if the registry alias is removed) OR replaced with actual decklists for those archetypes.

### Bigger fix (canonical-shifting; needs spec)

3. **Source actual decklists:**
   - Real Orzhov Blink (W/B color identity, Phelia + Solitude + Tidehollow Sculler / Liliana / etc.) from MTGGoldfish/MTGTop8.
   - Real Grinding Breach (U/R Underworld Breach + Grinding Station + Mox Opal + Emry + Mishra's Bauble) from any recent Modern Top 8 list.
   - Replace the duplicate files. Restores the canonical field's intended diversity.

4. **Author Temur Breach match APL** — file already exists for the deck, just registered as 26L SHIM. ~60-90 min to upgrade.

### Per-spec sequencing recommendation

For tomorrow's chain:
- **Spec #8 (100k re-validation)** — do this BEFORE applying fixes 1-3 to capture the current (broken) baseline as a measurement. After fixes, do another 100k as the new clean baseline.
- **Fix 1 (registry/format_config cleanup)** — bundle into a "canonical field integrity v1" spec ~30-60 min, pre-spec #8 second run.
- **Fix 3 (decklist sourcing)** — separate spec, bigger scope, needs human input on which lists to source from.

## Validation gates for proposed fixes

| Gate | Pre-fix | Post-fix expected |
|---|---|---|
| Boros Energy canonical FWR | 64.5% | 64.5% +/- 5pp (unknown direction) |
| Variant Boros canonical FWR | 78.8% | 78.8% +/- 5pp |
| Total format_config Modern share | 100.0% | 87.5% (after removing 2 phantoms) OR 100.0% (after sourcing real decklists for both) |
| Field cardinality | 15 | 13 (removal) or 15 (sourcing) |

## Action capture

3 IMPERFECTIONS to OPEN/UPDATE:

- `duplicate-deck-files` — NEW. Files with bit-identical SHA-256 in canonical field. Concrete fix: remove or replace.
- `canonical-field-missing-match-apl-entries` — UPDATE. Add the 19.1% phantom finding context.
- `apl-deck-mismatch-grinding-breach` — NEW. APL expects cards not in the deck file.

## Changelog

- 2026-04-29: Created during 2026-04-28/04-29 night session investigation. Triggered by `canonical-field-missing-match-apl-entries` resolution; followed Jeskai Blink fix downstream and discovered deck-file integrity issues.
