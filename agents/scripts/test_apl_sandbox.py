"""Tests for apl_sandbox -- the shared containment gate (#2, #65).

Pure: no mtg-sim, no network, no secrets. Runnable in CI and via
`python agents/scripts/test_apl_sandbox.py`.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import apl_sandbox as s


def test_reject_blocks_disallowed_imports():
    for payload in [
        "import os\n", "import subprocess as sp\n", "from socket import socket\n",
        "from os.path import join\n", "import shutil\n", "import requests\n",
        "import numpy as np\n", "from ..base import Thing\n", "import ctypes\n",
    ]:
        try:
            s.reject_bad_code(payload)
        except (ValueError, SyntaxError):
            continue
        raise AssertionError(f"disallowed import not rejected: {payload!r}")


def test_reject_blocks_eval_exec_open():
    for payload in [
        "x = eval('1+1')\n", "exec('import os')\n", "open('/etc/passwd')\n",
        "__import__('os')\n", "compile('1', '<s>', 'eval')\n",
    ]:
        try:
            s.reject_bad_code(payload)
        except (ValueError, SyntaxError):
            continue
        raise AssertionError(f"banned call not rejected: {payload!r}")


def test_reject_accepts_clean_first_party_code():
    good = (
        "from apl.match_apl import MatchAPL\n"
        "from data.card import Card\n"
        "import random\n"
        "class FooMatchAPL(MatchAPL):\n"
        "    def main_phase_match(self, gs, opp):\n"
        "        return None\n"
    )
    s.reject_bad_code(good)  # must not raise


def test_reject_rejects_syntax_error():
    try:
        s.reject_bad_code("def broken(:\n    pass\n")
    except SyntaxError:
        return
    raise AssertionError("syntax error not raised")


def test_child_env_drops_secrets_keeps_path():
    os.environ["ANTHROPIC_API_KEY"] = "sk-secret"
    os.environ["GH_TOKEN"] = "ghp_secret"
    try:
        env = s.child_env()
        assert "ANTHROPIC_API_KEY" not in env, "secret leaked into child env"
        assert "GH_TOKEN" not in env, "secret leaked into child env"
        if "PATH" in os.environ:
            assert "PATH" in env, "PATH should pass through"
    finally:
        os.environ.pop("ANTHROPIC_API_KEY", None)
        os.environ.pop("GH_TOKEN", None)


def test_run_apl_subprocess_fails_closed_on_bad_module():
    # A module that can't import makes the -I child exit without a verdict.
    # run_apl_subprocess must return a non-"ran" status, never raise, so a
    # caller gating on status=="ran" can't be fooled into passing it.
    out = s.run_apl_subprocess("C:/nonexistent_sim", "definitely_not_a_module",
                               "C:/nope.txt", 1, 1, mode="goldfish", timeout=30)
    assert isinstance(out, dict)
    assert out.get("status") != "ran", f"bad module should not report ran: {out}"


def test_smoke_python_prefers_existing_override():
    os.environ["MTG_SMOKE_PYTHON"] = sys.executable  # exists
    try:
        assert s._smoke_python("C:/whatever/no/venv") == sys.executable
    finally:
        os.environ.pop("MTG_SMOKE_PYTHON", None)


def test_smoke_python_ignores_missing_override_and_falls_back():
    os.environ["MTG_SMOKE_PYTHON"] = "C:/definitely/not/here/python.exe"
    try:
        assert s._smoke_python("C:/no/venv/here") == sys.executable
    finally:
        os.environ.pop("MTG_SMOKE_PYTHON", None)


def test_smoke_python_finds_sibling_venv():
    import shutil
    import tempfile
    os.environ.pop("MTG_SMOKE_PYTHON", None)
    d = tempfile.mkdtemp()
    try:
        # create both conventional venv-python locations so this passes on any OS
        for rel in ("Scripts/python.exe", "bin/python"):
            p = Path(d) / ".venv" / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("")
        got = s._smoke_python(d)
        assert ".venv" in got and got != sys.executable, got
    finally:
        shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"  {name}: OK")
    print("test_apl_sandbox: OK")
