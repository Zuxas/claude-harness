---
name: threat-answer-density
description: Threat density / answer density math. Use when evaluating whether a deck has enough threats or whether the field has enough answers for those threats.
metadata:
  type: knowledge
  domain: mtg
  slice: strategy
---

# Threat / Answer Density

[Strong] The density math sitting underneath [[chapin-principles]] and
[[card-advantage]]. This block makes the implicit ratios explicit.

## Threat density

[Strong] Threat density = % of your 60-card deck that can win the
game on its own if left unanswered. Creatures, planeswalkers,
finishers, combo pieces. Not card draw, not removal, not mana.

[Inference] Approximate ranges in modern Standard / Pioneer:

| Deck type | Threat count | % of deck |
|---|---|---|
| Aggro | 25-32 | ~40-55% |
| Midrange | 18-24 | ~30-40% |
| Tempo | 16-22 | ~25-35% |
| Control | 4-8 | ~7-13% |
| Combo | 6-12 combo pieces + redundancy | varies |

[Strong] Threat density determines how many sweepers your opponent
needs to draw to break you. A 32-threat aggro deck typically forces
control to draw 2-3 sweepers to win; control's answer density must be
sized accordingly. A 22-threat midrange deck is breakable with 1
well-timed sweeper -- which is why midrange decks invest in
sweeper-resilient threats (planeswalkers, recursive creatures, manlands).

[Inference] Codebase signal: `mtg-meta-analyzer/analysis/blunders.py`
flags Standard decks with fewer than 8 threats (warn) or 4 threats
(major). This isn't tied to deck type -- it's a floor regardless of
strategy. Even control needs some win conditions; a 0-threat deck wins
0 games.

## Answer density

[Strong] Answer density = % of your deck dedicated to disrupting the
opponent. Spot removal, sweepers, counters, discard, hate cards. Not
card draw, not threats.

[Inference] Approximate ranges:

| Deck type | Answer count | % of deck |
|---|---|---|
| Aggro | 2-6 reach / burn | ~3-10% |
| Tempo | 8-12 | ~13-20% |
| Midrange | 10-14 | ~17-23% |
| Control | 18-26 | ~30-43% |
| Combo | varies -- combo protection + sideboard hate hate | varies |

[Strong] Answer composition matters as much as count. 12 spot removal
vs 6 spot + 4 sweepers + 2 counters give very different matchup
spreads:

- High-spot-removal deck: loses to a deck with many small threats
  (go-wide / token swarms outpace your one-at-a-time answers)
- High-sweeper deck: loses to sticky / recurring / planeswalker-heavy
  threats (sweep them once, they come back)
- High-counter deck: loses to decks with cheap threats that develop
  before your counter mana is up

[Inference] Codebase signal: `analysis/blunders.py` warns at 6
interaction cards (Standard / Pioneer / Pauper) and majors at 3. The
check is format-aware: Modern's threshold is 8/4 because Modern is
faster, Legacy's is 10/5 for the same reason.

## Why high threat density beats removal-light control

[Strong] If aggro plays 32 threats and control plays 12 answers,
control runs out of answers around turn 7-8 (assuming roughly
1-for-1 trades). Aggro's job is to ensure threat #25 (the one drawn
around turn 8) is still threatening when it lands.

[Inference] This is why aggro decks lean on "must-answer" threats
(Glistener Elf in Modern Infect; Sheoldred with passive drain;
Atraxa, Grand Unifier as a finisher). Each unanswered threat is a
tempo-CA windfall (see [[card-advantage]]).

[Inference] The math also explains why control decks invest in
high-card-quality answers over high-quantity answers. A Wrath is
worth 3 spot removal in the right matchup; a Sphinx's Revelation is
worth a draw spell + buyback mana for the next answer.

## Why sweepers break the math

[Strong] A sweeper at the right time generates virtual CA equal to
the number of creatures killed minus 1. Against an aggro deck that's
committed to the board (4+ creatures), a Wrath of God is a 3+ for 1.

[Inference] This is why sweeper count + sweeper mana cost is the
control mirror's binding constraint. A sweeper that costs 4 mana vs
one that costs 6 changes the entire meta -- everything faster than 4
mana beats the 6-mana sweeper.

[Strong] Aggro's counter-play to sweepers:
- Deploy threats over multiple turns ("sand-bagging")
- Develop board faster than the sweeper threshold (e.g., 4-mana sweeper
  means deploy lethal damage by turn 4 if possible)
- Play uncounterable / unblockable threats (Cavern of Souls, manlands)
- Play recursive threats that survive sweepers (Bloodghast, Squee,
  unearth creatures)

[Inference] These aren't optional anti-sweeper tools -- they're the
reason aggro decks survive in formats with viable sweepers.

## The 60-card budget tension

[Strong] Every threat slot is not an answer slot, and every answer
slot is not a card-draw slot, and every card-draw slot is not a
mana-fix slot. The 60-card budget forces explicit trade-offs.

[Inference] The "right" budget depends on:
- **Speed of the format**: fast format = more answers + lower mana
  curve (Modern's interaction floor is 8, Standard's is 6)
- **Diversity of the field**: high-diversity field = more flexible
  answers (Stroke of Genius / Force of Will outclass narrow Naturalize
  effects when the field is varied)
- **Your deck's clock**: fast clock = fewer answers needed because
  the game ends before late-game answers matter

[Strong] Chapin's framing (see [[chapin-principles]]): the principle
that becomes binding depends on the field. Threat / answer density
is a measurable expression of that binding constraint -- it's how
the binding constraint manifests at the deckbuilding stage rather
than the in-game stage.

## How to use this block

[Inference] When building a deck, count threat and answer cards
explicitly. Cross-check against the % ranges above for your intended
role. If you're "midrange" but you have 30 threats, you're actually
aggro and should embrace it. If you're "control" but you have only
8 answers, you're brewer-mode and the deck will fold to aggressive
matchups.

[Inference] When evaluating a matchup, compare your answer density
against their threat density. If their threats > your answers, you
must shift to beatdown mode ([[role-theory]]) because you can't grind
them out -- you have to race.

[Inference] When sideboarding, the goal is to change density ratios
in your favor. Bringing in 3 hate cards and 3 sweepers against
go-wide aggro raises your answer density from 10% to 20% -- the
post-board matchup math is dramatically different.

## Codebase pointer

`mtg-meta-analyzer/analysis/blunders.py` -- threat count, interaction
count, and "sweeper viability" checks per format. Standard thresholds:
threats warn ≤ 8 / major ≤ 4; interaction warn ≤ 6 / major ≤ 3.
`mtg-meta-analyzer/analysis/chapin.py` -- Threats and Answers
principles scored against calibrated thresholds (see [[chapin-principles]]
for the formula).

See also: [[card-advantage]] -- virtual CA is what makes sweepers
matter. [[role-theory]] -- the player whose answer density runs out
first is the player who shifts to beatdown mode by necessity.
