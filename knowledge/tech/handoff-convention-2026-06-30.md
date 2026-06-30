# Handoff convention (project overrides for the `handoff` skill)

**Status:** ACTIVE
**Created:** 2026-06-30
**Applies to:** the `handoff` skill (Matt Pocock, MIT) — globally installed at
`~/.claude/skills/handoff/SKILL.md`, user-invoked via `/handoff`
(`disable-model-invocation: true`, so Claude never auto-fires it).

The global skill is intentionally generic. This file layers the Zuxas-project
overrides on top — it is project-scoped so harness-only paths never leak into the
global skill that every other repo inherits.

---

## What `/handoff` is for (and is NOT)

A `/handoff` doc is **on-demand, scoped, live-context compression**: you are mid-session,
spot work that is out-of-scope for the current thread, and eject *just that slice* to a
fresh agent instead of polluting the current context (which pushes you into the
"dumb zone" past ~120k tokens). Ejecting scope also **sharpens the current session** —
the agent stops trying to hold the tangent.

Use it for:
- **Scope ejection mid-grilling/build** — `/handoff <purpose>` -> fresh session.
- **Cross-tool work** — hand a slice to Codex / Copilot (we already keep `.codex/` +
  `AGENTS.md` in mtg-sim). Plain markdown is the cleanest Claude<->Codex carrier.
- **Round-trip** — parent session -> `/handoff` to a prototype session -> that session
  `/handoff`s its learnings back to the parent. A DIY subagent across context windows.

Do NOT use it for:
- **In-session parallel work** — use the `Agent` tool / `Workflow` instead; subagents
  return into this context, a handoff doc does not.
- **Durable forward planning** — that is a *primer* (see distinction below), not a handoff.

---

## Project overrides vs the stock skill

1. **Save location.** Stock skill writes to bare OS `%TEMP%`. HERE, write to the session
   scratchpad dir (see root `CLAUDE.md` > Scratchpad Directory) so the doc is co-located
   with session work and still disposable. Still disposable — do not commit handoff docs.

2. **PII redaction (hard rule, not generic).** Beyond keys/passwords, redact our specific
   PII that the mtg-sim pre-push hook scrubs: the real first name (Jermey/Jerme), the
   `Zuxas` handle, and personal deck-variant names. A handoff that later gets pasted into a
   committed artifact must not carry these. See `feedback_personal_files`.

3. **"Suggested skills" section pulls from our menus.** Populate it from
   `harness/skills/_index.md` first (mtg-sim-quality / meta-analysis / apl-generation /
   harness-ops), then the global skill set (`grilling`, `diagnosing-bugs`, `prototype`,
   `tdd`, `next-card`, `planner`, etc.). This plugs the next session straight into the
   skill-first protocol.

4. **Point at artifacts, don't restate.** Reference `harness/specs/`, `IMPERFECTIONS.md`,
   `MEMORY.md`, commit hashes, and decklists by path — never duplicate their content.

---

## "Suggested skills" — template block

Every `/handoff` doc in this project ends with a block of this shape. List only skills
that exist (harness menu first, then global set); one line each on WHY the next session
needs it. Omit the row if none applies — never invent a skill name.

```markdown
## Suggested skills
Invoke these at the start of the next session:
- `<harness skill from skills/_index.md>` — <why this slice needs it>
  (e.g. `meta-analysis` — the slice runs a Modern gauntlet + reads field WRs)
- `<global skill>` — <why>
  (e.g. `diagnosing-bugs` — the slice is a repro-first bug hunt)
- `/grilling` — <only if the next session is design-before-build>
```

---

## Disposable handoff vs durable primer (do NOT conflate)

| | `/handoff` doc (disposable) | Primer (durable) |
|---|---|---|
| Purpose | eject a slice of LIVE context now | plan the NEXT slate of sessions ahead |
| Authored | on demand, mid-session | end-of-day / forward planning |
| Lives in | session scratchpad | `harness/handoffs/` (gitignored) |
| Lifetime | delete after the receiving session consumes it | picked off over days |
| Skill | `/handoff` | hand-authored per `feedback_handoff_primers` |

**Promote path:** if a disposable handoff turns out to describe a real, session-sized
unit of planned work, promote it into a durable primer under `harness/handoffs/`
(add it to that dir's `_index.md`) rather than leaving it to rot in scratchpad.

---

## Changelog
- 2026-06-30: Created. Globalized the `handoff` skill (confirmed byte-identical at
  `~/.claude/skills/handoff`) and wrote this project override. Added a row to
  `harness/skills/_index.md` and the disposable-vs-primer note to
  `harness/handoffs/_index.md`.
