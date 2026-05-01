"""
matchup_gauntlet.py — Full matchup matrix runner using the real match engine.

Discovers all decks for a format, pairs each with its APL (or GenericMatchAPL),
then runs every deck pair through run_match_set() to produce a complete
matchup matrix with field-weighted win rates.

Usage:
    python matchup_gauntlet.py --format modern --games 500
    python matchup_gauntlet.py --format modern --games 1000 --top 8
    python matchup_gauntlet.py --format standard --dry-run
    python matchup_gauntlet.py --format modern --deck "Boros Energy"
"""

from __future__ import annotations

import argparse
import csv
import importlib
import inspect
import os
import sys
import time
from datetime import date, datetime
from itertools import combinations
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Path setup — must come before any mtg-sim imports
# ---------------------------------------------------------------------------
SIM_ROOT = Path("E:/vscode ai project/mtg-sim")
PROJECT_ROOT = Path("E:/vscode ai project")

sys.path.insert(0, str(SIM_ROOT))
sys.path.insert(0, str(Path("E:/vscode ai project/harness/agents/scripts")))

from agent_hardening import AgentLogger, LoopController

# mtg-sim imports
from data.deck import load_deck_from_file
from apl.base_apl import BaseAPL
from apl.match_apl import MatchAPL, GoldfishAdapter, GenericMatchAPL
from engine.match_engine import run_match_set, print_match_report


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DECKS_DIR = SIM_ROOT / "decks"
APL_DIR = SIM_ROOT / "apl"
KNOWLEDGE_DIR = PROJECT_ROOT / "harness" / "knowledge" / "mtg"
TEAM_DATA_DIR = PROJECT_ROOT / "Team Resolve" / "data"

log = AgentLogger("matchup-gauntlet")


# ---------------------------------------------------------------------------
# Deck discovery
# ---------------------------------------------------------------------------

def _get_competitive_archetypes(format_name: str, weeks: int = 8) -> dict:
    """Query meta-analyzer DB for archetypes with competitive results in the last N weeks.

    Competitive = at least one of:
      - 5-0 in an MTGO league
      - Top 8 in an MTGO Challenge (32 or 64)
      - Top 32 in a paper event with 101+ players (inferred from placement)

    Returns {archetype_name: {"meta_share": float, "results": int, "best_finish": int}}
    """
    import sqlite3
    META_DB = Path("E:/vscode ai project/mtg-meta-analyzer/data/mtg_meta.db")
    if not META_DB.exists():
        return {}

    try:
        conn = sqlite3.connect(str(META_DB))
        conn.row_factory = sqlite3.Row

        # Date cutoff: DB has mixed formats (DD/MM/YY and YYYY-MM-DD)
        # Build cutoffs for both formats
        from datetime import datetime, timedelta
        cutoff_dt = datetime.now() - timedelta(weeks=weeks)
        cutoff_iso = cutoff_dt.strftime("%Y-%m-%d")
        # For DD/MM/YY: we need to match recent months/years
        cutoff_yy = cutoff_dt.strftime("%y")  # e.g. "26"
        # Get all months from cutoff to now as DD/MM/YY patterns
        recent_patterns = []
        d = cutoff_dt
        while d <= datetime.now():
            recent_patterns.append(f"%/{d.strftime('%m/%y')}")
            d += timedelta(days=32)
            d = d.replace(day=1)

        # Build date filter SQL for both formats
        date_clauses = [f"e.date >= '{cutoff_iso}'"]  # ISO format
        for pat in recent_patterns:
            date_clauses.append(f"e.date LIKE '{pat}'")
        date_filter = "(" + " OR ".join(date_clauses) + ")"

        # Find archetypes with competitive finishes in recent weeks
        query = f"""
            SELECT d.archetype,
                   COUNT(*) as results,
                   MIN(d.placement) as best_finish,
                   e.event_type
            FROM decks d
            JOIN events e ON d.event_id = e.id
            WHERE e.format = ?
              AND d.archetype IS NOT NULL AND d.archetype != ''
              AND d.placement IS NOT NULL AND d.placement > 0
              AND {date_filter}
              AND (
                  (e.event_type = 'mtgo_league' AND d.placement <= 5)
                  OR (e.event_type IN ('mtgo_challenge_32', 'mtgo_challenge_64') AND d.placement <= 8)
                  OR (e.event_type = 'paper' AND d.placement <= 32)
              )
            GROUP BY d.archetype
            ORDER BY results DESC
        """
        rows = conn.execute(query, (format_name,)).fetchall()

        competitive = {}
        for r in rows:
            competitive[r["archetype"]] = {
                "results": r["results"],
                "best_finish": r["best_finish"],
                "event_type": r["event_type"],
            }

        # Also get meta shares from the recent period only
        share_query = f"""
            SELECT d.archetype, COUNT(*) as cnt
            FROM decks d
            JOIN events e ON d.event_id = e.id
            WHERE e.format = ?
              AND d.archetype IS NOT NULL AND d.archetype != ''
              AND {date_filter}
            GROUP BY d.archetype
            ORDER BY cnt DESC
        """
        share_rows = conn.execute(share_query, (format_name,)).fetchall()

        total = sum(r["cnt"] for r in share_rows)
        for r in share_rows:
            arch = r["archetype"]
            if arch in competitive:
                competitive[arch]["meta_share"] = round(r["cnt"] / total * 100, 1) if total else 0

        conn.close()
        return competitive
    except Exception as e:
        log.warn(f"Could not query competitive archetypes: {e}")
        return {}


def discover_decks(format_name: str, top_n: Optional[int] = None) -> list[dict]:
    """
    Find deck files for a format, filtered by competitive results.

    Filters:
      1. Archetype must appear in meta within last 8 weeks (if DB available)
      2. Decklist must have noteworthy results (5-0 league, top 8 challenge,
         top 32 paper event with 101+ players)
      3. Ranked by meta share, optionally trimmed to top N

    Falls back to all deck files if DB is unavailable.
    """
    pattern = f"*_{format_name}.txt"
    deck_files = sorted(DECKS_DIR.glob(pattern))

    if not deck_files:
        log.error(f"No deck files found matching {pattern} in {DECKS_DIR}")
        return []

    # Load competitive archetype data from meta-analyzer
    competitive = _get_competitive_archetypes(format_name, weeks=8)

    decks = []
    skipped = []
    for f in deck_files:
        slug = f.stem.replace(f"_{format_name}", "")
        name = slug.replace("_", " ").title()

        # Check if this archetype has competitive results
        matched_arch = None
        slug_lower = slug.lower()
        for arch in competitive:
            arch_slug = arch.lower().replace(" ", "_").replace("-", "_")
            if slug_lower in arch_slug or arch_slug in slug_lower:
                matched_arch = arch
                break

        if competitive and not matched_arch:
            skipped.append(name)
            continue

        entry = {"name": name, "file": str(f), "slug": slug, "format": format_name}
        if matched_arch:
            info = competitive[matched_arch]
            entry["meta_share"] = info.get("meta_share", 0)
            entry["results"] = info.get("results", 0)
            entry["best_finish"] = info.get("best_finish", 0)
        else:
            entry["meta_share"] = 0

        decks.append(entry)

    if skipped:
        log.info(f"Filtered out {len(skipped)} decks (no competitive results in 8 weeks): "
                 f"{', '.join(skipped)}")

    log.info(f"Found {len(decks)} competitive deck files for {format_name}: "
             f"{', '.join(d['name'] for d in decks)}")

    # Rank by meta share
    decks.sort(key=lambda d: -d.get("meta_share", 0))

    if top_n and top_n < len(decks):
        log.info(f"Ranked by meta share, taking top {top_n}")
        decks = decks[:top_n]

    return decks


# ---------------------------------------------------------------------------
# APL discovery and wrapping
# ---------------------------------------------------------------------------

def _find_apl_class(module) -> Optional[type]:
    """Find a class in the module that's a subclass of BaseAPL (but not BaseAPL itself)."""
    for name, obj in inspect.getmembers(module, inspect.isclass):
        if obj is BaseAPL or obj is MatchAPL or obj is GoldfishAdapter or obj is GenericMatchAPL:
            continue
        if issubclass(obj, (BaseAPL, MatchAPL)):
            return obj
    return None


def load_apl_for_deck(slug: str, format_name: str = "") -> tuple[MatchAPL, str]:
    """
    Try to find and load a match-aware or goldfish APL for the given deck slug.

    Search order:
      1. apl/{slug}_{format}_match.py  (format-specific match APL)
      2. apl/{slug}_match.py           (generic match APL)
      3. apl/{slug}.py                 (goldfish APL, wrap in GoldfishAdapter)
      4. Fall back to GenericMatchAPL

    Returns (apl_instance, source_label).
    """
    # 1. Try format-specific match APL (e.g., gruul_aggro_standard_match)
    if format_name:
        fmt_module = f"apl.{slug}_{format_name}_match"
        try:
            mod = importlib.import_module(fmt_module)
            cls = _find_apl_class(mod)
            if cls and issubclass(cls, MatchAPL):
                return cls(), "match-apl"
        except (ImportError, ModuleNotFoundError):
            pass
        except Exception as e:
            log.warn(f"Error loading format match APL {fmt_module}: {e}")

    # 2. Try generic match APL (e.g., gruul_aggro_match)
    match_module_name = f"apl.{slug}_match"
    try:
        mod = importlib.import_module(match_module_name)
        cls = _find_apl_class(mod)
        if cls and issubclass(cls, MatchAPL):
            apl = cls()
            return apl, "match-apl"
    except (ImportError, ModuleNotFoundError):
        pass
    except Exception as e:
        log.warn(f"Error loading match APL {match_module_name}: {e}")

    # 2. Try goldfish APL -> wrap in GoldfishAdapter
    goldfish_module_name = f"apl.{slug}"
    try:
        mod = importlib.import_module(goldfish_module_name)
        cls = _find_apl_class(mod)
        if cls:
            inner = cls()
            return GoldfishAdapter(inner), "goldfish-wrapped"
    except (ImportError, ModuleNotFoundError):
        pass
    except Exception as e:
        log.warn(f"Error loading goldfish APL {goldfish_module_name}: {e}")

    # 3. Fallback: GenericMatchAPL
    return GenericMatchAPL(), "generic"


def prepare_entries(decks: list[dict]) -> list[dict]:
    """
    Load deck cards and APL for each deck entry.
    Adds 'mainboard', 'sideboard', 'apl', 'apl_source' keys.
    """
    entries = []
    for d in decks:
        log.info(f"Loading deck: {d['name']} ({d['file']})")
        try:
            mainboard, sideboard = load_deck_from_file(d["file"])
        except Exception as e:
            log.error(f"Failed to load deck {d['name']}: {e}")
            continue

        apl, source = load_apl_for_deck(d["slug"], d.get("format", ""))
        log.info(f"  APL: {source} ({apl.__class__.__name__})")

        d["mainboard"] = mainboard
        d["sideboard"] = sideboard
        d["apl"] = apl
        d["apl_source"] = source
        entries.append(d)

    # Summary
    real_count = sum(1 for e in entries if e["apl_source"] != "generic")
    generic_count = sum(1 for e in entries if e["apl_source"] == "generic")
    log.info(f"APL coverage: {real_count} real, {generic_count} generic "
             f"({len(entries)} total)")
    return entries


# ---------------------------------------------------------------------------
# Matrix runner
# ---------------------------------------------------------------------------

def _mp_worker(args):
    """Worker function for multiprocessing matchup execution.

    Receives APL class info as (module_name, class_name) tuples so they
    can be reconstructed in the child process (classes aren't picklable).
    """
    name_a, deck_a_cards, apl_a_info, name_b, deck_b_cards, apl_b_info, games, seed = args

    import importlib

    def _make_apl(info):
        mod_name, cls_name = info
        if mod_name == "__generic__":
            from apl.match_apl import GenericMatchAPL
            return GenericMatchAPL()
        mod = importlib.import_module(mod_name)
        cls = getattr(mod, cls_name)
        return cls()

    try:
        apl_a = _make_apl(apl_a_info)
        apl_b = _make_apl(apl_b_info)
        results = run_match_set(apl_a, deck_a_cards, apl_b, deck_b_cards,
                                n=games, mix_play_draw=True, seed=seed)
        return name_a, name_b, results.win_pct_a(), results.avg_turns, None
    except Exception as e:
        import traceback
        return name_a, name_b, None, None, traceback.format_exc()


def _get_apl_info(apl):
    """Extract (module_name, class_name) for pickling across processes."""
    cls = type(apl)
    mod = cls.__module__
    name = cls.__name__
    if name == "GenericMatchAPL":
        return ("__generic__", "GenericMatchAPL")
    # GoldfishAdapter wraps an inner APL -- reconstruct the adapter
    if name == "GoldfishAdapter":
        return (mod, name)
    return (mod, name)


def run_gauntlet(entries: list[dict], games: int = 500,
                 single_deck: Optional[str] = None,
                 parallel_matchups: int = 0) -> dict:
    """
    Run every deck pair through run_match_set().

    If single_deck is set, only run that deck vs all others.
    If parallel_matchups > 0, run that many matchups concurrently.

    Returns matrix dict: {(deck_a_name, deck_b_name): win_pct_a}
    """
    matrix = {}
    pairs = []

    if single_deck:
        target = None
        for e in entries:
            if e["name"].lower() == single_deck.lower():
                target = e
                break
        if not target:
            log.error(f"Deck '{single_deck}' not found. Available: "
                      f"{', '.join(e['name'] for e in entries)}")
            return matrix
        opponents = [e for e in entries if e["name"] != target["name"]]
        pairs = [(target, opp) for opp in opponents]
    else:
        pairs = list(combinations(entries, 2))

    total_pairs = len(pairs)
    log.section(f"Running {total_pairs} matchups ({games} games each)"
                + (f" [{parallel_matchups} parallel]" if parallel_matchups > 1 else ""))

    ctrl = LoopController(max_steps=total_pairs, time_budget=7200, stall_limit=total_pairs)

    if parallel_matchups > 1:
        # True multiprocessing: spread across CPU cores
        from multiprocessing import Pool

        t0_all = time.time()

        worker_args = []
        for idx, (deck_a, deck_b) in enumerate(pairs):
            worker_args.append((
                deck_a["name"], deck_a["mainboard"], _get_apl_info(deck_a["apl"]),
                deck_b["name"], deck_b["mainboard"], _get_apl_info(deck_b["apl"]),
                games, 42 + idx
            ))

        with Pool(processes=parallel_matchups) as pool:
            results_list = pool.map(_mp_worker, worker_args)

        for result in results_list:
            name_a, name_b, win_pct_a, avg_turns, error = result
            if error:
                log.error(f"  {name_a} vs {name_b}: FAILED\n{error[:300]}")
                ctrl.step(progress=False)
            else:
                matrix[(name_a, name_b)] = win_pct_a
                matrix[(name_b, name_a)] = round(100.0 - win_pct_a, 1)
                log.info(f"  {name_a} {win_pct_a}% - "
                         f"{100.0 - win_pct_a:.1f}% {name_b} (avg {avg_turns:.1f}T)")
                ctrl.step(progress=True)

        elapsed_all = time.time() - t0_all
        log.info(f"Parallel gauntlet: {total_pairs} matchups in {elapsed_all:.0f}s "
                 f"({total_pairs * games / elapsed_all:.0f} games/sec)")

    else:
        # Sequential execution (original)
        for idx, (deck_a, deck_b) in enumerate(pairs):
            if not ctrl.can_continue():
                log.warn(f"Loop controller stopped: {ctrl.stop_reason}")
                break

            name_a = deck_a["name"]
            name_b = deck_b["name"]
            log.info(f"[{idx+1}/{total_pairs}] {name_a} vs {name_b} ({games} games)...")

            t0 = time.time()
            try:
                results = run_match_set(
                    deck_a["apl"], deck_a["mainboard"],
                    deck_b["apl"], deck_b["mainboard"],
                    n=games, mix_play_draw=True, seed=42 + idx,
                )
                elapsed = time.time() - t0
                win_pct_a = results.win_pct_a()

                matrix[(name_a, name_b)] = win_pct_a
                matrix[(name_b, name_a)] = round(100.0 - win_pct_a, 1)

                log.info(f"  {name_a} {win_pct_a}% - {100.0 - win_pct_a:.1f}% {name_b} "
                         f"(avg {results.avg_turns:.1f}T, {elapsed:.1f}s)")
                ctrl.step(progress=True)

            except Exception as e:
                log.error(f"  FAILED: {e}")
                ctrl.step(progress=False)

    summary = ctrl.summary()
    log.info(f"Gauntlet complete: {summary['steps']} matchups in {summary['elapsed']:.0f}s")
    return matrix


# ---------------------------------------------------------------------------
# Field-weighted win rates
# ---------------------------------------------------------------------------

def compute_field_wr(matrix: dict, entries: list[dict],
                     format_name: str) -> dict[str, float]:
    """
    Compute field-weighted win rate for each deck using meta shares.
    Returns {deck_name: field_wr_pct}.
    """
    # Try to get meta shares
    meta_shares = {}
    try:
        from db_bridge import get_meta_field
        raw_meta = get_meta_field(format_name, top_n=50)
        # Map meta archetypes to our deck names (fuzzy match)
        for entry in entries:
            slug_lower = entry["slug"].lower()
            best_share = 0.0
            for arch, share in raw_meta.items():
                arch_slug = arch.lower().replace(" ", "_").replace("-", "_")
                if slug_lower in arch_slug or arch_slug in slug_lower:
                    best_share = max(best_share, share)
            meta_shares[entry["name"]] = best_share
        log.info(f"Meta shares loaded: {meta_shares}")
    except Exception as e:
        log.warn(f"Could not load meta shares: {e}. Using equal weighting.")
        for entry in entries:
            meta_shares[entry["name"]] = 1.0

    # Normalize shares to sum to 100 across the field we have
    total_share = sum(meta_shares.values())
    if total_share == 0:
        total_share = len(entries)
        meta_shares = {e["name"]: 1.0 for e in entries}

    deck_names = [e["name"] for e in entries]
    field_wr = {}

    for deck in deck_names:
        weighted_sum = 0.0
        weight_total = 0.0
        for opp in deck_names:
            if opp == deck:
                continue
            key = (deck, opp)
            if key not in matrix:
                continue
            opp_weight = meta_shares.get(opp, 1.0)
            weighted_sum += matrix[key] * opp_weight
            weight_total += opp_weight

        if weight_total > 0:
            field_wr[deck] = round(weighted_sum / weight_total, 1)
        else:
            field_wr[deck] = 50.0  # no data

    return field_wr


# ---------------------------------------------------------------------------
# Output: stdout table
# ---------------------------------------------------------------------------

def print_matrix(entries: list[dict], matrix: dict,
                 field_wr: dict[str, float]):
    """Print a formatted matchup matrix table to stdout."""
    names = [e["name"] for e in entries]

    # Truncate names for display
    max_name = 18
    short = {n: (n[:max_name-2] + "..") if len(n) > max_name else n for n in names}

    # Header
    header = f"{'':>{max_name}}"
    for n in names:
        header += f"  {short[n]:>8}"
    header += f"  {'Field WR':>8}"
    print()
    print("=" * len(header))
    print(header)
    print("-" * len(header))

    for deck in names:
        row = f"{short[deck]:>{max_name}}"
        for opp in names:
            if deck == opp:
                row += f"  {'--':>8}"
            else:
                key = (deck, opp)
                if key in matrix:
                    row += f"  {matrix[key]:>7.1f}%"
                else:
                    row += f"  {'?':>8}"
        fw = field_wr.get(deck, 0.0)
        row += f"  {fw:>7.1f}%"
        print(row)

    print("=" * len(header))
    print()


# ---------------------------------------------------------------------------
# Output: CSV
# ---------------------------------------------------------------------------

def write_csv(entries: list[dict], matrix: dict,
              field_wr: dict[str, float], format_name: str) -> str:
    """Write matchup matrix to CSV. Returns file path."""
    TEAM_DATA_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = TEAM_DATA_DIR / f"gauntlet_matrix_{format_name}.csv"

    names = [e["name"] for e in entries]

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        # Header row
        writer.writerow(["Deck"] + names + ["Field WR"])
        # Data rows
        for deck in names:
            row = [deck]
            for opp in names:
                if deck == opp:
                    row.append("--")
                else:
                    key = (deck, opp)
                    row.append(f"{matrix.get(key, 0):.1f}")
            row.append(f"{field_wr.get(deck, 0):.1f}")
            writer.writerow(row)

    log.info(f"CSV written: {csv_path}")
    return str(csv_path)


# ---------------------------------------------------------------------------
# Output: knowledge block
# ---------------------------------------------------------------------------

def write_knowledge_block(entries: list[dict], matrix: dict,
                          field_wr: dict[str, float],
                          format_name: str, games: int) -> str:
    """Write a knowledge block markdown file. Returns file path."""
    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    kb_path = KNOWLEDGE_DIR / f"gauntlet-{format_name}-{today}.md"

    names = [e["name"] for e in entries]
    # Sort by field WR descending
    ranked = sorted(names, key=lambda n: -field_wr.get(n, 0))

    lines = [
        "---",
        f"title: {format_name.title()} Gauntlet Results",
        f"last_updated: {today}",
        "confidence: sim-derived",
        f"sources: [mtg-sim match engine, {games} games/pair]",
        "---",
        "",
        f"# {format_name.title()} Matchup Gauntlet - {today}",
        "",
        f"**Engine**: mtg-sim match engine (real two-player games)",
        f"**Games per pair**: {games}",
        f"**Decks tested**: {len(entries)}",
        "",
        "## Tier List (by field-weighted win rate)",
        "",
    ]

    # Tier thresholds
    for i, deck in enumerate(ranked, 1):
        fw = field_wr.get(deck, 0)
        apl_src = next((e["apl_source"] for e in entries if e["name"] == deck), "?")
        lines.append(f"{i}. **{deck}** -- {fw:.1f}% field WR ({apl_src})")

    lines.extend(["", "## Matchup Matrix", ""])

    # Compact matrix
    short_names = {n: n.split()[0][:8] for n in names}  # first word, 8 chars
    # Handle duplicates in short names
    seen = {}
    for n in names:
        s = short_names[n]
        if s in seen:
            seen[s] += 1
            short_names[n] = s + str(seen[s])
        else:
            seen[s] = 1

    header = "| Deck |"
    sep = "|------|"
    for n in ranked:
        header += f" {short_names[n]} |"
        sep += "------|"
    header += " Field |"
    sep += "------|"
    lines.append(header)
    lines.append(sep)

    for deck in ranked:
        row = f"| {deck} |"
        for opp in ranked:
            if deck == opp:
                row += " -- |"
            else:
                key = (deck, opp)
                val = matrix.get(key, 0)
                row += f" {val:.1f} |"
        row += f" {field_wr.get(deck, 0):.1f} |"
        lines.append(row)

    lines.extend([
        "",
        "## APL Coverage",
        "",
        "| Deck | APL Type | Class |",
        "|------|----------|-------|",
    ])
    for e in entries:
        lines.append(f"| {e['name']} | {e['apl_source']} | {e['apl'].__class__.__name__} |")

    lines.extend([
        "",
        "## Changelog",
        f"- {today}: Generated via matchup_gauntlet.py ({games} games/pair, "
        f"{len(entries)} decks)",
    ])

    kb_path.write_text("\n".join(lines), encoding="utf-8")
    log.info(f"Knowledge block written: {kb_path}")
    return str(kb_path)


# ---------------------------------------------------------------------------
# Dry run
# ---------------------------------------------------------------------------

def dry_run(entries: list[dict], games: int, single_deck: Optional[str]):
    """Print what would be run without executing any games."""
    log.section("DRY RUN -- no games will be played")

    names = [e["name"] for e in entries]
    if single_deck:
        target = single_deck.title()
        opponents = [n for n in names if n.lower() != single_deck.lower()]
        pairs = [(target, o) for o in opponents]
    else:
        pairs = list(combinations(names, 2))

    total_games = len(pairs) * games
    est_seconds = total_games * 0.005  # rough estimate ~200 games/sec

    print(f"\nFormat decks ({len(entries)}):")
    for e in entries:
        results_str = ""
        if e.get("results"):
            results_str = f"  [{e['results']} results, best #{e.get('best_finish', '?')}]"
        meta_str = f"{e.get('meta_share', 0):.1f}%" if e.get("meta_share") else ""
        print(f"  {e['name']:<30} APL: {e['apl_source']:<18} "
              f"({e['apl'].__class__.__name__}) {meta_str}{results_str}")

    print(f"\nMatchups: {len(pairs)}")
    print(f"Games per matchup: {games}")
    print(f"Total games: {total_games:,}")
    print(f"Estimated time: {est_seconds:.0f}s ({est_seconds/60:.1f}m)")
    print()

    for i, (a, b) in enumerate(pairs[:20], 1):
        print(f"  {i:3d}. {a} vs {b}")
    if len(pairs) > 20:
        print(f"  ... and {len(pairs) - 20} more")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Run a full matchup gauntlet using the mtg-sim match engine.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python matchup_gauntlet.py --format modern --games 500
  python matchup_gauntlet.py --format modern --games 1000 --top 8
  python matchup_gauntlet.py --format standard --dry-run
  python matchup_gauntlet.py --format modern --deck "Boros Energy"
        """,
    )
    parser.add_argument("--format", default="modern",
                        help="Format to test (matches deck file suffix)")
    parser.add_argument("--games", type=int, default=500,
                        help="Games per matchup (default: 500)")
    parser.add_argument("--top", type=int, default=None,
                        help="Only test top N decks by meta share")
    parser.add_argument("--deck", type=str, default=None,
                        help="Single deck name to test vs the field")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would run without playing games")
    parser.add_argument("--no-csv", action="store_true",
                        help="Skip CSV output")
    parser.add_argument("--no-kb", action="store_true",
                        help="Skip knowledge block output")
    parser.add_argument("--parallel", type=int, default=0,
                        help="Run N matchups in parallel (0=sequential, 4-8 recommended)")
    args = parser.parse_args()

    log.section(f"Matchup Gauntlet: {args.format}")
    log.info(f"Games per matchup: {args.games}")
    if args.deck:
        log.info(f"Single deck mode: {args.deck}")
    if args.top:
        log.info(f"Top N filter: {args.top}")

    # 1. Discover decks
    decks = discover_decks(args.format, top_n=args.top)
    if not decks:
        log.error("No decks found. Exiting.")
        sys.exit(1)

    # 2. Load decks and APLs
    entries = prepare_entries(decks)
    if len(entries) < 2:
        log.error(f"Need at least 2 decks, got {len(entries)}. Exiting.")
        sys.exit(1)

    # 3. Dry run check
    if args.dry_run:
        dry_run(entries, args.games, args.deck)
        return

    # 4. Run the gauntlet
    matrix = run_gauntlet(entries, games=args.games, single_deck=args.deck,
                          parallel_matchups=args.parallel)
    if not matrix:
        log.error("No results produced. Exiting.")
        sys.exit(1)

    # 5. Compute field-weighted win rates
    field_wr = compute_field_wr(matrix, entries, args.format)

    # 6. Output
    log.section("Results")
    print_matrix(entries, matrix, field_wr)

    if not args.no_csv:
        csv_path = write_csv(entries, matrix, field_wr, args.format)
        print(f"CSV: {csv_path}")

    if not args.no_kb:
        kb_path = write_knowledge_block(entries, matrix, field_wr,
                                         args.format, args.games)
        print(f"Knowledge block: {kb_path}")

    # 7. Summary to log
    ranked = sorted(field_wr.items(), key=lambda x: -x[1])
    log.section("Final Rankings")
    for i, (deck, fw) in enumerate(ranked, 1):
        log.info(f"  {i}. {deck:<30} {fw:.1f}% field WR")

    log.success(f"Gauntlet complete: {len(matrix)//2} matchups, "
                f"{len(entries)} decks, {args.games} games/pair")


if __name__ == "__main__":
    main()
