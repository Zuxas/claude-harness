# Standard calibration trace: Selesnya Landfall vs Izzet Prowess (2026-06-29)

Spec: `harness/specs/2026-06-29-next-structural-build.md` (STEP 1 diagnosis).
Target error: sim ~80% Selesnya WR vs PT SOS truth 62.9% (+17pp overshoot). Both fair combat decks, no card-advantage confound.

## Method

- Resolved both APLs from `MATCH_APL_REGISTRY` (`selesnyalandfall` -> `SelesnyaLandfallStandardMatchAPL`,
  `izzetprowessstandard` -> `IzzetProwessStandardMatchAPL`) and their decks via `load_deck_and_apl(..., "standard")`.
- Ran `engine.match_engine.run_match` (Path A single-game engine, the one Bo3 calls) with seed=42, n=8 games
  (alternating play/draw), verbose `gs._log` + combat/board instrumentation.
- Result in trace: Selesnya 8/8 (single-game, preboard). Bo3 wrapper (`run_matchup.py ... 10 8 42 standard fair 1`)
  reported G1=75.0% / Match=87.5%. Both confirm the gross overshoot.

## Dominant loss pattern (every sampled Prowess loss)

Izzet Prowess, the tempo/aggro deck, **declares ZERO attackers turn after turn** and deals almost no combat
damage. Representative board states where Prowess attacked with `[]`:

```
[PRO pre-attack] BF=[Eddymurk Crab(5/5), Slickshot Show-Off(1/2 flying haste),
                     Otter Token(1/1) x4]  life=7
[PRO ATTACK] -> []        <-- ~11 power on board incl. an UNBLOCKABLE flyer, attacks with nothing
```

Meanwhile Selesnya snowballs Badgermole Cub to 13/7, 27/8 via landfall + Mightform Harmonizer and wins on the
ground unopposed. Prowess's only damage is incidental Burst Lightning to face (burn-to-face works correctly).

## Root cause (mechanically confirmed)

`apl/aware_match_apl.py :: AwareMatchAPL.declare_attackers` (lines ~454-520) is **strictly more conservative
than the `MatchAPL` base it delegates to, and strips attackers the base correctly included.**

It calls `super().declare_attackers()` (= `MatchAPL.declare_attackers`, lines 350-449), which is a sensible
attacker selector (evasion-aware flyer-to-face at match_apl.py 412-420; pump/race math; "hold back small
creatures only against bigger blockers"). `AwareMatchAPL` then **re-filters that list** through a ground-only
trade loop (lines 474-509) that:
  1. picks the opponent's single highest-power creature as `best_blk` and applies it to **every** attacker,
  2. has **no flying/evasion check** (so an unblockable flyer is treated as blockable),
  3. ignores that one blocker can only block one attacker, and that a racing opponent won't block at all,
  4. drops any attacker that "dies alone" to that best_blk unless `opp_dmg > my_dmg + 8` (which never fires
     because Selesnya is ahead on the race).

Net effect: against any opponent with one big creature, Prowess attacks with **nothing** — including
unblockable flyers and a board the base class would have correctly sent in.

Direct confirmation (super() vs final on Prowess's seat) — the filter strips BOTH flyers and non-flyers:

```
eligible=['Eddymurk Crab','Eddymurk Crab']  flyers_eligible=[]            <-- NO flyer, two 5/5s
   MatchAPL(super)      -> ['Eddymurk Crab','Eddymurk Crab']
   AwareMatchAPL(final) -> []                                              <-- still stripped to nothing

eligible=[Crab, Colorstorm Stallion, Slickshot Show-Off, Otter x2]  flyers_eligible=[Slickshot Show-Off]
   MatchAPL(super)      -> [Crab, Stallion, Slickshot, Otters, ...]
   AwareMatchAPL(final) -> []                                              <-- unblockable flyer also dropped
```

The unblockable-flyer holdback is the cleanest confirmed instance, but the defect is the broad over-conservatism
of the re-filter, not evasion alone. The SAME loop is duplicated in
`SelesnyaLandfallStandardMatchAPL.declare_attackers` (lines 276-333) but is mostly inert on Selesnya's seat
because Selesnya is the one with the dominant board. `_lethal_this_turn` (line 392) is already evasion-aware
(KWTag.FLYING), so the bug only bites in the non-lethal branch.

## Branch verdict: A (LOCALIZED)

Fixable in the APL layer with NO engine change. The engine already models flying reach correctly
(`MatchAPL.declare_attackers` evasion path, `_lethal_this_turn` flying term, `resolve_combat` unblocked-flyer
damage). The defect is purely the over-conservative re-filter in `AwareMatchAPL.declare_attackers` discarding
evasive (and all) attackers when the opponent has a big ground board.

## Fix location (STEP 2 — not yet applied)

`apl/aware_match_apl.py`, `AwareMatchAPL.declare_attackers`, the per-attacker filter loop (~lines 474-509).
NOTE: `izzet_prowess_standard_match.py` (the spec's named scope file) does NOT override this method — it
inherits it from the shared base, so the fix lands in `aware_match_apl.py` and the blast radius is all 38
Standard match APLs.

Minimal fix should restore the base class's correct behavior rather than only flyers:
  - evasion early-accept (mirror `MatchAPL` 412-420): flyer with no opp flying/reach blocker always attacks;
  - and stop treating the single biggest opp creature as a universal blocker for every attacker (the
    "dies-alone-to-best_blk" holdback is the over-conservative core). Cheapest robust option: when the
    re-filter would strip an attacker the evasion-aware base included, defer to the base decision (i.e. only
    SUBTRACT for genuinely-bad trades, never drop evasive/unblocked attackers or a whole racing board).

If STEP 2 fixes only the flyer case, expect the number to move 80% -> ~74% and MISS the <=71.5% gate (the
two-Crabs-no-flyer case stays broken). Fix the breadth.

No-regression watch (per spec sec 5): this base class is inherited by all 38 Standard match APLs, so STEP 3
must re-check Selesnya vs Mono-Green Landfall (stay de-inverted) and Prowess vs the control decks it already
beats, and Prowess vs aggro mirrors, n>=200, after the fix.

## n used

n=8 (spec STEP-1 command), plus single-game verbose traces (4) and a super()-vs-final confirmation harness (4).
