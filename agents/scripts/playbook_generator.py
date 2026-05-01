"""
playbook_generator.py -- Auto-generate playbook HTML from sim data + gauntlet results.

Reads knowledge blocks (sim, tune, gauntlet/grind) and produces standalone HTML
playbooks in the My-Website/{format}/ directory.

CLI:
    python playbook_generator.py "Boros Energy" --format modern
    python playbook_generator.py --format modern --all
    python playbook_generator.py --format modern --all --dry-run
"""

import argparse
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path("E:/vscode ai project/harness/agents/scripts")))
from agent_hardening import AgentLogger

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path("E:/vscode ai project")
KNOWLEDGE_DIR = PROJECT_ROOT / "harness" / "knowledge" / "mtg"
WEBSITE_DIR = PROJECT_ROOT / "My-Website"

# ---------------------------------------------------------------------------
# YAML Frontmatter + Markdown Parser
# ---------------------------------------------------------------------------

def parse_knowledge_block(path: Path) -> dict:
    """Parse a knowledge block markdown file.

    Returns dict with 'frontmatter' (dict) and 'body' (str).
    """
    text = path.read_text(encoding="utf-8")
    result = {"frontmatter": {}, "body": text, "path": str(path)}

    fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if fm_match:
        raw_fm = fm_match.group(1)
        result["body"] = text[fm_match.end():]
        for line in raw_fm.splitlines():
            m = re.match(r'^(\w[\w_-]*)\s*:\s*(.+)$', line)
            if m:
                key = m.group(1).strip()
                val = m.group(2).strip().strip('"').strip("'")
                # Handle lists like ["a", "b"]
                if val.startswith("[") and val.endswith("]"):
                    val = [v.strip().strip('"').strip("'")
                           for v in val[1:-1].split(",")]
                result["frontmatter"][key] = val

    return result


def slugify(name: str) -> str:
    """Convert 'Boros Energy' to 'boros-energy'."""
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')


# ---------------------------------------------------------------------------
# Data Extraction from Knowledge Blocks
# ---------------------------------------------------------------------------

def find_sim_block(deck_slug: str) -> dict | None:
    """Find sim-{deck}.md and extract goldfish stats."""
    pattern = f"sim-{deck_slug}.md"
    candidates = list(KNOWLEDGE_DIR.glob(pattern))
    if not candidates:
        # Try partial match
        candidates = [p for p in KNOWLEDGE_DIR.glob("sim-*.md")
                      if deck_slug in p.stem]
    if not candidates:
        return None

    block = parse_knowledge_block(candidates[0])
    body = block["body"]

    stats = {}
    for key, regex in [
        ("avg_kill", r"Avg Kill Turn:\s*([\d.]+)"),
        ("median_kill", r"Median Kill:\s*([\d.]+)"),
        ("fastest_kill", r"Fastest Kill:\s*T?(\d+)"),
        ("win_rate", r"Win Rate:\s*([\d.]+)%"),
        ("speed", r"Speed:\s*([\d.]+)"),
    ]:
        m = re.search(regex, body)
        if m:
            stats[key] = m.group(1)

    # Pull Gemma analysis for game plan if available
    plan_match = re.search(
        r"###?\s*1\.\s*ASSESSMENT.*?\n\n(.*?)(?=\n###|\Z)", body, re.DOTALL
    )
    if plan_match:
        stats["analysis"] = plan_match.group(1).strip()

    return stats


def find_tune_blocks(deck_slug: str) -> list[dict]:
    """Find all tune-{deck}-*.md and extract matchup + experiment data."""
    results = []
    for path in sorted(KNOWLEDGE_DIR.glob(f"tune-{deck_slug}-*.md")):
        block = parse_knowledge_block(path)
        body = block["body"]

        entry = {"path": str(path), "matchups": {}, "experiments": []}

        # Extract format
        fmt_m = re.search(r"Format:\s*(\w+)", body)
        if fmt_m:
            entry["format"] = fmt_m.group(1)

        # Extract baseline win rate
        base_m = re.search(r"Field-weighted win rate:\s*([\d.]+)%", body)
        if base_m:
            entry["baseline_wr"] = float(base_m.group(1))

        # Extract matchups
        for m in re.finditer(
            r"vs\s+(.+?):\s*([\d.]+)%", body
        ):
            entry["matchups"][m.group(1).strip()] = float(m.group(2))

        # Extract experiments (sideboard swap suggestions)
        for m in re.finditer(
            r"\*\*(-[^+]+\+[^*]+)\*\*:\s*(BETTER|WORSE|NEUTRAL)\s*\(([^)]+)\)",
            body,
        ):
            entry["experiments"].append({
                "swap": m.group(1).strip(),
                "result": m.group(2),
                "delta": m.group(3),
            })

        results.append(entry)
    return results


def find_grind_blocks(deck_slug: str) -> list[dict]:
    """Find grind-{deck}-*.md (gauntlet-style) and extract speed data."""
    results = []
    for path in sorted(KNOWLEDGE_DIR.glob(f"grind-{deck_slug}-*.md")):
        block = parse_knowledge_block(path)
        body = block["body"]

        entry = {"path": str(path), "steps": []}

        # Extract original/final kill turns
        turn_m = re.search(
            r"Original:\s*T([\d.]+)\s*\|\s*Final:\s*T([\d.]+)", body
        )
        if turn_m:
            entry["original_turn"] = float(turn_m.group(1))
            entry["final_turn"] = float(turn_m.group(2))

        gain_m = re.search(r"Gain:\s*\+([\d.]+)", body)
        if gain_m:
            entry["gain"] = float(gain_m.group(1))

        # Extract individual results
        for m in re.finditer(
            r"\[(FASTER|SLOWER|SAME)\]\s*\w+\s*T([\d.]+)->T([\d.]+)\s*\(([^)]+)\)",
            body,
        ):
            entry["steps"].append({
                "result": m.group(1),
                "from_turn": float(m.group(2)),
                "to_turn": float(m.group(3)),
                "delta": m.group(4),
            })

        results.append(entry)
    return results


def find_gauntlet_blocks(deck_slug: str, fmt: str) -> list[dict]:
    """Find gauntlet-{format}-*.md blocks that contain this deck's matchup data."""
    results = []
    for path in sorted(KNOWLEDGE_DIR.glob(f"gauntlet-{fmt}-*.md")):
        block = parse_knowledge_block(path)
        body = block["body"]

        # Look for matchup rows mentioning the deck
        matchups = {}
        for m in re.finditer(
            r"\|\s*(.+?)\s*\|\s*([\d.]+)%\s*\|", body
        ):
            matchups[m.group(1).strip()] = float(m.group(2))

        if matchups:
            results.append({"path": str(path), "matchups": matchups})

    return results


# ---------------------------------------------------------------------------
# Difficulty Rating
# ---------------------------------------------------------------------------

def difficulty_rating(win_pct: float) -> tuple[str, str]:
    """Return (label, css_class) for a win percentage."""
    if win_pct >= 65:
        return "Dominant", "diff-good"
    elif win_pct >= 55:
        return "Favorable", "diff-good"
    elif win_pct >= 50:
        return "Even+", "diff-even"
    elif win_pct >= 45:
        return "Even-", "diff-medium"
    else:
        return "Hard", "diff-hard"


# ---------------------------------------------------------------------------
# Aggregate Data
# ---------------------------------------------------------------------------

def aggregate_deck_data(deck_name: str, fmt: str) -> dict:
    """Collect all available data for a deck across knowledge blocks."""
    slug = slugify(deck_name)
    data = {
        "deck_name": deck_name,
        "format": fmt,
        "slug": slug,
        "sim": find_sim_block(slug),
        "tune": find_tune_blocks(slug),
        "grind": find_grind_blocks(slug),
        "gauntlet": find_gauntlet_blocks(slug, fmt),
        "matchups": {},
        "experiments": [],
        "kill_turn": None,
        "games_simulated": 0,
    }

    # Merge matchups from tune blocks (latest wins)
    for tb in data["tune"]:
        for opp, wr in tb["matchups"].items():
            data["matchups"][opp] = wr

    # Merge matchups from gauntlet blocks
    for gb in data["gauntlet"]:
        for opp, wr in gb["matchups"].items():
            data["matchups"][opp] = wr

    # Collect experiments
    for tb in data["tune"]:
        data["experiments"].extend(tb["experiments"])

    # Best kill turn from grind or sim
    if data["grind"]:
        latest = data["grind"][-1]
        data["kill_turn"] = latest.get("final_turn")
    if data["sim"]:
        sim_kill = data["sim"].get("avg_kill")
        if sim_kill:
            sim_val = float(sim_kill)
            if data["kill_turn"] is None or sim_val < data["kill_turn"]:
                data["kill_turn"] = sim_val

    return data


# ---------------------------------------------------------------------------
# HTML Generation
# ---------------------------------------------------------------------------

def generate_matchup_rows(matchups: dict) -> str:
    """Generate <tr> rows for the matchup table."""
    if not matchups:
        return '<tr><td colspan="4"><em>No matchup data available yet.</em></td></tr>'

    rows = []
    for opp, wr in sorted(matchups.items(), key=lambda x: x[1]):
        label, css = difficulty_rating(wr)
        rows.append(
            f'                <tr>'
            f'<td>{opp}</td>'
            f'<td>{wr:.1f}%</td>'
            f'<td><span class="{css}">{label}</span></td>'
            f'<td></td>'
            f'</tr>'
        )
    return "\n".join(rows)


def generate_sb_sections(experiments: list, matchups: dict) -> str:
    """Generate sideboard guide sections from tuning experiments."""
    if not experiments and not matchups:
        return '<p><em>No sideboard data available yet. Run tuning experiments to populate.</em></p>'

    sections = []

    # Group experiments by what was swapped
    if experiments:
        sections.append('<h3>Tested Swaps</h3>')
        sections.append('<table class="matchup-table">')
        sections.append(
            '<thead><tr><th>Swap</th><th>Result</th><th>Delta</th></tr></thead>'
        )
        sections.append('<tbody>')
        for exp in experiments:
            result = exp["result"]
            css = {
                "BETTER": "diff-good",
                "WORSE": "diff-hard",
                "NEUTRAL": "diff-medium",
            }.get(result, "diff-even")
            sections.append(
                f'<tr><td>{exp["swap"]}</td>'
                f'<td><span class="{css}">{result}</span></td>'
                f'<td>{exp["delta"]}</td></tr>'
            )
        sections.append('</tbody></table>')

    # Per-matchup stubs
    if matchups:
        sections.append('<h3>Per-Matchup Sideboarding</h3>')
        for opp in sorted(matchups.keys()):
            wr = matchups[opp]
            label, css = difficulty_rating(wr)
            sections.append(f'<div class="sb-matchup">')
            sections.append(
                f'<h3>vs {opp} '
                f'<span class="{css}">{wr:.1f}% - {label}</span></h3>'
            )
            sections.append('<div class="sb-table">')
            sections.append(
                '<div class="sb-col">'
                '<div class="sb-col-label">IN</div>'
                '<div class="sb-item"><em>TBD</em></div>'
                '</div>'
            )
            sections.append(
                '<div class="sb-col">'
                '<div class="sb-col-label">OUT</div>'
                '<div class="sb-item"><em>TBD</em></div>'
                '</div>'
            )
            sections.append('</div></div>')

    return "\n            ".join(sections)


def generate_playbook_html(data: dict) -> str:
    """Generate the full HTML playbook from aggregated data."""
    deck_name = data["deck_name"]
    fmt = data["format"].capitalize()
    kill_turn = f'{data["kill_turn"]:.2f}' if data["kill_turn"] else "N/A"
    today = date.today().isoformat()

    # Try to get meta % and role from existing knowledge
    meta_pct = "?"
    role = "aggro"  # default

    # Build game plan from sim analysis
    game_plan = "No simulation analysis available yet. Run goldfish sims to populate."
    if data["sim"] and data["sim"].get("analysis"):
        # Trim to first ~300 chars for the summary
        raw = data["sim"]["analysis"]
        # Strip markdown bold
        raw = re.sub(r'\*\*([^*]+)\*\*', r'\1', raw)
        game_plan = raw[:500]
        if len(raw) > 500:
            game_plan += "..."

    matchup_rows = generate_matchup_rows(data["matchups"])
    sb_sections = generate_sb_sections(data["experiments"], data["matchups"])

    # Count data sources
    source_count = 0
    if data["sim"]:
        source_count += 1
    source_count += len(data["tune"])
    source_count += len(data["grind"])
    source_count += len(data["gauntlet"])

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{deck_name} - {fmt} Playbook</title>
    <link rel="icon" href="../images/tab32.png" type="image/png">
    <link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Mono:ital,wght@0,300;0,400;0,500;1,300&family=Crimson+Pro:ital,wght@0,300;0,400;0,600;1,300;1,400&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="../styles.css">
    <style>
        :root {{
            --ink: #0e0e0e; --paper: #f2ede6; --paper-dark: #e8e1d6; --rule: #c8bfb0;
            --primary: #4c1611;
            --accent: #c0392b; --accent-light: #f7d6d6;
            --danger: #8f1a1a; --danger-light: #f7d6d6;
            --gold: #8f6a1a; --gold-light: #f7ead6;
            --mid: #5a5248;
        }}
        html {{ overflow-y: scroll; }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ background: var(--paper); color: var(--ink); font-family: 'Crimson Pro', Georgia, serif; font-size: 17px; line-height: 1.6; }}
        .header-band {{ background: var(--primary); color:#f1f5f9; border-bottom: 3px solid #c0392b; padding: 48px 80px 40px; position: relative; overflow: hidden; }}
        .header-inner {{ max-width: 1080px; margin: 0 auto; display: flex; justify-content: space-between; align-items: flex-end; gap: 40px; }}
        .header-label {{ font-family: 'DM Mono', monospace; font-size: 10px; letter-spacing: 0.2em; text-transform: uppercase; color: rgba(242,237,230,0.35); margin-bottom: 8px; }}
        .header-title {{ font-family: 'DM Mono', monospace; font-size: clamp(32px,4vw,52px); font-weight: 500; letter-spacing: 0.06em; line-height: 1.05; text-transform: uppercase; }}
        .header-right {{ display: flex; flex-direction: column; gap: 8px; text-align: right; padding-bottom: 4px; }}
        .header-stat {{ display: flex; gap: 12px; align-items: center; justify-content: flex-end; }}
        .hs-label {{ font-family: 'DM Mono', monospace; font-size: 10px; letter-spacing: 0.15em; text-transform: uppercase; color: rgba(242,237,230,0.3); }}
        .hs-val {{ font-family: 'DM Mono', monospace; font-size: 12px; color: var(--paper); }}
        .page {{ max-width: 1100px; margin: 0 auto; padding: 80px 80px; }}
        h1 {{ font-family: 'Bebas Neue', sans-serif; font-size: 64px; line-height: 0.9; letter-spacing: 0.01em; color: var(--ink); margin-bottom: 40px; }}
        h2 {{ font-family: 'Bebas Neue', sans-serif; font-size: 36px; letter-spacing: 0.02em; color: var(--ink); margin: 56px 0 20px; padding-bottom: 8px; border-bottom: 2px solid var(--ink); }}
        h3 {{ font-family: 'DM Mono', monospace; font-size: 12px; letter-spacing: 0.15em; text-transform: uppercase; color: var(--accent); margin: 32px 0 12px; }}
        p {{ margin-bottom: 16px; color: var(--ink); font-weight: 300; }}
        .matchup-table {{ width: 100%; border-collapse: collapse; margin: 24px 0; font-size: 15px; }}
        .matchup-table thead tr {{ background: var(--ink); color: var(--paper); }}
        .matchup-table th {{ font-family: 'DM Mono', monospace; font-size: 10px; letter-spacing: 0.15em; text-transform: uppercase; padding: 12px 16px; text-align: left; font-weight: 400; }}
        .matchup-table td {{ padding: 12px 16px; border-bottom: 1px solid var(--rule); font-weight: 300; vertical-align: top; }}
        .matchup-table tr:hover td {{ background: var(--paper-dark); }}
        .diff-hard {{ font-family: 'DM Mono', monospace; font-size: 11px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--danger); background: var(--danger-light); padding: 2px 8px; border-radius: 2px; }}
        .diff-medium {{ font-family: 'DM Mono', monospace; font-size: 11px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--gold); background: var(--gold-light); padding: 2px 8px; border-radius: 2px; }}
        .diff-even {{ font-family: 'DM Mono', monospace; font-size: 11px; letter-spacing: 0.08em; text-transform: uppercase; color: #1a3a8f; background: #d6e0f7; padding: 2px 8px; border-radius: 2px; }}
        .diff-good {{ font-family: 'DM Mono', monospace; font-size: 11px; letter-spacing: 0.08em; text-transform: uppercase; color: #1a6b1a; background: #d4f0d4; padding: 2px 8px; border-radius: 2px; border: 1px solid #a0d4a0; }}
        .sb-table {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1px; background: var(--rule); border: 1px solid var(--rule); margin: 16px 0; }}
        .sb-col {{ background: var(--paper); padding: 20px; }}
        .sb-col-label {{ font-family: 'DM Mono', monospace; font-size: 10px; letter-spacing: 0.2em; text-transform: uppercase; color: var(--mid); margin-bottom: 12px; }}
        .sb-item {{ font-size: 14px; font-weight: 400; padding: 4px 0; border-bottom: 1px solid var(--rule); }}
        .sb-item:last-child {{ border-bottom: none; }}
        .sb-matchup {{ margin-bottom: 24px; }}
        .back-link {{ font-family: 'DM Mono', monospace; font-size: 11px; letter-spacing: 0.12em; text-transform: uppercase; color: rgba(242,237,230,0.5); text-decoration: none; }}
        .back-link:hover {{ color: var(--paper); }}
        .gen-footer {{ margin-top: 80px; padding-top: 24px; border-top: 1px solid var(--rule); font-family: 'DM Mono', monospace; font-size: 11px; color: var(--mid); letter-spacing: 0.05em; }}
    </style>
</head>
<body>
    <div class="header-band">
        <div class="header-inner">
            <div>
                <div class="header-label">Team Resolve &middot; {fmt} &middot; {today[:7].replace('-', ' ')}</div>
                <div class="header-title">{deck_name}</div>
            </div>
            <div class="header-right">
                <div class="header-stat">
                    <span class="hs-label">Meta</span>
                    <span class="hs-val">{meta_pct}%</span>
                </div>
                <div class="header-stat">
                    <span class="hs-label">Role</span>
                    <span class="hs-val">{role}</span>
                </div>
                <div class="header-stat">
                    <span class="hs-label">Avg Kill</span>
                    <span class="hs-val">T{kill_turn}</span>
                </div>
            </div>
        </div>
    </div>

    <div class="page">
        <a href="../deck-guides.html" class="back-link">&larr; Back to Guides</a>

        <section class="engine-block">
            <h2>Game Plan</h2>
            <p>{game_plan}</p>
        </section>

        <section>
            <h2>Matchup Overview</h2>
            <table class="matchup-table">
                <thead><tr><th>Matchup</th><th>Win Rate</th><th>Difficulty</th><th>Key Cards</th></tr></thead>
                <tbody>
{matchup_rows}
                </tbody>
            </table>
        </section>

        <section class="sideboard-guide">
            <h2>Sideboard Guide</h2>
            {sb_sections}
        </section>

        <div class="gen-footer">
            <p>Auto-generated by Harness Playbook Generator | {today}</p>
            <p>Data sources: {source_count} knowledge blocks | Source: mtg-sim + meta-analyzer</p>
        </div>
    </div>
</body>
</html>'''
    return html


# ---------------------------------------------------------------------------
# Existing Playbook Detection
# ---------------------------------------------------------------------------

def find_existing_playbook(deck_slug: str, fmt: str) -> Path | None:
    """Check if a playbook already exists for this deck."""
    fmt_dir = WEBSITE_DIR / fmt
    # Try common naming patterns
    for pattern in [
        f"{deck_slug}-playbook.html",
        f"{deck_slug}.html",
    ]:
        path = fmt_dir / pattern
        if path.exists():
            return path
    return None


def extract_manual_content(playbook_path: Path) -> dict:
    """Extract manually-written content from an existing playbook.

    Preserves strategy notes, key cards, and other hand-curated content
    that should survive regeneration.
    """
    text = playbook_path.read_text(encoding="utf-8")
    manual = {}

    # Extract meta % if present
    m = re.search(r'meta-share["\s>]*[^<]*?([\d.]+)%', text)
    if m:
        manual["meta_pct"] = m.group(1)

    # Extract role if present
    m = re.search(r'<span class="hs-val">(\w+)</span>\s*$', text, re.MULTILINE)
    # More targeted: look for Role row
    m = re.search(r'Role</span>\s*<span class="hs-val">([^<]+)</span>', text)
    if m:
        manual["role"] = m.group(1).strip()

    # Extract meta pct from header stat
    m = re.search(r'Meta</span>\s*<span class="hs-val">([\d.?]+)%?</span>', text)
    if m:
        manual["meta_pct"] = m.group(1).strip()

    return manual


# ---------------------------------------------------------------------------
# Deck Discovery
# ---------------------------------------------------------------------------

def discover_decks_with_data(fmt: str) -> list[str]:
    """Find all decks that have at least one knowledge block."""
    deck_names = set()

    for pattern_prefix in ["sim-", "tune-", "grind-", "gauntlet-"]:
        for path in KNOWLEDGE_DIR.glob(f"{pattern_prefix}*.md"):
            stem = path.stem
            # Remove prefix
            name_part = stem.split(pattern_prefix, 1)[-1]
            # Remove date suffix (e.g., -2026-04-16)
            name_part = re.sub(r'-\d{4}-\d{2}-\d{2}$', '', name_part)
            if name_part:
                deck_names.add(name_part)

    return sorted(deck_names)


def slug_to_title(slug: str) -> str:
    """Convert 'boros-energy' to 'Boros Energy'."""
    return " ".join(word.capitalize() for word in slug.split("-"))


# ---------------------------------------------------------------------------
# Main Generator
# ---------------------------------------------------------------------------

def generate_playbook(
    deck_name: str,
    fmt: str,
    dry_run: bool = False,
    log: AgentLogger | None = None,
) -> dict:
    """Generate or update a playbook for the given deck.

    Returns a summary dict.
    """
    if log is None:
        log = AgentLogger("playbook-gen")

    slug = slugify(deck_name)
    log.section(f"Generating: {deck_name} ({fmt})")

    # 1. Aggregate data from knowledge blocks
    data = aggregate_deck_data(deck_name, fmt)

    sources_found = []
    if data["sim"]:
        sources_found.append("sim")
    if data["tune"]:
        sources_found.append(f"tune x{len(data['tune'])}")
    if data["grind"]:
        sources_found.append(f"grind x{len(data['grind'])}")
    if data["gauntlet"]:
        sources_found.append(f"gauntlet x{len(data['gauntlet'])}")

    if not sources_found:
        log.warn(f"No data found for {deck_name}. Skipping.")
        return {"deck": deck_name, "status": "skipped", "reason": "no data"}

    log.info(f"Data sources: {', '.join(sources_found)}")
    log.info(f"Matchups found: {len(data['matchups'])}")
    log.info(f"Experiments found: {len(data['experiments'])}")
    log.info(f"Kill turn: {data['kill_turn']}")

    # 2. Check for existing playbook
    existing = find_existing_playbook(slug, fmt)
    if existing:
        log.info(f"Existing playbook found: {existing}")
        manual = extract_manual_content(existing)
        if manual.get("meta_pct"):
            log.info(f"Preserving meta %: {manual['meta_pct']}")
        if manual.get("role"):
            log.info(f"Preserving role: {manual['role']}")
    else:
        manual = {}
        log.info("No existing playbook -- creating new.")

    # 3. Generate HTML
    html = generate_playbook_html(data)

    # Patch in preserved manual content
    if manual.get("meta_pct"):
        html = html.replace(
            f'<span class="hs-val">?%</span>',
            f'<span class="hs-val">{manual["meta_pct"]}%</span>',
        )
    if manual.get("role"):
        html = html.replace(
            f'<span class="hs-val">aggro</span>',
            f'<span class="hs-val">{manual["role"]}</span>',
        )

    # 4. Output
    out_dir = WEBSITE_DIR / fmt
    out_path = out_dir / f"{slug}-playbook.html"

    if dry_run:
        log.info(f"[DRY RUN] Would write to: {out_path}")
        log.info(f"[DRY RUN] HTML size: {len(html)} bytes")
    else:
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path.write_text(html, encoding="utf-8")
        log.success(f"Wrote: {out_path}")
        log.info(f"Size: {len(html)} bytes")

    return {
        "deck": deck_name,
        "status": "dry-run" if dry_run else "written",
        "path": str(out_path),
        "sources": sources_found,
        "matchups": len(data["matchups"]),
        "experiments": len(data["experiments"]),
        "kill_turn": data["kill_turn"],
        "had_existing": existing is not None,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate playbook HTML from sim data + gauntlet results."
    )
    parser.add_argument(
        "deck",
        nargs="?",
        help='Deck name, e.g. "Boros Energy"',
    )
    parser.add_argument(
        "--format",
        required=True,
        help="Format: modern, standard, pioneer, legacy, pauper",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Generate for all decks with data",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be generated without writing files",
    )

    args = parser.parse_args()

    if not args.deck and not args.all:
        parser.error("Provide a deck name or use --all")

    log = AgentLogger("playbook-gen")
    log.section("Playbook Generator")
    log.info(f"Format: {args.format}")
    log.info(f"Dry run: {args.dry_run}")

    results = []

    if args.all:
        slugs = discover_decks_with_data(args.format)
        log.info(f"Discovered {len(slugs)} decks with data")
        for slug in slugs:
            title = slug_to_title(slug)
            result = generate_playbook(title, args.format, args.dry_run, log)
            results.append(result)
    else:
        result = generate_playbook(args.deck, args.format, args.dry_run, log)
        results.append(result)

    # Summary
    log.section("Summary")
    written = [r for r in results if r["status"] == "written"]
    skipped = [r for r in results if r["status"] == "skipped"]
    dry = [r for r in results if r["status"] == "dry-run"]

    if written:
        log.success(f"Generated {len(written)} playbook(s)")
        for r in written:
            log.info(f"  {r['deck']}: {r['matchups']} matchups, kill T{r['kill_turn']}")
    if dry:
        log.info(f"Dry-run: {len(dry)} playbook(s) would be generated")
        for r in dry:
            log.info(f"  {r['deck']}: {r['matchups']} matchups, kill T{r['kill_turn']}")
    if skipped:
        log.warn(f"Skipped {len(skipped)} deck(s) (no data)")
        for r in skipped:
            log.info(f"  {r['deck']}: {r.get('reason', 'unknown')}")


if __name__ == "__main__":
    main()
