# Next-Fronts Roadmap — Risk-Ordered Execution Plan
**Date:** 2026-06-27
**Author:** synthesis pass over 4 front-designs (Stage B Izzet Affinity, R3 Storm, R6 Hidden Info, backlog triage)
**Audience:** careful engineer executing solo, sequentially
**Ordering principle:** value / risk / dependency — cheap-safe-high-value first, expensive-risky-uncertain last.

---

## TL;DR — TOP-3 NEXT ACTIONS

| # | Action | Effort | Risk |
|---|--------|--------|------|
| 1 | **Reconcile pass on `harness/IMPERFECTIONS.md`** — close ~10 already-fixed OPEN entries, annotate the structural rung entries (sim-no-stack-priority / instant-combat / planeswalker-loyalty / warp-mechanic) as SUPERSEDED by shipped R1/R2/R4/R5, narrow residual to "per-deck `WANTS_*` wiring". | 30-45 min | near-zero (doc-only, no code) |
| 2 | **Stage B — Izzet Affinity counters** — re-base `IzzetAffinityMatchAPL` on `AwareMatchAPL` + `WANTS_PRIORITY_STACK=True`, add `Metallic Rebuke` to `counter_resolver.py COUNTER_VALIDITY`. Flips the deck's fidelity gate low→high. | ~15-25 lines across **2 isolated files** + ~half-day decomposed validation | medium (risk is in **validation**, not code) |
| 3 | **R3 — Storm mechanic** behind `WANTS_STORM` — gated main1 spell-damage sync in `_simple_play_turn` + fidelity-gate wiring + Ruby Storm APL rewrite through `cast_spell`. Next fidelity-ladder rung; storm decks stop being false-high. | ~6-line engine sync + mechanical fidelity wiring + APL rewrite; one-to-few sittings | medium (contained engine change, crisp abort triggers) |

**Defer:** R6 Increment 2 (high risk, multi-week, de-inversion may be structurally capped); warp-cost-unbraced (trap — tiny diff but non-byte-identical, needs per-deck re-baseline); card-specs Phase B; CI runner (human-in-loop); low-value no-APL aliases; oracle audits.

---

## WHY THIS ORDER

### 1. Reconcile pass — FIRST, unconditionally
- **Value: high.** The triage headline is that the IMPERFECTIONS registry is ~1/3 decayed: of ~30 OPEN entries, ~10 are already fixed in code (including the two newest 2026-06-26 entries). Every future triage built on this registry is untrustworthy until reconciled — you would waste a session re-discovering fixed work, and risk "fixing" things already done.
- **Risk: near-zero.** Doc-only. No code touched. Each entry is verified against a cited code location, Status flipped to RESOLVED, moved to `RESOLVED.md`.
- **Dependencies: none.** It is the prerequisite for *trusting* everything downstream.
- **Load-bearing side effect:** annotating the structural entries as SUPERSEDED redefines the genuine residual as "per-deck `WANTS_*` wiring." That residual's canonical instance is **Stage B** — so step 1 sets up step 2's framing directly.

### 2. Stage B (Izzet Affinity) — SECOND
- **Value: medium.** Promotes Izzet Affinity (~7-9% of Modern top-8 field) from "low" to "high" fidelity confidence by routing its 3 Metallic Rebukes through already-shipped R1 priority-stack machinery. It is the concrete proof of the per-deck-wiring residual the reconcile pass just defined.
- **Risk: medium — but the risk lives in validation, not code.** No engine-mechanism change (R1 already shipped). The code is ~15-25 lines across **two files that no other front touches**: `apl/affinity_match.py` and `engine/counter_resolver.py`. R3 explicitly leaves `counter_resolver.py` unchanged; neither R3 nor R6 touch `affinity_match.py`. **Lowest merge-surface, zero-engine-change item of the three capability fronts** — this is the discriminator that places it at #2.
- **Dependencies:** R1 (shipped). Nothing else.
- **The real risk to honor (not the sanitized "medium" label):** flipping affinity's gate ON also swaps how *opponents* counter affinity — legacy `try_counter_spell` (loose `_tap_lands_for_response` mana) → R1 `_pay_for_counter` (real untapped mana). Field opponents tap out, so they often *can't* counter affinity under R1 (generally favors affinity). The FWR delta therefore conflates THREE things: affinity's new counters + the opponent counter-path swap + affinity's new reserve-mana tempo cost. A naive `FWR≥41% → ship` bakes in inflation.
  - **Mandatory mitigations:** decompose via `COUNTERS_CAST` on **both seats**; report opponent-counters-affinity count gate-OFF vs gate-ON; sweep `COUNTER_COST {0,1,2,3}` (0 flips the gate but barely fires Rebuke; 3 over-taxes the clock). This is what turns "half a day" into the dominant cost of the front.
  - Premise correction baked into the spec: the re-base does NOT change combat or mulligans (MRO shadows `AwareMatchAPL` via affinity's own `declare_attackers`/`declare_blockers`/`keep`/`bottom`/`main_phase` overrides). The genuinely new behaviors are `reserve_mana` firing and the defense instant hooks (override both to `pass`).

### 3. R3 (Storm) — THIRD
- **Value: medium-high (capability).** Extends the fidelity ladder to a whole new mechanic class: storm decks (Ruby Storm) currently score a FALSE-high because the gate is blind to storm. R3 makes storm detected / severity-mapped / credited.
- **Risk: medium, contained.** Unlike R1/R2/R4/R5, storm is HALF-BUILT: storm count + copy-on-resolve already work in goldfish. The single genuine engine change is the **gated main1 spell-damage sync** in `_simple_play_turn`, gated on the ACTIVE player's `WANTS_STORM` (active-only, not either-seat — either-seat would leak the opponent's main1 face burn). Byte-identical OFF, mirrors the verified `_run_post_combat_phase` sync. Crisp abort triggers (`STORM_PAYOFFS_RESOLVED==0`, avg copies==1, any Class-A break).
- **Dependencies:** none functional. See R3↔R6 coupling note below.
- **The real risks to honor:**
  - The lifecycle proof MUST assert on the match-path `TwoPlayerGameState` (`gs.life_b` / `gs.damage_to_b`) immediately after `_simple_play_turn` — NEVER on `view.damage_dealt`, which is green pre AND post (the handler always copies on the view) and is therefore non-discriminating.
  - `RubyStormMatchAPL.AUTO_GENERATED=True` bypasses `cast_spell`, so storm count is permanently 0 on the match path. The APL rewrite to route casts through `cast_spell` (payoff last) is REQUIRED or the gate has nothing to propagate — it is the fiddliest piece.
  - arl_profile changes are NOT engine-byte-identical (every deck's `mechanic_counts` JSON gains a `storm:0` key); the guarantee is gate-VERDICT-identical for non-storm decks. State this honestly.

### Defer: R6 (Hidden Information) — LAST, and SPLIT
- **Value: high if it lands, but the high-value half may not land.** R6 targets the worst card-advantage / inevitability mis-models (e.g. the inverted Izzet Lessons 20% WR).
- **Risk: high. Multi-week, phased.** Split it:
  - **R6 Increment 1** (scaffolding + Phase-1 timeout tiebreaker + arl_profile crediting + TEST1/TEST3 + NR gates): ~2-4 focused days, clean, low-risk, mergeable on its own. BUT it is groundwork — the timeout decides only ~8% of the Lessons matchup, so **Inc 1 cannot de-invert anything.**
  - **R6 Increment 2** (Phase-2 mid-game inevitability concession + WR de-inversion calibration): ~1-2 weeks WITH real risk the de-inversion is **structurally capped by its own guard(3)** ("not facing imminent lethal"), which suppresses the trigger on exactly the Lessons-vs-Selesnya games it targets. Do NOT relax guard(3) to force the WR number — the residual is an attrition-fidelity gap outside R6 scope.
- **Why defer:** the expensive half (Inc 2) is the only one that delivers the headline value, and it may cap short of the anchor. Don't let it gate the cheap, certain wins above it. If/when capacity allows, land **R6 Inc 1 only** as standalone groundwork; treat Inc 2 as a separate bet.

---

## DEPENDENCY MAP (explicit answer to "does R3 or R6 need anything from the other?")

- **R3 ↔ R6: NO functional dependency, either direction.** Both are independent fidelity-ladder rungs. Both depend only on already-shipped **R1**. R6's *fidelity-gate* goal needs R1, NOT R3. R3 is fully standalone.
- **The only R3↔R6 coupling is shared-file soft-conflict:** both add a `WANTS_*` flag to the base `apl/match_apl.py`, and both add a crediting branch + a `_severity_for_counts` rule to `scripts/arl_profile.py`. → land them **sequentially**; the second one rebases on the first. Pick R3 first (lower risk, contained).
- **Stage B is the most file-isolated front:** it touches ONLY `affinity_match.py` + `counter_resolver.py` and relies on the *existing* R1 crediting logic (`WANTS_PRIORITY_STACK` + `r1-` proof). Zero overlap with R3/R6's `arl_profile.py` / `match_apl.py` edits, and R3 leaves `counter_resolver.py` untouched. → Stage B can land before, between, or after R3/R6 with no merge coordination.
- **The Stage B ↔ R6 latent tie:** R6's own gotcha states that clearing the Lessons *fidelity gate* needs Lessons wired to R1 (`WANTS_PRIORITY_STACK`, since it runs ~7 counter-ish cards) **PLUS** R6. That is the **same per-deck-wiring residual Stage B exemplifies.** Stage B is not "one deck" — it is the **template** for the residual that the reconcile pass (step 1) just redefined. This is the thread that ties the whole roadmap together: reconcile redefines the residual → Stage B is its first concrete instance → R6 (eventually) needs the same wiring for Lessons.

---

## FULL SEQUENCE (value/risk/dependency)

1. **Reconcile pass** — near-zero risk, high value, no deps. *(do now)*
2. **Stage B Izzet Affinity** — medium risk (validation-bound), medium value, dep: R1 (shipped), zero merge surface.
3. **R3 Storm** — medium risk (contained), medium-high capability value, dep: R1 (shipped); land before R6 to claim the shared wiring first.
4. **`scripts/mulligan_sweep.py`** — low risk (additive new script), med-high value (calibrates `keep()` vs external Nettle 2-1-2 baseline), no deps. The only genuinely-unstarted spec that is additive + low-risk + has an external validation anchor. Good independent/parallel filler; 90 min script + 2-4h unattended compute.
5. **R6 Increment 1 only** — ~2-4 days, low-risk groundwork (timeout tiebreaker + crediting + scaffolding). Land sequentially after R3 (shared `match_apl.py`/`arl_profile.py`).
6. **DEFER (do not schedule until the above clears):**
   - **R6 Increment 2** — high risk, ~1-2 weeks, de-inversion may be guard(3)-capped.
   - **warp-cost-unbraced** (`game_state.py:719-725`) — TRAP, not a quick win: 15-min diff but **non-byte-identical** (free→costed shifts affected decks' scores), requires per-deck re-baseline. Schedule deliberately, not opportunistically.
   - **card-specs Phase B** (boros_energy / jeskai_blink import card_specs) — medium risk, Boros locked at 64.5%/78.8%, bit-stable gate mandatory.
   - **GitHub Actions self-hosted runner** — low risk but human-in-loop (manual UI + admin PowerShell), not fully agent-automatable.
   - **no-APL aliases** (temur-prowess / sultai-midrange / grixis-midrange) — genuinely low-risk + bounded but low value (1.5-1.7% field each; sultai/grixis aliasable to dimir_midrange).
   - **llm-as-judge-apl-evaluation**, **skill-system-harness**, **mtg-strategy KB hygiene** — additive, low-risk, operational value; backlog.
   - **cross-canonical oracle audits / Temur Breach SHIM** — compounding value but 16-32h, each fix canonical-baseline-affecting.

---

## HONEST BOTTOM LINE
The reconcile pass is the only unambiguous first move — it is near-free and every downstream triage is untrustworthy until it runs, and it conveniently redefines the real residual as "per-deck `WANTS_*` wiring," whose first concrete instance is Stage B. Stage B then earns #2 not because it is the highest-value front but because it is the lowest-risk, lowest-merge-surface one (two isolated files, zero engine change, R1 already shipped) — provided you respect that its true cost is the decomposed `COUNTERS_CAST`/`COUNTER_COST`-sweep validation that prevents the opponent-counter-swap from inflating FWR, not the 20 lines of code. R3 follows as the next contained ladder rung and should claim the shared `match_apl.py`/`arl_profile.py` wiring before R6 touches it. R6 is the right long-term target but its valuable half (Increment 2 de-inversion) is high-risk, multi-week, and may be structurally capped by its own over-credit guard — so split it, land only the clean Increment 1 groundwork when capacity allows, and never let the uncertain half gate the certain wins above it. R3 and R6 have no functional dependency on each other (both ride shipped R1); their only coupling is shared-file merge ordering, which is solved by doing them sequentially.
