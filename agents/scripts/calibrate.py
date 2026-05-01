"""
calibrate.py -- Layer 4: Real Match Feedback Loop

Compares sim predictions vs actual match results from MTGA logs.
Identifies where the sim is wrong and feeds corrections back.

FLOW:
  1. Read real match data from match_log table
  2. Run sim for the same matchup
  3. Compare predicted vs actual win rates
  4. Score sim accuracy per matchup
  5. Flag matchups where sim diverges from reality
  6. Write calibration report to harness knowledge base
  7. Feed discrepancy data into tuning loop priorities

USAGE:
  python calibrate.py                          # analyze all matches
  python calibrate.py --deck "Dimir Tempo"     # specific deck
  python calibrate.py --format standard        # specific format
  python calibrate.py --min-matches 3          # require N matches minimum
  python calibrate.py --dry-run                # show data without simming

REQUIRES: match_log populated via parse-mtga.ps1, mtg-sim operational
"""

import sys
import os
import json
import time
import sqlite3
import argparse
from pathlib import Path
from datetime import datetime
from collections import defaultdict

SIM_ROOT = Path("E:/vscode ai project/mtg-sim")
HARNESS_ROOT = Path("E:/vscode ai project/harness")
META_DB = Path("E:/vscode ai project/mtg-meta-analyzer/data/mtg_meta.db")
sys.path.insert(0, str(SIM_ROOT))

TODAY = datetime.now().strftime("%Y-%m-%d")

# ---------------------------------------------------------------------------
# Real Match Data
# ---------------------------------------------------------------------------

def load_real_matches(deck=None, format_name=None, min_date=None):
    """Load match results from match_log table."""
    conn = sqlite3.connect(str(META_DB))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    query = "SELECT * FROM match_log WHERE 1=1"
    params = []
    if deck:
        query += " AND my_deck LIKE ?"
        params.append(f"%{deck}%")
    if format_name:
        query += " AND format = ?"
        params.append(format_name)
    if min_date:
        query += " AND event_date >= ?"
        params.append(min_date)
    query += " ORDER BY event_date DESC"
    
    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def aggregate_matchups(matches):
    """Aggregate match results by my_deck vs opp_deck."""
    matchups = defaultdict(lambda: {
        "wins": 0, "losses": 0, "total": 0,
        "g1_wins": 0, "g1_losses": 0, "g1_total": 0,
        "play_wins": 0, "play_total": 0,
        "draw_wins": 0, "draw_total": 0,
        "matches": []
    })
    
    for m in matches:
        my_deck = m["my_deck"] or "Unknown"
        opp_deck = m["opp_deck"] or "Unknown Opponent"
        key = (my_deck, opp_deck)
        mu = matchups[key]
        
        is_win = m["result"] == "win"
        mu["total"] += 1
        mu["wins"] += int(is_win)
        mu["losses"] += int(not is_win)
        
        # Per-game tracking
        for g in ["g1_result", "g2_result", "g3_result"]:
            if m.get(g) and m[g] in ("win", "loss"):
                if g == "g1_result":
                    mu["g1_total"] += 1
                    mu["g1_wins"] += int(m[g] == "win")
                    mu["g1_losses"] += int(m[g] == "loss")
        
        # Play/draw tracking
        pd = m.get("play_draw", "")
        if pd == "play":
            mu["play_total"] += 1
            mu["play_wins"] += int(is_win)
        elif pd == "draw":
            mu["draw_total"] += 1
            mu["draw_wins"] += int(is_win)
        
        mu["matches"].append(m)
    
    return dict(matchups)


# ---------------------------------------------------------------------------
# Sim Prediction Lookup
# ---------------------------------------------------------------------------

def get_sim_prediction(my_deck, opp_deck, n_games=500):
    """Run sim for a specific matchup and return predicted win rate."""
    try:
        from data.deck import load_deck_from_file
        from engine.match_engine import run_match_set
        from apl.match_apl import GenericMatchAPL
        
        deck_dir = SIM_ROOT / "decks"
        
        # Find deck files by fuzzy name match
        my_file = _find_deck_file(my_deck, deck_dir)
        opp_file = _find_deck_file(opp_deck, deck_dir)
        
        if not my_file or not opp_file:
            missing = []
            if not my_file: missing.append(f"my_deck: {my_deck}")
            if not opp_file: missing.append(f"opp_deck: {opp_deck}")
            return {"status": "no_deck_file", "missing": missing}
        
        my_cards, _ = load_deck_from_file(str(my_file))
        opp_cards, _ = load_deck_from_file(str(opp_file))
        
        apl_a = GenericMatchAPL()
        apl_b = GenericMatchAPL()
        
        results = run_match_set(apl_a, my_cards, apl_b, opp_cards, n=n_games)
        
        return {
            "status": "ok",
            "sim_wr": round(results.win_rate_a() * 100, 1),
            "games": n_games,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def _find_deck_file(deck_name, deck_dir):
    """Fuzzy match a deck name to a file in the decks directory."""
    if not deck_name or deck_name == "Unknown Opponent":
        return None
    safe = deck_name.lower().replace(" ", "_").replace("-", "_")
    for f in deck_dir.glob("*.txt"):
        if safe in f.stem.lower():
            return f
    # Try partial match
    words = safe.split("_")
    for f in deck_dir.glob("*.txt"):
        stem = f.stem.lower()
        if all(w in stem for w in words if len(w) > 2):
            return f
    return None


# ---------------------------------------------------------------------------
# Calibration Engine
# ---------------------------------------------------------------------------

def calibrate(matchups, n_sim_games=500, dry_run=False):
    """Compare real results vs sim predictions for each matchup."""
    results = []
    
    for (my_deck, opp_deck), data in matchups.items():
        real_wr = round(data["wins"] / max(data["total"], 1) * 100, 1)
        real_g1_wr = round(data["g1_wins"] / max(data["g1_total"], 1) * 100, 1) if data["g1_total"] > 0 else None
        
        entry = {
            "my_deck": my_deck,
            "opp_deck": opp_deck,
            "real_matches": data["total"],
            "real_wr": real_wr,
            "real_g1_wr": real_g1_wr,
            "play_wr": round(data["play_wins"] / max(data["play_total"], 1) * 100, 1) if data["play_total"] > 0 else None,
            "draw_wr": round(data["draw_wins"] / max(data["draw_total"], 1) * 100, 1) if data["draw_total"] > 0 else None,
        }
        
        if dry_run:
            entry["sim_wr"] = None
            entry["delta"] = None
            entry["accuracy"] = None
        else:
            # Run sim prediction
            print(f"  Simming: {my_deck} vs {opp_deck}...", end=" ")
            sim = get_sim_prediction(my_deck, opp_deck, n_sim_games)
            
            if sim["status"] == "ok":
                entry["sim_wr"] = sim["sim_wr"]
                entry["delta"] = round(entry["real_wr"] - sim["sim_wr"], 1)
                entry["accuracy"] = _score_accuracy(entry["delta"], data["total"])
                print(f"Real: {real_wr}% | Sim: {sim['sim_wr']}% | Delta: {entry['delta']:+.1f}% [{entry['accuracy']}]")
            else:
                entry["sim_wr"] = None
                entry["delta"] = None
                entry["accuracy"] = "no_sim"
                print(f"Real: {real_wr}% | Sim: N/A ({sim['status']})")
        
        results.append(entry)
    
    return results


def _score_accuracy(delta, n_matches):
    """Score how accurate the sim is for this matchup."""
    abs_delta = abs(delta)
    
    # Small sample warning
    if n_matches < 5:
        if abs_delta < 15:
            return "low_sample_ok"
        return "low_sample_divergent"
    
    # Enough data to judge
    if abs_delta < 5:
        return "accurate"
    elif abs_delta < 10:
        return "close"
    elif abs_delta < 20:
        return "divergent"
    else:
        return "wrong"


# ---------------------------------------------------------------------------
# Knowledge Block Output
# ---------------------------------------------------------------------------

def write_calibration_report(results, deck_filter=None, format_filter=None):
    """Write calibration results as a harness knowledge block."""
    total = len(results)
    with_sim = [r for r in results if r.get("sim_wr") is not None]
    accurate = [r for r in with_sim if r["accuracy"] in ("accurate", "close", "low_sample_ok")]
    divergent = [r for r in with_sim if r["accuracy"] in ("divergent", "wrong", "low_sample_divergent")]
    
    lines = [
        "---",
        f'title: "Calibration Report ({TODAY})"',
        f'domain: "mtg"',
        f'last_updated: "{TODAY}"',
        f'confidence: "high"',
        f'sources: ["calibration-agent", "match_log", "mtg-sim"]',
        "---",
        "",
        f"## Sim Calibration Report -- {TODAY}",
        f"Deck filter: {deck_filter or 'all'} | Format: {format_filter or 'all'}",
        f"Matchups analyzed: {total} | With sim data: {len(with_sim)}",
        f"Accurate: {len(accurate)} | Divergent: {len(divergent)}",
        "",
    ]
    
    # Divergent matchups first (these need attention)
    if divergent:
        lines.append("## ATTENTION: Sim Diverges From Reality")
        lines.append("These matchups have significant gaps between sim predictions and real results.")
        lines.append("The tuning loop should prioritize these for APL adjustment.")
        lines.append("")
        for r in sorted(divergent, key=lambda x: -abs(x.get("delta", 0))):
            lines.append(f"### {r['my_deck']} vs {r['opp_deck']}")
            lines.append(f"- Real: {r['real_wr']}% ({r['real_matches']} matches)")
            lines.append(f"- Sim: {r['sim_wr']}%")
            lines.append(f"- Delta: {r['delta']:+.1f}% [{r['accuracy']}]")
            if r.get("real_g1_wr") is not None:
                lines.append(f"- G1 real WR: {r['real_g1_wr']}%")
            if r.get("play_wr") is not None:
                lines.append(f"- Play WR: {r['play_wr']}% | Draw WR: {r.get('draw_wr', '?')}%")
            sim_dir = "overestimates" if r["delta"] < 0 else "underestimates"
            lines.append(f"- Interpretation: Sim {sim_dir} this matchup by {abs(r['delta'])}%")
            lines.append("")
    
    # All matchup data
    lines.append("## Full Matchup Data")
    lines.append("| My Deck | Opponent | Real WR | Sim WR | Delta | Accuracy | Matches |")
    lines.append("|---------|----------|---------|--------|-------|----------|---------|")
    for r in results:
        sim = f"{r['sim_wr']}%" if r.get("sim_wr") is not None else "N/A"
        delta = f"{r['delta']:+.1f}%" if r.get("delta") is not None else "N/A"
        acc = r.get("accuracy", "N/A")
        lines.append(f"| {r['my_deck']} | {r['opp_deck']} | {r['real_wr']}% | {sim} | {delta} | {acc} | {r['real_matches']} |")
    
    lines.extend(["", "## Changelog", f"- {TODAY}: Generated by calibrate.py"])
    
    path = HARNESS_ROOT / "knowledge" / "mtg" / f"calibration-{TODAY}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n[harness] Calibration report: {path}")
    return str(path)


# ---------------------------------------------------------------------------
# Main Pipeline
# ---------------------------------------------------------------------------

def run_calibration(deck=None, format_name=None, min_matches=1,
                    n_sim_games=500, dry_run=False):
    """Run the full calibration pipeline."""
    print(f"\n{'='*60}")
    print(f"  LAYER 4: SIM CALIBRATION")
    print(f"  Deck: {deck or 'all'} | Format: {format_name or 'all'}")
    print(f"  Min matches: {min_matches} | Sim games: {n_sim_games}")
    print(f"{'='*60}\n")
    
    start = time.time()
    
    # Load real data
    print("[1/4] Loading real match data from match_log...")
    matches = load_real_matches(deck, format_name)
    print(f"  Found {len(matches)} matches")
    
    if not matches:
        print("  No matches found. Play some games and run parse-mtga.ps1 first.")
        return
    
    # Aggregate by matchup
    print("\n[2/4] Aggregating matchups...")
    matchups = aggregate_matchups(matches)
    
    # Filter by minimum matches
    filtered = {k: v for k, v in matchups.items() if v["total"] >= min_matches}
    print(f"  {len(filtered)} matchups with {min_matches}+ matches")
    
    if not filtered:
        print(f"  No matchups meet the {min_matches}-match threshold.")
        print(f"  You have {len(matchups)} matchups but need more games per matchup.")
        # Still show what we have
        for (my, opp), data in matchups.items():
            wr = round(data["wins"] / max(data["total"], 1) * 100, 1)
            print(f"    {my} vs {opp}: {wr}% ({data['total']} matches)")
        return
    
    # Run calibration
    print(f"\n[3/4] Running calibration (sim vs reality)...")
    results = calibrate(filtered, n_sim_games, dry_run)
    
    # Write report
    print(f"\n[4/4] Writing calibration report...")
    if not dry_run:
        write_calibration_report(results, deck, format_name)
    
    # Summary
    elapsed = time.time() - start
    with_sim = [r for r in results if r.get("sim_wr") is not None]
    divergent = [r for r in with_sim if r.get("accuracy") in ("divergent", "wrong")]
    
    print(f"\n{'='*60}")
    print(f"  CALIBRATION COMPLETE")
    print(f"  Matchups: {len(results)} | With sim: {len(with_sim)} | Divergent: {len(divergent)}")
    if with_sim:
        avg_delta = sum(abs(r["delta"]) for r in with_sim) / len(with_sim)
        print(f"  Avg absolute delta: {avg_delta:.1f}%")
    print(f"  Time: {elapsed:.1f}s | Cost: $0.00")
    print(f"{'='*60}")
    
    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Layer 4: Sim Calibration")
    parser.add_argument("--deck", default=None, help="Filter by deck name")
    parser.add_argument("--format", default=None, help="Filter by format")
    parser.add_argument("--min-matches", type=int, default=1, help="Minimum matches per matchup")
    parser.add_argument("--games", type=int, default=500, help="Sim games per matchup")
    parser.add_argument("--dry-run", action="store_true", help="Show data without simming")
    args = parser.parse_args()
    
    run_calibration(args.deck, args.format, args.min_matches, args.games, args.dry_run)
