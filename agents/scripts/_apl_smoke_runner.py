"""Out-of-process smoke runner for one auto-generated APL (#2, #65).

Invoked (by apl_sandbox.run_apl_subprocess) as:

    python -I _apl_smoke_runner.py <sim_root> <module> <deck_path> <n> <seed> [mode]

mode is "goldfish" (default, back-compat) or "match":
  - goldfish: run_simulation -> lethal win_rate + avg_kill_turn.
  - match:    run_match_set vs GenericMatchAPL (self-play deck) -> win_rate.

The generated APL is imported and executed HERE, in a separate interpreter with
a timeout, never inside the orchestrator -- so hostile or broken model output
can't touch the orchestrator's tokens, git, or the rest of the filesystem. One
JSON object is printed to stdout; anything else (crash, timeout) is the caller's
signal that the APL failed the gate.

Run with -I: the module path is set explicitly, so neither the cwd nor this
script's own directory is on sys.path, and planted modules next to the untrusted
code can't be imported ahead of the real engine.
"""
import inspect
import json
import sys


def _find_apl_class(mod):
    """The concrete APL class defined in this module. Skips abstract bases
    (AwareMatchAPL etc. are abstract and can't be instantiated) and prefers a
    class actually defined here over an imported base/helper that also ends in
    'APL'. Without this, dir() order can hand back the abstract base class."""
    candidates = []
    for attr_name in dir(mod):
        obj = getattr(mod, attr_name)
        if (isinstance(obj, type) and attr_name.endswith("APL")
                and attr_name != "BaseAPL" and not inspect.isabstract(obj)):
            candidates.append((obj, attr_name))
    for obj, attr_name in candidates:  # prefer a class defined in THIS module
        if getattr(obj, "__module__", None) == getattr(mod, "__name__", None):
            return obj, attr_name
    return candidates[0] if candidates else (None, None)


def main():
    if len(sys.argv) not in (6, 7):
        print(json.dumps({"status": "bad_args"}))
        return
    sim_root, mod_name, deck_path, n, seed = sys.argv[1:6]
    mode = sys.argv[6] if len(sys.argv) == 7 else "goldfish"
    sys.path.insert(0, sim_root)

    import importlib
    mod = importlib.import_module(mod_name)

    cls, cls_name = _find_apl_class(mod)
    if cls is None:
        print(json.dumps({"status": "no_apl_class"}))
        return

    from data.deck import load_deck_from_file
    main_deck, _ = load_deck_from_file(deck_path)
    apl = cls()
    if getattr(apl, "name", None) is None:
        apl.name = mod_name

    if mode == "match":
        from engine.match_engine import run_match_set
        from apl.match_apl import GenericMatchAPL
        opp_deck, _sb = load_deck_from_file(deck_path)  # self-play deck vs Generic
        results = run_match_set(apl, main_deck, GenericMatchAPL(), opp_deck,
                                n=int(n), mix_play_draw=True)
        print(json.dumps({
            "status": "ran",
            "mode": "match",
            "win_rate": results.win_rate_a(),
            "class_name": cls_name,
        }))
        return

    from engine.runner import run_simulation
    result = run_simulation(apl, main_deck, n=int(n), verbose_first=0, seed=int(seed))
    akt = result.avg_kill_turn()
    print(json.dumps({
        "status": "ran",
        "mode": "goldfish",
        "win_rate": result.win_rate(),
        "avg_kill_turn": akt,
        "class_name": cls_name,
    }))


if __name__ == "__main__":
    main()
