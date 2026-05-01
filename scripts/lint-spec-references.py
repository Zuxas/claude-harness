"""lint-spec-references.py -- Spec reference validator for drift-detect.

Walks harness/specs/*.md (excluding _template.md, RETROACTIVE.md, README.md)
and validates references found in spec bodies.

Sub-detection 1.1 (ERROR): python <path>.py references that don't exist on disk.
Sub-detection 1.3 (INFO): <tool> --help in pre-flight/preflight/verify headings.

Sub-detection 1.2 (winget) is skipped -- network-dependent, high false-negative
rate, deferred behind a flag (not worth adding latency to every drift run).

Usage:
    python lint-spec-references.py [--json] [--specs-dir PATH]

Exit codes:
    0  clean (or INFO-only)
    1  ERROR findings present
"""
import argparse
import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
HARNESS_ROOT = SCRIPT_DIR.parent
MTG_SIM_ROOT = (HARNESS_ROOT.parent / "mtg-sim").resolve()

SKIP_SPECS = {"_template.md", "RETROACTIVE.md", "README.md", "_index.md"}
# Only scan specs that haven't been executed yet; SHIPPED/SUPERSEDED are historical.
ACTIVE_STATUSES = {"PROPOSED", "EXECUTING"}

# Matches: python path/to/script.py or python3 path/to/script.py
# Does NOT match: python -c "...", python -m module
PYTHON_SCRIPT_RE = re.compile(
    r'python3?\s+(?!-[cm]\s)([A-Za-z0-9_./\\][A-Za-z0-9_./\\ -]*\.py)\b'
)

# Section headings that indicate pre-flight context
PREFLIGHT_HEADING_RE = re.compile(
    r'^#+\s.*(pre[-\s]?flight|pre[-\s]?execution|verify|verification)',
    re.IGNORECASE
)
# Tool --help pattern
HELP_PATTERN_RE = re.compile(r'(\S+)\s+--help')


def resolve_script_path(raw_path: str):
    """Try to resolve a script path relative to known roots. Return Path if found."""
    p = Path(raw_path)
    if p.is_absolute():
        return p if p.exists() else None
    # Try mtg-sim root
    candidate = MTG_SIM_ROOT / p
    if candidate.exists():
        return candidate
    # Try harness root
    candidate = HARNESS_ROOT / p
    if candidate.exists():
        return candidate
    # Try as-is (cwd)
    if p.exists():
        return p
    return None


def check_spec(path: Path):
    """Return list of finding dicts for one spec file."""
    findings = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return findings
    # Whole-file allow-list: if any line contains spec-ref-ok, skip the file
    if "spec-ref-ok" in text:
        return findings

    lines = text.splitlines()
    in_preflight = False

    for lineno, line in enumerate(lines, start=1):
        # Track section headings
        if line.startswith("#"):
            in_preflight = bool(PREFLIGHT_HEADING_RE.match(line))

        # Sub-detection 1.1: python script references
        for m in PYTHON_SCRIPT_RE.finditer(line):
            raw = m.group(1).strip().strip('"').strip("'")
            # Skip obvious inline args like "--seed" appearing after .py
            if raw.startswith("-"):
                continue
            resolved = resolve_script_path(raw)
            if resolved is None:
                findings.append({
                    "level": "ERROR",
                    "check": "spec-references",
                    "spec": path.name,
                    "line": lineno,
                    "message": (
                        f"spec '{path.name}' references python script "
                        f"'{raw}' which doesn't exist on disk"
                    ),
                    "fix": f"Verify the path is correct relative to mtg-sim/ or harness/",
                })

        # Sub-detection 1.3: --help in pre-flight sections
        if in_preflight:
            for m in HELP_PATTERN_RE.finditer(line):
                tool = m.group(1)
                findings.append({
                    "level": "INFO",
                    "check": "spec-references",
                    "spec": path.name,
                    "line": lineno,
                    "message": (
                        f"spec '{path.name}' uses '{tool} --help' as pre-flight probe; "
                        f"--help may invoke an interactive pager in non-tty contexts"
                    ),
                    "fix": (
                        f"Prefer '{tool} --version' or 'Get-Command {tool}' "
                        f"(see prefer-version-over-help-for-preflight-probes lesson)"
                    ),
                })

    return findings


def _spec_status(text: str) -> str:
    """Extract status from spec frontmatter line like '**Status:** PROPOSED'."""
    m = re.search(r'\*\*Status:\*\*\s+(\w+)', text)
    return m.group(1).upper() if m else "UNKNOWN"


def scan(specs_dir: Path):
    all_findings = []
    spec_count = 0
    for md_file in sorted(specs_dir.glob("*.md")):
        if md_file.name in SKIP_SPECS:
            continue
        try:
            text = md_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        status = _spec_status(text)
        if status not in ACTIVE_STATUSES:
            continue  # skip SHIPPED, SUPERSEDED, UNKNOWN — already executed or historical
        spec_count += 1
        all_findings.extend(check_spec(md_file))
    return all_findings, spec_count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--specs-dir", default=str(HARNESS_ROOT / "specs"))
    args = parser.parse_args()

    specs_dir = Path(args.specs_dir)
    findings, spec_count = scan(specs_dir)

    errors = [f for f in findings if f["level"] == "ERROR"]

    if args.json:
        print(json.dumps({
            "findings": findings,
            "errors": len(errors),
            "specs_checked": spec_count,
        }, indent=2))
    else:
        if not findings:
            print(f"OK -- {spec_count} specs checked, 0 issues")
        for f in findings:
            print(f"[{f['level']}] {f['spec']}:{f['line']} -- {f['message']}")
            if f.get("fix"):
                print(f"       fix: {f['fix']}")

    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
