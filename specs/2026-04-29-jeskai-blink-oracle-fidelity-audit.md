---
title: "Jeskai Blink oracle-fidelity audit + engine gap spec"
status: "PROPOSED"
created: "2026-04-29"
updated: "2026-04-29"
project: "mtg-sim"
estimated_time: "varies — see Phase A/B/C below"
related_findings:
  - "harness/knowledge/tech/jeskai-blink-card-specs-2026-04-28.md"
  - "harness/knowledge/tech/canonical-field-integrity-2026-04-29.md"
related_commits: []
supersedes: null
superseded_by: null
---

# Jeskai Blink oracle-fidelity audit + engine gap spec

## Goal

Get every card in `decks/jeskai_blink_modern.txt` modeled with oracle accuracy. Tonight's session shipped 11 commits worth of fixes to `apl/jeskai_blink_match.py`, but a re-read of every card's actual Scryfall oracle text revealed multiple **mismodeled mechanics** that go deeper than my prior fixes — including a few of my own commits that were based on misreads.

This spec captures the full per-card audit, distinguishes engine-level gaps from APL-level gaps, and proposes a phased fix path.

## Methodology

Loaded all unique cards in `decks/jeskai_blink_modern.txt` (mainboard + sideboard) and printed the local Scryfall oracle text via the existing card DB. Compared each card's oracle to current engine modeling (`engine/card_handlers_verified.py`, `engine/sagas.py`, `engine/keywords.py`) and current match APL behavior (`apl/jeskai_blink_match.py`).

## Per-card audit (mainboard nonland)

### Casey Jones, Vigilante {1}{R}{R} 4/3 Legendary Human Berserker (×2)

**Oracle:** "When Casey Jones enters, draw three cards. At the beginning of your next upkeep, discard three cards at random."

**Engine:** ETB draw 3 fires via `gs.cast_spell()` chain (assumed; not specifically wired but should resolve via standard ETB draw).

**APL:** ✓ Casts on curve. ✓ Tracks pending discards (post 02680f9 fix — accumulates per ETB). ✗ Discards "worst 3" heuristic instead of random — engine pattern, not just JB's.

**Gap:** None at JB level (heuristic matches engine convention). Long-term: deterministic-random for proper RNG channel, but defer.

### Consign to Memory {U} Instant (×4)

**Oracle:** "Replicate {1} (When you cast this spell, copy it for each time you paid its replicate cost. You may choose new targets for the copies.) Counter target triggered ability or colorless spell."

**Engine:** Not specifically modeled (instant resolution; Consign is APL-driven via `respond_to_spell`).

**APL:** ✓ Counters opp triggered abilities + high-CMC colorless spells. ✗ **REPLICATE not modeled** — cannot pay {U}{1} to counter 2 triggers, {U}{1}{1} to counter 3, etc. Limits Consign's combo potential vs storm decks (lots of triggers per turn) and vs the "Phlage hardcast + Consign sacrifice trigger" play (which would also benefit from Consign+replicate).

**Gap:** Replicate alt-cost path needed. APL-level: cost decision (pay 1 replicate vs 2 vs 3 based on # of triggers in stack). Engine: replicate cost mechanic.

### Ephemerate {W} Instant (×2)

**Oracle:** "Exile target creature you control, then return it to the battlefield under its owner's control. Rebound (If you cast this spell from your hand, exile it as it resolves. At the beginning of your next upkeep, you may cast this card from exile without paying its mana cost.)"

**Engine:** Standard cast resolves to blink target.

**APL:** ✓ Casts and blinks best ETB. ✓ Rebound flag persists. ✓ Pays {W} (post a966a74 fix).

**Gap:** None at JB level. Per user feedback: "you can choose not to rebound" — current always-cast-when-target-on-board is correct play; no scenario where skipping is better in goldfish/match.

### Galvanic Discharge {R} Instant (×4)

**Oracle:** "Choose target creature or planeswalker. You get {E}{E}{E} (three energy counters), then you may pay any amount of {E}. Galvanic Discharge deals that much damage to that permanent."

**Per user clarification 2026-04-29:** Damage = energy paid (no +1 base). Gain {E}{E}{E} at resolution → can spend up to total energy on this Discharge's damage.

**APL:** ✓ Damage formula correct (`energy_to_spend >= toughness` is the kill check; matches damage = energy paid).

**Gap:** None — my proposed "off-by-one fix" was a misread; reverted.

### March of Otherworldly Light {X}{W} Instant (×1)

**Oracle:** "As an additional cost to cast this spell, you may exile any number of white cards from your hand. This spell costs {2} less to cast for each card exiled this way. Exile target artifact, creature, or enchantment with mana value X or less."

**Engine:** Not specifically wired (exile-target-permanent resolution).

**APL (post 46e6160):** ✓ White-only pitch filter. ✗ **2-pitch cap was WRONG** — oracle says "any number." My pre-46e6160 fix added a cap that doesn't exist.

**Gap:** Remove 2-pitch cap. With more pitches, March can exile bigger targets cheaply. Need to ensure mana_pool / hand state respects the actual oracle.

### Phelia, Exuberant Shepherd {1}{W} 2/2 Flash Legendary Dog (×4)

**Oracle:** "Flash. Whenever Phelia attacks, exile up to one other target nonland permanent. At the beginning of the next end step, return that card to the battlefield under its owner's control. If it entered under your control, put a +1/+1 counter on Phelia."

**APL:** ✓ Casts on curve. ✓ Attack-blink path with +1/+1 counter applied to `phelia.counters` (post 20518c9). ✓ Opp-creature exile returns at end step (post 02680f9).

**Gap:** None at JB level. Flash usage in matchup play (cast end-of-opp-turn) not modeled — APL only casts in main phase. Minor.

### Phlage, Titan of Fire's Fury {1}{R}{W} 6/6 Legendary Elder Giant (×4)

**Oracle:** "When Phlage enters, sacrifice it unless it escaped. Whenever Phlage enters or attacks, it deals 3 damage to any target and you gain 3 life. Escape—{R}{R}{W}{W}, Exile five other cards from your graveyard. (You may cast this card from your graveyard for its escape cost.)"

**Engine (`_phlage_titan_etb`):** Fires 3 damage + 3 life via `_damage_any_helper`. **Sacrifice clause explicitly NOT modeled** (per code comment). **Attack trigger NOT wired.**

**APL:** Match APL manually models hardcast (3 dmg + 3 life + sacrifice to GY) and escape (4-mana + exile 5 + 3 dmg + 3 life + 6/6 stays). Attack-trigger 3 dmg + 3 life modeled in `declare_attackers`.

**Gap:** Engine handler oracle-incorrect. Match APL is more accurate than engine. **Tension:** when migrating to card_specs, which model wins? Currently goldfish uses engine quirk (Phlage stays after hardcast), match uses oracle-correct sacrifice. Need to decide consistent path:
1. Make engine model sacrifice → goldfish APLs lose Phlage as blocker → canonical baseline shifts (Boros Energy locked at 64.5%)
2. Make card_specs always sacrifice (match-style) → goldfish APLs slow down (T6.43 → T7.51 measured)
3. Document engine-model gap; goldfish accepts the inflation

### Prismatic Ending {X}{W} Sorcery (×1)

**Oracle:** "Converge — Exile target nonland permanent if its mana value is less than or equal to the number of colors of mana spent to cast this spell."

**APL (post db68d8a):** ✗ **WRONG MODEL.** I implemented as `cost = tgt_mv + 1` (X mana = target's MV). Oracle uses CONVERGE: scaling by **number of colors** of mana spent, not by mana amount.

**Gap:** Fix Prismatic logic:
- Pay {X}{W} where X is mana spent in any colors
- Count distinct colors in the payment (Jeskai = max 3: R/U/W)
- Exile target if MV ≤ color count
- E.g., 3-MV target requires paying with at least 3 different colors (R + U + W minimum)

**Engine note:** Converge mechanic likely not modeled at engine level either (no `colors_spent` tracking on cast).

### Quantum Riddler {3}{U}{U} 4/6 Sphinx (×4)

**Oracle:** "Flying. When this creature enters, draw a card. As long as you have one or fewer cards in hand, if you would draw one or more cards, you draw that many cards plus one instead. Warp {1}{U}"

**Engine (`_quantum_riddler_etb`):** Adds FLYING tag, draws 1 on ETB.

**APL:** Casts on curve at 5 mana.

**Gaps:**
1. **Warp {1}{U} not modeled at all** — see `engine-fidelity-gaps-warp-mechanic-not-modeled` IMPERFECTION (~28% of canonical field affected).
2. **+1 draw when hand ≤ 1** — static ability not modeled. Medium impact in Casey discard / Phelia blink loops where hand size cycles low.

### Ragavan, Nimble Pilferer {R} 2/1 Legendary Monkey Pirate (×4)

**Oracle:** "Whenever Ragavan deals combat damage to a player, create a Treasure token and exile the top card of that player's library. Until end of turn, you may cast that card. Dash {1}{R}"

**Engine:** Standard creature.

**APL:** Casts at 1 mana. ✗ **Combat-damage trigger (treasure + top-card-exile) NOT modeled** (line 487-493 explicit `pass`). ✗ **Dash {1}{R} not modeled.**

**Gaps:**
1. **Treasure on combat damage** — needs combat-damage hook in engine. Real ramp loss; T1 Ragavan + 4 attacks = 4 free mana over 4 turns + 4 cards from opp library to potentially cast.
2. **Dash {1}{R}** — alternate cost like Warp. Same engine framework needed (alternate cost + return at end step + works around summoning sickness).

### Solitude {3}{W}{W} 3/2 Flash Lifelink Elemental Incarnation (×4)

**Oracle:** "Flash. Lifelink. When this creature enters, exile up to one other target creature. That creature's controller gains life equal to its power. Evoke—Exile a white card from your hand."

**APL (post ce492dc):** ✓ Evoke pitches white-only. ✓ Hardcast at 5 mana modeled. ✓ Lifelink not specifically modeled but body lifelink fires through normal combat damage.

**Gap:** Lifelink keyword tag — verify engine respects KWTag.LIFELINK on Solitude when she stays as 3/2 attacker. Probably handled via standard keyword pipeline.

### Teferi, Time Raveler {1}{W}{U} Planeswalker (×1)

**Oracle:** "Each opponent can cast spells only any time they could cast a sorcery. +1: Until your next turn, you may cast sorcery spells as though they had flash. −3: Return up to one target artifact, creature, or enchantment to its owner's hand. Draw a card."

**APL:** ✓ -3 draw modeled (bounce dead in goldfish; ignored).

**Gaps:**
1. **Static ability "opponents only sorcery-speed"** — not modeled. Locks opp counterspells (can only cast on own turn). Big in matchups vs blue interaction.
2. **+1 ability** — own sorceries gain flash. Not used; could be relevant for Wrath / Prismatic / March played at instant speed.
3. **Loyalty tracking** — Teferi enters with 4 loyalty. -3 once leaves him at 1. Second activation kills him. Not tracked.

### Wrath of the Skies {X}{W}{W} Sorcery (×1 main + 2 sb)

**Oracle:** "You get X {E} (energy counters), then you may pay any amount of {E}. Destroy each artifact, creature, and enchantment with mana value less than or equal to the amount of {E} paid this way."

**APL:** Modeled with `_should_wrath` heuristic + symmetrical wipe at MV ≤ X. ✓ X-cap tracking.

**Gap:** Optimal X selection (asymmetrical-wipe optimization — pick X such that net opp-creatures-killed minus our-creatures-killed is maximized). Currently caps at X=3 hardcoded. Worth improving but lower priority than other gaps.

## Per-card audit (lands worth modeling)

### Arena of Glory ×3
**Oracle:** {T} = R; {R}{T}+Exert = {R}{R} that grants haste to creatures cast this turn. Exert prevents next-turn untap.
**Engine:** Just logs "mass haste" — no actual haste tracking, no exert tracking, no mana-tagging.
**Impact:** T1 Ragavan + Arena haste = T1 attacker (treasure trigger). Currently summoning-sick. Big tempo loss.

### Elegant Parlor / Meticulous Archive / Thundering Falls (×1 each)
**Oracle:** Surveil 1 on ETB.
**Engine:** Likely vanilla land — no surveil.
**Impact:** Small per land but compounds across 3 lands × N games. Surveil 1 = 1 GY-or-keep per land ETB.

### Hallowed Fountain / Sacred Foundry / Steam Vents (shock lands ×1 each)
Standard 2-life shocks. Probably modeled correctly via ETB.

### Arid Mesa / Flooded Strand / Marsh Flats / Scalding Tarn (fetches ×4/4/1/4)
Standard fetch. Pay 1 life, sac, search.

## Phased fix spec

### Phase A — Match APL fidelity (low risk, today)

In-scope, ~60-90 min total:

1. **Revert March 2-pitch cap** (commit 46e6160 added a wrong cap — oracle says "any number"). Hand-rotted hands on big targets can now cast March correctly. ~5 min.

2. **Fix Prismatic Ending CONVERGE model.** Pay {X}{W} where X = generic mana, color count determines exile threshold. Pick color spread maximizing converge while affording. ~30 min.

3. **Add Quantum Riddler "≤1 hand → +1 draw" static.** Hook into `gs.zones.draw()` or similar. ~15 min.

4. **Add Solitude lifelink verification.** Check `KWTag.LIFELINK` is set on the card from engine ETB; if not, add it manually. ~10 min verification.

### Phase B — Match APL combo additions (medium risk, today or tomorrow)

In-scope, ~60-90 min total:

5. **Phlage hardcast + Consign sacrifice-trigger combo.** When casting Phlage as hardcast, if Consign in hand AND we have {U} extra: counter our own Phlage's "sacrifice unless escaped" trigger. Phlage stays without escape cost. Real 4-mana 6/6 play.

6. **Consign Replicate {1} cost path.** When countering N triggers in a single cast (e.g., Storm), pay {U} + {1}×(N-1) for replicate copies.

7. **Wrath optimal X selection.** Compute opp-creatures-MV distribution + our-creatures-MV distribution; pick X maximizing (opp dead - our dead).

### Phase C — Engine framework gaps (canonical-shifting; needs proper spec)

OUT of tonight's scope. Tracked as IMPERFECTIONS:

8. **Warp alternate-cost mechanic** (28% of canonical field; `engine-fidelity-gaps-warp-mechanic-not-modeled`). 3-4 hr engine work + per-deck APL update.

9. **Dash alternate-cost mechanic** (Ragavan + others). Similar scope to Warp; could share infrastructure.

10. **Saga chapter II + III for Fable** (only Kumano + Roku in `engine/sagas.py:SAGA_EFFECTS`). Plus Fable's transform + tap-to-copy ability.

11. **Goblin Shaman token "treasure on attack" trigger** (Fable Ch2 token).

12. **Arena of Glory haste-grant + exert tracking** (Boros canonical-impact).

13. **Surveil mechanic** (Elegant Parlor / Meticulous Archive / Thundering Falls).

14. **Converge cost-tracking** (Prismatic Ending — counts colors of mana spent on resolution).

15. **Static "opponents sorcery-speed only"** for Teferi, Time Raveler.

16. **Combat-damage triggers framework** for Ragavan treasure / Phlage attack / general attack-trigger registry.

17. **Loyalty-counter tracking for planeswalkers** — Teferi loyalty after activations.

18. **Engine Phlage hardcast sacrifice clause** — currently engine just leaves Phlage as 6/6; oracle says sacrifice unless escaped.

## Validation gates

Per affected APL after Phase A + B fixes:

| Gate | Acceptance | Stop trigger |
|---|---|---|
| JB vs Boros Energy n=1000 seed=42 WR | within ±3pp of 47.0% | >5pp deviation |
| JB vs Amulet Titan n=500 seed=42 WR | within ±3pp of ~78% | >5pp deviation |
| Boros Energy mirror canonical 64.5% | bit-identical (no Boros-side change) | any deviation |
| Prismatic Ending casts in n=1000 game log | actual converge spread, no over-cost | logs show cost > converge requirement |
| March pitches in n=1000 game log | uncapped pitch counts (3+ when hand is loaded) | only 2-cap pitches observed |
| Phlage+Consign combo trigger frequency | observable in verbose mode | never fires when conditions met |

## "And else?" — what else is worth knowing

A. **The 11 commits this session ALL targeted JB only.** Other canonical APLs likely have similar oracle-mismodel patterns I haven't audited. Boros Energy is locked baseline so deferred; but Amulet Titan, Eldrazi Tron, Goryo's Vengeance, Domain Zoo, Eldrazi Ramp, Izzet Affinity, Izzet Prowess, Mono Red Aggro, Dimir Murktide, Esper Blink could each yield 5-15 oracle-correctness commits if audited the same way.

B. **The "tonight" pattern is risky after the Galvanic mistake.** Each "I think this is a bug" commit needs oracle-text verification BEFORE touching code. The Galvanic (1 base + energy) and Prismatic (MV-scaling instead of converge) and March (2-pitch cap) misreads all happened tonight from me not reading oracle text closely enough. **Adding an oracle-verify pre-flight step to any future "bug fix" commit** is a methodology lesson worth codifying.

C. **Many Phase C gaps share infrastructure.** Warp + Dash + Foretell + Suspend are all "alternate cost + delayed return-to-hand trigger" mechanics. One framework could serve all. Same for surveil + scry + investigate (top-card-of-library manipulation).

D. **Combat-damage triggers** are a foundational gap. Ragavan treasure, Phlage attack, Phelia attack-trigger blink, Casey Jones (no but related to combat in some matchups), Goblin Shaman treasure — all need a combat-damage hook. One spec could cover the engine infrastructure; downstream APLs add their card-specific handlers.

E. **Bit-stable testing infrastructure** would compound across all this work. Right now each oracle-correctness commit relies on n=1000 single-matchup spot-checks. A `tools/bit_stability.py` that runs before/after canonical mirror gauntlets at n=2000 against a frozen "pre-fix" baseline would catch regressions automatically.

F. **The current `_phelia_counters` debug field** (preserved alongside `phelia.counters`) is now redundant since the actual counter is applied to the card. Could remove for cleanup.

G. **Match APL should have its own card_specs migration when Phase B ships** — tonight's commits all added inline logic to `jeskai_blink_match.py` (1115L now). Phase B migration would deduplicate that inline logic into `apl/card_specs/`.

## Changelog

- 2026-04-29: Created during late-session oracle re-read after user pointed out missed Warp + Phlage+Consign combo plays. Captures full deck oracle-fidelity audit + phased fix spec.
