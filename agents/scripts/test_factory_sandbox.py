"""Behavioral regression tests for #65: gemma_apl_factory must gate model code
and run it OUT OF PROCESS -- never import it into this (secret-holding) process.

No mtg-sim needed: run_apl_subprocess is stubbed, so the sim never runs; we only
assert the factory's control flow (reject-before-execute, no in-process import,
fail-closed). Runnable in CI and via `python agents/scripts/test_factory_sandbox.py`.
"""
import atexit
import importlib
import os
import shutil
import sys
import tempfile
from pathlib import Path

# SIM_ROOT is resolved at factory import time, and validate writes a temp module
# under SIM_ROOT/apl. Point it at a throwaway dir with apl/ so the write works
# without a real mtg-sim checkout.
_TMP = tempfile.mkdtemp(prefix="factory_sbx_")
(Path(_TMP) / "apl").mkdir(parents=True, exist_ok=True)
os.environ["MTG_SIM_ROOT"] = _TMP
os.environ.setdefault("HARNESS_ROOT", str(Path(__file__).resolve().parents[2]))
atexit.register(lambda: shutil.rmtree(_TMP, ignore_errors=True))

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gemma_apl_factory as f

CLEAN = (
    "from apl.match_apl import MatchAPL\n"
    "class FooMatchAPL(MatchAPL):\n"
    "    def main_phase_match(self, gs, opp):\n"
    "        return None\n"
)


def _recorder(ret):
    def fake(*a, **k):
        fake.calls.append((a, k))
        return ret
    fake.calls = []
    return fake


def _run(code, ret={"status": "ran", "win_rate": 0.5}):
    rec = _recorder(ret)
    orig = f.run_apl_subprocess
    f.run_apl_subprocess = rec
    try:
        ok, msg = f.validate_apl_code(code, "deck.txt", "foo", "modern")
    finally:
        f.run_apl_subprocess = orig
    return ok, msg, rec


def test_unsafe_import_rejected_before_execution():
    ok, msg, rec = _run("import os\nx = 1\n")
    assert ok is False
    assert "unsafe" in msg.lower() or "rejected" in msg.lower(), msg
    assert rec.calls == [], "the sandbox subprocess must NOT run for unsafe code"


def test_banned_call_rejected_before_execution():
    ok, msg, rec = _run("x = eval('2+2')\n")
    assert ok is False
    assert rec.calls == [], "eval() must be rejected before any execution"


def test_syntax_error_rejected():
    ok, msg, rec = _run("def broken(:\n    pass\n")
    assert ok is False and "Syntax" in msg, msg
    assert rec.calls == []


def test_clean_code_runs_out_of_process_never_imported():
    # Guard: if the factory ever import_module's the model, fail loudly.
    orig_imp = importlib.import_module

    def guard(name, *a, **k):
        if name == "apl._temp_generated":
            raise AssertionError("model code imported IN-PROCESS -- must be sandboxed")
        return orig_imp(name, *a, **k)

    importlib.import_module = guard
    try:
        ok, msg, rec = _run(CLEAN, {"status": "ran", "win_rate": 0.55})
    finally:
        importlib.import_module = orig_imp
    assert ok is True, msg
    assert len(rec.calls) == 1, "validate must run the smoke exactly once"
    args, kwargs = rec.calls[0]
    assert "apl._temp_generated" in args, args
    assert kwargs.get("mode") == "match", kwargs


def test_fail_closed_on_non_ran_status():
    for ret in ({"status": "timeout"}, {"status": "no_apl_class"},
                {"status": "subprocess_error", "error": "x"},
                {"status": "no_output"}):
        ok, msg, rec = _run(CLEAN, ret)
        assert ok is False, f"{ret} must fail closed, got {msg}"


def test_degenerate_win_rates_rejected():
    for wr in (0.0, 1.0):
        ok, msg, rec = _run(CLEAN, {"status": "ran", "win_rate": wr})
        assert ok is False, f"win_rate {wr} should be rejected"


def test_valid_win_rate_passes():
    ok, msg, rec = _run(CLEAN, {"status": "ran", "win_rate": 0.52})
    assert ok is True, msg


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"  {name}: OK")
    print("test_factory_sandbox: OK")
