---
name: chapin-six-principles
description: Patrick Chapin's 6 Principles for evaluating decks -- Threats, Answers, Consistency, Velocity, Mana, Clock. Use when grading a decklist, comparing two builds, or identifying the binding constraint in a matchup.
metadata:
  type: knowledge
  domain: mtg
  slice: strategy
  source: "Chapin, Next Level Magic / Next Level Deckbuilding"
---

# Chapin's 6 Principles

[Strong] Patrick Chapin's framework for evaluating a deck or comparing
builds. First articulated in *Next Level Magic* (2010) and refined in
*Next Level Deckbuilding* (2013). The codebase operationalizes a
numeric version in `mtg-meta-analyzer/analysis/chapin.py` -- 0-10
scoring per principle, weighted average for overall.

## The six principles

### 1. Threats

[Strong] What can your deck do *to* the opponent? Cards that pressure
life total, force action, or end the game on their own -- creatures,
planeswalkers, finishers, combo win conditions. Threat density is what
wins inevitability races.

[Inference] Pure value/draw spells are NOT threats by this framing. A
deck that draws cards forever but never closes still loses on time.
This is why "card advantage" alone is insufficient -- see
[[card-advantage]] for why drawing without pressuring is virtual card
disadvantage.

Codebase calibration (`analysis/chapin.py:198-228`): Threats = (creatures
+ planeswalkers) as % of non-land cards. Score scales:
- ≥ 40% density → 10
- 25-40% → 7-10 (linear)
- 15-25% → 5-7 (linear)
- < 15% → max(1, density/0.15 * 5)

### 2. Answers

[Strong] What can your deck do *about* the opponent? Removal, counters,
discard, sweepers. Answer density is what keeps you alive long enough
for your threats to matter.

[Inference] The composition matters as much as the count. 12 spot
removal vs 6 spot + 4 sweepers + 2 counters give very different
matchup spreads. A deck heavy on spot removal loses to go-wide; a deck
heavy on sweepers loses to recurring/sticky threats.

Codebase calibration (`analysis/chapin.py:231-259`): Answers target
varies by format -- Standard/Pioneer/Pauper target 6, Modern 8, Legacy
10. Creature-based interaction (ETB removal etc.) counts at 50%
weight. Score = min(10, qty/target * 10).

### 3. Consistency

[Strong] How reliably does your deck do what it's supposed to do? Land
counts, mana-fixing, redundancy on key effects, draw-smoothing
(cantrips, scry, surveil). The least glamorous principle and the most
often under-weighted.

[Inference] A 60% deck you can pilot reliably beats an 80% deck that
mulligans into a chokehold 1 in 4 games. Brewers under-value
consistency because singletons look interesting; professional builds
correct this by concentrating into 4-ofs.

Codebase calibration (`analysis/chapin.py:262-289`): Consistency =
min(10, 2 + concentration * 10) where concentration is the fraction of
spell slots in 4-ofs. Bonus penalty if singletons exceed 40% of unique
non-land cards.

### 4. Velocity

[Strong] How fast does your deck see its cards? Cantrips, draw spells,
tutors, library manipulation. Velocity converts surplus mana into card
flow and lets you sculpt your hand mid-game.

[Inference] High-velocity decks (cantrip-heavy, looting effects) tend
to play well into longer games but pay a tempo tax G1 -- a cantrip on
turn 2 isn't pressuring the opponent. They benefit most from a strong
clock principle (next) to convert the late game without losing it
early.

Codebase calibration (`analysis/chapin.py:292-324`): Velocity counts
cantrips + draw spells + scry/surveil effects. Creature-based card
draw counts at 50%. Tiers: ≥10 → 10, 6-10 → 7-10, 3-6 → 5-7, <3 →
max(2, draw/3 * 5).

### 5. Mana

[Strong] Mana base quality: color requirements vs sources, fixing
density, tempo cost of duals, fast lands vs check lands vs basics. The
necessary-but-not-sufficient enabler -- a great deck on a broken mana
base is a worse deck.

[Inference] Three-color decks pay a real cost in current Standard.
Two-color decks have nearly free mana bases. The cost shows up as
keepability of opening hands and turn-1 enters-tapped frequency.

Codebase calibration (`analysis/chapin.py:327-362`): Expected lands ≈
17 + (avg CMC × 1.5). Score = min(10, land_ratio × 8 − color_penalty),
where color_penalty = max(0, num_colors − 2) × 0.5. So 3-color decks
pay 0.5 points; 4-color decks pay 1.0; 5-color pay 1.5.

### 6. Clock

[Strong] How fast does your deck actually win? Measured in turns from
"engaged" to "game-ending board state." Aggressive decks have clocks
of 5-7; midrange 7-10; control 10+.

[Strong] Clock pressure is what makes opposing answers desperate. Slow
decks let opponents find perfect answers; fast decks force opponents
to interact with whatever's on top.

Codebase calibration (`analysis/chapin.py:365-400`, format speeds at
lines 184-191): Standard's "fast clock" threshold is avg threat CMC
3.5; "good clock" is 4.0. Modern is faster (2.5 / 3.0). Legacy/Vintage
faster still (1.5 / 2.5). Score formula tiers around these thresholds;
avg threat CMC > "good_clock" drops the score by 1.5 per CMC point.

## The principle weights

[Strong] The codebase weights principles for the overall score
(`analysis/chapin.py:407-414`):

| Principle | Weight |
|---|---|
| Threats | 0.20 |
| Answers | 0.20 |
| Consistency | 0.18 |
| Mana | 0.17 |
| Velocity | 0.15 |
| Clock | 0.10 |

[Inference] Threats + Answers tied for highest weight is consistent
with Chapin's framing that the "what can it do / what can it stop"
axis is the core of deck evaluation. Clock's relatively low weight (10%)
reflects that clock is partially a function of the other principles
(threat density + mana curve) -- it's an emergent property as much as
an input.

## The interaction lattice

[Inference] The principles aren't independent. They form a lattice:

- **Velocity vs Consistency**: more cantrips = better mid-game card
  selection but worse opening hands (cantrips don't pressure life).
  Brewers often over-correct toward velocity at the cost of consistency.
- **Clock vs Answer density**: faster clock = less time to draw answers
  = answer density matters more for the slower side.
- **Threats vs Mana**: 4-color threat density is hard because the mana
  base eats slots. The codebase's color penalty quantifies this.
- **Consistency vs Threats**: 60-card decks trade 4-of consistency for
  threat diversity. Most pro decks stay at 60-card minimum because
  consistency wins more games than novelty.

[Inference] The binding constraint depends on the field:

- Against fast aggro: **Answers + Clock** matter most. You either kill
  their stuff or race them.
- Against slow control: **Threats + Velocity** matter most. You need
  enough must-answer threats and enough draws to keep finding them.
- Against combo: **Answers + Clock** again. Disrupt their plan or beat
  them to the punch.

[Strong] Chapin's framing in *Next Level Deckbuilding*: a deck is only
as strong as its weakest principle, but matchups are won by leveraging
your strongest principle against the opponent's weakest. The framework
isn't a sum -- it's a max-min lattice.

## How to use this block

[Inference] When grading a decklist, score it 0-10 on each principle
(matching the calibration in `analysis/chapin.py`). Identify the
weakest principle -- that's the constraint to address. Identify the
strongest -- that's the matchup angle.

[Inference] When comparing two decks, the higher average score is the
favorite only if principle distributions are similar. A deck with one
10 and three 4s loses more often than a deck with five 7s, even at
identical average.

[Inference] The framework is a guide, not a verdict. A novel deck can
break the framework by leveraging an exploit -- Storm decks violate
Threat density assumptions; Combo decks violate Clock calibrations;
Lands.dec violates Mana assumptions by treating lands as threats.

## Codebase pointer

`mtg-meta-analyzer/analysis/chapin.py` -- 0-10 score per principle on
any decklist, weighted average for overall rating
(Excellent ≥ 8 / Good ≥ 6 / Fair ≥ 4 / Poor < 4).

If this block's framing drifts from what the code does, the code is
the source of truth. File an imperfection and rewrite this block.

See also: [[card-advantage]] for the value math behind Threats and
Answers. [[threat-answer-density]] for the density math behind the
principle calibrations. [[role-theory]] for which principles bind
depending on role assignment.
