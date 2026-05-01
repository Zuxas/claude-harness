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

# Names that signal safe atomic writes — seeing any of these in a function
# means it has been migrated to the safe pattern.
SAFE_PATTERNS = {
    "atomic_rmw_json", "atomic_write_json", "os.replace",
    "atomic_json_update",
}


def _extract_string(node):
    """Return the string value of a constant string AST node, or None."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _find_open_paths(func_body, mode_hint):
    """
    Find hardcoded string paths passed to open() with the given mode hint.
    mode_hint: 'r' matches open(path) or open(path, 'r')
               'w' matches open(path, 'w') or open(path, 'wb')
    Returns set of (path_str, lineno).
    """
    results = set()
    for node in ast.walk(ast.Module(body=func_body, type_ignores=[])):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        # open(path, ...) or open(path)
        is_open = (isinstance(func, ast.Name) and func.id == "open")
        if not is_open:
            continue
        if not node.args:
            continue
        path_str = _extract_string(node.args[0])
        if path_str is None:
            continue
        # Determine mode
        if len(node.args) >= 2:
            mode_arg = _extract_string(node.args[1])
        else:
            # Check keyword mode=
            mode_arg = None
            for kw in node.keywords:
                if kw.arg == "mode":
                    mode_arg = _extract_string(kw.value)
        if mode_hint == "r":
            if mode_arg is None or mode_arg in ("r", "rb", "rt"):
                results.add((path_str, node.lineno))
        elif mode_hint == "w":
            if mode_arg in ("w", "wb", "wt"):
                results.add((path_str, node.lineno))
    return results


def _has_safe_pattern(func_src):
    """Return True if any safe atomic-write pattern name appears in function source."""
    for safe in SAFE_PATTERNS:
        if safe in func_src:
            return True
    return False


def _has_allowlist(func_src):
    """Return True if allow-list comment is present in function source."""
    return "drift-detect:rmw-ok" in func_src


def _get_func_source(source_lines, func_node):
    """Extract source lines for a function node."""
    start = func_node.lineno - 1
    end = func_node.end_lineno
    return "\n".join(source_lines[start:end])


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

        # Fast exits
        if _has_allowlist(func_src):
            continue
        if _has_safe_pattern(func_src):
            continue
        # Must mention json somewhere
        if "json" not in func_src:
            continue

        read_paths = _find_open_paths(node.body, "r")
        write_paths = _find_open_paths(node.body, "w")

        read_path_strs = {p for p, _ in read_paths}
        write_path_strs = {p for p, _ in write_paths}
        overlap = read_path_strs & write_path_strs

        for shared_path in overlap:
            # Only flag if json.load/dump appears in the function
            if ("json.load" in func_src or "json.loads" in func_src) and (
                "json.dump" in func_src or "json.dumps" in func_src
            ):
                findings.append({
                    "file": str(path),
                    "function": node.name,
                    "line": node.lineno,
                    "path": shared_path,
                    "message": (
                        f"RMW pattern on '{shared_path}' without atomic-write. "
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
    findings = scan(roots)

    if args.json:
        print(json.dumps({"findings": findings, "count": len(findings)}, indent=2))
    else:
        if not findings:
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
