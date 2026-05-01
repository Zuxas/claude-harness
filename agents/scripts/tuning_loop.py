"""
tuning_loop.py -- Layer 3: Autonomous APL Tuning Loop

Takes a deck, runs baseline sim, asks Gemma for card swap suggestions,
tests each swap against the field, keeps improvements, logs everything.

FLOW:
  1. Load deck + field from mtg-sim
  2. Run baseline field analysis (win rate vs every opponent)
  3. Ask Gemma to propose card swaps based on weak matchups
  4. Run variant tester on each proposed swap
  5. Compare field-weighted win rates (before vs after)
  6. Log results: improved / neutral / worse
  7. Write experiment report to harness/knowledge/mtg/
  8. Repeat for N iterations (each iteration uses prior results as context)

USAGE:
  python tuning_loop.py "Boros Energy" --format modern --iterations 3
  python tuning_loop.py "Humans" --format legacy --games 500
  python tuning_loop.py "Boros Energy" --dry-run

REQUIRES: Ollama running with gemma4, mtg-sim operational
"""

import sys
import os
import json
import time
import re
import argparse
from pathlib import Path
from datetime import datetime
from copy import deepcopy

SIM_ROOT = Path("E:/vscode ai project/mtg-sim")
HARNESS_ROOT = Path("E:/vscode ai project/harness")
sys.path.insert(0, str(SIM_ROOT))
sys.path.insert(0, str(HARNESS_ROOT / "agents" / "scripts"))

import urllib.request
from agent_hardening import (
    check_ollama_health, ollama_breaker, LoopController, AgentLogger
)

OLLAMA_API = "http://localhost:11434/api/generate"
TODAY = datetime.now().strftime("%Y-%m-%d")
META_DB = Path("E:/vscode ai project/mtg-meta-analyzer/data/mtg_meta.db")

log = AgentLogger("tuning-loop")

# ---------------------------------------------------------------------------
# Card Legality Checker
# ---------------------------------------------------------------------------

def check_card_legal(card_name, format_name):
    """Check if a card is legal in a format using Scryfall data in meta-analyzer DB."""
    import sqlite3
    if not META_DB.exists():
        return True  # fail open if DB missing
    try:
        conn = sqlite3.connect(str(META_DB))
        cur = conn.cursor()
        cur.execute("SELECT legalities FROM card_data WHERE name=? LIMIT 1", (card_name,))
        row = cur.fetchone()
        conn.close()
        if not row:
            return False  # card not found = assume illegal
        legs = json.loads(row[0])
        status = legs.get(format_name.lower(), "not_legal")
        return status == "legal"
    except Exception:
        return True  # fail open on error


def check_card_exists(card_name):
    """Check if a card exists in the Scryfall database."""
    import sqlite3
    if not META_DB.exists():
        return False
    try:
        conn = sqlite3.connect(str(META_DB))
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM card_data WHERE name=?", (card_name,))
        count = cur.fetchone()[0]
        conn.close()
        return count > 0
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Gemma Integration
# ---------------------------------------------------------------------------

def ask_gemma(question, context="", model="gemma4"):
    # Circuit breaker check before calling Ollama
    if not check_ollama_health():
        state = ollama_breaker.state
        log.error(f"Ollama unavailable (circuit: {state}) — cannot propose swaps")
        return f"ERROR: Ollama unavailable (circuit breaker {state})"

    prompt = question
    if context:
        prompt = f"Context:\n{context}\n\nQuestion: {question}"
    body = json.dumps({
        "model": model, "prompt": prompt,
        "system": "You are an expert MTG competitive analyst and deckbuilder. When suggesting card swaps, output ONLY in the exact format requested. No preamble.",
        "stream": False,
        "options": {"temperature": 0.3, "num_predict": 2048}
    }).encode()
    try:
        req = urllib.request.Request(OLLAMA_API, data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=300) as resp:
            result = json.loads(resp.read()).get("response", "")
            ollama_breaker.record_success()
            return result
    except Exception as e:
        ollama_breaker.record_failure()
        log.error(f"Ollama call failed: {e}")
        return f"ERROR: {e}"


def propose_swaps(deck_name, decklist_str, baseline_results, format_name="modern",
                  iteration=1, prior_experiments=""):
    """Ask Gemma to propose card swaps based on matchup data."""
    context = f"""Deck: {deck_name}
Format: {format_name} (ALL suggested cards MUST be legal in {format_name})
Current decklist:
{decklist_str}

Baseline field-weighted win rate: {baseline_results['field_wr']}%

Matchup breakdown:
"""
    for opp, wr in sorted(baseline_results['matchups'].items(), key=lambda x: x[1]):
        context += f"  vs {opp}: {wr:.1f}%\n"
    
    if prior_experiments:
        context += f"\nPrevious experiments this session:\n{prior_experiments}\n"

    question = f"""This is iteration {iteration} of an automated tuning loop.
Based on the matchup data above, suggest exactly 3 mainboard card swaps
that could improve the field-weighted win rate. Focus on the WORST matchups.

{"Do NOT repeat swaps from previous experiments." if prior_experiments else ""}

OUTPUT FORMAT (follow EXACTLY, one swap per line, no other text):
OUT:CardName|IN:CardName|REASON:one sentence
OUT:CardName|IN:CardName|REASON:one sentence
OUT:CardName|IN:CardName|REASON:one sentence

Rules:
- Card names must be real Magic cards legal in {format_name}
- CRITICAL: Only suggest cards that are LEGAL in {format_name}
  Modern-legal means printed in a Modern-legal set (8th Edition forward)
  Legacy-legal means not on the Legacy banned list
  Standard-legal means in the current Standard rotation
- OUT card must be in the current decklist
- IN card should address a specific weak matchup
- Each swap is independent (not cumulative)
- Do NOT suggest Commander-only cards, silver-border cards, or banned cards
"""
    return ask_gemma(question, context)


def parse_swaps(gemma_response):
    """Parse Gemma's swap suggestions into structured tuples."""
    swaps = []
    for line in gemma_response.strip().split("\n"):
        line = line.strip()
        if not line or not line.startswith("OUT:"):
            continue
        try:
            parts = line.split("|")
            card_out = parts[0].replace("OUT:", "").strip()
            card_in = parts[1].replace("IN:", "").strip()
            reason = parts[2].replace("REASON:", "").strip() if len(parts) > 2 else ""
            if card_out and card_in:
                swaps.append({"out": card_out, "in": card_in, "reason": reason})
        except (IndexError, ValueError):
            continue
    return swaps


# ---------------------------------------------------------------------------
# Sim Integration
# ---------------------------------------------------------------------------

def load_field(format_name="modern", max_decks=8):
    """Load the top N decks for a format from mtg-sim deck files."""
    from data.deck import load_deck_from_file
    from db_bridge import get_meta_field
    
    deck_dir = SIM_ROOT / "decks"
    shares = {}
    decks = {}
    
    try:
        raw_shares = get_meta_field(format_name, top_n=max_decks)
        # Convert from % to fraction, normalize names
        for name, pct in raw_shares.items():
            shares[name] = pct / 100.0
    except Exception as e:
        print(f"  Warning: Could not load meta shares: {e}")
    
    # Load deck files that match the format
    for f in deck_dir.glob(f"*_{format_name}.txt"):
        name = f.stem.replace(f"_{format_name}", "").replace("_", " ").title()
        try:
            main, sb = load_deck_from_file(str(f))
            decks[name] = main
            if name not in shares:
                shares[name] = 1.0 / max_decks  # equal weight fallback
        except Exception:
            continue
    
    # Trim to max_decks by share
    if len(decks) > max_decks:
        top_names = sorted(shares.keys(), key=lambda k: -shares.get(k, 0))[:max_decks]
        decks = {k: v for k, v in decks.items() if k in top_names}
        shares = {k: v for k, v in shares.items() if k in top_names}
    
    # Normalize shares
    total = sum(shares.values()) or 1.0
    shares = {k: v / total for k, v in shares.items()}
    
    return decks, shares


def run_baseline(deck, field_decks, field_shares, n_per=500):
    """Run baseline field analysis. Returns matchup dict + field WR."""
    from engine.variant import run_field_analysis
    
    print(f"  Running baseline vs {len(field_decks)} opponents ({n_per} games each)...")
    start = time.time()
    result = run_field_analysis(deck, field_decks, field_shares, n_per)
    elapsed = time.time() - start
    
    matchups = {name: round(wr * 100, 1) for name, wr in result.matchup_wrs.items()}
    print(f"  Baseline: {result.field_wr}% field-weighted ({elapsed:.1f}s)")
    for name, wr in sorted(matchups.items(), key=lambda x: x[1]):
        tag = "WEAK" if wr < 45 else "OK  " if wr < 55 else "GOOD"
        print(f"    [{tag}] vs {name}: {wr}%")
    
    return {"field_wr": result.field_wr, "matchups": matchups, "time": elapsed}


def test_swap(deck, card_out, card_in, field_decks, field_shares, n_per=500):
    """Test a single card swap against the field. Returns delta."""
    from engine.variant import _swap_card, run_field_analysis
    
    variant_deck = _swap_card(deck, card_out, card_in)
    
    # Check if swap actually happened (card might not be in deck)
    original_names = [c.name for c in deck]
    variant_names = [c.name for c in variant_deck]
    if original_names == variant_names:
        return {"status": "card_not_found", "card_out": card_out, "delta": 0}
    
    result = run_field_analysis(variant_deck, field_decks, field_shares, n_per)
    
    matchups = {name: round(wr * 100, 1) for name, wr in result.matchup_wrs.items()}
    return {
        "status": "tested",
        "card_out": card_out,
        "card_in": card_in,
        "field_wr": result.field_wr,
        "matchups": matchups,
    }


# ---------------------------------------------------------------------------
# Main Tuning Loop
# ---------------------------------------------------------------------------

def run_tuning_loop(deck_name, format_name="modern", iterations=3,
                    n_per=500, max_field=8, dry_run=False):
    """Run the autonomous tuning loop."""
    print(f"\n{'='*65}")
    print(f"  LAYER 3: AUTONOMOUS TUNING LOOP")
    print(f"  Deck: {deck_name} | Format: {format_name}")
    print(f"  Iterations: {iterations} | Games/matchup: {n_per}")
    print(f"{'='*65}\n")
    
    total_start = time.time()
    
    # Load deck
    from data.deck import load_deck_from_file
    deck_dir = SIM_ROOT / "decks"
    deck_file = None
    for f in deck_dir.glob("*.txt"):
        if deck_name.lower().replace(" ", "_") in f.stem.lower():
            deck_file = f
            break
    if not deck_file:
        print(f"[FAIL] No deck file found for '{deck_name}'")
        return
    
    main_deck, sideboard = load_deck_from_file(str(deck_file))
    decklist_str = "\n".join(f"  {c.name}" for c in main_deck[:20]) + "\n  ..."
    print(f"Loaded: {deck_file.name} ({len(main_deck)} cards)")
    
    # Load field
    print(f"\nLoading {format_name} field...")
    field_decks, field_shares = load_field(format_name, max_field)
    
    # Remove self from field
    self_keys = [k for k in field_decks if deck_name.lower() in k.lower()]
    for k in self_keys:
        del field_decks[k]
        field_shares.pop(k, None)
    # Renormalize
    total_share = sum(field_shares.values()) or 1.0
    field_shares = {k: v / total_share for k, v in field_shares.items()}
    
    print(f"Field: {len(field_decks)} opponents")
    for name, share in sorted(field_shares.items(), key=lambda x: -x[1]):
        print(f"  {name}: {share:.1%}")

    if dry_run:
        print("\n[DRY RUN] Would run baseline + 3 iterations. Exiting.")
        return
    
    # Run baseline
    print(f"\n--- BASELINE ---")
    baseline = run_baseline(main_deck, field_decks, field_shares, n_per)
    
    # Iteration loop with hardened loop control
    all_experiments = []
    experiment_log = ""
    best_field_wr = baseline["field_wr"]
    best_swap = None

    # Loop controller: max 10 iterations, 30 min budget, stop after 3 stalls
    ctrl = LoopController(
        max_steps=min(iterations, 10),
        time_budget=1800,
        stall_limit=3
    )

    for iteration in range(1, iterations + 1):
        if not ctrl.can_continue():
            log.warn(f"Loop stopped: {ctrl.stop_reason}")
            break

        print(f"\n{'='*65}")
        print(f"  ITERATION {iteration}/{iterations}")
        print(f"{'='*65}")
        
        # Ask Gemma for swap suggestions
        print(f"\n[Gemma] Proposing swaps (iteration {iteration})...")
        raw_response = propose_swaps(
            deck_name, decklist_str, baseline, format_name, iteration, experiment_log
        )
        swaps = parse_swaps(raw_response)
        
        if not swaps:
            print(f"[Gemma] No valid swaps parsed. Raw response:")
            print(f"  {raw_response[:300]}")
            continue
        
        print(f"[Gemma] Proposed {len(swaps)} swaps:")
        for s in swaps:
            print(f"  -{s['out']} +{s['in']} ({s['reason']})")
        
        # Validate legality
        valid_swaps = []
        for s in swaps:
            if not check_card_exists(s["in"]):
                print(f"  [ILLEGAL] {s['in']} - card not found in Scryfall DB, skipping")
            elif not check_card_legal(s["in"], format_name):
                print(f"  [ILLEGAL] {s['in']} - not legal in {format_name}, skipping")
            else:
                valid_swaps.append(s)
        
        if not valid_swaps:
            print(f"  All swaps were illegal. Skipping iteration.")
            continue
        
        if len(valid_swaps) < len(swaps):
            print(f"  {len(valid_swaps)}/{len(swaps)} swaps passed legality check")
        
        # Test each valid swap
        for s in valid_swaps:
            print(f"\n  Testing: -{s['out']} +{s['in']}...")
            start = time.time()
            result = test_swap(
                main_deck, s["out"], s["in"],
                field_decks, field_shares, n_per
            )
            elapsed = time.time() - start
            
            if result["status"] == "card_not_found":
                print(f"    SKIP: '{s['out']}' not found in deck")
                experiment = {
                    "iteration": iteration,
                    "out": s["out"], "in": s["in"],
                    "reason": s["reason"],
                    "status": "card_not_found",
                }
            else:
                delta = result["field_wr"] - baseline["field_wr"]
                verdict = "IMPROVED" if delta > 0.5 else "WORSE" if delta < -0.5 else "NEUTRAL"
                
                print(f"    Result: {result['field_wr']}% (delta: {delta:+.1f}%) [{verdict}] ({elapsed:.1f}s)")
                
                # Show per-matchup changes for significant swaps
                if abs(delta) > 0.5:
                    for opp in sorted(result["matchups"].keys()):
                        base_wr = baseline["matchups"].get(opp, 50)
                        var_wr = result["matchups"][opp]
                        mu_delta = var_wr - base_wr
                        if abs(mu_delta) > 1:
                            print(f"      vs {opp}: {base_wr}% -> {var_wr}% ({mu_delta:+.1f}%)")
                
                experiment = {
                    "iteration": iteration,
                    "out": s["out"], "in": s["in"],
                    "reason": s["reason"],
                    "status": verdict.lower(),
                    "base_wr": baseline["field_wr"],
                    "variant_wr": result["field_wr"],
                    "delta": round(delta, 1),
                    "matchups": result["matchups"],
                    "time": round(elapsed, 1),
                }
                
                if delta > 0.5 and result["field_wr"] > best_field_wr:
                    best_field_wr = result["field_wr"]
                    best_swap = experiment
            
            all_experiments.append(experiment)
            experiment_log += f"  Iter{iteration}: -{s['out']} +{s['in']} = {experiment.get('delta', 'N/A')}% ({experiment.get('status', 'skip')})\n"

        # Track loop progress: any improvement this iteration = progress
        iteration_improved = any(
            e.get("status") == "improved" and e.get("iteration") == iteration
            for e in all_experiments
        )
        ctrl.step(progress=iteration_improved)
    
    # Final summary
    total_elapsed = time.time() - total_start
    tested = [e for e in all_experiments if e.get("status") not in ("card_not_found",)]
    improved = [e for e in tested if e.get("status") == "improved"]
    
    print(f"\n{'='*65}")
    print(f"  TUNING LOOP COMPLETE")
    print(f"{'='*65}")
    print(f"  Iterations: {iterations}")
    print(f"  Swaps tested: {len(tested)}")
    print(f"  Improved: {len(improved)}")
    print(f"  Baseline: {baseline['field_wr']}%")
    if best_swap:
        print(f"  Best: -{best_swap['out']} +{best_swap['in']} = {best_swap['variant_wr']}% ({best_swap['delta']:+.1f}%)")
    else:
        print(f"  Best: No improvements found")
    print(f"  Time: {total_elapsed:.0f}s | Cost: $0.00")
    print(f"{'='*65}")
    
    # Write experiment report
    write_experiment_report(deck_name, format_name, baseline, all_experiments,
                            best_swap, total_elapsed)
    
    return {"baseline": baseline, "experiments": all_experiments, "best": best_swap}


# ---------------------------------------------------------------------------
# Knowledge Block Output
# ---------------------------------------------------------------------------

def write_experiment_report(deck_name, format_name, baseline, experiments,
                            best_swap, elapsed):
    """Write tuning experiment results as a knowledge block."""
    safe = deck_name.lower().replace(" ", "-")
    lines = [
        f"---",
        f'title: "Tuning Experiment: {deck_name} ({TODAY})"',
        f'domain: "mtg"',
        f'last_updated: "{TODAY}"',
        f'confidence: "high"',
        f'sources: ["tuning-loop-agent", "mtg-sim-variant-tester"]',
        f"---",
        f"",
        f"## Tuning Experiment: {deck_name}",
        f"Format: {format_name} | Date: {TODAY} | Time: {elapsed:.0f}s | Cost: $0.00",
        f"",
        f"## Baseline",
        f"- Field-weighted win rate: {baseline['field_wr']}%",
        f"",
        f"### Matchups",
    ]
    for opp, wr in sorted(baseline["matchups"].items(), key=lambda x: x[1]):
        lines.append(f"- vs {opp}: {wr}%")
    
    lines.extend(["", "## Experiments"])
    for e in experiments:
        status = e.get("status", "unknown").upper()
        delta = e.get("delta", "N/A")
        delta_str = f"{delta:+.1f}%" if isinstance(delta, (int, float)) else delta
        lines.append(f"- **-{e['out']} +{e['in']}**: {status} ({delta_str})")
        if e.get("reason"):
            lines.append(f"  - Reason: {e['reason']}")
        if e.get("variant_wr"):
            lines.append(f"  - Variant WR: {e['variant_wr']}% (base: {e.get('base_wr', '?')}%)")
    
    if best_swap:
        lines.extend([
            "", "## Best Result",
            f"- Swap: -{best_swap['out']} +{best_swap['in']}",
            f"- Field WR: {best_swap['variant_wr']}% ({best_swap['delta']:+.1f}% vs baseline)",
            f"- Reason: {best_swap.get('reason', 'N/A')}",
            "", "### Matchup Changes",
        ])
        for opp in sorted(best_swap.get("matchups", {}).keys()):
            base_wr = baseline["matchups"].get(opp, 50)
            var_wr = best_swap["matchups"][opp]
            mu_delta = var_wr - base_wr
            if abs(mu_delta) > 0.5:
                lines.append(f"- vs {opp}: {base_wr}% -> {var_wr}% ({mu_delta:+.1f}%)")
    else:
        lines.extend(["", "## Result", "No improvements found in this session."])
    
    lines.extend(["", "## Changelog", f"- {TODAY}: Generated by tuning_loop.py"])
    
    # Write
    path = HARNESS_ROOT / "knowledge" / "mtg" / f"tune-{safe}-{TODAY}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n[harness] Experiment report: {path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Layer 3: Autonomous Tuning Loop")
    parser.add_argument("deck", help="Deck name (e.g. 'Boros Energy')")
    parser.add_argument("--format", default="modern", help="Format")
    parser.add_argument("--iterations", type=int, default=3, help="Tuning iterations")
    parser.add_argument("--games", type=int, default=500, help="Games per matchup")
    parser.add_argument("--field-size", type=int, default=8, help="Max opponents in field")
    parser.add_argument("--dry-run", action="store_true", help="Show plan without running")
    args = parser.parse_args()
    
    run_tuning_loop(args.deck, args.format, args.iterations,
                    args.games, args.field_size, args.dry_run)
