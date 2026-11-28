"""Runs the on-disk linter fixtures and asserts the pass/fail each documents (#8).

These fixtures existed under scripts/tests/{cache_key,rmw,spec_ref}_fixtures/ but
nothing executed them, so the linters could regress silently. Each fixture's
module docstring / filename states its expected finding count; this pins them.
"""
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
FIX = ROOT / "scripts" / "tests"


def _load(stem, name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / stem)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


rmw = _load("lint-rmw-pattern.py", "lint_rmw_fx")
ck = _load("lint-cache-keys.py", "lint_ck_fx")
sr = _load("lint-spec-references.py", "lint_sr_fx")


@pytest.mark.parametrize("fname, expected", [
    ("fixture_rmw_unsafe.py", 1),
    ("fixture_different_paths.py", 0),
    ("fixture_write_only.py", 0),
    ("fixture_atomic_safe.py", 0),
    ("fixture_allowlisted.py", 0),
])
def test_rmw_fixtures(fname, expected):
    findings = rmw.check_file(FIX / "rmw_fixtures" / fname)
    assert len(findings) == expected, findings


@pytest.mark.parametrize("fname, expected", [
    ("fixture_good_cache.py", 0),
    ("fixture_partial_key.py", 1),
    ("fixture_allowlisted.py", 0),
])
def test_cache_key_fixtures(fname, expected):
    d = FIX / "cache_key_fixtures" / fname
    findings = ck.analyze_file(d, scan_root=d.parent)
    assert len(findings) == expected, findings


@pytest.mark.parametrize("fname, errors, infos", [
    ("fixture-fictional-script.md", 1, 0),
    ("fixture-good-spec.md", 0, 0),
    ("fixture-help-preflight.md", 0, 1),
])
def test_spec_ref_fixtures(fname, errors, infos):
    findings = sr.check_spec(FIX / "spec_ref_fixtures" / fname)
    assert len([f for f in findings if f["level"] == "ERROR"]) == errors, findings
    assert len([f for f in findings if f["level"] == "INFO"]) == infos, findings
