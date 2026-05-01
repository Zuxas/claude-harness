---
title: "BorosEnergyAPL content-gap audit + tier-1 fix specs"
domain: "tech"
last_updated: "2026-04-25"
confidence: "high"
status: "spec — fresh-session work, do NOT execute mid-context-fatigue"
sources: ["conversation 2026-04-25 deep-audit thread", "engine.card_db", "apl/boros_energy.py", "engine/card_handlers_verified.py"]
---

## Summary

Tonight's role-refactor work (Phase 1+2) made the BE APL **variant-adaptive**
— that's infrastructure. This doc is **content**: a per-card audit of
what's actually modeled vs what the oracle text says, with the gaps
ranked by play-pattern impact and queued as fresh-session tasks.

**Two real bugs and one obsolete kludge surfaced by tonight's validation
(card_db lookups on Phlage / Guide / Ajani):**

1. **Guide of Souls "another creature" filter is wrong.** Current APL
   fires Guide-of-Souls ETB trigger on Guide's own ETB. Oracle: "Whenever
   ANOTHER creature you control enters". Bug accumulates per Guide on bf.
2. **Ajani planeswalker transform on Cat-die is unmodeled.** The back
   face (Ajani, Nacatl Avenger) has +2, 0, −4 abilities — substantial
   game value, currently invisible to the sim.
3. **Phlage CMC=0 kludge is obsolete.** Card object now reports cmc=3.0
   (data fixed upstream). The hand-rolled `mana_pool.can_pay("{1}{R}{W}", 3)`
   workaround can be replaced with standard `gs.cast_spell(card)`.

These are content fixes, not infrastructure. Different work from the
role refactor. **Do not execute mid-context-fatigue** — content bugs
are exactly the failure mode where tired engineers ship subtly wrong
oracle interpretations that don't surface until the next gauntlet runs
weird.

## Validation results (card_db verified 2026-04-25 night)

### Phlage, Titan of Fire's Fury

```
cost: {1}{R}{W}    cmc: 3.0    type: Legendary Creature — Elder Giant
P/T:  6/6
oracle:
  When Phlage enters, sacrifice it unless it escaped.
  Whenever Phlage enters or attacks, it deals 3 damage to any target
    and you gain 3 life.
  Escape—{R}{R}{W}{W}, Exile five other cards from your graveyard.
```

- **P/T 6/6 confirmed** — the hardcoded `power = "6"; toughness = "6"`
  in `_handle_phlage` escape branch IS correct. Tom's "likely wrong"
  suspicion was wrong; implementation matches oracle.
- **CMC=0 kludge OBSOLETE.** `Card.cmc` loaded from deck file now
  reports 3.0. The mana-pool kludge can be removed (cleanup task in
  Tier 1).
- **"sacrifice unless escaped"** correctly modeled — hardcast path
  always sacs (didn't escape); escape path stays on bf.
- **Attack trigger correctly modeled** as of tonight's commit `bffad48`
  (extracted into `_handle_phlage(phase='combat')`).

### Guide of Souls

```
cost: {W}    cmc: 1.0    type: Creature — Human Cleric
P/T:  1/2
oracle:
  Whenever ANOTHER creature you control enters, you gain 1 life and
    get {E} (an energy counter).
  Whenever you attack, you may pay {E}{E}{E}. When you do, put two
    +1/+1 counters and a flying counter on target attacking creature.
    It becomes an Angel in addition to its other types.
```

**BUG**: APL docstring claim is "Creature enters → gain 1 life + 1 energy"
— missing the **"another"** qualifier. Implementation fires Guide triggers
on Guide's own ETB.

Concrete bug locations in `apl/boros_energy.py`:
- `main_phase2` fill loop, after `gs.cast_spell(card)`:
  ```python
  if "Guide of Souls" in self._deck_names:
      guides = sum(1 for c in gs.zones.battlefield
                   if c.name == GUIDE_OF_SOULS)
      if guides:
          gs.life += guides
          gs.energy += guides
  ```
  When `card` is a Guide, `guides` count includes the just-cast Guide
  → spurious +1 life +1 energy on Guide's own ETB.
- Same pattern repeats in `_handle_arena_exert_haste`,
  `_simulate_ajani_etb`, `_handle_pyromancer_loot` (any place that
  fires a Guide trigger).

Severity: Guide is a 4-of, often 2-3 on bf simultaneously. Each spurious
trigger gives free +1 life +1 energy. Energy fuels Guide attack-pump
(3E for +2/+2 flying counters) and Galvanic Discharge. Over a 5-turn
goldfish, accumulated bonus is meaningful.

Direction of impact: **bug INFLATES sim performance** (extra energy +
life). Real BE plays slightly weaker than the sim shows. Modest
overestimate, but real.

Fix sketch: when the freshly-cast `card` is a Guide, exclude it from
the trigger count (decrement by 1 if `card.name == "Guide of Souls"`).
Or refactor: pass `card_just_cast` into a `_fire_guide_etb_trigger(gs, card_just_cast)`
helper that does the exclusion logic in one place.

### Ajani, Nacatl Pariah

```
front face (creature):
  cost: {1}{W}    cmc: 2.0    type: Legendary Creature — Cat Warrior
  P/T: 1/2
  oracle:
    When Ajani enters, create a 2/1 white Cat Warrior creature token.
    Whenever one or more other Cats you control die, you may exile
      Ajani, then return him to the battlefield transformed under
      his owner's control.

back face (planeswalker):
  name: Ajani, Nacatl Avenger
  type: Legendary Planeswalker — Ajani
  oracle:
    +2: Put a +1/+1 counter on each Cat you control.
    0:  Create a 2/1 white Cat Warrior creature token. When you do,
        if you control a red permanent other than Ajani, he deals
        damage equal to the number of creatures you control to any
        target.
    −4: Each opponent chooses an artifact, a creature, an enchantment,
        and a planeswalker from among the nonland permanents they
        control, then sacrifices the rest.
```

**Currently unmodeled in BE APL**: front-face transform trigger AND
back-face planeswalker abilities.

Trigger conditions for transform (BE-relevant):
- Ocelot Pride dies (Cat) → triggers
- Ajani's own Cat Warrior token dies (Cat) → triggers
- Bombardment sacs an Ocelot or Cat token → triggers
- Combat lethal damage to any Cat → triggers (matchup mode mostly)

Once transformed, Ajani-as-planeswalker provides:
- **+2 ability** is the value engine: pumps every Cat on bf by +1/+1.
  In a board state with Ocelot Pride + Cat tokens + Voice tokens (Voice
  tokens are Warriors, not Cats — don't get pumped), this snowballs hard.
- **0 ability** is a token + conditional Bolt-to-face (red permanent
  required → Ragavan / Phlage / Bolt / Galvanic / Goblin Bombardment
  all qualify).
- **−4** is opp-removal, irrelevant in goldfish.

Implementation concerns:
- Need transform-state tracking on the Card object (currently no
  transform support in engine).
- Need a planeswalker representation (loyalty counters, ability
  activation per turn, +/0/− ability dispatch).
- Need a "Cat died this turn" event tracker (or check on each
  graveyard append).

This is a non-trivial engine extension, not just an APL handler add.
Sized in Tier 1 below at 2-3 hours; could be larger.

## Per-card audit (refined from Tom's deep-audit thread)

| Card | Modeled correctly | Real gap | Tier |
|---|---|---|---|
| **Ragavan** (4) | haste, treasure-on-CD | dash {1}{R}, exile-cast | T3 (matchup) |
| **Ocelot Pride** (4) | lifelink, end-step Cat | city's blessing token copy | T2 |
| **Guide of Souls** (4) | ETB trigger fires | **BUG: "another" filter missing** | **T1** |
| **Phlage** (4) | hardcast/escape/attack/P-T 6/6 | obsolete CMC=0 kludge to remove | T1 (cleanup) |
| **Ajani** (4) | ETB token + Cat trigger Guide | **transform + planeswalker side** | **T1** |
| **Pyromancer** (2) | ETB loot | GY recur activated ability | T2 |
| **Ranger-Captain** (1) | tutor + shuffle | priority routing T3 if no 1-drops | T2 |
| **Bombardment** (3) | lethal sac | mid-game sac for Ajani-transform / Phlage-GY-fill | T2 |
| **Galvanic Discharge** (4) | +3 energy, 0 dmg own creature | face damage in matchup | T3 |
| **Thraben Charm** (2) | dead-in-goldfish skip | (modes for matchup) | T3 |
| **Lightning Bolt** (1) | face_burn 3 dmg | — | done |
| **Blood Moon** (2 MB + 1 SB) | not cast (no opp lands matter) | matchup hosing | T3 |
| **The Legend of Roku** (2 MB + 1 SB) | **NOT CAST AT ALL** | **saga support architecture** | **T1** |
| **Voice of Victory** (variant) | Mobilize 2 dmg + Guide trigger | — | done (today) |

## Tier 1 fix specs (fresh-session ready)

### T1.1 — Guide of Souls "another creature" filter fix (~30-45 min)

**Problem:** `_simulate_guide_attack_trigger` and inline Guide trigger
firings throughout the file count Guide-just-cast as a triggerable
Guide, giving spurious +1 life +1 energy on Guide's own ETB.

**Fix:** Add a helper `_fire_guide_etb_trigger(gs, card_just_cast)`:
```python
def _fire_guide_etb_trigger(self, gs, card_just_cast):
    """Fire Guide of Souls "another creature enters" trigger.
    Per oracle, Guide doesn't trigger on its OWN ETB -- the card
    that just entered must be a different creature."""
    if "Guide of Souls" not in self._deck_names:
        return
    guides = sum(1 for c in gs.zones.battlefield
                 if c.name == GUIDE_OF_SOULS
                 and c is not card_just_cast)  # "another" filter
    if guides > 0:
        gs.life += guides
        gs.energy += guides
        self._gained_life_this_turn = True
        gs._log(f"  Guide trigger ({card_just_cast.name} ETB): "
                f"+{guides} life, +{guides} energy")
```

Then audit every site in `apl/boros_energy.py` that currently does the
inline `if "Guide of Souls" in self._deck_names: guides = sum(...)` and
replace with `self._fire_guide_etb_trigger(gs, card)`. Sites identified:
- `main_phase2` fill-curve loop (cast_spell creature path)
- `_handle_arena_exert_haste` (Arena gives haste to a creature)
- `_simulate_ajani_etb` (Ajani's Cat Warrior token entering)
- `_handle_pyromancer_loot` (Elemental tokens entering)
- `_handle_voice` (Voice's Warrior tokens entering)

For TOKEN ETBs the helper still works (token isn't a Guide, so the
"another" check doesn't matter — guides count is unfiltered).

For CREATURE casts (cast_spell path), pass the just-cast Card so the
helper can exclude it from the count when it's a Guide.

**Validation:** 1000-game canonical, seed=42. Expected: WR stays 100%,
avg kill turn ticks UP slightly (less free energy/life accelerating
Guide pumps). Drift direction: slower. Bound: ±0.3 turn.

### T1.2 — Phlage CMC=0 kludge cleanup (~15 min)

**Problem:** `_handle_phlage(phase='main2')` uses `gs.mana_pool.can_pay("{1}{R}{W}", 3)`
+ manual hand/bf shuffle because of a historical card_db CMC=0 bug.
The bug is now FIXED upstream — card_db loads Phlage with cmc=3.0.

**Fix:** Replace the kludge with standard `gs.cast_spell(card)`:
```python
# OLD
if card.name == PHLAGE and gs.mana_pool.can_pay("{1}{R}{W}", 3):
    gs.mana_pool.pay("{1}{R}{W}", 3)
    gs.zones.remove_from_hand(card)
    gs.zones.battlefield.append(card)
    card.turn_entered = gs.turn
    gs.damage_dealt += 3
    gs.life += 3
    self._gained_life_this_turn = True
    if card in gs.zones.battlefield:
        gs.zones.battlefield.remove(card)
        gs.zones.graveyard.append(card)

# NEW
if card.name == PHLAGE and gs.mana_pool.can_cast(card.mana_cost, card.cmc):
    if not gs.cast_spell(card):  # standard path: pay + ETB + put on bf
        continue
    # Phlage's "ETB unless escaped → sacrifice" handled by handler
    # registry on cast (assuming Phlage has a registered handler;
    # verify before this fix). Damage + life from oracle attack
    # trigger fire here.
    gs.damage_dealt += 3
    gs.life += 3
    self._gained_life_this_turn = True
    # Sac after ETB (didn't escape)
    if card in gs.zones.battlefield:
        gs.zones.battlefield.remove(card)
        gs.zones.graveyard.append(card)
```

**Pre-fix verification:** check whether `card_handlers_verified.py`
has a registered ETB handler for Phlage. If yes, `gs.cast_spell` will
fire it automatically, and the manual `damage_dealt += 3 / life += 3`
in the APL would DOUBLE-COUNT damage. If no registered handler, the
APL must continue to handle damage/life manually.

```bash
grep -n "Phlage" engine/card_handlers_verified.py
```

**Validation:** 1000-game canonical. Expected: numbers IDENTICAL to
current state (cleanup is functional-equivalent). Bound: ±0.05 turn,
±0.5% WR.

### STAGE 0 FINDING (2026-04-25 night) — T1.3 and T1.4 share infrastructure

**Verified via card_db pulls of Roku, Kumano, Kuruk:** all three sagas'
Chapter III is **TRANSFORM**, not sacrifice. The original T1.4 spec
assumed Theros/Dominaria-style "sacrifice after final chapter" sagas;
the actual MH3 sagas in BE all use the transform-into-creature pattern
that DFC planeswalkers like Ajani also use.

The three back faces:

```
The Legend of Roku  →  Avatar Roku (Legendary Creature — Avatar, 4/4)
  Firebending 4 (Whenever this creature attacks, add {R}{R}{R}{R}.
    This mana lasts until end of combat.)
  {8}: Create a 4/4 red Dragon creature token with flying and
    firebending 4.

Kumano Faces Kakkazan  →  Etching of Kumano (Enchantment Creature
                                              — Human Shaman, 2/2)
  Haste
  If a creature dealt damage this turn by a source you controlled
    would die, exile it instead.

The Legend of Kuruk  →  Avatar Kuruk (Legendary Creature — Avatar, 4/3)
  Whenever you cast a spell, create a 1/1 colorless Spirit creature
    token with "This token can't block or be blocked by non-Spirit
    creatures."
  Exhaust — Waterbend {20}: Take an extra turn after this one.
```

All three back faces are creatures with non-trivial mechanics. Implementing
T1.4 as originally specced (sacrifice on Chapter III) would ship a
**half-feature** — Roku gets cast → Chapter I scry-3 → Chapter II +1 mana
→ dies. Avatar Roku, the actual value engine the card is built around,
never appears.

**Net effect:** T1.3 (Ajani transform + planeswalker side) and T1.4 (saga
support + transform on Chapter III) **share the same engine-extension
work**. Doing them sequentially with separate transform implementations
would duplicate effort and risk divergent representations. Doing them as
a combined arc is the architecturally correct path.

### T1.3+T1.4 combined arc — transform infrastructure + first two consumers (~4-7 hours, fresh session required)

**Problem stated:** Engine has no representation for DFC transform. This
silently affects every DFC card across every deck — Ajani's planeswalker
side, MH3 sagas' creature back faces, Magic Origins planeswalkers,
Innistrad werewolves, etc. The audit identified Ajani (T1.3) and Roku
(T1.4) as the two consumers blocking BE accuracy; both need the same
infrastructure.

**Architectural pieces needed:**

1. `Card.is_transformed: bool` — current face indicator.
2. `Card.front_face`, `Card.back_face` populated from `card_db.card_faces`
   at deck load. Each face captures: name, type_line, mana_cost, P/T,
   oracle_text, keywords, loyalty (if planeswalker), lore_counters
   start state (if saga).
3. **Transform mechanic**: `gs.transform(card)` exiles the card,
   instantiates the back face as a new permanent, and triggers any
   "enters transformed" effects per oracle.
4. **Planeswalker representation**: `Card.loyalty: int`, ability
   dispatch (+N / 0 / −N), per-turn activation budget (one ability
   per turn unless flash-style exception).
5. **Saga representation**: `Card.lore_counters: int`, chapter trigger
   dispatch on upkeep + post-draw, transform on final chapter
   (instead of the audit's original "sacrifice" assumption).
6. **APL handlers** for each consumer (Ajani transform-on-Cat-die,
   Ajani-as-planeswalker per-turn loyalty activation, Roku Chapters
   I-II-III, Avatar Roku attack trigger + activated Dragon token).

**Suggested staged execution (5 stages, sustained focus):**

- **Stage 1: Pre-baseline + DFC field plumbing** (~30 min)
  - Re-baseline canonical 1000-game BE (confirm post-T2 stack T4.47).
  - Add `Card.is_transformed`, `Card.front_face`, `Card.back_face`
    fields. Populate from `card_db.card_faces` at deck load.
  - No APL behavior change. 100-game smoke (zero drift).

- **Stage 2: Generic transform mechanic** (~45 min)
  - `gs.transform(card)`: exile card, instantiate back face on
    battlefield, set summoning_sickness (back face is a "new" permanent),
    fire any back-face ETB triggers via existing dispatch.
  - Helper `card.flip_to_back_face()` mutates the Card in place for
    cards that don't actually move zones (some transform mechanics).
  - 100-game smoke (still zero drift — no consumer wired yet).

- **Stage 3: Planeswalker representation** (~60 min)
  - `Card.loyalty: int` field, defaults from `card_faces[N].loyalty`.
  - Per-turn loyalty ability budget (one per turn, except "flash-style"
    exceptions which Ajani doesn't have).
  - Ability dispatch via a `PLANESWALKER_ABILITIES` registry similar
    to `SPECIAL_MECHANICS`: `{card_name: {"+N": handler, "0": handler,
    "-N": handler}}`.
  - Death by 0 loyalty: send to graveyard.
  - Smoke test still zero drift (no consumer wired).

- **Stage 4: Saga representation** (~45 min)
  - `Card.lore_counters: int`, defaults to 0; bump to 1 on ETB
    (oracle: "As this Saga enters and after your draw step, add a
    lore counter").
  - Upkeep + post-draw tick: increment lore_counters, fire chapter
    handler at the new count.
  - When `lore_counters == final_chapter_n`: invoke transform mechanic
    from Stage 2 instead of sacrifice (sagas in this set transform per
    Stage 0 finding).
  - `SAGA_HANDLERS` registry: `{card_name: [chapter_1_fn, chapter_2_fn,
    chapter_3_fn]}` where chapter_3_fn is implicitly "transform" (or
    explicit no-op since transform is automatic).
  - Smoke test still zero drift (no consumer cast yet).

- **Stage 5: First consumer — Ajani transform + planeswalker (T1.3 work)**
  (~60-90 min)
  - Cat-die event tracker (graveyard.append hook for cards with
    "Cat" subtype).
  - APL handler `_handle_ajani_transform(gs)`: detect Cat-die, call
    `gs.transform(ajani_card)` per oracle "you may exile Ajani, then
    return him to the battlefield transformed".
  - Ajani-as-planeswalker registered in `PLANESWALKER_ABILITIES`:
    +2 = pump each Cat by +1/+1. 0 = create 2/1 Cat Warrior token,
    conditional Bolt-to-face if red permanent. −4 = opp-removal
    (no-op in goldfish).
  - APL `_handle_ajani_loyalty(gs)`: +2 each turn for tempo snowball.
  - 100-game smoke + 1000-game validation. Expected drift:
    -0.3 to -0.6 turn faster (Ajani planeswalker is a real value engine).

- **Stage 6: Second consumer — Roku saga + Avatar Roku (T1.4 work)**
  (~60-90 min)
  - APL `self.sagas` role bucket (any Card with "Saga" in type_line).
  - Cast sagas in main_phase2 like other 4-CMC noncreature spells.
  - Register Roku chapter handlers in `SAGA_HANDLERS`:
    - Chapter I: exile top 3, "may play until end of next turn" —
      implement via a `gs.zones.exile_with_play_window` zone or
      flag. Approximation acceptable: treat exiled cards as
      "playable from exile" for next 2 turns.
    - Chapter II: `gs.mana_pool.add_any(1)` — one mana of any color.
    - Chapter III: implicit transform via Stage 4 plumbing.
  - Avatar Roku as a creature: registered as a SPECIAL_MECHANICS
    handler for attack trigger (firebending 4 = +4 mana when attacks),
    activated ability ({8}: 4/4 Dragon token).
  - 100-game smoke + 1000-game validation. Expected drift:
    -0.2 to -0.4 turn faster (Avatar Roku is a 4/4 attacker with
    mana-on-attack value engine, but Roku is 2-of so impact is per-game-
    contingent).

**Stop conditions (any stage):**
- Engine surface area expanding into match_runner / combat / tournament
  code: STOP, narrow scope.
- Smoke test breaks bound: STOP, debug the most recent stage.
- DFC card_faces shape varies between cards in unexpected ways: STOP,
  surface findings before proceeding.
- Stage 5 (Ajani) smoke test direction is FASTER than expected: probably
  +1/+1 counters being double-applied; check for state leak.

**Generalization payoff (record after stage 6):**

After stages 1-6 land, the same infrastructure handles:
- Kumano Faces Kakkazan → Etching of Kumano (Modern Mono Red Aggro)
- The Legend of Kuruk → Avatar Kuruk (deferred in card_handlers_verified.py)
- Magic Origins planeswalkers (Liliana Defiant Necromancer, etc.)
- Innistrad werewolves (transform on day/night)
- Any future DFC card

Each new consumer is just: register chapter or ability handlers in the
appropriate registry, no engine work. Per-format expansion becomes a
content task, not an architecture task.

**Estimated: 4-7 hours, fresh session required.** Not suited for
mid-session execution — engine-wide changes have failure modes that
single-deck smoke tests don't catch (a transform bug could silently
break every DFC card across every deck for weeks).

## Tier 2 (lower-leverage, queue after Tier 1)

- **Ocelot Pride city's blessing token-copy** (~30 min). Conditional on
  10+ permanents. Doubles Ocelot/Ajani/Voice/Pyromancer token output
  for that turn when active.
- **Bombardment sac for Phlage GY-fill** (~30 min). APL currently sacs
  only for lethal. Pre-lethal sacs put creatures in GY → enables Phlage
  escape sooner. Real game pattern.
- **Pyromancer GY recur activated ability** (~30 min). `{R}, exile
  from GY: discard 2, draw 2, +Elementals`. Pyromancer in GY is a
  second Pyromancer cast for 1 mana.
- **Ranger-Captain priority routing** (~10 min). Currently fills curve
  naturally. Could prefer T3 cast when 1-drops are scarce in hand.
- **Bombardment trigger Ajani transform** (after T1.3 lands) — sacing
  Ocelot/Cat tokens to Bombardment fires Ajani's Cat-die trigger.
  Wire after T1.3 plumbing exists.

## Tier 3 (matchup-engine work, not goldfish)

- Ragavan dash {1}{R} alternative cost
- Ragavan exile-cast top of opp library
- Galvanic Discharge face damage (matchup mode)
- Blood Moon color-hosing vs Tron / Domain / Eldrazi
- Thraben Charm modes (creature kill / enchantment kill / GY exile)
- Ranger-Captain sac for opp-noncreature silence
- Phlage 3 dmg to OPPONENT (not own creature) for matchup face damage

## Tier 4 (minor / acceptable)

- Sunbaked Canyon `{T}, sac, pay 1 life: any color` — edge-case mana
  fixing in tight situations. Low frequency.
- Various enters-tapped condition lands (Elegant Parlor, Arena of Glory).
  Engine generic land logic likely handles correctly; verify if BE
  ever fails to make a T2 land drop in sim.

## Execution checklist for fresh session

1. **Re-read this doc + spec doc** at
   `harness/knowledge/tech/apl-role-refactor-2026-04-25.md`.
2. **Pick ONE tier-1 task.** Don't try to do them all in parallel.
   Recommended order:
   - T1.2 (Phlage CMC kludge) first — 15 min, low risk, builds
     confidence in the workflow.
   - T1.1 (Guide "another" filter) second — ~30-45 min, single-file
     change, clear validation.
   - T1.4 (Saga architecture) or T1.3 (Ajani transform) third —
     both are multi-hour engine-extension work. Pick based on which
     compounds more across formats. Probably saga (Kumano + Roku +
     others) wins on generalization.
3. **Re-baseline canonical 1000-game first** if it's been more than a
   week since the last baseline (engine WIP push could have moved
   numbers again).
4. **Stage commits** like the role refactor — small commits per
   sub-step, smoke test after each, full 1000-game validation at the end.
5. **No midnight execution.** This audit was Tom's discipline; honor it.

## Open verification items

These weren't fully verified tonight:

1. Does `card_handlers_verified.py` have an ETB handler for Phlage?
   (Affects T1.2 — if yes, manual damage tracking double-counts.)
   ```bash
   grep -n "Phlage" engine/card_handlers_verified.py
   ```
2. The Legend of Roku exact chapter text (T1.4 implementation needs
   the chapter list).
   ```bash
   python -c "from engine.card_db import CardDB; print(CardDB().get('The Legend of Roku')['oracle_text'])"
   ```
3. Ajani's printed starting loyalty (T1.3 needs it for stage 3).
   `card_db` may not surface loyalty cleanly; check `card_faces[1]`
   for loyalty field.

## Changelog

- 2026-04-25 night (initial): Created from Tom's deep-audit thread.
  Added validation results from card_db lookups (Phlage P/T confirmed,
  Guide "another" bug confirmed, Phlage CMC kludge confirmed obsolete,
  Ajani transform mechanics enumerated). Tier-1 task specs sized for
  fresh-session execution.
- 2026-04-25 night (after T1.2 + T1.1 + T2 stack):
  - **T1.2 LANDED** (commit `554b567`): Phlage CMC=0 kludge removed.
  - **T1.1 LANDED** (commits `7d50bb8` + `ddf34ba`): Guide of Souls
    "another creature" oracle bug fixed; helper extraction across 7
    sites including newly-added Phlage hardcast/escape Guide triggers.
  - **T2.1 REVERTED** (commit `e16f8bd`): Ranger-Captain priority block
    attempted twice, both forms drifted SLOWER. Negative finding
    documented in code; natural fill-curve handling is correct.
  - **T2.2 LANDED with oracle correction** (commit `9a30e7c`):
    Pyromancer GY activation costs {3}{R}{R} per actual oracle, not
    {R} as initially specced. 5-mana cost rarely fires in T4-median
    goldfish. Capability added.
  - **T2.3 LANDED** (commit `4af1354`): Bombardment GY-fill, tokens-only
    safe filter. Conjunction of conditions rare in canonical.
  - **T2.4 LANDED** (commit `198ed30`): Ocelot city's blessing copy
    (Ascend triggered by 10+ permanents). Activates T6+ when game
    lasts long enough.
  - **Re-baseline** (commit `6edf682`): post-T2 stack BE goldfish
    100% / T4.47 / 53% T4 / 93% by T5.
- 2026-04-25 night (T1.4 Stage 0 finding):
  - **STAGE 0 SURFACED MAJOR SCOPE FINDING.** Roku, Kumano, Kuruk
    Chapter III is TRANSFORM, not sacrifice. Original T1.4 spec
    assumption was wrong. T1.3 (Ajani transform) and T1.4 (saga
    transform) share infrastructure. Re-spec'd as a combined
    "T1.3+T1.4 transform infrastructure + first two consumers" arc
    with 6 stages, ~4-7 hours sustained-focus work. Execution
    deferred to fresh session per the architectural-stop discipline
    that caught this finding before any code went in.
  - Three back faces documented: Avatar Roku (4/4 Avatar with
    firebending), Etching of Kumano (2/2 enchantment creature with
    haste + exile-on-death), Avatar Kuruk (4/3 Avatar with
    spell-trigger Spirit tokens + 20-mana extra turn).
- 2026-04-26 (T1.3+T1.4 combined arc COMPLETE -- 6 stages + final):
  - **All 6 stages shipped + final re-baseline commit.** Commits:
    - `68aae47` Stage 1: Card DFC fields (is_transformed, front_face,
       back_face, lore_counters, loyalty) + sagas migration to
       lore_counters. Caught + fixed _get_cards_local whitelist
       bug stripping card_faces.
    - `7ede331` Stage 2: gs.transform(card) mechanic. Note:
       commingled with ~200 lines of pre-existing engine WIP
       (Affinity reducers, Restless lands, Impending tick) that
       were sitting uncommitted in game_state.py; surfaced + accepted.
    - `608b4a4` Stage 3: planeswalker dispatch infrastructure.
       Empty registry; lazy per-turn budget reset (avoids touching
       game_state.py).
    - `8df2e0a` Stage 4: Kumano chapter III now transforms via
       gs.transform (replaces exile approximation).
    - `defde40` Stage 5: Ajani Pariah -> Avenger transform on
       Cat-die + Avenger +2 loyalty per turn. Implementation
       correct; canonical drift ZERO because BE clock too fast
       for planeswalker snowball.
    - `6a6d1fb` Stage 6: Roku saga + Avatar Roku back face. Roku
       Chapters I (draw 1 approximation), II (+1 R mana), III
       (transform). Avatar Roku firebending 4 attack trigger.
       Dispatch helper extended for transformed-card-on-bf check.
       Canonical drift -0.16 turn at 100 games, -0.02 at 1000 games.
  - **Final 1000-game canonical baseline:** 100% WR, T4.45, T4 median,
    53% T4 exact, 92% by T5. Net drift vs pre-arc T2-stack baseline
    T4.47: -0.02 turn faster.
  - **Real value of arc is INFRASTRUCTURE not canonical-BE impact.**
    Same pattern as T2 stack: late-game capabilities lap correctly
    but BE's T4-median clock leaves little room for them to
    materially affect kill turn. Architecturally the arc unlocks:
    Magic Origins planeswalkers, Innistrad werewolves, MH3 sagas in
    Pioneer/Modern decks, all future DFC cards. Each new consumer
    is now a content task (register handlers in
    PLANESWALKER_ABILITIES / SAGA_EFFECTS), not engine work.
  - **Spec deltas confirmed during execution:**
    - Ajani back-face starting loyalty was 3 (not 4).
    - Saga infrastructure was more built-out than spec assumed
      (tick_saga already wired into both upkeep and ETB);
      Stage 4 shrunk from 30min to 10min.
    - Pyromancer GY activation cost was {3}{R}{R} (not {R} as Tom
      originally said) -- caught earlier in T2.2.
    - Summoning sickness on transform: NOT reset per CR 302.1
      (Tom's original spec said reset; CR research showed it's
      preserved through continuous control).
  - **Honest finding for future spec authors:** Tom predicted Stage
    5 (Ajani) would produce -0.3 to -0.6 turn faster drift. Actual
    was zero. The prediction assumed a mid-game window for
    planeswalker activation that doesn't exist in fast goldfish.
    Calibrate predictions against the kill-clock window for the
    deck under test.
