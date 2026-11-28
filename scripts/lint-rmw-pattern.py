"""lint-rmw-pattern.py -- Stage S6+: heuristic detector for RMW-race bug class.

Subspecies-2 of cache-collision class: a function reads JSON from a
hardcoded path, mutates the dict, and writes back to the same path
without using atomic_rmw_json / atomic_write_json / os.replace.
Concurrent invocations stomp each other's mutations.

Allow-list: place `# drift-detect:rmw-ok reason="..."` anywhere in the
function body to suppress the finding for that function.

Usage:
    python lint-rmw-pattern.py [--json] [--strict]

Exit codes:
    0  clean
    1  INFO findings present (--strict exits 1 on INFO)
"""
import argparse
import ast
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
HARNESS_ROOT = SCRIPT_DIR.parent
MTG_SIM_ROOT = (HARNESS_ROOT.parent / "mtg-sim").resolve()
AGENTS_ROOT = HARNESS_ROOT / "agents" / "scripts"

SKIP_DIRS = {"__pycache__", "_research", "auto_apls", "tests", ".git"}


def _attr_chain(node):
    """Attribute(Name(os), 'replace') -> 'os.replace'; returns '' if not a pure
    Name/Attribute chain."""
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))
    return ""


def _path_identity(node):
    """A canonical identity for a path expression, so a read and a write can be
    recognized as the SAME target whether it's a string literal, a constant name
    (MATRIX), or an attribute (self.path). Returns None for anything else."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return ("lit", node.value)
    if isinstance(node, ast.Name):
        return ("name", node.id)
    if isinstance(node, ast.Attribute):
        chain = _attr_chain(node)
        return ("attr", chain) if chain else None
    return None


def _open_mode(call):
    """'w' if an open() call opens for writing/appending, else 'r'."""
    mode = None
    if len(call.args) >= 2 and isinstance(call.args[1], ast.Constant):
        mode = call.args[1].value
    else:
        for kw in call.keywords:
            if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                mode = kw.value.value
    if isinstance(mode, str) and mode[:1] in ("w", "a"):
        return "w"
    return "r"


# Call names that make a write to their path argument atomic/safe.
_SAFE_CALL_NAMES = {"atomic_rmw_json", "atomic_write_json", "atomic_json_update"}


def _collect_targets(func):
    """Return (reads, writes, safe_ids): path identities read, written, and made
    safe by an atomic call (os.replace / Path.replace / atomic_* targeting them).
    Covers open(x[, mode]) and Path x.read_text/write_text/read_bytes/write_bytes."""
    reads, writes, safe_ids = set(), set(), set()
    for node in ast.walk(func):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        if isinstance(f, ast.Name):
            if f.id == "open" and node.args:
                ident = _path_identity(node.args[0])
                if ident:
                    (writes if _open_mode(node) == "w" else reads).add(ident)
            elif f.id in _SAFE_CALL_NAMES and node.args:
                ident = _path_identity(node.args[0])
                if ident:
                    safe_ids.add(ident)
        elif isinstance(f, ast.Attribute):
            if f.attr in ("read_text", "read_bytes"):
                ident = _path_identity(f.value)
                if ident:
                    reads.add(ident)
            elif f.attr in ("write_text", "write_bytes"):
                ident = _path_identity(f.value)
                if ident:
                    writes.add(ident)
            elif f.attr == "replace" or _attr_chain(f) in _SAFE_CALL_NAMES:
                # os.replace(src, dst) / tmp.replace(dst): every path arg of an
                # atomic rename is a safe target (path-specific, so os.replace on
                # a DIFFERENT file does not exempt this one).
                for a in node.args:
                    ident = _path_identity(a)
                    if ident:
                        safe_ids.add(ident)
    return reads, writes, safe_ids


def _has_allowlist(func_src):
    """Return True if allow-list comment is present in function source."""
    return "drift-detect:rmw-ok" in func_src


def _get_func_source(source_lines, func_node):
    """Extract source lines for a function node."""
    start = func_node.lineno - 1
    end = func_node.end_lineno
    return "\n".join(source_lines[start:end])


def _fmt_identity(ident):
    kind, val = ident
    return val if kind == "lit" else val


def check_file(path: Path):
    """Return list of finding dicts for one Python file."""
    findings = []
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return findings

    source_lines = source.splitlines()

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        func_src = _get_func_source(source_lines, node)

        if _has_allowlist(func_src):
            continue
        # RMW-of-JSON shape: the function both loads and dumps JSON.
        if not (("json.load" in func_src or "json.loads" in func_src)
                and ("json.dump" in func_src or "json.dumps" in func_src)):
            continue

        reads, writes, safe_ids = _collect_targets(node)
        for ident in (reads & writes) - safe_ids:
            shared = _fmt_identity(ident)
            findings.append({
                "file": str(path),
                "function": node.name,
                "line": node.lineno,
                "path": shared,
                "message": (
                    f"RMW pattern on '{shared}' without atomic-write. "
                    f"Use atomic_rmw_json() or os.replace(). "
                    f"Suppress with: # drift-detect:rmw-ok reason=\"...\""
                ),
                "level": "INFO",
            })

    return findings


def scan(roots):
    all_findings = []
    for root in roots:
        root = Path(root)
        if not root.exists():
            continue
        for py_file in root.rglob("*.py"):
            if any(skip in py_file.parts for skip in SKIP_DIRS):
                continue
            all_findings.extend(check_file(py_file))
    return all_findings


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--strict", action="store_true",
                        help="Exit 1 on INFO findings (for CI)")
    parser.add_argument("--roots", nargs="*",
                        help="Override scan roots (default: mtg-sim + harness/agents)")
    args = parser.parse_args()

    roots = args.roots or [str(MTG_SIM_ROOT), str(AGENTS_ROOT)]
    missing = [r for r in roots if not Path(r).exists()]

    # A missing root means the scan never ran -- reporting "clean" would hide the
    # bug this linter exists to catch. Under --strict that is a hard failure, not
    # an exit-0 "OK" (drift-detect runs --strict).
    if missing:
        msg = f"scan root(s) missing, cannot certify clean: {missing}"
        if args.strict:
            print(f"ERROR: {msg}", file=sys.stderr)
            sys.exit(2)
        print(f"WARNING: {msg}", file=sys.stderr)

    findings = scan(roots)

    if args.json:
        print(json.dumps({"findings": findings, "count": len(findings),
                          "missing_roots": missing}, indent=2))
    else:
        if not findings and not missing:
            print("OK -- no RMW-pattern findings")
        for f in findings:
            print(f"[{f['level']}] {f['file']}:{f['line']} {f['function']}()")
            print(f"       path: {f['path']}")
            print(f"       {f['message']}")

    if args.strict and findings:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
