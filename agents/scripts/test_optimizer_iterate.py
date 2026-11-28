"""Tests for #15: iterate on the accepted patch, keep the winner on disk, and
treat a 0-win patch as WORSE instead of crashing.

Run: python -I agents/scripts/test_optimizer_iterate.py   (from repo root)

Items 1 (refinement) and 2 (save-to-disk) need run_optimizer's loop, which
normally calls into mtg-sim. mtg-sim isn't importable here, so the sim seams
(analyze_apl / parse_patches / apply_patch / _paired_runs / run_goldfish /
load_* / find_*) are stubbed and the loop is driven for real -- this tests the
BEHAVIOR (iteration 2 analyzes iteration 1's accepted source; the opt file lands
on disk), not just the source text. Item 3 is a pure paired_verdict check.
"""
import sys
import types
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import apl_optimizer as opt


def test_zero_win_patch_is_worse_not_crash():
    # A patch that wins 0 games -> patched_wr=0, all kills None. Must be WORSE
    # (win-rate dropped) and must not raise on the all-None kill arrays.
    base_kills = [6.0, 6.1, 5.9, 6.0, 6.2]
    patched_kills = [None] * 5
    verdict = opt.paired_verdict(base_kills, patched_kills, base_wr=0.5, patched_wr=0.0)
    assert verdict == "worse", verdict


def _install_stubs(tmp, seen_sources, analyzed_counter):
    """Stub every mtg-sim seam run_optimizer touches. _paired_runs returns a
    clean improvement (base mean 6.0, candidate 5.0, SE 0) so each iteration's
    patch is accepted."""
    sim_root = tmp / "sim"
    harness_root = tmp / "harness"
    (sim_root / "apl").mkdir(parents=True)
    (harness_root / "agents" / "temp").mkdir(parents=True)
    (harness_root / "knowledge" / "mtg").mkdir(parents=True)
    opt.SIM_ROOT = sim_root
    opt.HARNESS_ROOT = harness_root

    apl_file = sim_root / "apl" / "test_deck_modern_match.py"
    apl_file.write_text("# ORIGINAL APL SOURCE\n", encoding="utf-8")
    deck_file = sim_root / "decks" / "test_deck.txt"
    deck_file.parent.mkdir(parents=True, exist_ok=True)
    deck_file.write_text("60 Card\n", encoding="utf-8")

    opt.find_apl_file = lambda deck, fmt="modern": apl_file
    opt.find_deck_file = lambda deck: deck_file
    opt.find_missing_cards = lambda df, src: []
    # Tag by path so the original (slow) is distinguishable from every candidate
    # (fast) -- the reconfirm step compares original vs best, so they must differ.
    opt.load_apl_from_file = lambda path: ("ORIG" if Path(path) == apl_file else "CAND")
    opt.run_goldfish = lambda apl, deck, n, **kw: {
        "win_rate": 0.5, "avg_kill": 6.0, "fastest": 4, "games": n, "time": 1.0}

    def paired(apl, mainboard, seeds, n_per_seed):
        if apl == "ORIG":
            return ([6.0] * len(seeds), 0.5)   # baseline: slower
        return ([5.0] * len(seeds), 0.6)       # candidate: faster -> improved
    opt._paired_runs = paired

    def fake_analyze(deck_name, apl_source, baseline, missing, use_claude, model):
        seen_sources.append(apl_source)
        analyzed_counter[0] += 1
        return f"ANALYSIS-{analyzed_counter[0]}"
    opt.analyze_apl = fake_analyze

    opt.parse_patches = lambda analysis: [{
        "issue": f"fix-{analysis}", "impact": "HIGH", "type": "replace",
        "after": "OLD", "code": "NEW", "find": "OLD"}]
    # Each accepted patch appends a unique marker, so current_source grows and
    # iteration 2's analyzed source differs from iteration 1's.
    opt.apply_patch = lambda source, patch: source + f"\n# {patch['issue']}\n"

    # data.deck.load_deck_from_file is imported inside run_optimizer.
    data_mod = types.ModuleType("data")
    deck_mod = types.ModuleType("data.deck")
    deck_mod.load_deck_from_file = lambda p: (["card"] * 60, [])
    data_mod.deck = deck_mod
    sys.modules["data"] = data_mod
    sys.modules["data.deck"] = deck_mod
    return apl_file


def test_iteration_refines_accepted_source_and_saves():
    saved = {k: getattr(opt, k) for k in
             ("SIM_ROOT", "HARNESS_ROOT", "find_apl_file", "find_deck_file",
              "find_missing_cards", "load_apl_from_file", "run_goldfish",
              "_paired_runs", "analyze_apl", "parse_patches", "apply_patch")}
    saved_mods = {k: sys.modules.get(k) for k in ("data", "data.deck")}
    try:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            seen_sources, counter = [], [0]
            apl_file = _install_stubs(tmp, seen_sources, counter)

            opt.run_optimizer("Test Deck", "modern", n_games=50, iterations=2)

            # Item 1: iteration 2 analyzed the source ACCEPTED in iteration 1,
            # not the original. seen_sources[0] is the original; seen_sources[1]
            # must carry iteration 1's patch marker.
            assert len(seen_sources) >= 2, f"only {len(seen_sources)} iterations ran"
            assert seen_sources[0] == "# ORIGINAL APL SOURCE\n"
            assert "fix-ANALYSIS-1" in seen_sources[1], \
                "iteration 2 did not analyze iteration 1's accepted source"
            assert seen_sources[1] != seen_sources[0]

            # Item 2: the optimized APL is on disk after the run.
            opt_files = list((opt.SIM_ROOT / "apl").glob("test_deck_modern_match_opt_*.py"))
            assert opt_files, "no optimized APL saved to disk"
            body = opt_files[0].read_text()
            assert "fix-ANALYSIS-1" in body, "saved APL missing the accepted patch"
    finally:
        for k, v in saved.items():
            setattr(opt, k, v)
        for k, v in saved_mods.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"test_optimizer_iterate: OK ({len(fns)} tests)")


if __name__ == "__main__":
    _run_all()
