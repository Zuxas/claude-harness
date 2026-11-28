"""Run every standalone `_run_all()`-style test suite as a subprocess, so one
`pytest` invocation (and CI) exercises the whole harness test corpus (#8).

The suites under scripts/ and agents/scripts/ predate pytest: they define
test_* functions plus a `__main__` that runs them, and a few take helper
default-args pytest would misread as fixtures. Rather than rewrite 15 files,
each is run as `python <file>` and asserted to exit 0.
"""
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

# Non-recursive globs: scripts/test_*.py and agents/scripts/test_*.py, NOT the
# pytest files under scripts/tests/.
SUITES = sorted(
    [p for p in (ROOT / "scripts").glob("test_*.py")]
    + [p for p in (ROOT / "agents" / "scripts").glob("test_*.py")]
)

# Suites that can only run on the owner's box (e.g. a module that touches the
# hardcoded workspace at import). Empty now that roots are derived (#1) --
# test_playbook_generator imports cleanly again.
_WORKSPACE_ONLY: set = set()


def test_suites_discovered():
    assert SUITES, "no standalone test suites found"


@pytest.mark.parametrize("suite", SUITES, ids=[p.name for p in SUITES])
def test_standalone_suite(suite):
    if suite.name in _WORKSPACE_ONLY:
        pytest.skip(f"{suite.name} imports a module bound to the hardcoded "
                    f"workspace path; runnable only on the owner's box until #1")
    r = subprocess.run([sys.executable, str(suite)], cwd=str(ROOT),
                       capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, (
        f"{suite.name} exited {r.returncode}\n--- stdout ---\n{r.stdout}\n"
        f"--- stderr ---\n{r.stderr}")
