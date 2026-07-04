"""Ollama backend (tier-1). Thin wrapper over the shared ollama_client."""
from __future__ import annotations

import pathlib
import sys

try:
    import ollama_client
except ImportError:  # allow import when harness/agents isn't already on path
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
    import ollama_client


def run(prompt: str, model: str, *, endpoint: str, max_ctx: int,
        max_tokens: int, timeout: int, system: str | None = None,
        temperature: float = 0.2) -> dict:
    """Return {text, model, tok_s, backend, ...}. Raises on failure."""
    return ollama_client.generate(
        prompt, model, system=system, temperature=temperature,
        max_tokens=max_tokens, num_ctx=max_ctx, timeout=timeout,
        endpoint=endpoint,
    )
