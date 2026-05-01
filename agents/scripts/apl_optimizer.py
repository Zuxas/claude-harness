"""
apl_optimizer.py -- Self-tuning APL optimizer

Reads APL source code + sim results, identifies logic holes,
proposes code fixes, applies them to a copy, tests, and compares.

FLOW:
  1. Run baseline sim (goldfish + matchup)
  2. Read the APL Python source code
  3. Feed sim results + APL code to Gemma
  4. Gemma identifies: sequencing issues, missing interactions,
     mulligan problems, priority gaps
  5. Gemma outputs specific FIND/REPLACE code patches
  6. Apply patches to a copy of the APL
  7. Re-run sim with patched APL
  8. Compare results — keep improvements, revert failures
  9. Write experiment report

USAGE:
  python apl_optimizer.py "Boros Energy" --format modern
  python apl_optimizer.py "Boros Energy" --analyze-only
  python apl_optimizer.py "Boros Energy" --iterations 3
"""

import sys
import os
import json
import time
import re
import shutil
import importlib
import importlib.util
import argparse
from pathlib import Path
from datetime import datetime
from copy import deepcopy

SIM_ROOT = Path("E:/vscode ai project/mtg-sim")
HARNESS_ROOT = Path("E:/vscode ai project/harness")
sys.path.insert(0, str(SIM_ROOT))

import urllib.request
OLLAMA_API = "http://localhost:11434/api/generate"
TODAY = datetime.now().strftime("%Y-%m-%d")

# ---------------------------------------------------------------------------
# AI Backends (Gemma local + Claude API)
# ---------------------------------------------------------------------------

SIM_API_REFERENCE = """SIMULATOR API REFERENCE (use ONLY these functions):

GameState (gs):
  gs.hand() -> list[Card]              # cards in hand
  gs.battlefield() -> list[Card]       # permanents in play
  gs.graveyard() -> list[Card]         # cards in graveyard
  gs.cast_spell(card) -> bool          # cast from hand (pays mana)
  gs.play_land(card) -> bool           # play a land
  gs.tap_lands()                       # tap all lands for mana
  gs.run_combat()                      # attack with all creatures
  gs.has_won(20) -> bool               # check if 20 damage dealt
  gs.vial_in_play()                    # returns Aether Vial or None
  gs.put_via_vial(card, vial)          # put creature via vial
  gs.damage_dealt                      # int, cumulative damage
  gs.energy                            # int, energy counter
  gs.life                              # int, your life total
  gs.turn                              # int, current turn number
  gs.land_played                       # bool, land played this turn
  gs.on_play                           # bool, on the play
  gs.mana_pool.total() -> int          # available mana
  gs.mana_pool.can_cast(cost,cmc) -> bool
  gs.mana_pool.add(color, n)           # add mana
  gs.zones.hand -> list[Card]
  gs.zones.draw(n)                     # draw n cards
  gs.zones.hand_size() -> int
  gs.zones.lands_in_hand() -> list
  gs.zones.nonlands_in_hand() -> list
  gs.zones.lands_on_battlefield() -> list
  gs.zones.creatures_on_battlefield() -> list
  gs.zones.count_lands_in_play() -> int
  gs.zones.play_from_hand(card)        # move card hand->battlefield
  gs.zones.remove_from_hand(card)
  gs.zones.destroy(card)               # permanent -> graveyard
  gs._make_token(name, power, toughness, type_line) -> Card
  gs._log(msg)                         # log a message

Card attributes:
  card.name, card.cmc, card.mana_cost, card.type_line, card.oracle_text
  card.power, card.toughness, card.effective_power(), card.effective_toughness()
  card.tapped, card.summoning_sickness, card.counters, card.turn_entered
  card.has(Tag.HASTE), card.is_land(), card.is_castable(gs)

Tags: Tag.HASTE, Tag.FLYING, Tag.LIFELINK, Tag.FIRST_STRIKE, Tag.PROWESS,
      Tag.TOKEN, Tag.CREATURE, Tag.ENCHANTMENT, Tag.ARTIFACT, Tag.PLANESWALKER

GOLDFISH RULES: No opponent interaction, no blocking. Focus on advancing the damage clock."""


def _get_claude_token():
    """Get Anthropic API token from Claude Code credentials."""
    import os as _os
    key = _os.environ.get("ANTHROPIC_API_KEY", "")
    if key:
        return key
    creds_path = Path.home() / ".claude" / ".credentials.json"
    if creds_path.exists():
        try:
            import time as _time
            creds = json.loads(creds_path.read_text(encoding="utf-8"))
            oauth = creds.get("claudeAiOauth", {})
            token = oauth.get("accessToken", "")
            expires = oauth.get("expiresAt", 0)
            if token and expires > (_time.time() * 1000 + 300_000):
                return token
        except Exception:
            pass
    env_file = SIM_ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("ANTHROPIC_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"')
    return None


def call_claude_api(prompt, model="claude-sonnet-4-20250514"):
    """Call Claude API for high-quality code generation."""
    token = _get_claude_token()
    if not token:
        log("  [WARN] No Claude API token found, falling back to Gemma")
        return ask_gemma(prompt)
    
    if token.startswith("sk-ant-oat") or token.startswith("Bearer "):
        auth = {"Authorization": f"Bearer {token.lstrip('Bearer ')}"}
    else:
        auth = {"x-api-key": token}
    
    from apl_cookbook import APL_COOKBOOK
    payload = json.dumps({
        "model": model, "max_tokens": 4000,
        "system": "You are an expert MTG simulator engineer. Write precise Python code.\n\n" + APL_COOKBOOK,
        "messages": [{"role": "user", "content": prompt}]
    }).encode("utf-8")
    
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={"Content-Type": "application/json", "anthropic-version": "2023-06-01", **auth},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read())
            return data["content"][0]["text"]
    except Exception as e:
        log(f"  [WARN] Claude API failed ({e}), falling back to Gemma")
        return ask_gemma(prompt)

def log(msg):
    # Sanitize unicode for Windows console
    safe = str(msg).encode("ascii", errors="replace").decode("ascii")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {safe}")

def ask_gemma(prompt, model="gemma4", max_tokens=4096):
    from apl_cookbook import APL_COOKBOOK
    body = json.dumps({
        "model": model, "prompt": prompt,
        "system": "You are an expert MTG simulator engineer. Write precise Python code.\n\n" + APL_COOKBOOK,
        "stream": False,
        "options": {"temperature": 0.2, "num_predict": max_tokens}
    }).encode()
    try:
        req = urllib.request.Request(OLLAMA_API, data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=300) as resp:
            return json.loads(resp.read()).get("response", "")
    except Exception as e:
        return f"ERROR: {e}"


# ---------------------------------------------------------------------------
# APL Discovery + Loading
# ---------------------------------------------------------------------------

def find_apl_file(deck_name, format_name="modern"):
    """Find the APL Python file for a deck, checking format-specific first."""
    apl_dir = SIM_ROOT / "apl"
    safe = deck_name.lower().replace(" ", "_").replace("-", "_")

    # 1. Format-specific match APL (e.g., gruul_aggro_standard_match.py)
    fmt_match = apl_dir / f"{safe}_{format_name}_match.py"
    if fmt_match.exists():
        return fmt_match

    # 2. Generic match APL (e.g., gruul_aggro_match.py)
    gen_match = apl_dir / f"{safe}_match.py"
    if gen_match.exists():
        return gen_match

    # 3. Base APL (e.g., gruul_aggro.py)
    base = apl_dir / f"{safe}.py"
    if base.exists():
        return base

    # 4. Fuzzy match
    for f in apl_dir.glob("*.py"):
        if safe in f.stem.lower():
            return f
    return None


def find_deck_file(deck_name):
    """Find the deck list file."""
    deck_dir = SIM_ROOT / "decks"
    safe = deck_name.lower().replace(" ", "_")
    for f in deck_dir.glob("*.txt"):
        if safe in f.stem.lower():
            return f
    return None


def load_apl_from_file(apl_path):
    """Dynamically load an APL class from a Python file."""
    spec = importlib.util.spec_from_file_location("temp_apl", str(apl_path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    
    # Find the APL class (subclass of BaseAPL or has main_phase method)
    for name in dir(module):
        obj = getattr(module, name)
        if isinstance(obj, type) and name.endswith("APL") and name != "BaseAPL":
            return obj()
    return None


# ---------------------------------------------------------------------------
# Sim Runner
# ---------------------------------------------------------------------------

def run_goldfish(apl, deck, n=500):
    """Run goldfish sim and return results dict."""
    from engine.runner import run_simulation
    start = time.time()
    results = run_simulation(apl, deck, n=n, on_play=True)
    elapsed = time.time() - start
    return {
        "win_rate": results.win_rate(),
        "avg_kill": results.avg_kill_turn(),
        "median_kill": results.median_kill_turn(),
        "fastest": min(results.kill_turns) if results.kill_turns else 0,
        "kill_dist": results.kill_turn_distribution(),
        "time": round(elapsed, 1),
        "games": n,
    }


# ---------------------------------------------------------------------------
# APL Analysis — the brain
# ---------------------------------------------------------------------------

def find_missing_cards(deck_file, apl_source):
    """Compare deck list vs APL source to find unmodeled cards."""
    deck_cards = []
    for line in deck_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and line[0].isdigit() and not line.lower().startswith("sideboard"):
            parts = line.split(" ", 1)
            if len(parts) == 2:
                name = parts[1].strip()
                count = int(parts[0])
                # Check if card is referenced in APL
                apl_lower = apl_source.lower()
                mentioned = (name.lower() in apl_lower or 
                            name.split(",")[0].lower() in apl_lower)
                if not mentioned:
                    deck_cards.append({"name": name, "count": count, "status": "MISSING"})
    return deck_cards


def analyze_apl(deck_name, apl_source, sim_results, missing_cards=None, use_claude=False, model="gemma4"):
    """Feed APL source + sim results to AI and get analysis."""
    prompt = f"""Analyze this MTG simulator APL (Action Priority List) for the deck "{deck_name}".

SIM RESULTS:
- Win Rate: {sim_results['win_rate']:.1%}
- Avg Kill Turn: {sim_results['avg_kill']:.2f}
- Median Kill: {sim_results['median_kill']:.1f}
- Fastest Kill: T{sim_results['fastest']}
- Kill Distribution: {sim_results.get('kill_dist', 'N/A')}
"""
    if missing_cards:
        prompt += "\nMISSING CARDS (in deck but NOT modeled in APL):\n"
        for mc in missing_cards:
            prompt += f"  - {mc['name']} x{mc['count']} -- NO LOGIC IN APL\n"
        prompt += "\nThese cards are being treated as generic creatures/spells with no special abilities.\n"

    prompt += f"""
APL SOURCE CODE:
```python
{apl_source}
```

Analyze the APL and identify exactly 3 specific code-level improvements.
Focus on these priorities (in order):
1. MISSING CARDS: Write NEW code for cards in the deck that have NO logic in the APL.
   These cards are being played as generic vanilla creatures. Add their real abilities.
2. SEQUENCING: Are cards being played in the wrong order?
3. MULLIGAN: Are the keep/mulligan criteria too loose or too strict?
4. PRIORITY BUGS: Is the main_phase priority list suboptimal?

For EACH improvement, output in this EXACT format:

ISSUE: one-line description
IMPACT: high/medium/low
TYPE: INSERT or REPLACE
AFTER:
<exact Python code line to insert AFTER - copy from source above>
CODE:
<new Python code to insert or replace with>
END_PATCH

Rules for INSERT:
- AFTER must be an EXACT line from the APL source
- CODE is the new block to insert right after that line
- Use this to add NEW card logic that is completely missing

Rules for REPLACE (use TYPE: REPLACE):
- Put the old code in AFTER: field  
- Put the new code in CODE: field
- AFTER must be an EXACT substring from the APL source

Focus on writing NEW code for missing cards first. Each patch must be independent.
"""
    if use_claude:
        return call_claude_api(prompt)
    return ask_gemma(prompt, model=model, max_tokens=4096)


def parse_patches(response):
    """Parse Gemma's patch suggestions into structured data."""
    patches = []
    current = None
    mode = None
    buffer = []
    
    for line in response.split("\n"):
        if line.startswith("ISSUE:"):
            if current and current.get("after") and current.get("code"):
                patches.append(current)
            current = {"issue": line[6:].strip(), "impact": "", "type": "replace",
                       "after": "", "code": ""}
            mode = None
            buffer = []
        elif line.startswith("IMPACT:"):
            if current:
                current["impact"] = line[7:].strip()
        elif line.startswith("TYPE:"):
            if current:
                current["type"] = line[5:].strip().lower()
        elif line.startswith("AFTER:"):
            mode = "after"
            buffer = []
        elif line.startswith("CODE:"):
            if current and mode == "after":
                current["after"] = "\n".join(buffer)
            mode = "code"
            buffer = []
        elif line.startswith("FIND:"):
            mode = "after"  # treat FIND as AFTER for backwards compat
            buffer = []
        elif line.startswith("REPLACE:"):
            if current and mode == "after":
                current["after"] = "\n".join(buffer)
            mode = "code"
            buffer = []
        elif line.strip() == "END_PATCH":
            if current and mode == "code":
                current["code"] = "\n".join(buffer)
            mode = None
            buffer = []
        elif mode in ("after", "code"):
            if line.strip() in ("```python", "```"):
                continue
            buffer.append(line)
    
    if current and current.get("after") and mode == "code":
        current["code"] = "\n".join(buffer)
    if current and current.get("after") and current.get("code"):
        patches.append(current)
    
    return patches


def apply_patch(apl_source, patch):
    """Apply a patch (INSERT or REPLACE) to APL source with auto-indentation."""
    after_text = patch["after"].strip()
    code_text = patch["code"]
    patch_type = patch.get("type", "replace")
    
    if not after_text:
        return None
    
    # Find the AFTER text in source
    source_lines = apl_source.splitlines()
    match_line_idx = None
    
    # Try exact match first
    if after_text in apl_source:
        # Find which line it's on
        for i, line in enumerate(source_lines):
            if after_text in line or (len(after_text.splitlines()) > 1 and 
                after_text.splitlines()[0].strip() in line):
                match_line_idx = i
                break
    
    # Try single-line fuzzy match
    if match_line_idx is None:
        after_first = after_text.splitlines()[0].strip() if after_text else ""
        for i, line in enumerate(source_lines):
            if after_first and after_first in line.strip():
                match_line_idx = i
                break
    
    if match_line_idx is None:
        return None
    
    # Detect indentation of the matched line
    matched_line = source_lines[match_line_idx]
    base_indent = len(matched_line) - len(matched_line.lstrip())
    indent_str = matched_line[:base_indent]
    
    # Auto-indent the new code to match the insertion point
    code_lines = code_text.splitlines()
    indented_code_lines = []
    for cl in code_lines:
        stripped = cl.lstrip()
        if not stripped:
            indented_code_lines.append("")
            continue
        # Detect how much indent the code already has
        original_indent = len(cl) - len(stripped)
        # Re-indent relative to the base indentation
        indented_code_lines.append(indent_str + "    " * (original_indent // 4) + stripped)
    
    reindented_code = "\n".join(indented_code_lines)
    
    if patch_type == "insert":
        # For multi-line AFTER text, find the last line of the match
        after_lines = after_text.strip().splitlines()
        if len(after_lines) > 1:
            # Find end of multi-line match
            end_idx = match_line_idx + len(after_lines) - 1
            source_lines.insert(end_idx + 1, reindented_code)
        else:
            source_lines.insert(match_line_idx + 1, reindented_code)
        return "\n".join(source_lines)
    else:
        # REPLACE: replace the matched line(s) with new code
        after_lines = after_text.strip().splitlines()
        end_idx = match_line_idx + len(after_lines)
        source_lines[match_line_idx:end_idx] = reindented_code.splitlines()
        return "\n".join(source_lines)


# ---------------------------------------------------------------------------
# Main Pipeline
# ---------------------------------------------------------------------------

def run_optimizer(deck_name, format_name="modern", n_games=500,
                  iterations=2, analyze_only=False, use_claude=False, model="gemma4"):
    log(f"")
    log(f"{'='*65}")
    log(f"  APL SELF-TUNER ({model})")
    log(f"  Deck: {deck_name} | Format: {format_name}")
    log(f"  Games: {n_games} | Iterations: {iterations}")
    log(f"{'='*65}")
    
    total_start = time.time()
    
    # Find APL + deck files
    apl_file = find_apl_file(deck_name, format_name)
    deck_file = find_deck_file(deck_name)
    
    if not apl_file:
        log(f"[FAIL] No APL file found for '{deck_name}'")
        return
    if not deck_file:
        log(f"[FAIL] No deck file found for '{deck_name}'")
        return
    
    log(f"APL: {apl_file.name}")
    log(f"Deck: {deck_file.name}")
    
    # Load deck
    from data.deck import load_deck_from_file
    mainboard, sideboard = load_deck_from_file(str(deck_file))
    log(f"Loaded: {len(mainboard)} cards")
    
    # Read APL source
    apl_source = apl_file.read_text(encoding="utf-8")
    log(f"APL source: {len(apl_source)} chars, {len(apl_source.splitlines())} lines")
    
    # Find missing cards
    missing = find_missing_cards(deck_file, apl_source)
    mainboard_missing = [m for m in missing if m["count"] > 0]
    if mainboard_missing:
        log(f"\nMISSING CARD LOGIC ({len(mainboard_missing)} cards in deck but not modeled):")
        for m in mainboard_missing:
            log(f"  [{m['status']}] {m['name']} x{m['count']}")
    else:
        log(f"All mainboard cards are modeled in the APL.")
    
    # Load original APL
    original_apl = load_apl_from_file(apl_file)
    if not original_apl:
        log(f"[FAIL] Could not load APL class from {apl_file.name}")
        return
    log(f"APL class: {type(original_apl).__name__}")
    
    # Run baseline
    log(f"\n--- BASELINE ---")
    baseline = run_goldfish(original_apl, mainboard, n_games)
    log(f"  Win rate: {baseline['win_rate']:.1%}")
    log(f"  Avg kill: {baseline['avg_kill']:.2f}")
    log(f"  Fastest: T{baseline['fastest']}")
    log(f"  Speed: {baseline['games'] / baseline['time']:.0f} g/s")
    
    all_results = []
    current_source = apl_source
    best_kill = baseline["avg_kill"]
    best_patch = None
    
    for iteration in range(1, iterations + 1):
        log(f"\n{'='*65}")
        log(f"  ITERATION {iteration}/{iterations}")
        log(f"{'='*65}")
        
        # Analyze APL
        log(f"\n[{model}] Analyzing APL source code...")
        analysis = analyze_apl(deck_name, current_source, baseline, mainboard_missing, use_claude, model)
        
        # Parse patches
        patches = parse_patches(analysis)
        log(f"[Gemma] Found {len(patches)} patches:")
        for i, p in enumerate(patches):
            ptype = p.get("type", "replace").upper()
            log(f"  [{i+1}] [{ptype}] {p['issue']} [{p['impact']}]")
        
        if not patches:
            log(f"  No valid patches parsed. Raw analysis:")
            log(f"  {analysis[:500]}")
            all_results.append({"iteration": iteration, "status": "no_patches",
                               "analysis": analysis[:1000]})
            continue
        
        if analyze_only:
            log(f"\n  [ANALYZE ONLY] Patches not applied.")
            all_results.append({"iteration": iteration, "status": "analyze_only",
                               "patches": patches, "analysis": analysis[:2000]})
            continue
        
        # Test each patch independently
        for i, patch in enumerate(patches):
            log(f"\n  Testing patch [{i+1}]: {patch['issue']}")
            
            patched_source = apply_patch(current_source, patch)
            if patched_source is None:
                log(f"    SKIP: FIND text not found in APL source")
                all_results.append({"iteration": iteration, "patch": i+1,
                                   "issue": patch["issue"], "status": "not_found"})
                continue
            
            # Write patched APL to temp file
            temp_dir = HARNESS_ROOT / "agents" / "temp"
            temp_dir.mkdir(exist_ok=True)
            temp_apl_file = temp_dir / f"patched_apl_{iteration}_{i}.py"
            temp_apl_file.write_text(patched_source, encoding="utf-8")
            
            # Try to load patched APL
            try:
                patched_apl = load_apl_from_file(temp_apl_file)
                if not patched_apl:
                    log(f"    FAIL: Could not load patched APL class")
                    all_results.append({"iteration": iteration, "patch": i+1,
                                       "issue": patch["issue"], "status": "load_fail"})
                    continue
            except Exception as e:
                log(f"    FAIL: Syntax error in patch: {str(e)[:100]}")
                all_results.append({"iteration": iteration, "patch": i+1,
                                   "issue": patch["issue"], "status": "syntax_error",
                                   "error": str(e)[:200]})
                continue
            
            # Run sim with patched APL
            try:
                patched_results = run_goldfish(patched_apl, mainboard, n_games)
            except Exception as e:
                log(f"    FAIL: Sim crashed with patch: {str(e)[:100]}")
                all_results.append({"iteration": iteration, "patch": i+1,
                                   "issue": patch["issue"], "status": "sim_crash",
                                   "error": str(e)[:200]})
                continue
            
            delta_kill = baseline["avg_kill"] - patched_results["avg_kill"]
            delta_wr = patched_results["win_rate"] - baseline["win_rate"]
            
            verdict = "IMPROVED" if delta_kill > 0.05 else "WORSE" if delta_kill < -0.05 else "NEUTRAL"
            log(f"    Kill: {baseline['avg_kill']:.2f} -> {patched_results['avg_kill']:.2f} ({delta_kill:+.2f} turns)")
            log(f"    WR: {baseline['win_rate']:.1%} -> {patched_results['win_rate']:.1%} ({delta_wr:+.1%})")
            log(f"    [{verdict}]")
            
            result = {
                "iteration": iteration, "patch": i+1,
                "issue": patch["issue"], "impact": patch["impact"],
                "status": verdict.lower(),
                "baseline_kill": round(baseline["avg_kill"], 2),
                "patched_kill": round(patched_results["avg_kill"], 2),
                "delta_kill": round(delta_kill, 2),
                "baseline_wr": round(baseline["win_rate"], 3),
                "patched_wr": round(patched_results["win_rate"], 3),
            }
            all_results.append(result)
            
            if delta_kill > 0.05 and patched_results["avg_kill"] < best_kill:
                best_kill = patched_results["avg_kill"]
                best_patch = {"patch": patch, "results": patched_results,
                              "file": str(temp_apl_file)}
            
            # Clean up temp file
            temp_apl_file.unlink(missing_ok=True)
    
    # Summary
    elapsed = time.time() - total_start
    tested = [r for r in all_results if r.get("status") in ("improved","neutral","worse")]
    improved = [r for r in tested if r["status"] == "improved"]
    
    log(f"\n{'='*65}")
    log(f"  APL SELF-TUNER COMPLETE")
    log(f"{'='*65}")
    log(f"  Baseline: T{baseline['avg_kill']:.2f} avg kill, {baseline['win_rate']:.1%} WR")
    log(f"  Patches tested: {len(tested)}")
    log(f"  Improved: {len(improved)}")
    if best_patch:
        bp = best_patch
        log(f"  Best: {bp['patch']['issue']}")
        log(f"    Kill: T{baseline['avg_kill']:.2f} -> T{bp['results']['avg_kill']:.2f} "
            f"({baseline['avg_kill'] - bp['results']['avg_kill']:+.2f} turns)")
    else:
        log(f"  Best: No improvements found")
    log(f"  Time: {elapsed:.0f}s | Cost: $0.00")
    log(f"{'='*65}")
    
    # Write report
    write_report(deck_name, format_name, baseline, all_results, best_patch, elapsed)


def write_report(deck_name, format_name, baseline, results, best_patch, elapsed):
    """Write APL optimization report to knowledge base."""
    safe = deck_name.lower().replace(" ", "-")
    lines = [
        "---", f'title: "APL Optimization: {deck_name} ({TODAY})"',
        f'domain: "mtg"', f'last_updated: "{TODAY}"',
        f'confidence: "high"',
        f'sources: ["apl-optimizer", "mtg-sim"]', "---", "",
        f"## APL Self-Tuning: {deck_name}", "",
        f"### Baseline",
        f"- Kill turn: {baseline['avg_kill']:.2f}",
        f"- Win rate: {baseline['win_rate']:.1%}",
        f"- Fastest: T{baseline['fastest']}", "",
        f"### Patches Tested",
    ]
    for r in results:
        status = r.get("status", "unknown").upper()
        issue = r.get("issue", "N/A")
        if r.get("delta_kill") is not None:
            lines.append(f"- [{status}] {issue} (kill delta: {r['delta_kill']:+.2f} turns)")
        else:
            lines.append(f"- [{status}] {issue}")
    
    if best_patch:
        bp = best_patch
        ptype = bp['patch'].get('type', 'replace').upper()
        lines.extend(["", "### Best Improvement",
            f"- Issue: {bp['patch']['issue']}",
            f"- Type: {ptype}",
            f"- Kill: {baseline['avg_kill']:.2f} -> {bp['results']['avg_kill']:.2f}",
            f"- Code change:", "```python",
            f"# {ptype} AFTER:", bp['patch']['after'][:300],
            f"# NEW CODE:", bp['patch']['code'][:300],
            "```"])
    
    lines.extend(["", f"Time: {elapsed:.0f}s | Cost: $0.00", "",
                  "## Changelog", f"- {TODAY}: Generated by apl_optimizer.py"])
    
    path = HARNESS_ROOT / "knowledge" / "mtg" / f"apl-opt-{safe}-{TODAY}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    log(f"\n[harness] Report: {path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="APL Self-Tuner")
    parser.add_argument("deck", help="Deck name")
    parser.add_argument("--format", default="modern")
    parser.add_argument("--games", type=int, default=500)
    parser.add_argument("--iterations", type=int, default=2)
    parser.add_argument("--analyze-only", action="store_true",
                        help="Show analysis without testing patches")
    parser.add_argument("--use-claude", action="store_true",
                        help="Use Claude API for code generation")
    parser.add_argument("--model", default="gemma4",
                        help="Ollama model to use (gemma4, qwen3-coder:30b, deepseek-v3.1:671b-cloud, etc.)")
    args = parser.parse_args()
    
    run_optimizer(args.deck, args.format, args.games, args.iterations,
                  args.analyze_only, args.use_claude, args.model)
