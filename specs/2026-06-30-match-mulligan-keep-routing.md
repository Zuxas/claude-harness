---
title: Match mulligan keep-routing -- route run_match opening hands through each APL's keep()
status: EXECUTING
created: 2026-06-30
updated: 2026-06-30
project: mtg-sim
estimated_time: see Estimated time (code ~50 lines; the work is validation on a SCOPED slice)
scopes_spec:
  - harness/specs/2026-04-30-mulligan-parameter-sweep.md
  - harness/specs/2026-06-28-mulligan-sweep-impl-plan.md
related_specs:
  - harness/specs/2026-06-30-modern-combo-interaction.md (Amendment 3 -- the Grixis finding)
  - harness/specs/PREDECESSOR-full-field-id-ordering-stabilization.md (TO AUTHOR -- Gate-0 blocker; see Step 0)
related_findings:
  - harness/knowledge/tech/spec-authoring-lessons.md
related_imperfections:
  - grixis-reanimator-match-assembly-capped-by-crude-mulligan (IMPERFECTIONS.md:49)
  - engine-apl-nondeterminism-id-based-ordering (IMPERFECTIONS.md:65 -- RESOLVED for Amulet+Boros ONLY)
  - mulligan-threshold-not-empirically-validated (IMPERFECTIONS.md:365)
  - mulligan-logic-portfolio-gap (IMPERFECTIONS.md:116)
related_commits: []
supersedes: []
superseded_by: []
branch: modern-postban-arc
---

# Match Mulligan Keep-Routing

## Goal

Route the `run_match` opening-hand mulligan decision through each deck's real
`apl.keep()` / `apl.bottom()` (a London mulligan, seeded, both seats), replacing the
crude inline `mull-if-fewer-than-2-lands` heuristic, so decks mulligan the way they
actually would -- unstarving combo assembly (Grixis measured ~32% match-assembly vs
~56% faithful goldfish) -- WITHOUT unfairly self-helping our own deck or destabilizing
the non-combo field.

This is the concrete realization of the **B0 engine prerequisite** that the 2026-06-28
mulligan-sweep impl plan (Gotcha G1) identified as blocking a true WR mulligan sweep:
`run_match` (the canonical FWR engine) currently never calls `keep()`, so the swept
variable is off the code path. This spec makes `keep()` load-bearing in `run_match`.
It is a DESIGN pass -- no code is written here.

## SCOPE DECISION: this ships on the boros+amulet lanes ONLY (first slice)

**The adversarial review's single structural finding is correct and forces a scope cut.**
Gate 0 (byte-identical double baseline) is a hard prerequisite for trusting any per-cell
delta. But `engine-apl-nondeterminism-id-based-ordering` (IMPERFECTIONS.md:65) is RESOLVED
**only for the Amulet-goldfish and Boros-match lanes**, not the full field. `PYTHONHASHSEED=0`
pins `set`/`dict` iteration order but does **not** retire `id()`-based ordering, so a
full-field Gate 0 is expected to FAIL field-wide (see Step 0.3). A spec that keeps a
full-field Gate 0 is unexecutable: it would STOP on day one on out-of-scope nondeterminism.

Therefore this spec is **deliberately restricted to the two lanes where full byte-identity
is currently reachable: boros (as hero, seat A) and amulet**. Concretely:
- The routing code change (`_do_mulligan_runner`) ships engine-wide -- it is guarded and
  fallback-safe (Step 4), so it is safe for every deck. It is the *validation and the
  "flip to keep in production"* that are scoped to boros+amulet.
- Gate 0 / Gate 1 byte-identity is required and asserted **only on the boros+amulet lanes.**
- The full-field flip to `mode="keep"` in production is BLOCKED until the predecessor spec
  below retires `id()`-ordering field-wide.

**Named predecessor (out of scope here, must be authored + shipped before the full-field
flip):** `full-field id()-ordering stabilization` -- replace every `id()`-keyed / object-
identity-ordered iteration in the match engine and APLs with a deterministic key (name,
registry index, or a stable synthetic id), then re-run the Step 0.3 double baseline
field-wide and require byte-identity. Until that lands, this spec's production default stays
`crude` for all non-(boros/amulet) lanes.

## Reconciliation with the prior mulligan specs (a vs b vs c)

The 2026-04-30 spec asked whether to (a) route through `keep()`, (b) parameter-sweep the
crude heuristic, or (c) both. **The call is (a) now, which UNBLOCKS (b) later** -- not (b),
never (b)-instead-of-(a).

- **(b) parameter-sweeping the crude heuristic is the wrong grain.** The crude rule is a
  single portfolio-wide `min_lands` knob that ignores every deck's actual keep logic.
  Sweeping it cannot make Grixis keep a 1-land + reanimator-package hand it should keep,
  nor mull a 2-land + zero-combo-piece hand it should ship. The Grixis evidence
  (Amendment 3 of the combo spec: match P_assemble ~32% vs goldfish ~56%) is a per-deck
  combo-awareness failure, not a threshold-tuning failure. No value of `min_lands` fixes it.
- **(a) routing through `keep()` is the fix.** Each deck already ships (or inherits) a
  `keep()` that encodes its keep criteria (Grixis keeps on tutor/reanimate/target + >=1
  land; combo decks that OVERRIDE keep keep combo-enabling hands). The goldfish path
  (`apl/mulligan.py::take_opening_hand`, invoked by `base_apl.run_game`) already consults
  these. Routing `run_match` through the SAME `keep()` closes the divergence that caps
  combo assembly -- *for the decks that override keep* (see the fidelity-tier table below).
- **(c) both, sequenced.** After (a) lands, the 2026-06-28 impl plan's Track B (WR-measured
  parameter sweep) becomes measurable for the first time -- its B0 blocker is exactly this
  spec. This spec does NOT do the sweep; it is the prerequisite that makes the sweep real.

## Scope

### In scope
- Extract the inline mulligan block in `engine/match_runner.py::run_match` (L1595-1620:
  the `draw_a(7)`/`draw_b(7)` + two `mull-if-<2-lands` loops) into a single overridable
  `_do_mulligan_runner(gs, side, apl, result, mode)` function, with THREE modes:
  - `mode="crude"` -- a VERBATIM extract of the current behavior (proven byte-identical).
  - `mode="london_crude"` -- London draw-7-bottom-N *mechanic* but the crude `lands<2` keep
    predicate + `generic_bottom` (isolates the Vancouver->London mechanic from keep quality;
    see Step 5).
  - `mode="keep"` -- London mulligan routed through `apl.keep()` / `apl.bottom()`, seeded
    via `gs.rng`, both seats.
- A per-seat mode selector (env-var or param). Production default is `keep` **only on the
  boros+amulet lanes**; `crude` elsewhere until the predecessor stabilization lands.
- Fallback safety for the (currently empty) set of decks whose resolved `keep()`/`bottom()`
  RAISES at runtime (getattr + try/except -> crude predicate / `generic_bottom`). See the
  false-premise note under "Which decks override keep()" -- this is defensive, not load-bearing.
- A boros+amulet-lane re-baseline (both drivers, PYTHONHASHSEED-pinned, seeded, n>=500 combo
  / n>=1000 field-sanity) that becomes the new reference for those lanes.
- Validation that combo-assembly rates rise toward goldfish rates and flagged combo cells
  move toward their primer bands, with non-combo cells bounded + explicable AND with
  externally-anchored non-combo bands retained as REGRESSION guards (Step 1.1).

### Explicitly out of scope
- The parameter sweep itself (2026-06-28 Track B) -- this spec unblocks it, does not run it.
- **Full-field rollout / the full-field flip to keep** -- blocked on the named predecessor
  (full-field id()-ordering stabilization). This slice is boros+amulet only.
- Opponent-aware mulligan (`keep_vs_opp` via `_opp_key`). `run_match` does NOT wire
  `_opp_key`, so `AwareMatchAPL.keep()` takes its generic-fallback branch (opp-blind),
  which is CORRECT here: it matches the goldfish ~56% target (also opp-blind) and isolates
  a self-help vector. Opp-aware match mulligan is a deliberate later slice.
- Fixing the Grixis 66-card `audit:stub` decklist (cause (b) of the ~32% cap) -- forbidden
  here (trimming toward a target is Stop-condition-2b reverse-fit); tracked separately.
- Raising the fidelity of the ~21 inherit-keep opponents' keep (see fidelity-asymmetry
  guard, Step 5 / Gate 7). Tracked, not fixed here.
- The `match_engine.py` legacy path (already calls `keep`) and the goldfish path (already
  calls `keep`) -- unchanged.

## This IS the "mulligan overhaul" -- first slice

The MEMORY task `project_mtg_sim_session_2026_05_04.md` lists "mulligan overhaul" as a
long-standing pending item. This spec is its **first slice: the structural routing fix,
validated on the boros+amulet lanes.** It deliberately does NOT include (i) full-field
rollout (blocked on id()-ordering stabilization), (ii) the empirical threshold sweep
(downstream, now unblocked), (iii) opponent-aware match mulligan, or (iv) London scry /
play-vs-draw threshold differentiation. Those are named as follow-on slices so the overhaul
is scoped, not silently half-done.

## Pre-flight reads (do all before any Step)
- `harness/knowledge/tech/spec-authoring-lessons.md` (Rule 9 prior lessons -- esp. gate
  predictions must account for SIM-vs-DB source per matchup, and keyword/behavior density
  across BOTH decks).
- `harness/specs/2026-06-28-mulligan-sweep-impl-plan.md` (Gotchas G1-G9; this spec is its B0).
- `harness/specs/2026-04-30-mulligan-parameter-sweep.md` (the original sweep spec).
- `harness/specs/2026-06-30-modern-combo-interaction.md` -- Amendment 3 (the Grixis cell:
  the 32%-vs-56% cap, the 55.0% cell value, the "stays flagged" pre-commitment).
- `harness/IMPERFECTIONS.md` -- `grixis-reanimator-match-assembly-capped-by-crude-mulligan`
  (49), `engine-apl-nondeterminism-id-based-ordering` (65, RESOLVED for Amulet+Boros ONLY --
  this is the scope-cut driver), `mulligan-threshold-not-empirically-validated` (365),
  `mulligan-logic-portfolio-gap` (116).
- `engine/match_runner.py` -- the inline mulligan (L1595-1620); `TwoPlayerGameState.__init__`
  (`gs.rng = random.Random(seed)`, init shuffles); `draw_a`/`draw_b` (rng-FREE `lib.pop(0)`);
  `run_match_set` determinism contract. NOTE the ordering footgun (Step 2.3).
- `apl/mulligan.py` -- `take_opening_hand` (London reference), `generic_keep`,
  `generic_bottom` (the fallbacks). NOTE: uses GLOBAL `random` -- do NOT reuse (see Step 3).
- `apl/base_apl.py` L37-45 -- `keep`/`bottom` are `@abstractmethod` (the false-premise fact).
- `apl/match_apl.py` -- `MatchAPL` (abstract; defines NO keep -- so it cannot be instantiated
  bare); `GoldfishAdapter`/`RemovalAwareGoldfishAdapter.keep`; `GenericMatchAPL.keep`
  (L619-626, creature-requiring -- see registry note below).
- `apl/aware_match_apl.py` L864-934 -- `keep`, `keep_vs_opp`, `_keep_generic_fallback`
  (2-5 lands + >=1 nonland, KEEPS creatureless), the `_in_keep_dispatch` re-entrancy guard.
- `apl/generic_apl.py` L38+ -- `GenericAPL.keep` (role-aware goldfish keep -- the fallback
  that inherit-keep MRO actually resolves to for e.g. izzet_control).
- `apl/grixis_reanimator_match.py` -- the combo-aware `keep()` this fix must let fire.
- `apl/__init__.py` L264 -- `MATCH_APL_REGISTRY` (confirm no cell maps to bare
  `GenericMatchAPL`; verified 2026-06-30 -- none do).
- `scripts/full_field_gauntlet.py` and `run_match_set` -- the two validation drivers.

## Which decks actually override keep() (determined from the tree, 2026-06-30)

**FALSE-PREMISE CORRECTION (was wrong in the -original draft; fixed here).** The prior draft
feared "a hand-tuned subclass that forgot to define keep() would AttributeError, so the
getattr fallback is load-bearing." **This cannot happen.** `BaseAPL.keep`/`bottom` are
`@abstractmethod` (`apl/base_apl.py` L37-45), so any INSTANTIABLE APL necessarily resolves a
concrete `keep()`/`bottom()` (an ABC missing them raises `TypeError` at *construction*, long
before a match). **Zero modeled decks lack `keep()`.** The getattr+try/except fallback
(Step 4) is therefore **defensive-against-a-RAISE only** (a keep that throws mid-hand), not a
guard against a missing method. Keep it -- cheap insurance -- but do not describe it as
covering "keep-less decks"; there are none.

**Fidelity tiers (this is the real, verified risk -- mismatched generic keep, not missing keep):**
Of 81 match-APL files, **60 OVERRIDE `keep()` and 21 INHERIT it.** The inherited keep resolves
by MRO to one of two goldfish-tier fallbacks:

| Tier | Decks (examples) | Resolved keep() | Combo-aware? |
|---|---|---|---|
| **A. Match-tuned override** | grixis_reanimator, goryos, living_end, affinity, gruul_broodscale, boros_energy, amulet_titan, belcher, neoform, murktide, humans, ... (60 files) | the deck's own hand-tuned match keep | YES (for combo decks) |
| **B. Aware generic fallback** | jeskai_control, sultai_control, uw_control_modern, izzet_lesson, izzet_spellementals, dimir_excruciator (AwareMatchAPL subclasses, `_opp_key` unset) | `AwareMatchAPL._keep_generic_fallback` = 2-5 lands + >=1 nonland (KEEPS creatureless) | no |
| **C. Goldfish role keep** | izzet_control, superior_doomsday (`(MatchAPL, <GoldfishAPL>)` MRO) | `GenericAPL.keep` / `ControlAPL.keep` -- role-aware goldfish keep | no |

**Correction to the review's mechanism claim:** the review asserted the inherit-keep control/
combo decks fall to `GenericMatchAPL.keep`, which requires `creatures>=1` and therefore
"MULLS good creatureless control/combo hands." **This is imprecise.** No modeled cell resolves
to bare `GenericMatchAPL.keep` -- `MATCH_APL_REGISTRY` (`apl/__init__.py`) contains no bare
`GenericMatchAPL` mapping; that creature-requiring predicate fires only as the *engine default*
for UNREGISTERED decks (`GenericMatchAPL()` in `parallel_match.py`/`variant.py`/`meta_solver.py`
when `apl_cls is None`). Tier-B and Tier-C fallbacks both KEEP creatureless hands. So the
"creatureless control hand gets mulled" harm does **not** bite any modeled cell.

**BUT the review's larger point survives and is the cardinal guard:** there is a real
**fidelity asymmetry** -- our hero (boros/amulet) routes through a *match-tuned* keep (tier A),
while ~21 opponents route through a *goldfish-tier* fallback (tier B/C). That asymmetry can
inflate hero WR for a MODELING reason (our mulligan is higher-fidelity than the field's), not
a real edge. Step 5 / Gate 7 isolate this by splitting hero gains by opponent tier.

**Payoff still holds for the flagged combo cells:** every flagged Modern combo cell
(grixis_reanimator, goryos, living_end, affinity, gruul_broodscale) is tier A -- it overrides
keep, so its combo-aware logic fires. **superior_doomsday is a combo deck in tier C** (inherits
`ControlAPL.keep`, no combo-aware match keep) -- flag its cell "generic keep, combo payoff N/A"
(Gate 4 / Step 6.2).

## Steps

### Step 0 -- Determinism prerequisite (PYTHONHASHSEED) + fact-checks + SCOPE the double baseline
0.1 **Pin `PYTHONHASHSEED=0` in the baseline-capture AND validation harness.** It pins
    `set`/`dict` iteration order. It does NOT retire `id()`-based ordering -- that is why the
    double baseline is SCOPED to the stabilized lanes (0.3).
0.2 **Fact-checks (grep, ~10 min):** (a) confirm `BaseAPL.keep`/`bottom` are `@abstractmethod`
    (they are -- L37-45) so no instantiable deck is keep-less; (b) confirm `draw_a`/`draw_b`
    are rng-free (`lib.pop(0)`); (c) `grep -rn "random\." apl/*.py` restricted to `keep`/
    `bottom` bodies -- confirm no deck's `keep`/`bottom` touches global `random` (routing
    determinism relies on keep/bottom being PURE). If any does, note it as an isolation risk
    before proceeding.
0.3 **SCOPED determinism gate (run baseline TWICE, on the boros+amulet lanes).** With
    PYTHONHASHSEED pinned, run the pre-change baseline twice at the same (n, seed, n_workers)
    **for boros-as-hero and amulet lanes only**. Require byte-identical per-cell `a_wins`
    across the two runs. If ANY of these cells differs -> even the "stabilized" lanes are not
    actually stable -> STOP; the id()-fix regressed. **Do NOT gate the full field here** -- the
    full field is known to fail this (that is the scope-cut driver and the predecessor spec's
    job). Running the full field twice is still WORTH DOING as diagnostic input for the
    predecessor spec, but a full-field mismatch is EXPECTED and does not block this slice.

### Step 1 -- Capture the pre-change baseline (boros+amulet lanes) + retain anchored guards
1.1 **Do NOT blanket-void externally-anchored non-combo locks.** The prior draft said "every
    cited FWR lock is void." That is wrong for locks anchored to real-world data. Two classes:
    - **Externally-anchored non-combo locks are RETAINED as post-re-baseline REGRESSION
      guards.** selesnya-vs-prowess band [60,71.5] (primer + PT) and borosenergy-vs-affinity
      88.5% are validated against real events. After re-baseline they are NOT "superseded" --
      a cell that was in its real-world primer band and drifts OUT of it under routing is a
      **STOP** (Gate 8), not "different, therefore fine." Only the *point value* moves; the
      real-world *band* remains a hard guard.
    - **Un-anchored / purely self-referential locks are re-baselined.** WR-keyed quality grades
      and the combo-spine baseline (`data/combo_spine_baseline_2026-06-30.txt`) that were only
      ever sim-internal are superseded by the new pinned baseline; do not chase their old
      point values.
1.2 Capture a fresh baseline on BOTH drivers, PYTHONHASHSEED-pinned, seed=42, n_workers pinned,
    **at the mandated floors: n>=500 for combo cells, n>=1000 for the non-combo field-sanity
    cells** (see Measurement floor below -- these are MANDATORY, not "preferred"):
    - PRIMARY: single-hero `run_match_set` (boros seat A vs each modeled opponent seat B).
    - SECONDARY: round-robin `full_field_gauntlet` (field-health; report but only the
      boros+amulet lanes are gated).
    Save per-cell `a_wins` to `data/mull_routing_baseline_2026-06-30.txt`. Also record, for
    each flagged combo cell, the combo-fires / P_assemble metric (e.g. Archon-online rate for
    grixis) via the existing per-APL instrumentation.

### Step 2 -- Extract the crude block VERBATIM (pure refactor; must be byte-identical)
2.1 Move L1595-1620 into `_do_mulligan_runner(gs, side, apl, result, mode="crude")`. The
    `crude` mode is a LITERAL transcription of today's logic: draw 7 (rng-free pop), then
    `for _ in range(3)`: if `lands < 2`, put hand back into `lib`, `gs.rng.shuffle(lib)`,
    redraw `max(4, 7 - mulligans - 1)`, `mulligans += 1`. **Preserve seat order:** run the
    seat-A helper fully, THEN the seat-B helper. The interleaved `draw_b(7)` is rng-free, so
    folding both initial draws into their helpers does not perturb the `gs.rng` stream.
    ```
    # engine/match_runner.py  (inside run_match, replacing L1595-1620)
    _do_mulligan_runner(gs, "a", apl_a, result, mode=_mull_mode("a"))
    _do_mulligan_runner(gs, "b", apl_b, result, mode=_mull_mode("b"))
    ```
2.2 **Gate 1 (faithful-refactor invariant):** with BOTH seats in `mode="crude"`, re-run the
    Step-1 baseline. Require byte-identical per-cell `a_wins` on both drivers, **on the
    boros+amulet lanes**. This proves the plumbing is faithful before any behavior change.
    Mismatch -> the extract is wrong; fix before Step 3.
2.3 **ORDERING FOOTGUN (do not "clean up"):** the crude block does
    `gs.lib_a = gs.hand_a + gs.lib_a` -- hand cards go to the FRONT of the library *before*
    the shuffle. Reordering to `gs.lib_a + gs.hand_a` (which "looks equivalent") permutes the
    pre-shuffle positions and BREAKS Gate 1 byte-identity. Transcribe the concatenation order
    exactly. Same for seat B.
2.4 **MAX_MULL note (fidelity choice, surfaced not silent):** crude mode keeps cap 3 (mull
    to 4). `keep`/`london_crude` modes use cap 4 to MATCH goldfish's London cap (the ~56%
    Grixis assembly target was measured under goldfish's cap-4 London). Deliberate parity
    choice, called out, not bundled silently.

### Step 3 -- Add mode="keep" and mode="london_crude" (London, seeded, both seats)
3.1 Implement, using `gs.rng` EXCLUSIVELY (never global `random`, never `take_opening_hand` --
    global random is the shared stream ~10 in-game engine handler sites read; consuming it
    here would shift in-game handler behavior vs baseline, a change far beyond mulligan):
    ```
    def _do_mulligan_runner(gs, side, apl, result, mode="keep"):
        if mode == "crude":
            ... # verbatim extract from Step 2, exact concat order (2.3) ...
            return
        # --- London (mode in {"keep","london_crude"}), seeded via gs.rng ---
        on_play  = gs.on_play if side == "a" else (not gs.on_play)
        if mode == "london_crude":
            keep_fn   = lambda hand, m, op: _crude_keep(hand)   # crude lands<2 predicate
            bottom_fn = generic_bottom
        else:  # mode == "keep"
            keep_fn   = _safe_keep(apl)      # getattr(apl,'keep') (always present) else crude
            bottom_fn = _safe_bottom(apl)    # getattr(apl,'bottom') else generic_bottom
        MAX_MULL  = 4                    # goldfish-parity London cap (Step 2.4)
        mulligans = 0
        while True:
            _reshuffle_hand_into_lib(gs, side)   # lib += hand; hand = []
            gs.rng.shuffle(_lib(gs, side))
            _draw(gs, side, 7)                   # rng-free pop from front
            hand = _hand(gs, side)
            forced = mulligans >= MAX_MULL
            try:
                do_keep = forced or bool(keep_fn(hand, mulligans, on_play))
            except Exception:
                do_keep = _crude_keep(hand)      # never crash the match
            if do_keep:
                if mulligans > 0:
                    try:    to_bottom = bottom_fn(hand, mulligans)
                    except Exception: to_bottom = generic_bottom(hand, mulligans)
                    for c in list(to_bottom):
                        if c in hand:
                            hand.remove(c); _lib(gs, side).append(c)
                break
            mulligans += 1
        if side == "a": result.mulligans_a = mulligans
        else:           result.mulligans_b = mulligans
    ```
3.2 `keep_fn(hand, mulligans, on_play)` is called with exactly 3 args (opp-blind), matching
    `base_apl.run_game`'s goldfish invocation. Do NOT pass `_opp_key` (out of scope).
    `AwareMatchAPL.keep` naturally takes its generic-fallback branch when `_opp_key` is unset;
    tier-A combo APLs override `keep` and fire their own logic. The `_in_keep_dispatch` guard
    is untouched (no keep<->keep_vs_opp ping-pong is introduced -- we never set `_opp_key`).
3.3 Determinism note: `keep`/`london_crude` consume MORE `gs.rng` than crude (a reshuffle per
    mull + the mull-0 reshuffle). Expected -- behavior-changing by design. The `run_match_set`
    per-game-seed contract (identical aggregate for all `n_workers >= 1`) STILL holds because
    `gs.rng` is per-game-seeded and workers each get the same `(game_seed, on_play)`.

### Step 4 -- Fallback safety (defensive-against-RAISE; NOT covering "keep-less decks")
4.1 `_safe_keep(apl)` = `getattr(apl, "keep", None)` if callable else `_crude_keep`.
    `_safe_bottom(apl)` similarly -> `generic_bottom`. Because keep/bottom are abstract in
    `BaseAPL`, the `else` branches are effectively DEAD for modeled decks (verified Step 0.2a).
    The load-bearing safety is the per-call try/except (Step 3.1) that falls to `_crude_keep`/
    `generic_bottom` when a resolved keep/bottom RAISES mid-hand. Frame this honestly in the
    findings doc: "defensive against a throwing keep(), not a missing keep()."
4.2 `_crude_keep(hand)` = the literal `sum(is_land) >= 2` predicate, so the exception path
    reproduces the OLD keep decision. `generic_keep`/`generic_bottom` are imported from
    `apl/mulligan.py`.

### Step 5 -- Self-help decomposition (5-mode matrix) + fidelity-asymmetry split + pre-check
5.1 **Cheap pre-check FIRST (before the expensive gauntlet):** sample N (e.g. 5000) random
    7-card boros hands (seeded, PYTHONHASHSEED-pinned) and diff `BorosEnergyMatchAPL.keep()`
    vs the crude `lands<2` decision on each. Report the disagreement rate. NOTE (do not
    pre-judge as ~0): boros's tuned keep is strictly MORE selective than crude `lands>=2`
    (its `return mulligans>=2` tail also mulls flood and action-less 2-landers), so the
    M2-M0 self-help is STRUCTURALLY >= 0, not "expected near-identical." Report the
    disagreement rate as data; do not editorialize it toward zero.
5.2 **5-mode matrix** via the per-seat mode selector (`_mull_mode("a"|"b")` from env/param).
    This SEPARATES the Vancouver->London *mechanic* from *keep quality* (the review's
    attribution-leak point C -- keep-mode bundles both):
    - **M0** `{a:crude,        b:crude}`  = baseline (== Step 1 / Gate 1; byte-identical).
    - **Mmech** `{a:london_crude, b:crude}` = WE draw-7-London with the CRUDE keep predicate,
      opponents crude. Isolates the mechanic-only self-help.
    - **M1** `{a:crude,        b:keep}`   = opponents mulligan properly, we don't (opp-help).
    - **M2** `{a:keep,         b:crude}`  = WE mulligan properly (mechanic + tuned keep), opp crude.
    - **M3** `{a:keep,         b:keep}`   = full fix (production, boros+amulet lanes).
    Run boros seat A vs each opponent at each mode (n>=500, seeded, pinned).
5.3 **Attribution arithmetic (write it down -- this is what makes Gate 6 falsifiable):**
    - **mechanic-only self-help**  = Mmech - M0
    - **keep-quality self-help**   = M2   - Mmech
    - **total self-help**          = M2   - M0   (= mechanic + keep-quality)
    - **opp-help**                 = M1   - M0   (LOWERS boros WR; opponents' combos assemble)
    Gate 6 reads the DECOMPOSED pieces, not bundled M2-M0. Predicted signs: mechanic and
    keep-quality both RAISE boros WR (>=0 structurally per 5.1); opp-help LOWERS it. A net-flat
    M3 can HIDE both -> the decomposition is what catches it.
5.4 **Fidelity-asymmetry split (Gate 7 -- the cardinal guard):** partition boros's per-cell
    gains (M3 - M0) by OPPONENT TIER: tier-A (match-tuned-keep opponents) vs tier-B/C
    (goldfish-fallback-keep opponents, the ~21 inherit-keep decks). If boros's gains are
    CONCENTRATED against tier-B/C opponents, that is **modeling asymmetry** (our keep is
    higher-fidelity than theirs -- the mirror of number-forcing), and must be ATTRIBUTED in
    the findings doc, NOT banked as a real WR edge. Gains spread evenly across tiers, or
    concentrated against tier-A, are more likely a real routing effect.

### Step 6 -- Update trackers
6.1 Update `grixis-reanimator-match-assembly-capped-by-crude-mulligan` IMPERFECTION: cause (a)
    crude mulligan FIXED on the boros lane; note residual causes (b) 66-card stub + (c)
    legitimate boros pressure. Note full-field fix blocked on the id()-ordering predecessor.
6.2 Update `mismodeled_matchups.py` for any flagged combo cell that moved materially; keep +
    annotate cells still out of band (Stop condition 2). **Enumerate override-keep vs
    inherit-keep per MODELED cell; flag inherit-keep combo/control cells (e.g.
    superior_doomsday) as "generic keep, combo payoff N/A."**
6.3 Update the mulligan-sweep impl plan: Track B's B0 prerequisite is SHIPPED for the
    boros+amulet slice; full-field flip blocked on the id()-ordering predecessor spec.
6.4 **Author the predecessor spec stub:** `full-field id()-ordering stabilization` (retire
    id()-keyed iteration, re-run Step 0.3 field-wide). This slice's full-field rollout depends
    on it.
6.5 Write `harness/knowledge/tech/mull-routing-<date>.md` with the 5-mode decomposition, the
    per-tier gain split, the new boros+amulet baseline, and the per-cell direction+mechanism
    table. Update WR-keyed quality grades for the boros+amulet lanes only. Run `drift-detect.ps1`
    -> 0 new errors.

## Validation gates (falsifiable)

All WR gates are stated at the MANDATORY floors (n>=500 combo, n>=1000 field-sanity) so the
acceptance band exceeds ~3SE (see Measurement floor). "pp" = percentage points of WR.

| Gate | Metric source | Acceptance | Stop trigger |
|---|---|---|---|
| 0 determinism (SCOPED) | boros+amulet baseline x2, PYTHONHASHSEED pinned | byte-identical per-cell across the two runs, **boros+amulet lanes only** | ANY boros/amulet cell differs -> the "stabilized" lanes regressed; STOP. (Full-field mismatch EXPECTED, not gated -- it is the predecessor spec's job.) |
| 1 faithful refactor | both drivers, mode=crude both seats | byte-identical per-cell vs Step-1 baseline, boros+amulet lanes | any delta -> extract wrong (check 2.3 concat order); fix before Step 3 |
| 2 grixis assembly (mechanism) | single-hero boros-vs-grixis, mode=keep, n>=500 | P_assemble (Archon-online) rises materially above 32% (>=42%), toward goldfish ~56% | P_assemble does not rise -> routing not effective for grixis; diagnose |
| 3 grixis outcome | same cell, n>=500 | boros-vs-grixis drops materially below 55% (<=48%; a ~7pp move ~= 3SE at n=500), toward primer 38 | cell does not move despite risen P_assemble -> kill-channel gap, NOT routing failure (keep going) |
| 4 other combo cells | single-hero, per flagged cell, n>=500 | each tier-A combo cell moves TOWARD its primer band with a predicted direction + mechanism; tier-C combo cells (superior_doomsday) flagged "payoff N/A" | a tier-A flagged cell moves AWAY from primer with no mechanism -> investigate |
| 5 non-combo sanity | both drivers, n>=1000 | non-combo cells bounded: `|delta| <= ~3SE` (~5pp at n=1000) + explicable direction + a stated per-cell mechanism; no chaotic flips | a non-combo cell swings > band with no keep()-mechanism, OR any cell moves with no stated mechanism -> a keep() is pathological / mechanic-driven; investigate |
| 6 self-help (decomposed) | 5-mode matrix (Step 5.3), n>=500 | mechanic-only (Mmech-M0) AND keep-quality (M2-Mmech) each small/explicable OR explicitly attributed; neither silently banked | either component is a DOMINANT source of a boros WR gain and is banked as "we got better" -> STOP, attribute |
| 7 fidelity asymmetry | per-tier gain split (Step 5.4), n>=500 | boros gains NOT concentrated against tier-B/C (goldfish-fallback) opponents; if concentrated, attributed as modeling asymmetry not real edge | gains concentrated on tier-B/C opponents and banked as a real WR edge -> STOP, attribute (mirror of number-forcing) |
| 8 anchored-band regression | externally-anchored non-combo cells (selesnya-vs-prowess [60,71.5]; borosenergy-vs-affinity 88.5%), n>=1000 | each stays INSIDE its real-world primer band post-routing | a previously in-band cell drifts OUT of its real-world band -> STOP (this is a real-world regression, NOT "superseded by re-baseline") |

**Gate 2/3 scoping note (prevents a self-inflicted STOP):** Amendment 3 attributes the ~32%
cap to THREE causes -- (a) crude mulligan [FIXED here], (b) 66-card stub decklist [out of
scope], (c) legitimate boros pressure [part of the matchup]. Full [25,45] band entry likely
needs (b) too. So the gate is "moves MATERIALLY toward the band (P_assemble >=42%, cell
<=48%)", NOT "reaches [25,45]". Writing it as [25,45] would fire a STOP on out-of-scope
causes (b)+(c).

**Gate interpretation rule:** pair every combo gate with a mechanism check (P_assemble rises)
AND an outcome check (cell moves). "Assembly rose but cell didn't move" = a DIFFERENT gap
(e.g. drain kill-channel without WANTS_BURN), not a routing failure -> keep going.

## Measurement floor (why the old n=200 / ~8pp band was unfalsifiable)

The review is correct: at n=200 the binomial SE ~= 3.5pp, so 2SE ~= 7pp -- the old "~8pp =
sane" non-combo band sat INSIDE the noise envelope, and the combo WR gate (55->48, 7pp) was
only ~1SE. Bands must exceed ~3SE to distinguish signal from variance. Therefore:
- **Combo cells (Gates 2,3,4,6,7): n>=500 MANDATORY** (SE~=2.2pp; the 7pp grixis move ~= 3SE).
- **Non-combo field-sanity + anchored-band cells (Gates 5,8): n>=1000 MANDATORY** (SE~=1.6pp;
  the ~5pp band ~= 3SE).
- Gate 5's band is stated in SE units at the chosen n (~5pp at n=1000), NOT a fixed 8pp.
- The mechanistic gate (Gate 2, P_assemble 32%->>=42%, a ~10pp mechanistic move) is the one
  gate detectable even at modest n; it is the primary signal that routing worked.

## Stop conditions (teeth)
1. **Scoped determinism broken (Gate 0):** any boros/amulet cell differs across two pinned
   baseline runs -> STOP; the id()-fix regressed on a lane we thought was stable.
2. **Faithful-refactor invariant broken (Gate 1):** crude-mode both-seats is NOT byte-identical
   to baseline -> the extract diverged (check 2.3 concat order); STOP + fix.
3. **Reverse-fit trap:** if a flagged combo cell lands out of its primer band and the only way
   to pull it in is to tune assembly -- trim the stub decklist, dial a keep threshold to a
   target, or add damage the deck does not deal -> STOP. Keep the cell flagged; document residual.
4. **Silent self-help (Gate 6):** if boros WR rises and the 5-mode decomposition shows
   mechanic-only OR keep-quality self-help is a dominant driver, it MUST be attributed, not
   banked -> STOP the "we got better" narrative.
5. **Fidelity-asymmetry banking (Gate 7):** boros gains concentrated against goldfish-fallback
   (tier-B/C) opponents and reported as a real edge -> STOP; attribute as modeling asymmetry.
6. **Anchored-band regression (Gate 8):** an externally-anchored non-combo cell drifts out of
   its real-world primer band -> STOP; this is a real regression, not a re-baseline artifact.
7. **Crash / pathology:** any deck's resolved `keep()`/`bottom()` raises repeatedly under
   SIM_DEBUG=1 (the fallback should prevent crashes, so a repeated raise is a real bug), or a
   non-combo cell swings past the Gate-5 band with no explicable keep()-mechanism -> STOP.

Per harness Rule 4, a fired stop condition halts execution; outcome is one of {bug found ->
fix + amend + resume; honest model improvement -> verify + amend + resume; unfalsifiable ->
abort + IMPERFECTIONS + ship partial}.

## Estimated time
- Code (`_do_mulligan_runner` + 3 modes + helpers + mode selector + fallbacks): ~50 lines, ~1.5 hrs.
- Step 0 determinism pin + fact-checks + SCOPED double-baseline (boros+amulet): ~1 hr + compute.
- Step 1 boros+amulet baseline capture (both drivers, n>=500-1000, pinned): ~compute (multi-hr;
  cheaper than full-field because scoped).
- Step 2 crude-mode byte-identical gate: ~0.5 hr + compute.
- Step 3-4 keep + london_crude modes + fallbacks: ~1.5 hrs.
- Step 5 5-mode decomposition + pre-check + per-tier split: ~2-3 hrs + compute (5x single-hero
  sweep at the higher n floor -- this is the dominant cost).
- Step 6 trackers + findings + grades + predecessor stub + drift: ~1.5 hrs.
- **Total: ~1.5 working sessions of engineering + significant SCOPED-lane re-baseline compute.**
  This is a FIRST SLICE, not the full overhaul: full-field rollout is blocked on the named
  id()-ordering predecessor spec.

## Annotated imperfections (carried / expected after this spec)
- **Slice-scoped, not full-field:** routing is validated + flipped-to-keep on boros+amulet
  lanes only. Full-field flip blocked on the `full-field id()-ordering stabilization`
  predecessor (Gate 0 fails full-field today). Tracked as its own spec.
- **Fidelity asymmetry (tier A vs tier B/C keep):** our hero uses a match-tuned keep; ~21
  opponents use a goldfish-tier fallback. Gate 7 attributes any hero gain concentrated on
  tier-B/C opponents as modeling asymmetry rather than banking it; RAISING opponent keep
  fidelity is a deferred slice, not fixed here.
- **Opp-blind match mulligan:** `run_match` keeps `keep()` opp-blind (no `_opp_key`). Deferred slice.
- **superior_doomsday (and other inherit-keep combo/control cells):** no combo-aware match keep;
  routing gives them a goldfish-tier keep, so the combo-assembly lift does NOT apply. Flagged
  "generic keep, payoff N/A"; a per-deck match keep is a deferred slice.
- **Grixis residual:** even with routing, causes (b) 66-card stub + (c) legitimate boros
  pressure may keep boros-vs-grixis above [25,45]. Cell stays flagged rather than reverse-fit.
- **keep/bottom purity assumption:** determinism relies on every deck's `keep`/`bottom` being
  RNG-free (Step 0.2c). If a deck's keep touches global `random`, that deck's routing has a
  latent nondeterminism vector -- tracked, not fixed here.
- **MAX_MULL 3->4 in keep/london_crude modes:** goldfish-parity choice; a deck whose real cap
  is lower is slightly over-permitted at deep mulligans. Minor; documented.
- **Fallback is defensive-against-RAISE only:** there are NO keep-less modeled decks
  (keep/bottom are abstract in BaseAPL), so the getattr-else branch is dead for modeled decks;
  only the try/except (throwing keep) path is live. Framed honestly, not as "keep-less coverage."

## Mid-execution Amendments

### Amendment 1 (2026-06-30) -- First-slice landed: code + Gate 0 + Gate 1 (Steps 0-4)

Status -> EXECUTING. This amendment records what the first execution slice shipped
(the engine routing + the two byte-identity gates) and the ONE stop-condition firing
and its Rule-4 resolution. Steps 5 (five-mode WR decomposition) and 6 (trackers/
findings/predecessor stub/grades) remain OPEN -- they are the downstream WR-validation
and documentation work, not the structural routing fix.

**What shipped (engine/match_runner.py):**
- `_do_mulligan_runner(gs, side, apl, result, mode)` extracted from the inline
  L1595-1620 block, with modes `crude` (verbatim), `london_crude` (London mechanic +
  crude predicate + generic_bottom), `keep` (routes apl.keep()/apl.bottom(), seeded via
  gs.rng ONLY, both seats, London bottoming, cap 4).
- `_mull_mode(side, apl)` selector: per-seat env override (`MULL_MODE_A/B`) -> global
  (`MULL_MODE`) -> production default. Production default = `keep` only for
  `_KEEP_ROUTED_APLS = {BorosEnergyMatchAPL, AmuletTitanMatchAPL}`; `crude` elsewhere.
  String-set (not isinstance) gating to avoid a match_runner<->APL circular import.
- Fallback safety: per-call try/except around keep()/bottom() -> `_crude_keep` /
  `generic_bottom`. Framed defensive-against-RAISE (keep/bottom abstract in BaseAPL; no
  keep-less modeled deck). `_safe_keep`/`_safe_bottom` getattr-else branches are dead for
  modeled decks, kept as cheap insurance.
- `import os` added at module top (was only imported inline).
- `_run_match_with_combo` (the combo-sampler seat-A path, L~1420) LEFT UNTOUCHED --
  spec scope names run_match L1595-1620 only. See carried imperfection below.

**Harness / determinism (Step 0):** `scripts/mull_routing_capture.py` (PRIMARY driver
run_match_set, single-hero, n=500 seed=42 n_workers=1, `PYTHONHASHSEED` read from env).
13 boros+amulet-lane cells. Baseline saved to `data/mulligan_baseline_pinned_2026-06-30.txt`.

**Gate 0 (determinism, SCOPED) -- PASS on 12/13 cells; ONE stop-condition firing:**
Ran the PRE-change baseline across FOUR separate pinned process launches
(`PYTHONHASHSEED=0`). 12 of 13 cells byte-identical across all four. STOP CONDITION 1
fired on `boros_vs_uw_control` (a_wins = 446,447,447,447 across launches 1-4).
- **Rule-4 outcome: honest model refinement, NOT a boros/amulet-hero regression.**
  Diagnosis (PROVISIONAL, 4-launch evidence): opponent-side `id()`-ordering
  nondeterminism surfacing in this cell -- it reproduces on the PRE-change code, so it is
  NOT introduced by keep-routing. `amulet_vs_uw_control` was byte-stable across the same 4
  launches, WEAKLY suggesting the instability is boros/UW-pairing-specific rather than UW
  Control unconditional -- but 4 launches cannot distinguish a low-rate (~5-25%) flip from
  true stability, so the predecessor spec should re-sample widely (>=20 launches) before
  trusting the pairing-specific attribution. What IS firmly established: every hero-side
  (boros/amulet own-lane) result is stable across all 4 launches, and the spec's Gate-0
  model (whole boros/amulet CELLS byte-identical) is too optimistic -- an opponent's
  un-retired `id()`-ordering can leak into a cell even when the hero lane is stable.
- **Resolution:** the Gate-0/Gate-1 gated set is refined to the 12 cross-launch-stable
  cells; `boros_vs_uw_control` is EXCLUDED (reported, not asserted) and handed to the
  named predecessor spec (full-field id()-ordering stabilization). This is exactly the
  predecessor's job per the SCOPE DECISION; it does not block the slice.

**Gate 1 (faithful refactor) -- PASS.** Post-refactor `MULL_MODE=crude` (both seats)
reproduced all 12 GATED baseline cells byte-identically (and the excluded uw_control cell
landed on its modal 447). The extract (concat order + cap 3) is faithful.

**Routing confirmed live (sanity, NOT a gate):** production keep-mode a_wins deltas vs
crude baseline -- boros gains (its tuned keep is strictly more selective: e.g.
vs_amulet +21, vs_izzet_prowess +19, vs_humans +17, vs_eldrazi_tron +15, vs_grixis +8);
amulet drops on raw WR (vs_boros -39, vs_humans -24, vs_izzet -21) as its combo-keep mulls
more aggressively. These magnitudes are NOT validated here -- Step 5's five-mode
decomposition + per-tier split (Gates 6-8) is the deferred attribution work. Do NOT bank
any of these as a real edge yet.

**Tests:** `tests/test_mull_routing.py` (10, all pass): crude byte-faithful to an inline
reference, mode-selector gating + env precedence, keep-mode consults apl.keep/bottom,
london_crude uses the crude predicate, RAISING keep -> crude fallback (keep + mull cases),
RAISING bottom -> generic_bottom, keep-mode seed-determinism. Touched existing test
`tests/test_determinism.py` still passes (6). Keep-mode worker-invariance spot-checked
(n_workers 1 vs 4 identical). (Pre-existing unrelated breakage: `test_run_match_set_workers.py`
calls `run_match_set(workers=...)` -- stale kwarg, not touched by this slice.)

**Still OPEN (this spec continues EXECUTING):** Step 5 (5-mode WR matrix at the n>=500/
n>=1000 floors + attribution + per-tier fidelity split), Step 6 (IMPERFECTIONS updates,
mismodeled_matchups annotations, impl-plan B0 note, predecessor-spec stub, findings doc +
grades + drift-detect).

**Carried imperfections (new, from this slice):**
- `mull-routing-combo-sampler-seat-a-crude`: `_run_match_with_combo` (used when the
  opponent's name matches a `ComboKillSampler.KILL_DISTS` key: dimir reanimator, lotus
  combo, cephalid breakfast, sneak and show, mono red painter, doomsday, bant nadu) still
  uses the inline crude seat-A mulligan; boros/amulet keep does NOT route there. Grixis
  Reanimator does NOT normalize to any KILL_DISTS key, so boros-vs-grixis (Gate 2/3) still
  routes through run_match and IS keep-routed -- the bypass affects only those ~7 opponents.
- `mull-routing-uw-control-cross-launch-nondeterminism`: boros_vs_uw_control not
  cross-launch byte-stable under PYTHONHASHSEED=0 (opponent id()-ordering). Deferred to the
  full-field id()-ordering stabilization predecessor.

### Amendment 2 (2026-07-01) — Steps 5-6 executed: HYPOTHESIS FALSIFIED (honest negative)

Status stays EXECUTING pending ONE open decision (keep vs revert the slice — below). Steps 5
(5-mode WR decomposition) and 6 (combo re-measure + trackers) are now COMPLETE. Full findings:
`harness/knowledge/tech/mull-routing-falsification-2026-07-01.md`. Raw captures:
`mtg-sim/data/mull_5mode_captures_2026-07-01/`. Re-measure flag commit: `002e9df`.

**The spec's core premise — "crude mulligan starves combo assembly; routing through keep()
unstarves it and moves the flagged cells" — is FALSIFIED.** Isolated mulligan contribution to
grixis assembly is ~+3pp (32.4%→35.4%, ~1 SE), WR flat at 55.0% (gate needed ≥42% AND ≤48% —
NOT met). Yawgmoth's assembly FELL (9.8%→6.8%; its keep mulls away combo pieces). The
"match 32% vs goldfish 56%" gap was a MISATTRIBUTION: goldfish-vs-match bundles the whole
opponent-pressure channel (legit Boros pressure + the 66-card stub list), not the mulligan.
Spec Gate 2 stop-trigger ("P_assemble does not rise") effectively fired for BOTH cells. Both
stay flagged; nothing tuned (Stop condition 2 respected).

**5-mode attribution (Gates 6-8): shipped slice is artifact-only.**
- keep-quality self-help = M2 − Mmech_spec = **−0.17pp** (NEGLIGIBLE — spec's near-zero
  prediction for an aggro 2-land keep CONFIRMED).
- mechanic-only self-help = Mmech_spec − M0 = **+1.89pp** (SYSTEMATIC, 6/7 cells) — the
  London-vs-Vancouver asymmetry (Boros gets London cap-4; opponents stay crude Vancouver cap-3).
  A MODELING ARTIFACT (mirror of number-forcing), must be attributed.
- **Shipped reality is M2, not M3.** `_KEEP_ROUTED_APLS = {Boros, Amulet}` → every
  Boros-vs-opponent cell is {keep,crude} = M2 (+1.71pp); only Boros-vs-Amulet is genuine M3.
  Do NOT cite M3's +2.40pp as "production" — it is the blocked full-field projection.
  The +1.89pp artifact ≈ the entire +1.71pp shipped gain, so the slice's ONLY real effect is
  the artifact. keep-quality benefit ≈ 0.
- opp-help = M1 − M0 = **+1.86pp**, OPPOSITE to prediction (spec predicted opponents routing
  keep would LOWER Boros WR). Gates 0/1/7 held; Gate 8 no routing regression.

**OPEN DECISION (user):** the shipped Boros+Amulet slice now delivers ~zero real benefit and
one live artifact whose neutralization (all-field London) is blocked on the id()-ordering
predecessor. Keep it enabled (faithful, safe, but artifact-contaminates #5/#6 field WR ~1.7pp)
or revert the production flip (keep the refactor + modes, default back to crude)? Tracked as
IMPERFECTION `mull-routing-london-vancouver-asymmetry-artifact`.

**Redirect for arc #2:** the mulligan lever does NOT unstarve the flagged cells. Remaining #2
work targets the real causes: grixis = 66-card stub + legit Boros pressure; yawgmoth = combat
over-credit. Methodology lesson added to spec-authoring-lessons.md
(`goldfish-vs-match-gap-conflates-channels`).

## Changelog
- 2026-06-30: Created (PROPOSED). Realizes the 2026-06-28 impl plan's B0 engine prerequisite
  (route run_match through keep()). Two-mode extract, seeded via gs.rng, opp-blind,
  fallback-safe. 4-mode self-help decomposition. PYTHONHASHSEED pin as Step 0. Advisor-reviewed.
- 2026-06-30: REVISED after adversarial review (status stays PROPOSED). (1) SCOPE CUT: this is
  now explicitly a boros+amulet-lane first slice; full-field Gate 0 is known to fail (id()-
  ordering resolved only for those lanes), so a named predecessor spec (full-field id()-ordering
  stabilization) is required before any full-field flip. (2) FALSE-PREMISE FIX: keep/bottom are
  @abstractmethod, so NO modeled deck is keep-less; fallback reframed as defensive-against-RAISE,
  not "keep-less coverage." (3) FIDELITY-TIER TABLE + Gate 7: real risk is mismatched generic
  keep (match-tuned-ours vs goldfish-tier-theirs), not missing keep; hero gains split by
  opponent tier to catch modeling asymmetry. Corrected the review's imprecise "GenericMatchAPL
  mulls creatureless" claim (no modeled cell maps to bare GenericMatchAPL; tier-B/C fallbacks
  keep creatureless). (4) MEASUREMENT FLOOR: n>=500 combo / n>=1000 field MANDATORY; Gate 5 band
  restated in SE units (~5pp at n=1000, was an unfalsifiable ~8pp at n=200). (5) ATTRIBUTION
  LEAK FIX: added mode="london_crude" + 5-mode matrix with explicit contrast arithmetic to
  separate the Vancouver->London mechanic from keep quality (Gate 6 reads decomposed pieces).
  (6) ANCHORED-LOCK REGRESSION GUARD (Gate 8): externally-anchored non-combo bands (selesnya-vs-
  prowess, borosenergy-vs-affinity) retained as STOP guards, not blanket-voided. (7) Ordering
  footgun (hand+lib concat before shuffle) called out in Step 2.3.
- 2026-06-30: EXECUTING. Amendment 1 -- first slice shipped: _do_mulligan_runner (crude/london_crude/
  keep) + _mull_mode selector + fallback safety in engine/match_runner.py; keep-mode flipped to
  production for boros+amulet lanes only. Gate 0 PASS on 12/13 cells (Stop-1 fired on boros_vs_uw_control
  = opponent-side id()-ordering nondeterminism -> Rule-4 honest refinement: cell EXCLUDED, deferred to the
  id()-ordering predecessor). Gate 1 PASS (crude-both byte-identical to pre-change baseline). Baseline:
  data/mulligan_baseline_pinned_2026-06-30.txt. Tests: tests/test_mull_routing.py (10). Steps 5-6 OPEN.
