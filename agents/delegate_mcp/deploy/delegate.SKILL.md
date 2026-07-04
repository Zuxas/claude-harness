---
name: delegate
description: Offload a bounded, high-output task to a LOCAL model (tier-1 Ollama qwen2.5-coder:7b / tier-2 llama.cpp Qwen3-Coder-30B-A3B) via the delegate MCP, to save Claude tokens. Use when asked to route/offload/delegate mechanical work to local LLMs, or when running a task list and a subtask is bulk/boilerplate/draft/summarize work worth handing off. Do NOT use for contested judgment, tightly-coupled code, or anything security-sensitive — keep those on Claude. Routing is user-controlled in harness/agents/routing.yaml.
---

# /delegate — local-LLM worker delegation

Spec: `harness/specs/2026-07-03-local-llm-delegation.md`. The council decides
(Claude / high-level AI only); local models are WORKERS invoked case-by-case.
Local models never run the council.

## The tool

`mcp__delegate__run(prompt, task_type?, model?, max_tokens?, system?)` -> dict
`{ok, text, model, backend, tok_s, total_duration_s, resolved_by, truncated}`.
Also: `mcp__delegate__list_models()`, `mcp__delegate__health()`,
`mcp__delegate__echo(text)`.

If the MCP isn't loaded (fresh install / not yet approved), it won't appear —
tell the user to restart Claude Code and approve the `delegate` server.

## Routing (user-controlled)

Resolution order: explicit `model` > `task_type` (looked up in
`harness/agents/routing.yaml`) > size-based auto. The user edits routing.yaml to
reassign a task type; no code change needed. Current task_types:
- tier-1 (Ollama, ~90-100 tok/s, all-GPU): `test_scaffold`, `summarize`,
  `boilerplate`, `commit_message` (low-output — explicit only)
- tier-2 (llama.cpp, ~20 tok/s, MoE offload): `bulk_edit`, `draft_long`

## The "worth it?" gate — apply BEFORE delegating

```
DELEGATE when BOTH:
  - bounded task (bulk edit, draft, test scaffold, summarize, boilerplate)
    AND not tightly coupled to the reasoning just produced
  - worth the round-trip — EITHER high output vs input (savings bank on OUTPUT
    tokens Claude would otherwise generate) OR cheap-to-verify boilerplate
Then VERIFY by output type:
  - CODE  -> ast.parse / lint / test before accepting
  - PROSE -> a quick Claude read before accepting (not machine-checkable)
KEEP on Claude when ANY:
  - contested judgment / architecture / trade-off (that's /council)
  - tightly-coupled multi-file edit needing one coherent context
  - security-sensitive or irreversible
  - low output AND high precision (round-trip not worth it — e.g. commit msgs)
```
Savings are real only when the local model GENERATES bulk output. A Claude
subagent still pays tokens to prompt + read back, so a tiny-output task loses.

## tier-2 lifecycle (one_tier_hot)

The 10GB GPU holds ONE tier at a time (tier-2 uses ~9.8GB; measured). To use
tier-2, first start the persistent server:
`powershell -ExecutionPolicy Bypass -File harness/scripts/start-llamacpp-tier2.ps1`
(it unloads Ollama first). `list_models()`/`health()` show `llamacpp_up`. When
tier-2 is down, tier-2 task_types will error — either start it or route to tier-1.

## Executor pattern (for a task list)

Given a list of tasks (from Claude's own plan, an agent, or the user — NOT an
automatic council-verdict pipe; that was descoped), for each task:
1. Apply the gate above. KEEP-on-Claude tasks: do them yourself, don't delegate.
2. For a DELEGATE task: call `mcp__delegate__run` with the right `task_type`.
3. Verify by output type (code: machine; prose: read). If verify fails, redo on
   Claude — never let unverified local output land.
4. Record outcome (delegated/kept, model, tok_s, verified y/n) for the summary.

A subagent CAN call this MCP (verified) — but keep interdependent code on one
Claude context; delegate only the independent, bounded, high-output pieces.
