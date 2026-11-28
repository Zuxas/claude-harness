"""Tests for #27: the project-graph generator excludes gitignored paths and
private repos by default, with opt-in.

Run: python -I scripts/test_graph_privacy.py   (from repo root)

Builds a real temp workspace (a git repo with a gitignored file + a private
top-folder) and drives build_snapshot / the GEXF filter for real -- behavior,
not a source pin. Needs `git` on PATH.
"""
import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent


def _load(stem, name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / stem)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


gp = _load("graph_privacy.py", "graph_privacy")
gs = _load("graph-snapshot.py", "graphsnapshot")
jg = _load("json-to-gexf.py", "jsontogexf")


def _make_workspace(root: Path):
    # Public repo with a gitignored file
    repo = root / "pub_repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    (repo / ".gitignore").write_text("secret.py\n", encoding="utf-8")
    (repo / "keep.py").write_text("import os\n", encoding="utf-8")
    (repo / "secret.py").write_text("API_KEY = 'leak'\n", encoding="utf-8")
    (repo / "notes.md").write_text("# notes\n", encoding="utf-8")
    # Private, local-only repo (named in the default private set)
    priv = root / "Team Resolve"
    priv.mkdir()
    (priv / "guide.md").write_text("# secret sideboard guide\n", encoding="utf-8")


def test_default_excludes_gitignored_and_private():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _make_workspace(root)
        snap = gs.build_snapshot(root, private_folders=gp.resolve_private_folders(),
                                 include_gitignored=False)
        ids = {n["id"] for n in snap["nodes"]}
        assert "pub_repo/keep.py" in ids, ids
        assert "pub_repo/notes.md" in ids, ids
        # gitignored file is gone
        assert "pub_repo/secret.py" not in ids, "gitignored file leaked into graph"
        # private repo is gone, by any path under it
        assert not any(i.startswith("Team Resolve/") for i in ids), "private repo leaked"
        assert "Team Resolve" in snap["stats"]["excluded_private_folders"]
        assert snap["stats"]["excluded_gitignored_count"] >= 1


def test_opt_in_includes_everything():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _make_workspace(root)
        snap = gs.build_snapshot(root, private_folders=frozenset(),
                                 include_gitignored=True)
        ids = {n["id"] for n in snap["nodes"]}
        assert "pub_repo/secret.py" in ids, "opt-in should include gitignored"
        assert any(i.startswith("Team Resolve/") for i in ids), "opt-in should include private"


def test_gexf_publication_guard_drops_private():
    snapshot = {
        "snapshot_date": "2026-11-27", "stats": {},
        "nodes": [
            {"id": "pub_repo/keep.py", "top_folder": "pub_repo"},
            {"id": "Team Resolve/guide.md", "top_folder": "Team Resolve"},
        ],
        "edges": [{"from": "pub_repo/keep.py", "to": "Team Resolve/guide.md", "type": "wikilink"}],
    }
    priv = gp.resolve_private_folders()
    nodes, edges, dropped = jg._filter_private(snapshot, priv)
    ids = {n["id"] for n in nodes}
    assert "Team Resolve/guide.md" not in ids, "private node reached GEXF"
    assert "pub_repo/keep.py" in ids
    assert edges == [], "edge to a private node survived"
    assert dropped == 1
    # opt-in keeps everything
    n2, e2, d2 = jg._filter_private(snapshot, frozenset())
    assert d2 == 0 and len(n2) == 2 and len(e2) == 1


def test_env_extends_private_set(monkeypatch=None):
    import os
    saved = os.environ.get("GRAPH_PRIVATE_FOLDERS")
    try:
        os.environ["GRAPH_PRIVATE_FOLDERS"] = "Secret Repo, Another"
        s = gp.resolve_private_folders()
        assert "Secret Repo" in s and "Another" in s
        assert "Team Resolve" in s  # defaults still present
    finally:
        if saved is None:
            os.environ.pop("GRAPH_PRIVATE_FOLDERS", None)
        else:
            os.environ["GRAPH_PRIVATE_FOLDERS"] = saved


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"test_graph_privacy: OK ({len(fns)} tests)")


if __name__ == "__main__":
    _run_all()
