---
title: "Mulligan logic audit across mtg-sim primary APLs"
domain: "tech"
created: "2026-04-28"
updated: "2026-04-28"
status: "COMPLETE"
sources: ["mtg-sim/apl/", "mtg-sim/CLAUDE.md user note 2026-04-28"]
---

## Summary

User flagged that "boros energy is the only APL that feels close to right" and floated mulligan-logic improvement as a portfolio-wide compounding fix. Audit confirms: **52 primary APLs, only 26 (50%) are hand-tuned at the keep() level. 16 (31%) are SHIM or SHALLOW — the canonical Modern field includes 2 SHIMs and 1 SHALLOW.**

Crucially: **the framework already exists**. `aggro_base.py / combo_base.py / control_base.py / ramp_base.py` provide role-parameterized `keep()` using named card sets (CREATURES, BURN_SPELLS, SETUP_PIECES, ENABLERS, CANTRIPS, THREATS, RAMP_SPELLS, PAYOFFS) and tunable thresholds (MULL_MIN_LANDS, MULL_MAX_LANDS, MULL_MIN_PIECES, MULL_MIN_DISRUPT_OR_THREAT). The fix isn't building a framework — it's migrating SHIM/SHALLOW APLs to use the framework that's already on disk.

## Methodology

AST-walked every `apl/<deck>.py` (excluding base classes, mixins, frameworks, and `_match.py` variants). For each, located the `keep()` method (own or inherited) and counted: lines, `if` branches, named string constants (proxy for must-have cards), `on_play` references, `mulligans` references, base classes.

Classification:
- **SHIM**: inherits from `GenericAPL` (no own keep — falls back to generic land-count heuristic)
- **NO_KEEP**: class doesn't define keep() but inherits from a role-base (good — uses parameterized framework)
- **TRIVIAL**: keep() exists but ≤6 lines or ≤1 if-branch with no named cards
- **SHALLOW**: 1-3 if-branches, no named cards
- **TUNED**: 4+ if-branches with named cards or play-aware logic

## Distribution (52 primary APLs)

| Class | Count | % |
|---|---|---|
| TUNED | 26 | 50% |
| NO_KEEP (role-base inheritor) | 10 | 19% |
| SHIM (GenericAPL inheritor) | 9 | 17% |
| SHALLOW | 7 | 13% |
| TRIVIAL | 0 | 0% |

## Canonical 15-deck Modern field — per-deck tuning grade

| Deck | Field % | Class | Notes |
|---|---|---|---|
| Boros Energy | 22.1 | TUNED 28L 9 ifs | reference quality |
| Amulet Titan | 8.5 | TUNED 74L 29 ifs | most-tuned in repo |
| Eldrazi Ramp | 7.4 | TUNED 15L 5 ifs, 5 named | mid-tuned |
| Izzet Prowess | 7.2 | TUNED 15L 5 ifs | shallow-TUNED |
| Izzet Affinity | 6.8 | TUNED 38L 9 ifs | well-tuned |
| Grinding Breach | 6.4 | TUNED 12L 4 ifs | borderline |
| **Jeskai Blink** | **6.4** | **SHIM** | **goldfish under-represents real deck** |
| Orzhov Blink | 6.1 | (no own .py — uses uw_blink?) | needs investigation |
| Goryo's Vengeance | 5.6 | TUNED 38L 10 ifs | well-tuned |
| Domain Zoo | 5.0 | TUNED 13L 4 ifs | borderline |
| Eldrazi Tron | 4.3 | TUNED 40L 10 ifs | well-tuned |
| Mono Red Aggro | 4.1 | TUNED 26L 6 ifs | mid-tuned |
| **Temur Breach** | **3.8** | **SHIM** | **goldfish under-represents** |
| Dimir Murktide | 3.5 | TUNED 31L 8 ifs | mid-tuned |
| **Esper Blink** | **2.8** | **SHALLOW** | **does not use control_base** |

**Three canonical-field decks (12.4% combined field share) have stub goldfish APLs.** HOWEVER — correction added 2026-04-28 post-investigation: canonical Modern gauntlets use `MATCH_APL_REGISTRY` (matchup-aware variants in `apl/<deck>_match.py`), NOT the goldfish APLs (`apl/<deck>.py`) classified above. So Jeskai Blink in canonical uses `apl/jeskai_blink_match.py` (595L, fully tuned), not the 24L SHIM. The mulligan audit's claim that "SHIM/SHALLOW APLs skew canonical baseline" is INCORRECT — those APLs only affect goldfish-only diagnostic flows (sim.py + apl_tuner.py), which don't drive the canonical 64.5%/78.8% number. The actual canonical-impact gap is the MATCH APL inventory (separate audit needed). This finding learned by attempting to tune `apl/jeskai_blink.py` and discovering it doesn't affect canonical at all.

## SHIMs (9 total — pure GenericAPL fallback)

These all inherit from `GenericAPL` and use `apl/mulligan.py:generic_keep` (land-count only):

| APL | Field/Notes |
|---|---|
| jeskai_blink | **canonical Modern 6.4%** |
| temur_breach | **canonical Modern 3.8%** |
| living_end | fringe Modern (cascade combo) |
| yawgmoth | fringe Modern (sac combo) |
| glockulous | fringe Modern (Grixis reanimator) |
| uw_control | fringe Modern (planeswalker control) |
| izzet_control_standard | Standard |
| mono_green_aggro_standard | Standard |
| roaming_elementals_standard | Standard |

All 9 are documented Stage A 2026-04-26 triage outputs ("registered for gauntlet coverage, hand-tune later"). Now is later.

## NO_KEEP (10 total — role-base inheritors, mostly OK)

These don't define their own keep() but inherit from a role base class that does. Need spot-check that:
- They set the class-attribute card sets (CREATURES / BURN_SPELLS / SETUP_PIECES / ENABLERS / CANTRIPS / THREATS / RAMP_SPELLS / PAYOFFS)
- They override the threshold constants where archetype demands it

| APL | Likely base | Risk |
|---|---|---|
| azorius_aggro_standard | aggro_base | needs verification |
| boros_aggro_standard | aggro_base | needs verification |
| domain_ramp | ramp_base | needs verification |
| gruul_aggro_standard | aggro_base | needs verification |
| izzet_lesson | combo_base? | needs verification |
| izzet_prowess_standard | aggro_base? | needs verification |
| izzet_spellementals_standard | combo_base? | needs verification |
| jeskai_control_standard | control_base | needs verification |
| mono_red_aggro_standard | aggro_base | needs verification |
| superior_doomsday_standard | combo_base | needs verification |

## SHALLOW (7 total — own keep() but only land+1-2 checks)

| APL | Lines | Ifs | Recommended action |
|---|---|---|---|
| burn | 12 | 3 | should inherit aggro_base |
| dimir_midrange | 11 | 3 | should expand or inherit |
| esper_blink | 11 | 3 | **canonical** — should inherit control_base |
| esper_midrange | 11 | 3 | should expand |
| mono_green_landfall | 11 | 3 | should inherit aggro_base or ramp_base |
| rakdos_midrange | 11 | 3 | should expand |
| uw_blink | 10 | 3 | the actual Phelia/Ephemerate engine — should expand |

## Issues identified across all 4 categories

1. **`on_play` parameter universally ignored.** All 4 role-base implementations accept `on_play` but never branch on it. Modern playing T1 lord vs drawing T1 lord matters; this is silently lost.

2. **No must-have-card logic for combo decks.** `combo_base.keep` checks "pieces >= MULL_MIN_PIECES" where pieces is `SETUP_PIECES ∪ ENABLERS ∪ CANTRIPS`. Yawgmoth needs Yawgmoth himself + a persist creature; counting "any 3 cards from the union" lets you keep with just enablers (no Yawgmoth) which is unkeepable in reality.

3. **No sideboarded-keep pattern.** `keep_vs` exists in some APLs as opponent-aware keep, but no `keep_post_board` to handle Bo3 G2/G3 different decision criteria (more interaction, fewer haymakers).

4. **TUNED hand-rolled keeps duplicate role-base logic.** Several TUNED APLs (e.g., burn, mono_red_aggro) reimplement what `aggro_base.keep` would give them via inheritance. Not a bug, but a maintenance tax.

5. **No `bottom()` reflection of strategic priority post-mull.** Most APLs use the `generic_bottom` (cmc-sorted lands+spells) which doesn't know "this deck wants to keep Phlage but bottom Solitude on a draw" — those choices live in main_phase logic, not mull selection.

## Recommended fix path (FUTURE SPEC, not tonight)

**Phase 1 — universal framework (3-4 hrs):**
1. Add play-vs-draw branch to all 4 role-base `keep()` implementations (e.g., on_play allows 1-land hand with 2 ramp; on_draw requires 2 lands)
2. Add `MUST_HAVE_FROM` class attribute to `combo_base` (set of card subsets — keep requires ≥1 from each subset; e.g., Yawgmoth requires `[{"Yawgmoth, Thran Physician"}, {"Young Wolf", "Geralf's Messenger", ...}]`)
3. Migrate the 9 SHIM APLs to appropriate role-base + card sets (~5-10 min each)
4. Audit + fix the 10 NO_KEEP APLs' card-set declarations
5. Audit + (where appropriate) migrate 7 SHALLOW APLs to role bases

**Phase 2 — Bo3 sideboarded keep (1-2 hrs):**
6. Add `MULL_POST_BOARD_*` thresholds to role bases
7. Pass sideboard-game flag through `take_opening_hand` to keep_fn

**Phase 3 — A/B measurement (1 hr per affected deck):**
8. Goldfish baseline before migration
9. Goldfish after migration
10. Document delta in `harness/knowledge/tech/mulligan-framework-deltas-<date>.md`

Estimated total effort: 5-8 hours real work + per-deck A/B testing time (~30 min each * 26 affected APLs would be 13 hrs of validation; can be batched in nightly).

## Tonight's action — outcome

Attempted to tune `apl/jeskai_blink.py` (24L SHIM → ~200L hand-tuned). **Made it WORSE** in goldfish: T6.43 → T7.51, win rate 100% → 98.6%. Investigation revealed:

1. **`sim.py` is hardcoded to `HumansAPL()`** at line 50, regardless of `--deck` arg. So sim.py output never reflected my JeskaiBlinkAPL changes. Only direct `run_simulation(JeskaiBlinkAPL(), ...)` invocations did.
2. **Canonical gauntlets use `MATCH_APL_REGISTRY` (match APLs in `apl/<deck>_match.py`), not `APL_REGISTRY`**. So tuning `apl/jeskai_blink.py` had zero canonical impact.
3. **Match APL is already 595L fully-tuned** (Phelia attack loop, Solitude evoke chain, Phlage escape, Casey Jones, Wrath, March pitch, Consign trigger counters). The match APL is what drives canonical.
4. **For goldfish-only use, GenericAPL beats intricate logic** because half this deck (Solitude evoke, Galvanic, Prismatic, Wrath, March, Consign) is dead in goldfish. My Phlage hardcast prematurely sacrifices a 3/3 attacker for one-shot 3 damage; Phlage escape never fires because no GY fuel; net: slower clock.

**Reverted to SHIM.** Original 24L stub stands.

## Revised action

Two corrected next steps:

1. **Fix `sim.py:50` HumansAPL hardcoding** — accept a `--apl` arg or auto-resolve from `APL_REGISTRY` based on `--deck`. Without this, sim.py is misleading for any deck except Humans.

2. **Pivot the mulligan-framework spec from goldfish APLs to match APLs.** The 30+ goldfish APLs have varying quality but don't drive canonical; the match APL inventory is the right audit target if we want to lift the 64.5%/78.8% baseline.

3. **Match APL inventory audit** — separate doc, similar AST classification but on `apl/*_match.py` files. Until done, we don't know how many match APLs are SHIMs / SHALLOW.

## Connection to existing IMPERFECTIONS

- `gemma-apl-quality-low-for-smoke-gate` — Gemma APLs failing smoke partly because they don't define proper keep(). A keep-framework that defaults to `combo_base.keep` for combo-role generations would lift the floor.
- (No existing entry covers the mulligan-portfolio gap — opening one below.)

## Supporting commands re-runnable from any session

```python
# AST classification (run from mtg-sim root)
import ast, os, re, glob
SKIP = {'__init__','base_apl','generic_apl','auto_apl','playbook_parser',
        'sb_mixin','sb_plans','mulligan','match_apl',
        'aggro_base','combo_base','control_base','ramp_base'}
files = sorted([f for f in glob.glob('apl/*.py')
                if os.path.basename(f).replace('.py','') not in SKIP
                and not os.path.basename(f).endswith('_match.py')])
# (then walk each, find class.keep, classify per Methodology section above)
```
