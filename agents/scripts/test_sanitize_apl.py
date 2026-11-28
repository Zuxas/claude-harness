"""Tests for #2: slug allowlist + banned-code rejection + out-of-process smoke.

Run: python -I agents/scripts/test_sanitize_apl.py   (from repo root)
No pytest/framework; asserts + a __main__ driver, like the other harness tests.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import auto_pipeline as ap


def test_safe_slug_accepts_real_names():
    assert ap._safe_slug("Izzet Prowess") == "izzet_prowess"
    assert ap._safe_slug("Mono-Green Landfall") == "mono_green_landfall"
    assert ap._safe_slug("Urza's Saga") == "urzas_saga"
    assert ap._safe_slug("4-Color Control") == "4_color_control"


def test_safe_slug_rejects_path_traversal():
    for hostile in ["../../x", "../etc/passwd", "a/b", r"a\b"]:
        try:
            ap._safe_slug(hostile)
        except ValueError:
            continue
        raise AssertionError(f"traversal name not rejected: {hostile!r}")


def test_safe_slug_rejects_shell_and_overlong():
    for hostile in ["x; rm -rf ~", "$(whoami)", "a`id`", "x" * 65, "", "   "]:
        try:
            ap._safe_slug(hostile)
        except ValueError:
            continue
        raise AssertionError(f"not rejected: {hostile!r}")


def test_reject_bad_code_blocks_banned_imports():
    for payload in [
        "import os\nx = 1\n",
        "import subprocess as sp\n",
        "from socket import socket\n",
        "from os.path import join\n",
        "import shutil\n",
    ]:
        try:
            ap._reject_bad_code(payload)
        except ValueError:
            continue
        raise AssertionError(f"banned import not rejected: {payload!r}")


def test_reject_bad_code_blocks_eval_exec_open():
    for payload in [
        "eval('1+1')\n",
        "exec('x=1')\n",
        "open('/etc/passwd')\n",
        "__import__('os')\n",
    ]:
        try:
            ap._reject_bad_code(payload)
        except ValueError:
            continue
        raise AssertionError(f"banned call not rejected: {payload!r}")


def test_reject_bad_code_blocks_syntax_error():
    try:
        ap._reject_bad_code("def f(:\n")
    except SyntaxError:
        return
    raise AssertionError("syntax error not raised")


def test_reject_bad_code_allows_legit_apl():
    legit = (
        "from data.card import Card, Tag\n"
        "from apl.base_apl import BaseAPL\n\n"
        "class BurnAPL(BaseAPL):\n"
        "    name = 'Burn'\n"
        "    def keep(self, hand, mulligans, on_play):\n"
        "        return len([c for c in hand if c.is_land()]) >= 2\n"
        "    def main_phase(self, gs):\n"
        "        for c in gs.hand():\n"
        "            if c.has(Tag.INSTANT):\n"
        "                gs.cast_spell(c)\n"
    )
    ap._reject_bad_code(legit)  # must not raise


def test_save_apl_code_rejects_hostile_slug(tmp_root=None):
    # A hostile deck name never reaches the filesystem: _safe_slug raises before
    # any path is built.
    try:
        ap._save_apl_code("../../pwned", "x = 1\n")
    except ValueError:
        return
    raise AssertionError("hostile slug reached _save_apl_code write path")


def test_save_apl_code_rejects_banned_payload(monkeypatch=None):
    # A clean name but hostile generated code: rejected before write. Point the
    # cache dir at a temp location so a regression that DID write is visible.
    import tempfile
    real_root = ap.SIM_ROOT
    try:
        ap.SIM_ROOT = Path(tempfile.mkdtemp())
        try:
            ap._save_apl_code("Temp Test Deck", "import os\nos.system('echo pwned')\n")
        except ValueError:
            # nothing should have been written
            assert not list((ap.SIM_ROOT / "apl" / "auto_apls").glob("temp_test_deck.py")), \
                "rejected code was still written"
            return
        raise AssertionError("banned payload was saved")
    finally:
        ap.SIM_ROOT = real_root


def test_smoke_test_uses_subprocess_not_import():
    # The smoke path must shell out to the runner, never importlib the APL into
    # this process. Assert on the source so a refactor back to in-process import
    # fails here.
    src = Path(ap.__file__).read_text()
    body = src.split("def _smoke_test_apl", 1)[1].split("\ndef ", 1)[0]
    assert "subprocess.run" in body, "smoke test no longer shells out"
    assert "import_module" not in body and "importlib" not in body, \
        "smoke test still imports generated code in-process"
    assert ap._SMOKE_RUNNER.name == "_apl_smoke_runner.py"
    assert ap._SMOKE_RUNNER.exists(), "runner script missing"


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"test_sanitize_apl: OK ({len(fns)} tests)")


if __name__ == "__main__":
    _run_all()
