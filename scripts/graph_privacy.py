"""Shared privacy filters for the project-graph pipeline (#27).

The graph pipeline walks the whole local workspace, which mixes PUBLIC repos
(mtg-sim, mtg-meta-analyzer, claude-harness) with PRIVATE, local-only ones. The
harness repo is public, so a snapshot or GEXF that indexes gitignored paths or
non-public file names leaks them. Gitignoring the output is a safety net, not the
fix; privacy is enforced here, at generation (graph-snapshot.py) AND publication
(json-to-gexf.py), per the #3/#11 review.

Fail-closed by design (Tom, #27): the graph includes ONLY an explicit allowlist
of public repositories. Unknown workspace folders and private repos are excluded
by default, so a newly added private repo is never exposed because someone forgot
to update a denylist -- for a public repo with a history of leaks, missing graph
coverage beats accidental disclosure. Adding a repository to the graph requires an
explicit decision (edit the allowlist / GRAPH_PUBLIC_FOLDERS env / --public-folder).
`--include-private` + `--include-gitignored` are local-only opt-ins.

There is no reliable local public/private signal without the GitHub API, so the
allowlist is operator-maintained.
"""
from __future__ import annotations

import os

# Explicitly approved public repositories (top-level folder names). The local
# claude-harness checkout lives in a folder named "harness"; both names are
# listed so the allowlist works whether the walk root is the workspace or the
# repo itself.
DEFAULT_PUBLIC_TOP_FOLDERS = frozenset({
    "mtg-sim", "mtg-meta-analyzer", "claude-harness", "harness",
})


def resolve_public_folders(extra=None):
    """The active public-allowlist: the defaults, plus GRAPH_PUBLIC_FOLDERS
    (comma-separated env), plus any `extra` names passed on the CLI."""
    names = set(DEFAULT_PUBLIC_TOP_FOLDERS)
    env = os.environ.get("GRAPH_PUBLIC_FOLDERS", "")
    names.update(n.strip() for n in env.split(",") if n.strip())
    if extra:
        names.update(n for n in extra if n)
    return frozenset(names)


def top_folder_of(rel_path):
    """The top-level folder of a forward-slash relative path ('(root)' if none)."""
    rel_path = str(rel_path).replace("\\", "/")
    return rel_path.split("/", 1)[0] if "/" in rel_path else "(root)"


def is_public(top_folder, public_folders):
    return top_folder in public_folders
