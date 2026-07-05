# /bob convention (project overrides for the bob skill)

**Status:** ACTIVE
**Created:** 2026-07-04
**Applies to:** the `bob` skill (hybrid-conductor autonomous orchestrator) --
globally installed at `~/.claude/skills/bob/SKILL.md`, user-invoked via `/bob`
(`disable-model-invocation: true`, so Claude never auto-fires it).

The global skill is intentionally generic: point it at a tasking doc and it drives
the work to a proven-done state or an honest documented stop. This file layers the
Zuxas-project overrides on top -- it is project-scoped so harness-only paths, the
hot-zone list, and PII rules never leak into the global skill that every other repo
inherits. Outside this workspace `/bob` runs with generic hot zones and the inlined
council pattern; inside it, this note lights up the workspace-specific behavior.

---

## What `/bob` is for (in THIS workspace)

`/bob <path-to-doc>` is the single named entry point that takes any pre-existing
tasking document -- a `harness/specs/` spec, a `harness/handoffs/` primer, or a loose
`.md` being worked in another terminal -- and drives it to completion OR to an honest,
documented stop, fanning out 4-20 agents for the heavy work and reporting to the user
like a foreman.

It does NOT invent new capability; it composes existing primitives (`Workflow`, the
`council` skill, the `handoff` skill, the `advisor` tool, `brainstorming`) behind a
fixed reliability spine (INTAKE -> PLAN+CLAIM -> FAN-OUT -> VERIFY -> GATE -> COMMIT ->
CLOSE). The honest framing: `/bob` converts "will the result be up to standard?" into
"it is PROVEN up to standard, or it STOPPED and told you why." It is a conductor, not
a correctness guarantee.

Use it for: driving a scoped, gated unit of harness work to done with adversarial
verification. Do NOT use it for: in-session parallel work that returns into this
context (use `Agent`/`Workflow` directly), or durable forward planning (that is a
primer, per the handoff convention).

---

## Harness HOT-ZONE list (force STOP + handoff + sign-off)

`/bob` NEVER autonomously touches a hot zone. Reaching one forces STOP, a written
`/handoff`, and a request for user sign-off -- never an autonomous edit. Hot zones in
this workspace:

- `mtg-sim/engine/` -- the simulation engine.
- Live databases on `E:\mtg-data`.
- `harness/knowledge/` (Tier K, the curated source of truth). Knowledge writes STAGE
  to `harness/inbox/promoted/` per the RESEARCH-BRAIN promotion gate; `/bob` never
  blesses Tier K directly.
- `harness/MEMORY.md` and `harness/CLAUDE.md` -- Obsidian full-content-write-only. The
  Obsidian auto-formatter corrupts these on incremental edits, so `/bob` may propose a
  MEMORY.md session-log update in CLOSE but must (a) surface it for user sign-off and
  (b) write it with a FULL-CONTENT write only, never edit-block, never on a timeout.
- Any `git push` or merge-to-main. Commits to the run's dedicated `bob/<runid>` branch
  are autonomous (reversible, low blast radius); push/merge is always a sign-off gate.

Tiered-by-blast-radius rule: a non-hot-zone unmet gate -> `council` authorizes and
proceeds; a hot-zone touchpoint -> STOP + handoff for sign-off.

---

## Run directory: `bob-runs/<runid>/`

Every run scaffolds `bob-runs/<runid>/` (STATUS.md, control.md, decisions.md, agents/,
evidence/) via `bob_run.py init`. This directory is:

- Located in the **session scratchpad** (see root `CLAUDE.md` > Scratchpad Directory),
  co-located with session work.
- **Gitignored and disposable** -- it is a live monitoring surface, audit trail, and
  handoff source, not a durable artifact. Do not commit it.
- `runid` format: `bob-YYYYMMDD-HHMMSS-<4hex>`.

The `control.md` file is the watch+intervene channel: the user writes `!pause`,
`!kill agent-NN`, `!redirect agent-NN <note>`, `!stop` etc.; agents poll it at each
checkpoint and the conductor re-reads it at wave boundaries. Interventions are honored
at checkpoints, not mid-token (calibrate expectations accordingly).

---

## Evidence floor (existence AND substance)

A gate cannot pass on a merely-present file. The `evidence/` artifact must be produced
by an INDEPENDENT verifier (the agent that verifies is not the agent that did the work)
re-running the actual check -- a hollow or self-reported artifact does not satisfy the
floor, and the refute-council explicitly attacks whether the evidence is real and maps
to the gate. On a human-gate timeout, `/bob` auto-proceeds only on a POSITIVE
evidence-backed PASS, never on a mere "not refuted."

---

## PII redaction (hard rule, not generic)

Any `/handoff` doc, staged promotion, or committed artifact `/bob` produces MUST be
scrubbed of our specific PII -- the same set the mtg-sim pre-push hook scrubs:

- the real first name (`Jermey` / `Jerme`),
- the `Zuxas` handle,
- personal deck-variant names.

Beyond keys/passwords. A handoff that later gets pasted into a committed artifact must
not carry these. See `feedback_personal_files`.

---

## Suggested skills (sourcing order)

When `/bob` writes a handoff on stop, or when it needs to recommend skills to a next
session, populate the "Suggested skills" block from `harness/skills/_index.md` FIRST
(mtg-sim-quality / meta-analysis / apl-generation / harness-ops), THEN the global set
(`grilling`, `diagnosing-bugs`, `prototype`, `tdd`, `next-card`, `council`, `handoff`,
etc.). List only skills that exist; one line each on WHY the next session needs it;
omit the row if none applies -- never invent a skill name. This mirrors the handoff
convention's suggested-skills rule verbatim.

Dependency note: `council` and `delegate` are project-scoped, not global. Inside this
workspace both are present; `/bob` prefers the `council` skill (Codex cross-vendor seat
+ house verdict format) and may route bulk/boilerplate work to `delegate`. Outside, it
degrades to the inlined blind-refute panel and skips delegation.

---

## Point at artifacts, do not restate

Reference `harness/specs/`, `harness/IMPERFECTIONS.md`, `harness/MEMORY.md`, commit
hashes, and decklists BY PATH -- never duplicate their content into a PLAN, a handoff,
or a decision-log entry. The run's `decisions.md` records what/why/source/reversal and
points at the evidence artifacts under `evidence/`; it does not re-narrate them.

---

## Related artifacts (by path)

- Spec: `harness/specs/2026-07-04-bob-orchestrator-skill.md`
- Impl plan: `harness/specs/2026-07-04-bob-orchestrator-skill-IMPL-PLAN.md`
- Handoff convention (the model for this file):
  `harness/knowledge/tech/handoff-convention-2026-06-30.md`
- Skill files: `~/.claude/skills/bob/` (SKILL.md, references/spine.md,
  references/timeout-gate.md, scripts/bob_run.py + test_bob_run.py -- 7/7 green).

---

## Changelog

- 2026-07-04: Created (STAGED) via ultracode build workflow `wwmp4vkiy`, modeled on
  `handoff-convention-2026-06-30.md`.
- 2026-07-04: LANDED at `harness/knowledge/tech/bob-convention-2026-07-04.md` with user
  sign-off (hot-zone write; NEW additive file, not a Tier-K rewrite). Added
  `harness/MEMORY.md` + `harness/CLAUDE.md` to the hot-zone list and an Evidence-floor
  section -- both closing refute-council findings from spec Amendment 1 (the staged
  draft had the same G6 omission the council caught in spine.md).
