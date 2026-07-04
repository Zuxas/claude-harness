"""Hybrid model resolution for delegate run() calls.

Resolution order (spec 2026-07-03):
    1. explicit `model` arg    -> used verbatim (hard override)
    2. else `task_type` arg    -> routing.yaml.task_types[task_type]
    3. else                    -> defaults.auto_small | auto_large (by prompt size)

Also applies the budget cap (defaults.budget) to max_tokens.
"""
from __future__ import annotations

from dataclasses import dataclass

from . import config

# Rough prompt-size split for auto mode. ~4 chars/token; 8k tokens ~= 32k chars.
_AUTO_LARGE_CHAR_THRESHOLD = 32_000


@dataclass
class Resolution:
    model: str
    backend: str          # "ollama" | "llamacpp"
    endpoint: str
    kind: str             # "ollama" | "openai_compat"
    max_ctx: int
    max_tokens: int
    reason: str           # how this was resolved (for observability)


def _model_to_backend(cfg: dict, model: str) -> tuple[str, dict]:
    """Best-effort backend guess for an explicit model not in a task_type.
    Heuristic: names containing a ':' are ollama tags; others default to the
    backend whose default model matches, else ollama."""
    tt = cfg.get("task_types", {})
    for spec in tt.values():
        if spec.get("model") == model:
            b = spec["backend"]
            return b, cfg["backends"][b]
    # fallback heuristic
    backend = "ollama" if ":" in model else "llamacpp"
    if backend not in cfg["backends"]:
        backend = next(iter(cfg["backends"]))
    return backend, cfg["backends"][backend]


def resolve(prompt: str, task_type: str | None = None,
            model: str | None = None, max_tokens: int | None = None) -> Resolution:
    cfg = config.load()
    backends = cfg["backends"]
    defaults = cfg["defaults"]
    budget = defaults.get("budget", {})
    cap = budget.get("max_tokens", 4000)

    max_ctx = 8192

    if model:  # 1. explicit override
        backend, bcfg = _model_to_backend(cfg, model)
        reason = f"explicit model={model}"
        mt = max_tokens or cap
    elif task_type and task_type in cfg.get("task_types", {}):  # 2. task_type
        spec = cfg["task_types"][task_type]
        model = spec["model"]
        backend = spec["backend"]
        bcfg = backends[backend]
        max_ctx = spec.get("max_ctx", max_ctx)
        mt = max_tokens or spec.get("max_tokens", cap)
        reason = f"task_type={task_type}"
    else:  # 3. auto
        big = len(prompt) >= _AUTO_LARGE_CHAR_THRESHOLD
        model = defaults["auto_large"] if big else defaults["auto_small"]
        backend, bcfg = _model_to_backend(cfg, model)
        mt = max_tokens or cap
        reason = f"auto_{'large' if big else 'small'} (prompt {len(prompt)} chars)"
        if task_type:
            reason += f"; unknown task_type={task_type!r} fell through to auto"

    mt = min(mt, cap)  # budget cap always wins
    return Resolution(
        model=model, backend=backend, endpoint=bcfg["endpoint"],
        kind=bcfg["kind"], max_ctx=max_ctx, max_tokens=mt, reason=reason,
    )
