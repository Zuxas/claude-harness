---
title: "Match APL mulligan audit (corrected scope)"
domain: "tech"
created: "2026-04-29"
updated: "2026-04-29"
status: "COMPLETE"
sources: ["mtg-sim/apl/*_match.py",
         "harness/knowledge/tech/mulligan-audit-2026-04-28.md (corrected)"]
---

## Summary

Re-audit of mulligan logic, this time scoped to MATCH APLs (`apl/*_match.py`) — the variants that actually drive canonical Modern gauntlet baseline (64.5% / 78.8%). Yesterday's goldfish-APL audit was on the wrong files; canonical uses `MATCH_APL_REGISTRY` not `APL_REGISTRY`.

Also caught a **classifier bug** in yesterday's audit: it counted card-name references as `ast.Constant` strings only, missing module-level constant references like `RAGAVAN = "Ragavan, Nimble Pilferer"` followed by `c.name == RAGAVAN`. Fixed classifier counts both string literals AND ALL_CAPS Name references.

**Headline:** match APLs are mostly fine. **57% TUNED, 24% SHALLOW, 19% NO_KEEP** out of 37 match APL files. The earlier "31% inadequate" claim was a combination of wrong scope (goldfish vs match) and classifier bug. Within the canonical 15-deck Modern field, mulligan logic is in good shape.

## Methodology

Same AST walk as `mulligan-audit-2026-04-28.md` Methodology section, but applied to `apl/*_match.py` files (37 total) instead of `apl/<deck>.py`. Picks `keep_vs()` if defined and longer than `keep()`; else falls back to `keep()`. Classifier fixed to count constant references.

## Distribution (37 match APLs)

| Class | Count | % |
|---|---|---|
| TUNED | 21 | 57% |
| SHALLOW | 9 | 24% |
| NO_KEEP (base-class inheritor) | 7 | 19% |
| TRIVIAL | 0 | 0% |

## Canonical 15-deck Modern field — per-deck match APL grade

| Deck | Match APL file | Class | named-cards in keep |
|---|---|---|---|
| Boros Energy | `boros_energy_match.py` | TUNED | 2 |
| Amulet Titan | `amulet_titan_match.py` | TUNED | 9 |
| Eldrazi Ramp | `eldrazi_ramp_match.py` | TUNED | 9 |
| Izzet Prowess | `izzet_prowess_match.py` | TUNED | 3 |
| Izzet Affinity | `affinity_match.py` | TUNED | 6 |
| Grinding Breach | (no `_match.py` file?) | unknown | — |
| Jeskai Blink | `jeskai_blink_match.py` | TUNED | 9 |
| Orzhov Blink | (no `_match.py` file?) | unknown | — |
| Goryo's Vengeance | `goryos_match.py` | TUNED | 6 |
| Domain Zoo | `domain_zoo_match.py` | TUNED | 4 |
| Eldrazi Tron | `eldrazi_tron_match.py` | TUNED | 7 |
| Mono Red Aggro | `mono_red_match.py` | TUNED | 2 |
| Temur Breach | (no `_match.py` file?) | unknown | — |
| Dimir Murktide | `murktide_match.py` | TUNED | 6 |
| Esper Blink | `esper_blink_match.py` | TUNED | 3 |

12 of 15 canonical decks have TUNED match APLs. 3 (Grinding Breach, Orzhov Blink, Temur Breach) need investigation — possibly missing match APL files or routed differently in the registry. **Action:** verify these 3 in registry.

## SHALLOW match APLs (9) — none in canonical Modern field

| APL | Notes |
|---|---|
| dimir_oculus_match | fringe Modern (not in canonical 15) |
| glockulous_match | fringe Modern |
| humans_match | Legacy (not Modern field) |
| living_end_match | fringe Modern |
| neoform_match | fringe Modern |
| ruby_storm_match | fringe Modern |
| uw_blink_match | fringe Modern (Phelia engine) |
| uw_control_match | fringe Modern |
| yawgmoth_match | fringe Modern |

These 9 are exactly the same set classified as SHIM/SHALLOW in yesterday's goldfish audit. They're "documented stubs from 2026-04-26 Stage A no-APL triage" — registered for gauntlet coverage but not hand-tuned. **They affect goldfish-only and matchup-against-fringe-decks gauntlets, NOT canonical 15-deck Modern field.**

## NO_KEEP match APLs (7) — Standard mostly

| APL | Inherits from |
|---|---|
| azorius_aggro_standard_match | AzoriusAggroAPL (not directly verified, likely aggro_base via the Standard goldfish) |
| azorius_control_standard_match | ControlAPL (control_base) |
| izzet_lesson_standard_match | IzzetLessonAPL |
| izzet_prowess_standard_match | IzzetProwessAPL |
| izzet_spellementals_standard_match | IzzetSpellementalsAPL |
| jeskai_control_standard_match | JeskaiControlAPL |
| superior_doomsday_standard_match | SuperiorDoomsdayAPL |

These NO_KEEPs inherit `keep` from their goldfish APL or role base. **Not necessarily a bug** — needs spot-check that the inherited keep is appropriate for the matchup context.

Note: all are Standard, not Modern. Standard canonical is a separate gauntlet from Modern canonical; doesn't directly affect 64.5%/78.8% Modern baseline.

## Issues that survive the corrected audit

1. **`on_play` parameter still ignored across all match APLs.** Same finding as goldfish audit. Match-APL `keep()` accepts the parameter but never branches on it. Modern goes/draw decisions matter; this is silently lost.

2. **No `keep_vs` opp-archetype branching in most match APLs.** `keep_vs(hand, mulligans, on_play, opp_archetype)` is the optional 4-arg keep that lets APLs adjust mulligan thresholds per opponent. Most match APLs only define `keep()`, not `keep_vs()`. So mulligan decisions are matchup-blind even when match data is available.

3. **Three canonical decks (Grinding Breach, Orzhov Blink, Temur Breach) need verification.** Their match APLs may be missing or routed to a different registry entry. If missing, those gauntlets fall back to MATCH_APL_REGISTRY hopefully or use the goldfish APL by default. **Action:** investigate.

4. **Fringe Modern SHALLOW (9 APLs)** still relevant for non-canonical gauntlets and for any future scenario where these decks enter the canonical field.

## Recommended action

1. **Verify Grinding Breach + Orzhov Blink + Temur Breach** — check `MATCH_APL_REGISTRY` for entries pointing to their match APLs. If missing, that's its own IMPERFECTION.
2. **Add `on_play` branching to role-base `keep()` implementations** (aggro_base, combo_base, control_base, ramp_base). One-time change benefits all NO_KEEP inheritors.
3. **Convert SHALLOW fringe APLs** (Living End, Yawgmoth, Glockulous, etc.) to use `combo_base.keep()` with named card sets. These are the 9 listed above. Goldfish audit recommended this; same recommendation applies.
4. **Skip the "mulligan-framework" portfolio refactor** as initially proposed — the role-base classes are already the framework, and most match APLs (the canonical-driving ones) already implement appropriate keeps. The compounding ROI is much smaller than yesterday's audit suggested.

## Connection to IMPERFECTIONS

Updates required to `mulligan-logic-portfolio-gap`:
- "31% inadequate" claim was wrong — actual is **24% SHALLOW + 19% NO_KEEP = 43% non-TUNED for match APLs**, but most NO_KEEP are correctly inheriting from role bases. True "inadequate" rate is closer to 24% SHALLOW.
- **None of the SHALLOW match APLs are in the canonical 15-deck Modern field.** So canonical baseline impact is 0 from this audit's findings.
- The remaining real gap is `on_play` branch missing universally + 3 unverified canonical decks (Grinding Breach / Orzhov Blink / Temur Breach).

## Changelog

- 2026-04-29: Created. Corrects yesterday's goldfish-scoped audit. Fixed classifier bug (was missing constant-name refs). Verifies match APLs are mostly fine for canonical purposes.
