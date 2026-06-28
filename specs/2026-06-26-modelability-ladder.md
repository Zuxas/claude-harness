---
title: Modelability Ladder — turning unmodelable archetypes into modeled-and-PROVEN ones
status: SHIPPED
created: 2026-06-26
project: mtg-sim
related_commits:
  - 7b62092  # R4 trilogy merge
  - b1e757d  # Izzet Affinity warp modeling
estimated_time: ladder is multi-wave; each rung S/M/L sized below (R1 M ~6-8h, R6 L ~12h+)
related:
  - harness/specs/2026-06-26-archetype-capability-profiles.md  (the fidelity gate + modelability_backlog.json this climbs)
  - harness/IMPERFECTIONS.md  (sim-no-stack-priority, sim-no-instant-speed-combat, sim-no-hidden-information, warp-mechanic-not-modeled, planeswalker-loyalty-not-tracked)
  - mtg-sim/engine/{game_state.py, match_runner.py, stack.py, counter_resolver.py, planeswalkers.py}
  - mtg-meta-analyzer/data/mtg_meta.db  (real WR anchors)
supersedes:
superseded_by:
---

## 1. Principle

**Everything is quantifiable. "Unmodelable" is a temporary state, never a verdict.** These
decks win in reality with measurable frequency; the engine's only job is to *replicate those
wins and PROVE it*. This spec is the climbing plan: it converts each `unmodelable` /`low`
tag emitted by the fidelity gate into a proven, trustworthy win-rate, fastest-payoff first.

Tie-in to the fidelity gate (`2026-06-26-archetype-capability-profiles.md`):
- That spec's gate (ARL loop step 10) reads each profile's `engine_fidelity.confidence`
  (`high | medium | low | unmodelable`). When a deck's *primary* win condition depends on an
  unmodeled mechanic, the gate sets `verdict="unmodelable"`, refuses to publish a confident
  FWR, and **enqueues a work item to `mtg-sim/data/modelability_backlog.json`** carrying:
  the mechanic, the blocking imperfection (key from `mtg-sim/data/engine_fidelity_map.json`),
  the `field_share × win_impact` priority, and the **real-world replication target**
  (actual tournament WR + at least one known winning line to reproduce).
- **This spec is what works that backlog.** Each backlog item maps to a *rung* below. A rung
  is PROVEN — and only then does the gate flip the archetype to `high` — when BOTH hold:
  1. **WR replication:** field-weighted gauntlet MWR lands within tolerance of the real
     anchor (±3pp for low-n control samples, ±2pp where the repo's gauntlet tolerance applies).
  2. **Known-line replication:** a deterministic, seedable unit test reproduces at least one
     documented real-world winning line for that archetype (the falsifiable gate, Rule 5).

A capability that passes WR-only is *not* proven (a deck can hit the right WR by the wrong
mechanism — the Izzet Lessons information-leak inflation is the canonical failure). A capability
that reproduces a line but misses the WR band is *not* proven either. Both, or it stays
`unmodelable`. Passing both is the **event** that (a) flips `engine_fidelity.confidence`,
(b) removes the item from `modelability_backlog.json`, (c) makes the FWR promotable.

Source-of-truth files this spec assumes exist (created by the capability-profiles spec; if
absent, the first run of the workflow seeds them):
- `mtg-sim/data/modelability_backlog.json` — the prioritized work queue.
- `mtg-sim/data/engine_fidelity_map.json`  — mechanic → blocking-imperfection map.
- `mtg-sim/docs/archetype_profiles/<slug>.json` — per-deck profile w/ `engine_fidelity` block.

---

## 2. The Ladder (ordered engine-capability rungs)

Ordering is **cheapest-fidelity-first × field-share × win-impact**, with dependency edges
respected. Note on ordering vs the task's example sketch (stack→hidden-info→storm→warp→PW):
hidden-info masking is moved to **last** because the source designs put it as the most
expensive rung (M–L) and the gateway to determinized search — and because it is proven by a
masked-vs-unmasked *delta* that presupposes the permission core (R1) already exists. Stack/
priority leads because IMPERFECTIONS marks it STRUCTURAL (~40% of matchups) AND it is the
honesty prerequisite that keeps storm/warp WR from being silently inflated.

Each rung is an **additive evolution of an existing hook** — no rewrites. Real hooks cited.

---

### R1 — Stack + priority + mana-hold (the permission foundation)   [size: M]

The keystone. Upgrades the already-wired one-shot counter heuristic into a real LIFO stack
with one priority pass and true mana-hold tension.

- **Unlocks:** Azorius / UW Control (anchor 49.2%, n=818). Honesty prerequisite for R3/R4.
- **Blocking imperfection cleared:** `sim-no-stack-priority` (for permission).
- **Incremental path (existing hooks):**
  - L1 `MatchAPL.want_to_counter(spell, gs, opp) -> Optional[Card]` (default `None`). Refactor
    `counter_resolver.try_counter_spell` (game_state.py L122 region) to delegate to the APL when
    overridden, else fall back to today's heuristic. First callers `apl/uw_control_match.py`,
    `apl/jeskai_control_match.py`. The window is *already wired* into `game_state.cast_spell`
    (L1353–1366) — this upgrades a live hook, it does not build counters from scratch.
  - L2 drive `engine/stack.py` (`Stack`, `counter_top` L86, `resolve_one` L91,
    `resolve_interaction` L227 — built but never imported on the 2-player path) from the
    `cast_spell` window: push caster item → opp priority → push counter → **caster priority
    back** (protect with second counter / Spell Pierce) → LIFO resolve. Depth-cap 2–3.
  - L3 replace tap-agnostic `counter_resolver._tap_lands_for_response` (L100) with true
    untapped-mana accounting; route control mana-hold through `aware_match_apl.reserve_mana`
    (L555). "Tap out for a threat" and "hold UU for permission" become mutually exclusive.
- **Dependency:** none (L1 mostly scaffolded). Internal order L1→L2→L3.
- **PROOF acceptance test (UW Control):**
  - WR: gauntlet field-weighted MWR = **49.2% ± 3pp** (re-pulled at build time from
    `mtg_meta.db.matchup_matrix`, modern; prefer fresher `untapped_meta_archetypes` if newer).
  - Line: a counter from hand fires on the opponent's flagged must-answer threat **with ≥2
    lands left untapped that turn** (proves L3 hold, not a tap-out coincidence); a sweeper
    resolves into ≥3 opposing creatures; game won turn >10 with ≤2 threats cast (inevitability).
  - Counter-war sub-assertion (L2): in ≥1 logged game the controller protects a resolving
    spell by countering the opponent's counter.

### R2 — Instant-speed combat windows   [size: M]

"Free combat correctness" once R1 exists — reuses the same stack+priority machinery, only
adds the window at two combat points.

- **Unlocks:** Dimir Frog / Izzet Murktide tempo (anchors: Dimir Frog 52.6% n=643; Izzet
  Prowess 50.3% n=4165 — match whichever the deck file mirrors).
- **Blocking imperfection cleared:** `sim-no-instant-speed-combat`.
- **Incremental path:** step `match_runner._resolve_combat` (L613) into declare-attackers →
  priority window → declare-blockers → priority window → damage, reusing R1's stack/priority.
  APL hooks already present: `pre_combat_instant` (L234), `post_attackers_instant` (L271),
  `declare_blockers` (L515). Fold the Mutagenic Growth carve-out into the general path.
- **Dependency:** R1 (shares stack/priority).
- **PROOF acceptance test (Murktide tempo):**
  - WR within target ±3pp of the matched list.
  - Line ("holds UU, counters the turn-3 threat, wins the longer game"): threat resolves T3–T4
    and *survives* because a counter fired during the opponent's turn while UU was held; ≥1
    instant-speed burn resolves **inside a combat window** (not main phase); game won with 1–2
    threats on board while interaction is still in hand on the winning turn.
  - **Falsifier:** turning combat windows OFF must measurably drop this deck's MWR — else the
    combat model isn't load-bearing and the proof fails.

### R3 — Storm count + triggers ordering   [size: M]

Highest *reuse*: storm count, cost reduction, and the on-cast trigger seam benefit every
spell-based deck. All hooks already on the path.

- **Unlocks:** Ruby Storm (from-zero — no `ruby storm` key in `sim_bridge.ARCHETYPE_CLOCKS`,
  and `apl/ruby_storm_match.py` is an `AUTO_GENERATED` stub that does not combo).
- **Blocking imperfection cleared:** (storm modeling) — gated `data_quality:medium` until R1
  permission lands (combo WR inflated without opponent counters).
- **Incremental path (cite hooks):**
  - Engine `gs.storm_count`: reset per turn alongside `spells_cast_this_turn`
    (game_state.py L150/163/258); increment in the same spots `spells_cast_this_turn += 1`
    lives (`cast_spell` L1340, `cast_spell_warp` L724); thread through
    `match_runner._build_view` sync (L175–179 / L219–223) so it persists across windows.
  - Cost-reduction layer `gs.cost_reduction` consulted in `ManaPool.can_cast/pay` (or a
    `gs._effective_cost(card)` wrapper) — Ruby Medallion ETB registers `-{1}` for red. Replaces
    the APL's hardcoded `_ritual_cost()`; reusable by Goblin Electromancer etc.
  - `on_spell_cast(gs, card)` dispatch at the end of `cast_spell`/`cast_spell_warp` (right
    where Cosmogrand's 2nd-spell trigger fires, L737/L1345 — existing cast-count precedent):
    register Ral flip at `storm_count >= 3`; once flipped `gs.damage_dealt += 1` (bridges to
    life in `main_phase2`). Grapeshot copies = `gs.storm_count`.
  - Rewrite `ruby_storm_match.py` (drop `AUTO_GENERATED`) to combo in `main_phase2` via real
    engine paths; delete the goldfish `ruby_storm.py` `_storm`/`_ritual_cost` fakes.
- **Dependency:** R1 for an honest (non-inflated) gauntlet WR; the storm mechanics themselves
  have no dependency.
- **PROOF acceptance test:**
  - Line (deterministic, seedable): hand = Land + Ruby Medallion + 2× ritual + Manamorphose +
    Past in Flames + Grapeshot → cast Medallion → chain rituals at reduced cost to float ≥7 →
    cantrip → PiF → re-flash rituals from GY → Grapeshot at storm ≥ N → assert opp life ≤0 by
    T3 on the play. (Mirrors how `amulet_titan` documents its Scapeshift OHKO line.)
  - Distribution: post-build goldfish modal kill T3–T4, modal storm-at-kill in [6,10]
    `[needs source: real kill-turn + storm-count from mtg_meta.db top finishes / MTGGoldfish —
    do not lock the band until sourced]`.
  - WR: defensible combo band vs the Modern field, N≥200; flag `data_quality:medium` until R1.

### R4 — Warp cast-from-exile + delayed return trigger   [size: M (split S bug-fix + M feature)]

A cheap live-bug fix first, then the interaction fidelity that makes warp tempo real.

- **Unlocks:** Jeskai Blink (Warp representative) + the ~28% combined Warp Modern field
  (`engine-fidelity-gaps-warp-mechanic-not-modeled` enumerates 6 decks; 26 warp copies).
- **Blocking imperfection cleared:** `warp-mechanic-not-modeled`.
- **Incremental path (cite hooks):**
  - **S, do first:** wire the end-step tick into the match path — call `view._tick_warp()`
    (and `_tick_impending`) in `match_runner._run_player_turn` after `_run_post_combat_phase`
    (~L388). Today no `_tick_warp` runs on the match path (only goldfish `next_turn`
    L610–614), so warp creatures *never exile in matches* for the 3 current callers
    (`azorius_high_noon` L428, `dimir_midrange_jermey` L1077, `izzet_looting` L344). One
    wire-up fixes a live correctness bug. `cast_spell_warp` itself already exists (L697).
  - Promote the return to a delayed triggered ability: replace the inline exile in `_tick_warp`
    (L748–753) with a `Resolution`/trigger enqueued on `engine/stack.py` (`InteractionType`,
    `resolve_interaction` L227) so it has an identity Consign can target.
  - Cast-from-exile: on warp-exile set `card._warp_recastable = True`; APL cast loop considers
    `gs.zones.exile` cards with the flag at full `mana_cost` (per-Card flag persists, no runner
    change needed).
  - Consign to Memory: add to `counter_resolver` `COUNTER_VALIDITY` with target type
    `triggered_ability`; countering the return → clear `_warp_cast` so the creature stays.
  - Blink-breaks-linkage (CR 400.7): Ephemerate/Phelia blink of a `_warp_cast` creature clears
    `_warp_cast` (new object, no pending return). One-line guard in the blink path.
- **Dependency:** R1 (delayed trigger lives on the same stack; mirror permission gating).
- **PROOF acceptance test (Jeskai Blink):**
  - Lines (deterministic): (a) T2 `cast_spell_warp(Quantum Riddler)` for `{1}{U}`, draw, assert
    exiles at end step AND recastable from exile next turn; (b) warp Quantum + opp Consign on
    the return trigger → Quantum STAYS; (c) warp Quantum + Ephemerate → `_warp_cast` cleared,
    Quantum permanent.
  - Curve shift: current modeled `jeskaiblink` clock avg ~T7 must shift mass toward T5–6 as T2
    warp + blink value fire — drift is EXPECTED here and is the measurement (predict direction
    before running, Rule 5).
  - Regression smoke: re-run Izzet Affinity (Pinnacle Emissary) + Goryo's (Quantum) — no
    regression now that `_tick_warp` actually runs.
  - WR `[needs source: Jeskai Blink real WR from mtg_meta.db]`; ±2pp once sourced;
    `data_quality:medium` until R1 models the counterspell mirror.

### R5 — Planeswalker loyalty over turns   [size: L]

Largest blast radius (touches every canonical deck running a PW), so it climbs late with a
deliberate re-baseline. Loyalty-driven inevitability, not a race.

- **Unlocks:** Eldrazi/Mono-G Tron (`eldrazitron`/`eldrazi_ramp`, already canonical field).
- **Blocking imperfection cleared:** `planeswalker-loyalty-not-tracked`.
- **Incremental path (cite hooks):**
  - Populate `PLANESWALKER_ABILITIES` (planeswalkers.py L100) — Karn Liberated, Ugin the Spirit
    Dragon, Karn the Great Creator, + canonical Standard PWs, following the Ajani template
    `{+N, 0, -N}`. Convert existing one-shot ETB handlers (e.g. Chandra
    `card_handlers_verified.py` L1670) to merely SET loyalty at ETB; registry drives ticks.
  - Wire the call site: in `match_runner._run_player_turn` (L279), after deploying a PW, call
    `planeswalkers.activate_planeswalker_ability(pw, view, change)` once/PW. Add
    `MatchAPL.choose_pw_ability(pw, gs, opp) -> int` (default: tick up when safe, minus toward
    ult when lethal). `activate_planeswalker_ability` (L109) already has the CR 606.3 per-turn
    budget + CR 704.5i 0-loyalty SBA (L168).
  - Persist the per-turn budget: move `_pw_activated_this_turn`/`_pw_activation_turn` onto
    `TwoPlayerGameState` (per player) and sync via `_build_view` (L175–179 pattern) — currently
    lost each window rebuild. Loyalty itself persists FREE (shared `card.loyalty`).
  - Attackable PWs (the one new combat concept): in `_resolve_combat` (L613) allow an attack
    target = opposing PW, subtract attacker power from `card.loyalty`, fire 0-loyalty SBA; add
    `declare_attackers` "attack the walker." Keep minimal for v1.
  - Ultimate handlers: Karn −6 exile-all + restart, Ugin −X sweep, emblems, on `opp_view` zones.
- **Dependency:** none mechanically, but sequence LAST — it is baseline-shifting.
- **PROOF acceptance test (Tron; loyalty-shaped, NOT kill-turn):**
  - Line: Tron online T3 → Karn resolves T4 at loyalty 6 → +4 / −3 ticks → reaches **−6
    ultimate by turn N**; Ugin −X wipes board. Assert: loyalty strictly increases on tick-up
    turns and persists; Karn reaches −6 and ult fires; Ugin −X removes opp nonland permanents;
    a PW at 0 loyalty leaves play.
  - Win-source attribution: add a `win_reason` tag (combat / pw_ultimate / board_lock); target a
    nonzero pw_ultimate share vs the inert baseline (`eldrazitron` clock avg ~T6, PWs currently
    inert) — acceptance is on win-SOURCE, not a faster clock.
  - MANDATORY re-baseline: full canonical gauntlet pre/post (locked 64.5%/78.8% WILL move);
    expected shift is the measurement; investigate any per-matchup move whose sign contradicts
    "PWs now do something." WR `[needs source: Tron real WR from mtg_meta.db]`, ±2pp;
    `data_quality:high` (no hidden-info dependency).

### R6 — Hidden-information masking + determinization seed   [size: M–L]

Most expensive rung and the gateway to determinized search (ISMCTS). Proven by an anti-cheat
*delta*, which is the single strongest test in the program.

- **Unlocks:** Jeskai Control (anchor 53.9%, n=448). Consumes R1's L1–L3 — no new stack work.
- **Blocking imperfection cleared:** `sim-no-hidden-information`.
- **Incremental path (cite hooks):** add `revealed_to_opponent: set` to player state; build
  `_opp_view(gs)` filtering `opp.zones.hand` to revealed cards only; pass the **masked** view to
  the *active* APL's decision methods. Fixes `match_runner._build_view` opp-hand alias (L160–163)
  + perfect-info wiring (L194–198). The reactive `want_to_counter` still legitimately reads the
  opp's *own* real hand (it's their decision); the active APL must decide from a belief/
  determinization heuristic keyed on the opponent's revealed archetype, never `gs.hand_b`.
- **Dependency:** R1 (the permission core it masks).
- **PROOF acceptance test (Jeskai Control — masked-vs-unmasked delta):**
  - WR: masked-info gauntlet MWR = **53.9% ± 3pp**.
  - **Anti-cheat gate:** `WR_perfect_info − WR_masked_info ≤ 4pp`. If the engine wins much more
    with the opponent's hand visible, it was cheating, and only the *masked* number is
    promotable. (Mechanical analog of the Izzet Lessons information-leak inflation.)
  - Line: a logged counter decision made with `gs.hand_b` masked — APL leaves up the
    archetype-appropriate counter and answers a threat it could only predict; plus a bait
    sequence (deploy a decoy threat, sandbag the real finisher).

**Dependency graph (climb order):**
`R1 → R2`, `R1 → R3`, `R1 → R4`, `R1 → R6`; `R5` independent but sequenced last (blast radius).
Recommended wave order: **R1 → R2 → R3 → R4 → R5 → R6.**

| Rung | Capability | Field × impact | Size | Clears imperfection |
|---|---|---|---|---|
| R1 | stack/priority + mana-hold | ~40% matchups | M | sim-no-stack-priority |
| R2 | instant-speed combat | tempo cluster | M | sim-no-instant-speed-combat |
| R3 | storm count + triggers | combo cluster | M | (storm; medium until R1) |
| R4 | Warp cast-from-exile | ~28% Modern | M | warp-mechanic-not-modeled |
| R5 | planeswalker loyalty | all PW decks | L | planeswalker-loyalty-not-tracked |
| R6 | hidden-info masking | all control / ISMCTS gate | M–L | sim-no-hidden-information |

---

## 3. The DYNAMIC MODELABILITY WORKFLOW

A reusable, re-runnable workflow (proposed: `mtg-sim/scripts/modelability_workflow.py`,
orchestrated by the harness; worktree isolation via the `EnterWorktree`/`ExitWorktree` tools).
Each run pops one item, implements the smallest increment for it in isolation, validates by
replication, and on proof promotes the archetype `unmodelable → modeled`.

### Phases

- **P0 — POP.** Read `mtg-sim/data/modelability_backlog.json`. Sort by
  `priority = field_share × win_impact` (descending). Pop the highest-priority item **whose
  dependency rung is already PROVEN**; if its dependency is unproven, skip to the next and
  requeue this one. (Seed the backlog from the gate's `unmodelable`/`low` records if empty.)
- **P1 — SCOPE.** Resolve the item to its rung (§2). Load the rung's cited hooks; read the
  blocking imperfection from `engine_fidelity_map.json`; confirm the documented real-world WR
  anchor + the known-line target are present and sourced (no `[needs source]` left in the
  acceptance band — if missing, re-pull from `mtg_meta.db.matchup_matrix` / fresher
  `untapped_meta_archetypes`, write into the profile's `engine_fidelity` block, Rule 5).
- **P2 — ISOLATE.** `EnterWorktree` a per-rung branch (`modelability/R<n>-<slug>`) so parallel
  rungs do not collide on shared engine files (`game_state.py`, `match_runner.py`, `stack.py`).
  Record the worktree path in the backlog item (`worktree`, `status:"in_progress"`).
- **P3 — IMPLEMENT (smallest increment).** Apply the rung's additive engine change on the
  existing hook + the matching APL increment, plus the minimum instrumentation the proof needs
  (game-log assertions, `win_reason` tag, masked/unmasked toggle). No rewrite; one rung at a
  time.
- **P4 — VALIDATE BY REPLICATION.** Run BOTH gates against real data:
  1. Deterministic, seeded **known-line** unit test — must reproduce the documented winning
     line(s) for the archetype.
  2. **WR** — field-weighted gauntlet MWR within tolerance of the real anchor (±3pp low-n /
     ±2pp normal). Plus bit-stable re-baseline
     (`parallel_launcher.py --deck <X> --n 1000 --seed 42` pre/post) — for warp/PW the drift is
     intended and its *predicted direction* must be written before the run.
- **P5 — PROVE / ITERATE / ABORT.** If both gates pass → PROVEN, go P6. If one fails →
  iterate within the rung's effort budget. Hit a stop/abort condition (below) → revert the
  worktree, write an IMPERFECTIONS entry with the concrete remaining gap, leave the item
  `unmodelable` with notes, exit.
- **P6 — RECORD PROOF + PROMOTE.** Write a proof artifact
  `mtg-sim/data/modelability_proofs/<slug>-<date>.json` =
  `{rung, anchor_wr, tolerance, wr_achieved, line_reproduced:true, seed, log_excerpt,
  commit_hash, baseline_shift}`. Flip `engine_fidelity.confidence` in the profile +
  `engine_fidelity_map` for every archetype the rung unlocks. Move the item
  `unmodelable → modeled` (remove from the active queue, append to a `proven` list). Merge the
  worktree (`ExitWorktree`).
- **P7 — HAND TO ARL.** Signal the ARL that these archetypes are re-promotable (see §4).

### Stop / abort conditions (teeth, Rule 4)

- Known winning line not reproducible after the rung's iteration budget → ABORT, IMPERFECTIONS
  entry, item stays `unmodelable`.
- WR cannot reach the band after iteration → ABORT (do NOT widen the band to pass).
- Bit-stable re-baseline shows an unexplained per-matchup move whose **sign contradicts the
  written prediction** (>0.5pp/matchup) → STOP, investigate; resume only with a documented
  amendment.
- Anti-cheat delta `WR_perfect − WR_masked > 4pp` (R6) → ABORT; the masked number is the only
  promotable one and it failed.
- Dependency rung not yet PROVEN → requeue the item, pop the next instead (never build a rung on
  an unproven dependency).
- Any `[needs source]` band that cannot be sourced from `mtg_meta.db` → HITL=true, pause (no
  fabricated targets, no-fabrication rule).

### How proof is recorded

Proof is durable and machine-readable: the `modelability_proofs/<slug>-<date>.json` artifact
(above) is the evidence; the backlog item's status flip + the `engine_fidelity.confidence`
flip are the *consequences*. A WR-only or line-only pass is recorded as `partial` and the item
stays `unmodelable` — only a both-gates pass writes `line_reproduced:true` + an in-band
`wr_achieved` and earns `modeled`.

---

## 4. How this feeds the ARL

The fidelity gate (`2026-06-26-archetype-capability-profiles.md`, ARL loop step 10) reads
`engine_fidelity.confidence` to decide promote vs low-confidence vs unmodelable. While an
archetype sits at `unmodelable`/`low`, the gate keeps its FWR OUT of `promoted` and the ARL
does not autonomously tune it (and `arl_distill.py` will not distill heuristics from it).

When a rung is PROVEN (P6), the confidence flip is exactly the input the gate consumes:

1. The unlocked archetypes flip to `high` (or `medium` where a higher rung is still pending,
   e.g. R3 storm stays `medium` until R1 ships, R4/R6 noted similarly).
2. On the next ARL loop, the gate sees `high` → applies normal promote/mutate/discard
   thresholds → the archetype's gauntlet FWR becomes **promotable** and trustworthy.
3. The ARL **resumes autonomous tuning** on those archetypes: mutate/hill-climb APL params,
   feed results into `promoted`, distill heuristics — all now safe because the underlying
   capability is modeled-and-proven, not silently approximated.
4. The backlog shrinks by exactly the proven item; the next workflow run pops the next
   highest `field_share × win_impact` rung. The loop is self-feeding: deeper modeling →
   more promotable archetypes → a stronger bot, with every step proven against real data.

This is the whole point: the gate stops bad data AND emits the prioritized engine-capability
backlog; this ladder climbs that backlog fastest-payoff-first; each proven rung hands a newly
trustworthy archetype back to the ARL for autonomous improvement.

## Changelog
- 2026-06-26: Authored from the two modelability design summaries (interaction/control +
  combo/storm/warp/pw clusters). Climbs the modelability_backlog.json emitted by the
  2026-06-26 archetype-capability-profiles fidelity gate.
- Reconciled 2026-06-27: verified complete; status was stale after the ~2026-05-16 cadence lapse.
