---
name: card-advantage-taxonomy
description: Taxonomy of card advantage -- raw, virtual, tempo, quality, exchange ratios. Use when evaluating whether a card or play is worth its slot or its mana.
metadata:
  type: knowledge
  domain: mtg
  slice: strategy
  source: "common doctrine -- Romeo, Flores, Duke; calibrated against analysis/blunders.py"
---

# Card Advantage Taxonomy

[Strong] "Card advantage" is shorthand for several distinct concepts
that are often conflated. Separating them is the first move in
evaluating a card or a play.

## Raw card advantage

[Strong] You start with X cards in hand and your opponent starts with
Y. After some exchange, the player with more cards remaining (in hand,
or hand + board depending on framing) has raw card advantage.

[Strong] Sources of raw CA:
- Drawing 2+ from 1 spell (Divination, Read the Bones, Brilliant Restoration)
- Reanimating dead creatures (Animate Dead -- 1 card to get back N cards
  of value from the graveyard)
- 1-for-2 exchanges (Wrath of God kills 2+ creatures = nominally
  2-for-1; cf. virtual CA below)
- Recursion (flashback, escape, delve -- one card resolves twice)

[Inference] Raw CA is the easiest form to measure and the form newer
players over-weight. Drawing cards is good. Drawing cards that don't
directly impact the game state is the failure mode that label-only
"card advantage" engines suffer from. A draw spell that lets you find
your win condition matters; a draw spell that lets you find the next
draw spell in a long chain is dead weight.

## Virtual card advantage

[Strong] A card whose effective value scales with the board state. A
Wrath of God against an empty board is a dead draw; against 4
creatures it's a 4-for-1. The card's "actual" CA is therefore not 1
or 4 -- it's contingent on game state.

[Strong] Sources of virtual CA:
- Sweepers (Wrath, Pyroclasm, Sunfall) -- scale with opponent's board
- Mass disenchant (Cleansing Nova vs artifact decks) -- N-for-1 vs
  artifact-heavy
- Hate cards (Rest in Peace vs reanimator, Containment Priest vs
  combo) -- can lock down an entire strategy from a single slot
- Sideboard slots -- the entire concept of sideboarding is virtual CA
  generation (you swap in cards that scale better in this matchup)

[Inference] Counterspells are partial virtual CA. A Counterspell
trading 1-for-1 nominally generates 0 CA, but if it counters a spell
worth more than 1 card on its own (a Sphinx's Revelation resolving =
~3 cards drawn + life), the counter generates virtual CA proportional
to the prevented value.

[Inference] Codebase signal: `mtg-meta-analyzer/analysis/blunders.py`
flags decks with low interaction counts (Standard: warn at 6, major
at 3). The check isn't asking "how many cards interact?" -- it's
asking "do you have enough virtual-CA tools for the format speed?"

## Tempo as card advantage

[Strong] Every turn you spend on the back foot (no relevant mana spent,
no relevant play made, attacked for X damage) is implicit card
disadvantage -- you're behind on resources whose value compounds.

[Inference] Tempo CA is the form most often invisible to spreadsheet
analysis. A Mana Leak doesn't trade cards 2-for-1, but it costs the
opponent a turn (their spell + the next turn of board development).
Tempo is why counter-burn decks beat midrange even when raw CA looks
even on paper -- the counter+burn shell trades efficient tempo for
the opponent's inefficient threats.

[Strong] Tempo and life total are correlated. Aggro decks convert
tempo into damage; control decks convert tempo into card advantage
later. Both directions work. The mistake is treating tempo as
"meaningless" because it doesn't show up in card-count math.

## Card quality

[Strong] A Sheoldred, the Apocalypse is not equivalent to a Llanowar
Elves. Raw CA counting ignores quality. A 1-for-1 trade of Sheoldred
for Llanowar Elves is a massive loss for the player who lost Sheoldred
even though the card count is "even".

[Inference] Card quality is what makes mana-efficient threats
backbreaking. Sheoldred at 4 mana that draws a card per turn = ~4
free cards over the game = effectively a 5-for-1 if she survives 4
turns. This is why midrange decks lean on "stat-pile" creatures: each
slot must generate value beyond its raw cost.

[Inference] Card quality also explains why "1-for-1 removal" isn't
all created equal. A Lightning Bolt killing a Sheoldred is far better
than a Hero's Downfall killing a Sheoldred -- same raw effect, but
the cheaper card preserves tempo (see above).

## Exchange ratios

[Strong] Trading cards efficiently is the heart of attrition gameplay.
Key ratios:

- **1-for-1**: even (raw), but the player who *chose* the trade gets
  a tempo edge if their card was cheaper or their initiative was higher.
- **1-for-2**: card disadvantage on its face, but often correct when
  one of those 2 cards would have won the game. (Counterspelling a
  win condition with a 1-mana counter trades 1-for-1 but prevents 0-for-game.)
- **2-for-1**: standard "value" trade. Most professional decklists are
  optimized to generate 2-for-1s. Cards that 2-for-1 reliably:
  Snapcaster Mage (1 card slot, 2 cards resolved), Up the Beanstalk
  (N-for-1 over the game), Sphinx's Revelation (1-for-N).
- **N-for-1 (virtual CA)**: the dream, but only when the board aligns.

[Inference] Pro-level deckbuilding is largely an exercise in finding
cards that 2-for-1 reliably under realistic board states. Examples:
modal cards (Bloodbraid Elf -- a creature + a free spell), recursion
(Eternal Witness rebuying any card), engines (Tireless Tracker -- one
card converts each subsequent land into a clue).

[Inference] Brewers under-weight exchange ratios when they include
"cool" 1-for-1 removal over efficient 2-for-1 alternatives. The
question is never "does this card kill the thing?" -- it's "does this
card kill the thing AND do something else?"

## How to use this block

[Inference] When evaluating a card, ask:

1. **Raw CA in a vacuum**? (mostly irrelevant -- a Glimmer of Genius
   in a vacuum is 1.5-for-1 but says nothing about whether you should
   play it)
2. **Virtual CA in the matchup**? (sometimes decisive -- a Wrath is
   amazing vs aggro, dead vs control)
3. **Tempo cost / gain**? (often the binding constraint -- a 6-mana
   2-for-1 is worse than a 3-mana 1.5-for-1)
4. **Card quality vs the slot's alternative**? (Sheoldred ≠ Llanowar
   Elves -- the slot's opportunity cost is the alternative card you'd
   play there)

[Inference] When evaluating a play, ask: am I trading at value, or am
I being forced into a bad trade? If the latter, can I refuse the trade
(hold mana up, don't block, race to bypass) -- forcing the opponent to
either pass or take an even worse trade?

## Codebase pointer

`mtg-meta-analyzer/analysis/blunders.py` -- encodes virtual-CA-style
checks: sweeper viability, interaction count, color consistency. If
the analyzer flags a deck for "low interaction count" (Standard: warn
at 6 cards, major at 3 cards), it's diagnosing answer density (see
[[threat-answer-density]]) but the underlying logic is card-advantage
math: do you have enough cards-per-slot to outvalue the field?

See also: [[chapin-principles]] -- the Threats and Answers principles
quantify the "how many cards are worth their slot" question across the
whole 60-card budget. [[threat-answer-density]] -- the density math
that connects card-advantage theory to actual deck construction.
