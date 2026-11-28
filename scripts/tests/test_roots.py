"""Tests for #1: portable root resolution (agents/scripts/roots.py).

The key invariant: on the owner's box (roots.py at
E:/vscode ai project/harness/agents/scripts/roots.py) the derived roots equal
the old hardcoded values, so behaviour there is unchanged; env vars override;
and a clone elsewhere resolves relative to its own location.
"""
import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AGENTS = ROOT / "agents" / "scripts"
sys.path.insert(0, str(AGENTS))


def _fresh_roots(monkeypatch, **env):
    for k in ("ZUXAS_PROJECT_ROOT", "HARNESS_ROOT", "MTG_SIM_ROOT",
              "MTG_META_ANALYZER_ROOT", "MTG_META_DB", "MY_WEBSITE_ROOT",
              "ZUXAS_BOOKS_DIR"):
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    sys.modules.pop("roots", None)
    return importlib.import_module("roots")


def test_harness_root_is_this_repo(monkeypatch):
    r = _fresh_roots(monkeypatch)
    # roots.py lives in THIS checkout, so harness_root() is it, and the sibling
    # roots derive from its parent.
    assert r.harness_root() == ROOT
    assert r.project_root() == ROOT.parent
    assert r.sim_root() == ROOT.parent / "mtg-sim"
    assert r.meta_root() == ROOT.parent / "mtg-meta-analyzer"
    assert r.meta_db() == ROOT.parent / "mtg-meta-analyzer" / "data" / "mtg_meta.db"


def test_env_overrides_win(monkeypatch, tmp_path):
    ws = tmp_path / "ws"
    r = _fresh_roots(monkeypatch, ZUXAS_PROJECT_ROOT=str(ws))
    assert r.project_root() == ws.resolve()
    assert r.sim_root() == ws.resolve() / "mtg-sim"

    r = _fresh_roots(monkeypatch, MTG_SIM_ROOT=str(tmp_path / "custom-sim"))
    assert r.sim_root() == (tmp_path / "custom-sim").resolve()


def test_owner_box_layout_preserved(monkeypatch):
    # Simulate the owner's box: roots.py at <ws>/harness/agents/scripts/roots.py.
    # Derivation must reproduce the old hardcoded E:\ values with no env set.
    import roots as r
    monkeypatch.setattr(r, "_HARNESS_FROM_FILE",
                        Path("E:/vscode ai project/harness"))
    for k in ("ZUXAS_PROJECT_ROOT", "HARNESS_ROOT", "MTG_SIM_ROOT"):
        monkeypatch.delenv(k, raising=False)
    assert r.harness_root() == Path("E:/vscode ai project/harness")
    assert r.project_root() == Path("E:/vscode ai project")
    assert r.sim_root() == Path("E:/vscode ai project/mtg-sim")
    assert r.meta_root() == Path("E:/vscode ai project/mtg-meta-analyzer")


def test_agent_hardening_uses_derived_root(monkeypatch):
    # agent_hardening must import without crashing off the owner's box and point
    # STATE_DIR under the derived harness root.
    monkeypatch.delenv("HARNESS_ROOT", raising=False)
    sys.modules.pop("roots", None)
    sys.modules.pop("agent_hardening", None)
    ah = importlib.import_module("agent_hardening")
    assert ah.HARNESS_ROOT == ROOT
    assert ah.STATE_DIR == ROOT / "state"


def test_resolved_equals_legacy_on_owner_box(monkeypatch):
    # #50 phase-2 equivalence: with roots.py at the owner's layout and no env,
    # EVERY resolved root equals the exact value the migrated scripts used to
    # hardcode. This is the automated form of the dry-run diff the migration
    # requires before the live pipeline runs against the new code.
    import roots as r
    monkeypatch.setattr(r, "_HARNESS_FROM_FILE", Path("E:/vscode ai project/harness"))
    for k in ("ZUXAS_PROJECT_ROOT", "HARNESS_ROOT", "MTG_SIM_ROOT",
              "MTG_META_ANALYZER_ROOT", "MTG_META_DB", "MY_WEBSITE_ROOT",
              "ZUXAS_BOOKS_DIR"):
        monkeypatch.delenv(k, raising=False)
    resolved = r.resolved()
    assert resolved == {name: Path(legacy) for name, legacy in r._LEGACY.items()}
    # and the pieces the scripts build on top of the roots:
    assert r.harness_root() / "knowledge" / "library" == Path(
        "E:/vscode ai project/harness/knowledge/library")
