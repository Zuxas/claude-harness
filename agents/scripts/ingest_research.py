#!/usr/bin/env python3
"""ingest_research.py -- LOCAL-ONLY research-queue ingester.

Drains a research-URL queue, fetches each page, produces a LOCAL-model
draft summary (Ollama only), writes a Source note into the research-brain
vault, and writes a run heartbeat. A stronger model does the real
synthesis later, on-demand -- this is the cheap local first pass.

LOCAL-ONLY: no external LLM provider is ever contacted. Only Ollama on
localhost is used for drafting. (Gate G6.)
"""

import sys
import re
import json
import argparse
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timezone
from urllib import request as urlrequest
from urllib.parse import urlparse
from urllib.error import URLError, HTTPError

# Shared streaming Ollama client (harness/agents/); this file is in
# harness/agents/scripts/, so hop up one dir.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ollama_client import call_ollama  # noqa: E402  (path set above)

# --- Paths (Windows, forward slashes) ---------------------------------------
QUEUE = Path("E:/vscode ai project/harness/inbox/research-queue.md")
SOURCES_DIR = Path("E:/vscode ai project/research-brain/Sources")
HEARTBEAT = Path("E:/vscode ai project/harness/state/research-ingest-last-run.json")
OLLAMA = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "gemma4"

USER_AGENT = "ingest-research/1.0 (+local)"
FETCH_TIMEOUT = 10
MAX_PAGE_CHARS = 6000
DONE_HEADING = "## done"


# --- Queue parsing ----------------------------------------------------------
def parse_queue(text):
    """Return list of URLs from queue text.

    A line counts as a URL if it starts with http:// or https:// (after
    stripping list/markdown markers). Blank lines, ``#`` comments, and any
    line at or after a ``## done`` heading are ignored.
    """
    urls = []
    for raw in text.splitlines():
        line = raw.strip()
        if line.lower() == DONE_HEADING:
            break
        if not line or line.startswith("#"):
            continue
        # strip common markdown list markers
        candidate = line.lstrip("-*+ \t").strip()
        # unwrap markdown link/angle-bracket forms crudely
        m = re.search(r"(https?://\S+)", candidate)
        if m:
            url = m.group(1).rstrip(">)].,")
            urls.append(url)
    return urls


def split_done(text):
    """Split queue text into (active_text, done_urls_set)."""
    lines = text.splitlines()
    done_urls = set()
    active_lines = []
    in_done = False
    for raw in lines:
        if raw.strip().lower() == DONE_HEADING:
            in_done = True
            continue
        if in_done:
            m = re.search(r"(https?://\S+)", raw)
            if m:
                done_urls.add(m.group(1).rstrip(">)].,"))
        else:
            active_lines.append(raw)
    return "\n".join(active_lines), done_urls


# --- HTML fetch/strip -------------------------------------------------------
def fetch_page(url):
    """Fetch url and return raw text (may raise)."""
    req = urlrequest.Request(url, headers={"User-Agent": USER_AGENT})
    with urlrequest.urlopen(req, timeout=FETCH_TIMEOUT) as resp:
        raw = resp.read()
    charset = "utf-8"
    try:
        ctype = resp.headers.get_content_charset()
        if ctype:
            charset = ctype
    except Exception:
        pass
    return raw.decode(charset, errors="replace")


def extract_title(html):
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if m:
        title = re.sub(r"\s+", " ", m.group(1)).strip()
        if title:
            return title
    return None


def strip_html(html):
    """Crudely strip HTML to plain text."""
    # remove script/style blocks
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", html,
                  flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text,
                  flags=re.IGNORECASE | re.DOTALL)
    # remove remaining tags
    text = re.sub(r"<[^>]+>", " ", text)
    # collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


# --- Local model draft (Ollama only) ----------------------------------------
def local_draft(page_text):
    """Call Ollama for a <=200-word factual summary.

    Returns (draft_string, error_or_None). On any failure returns a
    graceful placeholder draft and the reason. Only ever contacts Ollama
    on localhost.
    """
    prompt = (
        "Summarize the following web page content in at most 200 words. "
        "Be strictly factual, no speculation, no marketing language. "
        "Content:\n\n" + page_text
    )
    # Migrated onto shared ollama_client. retries=0 keeps the fast single-shot
    # degrade-on-failure behavior (a stronger model re-synthesizes later).
    # temperature is now pinned to the client default 0.3 (the prior call sent
    # no options, so it used the model's default sampling temperature) -- fine
    # for a strictly-factual summary. The client raises on empty/error; the
    # broad except below preserves the graceful-placeholder contract.
    try:
        draft = call_ollama(prompt, OLLAMA_MODEL, timeout=120, retries=0).strip()
        if not draft:
            return ("[local draft unavailable: empty response]",
                    "empty response")
        return (draft, None)
    except Exception as exc:  # noqa: BLE001 - graceful by design
        reason = "ollama error: {}".format(exc)
        return ("[local draft unavailable: {}]".format(reason), reason)


# --- Source note ------------------------------------------------------------
def safe_title(title, url):
    """Produce an ASCII, filesystem-safe title string."""
    if not title:
        title = urlparse(url).netloc or url
    # ASCII only
    title = title.encode("ascii", errors="ignore").decode("ascii")
    # remove characters illegal on Windows filesystems
    title = re.sub(r'[<>:"/\\|?*]', " ", title)
    title = re.sub(r"\s+", " ", title).strip()
    if not title:
        title = urlparse(url).netloc or "source"
        title = title.encode("ascii", errors="ignore").decode("ascii")
    # keep filenames reasonable
    return title[:80].strip()


def build_note(url, title, draft, today):
    return (
        "---\n"
        "type: source\n"
        "date: {date}\n"
        "tags: [source]\n"
        "ai-first: true\n"
        "status: pending-synthesis\n"
        "sources:\n"
        "  - {url}\n"
        "confidence: medium\n"
        "---\n"
        "For future synthesis: local-drafted source note, pending synthesis. "
        "NOT yet promoted.\n"
        "\n"
        "## Source\n"
        "{url}\n"
        "\n"
        "## Draft summary (local model, unverified)\n"
        "{draft}\n"
    ).format(date=today, url=url, draft=draft)


def unique_path(sources_dir, base_name):
    """Return a non-colliding path for base_name (without extension)."""
    path = sources_dir / (base_name + ".md")
    if not path.exists():
        return path
    i = 2
    while True:
        path = sources_dir / ("{} ({}).md".format(base_name, i))
        if not path.exists():
            return path
        i += 1


# --- Dedupe -----------------------------------------------------------------
def existing_urls(sources_dir):
    """Return set of URL strings already referenced by Source notes."""
    found = set()
    if not sources_dir.exists():
        return found
    for md in sources_dir.glob("*.md"):
        try:
            content = md.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for m in re.finditer(r"https?://\S+", content):
            found.add(m.group(0).rstrip(">)].,"))
    return found


# --- Heartbeat --------------------------------------------------------------
def write_heartbeat(path, urls_processed, new_sources, skipped, errors):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "last_run": datetime.now(timezone.utc).isoformat(),
        "urls_processed": urls_processed,
        "new_sources": new_sources,
        "skipped": skipped,
        "errors": errors,
    }
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


# --- Queue rewrite ----------------------------------------------------------
def rewrite_queue(queue_path, processed_urls):
    """Move processed URLs under a ## done section at end of the queue."""
    text = queue_path.read_text(encoding="utf-8", errors="replace")
    active_text, done_urls = split_done(text)

    # Remove processed URL lines from the active section.
    keep_lines = []
    for raw in active_text.splitlines():
        m = re.search(r"(https?://\S+)", raw)
        if m and m.group(1).rstrip(">)].,") in processed_urls:
            continue
        keep_lines.append(raw)
    active_body = "\n".join(keep_lines).rstrip()

    all_done = list(done_urls) + [u for u in processed_urls if u not in done_urls]
    done_body = DONE_HEADING + "\n" + "\n".join(all_done) + "\n"

    new_text = (active_body + "\n\n" if active_body else "") + done_body
    queue_path.write_text(new_text, encoding="utf-8")


# --- Main run ---------------------------------------------------------------
def run(queue_path=QUEUE, sources_dir=SOURCES_DIR, heartbeat_path=HEARTBEAT,
        do_fetch=True, drafter=local_draft):
    today = datetime.now().strftime("%Y-%m-%d")
    errors = []
    skipped = 0
    new_sources = 0
    processed = []

    if not queue_path.exists():
        write_heartbeat(heartbeat_path, 0, 0, 0, ["queue not found"])
        return {"urls_processed": 0, "new_sources": 0, "skipped": 0,
                "errors": ["queue not found"]}

    queue_text = queue_path.read_text(encoding="utf-8", errors="replace")
    urls = parse_queue(queue_text)
    seen_existing = existing_urls(sources_dir)

    sources_dir.mkdir(parents=True, exist_ok=True)

    run_seen = set()
    for url in urls:
        if url in run_seen:
            continue
        run_seen.add(url)

        if url in seen_existing:
            skipped += 1
            processed.append(url)
            continue

        title = None
        page_text = ""
        if do_fetch:
            try:
                html = fetch_page(url)
                title = extract_title(html)
                page_text = strip_html(html)[:MAX_PAGE_CHARS]
            except Exception as exc:  # noqa: BLE001
                errors.append("fetch {}: {}".format(url, exc))

        if page_text:
            draft, derr = drafter(page_text)
            if derr:
                errors.append("draft {}: {}".format(url, derr))
        else:
            draft = "[local draft unavailable: no page text fetched]"

        st = safe_title(title, url)
        note_path = unique_path(sources_dir, "Source - {} ({})".format(st, today))
        note_path.write_text(build_note(url, title, draft, today),
                             encoding="utf-8")
        new_sources += 1
        seen_existing.add(url)
        processed.append(url)

    if processed:
        rewrite_queue(queue_path, processed)

    hb = write_heartbeat(heartbeat_path, len(processed), new_sources,
                         skipped, errors)
    return {
        "urls_processed": hb["urls_processed"],
        "new_sources": hb["new_sources"],
        "skipped": hb["skipped"],
        "errors": errors,
    }


# --- Selftest ---------------------------------------------------------------
def selftest():
    """Offline self-test. No network, no Ollama required."""
    tmp = Path(tempfile.mkdtemp(prefix="ingest_selftest_"))
    try:
        q = tmp / "queue.md"
        src = tmp / "Sources"
        hb = tmp / "state" / "hb.json"

        # queue with a comment, blanks, two urls, a dupe target, and a done section
        q.write_text(
            "# research queue\n"
            "\n"
            "https://example.com/alpha\n"
            "- https://example.org/beta\n"
            "https://example.com/already\n"
            "\n"
            "## done\n"
            "https://example.net/old\n",
            encoding="utf-8",
        )

        # Verify parse ignores comments/blanks/done
        parsed = parse_queue(q.read_text(encoding="utf-8"))
        assert parsed == [
            "https://example.com/alpha",
            "https://example.org/beta",
            "https://example.com/already",
        ], "parse_queue mismatch: {}".format(parsed)

        # Pre-seed a Source note referencing 'already' to test dedupe.
        src.mkdir(parents=True, exist_ok=True)
        (src / "Source - preexisting (2000-01-01).md").write_text(
            "---\ntype: source\nsources:\n  - https://example.com/already\n---\n"
            "## Source\nhttps://example.com/already\n",
            encoding="utf-8",
        )

        def fake_drafter(text):
            return ("Offline draft summary for selftest.", None)

        result = run(queue_path=q, sources_dir=src, heartbeat_path=hb,
                     do_fetch=False, drafter=fake_drafter)

        # dedupe: 'already' skipped, two new notes.
        assert result["skipped"] == 1, "expected 1 skipped, got {}".format(result)
        assert result["new_sources"] == 2, "expected 2 new, got {}".format(result)

        # A Source note must exist with required frontmatter keys.
        notes = [p for p in src.glob("*.md") if "preexisting" not in p.name]
        assert notes, "no Source note produced"
        note_text = notes[0].read_text(encoding="utf-8")
        for key in ("type: source", "date:", "tags: [source]",
                    "ai-first: true", "status: pending-synthesis",
                    "sources:", "confidence: medium",
                    "## Source", "## Draft summary (local model, unverified)"):
            assert key in note_text, "note missing {!r}".format(key)

        # Heartbeat json has required keys.
        hb_data = json.loads(hb.read_text(encoding="utf-8"))
        for key in ("last_run", "urls_processed", "new_sources",
                    "skipped", "errors"):
            assert key in hb_data, "heartbeat missing {!r}".format(key)

        # Queue must now carry a done section with processed urls.
        qtext = q.read_text(encoding="utf-8")
        assert DONE_HEADING in qtext, "queue lost done heading"
        assert "https://example.com/alpha" in qtext.split(DONE_HEADING, 1)[1]

        # Module source must not reference the forbidden provider (gate G6).
        # Build the tokens dynamically so this check does not itself embed them.
        module_src = Path(__file__).read_text(encoding="utf-8")
        low = module_src.lower()
        forbidden_root = "anthrop" + "ic"
        forbidden_api = "api." + forbidden_root
        assert forbidden_root not in low, "forbidden provider token present"
        assert forbidden_api not in low, "forbidden api host token present"

        print("SELFTEST OK")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --- CLI --------------------------------------------------------------------
def main(argv=None):
    parser = argparse.ArgumentParser(description="Local research-queue ingester.")
    parser.add_argument("--selftest", action="store_true",
                        help="run offline self-test and exit")
    args = parser.parse_args(argv)

    if args.selftest:
        selftest()
        return 0

    result = run()
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write("error: {}\n".format(exc))
        sys.exit(1)
