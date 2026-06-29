#!/usr/bin/env python3
"""ralph_status.py -- read-only status reader for the Ralph autonomous-Executor loop.

The Ralph loop (ralph_executor.py) keeps its only persistent state in git history: each
iteration lands a `RALPH:` commit whose body carries task / prd_ref / decisions / files /
notes_for_next. This tool reads those commits back and prints what the loop has done --
mirroring arl_status.py for the ARL. READ-ONLY: no writes, no side effects.

Usage:
    python ralph_status.py                 # offline self-test (no git)
    python ralph_status.py --repo <dir>    # status of the RALPH commits in <dir>
    python ralph_status.py -n <count>      # how many recent RALPH commits to read (default 20)

ASCII-only output (CONVENTIONS). Reuses ralph_executor's parser -- does not reinvent it.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ralph_executor import memory_from_commits, parse_ralph_log  # noqa: E402


def summarize(entries):
    """PURE: derive a status dict from a list of MemoryEntry (newest-first)."""
    files = []
    seen = set()
    for e in entries:
        for f in e.files:
            if f not in seen:
                seen.add(f)
                files.append(f)
    return {
        "iterations": len(entries),
        "last_task": entries[0].task if entries else None,
        "task_chain": [e.task for e in entries],
        "files_touched": files,
        "latest_notes_for_next": entries[0].notes_for_next if entries else "",
        "latest_decisions": list(entries[0].decisions) if entries else [],
    }


def format_status(status):
    """PURE: human-readable ASCII status lines."""
    lines = ["=== Ralph loop status ==="]
    lines.append("RALPH iterations recorded: %d" % status["iterations"])
    if status["iterations"] == 0:
        lines.append("(no RALPH: commits found -- loop has not run here, or wrong branch/repo)")
        return "\n".join(lines)
    lines.append("Last task: %s" % status["last_task"])
    if status["latest_decisions"]:
        lines.append("Latest decisions: %s" % "; ".join(status["latest_decisions"]))
    if status["files_touched"]:
        lines.append("Files touched (recent first): %s" % ", ".join(status["files_touched"]))
    if status["latest_notes_for_next"]:
        lines.append("Notes for next iteration: %s" % status["latest_notes_for_next"])
    lines.append("Task chain (newest first):")
    for i, task in enumerate(status["task_chain"]):
        lines.append("  %d. %s" % (i + 1, task))
    return "\n".join(lines)


def ralph_status(repo_dir=".", n=20):
    """IMPURE: read the last n RALPH: commits from repo_dir; return (status_dict, formatted_str)."""
    entries = memory_from_commits(n, repo_dir)
    status = summarize(entries)
    return status, format_status(status)


def _selftest():
    """Offline: round-trip synthetic RALPH bodies through the loop's own builder + parser."""
    from ralph_executor import build_ralph_commit_message
    body_latest = build_ralph_commit_message(
        "add ralph_status.py", prd_ref="ralph tooling",
        decisions=["reuse the parser", "read-only"],
        files=["ralph_status.py"], notes_for_next="wire into a status command")
    body_prev = build_ralph_commit_message(
        "scaffold the loop", files=["ralph_executor.py"], notes_for_next="add adapters")
    # git log emits newest-first, NUL-separated bodies; include a non-RALPH commit (must skip).
    log = "\x00".join([body_latest, body_prev, "chore: not a ralph commit -- skip me"])
    entries = parse_ralph_log(log)
    assert len(entries) == 2, "expected 2 RALPH entries (non-RALPH skipped), got %d" % len(entries)

    status = summarize(entries)
    assert status["iterations"] == 2, status
    assert status["last_task"] == "add ralph_status.py", status["last_task"]
    assert status["task_chain"] == ["add ralph_status.py", "scaffold the loop"], status["task_chain"]
    assert "ralph_status.py" in status["files_touched"], status["files_touched"]
    assert "ralph_executor.py" in status["files_touched"], status["files_touched"]
    assert status["latest_notes_for_next"] == "wire into a status command", status
    assert status["latest_decisions"] == ["reuse the parser", "read-only"], status["latest_decisions"]

    # empty case
    empty = summarize([])
    assert empty["iterations"] == 0 and empty["last_task"] is None
    assert "no RALPH" in format_status(empty)

    out = format_status(status)
    assert "Ralph loop status" in out and "add ralph_status.py" in out
    print(out)
    print("ALL RALPH_STATUS TESTS PASS")
    return 0


def _parse_args(argv):
    repo, n = ".", 20
    i = 0
    while i < len(argv):
        if argv[i] == "--repo" and i + 1 < len(argv):
            repo = argv[i + 1]; i += 2
        elif argv[i] == "-n" and i + 1 < len(argv):
            try:
                n = int(argv[i + 1])
            except ValueError:
                pass
            i += 2
        else:
            i += 1
    return repo, n


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        sys.exit(_selftest())
    repo_dir, count = _parse_args(args)
    _, formatted = ralph_status(repo_dir, count)
    print(formatted)
    sys.exit(0)
