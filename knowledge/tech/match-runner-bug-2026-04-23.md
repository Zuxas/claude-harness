---
title: "Match Runner Bug 2026-04-23 — APL Param Ignored"
domain: "tech"
last_updated: "2026-04-23"
confidence: "high"
sources: ["code-inspection", "sim-runs"]
---

## Summary
`engine/match_runner.py:_simple_play_turn()` in mtg-sim accepts an
`apl` parameter and never references it. Every two-player matchup
sim ever run has played a "one land + cheapest creature" heuristic
for both sides, ignoring the APL's real sequencing. The 2,009-entry
handler registry is never reached by the match_runner family of
functions.

## The bug

```python
def _simple_play_turn(gs: TwoPlayerGameState, player: str, apl=None):
    """Simple turn simulator for a player.
    If they have an APL, use it via a stub GameState.
    Otherwise, use the generic heuristic (play cheapest creature first).
    """
    # Body does not reference `apl` anywhere.
    # Only plays a land + casts cheapest-CMC creatures from hand.
```

Docstring claims APL-aware branch. Implementation has none. Classic
half-finished stub where two subsystems were supposed to meet.

## Affected code paths
- `engine.match_runner.run_match` → `_simple_play_turn`
- `engine.match_runner.run_match_set` → `run_match` → `_simple_play_turn`
- `engine.bo3_match.run_bo3` → `run_match` → `_simple_play_turn`
- `engine.bo3_match.run_bo3_set` → `run_bo3` → `run_match` →
  `_simple_play_turn`

Any `run_matchup.py` path (heuristic or Bo3) routes through this.

## NOT affected
- Single-deck goldfish via `sim.py` — if it calls APL methods
  directly against a single `GameState`, it works normally.
- `gauntlet_any_deck.py` — if it goldfishes one side against
  fixed kill-turn distributions, APL runs fine on our side.
- `apl_tuner.py` — goldfish-based, APL drives the single side
  it simulates.

The affected set is: any code that uses `match_runner` / `bo3_match`
to simulate two decks playing each other.

## Symptoms
- Control decks (Izzet Lessons, Jeskai Control) post <15% match WR
  regardless of opponent — they never cast their spells.
- Aggro decks look fine or slightly over-tuned — creature-only plans
  happen to approximate the heuristic.
- Results independent of sideboard plan quality — no spells are ever
  cast in any game.
- Handler registry telemetry never increments during matchup runs.
- Runtime: 10-16ms/game (fast enough to suggest games end in few
  turns, no complex decision tree executes).

## The MVP fix

~40 lines to `_simple_play_turn`. Build a GameState view over
TwoPlayerGameState's per-player flat fields (lists alias directly
so mutations propagate), populate a colorless ManaPool from lands
in play, call `apl.main_phase(view)` + `apl.main_phase2(view)`,
sync back the land_played flag.

```python
def _simple_play_turn(gs, player, apl=None):
    if apl is not None:
        from engine.game_state import GameState
        view = GameState(mainboard=[], on_play=gs.on_play)
        view.turn = gs.turn
        view.zones.hand        = gs.hand_a if player == 'a' else gs.hand_b
        view.zones.battlefield = gs.bf_a   if player == 'a' else gs.bf_b
        view.zones.graveyard   = gs.gy_a   if player == 'a' else gs.gy_b
        view.zones.library     = gs.lib_a  if player == 'a' else gs.lib_b
        view.life              = gs.life_a if player == 'a' else gs.life_b
        view.land_played       = gs.land_played_a if player == 'a' else gs.land_played_b
        lands = sum(1 for c in view.zones.battlefield if c.is_land())
        view.mana_pool.add_colorless(lands)  # confirm exact API
        try:
            apl.main_phase(view)
            if hasattr(apl, 'main_phase2'):
                apl.main_phase2(view)
        except Exception as e:
            if os.environ.get("SIM_DEBUG"):
                raise
            import sys
            print(f"  [WARN _simple_play_turn APL exec failed for "
                  f"{type(apl).__name__} player={player} turn={gs.turn}: {e}]",
                  file=sys.stderr)
        if player == 'a': gs.land_played_a = view.land_played
        else:             gs.land_played_b = view.land_played
        return
    # Existing heuristic body stays as fallback when apl is None
```

## Verified before implementing

Registry invocation chain: `apl.main_phase(view)` →
`_cast_all_castable(gs)` → `_cheapest_castable` → `gs.cast_spell(card)`
→ splits:
- Instants/sorceries: `on_spell_resolve(gs, card)` at
  `engine/card_effects.py:736` — does `SPELL_EFFECTS.get(card.name)`
  and invokes
- Permanents: `self._fire_etb_triggers(card)` — same pattern against
  `ETB_EFFECTS`

Once MVP lands, spells will cast and handlers will fire.

## Three known accuracy losses after MVP

1. **Colorless-mana approximation.** View's `mana_pool` gets all
   colorless from land count. Color-requiring spells (most of MTG)
   will cast when they shouldn't and fail when they should succeed.
   Separate 15-30 line diff: build ManaPool by querying each land's
   color production via existing Zones helpers.

2. **Goldfish `main_phase` not opp-aware `main_phase_match`.** APL
   plays as if alone. Control removal doesn't target opp creatures
   optimally. Aggro doesn't hold combat tricks. Upgrade requires
   opponent GameState accessible to the calling APL — another
   30-50 line diff. `MatchAPL.main_phase_match(gs, opp)` and
   `GoldfishAdapter` already exist.

3. **Triggers unverified.** `_cast_all_castable` → `gs.cast_spell`
   should fire the registry, but I haven't observed it end-to-end in
   a two-player view context. Smoke test as part of Gate A.

## Gated validation sequence (post-MVP)
1. 1 game with full logging — confirm APL runs, spells cast, game
   reaches >3 turns
2. 100 games with turn-count distribution — confirm median turn > 3,
   no turn-1 bailouts
3. 5k-per-matchup narrow gauntlet — compare FWR to tournament 49.5%
   ballpark for Izzet Lessons
4. 25k-per-matchup — only after step 3 looks sane

## Status
**Deferred to 2026-04-24.** Pre-MVP verifications completed tonight.
MVP + Gates A-D tomorrow. Fall-back plan if MVP fails: RC prep
continues on tournament-data-only basis, no time lost vs prior plan.

## Update 2026-04-24: MVP landed, upgrade landed, scope decision pending

Two commits landed overnight:
- `d9df94e` — initial MVP wiring APL into `_simple_play_turn`
- `8c63c63` — upgrade to `main_phase_match` via new
  `RemovalAwareGoldfishAdapter` so the `MATCH_REMOVAL` removal path
  fires at opp creatures before the goldfish main_phase runs

Gate A passed (14 spells cast in one game vs previous zero). Gate B
still 0/100 IL vs Mono Green Aggro — **not a bug, coverage gap.**
IL's actual interaction suite is ~70% bounce (Boomerang Basics),
saga tokens (Firebending Lesson), enchantment removal (Abandon
Attachments) — none modeled by `MATCH_REMOVAL`. Only Combustion
Technique is modeled, and only kills toughness ≤ 2 creatures.
Against MG Aggro's Earthbender-Ascension-buffed curve, CT runs
out of targets and IL legitimately loses.

### Scope decision — Option 2 (calibrate on shared-opponent pairings)

**The sim's job is to evaluate PT-emergent brews**, not to score
established decks. Established decks have real tournament data
(IL has 7,182 matches); sim calibration is meta-information about
tooling, not new strategic information. So "calibrate" doesn't mean
"pick a deck that fires cleanly in this framework" — it means
"prove the sim is trustworthy for evaluating novel post-PT lists
vs the known field."

**Highest-leverage calibration pairings:**
1. Dimir Midrange vs Izzet Prowess — both in-model for
   `MATCH_REMOVAL`; Izzet Prowess is 14% of meta and will be the
   shared opponent in every downstream evaluation
   (*Note: earlier framing cited "user's 23 RCQ T8s of personal
   Dimir Mid data" as a cross-check — that figure was traced to
   Team Resolve/CLAUDE.md and is labeled team-aggregate by
   ECOSYSTEM.md, not personal. Personal count is `[UNVERIFIED]`.
   See competitive-history.md 2026-04-24 correction.*)
2. Izzet Prowess vs Mono Green Landfall — top 2 meta decks, both
   in-model; stress-tests the shared opponent

**Success bar:** sim FWR within ~4% of matchup_matrix on those
pairings → sim is trustworthy for any PT-emergent brew vs known
field → decision-relevant use unlocked.

**Explicitly not doing:**
- Expanding `MATCH_REMOVAL` to include bounce, saga damage, or
  enchantment-removal paths. Bounce needs tempo accounting (card
  returns to hand, recast with summoning sickness reset); sagas
  are multi-turn state machines. Realistic cost 8–12 hours +
  regression risk in code just stabilized. Don't take on
  architectural debt for a deck (IL) that doesn't need sim anyway.
- Calibrating on matchups where one side is out-of-model. If
  Spellementals becomes a real candidate post-PT and its bounce
  lines matter, this decision gets revisited — but today it's
  premature.

**Combat is still heuristic** — `_resolve_combat` in `match_runner.py`
uses "biggest blocks biggest" instead of calling `declare_attackers`
/ `declare_blockers` on MatchAPL. If the shared-opponent calibration
lands within ~4% target, accept combat heuristic. If it misses by
10%+, combat is the next suspect, not MATCH_REMOVAL.

## Update 2026-04-24 afternoon: calibration FAILED — combat-trigger gap confirmed as unified root cause

Ran the Option 2 calibration (5000 games per pairing, see
[[sim-calibration-2026-04-24]]). **Both pairings failed by large
margins:**

| Pairing | Sim WR | Truth WR | Δ |
|---|---|---|---|
| Dimir Midrange vs Izzet Prowess | 64.6% | 40.0% | **24.6pt** |
| Izzet Prowess vs Mono Green Landfall | 1.4% | 53.0% | **51.6pt** |

Izzet Prowess is catastrophically under-weighted in both. **The bug
is `_resolve_combat`'s `_safe_power(card)` helper not applying
combat-phase triggered buffs** — prowess in particular. Slickshot
Show-Off attacks as its base 1/2 instead of 3/4 after two cantrips;
Stormchaser's Talent Otter tokens attack as 1/1 instead of pumped.
Any deck relying on noncreature-spell-triggered buffs punches far
below weight.

### Unified root cause — retroactive explanation of prior mystery

**This is the same bug that produced IL 0/100 vs Mono Green Aggro in
Gate B last night.** Earlier diagnosis attributed that 0% to
`MATCH_REMOVAL` coverage gap (bounce/saga/enchant-kill not modeled).
The coverage gap is real, but the ALSO-true cause was:
Stormchaser's Talent Otter tokens never got prowess buffs, so IL's
token-pressure plan collapsed into vanilla 1/1 pokes vs MG Aggro's
buffed-by-Earthbender-Ascension creature curve.

One root cause, two surface symptoms.

### Priority order if / when the sim gets rebuilt post-RC

**First fix = combat-trigger accounting**, NOT `MATCH_REMOVAL`
expansion. The path:
1. Modify `_resolve_combat` (or `_safe_power` / `_safe_toughness`
   helpers) to query effective power/toughness through a
   trigger-aware accessor, OR
2. Track per-turn pump counters on Card objects and have the helpers
   read them
3. Validate with the same two-pairing calibration — if Prowess lands
   within 4% of truth, combat is calibrated and MATCH_REMOVAL
   coverage is the next question

Expected effort: 8–12 hours per Tom's earlier estimate for this
class of combat/trigger work. Plus regression risk across all
other decks. **Deferred past May 29 RC.** Tournament data remains
the authoritative decision input for RC prep.

### Scope decision now resolved → SIDELINE

Both calibration pairings >10% delta → sim is structurally wrong
for any deck using combat-phase triggers. That covers most of
current Standard (Izzet variants, landfall decks) and a substantial
slice of Modern. **Sim is not available infrastructure for the RC
prep window.** Deck decisions revert fully to matchup_matrix +
personal experience + paper testing, as they were before sim work
started.

## Cross-links
- [[session-2026-04-23]] — session that surfaced the bug
- [[sim-framework]] — what the sim is for
- [[apl-architecture]] — APL interface reference
- [[rc-prep-path-forward]] — how this fits the RC timeline

## Changelog
- 2026-04-23: Created after code inspection revealed the bug during
  diagnostic gauntlet for Izzet Lessons RC prep.
