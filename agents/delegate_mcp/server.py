"""delegate MCP server — local-LLM delegation over stdio for Claude Code.

Spec: harness/specs/2026-07-03-local-llm-delegation.md (EXECUTING).

Tools:
  run(prompt, task_type?, model?, max_tokens?)  -> delegate to a local model
  list_models()                                 -> configured + live models
  health()                                      -> backend liveness
  echo(text)                                    -> Gate 2.1 probe (no model)

Run:      python -m delegate_mcp.server        (cwd = harness/agents)
Register: see workspace-root .mcp.json
"""
from __future__ import annotations

import pathlib
import sys

# make harness/agents importable (for ollama_client) regardless of launch cwd
_AGENTS_DIR = pathlib.Path(__file__).resolve().parents[1]
if str(_AGENTS_DIR) not in sys.path:
    sys.path.insert(0, str(_AGENTS_DIR))

import urllib.error  # noqa: E402
import urllib.request  # noqa: E402

from mcp.server.fastmcp import FastMCP  # noqa: E402

from delegate_mcp import config, router  # noqa: E402
from delegate_mcp.backends import ollama as ollama_backend  # noqa: E402
from delegate_mcp.backends import llamacpp as llamacpp_backend  # noqa: E402

mcp = FastMCP("delegate")

_BACKENDS = {"ollama": ollama_backend, "llamacpp": llamacpp_backend}


def dispatch(prompt: str, task_type: str | None = None,
             model: str | None = None, max_tokens: int | None = None,
             system: str | None = None) -> dict:
    """Resolve routing + run on the chosen backend. Never raises — returns a
    structured error dict so the MCP transport stays clean."""
    try:
        res = router.resolve(prompt, task_type=task_type, model=model,
                             max_tokens=max_tokens)
    except Exception as e:  # config/routing error
        return {"ok": False, "error": "routing_error", "message": str(e)}

    cfg = config.load()
    timeout = cfg["defaults"].get("budget", {}).get("timeout_s", 300)
    backend = _BACKENDS.get(res.backend)
    if backend is None:
        return {"ok": False, "error": "unknown_backend", "message": res.backend}

    try:
        out = backend.run(
            prompt, res.model, endpoint=res.endpoint, max_ctx=res.max_ctx,
            max_tokens=res.max_tokens, timeout=timeout, system=system,
        )
    except Exception as e:
        return {"ok": False, "error": "backend_error", "backend": res.backend,
                "model": res.model, "resolved_by": res.reason, "message": str(e)}

    truncated = bool(out.get("eval_count", 0) >= res.max_tokens > 0)
    out.update({
        "ok": True,
        "resolved_by": res.reason,
        "backend": res.backend,
        "max_tokens": res.max_tokens,
        "truncated": truncated,
    })
    return out


@mcp.tool()
def run(prompt: str, task_type: str | None = None, model: str | None = None,
        max_tokens: int | None = None, system: str | None = None) -> dict:
    """Delegate a bounded task to a LOCAL model and return its output.

    Use for bounded, worth-the-round-trip work (bulk edits, drafts, test
    scaffolds, summaries) — NOT for contested judgment or tightly-coupled code
    (keep those on Claude). Routing is user-controlled in
    harness/agents/routing.yaml.

    Args:
        prompt: The full instruction for the local model.
        task_type: Optional routing key (e.g. 'summarize', 'bulk_edit'). Looked
            up in routing.yaml. If omitted, size-based auto routing is used.
        model: Optional hard override (e.g. 'qwen2.5-coder:7b'); wins over
            task_type.
        max_tokens: Optional output cap (clamped to the routing budget).
        system: Optional system prompt.

    Returns a dict: {ok, text, model, backend, tok_s, total_duration_s,
    resolved_by, truncated} — or {ok: false, error, message} on failure.
    """
    return dispatch(prompt, task_type=task_type, model=model,
                    max_tokens=max_tokens, system=system)


@mcp.tool()
def list_models() -> dict:
    """List models: those configured in routing.yaml, plus live Ollama tags and
    tier-2 llama-server liveness."""
    cfg = config.load()
    configured = sorted({s["model"] for s in cfg.get("task_types", {}).values()}
                        | {cfg["defaults"]["auto_small"],
                           cfg["defaults"]["auto_large"]})
    live_ollama: list[str] = []
    try:
        ep = cfg["backends"]["ollama"]["endpoint"]
        with urllib.request.urlopen(f"{ep}/api/tags", timeout=5) as r:
            import json
            live_ollama = [m["name"] for m in json.loads(r.read()).get("models", [])]
    except (urllib.error.URLError, TimeoutError, OSError, KeyError):
        pass
    tier2 = cfg["backends"].get("llamacpp", {}).get("endpoint")
    tier2_up = llamacpp_backend.health(tier2) if tier2 else False
    return {"configured": configured, "ollama_live": live_ollama,
            "llamacpp_up": tier2_up}


@mcp.tool()
def health() -> dict:
    """Ping both backends. Returns liveness booleans."""
    cfg = config.load()
    ollama_ep = cfg["backends"]["ollama"]["endpoint"]
    ollama_up = False
    try:
        with urllib.request.urlopen(f"{ollama_ep}/api/tags", timeout=5) as r:
            ollama_up = r.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        pass
    tier2 = cfg["backends"].get("llamacpp", {}).get("endpoint")
    return {"ollama": ollama_up,
            "llamacpp": llamacpp_backend.health(tier2) if tier2 else False}


@mcp.tool()
def echo(text: str) -> dict:
    """Gate 2.1 probe — returns the input unchanged. No model involved. Used to
    prove a Task-spawned subagent can invoke this MCP before wiring real work."""
    return {"ok": True, "echo": text, "server": "delegate"}


if __name__ == "__main__":
    mcp.run()
