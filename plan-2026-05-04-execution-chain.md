# Execution chain: 2026-05-04 (Monday -- Post-PT re-analysis day 1)

**Created:** 2026-05-03 end-of-day by Claude Code
**Target executor:** fresh Claude Code session
**Estimated wall time:** 6-8 hours active work
**Source:** Post-PT SOS analysis + RC DC prep + pending backlog

## Context

PT Secrets of Strixhaven is complete (or finalizing). Key findings:
- Selesnya Landfall: 63.81% overall WR -- clear best deck
- Mono-Green Landfall: 55.45%
- Izzet Lessons: 49.44% -- Zhang won it but deck is slightly negative vs the field
- Izzet Prowess: 49.80% at 31% of field -- zero Top 8 finishers
- Selesnya beats Mono-Green 65.4%, loses to Izzet Lessons 25%

CORRECTION (2026-05-03): Both upcoming RCs are Standard format:
- **May 11-12 Standard RC** -- 8 days away, URGENT deck decision
- **May 29 Standard RC DC** -- 26 days away
Modern Boros Energy sim work was for teammates/RCQs, not Jermey's RCs.

Yesterday shipped:
- PT SOS Top 8 + official matchup matrix in data/pt_sos_2026.json
- Standard field updated to 481-player PT SOS final shares
- Izzet Lessons deck updated to Zhang's PT #1-seed list
- Dimir Excruciator deck file + stub APL
- GitHub Actions Node 24 update (both repos)
- Variant BE 100k clean confirmation: 75.1%

## Read me first (SESSION START PROTOCOL)

1. Read harness/state/latest-snapshot.md
2. Read harness/inbox/drift-pr--2026-05-04.md if present
3. Read harness/MEMORY.md
4. Check harness/IMPERFECTIONS.md
5. Read this file

## Pre-session checks

- Check PT Top 8 results: did they publish overnight?
  Search: "Pro Tour Secrets of Strixhaven winner champion" -- should be live by now
  Write winner + placement to data/pt_sos_2026.json['top8_winner']
  Commit: "data: PT SOS champion + Top 8 placements"

## Specs in scope today

| # | Item | Type | Effort | Priority |
|---|---|---|---|---|
| 1 | **PT Top 8 results + champion** | data | ~15 min | HIGH |
| 2 | **Selesnya Landfall match APL** | APL | ~3h | HIGH |
| 3 | **RC Standard deck decision analysis** | research | ~45 min | HIGH |
| 4 | **Selesnya Ouroboroid APL + deck** | APL | ~2h | MED |
| 5 | Azorius Blink deck stub | data | ~30 min | MED |
| 6 | Standard gauntlet with Selesnya match APL | gauntlet | ~30 min wall | MED |

---

## Section 0 -- Session start + PT results check (~15 min)

Read snapshot + inbox + memory per protocol.

Check PT Top 8 results:
- `https://magic.gg/events/pro-tour-secrets-of-strixhaven` -- look for champion article link
- `https://magic.gg/news/pro-tour-secrets-of-strixhaven-champion` (likely URL)
- If live: fetch Top 8 bracket (QF/SF/Final), record winner + placements

Write to pt_sos_2026.json and commit.

**[STOP -- surface champion + placements]**

---

## Section 1 -- Selesnya Landfall match APL (~3h)

The most impactful Standard sim improvement. Selesnya is the best deck (63.81% PT WR)
and its matchups are entirely creature-based -- no stack priority needed to model.

### Pre-flight reads
- `apl/selesnya_landfall_standard.py` -- current goldfish APL (understand current structure)
- `apl/boros_energy.py` -- template for a working aggro match APL
- `decks/selesnya_landfall_standard.txt` -- current Larsen/Steuer PT list
- `harness/knowledge/tech/spec-authoring-lessons.md` -- methodology

### Key mechanics to model in match APL

From Larsen/Steuer list (Top 8):
- **Earthbender Ascension** (4x): landfall saga -- gets counters, attacks for big damage
- **Mightform Harmonizer** (3x): landfall pump -- triggers on each land ETB
- **Sazh's Chocobo** (4x): 2/2 for 1G with relevant ability
- **Badgermole Cub** (4x): landfall 2/2 that grows
- **Llanowar Elves** (4x): T1 accelerant
- **Fabled Passage** (4x) + Escape Tunnel (3x) + Ba Sing Se (3x): fetches that trigger landfall twice
- **Erode** (4x): removal spell -- bounce/destroy

### Match APL structure

Extend an aggro base (similar to BorosEnergyMatchAPL structure):
1. `keep()`: T1 Llanowar Elves or 2 lands + 2-drop
2. `main_phase()`: deploy Llanowar Elves T1, then accelerate into 3-drop threats
3. Attack with full board each combat
4. `main_phase2()`: play fetches/cycling lands post-combat to trigger extra landfall
5. Erode opponent's best creature (oracle: bounce or destroy) before attacking

Validation gate: gauntlet vs Izzet Prowess should show ~60-65% WR (matching PT 62.9%)

**[STOP -- surface Selesnya gauntlet results]**

---

## Section 2 -- RC STANDARD DECK DECISION (URGENT -- May 11-12 is 8 days away)

This is the highest-priority item. May 11-12 Standard RC lock needed now.

Decision framework (from rc-prep-may29-candidates.md: "pick the deck the data likes"):

PT SOS official matrix:
  Selesnya Landfall:   63.81% -- best deck, only loses to Lessons (25%)
  Mono-Green Landfall: 55.45% -- beats Prowess, loses to Selesnya
  Izzet Spellementals: 50.87% -- beats Prowess + Mono-Green, even vs Selesnya
  Izzet Lessons:       49.44% -- 75% vs Selesnya but -WR vs Mono-Green + Spells

Default call: **Selesnya Landfall**
  - Best data WR by 8+ points
  - Creature-based aggro -- simplest to pick up under 8-day time pressure
  - Strategic identity (meta-analyst/strategist): pick by data, not reps

Counter-argument for Izzet Lessons: if the field is full of Selesnya (anti-Prowess metagame)
  Lessons beats Selesnya 75% but the numbers have to work out. With only 5% Lessons at PT
  and all those players now aware of Selesnya being the best deck...

Action:
1. Get PT winner + Top 8 placements (signals which deck won the finals)
2. Lock deck for May 11-12 RC
3. Pull the appropriate deck from the DB (Larsen's Selesnya list is already in sim)
4. Write sideboard plan: harness/knowledge/mtg/rc-may11-12-deck-plan.md
5. Order physical cards if needed (flag any cards you don't have)

**[STOP -- confirm May 11-12 RC deck locked]**

---

## Section 3 -- Selesnya Ouroboroid APL (~2h)

Matt Nass's #2-seed deck. New archetype not in sim. Key cards (from Top 8 article):
- Ouroboroid (4x): the namesake engine
- Llanowar Elves (4x): T1 accelerant  
- Badgermole Cub (4x): aggressive 2-drop
- Sazh's Chocobo (4x): 2/2 value
- Bright glass Gearhulk (3x): artifact-creature finisher
- Gene Pollinator (3x): landfall value
- Keen-Eyed Curator (4x): loot/draw
- Seam Rip / Erode: removal

Deck file: build from Nass's Top 8 decklist (already have it from magic.gg).
APL: similar to Selesnya Landfall but with Ouroboroid combo engine as finisher.

Register: "selesnyaouroboroid", "ouroboroid" in APL_REGISTRY.

---

## Section 4 -- Azorius Blink deck stub (~30 min)

2.5% of Standard field, causing ERROR in gauntlet. Pull from PT SOS DB or MTGDecks.

```python
# In meta-analyzer DB
c.execute("SELECT d.player, d.id FROM decks d JOIN events e ON d.event_id=e.id
           WHERE e.id IN (11739,11881) AND d.archetype LIKE '%Blink%' LIMIT 3")
```

Build deck file, register GenericAPL stub. Fixes the remaining ERROR in Standard gauntlet.

---

## Section 5 -- Standard gauntlet with new APLs (~30 min wall, optional)

Once Selesnya match APL + Ouroboroid stub are registered:

```bash
cd "E:\vscode ai project\mtg-sim"
python parallel_launcher.py --deck "Selesnya Landfall" --format standard --n 1000 --seed 42
python parallel_launcher.py --deck "Mono Green Landfall" --format standard --n 1000 --seed 42
```

Key matchup to validate: Selesnya vs Mono-Green (PT: 65.4%). If sim shows ~60-70%, APL quality confirmed.

---

## Stop conditions

- PT Top 8 results not published by session start: proceed anyway, check again mid-session
- Selesnya match APL gauntlet shows Selesnya vs Prowess <50% or >85%: APL quality issue, investigate
- Any engine crash from new deck/APL: debug before proceeding

---

## Deferred (explicitly out of scope today)

- Phase 3.5 Stages D-K -- no pressure
- Pioneer L1 backlog -- no event pressure
- Skill system harness -- start 2026-05-05
- Gruul/Temur Ouroboroid post-PT build (Modern) -- post-RC
- Node.js 24 follow-up -- done

---

## End-of-day checklist

- [ ] Author plan-2026-05-05-execution-chain.md before closing
- [ ] Update MEMORY.md with session log
- [ ] PT champion documented in pt_sos_2026.json
- [ ] Selesnya Landfall match APL committed + gauntlet run
- [ ] RC Standard deck analysis memo written
- [ ] IMPERFECTIONS.md updated if any new gaps found

---

## Changelog

- 2026-05-03 night: Created. Post-PT re-analysis window opens. Primary focus:
  Selesnya Landfall match APL + RC Standard deck decision analysis.
  PT official matrix is authoritative Standard WR source.
  Modern RC DC: Boros Energy locked (68.4% canonical / 75.1% variant).
