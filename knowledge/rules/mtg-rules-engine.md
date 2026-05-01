---
title: "MTG Rules Engine — Complete Reference for APL Development"
domain: "rules"
last_updated: "2026-04-16"
confidence: "high"
sources: ["comprehensive-rules", "competitive-play-patterns"]
---

# MTG Rules Engine for Sim APL Development

This document teaches the AI how Magic actually works so it can write
APL code that models real competitive play, not random card-slinging.

## 1. TURN STRUCTURE

A turn has these phases IN ORDER. The APL must respect this sequence:

### Beginning Phase
1. **Untap Step** — untap all permanents. No player gets priority.
2. **Upkeep Step** — "at the beginning of your upkeep" triggers go here.
   Players get priority. (Pact debt is paid here. Saga advances here.)
3. **Draw Step** — draw a card. Players get priority after.

### Pre-Combat Main Phase (main_phase in sim)
- Play a land (one per turn unless effects grant more)
- Cast any spell type (creatures, artifacts, enchantments, sorceries)
- Activate abilities
- THIS IS WHERE MOST SETUP HAPPENS

### Combat Phase
1. **Beginning of Combat** — "at beginning of combat" triggers
2. **Declare Attackers** — choose which creatures attack
3. **Declare Blockers** — opponent assigns blockers (goldfish: skip)
4. **Combat Damage** — damage is dealt simultaneously
   - First strike/double strike creatures deal damage first
5. **End of Combat** — cleanup triggers

### Post-Combat Main Phase (main_phase2 in sim)
- Another chance to cast spells and play lands (if not played yet)
- Cast creatures that DON'T need to attack this turn
- Use mana generated during combat (e.g., Ragavan Treasure)

### Ending Phase
1. **End Step** — "at the beginning of the end step" triggers
   - Ocelot Pride token trigger happens HERE
   - "Until end of turn" effects still active
2. **Cleanup Step** — discard to hand size, damage wears off

## 2. THE STACK AND PRIORITY

The stack is how spells and abilities resolve. LIFO (last in, first out).

### How it works:
1. Active player casts a spell or activates an ability — it goes ON the stack
2. Both players get priority to respond (add more to the stack)
3. When both players pass priority, the TOP item resolves
4. After resolution, both players get priority again
5. Repeat until stack is empty

### Why this matters for APLs:
- **Ordering triggers matters.** If Guide of Souls and Ocelot Pride both
  trigger when a creature enters, you CHOOSE the order they go on the stack.
  The one on TOP resolves FIRST.
- **Amulet of Vigor:** When a land enters tapped, each Amulet creates a
  separate untap trigger. With 2 Amulets, you get 2 triggers. You can TAP
  the land between triggers resolving. This is how bounce lands make 4+ mana.
- **ETB triggers go on the stack.** The permanent is already on the
  battlefield when the trigger resolves.

### Goldfish simplification:
In goldfish sim, the opponent never has priority. But the ORDERING of your
own triggers still matters enormously.

## 3. TRIGGERS

### Types of triggers (and when they fire):
- **ETB (enters the battlefield):** "When [this] enters..." 
  Fires AFTER the permanent is on the battlefield.
  Example: Primeval Titan ETB searches for 2 lands.

- **Attack triggers:** "Whenever [this] attacks..."
  Fires when declared as an attacker (beginning of declare attackers).
  Example: Titan attack trigger searches for 2 MORE lands.

- **Upkeep triggers:** "At the beginning of your upkeep..."
  Fires during the upkeep step.
  Example: Pact debt, Saga chapter advancement.

- **End step triggers:** "At the beginning of your end step..."
  Example: Ocelot Pride creates tokens.

- **Death triggers:** "When [this] dies..."
  Fires when moved from battlefield to graveyard.

- **Cast triggers:** "When you cast [this]..."
  Goes on the stack ABOVE the spell itself. Resolves FIRST.
  Example: Eldrazi cast triggers.

- **State triggers:** "Whenever you gain life..."
  Fire whenever the condition is met, checked after any event.

## 4. MANA AND LANDS

### Land drops:
- Base: 1 land per turn
- Extra land drops from: Arboreal Grazer ETB, Spelunking ETB, Explore,
  Dryad of the Ilysian Grove, Azusa
- CRITICAL: Extra land drops are CUMULATIVE. Grazer + Spelunking = 3 drops.
- Land drops are a RESOURCE. Using them efficiently is the difference
  between T3 and T6 kills in decks like Amulet Titan.

### Bounce lands (Gruul Turf, Simic Growth Chamber, etc.):
- Enter tapped (normally)
- ETB trigger: return a land you control to hand (MANDATORY)
- Tap for 2 colors of mana
- THE KEY INTERACTION: With Amulet of Vigor, the bounce land enters tapped
  then immediately untaps. You tap it for mana, THEN the bounce trigger
  resolves. You can bounce THE SAME LAND back to hand and replay it with
  another land drop.
- With 1 Amulet + 1 bounce land + 3 land drops = 6 mana from one card.
- With 2 Amulets: each entry = 2 untap triggers = tap between each = 4 mana
  PER ENTRY. 3 entries = 12 mana.

### Lotus Field:
- Enters tapped, ETB sacrifice 2 lands
- Taps for 3 mana of any one color
- With Amulet: enters tapped -> untap trigger -> tap for 3 -> sacrifice 2
- NET GAIN: +3 mana but lose 2 lands. Worth it when you have expendable lands.

### Urza's Saga:
- Is BOTH a land AND an enchantment (counts for delirium)
- Chapter I: "{T}: Add {C}"
- Chapter II: Create Construct token (P/T = artifact count)
- Chapter III: Search library for artifact with MV 0 or 1 (finds Amulet!)
- After Ch III: sacrifice Saga
- PACE: enters on Ch I. Advances at beginning of your draw step (actually
  it's the lore counter added as a triggered ability).

## 5. CREATURES AND COMBAT

### Summoning sickness:
- Creatures can't attack or use {T} abilities the turn they enter
- EXCEPTION: Haste removes summoning sickness
- EXCEPTION: Lands that become creatures (Shifting Woodland) have
  summoning sickness if they entered this turn

### Combat damage:
- Each attacking creature deals damage equal to its POWER
- Trample: excess damage over blocker's toughness goes to player
- In goldfish: all damage goes to opponent (no blockers)

### Haste sources in Amulet Titan:
- Hanweir Battlements: {R}, {T}: give target creature haste
- Spelunking: gives all creatures haste (static ability)
- CRITICAL for Titan: casting Titan without haste = wait a turn to attack
  = miss the attack trigger = 2 fewer land searches = much slower kill

## 6. INTERACTION AND PLAY PATTERNS

### When the opponent can interact (relevant for match APLs):
- Any time they have priority (after each spell/ability resolves)
- Common interaction: counterspells, removal, discard
- CANNOT interact during: untap step, while spells are resolving

### Playing around interaction:
- Bait removal before playing your best threat
- Sequence land drops to play around Blood Moon / land destruction
- Hold Summoner's Pact until you can pay the debt next upkeep

### Sequencing for speed (CRITICAL for combo decks):
THE DIFFERENCE BETWEEN T3 AND T6 IS SEQUENCING.

Wrong sequence (T6):
  T1: Forest, pass
  T2: Bounce land (tapped, no Amulet), bounce Forest
  T3: Forest, cast Amulet, pass
  T4: Play bounce (now with Amulet, get 2 mana), can't cast Titan yet
  T5: Another land, still building mana
  T6: Finally cast Titan

Right sequence (T3):
  T1: Forest, cast Amulet (1 mana)
  T2: Bounce land -> Amulet untaps it -> tap for 2 -> bounce itself
      Replay bounce -> Amulet untaps -> tap for 2 more -> bounce itself
      (if Grazer in hand) cast Grazer (1G) -> ETB put bounce from hand
      Replay bounce -> tap for 2 = 6+ mana total
      Cast Primeval Titan with haste (Spelunking or Hanweir)
  T3: Titan attacks -> searches 2 lands -> wins

The APL must model this T1-Amulet -> T2-chain sequence explicitly.

## 7. AMULET TITAN SPECIFIC KILL LINES

### Line 1: Scapeshift OHKO
Requirements: 1+ Amulet, 4+ lands on battlefield, Scapeshift
- Cast Scapeshift, sacrifice all lands
- Search for: Lotus Field + Tolaria West + bounce lands
- Amulet untaps everything -> massive mana
- Transmute Tolaria West -> find Summoner's Pact -> find creature -> win

### Line 2: Titan + Haste + Chain
Requirements: 6 mana, Titan, haste source
- Cast Titan -> ETB searches 2 lands (Mirrorpool + land)
- Attack -> searches 2 more lands
- Mirrorpool copies Titan -> copy's ETB searches 2 MORE lands
- Each Titan deals 6 trample = 12 damage on the spot, 20+ with extras

### Line 3: Analyst Loop (infinite)
Requirements: Amulet + Lotus + Echoing Deeps + Shifting Woodland + delirium
- Analyst sacrifices all lands -> they go to graveyard
- Deeps copies Lotus from GY -> 3 mana
- Shifting Woodland activates -> becomes creature -> attacks
- Loop generates infinite mana and damage

### Line 4: Beatdown (fallback)
- Titan + whatever attacks. 6/6 trample = 4 hits to kill.
- Construct tokens from Saga add damage.
- This is the T6-T8 line. The APL should AVOID this when faster lines exist.

## 8. GENERAL TRUTHS FOR ALL APLs

### Speed principles:
- Play haste creatures BEFORE combat (so they attack this turn)
- Play non-haste creatures AFTER combat (summoning sickness anyway)
- Cast mana acceleration BEFORE threats (ramp -> threat, not threat -> ramp)
- Use free spells (Pact, Force) when mana is tight
- Sequence energy generators BEFORE energy spenders

### Mulligan principles:
- Aggressive decks: need a 1-drop or fast start
- Combo decks: need at least 1 engine piece + 1 payoff
- Keep hands that DO something by T2, not "hope to draw into it"
- The London mulligan lets you bottom the worst cards — use it

### Resource management:
- Mana is not just "do I have enough" — it's "do I have the RIGHT colors"
- Life total is a resource in goldfish (fetch lands, Phlage life gain)
- Energy is a resource that should be spent efficiently, not hoarded
- Cards in hand = options. Don't waste draw spells early unless desperate.

### Trigger ordering (you choose the order of your simultaneous triggers):
- Put the trigger you want to resolve FIRST on TOP of the stack
- Example: Ocelot Pride + Guide of Souls both trigger on creature ETB.
  Put Guide on top -> resolve Guide first -> gain life + energy ->
  THEN Ocelot resolves -> checks "did you gain life?" -> YES -> make token
  If you ordered wrong: Ocelot resolves first -> no life gained yet -> no token

### Common APL bugs that cost turns:
1. Not replaying bounce lands with extra land drops (Titan: costs 2-3 turns)
2. Playing threats before engine pieces (costs 1-2 turns of setup)
3. Missing haste — casting Titan without Hanweir/Spelunking (costs 1 turn)
4. Wrong land sequencing — tapped land when untapped was available
5. Not using Saga to find Amulet (Titan: costs 1-2 turns vs drawing into it)
6. Casting spells in wrong phase (pre-combat vs post-combat)
7. Not modeling token creation from triggers (Ocelot, Seasoned Pyromancer)
8. Spending energy on wrong targets (pump a 1/1 vs pump a 6/6)
