# CONTEXT — harness (claude-harness)

Purpose: multi-layer agent coordination — persistent knowledge, dual-model
routing (Claude + local Gemma/Qwen via Ollama), three-agent execution, nightly
automation over mtg-sim + mtg-meta-analyzer. (Upstream clone: claude-harness-repo.)

## Vocabulary (as used in THIS repo)
- planner / executor / evaluator — three-agent pattern
- spec / spec lifecycle — PROPOSED -> EXECUTING -> SHIPPED (status on disk)
- knowledge blocks / _index.md — markdown KB under knowledge/, domain-tagged
- MEMORY.md — append-only durable session log
- snapshot / drift-detect — session capture + consistency-check battery
- IMPERFECTIONS.md — tracked known limits (OPEN/RESOLVED, spec + commit hash)
- Gemma / Qwen — local LLMs via Ollama (http://localhost:11434/api/generate)
- RTK — optional terminal-output compression layer

## Automation entry points (agents/scripts/)
- auto_pipeline.run_pipeline / find_new_archetypes / generate_apl / _smoke_test_apl
  / _generate_deck_file_from_db / _register_auto_apl
- apl_optimizer.run_optimizer        (APL logic self-tuning)
- tuning_loop.run_tuning_loop        (card-swap loop + check_card_legal)
- nightly_harness.run_nightly        (scheduled orchestration)
- agent_hardening: CircuitBreaker, LoopController, IdempotencyGuard, atomic_write_json

## Gotchas
- Ollama must be running for Gemma/Qwen generation; circuit breaker opens after 3 fails
- optimization_memory.json is the experiment log; always atomic_write_json
- Obsidian auto-formatter can destroy CLAUDE.md / MEMORY.md on incremental edits —
  use full-content writes on those two files, never partial edits
- This repo drives the mtg-sim ARL (loop_state.json) via the reusable scripts above

## Key paths
agents/scripts/  scripts/  knowledge/  specs/  MEMORY.md  HARNESS_STATUS.md  IMPERFECTIONS.md
