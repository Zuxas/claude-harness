"""Tests for #17: parallel gauntlet reconstructs goldfish-wrapped APLs, and
failed matchups are surfaced instead of silently becoming 50.0.

Run: python agents/scripts/test_gauntlet_goldfish.py   (from repo root)

Needs the sibling mtg-sim checkout for GoldfishAdapter; skips cleanly (exit 0)
where it isn't present, e.g. CI.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import roots  # noqa: E402

_SIM = roots.sim_root()
if not (_SIM / "apl" / "match_apl.py").exists():
    print(f"  skip test_gauntlet_goldfish (mtg-sim not found at {_SIM})")
    print("test_gauntlet_goldfish: OK (skipped)")
    sys.exit(0)

sys.path.insert(0, str(_SIM))
import matchup_gauntlet as mg  # noqa: E402
from apl.base_apl import BaseAPL  # noqa: E402
from apl.match_apl import GoldfishAdapter  # noqa: E402


class _InnerGoldfish(BaseAPL):
    """A minimal concrete goldfish APL to wrap."""
    name = "Inner Test Deck"

    def keep(self, hand, mulligans, on_play):
        return True

    def bottom(self, hand, n):
        return hand[:n]

    def main_phase(self, gs):
        pass


def test_get_apl_info_encodes_inner_not_adapter():
    ga = GoldfishAdapter(_InnerGoldfish())
    info = mg._get_apl_info(ga)
    # Must encode the INNER class, not ("...", "GoldfishAdapter") which the worker
    # would call with no args -> TypeError.
    assert info[0] == "__goldfish__", info
    assert info[1].endswith(":_InnerGoldfish"), info
    assert "GoldfishAdapter" not in info[1], info


def test_rebuild_roundtrips_goldfish():
    ga = GoldfishAdapter(_InnerGoldfish())
    rebuilt = mg._rebuild_apl(mg._get_apl_info(ga))
    assert isinstance(rebuilt, GoldfishAdapter), type(rebuilt)
    assert type(rebuilt.inner).__name__ == "_InnerGoldfish"
    assert rebuilt.name == ga.name


def test_field_wr_none_not_fifty_for_no_data():
    entries = [{"name": "A", "slug": "a"}, {"name": "B", "slug": "b"},
               {"name": "Ghost", "slug": "ghost"}]
    # A and B played each other; Ghost has no completed matchups.
    matrix = {("A", "B"): 60.0, ("B", "A"): 40.0}
    fw = mg.compute_field_wr(matrix, entries, "modern")
    assert fw["Ghost"] is None, fw          # NOT 50.0
    assert fw["A"] is not None and fw["B"] is not None, fw


def test_failed_set_and_csv_render():
    assert mg._failed_set([("A", "B")]) == {("A", "B"), ("B", "A")}
    import tempfile
    entries = [{"name": "A", "slug": "a"}, {"name": "Ghost", "slug": "ghost"}]
    matrix = {}  # every pair failed
    fw = {"A": None, "Ghost": None}
    orig = mg.TEAM_DATA_DIR
    try:
        mg.TEAM_DATA_DIR = Path(tempfile.mkdtemp())
        path = Path(mg.write_csv(entries, matrix, fw, "modern", failed_pairs=[("A", "Ghost")]))
        text = path.read_text()
        assert "FAIL" in text, text                 # failed cell, not 0.0
        assert "# failed_matchups,1" in text, text   # explicit count
        assert "N/A" in text, text                   # no-data field WR
    finally:
        mg.TEAM_DATA_DIR = orig


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"test_gauntlet_goldfish: OK ({len(fns)} tests)")


if __name__ == "__main__":
    _run_all()
