---
title: "CLAUDE.md Conservative Trim + Skill-Menu Wiring Plan"
status: "PROPOSED"
created: "2026-06-29"
updated: "2026-06-29"
project: "harness"
estimated_time: "90-150 min (execution, when approved)"
related_findings:
  - "harness/specs/2026-06-28-skill-system-impl-plan.md"
  - "harness/specs/2026-05-01-skill-system-harness.md"
related_commits: []
supersedes: null
superseded_by: null
---

# CLAUDE.md Conservative Trim + Skill-Menu Wiring Plan

READ-ONLY design doc. This plan EDITS NOTHING. It specifies a conservative
trim of the three always-loaded CLAUDE.md files plus the skill-menu wiring
into `harness/CLAUDE.md` (from `specs/2026-06-28-skill-system-impl-plan.md`
Step 3, which is NOT yet applied -- the skills/ tree exists with real content
but the CLAUDE.md gate that points at it does not).

Lint note: this doc avoids the `python <path>.py` invocation pattern for any
UNBUILT script (ARL / telemetry scripts are named bare), so it stays clean
under `lint-spec-references.py` despite a PROPOSED status.

## Principle (the discriminator)

Matt Pocock, validated by our own skills build: a CLAUDE.md holds ONLY what is
BOTH (a) undiscoverable AND (b) globally relevant. Sharpened test for (b):

- GLOBAL = applies to ALL tasks -> KEEP in CLAUDE.md. Skill-gating it would
  HIDE it from non-matching tasks (SESSION START, CONVENTIONS, KNOWLEDGE
  LOADING, SPEC-FIRST methodology).
- TRIGGER-SCOPED = applies only to a specific domain/trigger -> MOVE to the
  matching skill or a docs/ file, leave a one-line pointer (DECK ANALYSIS,
  SCHEDULED TASKS, per-archetype APL status, ARL spec, telemetry spec).

When unsure: KEEP. No move DELETES content; every move relocates with a
pointer left behind.

## Risk taxonomy (applied to every move below)

- LOW-RISK -- clear win, safe to execute under a git-diff gate without
  per-cut sign-off.
- NEEDS-REVIEW -- show the user the exact cut before executing (behavioral
  content, load-bearing status, or a back-reference that must be repaired in
  lockstep).

## Edit-safety classification

- `E:/vscode ai project/CLAUDE.md` (root) -- EDIT-SAFE (not Obsidian-open).
- `E:/vscode ai project/mtg-sim/CLAUDE.md` -- EDIT-SAFE (not Obsidian-open).
- `E:/vscode ai project/harness/CLAUDE.md` -- OBSIDIAN-PROTECTED. FULL-CONTENT
  write_file ONLY, never edit_block. Same for `harness/MEMORY.md`.
- `harness/skills/*/SKILL.md` and `harness/skills/_index.md` -- EDIT-SAFE
  (NOT Obsidian-protected). Receiving moved content here is safe.

## CRITICAL coordination note (Obsidian + the gate model)

`harness/CLAUDE.md` is BOTH the wiring target AND a trim target AND
Obsidian-protected (every edit = a full-content rewrite; v1.1 was once
truncated to a 1493-byte stub by the auto-formatter). Two competing pressures:

- Fewer rewrites -> less Obsidian-corruption exposure (argues for one big write).
- Smaller required diff -> easier to verify the must-be-perfect wiring (argues
  for isolating it).

Resolution that satisfies BOTH the Obsidian constraint and the LOW-RISK /
NEEDS-REVIEW gate: do it in at most TWO coordinated full-content rewrites.

- Write A (no sign-off needed): skill-menu wiring + the two LOW-RISK harness
  trims (DIRECTORY STRUCTURE, SCHEDULED TASKS), one version bump, one changelog
  entry. You cannot fold the NEEDS-REVIEW harness trims into the required
  wiring -- that would force approval of everything at once.
- Write B (only after user sign-off): the NEEDS-REVIEW harness trims
  (DECK ANALYSIS PROTOCOL, DAILY RHYTHM prose), with its own changelog line.

The header currently reads `**Version:** 1.4` while the changelog already has a
1.5 entry -- do NOT reconcile that mismatch; just bump coherently forward to
1.6 (matching the 2026-06-28 impl plan).

---

## FILE 1 -- E:/vscode ai project/CLAUDE.md (root bootstrap)

1. ~55 lines. Obsidian-protected: NO (EDIT-SAFE).

2. KEEP list (all of it -- tiny + entirely global bootstrap):
   - MANDATORY STARTUP SEQUENCE, MANDATORY KNOWLEDGE LOADING, CONVENTIONS,
     THREE-AGENT PATTERN, WRITING BACK, PROJECT MAP. Every section is
     undiscoverable + global; no move is worth the risk on a 1.5 KB
     always-loaded bootstrap.

3. MOVE list: NONE recommended. CONSERVATIVE verdict KEEP-WHOLE.
   - Optional note (NOT a proposed move): the root "MANDATORY KNOWLEDGE
     LOADING" per-domain "read ALL files" list partially duplicates the
     harness KNOWLEDGE LOADING section and is the opposite of the new
     context-reduction skill gate. Leave it; revisit only after the skill
     system proves out. Touching the bootstrap for a trivial saving is not
     worth the contract risk. [NEEDS-REVIEW if ever pursued; default KEEP.]

4. Before/after: 55 -> 55 (KEEP-WHOLE). Trimming this file yields ~nothing.

---

## FILE 2 -- E:/vscode ai project/harness/CLAUDE.md (OBSIDIAN-PROTECTED)

1. ~337 lines. Obsidian-protected: YES (full-content write only).

KEEP (global -- applies to all tasks):
- SESSION START PROTOCOL (steps 1-6). Step 6 prose is verbose but load-bearing
  (the morning pivot contract).
- KNOWLEDGE LOADING (MANDATORY) -- and this is where the skill-menu gate is
  INSERTED (see "Skill-menu wiring" below).
- CONVENTIONS (~lines 219-233). The Obsidian full-content-write rule (line 231)
  MUST stay verbatim -- it is load-bearing safety.
- CHANGELOG (~lines 328-337). KEEP; it is the file's own history and the wiring
  appends to it.
- SPEC-FIRST EXECUTION PROTOCOL (9 rules, ~lines 127-217). KEEP -- it is the
  heart of the harness methodology and applies to ALL non-trivial work, so it
  fails the MOVE test on the "global" axis.
  - [NEEDS-REVIEW, optional, defer] A future pass MAY relocate only the
    expansion prose/examples inside each rule to
    `harness/docs/spec-first-protocol.md` while keeping all 9 rule headers +
    one crisp sentence each (~91 lines -> ~9-line summary). Do NOT do this
    without explicit approval; when unsure, KEEP.

MOVE list (trigger-scoped):

1. [NEEDS-REVIEW] DECK ANALYSIS PROTOCOL (~lines 100-125: the Karn context-block
   format + "Sources for this context").
   DEST: INTO `harness/skills/meta-analysis/SKILL.md` (the skill already
   references this block by name). POINTER in CLAUDE.md (one line):
   "Deck-analysis (Karn) context block: see harness/skills/meta-analysis/
   SKILL.md."
   REQUIRED LOCKSTEP FIX: meta-analysis/SKILL.md line 17 currently says the
   Karn pattern is "from harness/CLAUDE.md" -- a PROSE back-reference. Moving
   the section out leaves that prose pointer dangling, and the impl-plan Gate 1
   (reference integrity) matches only backtick FILE PATHS, not prose, so it
   will NOT catch this. The move MUST inline the block into the skill and
   rewrite line 17 to drop the back-reference. RISK if mishandled: matchup/SB
   analysis reverts to ungrounded/abstract when the skill is not loaded (loses
   the documented context-quality gain). Classified NEEDS-REVIEW because it is
   a behavioral protocol and should land only AFTER the skill-menu wiring is
   live so the meta-analysis skill reliably loads on matchup/WR/field tasks.

2. [LOW-RISK, borderline] SCHEDULED TASKS (~lines 291-324: task-scheduler table
   + daily-flow diagram).
   DEST: INTO `harness/skills/harness-ops/SKILL.md` (triggers already include
   "schedule"/"nightly"). POINTER: "Scheduled tasks + daily flow: see
   harness/skills/harness-ops/SKILL.md." RISK: low -- but this is the SOFTEST
   LOW-RISK item: the 04:30/04:50 timing RATIONALE is not discoverable from
   Task Scheduler, so the destination must preserve the "why." Defensible as
   LOW-RISK because the harness-ops skill covers the triggers and times are
   also recoverable from register-harness-tasks.ps1.

3. [LOW-RISK] DIRECTORY STRUCTURE tree (~lines 235-287).
   DEST: `harness/docs/directory-structure.md`. POINTER: "Full harness tree:
   see harness/docs/directory-structure.md (or list the directory)." RISK:
   very low -- the tree is reconstructable by listing the filesystem; it is the
   definition of "discoverable." Cleanest harness win.

4. [NEEDS-REVIEW] DAILY RHYTHM explanatory section (~lines 41-77, the 9-hour
   cadence rationale).
   DEST: `harness/docs/daily-rhythm.md`. Keep a 2-3 line summary + pointer
   (the actionable bits -- author tomorrow's chain end-of-day, run SESSION
   START steps 1-6 then step 6 -- already live in SESSION START PROTOCOL +
   CONVENTIONS, so only rationale moves). POINTER: "Daily 9-hour cadence
   rationale: see harness/docs/daily-rhythm.md." RISK: low mechanically, but it
   is user-authored behavioral framing -> NEEDS-REVIEW (show the cut first).

Skill-menu wiring (REQUIRED, from 2026-06-28 impl plan Step 3 -- NOT yet
applied). Insert at the TOP of the KNOWLEDGE LOADING section.
ANCHOR (verbatim -- the section currently opens):

  ## KNOWLEDGE LOADING (MANDATORY)

  When working on a task, Claude MUST consult relevant knowledge blocks in
  `harness/knowledge/` before answering. The directory is structured by domain:

INSERT immediately AFTER the heading and BEFORE the "When working on a task..."
sentence (ASCII, verbatim from impl-plan section 3):

  **Step 0 -- check the skill menu first.** Before loading domain knowledge
  blocks, read `harness/skills/_index.md`. If a skill matches the task, load
  ONLY that skill's listed files (~2-5 files). Fall back to the full domain
  blocks below ONLY if no skill matches. This is the context-reduction path;
  the per-domain loading below is the fallback.

VERSION BUMP: change `**Version:** 1.4 (2026-04-28)` ->
`**Version:** 1.6 (2026-06-28)`. (Do NOT reconcile the v1.5-changelog /
v1.4-header mismatch; just bump forward to 1.6, per impl-plan.)

CHANGELOG line to append (verbatim from impl-plan section 3 for Write A; if a
later landing date is used, update the date explicitly, do not change silently):

  - 2026-06-28: v1.6 -- Added skill-menu gate at top of KNOWLEDGE LOADING.
    New harness/skills/ tree (mtg-sim-quality, meta-analysis,
    apl-generation, harness-ops) + skills/_index.md menu. Skills are
    additive; knowledge/ remains the fallback. Impl per
    specs/2026-06-28-skill-system-impl-plan.md.

  (Write A may extend this same entry to note the two LOW-RISK trims
  -- DIRECTORY STRUCTURE -> docs/directory-structure.md, SCHEDULED TASKS ->
  harness-ops SKILL.md -- since they land in the same rewrite.)

MECHANISM: read the entire current harness/CLAUDE.md, apply the deltas, write
back in full via write_file. NEVER edit_block (impl-plan G1/G2). Validate with
Gate 2 (downstream protocol text byte-intact) + Gate 1 (no dangling skill
paths).

Before/after (harness):
- After Write A (wiring + 2 LOW-RISK trims, +~12 wiring lines): ~337 - 53 - 34 +
  12 = ~262 lines.
- After Write B (the 2 NEEDS-REVIEW trims as well): ~262 - 26 - 37 = ~199 lines.

---

## FILE 3 -- E:/vscode ai project/mtg-sim/CLAUDE.md (the big win)

1. ~537 lines. Obsidian-protected: NO (EDIT-SAFE; ordinary Edit/Write fine).
   Largest always-loaded context cost; mostly per-archetype status + two
   embedded unbuilt-feature SPECS -> neither undiscoverable-and-global.

KEEP (global orientation for this repo, ~lines 1-40 + the next-card rule):
- "What you're looking at", "Navigation priorities", "Standalone repo",
  "Conventions you must follow" (ASCII-only terminal, APL module shape,
  test/script sys.path conventions). Genuine repo bootstrap.
- The "Workflow rule for next-card picks" (~lines 194-208: grep
  card_handlers_verified.py before proposing handler work; deck-file audit
  markers). Undiscoverable behavior rule. KEEP in CLAUDE.md (could relocate to
  a next-card skill in a later pass; KEEP for now).

DUPLICATION NOTE (handle at relocation time, NOT a standalone deletion):
- The Coverage-audit "Artifacts / Re-run: full_audit.py" block appears TWICE
  verbatim (~lines 178-183 and ~185-192). Per the no-delete rule this plan does
  NOT propose deleting it in place; when the coverage section is relocated
  (move 2 below) the destination doc keeps a SINGLE copy. Flag for the user.

MOVE list (status + unbuilt-spec content):

1. [NEEDS-REVIEW] Current APL status (~lines 42-166: Amulet Titan, Izzet
   Prowess, Izzet Looting x3, framework patches 2026-05-10, Standard 38/38
   match APLs, known model limitations, experimental).
   DEST: `mtg-sim/docs/apl-status.md`. POINTER: "Per-archetype APL status +
   known model limitations: see docs/apl-status.md."
   REQUIRED LOCKSTEP FIX: Navigation priority #3 (~line 22, "This file for
   repo-specific status...") currently PROMISES this content. The move must
   redirect priority #3 to docs/apl-status.md, or that line dangles (same class
   as the Karn prose back-reference). RISK: this is load-bearing status that
   feeds deck analysis (WRs, kill turns, framework-patch caveats, model
   limitations). It is read-when-relevant material and much is recoverable from
   apl/ + decks/, but the curated WR/limitation notes are not -> NEEDS-REVIEW.

2. [NEEDS-REVIEW] Coverage audit (~lines 168-209: 4218/4218, per-format gaps,
   audit artifacts/re-run -- collapsed to a single copy per DUPLICATION NOTE).
   DEST: fold into `mtg-sim/docs/apl-status.md` (or docs/coverage-audit.md);
   pointer folded into the APL-status pointer. The next-card workflow rule and
   deck-file-marker convention STAY in CLAUDE.md (see KEEP). RISK: low on the
   numbers alone (a dated snapshot regenerated by full_audit.py), but it is
   adjacent to APL status and shares the navigation back-reference concern ->
   NEEDS-REVIEW so the cut is shown with move 1.

3. [LOW-RISK] Autonomous Research Loop (ARL) (~lines 213-363: state-file schema,
   loop iteration, candidate generation, human interface, blockers, and the
   "entry-point scripts to BUILD" list -- arl_loop, arl_status, arl_steer,
   arl_generate_deck, arl_generate_apl). This is an UNBUILT-feature spec, not
   bootstrap. DEST: `mtg-sim/docs/arl-spec.md` (or promote to harness/specs/).
   POINTER: "ARL design + scripts to build: see docs/arl-spec.md." RISK: very
   low -- the feature is not yet built; nothing executes against it today.

4. [LOW-RISK] Sequencing Telemetry + Heuristic Distillation (~lines 366-537:
   JSONL event schemas, sample thresholds, distillation pass, APL candidates,
   playbook pipeline, the unbuilt arl_distill distiller). Same nature -- an
   unbuilt-feature spec. DEST: `mtg-sim/docs/telemetry-spec.md` (or fold into
   docs/arl-spec.md as a companion). POINTER: "Sequencing telemetry +
   distillation design: see docs/telemetry-spec.md." RISK: very low (feature
   not yet built).

MECHANISM: EDIT-SAFE -- ordinary Edit/Write; no Obsidian constraint. Create the
docs/ files first (move content verbatim, collapsing the coverage duplicate),
then trim CLAUDE.md, insert the pointers, and repair navigation priority #3.

Before/after (mtg-sim):
- After LOW-RISK only (ARL + telemetry moved, ~4 pointer lines added):
  537 - 151 - 172 + 4 = ~218 lines.
- After LOW-RISK + the 2 NEEDS-REVIEW moves: ~218 - 125 - 42 + 4 = ~55 lines
  (orientation + conventions + next-card rule + pointers). The single biggest
  always-loaded context reduction available.

---

## Skill-file edits required by the moves (EDIT-SAFE)

- `harness/skills/meta-analysis/SKILL.md`: inline the DECK ANALYSIS / Karn
  context-block format + sources; rewrite line 17 to drop the
  "from harness/CLAUDE.md" prose back-reference so it does not dangle.
- `harness/skills/harness-ops/SKILL.md`: inline the SCHEDULED TASKS table +
  daily-flow diagram.

## Validation gates

- Gate 1 (reference integrity): every backtick path in skills/*/SKILL.md,
  skills/_index.md, and every new pointer resolves on disk (impl-plan grep
  loop). Zero DANGLE lines. ALSO manually confirm the two PROSE back-references
  are repaired (Karn in meta-analysis SKILL line 17; mtg-sim navigation #3) --
  Gate 1's grep does NOT catch prose.
- Gate 2 (CLAUDE.md no-regression): after each harness/CLAUDE.md full-write,
  confirm the "When working on a task..." sentence and ALL downstream protocol
  text are byte-intact; only the intended deltas changed.
- Gate 3 (lint clean): `python harness/scripts/lint-spec-references.py --json`
  exits 0 -- this plan cites only existing scripts (unbuilt ARL/telemetry
  scripts are named bare, never as `python <x>.py`).

## Move classification summary

LOW-RISK (4) -- safe under a git-diff gate:
- harness: DIRECTORY STRUCTURE -> harness/docs/directory-structure.md
- harness: SCHEDULED TASKS -> harness-ops SKILL.md (borderline)
- mtg-sim: ARL section -> mtg-sim/docs/arl-spec.md
- mtg-sim: Sequencing Telemetry -> mtg-sim/docs/telemetry-spec.md

NEEDS-REVIEW (4 firm) -- show the cut before executing:
- harness: DECK ANALYSIS PROTOCOL -> meta-analysis SKILL.md (+ repair line-17
  prose back-reference)
- harness: DAILY RHYTHM prose -> harness/docs/daily-rhythm.md
- mtg-sim: Current APL status -> mtg-sim/docs/apl-status.md (+ repair
  navigation priority #3)
- mtg-sim: Coverage audit -> mtg-sim/docs/apl-status.md (collapse the verbatim
  duplicate at relocation; the next-card rule STAYS)

DEFERRED / OPTIONAL (1, NEEDS-REVIEW if ever pursued):
- harness: SPEC-FIRST rule expansion prose -> docs/spec-first-protocol.md
  (keep 9 rule headers + one sentence each). Default KEEP.

## Per-file before/after headline

| File | Obsidian | Before | After LOW-RISK only | After all moves |
|---|---|---|---|---|
| root CLAUDE.md | no | ~55 | ~55 (no moves) | ~55 |
| harness/CLAUDE.md | YES | ~337 | ~262 (incl. +12 wiring) | ~199 |
| mtg-sim/CLAUDE.md | no | ~537 | ~218 | ~55 |

## What this plan does NOT touch

Root CLAUDE.md content (KEEP-WHOLE), SPEC-FIRST 9-rule bodies (KEEP), any
mtg-sim CODE, the drift battery / lints / gauntlet scripts. mtg-sim is
otherwise read-only; only its CLAUDE.md + new docs/ files change, and only at
execution time, when approved.

## Changelog
- 2026-06-29: Created (status PROPOSED). Conservative trim + skill-wiring plan
  for the three CLAUDE.md files. Design only; edits nothing. Adds explicit
  LOW-RISK / NEEDS-REVIEW classification + counts, the two prose back-reference
  lockstep fixes (Karn / navigation #3), and a two-write Obsidian sequencing
  that keeps the required wiring un-blocked by NEEDS-REVIEW cuts.
