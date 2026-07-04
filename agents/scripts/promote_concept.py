#!/usr/bin/env python3
"""promote_concept.py -- scaffold/commit a research-brain Concept into Tier K.

Deterministic, stdlib-only. NO LLM, NO network.

Modes (mutually exclusive):
  --recommend <concept_path>          FAST | COUNCIL | NEEDS-CONTEXT (+reason)
  --concept   <concept_path>          scaffold a Tier-K block into STAGE (never KNOW)
  --commit    <staged_path>           the ONLY writer of KNOW (move + index)
  --selftest                          in-memory self checks

HARD SAFETY INVARIANT: only --commit may write anything under KNOW
(harness/knowledge/). --recommend and --concept must never write there; the
guard _assert_not_writing_knowledge() enforces this before every scaffold write.
"""

import argparse
import datetime
import pathlib
import re
import shutil
import sys

# --- Paths (Windows) --------------------------------------------------------
VAULT = pathlib.Path("E:/vscode ai project/research-brain")
KNOW = pathlib.Path("E:/vscode ai project/harness/knowledge")
STAGE = pathlib.Path("E:/vscode ai project/harness/inbox/promoted")
INDEX = pathlib.Path("E:/vscode ai project/harness/knowledge/_index.md")

TODAY = datetime.date.today().isoformat()

# numeric / competitive claim regex (case-insensitive)
CLAIM_RE = re.compile(
    r"\d+(\.\d+)?\s*%"
    r"|win rate|winrate|beats|favored|unfavored|matchup|vs\.?\s|meta share"
    r"|\b\d+-of\b",
    re.IGNORECASE,
)
URL_RE = re.compile(r"https?://", re.IGNORECASE)


# --- Safety guard -----------------------------------------------------------
def _assert_not_writing_knowledge(path):
    """Raise if `path` is at or under KNOW. Called before every scaffold write."""
    p = pathlib.Path(path).resolve()
    know = KNOW.resolve()
    if p == know or know in p.parents:
        raise RuntimeError(
            "SAFETY: refusing to write under harness/knowledge in scaffold mode: %s"
            % p
        )


# --- Tiny frontmatter parser (no yaml) --------------------------------------
def _strip_quotes(s):
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        return s[1:-1]
    return s


def parse_frontmatter(text):
    """Return (frontmatter_dict, body_str). Values are str or list[str]."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}, text
    fm_lines = lines[1:end]
    body = "\n".join(lines[end + 1:])
    fm = {}
    i = 0
    while i < len(fm_lines):
        line = fm_lines[i]
        if not line.strip() or line.lstrip().startswith("#"):
            i += 1
            continue
        m = re.match(r"^([A-Za-z0-9_\-]+):\s*(.*)$", line)
        if not m:
            i += 1
            continue
        key = m.group(1).strip()
        val = m.group(2).strip()
        if val == "":
            items = []
            j = i + 1
            while j < len(fm_lines):
                lm = re.match(r"^\s*-\s+(.*)$", fm_lines[j])
                if lm:
                    items.append(_strip_quotes(lm.group(1).strip()))
                    j += 1
                else:
                    break
            fm[key] = items if items else ""
            i = j
        elif val.startswith("[") and val.endswith("]"):
            inner = val[1:-1].strip()
            fm[key] = (
                [] if inner == "" else [_strip_quotes(x) for x in inner.split(",")]
            )
            i += 1
        else:
            fm[key] = _strip_quotes(val)
            i += 1
    return fm, body


def _sources_list(fm):
    """Normalize the frontmatter 'sources' value into a list of strings."""
    v = fm.get("sources")
    if v is None:
        return []
    if isinstance(v, list):
        return [s for s in (x.strip() for x in v) if s]
    v = v.strip()
    return [v] if v else []


def _has_sources(fm):
    return len(_sources_list(fm)) > 0


def _first_paragraph(body):
    """Concept preamble / first non-heading paragraph."""
    paras = re.split(r"\n\s*\n", body.strip())
    for p in paras:
        p = p.strip()
        if p and not p.startswith("#"):
            return p
    return "(no summary)"


# --- Mode: recommend --------------------------------------------------------
def recommend(fm, body):
    """Return (verdict, reason, question_or_None). Rules evaluated in order."""
    has_claim = bool(CLAIM_RE.search(body))
    # a claim is verifiable if there's a URL anywhere in the note -- body OR the
    # frontmatter sources list (not body-only; that dropped source-backed claims).
    has_url = bool(URL_RE.search(body)) or any(
        URL_RE.search(str(s)) for s in _sources_list(fm)
    )
    conf = fm.get("confidence")
    conf = conf.strip().lower() if isinstance(conf, str) else conf

    # 1. NEEDS-CONTEXT
    if not _has_sources(fm):
        return (
            "NEEDS-CONTEXT",
            "no sources in frontmatter; cannot verify provenance",
            "add a 'sources' key with at least one source/URL",
        )
    if "confidence" not in fm or fm.get("confidence") in ("", None):
        return (
            "NEEDS-CONTEXT",
            "no confidence in frontmatter; cannot assess reliability",
            "add a 'confidence' key (high/medium/speculation)",
        )
    if has_claim and not has_url:
        return (
            "NEEDS-CONTEXT",
            "falsifiable/numeric/competitive claim present but no source URL in the note",
            "add an http(s) source URL (in the body or sources) backing the claim",
        )

    # 2. COUNCIL
    if conf in ("medium", "speculation"):
        return (
            "COUNCIL",
            "confidence is %s; council should re-verify before blessing" % conf,
            None,
        )
    if has_claim:
        return (
            "COUNCIL",
            "numeric/competitive claim present; council should re-verify vs sources",
            None,
        )

    # 3. FAST
    return ("FAST", "sourced, confident, no falsifiable claims to re-verify", None)


def do_recommend(concept_path):
    text = pathlib.Path(concept_path).read_text(encoding="utf-8")
    fm, body = parse_frontmatter(text)
    verdict, reason, question = recommend(fm, body)
    out = [verdict, "reason: " + reason]
    if question is not None:
        out.append("QUESTION: " + question)
    sys.stdout.write("\n".join(out) + "\n")
    return 0


# --- Mode: concept (scaffold) ----------------------------------------------
def _slug(stem):
    return re.sub(r"[^a-z0-9]+", "-", stem.lower()).strip("-")


def build_block(title, domain, confidence, sources, summary, content):
    lines = []
    lines.append("---")
    lines.append('title: "%s"' % title)
    lines.append('domain: "%s"' % domain)
    lines.append('last_updated: "%s"' % TODAY)
    lines.append('confidence: "%s"' % confidence)
    lines.append("sources:")
    for s in sources:
        lines.append("  - %s" % s)
    lines.append("---")
    lines.append("")
    lines.append("## Summary")
    lines.append(summary)
    lines.append("")
    lines.append("## Content")
    lines.append(content)
    lines.append("")
    lines.append("## Changelog")
    lines.append(
        "- %s: promoted from research-brain (STAGED, pending human review)." % TODAY
    )
    lines.append("")
    return "\n".join(lines)


def scaffold(concept_path, domain, stage_dir):
    """Build a Tier-K block from a concept and write it under stage_dir. Returns path."""
    concept_path = pathlib.Path(concept_path)
    text = concept_path.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(text)

    title = fm.get("title") if isinstance(fm.get("title"), str) else None
    if not title:
        title = concept_path.stem
    confidence = fm.get("confidence")
    confidence = confidence if isinstance(confidence, str) and confidence else "medium"

    sources = ["\"research-brain concept: %s\"" % concept_path.as_posix()]
    sources.extend(_sources_list(fm))

    summary = _first_paragraph(body)
    content = body.strip() if body.strip() else "(no content)"

    block = build_block(title, domain, confidence, sources, summary, content)

    slug = _slug(concept_path.stem)
    out_path = pathlib.Path(stage_dir) / ("%s--%s.md" % (domain, slug))

    _assert_not_writing_knowledge(out_path)
    pathlib.Path(stage_dir).mkdir(parents=True, exist_ok=True)
    _assert_not_writing_knowledge(out_path)
    out_path.write_text(block, encoding="utf-8")
    return out_path


def do_concept(concept_path, domain):
    out_path = scaffold(concept_path, domain, STAGE)
    sys.stdout.write(str(out_path) + "\n")
    return 0


# --- Mode: commit (only KNOW writer) ---------------------------------------
def do_commit(staged_path, domain, council_verdict, force):
    staged_path = pathlib.Path(staged_path)
    if not staged_path.is_file():
        raise RuntimeError("staged file not found: %s" % staged_path)

    stem = staged_path.stem
    slug = stem.split("--", 1)[1] if "--" in stem else stem

    target_dir = KNOW / domain
    target = target_dir / ("%s.md" % slug)
    if target.exists() and not force:
        raise RuntimeError(
            "target exists (use --force to overwrite): %s" % target
        )

    content = staged_path.read_text(encoding="utf-8")

    if council_verdict:
        vpath = pathlib.Path(council_verdict).as_posix()
        cl_line = "- %s: council-verified -> %s" % (TODAY, vpath)
        content = _append_changelog(content, cl_line)

    target_dir.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    staged_path.unlink()

    row = "| %s/%s | %s | %s | promoted from research-brain |\n" % (
        domain,
        slug,
        domain,
        TODAY,
    )
    INDEX.parent.mkdir(parents=True, exist_ok=True)
    # newline-safe append: never glue the new row onto a file that doesn't end
    # in a newline (that previously merged the row into the prior index line).
    existing = INDEX.read_text(encoding="utf-8") if INDEX.exists() else ""
    prefix = "" if (existing == "" or existing.endswith("\n")) else "\n"
    with INDEX.open("a", encoding="utf-8") as fh:
        fh.write(prefix + row)

    sys.stdout.write(str(target) + "\n")
    return 0


def _append_changelog(content, cl_line):
    """Insert cl_line at the end of the ## Changelog section (append to file if none)."""
    lines = content.splitlines()
    idx = None
    for i, ln in enumerate(lines):
        if ln.strip().lower() == "## changelog":
            idx = i
            break
    if idx is None:
        return content.rstrip("\n") + "\n\n## Changelog\n" + cl_line + "\n"
    # find end of changelog block (next heading or EOF)
    end = len(lines)
    for j in range(idx + 1, len(lines)):
        if lines[j].startswith("## "):
            end = j
            break
    # insertion point: after last non-blank line within the section
    insert_at = idx + 1
    for j in range(idx + 1, end):
        if lines[j].strip():
            insert_at = j + 1
    lines.insert(insert_at, cl_line)
    return "\n".join(lines) + ("\n" if content.endswith("\n") else "")


# --- Self test --------------------------------------------------------------
def selftest():
    import tempfile

    fast = (
        "---\n"
        'title: "Stable Fact"\n'
        "confidence: high\n"
        "sources:\n"
        "  - https://example.com/doc\n"
        "---\n\n"
        "A calm settled fact with no falsifiable competitive claims.\n"
    )
    council = (
        "---\n"
        'title: "Medium Take"\n'
        "confidence: medium\n"
        "sources:\n"
        "  - https://example.com/doc\n"
        "---\n\n"
        "Some analysis with a source.\n"
    )
    council_claim = (
        "---\n"
        'title: "Claim With URL"\n'
        "confidence: high\n"
        "sources:\n"
        "  - https://example.com/doc\n"
        "---\n\n"
        "Deck A beats Deck B with a 62% win rate. See https://example.com/doc\n"
    )
    needs_nosrc = (
        "---\n"
        'title: "No Sources"\n'
        "confidence: high\n"
        "---\n\n"
        "Body text.\n"
    )
    needs_claim_nourl = (
        "---\n"
        'title: "Claim No URL"\n'
        "confidence: high\n"
        "sources:\n"
        "  - some-book\n"
        "---\n\n"
        "This deck is favored 55% in the matchup.\n"
    )

    def verd(t):
        fm, body = parse_frontmatter(t)
        return recommend(fm, body)[0]

    assert verd(fast) == "FAST", verd(fast)
    assert verd(council) == "COUNCIL", verd(council)
    assert verd(council_claim) == "COUNCIL", verd(council_claim)
    assert verd(needs_nosrc) == "NEEDS-CONTEXT", verd(needs_nosrc)
    assert verd(needs_claim_nourl) == "NEEDS-CONTEXT", verd(needs_claim_nourl)

    # guard must raise for a KNOW-bound path
    raised = False
    try:
        _assert_not_writing_knowledge(KNOW / "tech" / "x.md")
    except RuntimeError:
        raised = True
    assert raised, "guard failed to block a KNOW path"

    # scaffold must write to STAGE (here a temp dir), never KNOW, and leave
    # nothing under KNOW.
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="promote_selftest_"))
    try:
        concept = tmp / "my-concept.md"
        concept.write_text(council_claim, encoding="utf-8")
        stage_dir = tmp / "stage"
        out = scaffold(concept, "tech", stage_dir)
        assert out.exists(), "scaffold produced no file"
        assert out.parent.resolve() == stage_dir.resolve(), out
        know = KNOW.resolve()
        assert know not in out.resolve().parents and out.resolve() != know, out
        assert out.name == "tech--my-concept.md", out.name
        text = out.read_text(encoding="utf-8")
        assert "## Summary" in text and "## Content" in text and "## Changelog" in text
        assert "research-brain concept:" in text
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    sys.stdout.write("SELFTEST OK\n")
    return 0


# --- CLI --------------------------------------------------------------------
def build_parser():
    p = argparse.ArgumentParser(
        description="Promote a research-brain Concept into the harness knowledge base."
    )
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--recommend", metavar="CONCEPT", help="print promotion recommendation")
    g.add_argument("--concept", metavar="CONCEPT", help="scaffold a staged Tier-K block")
    g.add_argument("--commit", metavar="STAGED", help="commit a staged block into KNOW")
    g.add_argument("--selftest", action="store_true", help="run in-memory self checks")
    p.add_argument("--domain", default="tech", help="knowledge domain (default: tech)")
    p.add_argument("--council-verdict", metavar="FILE", help="council verdict file to record")
    p.add_argument("--force", action="store_true", help="overwrite existing commit target")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        if args.selftest:
            return selftest()
        if args.recommend:
            return do_recommend(args.recommend)
        if args.concept:
            return do_concept(args.concept, args.domain)
        if args.commit:
            return do_commit(args.commit, args.domain, args.council_verdict, args.force)
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write("error: %s\n" % exc)
        return 1
    return 1


if __name__ == "__main__":
    sys.exit(main())
