---
name: mtg-role-theory
description: Mike Flores' "Who's the Beatdown?" doctrine -- beatdown vs control as relational roles, not deck-intrinsic. Use mid-game when deciding whether to race or stabilize; use pre-sideboarding to plan role shifts.
metadata:
  type: knowledge
  domain: mtg
  slice: strategy
  source: "Flores, Who's the Beatdown? (2002 article)"
---

# Role Theory -- Who's the Beatdown?

[Strong] Mike Flores' 2002 essay *Who's the Beatdown?* is one of the
most cited pieces of MTG strategy writing. The thesis is simple but
counter-intuitive on first read, and misassigning role is the dominant
cause of close-game losses at competitive levels of play.

## The thesis

[Strong] In any matchup, one player has the role of "beatdown"
(aggressor, racing the opponent's win condition) and one player has
the role of "control" (stabilizer, denying the opponent's plan and
winning slowly via accumulated advantage). Roles are **relational** --
they depend on the matchup, not on what kind of deck you registered.

[Strong] The beatdown player's job: pressure the opponent fast enough
that they cannot execute their plan. Trade efficiency matters less
than speed; a 1-for-2 trade is acceptable if it puts the opponent on
a faster clock than they have answers for.

[Strong] The control player's job: survive long enough to leverage
inevitability -- whatever long-game advantage their deck has (card
draw, win condition, mana acceleration into a haymaker). Trade
efficiency matters more than speed; every card spent must be worth its
slot in the long game.

## Why the framing is counter-intuitive

[Inference] Most players identify with their deck's archetype label.
"I'm playing red aggro, so I'm always the beatdown." This is wrong
when you face an even faster aggro deck (Mono-Red vs Affinity in
historical Modern, for example), where your "aggro" deck must shift
to control mode -- play your removal, race only when you can finish
in fewer turns than they can.

[Strong] Flores' framing: "The player who is the control deck is
usually the one with the slower clock but more long-term value."
Notice this isn't tied to creatures vs spells, blue vs red, or any
deck label -- it's tied to **relative speed and inevitability** in
the specific matchup.

[Inference] The diagnostic question: if both players draw nothing but
lands from now on, who wins? That player is the control. The other
must apply pressure to flip the inevitability.

## Role-switching across games

[Inference] G1 to G2 transitions often flip roles. A common pattern:

- G1: your aggro deck is the beatdown vs midrange.
- Midrange sideboards in 4-6 sweepers and additional removal.
- G2: your aggro deck must shift to control mode -- play around the
  Wrath, hold a threat in hand, win the long game on board-after-sweeper
  value.

[Strong] The aggro player who keeps slamming threats into a sideboarded
field loses to the sweeper. The aggro player who recognizes the role
has shifted plays differently: deploys threats over multiple turns
("sand-bagging"), holds back card-advantage tools, leverages
must-answer threats first.

[Inference] Role-switching also happens mid-game on critical resolves:

- You resolve a planeswalker that ticks up to lethal in 4 turns -- you
  are now the control even if you started as the beatdown.
- Opponent resolves a Sphinx's Revelation for 5 -- they are now the
  control even if they started as the beatdown.
- Opponent reveals a deck variant you didn't expect (suddenly there's
  a Wrath in their hand) -- role may flip without you seeing the card.

## Beatdown vs Control vs the codebase's 5-role classification

[Inference] `mtg-meta-analyzer/analysis/deck_roles.py` uses a 5-role
taxonomy: Aggro / Midrange / Control / Combo / Tempo. This is finer
than Flores' 2-role frame and serves a different purpose:
**classification**, not role assignment.

Translation between the two frames:

- **Aggro**: structurally the beatdown in most matchups. Switches to
  control mode only vs faster decks (rare in current Standard) or
  vs control sideboarded with sweepers.
- **Control**: structurally the control in most matchups. Switches to
  beatdown mode only vs slower control mirrors (rare; usually one
  control variant is faster than another).
- **Midrange**: maximally role-flexible. Can shift between beatdown
  (vs control) and control (vs aggro) game-to-game. This is why
  midrange is the most demanding to pilot -- you re-diagnose role
  every match.
- **Combo**: usually beatdown (racing toward the combo turn), but can
  be control vs faster combo (disrupt + slow grind).
- **Tempo**: beatdown that pretends to be control. Plays cheap threats
  plus cheap interaction. Role assignment depends on opponent's clock
  vs your remaining interaction.

[Strong] The 5-role classification tells you what a deck typically
**does**. The 2-role role theory tells you what to **do** with that
deck in a specific matchup. They aren't competing frames -- they
operate at different scales.

[Inference] The codebase's classification thresholds
(`deck_roles.py:152-170`):

- Aggro: creature share ≥ 55% AND avg CMC ≤ 2.3 AND cheap-creature
  share ≥ 35%
- Control: creature share ≤ 25% AND (removal + draw) share ≥ 35%
- Combo: ≥ 8 combo indicator cards (must-have critical mass)
- Tempo: creature share ≥ 30% AND removal share ≥ 10% AND avg CMC ≤ 2.5
- Midrange: default (anything not matching the above)

The order matters: Combo is checked first because aggressive combo
decks would otherwise classify as Aggro. Tempo is checked before
Midrange because midrange-with-removal would otherwise classify as
Midrange.

## How to use this block

[Inference] Before sideboarding (and again before mulliganing G1),
explicitly ask: "Who is the beatdown in this matchup?" If you don't
know, you're playing on autopilot. If your answer is "me, always" or
"them, always", you're under-thinking it.

[Inference] Re-ask the question after every major game state change:
a sweeper resolved, opponent revealed an archetype variant, you lost
a critical creature. Role assignment can flip turn-to-turn.

[Inference] At lower levels of play, raw card-quality errors dominate
the loss rate. At RC level, the players are competent enough that
role-misassignment becomes the bottleneck. This is why Flores'
framing has survived 20+ years -- it remains the dividing line between
good and great players.

## Codebase pointer

`mtg-meta-analyzer/analysis/deck_roles.py` -- 5-role classification
based on average decklist composition. The block above translates
between Flores' 2-role frame and the codebase's 5-role frame. If the
codebase classification disagrees with the 2-role intuition for a
deck, that's worth investigating -- the deck may have shifted roles
in the meta.

See also: [[chapin-principles]] -- the Clock and Threats principles
inform which player has the faster clock and thus the beatdown role.
[[threat-answer-density]] -- when answer density runs out before the
opponent's threat density, the player whose answers ran out shifts
to beatdown mode by necessity.
