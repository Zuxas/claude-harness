---
title: R6 Hidden Information (card-advantage / inevitability) - Implementation Design
status: PROPOSED
created: 2026-06-27
project: mtg-sim
related_findings:
  - mtg-sim/CLAUDE.md "Known model limitations" (Izzet Lessons inversion)
supersedes: none
superseded_by: none
estimated_time: design-only (impl is multi-week, phased)
---

# R6 Hidden Information - Implementation Design

> The fifth and HARDEST rung of the engine-fidelity ladder
> (R1 stack/priority, R2 instant combat, R5 PW loyalty, R4 warp are SHIPPED).
> This spec is DESIGN ONLY. No engine code is edited here.
>
> HEADLINE HONESTY: full hidden-information modeling (belief states / information
> sets / playing-around-unseen-cards) is NOT tractable and is explicitly OUT OF
> SCOPE. What `WANTS_HIDDEN_INFO` actually models is **card-advantage /
> inevitability**, NOT literal hidden information. The `hidden_information`
> mechanic id is retained for the fidelity-map only because that is the existing
> key; no reader should infer belief states were built.

---

## 0. The one diagnostic that re-scoped this whole design

The motivating mis-model (mtg-sim/CLAUDE.md, "Known model limitations"): the sim
shows ~75% Selesnya Landfall WR vs Izzet Lessons; PT data shows ~75% Izzet
Lessons WR. The matchup is INVERTED because the sim "can't represent inevitable
card-advantage wins."

The intuitive fix is a timeout tiebreaker that credits the deck with more cards.
**That intuition is wrong, and I verified it before designing anything.** A
design-legal diagnostic run (no code edited) on the canonical Bo3 engine path
(`engine.match_engine.run_match`, Izzet Lessons as seat A vs Selesnya Landfall)
found the following. NOTE the canonical deck: the gauntlet resolves the Lessons
deck via `load_deck_and_apl` -> `APL_REGISTRY` (apl/__init__.py:149-150) to
`decks/izzet_lesson_standard.txt` (SINGULAR), NOT the plural
`decks/izzet_lessons_standard.txt`. The numbers below are measured on the
canonical singular file (n=60, seed=42, mix_play_draw) so the RED-pre baseline
reproduces; an earlier run on the plural file gave qualitatively identical
results (22.0% / ~82% combat / ~15% timeout):

| Metric (canonical singular deck) | Value |
|---|---|
| Izzet Lessons WR (as A) | **20.0%** (inversion confirmed) |
| win_method split | **~85% combat**, ~8% timeout, ~7% monument_drain |
| avg kill turn | ~7.8 |
| Lessons end life (avg) | **-6.5** (it is being KILLED) |
| Lessons END hand size (avg, plural-file probe) | **4.5** (cluster at 6; max 7) |
| Lessons END graveyard (avg, plural-file probe) | 19.1 (it casts a LOT) |

Two facts drive the entire design:

1. **The inversion is a PRE-TIMEOUT combat-death problem, not a timeout problem.**
   ~85% of games end in a combat kill around T6-8 with Lessons dead at -6.5 life.
   Only ~8% reach the turn-15 timeout. A timeout tiebreaker therefore touches
   roughly one game in twelve and CANNOT de-invert 20% -> >50% on its own.

2. **The card-advantage signal the scorer needs already exists and is reliable.**
   Lessons ends with avg 4.5 cards in hand (often 6-7) and a 19-card graveyard
   well before its average death (~T7.8 canonical). So the deck's card-advantage engine
   (Gran-Gran loot + Monument to Endurance + cantrips) DOES materialize in the
   sim. It just never converts that advantage into survival: Lessons sits on a
   six-card hand and still dies to the Selesnya clock.

Conclusion that re-scopes the tractable subset: the deck has the cards and loses
anyway. The load-bearing fix is therefore NOT "break the timeout tie" (Phase 1,
the safe primitive) but "model that an established card-advantage lead is an
inevitability that the opponent eventually concedes to, even while the
card-rich deck is behind on board/life" (Phase 2, the mandatory-but-harder
piece). This reordering IS the tractability call the task asks for.

---

## 1. What is and is NOT achievable

### Achievable (the tractable subset)

- **R6 scaffolding** that is byte-identical when OFF: a `WANTS_HIDDEN_INFO`
  capability flag on the base `MatchAPL`, a match-path gate mirroring
  `_warp_match_gate` / `_pw_match_gate`, and an `arl_profile` crediting branch
  mirroring how warp/stack are credited. This is clean, small, and provable.
- **Phase 1 - gated timeout inevitability tiebreaker** at the two timeout sites.
  Correct primitive; fixes the ~15% of games that reach turn 15. Insufficient
  ALONE for the Lessons inversion, but a real and safe fidelity gain (control
  decks that grind to time and lose the life tie despite a dominant board/hand).
- **Phase 2 - gated mid-game inevitability concession.** A two-sided, zero-RNG
  heuristic: when an opted-in deck holds a SUSTAINED card-advantage + resource
  lead over a window of turns AND is not facing imminent lethal, credit it the
  long-game win (model the opponent conceding to inevitability). This is the
  piece that can actually de-invert Lessons, and the diagnostic shows it CAN
  fire in time (hand elevated by ~T6, death at ~T7.8).
- **arl_profile crediting** of `hidden_information` when a deck declares
  `WANTS_HIDDEN_INFO` AND an `r6-*` proof exists - byte-identical for every deck
  that does not opt in.

### NOT achievable (out of scope; state plainly)

- **True hidden information.** The APLs are full-information decision functions;
  they read concrete game state, not belief distributions. Modeling information
  sets, bluffing, holding up an UNKNOWN answer, sculpting around unseen cards, or
  imperfect-information search is research-grade and would require rewriting the
  entire decision layer. Out of scope, permanently for this rung.
- **Why Lessons under-survives at the COMBAT level.** The deeper reason Lessons
  dies with a full hand is partly adjacent fidelity (does its spot removal /
  counter suite fire effectively vs a go-wide board; this overlaps R1 counters
  and combat resolution), not R6. R6 models the CONSEQUENCE of card advantage
  (inevitability), not the turn-by-turn attrition mechanics that produce it. If
  Phase 2's concession heuristic is calibrated too conservatively to fire before
  death, the residual inversion is an attrition-fidelity problem outside R6.

---

## 2. The capability flag and gate (scaffolding; byte-identical when OFF)

### 2.1 `apl/match_apl.py` (MODIFY - additive)

Add beside the existing R1/R2/R4/R5 flags (match_apl.py:44-80):

```python
# R6 hidden-information (card-advantage / inevitability) opt-in gate.
# Default OFF so every existing deck keeps the legacy life-total timeout and
# never receives a mid-game inevitability concession -> match path byte-identical.
# NOTE: this models card-advantage/inevitability, NOT literal hidden info /
# belief states (see spec section 1). The one (initial) opt-in class is the
# grindy card-advantage control deck IzzetLessonStandardMatchAPL.
WANTS_HIDDEN_INFO = False
```

No default method is required (unlike `priority_action` / `choose_pw_ability`):
the inevitability score is computed in the engine from zone counts, so no new
APL hook is mandatory. An OPTIONAL `inevitability_hint(self, my_gs, opp_gs)`
override may be added later for decks that want to bias their own score; base
returns 0.0 (neutral). Keeping the base hook absent in Phase 1 minimizes surface.

### 2.2 Match-path gate (MODIFY - additive, mirrors existing gates)

Add to BOTH runners, mirroring `_warp_match_gate` (match_runner.py:674) and the
`_instant_combat_enabled` / `_pw_match_gate` patterns:

- `engine/match_runner.py`: `_hidden_info_match_gate(gs)` reading
  `gs.apl_a` / `gs.apl_b` `WANTS_HIDDEN_INFO`.
- `engine/match_engine.py`: the analogous check using the `apl_a` / `apl_b`
  in scope in `run_match` (or `gs._self_apl` already wired there by R1, 1.4).

```python
def _hidden_info_match_gate(gs) -> bool:
    return bool(getattr(getattr(gs, "apl_a", None), "WANTS_HIDDEN_INFO", False)
                or getattr(getattr(gs, "apl_b", None), "WANTS_HIDDEN_INFO", False))
```

Fires iff EITHER seat opts in - consistent with every other rung. Combo-sampler
and goldfish paths never set `apl_a`/`apl_b`, so the gate is OFF there.

---

## 3. Phase 1 - gated timeout inevitability tiebreaker

### 3.1 The two timeout sites (BOTH must be gated - path parity)

There are TWO two-player runners and BOTH decide the timeout by raw life total:

- `engine/match_runner.py:1562-1566` (SB-less fallback / Path B):
  `result.won = gs.life_b < gs.life_a`
- `engine/match_engine.py:587-589` (canonical Bo3 / Path A):
  `mgs.winner = 'a' if mgs.gs_b.life < mgs.gs_a.life else 'b'`

R1 proved on Path A; R4/R5 live in Path B. R6 must gate BOTH so the verdict is
identical regardless of which runner a matchup takes. **Path-parity is an
explicit validation gate (section 6).** Note: the Standard gauntlet runs Path A
(Bo3); `ComboKillSampler` bypasses the engine entirely and neither Lessons nor
Selesnya is in `KILL_DISTS`, so the diagnostic / proof exercise the real engine.

### 3.2 The edit (each site)

```python
# match_engine.py:587-589, gated:
if _hidden_info_match_gate(mgs):
    mgs.winner = _resolve_inevitability_timeout(mgs)   # 'a' | 'b'
else:
    mgs.winner = 'a' if mgs.gs_b.life < mgs.gs_a.life else 'b'   # UNCHANGED
mgs.win_method = 'timeout'
```

`_resolve_inevitability_timeout` computes an inevitability score per seat
(section 5) and returns the higher; ties fall back to the legacy life
comparison (so the gate-ON path degenerates to the legacy verdict when the
inevitability signal is neutral). Identical shape at the match_runner.py site.

### 3.3 Byte-identical-when-OFF guarantee (Phase 1)

For any matchup where NEITHER seat sets `WANTS_HIDDEN_INFO`:
`_hidden_info_match_gate` returns False, the `else` branch runs the ORIGINAL
line verbatim, and `_resolve_inevitability_timeout` is never called. No new
`random()` is introduced on any path (the scorer is zero-RNG, section 5), and at
the timeout point the game loop has already ended so the RNG stream is not
consumed further regardless. **Falsifiable gate:** Boros Energy mirror
`run_match_set(n=1000, seed=42, mix_play_draw=True)` -> `a_wins / b_wins /
avg_turns` IDENTICAL pre/post R6 on BOTH runners (Boros sets no flag).

---

## 4. Phase 2 - gated mid-game inevitability concession (the de-inversion lever)

This is the part that can actually move Lessons 20% -> toward parity, because
the diagnostic shows the card-advantage signal is present and elevated (~T6)
BEFORE the average death (~T7.8).

### 4.1 Where it fires

In each runner's per-turn loop, AFTER the active player's post-combat phase and
win check, BEHIND the gate. Mirrors how `_run_pw_activations` is invoked once per
player-turn (match_runner.py:384). When OFF -> not called -> byte-identical.

### 4.2 The heuristic (two-sided, zero-RNG)

A seat is credited an inevitability concession on turn T iff ALL hold:

1. **Gate ON** for that seat (`WANTS_HIDDEN_INFO`).
2. **Sustained lead:** its inevitability score (section 5) has exceeded the
   opponent's by a margin `M` for `W` consecutive of its own turns (e.g. W=2).
   Persistence avoids one-turn-spike false positives. Tracked via a small
   per-seat counter stashed on the `gs` (additive attribute, gate-only).
3. **Not facing imminent lethal:** the opponent's on-board clock does not kill
   the credited seat next turn (reuse `MatchGameState.clock` /
   `attackable_creatures` on Path A; `power_b`/`life` on Path B). This is the
   guard that stops handing the game to a card-rich deck that is about to die -
   directly addresses the over-crediting risk.
4. **Floor turn:** T >= a minimum (e.g. 5) so early-game noise can't trigger it.

On trigger: set the winner to the credited seat, `win_method = 'inevitability'`.

### 4.3 Why this is honest, not a thumb on the scale

The concession only fires when a seat has a DURABLE resource lead AND is not
about to lose to the board. That is a faithful proxy for "the opponent is
drawing one-for-one against a deck drawing two-for-one and cannot win the long
game." It is a heuristic and will be wrong at the margins; that imperfection is
tracked (section 8), and the calibration target (`M`, `W`, floor) is set by the
WR gate, NOT by widening until the number looks right.

### 4.4 Honest risk on the Lessons matchup specifically

Even with Phase 2, de-inversion is NOT guaranteed. Lessons dies at avg ~T7.8 with
the opponent still on a winning board; the concession must fire in the T6-8 window while
Lessons is BEHIND on board/life but ahead on cards. Guard (3) ("not facing
imminent lethal") may suppress the trigger in exactly the games where Selesnya
already has lethal on board next turn - which is many of them. If guard (3)
suppresses too aggressively, Phase 2 will under-fire and the residual inversion
is an attrition-fidelity problem (Lessons should have REMOVED that board with its
card advantage) that lives outside R6. This is the central tractability caveat
and must be reported, not hidden, if the WR gate is missed.

---

## 5. The inevitability score (zero-RNG, deterministic)

`_inevitability_score(seat_gs, opp_gs) -> float`, computed from counts only:

```
score = w_life   * life
      + w_hand   * len(hand)
      + w_engine * recurring_engine_count
      - w_oppbrd * opp_board_power        # being under pressure lowers it
```

- **recurring_engine_count** is the load-bearing term, NOT raw hand size (a big
  hand can be dead cards - advisor point). Count permanents on the seat's
  battlefield that generate repeatable card advantage: a small curated set
  (Monument to Endurance, Gran-Gran, card-drawing planeswalkers) PLUS a generic
  oracle-text fallback ("draw a card" on a permanent's activated/triggered
  ability). The curated set keeps Phase-1/2 grounded for the target matchup; the
  oracle fallback generalizes.
- Weights are calibration parameters fixed by the WR gate (section 6).
- **Invariant: this function performs ZERO `random()`.** That is what keeps the
  Boros-mirror NR gate clean on both runners (section 3.3 / 6).

---

## 6. arl_profile crediting (clean, byte-identical for non-opt-in decks)

`scripts/arl_profile.py` already flags `hidden_information` but ONLY as a rider
on counterspell count (`_severity_for_counts`, lines 332-336: flagged iff
counters >= 2, severity == the counter severity). The fidelity map maps it to
`sim-no-hidden-information` (`data/engine_fidelity_map.json`).

### 6.1 Crediting branch (mirror warp/stack)

In `_apl_modeled_capabilities` (arl_profile.py:344), add - mirroring the existing
`WANTS_WARP`/`WANTS_PRIORITY_STACK` branches at lines 379-384:

```python
if getattr(cls, "WANTS_HIDDEN_INFO", False) and _proof("r6-"):
    modeled.add("hidden_information")
```

In `_severity_for_counts` (arl_profile.py:298), short-circuit at the
hidden_information assignment (the block at 332-336):

```python
if "hidden_information" in modeled:
    sev["hidden_information"] = "high"
elif c >= 2:
    sev["hidden_information"] = sev["counterspell_on_stack"]
else:
    sev["hidden_information"] = "high"
```

### 6.2 Byte-identical-when-OFF guarantee (profile side)

For every existing deck: no `WANTS_HIDDEN_INFO` flag and no `r6-*` proof ->
`_apl_modeled_capabilities` adds nothing to `modeled` ->
`"hidden_information" in modeled` is False -> the new `if` is skipped and the
existing `elif c >= 2 / else` runs verbatim. `_apl_modeled_capabilities` is
already fully guarded (returns empty set on any exception). **Falsifiable gate:**
run `build_profile` over ALL existing decks pre/post and diff every `<slug>.json`
- byte-identical except for decks that explicitly opt in.

### 6.3 IMPORTANT scope clarification (advisor point - do not overclaim)

R6 alone does NOT make Izzet Lessons "modeled" in the fidelity gate. Lessons has
7 counter-ish cards (verified: `decks/izzet_lessons_standard.txt`), so
`counterspell_on_stack` INDEPENDENTLY trips low/unmodelable. Even with
`hidden_information` credited, the deck's overall confidence stays gated by
counters until R1 ALSO credits them (the deck would need both
`WANTS_PRIORITY_STACK` and `WANTS_HIDDEN_INFO` + both proofs). Keep these
separate in the spec narrative:
- R6 fixes the WR INVERSION (engine output / gauntlet result).
- The fidelity GATE crediting Lessons as fully modeled needs R1 + R6 together.

### 6.4 OPTIONAL detection enhancement (deliberate gate diff - NOT byte-identical)

Flagging pure card-advantage decks that have < 2 counters (so `hidden_information`
currently never trips for them) is a SEPARATE, deliberate change to detection. It
is NOT byte-identical and must be validated with a before/after diff over ALL
existing profiles, reporting every confidence change. Do NOT smuggle this under
the byte-identical banner. Recommend deferring it until Phase 2 lands, since the
target deck (Lessons) already trips via its counters.

---

## 7. Build plan (isolated worktree; merge-only-if-green)

Mirror the R1 build discipline (R1 design section 3):

1. `EnterWorktree` branch `modelability/r6-hidden-info`.
2. FREEZE baselines at the branch-point commit FIRST: Boros mirror NR aggregate
   (both runners), Amulet goldfish, and the Lessons-vs-Selesnya pre-R6 WR +
   win_method split captured this spec (20% / ~85% combat, canonical deck).
3. Implement in order: (a) `match_apl.py` flag; (b) `_hidden_info_match_gate` on
   both runners; (c) `_inevitability_score`; (d) Phase 1 timeout edits (both
   sites); (e) Phase 2 concession hook (both sites); (f) arl_profile crediting.
4. Write `tests/test_r6_hidden_info.py` (section 6 below) with RED-pre / GREEN-post
   differentials; run RED-pre against the frozen commit.
5. Run the full acceptance gate; merge ONLY if every gate green; else
   `ExitWorktree`, leave the imperfection OPEN with a note.

Suggested sequencing: ship the scaffolding + Phase 1 + arl_profile crediting as
the first mergeable increment (clean, low-risk, provable), then iterate Phase 2
under its own WR gate. Phase 1 is the safe primitive; Phase 2 is the risky lever.

---

## 8. Proof + no-regression harness (acceptance gate)

### 8.1 Proof (differential - RED pre-R6, GREEN post-R6)

New `tests/test_r6_hidden_info.py` (standalone, `sys.path.insert`, plain asserts,
ASCII-only, prints "ALL R6 PROOF TESTS PASS", exit 0/1):

- TEST 1 (timeout tiebreaker fires): construct a timeout state where the
  opted-in seat is BEHIND on life but ahead on hand + recurring engines; assert
  it wins post-R6 and LOSES pre-R6 (gate OFF -> legacy life comparison).
- TEST 2 (concession fires mid-game): construct a sustained card-advantage lead
  over W turns with no imminent lethal; assert `win_method == 'inevitability'`
  for the opted-in seat post-R6, and no concession pre-R6.
- TEST 3 (over-credit guard): construct a card-rich seat that faces lethal next
  turn; assert NO concession is granted (guard (3) holds) - the card-rich seat
  still loses. This is the falsifier that proves Phase 2 is not a blanket
  thumb-on-the-scale.

GATE ON THE TEST: TEST 1 and TEST 2 MUST FAIL on the branch-point commit.

### 8.2 WR gate (statistical) and de-inversion target

- PRIMARY: Izzet Lessons (canonical `decks/izzet_lesson_standard.txt`) vs
  Selesnya Landfall, Path A, n>=1000, seed=42, mix_play_draw. RED pre-R6 = ~20%
  (this spec, n=60 canonical baseline). GREEN target = de-inversion,
  i.e. Lessons WR CROSSES 50% in Lessons' favor, moving toward the PT ~75%
  anchor. HONEST: exactly 75% is a calibration target, NOT the gate; the gate is
  (a) the concession mechanism FIRES (nonzero `win_method=='inevitability'`
  count) and (b) the sign flips (crosses 50%). If the sign does not flip because
  guard (3) suppresses the trigger (section 4.4), report it and treat the
  residual as an attrition-fidelity item outside R6 - do NOT relax guard (3) to
  force the number.
- NO-WRONG-FLIPS: Lessons vs an AGGRO matchup it SHOULD lose, and the Lessons
  MIRROR, must NOT be handed to Lessons by the concession. Predict and assert
  these stay within band pre/post.

### 8.3 No-regression (byte-identical)

- NR-1: Boros Energy mirror `run_match_set(n=1000, seed=42)` -> identical
  `a_wins/b_wins/avg_turns` pre/post on BOTH runners (Boros sets no flag).
- NR-2: Amulet Titan goldfish bit-identical at seed=42 (gate never set on
  goldfish path).
- NR-3 (PATH PARITY): a fixed opted-in timeout/concession scenario yields the
  SAME verdict on match_runner.py and match_engine.py.
- NR-4: `scripts/full_audit.py --formats standard` -> 4218/4218 (R6 is
  control-flow, not handlers).
- NR-5: arl_profile diff over ALL existing decks -> byte-identical JSON except
  opt-in decks (section 6.2).
- NR-6: existing APL/determinism test suite green
  (`test_determinism.py`, `test_match_engine.py`, modern/standard APL suites).

Compare against the FROZEN branch-point capture, not historical hardcoded
numbers.

---

## 9. Gotchas (the kind that only show up in the real code)

1. **Both timeout sites decide by life** (match_runner.py:1563 AND
   match_engine.py:588). A naive single-site edit breaks path parity; the gauntlet
   uses Path A but R4/R5 live in Path B, so both are reachable. Gate BOTH.
2. **The gate fires for EVERY matchup the opt-in deck plays**, not just the one
   being fixed. Opting Lessons in changes its timeout AND mid-game resolution vs
   ALL opponents. The mirror and vs-aggro no-wrong-flips gate (8.2) exists
   precisely to catch this.
3. **Hand size is a deceptive proxy** - the diagnostic shows Lessons sits on a
   6-card hand and still dies. Raw hand size must NOT dominate the score; weight
   recurring-engine count (section 5). A scorer keyed on hand size alone would
   credit any flooding deck.
4. **The swallowed-exception path** in `_simple_play_turn` (match_runner.py:251)
   and `_run_post_combat_phase` (545) prints a WARN and continues when an APL
   raises without `SIM_DEBUG`. If the Lessons APL silently fails to execute its
   draw engine, the card-advantage signal vanishes and Phase 2 is inert. The
   diagnostic confirms the signal IS present today (gy avg 19.1), but any APL
   edit must re-confirm under `SIM_DEBUG=1` that no exception is being eaten.
5. **`hidden_information` already trips via counters** for Lessons (rides the
   `counterspell_on_stack` severity at 2+ counters). Do not double-count or
   assume R6 is what flags it; R6's crediting branch is what UN-flags it once the
   proof exists. And it does not clear the counter-driven gate (section 6.3).
6. **Zero-RNG is non-negotiable** for both the scorer and the concession hook -
   any `random()` on the gate-ON path perturbs determinism and, if it ever leaks
   to a shared helper, the gate-OFF NR-1 bit-identical guarantee. Mirror the R1
   `priority_stack` "zero random()" discipline.
7. **`gs.apl_a`/`gs.apl_b` vs `gs._self_apl`.** match_runner stashes `apl_a`/
   `apl_b` on the TwoPlayerGameState (run_match:1494); match_engine wires
   `gs._self_apl` (R1, design 1.4). The gate helper must read the attribute that
   the respective runner actually sets - do not assume one shape on both paths.
8. **Phase 2 may under-fire on the very matchup it targets** (section 4.4): guard
   (3) suppresses the concession when the card-rich deck faces lethal next turn,
   which is common for Lessons-vs-Selesnya. This is the honest tractability
   ceiling: R6 models the consequence of card advantage, not the attrition that
   should have kept Lessons alive.

---

## 10. IMPERFECTIONS to register on ship

- Inevitability score is a heuristic; recurring-engine detection is a curated set
  + oracle fallback, not a semantic model of each engine's rate.
- Phase 2 concession is a proxy for opponent scoop; it can mis-fire at the
  margins (mitigated by sustained-lead + not-imminent-lethal guards).
- Residual Lessons inversion (if guard (3) suppresses the trigger) is an
  attrition-fidelity gap outside R6 scope; cross-link to R1 counters and combat
  resolution.
- Optional arl_profile detection for <2-counter card-advantage decks deferred
  (section 6.4).

---

## 11. GO / NO-GO

**NO-GO for autonomous implementation now. HOLD for user review.** This is the
hardest rung, it edits shared-path timeout logic on BOTH runners plus a mid-game
hook, and the diagnostic shows the headline mis-model is only partially within
R6's reach. On approval, proceed PHASED: scaffolding + Phase 1 + arl_profile
crediting first (clean, low-risk, provable), then Phase 2 under its own WR gate,
honestly reporting if guard (3) caps the de-inversion.

---

## Appendix - file-change list (absolute paths)

- MOD  E:/vscode ai project/mtg-sim/apl/match_apl.py (WANTS_HIDDEN_INFO=False; optional inevitability_hint)
- MOD  E:/vscode ai project/mtg-sim/engine/match_runner.py (_hidden_info_match_gate; gated timeout site ~1563; Phase 2 hook in turn loop)
- MOD  E:/vscode ai project/mtg-sim/engine/match_engine.py (_hidden_info_match_gate; gated timeout site ~588; Phase 2 hook; _inevitability_score)
- MOD  E:/vscode ai project/mtg-sim/apl/izzet_lesson_standard_match.py (WANTS_HIDDEN_INFO=True - the initial opt-in)
- MOD  E:/vscode ai project/mtg-sim/scripts/arl_profile.py (_apl_modeled_capabilities r6 branch; _severity_for_counts short-circuit)
- KEEP E:/vscode ai project/mtg-sim/engine/counter_resolver.py (UNCHANGED)
- KEEP E:/vscode ai project/mtg-sim/data/engine_fidelity_map.json (hidden_information id retained)
- ADD  E:/vscode ai project/mtg-sim/tests/test_r6_hidden_info.py
- ADD  E:/vscode ai project/mtg-sim/modelability_proofs/r6-hidden-info-2026-06-27.json (proof artifact, on impl)
