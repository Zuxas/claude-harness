---
title: "Affinity Offense Rebaseline (arc #3) — implement the missing Urza's Saga Construct engine; no Boros nerf, no tune-to-44"
status: PROPOSED
created: 2026-07-01
updated: 2026-07-01
project: mtg-sim
estimated_time: ~240 min engineering + measurement compute
related_findings:
  - harness/knowledge/tech/modern-apl-fidelity-audit-2026-06-30.md
  - (this spec authored from a read-only diagnose+verify+design workflow, run wf_a65d79db-35c, 2026-07-01)
related_imperfections:
  - izzet-affinity-cell-sign-inverted (IMPERFECTIONS.md — PRIMARY target)
  - locked-modern-boros-affinity-baseline-stale-63.5 (IMPERFECTIONS.md:573 — 63.5 is CONFIRMED FICTION; correct it)
  - engine-mp1-damage-dealt-discarded-for-nonstorm-decks (IMPERFECTIONS.md:598 — Munitions is one instance)
related_commits: []
supersedes: []
superseded_by: []
branch: (to author on modern-postban-arc or a fresh branch when executed)
provenance: "harness/handoffs/modern-affinity-offense-rebaseline.md (primer) — note its Galvanic/Frogmite reach premises are PHANTOMS, dropped here"
---

# Affinity Offense Rebaseline (arc unit #3)

> **PROPOSED, not EXECUTING.** Authored 2026-07-01 from a read-only diagnosis+adversarial-verify
> workflow while the mulligan-validation workflow held the branch. Execution is gated on user
> go-ahead. The root cause is code-confirmed and measurement-reproduced; the design already
> absorbed the adversarial corrections below.

## Goal

Fix `apl/affinity_match.py` so Izzet Affinity actually DEVELOPS A BOARD — primarily by
implementing the entirely-missing **Urza's Saga chapter/Construct engine** to oracle text, plus
a Thoughtcast card-advantage branch and a Munitions-damage fidelity fix — moving the live
`boros_energy_lowcurve`-vs-`izzet_affinity` cell down from ~81-88% Boros toward the ~44-56
reality band **through Affinity playing its deck**, not by nerfing Boros and not by tuning any
knob to hit 44.

## Confirmed root cause (held in all board-generation verdicts)

Affinity loses ~86% because its APL **never develops a board**, NOT because it fails to attack.
`engine/match_runner._resolve_combat` (L917-945) auto-attacks with every non-summoning-sick
creature (`declare_attackers` is DEAD CODE in the two-player path), so combat is already
maximally aggressive — the deck simply has nothing with power to swing.

**PRIMARY defect:** the Urza's Saga Construct engine is **entirely unimplemented**. Saga is
referenced only as a land-play priority scorer (`affinity_match.py:323 'if saga in n: return 0'`);
there is no chapter counter, no `{2},{T}` Construct token, no chapter-III tutor/self-sac in the
APL or the match path; `gs._make_token` fires only for 'Drone Token' (L211). Measured: **0
Constructs across 100 games**, 4 of 60 deck slots dead, peak attacking board power median ~0-1
(zero in ~44-51% of games) vs Boros median ~8-10 (zero in 0/100) under the identical harness.

**SECONDARY:** Kappa `{5}{U}` and Pinnacle `{3}{U}{R}` are mana-gated even with affinity/improvise
reduction and resolve in only ~16-30% of games; Thoughtcast (1 maindeck) has no handler (the
section-8 'fill curve' at L252 gates on `Tag.CREATURE`, which an instant can never satisfy);
Munitions burst is computed (L244 `gs.damage_dealt += dmg`) then discarded because
`match_runner.py:279` propagates mp1 damage only under `WANTS_STORM/WANTS_BURN` and the APL sets
neither.

## Adversarial corrections baked in (do NOT re-introduce)

- **REJECT the "88.5% is stale / ~76-80% is the real reference" reframe.** That was a
  deck-substitution error (ran `boros_energy_modern` ~77% instead of the primer's actual opponent
  `boros_energy_lowcurve`). The **lowcurve-vs-affinity cell REPRODUCES at HEAD (~81-88%) — it is
  NOT stale.** (The ~77% standard-Boros number is separately explained by the 2026-06-30 Phlage
  cut in `boros_energy_modern.txt`.)
- **63.5% "Modern lock" is CONFIRMED FICTION** — it was Eldrazi Tron's field-weighted WR
  (`gauntlet-modern-2026-05-10.md` L19/L32) misattributed. The genuine historical Boros-vs-Affinity
  value was ~95.2% goldfish-wrapped. Strip it everywhere it's cited as a target.
- **REJECT primer premises "Galvanic Blast reach" and "Frogmite":** Galvanic is SIDEBOARD-ONLY
  with no handler (phantom from the maindeck's view); Frogmite is not in the deck at all. Do NOT
  add a maindeck Galvanic-to-face line — that invents a clock that doesn't exist in the 60.
- **"Truth ~44%" has NO empirical anchor** (`mtg_meta.db` has no post-ban Modern data; most recent
  Modern event 2026-04-24, pre-ban). Acceptance is gated on **mechanism + direction**, never on
  landing on 44.

## Scope

### In scope
- `apl/affinity_match.py` **ONLY** — all offense-fidelity changes live here (this IS the
  "non-Affinity cells byte-identical" guard).
- Implement Urza's Saga to oracle text, APL-local (keyed off the Saga card's `turn_entered`, the
  way `boros_energy_match` self-generates tokens): track chapters I/II/III; from chapter II, a
  `{2},{T}` Saga ability makes a 0/0 colorless Construct artifact-creature that continuously gets
  +1/+1 per artifact you control (recompute P/T from live artifact count each main phase); on
  chapter III, search library for an MV 0-1 artifact → battlefield, THEN sacrifice Urza's Saga.
- Add a Thoughtcast branch (affinity reduces cost; draw exactly 2) placed before section-8 so it
  isn't stranded by the `Tag.CREATURE` gate.
- Fidelity-fix the section-6b Munitions line (make the sac faithful; set `WANTS_BURN=True` so
  `match_runner.py:279` propagates it) — capped as a ≤1-2pp footnote, never leaned on.
- Improve Kappa/Pinnacle deployment reliability WITHIN honest affinity/improvise mana (no free
  mana, no fake discounts).
- Re-establish corrected reference numbers in `mismodeled_matchups.py`, IMPERFECTIONS, and citing
  docs (documentation).
- Instrument (scratchpad-only) per-turn board-power/creature-count curves + goldfish kill-turn via
  the MATCH path (`run_match`), plus WR under a pinned harness.

### Out of scope
- NO nerfing Boros (any `boros_energy_*` deck/APL off-limits; the cell moves by Affinity improving).
- NO editing shared engine paths (`_resolve_combat`/warp tick, `game_state.py`) — Saga logic stays
  APL-local so non-Affinity cells stay byte-identical. Any edit outside `apl/affinity_match.py` is
  a STOP.
- NO maindeck Galvanic Blast handler (SB-only phantom) and NO Frogmite (not in deck).
- NO hand-editing `data/sim_matchup_matrix.json` cached cells (58.5/85.4/35.x) — an APL fix cannot
  move them; they need a `parallel_launcher` re-run (out of scope).
- NO exposing construct size, chapter timing, drone count, or burn magnitude as a free knob dialed
  toward 44 (contrast the existing `AFFINITY_COUNTER_COST` env-sweep fingerprint at L58-60).
- OUT: combo opponents (arc #2), field-data refresh (arc #4), and `apl/izzet_affinity.py` (the
  goldfish driver — same Saga gap but not the match-path file under test; open risk).

## Pre-flight reads
- `harness/handoffs/modern-affinity-offense-rebaseline.md` (primer — Galvanic/Frogmite premises are
  phantoms to drop).
- `apl/affinity_match.py` (L323 Saga scorer; L162/178 affinity cost_reduction; L189-214
  Pinnacle/Drone; L242-246 Munitions; L251-253 fill-curve `Tag.CREATURE` gate; L58-60
  `AFFINITY_COUNTER_COST` sweep fingerprint).
- `decks/izzet_affinity_modern.txt` (4x Urza's Saga maindeck; Galvanic Blast SB-only; no Frogmite;
  1x Thoughtcast).
- `engine/game_state.py:730 _make_token` and `:1462 play_land` (token creation + summoning_sickness
  + ETB firing).
- `engine/match_runner.py:279` (WANTS_BURN/WANTS_STORM mp1-damage gate) and `:917-945 _resolve_combat`
  (auto-attacker list; `declare_attackers` dead code).
- `mismodeled_matchups.py` ('izzet affinity' INFLATED entry; strip 'stale 63.5% Modern lock').
- `harness/IMPERFECTIONS.md` 'locked-modern-boros-affinity-baseline-stale-63.5' (L573) and
  'izzet-affinity-cell-sign-inverted'.
- `harness/knowledge/mtg/gauntlet-modern-2026-05-10.md` L19/L29/L32/L33 (proof 63.5 = Eldrazi Tron
  field WR; true Boros-vs-Affinity was 95.2 goldfish-wrapped).
- `harness/knowledge/tech/spec-authoring-lessons.md` (Rule 9 methodology).
- `mtg-sim/CLAUDE.md` (affinity blocker history; no post-ban Modern DB data).

## Steps
1. Pre-flight reads. Confirm in code: L323 is the ONLY Saga reference; `_make_token` signature
   (sets summoning_sickness=True, fires ETB); how cast_spell/play_land tap+pay; that
   `_resolve_combat` builds its own attacker list.
2. **Pin the baseline harness EXACTLY and record 'before':** `boros_energy_lowcurve_modern` seat A
   (BorosEnergyMatchAPL) vs `izzet_affinity_modern` seat B (IzzetAffinityMatchAPL), `run_match`,
   n=100, seat-alternating on_play=(i%2==0), seed=42+i, PYTHONHASHSEED=0 → observed Boros 81% /
   Affinity 19%. This exact harness is the ONLY valid before/after comparator.
3. Instrument (scratchpad script) the CLOCK metrics via the MATCH path: per-turn (T4/T5/T6) avg
   creature count + avg peak ATTACKING (non-summoning-sick) board power for Affinity seat B,
   %games-with-zero-attacking-power-ever, Construct count, kill-turn-when-Affinity-wins. Confirm
   pre-fix numbers (median attacking power ~0-1, zero in ~44-51%, 0 Constructs, wins kill ~T5.86).
4. Implement the Urza's Saga chapter engine, APL-local: seed a per-instance chapter counter on
   `turn_entered`; each controller main phase advances I→II→III. From chapter II, if `{2}` generic
   available and Saga untapped, activate `{2},{T}`: `gs._make_token('Construct Token','0','0',
   'Artifact Creature - Construct')` then set its P/T to the live artifact count (`_count_artifacts`)
   each main phase it survives (dynamic, recomputed — not frozen).
5. Implement chapter III to oracle text: search library for an MV 0-1 artifact → battlefield, fire
   `_on_artifact_enter`, THEN sacrifice Urza's Saga. The `{2},{T}` ability stops once Saga is gone.
   **Predict magnitude FIRST:** ~1 Construct of power 2-4 arriving ~T4-6 in ~60-66% of games; write
   this predicted band into the gate BEFORE measuring WR.
6. Add a Thoughtcast branch (affinity-reduced cost; draw exactly 2) before section-8 fill-curve.
7. Fidelity-fix Munitions (section-6b, L242-246): make the sac faithful; set `WANTS_BURN=True` so
   L279 syncs the now-faithful damage. Cap expected effect ≤1-2pp.
8. Improve Kappa/Pinnacle deployment reliability ONLY within honest mana. Do not co-vary with
   construct size or burn.
9. Re-measure under the IDENTICAL pinned harness (step 2); re-run instrumentation (step 3); confirm
   the MECHANISM moved (board curves up, zero-power games down, Constructs present, kill-turn
   earlier) — not just WR.
10. Regression sweep: (a) Affinity seat B vs the full modeled Modern field (n≥50/cell) — a real
    clock modestly helps vs most, NOT a uniform spike; flag any cell swinging >~15pp. (b) All THREE
    Boros builds (standard, lowcurve, variant_jermey) vs Affinity must move DOWN consistently. (c)
    Spot-check 2-3 non-Affinity cells are byte-identical (no shared file changed).
11. Update references + dates: rewrite IMPERFECTIONS 'locked-modern-boros-affinity-baseline-stale-63.5'
    (63.5 = fiction; lowcurve reproduces ~81-88%, NOT stale; reject the ~76-80 reframe; record
    post-fix cell + date); close/rescope 'izzet-affinity-cell-sign-inverted' (strip Galvanic
    maindeck reach, note phantoms); update `mismodeled_matchups.py['izzet affinity']` (strip the
    fiction phrase; set sim to the actual lowcurve figure; keep INFLATED/trust-direction until
    re-measured).

## Validation gates (falsifiable, mechanism-anchored)
1. **BOARD-DEVELOPMENT (primary):** Affinity seat B peak ATTACKING board power rises from median
   ~0-1 to median ≥3 (≥1 real body), and %games-with-zero-attacking-power-ever drops from ~44-51%
   toward <20% (Boros control = 0%).
2. **CONSTRUCT FIDELITY (oracle-anchored, predicted BEFORE WR):** ~1 Construct arriving ~T4-6,
   present in ~55-70% of games, P/T EQUAL to live artifact count at each recompute (dynamic 2-4),
   summoning-sick the turn made, `{2},{T}` gated on real mana + Saga untapped, Saga sacrificed at
   chapter III.
3. **MATCH-PATH CLOCK:** Affinity kill-turn-when-winning improves from ~T5.86 toward ~T4-5, measured
   via `run_match` on `affinity_match.py` (NOT the goldfish `sim.py` driver — that runs the
   unchanged `apl/izzet_affinity.py`).
4. **WR DIRECTION (band with WHY, acceptance on mechanism):** the pinned lowcurve-vs-affinity cell
   moves DOWN from ~81% Boros toward ~44-56 BECAUSE gates 1-3 moved. Acceptance = "direction moved
   AND every mechanic matches its card", NEVER "cell reads 44". A residual gap above the band is
   EXPECTED and is attributed to the mana model / opponent overmodeling, not closed by inflating
   construct stats.
5. **ANTI-TUNING DISCRIMINATOR (strongest guard):** all three Boros builds vs Affinity move DOWN by
   comparable magnitude. A genuine clock helps vs every build; a constant tuned to one will not.
6. **REGRESSION — other Affinity matchups:** modest, matchup-appropriate improvement, NO cell
   swinging >~15pp uniformly in Affinity's favor (uniform spike = oversized/overfast construct).
7. **REGRESSION — non-Affinity cells:** spot-checked cells byte-identical pre/post.
8. **MUNITIONS FOOTNOTE CAP:** the WANTS_BURN/6b change contributes ≤1-2pp in isolation and 6b is
   verified faithful (Munitions deal 2 on leaving, not blanket-sacrificed for free damage).

## Stop conditions (teeth)
1. Any edit required OUTSIDE `apl/affinity_match.py` → STOP (scope leak / Boros-nerf / shared-path).
2. A faithful oracle-text Saga build drives the cell PAST Affinity-favored (Aff >56% / Boros <44%)
   → STOP: construct size/timing over-generous; re-audit against oracle text.
3. WR moves toward band but per-turn board/creature curves do NOT rise and Constructs stay ~0 →
   STOP: a number was tuned, not a mechanism; revert and re-diagnose.
4. Any mechanism can't be pinned to a specific oracle sentence and would need a free parameter fit
   to the cell → STOP; do not add the knob.
5. Temptation to add a maindeck Galvanic handler or a Frogmite body to close a residual → STOP
   (phantoms); the residual belongs to the mana-model/opponent-overmodel diagnosis.
6. The three Boros builds move by divergent magnitudes → STOP: build-specific tuning, not a clock.
7. Any hand-edit of `data/sim_matchup_matrix.json` toward the target → STOP (forbidden).

## Open risks
- `apl/izzet_affinity.py` (goldfish driver) has the SAME Saga gap but is out of scope; any check via
  `sim.py izzetaffinity` measures the UNCHANGED file — all clock gates must use the `run_match`
  match path against `affinity_match.py`.
- "~44 truth" has no empirical anchor — acceptance gated on mechanism + direction, never on 44.
- Faithful Saga is a MODEST clock (~1 body of 2-4 power in ~60-66% of games) and may leave a
  residual gap above the band — EXPECTED; attribute to mana model / opponent overmodel, do not
  inflate construct stats.
- `AFFINITY_COUNTER_COST` env-sweep (L58-60: '0→42.0 1→42.0 2→42.3 3→41.9') is a documented
  tune-to-band fingerprint on this exact APL — do not repeat it with construct size/timing.
- `data/sim_matchup_matrix.json` cached cells (58.5/85.4/35.x) are independently stale and immovable
  by this APL fix; need a `parallel_launcher` re-run (out of scope) — do not read them as post-fix
  truth.

## Changelog
- 2026-07-01: Created (PROPOSED). Authored from read-only diagnose(3 lenses)+verify(6 adversarial)
  +design workflow (run wf_a65d79db-35c). Root cause (unimplemented Urza's Saga Construct engine)
  held in all board-generation verdicts; the "88.5 is stale" reframe was REFUTED (deck-substitution)
  and the 63.5 "Modern lock" confirmed FICTION (Eldrazi Tron field WR). Galvanic/Frogmite reach
  premises dropped as phantoms. Mechanism-anchored gates; no tune-to-44.
