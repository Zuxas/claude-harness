"""Tests for #27: fail-closed public allowlist. The project-graph generator and
the GEXF converter index ONLY allowlisted public repos; unknown folders, private
repos and gitignored paths are excluded by default, with local-only opt-ins.

Run: python -I scripts/test_graph_privacy.py   (from repo root)

Builds a real temp workspace (a public repo with a gitignored file, an UNKNOWN
repo, a PRIVATE repo) and drives build_snapshot / the GEXF filter for real --
behavior, not a source pin. Needs `git` on PATH.
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

# Allowlist used in tests: the real defaults plus our temp public repo name.
PUB = gp.resolve_public_folders(["pub_repo"])


def _make_workspace(root: Path):
    repo = root / "pub_repo"          # allowlisted public repo, with a gitignored file
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    (repo / ".gitignore").write_text("secret.py\n", encoding="utf-8")
    (repo / "keep.py").write_text("import os\n", encoding="utf-8")
    (repo / "secret.py").write_text("API_KEY = 'leak'\n", encoding="utf-8")
    (repo / "notes.md").write_text("# notes\n", encoding="utf-8")
    priv = root / "Team Resolve"      # known private repo (not in allowlist)
    priv.mkdir()
    (priv / "guide.md").write_text("# secret sideboard guide\n", encoding="utf-8")
    unknown = root / "brand_new_repo"  # UNKNOWN folder (Tom's regression case)
    unknown.mkdir()
    (unknown / "thing.py").write_text("x = 1\n", encoding="utf-8")
    (root / "loose_at_root.md").write_text("# loose\n", encoding="utf-8")


def test_default_includes_only_allowlist():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _make_workspace(root)
        snap = gs.build_snapshot(root, public_folders=PUB, include_gitignored=False)
        ids = {n["id"] for n in snap["nodes"]}
        assert "pub_repo/keep.py" in ids and "pub_repo/notes.md" in ids, ids
        # gitignored file in the public repo: excluded
        assert "pub_repo/secret.py" not in ids, "gitignored file leaked"
        # private AND unknown repos: excluded by default (fail-closed)
        assert not any(i.startswith("Team Resolve/") for i in ids), "private repo leaked"
        assert not any(i.startswith("brand_new_repo/") for i in ids), "unknown repo leaked"
        assert "loose_at_root.md" not in ids, "loose root file leaked"
        st = snap["stats"]
        assert "Team Resolve" in st["excluded_unknown_folders"]
        assert "brand_new_repo" in st["excluded_unknown_folders"]
        assert st["excluded_gitignored_count"] >= 1
        assert st["included_public_folders"] is not None
        # provenance markers: filtered, publishable
        assert st["gitignore_filtered"] is True
        assert st["local_only"] is False


def test_unknown_repo_excluded_by_default_regression():
    # Tom's required regression: add an unknown repo, prove BOTH layers exclude it.
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _make_workspace(root)
        # generation
        snap = gs.build_snapshot(root, public_folders=PUB)
        assert not any(n["id"].startswith("brand_new_repo/") for n in snap["nodes"])
        # publication (even if a stale snapshot still carried the node)
        stale = {"snapshot_date": "2026-11-27", "stats": {"excluded_gitignored_count": 0},
                 "nodes": [{"id": "brand_new_repo/thing.py", "top_folder": "brand_new_repo"},
                           {"id": "pub_repo/keep.py", "top_folder": "pub_repo"}],
                 "edges": []}
        nodes, _edges, dropped = jg._filter_public(stale, PUB)
        assert dropped == 1 and all(n["top_folder"] == "pub_repo" for n in nodes)


def test_opt_in_includes_everything():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _make_workspace(root)
        snap = gs.build_snapshot(root, public_folders=None, include_gitignored=True)
        ids = {n["id"] for n in snap["nodes"]}
        assert "pub_repo/secret.py" in ids, "opt-in should include gitignored"
        assert any(i.startswith("Team Resolve/") for i in ids), "opt-in should include private"
        assert any(i.startswith("brand_new_repo/") for i in ids), "opt-in should include unknown"


def test_gexf_publication_guard_drops_non_public():
    snapshot = {
        "snapshot_date": "2026-11-27", "stats": {"excluded_gitignored_count": 0},
        "nodes": [
            {"id": "pub_repo/keep.py", "top_folder": "pub_repo"},
            {"id": "Team Resolve/guide.md", "top_folder": "Team Resolve"},
        ],
        "edges": [{"from": "pub_repo/keep.py", "to": "Team Resolve/guide.md", "type": "wikilink"}],
    }
    nodes, edges, dropped = jg._filter_public(snapshot, PUB)
    ids = {n["id"] for n in nodes}
    assert "Team Resolve/guide.md" not in ids, "private node reached GEXF"
    assert "pub_repo/keep.py" in ids
    assert edges == [], "edge to a non-public node survived"
    assert dropped == 1
    n2, e2, d2 = jg._filter_public(snapshot, None)  # opt-in keeps everything
    assert d2 == 0 and len(n2) == 2 and len(e2) == 1


def test_privacy_established_requires_real_filtering():
    # Established only when filtering actually ran AND it's not a local-only export.
    assert jg._snapshot_privacy_established(
        {"stats": {"gitignore_filtered": True, "local_only": False}})
    # --include-gitignored run: count present (=0) but filtering was skipped -> refuse.
    assert not jg._snapshot_privacy_established(
        {"stats": {"gitignore_filtered": False, "local_only": True,
                   "excluded_gitignored_count": 0}})
    # --include-private run: filtered but local-only -> refuse.
    assert not jg._snapshot_privacy_established(
        {"stats": {"gitignore_filtered": True, "local_only": True}})
    # pre-fix snapshot: no markers -> refuse.
    assert not jg._snapshot_privacy_established({"stats": {"excluded_gitignored_count": 3}})
    assert not jg._snapshot_privacy_established({})


def test_check_ignore_failure_fails_closed():
    # If git check-ignore can't run, every path in that repo is EXCLUDED, not
    # passed through unchecked.
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _make_workspace(root)
        real_run = gs.subprocess.run

        def boom(cmd, *a, **k):
            if cmd[:2] == ["git", "-C"] and "check-ignore" in cmd:
                raise OSError("git exploded")
            return real_run(cmd, *a, **k)
        gs.subprocess.run = boom
        try:
            snap = gs.build_snapshot(root, public_folders=PUB, include_gitignored=False)
        finally:
            gs.subprocess.run = real_run
        ids = {n["id"] for n in snap["nodes"]}
        # pub_repo paths were all excluded because its ignore status was unknowable
        assert not any(i.startswith("pub_repo/") for i in ids), \
            "paths passed through despite check-ignore failure (fail-open!)"


def test_env_extends_public_set():
    import os
    saved = os.environ.get("GRAPH_PUBLIC_FOLDERS")
    try:
        os.environ["GRAPH_PUBLIC_FOLDERS"] = "new_public, another_pub"
        s = gp.resolve_public_folders()
        assert "new_public" in s and "another_pub" in s
        assert "mtg-sim" in s  # defaults still present
    finally:
        if saved is None:
            os.environ.pop("GRAPH_PUBLIC_FOLDERS", None)
        else:
            os.environ["GRAPH_PUBLIC_FOLDERS"] = saved


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"test_graph_privacy: OK ({len(fns)} tests)")


if __name__ == "__main__":
    _run_all()
