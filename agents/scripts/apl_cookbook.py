"""
apl_cookbook.py -- Working code patterns for APL generation

This file contains real, tested code patterns extracted from working APLs.
Used by the APL optimizer to teach Gemma how to write valid sim code.
"""

APL_COOKBOOK = """
SIMULATOR API REFERENCE (use ONLY these functions):

GameState (gs):
  gs.hand() -> list[Card]              # cards in hand
  gs.battlefield() -> list[Card]       # permanents in play
  gs.graveyard() -> list[Card]         # cards in graveyard
  gs.cast_spell(card) -> bool          # cast from hand (pays mana)
  gs.play_land(card) -> bool           # play a land
  gs.tap_lands()                       # tap all lands for mana
  gs.run_combat()                      # attack with all creatures
  gs.has_won(20) -> bool               # check if 20 damage dealt
  gs.damage_dealt                      # int, cumulative damage
  gs.energy                            # int, energy counter
  gs.life                              # int, your life total
  gs.turn                              # int, current turn number
  gs.land_played                       # bool, land played this turn
  gs.mana_pool.total() -> int          # available mana
  gs.mana_pool.can_cast(cost,cmc) -> bool  # cost is string "{1}{R}", cmc is float
  gs.mana_pool.flex                    # int, colorless mana available
  gs.zones.draw(n)                     # draw n cards
  gs.zones.hand_size() -> int
  gs.zones.lands_in_hand() -> list
  gs.zones.creatures_on_battlefield() -> list
  gs.zones.count_lands_in_play() -> int
  gs.zones.play_from_hand(card)        # move card hand->battlefield
  gs.zones.destroy(card)               # permanent -> graveyard
  gs._make_token(name, power, toughness, type_line) -> Card
  gs._log(msg)                         # log a message

Card attributes:
  card.name              # string (ALWAYS use for matching)
  card.cmc               # float
  card.mana_cost         # string e.g. "{1}{W}"
  card.is_land()         # bool
  card.has(Tag.HASTE)    # check tag
  card.counters          # int (+1/+1 counters)
  card.effective_power() # int
  card.tapped            # bool
  card.summoning_sickness # bool

Tags: Tag.HASTE, Tag.CREATURE, Tag.TOKEN

GOLDFISH RULES:
  - No opponent. NEVER reference opponent zones, opponent life, or opponent cards.
  - Goal is to deal 20 damage (gs.damage_dealt >= 20) as fast as possible.
  - All creatures attack every turn via gs.run_combat().

=== WORKING CODE PATTERNS (copy these EXACTLY) ===

PATTERN 1: Cast a specific card from hand
    for card in list(gs.hand()):
        if card.name == "Ragavan, Nimble Pilferer":
            if gs.mana_pool.can_cast(card.mana_cost, card.cmc):
                gs.cast_spell(card)

PATTERN 2: Cast all creatures by priority
    priority = ["Guide of Souls", "Ocelot Pride", "Ajani, Nacatl Pariah"]
    for target_name in priority:
        for card in list(gs.hand()):
            if card.name == target_name:
                if gs.mana_pool.can_cast(card.mana_cost, card.cmc):
                    gs.cast_spell(card)

PATTERN 3: Play a land
    lands = gs.zones.lands_in_hand()
    if lands and not gs.land_played:
        gs.play_land(lands[0])

PATTERN 4: Add energy and spend it
    gs.energy += 3
    if gs.energy >= 3:
        gs.energy -= 3
        # apply effect (e.g. pump creature)

PATTERN 5: Deal direct damage (burn spell effect)
    gs.damage_dealt += 3
    gs._log("  Lightning Bolt -> 3 face damage")

PATTERN 6: Create a token
    token = gs._make_token("Cat", 1, 1, "Creature - Cat")
    # token is automatically on battlefield after _make_token

PATTERN 7: Tutor (search library, put in hand)
    for i, card in enumerate(gs.zones.library):
        if card.cmc <= 1 and not card.is_land():
            found = gs.zones.library.pop(i)
            gs.zones.hand.append(found)
            gs._log(f"  Tutored {found.name}")
            break

PATTERN 8: Draw cards
    gs.zones.draw(2)

PATTERN 9: Sacrifice a creature for effect
    board = gs.zones.creatures_on_battlefield()
    if board:
        target = board[-1]
        gs.zones.destroy(target)
        gs.damage_dealt += 1
        gs._log(f"  Sacrificed {target.name} -> 1 damage")

PATTERN 10: Count specific permanents on board
    board = gs.battlefield()
    cats = [c for c in board if "Cat" in getattr(c, 'type_line', '')]
    cat_count = len(cats)

PATTERN 11: Gain life
    gs.life += 3
    gs._log("  Gained 3 life")

PATTERN 12: Discard and draw (looting)
    hand = list(gs.hand())
    worst = sorted(hand, key=lambda c: c.cmc)[-1]  # discard highest CMC
    gs.zones.remove_from_hand(worst)
    gs.zones.draw(1)

PATTERN 13: Saga / Enchantment with chapter effects
    for card in list(gs.hand()):
        if card.name == "The Legend of Roku":
            if gs.mana_pool.can_cast(card.mana_cost, card.cmc):
                gs.cast_spell(card)
                # Model chapter 1 effect immediately
                gs.energy += 2
                gs._log("  Legend of Roku chapter 1: +2 energy")

=== CRITICAL RULES (violations cause crashes) ===

DO:
  - ALWAYS use list(gs.hand()) when iterating (hand changes during iteration)
  - ALWAYS check gs.mana_pool.can_cast(card.mana_cost, card.cmc) before gs.cast_spell
  - ALWAYS use 4-space indentation
  - ALWAYS match card names EXACTLY as they appear in the deck list
  - Use gs._log() to log what you're doing

DO NOT:
  - NEVER access gs.zones.opponent (does not exist, crashes)
  - NEVER call card.is_castable(gs) (unreliable, use mana_pool.can_cast)
  - NEVER call gs.hand()() with double parens (crashes)
  - NEVER reference opponent life, opponent hand, or opponent board
  - NEVER use card.is_basic_land() (does not exist)
  - NEVER import modules inside main_phase (all imports at file top)
"""
