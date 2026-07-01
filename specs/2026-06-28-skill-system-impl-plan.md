---
title: "Skill System for the Harness -- Implementation Plan"
status: "SHIPPED"
created: "2026-06-28"
updated: "2026-07-01"
project: "harness"
estimated_time: "120-180 min"
related_findings:
  - "harness/specs/2026-05-01-skill-system-harness.md"
related_commits: []
supersedes: null
superseded_by: null
---

# Skill System for the Harness -- Implementation Plan

Concrete, executable plan to implement the PROPOSED spec
`harness/specs/2026-05-01-skill-system-harness.md`. This is the impl-plan
companion: the spec defines WHAT; this defines HOW, grounded in the live
harness tree as of 2026-06-28.

Scope guard: this plan ONLY touches files under `harness/`. Nothing under
`E:/vscode ai project/mtg-sim/` is read or modified here (a concurrent
workflow owns `mtg-sim/apl/`). The READ-ONLY constraint on mtg-sim is
satisfied by construction -- see "Byte-identical / no-regression" below.

ASCII-only throughout. For any Python invoked, set `PYTHONIOENCODING=utf-8`
and add the repo root to `sys.path`; this plan invokes no new Python (the
one validation gate is a shell/grep loop, deliberately -- see Gate 1).

---

## 1. Verification of the source spec against the live tree

Done 2026-06-28. Every file the spec lists for its four skills exists on
disk right now:

mtg-sim-quality:
- `harness/knowledge/tech/mtg-sim-quality-grades.md`  PRESENT
- `harness/knowledge/tech/spec-authoring-lessons.md`  PRESENT
- `harness/scripts/lint-mtg-sim.py`                   PRESENT
- `harness/scripts/drift-detect.ps1`                  PRESENT
- `harness/agents/scripts/apl_optimizer.py`           PRESENT
- `harness/scripts/verify_oracle.py`                  PRESENT

meta-analysis:
- `harness/knowledge/mtg/meta-analyzer.md`            PRESENT
- `harness/knowledge/tech/sim-framework.md`           PRESENT
- `harness/scripts/run-gauntlet.ps1`                  PRESENT
- `harness/agents/scripts/matchup_gauntlet.py`        PRESENT

apl-generation:
- `harness/knowledge/tech/apl-architecture.md`        PRESENT
- `harness/knowledge/tech/gemma-apl-failure-analysis-2026-04-29.md` PRESENT
- `harness/agents/scripts/auto_pipeline.py`           PRESENT
- `harness/agents/scripts/apl_tuner.py`               PRESENT

harness-ops:
- `harness/MEMORY.md`                                 PRESENT (60 KB -- see gotcha G6)
- `harness/scripts/session-snapshot.ps1`              PRESENT
- `harness/scripts/gemma-drift-pr.ps1`                PRESENT
- `harness/scripts/register-harness-tasks.ps1`        PRESENT
- `harness/SUBPROJECTS.md`                            PRESENT

No dangling references at authoring time. The skill files can be written
verbatim against these paths.

Schedule note: the spec was parked "post-PT, earliest 2026-05-05." That date
is 7+ weeks past. The specs index attributes the gap to the ~2026-05-16
cadence lapse (see `_index.md` SHIPPED reconciliations), not a live blocker.
PT data is ingested. There is no remaining dependency. RECOMMENDATION:
build-now.

---

## 2. Files to change

NEW (net-new, no conflict, no existing content touched):
1. `harness/skills/mtg-sim-quality/SKILL.md`
2. `harness/skills/meta-analysis/SKILL.md`
3. `harness/skills/apl-generation/SKILL.md`
4. `harness/skills/harness-ops/SKILL.md`
5. `harness/skills/_index.md`  (skill menu -- the ~150-token table CLAUDE.md points at)

MODIFIED (exactly one existing file):
6. `harness/CLAUDE.md`  (insert skill-menu gate into KNOWLEDGE LOADING section;
   bump version + changelog). FULL-CONTENT write_file only (gotcha G1).

PROCESS (required by harness conventions, NOT "content changes to other specs"
that the spec's Out-list excludes -- see "Scope reconciliation" below):
7. `harness/specs/_index.md`  (move this spec family PROPOSED -> SHIPPED on landing)
8. `harness/MEMORY.md`  (mark "Skill system for harness" complete; FULL-CONTENT write)

README.md per skill (mentioned in the spec's tree) is OPTIONAL and deferred --
SKILL.md is self-documenting. Do not author empty READMEs.

---

## 3. Approach (ordered steps)

### Step 0 -- Pre-flight reads (~5 min)
- `harness/specs/2026-05-01-skill-system-harness.md` (the spec)
- `harness/knowledge/tech/spec-authoring-lessons.md` (Rule 3 / Rule 9)
- `harness/CLAUDE.md` KNOWLEDGE LOADING section (exact anchor text, Step 3)

### Step 1 -- Create the directory + per-skill SKILL.md files (~70 min)

Create `harness/skills/<name>/SKILL.md` for the four skills. Each SKILL.md
uses this fixed shape (mirrors the spec's "Each SKILL.md contains" list):

```
# Skill: <name>

**One-line:** <what this capability does>

## Activate when
Trigger phrases: "<phrase>", "<phrase>", ...
(Lifted verbatim from the spec's Trigger line for each skill.)

## Load these files
- `<path>` -- <one-line why>
- `<path>` -- <one-line why>

## Behavior rules
- <skill-specific rule, e.g. "always run lint-mtg-sim.py before claiming
  registry/handler consistency">

## Related specs
- `harness/specs/<...>.md`
```

Exact trigger lines + file lists come straight from the spec (sec
"Initial skill definitions"):

- mtg-sim-quality -- triggers: lint, oracle, drift, APL quality, test, CI.
  Files: the 6 listed in sec 1. Behavior rules to add: "run
  `python harness/scripts/lint-mtg-sim.py` and `python
  harness/scripts/verify_oracle.py` before asserting handler/oracle
  fidelity"; "drift-detect.ps1 is the 8-check battery -- cite finding ids."
  Related specs: any 2026-04-2x drift-detect-Nth-check spec.
- meta-analysis -- triggers: meta, matchup, WR, field, gauntlet, Standard,
  Modern. Files: the 4 listed. Behavior rule: "prepend the DECK ANALYSIS
  PROTOCOL context block (Karn pattern) before matchup/SB analysis."
- apl-generation -- triggers: generate APL, auto-pipeline, new archetype,
  Gemma. Files: the 4 listed. Behavior rule: "read
  gemma-apl-failure-analysis before generating; Claude refines, Gemma
  authors bulk (per feedback_token_usage)."
- harness-ops -- triggers: session, snapshot, drift PR, nightly, schedule.
  Files: the 5 listed. Behavior rule for MEMORY.md: see gotcha G6 --
  "load only the relevant MEMORY section, never the whole 60 KB file."

ASCII-only. No em-dashes, arrows, or smart quotes in the SKILL.md bodies
(use "->" not the arrow glyph). The 2026-05-01 spec itself contains unicode
arrows; do NOT copy those glyphs.

### Step 2 -- Create `harness/skills/_index.md` (the skill menu) (~15 min)

This is the ~150-token menu CLAUDE.md will point readers at. A compact table:

```
# harness/skills -- Skill Menu
# Load only the skill matching the task. Each skill lists its own files.

| Skill | Load when (triggers) | Path |
|---|---|---|
| mtg-sim-quality | lint, oracle, drift, APL quality, test, CI | skills/mtg-sim-quality/SKILL.md |
| meta-analysis | meta, matchup, WR, field, gauntlet, Standard, Modern | skills/meta-analysis/SKILL.md |
| apl-generation | generate APL, auto-pipeline, new archetype, Gemma | skills/apl-generation/SKILL.md |
| harness-ops | session, snapshot, drift PR, nightly, schedule | skills/harness-ops/SKILL.md |

If no skill matches, fall back to the domain knowledge blocks in
harness/knowledge/ (existing behavior).
```

### Step 3 -- Wire the menu into CLAUDE.md (~20 min) -- HIGHEST-RISK STEP

This is the only existing file modified and the single highest-regression
action in the plan. The spec's instruction ("add to SESSION START PROTOCOL
after step 2") is STALE and must NOT be followed literally -- see gotcha G2.

Correct insertion point: the TOP of the `## KNOWLEDGE LOADING (MANDATORY)`
section. In the live file that section opens with:

  ANCHOR (verbatim):
  > ## KNOWLEDGE LOADING (MANDATORY)
  >
  > When working on a task, Claude MUST consult relevant knowledge blocks in
  > `harness/knowledge/` before answering. The directory is structured by domain:

Insert a new paragraph immediately AFTER the heading and BEFORE the "When
working on a task..." sentence:

  INSERT (ASCII):
  > **Step 0 -- check the skill menu first.** Before loading domain
  > knowledge blocks, read `harness/skills/_index.md`. If a skill matches the
  > task, load ONLY that skill's listed files (~2-5 files). Fall back to the
  > full domain blocks below ONLY if no skill matches. This is the
  > context-reduction path; the per-domain loading below is the fallback.

Then bump the header version line `**Version:** 1.4 (2026-04-28)` to
`**Version:** 1.6 (2026-06-28)` (note: header currently says 1.4 but the
changelog already has a 1.5 entry -- do NOT try to reconcile that here, just
bump forward to 1.6) and append a CHANGELOG entry:

  > - 2026-06-28: v1.6 -- Added skill-menu gate at top of KNOWLEDGE LOADING.
  >   New harness/skills/ tree (mtg-sim-quality, meta-analysis,
  >   apl-generation, harness-ops) + skills/_index.md menu. Skills are
  >   additive; knowledge/ remains the fallback. Impl per
  >   specs/2026-06-28-skill-system-impl-plan.md.

MANDATORY mechanism: edit CLAUDE.md by reading the entire current file and
writing it back in full via Write/write_file with the two changes applied.
Do NOT use Edit/edit_block -- the harness convention (CLAUDE.md CONVENTIONS
section) states Obsidian's auto-formatter has destroyed content during
incremental edits to CLAUDE.md / MEMORY.md.

### Step 4 -- Validation (~10 min) -- see Gate 1
### Step 5 -- Lifecycle + MEMORY update (~10 min) -- see Scope reconciliation

---

## 4. Validation gates (Rule 5)

The spec's only stated check ("loads <=5 files vs ~8+") is unmeasurable --
there is no instrument for "files the model loaded." Replace it with the one
genuinely falsifiable gate available: reference integrity.

Gate 1 (FALSIFIABLE -- reference integrity). Every path listed inside every
SKILL.md and skills/_index.md must resolve on disk. Run from `harness/`:

```
# Bash (Git Bash). Greps backtick-quoted paths out of the skill files and
# asserts each exists. Exit 1 on any dangle.
fail=0
for f in skills/*/SKILL.md skills/_index.md; do
  grep -oE '`[A-Za-z0-9_./-]+\.(md|py|ps1)`' "$f" \
    | tr -d '`' | sort -u | while read p; do
        # resolve relative to harness root
        [ -e "$p" ] || [ -e "harness/$p" ] || { echo "DANGLE $f -> $p"; exit 1; }
      done || fail=1
done
[ "$fail" = 0 ] && echo "GATE 1 PASS" || echo "GATE 1 FAIL"
```
Acceptance: prints "GATE 1 PASS", zero DANGLE lines. Stop trigger: any
DANGLE -> fix the path or the file before landing.

Gate 2 (smoke, manual). Open `harness/CLAUDE.md`, confirm: (a) the inserted
skill-menu block is present at the top of KNOWLEDGE LOADING, (b) the
"When working on a task..." sentence and ALL downstream protocol text are
byte-for-byte intact, (c) version bumped, (d) changelog entry appended.
Stop trigger: any pre-existing protocol text altered or dropped.

Gate 3 (lint clean). Run the existing drift spec-reference linter to confirm
this impl-plan spec itself introduces no dangling `python <x>.py`:
`python harness/scripts/lint-spec-references.py --json` -> exit 0. (This
plan cites only existing scripts; see gotcha G4.)

---

## 5. Gotchas (only the real code/tree reveals these)

G1 -- CLAUDE.md must be a FULL-CONTENT rewrite, never incremental.
The CLAUDE.md CONVENTIONS section explicitly forbids edit_block on
CLAUDE.md/MEMORY.md (Obsidian auto-formatter destroys content during
incremental edits; v1.1 was once truncated to a 1493-byte stub). Read whole,
apply two edits, write whole.

G2 -- The spec's CLAUDE.md insertion instruction is STALE.
The spec says "Add to SESSION START PROTOCOL (after step 2)". In the live
v1.5 file, SESSION START PROTOCOL has six numbered steps and step 2 is the
drift-PR inbox read -- unrelated to knowledge loading. Knowledge loading is a
SEPARATE section (`## KNOWLEDGE LOADING (MANDATORY)`), not a numbered step.
Inserting a "step 2b" would be semantically wrong. Put the gate at the top of
the KNOWLEDGE LOADING section instead (Step 3 above gives exact anchor text).

G3 -- Two CLAUDE.md files govern knowledge loading; only edit the harness one.
`E:/vscode ai project/CLAUDE.md` (project root) has its own "MANDATORY
KNOWLEDGE LOADING" that reads ALL files in a domain. The spec scopes changes
to `harness/CLAUDE.md` only. Leave the root CLAUDE.md untouched; the skill
menu is a harness-internal optimization.

G4 -- This impl-plan doc becomes lint fodder the moment it lands.
`lint-spec-references.py` scans `specs/*.md` with status PROPOSED/EXECUTING
(ACTIVE_STATUSES) and ERRORs on any `python <path>.py` that doesn't resolve
against mtg-sim or harness roots. Every script cited here exists, so it
passes. Do NOT introduce a new `python newhelper.py` reference in any
PROPOSED/EXECUTING spec/skill -- that is why Gate 1 is a grep loop, not a new
Python script. (The linter scans specs/ only; it does NOT scan skills/, so
skill-file path references are unguarded -- Gate 1 fills that hole manually.)

G5 -- skills/ references are unlinted going forward (maintenance debt).
Because lint-spec-references.py walks specs/ not skills/, a later rename or
deletion of a referenced knowledge block/script will silently rot a SKILL.md.
OPTIONAL follow-up (defer, separate spec): extend lint-spec-references.py
(or add a 9th drift-detect check) to also walk skills/*/SKILL.md. Out of
scope here to keep this additive and avoid touching the drift battery.

G6 -- harness-ops must NOT load all of MEMORY.md.
MEMORY.md is ~60 KB. Loading it whole defeats the skill system's entire
purpose (context reduction). The harness-ops SKILL.md must instruct loading
only the relevant MEMORY.md section (the spec already hedges this: "MEMORY.md
(summary)"). State this as a behavior rule in that SKILL.md.

G7 -- These are read-loaded doc-skills, NOT Claude Code native skills.
The spec deliberately rejects a programmatic SkillRegistry ("Claude Code
doesn't do programmatic tool loading"). `harness/skills/` is not a
`.claude/skills/` location, so Claude Code will not auto-discover or auto-run
these as runtime skills. That is intentional: the loading mechanism is "the
model reads skills/_index.md per the CLAUDE.md instruction." Do not convert
these to native-skill format (frontmatter name/description auto-invocation) --
that is a different design the spec did not choose. (Possible future
enhancement; out of scope.)

G8 -- ASCII discipline. The 2026-05-01 spec body contains unicode arrows and
em-dashes. The harness convention and this workflow require ASCII output. Use
"->" and "--" in the new SKILL.md files; do not copy glyphs from the spec.

---

## 6. Scope reconciliation (spec "Out" list vs harness conventions)

The spec's Out-list says "No changes to specs/, MEMORY.md, IMPERFECTIONS.md."
That refers to CONTENT changes to OTHER specs / knowledge -- i.e. the skill
work should not rewrite unrelated specs. It does NOT exempt this work from the
harness's own status lifecycle:

- Rule 6 + `specs/_index.md` "How to use" REQUIRE moving this spec family
  PROPOSED -> SHIPPED in `_index.md` on landing, with the commit hash.
- MEMORY.md has an explicit open item ("Skill system for harness (spec written
  2026-05-01, scheduled post-PT 2026-05-05)") at MEMORY.md:35/49 that must be
  marked done.

Treat _index.md status move + MEMORY.md completion note as REQUIRED PROCESS,
not as the prohibited "content changes." No IMPERFECTIONS.md change is needed
unless G5 is opened as a tracked follow-up (recommended).

---

## 7. Byte-identical / no-regression concerns

- Only ONE existing file is modified: `harness/CLAUDE.md`. All four SKILL.md
  files + skills/_index.md are net-new; creating them cannot regress anything.
- The CLAUDE.md edit must preserve ALL existing protocol text verbatim. Only
  two deltas: (a) one inserted block at the top of KNOWLEDGE LOADING, (b)
  version line + one changelog line. Gate 2 confirms no other text moved.
- No code behavior changes anywhere: drift-detect.ps1, lint-mtg-sim.py,
  verify_oracle.py, the gauntlet/auto-pipeline scripts are referenced but NOT
  edited. The 8-check drift battery, lints, and gauntlet runs behave
  identically -- spec validation item "no regressions in existing spec
  execution" holds by construction.
- mtg-sim is neither read nor written. The concurrent mtg-sim/apl/ workflow
  is fully disjoint from harness/skills/. READ-ONLY constraint satisfied.
- _index.md / MEMORY.md edits (Step 5) are additive status/log lines; MEMORY
  must use full-content write (same Obsidian rule as CLAUDE.md).

---

## 8. Effort + recommendation

Effort: 120-180 min (matches the spec's 2-3h estimate). Breakdown: 4 curated
SKILL.md files ~70 min, _index.md ~15 min, careful 20 KB CLAUDE.md
full-rewrite ~20 min, validation ~10 min, lifecycle/MEMORY ~10 min, pre-flight
~5 min. Do not undersell -- the value is in genuinely-curated trigger/behavior
content per skill, not boilerplate.

Recommendation: BUILD-NOW. Additive, low-regression (one file touched, fully
preserved), every dependency present, original schedule blocker long expired.
The only sharp edge is the CLAUDE.md full-rewrite discipline (G1/G2), which
this plan pins precisely.

OPTIONAL follow-ups (defer, do not block): per-skill README.md (G-tree);
extend linting to cover skills/ (G5); native-skill conversion (G7).

## Changelog
- 2026-06-28: Created (status PROPOSED). Impl plan for
  specs/2026-05-01-skill-system-harness.md.

## Reconciliation note (2026-07-01)
Status corrected PROPOSED->SHIPPED: harness/skills/ tree live (mtg-sim-quality, meta-analysis, apl-generation, harness-ops, _index.md); CLAUDE.md v1.6 skill-menu gate references this plan.
