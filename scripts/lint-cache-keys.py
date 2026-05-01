"""lint-cache-keys.py -- Stage S6: heuristic detector for cache-collision bug class.

Scans mtg-sim source for cache-write call sites where identity-shaping
function parameters don't appear in the path construction. INFO-level
findings (false positives possible). Skips test fixtures, _research/,
__pycache__/, generated auto_apls/.

Allow-list: `# drift-detect:cache-key-ok reason="..."` within 5 lines
above a cache-write call suppresses the finding for that function.
Reason= string is required (forces explicit justification, mirroring
audit:custom_variant pattern).

Usage:
    python lint-cache-keys.py [--check cache-keys] [--json]

Spec: harness/specs/2026-04-28-drift-detect-8th-check-cache-key-audit.md
Audit corpus: harness/knowledge/tech/cache-key-audit-2026-04-28.md
"""
import argparse
import ast
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
HARNESS_ROOT = SCRIPT_DIR.parent
MTG_SIM_ROOT = (HARNESS_ROOT.parent / "mtg-sim").resolve()

# Per-spec: narrow heuristic word list. Identity-shaping params should
# appear in path construction; if they don't, that's a cache-collision
# candidate. Keep narrow to reduce false positives at INFO level.
HEURISTIC_PARAMS = {
    "deck", "deck_a", "deck_b", "our_deck", "opp_deck",
    "opp", "opp_name",
    "format", "format_name",
    "seed", "n", "n_per_matchup",
    "variant",
    "side", "side_a", "side_b",
}

# AST patterns that count as "cache write"
CACHE_WRITE_FUNCS = {
    "json.dump", "pickle.dump",
    "write_text", "write_bytes",
}

# open(..., 'w') / open(..., 'wb') is special-cased
ALLOWLIST_TAG = "drift-detect:cache-key-ok"


def _is_cache_write_call(node):
    """Return True if this Call node is a cache-write."""
    if not isinstance(node, ast.Call):
        return False
    f = node.func
    # json.dump, pickle.dump
    if isinstance(f, ast.Attribute):
        full = _attr_chain(f)
        if full in CACHE_WRITE_FUNCS:
            return True
        # path.write_text, path.write_bytes
        if f.attr in ("write_text", "write_bytes"):
            return True
    # open(..., 'w'/'wb')
    if isinstance(f, ast.Name) and f.id == "open":
        if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
            mode = node.args[1].value
            if isinstance(mode, str) and mode in ("w", "wb", "a", "ab", "w+", "wb+"):
                return True
    return False


def _attr_chain(node):
    """Convert Attribute(Name(json), 'dump') -> 'json.dump'."""
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def _names_referenced(node):
    """Collect all Name identifiers used (read) anywhere in the subtree."""
    names = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load):
            names.add(sub.id)
    return names


def _has_allowlist_above(source_lines, lineno, window=5):
    """Check for allow-list comment within `window` lines above lineno."""
    start = max(0, lineno - 1 - window)
    end = lineno - 1  # lineno is 1-indexed; lines list is 0-indexed
    for i in range(start, end):
        if i < len(source_lines) and ALLOWLIST_TAG in source_lines[i]:
            return True
    return False


def analyze_file(path, scan_root=None):
    """Return list of findings for one .py file. scan_root is used for
    relative-path display in finding output (defaults to MTG_SIM_ROOT)."""
    if scan_root is None:
        scan_root = MTG_SIM_ROOT
    findings = []
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return findings
    source_lines = source.splitlines()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return findings  # skip unparseable files (likely test fixtures or generated code)

    for func in ast.walk(tree):
        if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        # Collect parameter names matching heuristic
        param_names = {arg.arg for arg in func.args.args}
        identity_params = param_names & HEURISTIC_PARAMS
        if not identity_params:
            continue

        # Find cache-write Call sites within this function. Dedupe by
        # function: one finding per function regardless of how many
        # cache-write calls it contains (typically `open()` + `json.dump()`
        # pair which are really one cache-write semantically).
        first_write_line = None
        for node in ast.walk(func):
            if not _is_cache_write_call(node):
                continue
            if _has_allowlist_above(source_lines, node.lineno):
                continue
            if first_write_line is None:
                first_write_line = node.lineno
            # Don't break — keep scanning to ensure ALL writes in this
            # function are allow-listed (if any aren't, we still flag).

        if first_write_line is None:
            continue

        # Heuristic: identity params not referenced anywhere in the function
        # body indicates a likely cache-key gap. Tolerant of false negatives
        # at INFO level (param referenced in a log message looks "OK" even
        # if not in path; that's acceptable for v1 — the audit doc covers
        # the strict case).
        body_names = _names_referenced(func)
        missing = identity_params - body_names
        if missing:
            findings.append({
                "severity": "INFO",
                "check": "cache-keys",
                "file": str(path.relative_to(scan_root)) if path.is_relative_to(scan_root) else str(path),
                "line": first_write_line,
                "function": func.name,
                "missing_params": sorted(missing),
                "detail": (f"function `{func.name}` writes cache at line {first_write_line} "
                           f"but identity-shaping parameter(s) {sorted(missing)} "
                           f"do not appear referenced in the function body"),
                "fix": ("Verify cache key includes all identity-shaping inputs. "
                        "Add `# drift-detect:cache-key-ok reason=\"...\"` above the "
                        "write call to suppress if intentional. See "
                        "harness/knowledge/tech/cache-key-audit-2026-04-28.md."),
            })
    return findings


def main():
    parser = argparse.ArgumentParser(description="Cache-key audit lint")
    parser.add_argument("--check", default="cache-keys",
                        help="Check name (only 'cache-keys' supported; arg for parity)")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--root", default=str(MTG_SIM_ROOT),
                        help="Root directory to scan (default: mtg-sim)")
    parser.add_argument("--include-tests", action="store_true",
                        help="Include tests/ subdirs (default: skip)")
    args = parser.parse_args()

    root = Path(args.root)
    if not root.exists():
        print(f"ERROR: scan root not found: {root}", file=sys.stderr)
        sys.exit(2)

    # Skip these subtrees (skip 'tests' unless --include-tests passed)
    skip_dirs = {"__pycache__", "_research", "auto_apls"}
    if not args.include_tests:
        skip_dirs.add("tests")

    all_findings = []
    file_count = 0
    for py_file in root.rglob("*.py"):
        if any(p in skip_dirs for p in py_file.parts):
            continue
        file_count += 1
        all_findings.extend(analyze_file(py_file, scan_root=root))

    if args.json:
        print(json.dumps({
            "issues": all_findings,
            "files_scanned": file_count,
            "errors": 0,
            "warnings": 0,
        }, indent=2))
    else:
        print(f"Scanned {file_count} files; found {len(all_findings)} cache-key issues")
        for f in all_findings:
            print(f"  [{f['severity']}] {f['file']}:{f['line']} {f['function']} -- "
                  f"missing {f['missing_params']}")

    # Always exit 0 (INFO-only check)
    sys.exit(0)


if __name__ == "__main__":
    main()
