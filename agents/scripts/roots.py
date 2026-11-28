"""Portable root resolution for the harness and its sibling repos (#1).

Active scripts hardcoded `E:/vscode ai project`, so a clone anywhere else (a
worktree, CI, another machine, a renamed folder) silently targeted the wrong
workspace or failed to find sibling repos. This module is the single place that
decides where things are.

Precedence for every root:
  1. An explicit environment override, if set.
  2. Otherwise a path DERIVED from this file's location.

The owner's box is unchanged by design: roots.py lives at
`<workspace>/harness/agents/scripts/roots.py`, so `harness_root()` derives to
`E:/vscode ai project/harness` and `project_root()` to `E:/vscode ai project`
there -- byte-for-byte the old hardcoded values -- with no env vars set. A fresh
clone resolves relative to wherever it sits.

Env overrides:
  ZUXAS_PROJECT_ROOT        -> project_root()
  HARNESS_ROOT              -> harness_root()
  MTG_SIM_ROOT              -> sim_root()
  MTG_META_ANALYZER_ROOT    -> meta_root()
  MTG_META_DB               -> meta_db()
  MY_WEBSITE_ROOT           -> website_root()
  ZUXAS_BOOKS_DIR           -> books_dir()
"""
import os
from pathlib import Path

# roots.py is at <harness>/agents/scripts/roots.py
_HARNESS_FROM_FILE = Path(__file__).resolve().parents[2]


def _env(name):
    v = os.environ.get(name)
    return Path(v).expanduser().resolve() if v and v.strip() else None


def harness_root() -> Path:
    """The harness repo itself (the one this file lives in)."""
    return _env("HARNESS_ROOT") or _HARNESS_FROM_FILE


def project_root() -> Path:
    """The workspace that holds the harness and its sibling repos."""
    return _env("ZUXAS_PROJECT_ROOT") or harness_root().parent


def sim_root() -> Path:
    return _env("MTG_SIM_ROOT") or (project_root() / "mtg-sim")


def meta_root() -> Path:
    return _env("MTG_META_ANALYZER_ROOT") or (project_root() / "mtg-meta-analyzer")


def meta_db() -> Path:
    return _env("MTG_META_DB") or (meta_root() / "data" / "mtg_meta.db")


def website_root() -> Path:
    return _env("MY_WEBSITE_ROOT") or (project_root() / "My-Website")


def books_dir() -> Path:
    return _env("ZUXAS_BOOKS_DIR") or (project_root() / "books")


# Module-level constants for drop-in replacement of the old hardcoded names.
# Resolved once at import (these scripts set env before running, if at all).
HARNESS_ROOT = harness_root()
PROJECT_ROOT = project_root()
SIM_ROOT = sim_root()
META_ROOT = meta_root()
