"""Tests for #21: the pre-commit hook lints the STAGED tree, and lint-mtg-sim
accepts --root.

Run: python -I scripts/test_precommit_staged.py   (from repo root)

Drives real git in a temp repo. The decisive case: stage a broken registry, fix
it in the working tree WITHOUT re-staging, and commit -- the hook must block
(the staged version is what lands), which it can only do by linting the staged
tree, not the working tree. Needs git + bash.
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
LINT = SCRIPTS / "lint-mtg-sim.py"
TEMPLATE = SCRIPTS / "templates" / "mtg-sim-pre-commit.sh"

CLEAN_INIT = (
    'APL_REGISTRY = {\n'
    '    "ghostdeck": ("apl.ghost", "GhostAPL", "decks/ghost.txt"),\n'
    '}\n'
    'MATCH_APL_REGISTRY = {}\n'
)
BROKEN_INIT = (
    'APL_REGISTRY = {\n'
    '    "ghostdeck": ("apl.ghost", "GhostAPL", "decks/MISSING.txt"),\n'
    '}\n'
    'MATCH_APL_REGISTRY = {}\n'
)


def _git(repo, *args, check=True):
    return subprocess.run(["git", "-C", str(repo), *args],
                          capture_output=True, text=True, check=check)


def _make_repo(root: Path):
    (root / "apl").mkdir()
    (root / "data").mkdir()
    (root / "decks").mkdir()
    (root / "apl" / "__init__.py").write_text(CLEAN_INIT, encoding="utf-8")
    (root / "data" / "stub_decks.py").write_text("_DB_DECKS = {}\n", encoding="utf-8")
    (root / "decks" / "ghost.txt").write_text("60 Mountain\n", encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")  # no hook installed yet


def _install_hook(root: Path):
    # Copy the template, point LINT_SCRIPT at the real linter, make executable.
    text = TEMPLATE.read_text(encoding="utf-8")
    text = text.replace('LINT_SCRIPT="E:/vscode ai project/harness/scripts/lint-mtg-sim.py"',
                        f'LINT_SCRIPT="{LINT}"')
    hook = root / ".git" / "hooks" / "pre-commit"
    hook.write_text(text, encoding="utf-8")
    hook.chmod(0o755)


def test_lint_accepts_root():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _make_repo(root)
        # clean tree -> exit 0
        r = subprocess.run([sys.executable, "-I", str(LINT), "--root", str(root)],
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
        # break the registry on disk -> exit 2
        (root / "apl" / "__init__.py").write_text(BROKEN_INIT, encoding="utf-8")
        r = subprocess.run([sys.executable, "-I", str(LINT), "--root", str(root)],
                           capture_output=True, text=True)
        assert r.returncode == 2, r.stdout + r.stderr


def test_hook_blocks_staged_break_even_when_worktree_fixed():
    if not shutil.which("bash"):
        print("  skip test_hook_blocks_staged_break... (bash unavailable)")
        return
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _make_repo(root)
        _install_hook(root)

        # Stage a BROKEN registry, then FIX the working tree without re-staging.
        (root / "apl" / "__init__.py").write_text(BROKEN_INIT, encoding="utf-8")
        _git(root, "add", "apl/__init__.py")
        (root / "apl" / "__init__.py").write_text(CLEAN_INIT, encoding="utf-8")  # worktree fixed

        # Commit must be BLOCKED: the hook lints the staged (broken) tree.
        env = dict(os.environ, PATH=os.path.dirname(sys.executable) + os.pathsep + os.environ.get("PATH", ""))
        res = _git(root, "commit", "-m", "sneak broken staged", check=False)
        assert res.returncode != 0, "commit was NOT blocked (hook linted the working tree, not the index)"
        assert "BLOCKED" in (res.stdout + res.stderr), res.stdout + res.stderr

        # Only the initial commit exists.
        log = _git(root, "log", "--oneline").stdout.strip().splitlines()
        assert len(log) == 1, f"broken commit landed anyway: {log}"


def test_hook_allows_clean_staged_commit():
    if not shutil.which("bash"):
        print("  skip test_hook_allows_clean_staged_commit (bash unavailable)")
        return
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _make_repo(root)
        _install_hook(root)
        # A genuinely clean change to a lint-relevant file commits fine.
        (root / "decks" / "ghost.txt").write_text("60 Island\n", encoding="utf-8")
        _git(root, "add", "decks/ghost.txt")
        res = _git(root, "commit", "-m", "clean change", check=False)
        assert res.returncode == 0, res.stdout + res.stderr
        assert len(_git(root, "log", "--oneline").stdout.strip().splitlines()) == 2


def test_hook_blocks_when_staged_export_fails():
    # Fail-closed: if `git checkout-index` can't export the index, the hook must
    # ABORT (exit non-zero), not fall back to linting the (possibly clean)
    # working tree. git forces its own binary into a hook's PATH, so a shim can't
    # be injected via `git commit`; instead run the hook DIRECTLY with a git shim
    # that breaks only checkout-index and passes everything else through -- same
    # code path, deterministic failure.
    real_git = shutil.which("git")
    if not real_git or not shutil.which("bash"):
        print("  skip test_hook_blocks_when_staged_export_fails (git/bash unavailable)")
        return
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _make_repo(root)
        _install_hook(root)

        shimdir = root / "_shim"
        shimdir.mkdir()
        shim = shimdir / "git"
        shim.write_text(
            "#!/usr/bin/env bash\n"
            'if [ "$1" = "checkout-index" ]; then exit 1; fi\n'
            f'exec "{real_git}" "$@"\n', encoding="utf-8")
        shim.chmod(0o755)

        # Stage a lint-relevant file so the hook reaches the export step.
        (root / "decks" / "ghost.txt").write_text("60 Forest\n", encoding="utf-8")
        _git(root, "add", "decks/ghost.txt")

        env = dict(os.environ, PATH=str(shimdir) + os.pathsep + os.environ.get("PATH", ""))
        res = subprocess.run(["bash", str(root / ".git" / "hooks" / "pre-commit")],
                             cwd=str(root), capture_output=True, text=True, env=env)
        assert res.returncode != 0, "hook passed despite a failed staged export (fail-open!)"
        assert "fail-closed" in (res.stdout + res.stderr).lower(), res.stdout + res.stderr


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"test_precommit_staged: OK ({len(fns)} tests)")


if __name__ == "__main__":
    _run_all()
