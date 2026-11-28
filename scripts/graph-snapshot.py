#!/usr/bin/env python3
"""
graph-snapshot.py -- Daily project graph snapshot

Walks E:\\vscode ai project\\ and emits a JSON snapshot of the project graph
state for today: nodes (files) + edges (wikilinks, Python imports).

Usage:
    python graph-snapshot.py [--root PATH] [--out PATH] [--verbose]

Defaults:
    --root  E:\\vscode ai project
    --out   E:\\vscode ai project\\harness\\state\\graph-snapshots\\YYYY-MM-DD.json

Output schema:
{
  "snapshot_date": "2026-04-28",
  "snapshot_iso": "2026-04-28T04:30:00Z",
  "project_root": "E:/vscode ai project",
  "stats": {
    "total_files": int,
    "total_nodes": int,
    "total_edges": int,
    "files_by_type": {"py": int, "md": int, "json": int, "txt": int, "other": int},
    "files_by_top_folder": {"mtg-sim": int, "harness": int, ...},
    "edges_by_type": {"wikilink": int, "import": int}
  },
  "nodes": [{id, type, folder, size_bytes, mtime_iso, in_degree, out_degree}, ...],
  "edges": [{from, to, type}, ...],
  "warnings": [str, ...]
}

Conventions:
- Skip .git, __pycache__, node_modules, .obsidian, .venv, env, venv, _research
- Every .md and .py file becomes a node
- .json/.txt files become nodes ONLY if referenced by another file
- Wikilinks: [[link]] patterns in .md, resolved to project file paths
- Imports: from X import Y / import X in .py, resolved to project file paths,
  stdlib + pip packages skipped

Created: 2026-04-27 by claude.ai per harness/specs/2026-04-28-project-visualization-mvp.md
Decisions made (Q1/Q2/Q3 from spec):
  Q1: edges = wikilinks AND within-project Python imports (recommendation b)
  Q2: JSON files become nodes only if referenced (recommendation)
  Q3: no folder-name conceptual matches (only explicit links)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "agents" / "scripts"))
from graph_privacy import resolve_public_folders  # noqa: E402
from roots import project_root  # noqa: E402

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_ROOT = project_root()
DEFAULT_OUT_DIR = DEFAULT_ROOT / "harness" / "state" / "graph-snapshots"

# Directories to skip entirely (anywhere in the tree)
SKIP_DIRS = {
    ".git", "__pycache__", "node_modules", ".obsidian",
    ".venv", "venv", "env", ".env",
    "_research",  # 2026-04-27 convention: research-in-progress, not part of canonical graph
    ".mypy_cache", ".pytest_cache", ".ruff_cache",
    "dist", "build", ".next", ".cache",
}

# File extensions we always nodeify
ALWAYS_NODE_EXTS = {".md", ".py"}

# File extensions that nodeify only if referenced
REFERENCE_ONLY_EXTS = {".json", ".txt"}

# All extensions we care about reading at all
INTERESTING_EXTS = ALWAYS_NODE_EXTS | REFERENCE_ONLY_EXTS

# Wikilink regex: [[target]] or [[target|alias]] or [[target#heading]]
WIKILINK_RE = re.compile(r"\[\[([^\]\|#]+)(?:[#\|][^\]]*)?\]\]")

# Python import regex (lightweight, regex-based for speed)
# Handles: import x, import x.y, from x import y, from x.y import z, from . import z
PY_IMPORT_RE = re.compile(
    r"^\s*(?:from\s+([\w\.]+)\s+import|import\s+([\w\.,\s]+))",
    re.MULTILINE,
)

# Common stdlib top-level modules we should skip when resolving imports
# (not exhaustive but covers the noise)
STDLIB_HINTS = {
    "os", "sys", "re", "json", "math", "random", "time", "datetime", "pathlib",
    "collections", "itertools", "functools", "typing", "dataclasses", "enum",
    "io", "csv", "sqlite3", "subprocess", "threading", "multiprocessing",
    "asyncio", "argparse", "logging", "warnings", "copy", "pickle", "hashlib",
    "abc", "contextlib", "tempfile", "shutil", "glob", "fnmatch", "string",
    "operator", "struct", "binascii", "base64", "uuid", "weakref",
    "unittest", "pytest", "doctest", "traceback", "inspect", "ast",
    "platform", "socket", "ssl", "urllib", "http", "email", "html",
    "xml", "configparser", "concurrent", "queue", "signal", "atexit",
    "__future__", "annotations",
}

# Common pip packages worth skipping
PIP_HINTS = {
    "numpy", "pandas", "scipy", "matplotlib", "seaborn", "plotly",
    "torch", "tensorflow", "sklearn", "transformers",
    "requests", "httpx", "aiohttp", "flask", "django", "fastapi",
    "pytest", "pytest_asyncio", "click", "tqdm", "rich", "loguru",
    "pydantic", "yaml", "toml", "openpyxl", "xlsxwriter",
    "PIL", "cv2", "selenium", "beautifulsoup4", "bs4", "lxml",
    "anthropic", "openai", "google",
}

# ---------------------------------------------------------------------------
# Tree walking
# ---------------------------------------------------------------------------

def _gitignored_rel_paths(files: dict[str, dict], root: Path,
                          warnings: list[str]) -> set[str]:
    """Rel-to-root paths that are gitignored IN THEIR OWN REPO (#27).

    Groups candidate files by the nearest ancestor repo (a dir containing .git,
    not above `root`) and batch-runs `git check-ignore --stdin` per repo, so a
    path ignored in mtg-sim is dropped even though it is tracked in this repo."""
    cache: dict[Path, Path | None] = {}

    def repo_for(start: Path) -> Path | None:
        d = start
        while True:
            if d in cache:
                return cache[d]
            if (d / ".git").exists():
                cache[start] = d
                return d
            if d == root or d.parent == d:
                cache[start] = None
                return None
            d = d.parent

    by_repo: dict[Path, list[tuple[str, Path]]] = defaultdict(list)
    for rel, meta in files.items():
        abs_p = Path(meta["abs_path"])
        repo = repo_for(abs_p.parent)
        if repo is not None:
            by_repo[repo].append((rel, abs_p))

    ignored: set[str] = set()
    for repo, items in by_repo.items():
        back: dict[str, str] = {}
        for rel_to_root, abs_p in items:
            rr = abs_p.relative_to(repo).as_posix()
            back[rr] = rel_to_root
        try:
            proc = subprocess.run(
                ["git", "-C", str(repo), "check-ignore", "--stdin"],
                input="\n".join(back), capture_output=True, text=True, timeout=120)
        except Exception as e:
            # FAIL CLOSED (#27): if we can't establish ignore status for a repo
            # (git missing, timeout, crash), exclude ALL its paths rather than
            # let unchecked paths through.
            warnings.append(f"check-ignore failed for repo {repo.name}: {e} "
                            f"-- excluding all {len(back)} of its paths (fail-closed)")
            ignored.update(back.values())
            continue
        if proc.returncode not in (0, 1):  # 0=some ignored, 1=none; else error
            warnings.append(f"check-ignore error (rc={proc.returncode}) for repo "
                            f"{repo.name} -- excluding all its paths (fail-closed)")
            ignored.update(back.values())
            continue
        for line in proc.stdout.splitlines():
            line = line.strip()
            if line in back:
                ignored.add(back[line])
    return ignored


def walk_project(root: Path, warnings: list[str],
                 public_folders: frozenset | None = None,
                 excluded_unknown: set | None = None) -> dict[str, dict]:
    """Walk the project tree, return a dict of {relative_path: {meta}}.

    relative_path is forward-slash POSIX style, relative to root. Fail-closed
    (#27): when `public_folders` is given, ONLY those top-level folders are
    indexed; every other top-level folder (unknown or private) is pruned and its
    name recorded in `excluded_unknown`. public_folders=None indexes everything
    (the local-only --include-private opt-in).
    """
    files: dict[str, dict] = {}

    for dirpath, dirnames, filenames in os.walk(root):
        # In-place mutation of dirnames to skip subtrees
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        # At the top level, keep ONLY allowlisted public repos; record the rest.
        if public_folders is not None and Path(dirpath) == root:
            if excluded_unknown is not None:
                excluded_unknown.update(d for d in dirnames if d not in public_folders)
            dirnames[:] = [d for d in dirnames if d in public_folders]

        for fname in filenames:
            full_path = Path(dirpath) / fname
            ext = full_path.suffix.lower()
            if ext not in INTERESTING_EXTS:
                continue

            try:
                rel = full_path.relative_to(root).as_posix()
            except ValueError:
                continue

            try:
                stat = full_path.stat()
            except OSError as e:
                warnings.append(f"stat failed for {rel}: {e}")
                continue

            top_folder = rel.split("/", 1)[0] if "/" in rel else "(root)"

            # Fail-closed: loose root-level files (and anything the dir prune
            # didn't catch) are excluded unless explicitly allowlisted (#27).
            if public_folders is not None and top_folder not in public_folders:
                if excluded_unknown is not None and top_folder != "(root)":
                    excluded_unknown.add(top_folder)
                continue

            files[rel] = {
                "path": rel,
                "abs_path": str(full_path),
                "type": ext.lstrip("."),
                "top_folder": top_folder,
                "folder": str(Path(rel).parent.as_posix()) if "/" in rel else "(root)",
                "size_bytes": stat.st_size,
                "mtime_iso": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            }

    return files


# ---------------------------------------------------------------------------
# Edge extraction: wikilinks
# ---------------------------------------------------------------------------

def read_text_safe(path: Path, warnings: list[str], rel: str) -> str:
    """Read file as text, trying utf-8 then cp1252. Return empty string on failure."""
    for encoding in ("utf-8", "cp1252"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
        except OSError as e:
            warnings.append(f"read failed for {rel}: {e}")
            return ""
    warnings.append(f"encoding failed for {rel} (tried utf-8 + cp1252)")
    return ""


def extract_wikilinks(content: str) -> list[str]:
    """Extract [[link]] targets from markdown content."""
    return [m.group(1).strip() for m in WIKILINK_RE.finditer(content)]


def resolve_wikilink(target: str, source_rel: str, all_files: dict[str, dict]) -> str | None:
    """Resolve a wikilink target to an actual file path in the project.

    Tries:
    1. Exact path match (target as relative path)
    2. Filename-stem match anywhere in the tree (Obsidian default behavior)
    3. Filename-stem match in same folder as source

    Returns the resolved relative path, or None if can't resolve.
    """
    target_norm = target.strip().replace("\\", "/")
    if not target_norm:
        return None

    # Try as a direct path with .md appended if no extension
    candidates = []
    if "." in Path(target_norm).name:
        candidates.append(target_norm)
    else:
        candidates.append(f"{target_norm}.md")
        candidates.append(target_norm)  # in case it's a folder reference

    for cand in candidates:
        # Direct match
        if cand in all_files:
            return cand
        # Trailing match (Obsidian: any file whose path ends with this)
        for fpath in all_files:
            if fpath.endswith("/" + cand) or fpath == cand:
                return fpath

    # Filename-stem match anywhere
    target_stem = Path(target_norm).stem
    matches = [fpath for fpath in all_files if Path(fpath).stem == target_stem]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        # Prefer same-folder match
        source_folder = str(Path(source_rel).parent.as_posix())
        for m in matches:
            if str(Path(m).parent.as_posix()) == source_folder:
                return m
        # Otherwise return first match (deterministic by sort)
        return sorted(matches)[0]

    return None


# ---------------------------------------------------------------------------
# Edge extraction: Python imports
# ---------------------------------------------------------------------------

def extract_py_imports(content: str) -> list[str]:
    """Extract module names imported by a Python file.

    Returns top-level module names like 'engine.game_state' or 'data.deck'.
    """
    imports = []
    for match in PY_IMPORT_RE.finditer(content):
        from_module = match.group(1)
        import_clause = match.group(2)

        if from_module:
            imports.append(from_module)
        elif import_clause:
            # 'import a, b, c' or 'import a.b, c.d as e'
            for part in import_clause.split(","):
                # Strip 'as alias' and whitespace
                name = part.split(" as ")[0].strip()
                if name:
                    imports.append(name)

    return imports


def is_likely_external(module_name: str) -> bool:
    """Best-effort filter for stdlib/pip vs project imports."""
    top = module_name.split(".", 1)[0]
    if top in STDLIB_HINTS or top in PIP_HINTS:
        return True
    # Heuristic: lowercase single-word that isn't in our project layout
    # is more likely external. We'll let the resolver decide via path lookup
    # rather than rejecting here.
    return False


def resolve_py_import(
    module_name: str,
    source_rel: str,
    all_files: dict[str, dict],
    project_top_folders: set[str],
) -> str | None:
    """Resolve a Python import to an actual .py file in the project.

    Examples:
        'engine.game_state' -> 'mtg-sim/engine/game_state.py' (if source is in mtg-sim)
        'data.deck' -> 'mtg-sim/data/deck.py'
        'apl.boros_energy' -> 'mtg-sim/apl/boros_energy.py'

    Returns relative path or None.
    """
    if is_likely_external(module_name):
        return None

    parts = module_name.split(".")

    # First try resolution scoped to the source file's top folder
    # (most imports are within the same project)
    source_top = source_rel.split("/", 1)[0] if "/" in source_rel else None

    candidates_to_try = []

    if source_top and source_top in project_top_folders:
        # Try as a path under the source's top folder
        candidates_to_try.append(source_top)

    # Also try as paths under each known top folder (fallback for cross-project)
    for tf in project_top_folders:
        if tf != source_top:
            candidates_to_try.append(tf)

    for tf in candidates_to_try:
        # Try: tf/parts[0]/parts[1]/.../parts[N].py (file)
        as_file = f"{tf}/" + "/".join(parts) + ".py"
        if as_file in all_files:
            return as_file
        # Try: tf/parts[0]/.../parts[N]/__init__.py (package)
        as_pkg = f"{tf}/" + "/".join(parts) + "/__init__.py"
        if as_pkg in all_files:
            return as_pkg
        # Try without the top folder prefix: parts[0]/.../parts[N].py
        # (handles imports that don't include a top-folder prefix)
        if len(parts) >= 2:
            as_file_notop = f"{tf}/" + "/".join(parts[1:]) + ".py"
            if as_file_notop in all_files:
                return as_file_notop

    # Last resort: search by filename stem anywhere
    target_stem = parts[-1]
    matches = [
        fpath for fpath in all_files
        if Path(fpath).stem == target_stem and fpath.endswith(".py")
    ]
    if len(matches) == 1:
        return matches[0]

    return None


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def build_snapshot(root: Path, verbose: bool = False,
                   public_folders: frozenset | None = None,
                   include_gitignored: bool = False) -> dict:
    warnings: list[str] = []
    excluded_unknown: set = set()

    if verbose:
        print(f"[graph-snapshot] walking {root}", file=sys.stderr)

    files = walk_project(root, warnings, public_folders=public_folders,
                         excluded_unknown=excluded_unknown)

    excluded_gitignored = 0
    if not include_gitignored:
        ignored = _gitignored_rel_paths(files, root, warnings)
        if ignored:
            files = {rel: m for rel, m in files.items() if rel not in ignored}
            excluded_gitignored = len(ignored)

    included_public = sorted(public_folders) if public_folders is not None else None
    if verbose:
        print(f"[graph-snapshot] found {len(files)} candidate files "
              f"(allowlist: {included_public if included_public is not None else 'ALL'}, "
              f"excluded unknown folders: {sorted(excluded_unknown) or 'none'}, "
              f"excluded {excluded_gitignored} gitignored)", file=sys.stderr)

    project_top_folders = {f["top_folder"] for f in files.values() if f["top_folder"] != "(root)"}

    edges: list[dict] = []
    referenced: set[str] = set()

    # Pass 1: extract edges from .md (wikilinks) and .py (imports)
    for rel, meta in files.items():
        if meta["type"] not in {"md", "py"}:
            continue

        content = read_text_safe(Path(meta["abs_path"]), warnings, rel)
        if not content:
            continue

        if meta["type"] == "md":
            for target in extract_wikilinks(content):
                resolved = resolve_wikilink(target, rel, files)
                if resolved and resolved != rel:
                    edges.append({"from": rel, "to": resolved, "type": "wikilink"})
                    referenced.add(resolved)
        elif meta["type"] == "py":
            for module_name in extract_py_imports(content):
                resolved = resolve_py_import(module_name, rel, files, project_top_folders)
                if resolved and resolved != rel:
                    edges.append({"from": rel, "to": resolved, "type": "import"})
                    referenced.add(resolved)

    # Pass 2: build node list
    # All .md and .py files are always nodes
    # .json and .txt files are nodes ONLY if referenced
    nodes: list[dict] = []
    in_degree: dict[str, int] = defaultdict(int)
    out_degree: dict[str, int] = defaultdict(int)

    for edge in edges:
        out_degree[edge["from"]] += 1
        in_degree[edge["to"]] += 1

    for rel, meta in files.items():
        ext = meta["type"]
        if ext in {"md", "py"}:
            include = True
        elif ext in {"json", "txt"}:
            include = rel in referenced
        else:
            include = False

        if not include:
            continue

        nodes.append({
            "id": rel,
            "type": ext,
            "folder": meta["folder"],
            "top_folder": meta["top_folder"],
            "size_bytes": meta["size_bytes"],
            "mtime_iso": meta["mtime_iso"],
            "in_degree": in_degree.get(rel, 0),
            "out_degree": out_degree.get(rel, 0),
        })

    # Filter edges to only those between included nodes
    node_ids = {n["id"] for n in nodes}
    edges = [e for e in edges if e["from"] in node_ids and e["to"] in node_ids]

    # Stats
    files_by_type: dict[str, int] = defaultdict(int)
    files_by_top_folder: dict[str, int] = defaultdict(int)
    edges_by_type: dict[str, int] = defaultdict(int)

    for n in nodes:
        files_by_type[n["type"]] += 1
        files_by_top_folder[n["top_folder"]] += 1
    for e in edges:
        edges_by_type[e["type"]] += 1

    now = datetime.now(timezone.utc)
    snapshot = {
        "snapshot_date": now.strftime("%Y-%m-%d"),
        "snapshot_iso": now.isoformat(),
        "project_root": root.as_posix(),
        "stats": {
            "total_files_walked": len(files),
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "files_by_type": dict(files_by_type),
            "files_by_top_folder": dict(files_by_top_folder),
            "edges_by_type": dict(edges_by_type),
            "included_public_folders": included_public,
            "excluded_unknown_folders": sorted(excluded_unknown),
            "excluded_gitignored_count": excluded_gitignored,
            # Privacy provenance for the publication layer (#27). gitignore_filtered
            # records whether filtering actually ran (the count alone is 0 both when
            # nothing matched AND when --include-gitignored skipped it). local_only
            # marks a snapshot made with an exposure-widening opt-in; publication
            # refuses those by default.
            "gitignore_filtered": not include_gitignored,
            "local_only": include_gitignored or (public_folders is None),
        },
        "nodes": sorted(nodes, key=lambda n: n["id"]),
        "edges": sorted(edges, key=lambda e: (e["from"], e["to"], e["type"])),
        "warnings": warnings,
    }

    return snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description="Project graph snapshot.")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT,
                        help="Project root to walk")
    parser.add_argument("--out", type=Path, default=None,
                        help="Output JSON path (default: harness/state/graph-snapshots/YYYY-MM-DD.json)")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Verbose progress output")
    parser.add_argument("--include-private", action="store_true",
                        help="Index ALL folders, not just the public allowlist "
                             "(default: fail-closed; local-only analysis)")
    parser.add_argument("--public-folder", action="append", default=[],
                        help="Extra public top-level folder to allowlist (repeatable)")
    parser.add_argument("--include-gitignored", action="store_true",
                        help="Include gitignored paths (default: exclude via git check-ignore)")
    args = parser.parse_args()

    root = args.root.resolve()
    if not root.exists():
        print(f"[graph-snapshot] ERROR: root does not exist: {root}", file=sys.stderr)
        return 2

    public_folders = (None if args.include_private
                      else resolve_public_folders(args.public_folder))
    snapshot = build_snapshot(root, verbose=args.verbose,
                              public_folders=public_folders,
                              include_gitignored=args.include_gitignored)

    out_path = args.out
    if out_path is None:
        out_dir = DEFAULT_OUT_DIR
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{snapshot['snapshot_date']}.json"
    else:
        out_path.parent.mkdir(parents=True, exist_ok=True)

    out_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")

    stats = snapshot["stats"]
    print(
        f"[graph-snapshot] {snapshot['snapshot_date']}: "
        f"{stats['total_nodes']} nodes, {stats['total_edges']} edges "
        f"({stats['edges_by_type'].get('wikilink', 0)} wikilinks, "
        f"{stats['edges_by_type'].get('import', 0)} imports). "
        f"Warnings: {len(snapshot['warnings'])}. "
        f"-> {out_path}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
