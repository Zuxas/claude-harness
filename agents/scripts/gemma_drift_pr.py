"""
gemma_drift_pr.py -- Background drift PR generator using Gemma 4.

OpenAI Codex pattern from the Harness Engineering blog post: an LLM reads
the day's harness state overnight and produces a structured "drift PR"
with concrete recommendations that next-session-Claude reads at startup.

This is RECOMMENDATION GENERATION, not auto-applied changes. Gemma drafts;
Claude reviews; user decides.

INPUTS (read-only):
  1. Today's git log from mtg-sim (commits + messages, last 24h)
  2. harness/state/latest-snapshot.md (current state)
  3. harness/knowledge/tech/drift-YYYY-MM-DD.md (today's drift findings if any)
  4. harness/IMPERFECTIONS.md (open items)
  5. harness/specs/_index.md (specs by status)
  6. Recent findings docs in harness/knowledge/tech/ (last 7 days)

OUTPUT:
  harness/inbox/drift-pr--YYYY-MM-DD.md
  
  Structured markdown with:
  - Summary of today's commits in plain English
  - Patterns observed across commits
  - Imperfections likely compounding from today's work
  - Recommended fixes for next session (ranked by impact/cost)
  - Spec status concerns (stalled EXECUTING, aged PROPOSED)
  - Methodology lesson candidates from today's amendments

USAGE:
  python gemma_drift_pr.py                    # full run
  python gemma_drift_pr.py --dry-run          # build prompt, don't call Gemma
  python gemma_drift_pr.py --show-prompt      # print prompt to stdout
  python gemma_drift_pr.py --model gemma4     # use specific model

Last updated: 2026-04-27 (initial build + UTF-8 stdout fix)
"""

import sys
import os
import json
import time
import argparse
import subprocess
from pathlib import Path
from datetime import datetime, timedelta

# Force UTF-8 stdout/stderr on Windows so --show-prompt and log output don't
# crash on non-cp1252 chars (>=, em-dashes, smart quotes, box-drawing, etc.).
# Python 3.13 on Windows still defaults stdout to cp1252 when piped to a file
# or another process; fix by reconfiguring once at startup.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    # Older Pythons (<3.7) don't have reconfigure; nothing to do.
    pass

# Paths
HARNESS_ROOT = Path("E:/vscode ai project/harness")
SIM_ROOT = Path("E:/vscode ai project/mtg-sim")
INBOX_DIR = HARNESS_ROOT / "inbox"
STATE_DIR = HARNESS_ROOT / "state"
KNOWLEDGE_TECH = HARNESS_ROOT / "knowledge" / "tech"
SPECS_DIR = HARNESS_ROOT / "specs"
LOG_DIR = HARNESS_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

# Add agent_hardening to path
sys.path.insert(0, str(HARNESS_ROOT / "agents" / "scripts"))

from agent_hardening import AgentLogger, check_ollama_health, ollama_breaker
import urllib.request

log = AgentLogger("gemma-drift-pr")
OLLAMA_API = "http://localhost:11434/api/generate"
TODAY = datetime.now().strftime("%Y-%m-%d")
TODAY_HHMM = datetime.now().strftime("%Y-%m-%d %H:%M")

# Token budget management
MAX_GIT_LOG_DAYS = 1            # only today's commits
MAX_FINDINGS_DAYS = 7           # last week of findings docs
MAX_INPUT_CHARS = 60000         # ~15k tokens, leaves room for output


# ---------------------------------------------------------------------------
# Input collectors
# ---------------------------------------------------------------------------

def collect_git_log(repo_path: Path, since_hours: int = 24) -> str:
    """Get commits from last N hours, formatted for LLM consumption."""
    if not (repo_path / ".git").exists():
        return "[no git repo at " + str(repo_path) + "]"
    
    since_str = f"{since_hours} hours ago"
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_path), "log",
             f"--since={since_str}",
             "--pretty=format:%h %ad %s%n%b%n---END-COMMIT---",
             "--date=short"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            return "[git log failed: " + result.stderr.strip() + "]"
        out = result.stdout.strip()
        if not out:
            return "[no commits in last " + str(since_hours) + " hours]"
        return out
    except Exception as e:
        return "[git log error: " + str(e) + "]"


def collect_uncommitted(repo_path: Path) -> str:
    """Get uncommitted changes summary."""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_path), "status", "--short"],
            capture_output=True, text=True, timeout=10
        )
        out = result.stdout.strip()
        return out if out else "[clean]"
    except Exception as e:
        return "[git status error: " + str(e) + "]"


def collect_file(path: Path, max_chars: int = 20000) -> str:
    """Read a file with size cap."""
    if not path.exists():
        return "[missing: " + str(path) + "]"
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        if len(text) > max_chars:
            text = text[:max_chars] + "\n\n[...truncated at " + str(max_chars) + " chars...]"
        return text
    except Exception as e:
        return "[read error " + str(path) + ": " + str(e) + "]"


def collect_recent_findings(directory: Path, days: int = 7) -> str:
    """Concatenate findings docs touched in the last N days."""
    if not directory.exists():
        return "[directory not found]"
    
    cutoff = time.time() - (days * 86400)
    relevant = []
    
    for md in sorted(directory.glob("*.md")):
        try:
            mtime = md.stat().st_mtime
            if mtime > cutoff:
                age_days = (time.time() - mtime) / 86400
                relevant.append((mtime, md.name, age_days))
        except Exception:
            continue
    
    if not relevant:
        return "[no findings touched in last " + str(days) + " days]"
    
    relevant.sort(reverse=True)  # newest first
    out = []
    for mtime, fname, age in relevant:
        age_label = "today" if age < 1 else f"{age:.1f}d ago"
        out.append(f"- {fname} ({age_label})")
    
    return "\n".join(out)


def collect_specs_by_status(specs_dir: Path) -> dict:
    """Group spec files by their status frontmatter."""
    by_status = {"PROPOSED": [], "EXECUTING": [], "SHIPPED": [], "SUPERSEDED": [], "OTHER": []}
    
    if not specs_dir.exists():
        return by_status
    
    for spec in sorted(specs_dir.glob("*.md")):
        if spec.name.startswith("_") or spec.name == "RETROACTIVE.md" or spec.name == "README.md":
            continue
        try:
            text = spec.read_text(encoding="utf-8", errors="replace")[:1500]
            status = "OTHER"
            for line in text.splitlines()[:30]:
                if line.strip().lower().startswith("status:"):
                    val = line.split(":", 1)[1].strip().strip('"').strip("'").upper()
                    if val in by_status:
                        status = val
                    break
            by_status[status].append(spec.name)
        except Exception:
            by_status["OTHER"].append(spec.name)
    
    return by_status


# ---------------------------------------------------------------------------
# Gemma API call
# ---------------------------------------------------------------------------

def ask_gemma(prompt, system="", model="gemma4", max_tokens=4096, temperature=0.3):
    """Call Gemma via Ollama API with circuit breaker. Returns (text, error)."""
    if not check_ollama_health():
        return None, "Ollama unavailable"
    
    body = json.dumps({
        "model": model,
        "prompt": prompt,
        "system": system,
        "stream": False,
        "options": {"temperature": temperature, "num_predict": max_tokens}
    }).encode()
    
    try:
        req = urllib.request.Request(
            OLLAMA_API, data=body,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=600) as resp:
            result = json.loads(resp.read()).get("response", "")
            ollama_breaker.record_success()
            return result, None
    except Exception as e:
        ollama_breaker.record_failure()
        return None, str(e)


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a senior software engineer reviewing the day's work on a Magic: The Gathering simulation engine project ("mtg-sim") that uses a structured harness for AI-assisted development.

Your job: produce a "drift PR" -- a concise structured report that the next development session reads at startup to land oriented on the state of work.

You are NOT generating code. You are generating recommendations and observations. Be specific, mechanical, and falsifiable. Avoid hedging language. Avoid restating things the human already knows from session-log style reports.

Audience: a senior engineer (Jermey) and an AI assistant (Claude) working together. They have full context on the project. They want concrete next-action items, not summaries of what they already did today.

Format: markdown with the section headers given in the user prompt. Keep total output under 1200 words. Be terse where terseness adds clarity; be specific where specificity adds value.

Style anti-patterns to avoid:
- "Today was a productive day" (no value)
- "Consider reviewing X" (vague)
- Bullet lists of every commit (just point at the most important 2-3)
- Restating IMPERFECTIONS verbatim (the human already has the file)

Style targets:
- "Stage A's amendment-1 fix is the same per-iteration-vs-cross-iteration class as last week's combo damage bug" (pattern recognition)
- "EXECUTING for 31 hours; either ship or abandon" (concrete trigger)
- "Mono Red haste-density model didn't catch this; lesson candidate: extend to flash creatures pre-Stage-D" (forward-looking)
"""


USER_PROMPT_TEMPLATE = """# Drift PR generation request

Date: {today}

I'm giving you the day's harness state. Produce a structured drift PR following the section headers below. This will be saved to `harness/inbox/drift-pr--{today}.md` and read by the next development session at startup.

---

## INPUT 1: Today's git log (mtg-sim)

```
{git_log}
```

## INPUT 2: Uncommitted changes (mtg-sim)

```
{uncommitted}
```

## INPUT 3: Latest session snapshot

```
{snapshot}
```

## INPUT 4: Today's drift findings (if any)

```
{drift_findings}
```

## INPUT 5: Open imperfections

```
{imperfections}
```

## INPUT 6: Specs by status

PROPOSED: {specs_proposed}
EXECUTING: {specs_executing}
SHIPPED (today/recent): {specs_shipped}

## INPUT 7: Findings docs touched in last 7 days

```
{recent_findings}
```

## INPUT 8: Spec authoring lessons (for cross-referencing patterns)

```
{lessons}
```

---

# YOUR OUTPUT

Produce a markdown document with EXACTLY these sections, in this order:

## Summary

Two sentences max. The shape of today: how many commits, what arc they advanced, what the headline metric movement was.

## Patterns observed

Cross-commit patterns. Did multiple commits touch the same file? Did multiple amendments produce the same class of methodology lesson? Are imperfections clustering around a single subsystem? 1-3 patterns max. If no patterns visible, write "None observed."

## Imperfections likely to compound

Look at the imperfections registry. Which open items got worse today (more code touched the affected subsystem)? Which got better (today's work moved toward closing them)? Specific. 1-3 items max.

## Recommended next-session work (ranked)

3-5 items, ordered by (impact / cost). For each: title, what it does, why it's the right next thing, estimated time. Don't just list everything that's pending; PICK the next 3-5 that maximize compounding.

Format:
```
1. **<title>** (~Nmin)
   - What: <one-line action>
   - Why now: <one-line rationale, ideally tying to today's work>
   - Risk: <low/medium/high + reason>
```

## Spec status concerns

Any EXECUTING spec older than 24h? Any PROPOSED spec older than 14d? Any SHIPPED spec missing a commit hash? List them. If clean, write "Clean."

## Methodology lesson candidates

Did any of today's commit messages or spec amendments contain a generalizable methodology lesson that should be added to spec-authoring-lessons.md? Be specific: name the lesson, summarize it in one line, point at the source amendment. If no candidates, write "None observed."

## Open questions for next session

Things that need user decision, not Claude decision. Ranked by urgency. Empty list is fine.

---

Keep total output under 1200 words. Use the section headers verbatim. Don't add a preamble or sign-off.
"""


def build_prompt() -> tuple:
    """Collect all inputs, build the prompt. Returns (system, user_prompt, input_size)."""
    log.info("Collecting inputs...")
    
    git_log = collect_git_log(SIM_ROOT, since_hours=24)
    uncommitted = collect_uncommitted(SIM_ROOT)
    snapshot = collect_file(STATE_DIR / "latest-snapshot.md", max_chars=15000)
    drift_today = collect_file(KNOWLEDGE_TECH / f"drift-{TODAY}.md", max_chars=8000)
    imperf = collect_file(HARNESS_ROOT / "IMPERFECTIONS.md", max_chars=10000)
    lessons = collect_file(KNOWLEDGE_TECH / "spec-authoring-lessons.md", max_chars=8000)
    recent_findings = collect_recent_findings(KNOWLEDGE_TECH, days=MAX_FINDINGS_DAYS)
    
    by_status = collect_specs_by_status(SPECS_DIR)
    proposed = ", ".join(by_status["PROPOSED"]) or "[none]"
    executing = ", ".join(by_status["EXECUTING"]) or "[none]"
    shipped = ", ".join(by_status["SHIPPED"][-5:]) or "[none]"  # last 5
    
    user_prompt = USER_PROMPT_TEMPLATE.format(
        today=TODAY,
        git_log=git_log,
        uncommitted=uncommitted,
        snapshot=snapshot,
        drift_findings=drift_today,
        imperfections=imperf,
        specs_proposed=proposed,
        specs_executing=executing,
        specs_shipped=shipped,
        recent_findings=recent_findings,
        lessons=lessons,
    )
    
    input_size = len(user_prompt) + len(SYSTEM_PROMPT)
    log.info(f"Prompt built: {input_size} chars (~{input_size//4} tokens)")
    
    if input_size > MAX_INPUT_CHARS:
        log.warn(f"Prompt size {input_size} exceeds soft cap {MAX_INPUT_CHARS}; Gemma context may overflow")
    
    return SYSTEM_PROMPT, user_prompt, input_size


# ---------------------------------------------------------------------------
# Output writer
# ---------------------------------------------------------------------------

def write_drift_pr(content: str, model_used: str) -> Path:
    """Write the drift PR to harness/inbox/drift-pr--YYYY-MM-DD.md."""
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    out_path = INBOX_DIR / f"drift-pr--{TODAY}.md"
    
    header = (
        f"# Drift PR -- {TODAY}\n\n"
        f"**Generated:** {TODAY_HHMM}\n"
        f"**By:** gemma_drift_pr.py (model: {model_used})\n"
        f"**Read at:** next session start, alongside `harness/state/latest-snapshot.md`\n\n"
        f"This is a Gemma-generated recommendation report. It is reading material,\n"
        f"not committed changes. Claude reviews and surfaces; Jermey decides.\n\n"
        f"---\n\n"
    )
    
    out_path.write_text(header + content.strip() + "\n", encoding="utf-8")
    log.info(f"Wrote {out_path}")
    return out_path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Build prompt + check Ollama, but don't call Gemma")
    parser.add_argument("--show-prompt", action="store_true",
                        help="Print prompt to stdout (for debugging)")
    parser.add_argument("--model", default="gemma4",
                        help="Ollama model name (default: gemma4)")
    parser.add_argument("--max-tokens", type=int, default=4096,
                        help="Max output tokens (default: 4096)")
    parser.add_argument("--temperature", type=float, default=0.3,
                        help="Sampling temperature (default: 0.3)")
    args = parser.parse_args()
    
    log.info(f"=== Gemma drift PR run for {TODAY} ===")
    
    system, user_prompt, input_size = build_prompt()
    
    if args.show_prompt:
        print("=" * 70)
        print("SYSTEM PROMPT:")
        print("=" * 70)
        print(system)
        print()
        print("=" * 70)
        print("USER PROMPT:")
        print("=" * 70)
        print(user_prompt)
        return 0
    
    if args.dry_run:
        log.info("Dry run -- checking Ollama health only")
        if check_ollama_health():
            log.info("Ollama healthy. Would call model: " + args.model)
        else:
            log.warn("Ollama unhealthy. Would have failed.")
        log.info("Dry run complete.")
        return 0
    
    log.info(f"Calling Gemma model={args.model} max_tokens={args.max_tokens}...")
    t0 = time.time()
    response, err = ask_gemma(
        user_prompt, system=system,
        model=args.model,
        max_tokens=args.max_tokens,
        temperature=args.temperature,
    )
    dt = time.time() - t0
    
    if err or not response:
        log.error(f"Gemma call failed after {dt:.1f}s: {err}")
        # Write a stub so the inbox file exists and the drift PR doesn't silently
        # disappear. Next session sees the failure and can decide what to do.
        stub = (
            f"# Drift PR generation FAILED\n\n"
            f"Gemma call failed: {err}\n\n"
            f"Likely causes: Ollama not running, model {args.model} not pulled, "
            f"or input too large ({input_size} chars).\n\n"
            f"To debug: `python harness/agents/scripts/gemma_drift_pr.py --dry-run`\n"
        )
        out = INBOX_DIR / f"drift-pr--{TODAY}.md"
        out.write_text(stub, encoding="utf-8")
        return 1
    
    log.info(f"Gemma responded in {dt:.1f}s ({len(response)} chars)")
    out_path = write_drift_pr(response, args.model)
    log.info(f"Drift PR ready at {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
