# Spec: Gemma APL quality lift via ICL examples + post-validation

**Status:** SHIPPED
**Created:** 2026-04-28 by claude.ai (for tomorrow execution)
**Target executor:** Claude Code
**Estimated effort:** 45-90 minutes (prompt iteration + measurement)
**Risk level:** MEDIUM — touches the prompt that drives auto-pipeline APL generation; quality regression possible if ICL examples bias generation badly. Fully gated by smoke test (no bad APLs reach registry regardless).
**Dependencies:**
- `harness/specs/2026-04-28-auto-pipeline-output-flow-to-retune.md` SHIPPED 2026-04-28 (smoke gate exists)
- 3 existing canonical APLs to use as ICL examples
**Resolves:** 1 OPEN imperfection (`gemma-apl-quality-low-for-smoke-gate`)

## Goal

Lift Gemma's APL pass rate against the 50-game smoke gate from the current 0/3 baseline to a meaningful fraction. Today's failures (Landless Belcher: API misuse `gs.get(...)`, Cutter Affinity: no class with `APL` suffix, Jeskai Phelia: SyntaxError at line 137) all look like Gemma not having seen enough examples of valid APL shape — fixable via in-context-learning examples and a post-validation pass.

After this ships, the auto-pipeline integration goes from "wired but inert" to "wired and producing some real APLs for retune." Friday-night nightly nightlies (post-PT) become more useful proportional to the pass rate gain.

## Pre-flight reads (REQUIRED)

1. `harness/IMPERFECTIONS.md` — entry `gemma-apl-quality-low-for-smoke-gate`
2. `harness/agents/scripts/auto_pipeline.py` — current Gemma prompt construction (find the `generate_apl` function)
3. `mtg-sim/apl/auto_apls/{landless_belcher,cutter_affinity,jeskai_phelia}.py` — today's failing samples (note SPECIFIC failure modes per file)
4. 3 canonical APLs to use as ICL exemplars: `mtg-sim/apl/boros_energy.py` (Boros aggro shape), `mtg-sim/apl/izzet_prowess.py` (tempo shape), one more from a different archetype (recommend `mtg-sim/apl/eldrazi_tron_match.py` for control-shape diversity)
5. `mtg-sim/apl/base_apl.py` or equivalent — the actual API surface Gemma must respect

## Scope

### In scope
- Modify Gemma prompt in `auto_pipeline.py` to:
  1. Include 2-3 ICL exemplars (shortened to fit context budget — don't paste full 200-line APLs, paste signature + key methods)
  2. Add explicit "valid GameState API" reference section listing actual attributes/methods (not invented ones)
  3. Add "class name MUST end in `APL`" instruction with example
  4. Add a post-generation `ast.parse` retry loop: if Gemma's output doesn't parse, ask Gemma to fix it once (one re-prompt with the SyntaxError as feedback). Bail after 1 retry.
- Smoke gate stays unchanged (50-game goldfish, crash-only) — already shipped from S4
- Re-run auto-pipeline against today's 3 archetypes (Landless Belcher, Cutter Affinity, Jeskai Phelia) as live measurement
- Document new pass rate in IMPERFECTIONS resolution note

### Explicitly out of scope
- Switching to Claude path — separate spec (`oauth-vs-raw-v1-messages-compat-unverified`); resolve auth question first before changing model choice
- Auto-fix of common errors (option 3 from IMPERFECTIONS) — reserve as fallback if ICL doesn't lift pass rate enough
- Gauntlet validation of generated APLs (small-N WR check) — separate quality gate; not in scope today

## Steps

### T.0 — Failure-mode analysis (~10 min)

Read the 3 failing APLs at `mtg-sim/apl/auto_apls/*.py`. For each, identify:
- Specific error class (API misuse / structural / syntactic)
- Whether the error is one Gemma could plausibly avoid given a good exemplar

Write findings into `harness/knowledge/tech/gemma-apl-failure-analysis-2026-04-29.md` (3-5 bullets per file).

### T.1 — Pick + extract ICL exemplars (~10 min)

For each of the 3 chosen canonical APLs, extract the parts that matter for shape-learning:
- Class declaration line with name suffix
- `__init__` signature
- 2-3 representative method signatures + 5-10 line body each
- Imports (so Gemma sees what's available)

Total target: ~150-250 lines of ICL across 3 examples (vs full APLs at 200+ lines each which would blow context budget).

### T.2 — API reference section (~10 min)

Build a concise reference block listing actual GameState/APL API:
- Attributes Gemma can read (e.g., `gs.zones.hand`, `gs.bf_a`, `gs.life_a`)
- Methods Gemma can call (whatever the actual base class provides)
- Things Gemma CANNOT do (the failure modes from T.0 — explicitly call out `gs.get(...)` doesn't exist if that's the issue)

Source of truth: `mtg-sim/apl/base_apl.py` + `mtg-sim/engine/game_state.py` (read these to extract the actual API).

### T.3 — Modify prompt (~10 min)

In `auto_pipeline.py:generate_apl` (or wherever the Gemma prompt is constructed), insert the new sections in this order:
1. Existing task description
2. NEW: ICL exemplars block
3. NEW: API reference block
4. NEW: Output shape requirements (class name, etc.)
5. Existing archetype-specific context

### T.4 — Post-generation parse-and-retry (~10 min)

After Gemma returns code, before writing to disk:

```python
import ast
try:
    ast.parse(generated_code)
except SyntaxError as e:
    # One retry with error context
    retry_prompt = f"The previous output had a SyntaxError at line {e.lineno}: {e.msg}\nFix and return the corrected APL code only."
    generated_code = ask_gemma(retry_prompt)
    try:
        ast.parse(generated_code)
    except SyntaxError:
        # Bail — let smoke gate catch it as before
        pass
```

### T.5 — Live measurement (~15 min)

Re-run auto-pipeline against the same 3 archetypes:

```bash
cd "E:/vscode ai project"
# Delete today's failing APLs first to force re-generation
rm mtg-sim/apl/auto_apls/landless_belcher.py
rm mtg-sim/apl/auto_apls/cutter_affinity.py
rm mtg-sim/apl/auto_apls/jeskai_phelia.py
# (Be aware: these are committed at 1a4f97a; re-generating overwrites the working tree.
# After measurement, decide whether to commit new versions or revert to baseline.)
python harness/agents/scripts/auto_pipeline.py --format modern --use-gemma
```

Observe: how many passed smoke gate? Document failure modes for any that still failed.

### T.6 — Cascade + commit (~10 min)

- IMPERFECTIONS → RESOLVED if pass rate >0/3
- IMPERFECTIONS update (not full resolution) if 0/3 again — document new failure modes
- Commit any prompt changes
- Commit new APL files if they pass smoke

## Validation gates

| Gate | Acceptance | Stop trigger |
|---|---|---|
| 1 — failure analysis written | `harness/knowledge/tech/gemma-apl-failure-analysis-2026-04-29.md` exists with 3-5 bullets per failing file | analysis missing detail |
| 2 — prompt changes don't crash | `auto_pipeline.py --format modern --use-gemma --top-n 1` completes without error | crash |
| 3 — pass rate gain | At least 1/3 of today's archetypes passes smoke (was 0/3) | 0/3 again — document and surface |
| 4 — passing APL is functional | Smoke-pass APL plays a visible game (goldfish kill turn within sane range, e.g., T3-T15) | nonsense numbers (e.g., goldfish 0% wins or T0 kills) |
| 5 — pre-existing tests still pass | menace 3/3, protection 5/5, determinism 3/3, atomic_json (if shipped earlier today) all pass | regression |

## Stop conditions

- **Pass rate stays 0/3 after ICL changes:** STOP. Document new failure modes. Pivot to option 3 (auto-fix common errors) or queue Claude-path verification.
- **Gemma prompt blows context budget (Ollama errors on input length):** STOP. Trim ICL exemplars further; smaller per-example chunks.
- **A passing APL produces a clearly-broken sim (e.g., 0% goldfish or T0 kills):** STOP. Smoke gate is too lenient; don't promote bad APLs into registry. Open follow-up IMPERFECTION for tighter gate.
- **Re-generated APLs overwrite committed 1a4f97a versions before measurement complete:** Use `git stash` before T.5, restore after, decide commit-or-revert based on results.

## Reporting expectations

1. Per-file failure mode from T.0
2. Prompt size before/after (token estimate)
3. Pass rate result (X/3)
4. Per-failure analysis if any persist
5. IMPERFECTIONS state delta
6. Decision: commit new APLs, revert to baseline, or partial (commit passing ones only)

## Future work this enables (NOT in scope)

- If pass rate >2/3, the auto-pipeline becomes meaningfully useful for Friday-night PT-watch nightlies
- If pass rate <2/3 even after this fix, queue Claude-path verification (separate spec) as the next quality lift
- Prompt-iteration methodology lesson candidate if a v1.6 generalization surfaces (e.g., "ICL exemplars need to be small but representative" — only compound if validated)

## Changelog

- 2026-04-28: Created (PROPOSED) by claude.ai for tomorrow execution. Lowest-cost lift on auto-pipeline output value. Pairs naturally with `oauth-vs-raw-v1-messages-compat-unverified` probe (do that BEFORE this if Claude path is desired path).
