"""llama.cpp backend (tier-2). Talks the OpenAI-compatible
/v1/chat/completions endpoint that `llama-server` exposes. Pure stdlib."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request


def health(endpoint: str, timeout: int = 3) -> bool:
    """llama-server exposes GET /health -> {"status":"ok"} when a model is loaded."""
    try:
        with urllib.request.urlopen(f"{endpoint}/health", timeout=timeout) as r:
            return r.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def run(prompt: str, model: str, *, endpoint: str, max_ctx: int,
        max_tokens: int, timeout: int, system: str | None = None,
        temperature: float = 0.2) -> dict:
    """Return {text, model, tok_s, backend, ...}. Raises on failure.

    llama-server ignores the `model` field (it serves whichever GGUF it was
    launched with) but we pass it for logging parity.
    """
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    body = json.dumps({
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False,
    }).encode()

    req = urllib.request.Request(
        f"{endpoint}/v1/chat/completions", data=body,
        headers={"Content-Type": "application/json"},
    )
    t0 = time.monotonic()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read())
    elapsed = time.monotonic() - t0

    text = (data.get("choices", [{}])[0]
                .get("message", {}).get("content", "")).strip()
    if not text:
        raise ValueError("empty response from llama-server")
    usage = data.get("usage", {})
    completion_toks = usage.get("completion_tokens", 0)
    tok_s = round(completion_toks / elapsed, 1) if elapsed and completion_toks else 0.0
    return {
        "text": text,
        "model": model,
        "eval_count": completion_toks,
        "total_duration_s": round(elapsed, 2),
        "tok_s": tok_s,
        "backend": "llamacpp",
    }
