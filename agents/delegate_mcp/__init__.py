"""delegate_mcp — thin local-LLM delegation MCP for the harness.

Spec: harness/specs/2026-07-03-local-llm-delegation.md (EXECUTING).
Council decides (Claude-only); local models are workers invoked case-by-case
via mcp__delegate__run. Routing is user-controlled in harness/agents/routing.yaml.
"""
