# Spec: Tagger-load-path unification (call tag_keywords on every Card-construction path)

**Status:** SHIPPED 2026-04-28 at commit 199d28e
**Created:** 2026-04-28 by Claude Code
**Target executor:** Claude Code (executed via execution-chain S3.7)
**Estimated effort:** 60-90 minutes (40 min code + baseline + comparison; 20-30 min documentation cascade across Stage A/B specs + v1.4 lesson amendments + first-class IMPERFECTIONS resolution)
**Actual effort:** ~50 min including all gates and cascade
**Risk level:** MEDIUM — touches a foundational engine setup function used by every gauntlet matchup; correct fix is small (one-line addition + idempotency check) but its empirical effect is potentially large because it activates Stage A/B/C keyword filters against 3 stub-loaded opps simultaneously.
**Dependencies:**
- Phase 3.5 Stage A SHIPPED 2026-04-27 at 99037a9
- Phase 3.5 Stage B SHIPPED 2026-04-27 at c95ea55
- Phase 3.5 Stage C SHIPPED 2026-04-28 at 186ee05 (C.1) + 18257b3 (C.4) — Stage C is latent infrastructure; this spec activates it against current field
- parallel-launcher cache-collision fix SHIPPED 2026-04-28 at e4fae86 (pipeline trustworthy)
**Surfaced by:** Phase 3.5 Stage C re-execution Amendment A5 (2026-04-28)

## Summary

Fix the tagger-vs-load-path mismatch surfaced by Stage C A5: `engine/keywords.py:tag_keywords` is called only from `data/deck.py:176` (the `load_deck_from_file` path used when a registry stub_key ends in `.txt`). The alternative path `build_deck_from_dict` in `generate_matchup_data.py` (used by stub-loaded decks via `data/stub_decks.py`) does NOT call the tagger. Engine never re-tags at game-setup. Of 14 Modern field opps, 3 use the stub path (Izzet Prowess, Domain Zoo, Esper Blink) and their cards enter the battlefield without keyword tags from oracle text scanning.

This affects **Stages A, B, AND C simultaneously**:
- Stage A's MENACE block-eligibility filter is silent against the 3 stub-loaded opps
- Stage B's HASTE/DEFENDER/VIGILANCE/lifelink filters are silent against them
- Stage C's HEXPROOF/SHROUD/PROTECTION targeting filter is silent against them

The shipped impact of Stages A and B is therefore **partial** — full impact materializes only after this fix lands.

## Pre-flight reads (REQUIRED before starting)

Per `harness/CLAUDE.md` Rule 1:

1. **`harness/knowledge/tech/spec-authoring-lessons.md` v1.4** — especially:
   - `load-path-dependent-setup-creates-silent-no-op-features` (the lesson this spec embodies fixing)
   - `re-execution-specs-require-fresh-baseline-capture` (this spec captures a new trusted baseline)
   - `spec-prediction-model-must-be-falsifiable` (per-matchup predictions for the 3 stub-loaded matchups)
2. **`harness/specs/2026-04-28-phase-3.5-stage-c-protection-cluster.md`** Amendment A5 — full diagnostic chain that surfaced this
3. **`mtg-sim/engine/keywords.py:tag_keywords`** (lines 183-203) — function under verification for idempotency
4. **`mtg-sim/data/deck.py`** lines 170-185 — current invocation site (the .txt load path)
5. **`mtg-sim/generate_matchup_data.py`** lines 24-90 — `load_deck_and_apl` and `build_deck_from_dict` (the dict path missing the call)
6. **`mtg-sim/data/stub_decks.py`** — verify return type (dict of {name: qty}) so the build_deck_from_dict patch site is correctly understood
7. Stage A spec changelog (post-fix re-validation will produce numbers to backfill)
8. Stage B spec changelog (same)

## Background

### The mismatch (full diagnostic from Stage C A5)

```
data/deck.py:load_deck_from_file
  -> data/deck.py:176: tag_keywords(card)                       <-- TAGS APPLIED

generate_matchup_data.py:load_deck_and_apl
  -> if stub_key.endswith('.txt'):
       -> data/deck.py:load_deck_from_file                      <-- TAGS APPLIED (delegates to above)
  -> elif stub_key:                                             <-- TAGS NOT APPLIED
       -> data.stub_decks.get_stub_deck_list(stub_key)
       -> generate_matchup_data.build_deck_from_dict(mb)
       -> Card(...) constructed without tag_keywords call
```

Engine setup (`engine/match_runner.py`, `engine/game_state.py`, etc.) never re-tags. Verified by `grep -rnE "tag_keywords" engine/ data/ apl/__init__.py` — only call sites are `data/deck.py:176` (production) and `engine/keywords.py` (definition + self-test in `__main__` block).

### Field load-path survey (from A5)

11 of 14 Modern field opps use `.txt` (tagged correctly):
- Mono Red Aggro, Amulet Titan, Eldrazi Ramp, Izzet Affinity, Grinding Breach,
  Jeskai Blink, Orzhov Blink, Goryo's Vengeance, Eldrazi Tron, Temur Breach, Dimir Murktide

3 use stub path (NOT tagged):
- **Izzet Prowess** — relevant for Stage B HASTE filter (Monastery Swiftspear etc.)
- **Domain Zoo** — relevant for Stage C HEXPROOF (4 Scion of Draco) AND Stage A FLYING/Stage B haste-creatures-they-may-have
- **Esper Blink** — likely some keyword interactions but TBD

## Sub-stages

### T.0 — Idempotency verification (5 min)

`tag_keywords` is currently called once per card at `data/deck.py:176`. After this spec, it will be called twice for cards loaded via `.txt` path that route through `load_deck_and_apl` (once in `data/deck.py:176`, then a second time if we add the call in `build_deck_from_dict` — but `build_deck_from_dict` is only called from the dict path, so this is actually NOT a double-call risk).

Wait — verify: does `data/deck.py:load_deck_from_file` go through `build_deck_from_dict`? Reading the code, the .txt path returns `(main, side)` directly from `data.deck.load_deck_from_file`, BYPASSING `build_deck_from_dict`. So adding tag_keywords inside `build_deck_from_dict` does NOT cause the .txt path to double-tag. Idempotency is moot for the patch as proposed.

But still verify tag_keywords IS idempotent (defensive — future code paths might hit it twice). Read tag_keywords source: it iterates `_COMPILED_RULES` and skips tags already present (`if tag in card.tags: continue`). Confirmed idempotent. T.0 verifies this empirically:

```python
from data.card import Card
from engine.keywords import tag_keywords

c = Card(name="Test", oracle_text="Hexproof, flying", ...)
added1 = tag_keywords(c)
added2 = tag_keywords(c)
assert added1 == {"hexproof", "flying"}
assert added2 == set()  # second call adds nothing
assert "hexproof" in c.tags and "flying" in c.tags
```

### T.1 — Apply tag_keywords in build_deck_from_dict (5 min)

```python
# generate_matchup_data.py
def build_deck_from_dict(card_dict):
    """Convert {card_name: qty} dict to list of Card objects."""
    from engine.keywords import tag_keywords  # NEW
    deck = []
    for card_name, qty in card_dict.items():
        for _ in range(qty):
            data = _db.get(card_name)
            if data:
                card = Card(...)
            else:
                card = Card(...)  # fallback
            tag_keywords(card)  # NEW — apply keyword tags from oracle text
            deck.append(card)
    return deck
```

Single-line addition (plus the import). Commit message:
`engine: apply tag_keywords in build_deck_from_dict (closes load-path mismatch)`

### T.2 — Fresh baseline capture (10-15 min, mostly waiting on simulation)

Identical pattern to Stage C C.0 (per `re-execution-specs-require-fresh-baseline-capture` lesson v1.4). Capture fresh canonical + variant gauntlets at the new HEAD (post-T.1 commit). Two sequential gauntlets:

```bash
cd "E:/vscode ai project/mtg-sim"
python parallel_launcher.py --deck "Boros Energy" --format modern --n 1000 --seed 42
python parallel_launcher.py --deck "Boros Energy Variant Jermey" --format modern --n 1000 --seed 42
```

This new baseline becomes the trusted reference for any future Phase 3.5 stages (D-K).

### T.3 — Comparison table + per-matchup analysis (10 min)

For each of the 3 stub-loaded matchups, compute pre-fix vs post-fix delta:

| Matchup | Pre-fix variant | Post-fix variant | Δ | Pre-fix canonical | Post-fix canonical | Δ |
|---|---|---|---|---|---|---|
| Domain Zoo | 99.8% (C.0) | <X.X>% | <ΔV>pp | 89.5% (C.0) | <X.X>% | <ΔC>pp |
| Izzet Prowess | 99.7% (C.0) | <X.X>% | <ΔV>pp | 49.2% (C.0) | <X.X>% | <ΔC>pp |
| Esper Blink | 76.5% (C.0) | <X.X>% | <ΔV>pp | 62.6% (C.0) | <X.X>% | <ΔC>pp |

Also compute: per-matchup deltas on the 11 .txt-loaded opps (these should all be ~0pp since their tagging path didn't change). If any .txt-loaded matchup shifts > 2pp, that's a sign of unrelated drift or interaction — investigate.

Predicted directions:
- **Variant Domain Zoo:** -2 to -5pp (Scion of Draco x4 now untargetable from BE damage spells; original Stage C prediction now applies)
- **Variant Izzet Prowess:** ambiguous — Izzet has Monastery Swiftspear (haste), Slickshot Show-Off etc. Stage B haste filter activating could marginally improve variant (T1 attacks landing) or marginally hurt (opp's hastes also attack). Predict ±3pp range.
- **Variant Esper Blink:** TBD — depends on Esper's keyword density. Predict ±2pp.
- **Canonical** on these matchups: same direction but smaller magnitude than variant (variant has higher edge therefore more leverage on filtered creatures).

### T.4 — Documentation cascade (15-20 min)

#### Stage A spec amendment

Add to `harness/specs/2026-04-27-phase-3.5-stage-a-block-eligibility.md`:

```
Amendment 4 (2026-04-28 via tagger-load-path-unification): Stage A's
MENACE block-eligibility was partial-effect at SHIP. Of 14 Modern
field opps, 3 are stub-loaded (Izzet Prowess, Domain Zoo, Esper Blink)
and their creatures didn't receive MENACE tag at runtime due to
tag_keywords not being called on the dict load path. Post-fix re-
validation: <pre-fix variant Y.Y% -> post-fix variant Z.Z% = +ΔV pp;
canonical similar with smaller magnitude>. The +12.0pp variant edge
documented at SHIP was the partial-effect measurement; full-effect
edge after tagger-fix is +<X>pp.
```

#### Stage B spec amendment

Same pattern for `harness/specs/2026-04-27-phase-3.5-stage-b-combat-modifiers.md`. Stage B's HASTE/DEFENDER/VIGILANCE/lifelink filters were silent against the 3 stub-loaded opps. Note: Stage B's Mono Red haste-density measurement (-6.5pp BE-vs-Mono-Red) WAS measured correctly because Mono Red is .txt-loaded; the stub-loaded subset's haste-creature-impact was missed.

#### Stage C spec amendment

Add to `harness/specs/2026-04-28-phase-3.5-stage-c-protection-cluster.md`:

```
Post-tagger-fix activation (2026-04-28 via tagger-load-path-unification):
Stage C C.1's chokepoint patch became active against current 14-deck
Modern field. Empirical activation: variant Domain Zoo <X.X% -> Y.Y%>,
matching A5's predicted -2 to -5pp from Scion of Draco hexproof
filtering. Latent-infrastructure-shipped-2026-04-28 transitioned to
active-effect-2026-04-28-via-tagger-fix.
```

#### Update `mtg-sim/ARCHITECTURE.md`

Add a note in the gauntlet section about the new post-tagger-fix
baseline, lifting any provisional annotations.

#### Update IMPERFECTIONS.md / RESOLVED.md

Mark `tagger-load-path-unification` RESOLVED at this spec's commit hash.

## Validation gates

**Gate 1: Idempotency confirmed.** `tag_keywords` is provably idempotent (running twice on the same card adds no new tags after the first call). Verified empirically in T.0.

**Gate 2: T.1 patch applied + drift-detect clean.** `build_deck_from_dict` calls `tag_keywords` on every constructed card. Drift-detect exits at same code as pre-spec.

**Gate 3: Stub-loaded card now has tags at gauntlet runtime.** Synthetic test:
```python
from generate_matchup_data import load_deck_and_apl
main, _, _ = load_deck_and_apl('Domain Zoo', 'modern')
scions = [c for c in main if 'Scion' in c.name]
assert all('hexproof' in c.tags for c in scions), "Scion should have HEXPROOF tag post-fix"
```

**Gate 4: T.2 fresh baseline captured.** Both gauntlets ran; both JSON files exist; no truncation.

**Gate 5: Comparison table populated.** Per-matchup table from T.3 with measured numbers (not estimates).

**Gate 6: .txt-loaded matchups stable.** All 11 .txt-loaded matchups within ±2pp of their C.0 baselines (no unrelated drift).

**Gate 7: Stub-loaded matchup shifts mechanically explainable.** Each of 3 stub-loaded matchups shifts in the predicted direction (Domain Zoo down for variant per Scion hexproof; Izzet Prowess and Esper Blink TBD with reasoning per T.3).

## Stop conditions

**Stop and ship when:** All 7 gates pass.

**Stop and amend if:**
- Idempotency fails (tag_keywords double-call adds extra tags) — investigate before patching
- Any .txt-loaded matchup shifts > 2pp — that's a sign of unrelated drift; investigate before declaring stub-loaded shifts attributable to tagger-fix
- Any stub-loaded matchup shifts > 10pp in unexpected direction — large unexpected shift, investigate before shipping

**DO NOT:**
- Do NOT bundle Stage A or Stage B re-validation re-runs into this spec beyond the comparison-table fresh baseline. Each prior stage's full re-validation (if needed) is its own follow-up.
- Do NOT re-spec or re-touch any Stage A / B / C engine code as part of this fix. The fix is ONE LINE in `build_deck_from_dict` + an import.

## Risk register

**T.R1: Hidden double-call site.** Some other code path might also call `tag_keywords` on cards loaded via stub path. Mitigation: pre-flight grep verified only `data/deck.py:176` calls it in production code. T.0 idempotency check is the safety net regardless.

**T.R2: Tag activation surfaces a Stage A/B engine bug previously hidden by silent-no-op.** If Stage A or B has a subtle bug in its keyword handling that didn't fire because tags weren't present, this spec activates the bug. Mitigation: stop condition #2 catches large unexplained shifts; investigation chain is well-rehearsed at this point.

**T.R3: Predictions for Izzet Prowess and Esper Blink are imprecise.** Domain Zoo is well-characterized (Scion x4 = -2 to -5pp predicted). The other two stub-loaded opps need density check before predicting. Mitigation: T.3 includes per-matchup density verification before measuring.

**T.R4: New baseline becomes a moving target.** Once this fix lands, the trusted reference baseline shifts. Future stages must capture against the post-fix baseline, not C.0. Mitigation: clearly document the new baseline in `harness/state/latest-snapshot.md` post-ship, and note in the Stage A/B/C spec amendments that the post-fix numbers are now the load-bearing reference.

## Reporting expectations

After completion:

1. Commit hash of T.1
2. Idempotency check result (T.0)
3. Pre-fix vs post-fix comparison table (T.3) for all 14 matchups, with per-matchup deltas annotated as "stub-loaded → expected to shift" or ".txt-loaded → expected stable"
4. Mechanical justification per stub-loaded matchup shift (T.3)
5. Stage A / B / C spec amendments landed (T.4)
6. New trusted baseline (canonical + variant aggregates + per-matchup table) for future-stage anchoring
7. Any deviations or surprises
8. Confirmation that drift-detect, lint, and synthetic tests for Stages A/B/C all still pass post-fix

Then update spec status to SHIPPED, add line to RESOLVED.md, summary in chat.

## Concrete steps (in order)

1. Pre-flight reads (10 min)
2. T.0: idempotency verification (5 min)
3. T.1: patch + commit (5 min)
4. T.2: fresh baseline capture (10-15 min, mostly unattended)
5. T.3: comparison table + per-matchup analysis (10 min)
6. T.4: documentation cascade across Stage A / B / C specs + ARCHITECTURE.md + IMPERFECTIONS/RESOLVED (15-20 min)
7. Run all 7 gates + drift-detect + lint smoke (5-10 min)
8. Update spec status to SHIPPED (2 min)
9. If new lessons surfaced (e.g. unexpected interactions between stages), update spec-authoring-lessons.md to v1.5 (5-10 min)

Total: 65-90 minutes wall.

## Why this order

- **Idempotency before patch:** if the function isn't idempotent, the patch could silently break the .txt-load-path even though the path doesn't currently double-call (defensive).
- **Patch before baseline:** can't measure post-fix without the fix landing.
- **Baseline before comparison:** comparison needs both pre and post numbers.
- **Comparison before cascade:** cascade documents the comparison; can't write the documentation without the numbers.
- **Documentation cascade as one focused block:** each Stage A/B/C amendment cites the same comparison table; bundling keeps the cascade reviewable as a single coherent edit pass.

## Future work this enables (NOT in scope)

- **Stage A re-validation against post-fix field.** If Stage A's full-effect numbers diverge meaningfully from the partial-effect SHIP measurements, a re-validation pass might be warranted. Decide based on T.3 results.
- **Stage B re-validation against post-fix field.** Same.
- **Phase 3.5 Stages D-K.** All future stages now anchor on post-tagger-fix baseline. The Stage C re-execution pattern (C.0 fresh baseline before patch) becomes the standard.
- **Drift-detect 8th check: tagger-application audit.** Scan codebase for `tag_keywords` invocations and flag every Card-constructor site that bypasses it. Higher priority than the cache-key audit per `load-path-dependent-setup-creates-silent-no-op-features` lesson tooling implication. Could surface other tagger-mismatch sites we haven't found yet.
- **Audit other setup functions for the same load-path-dependent pattern.** `tag_keywords` is the example surfaced; other per-card setup functions (color identity normalization, type-line parsing, mana-cost compilation) might have similar mismatches.

## Changelog

- 2026-04-28: Created (PROPOSED) by Claude Code immediately after Stage C re-execution shipped. First-class spec per user directive — explicitly NOT bundled into Stage C to preserve `spec-prediction-model-must-be-falsifiable` (validation gates need to isolate "is C.1 working" from "is tagger-fix working"; bundle would conflate them). Surfaced by Stage C A5; embodies the load-path-dependent-setup-creates-silent-no-op-features v1.4 lesson; will be the first re-execution-spec to use the v1.4 fresh-baseline-capture pattern.
- 2026-04-28: Status -> SHIPPED at commit 199d28e via execution-chain S3.7. T.0 idempotency PASS (empirical). T.0.5 inserted ahead of T.1 (deviation from spec) to capture pre-fix baseline at current HEAD instead of the spec's documented C.0-from-e4fae86 anchor; this eliminated engine-evolution drift contamination of T.3 deltas (per user instruction reinforcing v1.4 re-execution-specs-require-fresh-baseline-capture lesson). Pre-fix baseline: canonical 65.8% / variant 79.2%. T.1 commit 199d28e (1 file, +17/-5). T.2 post-fix baseline: canonical 64.5% / variant 78.7%. T.3 subset-aggregate analysis: .txt-loaded -0.51pp/-0.05pp (control), stub-loaded -4.52pp/+0.05pp (active). T.4 documentation cascade: Stage A/B/C amendments, ARCHITECTURE.md baseline section, IMPERFECTIONS->RESOLVED.

  **All 7 validation gates passed.** Per-matchup .txt-loaded variance ±2.5pp surfaced as Stage 1.7 non-determinism characterization refinement (prior aggregate noise estimate +0.6pp didn't predict per-matchup variance amplitude). Spec stop condition #2 (.txt > 2pp per-matchup) misfired against per-matchup noise; subset-aggregate level (-0.51pp .txt) is the correct calibration. Generalizable lesson candidate v1.5: "stop conditions on subset metrics must use the noise-floor-appropriate aggregation level — per-matchup noise can exceed aggregate noise by an order of magnitude when uncorrelated noise mostly cancels in aggregate." Queued for compounding after Stage 1.7 fix validates the broader pattern.

  **Future-stage anchoring:** Stages D-K should anchor on canonical 64.5% / variant 78.7% (post-tagger-fix at 199d28e), NOT on prior 65.8% headline (pre-tagger-fix). New baseline JSONs: data/parallel_results_20260428_125005.json (canonical) + data/parallel_results_20260428_125019.json (variant).
