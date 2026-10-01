---
title: "Engine v2 milestone four, step 1: asymmetric matchup survey + recommendation"
status: "EXECUTING"
created: "2026-10-01"
updated: "2026-10-01"
project: "mtg-sim"
estimated_time: "survey done; implementation sized below"
related_findings:
  - "harness/specs/2026-10-01-v2-m3-gameplay-launcher.md"
  - "mtg-sim data/v2_matchup_survey.json (scripts/v2_matchup_survey.py)"
related_commits:
  - "mtg-sim 0e79a4e (survey script and output; no engine code)"
supersedes: null
superseded_by: null
---

# Milestone four, step 1: which asymmetric matchup next (survey only, no engine code)

## Method
`scripts/v2_matchup_survey.py` classifies every non-basic main-deck card of the 137 parseable 60-card repo lists
(Modern / Pioneer / Standard) from its oracle text into: already supported / definition-only (existing v2
machinery: basic, shock, fast, fetch, pain lands; vanilla creatures with supported keywords; plain damage,
draw, pump, counter spells) / small new primitive / genuinely new subsystem, and ranks all 3,990 same-format
pairs (mirrors excluded) with heavy penalties for graveyard casting, discard, tokens, planeswalkers, layers,
copy and transform. The regex classification is a heuristic (it double-counts keyword tags and leaves some
cards "unclassified"), so the leading candidates were then read card by card.

## Findings
- No real asymmetric pairing avoids new subsystems; every candidate needs several.
- Because Burn (`mono_red_aggro_modern`) is already fully supported, Burn vs another Modern list is far cheaper
  than any pairing of two new decks (every non-Burn pair needs both decks' subsystems).
- The heuristic's raw top Modern opponents were the Breach combo decks -- rejected: they depend on graveyard
  casting, copy (Splice / storm-like) and tokens, all disfavoured.

Manual read of the leading non-combo Modern opponents (cards outside v2 today):

| Opponent | Unsupported cards | New subsystems (manual) | Disfavoured touched | Verdict |
|---|---|---|---|---|
| **Izzet Prowess** (`decks/auto/izzet_prowess_modern.txt`, RCQ 4th 2026-05-09) | 14 of 20 unique (6 already supported: Arid Mesa, Bloodstained Mire, Fiery Islet, Lightning Bolt, Monastery Swiftspear, Mountain) | ~7 | tokens (Cutter's Monk), graveyard casting (Lava Dart flashback), graveyard-reading static (delirium) | **recommended** |
| Izzet Prowess (`decks/izzet_prowess_modern.txt`, Challenge list) | same + Founding the Third Path, Stomping Ground | ~8 (adds a Saga with read ahead + free casting) | as above + Saga | second choice |
| Domain Zoo | 19 | ~11 (domain counting, cost reduction, characteristic-defining P/T, Leyline of the Guildpact type-changing layers, Treasure tokens, dash, flash, "exile until it leaves", trigger suppression, discard, cycling, counter-unless-pay) | layers, tokens, discard, graveyard | rejected |
| Death and Taxes | 17 | ~13 (protection, cost-increase static, flash, evoke, lifelink, blink + delayed return, monarch, Aether Vial counters, search restriction, equipment with counters, manland, channel, land destruction) | tokens, layers | rejected |
| Breach / Ruby Storm / Belcher | 16-17 | combo engines | graveyard casting, copy, tokens, discard | rejected |

## Recommendation: Burn (`mono_red_aggro_modern`) vs Izzet Prowess (`decks/auto/izzet_prowess_modern.txt`)
A real, common Modern matchup; asymmetric (burn-aggro vs prowess-tempo); the opponent shares six supported cards
with Burn and is mostly lands, 1-2 mana creatures and cheap spells. Exact work, by card:

Definition only (existing machinery): Scalding Tarn and Wooded Foothills (fetch lands), and Steam Vents (shock
land). Wooded Foothills can fetch either Mountain or Steam Vents because both have the Mountain land type. As
with every search of a hidden zone for cards with a stated quality, its controller may legally fail to find even
when a legal card is present; the absence of a Forest in this list is not what permits that choice.

Small primitives inside existing subsystems:
- Generic Phyrexian-mana payment `{G/P}` (choose {G} or 2 life) -- Mutagenic Growth. This exact list has no
  green-producing source and will therefore use the life option in games, but the primitive must implement both
  legal payments rather than hard-code a deck-specific shortcut.
- Trample (combat damage assignment past blockers) -- from Cori-Steel Cutter.
- "gains first strike until end of turn" turn effect -- Violent Urge (double strike already exists).
- "this creature gets +2/+0 until end of turn" on noncreature casts -- Slickshot Show-Off (existing trigger + eot_mod).
- Unconditional enters-tapped land behavior -- Thundering Falls. Its separate enters-the-battlefield surveil
  trigger belongs to slice 1 below.

New subsystems (each its own slice, tests first):
1. Private library-top decisions: scry N, surveil N, and look-at-top-3-and-distribute -- Preordain, Serum Visions,
   Dragon's Rage Channeler, Thundering Falls, and Expressive Iteration. Thundering Falls must trigger surveil 1
   after it enters tapped; it is not merely an enters-tapped dual land.
2. Graveyard-reading static ability: delirium counts distinct card types among cards in the controller's
   graveyard, with a single multi-type card contributing each of its types. Dragon's Rage Channeler gets +2/+2,
   gains flying, and attacks each combat if able while delirium is true. Violent Urge always gives its target
   +1/+0 and first strike until end of turn, and also grants double strike until end of turn when its controller
   has delirium. Scope this as minimal static and conditional-effect evaluation, not a general layer engine.
3. Equipment, creature tokens, and per-turn spell counting -- Cori-Steel Cutter. Equip `{1}{R}` follows normal
   equip timing and targets a creature its controller controls; attaching it moves it off any previous creature.
   The equipped creature gets +1/+1, trample, and haste. Flurry triggers on its controller's second spell each
   turn, creates a 1/1 white Monk creature token with prowess, then offers the optional attach to that token.
4. Temporary play permission from exile -- Expressive Iteration. "Play" permits either casting the card or
   playing it as a land, as appropriate; normal timing and the once-per-turn land-play limit still apply, and the
   permission expires at end of turn.
5. Flashback with a non-mana alternative cost ("Sacrifice a Mountain") -- Lava Dart. The card is cast from the
   graveyard, and the flashback replacement sends it to exile if it would leave the stack for any zone.
6. Delayed triggered ability ("at the beginning of the next turn's upkeep") plus an activated ability targeting
   a player and privately looking at that library's top card -- Mishra's Bauble. The delayed draw trigger must
   survive the Bauble being sacrificed as part of the activation cost.
7. Plot -- Slickshot Show-Off. Plot is a sorcery-speed special action that exiles the card from hand for its plot
   cost, then permits its controller to cast it as a sorcery on a later turn without paying its mana cost. Reuse
   the casting transaction and cast-from-exile/free-cost machinery where appropriate, but not suspend's
   resolution-time trigger continuation: the later plot cast is optional and chosen only when the player has
   sorcery timing.

Risks: three disfavoured areas cannot be avoided with this real list (tokens via Cutter, graveyard casting via Lava
Dart, graveyard-reading statics via delirium); they are scoped to the minimum these cards need. Pilots stay simple
(random / aggro) -- no skill modelling.

## Acceptance (proposed, same shape as milestone two)
- Both exact 60-card lists are supported; any unsupported card still causes strict refusal before a game starts.
- Run 10,000 seeded Burn-vs-Prowess games as four explicit 2,500-game cells: Burn in seat 0 and seat 1, crossed
  with Burn starting and Prowess starting. Report each cell separately as well as the combined result.
- With invariants enabled, all four cells have zero crashes, invariant violations, dead ends, and illegal actions
  accepted by the reducer.
- At least 1,000 stored game records sampled across all four cells replay to the exact event log and final full-state
  hash. Repeated runs with the same game and policy seeds are byte-for-byte identical.
- Manually inspect representative logs from all four cells, including every new mechanic above and games won by
  each deck when the simulation produces them. The logs must expose enough detail to audit choices and transitions.
- Run and report the milestone-one M7 benchmark and the new matchup throughput. The existing 20 games/second floor
  remains the only performance blocker unless a later approved spec changes it.
- No win-rate target and no pilot tuning are acceptance gates. This milestone validates rules execution, not player
  skill or agreement with observed matchup percentages.
- Legacy engines and their tests remain unchanged. Sideboards and best-of-three play stay out of scope.

## Changelog
- 2026-10-01: survey written (PROPOSED). Awaiting the user's choice before any engine code.
- 2026-10-01: manual oracle review corrected fetch, delirium, exile-play, flashback, Bauble, plot, and Thundering
  Falls requirements; acceptance split into four asymmetric seat/start cells. Still PROPOSED; no engine code.
- 2026-10-01: APPROVED by the user as one implementation block (Burn vs decks/auto/izzet_prowess_modern.txt); EXECUTING.
