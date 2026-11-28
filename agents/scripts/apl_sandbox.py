"""Shared containment boundary for model-generated APLs (#2, #65).

Single source of truth for the AST gate + the out-of-process smoke runner, so
every generated-APL path (auto_pipeline AND gemma_apl_factory) uses the SAME
boundary instead of its own copy. Before #65, gemma_apl_factory imported
model-written code in-process, ungated -- this module is what closes that gap.

What this is and is not: `python -I` + a scrubbed, secret-free env + a timeout
is a blast-radius reducer (the child can't read the orchestrator's tokens and
can't shadow the real engine via sys.path), NOT a kernel/OS sandbox. The child
still runs as the same OS user. An AST allowlist also can't catch every dynamic
reach. The real boundary is the declarative-APL migration (mtg-sim#124); until
then the pipeline stays operator-machine-only. See
specs/2026-11-28-generated-code-containment.md.
"""
import ast as _ast
import json
import os
import subprocess
import sys
from pathlib import Path

# Generated APLs are pure decision logic over the engine's own objects. They may
# import ONLY first-party engine/APL packages plus a few capability-safe stdlib
# modules; anything else is rejected. An allowlist, not a denylist: blocking
# known-dangerous names (os, subprocess, ...) is not a boundary -- an unlisted or
# obfuscated reach slips a denylist, so anything not explicitly approved is
# refused (#2, Tom review). Relative imports are rejected too.
_ALLOWED_IMPORT_ROOTS = frozenset({
    "data", "apl", "engine",                           # first-party, trusted
    "typing", "math", "random", "collections",         # capability-safe stdlib
    "itertools", "functools", "dataclasses", "enum",
})
# eval/exec/open/compile/__import__ are builtins, not imports, so the import
# allowlist can't see them; reject them by name too.
_BANNED_CALLS = frozenset({"eval", "exec", "compile", "__import__", "open"})

# The smoke subprocess gets a minimal environment: only what the interpreter
# needs. `python -I` controls sys.path and interpreter config but NOT os.environ,
# so without this the child would inherit every secret the orchestrator holds --
# ANTHROPIC_API_KEY, OAuth tokens, GH creds. Allowlist, so a newly-added secret
# env var isn't leaked by default.
_CHILD_ENV_KEEP = ("PATH", "SYSTEMROOT", "SystemRoot", "WINDIR", "TEMP", "TMP",
                   "TMPDIR", "LANG", "LC_ALL", "LC_CTYPE", "HOME", "HOMEPATH",
                   "HOMEDRIVE", "USERPROFILE", "PATHEXT", "COMSPEC")

SMOKE_RUNNER = Path(__file__).resolve().parent / "_apl_smoke_runner.py"
DEFAULT_SMOKE_TIMEOUT = 300  # seconds


def reject_bad_code(code):
    """Raise ValueError if generated APL code won't parse, imports anything
    outside the allowlist, or calls eval/exec/open/compile/__import__. Run this
    BEFORE the code is ever written to disk or executed, so hostile or broken
    model output is never persisted or imported (#2). ast.parse raises
    SyntaxError, which callers treat as a rejection too."""
    tree = _ast.parse(code)
    bad = []
    for node in _ast.walk(tree):
        if isinstance(node, _ast.Import):
            for a in node.names:
                if a.name.split(".")[0] not in _ALLOWED_IMPORT_ROOTS:
                    bad.append(f"import {a.name}")
        elif isinstance(node, _ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if node.level or root not in _ALLOWED_IMPORT_ROOTS:
                bad.append(f"from {'.' * node.level}{node.module or ''} import ...")
        elif isinstance(node, _ast.Call) and isinstance(node.func, _ast.Name):
            if node.func.id in _BANNED_CALLS:
                bad.append(f"{node.func.id}()")
    if bad:
        raise ValueError("disallowed constructs in generated APL: "
                         + ", ".join(sorted(set(bad))))


def child_env():
    """Minimal, secret-free environment for the smoke subprocess (#2)."""
    return {k: os.environ[k] for k in _CHILD_ENV_KEEP if k in os.environ}


def run_apl_subprocess(sim_root, module, deck_path, n, seed,
                       mode="goldfish", timeout=DEFAULT_SMOKE_TIMEOUT):
    """Run an already-written, already-gated generated APL OUT OF PROCESS and
    return the runner's verdict dict. NEVER imports the model code in-process.

    `python -I` (cwd + script dir off sys.path) + a scrubbed env (no secrets) +
    a timeout. mode is "goldfish" (lethal-rate + avg kill turn) or "match" (WR
    vs GenericMatchAPL). Fails closed: a timeout, a crash, or unparseable output
    returns a dict whose status is not "ran" (never raises for those), so a
    caller that only ships on status == "ran" cannot be fooled into treating a
    failed sandbox as a pass."""
    cmd = [sys.executable, "-I", str(SMOKE_RUNNER), str(sim_root), str(module),
           str(deck_path), str(n), str(seed), str(mode)]
    try:
        proc = subprocess.run(cmd, cwd=str(sim_root), capture_output=True,
                              text=True, timeout=timeout, env=child_env())
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "error": f"smoke exceeded {timeout}s"}
    except Exception as e:  # subprocess init failure -> fail closed, don't raise
        return {"status": "subprocess_error", "error": str(e)}

    out = (proc.stdout or "").strip().splitlines()
    for line in reversed(out):  # last JSON line is the runner's verdict
        try:
            return json.loads(line)
        except ValueError:
            continue
    return {"status": "no_output", "error": (proc.stderr or "").strip()[-500:]}
