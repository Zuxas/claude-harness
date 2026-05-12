# MTG Strategy Knowledge Base -- Slice A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Populate `harness/knowledge/mtg/strategy/` with 6 strategic-theory knowledge blocks (1 overview + 4 theory + 1 format snapshot) that Claude auto-loads before answering MTG strategic questions, grounding future sessions in framework instead of pattern-matching.

**Architecture:** Each block is a self-contained Markdown file with harness-format frontmatter (`name`, `description`, `type: knowledge`). Theory blocks are format-agnostic; one format snapshot block decays and carries a `Format snapshot` date. Blocks cross-link via `[[name]]` references. Every paragraph carries an epistemic tag (`[Strong]` / `[Inference]` / `[Uncertain]`) defined in the spec. Every non-trivial claim names a source. Every block ends with a pointer to the codebase module that operationalizes its doctrine.

**Tech Stack:** Markdown + harness knowledge-base format. Git. Pre-flight reads from `mtg-meta-analyzer/analysis/*.py` (Python) for codebase-pointer accuracy.

**Spec:** `harness/specs/2026-05-12-mtg-strategy-knowledge-base-slice-a.md` (committed 1dd32b3)

---

## File Structure

**Files created (this plan):**

| Path | Purpose | Approx size |
|---|---|---|
| `harness/knowledge/mtg/strategy/_overview.md` | Index of strategy blocks, when to use which | ~200 words |
| `harness/knowledge/mtg/strategy/chapin-principles.md` | Chapin's 6 Principles framework | ~800-1200 words |
| `harness/knowledge/mtg/strategy/role-theory.md` | Flores' "Who's the Beatdown?" doctrine | ~600-900 words |
| `harness/knowledge/mtg/strategy/card-advantage.md` | CA taxonomy: raw / virtual / tempo / quality | ~700-1000 words |
| `harness/knowledge/mtg/strategy/threat-answer-density.md` | Density math, sweeper viability | ~600-900 words |
| `harness/knowledge/mtg/strategy/format-standard-spring-2026.md` | Pillar archetypes' strategic identity (dated snapshot) | ~1200-1800 words |

**Files modified:**

| Path | Change |
|---|---|
| `harness/knowledge/_index.md` | Add `## MTG Strategy` section listing 6 blocks |

---

## Task 1: Setup + pre-flight reads

**Files:**
- Create: `harness/knowledge/mtg/strategy/` (directory)
- Read-only: `mtg-meta-analyzer/analysis/chapin.py`, `analysis/deck_roles.py`, `analysis/blunders.py`, `analysis/meta_scoring.py`
- Read-only: `harness/knowledge/_template.md`, `harness/CLAUDE.md`, `harness/MEMORY.md` (PT SOS findings section)

- [ ] **Step 1.1: Create the strategy subdirectory**

```bash
cd "E:/vscode ai project/harness"
mkdir -p knowledge/mtg/strategy
```

- [ ] **Step 1.2: Verify the harness CLAUDE.md load rule recurses**

Read `harness/CLAUDE.md`. Confirm the MANDATORY KNOWLEDGE LOADING rule for MTG says "read ALL files in `harness/knowledge/mtg/`" (or similar wording that recurses into subdirs).

Expected: A line like `- MTG questions ... → read ALL files in harness/knowledge/mtg/` or stronger.

If the rule only loads flat `mtg/*.md` and NOT subdirs: **STOP** (spec gate 4.1). Surface to user. Decide between:
- (a) Adding an explicit rule: `MTG strategic questions → read ALL files in harness/knowledge/mtg/strategy/`
- (b) Flattening blocks to `mtg/strategy-*.md`

Proceed only after the load rule is verified.

- [ ] **Step 1.3: Read codebase pre-flight files**

Read these and extract the concrete doctrine each encodes:

- `mtg-meta-analyzer/analysis/chapin.py` -- the 6 Principles + calibrated 0-10 scoring thresholds per principle. **Note the exact thresholds** (you'll cite them in Task 3).
- `mtg-meta-analyzer/analysis/deck_roles.py` -- the 5-role taxonomy (Aggro/Midrange/Control/Combo/Tempo) + classification logic. **Note the heuristics** (you'll cite them in Task 4).
- `mtg-meta-analyzer/analysis/blunders.py` -- sweeper viability checks, interaction count thresholds. **Note the specific checks** (you'll cite them in Tasks 5 and 6).
- `mtg-meta-analyzer/analysis/meta_scoring.py` -- Pillar/Trap/Underplayed/Fringe taxonomy. Useful context for Task 7.

If any module differs substantially from what the spec describes: **STOP**, surface, re-scope the affected block.

- [ ] **Step 1.4: Read harness template + PT SOS findings**

- `harness/knowledge/_template.md` -- frontmatter format (name, description, type, optional metadata)
- `harness/MEMORY.md`, section "PT SOS FINDINGS (2026-05-03) -- KEY FACTS FOR RC PREP" -- primary-source data for the format block. Note the official matchup matrix numbers (Selesnya Landfall 63.81%, Mono-Green 55.45%, etc.).

- [ ] **Step 1.5: Commit setup (empty subdir + plan reference)**

No file change yet -- the subdir is empty; Git won't track it. Skip the commit; Tasks 2-7 will create the first file and the subdir along with it.

---

## Task 2: Write `_overview.md`

**Files:**
- Create: `harness/knowledge/mtg/strategy/_overview.md`

- [ ] **Step 2.1: Write the frontmatter**

```markdown
---
name: mtg-strategy-overview
description: Index of MTG strategic-theory knowledge blocks; pointers to which block answers which question. Read first when approaching any MTG strategic question.
metadata:
  type: knowledge
  domain: mtg
  slice: strategy
---
```

- [ ] **Step 2.2: Write the body (~200 words)**

Structure:

```markdown
# MTG Strategy -- Overview

MTG strategic thinking is the layer of frameworks above raw statistics:
why a deck wins, when an archetype is the favorite, how to evaluate a
card outside its raw stats. This subdir crystallizes the doctrine
already encoded in `mtg-meta-analyzer/analysis/` modules plus widely
cited published strategy.

**When to consult which block:**

- [[chapin-principles]] -- evaluating a deck or a card. The
  Threats/Answers/Consistency/Velocity/Mana/Clock framework.
- [[role-theory]] -- "should I be the beatdown or the control?" Game-1
  vs Game-2 role assignment. Misassigning role = losing a winnable game.
- [[card-advantage]] -- "is this card worth its slot?" Raw / virtual /
  tempo CA, two-for-ones, exchange ratios.
- [[threat-answer-density]] -- "does my deck have enough threats / does
  the field have enough answers?" The math under the previous blocks.
- [[format-standard-spring-2026]] -- the strategic identity of each
  current Standard pillar. *Snapshot date matters; rewrite when meta
  shifts.*

Each block tags every paragraph with confidence: `[Strong]` (sourced
doctrine), `[Inference]` (synthesis), `[Uncertain]` (pattern-matched,
reserved for rare use). When in doubt, distrust `[Inference]`.

Each block points to the codebase module that operationalizes its
doctrine. If a block contradicts the code, the code wins -- file an
imperfection and rewrite the block.

[Strong] (this overview reflects the structure of the spec; the rest
is Inference about which block to consult when.)
```

- [ ] **Step 2.3: Validate against spec gates**

Gate 1.4: `description:` is one specific line ✓
Gate 1.2: `[Strong]` tag present ✓
Word count target: ~200 (~250 in the draft above — within bounds)

- [ ] **Step 2.4: Commit**

```bash
cd "E:/vscode ai project/harness"
git add knowledge/mtg/strategy/_overview.md
git commit -m "feat(mtg-strategy): add overview block (slice A, 1/6)"
```

---

## Task 3: Write `chapin-principles.md`

**Files:**
- Create: `harness/knowledge/mtg/strategy/chapin-principles.md`

This is the most important block. The codebase has `analysis/chapin.py` with calibrated thresholds; the block MUST cite those, not made-up numbers.

- [ ] **Step 3.1: Write the frontmatter**

```markdown
---
name: chapin-six-principles
description: Patrick Chapin's 6 Principles framework for evaluating decks -- Threats, Answers, Consistency, Velocity, Mana, Clock. Use when grading a decklist or comparing two builds.
metadata:
  type: knowledge
  domain: mtg
  slice: strategy
  source: "Chapin, Next Level Magic / Next Level Deckbuilding"
---
```

- [ ] **Step 3.2: Write the body (~800-1200 words)**

Outline (you fill in the prose):

```markdown
# Chapin's 6 Principles

Patrick Chapin's framework for evaluating a deck or comparing builds.
First articulated in *Next Level Magic* (2010) and refined in *Next
Level Deckbuilding* (2013). The codebase operationalizes a numeric
version in `mtg-meta-analyzer/analysis/chapin.py` (0-10 scoring per
principle).

## The Six Principles

### 1. Threats
[Strong] What can your deck do TO the opponent? Cards that pressure
life total, force action, or end the game on their own. Threat density
is what wins inevitability races.

[Inference] Pure value/draw spells are not threats. A 0-threat deck
that draws cards forever still loses if it never closes.

Codebase: `analysis/chapin.py` scores Threats based on [cite the actual
threshold from the code -- e.g. "creatures + planeswalkers + win
condition spells; full marks at 18+ slots"].

### 2. Answers
[Strong] What can your deck do ABOUT the opponent? Removal, counters,
discard, sweepers. Answer density is what keeps you alive long enough
for threats to matter.

[Inference] The composition matters as much as the count -- 12 spot
removal vs 6 spot + 4 sweepers + 2 counters give very different
matchup spreads. The "answer the right thing" check is what
`analysis/blunders.py` partially encodes.

Codebase: `analysis/chapin.py` Answers scoring [cite].

### 3. Consistency
[Strong] How reliably does your deck do what it's supposed to do? Land
counts, mana-fixing, redundancy on key effects, draw-smoothing
(cantrips, scry, surveil).

[Inference] Consistency is the principle most often under-weighted by
brewers. A 60% deck you can pilot reliably beats an 80% deck that
mulligans into a chokehold 1 in 4 games.

Codebase: `analysis/chapin.py` Consistency scoring + `analysis/blunders.py`
land count checks [cite].

### 4. Velocity
[Strong] How fast does your deck see its cards? Cantrips, draw spells,
tutors, library manipulation. Velocity converts surplus mana into card
flow and lets you sculpt your hand mid-game.

[Inference] High velocity decks (cantrips, looting effects) tend to
play well into longer games but pay a tempo tax G1. They benefit most
from the next principle.

Codebase: `analysis/chapin.py` Velocity scoring [cite].

### 5. Mana
[Strong] Mana base quality: color requirements vs sources, fixing,
tempo cost of duals, fast lands vs check lands vs basics. The
necessary-but-not-sufficient enabler -- a great deck on a broken mana
base is a worse deck.

[Inference] Three-color decks pay a real cost. Two-color decks have
near-free mana bases in modern Standard. The cost shows up as
keepability of opening hands.

Codebase: `analysis/chapin.py` Mana scoring [cite].

### 6. Clock
[Strong] How fast does your deck actually win? Measured in turns from
"engaged" to "game-ending board state." Aggressive decks have clocks
of 5-7; midrange 7-10; control 10+.

[Inference] Clock pressure is what makes opposing answers desperate.
Slow decks let opponents find perfect answers; fast decks force the
opponent to interact with whatever's on top.

Codebase: `analysis/chapin.py` Clock scoring [cite].

## The Interaction Lattice

[Inference] The principles aren't independent. They form a lattice:

- **Velocity vs Consistency**: more cantrips = better mid-game card
  selection but worse opening hands (cantrips don't pressure life).
- **Clock vs Answer density**: faster clock = less time to draw
  answers = answer density matters more.
- **Threats vs Mana**: 4-color threat density is hard because the mana
  base eats slots.
- **Consistency vs Threats**: 60-card decks trade 4-of consistency for
  threat diversity. 75-80% of pro decks stay at 60 because consistency
  wins.

The principle that becomes the binding constraint depends on the field.
Against fast aggro: Answers + Clock matter most. Against slow control:
Threats + Velocity matter most. Against combo: Answers + Clock again
(disrupt + race).

[Strong] Chapin's framing: "A deck is only as strong as its weakest
principle, but matchups are won by leveraging your strongest principle
against the opponent's weakest."

## How to use this block

When grading a decklist, score it 0-10 on each principle (matching the
calibration in `analysis/chapin.py`). Identify the weakest principle
-- that's the constraint to address. Identify the strongest principle
-- that's the matchup angle.

When comparing two decks, the deck with higher average score is the
favorite ONLY IF principle distributions are similar. A deck with one
10 and three 4s loses to a deck with five 7s most of the time.

[Inference] The framework is a guide, not a verdict. A novel deck can
break the framework by leveraging an exploit (e.g., Storm decks
violate Threat density assumptions; Combo decks violate Clock
calibrations).

## Codebase pointer

`mtg-meta-analyzer/analysis/chapin.py` operationalizes this framework
as a 0-10 score per principle on any decklist. If this block's framing
drifts from what the code does, the code is the source of truth.
File an imperfection and rewrite.
```

- [ ] **Step 3.3: Fill in the bracketed `[cite ...]` thresholds from `analysis/chapin.py`**

Open `mtg-meta-analyzer/analysis/chapin.py` and replace every `[cite ...]`
with the actual threshold from the code. Example: if chapin.py scores
Threats as `min(10, threat_count * 0.55)`, write that explicitly.

- [ ] **Step 3.4: Validate against spec gates**

- Gate 1.1: Every non-trivial claim has a name (Chapin / Inference) ✓ (verify)
- Gate 1.2: Every paragraph tagged ✓ (verify)
- Gate 1.3: `analysis/chapin.py` referenced and the doctrine actually appears in the code ✓ (you read it in Task 1)
- Gate 1.4: `description:` is one specific line ✓
- Gate 3.1: 800-1200 words ✓ (verify with `wc -w`)

- [ ] **Step 3.5: Commit**

```bash
cd "E:/vscode ai project/harness"
git add knowledge/mtg/strategy/chapin-principles.md
git commit -m "feat(mtg-strategy): add chapin-principles block (slice A, 2/6)"
```

---

## Task 4: Write `role-theory.md`

**Files:**
- Create: `harness/knowledge/mtg/strategy/role-theory.md`

- [ ] **Step 4.1: Write frontmatter**

```markdown
---
name: mtg-role-theory
description: Mike Flores' "Who's the Beatdown?" doctrine -- beatdown vs control as relational roles, not deck-intrinsic. Use mid-game when deciding whether to race or stabilize.
metadata:
  type: knowledge
  domain: mtg
  slice: strategy
  source: "Flores, Who's the Beatdown? (2002)"
---
```

- [ ] **Step 4.2: Write the body (~600-900 words)**

Outline:

```markdown
# Role Theory -- Who's the Beatdown?

Mike Flores' 2002 essay "Who's the Beatdown?" is one of the most cited
pieces of MTG strategy writing. The thesis is simple but
counter-intuitive on first read.

## The thesis

[Strong] In any matchup, one player has the role of "beatdown"
(aggressor, racing the opponent's win condition) and one player has
the role of "control" (stabilizer, denying the opponent's win
condition and winning slowly). Roles are RELATIONAL -- they depend on
the matchup, not on what kind of deck you registered.

[Strong] The beatdown player's job: pressure the opponent's life total
or resources fast enough that they cannot execute their plan.

[Strong] The control player's job: survive long enough to leverage
inevitability -- whatever long-game advantage their deck has (card
draw, win condition, mana acceleration into a haymaker).

## Why it's counter-intuitive

[Inference] Most players identify with their deck's archetype label.
"I'm playing red aggro, so I'm always the beatdown." This is wrong
when you face an even faster aggro deck (Mono-Red vs Affinity, for
example), where your "aggro" deck must shift to control mode -- play
your removal, race only when you can finish in fewer turns than they
can.

[Strong] Flores: "The player who is the control deck is usually the
one with the slower clock but more long-term value." Notice this
isn't tied to creatures vs spells, blue vs red, or any deck label --
it's tied to relative speed and inevitability.

## Role-switching across games

[Inference] G1 to G2 transitions often flip roles. Common pattern:

- G1: aggro deck is the beatdown vs midrange.
- Midrange sideboards in 4-6 sweepers / additional removal.
- G2: aggro deck must shift to control mode -- play around the Wrath,
  hold a threat in hand, win the long game on resources.

The aggro player who keeps slamming threats into a sideboarded field
loses. The aggro player who realizes the role has shifted plays
differently.

## The codebase mapping

[Inference] `mtg-meta-analyzer/analysis/deck_roles.py` uses a 5-role
taxonomy: Aggro / Midrange / Control / Combo / Tempo. This is finer
than Flores' 2-role frame and serves a different purpose:
classification, not role assignment.

Translation:
- Aggro: structurally the beatdown in most matchups. Loses role only
  vs faster decks.
- Control: structurally the control in most matchups. Loses role only
  vs slower decks (other control mirrors).
- Midrange: most role-flexible. Can shift between beatdown (vs
  control) and control (vs aggro) game-to-game.
- Combo: usually beatdown (racing toward the combo turn), but can be
  control vs faster combo (disrupt + slow grind).
- Tempo: beatdown that pretends to be control. Plays cheap threats +
  cheap interaction. Role assignment depends on opponent's clock vs
  your remaining countermagic.

[Strong] The 5-role classification tells you what a deck typically
DOES. The 2-role role theory tells you what to DO in a specific
matchup with that deck.

## How to use this block

Before sideboarding (and again before mulliganing G1), explicitly ask:
"Who is the beatdown in this matchup?" If you don't know, you're
playing on autopilot. If your answer is "me, always" or "them,
always", you're under-thinking it.

Re-ask the question after every major game state change: a sweeper
resolved, opponent revealed their archetype variant, you lost a
critical creature. Role assignment can flip turn-to-turn.

[Inference] Misassigned role is the dominant cause of close-game
losses at the RC level. At lower levels of play, raw card-quality
errors dominate. At RC level, the players are competent enough that
role-misassignment becomes the bottleneck.

## Codebase pointer

`mtg-meta-analyzer/analysis/deck_roles.py` -- 5-role classification.
This block translates between Flores' 2-role frame and the codebase's
5-role frame. If the codebase classification disagrees with the
2-role intuition for a deck, that's worth investigating -- the deck
may have shifted roles in the meta.

See also: [[chapin-principles]] -- Clock and Threats principles
inform which player has the faster clock and thus the beatdown role.
```

- [ ] **Step 4.3: Validate against spec gates**

- Sources: Flores cited ✓
- Tags: every paragraph tagged ✓
- Codebase pointer: deck_roles.py exists ✓
- Word count: ~700 words (verify with `wc -w`)

- [ ] **Step 4.4: Commit**

```bash
cd "E:/vscode ai project/harness"
git add knowledge/mtg/strategy/role-theory.md
git commit -m "feat(mtg-strategy): add role-theory block (slice A, 3/6)"
```

---

## Task 5: Write `card-advantage.md`

**Files:**
- Create: `harness/knowledge/mtg/strategy/card-advantage.md`

- [ ] **Step 5.1: Write frontmatter**

```markdown
---
name: card-advantage-taxonomy
description: Taxonomy of card advantage -- raw, virtual, tempo, quality, exchange ratios. Use when evaluating whether a card or play is worth its slot or its mana.
metadata:
  type: knowledge
  domain: mtg
  slice: strategy
  source: "common doctrine -- Romeo, Flores, Duke; calibrated against analysis/blunders.py"
---
```

- [ ] **Step 5.2: Write the body (~700-1000 words)**

Outline:

```markdown
# Card Advantage Taxonomy

## Raw card advantage

[Strong] You start with X cards and your opponent starts with Y. After
some exchange, the player with more cards remaining (in hand + board,
or just hand depending on the framing) has card advantage.

Sources: drawing 2 from 1 spell (Divination), reanimating dead
creatures (Animate Dead), exchanging 1 spell for 2 of opponent's
(Wrath against 2+ creatures).

[Inference] Raw CA is the most measurable form. Easy to count, easy
to compare. It's also the form newer players over-weight: drawing
cards is good, but drawing cards that don't directly impact the game
is the failure mode that label-only "card advantage" engines suffer.

## Virtual card advantage

[Strong] A card whose effective value scales with the board state. A
Wrath of God against an empty board is a dead draw; against 4
creatures it's a 4-for-1.

[Strong] Sweepers, mass disenchant effects, and global hate cards
(Rest in Peace, Containment Priest) generate virtual CA when the game
state aligns with them. Sideboard slots leverage this -- you bring in
the right hate at the right time.

[Inference] Counterspells are partial virtual CA: a Counterspell
trading 1-for-1 nominally generates 0 CA, but if the counter denies a
spell worth more than a card on its own (a Sphinx's Revelation
resolving = ~3 cards), the counter generates value via virtual CA.

Codebase: `mtg-meta-analyzer/analysis/blunders.py` checks sweeper
viability against the meta -- the "should you bring in Wrath?"
question is implicitly a virtual-CA question.

## Tempo as card advantage

[Strong] Every turn you spend on the back foot (no mana spent, no
relevant play made, attacked for X) is implicit card disadvantage --
you're behind on resources whose value compounds.

[Inference] Tempo CA is the form most often invisible to spreadsheet
analysis. A Mana Leak doesn't trade cards 2-for-1, but it costs the
opponent a turn (their spell + their next-turn tempo). Tempo is why
counter-burn decks beat midrange even when raw CA looks even.

[Strong] Tempo and life total are correlated. Aggro decks convert
tempo into damage; control decks convert tempo into card advantage
later. Both work.

## Card quality

[Strong] A Sheoldred, the Apocalypse is not equivalent to a Llanowar
Elves. Raw CA counting ignores this. A 1-for-1 trade of Sheoldred for
Llanowar Elves is a massive loss even though the CA is "even".

[Inference] Card quality is what makes mana-efficient threats
backbreaking. Sheoldred at 4 mana that draws a card per turn = ~4
free cards over the game = effectively a 5-for-1 if she survives 4
turns. This is why midrange decks lean on "stat-pile" creatures.

## Exchange ratios

[Strong] Trading cards efficiently is the heart of attrition gameplay.
Key ratios:

- 1-for-1: even (raw), but the player who CHOSE the trade gets a tempo
  edge.
- 1-for-2: card disadvantage on its face, but often correct when one
  of those 2 cards would have won the game.
- 2-for-1: standard "value" trade. Most professional decklists are
  optimized to generate 2-for-1s.
- N-for-1 (virtual CA): the dream, but only when the board aligns.

[Inference] Pro-level deckbuilding is largely an exercise in finding
cards that 2-for-1 reliably under realistic board states. Examples:
Snapcaster Mage (flashback target = 2 cards from 1 slot), Brainstorm
+ shuffle effects (1 cantrip + 2 tutored cards), Up the Beanstalk
(N-for-1 over the game).

## How to use this block

When evaluating a card, ask:
1. What's the raw CA in a vacuum? (mostly irrelevant)
2. What's the virtual CA in the matchup? (sometimes decisive)
3. What's the tempo cost / gain? (often the binding constraint)
4. What's the card quality compared to the slot's alternative?

When evaluating a play, ask: am I trading at value, or am I being
forced into a bad trade? If the latter -- can I refuse the trade
(holding mana up, not blocking, etc.)?

## Codebase pointer

`mtg-meta-analyzer/analysis/blunders.py` -- encodes virtual-CA-style
checks: sweeper viability, interaction count, color consistency. If
the analyzer flags a deck for "low interaction count" it's
diagnosing answer-density (see [[threat-answer-density]]) but the
underlying logic is card-advantage math.

See also: [[chapin-principles]] -- the Threats principle is implicitly
"how many cards in your deck are worth their slot vs the opponent's
clock?"
```

- [ ] **Step 5.3: Validate against spec gates**

- Sources: common doctrine + codebase pointer ✓
- Tags: every paragraph tagged ✓
- Word count: ~800 (verify)

- [ ] **Step 5.4: Commit**

```bash
cd "E:/vscode ai project/harness"
git add knowledge/mtg/strategy/card-advantage.md
git commit -m "feat(mtg-strategy): add card-advantage block (slice A, 4/6)"
```

---

## Task 6: Write `threat-answer-density.md`

**Files:**
- Create: `harness/knowledge/mtg/strategy/threat-answer-density.md`

- [ ] **Step 6.1: Write frontmatter**

```markdown
---
name: threat-answer-density
description: Threat density / answer density math. Use when evaluating whether a deck has enough threats or whether the field has enough answers for those threats.
metadata:
  type: knowledge
  domain: mtg
  slice: strategy
---
```

- [ ] **Step 6.2: Write the body (~600-900 words)**

Outline:

```markdown
# Threat / Answer Density

The density math sitting underneath [[chapin-principles]] and
[[card-advantage]].

## Threat density

[Strong] Threat density = % of your 60-card deck that can win the game
on its own if left unanswered. Creatures, planeswalkers, finishers,
combo pieces. Not card draw, not removal, not mana.

[Inference] Approximate thresholds in modern Standard:
- Aggro decks: 25-32 threats (~40-55% of the deck)
- Midrange: 18-24 threats (~30-40%)
- Control: 4-8 threats (~7-13%)
- Combo: 6-12 combo pieces + redundancy

[Strong] Threat density determines how many sweepers your opponent
needs to draw to break you. A 32-threat aggro deck typically forces
control to draw 2-3 sweepers to win; control's answer density must
be sized accordingly.

Codebase: `mtg-meta-analyzer/analysis/blunders.py` flags decks with
threat counts outside the calibrated range for the deck's role
(per `analysis/deck_roles.py`).

## Answer density

[Strong] Answer density = % of your deck dedicated to disrupting the
opponent. Spot removal, sweepers, counters, discard, hate cards. Not
card draw, not threats.

[Inference] Approximate thresholds:
- Aggro decks: 2-6 reach / burn (~3-10%)
- Midrange: 10-14 answers (~17-23%)
- Control: 18-26 answers (~30-43%)
- Combo: variable -- combo protection (Pact of Negation, sideboard
  hate hate)

[Strong] Answer composition matters as much as count. 12 spot removal
vs 6 spot + 4 sweepers + 2 counters give very different matchup
spreads. A deck with high spot-removal count loses to a deck with
many small threats (go-wide); a deck with high sweeper count loses
to a deck with sticky / recurring threats.

Codebase: `analysis/blunders.py` checks for "interaction package
balance" -- if a midrange deck has 10 spot removal and 0 sweepers,
it's flagged.

## Why high threat density beats removal-light control

[Strong] If aggro plays 32 threats and control plays 12 answers,
control runs out of answers around turn 7-8 (assuming 1-for-1
trades). Aggro's job is to ensure threat #25 (the one drawn around
turn 8) is still threatening.

[Inference] This is why aggro decks lean on "must-answer" threats
(Glistener Elf with infect counters, Sheoldred with passive drain).
Each unanswered threat is a tempo-CA windfall.

## Why sweepers break the math

[Strong] A sweeper at the right time generates virtual CA equal to
the number of creatures killed minus 1. Against an aggro deck that's
committed to the board (4+ creatures), a Wrath of God is a 3+ for 1.

[Inference] This is why sweeper count + sweeper mana cost is the
control mirror's binding constraint. A sweeper that costs 4 vs a
sweeper that costs 6 changes the meta -- everything that's faster
than 4 mana beats the 6-mana sweeper.

[Strong] Aggro's counter-play: deploy threats over multiple turns
("sand-bagging"), develop board faster than the sweeper threshold,
play uncounterable threats (Cavern of Souls), or play recursive
threats that survive sweepers (Bloodghast).

## The 60-card budget tension

[Strong] Every threat slot is not an answer slot, and every answer
slot is not a card-draw slot, and every card-draw slot is not a
mana-fix slot. The 60-card budget forces trade-offs.

[Inference] The "right" budget depends on:
- Speed of the format (fast format = more answers + lower mana curve)
- Diversity of the field (high-diversity field = more flexible
  answers like Stroke of Genius or Force of Will)
- Your deck's clock (fast clock = fewer answers needed)

[Strong] Chapin's framing (see [[chapin-principles]]): the principle
that becomes binding depends on the field. Threat / answer density is
a measurable expression of that binding constraint.

## Codebase pointer

`mtg-meta-analyzer/analysis/blunders.py` -- threat count, interaction
count, and "sweeper viability" checks.
`mtg-meta-analyzer/analysis/chapin.py` -- Threats and Answers
principles, scored against calibrated thresholds.

See also: [[card-advantage]] -- virtual CA is what makes sweepers
matter. [[role-theory]] -- the player whose answer density runs out
first is the player who shifts to beatdown mode.
```

- [ ] **Step 6.3: Validate against spec gates**

Tags, sources, codebase pointers, word count -- verify.

- [ ] **Step 6.4: Commit**

```bash
cd "E:/vscode ai project/harness"
git add knowledge/mtg/strategy/threat-answer-density.md
git commit -m "feat(mtg-strategy): add threat-answer-density block (slice A, 5/6)"
```

---

## Task 7: Write `format-standard-spring-2026.md`

**Files:**
- Create: `harness/knowledge/mtg/strategy/format-standard-spring-2026.md`

The longest block; the format-meta one that decays. Carries a snapshot date.

- [ ] **Step 7.1: Write frontmatter**

```markdown
---
name: format-standard-spring-2026
description: Strategic identity of pillar archetypes in Standard Spring 2026 (post PT Secrets of Strixhaven). Use when reasoning about a current Standard matchup or deck choice. Decays -- rewrite when meta shifts.
metadata:
  type: knowledge
  domain: mtg
  slice: strategy
  format_snapshot: 2026-05-12
  sources:
    - "PT Secrets of Strixhaven results (data/pt_sos_2026.json)"
    - "harness/MEMORY.md PT SOS FINDINGS section"
    - "mtg_meta.db archetype data as of 2026-05-12"
---
```

- [ ] **Step 7.2: Write the body (~1200-1800 words)**

Structure:

```markdown
# Standard Spring 2026 -- Pillar Archetypes

**Format snapshot: 2026-05-12** (post PT Secrets of Strixhaven, pre
May 29 RC)

This block decays. The pillar list and matchup reads are valid as of
2026-05-12; meta shifts after new sets release. When PT data is older
than 30 days or a new set legalizes, rewrite the block.

## The pillars

After PT SOS (2026-05-01 to 2026-05-03), the top 8 was:
- Selesnya Landfall x2
- Mono-Green Landfall x2
- Izzet Lessons x1 (Zhang #1 seed -- won by skill, not deck WR)
- Izzet Spellementals x1
- Selesnya Ouroboroid x1 (Nass)
- Azorius Tempo x1 (Faust)

Notably absent: Izzet Prowess (31% of the field, zero Top 8 finishes).

Official matchup matrix (draws excluded, from PT coverage image):

| Archetype | PT WR | Sample |
|---|---|---|
| Selesnya Landfall | 63.81% | N=105 |
| Mono-Green Landfall | 55.45% | N=514 |
| Izzet Spellementals | 50.87% | N=230 |
| Izzet Prowess | 49.80% | N=769 |
| Izzet Lessons | 49.44% | N=178 |

[Strong] These are primary-source PT numbers, not my inference. Cited
from harness/MEMORY.md PT SOS FINDINGS section.

## Strategic identity of each pillar

### Selesnya Landfall

[Inference] Beatdown with late-game inevitability. The deck wants to
land creatures, trigger landfall payoffs (Lotus Cobra, Scute Swarm),
and convert mana flood into damage via Up the Beanstalk + threat
density.

Per [[chapin-principles]]:
- Threats: high (~28-30)
- Answers: low-medium (~6-10 in main, more from SB)
- Velocity: medium (some card draw via Beanstalk)
- Mana: 2-color, clean -- no mana drag
- Clock: 6-8 turns to lethal in fair games

Per [[role-theory]]: structurally beatdown in most matchups. Shifts to
control only vs faster aggro (mono-red, mono-white) which is rare in
current Standard.

[Strong] Key matchup reads (from PT data):
- Beats Izzet Prowess 62.9%
- Beats Mono-Green Landfall 65.4%
- Loses to Izzet Lessons 25%

[Inference] The Lessons matchup is bad because Lessons can sweep the
go-wide payoffs (Pyroclasm effects) and has a delayed-clock win
condition that outlasts Landfall's mid-game pressure.

### Izzet Lessons

[Inference] Delayed-clock control. Faithless Looting + Brilliant
Restoration / Memory Deluge for value. Wins by exhausting the
opponent's threats and resolving a haymaker (Sphinx of Foresight,
late Brilliant Restoration loop).

Per Chapin:
- Threats: low (~4-6)
- Answers: high (~24-28 including sweepers)
- Velocity: very high (cantrips + draw spells dominate)
- Mana: 2-color, clean
- Clock: 12+ turns

Per role theory: control in nearly every matchup. Shifts to beatdown
only vs slower control mirrors (rare).

[Strong] Key reads:
- Beats Selesnya 75%
- Loses to Mono-Green 41.9%
- Loses to Spellementals 33.3%

[Inference] Lessons is the polarizing deck of the format. Excellent
into go-wide aggro (sweepers), terrible into linear ramp/landfall
that goes over the top. Zhang won PT with it via piloting -- the
deck WR overall is -EV.

### Mono-Green Landfall

[Inference] Linear aggro with go-wide payoffs. Plays like a hybrid
between ramp (Cultivator Colossus) and aggro (small creatures with
landfall). Less inevitability than Selesnya but lower variance.

Per Chapin:
- Threats: high (~30+)
- Answers: very low (1-3 reach spells)
- Velocity: medium (some scry)
- Mana: 1-color, perfect
- Clock: 5-7 turns

Per role theory: beatdown always.

[Strong] Key reads:
- Beats Izzet Prowess 62.7%
- Loses to Selesnya 34.6%

### Izzet Prowess

[Inference] Tempo deck. Uses cantrips for velocity, leverages cheap
spells for board pressure via prowess creatures + reach burn. Was 31%
of the field at PT but zero Top 8 -- the field adapted to it.

Per Chapin:
- Threats: medium-high (~18-22)
- Answers: medium (mostly removal, some counters in SB)
- Velocity: very high
- Mana: 2-color, clean
- Clock: 6-9 turns

Per role theory: usually beatdown G1; shifts to control G2 vs faster
aggro decks because Prowess can fall behind on board if it doesn't
also play interaction.

[Strong] PT WR 49.80% is below 50%. The deck is solved and the field
came prepared. Not the data call for May 29 unless the meta shifts.

### Izzet Spellementals

[Inference] Sleeper deck. Even matchups across the field. Beats
Prowess, beats Mono-Green, near-even vs Selesnya. The cost: lower
ceiling than Selesnya Landfall.

Per Chapin: middle-of-the-road on all 6 principles. No exploit, no
weakness.

[Strong] PT WR 50.87% with N=230. The "no bad matchup" deck.

### Other pillars

[Inference] Selesnya Ouroboroid (Nass's #2 seed deck) is a new
archetype -- hybrid combo-midrange. APL not yet written. Worth
testing.

Azorius Tempo (Faust) is similar to Izzet Prowess but with sweeper
access via Wrath effects. Edge over Selesnya, weaker vs Lessons.

## The May 29 RC deck-lock question

[Inference -- caveat heavily] The May 29 Standard RC is post-PT
meta-aware field. Expected meta share:
- Selesnya Landfall + Mono-Green Landfall combined: ~40% (most-played)
- Izzet Prowess: ~20% (declining from PT 31%)
- Izzet Spellementals: ~10% (rising)
- Izzet Lessons: ~5% (Zhang effect, but -EV so should fall)
- Other: ~25%

Per [[card-advantage]] and [[threat-answer-density]]: in a
landfall-heavy field, sweepers gain virtual CA. Decks that punish
sweepers (Mono-White flicker, recurring threats) gain edge.

[Strong] Best-deck-by-raw-WR call: Selesnya Landfall.
[Inference] Best-deck-by-field-mix call: depends on how much Lessons
remains. If Lessons dies off, Selesnya is the call. If Lessons holds
~5%, Spellementals' even matchups make it the safer floor.

## Codebase pointer

- `mtg-meta-analyzer/mtg_meta.db` -- archetype data, matches table
- `harness/MEMORY.md` PT SOS FINDINGS section -- the primary-source
  matrix
- `harness/knowledge/mtg/sim-*.md` -- per-archetype tactical sim notes
  (separate from this strategic block)

See also: [[chapin-principles]] for the principle-grade applied to
each archetype above. [[role-theory]] for matchup-by-matchup role
assignment.

## Decay tracking

This block expires. Triggers to rewrite:
- 30+ days since `format_snapshot:` date
- New set legalization
- A pillar archetype falls below 5% meta share or a new one rises
  above 5%
- Banning announcement affecting any pillar listed above

If 2+ triggers fire, the rewrite is overdue.
```

- [ ] **Step 7.3: Cross-check format claims against MEMORY.md**

Open `harness/MEMORY.md` and re-read the "PT SOS FINDINGS (2026-05-03)"
section. Confirm every number in the format block matches. If
anything contradicts, fix the block.

- [ ] **Step 7.4: Validate against spec gates**

- Gate 1.5: `format_snapshot: 2026-05-12` in frontmatter ✓ (verify)
- Tags applied throughout ✓
- Word count: 1200-1800 ✓ (verify with `wc -w`)
- All PT matchup numbers match MEMORY.md ✓ (verified in 7.3)

- [ ] **Step 7.5: Commit**

```bash
cd "E:/vscode ai project/harness"
git add knowledge/mtg/strategy/format-standard-spring-2026.md
git commit -m "feat(mtg-strategy): add format-standard-spring-2026 block (slice A, 6/6)"
```

---

## Task 8: Update `_index.md` + final commit

**Files:**
- Modify: `harness/knowledge/_index.md`

- [ ] **Step 8.1: Read the current index**

```bash
cd "E:/vscode ai project/harness"
cat knowledge/_index.md
```

Find a logical place to insert the new section -- probably after the
existing `## MTG` entries (operational artifacts) and before other
domains. If the structure is unclear, append at the end.

- [ ] **Step 8.2: Add the new section**

Add this block to `harness/knowledge/_index.md`:

```markdown
## MTG Strategy

- [Overview](mtg/strategy/_overview.md) -- index of strategic-theory blocks
- [Chapin's 6 Principles](mtg/strategy/chapin-principles.md) -- threats/answers/consistency/velocity/mana/clock framework
- [Role theory](mtg/strategy/role-theory.md) -- Flores' beatdown/control as relational roles
- [Card advantage taxonomy](mtg/strategy/card-advantage.md) -- raw, virtual, tempo, quality, exchange ratios
- [Threat/answer density](mtg/strategy/threat-answer-density.md) -- density math, sweepers, the 60-card budget
- [Format -- Standard Spring 2026](mtg/strategy/format-standard-spring-2026.md) -- pillar archetypes' strategic identity (snapshot 2026-05-12)
```

- [ ] **Step 8.3: Validate auto-load**

Re-read `harness/CLAUDE.md` MANDATORY KNOWLEDGE LOADING section. Confirm
the MTG rule recurses into `mtg/strategy/`. If you weren't 100% sure
in Step 1.2, this is the second check.

If the rule doesn't recurse, **STOP**. Surface to user. Decide between
(a) explicit subdir load rule, (b) flattening blocks. Apply the chosen
fix, then continue.

- [ ] **Step 8.4: Run the full per-block self-checklist one more time**

For each of the 6 blocks, run:

```bash
cd "E:/vscode ai project/harness"
for f in knowledge/mtg/strategy/*.md; do
  echo "=== $f ==="
  echo "word count: $(wc -w < "$f")"
  echo "has [Strong]: $(grep -c '\[Strong\]' "$f")"
  echo "has [Inference]: $(grep -c '\[Inference\]' "$f")"
  echo "has codebase pointer: $(grep -c 'mtg-meta-analyzer/analysis' "$f")"
  echo "has description in frontmatter: $(grep -c '^description:' "$f")"
done
```

Expected for each block:
- word count within target bounds (per Task table)
- at least one `[Strong]` and one `[Inference]`
- at least one codebase pointer (except `_overview.md` which is meta)
- exactly one `description:` line

If any block fails, return to its task and fix.

- [ ] **Step 8.5: Final commit**

```bash
cd "E:/vscode ai project/harness"
git add knowledge/_index.md
git commit -m "$(cat <<'EOF'
feat(mtg-strategy): index strategy blocks + close slice A

Adds the ## MTG Strategy section to harness/knowledge/_index.md.

Slice A complete: 6 knowledge blocks under
harness/knowledge/mtg/strategy/ now auto-loaded before MTG strategic
questions per harness/CLAUDE.md MANDATORY KNOWLEDGE LOADING rule.

Per spec 2026-05-12-mtg-strategy-knowledge-base-slice-a.md, plan
plan-2026-05-12-mtg-strategy-slice-a.md.
EOF
)"
git push
```

- [ ] **Step 8.6: Update the spec changelog**

Open `harness/specs/2026-05-12-mtg-strategy-knowledge-base-slice-a.md`
and add to the Changelog section:

```
- 2026-05-12: Status -> SHIPPED at commit <hash from step 8.5>
```

Commit:

```bash
cd "E:/vscode ai project/harness"
git add specs/2026-05-12-mtg-strategy-knowledge-base-slice-a.md
git commit -m "chore: mark mtg-strategy slice A spec SHIPPED"
git push
```

- [ ] **Step 8.7: Move imperfections to IMPERFECTIONS.md**

Per the spec's "Annotated imperfections" section, move the two
documented imperfections (`strategy-blocks-not-codebase-grounded` and
`format-meta-block-decays`) from the spec into
`harness/IMPERFECTIONS.md` as tracked items.

Commit:

```bash
cd "E:/vscode ai project/harness"
git add IMPERFECTIONS.md
git commit -m "chore: track mtg-strategy slice A imperfections"
git push
```

---

## Self-review (executor: skip; this is the plan author's check)

**Spec coverage check:**
- Section "In scope" item 1 (new subdir) → Task 1.1 ✓
- Section "In scope" item 2 (6 blocks) → Tasks 2-7 ✓
- Section "In scope" item 3 (_index.md update) → Task 8 ✓
- Section "In scope" item 4 (per-block self-checklist) → Step 8.4 ✓
- All 9 validation gates → covered across Tasks 1-8 ✓
- All 4 stop conditions → embedded in steps ✓

**Placeholder scan:**
- One bracketed placeholder in Task 3.2: `[cite the actual threshold from the code -- e.g. "creatures + planeswalkers + win condition spells; full marks at 18+ slots"]`. This is deliberate -- the executor reads chapin.py in Task 1 and fills in the real threshold in Step 3.3. Acceptable per the spec's pre-flight read protocol.
- All other tasks have complete content.

**Type consistency:** N/A (Markdown docs, no types).

**Block independence:** Each block can be written without the others. Cross-references via `[[name]]` are explicit but not blocking -- a block can ship before another it links to.

---

**Plan complete and saved to** `harness/plan-2026-05-12-mtg-strategy-slice-a.md`.

Two execution options:

**1. Subagent-Driven (recommended)** -- Dispatch a fresh subagent per block (Tasks 2-7), review between tasks. Each subagent gets the spec, the pre-flight reads, and one task. Pros: clean context per block, parallelizable if you want. Cons: each subagent re-derives the framework from scratch, voice may drift block-to-block.

**2. Inline Execution** -- Execute tasks in this session using `superpowers:executing-plans`. Pros: consistent voice across blocks, framework stays loaded. Cons: long single session, harder to checkpoint.

For prose-heavy work where voice consistency matters across the 6 blocks, **Inline Execution is the better fit here** despite the skill's default recommendation. The blocks cross-reference each other; one author writing all 6 will produce a more coherent series than 6 subagents each writing one.

Which approach?
