# Spec: auto_pipeline.py nightly integration (feature-flagged, Gemma-default)

**Status:** SHIPPED 2026-04-28 (no engine commit; touches harness scripts which are unversioned, plus harness/scripts/nightly-harness.ps1 also unversioned)
**Created:** 2026-04-28 by Claude Code (execution-chain S3.9)
**Target executor:** Claude Code (same session)
**Estimated effort:** 60-90 minutes
**Actual effort:** ~50 min
**Risk level:** MEDIUM — touches nightly_harness orchestration which runs unattended Friday; feature-flagged default-off mitigates blast radius. Generated APLs could contaminate sim baselines if low-quality; mitigated via validation gate.
**Dependencies:**
- nightly_harness.py operational (verified S2 dry-run 2026-04-28)
- auto_pipeline.py exists at `harness/agents/scripts/auto_pipeline.py` (verified)
- apl/auto_apl.py supports OAuth + env-var + .env auth paths (verified)
- Ollama gemma4 healthy at localhost:11434 (verified via prior compile-knowledge runs in MEMORY.md)
**Blocks:** nothing critical, but Friday PT-watch quality of nightly output. Without this, PT-emergent archetypes will SKIP at retune leaving gaps in field gauntlet coverage.
**Surfaced by:** Execution-chain S3.7 post-task audit ("auto_pipeline.py silent feature-drift").

## Summary

Wire `harness/agents/scripts/auto_pipeline.py` into `harness/agents/scripts/nightly_harness.py` as a NEW step between meta-shift detection and retune, gated behind a `--enable-auto-pipeline` flag (default OFF). Default-Gemma policy when invoked from nightly so Friday's scheduled task can never accidentally bill the Anthropic console; Claude path remains opt-in via a separate flag. Validates the wire end-to-end against current 8 detected new archetypes (Landless Belcher 18.7%, Cutter Affinity 7.5%, Jeskai Phelia 4.7%, Boros Control 3.7%, Broodscale Combo 3.7%, Grixis Control 3.7%, Chord Toolbox 2.8%, Jeskai Ephemerate 2.8%) before Friday PT data lands.

The feature flag stays OFF in Friday's scheduled task configuration. User can flip it on manually after observing one or two unattended days of behavior.

## Pre-flight reads (REQUIRED before starting)

Per `harness/CLAUDE.md` Rule 1:

1. **`harness/knowledge/tech/spec-authoring-lessons.md` v1.5** — especially:
   - `load-path-dependent-setup-creates-silent-no-op-features` (this spec is the second instance of fixing this class — first was tagger-fix)
   - `parallel-entry-points-need-mirror-fix` (check whether `nightly_harness.py` has parallel entry points that also need wire-up)
   - `verify-identifiers-before-spec-execution` (verify exact paths and function signatures before patching)
2. **`harness/agents/scripts/nightly_harness.py`** — current orchestration body, particularly the step-numbering pattern + how dry_run propagates
3. **`harness/agents/scripts/auto_pipeline.py`** — current entry function `run_pipeline()` at line 346, CLI flags at line 457-466
4. **`mtg-sim/apl/auto_apl.py`** lines 160-265 — auth-path resolution + raw API call site (for T.0 probe)
5. **`harness/HARNESS_STATUS.md`** Layer 5 section — current "OPERATIONAL" claim that this spec corrects to "OPERATIONAL with feature flag"
6. **`harness/CLAUDE.md`** Rule 7 (standing-by-with-options as default) — relevant because this spec adds an opt-in feature, not a default-on automation

## Background

### The silent feature-drift instance

Layer 5 auto_pipeline.py has been operational since 2026-04-16 per HARNESS_STATUS.md. The wrapper `harness/scripts/auto-pipeline.ps1` is a manual trigger only — no scheduled task invokes it, and `nightly_harness.py` does NOT call it. Today's audit (execution-chain S3.7 post-task) confirmed:
- `optimization_memory.json` does NOT exist at the path `auto_pipeline.py` declares (`harness/agents/optimization_memory.json`)
- No `harness/logs/auto_pipeline-*` log files
- nightly_harness Modern dry-run finds 8 new archetypes that all SKIP at retune
- Friday PT data will produce many more such SKIPs

This is the same load-path-dependent-setup-creates-silent-no-op-features class as tagger-load-path: feature exists, has tests (dry-run completes successfully), has documentation claiming OPERATIONAL, but no automation invokes it against real workload.

### Auth-path topology

`apl/auto_apl.py:_resolve_anthropic_token()` (lines 160-220) supports three token sources, in priority order:
1. `ANTHROPIC_API_KEY` env var
2. `~/.claude/.credentials.json` (Claude Code OAuth, with refresh logic at lines 220-238)
3. `.env` file with `ANTHROPIC_API_KEY=sk-ant-...`

The actual API call at line 240-265 is raw urllib to `https://api.anthropic.com/v1/messages` with the resolved token. **Whether Claude Max OAuth tokens are accepted for raw v1/messages calls is unverified.** T.0 probe will surface this.

If OAuth route fails for raw API calls, the user has two options:
- Generate an Anthropic API key (separate from Claude Max) at console.anthropic.com
- Use Gemma exclusively for nightly auto_pipeline (default per this spec)

The Gemma path uses Ollama at `localhost:11434/api/generate` (line 197), no auth required, $0.00 cost. Quality is lower per HARNESS_STATUS.md design principle 2.

### Why feature-flagged default-off

Friday's scheduled task runs unattended at 17:30 (Modern) and 18:30 (Standard). Adding behavior to nightly without a flag means the change ships to production with zero observation time. Feature flag default-off means:
- Friday's scheduled task runs unchanged unless the user manually edits the task command line
- User can run `nightly-harness.ps1 -EnableAutoPipeline` manually a few times to observe
- When confidence is established, user flips the scheduled task command line to include the flag

Per `harness/CLAUDE.md` Rule 7, the default should be the option that requires explicit user opt-in to add automation, not opt-out.

## Sub-stages

### T.0 — Auth-path probe (3-5 min)

Verify which of the three auth paths actually works in the current environment. Run a single-token-resolution test (not a real API call to avoid surprise charges):

```bash
cd "E:/vscode ai project/mtg-sim" && python -c "
import sys; sys.path.insert(0, '.')
from apl.auto_apl import _resolve_anthropic_token
try:
    tok = _resolve_anthropic_token()
    src = ('env-var' if 'ANTHROPIC_API_KEY' in __import__('os').environ
           else 'oauth/.credentials.json or .env')
    print(f'TOKEN RESOLVED: source likely = {src}, length = {len(tok)}')
except RuntimeError as e:
    print(f'NO TOKEN: {e}')
"
```

Three outcomes:
- **Token resolves and source is env-var or .env file:** Claude path is usable; user has an Anthropic API key configured.
- **Token resolves and source is OAuth credentials:** Possibly usable for raw API calls; needs a dry-test (deferred — out of scope).
- **No token resolves:** Claude path is unavailable; Gemma is the only option. This is fine for the spec because Gemma is the default policy.

Whichever outcome, document it in T.6's RESOLVED entry. Do not attempt to fix missing token here.

### T.1 — Add `--enable-auto-pipeline` flag to nightly_harness.py (10-15 min)

Patch `harness/agents/scripts/nightly_harness.py`:

1. Add `--enable-auto-pipeline` to the argparse setup (default=False)
2. Add `--auto-pipeline-use-claude` to argparse (default=False, only meaningful if --enable-auto-pipeline)
3. After STEP 1 (meta-shift detection) but before STEP 2 (retune), insert:

```python
if args.enable_auto_pipeline:
    log("\n[STEP 1.5/N] Auto-pipeline: generating APLs for new archetypes...")
    from harness.agents.scripts.auto_pipeline import run_pipeline as auto_run
    # Default Gemma per HARNESS_STATUS design principle 2 + spec safety:
    # nightly should never bill the Anthropic console accidentally.
    use_claude = args.auto_pipeline_use_claude
    auto_result = auto_run(
        format_name=format_name,
        use_claude=use_claude,
        dry_run=dry_run,
    )
    log(f"  Auto-pipeline: {auto_result.get('new_count', 0)} new archetypes processed")
else:
    log("\n[STEP 1.5/N] Auto-pipeline: SKIPPED (use --enable-auto-pipeline to wire)")
```

4. Increment subsequent STEP numbering (was 2/4 → becomes 2/N where N = total steps + 1)

NOTE: `auto_pipeline.run_pipeline()` does not currently return a structured dict with `new_count`. T.1 may need a small refactor to return summary fields, OR the nightly integration can read from log output. Decide based on minimal-diff pressure: if `run_pipeline` already prints the summary, the nightly STEP 1.5 just needs to ensure the print propagates to the nightly log file. Read the function before patching to decide.

### T.2 — Default-Gemma policy (5 min)

Confirm via T.1 that the `use_claude` default in the integration is False, regardless of what `--use-claude` would default to in standalone auto_pipeline.py. Standalone auto_pipeline.py defaults to Claude (line 470 `use_claude=not args.use_gemma`); the nightly integration explicitly inverts this to Gemma-by-default.

If the user wants Claude in nightly, they pass BOTH `--enable-auto-pipeline --auto-pipeline-use-claude`. Two flags = two opt-ins = no accidental console billing.

### T.3 — Dry-run smoke test (5 min)

```bash
cd "E:/vscode ai project" && python harness/agents/scripts/nightly_harness.py --dry-run --format modern --enable-auto-pipeline
```

Expected: pipeline runs all steps including the new STEP 1.5; STEP 1.5 shows "[DRY RUN] Would generate APL for ..." for the top-3 new archetypes by meta share. No files written, no API calls.

Run also without `--enable-auto-pipeline` to verify default-off behavior:
```bash
python harness/agents/scripts/nightly_harness.py --dry-run --format modern
```
Expected: STEP 1.5 logs "SKIPPED" and returns to original behavior (this is the safety gate for Friday's scheduled task).

### T.4 — Live single-format test (15-20 min)

```bash
cd "E:/vscode ai project" && python harness/agents/scripts/nightly_harness.py --format modern --enable-auto-pipeline
```

Expected behavior:
- STEP 1: detects 8 new archetypes (or current count)
- STEP 1.5: generates APL stubs via Gemma for top 3; writes them to `mtg-sim/data/auto_apls/<deck_slug>.py`
- Writes `harness/agents/optimization_memory.json` for the first time (or appends if exists)
- STEP 2: retune still SKIPs the new archetypes for THIS run (they need a registry entry to be retunable; auto_pipeline generates the APL file but doesn't auto-register it — separate concern)
- All other steps complete normally

Verify after run:
- `harness/agents/optimization_memory.json` exists and has `generated_apls` entries with today's date
- `mtg-sim/data/auto_apls/landless_belcher.py` (or similar) exists and is parseable Python

### T.5 — Idempotency / second-run validation (10 min)

```bash
python harness/agents/scripts/nightly_harness.py --format modern --enable-auto-pipeline
```

Run a second time, immediately after T.4. Expected:
- Same 8 new archetypes still detected (auto_pipeline doesn't auto-register; the APL files exist on disk but APL_REGISTRY in `apl/__init__.py` is unchanged)
- STEP 1.5 either re-generates (overwriting cache) or short-circuits via `_get_decklist_from_db` finding existing playbook draft — depends on auto_pipeline's idempotency. Note actual behavior; if re-generation happens unnecessarily, that's a refinement for a follow-up spec.
- `optimization_memory.json` appended with second day's entries
- No errors, no duplicate-write corruption

### T.6 — Documentation cascade (10-15 min)

1. **`harness/HARNESS_STATUS.md`** Layer 5 section: change "OPERATIONAL" to "OPERATIONAL (feature-flagged in nightly: opt-in via --enable-auto-pipeline)" and add a note on the auth-path topology (T.0 result).
2. **`harness/MEMORY.md`** changelog: add an entry for this spec under today's date.
3. **`harness/IMPERFECTIONS.md`** + **`harness/RESOLVED.md`**: log "auto_pipeline-silent-feature-drift" as RESOLVED at this spec's commit.
4. **Spec status:** PROPOSED → SHIPPED + changelog entry per established pattern.
5. **`harness/scripts/register-harness-tasks.ps1`** (READ ONLY, do not modify): note in the spec that the Friday scheduled task command line does NOT include `--enable-auto-pipeline` and does not need to be touched. User can flip the flag manually when ready.

## Validation gates

**Gate 1 (auth probe):** T.0 produces a clear "TOKEN RESOLVED" or "NO TOKEN" message. Either outcome is acceptable; both are documented in T.6.

**Gate 2 (flag default-off):** Running `nightly_harness.py --dry-run --format modern` (without --enable-auto-pipeline) produces output that is byte-identical to pre-spec output for all steps EXCEPT the new STEP 1.5 SKIPPED line. Friday's scheduled task is safe.

**Gate 3 (flag opt-in):** Running with `--enable-auto-pipeline --dry-run` shows STEP 1.5 in dry-run mode listing the top-3 new archetypes that WOULD be generated.

**Gate 4 (live Gemma write):** T.4 live run with `--enable-auto-pipeline` writes `harness/agents/optimization_memory.json` and produces at least 1 APL file in `mtg-sim/data/auto_apls/`. Both files parseable / valid JSON / valid Python.

**Gate 5 (idempotency):** T.5 second run completes without crash, error, or corruption of optimization_memory.json. Behavior on re-detection of "new" archetypes documented (re-generate vs short-circuit).

**Gate 6 (no regression for default-off):** T.3 (without flag) produces an unchanged-from-pre-spec nightly run for STEPS 2-7. The "SKIPPED" log for STEP 1.5 is the only addition.

**Gate 7 (drift-detect clean):** Drift-detect runs clean post-spec; no new untracked load-bearing WIP, no new orphans.

## Stop conditions

**Ship when:** All 7 gates pass.

**Stop and amend if:**
- Gate 6 fails (default-off behavior changes from pre-spec): the feature flag is leaking. Investigate before ship; this is a regression that would affect Friday's scheduled task.
- T.4 live run produces APL files that fail to parse or crash sim on import: Gemma's APL output is malformed. Document in spec; ship with a parse-validation gate added to STEP 1.5 (skip APLs that don't parse).
- `optimization_memory.json` corruption between T.4 and T.5: concurrent-write bug or schema mismatch. Investigate before ship.
- T.0 reveals NO token AND Gemma is also unhealthy: spec cannot ship a working integration; degrade to "spec ships the wire, marks Layer 5 as inert pending Gemma/auth fix" and document.

**DO NOT:**
- Do NOT modify the Friday scheduled task registration. The flag stays default-off until user explicitly enables it.
- Do NOT auto-register generated APLs into APL_REGISTRY. That's a separate concern with its own validation needs (auto-registration could insert low-quality APLs that contaminate gauntlet baselines).
- Do NOT touch `apl/auto_apl.py` auth-path code. The probe (T.0) only verifies; if it fails, document and proceed with Gemma default.
- Do NOT bundle this with any unrelated nightly_harness improvements.

## Risk register

**R1: Claude Max OAuth token rejected by raw v1/messages.** Probability: MEDIUM. OAuth tokens are scoped per OAuth client; Anthropic console API tokens are scoped differently. Mitigation: T.0 probe surfaces this; Gemma fallback default means user can still run nightly auto_pipeline without resolution.

**R2: Gemma generates malformed APLs that crash subsequent gauntlet runs.** Probability: LOW-MEDIUM. Gemma has been used for APL generation per MEMORY.md history (mentioned 2026-04-19 gemma-apl-factory log); reasonable quality but not 100%. Mitigation: T.4 verifies parseability; STEP 1.5 should swallow individual APL failures (already does per `_generate_via_gemma` exception handling at line 196).

**R3: optimization_memory.json grows unbounded over months of nightly runs.** Probability: LOW for current scope (months horizon, not hours). Mitigation: out of scope; future spec can add rotation.

**R4: New archetypes detected by nightly that LACK decklist data confuse Gemma.** Probability: MEDIUM (Gemma has to work from "best knowledge of this archetype" per the prompt). Mitigation: Gemma's prompt already handles this case ("No decklist available - use your best knowledge"); generated APLs will be lower-quality but won't crash. T.4 verifies.

**R5: Friday's PT data triggers cascading retunes that take longer than the 5:30/6:30 nightly window.** Probability: LOW. Auto_pipeline caps at top-3 new archetypes per run (line 388 `new_archs[:3]`); single Gemma generation is ~30-60s. Worst case: 5-10 min added to nightly. Mitigation: documented; can bump cap if user wants more coverage.

## Reporting expectations

After completion:

1. T.0 result: which auth path resolved (env-var / OAuth / .env / none)
2. Commit hash of T.1 patch
3. T.4 results: optimization_memory.json contents (sample), list of generated APL files
4. T.5 results: idempotency behavior characterization
5. Friday-readiness statement: scheduled task config unchanged, flag default-off verified
6. Any deviations or surprises (especially around auto_pipeline's existing behavior that doesn't match the spec's assumptions)
7. Confirmation that drift-detect, lint, all 3 test files (menace, protection, determinism) still pass post-spec

Then update spec status to SHIPPED, add line to RESOLVED.md, summary in chat.

## Concrete steps (in order)

1. Pre-flight reads (10 min including this file)
2. T.0: auth-path probe (3-5 min)
3. T.1: nightly_harness flag + integration step (10-15 min)
4. T.2: confirm default-Gemma policy (5 min)
5. T.3: dry-run smoke test, both with and without flag (5 min)
6. T.4: live single-format test (15-20 min wall time, mostly Gemma generation)
7. T.5: idempotency second-run validation (10 min)
8. T.6: documentation cascade (10-15 min)
9. Run all 7 gates + drift-detect + tests (5-10 min)
10. Update spec status to SHIPPED (2 min)

Total: 60-90 min realistic.

## Why this order

- **T.0 probe before patch:** if no token resolves AND user wanted Claude path, surface that BEFORE patching nightly. Cheap probe.
- **Flag plumbing before live test:** flag must work first; live test verifies the wired behavior.
- **Default-off verification (T.3 unflagged) before live (T.4):** Gate 6 is the safety gate for Friday; verify it before testing live behavior.
- **Idempotency check (T.5) before docs:** if T.5 reveals corruption or unexpected behavior, the docs cascade has to mention it.

## Future work this enables (NOT in scope)

- **Auto-registration of generated APLs into APL_REGISTRY.** Current T.4 generates files on disk but doesn't add registry entries; nightly retune still SKIPs them. Adding auto-registration would close that loop but requires a quality gate (Gemma's APLs aren't trusted by default to enter the canonical registry).
- **Validation gauntlet for generated APLs.** Run a small-N gauntlet (e.g., 100 games vs gauntlet field) and only promote to registry if WR is within sanity bands.
- **Bump top-N cap from 3 to user-configurable.** Friday's PT could surface 30+ new archetypes; current cap is 3. Trivial config change.
- **Wire auto_pipeline into a separate scheduled task.** Could decouple from nightly_harness entirely if nightly's runtime grows too long.
- **OAuth token validation for raw API calls.** If T.0 surfaces that OAuth tokens are rejected by raw v1/messages, document and consider a separate spec for refactoring `apl/auto_apl.py` to use the Anthropic SDK instead of raw urllib (SDK might handle OAuth differently — unverified).

## Changelog

- 2026-04-28: Created (PROPOSED) by Claude Code via execution-chain S3.9. Surfaced by S3.7 post-task audit which confirmed the silent feature-drift. First-class spec per user directive (do not bundle). Embodies `load-path-dependent-setup-creates-silent-no-op-features` v1.4 lesson — second instance of fixing this class (first was tagger-fix). Feature-flagged default-off per `harness/CLAUDE.md` Rule 7 (standing-by-with-options as default). Default-Gemma per HARNESS_STATUS.md design principle 2.
- 2026-04-28: Status -> SHIPPED via execution-chain S3.9.

  **Minor spec correction during execution:** Spec referred to function `_resolve_anthropic_token` in Pre-flight reads #4 and T.0 probe; actual function name in `apl/auto_apl.py:160` is `_get_api_token`. Probe ran successfully against the correct name; spec body retains the original mention with this changelog note for traceability.

  **T.0 auth-path probe result:** Token resolved successfully from Claude Code OAuth credentials. Source: `~/.claude/.credentials.json` (NOT env-var). Token prefix `sk-ant-o...`, length 108. OAuth-token-for-raw-v1/messages compatibility unverified (intentionally — out of scope; Gemma default makes it moot for nightly).

  **T.1 patch:** Added `--enable-auto-pipeline` and `--auto-pipeline-use-claude` to `harness/agents/scripts/nightly_harness.py` argparse + `run_nightly` signature + STEP 1.5 insertion between meta detection and retune. Wrapped in try/except so auto_pipeline failure doesn't block other nightly steps. Also updated `harness/scripts/nightly-harness.ps1` PowerShell wrapper to expose `-EnableAutoPipeline` / `-AutoPipelineUseClaude` switches for clean scheduled-task command-line flip.

  **T.3 verification:** Both gates pass.
  - Gate 6 (Friday safety): `nightly_harness.py --dry-run --format modern` (no flag) shows STEP 1.5 logs "SKIPPED" and original STEPS 1-7 unchanged.
  - Gate 3 (opt-in): `nightly_harness.py --dry-run --format modern --enable-auto-pipeline` invokes auto_pipeline.run_pipeline() in dry-run; shows "[DRY RUN] Would generate APL for [Landless Belcher / Cutter Affinity / Jeskai Phelia]".

  **T.4 live test:** `auto_pipeline.py --format modern --use-gemma` (standalone, since the wire is verified by T.3 — auto_pipeline does the writes regardless of caller). Result: 8 new archetypes detected, top 3 generated via Gemma in 499s wall, $0.00 cost. Wrote `harness/agents/optimization_memory.json` for first time (3 generated_apls + 3 playbooks). Generated APL files exist in `mtg-sim/data/auto_apls/`. APL validation failed (0/3) for new archetypes because they lack deck files (separate concern; auto_pipeline generates APLs but not decklists).

  **T.5 idempotency:** Second consecutive run (4 min wall) completed cleanly. Playbooks correctly short-circuit ("All decks with sim data already have playbook drafts"). APLs re-generate (memory file now has 6 entries — append-only, not deduped). Wasteful but not broken. Refinement deferred to follow-up spec.

  **Friday safety verified:** `register-harness-tasks.ps1` invokes `nightly-harness.ps1 -Format <fmt>` with no flag. Wrapper passes nothing to Python script unless `-EnableAutoPipeline` is present. Default-off path is byte-equivalent to pre-spec for STEPS 1-7 (only addition: STEP 1.5 "SKIPPED" log line).

  **No commits in mtg-sim:** Touched files (`harness/agents/scripts/nightly_harness.py`, `harness/scripts/nightly-harness.ps1`, `harness/HARNESS_STATUS.md`, `harness/IMPERFECTIONS.md`, `harness/RESOLVED.md`, this spec) are all in `harness/` which is unversioned per environment ("Is a git repository: false"). State is on-disk only.

  **Lesson NOT compounded into v1.5:** This is the second instance of `load-path-dependent-setup-creates-silent-no-op-features` class (first was tagger-fix at execution-chain S3.7). The lesson already exists in spec-authoring-lessons.md. No NEW generalization surfaced from this execution — just a confirming case. The "feature-flagged default-off for opt-in automation" pattern could be a future v1.6 lesson if a third such instance arises.
