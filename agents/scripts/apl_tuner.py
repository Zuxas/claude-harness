"""
apl_tuner.py — APL Generation + Tuning Agent for the Zuxas Harness

Orchestrates the full APL lifecycle:
  1. Generate APL (via auto_apl.py/Claude API or load existing)
  2. Validate via goldfish sim (does it even run? what's the kill turn?)
  3. Run matchup gauntlet (how does it perform vs the field?)
  4. Analyze results via Gemma 4 (local, free) 
  5. Propose improvements
  6. Output knowledge block to harness/knowledge/mtg/

USAGE:
  python apl_tuner.py "Boros Energy" --mode validate
  python apl_tuner.py "Humans" --mode full --format legacy
  python apl_tuner.py "Izzet Prowess" --mode tune --iterations 3
  python apl_tuner.py --list-decks --format modern

REQUIRES:
  - mtg-sim in E:\\vscode ai project\\mtg-sim
  - Ollama running with gemma4 model
  - harness at E:\\vscode ai project\\harness
"""

import sys
import os
import json
import time
import argparse
import urllib.request
from pathlib import Path
from datetime import datetime

# Add mtg-sim to path
SIM_ROOT = Path("E:/vscode ai project/mtg-sim")
sys.path.insert(0, str(SIM_ROOT))

HARNESS_ROOT = Path("E:/vscode ai project/harness")
OLLAMA_API = "http://localhost:11434/api/generate"

# ---------------------------------------------------------------------------
# Gemma 4 Integration (local analysis, $0.00)
# ---------------------------------------------------------------------------

def ask_gemma(question: str, context: str = "", model: str = "gemma4") -> str:
    """Send a question to Gemma 4 via Ollama API. Returns answer text."""
    prompt = question
    if context:
        prompt = f"Context:\n{context}\n\nQuestion: {question}"
    
    body = json.dumps({
        "model": model,
        "prompt": prompt,
        "system": "You are an expert MTG competitive analyst. Answer concisely with specific, actionable advice.",
        "stream": False,
        "options": {"temperature": 0.3, "num_predict": 2048}
    }).encode()
    
    try:
        req = urllib.request.Request(OLLAMA_API, data=body,
                                     headers={"Content-Type": "application/json"},
                                     method="POST")
        with urllib.request.urlopen(req, timeout=300) as resp:
            data = json.loads(resp.read())
            return data.get("response", "")
    except Exception as e:
        print(f"[gemma] API call failed: {e}")
        return f"ERROR: {e}"


# ---------------------------------------------------------------------------
# Sim Helpers
# ---------------------------------------------------------------------------

def list_available_decks(format_name: str = "modern") -> list:
    """List all deck files for a format."""
    deck_dir = SIM_ROOT / "decks"
    decks = []
    for f in deck_dir.glob("*.txt"):
        name = f.stem
        if format_name.lower() in name.lower() or "_" not in name:
            decks.append(name)
    # Also check format-specific naming
    for f in deck_dir.glob(f"*_{format_name}*.txt"):
        if f.stem not in decks:
            decks.append(f.stem)
    return sorted(decks)


def list_available_apls() -> dict:
    """List all APL files and their types (hand-written vs auto)."""
    apl_dir = SIM_ROOT / "apl"
    auto_dir = SIM_ROOT / "data" / "auto_apls"
    
    result = {"hand_written": [], "auto_generated": [], "match_aware": []}
    
    for f in apl_dir.glob("*.py"):
        name = f.stem
        if name.startswith("_") or name in ("base_apl", "auto_apl", "generic_apl",
                                              "match_apl", "mulligan", "sb_mixin",
                                              "sb_plans", "playbook_parser"):
            continue
        if "_match" in name:
            result["match_aware"].append(name)
        else:
            result["hand_written"].append(name)
    
    if auto_dir.exists():
        for f in auto_dir.glob("*.py"):
            result["auto_generated"].append(f.stem)
    
    return result


def run_goldfish(deck_name: str, n_games: int = 1000) -> dict:
    """Run goldfish simulation and return results summary."""
    try:
        from data.deck import load_deck_from_file
        from engine.runner import run_simulation
        from apl.auto_apl import AutoAPLFactory
        
        # Try to find deck file
        deck_dir = SIM_ROOT / "decks"
        deck_file = None
        for f in deck_dir.glob("*.txt"):
            if deck_name.lower().replace(" ", "_") in f.stem.lower():
                deck_file = f
                break
        
        if not deck_file:
            return {"error": f"No deck file found for '{deck_name}'"}
        
        mainboard, sideboard = load_deck_from_file(str(deck_file))
        
        # Try hand-written APL first, then auto
        apl = _load_apl(deck_name)
        if not apl:
            factory = AutoAPLFactory()
            apl = factory.get_apl(deck_name)
        
        print(f"[sim] Running {n_games} goldfish games with {type(apl).__name__}...")
        start = time.time()
        results = run_simulation(apl, mainboard, n=n_games, on_play=True)
        elapsed = time.time() - start
        
        return {
            "deck": deck_name,
            "apl": type(apl).__name__,
            "games": n_games,
            "win_rate": results.win_rate(),
            "avg_kill": results.avg_kill_turn(),
            "median_kill": results.median_kill_turn(),
            "fastest": min(results.kill_turns) if results.kill_turns else 0,
            "time_sec": round(elapsed, 1),
            "games_per_sec": round(n_games / elapsed, 0),
        }
    except Exception as e:
        return {"error": str(e)}


def _load_apl(deck_name: str):
    """Try to load a hand-written APL by deck name."""
    apl_dir = SIM_ROOT / "apl"
    safe_name = deck_name.lower().replace(" ", "_").replace("-", "_")
    
    # Direct file match
    apl_file = apl_dir / f"{safe_name}.py"
    if not apl_file.exists():
        # Fuzzy match
        for f in apl_dir.glob("*.py"):
            if safe_name in f.stem.lower():
                apl_file = f
                break
    
    if not apl_file.exists():
        return None
    
    try:
        import importlib.util
        from apl.base_apl import BaseAPL
        spec = importlib.util.spec_from_file_location(f"apl_{safe_name}", str(apl_file))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if isinstance(attr, type) and issubclass(attr, BaseAPL) and attr is not BaseAPL:
                return attr()
    except Exception as e:
        print(f"[apl] Failed to load {apl_file.name}: {e}")
    return None


def run_gauntlet(deck_name: str, format_name: str = "modern", 
                 n_games: int = 500) -> dict:
    """Run deck vs all opponents in the format. Returns matchup matrix."""
    try:
        from engine.meta_solver import MetaSolver
        
        solver = MetaSolver(format_name=format_name, sim_root=str(SIM_ROOT))
        print(f"[gauntlet] Running {deck_name} vs field ({format_name})...")
        start = time.time()
        results = solver.run_single_deck(deck_name, n_per_matchup=n_games)
        elapsed = time.time() - start
        
        return {
            "deck": deck_name,
            "format": format_name,
            "field_wr": results.get("field_weighted_wr", 0),
            "matchups": results.get("matchups", {}),
            "worst_matchup": results.get("worst_matchup", "unknown"),
            "best_matchup": results.get("best_matchup", "unknown"),
            "time_sec": round(elapsed, 1),
        }
    except Exception as e:
        # Fallback: run individual goldfish if meta solver not available
        print(f"[gauntlet] MetaSolver not available, running goldfish only: {e}")
        return run_goldfish(deck_name, n_games)


# ---------------------------------------------------------------------------
# Analysis + Tuning Loop
# ---------------------------------------------------------------------------

def analyze_results(deck_name: str, goldfish: dict, gauntlet: dict = None) -> str:
    """Send sim results to Gemma 4 for analysis. Returns analysis text."""
    
    context = f"Deck: {deck_name}\n"
    context += f"Goldfish results: {json.dumps(goldfish, indent=2)}\n"
    if gauntlet:
        context += f"Gauntlet results: {json.dumps(gauntlet, indent=2)}\n"
    
    # Read the APL source if available
    apl_source = _read_apl_source(deck_name)
    if apl_source:
        context += f"\nCurrent APL source code:\n{apl_source[:3000]}\n"
    
    question = """Analyze this MTG simulation data and provide:
1. ASSESSMENT: Is the goldfish kill turn competitive for this archetype?
2. WEAK MATCHUPS: Which matchups are below 45%? Why?
3. IMPROVEMENTS: What specific APL changes would improve performance?
   - Card sequencing priorities to change
   - Mulligan criteria adjustments
   - Sideboard plan suggestions for weak matchups
4. CARD SWAPS: Any mainboard card swaps worth testing in the variant tester?

Be specific with card names and numbers. Reference the APL code directly."""

    print("[gemma] Analyzing results locally (free)...")
    return ask_gemma(question, context)


def _read_apl_source(deck_name: str) -> str:
    """Read the APL source code for a deck."""
    apl_dir = SIM_ROOT / "apl"
    safe_name = deck_name.lower().replace(" ", "_").replace("-", "_")
    
    for f in apl_dir.glob("*.py"):
        if safe_name in f.stem.lower():
            try:
                return f.read_text(encoding="utf-8")
            except:
                pass
    return ""


# ---------------------------------------------------------------------------
# Knowledge Block Output
# ---------------------------------------------------------------------------

def write_knowledge_block(deck_name: str, goldfish: dict, 
                          gauntlet: dict = None, analysis: str = "") -> str:
    """Write simulation results as a harness knowledge block."""
    today = datetime.now().strftime("%Y-%m-%d")
    safe_name = deck_name.lower().replace(" ", "-").replace("_", "-")
    
    block = f"""---
title: "Sim Report: {deck_name}"
domain: "mtg"
last_updated: "{today}"
confidence: "high"
sources: ["apl-tuner-agent", "mtg-sim-gauntlet"]
---

## Summary
Automated simulation report for {deck_name} generated by the APL tuner agent.

## Goldfish Results
- APL: {goldfish.get('apl', 'unknown')}
- Win Rate: {goldfish.get('win_rate', 'N/A')}%
- Avg Kill Turn: {goldfish.get('avg_kill', 'N/A')}
- Median Kill: {goldfish.get('median_kill', 'N/A')}
- Fastest Kill: T{goldfish.get('fastest', 'N/A')}
- Speed: {goldfish.get('games_per_sec', 'N/A')} games/sec
"""
    
    if gauntlet and "matchups" in gauntlet:
        block += f"""
## Gauntlet Results
- Field-Weighted Win Rate: {gauntlet.get('field_wr', 'N/A')}%
- Best Matchup: {gauntlet.get('best_matchup', 'N/A')}
- Worst Matchup: {gauntlet.get('worst_matchup', 'N/A')}

### Matchup Breakdown
"""
        for opp, wr in sorted(gauntlet.get("matchups", {}).items(), 
                               key=lambda x: -x[1]):
            block += f"- vs {opp}: {wr:.1f}%\n"
    
    if analysis:
        block += f"""
## Gemma 4 Analysis
{analysis}
"""
    
    block += f"""
## Changelog
- {today}: Generated by apl_tuner.py -- automated simulation report
"""
    
    # Write to harness
    output_path = HARNESS_ROOT / "knowledge" / "mtg" / f"sim-{safe_name}.md"
    output_path.write_text(block, encoding="utf-8")
    print(f"[harness] Written: {output_path}")
    
    # Update _index.md
    index_path = HARNESS_ROOT / "knowledge" / "_index.md"
    index_entry = f"| mtg/sim-{safe_name} | mtg | {today} | apl-tuner-agent |"
    index_content = index_path.read_text(encoding="utf-8")
    if f"sim-{safe_name}" not in index_content:
        with open(index_path, "a", encoding="utf-8") as f:
            f.write(f"\n{index_entry}")
        print(f"[harness] Updated _index.md")
    
    return str(output_path)


# ---------------------------------------------------------------------------
# Main Pipeline
# ---------------------------------------------------------------------------

def run_pipeline(deck_name: str, format_name: str = "modern",
                 mode: str = "full", n_games: int = 1000):
    """
    Run the full APL tuning pipeline.
    
    Modes:
      validate  — goldfish only, check APL works
      analyze   — goldfish + Gemma analysis
      full      — goldfish + gauntlet + analysis + knowledge block
    """
    print(f"\n{'='*60}")
    print(f"  APL TUNER AGENT — {deck_name}")
    print(f"  Mode: {mode} | Format: {format_name} | Games: {n_games}")
    print(f"{'='*60}\n")
    
    start = time.time()
    
    # Step 1: Goldfish validation
    print("[1/4] Running goldfish simulation...")
    goldfish = run_goldfish(deck_name, n_games)
    
    if "error" in goldfish:
        print(f"[FAIL] Goldfish failed: {goldfish['error']}")
        return
    
    print(f"  Kill turn: {goldfish['avg_kill']} avg | "
          f"{goldfish['win_rate']}% win rate | "
          f"{goldfish['games_per_sec']} g/s")
    
    if mode == "validate":
        print(f"\n[DONE] Validation complete in {time.time()-start:.1f}s")
        return goldfish
    
    # Step 2: Gauntlet (if full mode)
    gauntlet = None
    if mode == "full":
        print("\n[2/4] Running matchup gauntlet...")
        gauntlet = run_gauntlet(deck_name, format_name, n_games // 2)
        if "error" not in gauntlet:
            print(f"  Field WR: {gauntlet.get('field_wr', 'N/A')}%")
            print(f"  Worst: {gauntlet.get('worst_matchup', 'N/A')}")
            print(f"  Best: {gauntlet.get('best_matchup', 'N/A')}")
    else:
        print("\n[2/4] Skipping gauntlet (use --mode full)")
    
    # Step 3: Gemma analysis
    print("\n[3/4] Analyzing with Gemma 4 (local, $0.00)...")
    analysis = analyze_results(deck_name, goldfish, gauntlet)
    print(f"  Analysis: {len(analysis)} chars")
    
    # Step 4: Write knowledge block
    print("\n[4/4] Writing knowledge block to harness...")
    output = write_knowledge_block(deck_name, goldfish, gauntlet, analysis)
    
    elapsed = time.time() - start
    print(f"\n{'='*60}")
    print(f"  PIPELINE COMPLETE")
    print(f"  Time: {elapsed:.1f}s | Cost: $0.00 (local analysis)")
    print(f"  Output: {output}")
    print(f"  Next: Ask Claude Code about this report")
    print(f"{'='*60}\n")
    
    return {"goldfish": goldfish, "gauntlet": gauntlet, "analysis": analysis}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="APL Tuner Agent")
    parser.add_argument("deck", nargs="?", help="Deck name (e.g. 'Boros Energy')")
    parser.add_argument("--mode", choices=["validate", "analyze", "full"],
                        default="analyze", help="Pipeline mode")
    parser.add_argument("--format", default="modern", help="Format name")
    parser.add_argument("--games", type=int, default=1000, help="Games per sim")
    parser.add_argument("--list-decks", action="store_true", help="List available decks")
    parser.add_argument("--list-apls", action="store_true", help="List available APLs")
    
    args = parser.parse_args()
    
    if args.list_apls:
        apls = list_available_apls()
        print(f"\nHand-written APLs ({len(apls['hand_written'])}):")
        for a in apls["hand_written"]:
            print(f"  {a}")
        print(f"\nMatch-aware APLs ({len(apls['match_aware'])}):")
        for a in apls["match_aware"]:
            print(f"  {a}")
        print(f"\nAuto-generated APLs ({len(apls['auto_generated'])}):")
        for a in apls["auto_generated"]:
            print(f"  {a}")
        sys.exit(0)
    
    if args.list_decks:
        decks = list_available_decks(args.format)
        print(f"\nAvailable decks ({args.format}): {len(decks)}")
        for d in decks:
            print(f"  {d}")
        sys.exit(0)
    
    if not args.deck:
        parser.print_help()
        sys.exit(1)
    
    run_pipeline(args.deck, args.format, args.mode, args.games)
