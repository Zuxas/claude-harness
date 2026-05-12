---
name: format-standard-spring-2026
description: Strategic identity of pillar archetypes in Standard Spring 2026 (post PT Secrets of Strixhaven). Use when reasoning about a current Standard matchup or deck choice. Decays -- rewrite when meta shifts.
metadata:
  type: knowledge
  domain: mtg
  slice: strategy
  format_snapshot: 2026-05-12
  sources:
    - "PT Secrets of Strixhaven results (mtg-meta-analyzer/data/pt_sos_2026.json)"
    - "harness/MEMORY.md PT SOS FINDINGS section (2026-05-03)"
    - "mtg_meta.db archetype data as of 2026-05-12"
---

# Standard Spring 2026 -- Pillar Archetypes

**Format snapshot: 2026-05-12** (post PT Secrets of Strixhaven 2026-05-01
to 2026-05-03, pre May 29 RC).

[Strong] This block decays. The pillar list and matchup reads are
valid as of 2026-05-12; meta shifts after new sets release or
banning announcements. When PT data is older than 30 days or a new
set legalizes, rewrite the block.

## PT Secrets of Strixhaven results (primary source)

[Strong] Top 8 from PT SOS (cited from `harness/MEMORY.md` PT SOS
FINDINGS section, 2026-05-03):

- Selesnya Landfall x2
- Mono-Green Landfall x2
- Izzet Lessons x1 (Zhang -- #1 seed, won the event)
- Izzet Spellementals x1
- Selesnya Ouroboroid x1 (Nass -- #2 seed)
- Azorius Tempo x1 (Faust)

Notably absent: Izzet Prowess (31% of the field; zero Top 8 finishes).

[Strong] Official matchup matrix (draws excluded, sourced from PT
coverage):

| Archetype | PT WR | Sample size |
|---|---|---|
| Selesnya Landfall | 63.81% | N=105 |
| Mono-Green Landfall | 55.45% | N=514 |
| Izzet Spellementals | 50.87% | N=230 |
| Izzet Prowess | 49.80% | N=769 |
| Izzet Lessons | 49.44% | N=178 |

[Strong] Key matchup reads from the same source:
- Selesnya Landfall beats Izzet Prowess 62.9%
- Selesnya Landfall beats Mono-Green Landfall 65.4%
- Selesnya Landfall **loses** to Izzet Lessons 25%
- Izzet Lessons beats Selesnya 75% but loses to Mono-Green 41.9%
  and Spellementals 33.3%
- Mono-Green Landfall beats Izzet Prowess 62.7%, loses to Selesnya 34.6%

## Strategic identity per pillar

### Selesnya Landfall

[Inference] **Beatdown with late-game inevitability.** The deck wants
to land creatures, trigger landfall payoffs (Lotus Cobra, Scute Swarm
in current lists), and convert mana flood into damage via Up the
Beanstalk plus threat density. Unlike pure aggro, Selesnya Landfall
doesn't run out of gas -- every land drop generates value.

[Inference] Per [[chapin-principles]] (estimated):
- Threats: high (~28-30)
- Answers: low-medium (~6-10 main, more from SB)
- Velocity: medium (Up the Beanstalk + scry effects)
- Mana: 2-color, clean -- no significant drag
- Clock: 6-8 turns to lethal in fair games

[Inference] Per [[role-theory]]: structurally beatdown in most
matchups. Shifts to control only vs faster aggro (mono-red, mono-white
linear), which is rare in current Standard.

[Strong] PT data: 63.81% WR (N=105). The objectively best raw-WR deck
of PT SOS.

[Inference] The Lessons matchup (lose 25%) is bad because Lessons can
sweep the go-wide payoffs (Pyroclasm + Anger of the Gods effects) and
has a delayed-clock win condition that outlasts Landfall's mid-game
pressure. Anti-Lessons SB cards (counter-magic, discard) help but
don't flip the matchup.

### Mono-Green Landfall

[Inference] **Linear aggro with go-wide payoffs.** Plays like a hybrid
between ramp (Cultivator Colossus in some builds) and aggro (small
creatures with landfall triggers). Less inevitability than Selesnya
Landfall but lower variance: the deck always knows what it's doing.

[Inference] Per Chapin (estimated):
- Threats: high (~30+)
- Answers: very low (1-3 reach spells)
- Velocity: medium (some scry)
- Mana: 1-color, perfect
- Clock: 5-7 turns

[Inference] Per role theory: beatdown in nearly every matchup. No
role-switching to speak of.

[Strong] PT data: 55.45% WR (N=514, large sample). The second-best
raw-WR deck.

[Inference] Mono-Green Landfall is the "safe choice" for May 29 -- it
has the largest sample at PT, a positive WR, and clean play patterns.
It loses to Selesnya (34.6%) but beats Prowess (62.7%), which is the
correct shape vs the expected field.

### Izzet Lessons

[Inference] **Delayed-clock control.** Faithless Looting + Brilliant
Restoration / Memory Deluge for value. Wins by exhausting the
opponent's threats and resolving a haymaker (Sphinx of Foresight in
some builds, late Brilliant Restoration loop in others).

[Inference] Per Chapin (estimated):
- Threats: low (~4-6)
- Answers: high (~24-28 including sweepers)
- Velocity: very high (cantrips + draw spells dominate)
- Mana: 2-color, clean
- Clock: 12+ turns

[Inference] Per role theory: control in nearly every matchup. Shifts
to beatdown only vs slower control mirrors (rare).

[Strong] PT data: 49.44% WR (N=178). Below 50% **overall** despite
crushing Selesnya 75%. The polarizing deck of the format -- great
into go-wide aggro, terrible into linear ramp/landfall that goes over
the top.

[Inference] Zhang won PT with Lessons via piloting, not deck WR. The
deck rewards a player who reads matchups well; it punishes
auto-pilot. For May 29, this is the deck-pick risk: if Lessons drops
off the meta after PT (likely, since people will adapt), the matchup
math shifts.

### Izzet Prowess

[Inference] **Tempo deck.** Uses cantrips for velocity, leverages
cheap spells for board pressure via prowess creatures + reach burn.
Was 31% of the field at PT (most-played) but zero Top 8 -- the field
adapted to it.

[Inference] Per Chapin (estimated):
- Threats: medium-high (~18-22)
- Answers: medium (mostly removal, some counters in SB)
- Velocity: very high
- Mana: 2-color, clean
- Clock: 6-9 turns

[Inference] Per role theory: usually beatdown G1; shifts to control
G2 vs faster aggro decks because Prowess can fall behind on board if
it doesn't also play interaction.

[Strong] PT data: 49.80% WR (N=769, largest sample). The deck is
solved and the field came prepared. The 31% field share crashed it --
everyone teched into Prowess hate.

[Inference] Not the data call for May 29 unless the meta shifts and
Prowess hate goes away. With Prowess at expected lower meta share
post-PT, the hate cards leave, and the deck could recover. But betting
on that requires meta-prediction beyond what the data supports.

### Izzet Spellementals

[Inference] **Sleeper deck.** Even matchups across the field. Beats
Prowess, beats Mono-Green, near-even vs Selesnya. The cost: lower
ceiling than Selesnya Landfall, no crushing matchup.

[Inference] Per Chapin (estimated): middle-of-the-road on all 6
principles. No exploit, no weakness.

[Strong] PT data: 50.87% WR (N=230). The "no bad matchup" deck.

[Inference] Spellementals is the "field-balanced" choice. If the May
29 meta is unpredictable -- Lessons holding 5%, Prowess unclear, mix
of Landfall variants -- Spellementals is the safest floor. Its
ceiling is lower than Selesnya Landfall's but its floor is higher.

### Selesnya Ouroboroid (Nass's #2 seed deck)

[Inference] **Hybrid combo-midrange.** New archetype as of PT SOS;
APL not yet authored in `mtg-sim/`. Worth testing but understudied.

[Strong] Made #2 seed at PT, Top 8 finish. Sample size 1, so the WR
data is unreliable for forecasting.

[Inference] Skip for May 29 RC unless you have time to gauntlet-test
extensively pre-event. Unknown archetypes punish piloting errors.

### Azorius Tempo (Faust's Top 8 list)

[Inference] Similar to Izzet Prowess but with sweeper access via
Wrath effects. Edge over Selesnya, weaker vs Lessons (Lessons
out-grinds it).

[Inference] One Top 8 at PT is a sample of 1 -- can't generalize.
Worth following if it gains traction in May 11-12 RC results.

## The May 29 RC deck-lock question

[Inference -- caveat heavily, this is my read on a meta-aware field]

Expected May 29 meta share (synthesis, NOT data-grounded):

| Archetype | Expected share |
|---|---|
| Selesnya Landfall + Mono-Green Landfall (combined) | ~40% |
| Izzet Prowess | ~20% (declining from PT 31%) |
| Izzet Spellementals | ~10% (rising post-PT exposure) |
| Izzet Lessons | ~5% (Zhang effect, but -EV so should fall) |
| Other (incl. Selesnya Ouroboroid, Azorius Tempo) | ~25% |

[Inference] In a landfall-heavy field, sweepers gain virtual CA (see
[[card-advantage]]). Decks that punish sweepers -- recursive threats,
planeswalkers, manlands -- gain edge.

[Strong] Per the PT data:
- **Best-deck-by-raw-WR call**: Selesnya Landfall (63.81%).
- **Best-deck-by-large-sample call**: Mono-Green Landfall (55.45% N=514).

[Inference]:
- **Best-deck-by-field-mix call**: depends on Lessons. If Lessons
  remains ~5%, Selesnya's 25% WR vs Lessons matters; Spellementals'
  even matchups make it the safer floor. If Lessons collapses below
  3%, Selesnya is the call.
- **Best-deck-by-skill-leverage call**: Lessons (Zhang's pick). Highest
  ceiling for a skilled pilot; lowest floor for an auto-pilot pilot.

[Strong] My recommendation requires understanding what role you want
to play. Per [[role-theory]] -- beatdown role (Selesnya / Mono-Green
Landfall) is the lower-variance play; control role (Lessons) is the
higher-skill play. There is no single right answer in the data;
there's a right answer given your goals.

## Codebase pointer

- `mtg-meta-analyzer/data/pt_sos_2026.json` -- raw PT data
- `mtg-meta-analyzer/mtg_meta.db` -- post-PT archetype data, matchup matrix
- `harness/MEMORY.md` PT SOS FINDINGS section -- the primary-source matrix
- `harness/knowledge/mtg/sim-*.md` -- per-archetype tactical sim notes
  (these are tactical not strategic; separate from this block)

See also: [[chapin-principles]] for the principle-grade applied to
each archetype above. [[role-theory]] for matchup-by-matchup role
assignment. [[threat-answer-density]] for the density math that
explains why Lessons crushes Selesnya but loses to Mono-Green.

## 2026-05-12 mid-snapshot correction

[Strong] After this block was first written (commit 1af8ab7), a live
query of `mtg-meta-analyzer/mtg_meta.db` for the last 14 days
(N=1262 Standard decks) produced meta shares that contradict the
"Expected May 29 meta share" predictions earlier in this block.

**Corrections** (data source: `mtg_meta.db` decks table joined to
events, format=standard, last 14 days as of 2026-05-12):

| Archetype | Earlier prediction | Actual 14d share | Correction |
|---|---|---|---|
| Izzet Prowess | ~20% (declining) | **23.5%** | Slightly declined from PT 31% but still #1 by large margin. Field has NOT abandoned Prowess. |
| Mono-Green Landfall | (combined ~40% with Selesnya) | **11.6%** | Single largest non-Prowess deck. The volume Landfall pick. |
| Izzet Spellementals | ~10% rising | **6.9%** | Flat, not rising. |
| Selesnya Landfall | (combined ~40% with Mono-G) | **4.3%** | Much smaller share than predicted. Despite top PT WR, the field hasn't adopted it broadly. |
| Selesnya Aggro | NOT PREDICTED | **5.2%** | New pillar. Triggers the "new archetype above 5%" decay condition. Strategic identity TBD pending more data. |
| Izzet Lessons | ~5% | 3.8-5.6% | Within prediction range (variance depends on Lessons / "Izzet Lesson" normalization). |

[Inference] The earlier "May 29 RC deck-lock question" section uses
the now-superseded meta shares. The corrected calculation:

[Inference] Field-weighted WR with corrected shares (assumes PT
matchup numbers still hold, which is itself an assumption):

For **Selesnya Landfall** (PT WR 63.81%):
- vs Prowess (23.5%): 62.9% × 0.235 = 14.8 pts
- vs Mono-G (11.6%): 65.4% × 0.116 = 7.6
- vs Spellementals (6.9%): ~50% × 0.069 = 3.5
- vs Selesnya Aggro (5.2%): UNKNOWN — assume 50% × 0.052 = 2.6
- vs Selesnya mirror (4.3%): 50% × 0.043 = 2.2
- vs Lessons (5.6%): 25% × 0.056 = 1.4
- vs rest (43%): assume ~52% × 0.43 = 22.4
- **Total: ~54.5%** [Inference, heavy dependence on "rest" bucket]

For **Mono-Green Landfall**:
- vs Prowess (23.5%): 62.7% × 0.235 = 14.7
- vs Selesnya (4.3%): 34.6% × 0.043 = 1.5
- vs Spellementals (6.9%): ~50% × 0.069 = 3.5
- vs Selesnya Aggro (5.2%): UNKNOWN — assume 50% × 0.052 = 2.6
- vs mirror (11.6%): 50% × 0.116 = 5.8
- vs Lessons (5.6%): 41.9% × 0.056 = 2.3
- vs rest (43%): assume ~50% × 0.43 = 21.5
- **Total: ~51.9%** [Inference]

[Strong] Both Landfall variants still favored vs the Prowess-heavy
field. The Selesnya/Mono-Green gap narrows from the earlier
calculation but Selesnya remains the higher-WR pick on paper, and
Mono-Green remains the larger-sample lower-variance pick.

[Uncertain] Selesnya Aggro at 5.2% is the largest data gap. No PT
matchup data. Likely a fast WG creature deck with Landfall-style
payoffs but more aggressive curve. If it has a Selesnya-Landfall-style
favorable matchup vs Prowess, it could be the actual best pick;
unknown.

[Strong] The "Pillar archetype rises above 5%" decay condition has
fired (Selesnya Aggro at 5.2%). Per this block's own rules, a Slice
A-prime / format-block-rewrite is overdue. Tracked as imperfection
`mtg-strategy-format-meta-block-decays` -- consider it primed for the
next session.

## Decay tracking

This block expires. Rewrite triggers:

- 30+ days since `format_snapshot` date (next rewrite: ~2026-06-11)
- New set legalization
- A pillar archetype falls below 5% meta share or a new one rises
  above 5%
- Banning announcement affecting any pillar listed above
- May 11-12 RC and May 29 RC results materially change matchup reads

If 2+ triggers fire, the rewrite is overdue.
