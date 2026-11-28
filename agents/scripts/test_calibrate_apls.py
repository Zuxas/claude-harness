"""Tests for #22: calibration uses the real deck APLs (not Generic-vs-Generic)
and excludes non-win/loss results from the real win-rate denominator.

Run: python agents/scripts/test_calibrate_apls.py   (from repo root)

aggregate_matchups is pure and runs anywhere. The APL-selection test needs the
sibling mtg-sim for GoldfishAdapter / the match APLs; it skips cleanly (e.g. CI).
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import roots  # noqa: E402

_SIM = roots.sim_root()
_HAVE_SIM = (_SIM / "apl" / "match_apl.py").exists()
if _HAVE_SIM:
    sys.path.insert(0, str(_SIM))

import calibrate  # noqa: E402  (lazy engine imports -> safe without mtg-sim)


def test_non_winloss_excluded_from_denominator():
    matches = [
        {"my_deck": "A", "opp_deck": "B", "result": "win"},
        {"my_deck": "A", "opp_deck": "B", "result": "loss"},
        {"my_deck": "A", "opp_deck": "B", "result": "draw"},     # excluded
        {"my_deck": "A", "opp_deck": "B", "result": None},        # excluded
        {"my_deck": "A", "opp_deck": "B", "result": ""},          # excluded
        {"my_deck": "A", "opp_deck": "B", "result": "win"},
    ]
    mu = calibrate.aggregate_matchups(matches)[("A", "B")]
    assert mu["total"] == 3, mu          # 2 wins + 1 loss, not 6
    assert mu["wins"] == 2 and mu["losses"] == 1, mu
    # the real WR is now 66.7%, not 2/6 = 33.3% with draws folded into losses
    assert round(mu["wins"] / mu["total"] * 100, 1) == 66.7


def test_playdraw_only_counts_decided():
    matches = [
        {"my_deck": "A", "opp_deck": "B", "result": "win", "play_draw": "play"},
        {"my_deck": "A", "opp_deck": "B", "result": "draw", "play_draw": "play"},  # excluded
    ]
    mu = calibrate.aggregate_matchups(matches)[("A", "B")]
    assert mu["play_total"] == 1 and mu["play_wins"] == 1, mu


def test_get_sim_prediction_uses_real_apls():
    if not _HAVE_SIM:
        print("  skip test_get_sim_prediction_uses_real_apls (mtg-sim not found)")
        return
    import matchup_gauntlet as mg
    import engine.match_engine as me

    # Pick a real modern deck that has its own APL file.
    deck_file = next((f for f in (_SIM / "decks").glob("*modern*.txt")
                      if (_SIM / "apl" / f"{f.stem.replace('_modern','')}.py").exists()
                      or (_SIM / "apl" / f"{f.stem}_match.py").exists()), None)
    if deck_file is None:
        deck_file = next((_SIM / "decks").glob("amulet_titan*.txt"), None)
    assert deck_file is not None, "no modern deck found to test"
    name = deck_file.stem.replace("_modern", "").replace("_", " ").title()

    class _Fake:
        def win_rate_a(self):
            return 0.55
    real_run = me.run_match_set
    me.run_match_set = lambda *a, **k: _Fake()
    orig_root = calibrate.SIM_ROOT
    try:
        calibrate.SIM_ROOT = _SIM
        out = calibrate.get_sim_prediction(name, name, "modern", n_games=2)
    finally:
        me.run_match_set = real_run
        calibrate.SIM_ROOT = orig_root

    assert out["status"] == "ok", out
    # The APL class/source must be recorded, and must match what the gauntlet
    # resolves for the same deck -- not GenericMatchAPL on both sides.
    slug = calibrate._deck_slug(name)
    expected_cls = type(mg.load_apl_for_deck(slug, "modern")[0]).__name__
    assert out["apl_a"] == expected_cls, (out, expected_cls)
    assert out["apl_a_source"] == mg.load_apl_for_deck(slug, "modern")[1], out
    assert "apl_b_source" in out, out


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"test_calibrate_apls: OK ({len(fns)} tests)")


if __name__ == "__main__":
    _run_all()
