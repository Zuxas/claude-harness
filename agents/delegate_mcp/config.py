"""Load + cache routing.yaml. The user edits routing.yaml to reassign tasks;
this module is the only place that reads it."""
from __future__ import annotations

import os
from pathlib import Path

import yaml

# routing.yaml lives one dir up: harness/agents/routing.yaml
_ROUTING_PATH = Path(__file__).resolve().parent.parent / "routing.yaml"
_cache: dict | None = None


def routing_path() -> Path:
    # env override for testing / relocation
    return Path(os.environ.get("DELEGATE_ROUTING_YAML", str(_ROUTING_PATH)))


def load(force: bool = False) -> dict:
    """Return the parsed routing config (cached). Raises FileNotFoundError /
    yaml.YAMLError with a clear message if the file is missing or malformed."""
    global _cache
    if _cache is not None and not force:
        return _cache
    p = routing_path()
    if not p.exists():
        raise FileNotFoundError(f"routing.yaml not found at {p}")
    with open(p, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict) or "backends" not in data or "defaults" not in data:
        raise ValueError(f"routing.yaml malformed (need backends+defaults): {p}")
    _cache = data
    return data
