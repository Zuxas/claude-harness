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


# The old hardcoded values, kept only so the dry-run below and the equivalence
# test can diff the resolved roots against what the scripts used to target.
_LEGACY = {
    "project_root": "E:/vscode ai project",
    "harness_root": "E:/vscode ai project/harness",
    "sim_root": "E:/vscode ai project/mtg-sim",
    "meta_root": "E:/vscode ai project/mtg-meta-analyzer",
    "meta_db": "E:/vscode ai project/mtg-meta-analyzer/data/mtg_meta.db",
    "website_root": "E:/vscode ai project/My-Website",
    "books_dir": "E:/vscode ai project/books",
}


def resolved() -> dict:
    """Every root as currently resolved (env overrides + derivation)."""
    return {
        "project_root": project_root(),
        "harness_root": harness_root(),
        "sim_root": sim_root(),
        "meta_root": meta_root(),
        "meta_db": meta_db(),
        "website_root": website_root(),
        "books_dir": books_dir(),
    }


def _main():
    """Dry-run: print every resolved root and whether it matches the legacy
    hardcoded value (#50). On the owner's box with no env set they should all
    MATCH; a fresh clone shows the derived paths. Modifies nothing."""
    import sys as _sys
    res = resolved()
    width = max(len(k) for k in res)
    all_match = True
    for name, path in res.items():
        legacy = Path(_LEGACY[name])
        match = path == legacy
        all_match = all_match and match
        tag = "MATCH " if match else "DIFFER"
        print(f"  {name:<{width}}  [{tag}]  {path}")
        if not match:
            print(f"  {'':<{width}}            (legacy: {legacy})")
    print()
    print("All roots match the legacy hardcoded values."
          if all_match else
          "Some roots differ from legacy -- expected on any box that isn't "
          "E:/vscode ai project (a fresh clone, a worktree, CI).")
    return 0 if all_match else 1


if __name__ == "__main__":
    raise SystemExit(_main())
