"""_apl_smoke_runner.py -- sandboxed subprocess for the ARL APL smoke gate.

SECURITY ROLE: auto_pipeline._smoke_test_apl must IMPORT + EXECUTE model-generated
APL code (apl/auto_apls/<slug>.py). The generation prompt can carry untrusted
scraped card oracle text, so a prompt-injection could plant hostile code that runs
at import/sim time. Running that in-process is an RCE/key-exfil path because the
nightly ARL process holds API keys in os.environ.

This runner is executed as a SEPARATE PROCESS with a SECRET-STRIPPED environment
(see auto_pipeline._stripped_env) and under a wall-clock TIMEOUT, so even if the
static deny-list (_scan_generated_code) is bypassed, the executing code sees no
API keys/tokens in its environment and cannot hang the loop.

It does exactly what the old in-process smoke body did -- import the module, find
the APL class, load the deck, run N seeded goldfish games -- and writes the raw
metrics as JSON to the --out file. All semantic gating (win-rate / kill-turn
thresholds) stays in the parent, so behaviour for benign code is unchanged.

Contract (stdout is noisy: CardDB prints on import), so results go to --out ONLY:
  ok           -> {"status":"ok","win_rate":f,"avg_kill_turn":f|null,
                   "games_completed":n,"class_name":s}
  no_apl_class -> {"status":"no_apl_class"}
  crashed      -> {"status":"crashed","error":s}   (any exception here)
"""
import sys
import os
import json
import argparse
import importlib


def _emit(out_path, payload):
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sim-root", required=True)
    ap.add_argument("--mod-name", required=True)
    ap.add_argument("--deck-path", required=True)
    ap.add_argument("--deck-name", required=True)
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    try:
        if args.sim_root not in sys.path:
            sys.path.insert(0, args.sim_root)

        # Fresh process -> no stale module, no reload needed.
        importlib.import_module(args.mod_name)
        mod = sys.modules[args.mod_name]

        cls = None
        cls_name = None
        for attr_name in dir(mod):
            obj = getattr(mod, attr_name)
            if isinstance(obj, type) and attr_name.endswith("APL") and attr_name != "BaseAPL":
                cls = obj
                cls_name = attr_name
                break
        if cls is None:
            _emit(args.out, {"status": "no_apl_class"})
            return

        from data.deck import load_deck_from_file
        from engine.runner import run_simulation
        main_deck, _ = load_deck_from_file(args.deck_path)
        apl_instance = cls()
        if not hasattr(apl_instance, "name") or apl_instance.name is None:
            apl_instance.name = args.deck_name
        result = run_simulation(apl_instance, main_deck, n=args.n,
                                verbose_first=0, seed=args.seed)

        win_rate = result.win_rate()
        avg_kt = result.avg_kill_turn()  # None if 0 wins
        _emit(args.out, {
            "status": "ok",
            "win_rate": win_rate,
            "avg_kill_turn": avg_kt,
            "games_completed": args.n,
            "class_name": cls_name,
        })
    except Exception as e:  # noqa: BLE001 -- report any failure as crashed
        try:
            _emit(args.out, {"status": "crashed", "error": str(e)[:200]})
        except Exception:
            # Last resort: signal via exit code; parent maps missing/bad file to crashed.
            sys.exit(3)


if __name__ == "__main__":
    main()
