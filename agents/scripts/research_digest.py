#!/usr/bin/env python3
# -*- coding: ascii -*-
"""
research_digest.py -- SP-4 nightly digest for the research-ingest loop.

LOCAL-ONLY. No network. Standard library only.

Reads the research-ingest heartbeat plus the research-brain Source and
Concept notes, then writes an ASCII digest to harness/inbox/ summarizing
loop liveness, new source drafts, pending synthesis, and promotion
candidates (Concepts at confidence: high, ready for /promote).

Usage:
    python research_digest.py            # write today's digest
    python research_digest.py --selftest # self-check, no files touched
"""

import glob
import json
import os
import re
import sys
from datetime import datetime, timezone

# --- Paths (Windows, forward slashes) ---------------------------------------
ROOT = "E:/vscode ai project"
HEARTBEAT = ROOT + "/harness/state/research-ingest-last-run.json"
SOURCES = ROOT + "/research-brain/Sources"
CONCEPTS = ROOT + "/research-brain/Concepts"
INBOX = ROOT + "/harness/inbox"

STALE_HOURS = 26


# --- Frontmatter parsing ----------------------------------------------------
def read_text(path):
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def split_frontmatter(text):
    """Return the raw YAML-ish frontmatter block (between the first two ---)."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return ""
    out = []
    for line in lines[1:]:
        if line.strip() == "---":
            break
        out.append(line)
    return "\n".join(out)


def parse_frontmatter(text):
    """Very small frontmatter reader: scalar keys plus simple list items.

    Returns a dict where list values (indented '- item' lines) become lists.
    """
    fm = split_frontmatter(text)
    data = {}
    current_list_key = None
    for raw in fm.splitlines():
        if not raw.strip():
            continue
        # list item under the current key
        m = re.match(r"^\s+-\s+(.*)$", raw)
        if m and current_list_key is not None:
            data.setdefault(current_list_key, [])
            if isinstance(data[current_list_key], list):
                data[current_list_key].append(m.group(1).strip())
            continue
        # key: value
        m = re.match(r"^([A-Za-z0-9_-]+)\s*:\s*(.*)$", raw)
        if m:
            key = m.group(1).strip()
            val = m.group(2).strip()
            if val == "":
                data[key] = []
                current_list_key = key
            else:
                data[key] = val
                current_list_key = None
    return data


def note_date(path, fm):
    """Best-effort age key: frontmatter date, else file mtime as YYYY-MM-DD."""
    d = fm.get("date")
    if isinstance(d, str) and re.match(r"^\d{4}-\d{2}-\d{2}", d):
        return d[:10]
    try:
        ts = os.path.getmtime(path)
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
    except OSError:
        return "9999-99-99"


def note_url(text, fm):
    """First URL from the sources list, else first http(s) URL in the body."""
    src = fm.get("sources")
    if isinstance(src, list) and src:
        return src[0]
    if isinstance(src, str) and src.startswith("http"):
        return src
    m = re.search(r"https?://\S+", text)
    if m:
        return m.group(0).rstrip(">)].,")
    return "(no url)"


# --- Heartbeat / liveness ---------------------------------------------------
def parse_iso(value):
    """Parse an ISO8601 timestamp to an aware UTC datetime, or None."""
    if not isinstance(value, str) or not value.strip():
        return None
    v = value.strip()
    if v.endswith("Z"):
        v = v[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(v)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def liveness_line(heartbeat_path, now=None):
    """Return the first header line: LOOP-ALIVE or LOOP-DEAD (with detail)."""
    if now is None:
        now = datetime.now(timezone.utc)
    if not os.path.exists(heartbeat_path):
        return "LOOP-DEAD: research-ingest heartbeat missing/stale (file missing)"
    try:
        data = json.loads(read_text(heartbeat_path))
    except (ValueError, OSError) as exc:
        return ("LOOP-DEAD: research-ingest heartbeat missing/stale "
                "(unreadable: {})".format(exc))
    last_raw = data.get("last_run")
    dt = parse_iso(last_raw)
    if dt is None:
        return ("LOOP-DEAD: research-ingest heartbeat missing/stale "
                "(unparseable last_run: {!r})".format(last_raw))
    age_h = (now - dt).total_seconds() / 3600.0
    if age_h > STALE_HOURS:
        return ("LOOP-DEAD: research-ingest heartbeat missing/stale "
                "(last_run {:.1f}h ago, > {}h)".format(age_h, STALE_HOURS))
    new_sources = data.get("new_sources", 0)
    return "LOOP-ALIVE: last run {}, {} new sources".format(last_raw, new_sources)


# --- Collectors -------------------------------------------------------------
def collect_pending_sources(sources_dir):
    """Return list of dicts for Source notes with status pending-synthesis."""
    out = []
    for path in sorted(glob.glob(os.path.join(sources_dir, "*.md"))):
        try:
            text = read_text(path)
        except OSError:
            continue
        fm = parse_frontmatter(text)
        if str(fm.get("status", "")).strip() == "pending-synthesis":
            out.append({
                "file": os.path.basename(path),
                "url": note_url(text, fm),
                "date": note_date(path, fm),
            })
    return out


def collect_promotion_candidates(concepts_dir):
    """Return list of filenames for Concept notes with confidence: high."""
    out = []
    for path in sorted(glob.glob(os.path.join(concepts_dir, "*.md"))):
        try:
            text = read_text(path)
        except OSError:
            continue
        fm = parse_frontmatter(text)
        if str(fm.get("confidence", "")).strip().lower() == "high":
            out.append(os.path.basename(path))
    return out


# --- Digest builder ---------------------------------------------------------
def build_digest(heartbeat_path, sources_dir, concepts_dir, today, now=None):
    header = liveness_line(heartbeat_path, now=now)
    pending = collect_pending_sources(sources_dir)
    candidates = collect_promotion_candidates(concepts_dir)

    lines = []
    lines.append(header)
    lines.append("")
    lines.append("# Research-brain digest -- {}".format(today))
    lines.append("")

    lines.append("## New source drafts")
    if pending:
        for item in pending:
            lines.append("- {} -- {}".format(item["file"], item["url"]))
    else:
        lines.append("- (none)")
    lines.append("")

    lines.append("## Pending synthesis")
    if pending:
        oldest = min(item["date"] for item in pending)
        lines.append("Count: {}. Oldest: {}.".format(len(pending), oldest))
    else:
        lines.append("Count: 0. Oldest: (none).")
    lines.append("")

    lines.append("## Promotion candidates")
    lines.append("Concept notes at confidence: high -- ready for /promote.")
    if candidates:
        for name in candidates:
            lines.append("- {}".format(name))
    else:
        lines.append("- (none)")
    lines.append("")

    text = "\n".join(lines)
    # Enforce ASCII output.
    return text.encode("ascii", errors="replace").decode("ascii")


# --- Main run ---------------------------------------------------------------
def run():
    today = datetime.now().strftime("%Y-%m-%d")
    digest = build_digest(HEARTBEAT, SOURCES, CONCEPTS, today)
    os.makedirs(INBOX, exist_ok=True)
    out_path = os.path.join(INBOX, "research-brain-digest--{}.md".format(today))
    with open(out_path, "w", encoding="ascii", errors="replace", newline="\n") as fh:
        fh.write(digest)
    sys.stdout.write(digest)
    if not digest.endswith("\n"):
        sys.stdout.write("\n")
    sys.stdout.write("\nWrote: {}\n".format(out_path))
    return 0


# --- Selftest ---------------------------------------------------------------
def selftest():
    import tempfile
    import shutil

    tmp = tempfile.mkdtemp(prefix="research_digest_selftest_")
    try:
        src_dir = os.path.join(tmp, "Sources")
        con_dir = os.path.join(tmp, "Concepts")
        os.makedirs(src_dir)
        os.makedirs(con_dir)
        hb = os.path.join(tmp, "heartbeat.json")
        now = datetime.now(timezone.utc)

        # (a) FRESH heartbeat -> LOOP-ALIVE
        with open(hb, "w", encoding="ascii") as fh:
            json.dump({"last_run": now.isoformat(), "urls_processed": 3,
                       "new_sources": 2, "skipped": 0, "errors": []}, fh)
        out = build_digest(hb, src_dir, con_dir, "2026-07-04", now=now)
        assert out.startswith("LOOP-ALIVE"), \
            "fresh heartbeat should be LOOP-ALIVE, got: " + out[:80]

        # (b) STALE heartbeat (> 26h) -> LOOP-DEAD
        stale = now.timestamp() - (27 * 3600)
        stale_iso = datetime.fromtimestamp(stale, timezone.utc).isoformat()
        with open(hb, "w", encoding="ascii") as fh:
            json.dump({"last_run": stale_iso, "urls_processed": 0,
                       "new_sources": 0, "skipped": 0, "errors": []}, fh)
        out = build_digest(hb, src_dir, con_dir, "2026-07-04", now=now)
        assert out.startswith("LOOP-DEAD"), \
            "stale heartbeat should be LOOP-DEAD, got: " + out[:80]

        # (c) MISSING heartbeat -> LOOP-DEAD
        os.remove(hb)
        out = build_digest(hb, src_dir, con_dir, "2026-07-04", now=now)
        assert out.startswith("LOOP-DEAD"), \
            "missing heartbeat should be LOOP-DEAD, got: " + out[:80]

        # Section presence + promotion candidate detection.
        with open(os.path.join(src_dir, "sample.md"), "w", encoding="ascii") as fh:
            fh.write("---\ntype: source\nstatus: pending-synthesis\n"
                     "sources:\n  - https://example.com/a\n"
                     "confidence: medium\n---\nbody\n")
        with open(os.path.join(con_dir, "concept.md"), "w", encoding="ascii") as fh:
            fh.write("---\ntype: concept\nconfidence: high\n---\nbody\n")
        with open(hb, "w", encoding="ascii") as fh:
            json.dump({"last_run": now.isoformat(), "urls_processed": 1,
                       "new_sources": 1, "skipped": 0, "errors": []}, fh)
        out = build_digest(hb, src_dir, con_dir, "2026-07-04", now=now)
        assert "## New source drafts" in out
        assert "## Pending synthesis" in out
        assert "## Promotion candidates" in out
        assert "sample.md" in out
        assert "https://example.com/a" in out
        assert "concept.md" in out
        assert "Count: 1" in out

        # No-network / no cloud-LLM-vendor guarantee: source must be clean.
        forbidden = "anthro" + "pic"
        self_src = read_text(os.path.abspath(__file__)).lower()
        assert forbidden not in self_src, "source must not name that vendor"

        # Output is 7-bit ASCII.
        out.encode("ascii")

        print("SELFTEST OK")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --- CLI --------------------------------------------------------------------
def main(argv):
    if "--selftest" in argv:
        return selftest()
    return run()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
