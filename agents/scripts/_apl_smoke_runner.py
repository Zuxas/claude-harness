"""Out-of-process smoke runner for one auto-generated APL (#2).

Invoked by auto_pipeline._smoke_test_apl as:

    python -I _apl_smoke_runner.py <sim_root> <module> <deck_path> <n> <seed>

The generated APL is imported and executed HERE, in a separate interpreter with
a timeout, never inside the orchestrator -- so hostile or broken model output
can't touch the orchestrator's tokens, git, or the rest of the filesystem. One
JSON object is printed to stdout; anything else (crash, timeout) is the caller's
signal that the APL failed the gate.

Run with -I: the module path is set explicitly, so neither the cwd nor this
script's own directory is on sys.path, and planted modules next to the untrusted
code can't be imported ahead of the real engine.
"""
import json
import sys


def main():
    if len(sys.argv) != 6:
        print(json.dumps({"status": "bad_args"}))
        return
    sim_root, mod_name, deck_path, n, seed = sys.argv[1:6]
    sys.path.insert(0, sim_root)

    import importlib
    mod = importlib.import_module(mod_name)

    cls = cls_name = None
    for attr_name in dir(mod):
        obj = getattr(mod, attr_name)
        if isinstance(obj, type) and attr_name.endswith("APL") and attr_name != "BaseAPL":
            cls, cls_name = obj, attr_name
            break
    if cls is None:
        print(json.dumps({"status": "no_apl_class"}))
        return

    from data.deck import load_deck_from_file
    from engine.runner import run_simulation

    main_deck, _ = load_deck_from_file(deck_path)
    apl = cls()
    if getattr(apl, "name", None) is None:
        apl.name = mod_name
    result = run_simulation(apl, main_deck, n=int(n), verbose_first=0, seed=int(seed))
    akt = result.avg_kill_turn()
    print(json.dumps({
        "status": "ran",
        "win_rate": result.win_rate(),
        "avg_kill_turn": akt,
        "class_name": cls_name,
    }))


if __name__ == "__main__":
    main()
