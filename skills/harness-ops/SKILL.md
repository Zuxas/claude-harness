# Skill: harness-ops

**One-line:** Operate the harness itself -- snapshots, the Gemma drift PR, scheduled tasks, and session state -- without dragging the whole 60 KB MEMORY.md into context.

## Activate when
Trigger phrases: "session", "snapshot", "drift PR", "nightly", "schedule".
Load this skill for any task about session handoff state, regenerating a
snapshot, the overnight drift PR, scheduled-task registration, or the
sub-project menu.

## Load these files
- `harness/MEMORY.md` -- durable session log + active task list. LOAD ONLY THE RELEVANT SECTION (see behavior rule G6), never the whole file.
- `harness/scripts/session-snapshot.ps1` -- 04:30 shift-handoff snapshot generator; run this if latest-snapshot is stale (>24h) or missing.
- `harness/scripts/gemma-drift-pr.ps1` -- 04:50 Gemma drift PR wrapper; regenerate the inbox drift PR when missing and Ollama is healthy.
- `harness/scripts/register-harness-tasks.ps1` -- Windows Task Scheduler registration (run as Administrator).
- `harness/SUBPROJECTS.md` -- canonical sub-project pivot menu for the morning DAILY RHYTHM CHECK.

## Behavior rules
- MEMORY.md is ~60 KB. Load ONLY the relevant MEMORY.md section, never the whole 60 KB file -- loading it whole defeats the skill system's entire purpose (context reduction). Grep to the active-task or section you need and read that slice.
- Use full-content `write_file` on MEMORY.md and CLAUDE.md, never incremental edit -- Obsidian's auto-formatter has destroyed content during incremental edits to these two files.
- If the snapshot is stale (>24h) or missing, run `harness/scripts/session-snapshot.ps1` before trusting handoff state. The drift PR is optional/non-blocking; regenerate only if missing and Ollama is healthy.
- ASCII-only output; use "->" and "--". Write PowerShell to C:\temp\ and execute with -ExecutionPolicy Bypass.

## Related specs
- `harness/specs/2026-06-26-harness-ollama-watcher-optimization.md`
- `harness/specs/2026-06-27-next-fronts-roadmap.md`
- `harness/specs/2026-06-28-skill-system-impl-plan.md`
