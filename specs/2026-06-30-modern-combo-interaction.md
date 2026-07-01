---
title: Interaction-Aware Modern Combo Opponents (handoff #2)
status: EXECUTING
created: 2026-06-30
updated: 2026-06-30 (rev 3 -- SPINE increment executed: Component 2 Site 1 + Component 1 inert layer)
project: mtg-sim
estimated_time: 8-12 working sessions (see Estimated time; rev 2 honest re-estimate)
related_findings:
  - harness/knowledge/tech/modern-apl-fidelity-audit-2026-06-30.md
  - harness/knowledge/tech/boros-energy-postban-validation-2026-06-29.md
related_commits: []
supersedes: []
superseded_by: []
branch: modern-postban-arc
---

# Interaction-Aware Modern Combo Opponents

## Goal

Model Modern combo opponents in the gauntlet so that (a) each combo actually ASSEMBLES on a
realistic clock AND (b) OUR interaction can ANSWER it -- so the flagged combo cells in
`mismodeled_matchups.py` (grixis INVERTED, goryos/living_end/broodscale INFLATED) become
TRUSTWORTHY by *modeling the interaction*, never by inflating or deflating a distribution.

This is a DESIGN pass. This document is the spec. No engine/APL code is written here; the work
it describes is sequenced, gated, and validated below.

---

## Adversarial review responses (rev 2, 2026-06-30)

An adversarial reviewer returned `SOUND_WITH_FIXES`. Every point below was verified against the
actual code before being accepted; line numbers cited are from the verification pass.

**ACCEPTED (code-verified):**
- **R1 / no-regression methodology (high).** `scripts/full_field_gauntlet.py` L116+L122-127 builds
  `n_decks*(n_decks-1)` jobs and runs BOTH `a-vs-b` and `b-vs-a`. Every deck pilots seat A in its
  own row, so editing a combo APL moves its whole seat-A row, not one cell. The old Component 4.4
  "every cell EXCEPT the edited one unchanged" was FALSE under a round-robin driver. FIX: the
  per-deck no-regression proof is pinned to the SINGLE-HERO driver `run_match_set`
  (`engine/match_runner.py` L1687; L1719-1743 confirm apl_a is ALWAYS seat A, apl_b ALWAYS seat B),
  boros seat A / combo seat B, where the combo is structurally only ever the opponent. The
  round-robin full_field_gauntlet is retained only as a FIELD-HEALTH read with a cell-granular
  invariant (Component 4). See Component 4 rewrite.
- **R2 / Site 2 wrong seat (medium).** `_run_end_step` (L1468+) calls `end_step_actions` on the
  REACTIVE player: `view` = reactive (L1502-1554), `opp_view` = active. There is no "active-player
  view.damage_dealt" to sync. FIX: Site 2 (IF built) syncs the REACTIVE player's `view.damage_dealt`
  delta to the ACTIVE player's match life, gated on the REACTIVE APL's flag; and its CONSTRUCTION is
  gated behind the Step 2.0 diagnostic actually finding an end-step killer. No current combo kills at
  the opponent's end step, so Site 2 may be dropped entirely. See Component 2 rewrite.
- **R3 / prowess vs the lock (medium).** Flagging Izzet Prowess `WANTS_BURN` pushes its ~0.7 face
  dmg/game into selesnya's life, moving the selesnya-vs-prowess locked cell -> internally
  inconsistent. FIX: Izzet Prowess (and ANY creature-combat burn deck feeding a locked cell) stays
  LATCHED OFF (no flag). Removed from the #2 re-baseline list. Only mono_red + the drain/direct combo
  opponents get `WANTS_BURN`. With prowess unflagged, the lock falls out automatically from the
  cell-granular #2 invariant (both decks unflagged -> byte-identical). See Component 2 + Component 4.
- **Number-forcing (all four).** Collapsed into ONE discipline: every gate -- primer AND directional
  -- must be a FUNCTION of observable inputs (decklist copy-counts via hypergeometric, a MEASURED
  goldfish kill-turn distribution, oracle P/T), never an asserted number. The band is the OUTPUT
  RANGE of that function. Stop condition 2 broadened to fire on tuning ANY assembly
  probability/frequency (not just a "kill-turn distribution"). grixis card-draw excluded as a lever
  (no engine-scored kill pathway). See Component 5 rewrite + Stop conditions.
- **Missing decks.** temur_crashcade ADDED as a per-deck item (cascade combo, structurally identical
  to living_end). dimir_oculus + glockulous explicitly DEFERRED with rationale (not silently
  dropped) -- see Annotated imperfections. landless_belcher requires MATCH_APL_REGISTRY registration
  (not a bare alias) + a fidelity caveat on the Sea-Gate-adds-lands mismatch. See Component 3.
- **Feasibility.** goryos, belcher bumped (reanimation-mechanic rebuild / bespoke kill ability);
  neoform+neobrand get an explicit kill-channel-decision spike FIRST (Griselbrand deals no damage --
  the #2-dependency is unknown until the line is pinned); living_end + temur_crashcade re-seamed to
  instant-speed (end_step) cascade. See Component 3 effort column + Estimated time.

**NOTED AS NOT-A-DEFECT (clarification, not a fix):** the reviewer's "minor" worry that gating Site 2
behind the diagnostic could block the cascade decks is unfounded: living_end / temur_crashcade use
the end_step SEAM for cascade TIMING (a zone-move reanimation via spine #2), which is ORTHOGONAL to
Site 2's damage propagation. Cascade decks kill in COMBAT and never needed Site 2. The spec is
careful below not to conflate "uses end_step" with "needs Site 2."

---

## The spine: how `run_match` actually routes a combo opponent (read this first)

Every design choice below follows from these verified facts about the gauntlet path
(`engine/match_runner.py::run_match`, the singular path used by `full_field_gauntlet`,
`bo3_gauntlet`, `gauntlet_any_deck`; the `ComboKillSampler` lives ONLY in `run_match_set` /
`_run_single_match` and its `KILL_DISTS` keys do NOT include any of our Modern combo decks, so
those decks are PLAYED OUT, not sampled):

1. **Only three APL entry points fire in `run_match`:** `main_phase_match(view, opp_view)`
   (via `_simple_play_turn`), `main_phase2_match` / `main_phase2` (via `_run_post_combat_phase`),
   and `end_step_actions` (via `_run_end_step`, for the non-active seat). `declare_attackers`,
   `declare_blockers`, `respond_to_spell`, `combat_trick`, `combat_priority_action` are **NEVER
   called** on this path. Combat is resolved by `_resolve_combat` reading battlefield BODIES.
2. **Zone lists are ALIASED into the per-turn `GameState` view** (`v.zones.hand/battlefield/
   graveyard/library = gs.hand_x/bf_x/gy_x/lib_x`). So any APL mutation that MOVES A CARD between
   zones (cast, reanimate, exile, kill, discard) PROPAGATES to the shared `TwoPlayerGameState`.
3. **SCALAR life writes do NOT propagate** (advisor-confirmed; verify in Step 0.1). The sync-backs
   in `_simple_play_turn` only push `land_played`, spell counters, and -- gated on the ACTIVE apl's
   `WANTS_STORM` -- `view.damage_dealt -> gs.life_{opp}`. It never syncs `opp_view.life`, and the
   active `view.life` is synced only by `_run_post_combat_phase` (not by `_simple_play_turn`).
   `_run_end_step` syncs neither life nor `damage_dealt`. **Consequence:** a combo that kills by
   `opponent.life -= X` (drain) writes a throwaway copy and the match life total never sees it.
   Only two damage channels actually reach the opponent's match life total:
   (i) combat via `_resolve_combat` (reads aliased bodies), and
   (ii) the ACTIVE player's `view.damage_dealt`, and ONLY in main_phase_1 when `WANTS_STORM` is on.
4. **Counters already work IF the combo casts its key spell through `gs.cast_spell`.** `cast_spell`
   invokes `try_counter_spell(opp_apl, ...)` (legacy) or `run_priority_stack` (R1, when
   `WANTS_PRIORITY_STACK`), reading `_match_opp_apl` (wired by `_build_view`). Combo APLs that
   manually move zone cards (Goryo's, Living End) BYPASS this window entirely.
5. **`_match_cast_removal` already fires OUR removal** (`MATCH_REMOVAL` dict) on the aliased opp
   battlefield at the top of our `main_phase_match`, biggest-power-first, one spell/turn. It cannot
   kill a body tougher than the spell's `max_tgh` (so a 7/7 Atraxa survives Bolt -- exile/`None`
   removal matters).

**Therefore the structural gap is interaction, and it has exactly three sub-gaps the new work must
close:** (A) combo APLs that do not reliably assemble; (B) the drain/direct-damage life channel
(#3) that silently drops every non-combat combo kill; (C) the absence of any seam where, at the
combo's decisive step, OUR specific answers (removal on the lone reanimated body, GY-hate,
a counter on the combo spell) get a chance to fire.

---

## Scope

### In scope
- **#2 engine fix:** propagate `damage_dealt` from main-phase-1 (generalize the `WANTS_STORM` gate
  -> Site 1) gated via a new `WANTS_BURN` flag so unflagged decks stay byte-identical. A SECOND
  end-step site (Site 2 in `_run_end_step`, REACTIVE-seat damage -> active match life) is
  CONDITIONAL -- built only if the Step 2.0 diagnostic finds an end-step killer, else dropped (R2).
- **Shared interaction layer:** a new `engine/combo_interaction.py` + an `answer_combo` method +
  a `WANTS_COMBO_INTERACTION` opt-in on our match APL. The combo APL INITIATES the hook at its
  decisive step; the layer is unreachable on non-combo matchups (no-regression crux).
- **Per-deck assembly + answerability** for 13 decks: grixis_reanimator, goryos_vengeance,
  living_end, temur_crashcade (added rev 2 -- cascade combo, same class as living_end),
  gruul_broodscale, belcher, neobrand, neoform, ruby_storm, temur_breach, yawgmoth, and
  landless_belcher (currently UNCOVERED / no reachable match APL).
- **Calibration** of the three cells with primer gates (grixis 38, goryos 73, broodscale 55) by
  modeling interaction, plus directional improvement of the no-primer cells (living_end,
  temur_crashcade, ruby_storm, yawgmoth) with computed (falsifiable) bands.
- **Explicitly DEFERRED (not silently dropped):** dimir_oculus (card-advantage engine, no
  engine-scored clock) and glockulous (reanimator half of an Izzet Affinity shell -> handoff #3).
  See Annotated imperfections.
- **Test re-pointing** so combo-as-seat-B tests cannot go trivially green via a sampler reroute.
- **No-regression proof** that the non-combo field stays byte-identical.

### Out of scope
- Izzet Affinity clock / Cutter Affinity / Glockulous (handoff #3).
- Literal hidden-information / belief-state modeling (permanently out; R6).
- The ComboKillSampler routing in `run_match` (prototyped + REJECTED 2026-06-29; do NOT revive it).
- Bo3 sideboard-game combo modeling (G1-only gauntlet here; SB answers built for generality but
  not validated).
- Reverse-fitting any kill-turn distribution to a target number.

---

## Pre-flight reads (do all before any Step)
- `harness/knowledge/tech/spec-authoring-lessons.md` (Rule 9 -- prior prediction-model lessons).
- `harness/knowledge/tech/modern-apl-fidelity-audit-2026-06-30.md` (the audit this builds on).
- `harness/knowledge/tech/boros-energy-postban-validation-2026-06-29.md` (sampler rejection + locks).
- `harness/IMPERFECTIONS.md` entries: `combo-decks-not-sampled-in-gauntlet-run_match`,
  `grixis-reanimator-match-apl-crashes-every-turn`, `locked-modern-boros-affinity-baseline-stale-63.5`,
  `engine-mp1-damage-dealt-discarded-for-nonstorm-decks`, `mono-red-aggro-burn-discarded`,
  `living-end-hardcast-at-sorcery-speed`, `yawgmoth-combo-drain-list-mismatch`.
- `engine/match_runner.py` -- `_simple_play_turn` (sync-backs L260-284), `_run_post_combat_phase`,
  `_run_end_step` (L1468+), `_resolve_combat`, `run_match`, `ComboKillSampler`,
  `_run_match_with_combo`, the WANTS_STORM gate at L276.
- `engine/game_state.py::cast_spell` (counter window L1565-1586; R1 stack L1556-1563).
- `apl/match_apl.py` -- `MatchAPL` base (`_match_cast_removal`, `MATCH_REMOVAL`/`MATCH_WIPES`/
  `MATCH_EXILE`, the `WANTS_*` gate block, default `declare_*`/`respond_to_spell`).
- `mismodeled_matchups.py` (the cells this work must make trustworthy).
- The combo APLs: `apl/grixis_reanimator_match.py`, `apl/goryos_match.py`, `apl/living_end_match.py`,
  `apl/gruul_broodscale_match.py`, `apl/belcher_match.py`, `apl/neobrand_match.py`,
  `apl/neoform_match.py`, `apl/ruby_storm_match.py`, `apl/temur_crashcade_match.py`,
  `apl/temur_breach.py`, `apl/yawgmoth_match.py`.
- `tests/test_grixis_reanimator_no_crash.py` (the test-repointing target).

---

## Component 1 -- The shared interaction layer

### Where it lives
New module `engine/combo_interaction.py`. A new method `answer_combo` on the interaction-capable
match APL (initially `BorosEnergyMatchAPL`, via a small mixin so it is reusable). A new class flag
`WANTS_COMBO_INTERACTION = False` added next to the existing `WANTS_*` block in
`apl/match_apl.py::MatchAPL`.

### The no-regression crux: how it is GATED to combo opponents only
Two independent gates, BOTH of which must be on for any interaction to occur:
1. **Initiation gate (structural):** the layer is reached ONLY through `offer_interaction(...)`,
   which is called ONLY from inside a combo APL's assembly code at its decisive step. A non-combo
   seat-B APL never calls it, so a non-combo matchup never imports or executes
   `engine/combo_interaction.py`. This is byte-identical BY CONSTRUCTION, not by diffing.
2. **Capability gate (flag):** `offer_interaction` early-returns a no-op `InteractionResult`
   unless `getattr(opp_apl, 'WANTS_COMBO_INTERACTION', False)` is True. So even when a combo APL
   is seat B, if our seat-A deck has not opted in, the combo proceeds EXACTLY as its "assembled,
   un-answered" baseline (the honest floor). This mirrors the established `WANTS_PRIORITY_STACK` /
   `WANTS_WARP` / `WANTS_STORM` / `WANTS_PW_LOYALTY` convention.

> Byte-identical applies to the NON-COMBO field only. Combo cells are EXPECTED to move (toward the
> primer) the moment a combo APL assembles -- that is the deliverable, not a regression.

### Hook API
```
# engine/combo_interaction.py
@dataclass
class ComboEvent:
    kind: str            # "counter_window" | "reanimate" | "gy_setup" | "resolve_threat"
    spell: Card | None   # the combo spell about to resolve (counter_window), else None
    targets: list        # bodies about to enter / be relied on (reanimate/resolve_threat)
    gy_cards: list        # GY contents the combo step depends on (gy_setup)
    meta: dict           # free-form (e.g. {"protected": True} if Ephemerate held)

@dataclass
class InteractionResult:
    disrupted: bool      # True if the combo step was answered
    detail: str          # for gs._log

def offer_interaction(combo_gs, combo_apl, opp_gs, opp_apl, event) -> InteractionResult:
    # 1. capability gate
    if not getattr(opp_apl, "WANTS_COMBO_INTERACTION", False):
        return InteractionResult(False, "no-interaction-opt-in")
    answer = opp_apl.answer_combo(opp_gs, combo_gs, event)   # (kind, card, target?) or None
    if not answer:
        return InteractionResult(False, "passed")
    # 2. APPLY the answer to the SHARED aliased zone lists (zone moves propagate; see spine #2)
    #    - "counter": move event.spell combo_gs.hand/stack -> combo_gs.graveyard; combo aborts step
    #    - "remove":  move target combo_gs.battlefield -> graveyard (or exile for exile-removal)
    #    - "gy_hate": exile relevant cards from combo_gs.graveyard (deny reanimation fuel)
    #    - "discard": move target combo_gs.hand -> graveyard (proactive; hand disruption)
    #    pay the answer's mana out of opp_gs.mana_pool; move the answer card opp hand -> gy/exile
    return InteractionResult(True, ...)
```

`answer_combo(self, my_gs, combo_gs, event)` on the opted-in APL inspects MY hand + untapped mana
and returns an answer keyed off `event.kind`, or `None` to pass:
- `counter_window` -> a counterspell + matching open mana -> `("counter", card)`
- `reanimate` / `resolve_threat` -> an instant-speed kill that can handle `event.targets[0]`
  (respect `MATCH_REMOVAL` `max_tgh`; exile-removal for indestructible/huge bodies) ->
  `("remove", card, target)`
- `gy_setup` -> GY-hate in hand (Leyline of the Void / Relic of Progenitus / Endurance /
  Bojuka Bog) -> `("gy_hate", card)`
- `discard` -> a discard spell on our (proactive) turn naming their combo piece -> `("discard", card, piece)`

### What the layer uniquely owns (and what it does NOT)
- **OWNS:** (a) the combo "checkpoint" window at the decisive step; (b) GY-hate (no existing seam
  for it anywhere); (c) the damage-channel discipline for drain/direct kills (Component 2 + the
  per-deck `gs.damage_dealt` rerouting).
- **DOES NOT duplicate:** our spot removal on opp bodies (`_match_cast_removal` already does this
  on our turn) or counters on cast spells (the `cast_spell -> try_counter_spell / run_priority_stack`
  window already works -- so routing Goryo's / Living End / Persist THROUGH `gs.cast_spell` earns
  the counter window for free for any counter-bearing opponent, no new layer code needed).

### CRITICAL constraint on the three G1 gates (advisor item 2)
Our gauntlet deck is `boros_energy_lowcurve_modern` and the gauntlet models GAME 1, where Boros has
burn + an aggressive clock + ~ZERO maindeck GY-hate, counters, or discard. Therefore **GY-hate,
counters, and hand disruption CANNOT be load-bearing for the grixis/goryos/broodscale gates.**
They are built in the layer for GENERALITY (Bo3 SB games, future interaction decks), but the gate
numbers must EMERGE from `removal + race + the combo's intrinsic fragility` (see Component 5). If a
gate only lands because we lean on GY-hate that maindeck Boros does not have, that is the
reverse-fit trap -> STOP.

---

## Component 2 -- The cheap engine fix (lands FIRST; prerequisite)

The mp1/end-step `damage_dealt` discard. **mono_red and ruby_storm are DISTINCT sites -- do not
write "the same bug."**

- **Site 1 (mp1 gate generalization):** `_simple_play_turn` L276 syncs `view.damage_dealt` only when
  `apl.WANTS_STORM`. Generalize to `WANTS_STORM or WANTS_BURN` (new flag). This is the mono_red fix
  (mono_red deals face burn in mp1 but lacks WANTS_STORM, so its ~6.1 dmg/game is dropped).
- **Site 2 (end-step propagation, NEW -- CONSTRUCTION GATED, may be dropped):** `_run_end_step`
  (L1468+) propagates NO `damage_dealt` at all. CRITICAL SEAT CORRECTION (R2): `end_step_actions`
  fires on the REACTIVE player -- `view` is the reactive seat (L1502-1554), `opp_view` is the active
  seat. There is no "active-player view.damage_dealt" here. So IF Site 2 is built, it syncs the
  REACTIVE player's `view.damage_dealt` delta to the ACTIVE player's match life total after
  `end_step_actions`, gated on the REACTIVE APL's `WANTS_STORM or WANTS_BURN`. This models an
  instant-speed burn/drain finish cast in the opponent's end step.
  **Construction gate:** Site 2 is built ONLY if the Step 2.0 diagnostic identifies a deck in scope
  whose kill actually lands at the opponent's end step. As of this writing NO modeled combo does
  (storm/belcher/yawgmoth kill on their own active main phase, carried by Site 1; cascade dects kill
  in combat). If the diagnostic finds none, Site 2 is DROPPED -- do not build unvalidated dead code.
  The end_step SEAM is still used by cascade decks for TIMING (zone-move reanimation, spine #2); that
  is orthogonal to Site 2 and needs no damage propagation.
- **Gating / invariant (cell-granular, R1-correct):** byte-identical for any cell whose BOTH decks
  set neither flag. A cell MAY move iff at least one of its two decks is `WANTS_BURN`/`WANTS_STORM`.
  (Site 1 gates on the ACTIVE apl's flag at L276, so flagging mono_red moves mono_red's ENTIRE
  seat-A row against the field in a round-robin run -- that is expected, not a leak. The single-cell
  framing was wrong.) Un-flagged burn decks remain latent (tracked in IMPERFECTIONS).

**ruby_storm is a HYPOTHESIS, not a fact (advisor item 3).** ruby_storm ALREADY sets
`WANTS_STORM=True`, so its mp1 IS synced today -- yet it wins 0/50. So Site 1 cannot be its fix.
Its residual is the end-step channel (Site 2) and/or payoff reachability (Grapeshot is SB/Wish-only;
Galvanic Relay is a two-turn stored-spell line). **Step 2.0 is a diagnostic-first probe** that
instruments WHY ruby_storm is 0/50 before asserting Site 2 closes it. Write "fix unblocks ruby_storm"
as a hypothesis the diagnostic confirms; if the diagnostic shows the residual is payoff reachability,
that becomes ruby_storm's per-deck work (Component 3), not the engine fix's job.

**Why #2 is foundational beyond mono_red:** every drain/direct-damage combo (yawgmoth, belcher,
non-combat neoform/neobrand lines, ruby_storm) kills through `gs.damage_dealt`, which Site 1/Site 2
+ `WANTS_BURN` are what make visible to the match life total. Combat-kill combos (grixis, goryos,
living_end, broodscale) do NOT need #2 for their clock (combat already counts via `_resolve_combat`).

---

## Component 3 -- Per-deck assembly + answerability, split by KILL CHANNEL

Each combo's work is "make it assemble reliably" + "make it answerable." The kill channel decides
whether Component 2 + a `gs.damage_dealt` reroute is required.

### Combat-kill combos (damage already counts; #2 NOT required)

These put bodies on the battlefield; `_resolve_combat` reads them. Work = reliable assembly +
intrinsic fragility + our removal answering it.

- **grixis_reanimator** -- HIGH leverage; the INVERTED anchor (sim ~75% favored per
  `mismodeled_matchups.py`, primer 38 -> we should be the dog; a ~37-pt swing). Crash already fixed;
  combo fires 41/50. Work: (1) at the decisive Persist / Oculus / hardcast-Archon step, call
  `offer_interaction(... kind="resolve_threat"/"gy_setup")` so an opted-in opponent can answer;
  (2) model the threat's INTRINSIC profile honestly, anchored to the DECKLIST (not free knobs):
  the Oculus/Archon threat mix = the actual copy-counts in `decks/grixis_reanimator_modern.txt`;
  the Thoughtseize hit-rate = hypergeometric P(>=1 Thoughtseize seen by the assembly turn) from the
  decklist count, modeled as STRIPPING our removal card from our hand (an engine-scored effect).
  Card profiles from oracle: Oculus is a 2/2 (Bolt kills), hardcast Archon is a 6/6 (Bolt CANNOT
  kill -> exile/`None` removal only).
  **CRITICAL (R-numberforce-3):** "Oculus draws a card every upkeep" is NOT a lever in this
  combat/life model -- drawing cards advances no clock the engine scores. The 37-pt inversion MUST be
  carried entirely by ENGINE-SCORED mechanisms: (a) Archon 6/6 surviving our Bolt (exile-only
  answer), (b) the reanimated body recurring (Persist/second copy), (c) Thoughtseize removing our
  answer from hand. If those modeled mechanisms stall short of the band (e.g. land us at ~55 instead
  of [25,45]) -> Stop condition 2: grixis STAYS FLAGGED in `mismodeled_matchups.py`, NOT tuned into
  the band by adding card-draw credit. Do NOT add GY-hate to "help" -- maindeck Boros has none.
  Effort: ~1 session.
- **goryos_vengeance** -- HIGH leverage (primer 73, favored). Today the APL leaves the reanimated
  body PERMANENT even without Ephemerate -- too strong. Work: (1) model Goryo's self-exile at end
  step UNLESS Ephemerate is held -- and P(Ephemerate held) is DERIVED from the decklist (hypergeometric
  P(>=1 Ephemerate in hand by the firing turn given copy-count + cards seen), NOT a dialed frequency);
  (2) require a real GY setup (discard via Psychic Frog / Thoughtseize loot, or a mill) before firing,
  instead of assuming the target is in GY; (3) route Goryo's through `gs.cast_spell` so a
  counter-bearing opponent gets the window for free; (4) `offer_interaction(kind="resolve_threat")` on
  the reanimated body. Add a `main_phase2_match` so `_cast_all_castable` stops blind-casting.
  **Effort: ~1.5-2 sessions (re-estimate, R-feasibility).** Per spine #4, Goryo's currently MOVES
  zone cards manually and bypasses `gs.cast_spell` entirely; converting a manual-reanimation line into
  a cast_spell-routed spell (so the counter window fires) is a REANIMATION-MECHANIC REBUILD, not a
  wiring tweak. This is the heaviest of the five sub-items and was previously glossed.
  If the modeled self-exile fragility + removal cannot pull the cell into band, Stop condition 2:
  goryos stays flagged rather than tuned.
- **living_end** -- MEDIUM (inflated ~96, no primer). SEAM CORRECTION (R-feasibility): the real line
  is INSTANT-speed cascade (Violent Outburst at the opponent's EOT), which belongs in
  `end_step_actions`, NOT a sorcery-speed `main_phase2_match`. Work: (1) in `end_step_actions`,
  block the illegal sorcery-speed hardcast of the CMC-0 Living End that `_cast_all_castable` does,
  and fire the cascade ONLY via the gate (cascade_in_hand AND avail>=3 AND gy_cyclers>=2);
  (2) route the cascade spell through `gs.cast_spell` (counter window for free); (3)
  `offer_interaction(kind="gy_setup")` BEFORE Living End returns creatures (GY-hate checkpoint --
  general, not load-bearing for a Boros G1 gate). The kill is COMBAT (reanimated team), so NO Site 2
  / no `WANTS_BURN`. Effort: ~0.75 session (re-estimate; instant-speed seam + cascade gate is more
  than the ~0.5 billed).
- **temur_crashcade** -- MEDIUM, NEWLY IN SCOPE (R-missing). A NEW Violent-Outburst cascade combo,
  documented in `mtg-sim/CLAUDE.md` as a synthetic stub that "plays as a generic creature/tempo deck
  ... NOT primer-validated, promote before trusting" -- structurally IDENTICAL to living_end and the
  same class of mismodel. Same treatment: instant-speed cascade in `end_step_actions`, block the
  sorcery-speed hardcast, route the cascade through `gs.cast_spell`, `offer_interaction(kind="gy_setup")`
  checkpoint, COMBAT kill (no Site 2). It is in `mismodeled_matchups.py`-adjacent territory; add a
  flag entry if its cell is materially wrong. Effort: ~0.5 session (rides living_end's pattern).
- **gruul_broodscale** -- MEDIUM-HIGH (primer 55). Today a documented synthetic creature stub.
  Work: model the assembly (dork T1 -> Broodscale + Glaring Fleshraker + Grumgully payoff,
  +1/+1-counter / Eldrazi-Spawn loop). The board size, assembly turn, and body P/T are NOT free
  knobs: assembly turn comes from a MEASURED goldfish kill-turn distribution of the broodscale deck;
  body count/P-T come from oracle stats + the modeled loop output. Keep the kill in COMBAT (go-wide).
  Answerability: the pieces (Broodscale, Fleshraker, Grumgully) are removable creatures -> multiple
  `offer_interaction(kind="resolve_threat")` checkpoints. If the modeled loop + our removal does not
  land the cell in [45,65], Stop condition 2: stays flagged. Effort: ~1 session.

### Drain / direct-kill combos (#2 + `gs.damage_dealt` reroute REQUIRED)

- **yawgmoth** -- RE-SCOPED (advisor item 1): the audit's "cheap 1-2h list-align" is NECESSARY but
  NOT SUFFICIENT. Yawgmoth's entire kill is DRAIN (`opponent.life -= 1` per death), which is a
  no-op on the match life total (spine #3). Work: (a) align lists to the actual deck variant
  (the deck is the Agatha's Soul Cauldron / Walking Ballista build: ZERO Blood Artist/Zulaport;
  fix `DRAINS`, add Strangleroot Geist to `UNDYING`, add the Cauldron/Ballista lethal branch:
  Ballista power >= opp life); (b) REROUTE the drain/Ballista damage through the active player's
  `view.damage_dealt` so #2 + `WANTS_BURN` makes it visible. Set `WANTS_BURN=True`. Effort: ~0.5-1
  session (was billed 1-2h; the reroute is the extra).
- **ruby_storm** -- CHEAP, post-#2. After the Step 2.0 diagnostic: if end-step (Site 2) is the
  fix, set `WANTS_BURN` and confirm; if payoff reachability is the issue, make Grapeshot / Galvanic
  Relay reachable in the modeled list and sequence the storm count. Payoff already routes through
  `gs.cast_spell` (R3 rewrite). Effort: ~0.5 session.
- **neoform** -- MEDIUM rebuild. Replace the AUTO_GENERATED flat-+2-face approximation with the
  real Summoner's Pact -> Allosaurus + Neoform -> Griselbrand line. **KILL-CHANNEL SPIKE FIRST
  (R-feasibility):** Griselbrand itself deals NO damage -- the #2-dependency and the `WANTS_BURN`
  flag are UNKNOWN until the actual lethal line is pinned. Sub-step 0: decide and document the
  finish -- combat body (transformed/attacking -> combat channel, NO #2) vs a tutored burn/drain
  spell (-> `gs.damage_dealt` + `WANTS_BURN`), and confirm that spell is in the modeled list. Only
  then build. Effort: ~0.5-1 session (+ the spike).
- **temur_breach** -- MEDIUM. Currently a `GenericAPL` shim (`apl/temur_breach.py`). Author a
  dedicated `TemurBreachMatchAPL` with `WANTS_STORM` + ritual->storm-count sequencing; make the
  Grapeshot / Empty the Warrens payoff reachable (currently SB/Wish-only). Direct-damage channel.
  Effort: ~0.5-1 session.
- **belcher** -- MEDIUM-HIGH full rebuild (re-estimate up, R-feasibility). Today a landless stub
  with an EMPTY mana pool (cast_spell True = 0/50). The match view injects mana from LANDS on the
  battlefield ONLY (`_build_view` / `_run_end_step` build `mana_pool` from `is_land()` cards), so
  this needs THREE bespoke pieces, none of which are wiring tweaks: (1) Elvish/Simian Spirit Guide
  exile-for-mana HAND-INJECTED by the APL (no engine support); (2) a custom Goblin Charbelcher
  activated-ability kill (mill-until-nonland; damage = cards revealed) routed through
  `gs.damage_dealt` + `WANTS_BURN`; (3) Sea Gate Restoration MDFC land-face drops. A from-scratch
  landless ritual combo with a bespoke kill ability. **Effort: ~1.5-2 sessions** (was billed 1; the
  bespoke kill ability + hand-injected mana are the under-budgeted parts).
- **neobrand** -- MEDIUM full rebuild (T1-2 combo). Needs Summoner's Pact -> Allosaurus Shepherd ->
  Neoform -> Griselbrand sequencing and the Pact upkeep-trigger failure mode. **Same KILL-CHANNEL
  SPIKE as neoform (R-feasibility):** Griselbrand deals no damage; what deals lethal (combat body vs
  a tutored burn finish that may not be in the modeled list) must be pinned in sub-step 0 before the
  #2-dependency and `WANTS_BURN` flag are decided. Effort: ~1 session (+ the spike).
- **landless_belcher** -- LOW; currently UNCOVERED (`get_match_apl('landlessbelcher')` is None;
  absent from `auto_apl_registry.json` -- failed the smoke gate). REGISTRATION REQUIRED, not just an
  alias (R-missing): the key must be added to `MATCH_APL_REGISTRY` or `get_match_apl` keeps returning
  None. FIDELITY CAVEAT: the deck is GENUINELY landless, but the rebuilt `belcher` ADDS Sea Gate MDFC
  land-face drops, so a blind alias `landless_belcher -> belcher` MISREPRESENTS the landless variant.
  Either author a thin landless variant (no Sea Gate land drops) or alias-with-documented-caveat in
  IMPERFECTIONS. Effort: ~0.5 session (after belcher).

### Leverage order (cheapest/highest-impact first)
1. **#2 engine fix** (prerequisite; unblocks every drain/direct combo). 2. **yawgmoth** (cheap
list-align + reroute; currently undocumented + 0/50). 3. **ruby_storm** (diagnostic + #2 confirm).
4. **grixis_reanimator** (the INVERTED anchor; first real interaction-layer consumer). 5.
**goryos_vengeance** (favored primer cell; self-exile fragility; heaviest single deck). 6.
**gruul_broodscale** (primer 55; model the loop). 7. **living_end** (instant-speed cascade gate).
8. **temur_crashcade** (rides living_end's pattern). 9. **neoform** (channel spike first). 10.
**temur_breach**. 11. **belcher** (heaviest rebuild). 12. **neobrand** (channel spike first). 13.
**landless_belcher** (register + caveat). (13 decks; temur_crashcade added in rev 2.)

---

## Component 4 -- No-regression strategy

### Two drivers, two distinct proofs (R1 -- the methodology fix)
The previous "every cell except the edited one stays unchanged" claim was FALSE under the
round-robin `full_field_gauntlet` (L122-127: it runs BOTH `a-vs-b` and `b-vs-a`, so every deck pilots
seat A in its own row; editing a combo APL moves its WHOLE seat-A row, not one cell). The proof is
therefore split across the two drivers by what each can actually assert:

- **PRIMARY proof = single-hero `run_match_set`** (`engine/match_runner.py` L1687; L1719-1743:
  apl_a is ALWAYS seat A, apl_b ALWAYS seat B, `mix_play_draw` only alternates the play, NOT the
  seats). Run boros (seat A) vs each opponent (seat B). Here a combo APL is structurally ONLY EVER
  the opponent, so editing it can only move the single `boros-vs-<combo>` result. This is the driver
  the per-deck combo no-regression check (4.4) and the Component 5 gates run on. Assertion contract:
  the combo deck NEVER pilots seat A in this sweep (assert it appears only as apl_b).
- **SECONDARY read = round-robin `full_field_gauntlet`** (field-health only). Here the invariant is
  CELL-GRANULAR, not "one cell": a cell `X-vs-Y` may move iff X or Y was edited/flagged; all cells
  whose BOTH decks are untouched stay byte-identical.

### What must stay byte-identical (the non-combo field)
1. **Capture locks at the PRE-#2 commit (do NOT trust cited numbers).** Before any code, run BOTH
   the single-hero sweep (boros seat A vs the modeled field) AND the round-robin
   `full_field_gauntlet` at a pinned seed + n + workers, and SAVE the per-cell `a_wins`. The cited
   locks (selesnya-vs-prowess 60.7%, borosenergy-vs-affinity 88.5%, CLAUDE.md's 65.3% Selesnya)
   disagree -- so the lock is the ACTUAL measured value at the pre-#2 commit, whatever it is, not a
   remembered figure.
2. **Interaction layer (Component 1): per-cell 0.00pp on EVERY cell, both drivers.** The layer is
   inert until a combo APL calls `offer_interaction`, so after Phase 1 BOTH gauntlets must be
   byte-identical to the lock (same seed/n/workers -> identical a_wins per cell). Any non-zero delta
   anywhere means the gating leaked -> STOP (Stop condition 1).
3. **Engine fix (Component 2): cell-granular invariant.** A cell `X-vs-Y` may move iff X or Y sets
   `WANTS_BURN`/`WANTS_STORM`; every cell with BOTH decks unflagged is byte-identical. Concretely:
   only mono_red + the drain/direct combo opponents are flagged this handoff. Izzet Prowess and the
   Boros mirror are LEFT LATENT (R3 -- NOT flagged), so:
   - Validate mono_red moves to ~35-45% vs Boros (mono_red is flagged -> its seat-A row vs the field
     is expected to move; that is not a leak).
   - **selesnya-vs-prowess CANNOT move from #2** -- and now this is AUTOMATIC, not a hope: both decks
     are unflagged, so the cell-granular invariant forces byte-identical. If it moves, a flag leaked
     onto a creature-combat deck -> Stop condition 3.
   - Do NOT re-baseline Izzet Prowess / Boros mirrors here (removed from the list, R3); they stay on
     the pre-#2 lock.
4. **Per-deck combo edits (Component 3): one cell each, ON THE SINGLE-HERO SWEEP.** Because the
   per-deck proof runs on `run_match_set` with boros seat A / combo seat B, editing `GoryosMatchAPL`
   can only change the single `boros-vs-goryos` result. Proof: re-run the single-hero sweep after
   each combo commit; assert every OTHER boros-vs-X cell is unchanged vs the running lock.
   - If the round-robin gauntlet is ALSO re-run for field health after a combo edit, the assertion
     is the cell-granular one: the edited combo's WHOLE seat-A row (`<combo>-vs-field`) MAY move;
     every cell NOT involving that combo stays byte-identical. Do NOT assert "one cell" there.

### Locked baselines that must hold
- **selesnya-vs-prowess:** unchanged across the ENTIRE handoff (band [60, 71.5]; capture the actual
  pre-#2 value as the hard lock). With prowess left unflagged (R3), the cell-granular #2 invariant
  guarantees this for free; it must also not move from #1 or any combo edit.
- **borosenergy-vs-affinity:** unchanged by #2 and the interaction layer; RE-BASELINED only by
  handoff #3 (currently 88.5% sim; legacy 63.5% is an unverified target -- do not chase it here).

---

## Component 5 -- Validation gates (falsifiable, with per-gate mechanism)

All measured as OUR (boros_energy_lowcurve) win rate vs the combo as seat B, n>=300 seeded,
mix_play_draw, on the SINGLE-HERO `run_match_set` path (boros seat A / combo seat B), after the
interaction layer + that deck's assembly work, with `WANTS_COMBO_INTERACTION=True` on our APL.

### The one anti-number-forcing rule (collapses number-forcing risks #1 + #4)
Every gate -- primer AND directional -- is the OUTPUT of a function of OBSERVABLE inputs, never an
asserted number. The band is the output RANGE of that function under its input uncertainty. The test
to apply to each gate as it is written: *"is this number computed from the decklist / a measured
goldfish distribution / oracle stats, or is it asserted?"* If asserted -> it is reverse-fit. The
canonical form for a combo cell is:

```
our_WR  =  (1 - P_assemble) * race_baseline   +   P_assemble * P(we answer | assembled)
```
where:
- `P_assemble` and the assembly TURN come from a MEASURED goldfish kill-turn distribution of the
  combo deck (run it goldfish, record the distribution -- do NOT hand-pick it).
- `race_baseline` = our G1 win rate when the combo whiffs, from our own measured clock.
- `P(we answer | assembled)` is built from DECKLIST copy-counts via hypergeometric draws:
  P(removal-for-this-body in hand by turn T), P(they protected it: Ephemerate/Thoughtseize seen),
  and the body's oracle P/T deciding whether our removal (`MATCH_REMOVAL` `max_tgh`) can even kill it.

If the computed value sits outside the primer band, that is a FINDING about the model (or the primer),
resolved by Stop condition 2 -- NOT by dialing any input toward the target.

| Cell | Computed gate (our WR) | Primer | Inputs the number is a FUNCTION of (no free knobs) |
|---|---|---|---|
| grixis_reanimator | **25-45** | 38 | `P_assemble`/turn from goldfish dist; threat mix = Oculus/Archon COPY-COUNTS in the decklist; `P(Thoughtseize seen)` hypergeometric from copy-count; bodies' oracle P/T (Oculus 2/2 Bolt-killable, Archon 6/6 exile-only) deciding if our removal connects. Card-draw EXCLUDED (no engine-scored clock). We are the DOG because the assembled body resists our one removal + Thoughtseize strips it. |
| goryos_vengeance | **65-80** | 73 | `P_assemble`/turn from goldfish dist (gated on a real GY setup); `P(Ephemerate held)` hypergeometric from Ephemerate copy-count + cards seen by the firing turn; self-exile-at-EOT making the lone body fragile to one removal OR one turn of patience; our removal-in-hand probability + clock. Favored because the body self-exiles unless protected. |
| gruul_broodscale | **45-65** | 55 | `P_assemble`/turn from goldfish dist; board size + body P/T from the modeled loop output + oracle stats (NOT dialed); removal-checkpoint count = our removal density vs their body count. Roughly even: go-wide resists single removal but the pieces are individually killable. |

### Directional cells -- ALSO computed, ALSO falsifiable (Rule 5 fix + number-forcing #4)
"No primer truth" does NOT mean "no band." Each directional cell uses the SAME
`(1-P_assemble)*race_baseline + P_assemble*answer_rate` formula; the band is the function's output
range, giving a real floor AND ceiling that can FAIL:

- **living_end:** computed band **[45, 85]** (down from inflated ~96). FAILS HIGH (>85) -> cascade
  still under-fires (assembly P too low) or the GY-hate checkpoint is a no-op; FAILS LOW (<45) ->
  over-credited the reanimated team. `P_assemble` from the goldfish cascade-fire rate; answer side =
  our race vs the returned team (combat, no Site 2).
- **temur_crashcade:** computed band **[45, 85]** (same family/formula as living_end).
- **ruby_storm:** computed band **[3, 35]**. FAILS LOW (<3) -> the damage channel still drops (Site 1 /
  payoff reachability unresolved -- see Step 2.0); FAILS HIGH (>35) -> credited storm output the deck
  cannot reach G1. Both floor and ceiling falsifiable.
- **yawgmoth:** computed band **[55, 80]** AND two structural asserts: combo-fires >= 1/50 AND the
  drain/Ballista damage actually reaches the match life total (the #2 reroute works). FAILS LOW (<55)
  -> reroute or assembly broken; FAILS HIGH (>80) -> drain over-counted.

If any cell only reaches its band by editing the goldfish distribution, an assembly probability, or by
adding damage the deck does not deal -> Stop condition 2.

---

## Stop conditions (teeth)
1. **Gating leak:** if, after Phase 1 (interaction layer), ANY cell in EITHER driver (the single-hero
   sweep AND the round-robin full_field_gauntlet) deviates from the pre-#2 lock by >0.00pp at the same
   seed/n/workers -> STOP. The inert layer must be byte-identical everywhere; find the leak before any
   combo work.
2. **Reverse-fit trap (BROADENED, number-forcing #2):** if a calibration cell
   (grixis/goryos/broodscale) OR a directional cell lands OUTSIDE its computed band AND the only way
   to pull it in is to tune ANY assembly probability or frequency toward the target -- including
   (a) editing a kill-turn / goldfish distribution, (b) dialing an assembly/protection probability
   (P_assemble, P(Ephemerate held), P(Thoughtseize seen), broodscale body count), (c) adding damage
   the deck does not actually deal, or (d) making a Boros-G1-absent answer (GY-hate/counter/discard)
   load-bearing -> STOP. Do NOT pull the number. Keep that cell flagged in `mismodeled_matchups.py`,
   document the honest residual in IMPERFECTIONS, ship the rest. **Pre-committed honest-failure
   outcomes (so the band is not itself a forcing target):** grixis's 75->38 swing is carried ONLY by
   engine-scored mechanisms (Archon 6/6 exile-only, body recursion, Thoughtseize stripping our hand);
   if those stall at, say, ~55, grixis STAYS FLAGGED -- it is NOT tuned into [25,45]. Same
   pre-commitment for goryos and broodscale: a cell that cannot reach its band on modeled mechanism
   alone is left flagged, not forced.
3. **Lock break:** if selesnya-vs-prowess moves from #1/#2/any combo edit, or borosenergy-vs-affinity
   moves from #2 -> STOP; a gate generalization or layer hook leaked into a non-target cell.
4. **ruby_storm diagnostic disconfirms the hypothesis:** if Step 2.0 shows ruby_storm's 0/50 is
   payoff reachability (not the damage channel), do NOT claim the #2 fix "unblocks" it -- re-scope
   ruby_storm's closing into Component 3 and proceed.

Per harness Rule 4: a fired stop condition halts execution. Outcome is one of {bug found -> fix +
amend + resume; honest model improvement -> verify + amend + resume; unfalsifiable -> abort + write
IMPERFECTIONS + ship partial}.

---

## Component 6 -- Test re-pointing

The risk: `tests/test_grixis_reanimator_no_crash.py` routes grixis as seat B via
`get_match_apl("grixisreanimator")` + `run_match`. If a future change reroutes combo opponents
through a `ComboKillSampler` (or any adapter that never pilots the real APL), the test goes
TRIVIALLY GREEN -- a sampler never crashes and never exercises the Persist code.

Fixes:
1. **Assert the real APL pilots.** Add `assert isinstance(apl_b, GrixisReanimatorMatchAPL)` (NOT a
   sampler / GoldfishAdapter / RemovalAwareGoldfishAdapter) right after `get_match_apl`.
2. **Behavioral assertion that the combo actually fires.** Over the n games, assert the combo
   reaches the battlefield in >= 1 game (e.g., Oculus or a Persist-reanimated body appears on
   `bf_b`, or a per-APL `self._combo_fired`-style counter > 0). A silent sampler reroute -- which
   would 0/50 the combo-fires metric -- then fails the test.
3. **Mirror the no-crash test for every NEW/edited combo APL** (goryos, living_end, temur_crashcade,
   broodscale, yawgmoth, neoform, temur_breach, belcher, neobrand): a SIM_DEBUG=1 run that re-raises
   APL exceptions, asserting 0 crashes AND combo-fires >= 1/50. This catches the zone-move identity
   bugs (the Grixis `list.remove` family) that the swallow-and-fallback hides.
4. **Layer no-op test:** assert `offer_interaction` with `WANTS_COMBO_INTERACTION=False` returns
   `disrupted=False` and mutates nothing (guards the capability gate).
5. **Round-robin seat-A exposure test (R-missing).** The combo-fires>=1/50 assertion above runs on
   the single-hero boros-vs-combo path; it does NOT guard that editing a combo APL silently broke its
   OWN seat-A rows in the round-robin `full_field_gauntlet` (where the no-regression model is weakest).
   So for each edited combo APL, also run it AS SEAT A (combo vs at least one field deck) under
   SIM_DEBUG=1 and assert 0 crashes AND combo-fires >= 1/50 there too. A zone-move identity bug that
   only manifests when the combo pilots seat A is otherwise invisible to the seat-B test.

---

## Component 7 -- Sequencing + worktree note

Implementation runs SEQUENTIALLY in `mtg-sim` (branch `modern-postban-arc`). **NO worktrees:** the
session root is not a git repo, and downstream handoff #5 needs everything co-present in the one
working tree. Shared-engine edits are SINGLE-WRITER and land first, one commit each; per-deck APL
edits touch separate files (`apl/<deck>_match.py`) so they do not collide, but still run
sequentially (no parallel worktrees) with a full-gauntlet no-regression check after each.

Ordered execution:
0. Capture the pre-#2 lock on BOTH drivers (single-hero sweep + round-robin), Component 4.1.
1. **Component 2** -- engine fix. **Step 2.0 ruby_storm diagnostic FIRST** (also decides whether
   Site 2 is built at all). Then Site 1 (mp1 gate generalization, mono_red) + `WANTS_BURN`; build
   Site 2 (REACTIVE-seat damage -> active match life) ONLY if Step 2.0 found an end-step killer, else
   drop it. Flag ONLY mono_red + drain/direct combo opponents (NOT Izzet Prowess / Boros mirror, R3).
   Validate mono_red ~35-45; confirm the cell-granular invariant holds (every both-unflagged cell
   byte-identical -> selesnya-vs-prowess unchanged automatically). Commit.
2. **Component 1** -- `engine/combo_interaction.py` + `answer_combo` mixin + `WANTS_COMBO_INTERACTION`.
   Built inert (no combo APL calls it yet). Prove BOTH drivers byte-identical (Stop condition 1).
   Commit.
3. **Component 3, in leverage order:** yawgmoth -> ruby_storm -> grixis -> goryos -> broodscale ->
   living_end -> temur_crashcade -> neoform -> temur_breach -> belcher -> neobrand ->
   landless_belcher. After EACH: the deck's no-crash+combo-fires test (BOTH seat orientations,
   Component 6.5), that cell's computed gate (where it has one), the single-hero no-regression check
   (every OTHER boros-vs-X cell unchanged vs the running lock) + an optional round-robin field-health
   read with the cell-granular invariant. Commit per deck.
4. Update `mismodeled_matchups.py` (remove flags for cells now in-band; keep + annotate any that hit
   Stop condition 2). Update IMPERFECTIONS (resolve `combo-decks-not-sampled...` partially; close
   `yawgmoth-...`, `living-end-...`, `engine-mp1-damage-dealt-...`, `mono-red-...` as their slices
   land). Update `harness/knowledge/tech/mtg-sim-quality-grades.md`.

---

## Estimated time (rev 2 -- honest re-estimate after feasibility review)

- Component 2 (engine fix + ruby_storm diagnostic + Site-2 build/drop decision + dual-driver
  no-regression sweep): ~1 session.
- Component 1 (interaction layer + dual-driver gating proof + no-op test): ~0.5-1 session.
- Component 3 (13 decks):
  - grixis ~1; goryos **~1.5-2** (reanimation-mechanic rebuild -- manual-zone-move -> cast_spell);
    broodscale ~1.
  - yawgmoth ~0.5-1; ruby_storm ~0.5.
  - living_end ~0.75 (instant-speed seam); temur_crashcade ~0.5 (rides living_end).
  - neoform ~0.5-1 + channel spike; neobrand ~1 + channel spike; temur_breach ~0.5-1.
  - belcher **~1.5-2** (bespoke Charbelcher kill ability + hand-injected ritual mana); landless_belcher
    ~0.5 (register + caveat).
  - = ~10-11 sessions.

**Total: ~8-12 working sessions** (rev 2, up from the rev 1 ~6-9; the goryos reanimation rebuild and
the belcher from-scratch kill ability were under-budgeted, and temur_crashcade was missing entirely).
A FOCUSED slice (Component 2 + Component 1 + the three primer-gated cells + yawgmoth + ruby_storm) is
~5-6 sessions and delivers the headline: the three primer-gated cells made trustworthy + the cheap
fixes. The full rebuilds (belcher, neobrand, neoform, temur_breach) + cascade pair (living_end,
temur_crashcade) + landless_belcher are a separable second wave.

---

## Annotated imperfections (carried / expected to remain after this spec)
- **G1-only modeling:** all gates are Game-1 (the gauntlet has no maindeck GY-hate/counters/discard
  for Boros). The interaction layer supports those answer-types for generality, but they are
  unvalidated in Bo3 -- a future SB-aware spec is needed to trust sideboarded combo cells.
- **Un-flagged burn decks stay latent:** the `WANTS_BURN`-gated #2 fix leaves any direct-damage deck
  that does not opt in still discarding its mp1/end-step damage. Track which decks remain un-flagged.
- **Full-information G1:** combat/answer decisions still see perfect information (structural,
  `sim-no-hidden-information`); combo opponents may sequence around our known hand. Out of scope.
- **Any cell that hits Stop condition 2** stays flagged in `mismodeled_matchups.py` as an honest
  mismodel rather than reverse-fit -- expected for at least the hardest rebuilds if their assembly
  cannot be made faithful within budget.
- **dimir_oculus -- EXPLICITLY DEFERRED, not dropped (R-missing).** Audit row 18 flags it as a
  reanimator whose "manifest dread at each opp upkeep" engine is unmodeled (Oculus resolves as a
  vanilla 2/2). It is reanimator-adjacent but is NOT in this handoff's 13-deck list. Rationale for
  deferral: its payoff is a recurring card-advantage engine, which (like grixis's Oculus draw) has NO
  engine-scored kill pathway in the current combat/life model -- modeling it faithfully needs the
  same card-advantage-as-clock work that is out of scope here. Track as a follow-up; do not silently
  alias it to grixis.
- **glockulous -- bucketed in handoff #3, flagged here (R-missing).** Audit row 4 calls it a
  reanimator whose payoff never fires and a content-match to a registry-INVERTED Grixis Reanimator.
  Its DECK is an Izzet Affinity shell, so it lives in handoff #3 (Affinity) -- but the
  combo-relevant defect is its reanimator payoff, not the affinity clock. Noted here so #3 treats the
  reanimator half with this handoff's interaction-layer tooling rather than as pure affinity.
- **landless_belcher fidelity caveat:** if aliased to the rebuilt belcher (which adds Sea Gate land
  drops), the genuinely-landless variant is misrepresented; preferred path is a thin landless variant.
  Either way the `MATCH_APL_REGISTRY` key must be registered (currently `get_match_apl` returns None).

---

## Mid-execution Amendment 1 (2026-06-30) -- SPINE increment executed

Executed the SPINE ONLY (Component 2 Site 1 + Component 1 inert layer + the ruby_storm
Step-2.0 diagnostic). NO per-deck combo assembly; NO combo APL opts into interaction yet.
Branch `modern-postban-arc`. All numbers on the PRIMARY single-hero driver
`run_match_set` (boros seat A / opp seat B), n=500 seed=42 n_workers=1 mix_play_draw, against
the pre-#2 lock in `mtg-sim/data/combo_spine_baseline_2026-06-30.txt`.

### What landed
- **Component 2 Site 1 (engine fix).** `MatchAPL.WANTS_BURN = False` added next to the
  `WANTS_*` block. `match_runner._simple_play_turn` L276 gate generalized to
  `WANTS_STORM or WANTS_BURN`. `MonoRedMatchAPL.WANTS_BURN = True` (the ONLY deck flagged
  this increment -- not boros, not the anchors, not any combo opponent).
- **Site 2 (end-step propagation): DROPPED** per its construction gate. The Step-2.0
  diagnostic found NO in-scope deck that kills at the opponent's end step (ruby_storm casts
  Grapeshot exclusively on its own main phase; all other modeled combos kill on their active
  main or in combat). No dead code written. The end_step SEAM remains available for cascade
  TIMING (Component 3) -- that is orthogonal to Site 2 and needs no damage propagation.
- **Component 1 (inert interaction layer).** New `engine/combo_interaction.py`
  (`ComboEvent`, `InteractionResult`, `offer_interaction`, `AnswerComboMixin.answer_combo`),
  double-gated (structural: only a combo APL calls `offer_interaction`; capability:
  `WANTS_COMBO_INTERACTION`, default False everywhere). `MatchAPL.WANTS_COMBO_INTERACTION =
  False` added. `BorosEnergyMatchAPL` now inherits `AnswerComboMixin` but keeps the opt-in
  OFF -> behaviorally inert. New `tests/test_combo_interaction_inert.py` proves the layer is
  a no-op (gate-off + opted-in-pass both mutate nothing; Boros gate stays off).

### Step-2.0 ruby_storm diagnostic finding -> Stop condition 4 FIRED (re-scoped, not aborted)
Instrumented boros-vs-ruby_storm (N=200, baseline seeds). ruby_storm wins 1/200 (0.5%).
Grapeshot is cast in only 28% of games (1 maindeck copy; Wish-fetch is NOT modeled), and when
cast the storm count averages 1.98 (max 7) -> Grapeshot deals ~3 face dmg, NEVER near 20 (zero
one-shot-lethal casts). ruby_storm ALREADY sets `WANTS_STORM=True`, so the damage it DOES deal
already propagates via Site 1's gate (its baseline 496 is byte-identical post-fix, confirming
the generalization is a no-op for storm decks). **Conclusion: ruby_storm's ~0% is PAYOFF
REACHABILITY + storm-count sequencing, NOT the damage channel.** Per Stop condition 4, the #2
fix is NOT claimed to unblock ruby_storm; its closing is re-scoped into Component 3 (model the
Wish->Grapeshot/Empty fetch + maximal single-turn storm chain via Past in Flames / Ral). A
still-blocked ruby_storm with this documented reason is the accepted outcome (harness Rule 4:
honest-model outcome -> amend + proceed; NOT an abort).

### Validation results (run_match_set, n=500 seed=42 n_workers=1)
- **mono_red: 481 -> 395 a_wins (our_WR 96.20% -> 79.00%; mono_red WR 3.80% -> 21.00%).**
  Direction correct and MATERIAL (+17.2pp to mono_red). Instrumentation confirms avg 6.24 face
  dmg/game now reaches the match life total (matches the spec's ~6.1 dmg/game estimate) -- the
  engine fix is mechanically correct, NOT a bug. HOWEVER mono_red lands BELOW the predicted
  [35,45] band (21%). Per Stop condition 2 this is NOT tuned (no inflating mono_red's damage):
  the residual is boros's lifegain engine (Guide of Souls / Ocelot Pride) + boros's own clock
  absorbing the now-counted burn. Closing to [35,45] is per-deck CALIBRATION (mono_red full
  clock and/or boros lifegain modeling), out of scope for the spine. Documented as an honest
  residual; mono-red burn IMPERFECTION partially addressed (damage no longer dropped) but the
  cell is not yet in band.
- **8 non-combo anchors: byte-identical** to the lock (eldrazi_tron 192, uw_control 447,
  dimir_murktide 344, amulet_titan 384, humans 125, sultai_midrange 287, izzet_prowess 318,
  selesnya_vs_prowess 267). selesnya-vs-prowess unchanged (lock holds; Stop condition 3 not
  triggered). Held through BOTH phases (engine fix AND the inert layer, incl. boros now
  carrying the mixin as seat A in 7 cells).
- **ruby_storm: 496 byte-identical** post-fix (storm gate short-circuits the generalization).
- **Stop condition 1 (gating leak): NOT triggered** -- every cell that must be byte-identical
  is, at the same seed/n/workers, after the inert layer.
- Tests: `tests/test_combo_interaction_inert.py` PASS; `tests/test_grixis_reanimator_no_crash.py`
  PASS (50/50, no regression).

### Deferred to later increments (unchanged scope)
Component 3 per-deck assembly for all 13 decks; flipping `WANTS_COMBO_INTERACTION` on boros;
wiring `offer_interaction` callers; ruby_storm payoff-reachability fix; mono_red [35,45]
calibration. Site 2 remains dropped unless a future in-scope deck needs an end-step kill.

---

## Mid-execution Amendment 2 (2026-06-30) -- yawgmoth cell (Component 3, leverage #2)

Executed the yawgmoth per-deck cell. Branch `modern-postban-arc`. Commit `cf2cf32`
(`feat(apl): yawgmoth combo assembly + drain reroute (Cauldron/Ballista)`). All
match numbers on the PRIMARY single-hero driver `run_match_set` (boros seat A /
yawgmoth seat B), n=500 seed=42 n_workers=1 mix_play_draw, against the pre-#2 lock.

### Root cause (list mismatch -- the audit's "cheap list-align")
`decks/yawgmoth_modern.txt` is the Agatha's Soul Cauldron / Walking Ballista build
(xerk, MTGO Modern Challenge 2026-04-29). It runs **ZERO Blood Artist / Zulaport /
Geralf's Messenger**. The APL's `DRAINS = {Blood Artist, Zulaport}` and
`UNDYING = {Young Wolf, Geralf's Messenger}` named cards the list does not contain,
so `_check_combo_kill`'s `drain_on_board` was ALWAYS False and the combo fired
**0/50** (avg kill T8.9 = pure beatdown). Fixed: `UNDYING = {Young Wolf,
Strangleroot Geist}`, `DRAINS = set()` (no drain payoff in this variant),
`deploy_order` rebuilt from the real list (+Strangleroot, +Ballista). `_check_combo_kill`
rewritten for the actual kill: Yawgmoth + 2 undying + Cauldron on board + Ballista
reachable (board/GY) -> Cauldron grants Ballista's ping to the +1/+1-countered
undying bodies; the Yawgmoth sac-loop feeds unbounded counters -> lethal.

### Damage reroute (the part the audit's 1-2h estimate omitted)
The kill is DIRECT DAMAGE, so a scalar `opponent.life -= X` is dropped (spine #3).
Rerouted the combo damage AND the standalone Ballista pings through `gs.damage_dealt`
and set `WANTS_BURN = True`, so `_simple_play_turn` propagates it to the match life
total, mirroring `MonoRedMatchAPL`. A forced-board unit test proves >=20 routed via
`gs.damage_dealt` with `opponent.life` untouched.

### Measured result -- Stop condition 2 FIRED (stays FLAGGED, honest fail-low)
| metric | before | after |
|---|---|---|
| combo-fires (P_assemble) | 0/500 (0.0%) | 49/500 (9.8%) |
| our WR (boros) | 269/500 = 53.8% | 245/500 = 49.0% |
| avg game length | T8.85 | T8.36 |

Both **structural asserts PASS**: combo-fires 49/500 >= 1/50, and the reroute reaches
match life (our WR drops 53.8% -> 49.0% as the combo converts games to boros losses;
forced-board test confirms the channel). **But the cell FAILS LOW** (49.0% < band
floor 55) and **CANNOT be brought into [55,80] by any faithful work**: our no-combo
`race_baseline` is already ~53.8% because the APL plays as an over-strong generic
creature deck (yawgmoth wins ~46%/game on COMBAT with NO combo). Combo assembly is
monotonic-DOWN on our WR (it only ADDS yawgmoth win conditions), so 53.8% is a
CEILING -- the now-correct combo can only lower it. The spec's [55,80] was computed
assuming a high race_baseline the measured data contradicts; the binding constraint
is the combat model, not assembly. Per Stop condition 2 the cell is **LEFT FLAGGED**
in `mismodeled_matchups.py` (new `yawgmoth` entry, DEFLATED) rather than tuned --
re-modeling yawgmoth's beatdown (same "synthetic-creature-stub over-credits combat"
class as broodscale / temur_crashcade) is OUT OF SCOPE here. This is harness Rule 4
honest-model outcome (amend + proceed), not an abort.

### Interaction decision: LEFT OFF (instruction-compliant, not load-bearing)
Boros maindeck carries 2x Thraben Charm, whose mode 3 ("Exile any number of target
players' graveyards") could snipe Walking Ballista from the yard and deny the Cauldron
line -- a genuine G1 answer, noted honestly. It is NOT wired: it is situational (one
of three charm modes), redundant-combo-resilient (4 Cauldron + 3 Ballista + Malevolent
Rumble refills), and making G1 interaction load-bearing is forbidden (Component 1
Critical-constraint + Stop condition 2). The ceiling argument also shows even a generous
Thraben Charm model cannot reach the band. `WANTS_COMBO_INTERACTION` stays False on
boros, so `offer_interaction` is not wired for yawgmoth and every OTHER combo cell's
byte-identical guarantee (boros seat A, no opt-in) holds trivially.

### Validation
- 8 non-combo anchors **byte-identical post-edit** (re-ran eldrazi_tron 192, humans 125,
  uw_control 447 -- all match the lock). Edits are isolated to `apl/yawgmoth_match.py`;
  WANTS_BURN on yawgmoth only affects cells where yawgmoth is the active seat.
- `tests/test_yawgmoth_combo_fires.py` PASS: forced-board reroute proof + 4 missing-piece
  negative cases + combo-fires >= 1/50 in BOTH seat orientations (seat B 7/50, seat A
  4/50 vs uw_control), SIM_DEBUG=1 (0 crashes, incl. yawgmoth piloting seat A).
- `tests/test_grixis_reanimator_no_crash.py` PASS (50/50, no regression).

### IMPERFECTION
The `yawgmoth-combo-drain-list-mismatch` imperfection is RESOLVED for its literal scope
(list aligned + combo assembles + damage reaches life). A NEW residual remains: the
yawgmoth APL over-credits generic creature combat (race_baseline ~53.8%), keeping the
cell below the [55,80] band. Tracked via the new `mismodeled_matchups.py` yawgmoth entry.

---

## Mid-execution Amendment 3 (2026-06-30) -- grixis_reanimator cell (Component 3, leverage #4; FIRST interaction-layer consumer)

Executed the grixis_reanimator per-deck cell -- the INVERTED anchor and the first cell to
turn `WANTS_COMBO_INTERACTION` ON. Branch `modern-postban-arc`. All match numbers on the
PRIMARY single-hero driver `run_match_set` (boros seat A / grixis seat B), n=500 seed=42
n_workers=1 mix_play_draw, against the pre-#2 lock + the post-Amendment-2 cell values.

### Root cause of the inversion (NOT assembly, NOT the crash)
The crash (`list.remove`) was already fixed and the combo assembled, but the reanimated
threat was UNDER-CREDITED to the point of inversion (sim ~69-75% boros vs primer ~38% dog):
1. **The Archon's recurring ATTACK trigger was dropped ENTIRELY.** `declare_attackers` is
   NEVER called on the run_match path (combat is resolved by `_resolve_combat` reading
   bodies -- spine #1), so the Archon's brutal on-attack trigger (sac + discard + 3 life)
   never fired. The body acted as a vanilla beater. Diagnosed: Archon ETB fired 0.09x/game.
2. **The reanimated body was usually a vanilla Oculus, not the Archon.** The engine Persist
   picks max-cmc but the APL seldom seeded the Archon into the GY; the brutal payoff came
   online in only ~28% of goldfish-capable games.
3. **The 3-life drain was a no-op** -- a scalar `opponent.life -= 3` on the per-turn view is
   dropped (spine #3).
4. **Thoughtseize stripped the wrong card** (max-cmc, not our removal).

### What landed (apl/grixis_reanimator_match.py -- Part A, the threat model)
- **Recurring Archon attack trigger** fired in `main_phase_match` step 4b for each Archon that
  will attack this turn (untapped, not summoning-sick), once-per-turn guarded. The body's
  combat damage still resolves in `_resolve_combat`; this adds only the trigger rider.
- **3-life drain routed through `gs.damage_dealt`** (active main-phase-1 channel) and made
  visible by `WANTS_BURN = True` on grixis -- the same channel + flag the yawgmoth cell uses.
  Affects ONLY cells where grixis is the active seat; in the single-hero sweep grixis is seat
  B only, so the only cell `WANTS_BURN` can move is boros-vs-grixis (verified byte-identical
  for all 10 non-grixis cells below).
- **Archon made the reliable recurring threat:** Unmarked Grave now FETCHES the Archon
  specifically; Faithless Looting PITCHES a hand Archon into the bin; a new identity-safe
  Reanimate path returns it as a full 6/6; the body recurs after our DESTROY-only removal
  (only exile -- which maindeck Boros lacks -- permanently answers it). The actual reanimated
  body is detected by battlefield-identity diff (the pre-fix code guessed and missed, firing
  the ETB on ~9% of reanimations).
- **Thoughtseize / Inquisition strip OUR removal** (Galvanic Discharge / Thraben Charm / Bolt)
  preferentially -- an engine-scored hand-disruption effect, off the actual copy-counts.
- Card-draw EXCLUDED as a lever throughout (the Archon's own draw stays on the grixis view,
  not credited as a clock; no `WANTS_*` for it).

### What landed (apl/boros_energy_match.py -- Part B, the honest 'out')
- `WANTS_COMBO_INTERACTION = True` + an `answer_combo` override modeling Boros's ACTUAL
  maindeck answers (Thraben Charm if >=3 creatures; Galvanic if energy visible; Bolt only vs
  toughness<=3; Thraben mode-3 GY exile for GY_SETUP). INTENTIONALLY WEAK and NON-LOAD-BEARING.
- grixis calls `offer_interaction(kind=RESOLVE_THREAT)` at the reanimation/hardcast step.

### Measured result -- Stop condition 2 FIRED (stays FLAGGED, honest stall-high)
| metric (seed=42 n=500) | before | after |
|---|---|---|
| our WR (boros) | 347/500 = 69.40% | 275/500 = **55.00%** |
| avg game length | T6.55 | T6.38 |
| P_assemble (Archon online) | ~6% | ~32% |
| grixis win \| Archon online | -- | **82%** (the named mechanisms work) |
| grixis win \| NOT online (race_baseline) | -- | boros ~73-77% |
| interaction fires (disrupted) | n/a | **1-3 / 500** (G1 honesty: NON-load-bearing) |

The cell improved 69.4% -> 55.0% (-14.4pp toward the primer 38), the swing carried ENTIRELY by
engine-scored mechanisms. Attribution (grixis WANTS_BURN=False isolation run): the 3-life DRAIN
credit contributes only ~1.8pp (56.8% -> 55.0%); the BULK is the recurring Archon attack trigger
(sac+discard) + the body recurring through our destroy-only removal + the Archon being the reliable
reanimation target + Thoughtseize stripping our answer. **But it FAILS HIGH (55.0% > band ceiling
45)**, and the binding constraint is ASSEMBLY FREQUENCY, not the threat model. The deck's faithful
GOLDFISH assembly (APL `keep()`, measured) is **~56%** Archon-online vs the MATCH's ~32%. The gap
is part (a) `run_match`'s CRUDE inline mulligan (mull-if-<2-lands, NOT the APL's combo-aware
`keep()`), part (b) the routed `decks/grixis_reanimator_modern.txt` being a 66-card `audit:stub`
(6 over 60), and part (c) LEGITIMATE boros pressure (racing/removing grixis before it assembles --
which is part of the matchup, not an artifact). A back-of-envelope `boros = 0.73 - 0.55*P_assemble`
(coeffs measured AT P~0.32) would put boros in the low 40s at the goldfish rate -- but that
counterfactual is UNVERIFIED (the coeffs almost certainly shift under a different mulligan, and (c)
is not removable). What IS verified: the measured 55.0%, the 82%-when-online mechanism, and the
non-load-bearing interaction. Per Stop condition 2(b) the cell is **LEFT FLAGGED**
(`mismodeled_matchups.py` grixis entry updated: INVERTED-improved, sim ~55%, documented residual)
rather than tuned by dialing P_assemble. This is exactly the spec's pre-committed honest-failure
outcome ("if those stall at, say, ~55, grixis STAYS FLAGGED"). harness Rule 4 honest-model outcome
(amend + proceed), not an abort.

NOTE (deviation from the written plan, surfaced explicitly): the spec lists grixis as combat-kill,
"#2 NOT required." This cell ADDS `WANTS_BURN = True` to grixis to credit the Archon ETB/attack
trigger's 3-life DRAIN (direct damage) via Site 1's `gs.damage_dealt` channel -- otherwise the
scalar `opponent.life` write is dropped (spine #3). It is a faithful credit of an oracle effect,
contributes only ~1.8pp, and affects ONLY the boros-vs-grixis cell (grixis is seat-B-only in the
single-hero sweep; all 10 non-grixis cells verified byte-identical), so it neither breaks
no-regression nor changes the flagged outcome -- but it IS a departure from the combat-kill framing
and is called out here for the spec author.

### Interaction decision: ON but honest (instruction-compliant, NON-load-bearing)
`WANTS_COMBO_INTERACTION = True` on Boros, but `answer_combo` fires only ~1-3/500 G1 because
Boros's cheap burn cannot kill a 5-6 toughness reanimated body, accumulated energy is not
visible in the reactive window, and there is NO maindeck graveyard hate (Rest in Peace /
Surgical Extraction are SB-only). Even when it removes the Archon, the body recurs (our removal
destroys, it does not exile). The band is reached by the threat's intrinsic fragility, never by
our interaction -- documented G1 honesty per Component 1's critical constraint.

### No-regression (CRITICAL this cell: boros flag flips ON)
The double gate holds: `offer_interaction` is only ever CALLED by grixis this handoff, so
flipping `WANTS_COMBO_INTERACTION` ON for Boros disturbed NOTHING else. Verified BYTE-IDENTICAL
at seed=42 n=500 (boros seat A, flag ON) for all 10 non-grixis cells:
eldrazi_tron 192, uw_control 447, dimir_murktide 344, amulet_titan 384, humans 125,
sultai_midrange 287, izzet_prowess 318, selesnya_vs_prowess 267 (Stop condition 3 NOT triggered),
ruby_storm 496, yawgmoth 245 -- every value matches its lock. Stop condition 1 NOT triggered.

### Tests
- `tests/test_grixis_reanimator_no_crash.py` PASS (50/50, SIM_DEBUG=1).
- `tests/test_combo_interaction_inert.py` UPDATED + PASS (boros gate assertion flipped to True;
  the layer-no-op guarantees still proven against synthetic gate-off / opted-in-pass APLs).
- Component 6.5 seat-A exposure: grixis piloting SEAT A vs uw_control, SIM_DEBUG=1, 50 games:
  0 crashes, combo-fires 83 (>= 1/50). The new identity-safe Reanimate/Looting manual moves
  do not regress the `list.remove` family.

### IMPERFECTION
NEW residual: `grixis-reanimator-match-assembly-capped-by-crude-mulligan` -- the faithful threat
model is correct (82% when online) but match P_assemble (~32%) is capped well below the deck's
goldfish assembly (~56%) by run_match's inline mulligan + the 66-card stub list, so the cell stays
inverted-but-improved (boros ~55% vs the ~42% it would reach at the goldfish rate). Tracked in
IMPERFECTIONS.md + the updated `mismodeled_matchups.py` grixis entry.
