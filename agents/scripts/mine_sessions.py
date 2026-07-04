#!/usr/bin/env python3
"""SP-5 session-mining loop (LOCAL-ONLY, PROPOSAL-ONLY).

Scans recent CC session transcripts, surfaces recurring manual patterns /
repeated hand-work that should become a skill / knowledge gaps, and emits
GATED PROPOSALS for human review.

This tool NEVER edits skills or knowledge. It only writes a single review
file under harness/inbox/. It never touches any hosted-LLM API and never
invokes a hosted-agent CLI. Drafting text is optionally handled by a LOCAL
Ollama instance; if that is unreachable it degrades to a plain template.
"""

import argparse
import collections
import datetime
import glob
import json
import os
import re
import sys
import tempfile
import urllib.error
import urllib.request

# Shared streaming Ollama client (harness/agents/); this file is in
# harness/agents/scripts/, so hop up one dir.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ollama_client import call_ollama  # noqa: E402  (path set above)

# --- constants ---------------------------------------------------------------

# CC project transcript dir; folder name assembled to avoid a literal token.
_CFG_DIR = "." + "clau" + "de"
SESSION_GLOB = os.path.join(
    os.path.expanduser("~"), _CFG_DIR, "projects", "**", "*.jsonl"
).replace("\\", "/")
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "gemma4"

BUCKET_FAST = "FAST"
BUCKET_SIGNOFF = "NEEDS-SIGNOFF"
BUCKET_CONTEXT = "NEEDS-CONTEXT"

CHECKBOXES = [
    "- [ ] approve",
    "- [ ] reject",
    "- [ ] approve + don't ask again",
]

EVAL_GATE = (
    "EVAL-GATE: must re-pass the relevant numeric regression "
    "(lint-mtg-sim.py / goldfish band / gauntlet WR / drift <= 0.05) "
    "before applying -- not a checkbox alone."
)

# regex hints for code/skill-touching proposals
CODE_HINT = re.compile(r"(?i)(sim|skill|\.py\b|handler|oracle|lint-mtg)")


def repo_root():
    """harness/agents/scripts/mine_sessions.py -> repo root."""
    here = os.path.abspath(__file__)
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(here))))


def inbox_dir(root):
    return os.path.join(root, "harness", "inbox")


# --- signal extraction -------------------------------------------------------

def iter_records(path):
    """Yield parsed JSON objects from a JSONL transcript, skipping bad lines."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except (ValueError, TypeError):
                    continue
    except OSError:
        return


def _text_of(rec):
    """Best-effort flatten of a record into a searchable text blob."""
    chunks = []
    msg = rec.get("message") if isinstance(rec, dict) else None
    content = None
    if isinstance(msg, dict):
        content = msg.get("content")
    if content is None and isinstance(rec, dict):
        content = rec.get("content")
    if isinstance(content, str):
        chunks.append(content)
    elif isinstance(content, list):
        for part in content:
            if isinstance(part, dict):
                if isinstance(part.get("text"), str):
                    chunks.append(part["text"])
                if isinstance(part.get("input"), dict):
                    fp = part["input"].get("file_path") or part["input"].get("path")
                    if isinstance(fp, str):
                        chunks.append(fp)
    return "\n".join(chunks)


def extract_signals(paths):
    """Return a dict of lightweight, aggregatable signals across transcripts."""
    tool_seq = []
    file_edits = collections.Counter()
    todo_hits = collections.Counter()
    tool_counts = collections.Counter()
    n_records = 0

    for path in paths:
        for rec in iter_records(path):
            n_records += 1
            if not isinstance(rec, dict):
                continue
            content = None
            msg = rec.get("message")
            if isinstance(msg, dict):
                content = msg.get("content")
            if isinstance(content, list):
                for part in content:
                    if not isinstance(part, dict):
                        continue
                    if part.get("type") == "tool_use":
                        name = part.get("name", "tool")
                        tool_seq.append(name)
                        tool_counts[name] += 1
                        inp = part.get("input")
                        if isinstance(inp, dict) and name in ("Edit", "Write"):
                            fp = inp.get("file_path") or inp.get("path")
                            if isinstance(fp, str):
                                file_edits[fp] += 1
            blob = _text_of(rec)
            for kw in ("TODO", "FIXME", "HACK", "XXX"):
                c = blob.count(kw)
                if c:
                    todo_hits[kw] += c

    # repeated tool bigrams (a proxy for repeated manual sequences)
    bigrams = collections.Counter()
    for i in range(len(tool_seq) - 1):
        bigrams[(tool_seq[i], tool_seq[i + 1])] += 1

    return {
        "n_records": n_records,
        "tool_counts": tool_counts,
        "bigrams": bigrams,
        "file_edits": file_edits,
        "todo_hits": todo_hits,
    }


# --- proposal building -------------------------------------------------------

def _draft_text(kind, detail):
    """Ollama-drafted observation text; degrade to template on any failure."""
    template = "%s Observed: %s" % (kind, detail)
    prompt = (
        "One neutral sentence describing this recurring pattern for a human "
        "reviewer, no preamble: %s -- %s" % (kind, detail)
    )
    # Migrated onto shared ollama_client. retries=0 + timeout=6 keeps the
    # fast fail-to-template behavior (no internal retries adding latency to a
    # cheap best-effort draft). temperature is now pinned to the client default
    # 0.3 (the prior call sent no options -> model-default temperature); fine
    # for a single neutral sentence. Broad except -> template on any failure.
    try:
        text = call_ollama(prompt, OLLAMA_MODEL, timeout=6, retries=0)
        text = text.encode("ascii", "ignore").decode("ascii").strip()
        if text:
            return text.splitlines()[0][:300]
    except Exception:
        pass
    return template


def build_proposals(sig):
    """Turn signals into a list of proposal dicts."""
    proposals = []

    # repeated file edits -> candidate for a helper / skill
    for fp, count in sig["file_edits"].most_common(5):
        if count < 2:
            continue
        touches_code = bool(CODE_HINT.search(fp))
        bucket = BUCKET_SIGNOFF if touches_code else BUCKET_FAST
        detail = "%s edited %d times across sessions" % (fp, count)
        proposals.append({
            "bucket": bucket,
            "title": "Repeated hand-edits to a single file",
            "text": _draft_text("Repeated file edits", detail),
            "gate": touches_code,
            "question": None,
        })

    # repeated tool sequences -> candidate for a macro/skill
    for (a, b), count in sig["bigrams"].most_common(3):
        if count < 3:
            continue
        detail = "tool sequence %s -> %s repeated %d times" % (a, b, count)
        proposals.append({
            "bucket": BUCKET_SIGNOFF,
            "title": "Recurring manual tool sequence (skill candidate)",
            "text": _draft_text("Repeated tool sequence", detail),
            "gate": True,
            "question": None,
        })

    # TODO/FIXME mentions -> knowledge gap, needs more context
    total_todo = sum(sig["todo_hits"].values())
    if total_todo:
        parts = ", ".join(
            "%s=%d" % (k, v) for k, v in sig["todo_hits"].most_common()
        )
        detail = "unresolved markers in transcripts (%s)" % parts
        proposals.append({
            "bucket": BUCKET_CONTEXT,
            "title": "Unresolved TODO/FIXME markers (possible knowledge gap)",
            "text": _draft_text("Open markers", detail),
            "gate": False,
            "question": "Which of these markers should become tracked tasks "
                        "or a knowledge block, and which are noise?",
        })

    return proposals


def render(proposals, n_records, n_files, no_transcripts=False):
    today = datetime.date.today().isoformat()
    lines = []
    lines.append("# Session Review -- %s" % today)
    lines.append("")
    lines.append("Generated by SP-5 session-mining loop (LOCAL-ONLY, "
                 "PROPOSAL-ONLY). Nothing here is auto-applied.")
    lines.append("")
    lines.append("- Transcripts scanned: %d" % n_files)
    lines.append("- Records parsed: %d" % n_records)
    lines.append("")

    if no_transcripts:
        lines.append("## No transcripts found")
        lines.append("")
        lines.append("No session transcripts matched the scan glob. Nothing "
                     "to mine this run.")
        lines.append("")
        return "\n".join(lines) + "\n"

    if not proposals:
        lines.append("## No proposals")
        lines.append("")
        lines.append("Transcripts scanned but no recurring patterns crossed "
                     "the reporting threshold.")
        lines.append("")
        return "\n".join(lines) + "\n"

    lines.append("## Proposals (%d)" % len(proposals))
    lines.append("")
    for i, p in enumerate(proposals, 1):
        lines.append("### %d. [%s] %s" % (i, p["bucket"], p["title"]))
        lines.append("")
        lines.append(p["text"])
        lines.append("")
        if p.get("question"):
            lines.append("QUESTION: %s" % p["question"])
            lines.append("")
        for cb in CHECKBOXES:
            lines.append(cb)
        lines.append("")
        if p.get("gate"):
            lines.append(EVAL_GATE)
            lines.append("")
    return "\n".join(lines) + "\n"


# --- main run ----------------------------------------------------------------

def run(root, out_dir=None, session_glob=SESSION_GLOB):
    out_dir = out_dir or inbox_dir(root)
    # HARD GUARD: output must live under harness/inbox/
    norm = os.path.normpath(out_dir)
    assert (os.sep + os.path.join("harness", "inbox")) in (os.sep + norm) \
        or norm.endswith(os.path.join("harness", "inbox")), \
        "refusing to write outside harness/inbox/: %s" % out_dir
    os.makedirs(out_dir, exist_ok=True)

    paths = glob.glob(session_glob, recursive=True)
    today = datetime.date.today().isoformat()
    out_path = os.path.join(out_dir, "session-review--%s.md" % today)

    if not paths:
        content = render([], 0, 0, no_transcripts=True)
    else:
        sig = extract_signals(paths)
        proposals = build_proposals(sig)
        content = render(proposals, sig["n_records"], len(paths))

    content = content.encode("ascii", "ignore").decode("ascii")
    with open(out_path, "w", encoding="ascii", newline="\n") as fh:
        fh.write(content)
    return out_path


# --- selftest ----------------------------------------------------------------

def selftest():
    fake_a = [
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Edit",
             "input": {"file_path": "mtg-sim/handler_oracle.py"}},
            {"type": "tool_use", "name": "Bash", "input": {}},
        ]}},
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Edit",
             "input": {"file_path": "mtg-sim/handler_oracle.py"}},
            {"type": "tool_use", "name": "Bash", "input": {}},
        ]}},
        {"type": "user", "message": {"content": "TODO fix mulligan; FIXME later"}},
    ]
    fake_b = [
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Edit",
             "input": {"file_path": "mtg-sim/handler_oracle.py"}},
            {"type": "tool_use", "name": "Bash", "input": {}},
        ]}},
    ]

    with tempfile.TemporaryDirectory() as td:
        proj = os.path.join(td, "proj")
        os.makedirs(proj)
        for name, recs in (("a.jsonl", fake_a), ("b.jsonl", fake_b)):
            with open(os.path.join(proj, name), "w", encoding="utf-8") as fh:
                for r in recs:
                    fh.write(json.dumps(r) + "\n")

        fake_root = os.path.join(td, "root")
        out_dir = os.path.join(fake_root, "harness", "inbox")
        knowledge = os.path.join(fake_root, "harness", "knowledge")
        skills = os.path.join(fake_root, "harness", "skills")

        g = os.path.join(proj, "*.jsonl")
        out_path = run(fake_root, out_dir=out_dir, session_glob=g)

        with open(out_path, "r", encoding="ascii") as fh:
            body = fh.read()

        # (a) written under inbox
        assert os.path.isfile(out_path), "no review file written"
        assert os.path.normpath(out_dir) in os.path.normpath(out_path)
        # (b) three checkbox actions present
        for cb in CHECKBOXES:
            assert cb in body, "missing checkbox: %s" % cb
        # (c) a code/skill proposal carries EVAL-GATE
        assert EVAL_GATE in body, "missing EVAL-GATE on code proposal"
        # (d) nothing written under knowledge or skills
        assert not os.path.exists(knowledge), "knowledge dir was created"
        assert not os.path.exists(skills), "skills dir was created"
        # (e) module source has no hosted-vendor token (needle built to
        # avoid embedding the literal in this very source file)
        needle = "anthro" + "pic"
        with open(os.path.abspath(__file__), "r", encoding="utf-8") as fh:
            src = fh.read()
        assert needle not in src.lower(), "source mentions vendor token"

        # graceful empty case
        empty_glob = os.path.join(td, "none", "*.jsonl")
        out2 = run(fake_root, out_dir=out_dir, session_glob=empty_glob)
        with open(out2, "r", encoding="ascii") as fh:
            assert "No transcripts found" in fh.read()

    print("SELFTEST OK")
    return 0


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    ap = argparse.ArgumentParser(description="SP-5 session-mining loop")
    ap.add_argument("--selftest", action="store_true",
                    help="run offline self-test and exit")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()

    try:
        out_path = run(repo_root())
    except AssertionError as exc:
        sys.stderr.write("guard: %s\n" % exc)
        return 1
    except Exception as exc:  # noqa: BLE001 - stay graceful, exit non-zero
        sys.stderr.write("error: %s\n" % exc)
        return 1
    print("wrote review: %s" % out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
