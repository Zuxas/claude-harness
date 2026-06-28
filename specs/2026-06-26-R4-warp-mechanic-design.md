---
title: R4 Warp Mechanic (cast-from-exile recast) - PROOF + NO-REGRESSION design (READ-ONLY, for review)
status: SUPERSEDED
created: 2026-06-26
project: mtg-sim
superseded_by: harness/specs/2026-06-26-R4-warp-design.md
superseded_note: Folded into the canonical three-report synthesis (2026-06-26-R4-warp-design.md). Retained for its expanded XMage hook-mapping and proof-discipline detail; the canonical doc is authoritative for scope/gate/GO-NO-GO.
estimated_time: design only (no engine code written); implementation is S/M (~4-6h) once approved
related:
  - harness/specs/2026-06-26-R1-stack-priority-design.md  (gate + red-pre/green-post pattern this mirrors)
  - harness/specs/2026-06-26-R2-instant-combat-design.md  (forced-engine falsifier + honesty-subset discipline)
  - harness/specs/2026-06-26-R5-planeswalker-loyalty-design.md  (registry-reuse + bit-identical discipline)
  - mtg-sim/modelability_proofs/r1-stack-priority-2026-06-26.json
  - mtg-sim/modelability_proofs/r2-instant-combat-2026-06-26.json
  - mtg-sim/modelability_proofs/r5-planeswalker-loyalty-2026-06-26.json
  - mtg-sim/engine/game_state.py  (cast_spell_warp L711 + _tick_warp L757 + _WARP_CARDS L700 -- REUSED, not rebuilt)
worktree: E:/vscode ai project/mtg-sim-r4  (branch: modelability/r4-warp-mechanic)
branch_point_commit: deee281d1e44e09edb9685e2bc252f4bfa017b44  (on modelability/trilogy-integration: "Integrate R1+R2+R5 trilogy: conclude R2 merge, add cross-gate proof" -- the task-pinned branch point; the branch HEAD has since advanced to e8829370, but deee281 is the verified trilogy integration commit Warp must compose with)
depends_on: branches OFF THE VERIFIED TRILOGY BRANCH so Warp composes with R1 (priority stack) + R2 (instant combat) + R5 (planeswalker loyalty); it is NOT off main
supersedes:
superseded_by:
related_findings:
related_commits:
---

# R4 Warp Mechanic - Implementation Design

READ-ONLY design. No engine code is written by this synthesis. This doc is the reviewable plan
(mirroring the R1, R2 and R5 designs) that must be approved before any R4 implementation. R4 REUSES
the already-shipping `cast_spell_warp` + `_tick_warp` + `_WARP_CARDS` machinery in
`engine/game_state.py`, adds ONLY the missing third piece (cast-from-exile on a later turn) behind a
new capability gate so every non-Warp deck AND today's Warp behavior stay bit-identical, is built in
an isolated worktree branched OFF THE VERIFIED TRILOGY BRANCH (deee281) so Warp composes with
R1+R2+R5, is proven by replication + no-regression, and the merge is held for the user.

XMage (magefree/mage, MIT) is the PATTERN reference; the github-discovery flagged
`WarpAbility.java` by name. All XMage files below were FETCHED this session (raw.githubusercontent.com)
and their paths are CITED and verified-to-exist; method/field names are quoted, never copied. We
DESCRIBE the essence and replicate a deterministic minimal subset.

R4 is an S/M rung and is LOW-MAGNITUDE by design: two of its three sub-mechanics already ship and are
already exercised by a real deck (Izzet Looting's Quantum Riddler {1}{U} warp helper, per
mtg-sim/CLAUDE.md). The single new behavior is recast-from-exile. Its value is FIDELITY and
COMPOSABILITY (the second cast can itself be countered on the R1 stack, blink/etc.), not a large WR
jump. Overclaiming WR is an explicit abort (5.3 C).

---

## 0. The synthesis calls that drive everything (surfaced by reading code)

### 0.1 [KEY FINDING] Two of the three Warp pieces ALREADY SHIP, UNGATED. Only recast is missing.

Reading `engine/game_state.py` at the branch base, the Warp mechanic is already partially implemented
and runs UNCONDITIONALLY (no capability gate today):

- WARP-COST CAST FROM HAND -- `cast_spell_warp(card)` (L711-755): looks the card up in `_WARP_CARDS`
  (L700-709, name -> (warp_cost_str, warp_cmc)), checks `mana_pool.can_cast(warp_cost_str, warp_cmc)`,
  pays the cheaper warp cost, plays the card from hand to the battlefield as a normal creature (full
  P/T, summoning sickness unless HASTE), sets `card._warp_cast = True`, fires ETB (`_fire_etb_triggers`),
  honors the High Noon / Voice-of-Victory locks (L723-735) and the Cosmogrand second-spell trigger
  (L750-753), then runs SBAs. Returns True/False.
- DELAYED END-STEP EXILE -- `_tick_warp()` (L757-767), CALLED from the end-of-turn handler at L628
  ("Warp: exile any creature that was cast for its warp cost"): for every battlefield card with
  `_warp_cast` True, removes it from `battlefield`, appends to `zones.exile`, and clears `_warp_cast`
  so it does not re-fire.
- CAST FROM EXILE ON A LATER TURN -- **MISSING.** The code says so in two places, verbatim:
  - L696-698: "We don't currently support cast-from-warp-exile (sim-equivalent: it just disappears and
    you draw fresh copies). Modeling the Warp ENTRY is the main correctness win."
  - L759-761: "In real Magic the card is exiled and can be hardcast later from exile; here we just send
    it to exile and don't track recast (4-of deck consistency means a fresh copy gets drawn anyway)."

CONSEQUENCE FOR THE GATE (the one call that makes this design correct rather than regressive): because
`cast_spell_warp` and `_tick_warp` already run with NO gate, and a SHIPPING deck (Izzet Looting) already
casts Quantum Riddler for its warp cost, the no-regression baseline is "today's behavior INCLUDING warp
casts that exile and then sit forever in exile." R4 therefore gates ONLY the new recast-from-exile
behavior. It MUST NOT gate the whole Warp mechanic, or gate-OFF would regress Izzet Looting. The single
behavioral delta R4 introduces is: gate-ON, a warp-exiled card can be cast again from exile on a later
turn (paying full cost); gate-OFF, it stays in exile exactly as today.

### 0.2 CORRECTNESS TRAP A -- the flat exile zone makes "which exiled card is recastable" ambiguous

`engine/zones.py` L22 defines `exile` as a single FLAT shared list. Many mechanics already dump cards
there: Plot (`__prowess_plotted__`), foretell-style holds, Ugin/Karn exile-removal, blink in flight,
generic exile effects. So "a card is in `zones.exile`" does NOT by itself mean "this is a warped card I
may recast." If the recast scan just looked for "any creature in exile," it would illegally try to
recast Plotted cards, exiled-by-removal opponents' cards, blink-suspended cards, etc.

This is the task's flagged tricky bit ("the card must remain trackable in exile as warped,
recastable"). XMage solves it structurally: it moves the card into a DEDICATED, per-player NAMED exile
zone (`CardUtil.getExileZoneId(WarpAbility.makeWarpString(player.getId()), game)`) and grants cast
permission scoped to that zone. We do NOT have named exile sub-zones; the deterministic collapse is a
PER-CARD MARKER on the flat list:
- `_tick_warp` sets, on each card it exiles, `card._warp_recastable = True` and
  `card._warp_exiled_turn = self.turn` (additive attributes; nothing else reads them).
- the recast scan filters `zones.exile` to `getattr(c, '_warp_recastable', False) and self.turn >
  c._warp_exiled_turn` -- the only cards eligible.
This marker IS the answer to "remain trackable as warped, recastable." It is the same reduction R1/R5
used (collapse an N-general XMage structure -- here a named exile zone + a continuous makeCardPlayable
effect -- into a tiny per-object flag the deterministic 2-player sim reads directly).

### 0.3 CORRECTNESS TRAP B -- recast cost and re-exile (pin both against the printed rules text)

Two specific rules facts decide the new branch; both were read from primary source this session
(`mtg-sim/data/rules_reference/scryfall_oracle_cards.json`, Quantum Riddler / Starbreach Whale), not
from memory. The printed Warp reminder text:

  "Warp {1}{U} (You may cast this card from your hand for its warp cost. Exile this creature at the
   beginning of the next end step, then you may cast it from exile on a later turn.)"

- COST: the warp DISCOUNT is qualified "from your hand for its warp cost." Clause three -- "cast it
  from exile on a later turn" -- carries NO warp-cost qualifier, so the recast is a NORMAL cast at the
  card's FULL mana cost. Quantum Riddler recast = its printed {3}{U}{U} (CMC 5), NOT {1}{U}. This is
  grounded in XMage: `WarpAbility` is a HAND-zone alternative-cost ability (its zone is HAND); the
  cast-from-exile permission is a separate `CardUtil.makeCardPlayable(...)` that grants a normal cast.
  The recast branch must call the FULL-cost cast path (`mana_pool.can_cast(card.mana_cost, card.cmc)` /
  the normal `cast_spell`), never `cast_spell_warp`.
- "A LATER TURN": strictly a later turn than the exile -- `self.turn > card._warp_exiled_turn`. This is
  the deterministic collapse of XMage's `WarpCondition`, which returns true only when
  `game.getTurnNum() > turnNumber`. A same-turn recast (e.g. flicker shenanigans on the exile turn)
  is illegal and the recast helper must return False for it even gate-ON.
- RE-EXILE: the recast is a NORMAL cast, so it must NOT re-set `_warp_cast` and MUST clear
  `_warp_recastable`. Otherwise `_tick_warp` would exile it again at the next end step (an infinite
  warp loop). After a successful recast the card is an ordinary permanent that stays in play.

### 0.4 What is FREE vs what needs wiring

- FREE: warp-cost cast (`cast_spell_warp` L711), end-step exile (`_tick_warp` L757), the `_WARP_CARDS`
  registry (L700), the flat `zones.exile` list, ETB dispatch (`_fire_etb_triggers`), SBAs, and the
  High Noon / Voice / Cosmogrand interactions -- all already implemented and exercised.
- NEEDS WIRING (the whole of R4):
  1. `_tick_warp` additionally stamps `_warp_recastable` + `_warp_exiled_turn` when it exiles (additive
     attribute writes; inert gate-OFF -- 0.2).
  2. a gated recast helper `cast_spell_from_warp_exile(card)` that validates the marker + later-turn +
     full-cost-affordable, removes the card from `zones.exile`, casts it at full cost, clears the
     warp markers, and fires ETB.
  3. INTEGRATION GAP found: `put_into_play(card, from_zone=...)` (game_state.py L1476-1504) handles
     removal for `'hand'` / `'graveyard'` / `'library'` but has NO `'exile'` branch -- an
     `from_zone='exile'` falls through to the `None` ("caller already removed it") case (the docstring
     at L1485 even lists `'exile'` as accepted, but the body never removes from exile). The recast helper
     must remove the card from `zones.exile` ITSELF before putting it into play (or a one-line
     `from_zone=='exile'` removal branch is added to `put_into_play`). This is the exact seam.
  4. the capability gate (1.4) + the APL opt-in + a recast decision hook.

---

## 1. Exact engine changes (all ADDITIVE; gate-OFF path frozen, including today's warp behavior)

### 1.1 REUSE the existing warp machinery; do NOT rebuild cast-from-hand or end-step exile

`cast_spell_warp` (L711) and `_tick_warp` (L757) are UNCHANGED in behavior. The ONLY edit to existing
code is two additive attribute writes inside the `_tick_warp` exile loop (mark the card as
warp-recastable and record the turn). These attributes are never read on the gate-OFF path, so the
observable game state (zone contents, life totals, RNG stream, spells_cast counters) is byte-identical
gate-OFF. `_WARP_CARDS` (L700) gains no new entries for R4 (data unchanged).

### 1.2 The new gated recast helper (the entire new mechanic)

CRITICAL DESIGN CONSTRAINT (the composability invariant): the recast is a CAST, so it MUST funnel into
the existing normal cast entry point `cast_spell` (game_state.py L1344), NOT `put_into_play` (L1476 --
that is the cheat-onto-battlefield path used by reanimation / Through the Breach; it does not cast, does
not touch the stack, and cannot be intercepted). Routing through `cast_spell` is what gives R4 three
things for free and for correctness:
1. COMPOSABILITY WITH R1 -- `cast_spell` already routes through the priority stack when
   `_priority_stack_enabled` is on (L1384-1397). A warp recast then lands on the real R1 LIFO stack and
   CAN be countered, exactly as NR-4 / abort-D require. `put_into_play` would silently bypass this and
   FAIL NR-4 by construction.
2. WHEN-YOU-CAST TRIGGERS -- per the printed text the recast is a "cast," so "when you cast" triggers
   must fire. Warped Tusker reads "When you cast or cycle Warped Tusker, create a 0/1 Eldrazi Spawn";
   `put_into_play` would skip it. (Quantum Riddler, the v1 in-scope card, is ETB-only, so its ETB fires
   either way -- which is why a same-zone ETB test would NOT catch this; the counterability check in
   NR-4 is the real discriminator.)
3. NO DUPLICATED RULES LOGIC -- `cast_spell` already owns the High Noon lock (L1357-1364), the Voice of
   Victory lock (L1370-1374), the mana payment, `spells_cast_this_turn += 1`, and the Cosmogrand
   second-spell trigger (L1381-1383). The recast helper must NOT re-implement or double-count any of
   these.

The one obstacle: `cast_spell` hard-checks `card in self.zones.hand` (L1346) and pays the *effective*
cost (L1350, after any "costs {X} less" reductions). Two ways to satisfy it (recommend (a) for v1; (b)
is the cleaner refactor):
- (a) MINIMAL: the recast helper validates the warp markers + later-turn + gate, RELOCATES the card from
  `zones.exile` to `zones.hand` (the 0.4 seam -- removal from exile happens here, since `cast_spell` only
  removes from hand), clears the warp markers, then calls `self.cast_spell(card)` and returns its result.
  The card is cast at its normal (effective) cost via the shared path; reductions apply as for any cast,
  which is correct.
- (b) CLEANER: add a `from_zone='hand'` parameter to `cast_spell` (and a matching `'exile'` branch to
  `put_into_play` L1476) so the cast path can source from exile directly without the hand round-trip.
  Larger blast radius; defer unless (a) proves leaky.

Helper shape (NOT final code -- intent only, path (a)):

```
def cast_spell_from_warp_exile(self, card) -> bool:
    if not _warp_recast_enabled(self):                 # 1.4 gate; gate-OFF -> always False
        return False
    if not getattr(card, "_warp_recastable", False):   # 0.2 marker -> trackable
        return False
    if self.turn <= getattr(card, "_warp_exiled_turn", self.turn):  # 0.3 strictly later turn
        return False
    if card not in self.zones.exile:
        return False
    # 0.3 do NOT let it re-exile; clear warp state BEFORE the cast so the
    # recast permanent is an ordinary permanent.
    card._warp_recastable = False
    card._warp_cast = False
    self.zones.exile.remove(card)                      # 0.4 seam: leave exile...
    self.zones.hand.append(card)                       # ...so the shared cast path can source it
    ok = self.cast_spell(card)                         # FULL/effective cost, R1 stack, when-you-cast,
                                                       #   High Noon / Voice / Cosmogrand -- ALL reused
    if not ok:
        # cast blocked (e.g. High Noon, or countered-path returns True; handle per cast_spell contract):
        # leave the card where cast_spell left it; do NOT re-mark warp state.
        return False
    return True
```

(Note: `cast_spell` returns True even when the spell is countered on the R1 stack -- see L1394-1397 --
which is the correct outcome: the recast was a legal cast that an opponent answered.) The recast is
sorcery-speed in v1 (cast from the active player's main phase), matching the printed timing for these
creatures.

### 1.3 Call site

The recast is an active-player main-phase play, so it is offered in the same place the APL makes other
sorcery-speed plays. In `engine/match_runner.py` (`_simple_play_turn` / `_run_player_turn`, the path
warp decks actually run) and the `match_engine.run_match` mirror, after normal land/spell deploys and
gated on `_warp_recast_enabled`, scan the active player's `zones.exile` for eligible warped cards
(0.2 filter) and, if the APL elects, call `cast_spell_from_warp_exile`. Gate-OFF the scan is never
entered (byte-identical). No combat-path edit is needed (unlike R5), so the live `_resolve_combat`
math is untouched.

### 1.4 The gate (mirror R1 / R2 / R5 exactly)

```python
def _warp_recast_enabled(gs) -> bool:
    self_apl = getattr(gs, '_self_apl', None)
    opp_apl  = getattr(gs, '_match_opp_apl', None)
    return bool(getattr(self_apl, 'WANTS_WARP_RECAST', False)
                or getattr(opp_apl, 'WANTS_WARP_RECAST', False))
```

This is a copy of `_priority_stack_enabled` (game_state.py L100-111) with a renamed flag -- pure
getattr reads, no mutation, no `random()`. On the goldfish / match_runner paths where `_self_apl` /
`_match_opp_apl` are absent, both reads return None -> False -> the new recast is never reachable and
the engine is exactly today's "warp-exile then vanish" behavior. Base `apl/match_apl.py`:
`WANTS_WARP_RECAST = False`. The narrowed opt-in class is the warp deck APL
(`apl/izzet_looting_standard_match.py` -- the deck that already casts Quantum Riddler for warp), exactly
the narrowed-scope pattern R1 (`UWControlModernMatchAPL`), R2 (`MurktideMatchAPL`) and R5
(`EldraziTronMatchAPL`) used.

### 1.5 APL layer

- `apl/match_apl.py` base: `WANTS_WARP_RECAST = False`; default `choose_warp_recast(self, gs, opp,
  eligible) -> card|None` returning None (never recast) so opted-out APLs are unaffected.
- `apl/izzet_looting_standard_match.py`: `WANTS_WARP_RECAST = True`; `choose_warp_recast` recasts a
  warped creature when the full cost is affordable AND the second ETB / body is worth a full-price card
  this turn (e.g. recast Quantum Riddler when low on cards to re-trigger its draw + card-advantage
  static). Conservative default: only recast when it does not cost the turn's tempo-critical play.

### 1.6 Instrumentation (test-only, zero-RNG, mirror R1 COUNTERS_CAST / R2 TRICKS_CAST / R5 PW_*)

Module-global counter `WARP_RECASTS` in `engine/game_state.py` (or a small shim), incremented inside
`cast_spell_from_warp_exile` on a successful recast, with `reset_fire_count()`. Pure integer
bookkeeping -> no `random()`, no game-state mutation -> determinism preserved. The legacy gate-OFF path
never reaches the increment, so any nonzero value is direct evidence R4 fired in real play.

---

## 2. Reference essence -- the four required questions (XMage PATTERN, paths cited)

All paths fetched this session from `https://raw.githubusercontent.com/magefree/mage/master/...` and
confirmed to exist; identifiers quoted, not copied.

### 2.1 (a) Casting for an alternative cost
`Mage/src/main/java/mage/abilities/keyword/WarpAbility.java`: `WarpAbility extends SpellAbility`. The
constructor sets the ability's zone to `HAND`, sets `spellAbilityType = SpellAbilityType.BASE_ALTERNATE`
(this is what makes it an ALTERNATIVE cost rather than an added cost), CLEARS the normal mana costs and
adds the warp cost via `this.addCost(new ManaCostsImpl<>(manaString))`. Fields:
`WARP_ACTIVATION_VALUE_KEY = "warpActivation"` (static final String), `allowGraveyard` (boolean), and a
`WarpAbilityWatcher` is registered. ESSENCE: an alternative cheaper cast usable from the HAND zone.
OUR ANALOG: `cast_spell_warp` (game_state.py L711) -- looks up the cheaper cost in `_WARP_CARDS`, pays
it instead of the printed cost, casts from hand. (Already implemented.)

### 2.2 (b) Delayed triggered ability that exiles at the next end step
`Mage/src/main/java/mage/abilities/common/delayed/AtTheBeginOfNextEndStepDelayedTriggeredAbility.java`
(confirmed exists): a delayed triggered ability that fires "at the beginning of the next end step"
(checks the `END_TURN_STEP_PRE` event). WarpAbility wraps this around a `WarpExileEffect extends
OneShotEffect`, whose `apply` calls `player.moveCardsToExile(...)` targeting the exile zone id
`CardUtil.getExileZoneId(WarpAbility.makeWarpString(player.getId()), game)`. ESSENCE: set up a one-time
"at the beginning of the next end step, exile this" trigger; exile into a per-player NAMED warp zone.
OUR ANALOG: `_tick_warp` (game_state.py L757), driven from the end-of-turn handler at L628, moves
`_warp_cast` creatures battlefield -> `zones.exile`. We collapse "next end step delayed trigger" into a
flag (`_warp_cast`) swept once at end of turn, and "named exile zone" into a per-card marker (0.2).
(Exile already implemented; the marker is the R4 addition.)

### 2.3 (c) Casting a card from exile later
`Mage/src/main/java/mage/util/CardUtil.java` (confirmed exists): `makeCardPlayable(Game game, Ability
source, Card card, boolean useCastSpellOnly, Duration duration, boolean anyColor, UUID playerId,
Condition condition)` grants permission to cast/play a card FROM ITS CURRENT ZONE (here, the warp exile
zone) for the given duration, subject to `condition`. Warp passes a `WarpCondition` that returns true
only when `game.getTurnNum() > turnNumber` (strictly a LATER turn). The card is cast for its NORMAL cost
(the warp alternative cost lives on the HAND-zone `WarpAbility`, not on this permission). ESSENCE:
a continuous "you may cast this from exile, on a later turn, at normal cost" permission scoped by a
turn-number condition. OUR ANALOG: the new `cast_spell_from_warp_exile` (1.2) -- gated, marker-scoped,
`self.turn > _warp_exiled_turn`, full cost. (The R4 new mechanic.)

### 2.4 Cast-from-exile permission windows, generally
XMage models "you may cast X from a non-hand zone" uniformly via `CardUtil.makeCardPlayable` (a
continuous effect added to the game with a `Duration` and an optional `Condition`), used by foretell,
adventure, escape-like effects, impulse-draw, etc. The card's IDENTITY stays stable because it sits in a
specific (often named) exile zone tracked by `getExileZoneId`. The minimal deterministic subset we
replicate: a per-card "may be recast" marker + a turn-number guard, read directly by the sorcery-speed
play loop -- no general continuous-effect engine required for v1.

---

## 3. The minimal subset we replicate (deterministic 2-player), and what is tricky

Three sub-mechanics; only the third is new:
1. WARP-COST CAST FROM HAND -- exists (`cast_spell_warp`).
2. DELAYED END-STEP EXILE -- exists (`_tick_warp` at end of turn), R4 adds the recastable marker.
3. LATER CAST-FROM-EXILE -- new (`cast_spell_from_warp_exile`): full cost, later-turn, gated, no
   re-exile.

THE TRICKY PART (the task's flag): the card "must remain trackable in exile as warped, recastable."
The flat shared `zones.exile` cannot distinguish a warped card from a Plotted / removed / blinked one.
The deterministic answer is the per-card marker (`_warp_recastable` + `_warp_exiled_turn`) set at exile
time -- the collapse of XMage's named per-player warp exile zone + `WarpCondition`. Secondary tricky
bits, all pinned in 0.3: the recast pays FULL cost (not the warp cost), only on a strictly LATER turn,
and must NOT re-arm `_warp_cast` (else an infinite exile/recast loop). And the integration seam (0.4):
`put_into_play` has no `'exile'` removal branch, so the recast helper removes from exile itself.

---

## 4. Proof + no-regression harness (acceptance gate)

R4 is PROVEN iff ALL of 4.1 AND 4.2 AND 4.3 hold.

### 4.1 PROOF-BY-REPLICATION (differential -- must be RED pre-R4, GREEN post-R4)

New file `tests/test_r4_warp_recast.py` (standalone, `sys.path.insert`, plain asserts, ASCII-only,
prints "ALL R4 PROOF TESTS PASS", exit 0/1; same conventions as R1/R2/R5 tests). Hand-place cards; do
not run a full match. A test APL sets `WANTS_WARP_RECAST=True`; a per-instance `=False` toggle captures
the RED pre-state on the SAME structures (the R1/R2/R5-proven gate-toggle technique). seed=42,
PYTHONHASHSEED=0.

- TEST 1 -- RECAST FROM EXILE ON A LATER TURN (the headline known line).
  Put Quantum Riddler in hand; cast it via `cast_spell_warp` ({1}{U}); run the end-of-turn so
  `_tick_warp` exiles it. Advance to a later turn with >=5 mana. Call `cast_spell_from_warp_exile`.
  Assert: (a) the card LEAVES `zones.exile` and ENTERS the battlefield; (b) FULL cost {3}{U}{U}=5 was
  paid (mana pool drops by 5, not 2); (c) the ETB fired AGAIN (a second draw event / its second ETB
  effect observed); (d) `WARP_RECASTS == 1`.
  RED pre (gate OFF): `cast_spell_from_warp_exile` returns False; the card STAYS in `zones.exile`,
  battlefield unchanged, no mana paid, `WARP_RECASTS == 0`. (a)/(b)/(c)/(d) FLIP. This is the
  discriminator.

- TEST 2 -- "A LATER TURN" GUARD (same-turn recast illegal even gate-ON).
  Warp-cast and exile a card, then on the SAME turn attempt `cast_spell_from_warp_exile`. Assert it
  returns False and the card stays in exile (CR/printed "on a later turn"; XMage `turnNum > turnNumber`).
  Then advance one turn and confirm it now succeeds (proves the guard is the turn check, not a blanket
  block).

- TEST 3 -- NO RE-EXILE AFTER RECAST (no infinite loop).
  After a successful later-turn recast (TEST 1), run another end-of-turn `_tick_warp`. Assert the
  recast permanent STAYS on the battlefield (its `_warp_cast` / `_warp_recastable` are clear) -- it is a
  normal permanent now, not re-exiled.

- TEST 4 -- TRACKABILITY ISOLATION (the flat-exile trap, 0.2).
  Place in `zones.exile` BOTH a warp-exiled card (marker set) AND a non-warp exiled card (e.g. a Plotted
  card / a removed card, no marker), on a later turn. Assert the eligible-scan returns ONLY the warped
  card, and `cast_spell_from_warp_exile` on the non-warp card returns False. Proves the marker -- not
  mere presence in exile -- is what makes a card recastable.

GATE ON THE TEST ITSELF (Rule 5): TEST 1(a)-(d) and TEST 4 MUST FAIL on the gate-OFF toggle. If any
passes pre-R4 the test is not discriminating -> fix the test before any R4 claim (R1 abort A precedent).
Record paired pre/post results in `modelability_proofs/r4-warp-mechanic-2026-06-26.json`.

### 4.2 BEHAVIOR METRIC (headline) + WR ANCHOR + FALSIFIER

BEHAVIOR FLOOR (the "does the new mechanic actually fire in real play" gate), forced-engine direct
`run_match_set` (cache bypassed -- the R1/R2/R5 db-cache honesty method), Izzet Looting = gate ON,
n>=1000, seed=42, over the genuinely-simulated `g1_source="sim"` subset only:
- `WARP_RECASTS` per 1000 games > 0 vs ~0 in the gate-OFF baseline (recast actually happens), AND
- the second ETB is observed (Quantum Riddler's recast re-fires its draw) -- so the recast does
  something, it is not a phantom zone move.

FALSIFIER (mirror R2 L116): turning `WANTS_WARP_RECAST` OFF must not IMPROVE the deck (recast is upside
or neutral). Run `engine.match_runner.run_match_set` DIRECTLY (cache bypassed), twice, ON vs OFF; assert
`MWR_on - MWR_off >= 0` on the `g1_source="sim"` subset with the per-matchup `g1_source` table. Report
the subset honestly (sim vs db vs ComboKillSampler), as R2 did.

WR ANCHOR (cross-check, HONEST about magnitude): R4 is LOW-MAGNITUDE. The engine's own comment notes
that with 4-of consistency "a fresh copy gets drawn anyway," so the recast's marginal WR is expected
SMALL (predict +0 to +2pp on Izzet Looting's FWR, most likely near-zero). The acceptance is the
behavior floor + the falsifier sign, NOT a WR jump. If `MWR_on - MWR_off` is large (> ~3pp), that is a
red flag the recast is being valued unrealistically (e.g. full cost not charged, or re-exile loop
generating value) -> investigate (5.3 C), do not celebrate.

### 4.3 NO-REGRESSION (bit-identical; mirror R1 / R2 / R5)

- NR-0 (THE load-bearing anchor, unique to R4): TODAY'S WARP BEHAVIOR is preserved gate-OFF. Izzet
  Looting (which casts Quantum Riddler via warp) run BOTH as goldfish (`sim.py` n=50) AND as a match via
  direct `run_match_set`, with `WANTS_WARP_RECAST` OFF, is BYTE-IDENTICAL to the frozen branch-point
  capture. This proves the `_tick_warp` marker writes (1.1) and the new helper are truly gated and do
  not perturb the warp-cast-then-exile path the deck already uses.
- NR-1 (non-warp bit-identical): a non-warp match (e.g. Boros Energy vs Dimir) via direct
  `run_match_set`, gate OFF -> byte-identical. Pick a non-degenerate (not 0/100) matchup.
- NR-2 (goldfish determinism): Amulet Titan goldfish (20-life 95.7% avg T7.11 / median T7; 17-life
  95.9% avg T6.81 / median T6) unchanged (no warp cards) -- determinism guard.
- NR-3 (coverage): `python scripts/full_audit.py --formats standard` -> 4218/4218, all 17 sets at 0
  remaining (R4 is control-flow + one helper + two attribute writes, not new handlers).
- NR-4 (CROSS-GATE, because R4 is off the trilogy -- the composability proof): with R4's branch base at
  deee281, the R1, R2 and R5 proof tests (`tests/test_r1_stack_priority.py`,
  `tests/test_r2_instant_combat.py`, `tests/test_r5_planeswalker_loyalty.py` -- all three CONFIRMED present
  on modelability/trilogy-integration this session via git ls-tree, plus a bonus
  `tests/test_r1_control_exercises.py`; re-check at the deee281 base at implementation time) ALL still pass post-R4,
  AND a composed check: a warped recast cast under `WANTS_PRIORITY_STACK` ON goes onto the real R1 stack
  and CAN be countered (proves the recast routes through the normal cast path, not a side channel). This
  is the trilogy-integration cross-gate discipline (deee281) extended to R4.
- NR-5 (APL smoke): `tests/test_standard_apls.py`, `tests/test_match_engine.py`,
  `tests/test_determinism.py` all green.

Compare post-R4 against the FROZEN branch-point capture (at deee281), not hardcoded historical numbers.

---

## 5. Honest effort / risk + ABORT conditions

### 5.1 Effort and risk (highest first)
1. The `_tick_warp` edit (1.1) touches a path a SHIPPING deck uses every game. Mitigated: the only edit
   is two inert attribute writes; NR-0 proves byte-identical gate-OFF before anything relies on gate-ON.
2. The integration seam (0.4): `put_into_play` lacking an `'exile'` removal branch means a naive recast
   could leave a duplicate (card both in exile and on battlefield). The helper removes from exile
   explicitly; TEST 1(a) asserts exile count drops by exactly 1.
3. Full-cost vs warp-cost (0.3): charging the warp cost on recast would over-value the mechanic (5.3 C).
   TEST 1(b) asserts the full cost is paid.
4. Re-exile loop (0.3): forgetting to clear `_warp_cast` / `_warp_recastable` would re-exile the recast
   permanent (infinite value). TEST 3 guards this.
5. Trackability leak (0.2): a marker that is too loose (e.g. "any creature in exile") would recast
   Plotted/removed cards. TEST 4 guards this.

### 5.2 Intentionally DEFERRED beyond R4
- Flash / instant-speed warp recast (v1 recast is sorcery-speed, matching these creatures' printed
  timing). If a future warp card grants flash, route it through R2's instant windows.
- Non-permanent warp cards: `cast_spell_warp` assumes battlefield entry (a creature). Any warp card that
  is an instant/sorcery (the `_WARP_CARDS` comment flags Close Encounter as "has Warp via additional
  cost" -- VERIFY its card type at implementation time; the local oracle for Warped Tusker shows Cycling,
  not Warp, a data-drift note) is OUT of v1 scope -- a spell would be exiled from the stack on
  resolution, a different path. v1 = permanent (creature) warp cards only; audit `_WARP_CARDS` against
  card types before enabling.
- `allowGraveyard` warp variants (XMage's boolean) -- not needed for the EOE cards in scope.
- Named per-player exile sub-zones (we use the flat list + marker; revisit only if another mechanic
  needs zone partitioning).

### 5.3 ABORT conditions (discard the worktree, leave the item unmodelable; mirror R1/R2/R5 + ladder P5)
A. Proof not falsifying: any TEST 1/4 discriminator passes pre-R4 (gate OFF) -> fix the test, no R4
   claim until clean red-pre / green-post.
B. NO-REGRESSION broken: NR-0 (today's warp behavior) / NR-1 / NR-2 not bit-identical -> abort; a leak
   into the gate-OFF path is the one thing R4 must not do.
C. WR OVER-VALUE: `MWR_on - MWR_off` large (> ~3pp) -> the recast is being mispriced (full cost not
   charged, or re-exile loop) -> investigate; do NOT ship a Warp WR claim that contradicts the
   low-magnitude prediction (4.2). Conversely a tiny/zero delta is EXPECTED and acceptable -- R4's win is
   fidelity, not WR.
D. CROSS-GATE break: any R1/R2/R5 proof test fails post-R4, or a recast does NOT route onto the R1 stack
   when `WANTS_PRIORITY_STACK` is on (NR-4) -> abort; R4 must compose with the trilogy, that is the whole
   point of branching off deee281.
E. Coverage regression: full_audit < 4218/4218.
F. Determinism leak: `test_determinism` fails (the helper or marker writes touch global random state) ->
   abort; RNG purity is non-negotiable.
G. Known line not reproducible in the iteration budget -> write an IMPERFECTIONS update
   ("warp-recast-from-exile-not-modeled"), leave the item partial (warp entry + exile keep shipping),
   revert R4.

---

## 6. GO / NO-GO recommendation

NO-GO for autonomous implementation now. HOLD for user review (same framing as R1/R2/R5: design before
engine code; the merge is held for the user). R4 is the lowest-risk rung of the four -- two of three
pieces already ship, there is no combat-path edit, and the new surface is one gated helper plus a marker
-- but it still touches a path a shipping deck uses, so it is not started autonomously before approval.

Middle option (forward motion without committing to merge): a bounded, reversible SPIKE --
`EnterWorktree modelability/r4-warp-mechanic` OFF THE TRILOGY BRANCH (deee281), freeze baselines, add
the `_tick_warp` markers + the gated `cast_spell_from_warp_exile` + the `WANTS_WARP_RECAST` gate, prove
`tests/test_r4_warp_recast.py` goes RED-pre / GREEN-post on TESTs 1-4, run NR-0 (Izzet Looting warp
behavior byte-identical gate-OFF) + NR-4 (R1/R2/R5 tests still green + recast composes with the R1
stack), and STOP. That validates the core bet (reuse the shipping warp machinery + one gated recast +
a trackability marker, composing with the trilogy) cheaply and is discardable via `ExitWorktree`.

Recommended: HOLD. On approval, spike first, then the full gate + the behavior floor + falsifier.

---

## Appendix -- file-change list (absolute paths, worktree mtg-sim-r4)

- MOD  E:/vscode ai project/mtg-sim-r4/engine/game_state.py        (1.1 _tick_warp L757: stamp _warp_recastable + _warp_exiled_turn on exile; 1.2 ADD cast_spell_from_warp_exile gated recast helper; 1.4 ADD _warp_recast_enabled gate (copy of _priority_stack_enabled L100); 1.6 ADD WARP_RECASTS instrument + reset_fire_count; OPTIONAL 0.4 add 'exile' removal branch to put_into_play L1476; existing cast_spell_warp L711 + _WARP_CARDS L700 behavior UNCHANGED)
- MOD  E:/vscode ai project/mtg-sim-r4/engine/match_runner.py      (1.3 gated eligible-warp-exile scan + recast call in the active-player main-phase deploy; gate-OFF never entered)
- MOD  E:/vscode ai project/mtg-sim-r4/engine/match_engine.py      (1.3 mirror: same gated recast offer after main_phase_match; gate-OFF byte-identical)
- MOD  E:/vscode ai project/mtg-sim-r4/apl/match_apl.py            (base WANTS_WARP_RECAST=False + default choose_warp_recast returning None)
- MOD  E:/vscode ai project/mtg-sim-r4/apl/izzet_looting_standard_match.py  (WANTS_WARP_RECAST=True + choose_warp_recast for Quantum Riddler; narrowed opt-in)
- KEEP E:/vscode ai project/mtg-sim-r4/engine/zones.py             (UNCHANGED -- flat exile list reused; trackability via per-card marker)
- ADD  E:/vscode ai project/mtg-sim-r4/tests/test_r4_warp_recast.py
- ADD  E:/vscode ai project/mtg-sim-r4/modelability_proofs/r4-warp-mechanic-2026-06-26.json  (proof artifact: rung, behavior_floor warp_recasts, wr_on, wr_off, falsifier_delta, second_etb_observed, line_reproduced, seed, log_excerpt, commit_hash, g1_source_table, cross_gate_r1r2r5_green)

## Pattern reference (cited as PATTERN only -- MIT, describe-don't-copy)

All XMage paths FETCHED this session (raw.githubusercontent.com/magefree/mage/master) and confirmed to
exist; identifiers quoted, not copied.
- `Mage/src/main/java/mage/abilities/keyword/WarpAbility.java` (the github-discovery-flagged file):
  `extends SpellAbility`; zone `HAND`; `spellAbilityType = SpellAbilityType.BASE_ALTERNATE`; clears mana
  costs and `addCost(new ManaCostsImpl<>(manaString))` (alternative warp cost from hand); fields
  `WARP_ACTIVATION_VALUE_KEY = "warpActivation"`, `allowGraveyard`; registers `WarpAbilityWatcher`. Sets
  up an `AtTheBeginOfNextEndStepDelayedTriggeredAbility` wrapping a `WarpExileEffect extends OneShotEffect`
  that `moveCardsToExile()` into `CardUtil.getExileZoneId(WarpAbility.makeWarpString(player.getId()),
  game)`, and grants cast-from-exile via `CardUtil.makeCardPlayable(...)` with a `WarpCondition`
  (`game.getTurnNum() > turnNumber`).
- `Mage/src/main/java/mage/abilities/common/delayed/AtTheBeginOfNextEndStepDelayedTriggeredAbility.java`:
  delayed triggered ability firing at the beginning of the NEXT end step (`END_TURN_STEP_PRE`). ESSENCE
  for 2.2.
- `Mage/src/main/java/mage/util/CardUtil.java`: `makeCardPlayable(Game, Ability, Card, boolean
  useCastSpellOnly, Duration, boolean anyColor, UUID playerId, Condition)` grants cast-from-current-zone
  permission scoped by a Condition + Duration; `getExileZoneId(String key, Game)` (and overloads) returns
  a per-key named exile zone id that keeps the card's identity stable. ESSENCE for 2.3 / 2.4.
- open-mtg (hlynurd/open-mtg, Python): no Warp / alternative-cost-from-exile model -- not a usable
  pattern source for this rung (XMage is the sole external reference, consistent with R5's finding).

## Changelog
- 2026-06-26: Authored as the R4 design (READ-ONLY), mirroring the R1/R2/R5 proof + bit-identical
  discipline. KEY FINDING: two of the three Warp sub-mechanics already ship UNGATED (cast_spell_warp
  L711, _tick_warp L757) and are exercised by a shipping deck (Izzet Looting / Quantum Riddler), so R4
  gates ONLY the missing recast-from-exile (not the whole mechanic) to avoid regressing that deck.
  Pinned the three rules facts from primary source (full recast cost not warp cost; strictly later turn;
  no re-exile) and the trackability collapse (per-card marker on the flat exile list = XMage named warp
  exile zone + WarpCondition). Surfaced the put_into_play 'exile' integration seam (L1476). Branch base
  is the VERIFIED trilogy (deee281) so Warp composes with R1+R2+R5; added the NR-4 cross-gate proof.
  No engine code written; doc remains READ-ONLY, status PROPOSED.
