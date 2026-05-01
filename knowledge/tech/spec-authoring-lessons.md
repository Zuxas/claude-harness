---

## title: "Spec Authoring Lessons" domain: "tech" last_updated: "2026-04-27" confidence: "high" sources: \["session-2026-04-27", "phase-3.5-stage-a-spec", "phase-3.5-stage-b-spec", "harness-tier-3-build-2026-04-27", "guide-attack-trigger-fix-spec", "d1-gource-renders-spec"\]

## Summary

Durable list of methodology lessons learned across spec executions. **Required reading before authoring any new spec** per `harness/CLAUDE.md` Rule 1. When a spec produces a new methodology lesson via Mid-execution Amendment, that lesson must be added here before the spec is marked SHIPPED (Rule 9).

The intent: turn one-time pain into permanent improvement. A lesson learned in Stage B's Amendment 4 should prevent the same mistake in Stage C's spec authoring, not evaporate when Stage B stops being read.

## How to use this file

**When authoring a spec:**

1. Read this file top to bottom
2. For each lesson, ask: "does this apply to the work I'm about to spec?"
3. If yes, incorporate the lesson into the spec's Validation gates / Stop conditions / Predictions sections
4. If you discover a NEW methodology lesson during spec execution, append it here before marking the spec SHIPPED

**When reviewing an existing spec:**

1. Cross-reference its predictions and validation gates against this file
2. Flag any lesson that should have been applied but wasn't

## Format

Each lesson follows this structure:

```
### lesson-slug

Discovered: <date> via <spec/commit/finding-doc>
One-line: <generalizable insight, not a stage-specific fact>
Background: <what happened that produced this lesson>
How to apply: <concrete checklist for future specs>
Anti-pattern: <what NOT to do, the mistake this lesson prevents>
Cost of ignoring: <what goes wrong if you skip this lesson>
```

---

## Open lessons

### per-iteration-vs-cross-iteration-state-changes

**Discovered:** 2026-04-27 via Phase 3.5 Stage A spec, Mid-execution Amendment 1 **One-line:** When refactoring per-iteration logic into accumulator logic over a collection, audit every assert/state-change inside the loop for whether it should be per-item or cross-item.

**Background:** Stage A refactored single-blocker assignment into list-of-blockers per attacker (to support menace). The per-blocker damage-to-attacker check was left at per-iteration scope: `if blk_pwr >= atk_tou: atk_dead.add(...)`. This is wrong per Magic CR 510.1 -- blocker damage SUMS on the attacker before the lethality check. Two 2/2 blockers vs a 3/4 menace attacker should kill it (4 &gt;= 4); per-iteration check kept it alive (neither 2 &gt;= 4 individually).

The bug was hidden in BE/Murktide mirrors because neither deck has menace creatures, so multi-blocker assignment never fired and the per-iteration loop ran exactly once (matching pre-refactor single-blocker behavior). Caught only when Claude reviewed the diff carefully before re-running validation; the gauntlets would have shipped with this bug undetected.

**How to apply:**

1. When a spec changes a one-to-one relationship into one-to-many (single -&gt; list, dict-value -&gt; list-value), explicitly enumerate every operation that was previously per-pair
2. For each operation, classify it: per-item (runs N times, accumulates state separately each iteration) OR cross-item (runs once after the loop, against summed/max/min of all iterations)
3. The default assumption should be CROSS-ITEM unless proven per-item -- most game rules sum/aggregate before checking thresholds
4. Add to spec validation gates: a synthetic test case that exercises N&gt;1 (e.g., menace with 2 blockers totaling lethal damage but neither lethal alone)

**Anti-pattern:** "The per-iteration check works in the N=1 case, ship it." Hidden bugs in N&gt;1 paths that aren't exercised by the existing test corpus.

**Cost of ignoring:** Bug ships, gets exposed only when matchup composition changes (e.g., Stage A's bug would have triggered the first time someone ran a Rakdos Aggro deck against the gauntlet -- silent wrong results, weeks of confused debugging).

---

### keyword-density-asymmetry-shifts-direction

**Discovered:** 2026-04-27 via Phase 3.5 Stage B spec, Mid-execution Amendment 4 **One-line:** Symmetric keyword fixes shift matchups asymmetrically by keyword density across decks; predict per-matchup shifts, not aggregate-from-our-side.

**Background:** Stage B added haste filter respecting `KWTag.HASTE`. Spec predicted upward shift +0.5 to +2pp because BE's Ragavans now attack T1. Actual canonical 1k Modern landed -0.5pp (in band but wrong direction). Mono Red matchup shifted -6.5pp.

Investigation: Mono Red Modern has 8 HASTE creatures (4 Goblin Guide + 4 Monastery Swiftspear) vs BE's 4 (4 Ragavan only). Symmetric fix shifted the matchup proportional to relative haste density. BE was over-rated pre-Stage-B because Mono Red's T1 hastes couldn't attack either; symmetric correction favors the deck with more haste creatures.

**How to apply:**

1. When a spec adds/fixes a symmetric keyword effect (one that benefits both sides), do not predict shift direction from BE-side keyword count alone
2. Run the keyword-density check across all 14 gauntlet matchups before predicting:

   ```python
   for opp_path in gauntlet_decks:
       opp_creatures_with_keyword = count_creatures_with_keyword(opp_path, KWTag.X)
   compare to BE_creatures_with_keyword
   ```
3. Predict per-matchup direction: if opp density &gt; BE density, the matchup shifts toward opp. If equal, expect mirror-like correction near 0. If BE density &gt; opp, BE gains.
4. Aggregate prediction = field-share-weighted sum of per-matchup predictions, not a single global direction

**Anti-pattern:** "Haste fix benefits BE Ragavans, so BE should win more." Ignores that BE's opponents also have haste.

**Cost of ignoring:** Stop conditions fire on what looks like regression but is actually honest model improvement. Time spent investigating the "regression" before realizing the prediction model was incomplete. Risk of rolling back a correct fix because it looked wrong.

---

### sim-vs-db-source-gates-engine-shifts

**Discovered:** 2026-04-27 via Phase 3.5 Stage B spec, B.6 spot-check resolution **One-line:** Engine changes can only shift matchups whose data source is `[SIM]`, not `[DB]`. Always check source per matchup before predicting shifts.

**Background:** Stage B spec included B.6 spot-check: "BE vs Eldrazi Ramp at n=500 should shift up from haste fix." Actual result: held at 49.2% (zero shift). Initially looked like the haste fix wasn't firing. Investigation showed canonical BE-vs-Eldrazi-Ramp is `[DB]`-cached (real tournament data, not simulation), so engine changes can't move the number. Variant Eldrazi Ramp at 91.9% IS `[SIM]` and DID shift, confirming engine working.

**How to apply:**

1. Before writing per-matchup spot-check predictions, run `python dashboard.py --deck "<deck>"` and identify which matchups are `[SIM]` vs `[DB]`
2. Spot-checks should target `[SIM]` matchups only -- `[DB]` matchups can't shift from engine changes
3. If you want to validate engine change against a `[DB]` matchup, you have to run the matchup explicitly through sim (`--no-cache` or whatever the equivalent is) -- the cached number is fixed
4. In the spec, annotate each prediction with `(SIM)` or `(DB)` so reviewers can sanity-check upfront

**Anti-pattern:** "We added X to the engine, so all 14 matchups should shift slightly." Assumes engine path runs for every matchup; ignores tournament-data caching.

**Cost of ignoring:** False-positive stop-condition triggers (looks like engine isn't firing when it actually is). Time spent trying to debug a non-bug. Worst case: assuming the engine change IS broken and reverting/rewriting it.

---

### load-bearing-wip-detection-applies-to-every-commit

**Discovered:** 2026-04-26 via load-bearing-wip findings doc + 2026-04-27 oracle_parser.py rediscovery **One-line:** When committing a tracked file that imports from another file, verify both files are tracked. Drift-detect now catches this mechanically, but the discipline applies at spec time too.

**Background:** Commit 0c0f42c committed `auto_handlers.py` + `effect_family_registry.py`, but `auto_handlers.py:22` did `from engine.oracle_parser import parse_oracle` and `oracle_parser.py` was untracked. Fresh clones couldn't import auto_handlers -- same pattern as the original load-bearing crash that necessitated commit 7e213ea.

Drift-detect.ps1 caught this on 2026-04-27 morning's run, \~24 hours after the bug was introduced. A pre-commit hook with import-graph awareness would have caught it at commit time, but [lint-mtg-sim.py](http://lint-mtg-sim.py) only checks AST-level registry/handler relationships -- not arbitrary imports across the engine module.

**How to apply:**

1. When a spec commits a tracked file that has any `from X import Y` or `import X` referencing other project files, the spec's pre-flight reads MUST include verification: `git ls-files <imported-file>`. If the import target isn't tracked, commit it in the same commit OR explicitly note it as a follow-up.
2. After committing, run `git stash && python -c "import <committed-module>"` to verify fresh-state imports succeed. Unstash after.
3. For multi-file refactors, write the spec's "Steps" section as: stage all imported files together, single commit. Don't commit the consumer without the producer.

**Anti-pattern:** "I just added an import to a working file, so this'll work after commit." Ignores that the import target may be untracked.

**Cost of ignoring:** Fresh clones / CI / new contributors hit ImportError on first run. Hours of confused debugging. Worst case: silent wrong behavior if the missing import has a partial fallback path.

---

### spec-prediction-model-must-be-falsifiable

**Discovered:** 2026-04-27 generalizing from Amendments 1-4 across Stages A and B **One-line:** A spec's predictions are part of the spec, not separate from it. If predictions are vague ("should shift modestly"), the stop-condition triggers can't distinguish "spec was wrong" from "implementation is broken."

**Background:** Stage A's BE mirror prediction was "47-54% range" -- a wide band that hid an actually-noise result (46.3% with overlapping CI). Stage B's canonical prediction was "+0.5 to +2pp upward" -- single direction, no per-matchup model, fired stop-condition on what turned out to be correct behavior. In both cases, mid-execution amendment had to reconstruct what the prediction SHOULD have been to interpret the result.

**How to apply:**

1. Predictions in specs should be: (a) numeric ranges with explicit acceptance bounds, (b) per-matchup not just aggregate when keyword effects vary by opponent, (c) accompanied by the mechanical reasoning behind the prediction so a failed gate can be diagnosed as "prediction wrong" vs "implementation wrong"
2. For aggregate predictions, decompose: `predicted_aggregate = sum(field_share[i] * predicted_per_matchup[i] for i in matchups)`. If you can't write this expression, the prediction isn't falsifiable.
3. After implementation, before running validation: write down what the per-matchup predictions imply for the aggregate. If the aggregate doesn't match what the spec predicted, the prediction model itself was wrong -- fix the model before interpreting the result.

**Anti-pattern:** "Aggregate should be in 65-69% range" with no per-matchup decomposition. When result lands at 65.3% (in band) but Mono Red moved -6.5pp, you can't tell if the aggregate-being-in-band is good news or coincidence.

**Cost of ignoring:** Stop-condition triggers on real correct behavior (false positive) OR fails to trigger on real bugs that happen to land in the prediction band (false negative). Trust in the validation pipeline degrades.

---

### windows-powershell-ascii-only-for-ps1-files

**Discovered:** 2026-04-27 via drift-detect.ps1 crash on first user-run after Tier 3 build **One-line:** Windows PowerShell 5.1 reads `.ps1` files as cp1252 by default; UTF-8 multibyte characters (em-dashes, smart quotes, box-drawing) corrupt to mojibake on read and crash the parser. Keep .ps1 files ASCII-only.

**Background:** drift-detect.ps1 v1.0 contained `"# Drift Report -- $dateStr"` written with a real em-dash character (U+2014) inside a `Set-Content` string literal. The bytes `0xE2 0x80 0x94` (UTF-8 for em-dash) were written to disk correctly. When PowerShell 5.1 read the file (as it does on every Windows machine without explicit pwsh 7+), it interpreted those bytes as cp1252 -&gt; garbled text. The parser crashed with "Unexpected token" errors that pointed at lines that LOOKED fine in any UTF-8-aware editor. The script crashed at parse time, before any logic ran.

The Python equivalent (gemma_drift_pr.py) had the same trap on the `--show-prompt` path (cp1252 stdout when piped). Fixed there with `sys.stdout.reconfigure(encoding="utf-8")` plus `$env:PYTHONIOENCODING="utf-8"` belt-and-suspenders. PowerShell can't be fixed the same way -- the file-read encoding is set before any code runs, so the only durable fix is "don't put non-ASCII in .ps1 files."

**How to apply:**

1. When writing `.ps1` files, restrict to 7-bit ASCII (chars 0x20-0x7E plus `\r\n\t`). No em-dashes, no smart quotes, no Unicode arrows, no box-drawing chars.
2. If you need a visual separator, use `--`, `==`, `**`, or ASCII pipes `|`. If you want pretty section dividers, use ASCII dashes only.
3. Add an "ENCODING NOTE: ASCII-only" comment near the top of each .ps1 file as a reminder for future editors.
4. The same trap applies to `.psm1`, `.psd1`, and `.ps1xml` files.
5. **Files where this DOES NOT apply** (UTF-8 is fine): markdown (`.md`), Python (`.py`, with `# -*- coding: utf-8 -*-` or default Python 3 UTF-8), JSON written via libraries that handle encoding, output files written by scripts with explicit `-Encoding UTF8`. The trap is specifically about source files that PowerShell 5.1 itself parses.
6. PowerShell 7+ (pwsh) defaults to UTF-8 reads. If you can guarantee pwsh 7+, the constraint relaxes -- but the Windows scheduled tasks run `powershell.exe` (5.1) by default, so this is not a safe assumption for harness scripts.

**Anti-pattern:** "I'll just paste this Markdown-style em-dash into the script comment, looks nicer." Or letting an LLM write strings with em-dashes by default (Claude does this without thinking; lesson candidate authors should review LLM-generated PowerShell explicitly for non-ASCII chars).

**Cost of ignoring:** Script crashes at parse time with a confusing "Unexpected token" error pointing at corrupted bytes the editor displays as normal text. The error message contains the mojibake which makes the cause obvious in retrospect but isn't searchable as such. In the worst case the trap hides until the script is invoked from an environment where it parses (UTF-8-aware editor REPL or pwsh 7) but crashes when run from the scheduled task or vanilla PowerShell.

**Detection rule for drift-detect (future enhancement):** scan all `harness/scripts/*.ps1` and `harness/scripts/templates/*.ps1` for any byte &gt; 0x7F. Flag as ERROR. Add to drift-detect.ps1 as a 7th check.

---

### verify-identifiers-before-spec-execution

**Slug history:** Originally `verify-script-filenames-before-spec-execution` (2026-04-27 v1.2). Generalized 2026-04-27 v1.3 to cover package manager IDs after D1 amendment A1. Both slugs valid -- index lookup table accepts either.

**Discovered:** 2026-04-27 via Guide attack-trigger fix spec (commit cf75e1a); generalized 2026-04-27 via D1 Gource render spec amendment A1 **One-line:** When a spec references CLI commands, script invocations, OR package manager IDs, verify each one exists in its canonical source BEFORE pasting. Guessing names from prose descriptions or naming conventions produces fictional identifiers that crash on execution.

**Background (case 1: fictional script filename):** Guide spec v1.0 prescribed `python goldfish_canonical.py --n 1000 --seed 42` as the validation Step 3. The IMPERFECTIONS entry the spec was based on said "re-baseline canonical goldfish (expect drift +0.0 to +0.05 turn slower)" -- an action description, not a command. I extrapolated `goldfish_canonical.py` from that description without checking the repo.

When user ran the command, Python crashed: `can't open file 'E:\vscode ai project\mtg-sim\goldfish_canonical.py': [Errno 2] No such file or directory`. Investigation surfaced the actual canonical entry point: `scripts/sleeve_check.py` invoked with `variant=canonical`.

**Background (case 2: fictional CLI flag):** Same Guide spec, Step 4: `python parallel_launcher.py --deck X --opponent Y --n 2000`. `parallel_launcher.py` has no `--opponent` flag. Actual single-matchup runner is `run_matchup.py "OUR_DECK" "OPP_DECK" FIELD_PCT N SEED FORMAT TYPE` (positional args, not flags).

**Background (case 3: fictional package manager ID):** D1 Gource render spec, 2026-04-27 evening, said `winget install Gource.Gource` -- following the natural-sounding `Publisher.Product` convention used by many winget packages. Real winget ID is `acaudwell.Gource` (matches the GitHub org name, not the project's display name). Claude Code caught this mid-execution and corrected by running `winget search Gource` first. Same root cause as cases 1-2: pattern-match from prose into a hypothesized identifier without verifying against the canonical source.

**How to apply:**

1. **Filenames:** when a spec's Steps section references a CLI command, the spec author MUST verify each script exists. Concrete check: list the script's directory or get_file_info on the exact path before pasting the command.
2. **CLI flags:** when a spec's Steps section references CLI flags, the spec author MUST verify the flags exist. Concrete check: read the script's argparse setup (typically near the bottom of the file or in a `main()` function) before pasting flag-based commands.
3. **Package manager IDs:** when a spec references a package install (winget, brew, apt, choco, pip, npm, cargo, etc.), verify the EXACT package ID via the canonical search command BEFORE pasting. Examples: `winget search <name>`, `brew search <name>`, `pip search <name>` (or `pip index <name>` on newer pip), `npm search <name>`. Do NOT infer IDs from `publisher.product` convention -- many packages don't follow it. Common gotchas:
   - winget often uses GitHub org names (`acaudwell.Gource`, `Gyan.FFmpeg`) not project display names
   - homebrew uses lowercase formula names that may not match the project's casing
   - apt uses lowercase package names that often have suffix variations (`-dev`, `-utils`, etc.)
4. **Pre-flight reads section:** the pre-flight reads section of every spec that includes shell commands MUST include the relevant script files (and a note about verifying package IDs if applicable), with verification recorded as part of the spec's Step 1.
5. **Meta-rule:** the act of writing a spec command should never be "guess from description" or "infer from convention" -- it should be "copy from verified source." This applies to filenames, flag names, and package manager IDs equally.

**Anti-pattern:** Pattern-match from imperfections-doc prose ("re-baseline canonical goldfish") into a hypothesized filename (`goldfish_canonical.py`). Or assume `winget install <Project>.<Project>` from the convention. The hypothesis sounds plausible to a reader; the identifier doesn't exist.

**Cost of ignoring:** Spec execution stalls at the first command that doesn't run. Fixing mid-flight requires re-reading the codebase or running the package search, hunting for the real identifier, amending the spec, then re-running. Three corrections needed across two specs in 2026-04-27; each cost \~5-10 minutes. In a worse case (e.g., spec is queued for someone else to execute), they'd be blocked until clarification.

**Prevention via tooling (SHIPPED 2026-04-29 as drift-detect check [9/9]):** `lint-spec-references.py` scans PROPOSED/EXECUTING specs for `python <path>` patterns and verifies each path exists on disk. FLAG missing scripts as ERROR. Wired into `drift-detect.ps1` as `Check-SpecReferences`. Catches fictional script paths before execution. Also detects `--help` in pre-flight sections (INFO). Found and flagged `goldfish_canonical.py` (Guide spec, already SHIPPED/historical) as first real detection.

---

### teach-the-tool-not-the-data

**Discovered:** 2026-04-27 via deck-count audit (no commit; harness file edit only) **One-line:** When a downstream tool flags an issue your upstream already triaged, fix the tool's recognition logic, not the underlying data. Going around the triage destroys the work the triage explicitly preserved.

**Background:** drift-detect surfaced 3 deck-count WARN entries (glockulous, livingend, yawgmoth in Modern). Initial framing of the fix was binary: "patch the counts to 60" (option A) or "replace decks with current canonical from DB" (option B). Both options would have modified deck files.

Investigation surfaced `data/deck_triage_2026-04-25.md` -- a triage doc from two days earlier that had already gone through this exact decision. The 2026-04-25 triage explicitly chose CUSTOM_VARIANT (preserve as-is, add header marker) over BUG (replace with canonical) for all three decks, with rationale documented per file. The decks already had `// audit:custom_variant` header comments.

The drift-detect WARN was a false positive: a downstream tool (`lint-mtg-sim.py`) didn't recognize the audit markers that the upstream tool (`verify_deck_load`) had already been taught about. Two solutions presented themselves:

- **Wrong:** Modify the deck files based on the WARN. Destroys 2026-04-25's variant content.
- **Right:** Teach `lint-mtg-sim.py` about the audit markers. WARNs downgrade to INFOs with explanatory note pointing at the triage doc. No deck files modified.

The right solution was a 30-line addition to `lint-mtg-sim.py`: a `_deck_is_audit_triaged()` helper that scans the first 10 lines of a deck file for `audit:intentional` or `audit:custom_variant` markers, and gates the count check on the result.

**How to apply:**

1. When drift / lint / CI flags an issue, before fixing the data, ask: "has this been triaged before? What did that triage decide?"
2. Search the project for triage / audit / decision docs that might have addressed this exact issue. (Concretely: `Get-ChildItem -Recurse -Filter "*triage*"` or grep for the file name.)
3. If a prior triage chose to preserve the flagged state (CUSTOM_VARIANT, INTENTIONAL, ACCEPTED, etc.), the right fix is in the tool that's flagging, not in the data.
4. Codify the convention: a marker comment that the tool can read (`// audit:X`, `// research:Y`, `// intentional`) lets the tool defer to the triage decision rather than overruling it.

**Anti-pattern:** "The lint says fix it, so I'll fix it." Treats lint output as authoritative when the lint tool may itself be incomplete relative to the project's triage history.

**Cost of ignoring:** Destroys triage work and forces rediscovery. In this case, the 2026-04-25 triage had pulled canonical references from `mtg_meta.db`, decided per-deck, and added per-file rationale. Replacing the deck files would have lost all that decision content; the drift WARN would have re-fired on the next iteration of the same custom variants.

**Methodology generalization:** Every project has multiple tools that look at the same data with different rules. When tool A is downstream of tool B's decisions, tool A should know how to read tool B's decision artifacts. The decision artifacts (markers, frontmatter, sidecar files) are the durable interface; reading them is cheaper than re-deriving the decision.

---

### research-in-progress-is-a-third-option

**Discovered:** 2026-04-27 via orphan-engine-files triage (no commit; filesystem move + harness file edits) **One-line:** When an imperfection presents as binary "delete dead code OR commit it as final", the right answer is sometimes a third option: stash the work to a `_research/` subdirectory with a README documenting status and revival path. Filesystem location communicates status better than stale code comments.

**Background:** [IMPERFECTIONS.md](http://IMPERFECTIONS.md) entry `orphan-engine-files` flagged two engine files (`engine/card_priority.py`, `engine/card_telemetry.py`) as "untracked AND no importers in tracked code, decision needed: wire up, finish, or delete." Reading them surfaced that they were a deliberately-designed pipeline (card-handler-priority queue with telemetry-driven scoring) -- well-architected (clean dataclasses, pure functions, persistent severity tags), but never wired into the simulator. Companion scripts (build_priority_queue, summarize_telemetry, etc.) also exist as untracked files.

Binary framing missed the right answer. Delete option (B) destroys \~600 lines of deliberate research. Wire-up option (A) is real engineering work (3-4 hours minimum to hook telemetry into all the right sim-loop sites). Defer option (C) leaves the orphan flag open indefinitely.

The right fix: move both files to `engine/_research/` and write a comprehensive README documenting (a) what's in each file, (b) what's NOT here -- the companion scripts that would need to move alongside, (c) why it was moved (research-in-progress, not ready to commit, not safe to delete), (d) revival path (concrete steps + effort estimate), (e) lint/drift handling (how the harness should treat `_research/` paths).

The act of moving the files communicates "not yet wired" more clearly than any status comment in the file itself. A reader who opens `engine/card_priority.py` at the top level expects it to be in the simulator's import graph; a reader who opens `engine/_research/card_priority.py` immediately understands the file is in a holding state.

**How to apply:**

1. When an imperfection presents as "delete OR commit", check for a third option: "stash to \_research/ with revival README."
2. Use `_research/` for code that is: (a) deliberately designed but not yet wired, (b) too valuable to delete, (c) too unfinished to commit as part of the live simulator. Anti-pattern: using `_research/` for actually-dead code (which should be deleted) or for finished features (which should be committed).
3. Every `_research/` stash MUST include a README with: file inventory, missing companion files (if any), reason for stashing, revival path with effort estimate, lint/drift handling notes.
4. The convention extends to any module: `engine/_research/`, `apl/_research/`, `scripts/_research/`. The pattern is "module/\_research/" not "single global research/" so research stays scoped to where the wired-up version would live.

**Anti-pattern:** Treating "delete vs commit" as the only options when reviewing orphan files. Deletes valuable research; commits forces unfinished work into production.

**Cost of ignoring:** Either (a) accumulating orphan files at top level that get re-flagged on every drift run (status = "imperfection forever open"), or (b) deleting deliberate research because the binary framing doesn't acknowledge "not done but not dead" as a state.

**Tooling implication:** Drift-detect's load-bearing-WIP check naturally handles `_research/` correctly without modification: files in `_research/` that get committed will be in `git ls-files` so they don't trip the untracked-but-load-bearing case; files in `_research/` that stay untracked won't trip the load-bearing case unless something tracked imports from them, which the convention prohibits. No drift-detect changes needed.

---

### prefer-version-over-help-for-preflight-probes

**Discovered:** 2026-04-27 via D1 Gource render spec amendment A3 **One-line:** When writing a pre-flight liveness check for a CLI tool, use `--version` (or `Get-Command` / `command -v`) not `--help`. Help commands often invoke interactive pagers that block forever in non-tty environments.

**Background:** D1 Gource render spec's pre-execution check used `gource --help | Select-Object -First 1` as a tool-existence probe. In Claude Code's non-interactive PowerShell session, `gource --help` invoked an interactive help viewer (pager-style) that blocked waiting for user keystrokes. The check stalled until Claude Code skipped it (amendment A3) and proceeded directly to the render commands themselves, which don't need a tty.

Real fix would have been `gource --version` (returns immediately with version string) or `Get-Command gource -ErrorAction SilentlyContinue` (returns CommandInfo if found, $null if not). Either is non-blocking and answers the actual question "does this tool exist on PATH?"

**How to apply:**

1. For pre-flight tool-existence checks, use `<tool> --version` first. Most CLIs print version and exit immediately.
2. If the tool doesn't support `--version`, fall back to:
   - Windows: `Get-Command <tool> -ErrorAction SilentlyContinue` (returns CommandInfo or $null)
   - POSIX: `command -v <tool>` (returns path or non-zero exit)
3. NEVER use `<tool> --help` in a non-interactive context unless you've verified that specific tool's `--help` is non-blocking. Many help implementations auto-detect "interactive terminal" and adapt -- in a piped or scheduled-task context they may misbehave.
4. Common offenders that pager-invoke their help: man-style tools (git, vim, less, more, gource on some platforms), Java-based tools that launch a GUI window for help, anything with a "more"/"less" page-through behavior.
5. When in doubt, prefer `Get-Command` / `command -v` over invoking the tool itself. Existence is what you need to check; you don't actually need to see the help text.

**Anti-pattern:** "I'll use `--help` for the pre-flight check, the help text will tell us if the tool exists." Help text is for humans reading interactively; pre-flight checks need a non-blocking liveness probe. Mixing the two reveals you haven't thought about the execution context (interactive vs piped vs scheduled).

**Cost of ignoring:** Pre-flight check stalls indefinitely in non-interactive environments (Claude Code sessions, CI pipelines, scheduled tasks). Spec executor either skips the check (defeats the purpose) or kills the hung process and amends the spec mid-flight. \~5 min cost per stall. Worse: erodes trust in pre-flight checks generally, making future spec authors skip them entirely.

**Tooling implication (SHIPPED 2026-04-29 as drift-detect check [9/9]):** `lint-spec-references.py` sub-detection 1.3 scans for `<tool> --help` in pre-flight/preflight/verify headings and flags INFO. Wired into `drift-detect.ps1`. Found `gource --help` in d1-gource-renders.md on first real scan.

---

### validation-pipelines-need-their-own-validation

**Discovered:** 2026-04-27 evening via Phase 3.5 Stage C C.4 (cache-collision bug surfaced)
**One-line:** The falsifiable-prediction discipline implicitly trusts the measurement pipeline. When the pipeline silently corrupts measurements, divergence-from-prediction surfaces the wrong root cause (the patch under audit, not the pipeline).

**Background:** Stage C C.4 validation showed variant Izzet Prowess shifting -51.2pp post-patch. Mechanical analysis confirmed Izzet Prowess deck has zero protection-cluster creatures — the patch IS a true no-op for that matchup. Synthetic tests passed 5/5 in isolation. The "shift" was 100% pipeline corruption: parallel_launcher's matchup_jobs subprocess output files were keyed by opp-name only; concurrent variant + canonical gauntlets clobbered each other's writes; variant gauntlet's display layer read canonical's value.

The v1.3 falsifiable-prediction lessons (per-matchup density, SIM-vs-DB source) all assumed the gauntlet measurements arriving at the prediction-comparison step were truthful per-deck per-matchup measurements. That assumption was unstated and unchecked. The cache-collision bug had been silently corrupting variant numbers across at least 3 stages before it surfaced.

**How to apply:**
1. The validation pipeline itself is part of the system under test, not an external oracle. Prediction divergences can mean: (a) implementation wrong, (b) prediction model wrong, OR (c) **pipeline corruption between implementation output and prediction comparison**.
2. When prediction divergence + mechanical proof of no-op contradict, the pipeline is the next suspect after the patch (see also `mechanical-noop-vs-large-shift-points-at-pipeline` below).
3. Validation pipelines should themselves have regression tests that prove the pipeline produces correct per-deck per-matchup output under realistic invocation patterns (concurrent runs, repeated runs, different parameter sets).
4. When designing the falsifiable predictions for a stage, include "and the pipeline is producing trustworthy measurements" as an unstated assumption that reviewers should be able to question.

**Anti-pattern:** "I added a regression test for the patch's effect; if the test passes the patch is good." Doesn't catch pipeline corruption that masks the patch's actual behavior in measurements.

**Cost of ignoring:** Bugs ship hidden inside other bugs; multiple stages compound corruption before anyone notices. Tonight's cost: Stage C revert + 4 hours of investigation + 4 specs to unwind. Without the spec-first execution discipline forcing diagnostic-before-shipping, this could have shipped silently and corrupted gauntlet numbers indefinitely.

---

### mechanical-noop-vs-large-shift-points-at-pipeline

**Discovered:** 2026-04-27 evening via Stage C C.4 diagnostic chain
**One-line:** When a stage's empirical results contradict mechanical proof, the pipeline is the next suspect after the patch.

**Background:** Stage C's C.1 patch added HEXPROOF/SHROUD filtering to `_damage_any_helper`. Density check confirmed Izzet Prowess deck has ZERO creatures with HEXPROOF/SHROUD/WARD/PROTECTION tags. Patch should be a true no-op for variant-vs-Izzet-Prowess. C.4 showed -51.2pp shift on that matchup. Synthetic tests confirmed helper logic correct in isolation. Direct `run_match_set` call returned 93.8%. Gauntlet display showed 48.5%.

The natural diagnostic priority order is:
1. Patch is wrong (default suspect)
2. Tests are insufficient
3. Prediction model is wrong
4. Pipeline is wrong (rare; usually trusted)

When mechanical proof rules out (1) and (2) — patch is no-op against this matchup, synthetic tests pass — the priority order needs to flip. (3) and (4) become the active suspects, and (4) should escalate above (3) when the magnitude of divergence is implausible for a prediction-model error (a prediction model error rarely produces -51pp on a single matchup; pipeline corruption easily can).

**How to apply:**
1. Calibrate magnitude expectations for each diagnosis class:
   - Patch bug: typically 0-10pp on affected matchups
   - Prediction-model gap: typically 0-5pp aggregate, can be larger per-matchup if mechanism overlooked
   - Pipeline corruption: can be arbitrary; not bounded by mechanism
2. When divergence magnitude is implausible for the suspected class (e.g., -51pp on a no-protection matchup; +43pp where 0pp predicted), escalate pipeline corruption ABOVE prediction-model errors in diagnostic priority.
3. Direct-call diagnostic (bypass the validation pipeline; call the engine function directly) is a fast disambiguator — if direct call gives the prediction-consistent value but pipeline-display gives a different value, pipeline corruption is confirmed.
4. Don't accept "the pipeline is producing correct numbers" as a default assumption when results contradict mechanical proof.

**Anti-pattern:** "C.4 showed an unexpected shift; the patch must have an unintended interaction." Default suspicion on the patch wastes investigation time when the pipeline is the actual fault.

**Cost of ignoring:** Stage C surfaced this exact pattern. Without the diagnostic chain (tagger audit -> direct match_set -> cache file inspection), the natural inclination would have been to revert the patch and re-investigate the helper logic — the wrong loop.

**Corollary (added 2026-04-28 from Stage C re-execution A6):** Small-magnitude shift on a mechanically-no-op patch points at non-determinism, NOT pipeline-corruption. The full diagnostic priority order, calibrated by magnitude:
- Pipeline corruption: arbitrary magnitude (often >10pp on a single matchup) — investigate when divergence is implausible for any mechanism
- Non-determinism in shared state: small magnitude (often <1-2pp aggregate) when the patch is mechanically inert — investigate when divergence is small but non-zero with same seed
- Patch bug: medium magnitude (5-15pp on affected matchups, smaller on others)
- Prediction-model gap: 0-5pp aggregate, can be larger per-matchup if mechanism overlooked

Stage C A6: variant gauntlet drifted +0.6pp between C.0 and C.4 at fixed seed=42, n=1000, with C.1 mechanically inert per A5. The drift wasn't pipeline-corruption (cache-fix verified at e4fae86) and wasn't a patch bug (patch can't fire). It was empirical evidence of the long-standing `stage-1-7-event-bus-determinism` IMPERFECTIONS entry operating at production gauntlet scale — a useful production-scale measurement that the existing n=200 same-seed evidence wasn't capturing.

---

### caches-keyed-on-partial-state-are-time-bombs

**Discovered:** 2026-04-27 evening via Stage C C.4 cache-collision-bug
**One-line:** Caches (or any shared-state file/path) keyed on partial context work correctly when the missing context is held constant by convention but break silently when convention is violated.

**Background:** `data/matchup_jobs/<opp_slug>.json` was keyed on opp name only, NOT on `(our_deck, opp)`. The implicit assumption: only one our_deck per session. When that assumption held (single deck per launch), the layout worked correctly. When it was violated (variant + canonical gauntlets running concurrently), last-writer-wins clobbered.

The bug class generalizes beyond caches: any path/file/key that is shared across processes/sessions with implicit context (env vars, current-time, our-deck, etc.) silently breaks when context is no longer held constant. Drift-detect's load-bearing-WIP check is the analogous safety net for one specific class (untracked-file imports); cache-key audit is the analogous safety net for shared paths.

**How to apply:**
1. When designing any shared cache / file / key / path layout, enumerate the parameter space the system might see (now and in the foreseeable future) and verify the key includes every dimension that varies.
2. If the key omits a dimension that's currently held constant by convention, document the convention as a precondition AND add a runtime check (or sentinel file) that fails loudly when the convention is violated.
3. Pipelines used by multiple parameter sets (e.g., variant + canonical gauntlets) should have cache-key audits as part of their test discipline.
4. New lesson: drift-detect 8th check could scan the codebase for cache-write patterns and verify the key namespace matches the parameter-space the launcher accepts.

**Anti-pattern:** "We only ever run one deck at a time, so opp-name-only keying is fine." Silent failure mode the first time someone runs two decks concurrently.

**Cost of ignoring:** Variant gauntlet numbers across at least 3 stages were silently polluted before the bug surfaced. Past-validation-numbers-audit had to be its own spec. The fix itself was small (~75 min) but the diagnostic + audit chain consumed an entire evening.

---

### re-execution-specs-require-fresh-baseline-capture

**Discovered:** 2026-04-28 via Phase 3.5 Stage C re-execution Amendment A4
**One-line:** When a spec re-executes after meaningful intervening engine changes, capture a fresh baseline at the new HEAD before validation. Documented prior-stage numbers are at-best a sanity-check reference, not a load-bearing acceptance anchor.

**Background:** Stage C was reverted at de96593 (cache-collision discovery). Cache-fix shipped at e4fae86. Past-validation-numbers-audit confirmed Stage A/B variant numbers (77.8% / 78.2%) were clean via JSON recovery — 0.0pp drift from documented. Cache-fix Gate 2 ran a fresh post-fix variant gauntlet and observed 78.5%, +0.3-0.7pp drift attributable to engine evolution between Stage B SHIP (c95ea55) and current HEAD (e4fae86) — primarily Guide attack-trigger fix at cf75e1a.

Stage C re-execution's original predictions ("canonical -0.13 to -0.35pp from 65.8% baseline") were anchored on Stage A/B numbers. Without a fresh-baseline capture, a mechanically-correct C.1 result would land outside the predicted band purely from the unrelated engine drift, looking like prediction failure. Conversely, a mechanically-wrong result that happened to land within the stale band would pass validation falsely.

**How to apply:**
1. Re-execution specs MUST include a baseline-capture step before any code change. The baseline is captured at current HEAD via the same validation script that the final acceptance gate will use.
2. Predictions express acceptance bands as `fresh_baseline ± shift = predicted_post_patch`, both sides numeric. Future-readers can verify the baseline AND the shift independently.
3. Drift between fresh baseline and prior-stage documented numbers is itself a useful diagnostic: small drift = engine-evolution noise (continue with confidence); large drift = something more significant changed (investigate before proceeding).
4. The pre-flight reads section of any re-execution spec should call out which prior commits intervened between the original stage and re-execution HEAD; the baseline-capture step then explicitly accounts for them.

**Anti-pattern:** "The original spec's predictions are good; just re-run the validation against them." Stale anchor; false-fail and false-pass risks both present, future-reader can't disambiguate.

**Cost of ignoring:** Stage C re-execution would have looked like prediction failure on a perfectly-correct C.1 result, triggering a wasted re-investigation chain. Or worse, a wrong result could have passed within stale tolerance bands.

---

### load-path-dependent-setup-creates-silent-no-op-features

**Discovered:** 2026-04-28 via Phase 3.5 Stage C re-execution Amendment A5
**One-line:** When a feature depends on per-card setup (tagging, indexing, registration) and the codebase has multiple load paths, verify the setup actually runs against every load path under test. Otherwise the feature is inert against the half of the test corpus that uses the unsetup path.

**Background:** Stage C C.1 added `can_be_targeted_by(target, ...)` checking `KWTag.HEXPROOF in target.tags`. The check is correct in isolation (5/5 synthetic tests pass) and correct against any card that has the HEXPROOF tag. But `tag_keywords` (which scans oracle text and applies tags) is called only from `data/deck.py:176` (the .txt load path) — NOT from `build_deck_from_dict` in `generate_matchup_data.py` (the dict path used by stub-loaded decks). Engine never re-tags at game-setup. Of 14 Modern field opps, 3 use the stub path and their hexproof creatures (notably Domain Zoo's 4 Scion of Draco) never receive HEXPROOF tag at runtime. C.1's filter is therefore a true no-op for those matchups.

Same mismatch implicates Stage A (MENACE block-eligibility) and Stage B (HASTE/DEFENDER/VIGILANCE/lifelink filters) — those features work for .txt-loaded opps but are silent against stub-loaded opps. The shipped impact of Stages A and B is partial; full impact materializes only after the load-path mismatch is fixed.

This is a class of bug: feature works correctly in isolation, passes synthetic tests, lands without breaking aggregate validation gates — but is inert against a meaningful fraction of the test corpus due to a load-path-dependent setup step that doesn't run universally.

**How to apply:**
1. When a feature depends on per-card or per-object state that's set up by a function (tagger, indexer, registry, normalizer), enumerate every load/construction path that produces those objects and verify the setup function runs on each path.
2. Synthetic tests prove the feature works when setup ran; they DON'T prove setup actually runs against the production test corpus. Add at least one "production-path" test that constructs an object via the actual production load path and asserts the setup state is present.
3. When predicting a feature's empirical impact, include a load-path verification step in the prediction model: "this prediction assumes setup runs on the test corpus; verify before measuring."
4. When a feature ships but lands ~0pp impact against a corpus that should mechanically show shift, the load-path-vs-setup-mismatch is a high-priority diagnostic suspect.
5. When a foundational fix (like extending setup to the missing load path) is identified, do NOT bundle it into the feature spec that surfaced it — bundle would violate `spec-prediction-model-must-be-falsifiable` (validation gates couldn't isolate which change drove which shift). Foundational fixes get their own spec.

**Anti-pattern:** "Synthetic tests pass and aggregate validation lands within band, ship it." Misses inert-against-corpus class. The 5/5 synthetic Stage C tests proved C.1 correct; the ~0pp aggregate landed within band; both gates passed but the feature is inert against current field.

**Cost of ignoring:** Stages A and B already shipped with this exact pattern (partial-effect against stub-loaded opps). Without A5's surfacing, Stage C would have shipped the same way — three stages of partial-effect features compounding before anyone noticed.

**Tooling implication:** Drift-detect could scan for tagger / setup function definitions and check that they're invoked from every Card-constructor or deck-load path in the codebase. Higher priority than the cache-key audit (more failure modes). Specifically: look for `tag_keywords` invocations and flag every Card-constructor site that bypasses it.

---

### parallel-entry-points-need-mirror-fix

**Discovered:** 2026-04-28 via Stage 1.7 execution-chain S3.8 D5 validation
**One-line:** When a fix touches one entry point, search the codebase for parallel entry points that perform the same role; the parallel point likely needs the mirror fix.

**Background:** Stage 1.7 fixed global-random-module determinism by save/seed/restore around the loop body in `engine/match_runner.py:run_match_set`. Initial production-scale validation (BE Modern gauntlet n=1000 seed=42 twice) showed canonical aggregate +0.10pp drift and per-matchup max-dev 1.80pp on five `bo3` matchups (Domain Zoo, Izzet Affinity, Izzet Prowess, Eldrazi Tron, Jeskai Blink). All `sim`/`db`/`com` matchups collapsed to 0.00pp, but `bo3` matchups did not. Root cause: `engine/bo3_match.py:run_bo3_set` is a parallel entry point with the same loop-over-games structure that does NOT route through `run_match_set` for the bo3-with-sideboarding path. Same fix needed at the bo3 entry. After mirror fix: all matchups 0.00pp.

This is a generalization of `load-path-dependent-setup-creates-silent-no-op-features` from setup functions to fixes themselves. Both share the underlying anti-pattern: the codebase has multiple call sites that perform structurally equivalent roles, but a change at one site doesn't propagate to the others. For setup, the symptom is silent-no-op features; for fixes, the symptom is partial fixes with persistent residual symptoms.

**How to apply:**
1. When fixing a function, grep the codebase for sibling functions with similar names, similar docstrings, or similar caller patterns. `run_match_set` has a sibling `run_bo3_set` — same shape, different specialization. The grep is `^def run_.*_set\b` or `^def .*(rng|seed)`.
2. Validation gates must include a parallel-entry-point check: enumerate every entry point that could exercise the bug and verify each is fixed.
3. When initial validation shows partial fix (some test cases pass, others persist), the parallel-entry-point hypothesis is the highest-priority diagnostic suspect — check it before deeper engine debugging.
4. Drift-detect implication: scan for clusters of similarly-named entry points (e.g., `run_*_set`, `load_*_from_*`, `build_deck_from_*`) and flag fixes that touch only one cluster member.

**Anti-pattern:** "I fixed the function, validation showed mostly-fixed, must be acceptable noise." Misses parallel-entry-point class. The "1.80pp on bo3 matchups only" residual was suspiciously structured (all bo3, no sim/db/com); structure suggested parallel entry, not noise.

**Cost of ignoring:** Stage 1.7 would have shipped 0.00pp on most matchups but persistent ±1-2pp on bo3 matchups, leaving Phase 3.5 Stages D-K with a mysterious "bo3-only noise floor" that would take another diagnostic session to chase down.

**Tooling implication:** Drift-detect 9th check candidate — when a commit touches an `engine/*_match.py` or `engine/*_set` file, flag any sibling files with similar suffixes that didn't change. Lower priority than the 8th check (cache-key audit) but compoundable.

---

### stop-conditions-on-subsets-must-use-noise-floor-appropriate-aggregation

**Discovered:** 2026-04-28 via execution-chain S3.7 tagger-fix gates 6+7 misfire (validating event: Stage 1.7 collapsed both per-matchup and aggregate noise to 0.00pp, confirming the original calibration was masked by uncontrolled non-determinism)
**One-line:** When a stop condition is defined on a subset metric, it must use the aggregation level whose noise floor matches the predicted signal magnitude. Per-matchup noise can exceed aggregate noise by 5-10x when uncorrelated noise mostly cancels in aggregate.

**Background:** Tagger-fix spec stop condition #2 read "Any .txt-loaded matchup shifts > 2pp — that's a sign of unrelated drift; investigate before declaring stub-loaded shifts attributable to tagger-fix." Calibrated against the +0.6pp aggregate non-determinism residual (Stage C A6). During T.3 comparison, Eldrazi Tron canonical .txt-loaded shifted -5.1pp, Mono Red -2.0pp, BE mirror variant -2.1pp — all violating the stop condition. Investigation revealed those per-matchup shifts were Stage 1.7 non-determinism residual (per-matchup variance ±2.5pp pre-fix), not patch effects. The real signal lived at subset-aggregate level: 11 .txt-loaded matchups subset-aggregate -0.51pp (within noise), 3 stub-loaded subset-aggregate -4.52pp (real patch effect).

The spec's stop condition was calibrated against the wrong aggregation level. The +0.6pp aggregate noise estimate was derived from cross-run aggregate measurements and didn't characterize per-matchup noise. Per-matchup noise was in fact ±2.5pp due to mostly-uncorrelated random.foo() advancement across games — and that uncorrelated noise mostly cancels at aggregate level via the central-limit pattern.

**Validating event:** Stage 1.7 fix (commit 30c992a) closed the global-random source and BOTH per-matchup AND aggregate noise collapsed to 0.00pp. This confirms the pre-fix per-matchup ±2.5pp was Stage 1.7 non-determinism (not natural variance, not patch effect), and confirms the aggregate noise WAS the cancellation residual of per-matchup noise. The framing was empirically validated.

**How to apply:**
1. When writing stop conditions on subset metrics, derive the noise floor at the SAME aggregation level as the metric. If the stop is per-matchup, measure per-matchup noise; if subset-aggregate, measure subset-aggregate noise.
2. When predicted signal lives at subset-aggregate (e.g., "the patch should affect a 3-of-14 subset"), the stop condition belongs at subset-aggregate, not per-matchup.
3. When per-matchup noise is large but aggregate is small, that's evidence of a cancellation pattern — the real noise budget is at the level where cancellation hasn't happened.
4. When a stop condition fires, distinguish "real signal exceeds noise floor at the stop's aggregation level" from "noise at the stop's aggregation level was mis-estimated." The latter is the v1.5 lesson; the former is the spec's intent.

**Anti-pattern:** "Aggregate noise is X, so per-matchup noise is also ~X." False whenever noise is mostly uncorrelated across matchups. Per-matchup noise can be an order of magnitude larger.

**Cost of ignoring:** Stop condition misfires consume investigation budget on non-issues. In execution-chain S3.7, three matchups apparently violated stop #2 — the investigation correctly identified non-determinism as the cause, but a less-careful executor could have backed out the patch on apparent-but-spurious .txt-shift evidence.

**Tooling implication:** None directly. This is a spec-authorship lesson, not a code or tooling change.

---

## Lessons by category

For quick lookup when authoring a spec, here's the lesson set indexed by spec section they apply to:

**For Pre-flight reads section:**

- load-bearing-wip-detection-applies-to-every-commit -&gt; verify imports of every committed file
- verify-identifiers-before-spec-execution -&gt; verify each CLI command's script, flags, AND package manager IDs exist before pasting into spec
- prefer-version-over-help-for-preflight-probes -&gt; use `--version` or `Get-Command`, never `--help`, for tool-existence checks

**For Validation gates / Predictions section:**

- keyword-density-asymmetry-shifts-direction -&gt; run keyword density check across all gauntlet matchups
- sim-vs-db-source-gates-engine-shifts -&gt; annotate each prediction (SIM) or (DB)
- spec-prediction-model-must-be-falsifiable -&gt; decompose aggregate predictions into per-matchup with field-share weighting

**For Implementation steps section:**

- per-iteration-vs-cross-iteration-state-changes -&gt; explicit per-item vs cross-item classification when refactoring 1-to-1 -&gt; 1-to-many
- windows-powershell-ascii-only-for-ps1-files -&gt; ASCII-only when generating PowerShell scripts; review LLM-generated .ps1 for non-ASCII chars before writing
- verify-identifiers-before-spec-execution -&gt; when writing shell commands or install commands into a spec, copy from verified sources, never guess from prose or naming conventions
- prefer-version-over-help-for-preflight-probes -&gt; non-interactive contexts (Claude Code, CI, scheduled tasks) must use non-blocking probes

**For Stop conditions section:**

- spec-prediction-model-must-be-falsifiable -&gt; stop-conditions tied to mechanical predictions, not just aggregate band membership

**For Tooling/scripts section (cross-cutting):**

- windows-powershell-ascii-only-for-ps1-files -&gt; .ps1 files must not contain UTF-8 multibyte chars
- teach-the-tool-not-the-data -&gt; when downstream tool flags an issue upstream already triaged, fix the tool's recognition logic via marker convention
- research-in-progress-is-a-third-option -&gt; stash deliberate-but-not-yet-wired research to module/\_research/ with revival README
- prefer-version-over-help-for-preflight-probes -&gt; default tool-existence probe is `--version` or `Get-Command`/`command -v`

**For Imperfection-handling decisions:**

- research-in-progress-is-a-third-option -&gt; "delete vs commit" is a false binary; \_research/ stash is the right answer for not-done-but-not-dead code
- teach-the-tool-not-the-data -&gt; false-positive flags often mean the tool is missing context the project already encoded; fix the tool
- load-path-dependent-setup-creates-silent-no-op-features -&gt; foundational fixes that surface mid-execution get their own first-class spec, not bundled into the spec that surfaced them

**For Validation pipeline / methodology trust:**

- validation-pipelines-need-their-own-validation -&gt; pipeline is part of the system under test, not an oracle; surface the assumption explicitly
- mechanical-noop-vs-large-shift-points-at-pipeline -&gt; calibrate magnitude expectations per diagnosis class; escalate pipeline above patch when divergence is implausible for prediction-model error
- caches-keyed-on-partial-state-are-time-bombs -&gt; enumerate parameter space, verify key includes every dimension that varies; document conventions explicitly with runtime check
- re-execution-specs-require-fresh-baseline-capture -&gt; documented prior numbers are sanity-check, not load-bearing anchor; capture fresh baseline at current HEAD
- load-path-dependent-setup-creates-silent-no-op-features -&gt; per-card setup must run against every load path; production-path tests not just synthetic

## Changelog

- 2026-04-27: Created. Initial 5 lessons compounded from Phase 3.5 Stages A and B Mid-execution Amendments. Referenced from harness/CLAUDE.md Rule 1 (read before spec authoring) and Rule 9 (compound new lessons here before SHIPPED).
- 2026-04-27 v1.1: Added 6th lesson `windows-powershell-ascii-only-for-ps1-files` after drift-detect.ps1 crash on first user-run. The em-dash that broke parsing was Claude-introduced when writing the script; this lesson is meta-cautionary for future LLM-generated PowerShell. Also added "Tooling/scripts" category to the lookup table.
- 2026-04-27 v1.2: Added 3 lessons compounded from the closing arc of 2026-04-27's session:
  - `verify-script-filenames-before-spec-execution` (Guide spec referenced fictional `goldfish_canonical.py`; actual entry was `scripts/sleeve_check.py`)
  - `teach-the-tool-not-the-data` (deck-count WARN was false positive against pre-triaged variants; fix taught lint about `audit:custom_variant` markers instead of modifying decks)
  - `research-in-progress-is-a-third-option` (orphan engine files were deliberate research; stashed to `engine/_research/` with revival README rather than delete-vs-commit binary) Added "Imperfection-handling decisions" category. Total lessons: 9.
- 2026-04-27 v1.3: Compounded 2 lessons from D1 Gource render spec execution (parent: [2026-04-28-project-visualization-mvp.md](http://2026-04-28-project-visualization-mvp.md), child: [2026-04-28-d1-gource-renders.md](http://2026-04-28-d1-gource-renders.md)):
  - Generalized `verify-script-filenames-before-spec-execution` to `verify-identifiers-before-spec-execution`. Original slug retained as alias. Added case 3: D1 amendment A1 -- spec said `winget install Gource.Gource`, real ID is `acaudwell.Gource`. Same root cause as the goldfish_canonical and parallel_launcher --opponent cases: pattern-match from naming convention into a hypothesized identifier without verifying against canonical source. Lesson now covers filenames, CLI flags, AND package manager IDs.
  - New lesson `prefer-version-over-help-for-preflight-probes` (D1 amendment A3): `gource --help` invoked an interactive pager in Claude Code's non-tty PowerShell, blocking the pre-flight check. Should have been `gource --version` or `Get-Command gource`. Generalizable to any non-interactive execution context.
- 2026-04-28 v1.4: Compounded 5 lessons from the cache-collision arc + Stage C re-execution (specs 2026-04-28-cache-collision-finding-doc-tightening, 2026-04-28-parallel-launcher-cache-collision-fix, 2026-04-28-past-validation-numbers-audit, 2026-04-28-phase-3.5-stage-c-protection-cluster):
  - `validation-pipelines-need-their-own-validation` (cache-collision was silently corrupting variant numbers across 3 stages before surfacing; the v1.3 falsifiable-prediction lessons assumed measurements were truthful)
  - `mechanical-noop-vs-large-shift-points-at-pipeline` (calibrate magnitude expectations per diagnosis class; -51pp on a no-protection matchup is implausible for prediction-model error, escalate pipeline)
  - `caches-keyed-on-partial-state-are-time-bombs` (matchup_jobs cache keyed on opp-name only; bug class generalizes to any shared path with implicit context)
  - `re-execution-specs-require-fresh-baseline-capture` (Stage C A4: documented prior numbers are stale-anchor risk if intervening engine changes exist; capture fresh baseline at current HEAD)
  - `load-path-dependent-setup-creates-silent-no-op-features` (Stage C A5: tag_keywords runs only on .txt load path; stub-loaded decks never get tagged; Stage A+B+C features all inert against 3 of 14 Modern field opps; foundational class of bug worth durable pattern recognition)
  Added two new categories to the lookup table: "Validation pipeline / methodology trust" + extended "Imperfection-handling decisions". Total lessons: 15.
  - A2 (Gource MSI doesn't add itself to PATH after winget install) intentionally NOT codified -- it's install-time-only knowledge specific to MSI packaging behavior, not generalizable across spec-authoring contexts. Documented in the parent spec's amendments and in [RESOLVED.md](http://RESOLVED.md) but not promoted to a methodology lesson. Total lessons: 10.
- 2026-04-28 v1.5: Compounded 2 lessons from execution-chain S3.7 (tagger-load-path-unification) + S3.8 (Stage 1.7 event_bus determinism). Both lessons were queued during S3.7 with explicit "hold compounding until validating event"; S3.8's clean collapse of per-matchup AND aggregate noise to 0.00pp was the validating event for both:
  - `parallel-entry-points-need-mirror-fix` (S3.8 D5 surfaced bo3 mirror needed of run_match_set fix; generalization of load-path-dependent-setup from setup functions to fixes themselves)
  - `stop-conditions-on-subsets-must-use-noise-floor-appropriate-aggregation` (S3.7 stop condition #2 misfired against per-matchup noise calibrated from aggregate noise estimate; S3.8 confirmed the per-matchup ±2.5pp WAS Stage 1.7 non-determinism as predicted, not natural variance)
  Total lessons: 17.

### oracle-text-verify-before-touching-card-mechanics

**Discovered:** 2026-04-29 night session via 3 misreads in a single Jeskai Blink audit (commits/edits that were oracle-incorrect on first try).

**One-line:** Before "fixing" any card-mechanic bug, pull the verbatim Scryfall oracle text from the local DB and quote it in the commit message. Do not work from memory of how the card "should" work.

**Background:** Tonight's JB session caught 12 real bugs but ALSO produced 3 misreads:

1. **Galvanic Discharge "1 base + energy" damage formula** — I claimed the existing code had an off-by-one bug because I thought damage was 1+energy_paid. Actual oracle: damage = energy paid (no base). The existing code was correct. User had to interrupt my edit to flag this.

2. **March of Otherworldly Light "2-pitch cap"** — I added a 2-pitch cap claiming oracle said "up to 2 white cards." Actual oracle: "any number of white cards." The cap was my invention. Reverted in commit 8805e31.

3. **Prismatic Ending "MV-scaling cost"** — I implemented `cost = tgt_mv + 1`. Actual oracle: CONVERGE — exiles MV ≤ number of distinct colors of mana spent. Cost scaling is by colors, not by mana amount. Pending fix (background agent assignment).

All three misreads followed the same pattern: I had a model in my head from prior MTG knowledge / general intuition, applied that model to code, did NOT verify against oracle. Two of them passed local "spot check" tests because the bug only materialized in specific board states.

The user explicitly called out the Galvanic mistake as a trust issue. Cumulative time cost: ~30-45 minutes across the three misread cycles plus reputational cost.

**How to apply:**

1. **Before any commit that changes card-mechanic logic**, run:
   ```python
   from data.deck import load_deck_from_file
   m, _ = load_deck_from_file('decks/<deck>.txt')
   c = next(c for c in m if c.name == "<CARD>")
   print(c.oracle_text)
   ```
2. **Quote the verbatim oracle text in the commit message body** — not paraphrased, not interpreted. Copy-paste from the DB output.
3. If your interpretation of a clause differs from the literal text, STOP and write a finding doc to `harness/knowledge/tech/<card>-oracle-clarification-<date>.md` before coding. Surface the ambiguity to the user.
4. For "alt cost" / "additional cost" / "replicate" / "converge" / "warp" / "dash" / similar mechanics — trace the cost-paying code path AND the resolution code path BEFORE assuming what model the engine uses.
5. Add to spec validation gates: "oracle-text quoted in commit message body" as a literal pre-commit check.

**Anti-pattern:** "I know what this card does, just code it." MTG cards have subtle clauses that often differ from naive expectations:
- Galvanic Discharge has no base damage (the {E}{E}{E} gain happens AFTER the damage, not before).
- March's pitch is "any number" not "up to 2."
- Prismatic Ending uses CONVERGE, not X-mana-value scaling.
- Phlage's sacrifice clause IS oracle-correct ("sacrifice unless escaped"), even though the engine doesn't model it.
- Solitude evoke specifically requires a WHITE card pitch, not any non-land.

**Cost of ignoring:**
- Wrong commits that need to be reverted (commit 8805e31 reverted 46e6160 reverting March cap).
- User trust erosion when same-session misreads compound.
- Validation gates pass against the wrong oracle, masking deeper issues.
- Future audits become harder because "the APL has been audited" is no longer trustworthy.

**Compounds with:** `verify-identifiers-before-spec-execution` (verify identifiers; this lesson extends to verifying card-mechanic interpretations).

- 2026-04-29 v1.6: Compounded 1 lesson from late-session JB oracle-fidelity audit:
  - `oracle-text-verify-before-touching-card-mechanics` (3 misreads in one session: Galvanic 1+energy, March 2-pitch cap, Prismatic MV-scaling. All from working-from-memory instead of verifying against local Scryfall DB. User explicitly called out as a trust issue.)
  Total lessons: 18.
