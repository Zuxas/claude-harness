# harness/specs/ — Durable Execution Specs

## Why this exists

Last night's MTG-Sim session (2026-04-26 to 2026-04-27) shipped 14 commits
across foundation, bug fixes, and the match-runner combat-gap arc. Every
commit started with a structured spec, but those specs evaporated when the
chat session ended. The findings docs in `harness/knowledge/tech/`
captured the OUTCOMES but not the SPECS that produced them.

This directory makes specs durable. Every non-trivial piece of work gets
a spec file here BEFORE execution. The spec file persists after the work
ships, so future sessions can:

1. See how prior specs were structured (pattern-following)
2. Trace why a commit looks the way it does (rationale archaeology)
3. Pick up specced-but-not-yet-executed work without re-deriving the spec
4. Resume an in-progress staged spec mid-execution

## Naming convention

`YYYY-MM-DD-<topic>.md` for one-shot specs.
`YYYY-MM-DD-<topic>-stage-<X>.md` for staged specs (per-stage commits).

Examples:
- `2026-04-27-phase-3-5-keywords.md` -- multi-stage keyword coverage spec
- `2026-04-27-phase-3-5-keywords-stage-A.md` -- Stage A sub-spec
- `2026-04-26-canonical-deck-alignment.md` -- single-commit alignment spec

## Status field

Every spec has a status in its frontmatter:

| Status | Meaning |
|---|---|
| `PROPOSED` | Written, not yet executing. Up for revision. |
| `EXECUTING` | Active. Mid-execution by Claude Code. |
| `SHIPPED` | All steps complete, all gates passed, commit landed. |
| `SUPERSEDED` | Replaced by a later spec (link to successor). |
| `ABANDONED` | Decided not to do. Document why. |
| `BLOCKED` | Can't proceed; document blocker + dependency. |

After SHIPPED, the spec stays on disk forever as historical record. Don't
delete or overwrite shipped specs -- write new specs that reference them.

## Required structure

Every spec needs:

1. **Goal** -- one paragraph, what shipping this commit means
2. **Scope** -- bulleted list, what's IN and what's explicitly OUT
3. **Steps** -- numbered, executable, with concrete code/commands
4. **Validation gates** -- numeric thresholds that must pass before commit
5. **Stop conditions** -- explicit "STOP and surface findings" triggers
6. **Estimated time** -- rough wall time
7. **Annotated imperfections** (if any survive) -- concrete fix specs for
   what didn't make it into this commit, formatted for next-session pickup.
   Move these to `harness/IMPERFECTIONS.md` after the spec ships.

## Anti-patterns (don't do this)

- "We can defer X to fresh session" -- if X is in scope, do X. If X isn't
  in scope, say so explicitly in the Scope section. No defer-by-default.
- "Skip Y because it's not BE-relevant" -- same pattern. Either Y is in
  scope or it's explicitly out.
- Inline summaries that paraphrase findings docs -- link to the findings
  doc instead. Specs are the WHAT, findings docs are the WHY.
- Specs without validation gates -- every spec needs measurable
  acceptance criteria.

## Workflow

```
NEW WORK NEEDED
    |
    v
Write spec to harness/specs/YYYY-MM-DD-<topic>.md (status: PROPOSED)
    |
    v
Review with Jermey, revise if needed
    |
    v
Update status to EXECUTING
    |
    v
Claude Code executes step by step
    |
    v
Each validation gate passes -> proceed
Any gate fails -> STOP, surface findings, revise spec
    |
    v
Final commit lands
    |
    v
Update status to SHIPPED
    |
    v
Update findings doc in harness/knowledge/tech/ if architectural finding surfaced
    |
    v
Move any annotated imperfections to harness/IMPERFECTIONS.md
```

## Index

See `_index.md` for the chronological list of all specs by status.
