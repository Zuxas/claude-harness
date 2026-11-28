"""Shared privacy filters for the project-graph pipeline (#27).

The graph pipeline walks the whole local workspace, which mixes PUBLIC repos
(mtg-sim, mtg-meta-analyzer, claude-harness) with PRIVATE, local-only ones. The
harness repo is public, so a snapshot or GEXF that indexes gitignored paths or
private-repo file names leaks them. Gitignoring the output is a safety net, not
the fix; privacy is enforced here, at generation (graph-snapshot.py) AND
publication (json-to-gexf.py), per the #3/#11 review.

- Private top-level folders are EXCLUDED by default; `--include-private` opts in
  for local full-graph analysis. The default list is the known private repos;
  extend it with the GRAPH_PRIVATE_FOLDERS env var (comma-separated) or a
  `--private-folder` CLI arg. There is no reliable local public/private signal
  without the GitHub API, so this is a conservative, operator-maintained list.
- Gitignored paths are excluded via `git check-ignore` in each file's OWN repo
  (graph-snapshot.py), so a path ignored in mtg-sim is dropped even though it is
  tracked here.
"""
from __future__ import annotations

import os

# Known private, local-only repositories in the workspace. Excluded by default.
DEFAULT_PRIVATE_TOP_FOLDERS = frozenset({"Team Resolve", "My-Website"})


def resolve_private_folders(extra=None):
    """The active private-folder set: the defaults, plus GRAPH_PRIVATE_FOLDERS
    (comma-separated env), plus any `extra` names passed on the CLI."""
    names = set(DEFAULT_PRIVATE_TOP_FOLDERS)
    env = os.environ.get("GRAPH_PRIVATE_FOLDERS", "")
    names.update(n.strip() for n in env.split(",") if n.strip())
    if extra:
        names.update(n for n in extra if n)
    return frozenset(names)


def top_folder_of(rel_path):
    """The top-level folder of a forward-slash relative path ('(root)' if none)."""
    rel_path = str(rel_path).replace("\\", "/")
    return rel_path.split("/", 1)[0] if "/" in rel_path else "(root)"


def is_private(top_folder, private_folders):
    return top_folder in private_folders
