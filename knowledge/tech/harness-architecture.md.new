---
title: "Harness Architecture"
domain: "tech"
last_updated: "2026-04-27"
confidence: "high"
sources: ["conversation-history", "live-testing", "session-2026-04-27"]
---

## Summary
The Zuxas Harness is an agent infrastructure system that gives Claude Code
persistent knowledge across sessions via markdown knowledge blocks, a
three-agent pattern (planner/executor/evaluator), and a local model pipeline
(Gemma 4 via Ollama) for zero-cost knowledge compilation.

As of 2026-04-27 the harness also includes a **spec-first execution
protocol** (8 rules in CLAUDE.md), durable spec storage in `harness/specs/`,
an annotated-imperfections registry in `harness/IMPERFECTIONS.md`,
per-domain quality grades in `harness/knowledge/tech/mtg-sim-quality-grades.md`,
mechanical drift detection (drift-detect.ps1, lint-mtg-sim.py), and a
shift-handoff session snapshot generator (session-snapshot.ps1). These
additions came from the 2026-04-26/27 mtg-sim marathon session and align
with the OpenAI Harness Engineering pattern + Anthropic effective-harness
post.

## System Architecture

### Layer 1: Bootstrap (Claude Code reads on startup)
- `CLAUDE.md` (project root) -- mandatory startup sequence, conventions,
  knowledge loading directives
- `harness/CLAUDE.md` -- master harness config including SPEC-FIRST EXECUTION
  PROTOCOL (8 rules) + SESSION START PROTOCOL (read latest-snapshot.md first)
- `harness/MEMORY.md` -- session state, active tasks, session log
- `harness/state/latest-snapshot.md` -- shift-handoff snapshot (regenerated
  by session-snapshot.ps1 at session end; read at session start)

### Layer 2: Knowledge Base (harness/knowledge/)
- `_index.md` -- registry of all blocks
- `_template.md` -- template for new blocks
- Domain-specific blocks across mtg/, career/, tech/, personal/, harness/
- Format: YAML frontmatter + markdown body + changelog
- Wikilinks (`[[other-block]]`) for cross-referencing
- Viewable in Obsidian as an interconnected graph

### Layer 3: Local Model Pipeline (Gemma 4 via Ollama)
- **Ollama** runs Gemma 4 models locally on RTX 3080 LHR (10GB VRAM)
- **compile-knowledge.ps1** -- feeds raw source to Gemma, outputs formatted
  knowledge block with frontmatter, saves to knowledge/, updates _index.md
- **ask-gemma.ps1** -- quick query tool, optional context file support
- **process-inbox.ps1** -- batch processes harness/inbox/ drop folder
- Performance: ~18 tokens/sec on gemma4 default, $0.00/query

### Layer 4: Token Compression (RTK)
- RTK v0.36.0 proxies Claude Code terminal commands
- Compresses output 60-90% before entering context window
- Windows: uses CLAUDE.md injection mode (global at ~/.claude/CLAUDE.md)
- KNOWN: rtk init -g hook mode is Unix-only; Windows falls back to CLAUDE.md
  injection. Cosmetic warning prints on every git wrap.

### Layer 5: Agent Prompts (harness/agents/)
- `planner.md` -- system prompt for planning agent
- `evaluator.md` -- system prompt for evaluation agent
- Three-agent pattern: planner -> executor -> evaluator

### Layer 6: Spec-First Execution (added 2026-04-27)
- `harness/specs/` -- durable execution specs (template, index, retroactive)
- `harness/IMPERFECTIONS.md` -- annotated imperfections registry
- `harness/knowledge/tech/mtg-sim-quality-grades.md` -- per-domain grades

### Layer 7: Drift Detection (added 2026-04-27)
- `harness/scripts/drift-detect.ps1` -- 6-check drift battery (BUILT)
- `harness/scripts/lint-mtg-sim.py` -- pure-AST static lint (BUILT)
- Gemma-powered background drift PRs (tier 3, planned)

### Layer 8: Session Snapshot (added 2026-04-27)
- `harness/scripts/session-snapshot.ps1` -- shift-handoff snapshot (BUILT)
- Output: harness/state/latest-snapshot.md (rolling) + timestamped history
- Wired into CLAUDE.md SESSION START PROTOCOL as required first read

## Script Inventory
| Script | Input | Output | Model |
|--------|-------|--------|-------|
| compile-knowledge.ps1 | raw file/text | knowledge block | gemma4 |
| ask-gemma.ps1 | question + context | answer to stdout | gemma4 |
| process-inbox.ps1 | inbox/ folder scan | compiled blocks | gemma4 |
| kb-status.ps1 | none | health check report | none |
| load-context.ps1 | domain name | block contents | none |
| drift-detect.ps1 | none | drift report | none (built 2026-04-27) |
| lint-mtg-sim.py | --check arg | lint report + exit code | none (built 2026-04-27) |
| session-snapshot.ps1 | optional flags | snapshot to harness/state/ | none (built 2026-04-27) |

## Future Extensions
- [x] MTGA log parser
- [ ] botctl -- autonomous agent process manager
- [ ] Claude Code -> Gemma delegation for cheap subtasks
- [x] Spec-first execution protocol (2026-04-27)
- [x] Annotated imperfections registry (2026-04-27)
- [x] Quality grades doc (2026-04-27)
- [x] Drift detection battery (2026-04-27)
- [x] Pre-commit lint (2026-04-27)
- [x] Session snapshot generator (2026-04-27)
- [ ] Background drift PR equivalent via Gemma (tier 3)

## Changelog
- 2026-04-14: Created
- 2026-04-15: Knowledge compiler pipeline + RTK integration
- 2026-04-27: Layer 6 (spec-first), Layer 7 (drift detection), Layer 8
  (session snapshot) added. drift-detect.ps1 + lint-mtg-sim.py +
  session-snapshot.ps1 BUILT during Phase 3.5 wait window. All three
  scripts read-only against mtg-sim, safe to run concurrently with Claude
  Code editing.
- 2026-04-27 (recovery): file rewritten from scratch after Obsidian
  auto-formatter truncated it during incremental edits. Future edits
  should write complete content rather than relying on edit_block to
  avoid same truncation issue.
