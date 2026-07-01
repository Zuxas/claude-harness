# Boros Energy Post-Ban Build-Off — Recommendation (Arc #6)

**Date:** 2026-07-01
**Branch (mtg-sim):** modern-postban-arc | setup commits `1a0b88f`, `d242351`
**Primer:** `harness/handoffs/modern-best-boros-energy-build.md` (grounded in `TeamResolve_BorosEnergy_Primer_4.pdf`)
**Engine:** shared `BorosEnergyMatchAPL`; 18-row modeled Modern field (`format_config.py`)

---

## TL;DR — RECOMMENDATION

**Play the Low Curve build** (`decks/boros_energy_lowcurve_modern.txt`, registry `borosenergylowcurve`).

**Verdict: PROVISIONAL.** Low Curve tops BOTH ranking lenses and is the only fully-piloted, paper-validated list (real-world 58-25 / 70% match WR). It beats Fable by a real, multi-SE margin. It is **NOT** a CLEAR_WINNER because its nearest rival, the Jitte build, (a) is a head-to-head coin-flip against it (49.6%, 0.25 SE — noise) and (b) is fidelity-gated (Umezawa's Jitte is UNMODELED), so the top-of-table separation cannot be cleanly established. All field-weighted numbers are estimates (documented pre-ban field, no post-ban DB).

---

## 1. Rankings (both lenses)

Field weights are a **DOCUMENTED ESTIMATE** — pre-ban 30-day baseline (1591 decks, 2026-03-25..04-24) with transparent per-ban deltas. **No post-ban Modern tournament DB exists**; re-pull when it lands. Every field-weighted number below is therefore an estimate.

| Rank | Build | Full-field WR | Trustworthy-only WR | Status |
|------|-------|---------------|---------------------|--------|
| 1 | **Low Curve** (`borosenergylowcurve`) | **74.55%** (n=220) | **70.39%** (13 non-flagged cells) | Fully piloted; paper-validated |
| 2 | **Jitte** (`borosenergyjitte`) | 66.3% (n=200) | 66.5% (14 non-flagged cells) | **PROVISIONAL — whole build gated** |
| 3 | **Fable** (`borosenergyfable`) | 61.0% (n=200) | 61.7% (14 non-flagged cells) | Reads low (2 dead-Fable blanks) |

- **Order is robust on every lens** — Low Curve > Jitte > Fable holds on full-field AND trustworthy-only, and is confirmed head-to-head.
- Low Curve's trustworthy-only 70.39% lands essentially ON the real-world 70% match WR (58-25). This is the credible number: ~34% of field weight sits on mismodeled cells, so the full-field 74.55% is inflated upward.
- Jitte's 66.3/66.5% is a **~57-card deck + 3 dead blanks** and reads STRICTLY LOW — do not compare it 1:1 to Low Curve or to paper (see #3).
- Fable's 61.0/61.7% is a milder version of the same defect (2 cast-inert Fable), visible directly in its sub-50 mirror cell (49.0%).

### Head-to-head (mirror-core, shared APL; WR of first-named)
- **Low Curve vs Fable: 58.1%** (n=1000, seed=7) → 8.1pp = **5.2 SE = SIGNAL** (Low Curve favored). Pooled 1700-game independent sample: 58.0%.
- **Low Curve vs Jitte: 49.6%** → 0.4pp = **0.25 SE = NOISE (true coin flip)**. Stable ~50% at every n tested; pooled 49.9%.
- **Fable vs Jitte: 41.4%** (Jitte 58.6%) → **5.5 SE = SIGNAL** (Jitte favored). Pooled Jitte 57.6%.
- Ordering: **Low Curve ≈ Jitte > Fable.** Fable is the clear loser to both.
- **Caveat (`rests_on_flagged=true`):** these gaps are driven partly by cast-inert dead blanks (3 Jitte, 2 Fable) under the shared APL. The head-to-head validates the *core+blanks* ordering, NOT the Jitte or Fable axes themselves. Jitte ties Low Curve *while carrying 3 dead cards* — its strength comes from the non-Jitte swaps (2 Ranger-Captain of Eos, 2 Lightning Bolt, leaner curve, no Phlage top-end), not from Jitte.

---

## 2. Why PROVISIONAL, not CLEAR_WINNER

The primer's gate: a build is CLEAR_WINNER only if its margin holds on TRUSTWORTHY cells AND exceeds ~2-3 SE. Low Curve clears this **against Fable** (~5 SE) but **not against Jitte** (49.6% h2h = noise; gauntlet 70.39 vs 66.5 trustworthy cannot be trusted because Jitte's number is fidelity-gated and reads artificially low). The real margin secures the *order*, not top-of-table *separation*. Combined with the estimated field, the honest verdict is a firm recommendation-with-caveats = **PROVISIONAL** (not INCONCLUSIVE — we can and do firmly recommend Low Curve as the only fully-piloted, paper-validated, top-of-both-rankings option).

---

## 3. The Jitte axis — GATED / PROVISIONAL (do not crown)

**Setup `jitte_fidelity` verdict: UNMODELED.** Umezawa's Jitte is a cast-inert dead blank under the shared engine:
- No `Umezawa's Jitte` key in any handler dict; the only "Jitte" handler is `_lost_jitte_etb` (a *different* card).
- **Equip is not modeled** — equipment handlers are uniformly log-only stubs (Batterskull/Cranial Plating/etc. just log "equipment on board"); no generic equip step, no equipped-creature stat layer.
- **Charge counters not modeled** — no charge-counter-on-combat-damage hook in the combat path.
- **All three modes unmodeled** — +2/+2 EOT, -1/-1 to a creature, gain 2 life: none implemented.
- `BorosEnergyMatchAPL` has no Jitte constant and no artifact/equip cast path, so even setting the engine aside the card is never deployed.

**Consequence:** every Jitte-build number (66.3 full / 66.5 trustworthy) is PROVISIONAL, reflects a ~57-card deck + 3 blanks, and reads strictly LOWER than the paper build. **We do NOT crown Jitte on an unmodeled number**, even though its non-blank core ties Low Curve — that datum says "the leaner non-Jitte swaps look competitive," nothing more.

**Engine work that would unlock a believable Jitte number (out of scope this arc):**
1. Add an `Umezawa's Jitte` constant and an artifact/equip **cast path** to `BorosEnergyMatchAPL`.
2. Add a generic **equip step** + an **equipped-creature stat layer** to the engine (equipment handlers are log-only stubs today).
3. Add a **charge-counter-on-combat-damage hook** in the combat path (`engine/match_runner.py` / `engine/game_state.py`).
4. Implement the **three modes**: +2/+2 until EOT, -1/-1 to a creature, gain 2 life.

Until (1)-(4) land, Jitte cannot be measured on card quality — only on dilution.

---

## 4. Tuning findings (signal vs noise)

Base = Low Curve (the only build the shared APL fully pilots). Field-weighted per-game G1 delta is the noise gate. **No sideboard experiments were run — everything here is G1 / SB-unmodeled.**

- **(a) 3rd Reckless Pyrosurfer — WITHIN NOISE, keep at 2.** Modeled (on_landfall battle-cry accrual). n=500, SE(dG1)=0.76pp. +Pyro3/−Thraben Charm#2 (clean): dG1 = −0.20pp (0.3 SE). +Pyro3/−Seasoned#3 (contaminated): −0.54pp (0.7 SE). Sign-stable ~0-to-slightly-negative; does not clear noise. **A wash — stay at 2.**
- **(b) Jitte 0/1/2 — BLOCKED BY FIDELITY GATE, not a tuning result.** Jitte is UNMODELED, so the sweep measures only DILUTION: +1 Jitte(−Thraben) dG1 = −0.77pp (1.0 SE); +2 Jitte dG1 = −1.18pp (1.6 SE). Monotone ~−0.6 to −0.8 G1pp per dead blank = the dilution signature. **No card-quality signal obtainable until the engine models Jitte (#3).**
- **(c) The one real signal — KEEP the 4th Guide of Souls.** n=1500, SE(dG1)=0.43pp. Swapping Guide of Souls 4→3 for a 4th Seasoned Pyromancer: dG1 = **−1.18pp (2.7 SE, CLEARS; survives Bonferroni across 6 arms)**, dMATCH = −1.87pp. Fidelity-clean; the Seasoned over-credit confound is in the SAFE direction; sign-robust to removing flagged Affinity (−0.86pp @ 2.3 SE ex-Affinity). **VERDICT: do NOT cut the 4th Guide of Souls for a 4th Seasoned.**
- **(c′) Voice of Victory 4→3 for Seasoned — SUGGESTIVE only.** dG1 = +0.95pp (2.2 SE) — fails Bonferroni (p≈0.028 vs 0.008), and doubly confounded (Seasoned over-credit + Voice cast-lock only partially modeled → Voice under-credited). Derived Seasoned-free contrast suggests ordering Guide#4 > Seasoned#4 > Voice#4 ("if trimming a 4-of, trim Voice first"), but carries the Voice-undervalue caveat. Revisit only if the Voice cast-lock is fully modeled.

---

## 5. Provisional calls (everything resting on a flagged cell or the estimated field)

1. **All field-weighted numbers** (full AND trustworthy, all three builds) rest on the **documented-estimate field** — no post-ban Modern DB. Re-pull and re-run when post-ban data lands.
2. **Full-field ranking is inflated by 4 flagged field cells** (~34% of Low Curve's field weight): Affinity/Izzet-Affinity [INFLATED, truth ~44%], Living End [INFLATED, cascade under-fires], Goryo's Vengeance [INFLATED, truth ~73% still favored], Grixis Reanimator [**INVERTED** — sim favors us ~57% but truth ~38%, we are the DOG]. Trust DIRECTION, not the number, on these; prefer the trustworthy-only column.
3. **The entire Jitte build number is provisional** (whole-build gated, Jitte UNMODELED — see #3).
4. **Fable reads low** from 2 cast-inert Fable-of-the-Mirror-Breaker blanks (milder version of the Jitte gap; visible in the 49.0% mirror cell).
5. **Any individual read on the 4 flagged cells** above is provisional (direction only).
6. **Broodscale Combo — NO build was validated against it.** It is one of the primer's HARDEST post-BnR matchups, but its sim cell is an INFLATED synthetic stub (sim ~89% vs truth ~55%, no infinite combo modeled) and it is **not a field row / never gauntleted**. This is a real coverage hole for the recommendation.
7. **Death and Taxes + Temur Crashcade are synthetic stubs** (Jitte / cascade unmodeled) — they read TRUST only because they are absent from `mismodeled_matchups.py`; they are **NOT primer-validated**. (Also: two Jitte-build TRUST cells — Dimir Midrange, Death and Taxes — are credibility-capped by the INTERACTIVE rule, not raw sim.)
8. **Voice-of-Victory tuning (c′) is suggestive only** (partial cast-lock model + Bonferroni failure).
9. **All TRUST cells are SB-unmodeled (G1-representative)** — no sideboard plans were modeled for any build.

---

## Reproduce

- Gauntlets: `PYTHONHASHSEED=0 python parallel_launcher.py --deck <borosenergylowcurve|borosenergyfable|borosenergyjitte> --format modern --n 200 --top-n 18 --seed 42 --cores 18`. Raw: `data/parallel_results_20260701_130148.json` (fable), `..._130216.json` (jitte); `scratchpad/lowcurve_gauntlet.py` + `scratchpad/lowcurve_result.json`.
- Head-to-head: `scratchpad/h2h.py` (`engine/match_engine.run_match_set`, mix_play_draw, PYTHONHASHSEED=0).
- Tuning: `scratchpad/run_ab.py` + `build_variants.py`; logs `ab_n500.log`, `ab_flex_n1500b.log`; `ab_results.json`.

## Changelog
- 2026-07-01: Arc #6 build-off synthesis authored. Recommend Low Curve (PROVISIONAL). Jitte axis gated on engine fidelity. Keep 4th Guide of Souls; 3rd Pyrosurfer = wash; Jitte count untunable until modeled.
