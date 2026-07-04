"""Importable Ollama client — the shared streaming client the harness has
wanted since spec 2026-06-26 B4 (which was never shipped).

Both the delegate MCP (harness/agents/delegate_mcp/backends/ollama.py) and the
~9 legacy `ask_gemma`/`_call_ollama` sites can import this. Modeled on the
proven `auto_pipeline.py::_call_ollama` streaming-accumulation pattern:
stream=True avoids the Ollama bug where stream=False returns an empty response
for some models after heavy load. Retries with backoff. Pure stdlib (urllib) —
no `requests` dependency.

Public API:
    generate(prompt, model, ...) -> dict   # text + timing/tok_s metadata
    call_ollama(prompt, model, ...) -> str # B4 drop-in: just the text
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
import urllib.error

DEFAULT_ENDPOINT = "http://localhost:11434"


def _log(msg: str) -> None:
    # stderr only — stdout is reserved for MCP JSON-RPC when wrapped.
    print(f"[ollama_client] {msg}", file=sys.stderr, flush=True)


def generate(
    prompt: str,
    model: str,
    *,
    system: str | None = None,
    temperature: float = 0.3,
    max_tokens: int = 512,
    num_ctx: int = 4096,
    keep_alive: str = "30m",
    timeout: int = 300,
    retries: int = 2,
    endpoint: str = DEFAULT_ENDPOINT,
) -> dict:
    """Call Ollama /api/generate (streaming) and return text + metadata.

    Returns: {text, model, eval_count, total_duration_s, tok_s, backend}
    Raises the last error after `retries` backoff attempts (2s, 8s, ...).
    """
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": True,
        "keep_alive": keep_alive,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
            "num_ctx": num_ctx,
            "num_batch": 1024,
        },
    }
    if system:
        payload["system"] = system
    body = json.dumps(payload).encode()

    backoffs = [2, 8][:max(0, retries)]
    last_err: Exception | None = None
    for attempt in range(len(backoffs) + 1):
        try:
            req = urllib.request.Request(
                f"{endpoint}/api/generate", data=body,
                headers={"Content-Type": "application/json"},
            )
            tokens: list[str] = []
            final: dict = {}
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                for line in resp:
                    if not line.strip():
                        continue
                    chunk = json.loads(line)
                    tokens.append(chunk.get("response", ""))
                    if chunk.get("done"):
                        final = chunk
                        break
            text = "".join(tokens).strip()
            if not text:
                raise ValueError("empty response from Ollama")
            ec = final.get("eval_count", 0)
            ed = final.get("eval_duration", 0) or 0
            tok_s = (ec / (ed / 1e9)) if ed else 0.0
            return {
                "text": text,
                "model": model,
                "eval_count": ec,
                "total_duration_s": (final.get("total_duration", 0) or 0) / 1e9,
                "tok_s": round(tok_s, 1),
                "backend": "ollama",
            }
        except (urllib.error.URLError, TimeoutError, ValueError) as e:
            last_err = e
            if attempt < len(backoffs):
                _log(f"call failed ({e}); retry {attempt + 1}/{len(backoffs)} "
                     f"in {backoffs[attempt]}s")
                time.sleep(backoffs[attempt])
    assert last_err is not None
    raise last_err


def call_ollama(prompt: str, model: str, **kw) -> str:
    """B4 drop-in: return just the response text (compat with legacy ask_gemma)."""
    return generate(prompt, model, **kw)["text"]
