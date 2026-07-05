---
title: "/bob — hybrid-conductor autonomous orchestrator skill"
status: "SHIPPED-PARTIAL"
created: "2026-07-04"
updated: "2026-07-04"
project: "harness"
estimated_time: "1-2 sessions (build); prove-first the timeout-gate slice ~60-90 min"
related_findings:
  - "harness/knowledge/tech/handoff-convention-2026-06-30.md"
  - "harness/knowledge/tech/council-2026-07-04-loop-engineering-handoff.md"
related_commits: []
supersedes: null
superseded_by: null
---

# /bob — hybrid-conductor autonomous orchestrator skill

## Goal

Give the workspace one named entry point — `/bob <path-to-doc>` — that takes any
pre-existing tasking document (a `harness/specs/` spec, a `harness/handoffs/`
primer, or a loose `.md` being worked in another terminal) and drives it to
completion **or to an honest, documented stop**, fanning out 4–20 agents for the
heavy work and reporting to the user like a foreman. `/bob` does not invent new
capability; it **composes** existing primitives (`Workflow`, the `council` skill,
the `handoff` skill, the `advisor` tool, `brainstorming`) behind a fixed
reliability spine so that the output is either **proven good (evidence + adversarial
refute-council) or stopped-with-a-handoff explaining why** — never shipped on "looks
done." It subsumes the user's imagined `/goal` feature: the doc pointed at *is* the
goal, and INTAKE turns it into a checkable definition-of-done.

The honest framing (load-bearing, do not soften in the SKILL.md): `/bob` converts
the question "will the result be up to standard?" into "it is *proven* up to standard,
or it *stopped and told you why*." It is a conductor, not a correctness guarantee.

## Scope

### In scope
- A global, user-invoked skill at `~/.claude/skills/bob/SKILL.md`
  (`disable-model-invocation: true`, like `/handoff` — Claude never auto-fires it).
- A Zuxas project-override note at `harness/knowledge/tech/bob-convention-2026-07-04.md`
  (same pattern as `handoff-convention-2026-06-30.md`) carrying harness-only paths,
  hot-zone list, and PII-redaction rules so the global skill stays generic.
- The **hybrid-conductor architecture (Approach C):** an interactive conductor in the
  main loop + `Workflow`-tool fan-out for the heavy execute/verify phases, run in
  bounded waves.
- The **fixed spine:** INTAKE → PLAN+CLAIM → FAN-OUT → VERIFY → GATE → COMMIT → CLOSE.
- The **live run directory** (`bob-runs/<runid>/`) for content-level monitoring +
  audit trail + handoff source.
- The **watch+intervene** control channel (`control.md`) polled by agents at
  checkpoints and by the conductor at wave boundaries.
- The **reliability core:** evidence-artifact floor → adaptive verifier → blind
  refute-council → human gate with timeout-default-to-council + reversible decision log.
- **Tiered-by-blast-radius** decision rule (non-hot-zone unmet gate → council
  authorizes + proceeds; hot zone → stop + handoff for sign-off).
- Concurrency safety: read-only intake → plan → user confirm → claim/lockfile +
  dedicated branch in the affected git subproject; refuse if a live claim exists.

### Explicitly out of scope
- A fully hands-off "commits to main and pushes without me" mode — VIOLATES the
  harness hot-zone protocol by design. Push/merge-to-main is always a sign-off gate.
- Auto-writing `harness/knowledge/` (Tier K). `/bob` stages knowledge into
  `harness/inbox/promoted/` per the existing promotion gate; it never blesses Tier K.
- Cross-machine coordination with the *other* terminal beyond the claim/lockfile
  convention (we detect and refuse collisions; we do not negotiate with the other
  session). Follow-up if richer coordination is ever needed.
- A general-purpose non-harness release. v1 is tuned to this workspace's conventions;
  generalization is a later concern.

## Pre-flight reads (if any)

Executor must read BEFORE building:
- `harness/knowledge/tech/handoff-convention-2026-06-30.md` — the `/handoff` project
  overrides `/bob` reuses verbatim on stop (scratchpad location, PII redaction,
  suggested-skills block, point-at-artifacts).
- `harness/knowledge/tech/spec-authoring-lessons.md` — per Rule 3/9; INTAKE authors a
  working spec, so prior lessons must inform it.
- `~/.claude/skills/handoff/SKILL.md` — the stock handoff skill `/bob` calls on stop.
- The `council` skill + `writing-skills` skill (build `/bob` with the latter).
- `harness/CLAUDE.md` VERIFICATION & HOT-ZONE PROTOCOL + RESEARCH-BRAIN TIER promotion
  gate — the two sources of the hot-zone list and the Tier-K staging rule.

## External dependencies & global-safety (added 2026-07-04 after dependency check)

`/bob` installs globally (`~/.claude/skills/bob/`) but two skills it leans on are
**project-scoped, not global** — verified 2026-07-04:
- `council` lives at `E:/vscode ai project/.claude/skills/council/` (project only).
- `delegate` is project only. `handoff` IS global; `advisor` is a tool (always present).

Therefore `/bob` must **degrade gracefully**, never hard-fail, when a skill is absent:
- **Refute-council / decision-council:** `council` is just a protocol (3–4 blind
  parallel subagents + optional Codex cross-vendor seat + chairman synthesis). `/bob`
  **inlines that same pattern** via the always-global `Agent`/`Workflow` tools. When the
  `council` skill IS present, prefer invoking it (Codex seat + house verdict format);
  when absent, run the inlined blind-refute panel. Either way, fall back to `advisor()`
  if even subagent spawning is unavailable. Net: the council-gate works in ANY project.
- **Handoff on stop:** `handoff` is global — safe to call anywhere. Project override
  (`bob-convention-*.md`) applies only when running inside this workspace.
- **Local delegation:** if `delegate` MCP is absent, skip it (it's an optimization, not
  a correctness dependency).

This is what makes "works globally" true rather than aspirational: outside the harness,
`/bob` runs with generic hot zones + the inlined council pattern; inside it, the override
note lights up the workspace-specific behavior.

## Steps

### Step 1 — Author the SKILL.md skeleton (~20 min)

Create `~/.claude/skills/bob/SKILL.md` via the `writing-skills` skill. Frontmatter:
`name: bob`, `description: <trigger on "/bob", "use bob to…">`,
`disable-model-invocation: true`. Body is the CONDUCTOR CHECKLIST — the fixed spine
below, written as an ordered procedure Claude follows in the main loop, with explicit
"delegate this phase to Workflow" markers on FAN-OUT and VERIFY.

### Step 2 — INTAKE (read-only) (~ built into SKILL.md)

- Read the pointed-at doc + relevant repo context. **No writes.**
- Classify: (a) spec-with-gates → use its gates; (b) handoff/primer → tighten into a
  working definition-of-done; (c) loose `.md` → derive gates.
- If deriving gates needs a real decision, or scope is ambiguous → invoke
  `brainstorming` (and `council` for contested calls) BEFORE proceeding.
- Emit a **PLAN**: goal restatement, derived gates, the independent sub-units, the
  agent count (auto-scaled to sub-units, capped 20), the affected git subproject, the
  hot-zone touchpoints flagged up front.

### Step 3 — PLAN+CLAIM gate (~ built into SKILL.md)

- Present the PLAN to the user. **Make no writes until the user confirms.**
- Check for a live claim/lockfile on the doc. If one exists → **refuse**, tell the user
  who/when, stop.
- On confirm: write `bob-runs/<runid>/` (STATUS.md, control.md, agents/, evidence/,
  decisions.md), drop the claim/lockfile next to the doc, and cut a dedicated branch
  in the affected git subproject (never the non-git workspace root).

### Step 4 — FAN-OUT + VERIFY (delegate to Workflow, in waves) (~ built into SKILL.md)

- Conductor writes a `Workflow` script for a wave of sub-units. Each agent's prompt
  MUST include: (i) append a one-line worklog to `agents/agent-NN.md` before each
  read/write; (ii) poll `control.md` at each checkpoint and honor pause/kill/redirect;
  (iii) produce a concrete evidence artifact into `evidence/` per gate.
- VERIFY per sub-unit: evidence-floor (no artifact → fail) → adaptive verifier by task
  type (code → `verify` skill / tests / lint / run; sim → gates/gauntlet numbers; docs
  → review) → **blind refute-council** (2–3 agents try to break "gate met"; majority
  refute = fail).
- Wave boundary: conductor re-reads `control.md` + `STATUS.md`, honors interventions,
  updates STATUS.md, launches next wave.

### Step 5 — GATE (human, with timeout-default) (~ built into SKILL.md)

- Present artifacts + refute-council verdict to the user (`AskUserQuestion`).
- **Timeout path:** if the user does not respond within the allotted window (conductor
  uses `ScheduleWakeup`/poll to bound the wait), default to the refute-council verdict,
  proceed, and append a **reversible decision** to `decisions.md`: what was decided,
  why, that it was a timeout-default, and how to reverse it.
- Apply the **tiered rule:** non-hot-zone unmet gate → `council` authorizes + proceeds;
  hot zone (engine / DB on `E:\mtg-data` / `knowledge/` Tier-K / push / merge-to-main) →
  STOP + handoff for sign-off.

### Step 6 — COMMIT (~ built into SKILL.md)

- Commit to the claimed dedicated branch (autonomous — reversible, low blast radius:
  this is the user's "commit progress").
- Push / merge-to-main → **sign-off gate**, never autonomous.

### Step 7 — CLOSE (~ built into SKILL.md)

- Update `MEMORY.md` session log + relevant docs per WRITING BACK. Knowledge → stage to
  `inbox/promoted/`, never Tier K directly.
- If the run stopped early: write a `/handoff` primer (stock skill + project override)
  from the run dir; if it's a real session-sized unit, promote it into
  `harness/handoffs/` + its `_index.md`.
- Release the claim/lockfile.

### Step 8 — "Stuck" handler (~ built into SKILL.md)

Repeated gate failure, council deadlock, or agent death → conductor calls `advisor()`
and/or the cross-vendor Codex council seat, records the consult in `decisions.md`, then
replans (non-hot-zone) or stops+handoff (hot-zone / unresolved). Nothing unproven ships.

## Validation gates

Every gate must pass before `/bob` is considered SHIPPED. These test the skill itself.

| Gate | Acceptance | Stop trigger |
|---|---|---|
| G1 Dry-run intake | Point at an existing spec; `/bob` produces a PLAN + derived gates and makes ZERO writes (git status clean, no run dir) until confirm | any write before confirm |
| G2 Claim refusal | With a live claim/lockfile present, `/bob` refuses and names who/when | it proceeds anyway |
| G3 Branch isolation | On confirm, commits land ONLY on the dedicated branch, never the subproject's main | any commit to main |
| G4 Evidence floor | A sub-unit with no evidence artifact CANNOT pass its gate → stop+handoff | a gate passes with empty `evidence/` |
| G5 Timeout-default | Simulated no-response → run proceeds on refute-council verdict AND `decisions.md` logs {what, why, timeout-default, reversal} | proceeds with no decision-log entry |
| G6 Hot-zone stop | A planted engine/`knowledge/`/push touchpoint forces STOP + a written handoff, not an autonomous edit | it edits a hot zone without sign-off |
| G7 Watch+intervene | A `kill agent-NN` / `pause` written to `control.md` is honored at the next checkpoint | the command is ignored |
| G8 Handoff on stop | A forced stop yields a `/handoff` doc that follows the project override (scratchpad, PII-redacted, suggested-skills block) | no handoff, or PII leaked |

## Stop conditions

- INTAKE finds the doc's scope needs a decision the skill can't derive: STOP, invoke
  `brainstorming`/`council`, surface to user.
- A live claim exists on the doc (G2): STOP, refuse.
- Any hot-zone touchpoint reached (G6): STOP, write handoff, request sign-off.
- Refute-council deadlocks or `advisor` can't resolve (Step 8): STOP, handoff.
- The `Workflow` fan-out dies mid-wave (cf. the 2026-07-04 monolithic-doc-writer stall):
  recover from journal per wave, do NOT silently continue; surface partial + decide.

## Commit message template

```
feat(harness): add /bob hybrid-conductor orchestrator skill

<what shipped: SKILL.md + bob-convention note + run-dir scaffold; the fixed
spine, tiered decision rule, watch+intervene control channel, timeout-default
verify gate with reversible decision log>

Validation results:
  G1 dry-run intake:   PASS (zero writes pre-confirm)
  G2 claim refusal:    PASS
  G3 branch isolation: PASS (commits on branch only)
  G4 evidence floor:   PASS
  G5 timeout-default:  PASS (decision logged + reversible)
  G6 hot-zone stop:    PASS (handoff written)
  G7 watch+intervene:  PASS
  G8 handoff on stop:  PASS (PII-redacted)

Convention doc: harness/knowledge/tech/bob-convention-2026-07-04.md
Related specs: harness/specs/2026-07-04-bob-orchestrator-skill.md
```

## Annotated imperfections (if any)

```
## bob-timeout-gate-mechanism-fiddly

**What's not perfect:** The human-gate-with-timeout-default depends on a
ScheduleWakeup/poll wait bound in the conductor. A running Workflow can't block on a
keystroke, so the wait lives in the main loop between waves — the fiddliest piece.
**Why not fixed in this spec:** It's the highest-risk mechanism; prove it in isolation
(G5) before wiring the full spine.
**Concrete fix:** Build + pass G5 as a standalone 60–90 min slice first; only then wire
Steps 4–7.
**Estimated effort:** 60–90 min.
```

```
## bob-intervention-granularity

**What's not perfect:** watch+intervene is honored at checkpoints / wave boundaries,
not truly instantaneously mid-token. A long-running single agent may not see a `kill`
until its next checkpoint.
**Why not fixed in this spec:** True preemption isn't available through the tool layer;
checkpoint polling is the best faithful mechanism.
**Concrete fix:** Instruct agents to checkpoint frequently on long tasks; document the
latency in the SKILL.md so the user's expectation is calibrated.
**Estimated effort:** doc-only.
```

## Mid-execution Amendment 1 (2026-07-04) — dogfood build + refute-council findings

Built `/bob` by acting as `/bob`, ultracode as the fan-out engine. Conductor pinned the
deterministic core by hand (`bob_run.py`, 7/7 pytest green: run-dir, claim+staleness,
control parse, decision log, **+ `assert_branch` git guard added in this amendment**).
Ultracode workflow `wwmp4vkiy` (7 agents, 0 errors): 4 build agents wrote
`SKILL.md` + `references/spine.md` + `references/timeout-gate.md` + staged the convention
note; 3 blind refuters (ANALYST/CONTRARIAN/EMPIRICIST) verified against G1–G8.

**Council verdict: NOT shippable as first-built — 6/8 gates enforced, real holes found.**
Chairman synthesis + fixes applied (all in non-hot-zone skill files):
- **G6 (CONFIRMED, critical):** `MEMORY.md` + `harness/CLAUDE.md` were missing from the
  hot-zone list and CLOSE wrote `MEMORY.md` autonomously. FIXED — added both to the
  hot-zone list (Obsidian full-content-write-only), CLOSE now proposes+sign-off+full-content.
- **G4 (CONFIRMED):** evidence floor was existence-only → hollow/fabricated artifact + AFK
  timeout could ship unproven work. FIXED — floor now requires an INDEPENDENT verifier
  (executor ≠ verifier) re-running the check; refute-council attacks evidence realness;
  timeout auto-proceed requires a POSITIVE evidence-backed PASS, not mere non-refutation.
- **G3 (CONFIRMED):** branch isolation was prose-only. FIXED — deterministic
  `bob_run.py assert-branch` guard called before every commit (+ test).
- **G8 (all seats):** SKILL.md hard-referenced the not-yet-existing convention note.
  FIXED — read is now conditional on the file existing; generic hot zones back it up.
- **G5 (partially overruled):** seats said `ScheduleWakeup` doesn't exist — it does, in the
  CONDUCTOR surface (subagents lack it, hence their error). Kept the finding's valid half:
  added a Monitor/re-prompt fallback + prove-first note. Decision-log half verified real.

## Annotated imperfections (updated by Amendment 1)

```
## bob-evidence-floor-not-mechanized
**What's not perfect:** The evidence floor is now substance-aware in prose (independent
verifier + positive-confirm) but has no deterministic helper verb — it relies on the
conductor enforcing executor≠verifier and the refute-council catching hollow artifacts.
**Why not fixed here:** Mechanizing "is this artifact real and does it map to the gate"
is a genuine design unit, not a one-line edit.
**Concrete fix:** add a `bob_run.py verify-evidence` verb that at minimum asserts the
artifact is non-empty AND was written by a different agent id than the executor (thread
agent ids through the run dir); escalate to re-executing the recorded check command.
**Estimated effort:** 60–90 min.
```

```
## bob-timeout-gate-mechanism-fiddly
**What's not perfect:** The timeout WAIT (ScheduleWakeup, conductor-only) is documented
with a fallback but not yet proven end-to-end (no live no-response run executed).
**Why not fixed here:** highest-risk mechanism; prove in isolation before trusting.
**Concrete fix:** run the G5 behavioral slice with a real bounded wait; confirm
auto-proceed fires only on a positive PASS and logs the reversible decision.
**Estimated effort:** 60–90 min.
```

## Mid-execution Amendment 2 (2026-07-04) — self-acceptance run (`/bob` graduates `/bob`)

Ran `/bob`'s own Task-11 acceptance as its collision-free "real spin" (chosen because the
blueprint path was correctly BLOCKED — see below). All 8 gates exercised on live artifacts:

| Gate | Proof | Verdict |
|---|---|---|
| G1 read-only intake | blueprint real-spin made zero writes / cut no branch (git status) | PASS (live) |
| G2 claim refusal | `claim`→OK, second `claim`→REFUSED | PASS (live) |
| G3 branch isolation | `assert-branch` on `bob/<runid>`→OK exit0; stray `master`→FAIL exit1 | PASS (live) |
| G4 evidence floor | 2-agent fan-out `wz714ufkq`: executor wrote code + could NOT self-certify; DIFFERENT agent (agent-02) independently ran pytest → real verbatim artifact `evidence/g4-verify.txt` (1 passed). Separate worklogs on disk confirm executor≠verifier | PASS (live, un-gameable) |
| G5 timeout-default | decision-log arm live (`decision --source timeout-default` → WHAT/WHY/REVERSAL). WAIT-primitive (ScheduleWakeup, conductor-only) documented + fallback but NOT live-waited | PARTIAL |
| G6 hot-zone stop | REAL: `/bob` stopped on live WP-A engine work + a live parallel session (dirty `mtg-sim` tree), wrote a handoff, made zero writes | PASS (live, real) |
| G7 watch+intervene | `!pause`/`!kill agent-03`/`!redirect` parsed correctly by `bob_run.py control` | PASS (live) |
| G8 handoff on stop | REAL: `bob-handoff-wpa-stop.md` written on the WP-A stop, PII-clean, suggested-skills + points-at-artifacts | PASS (live, real) |

Underlying deterministic core: **8/8 pytest green** (added `assert_branch` guard test in Amdt 1).
Net: 7 gates clean-live + G5 partial. Two imperfections remain OPEN (see below) → status
**SHIPPED-PARTIAL**, not clean SHIPPED (honest, per `/bob`'s own contract; mirrors the harness
SHIPPED-PARTIAL precedent). G6 + G8 notably proved on REAL hot-zone work, not a fixture.

**Blueprint real-spin (why it stopped, not a failure):** pointed at `BLUEPRINT-2026-07-03.md`
next move (WP-A), `/bob` hit two stop triggers at PLAN+CLAIM and refused to fan out: (1) a live
parallel session mid-edit on `mtg-sim` (dirty tree: `CLAUDE.md`, `sim_matchup_matrix.json`;
fresh commits e2861f9/ee83e45) = the two-terminal collision `/bob` exists to prevent; (2) WP-A
is a `mtg-sim/engine/` hot zone. Handoff: `scratchpad/bob-handoff-wpa-stop.md`.

## Mid-execution Amendment 3 (2026-07-04) — free-text GOAL mode (`/bob "do X"`)

Added a second input mode so `/bob` accepts either a doc path OR a free-text goal in
quotes, sharing one entry point. Deterministic detector `bob_run.py classify-input --arg`
returns `path` (doc mode: READ the definition-of-done) vs `goal` (goal mode: DRAFT it) --
coded + tested (`test_classify_input_path_vs_goal`; `bob_run.py` now 8/8 pytest, live demo
confirmed: free text -> goal, real path -> path). SKILL.md INTAKE + spine.md updated:

- GOAL MODE = the `/goal` capture step made real. INTAKE drafts falsifiable gates from the
  sentence; at PLAN+CLAIM (after confirm) it WRITES the drafted `bob-runs/<runid>/goal-spec.md`
  so intent is legible -- never fan out on an unwritten goal.
- "Goes for it" veto window: after the PLAN, a NON-hot-zone unambiguous goal auto-Goes on a
  no-response (reusing the timeout-gate wait + reversible decision log); hot-zone/ambiguous
  goals NEVER auto-Go. User may set the veto window to 0 for pure autonomy on non-hot-zone
  goals (never on hot zones). This preserves the proven-or-stop contract even in "just go" mode.

DOC-SYNC PENDING (hot zone): `harness/knowledge/tech/bob-convention-2026-07-04.md` still
describes only doc mode; adding the goal-mode line is a `harness/knowledge/` write and awaits
user sign-off (not silently edited -- `/bob`'s own hot-zone rule applied to itself).

## Changelog

- 2026-07-04: Amendment 3 — added free-text GOAL mode (`/bob "do X"`): coded+tested
  `classify-input` detector (8/8 pytest), INTAKE drafts+writes goal-spec.md, "goes for it"
  veto window (non-hot-zone auto-Go on timeout; hot zones always hold). Convention-note
  doc-sync flagged pending (hot zone). Status stays SHIPPED-PARTIAL.
- 2026-07-04: Amendment 2 — self-acceptance run: 8 gates exercised live (7 clean + G5 partial),
  G4 un-gameable proof via fan-out `wz714ufkq` (executor≠verifier), G6+G8 proven on real WP-A
  stop. Status PROPOSED → SHIPPED-PARTIAL. Two imperfections stay OPEN (G5 wait-primitive live
  proof; evidence-floor mechanization). Blueprint real-spin correctly STOPPED (collision + hot zone).
- 2026-07-04: Amendment 1 — dogfood build via ultracode `wwmp4vkiy`; refute-council found
  G3/G4/G6 confirmed + G8 + G5-partial; all fixed in skill files (branch guard coded + tested,
  hot-zone list corrected, evidence floor hardened, conditional override read); two imperfections
  recorded. Status stays PROPOSED (not SHIPPED): pending G5 live proof + convention-note sign-off.
- 2026-07-04: Created (status PROPOSED). Brainstormed via `superpowers:brainstorming`;
  6 design decisions locked with the user — Approach C (hybrid conductor), name `/bob`,
  tiered-by-blast-radius contract, any-file intake→gates, read-only+claim+branch
  concurrency, evidence-floor+refute-council+timeout-default-to-council verify, live
  run-dir with watch+intervene.
