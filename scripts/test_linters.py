"""Tests for #20: the RMW, cache-key and spec-reference linters catch the bug
shapes they document (and don't over-report).

Run: python -I scripts/test_linters.py   (from repo root)

Loads the hyphenated linter modules by path and exercises their detection
functions on in-memory fixtures matching the issue's failure scenarios.
"""
import ast
import importlib.util
import sys
import tempfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent


def _load(stem, name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / stem)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


rmw = _load("lint-rmw-pattern.py", "lint_rmw")
ck = _load("lint-cache-keys.py", "lint_ck")
sr = _load("lint-spec-references.py", "lint_sr")


def _rmw_findings(src):
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(src)
        p = Path(f.name)
    try:
        return rmw.check_file(p)
    finally:
        p.unlink(missing_ok=True)


# ---- RMW linter ----------------------------------------------------------

def test_rmw_catches_constant_path():
    # open(MATRIX) read + open(MATRIX,'w') write -- path held in a constant.
    src = (
        "import json\n"
        "MATRIX = 'data/m.json'\n"
        "def f():\n"
        "    m = json.load(open(MATRIX))\n"
        "    m['x'] = 1\n"
        "    json.dump(m, open(MATRIX, 'w'))\n"
    )
    f = _rmw_findings(src)
    assert any(x["path"] == "MATRIX" for x in f), f


def test_rmw_catches_pathlib_read_write_pair():
    src = (
        "import json\n"
        "def f(P):\n"
        "    m = json.loads(P.read_text())\n"
        "    m['x'] = 1\n"
        "    P.write_text(json.dumps(m))\n"
    )
    f = _rmw_findings(src)
    assert any(x["path"] == "P" for x in f), f


def test_rmw_still_catches_string_literal():
    src = (
        "import json\n"
        "def f():\n"
        "    m = json.load(open('a.json'))\n"
        "    json.dump(m, open('a.json', 'w'))\n"
    )
    assert _rmw_findings(src), "literal RMW no longer detected"


def test_rmw_os_replace_on_different_file_does_not_exempt():
    # os.replace targets OTHER, but the RMW is on MATRIX -> still flagged.
    src = (
        "import json, os\n"
        "def f():\n"
        "    m = json.load(open('MATRIX.json'))\n"
        "    json.dump(m, open('MATRIX.json', 'w'))\n"
        "    os.replace('tmp', 'OTHER.json')\n"
    )
    f = _rmw_findings(src)
    assert any(x["path"] == "MATRIX.json" for x in f), f


def test_rmw_os_replace_on_same_file_exempts():
    # Atomic write to the SAME path -> no finding.
    src = (
        "import json, os\n"
        "def f():\n"
        "    m = json.load(open('a.json'))\n"
        "    json.dump(m, open('tmp', 'w'))\n"
        "    os.replace('tmp', 'a.json')\n"
    )
    # 'a.json' is read + ... written? only 'tmp' is opened 'w'. read={a.json},
    # write={tmp}; no overlap -> clean. And if someone wrote a.json directly,
    # os.replace(_, 'a.json') would exempt it.
    assert not _rmw_findings(src), "safe atomic rename wrongly flagged"


def test_rmw_allowlist_suppresses():
    src = (
        "import json\n"
        "def f():\n"
        "    # drift-detect:rmw-ok reason=\"single-writer\"\n"
        "    m = json.load(open('a.json'))\n"
        "    json.dump(m, open('a.json', 'w'))\n"
    )
    assert not _rmw_findings(src)


# ---- cache-key linter ----------------------------------------------------

def _ck_missing(src):
    tree = ast.parse(src)
    func = next(n for n in ast.walk(tree)
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)))
    params = ({x.arg for x in func.args.args + func.args.posonlyargs + func.args.kwonlyargs}
              & ck.HEURISTIC_PARAMS)
    return params - ck._cache_path_names(func)


def test_ck_catches_identity_param_used_in_sim_but_not_in_path():
    # The documented collision: deck+seed go to simulate(), path keys on opp only.
    src = (
        "def run_and_cache(deck, opp, seed):\n"
        "    r = simulate(deck, opp, seed)\n"
        "    open(f'data/cache/{opp}.json', 'w').write(str(r))\n"
    )
    missing = _ck_missing(src)
    assert "deck" in missing and "seed" in missing and "opp" not in missing, missing


def test_ck_considers_keyword_only_params():
    src = (
        "def g(deck, *, seed, n):\n"
        "    p = f'c/{deck}.json'\n"
        "    p_obj = p\n"
        "    open(p, 'w').write('x')\n"
    )
    tree = ast.parse(src)
    func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
    params = {x.arg for x in func.args.args + func.args.kwonlyargs} & ck.HEURISTIC_PARAMS
    assert "seed" in params and "n" in params, "kwonly params not collected"
    missing = params - ck._cache_path_names(func)
    assert "seed" in missing and "n" in missing and "deck" not in missing, missing


def test_ck_path_from_assigned_variable_counts():
    # p = f'...{opp}...'; p.write_text(...) -> opp is in the path.
    src = (
        "def h(opp):\n"
        "    p = make_path(f'cache/{opp}.json')\n"
        "    p.write_text('x')\n"
    )
    tree = ast.parse(src)
    func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
    assert "opp" in ck._cache_path_names(func)


# ---- spec-reference linter ----------------------------------------------

def test_sr_regex_stops_at_whitespace():
    line = "run python scripts/lint-rmw-pattern.py then fix calibrate.py"
    matches = [m.group(1) for m in sr.PYTHON_SCRIPT_RE.finditer(line)]
    assert matches == ["scripts/lint-rmw-pattern.py"], matches


def test_sr_regex_still_matches_plain_ref():
    line = "python3 agents/scripts/auto_pipeline.py"
    matches = [m.group(1) for m in sr.PYTHON_SCRIPT_RE.finditer(line)]
    assert matches == ["agents/scripts/auto_pipeline.py"], matches


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"test_linters: OK ({len(fns)} tests)")


if __name__ == "__main__":
    _run_all()
