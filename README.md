# claude-harness

The memory + quality layer for a local multi-repo MTG ecosystem (mtg-sim,
mtg-meta-analyzer, My-Website). It keeps agent work honest across sessions:
durable knowledge, spec-first execution with falsifiable gates, local-model
delegation, and structured decision review.

This repo is read at the start of every Claude Code session (see `CLAUDE.md`).
It is not an app — it is the harness the apps are built under.

## What it is (read these first)
- **`CLAUDE.md`** — master harness config + the 9-rule SPEC-FIRST EXECUTION
  PROTOCOL. Read at session start.
- **`HARNESS_STATUS.md`** — current system state, capabilities, and roadmap.
- **`MEMORY.md`** — durable session log + active task list (gitignored on some
  clones; local planning state).
- **`specs/`** — every non-trivial change gets a dated spec (PROPOSED → EXECUTING
  → SHIPPED) with goal/scope/steps/validation-gates/stop-conditions. `_index.md`
  mirrors status. This is where work is designed before code is written.
- **`knowledge/`** — durable domain blocks (mtg / tech / career / personal) +
  findings docs + council verdicts. `_index.md` is the registry.
- **`IMPERFECTIONS.md`** — tracked known-limits with concrete fix paths.

## Core capabilities
- **Spec-first protocol** — falsifiable, pre-registered gates; stop conditions
  with teeth; status lifecycle on disk; compounding methodology lessons.
- **Knowledge persistence** — inbox → local-model compile → structured blocks
  Claude reads next session; grows without spending Claude tokens.
- **Local-model pipeline + delegation** — Ollama (qwen2.5-coder for code, gemma4
  for prose) on an RTX 3080; plus the **delegate MCP** (`agents/delegate_mcp/`,
  `agents/routing.yaml`) that hands bounded, high-output work to local models
  case-by-case. Council decides (Claude/high-level AI only); local models are
  workers. See `specs/2026-07-03-local-llm-delegation.md`.
- **Council decision protocol** — `.claude/skills/council` (workspace root): a
  blind, anonymized, cross-critique review with a Codex cross-vendor seat, for
  M+ spec approvals, gate verdicts, and irreversible operations.
- **Drift PRs + session snapshots** — overnight pattern observations and a
  canonical handoff doc, so each session starts from verified state.
- **RTK token compression** — compact command output to conserve context.

## Agents & scripts
`agents/scripts/` holds the Python agents (auto-pipeline, tuning loop, drift PR,
nightly harness, etc.); `agents/` also holds `ollama_client.py` (shared local-LLM
client) and `delegate_mcp/`. `scripts/` holds PowerShell wrappers (snapshots,
drift PR, inbox watcher, `start-llamacpp-tier2.ps1`). See `HARNESS_STATUS.md`
§SCRIPT REFERENCE.

## Conventions
- Specs in `specs/YYYY-MM-DD-<topic>.md`; findings in `knowledge/tech/`; a new
  block registers in the relevant `_index.md`.
- File-scoped git adds only — multiple agents/sessions share these repos; never
  `git add -A`.
- ASCII terminal output; PowerShell scripts run `-ExecutionPolicy Bypass`.

## Related repos (siblings, local)
`../mtg-sim` (engine), `../mtg-meta-analyzer` (data/GUI), `../My-Website`
(playbooks). This harness is the shared memory/quality layer above all three.
