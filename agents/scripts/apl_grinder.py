"""
apl_grinder.py -- Iterative APL refinement via method rewriting

Reads game logs, compares fast vs slow games, rewrites specific methods
until the target kill turn is met.

USAGE:
  python apl_grinder.py "Amulet Titan" --target 5.5 --max-iterations 5
  python apl_grinder.py "Boros Energy" --target 4.5
  python apl_grinder.py "Amulet Titan" --analyze-logs
"""

import sys, os, json, time, re, importlib.util, argparse
from pathlib import Path
from datetime import datetime

SIM_ROOT = Path("E:/vscode ai project/mtg-sim")
HARNESS_ROOT = Path("E:/vscode ai project/harness")
RULES_FILE = HARNESS_ROOT / "knowledge" / "rules" / "mtg-rules-engine.md"
sys.path.insert(0, str(SIM_ROOT))
sys.path.insert(0, str(HARNESS_ROOT / "agents" / "scripts"))

import urllib.request
OLLAMA_API = "http://localhost:11434/api/generate"
TODAY = datetime.now().strftime("%Y-%m-%d")

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

# ---------------------------------------------------------------------------
# AI Backend — Gemma (free) or GPT-4o (better code, ~$0.02/call)
# ---------------------------------------------------------------------------

# Active model — set by CLI flag
_AI_MODEL = "gemma4"  # default — 12B is faster and more reliable

def _get_system_prompt():
    from apl_cookbook import APL_COOKBOOK
    # Trim rules to essential parts only — full rules overwhelm smaller models
    rules = ""
    if RULES_FILE.exists():
        full = RULES_FILE.read_text(encoding="utf-8")
        # Only include sections 1 (turn structure) and 8 (common bugs)
        for section in ["## 1. TURN STRUCTURE", "## 8. GENERAL TRUTHS"]:
            idx = full.find(section)
            if idx >= 0:
                end = full.find("\n## ", idx + 10)
                rules += full[idx:end if end > 0 else idx+2000] + "\n\n"
    return (
        "You are an expert MTG simulator engineer. Output ONLY Python code.\n\n"
        + APL_COOKBOOK + "\n\n" + rules
    )

def ask_ai(prompt, max_tokens=4096):
    """Route to the active AI model."""
    if _AI_MODEL.startswith("gpt"):
        return _call_openai(prompt, max_tokens)
    elif _AI_MODEL.startswith("gemini"):
        return _call_gemini(prompt, max_tokens)
    else:
        return _call_ollama(prompt, max_tokens)

def _call_ollama(prompt, max_tokens=4096):
    system = _get_system_prompt()
    body = json.dumps({
        "model": _AI_MODEL, "prompt": prompt, "system": system,
        "stream": False, "options": {"temperature": 0.2, "num_predict": max_tokens}
    }).encode()
    try:
        req = urllib.request.Request(OLLAMA_API, data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=600) as resp:
            return json.loads(resp.read()).get("response", "")
    except Exception as e:
        return f"ERROR: {e}"

def _call_openai(prompt, max_tokens=4096):
    key = os.environ.get("OPENAI_API_KEY", "")
    if not key:
        log("  [WARN] No OPENAI_API_KEY, falling back to Gemma")
        return _call_ollama(prompt, max_tokens)
    system = _get_system_prompt()
    body = json.dumps({
        "model": "gpt-4o",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": max_tokens, "temperature": 0.2
    }).encode()
    try:
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=body,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
            return data["choices"][0]["message"]["content"]
    except Exception as e:
        log(f"  [WARN] OpenAI failed ({e}), falling back to Gemma")
        return _call_ollama(prompt, max_tokens)

def _call_gemini(prompt, max_tokens=4096):
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        log("  [WARN] No GEMINI_API_KEY, falling back to Gemma")
        return _call_ollama(prompt, max_tokens)
    system = _get_system_prompt()
    body = json.dumps({
        "contents": [{"parts": [{"text": system + "\n\n" + prompt}]}],
        "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.2}
    }).encode()
    try:
        req = urllib.request.Request(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key}",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
            return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        log(f"  [WARN] Gemini failed ({e}), falling back to Gemma")
        return _call_ollama(prompt, max_tokens)


# ---------------------------------------------------------------------------
# Sim — with logs (baseline) and fast parallel (testing)
# ---------------------------------------------------------------------------

def run_sim_with_logs(apl, deck, n=200):
    """Single-threaded sim with game logs for analysis."""
    from engine.runner import run_simulation
    start = time.time()
    results = run_simulation(apl, deck, n=n, on_play=True, store_logs=True)
    elapsed = time.time() - start
    
    games = []
    for gr in results.game_logs:
        lines = [f"Hand: {gr.opening_hand}", f"Mulls: {gr.mulligans}"]
        for snap in gr.turn_snapshots:
            t = snap.get("turn", "?")
            lines.append(
                f"T{t}: {snap.get('damage_dealt',0)}dmg "
                f"{snap.get('lands_in_play',0)}lands "
                f"{snap.get('creatures_in_play',0)}creatures(pow={snap.get('total_power',0)}) "
                f"{snap.get('hand_size',0)}cards"
            )
        games.append({"kill_turn": gr.kill_turn, "log": "\n".join(lines),
                       "hand": gr.opening_hand, "mulls": gr.mulligans})
    
    return {
        "avg_kill": results.avg_kill_turn(),
        "fastest": min(results.kill_turns) if results.kill_turns else 99,
        "win_rate": results.win_rate(),
        "dist": results.kill_turn_distribution(),
        "games": games, "time": round(elapsed, 1),
    }


def run_sim_fast(apl, deck, n=200):
    """Parallel sim for quick testing — no game logs, uses all CPU cores."""
    try:
        from engine.runner import run_simulation_parallel
        start = time.time()
        results = run_simulation_parallel(apl, deck, n=n, on_play=True)
        elapsed = time.time() - start
    except Exception:
        # Fallback to single-threaded
        from engine.runner import run_simulation
        start = time.time()
        results = run_simulation(apl, deck, n=n, on_play=True)
        elapsed = time.time() - start
    
    return {
        "avg_kill": results.avg_kill_turn(),
        "fastest": min(results.kill_turns) if results.kill_turns else 99,
        "win_rate": results.win_rate(),
        "dist": results.kill_turn_distribution(),
        "games": [], "time": round(elapsed, 1),
    }


# ---------------------------------------------------------------------------
# Method Extraction — pull a single method from APL source
# ---------------------------------------------------------------------------

def extract_method(source, method_name):
    """Extract a method from Python source by name. Returns (code, start_line, end_line)."""
    lines = source.splitlines()
    start = None
    indent = None
    for i, line in enumerate(lines):
        if f"def {method_name}(" in line or f"def {method_name} (" in line:
            start = i
            indent = len(line) - len(line.lstrip())
            break
    if start is None:
        return None, 0, 0
    
    end = start + 1
    while end < len(lines):
        line = lines[end]
        # Next method at same or lower indent = end of this method
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and not stripped.startswith("\"\"\""):
            line_indent = len(line) - len(line.lstrip())
            if line_indent <= indent and stripped.startswith("def "):
                break
        end += 1
    
    return "\n".join(lines[start:end]), start, end


def replace_method(source, method_name, new_code):
    """Replace a method in APL source with new code, auto-fixing indentation."""
    lines = source.splitlines()
    _, start, end = extract_method(source, method_name)
    if start is None:
        return None
    
    # Detect original indentation
    original_indent = len(lines[start]) - len(lines[start].lstrip())
    
    # Detect new code indentation
    new_lines_raw = new_code.splitlines()
    new_indent = 0
    for nl in new_lines_raw:
        if nl.strip():
            new_indent = len(nl) - len(nl.lstrip())
            break
    
    # Re-indent new code to match original
    if new_indent != original_indent:
        delta = original_indent - new_indent
        reindented = []
        for nl in new_lines_raw:
            if not nl.strip():
                reindented.append("")
            elif delta > 0:
                reindented.append(" " * delta + nl)
            else:
                # Remove indent
                stripped = nl[min(abs(delta), len(nl) - len(nl.lstrip())):]
                reindented.append(stripped)
        new_lines_raw = reindented
    
    result = lines[:start] + new_lines_raw + lines[end:]
    return "\n".join(result)


# ---------------------------------------------------------------------------
# Bottleneck Detection — which method to rewrite
# ---------------------------------------------------------------------------

def find_bottleneck(fast_games, slow_games, source, tried_methods=None):
    """Identify bottleneck method. Cycles through candidates after failures.
    After 3 consecutive failures on a method, moves to next candidate."""
    if tried_methods is None:
        tried_methods = {}
    
    candidates = []
    for method in ["_land_play_value", "_play_land", "_try_cast_grazer",
                   "_try_cast_spelunking", "_try_cast_amulet", "keep",
                   "_try_cast_rumble", "_apply_bounce_return",
                   "_resolve_land_etb", "main_phase2", "bottom"]:
        code, s, e = extract_method(source, method)
        if code and 15 <= (e - s) <= 100:
            fails = tried_methods.get(method, 0)
            if fails >= 3:  # skip methods with 3+ consecutive failures
                continue
            candidates.append((method, e - s, fails))
    
    if not candidates:
        # All methods exhausted — reset and try again
        tried_methods.clear()
        return "_land_play_value"
    
    # Sort by fewest failures first, then smaller methods first
    candidates.sort(key=lambda x: (x[2], x[1]))
    return candidates[0][0]


# ---------------------------------------------------------------------------
# Method Rewrite Request — ask Gemma to rewrite one method
# ---------------------------------------------------------------------------

def ask_for_rewrite(method_name, method_code, fast_games, slow_games,
                    sim_data, deck_name, prior_log=""):
    fast_text = ""
    for g in fast_games[:3]:
        fast_text += f"\n--- FAST (T{g['kill_turn']}) ---\n{g['log']}\n"
    slow_text = ""
    for g in slow_games[:3]:
        slow_text += f"\n--- SLOW (T{g['kill_turn']}) ---\n{g['log']}\n"
    
    prompt = f"""Deck: {deck_name} | Avg kill: T{sim_data['avg_kill']:.2f} | Target: FASTER

FAST GAMES (good):
{fast_text}

SLOW GAMES (bad):
{slow_text}

The bottleneck method is `{method_name}`. Here is the CURRENT code:

```python
{method_code}
```

{f"Previous attempts:{chr(10)}{prior_log}" if prior_log else ""}

Rewrite `{method_name}` to make slow games play more like fast games.
Key differences to fix:
- Fast games develop more lands by T2-T3
- Fast games have higher power by T3-T4
- Slow games waste land drops or play lands in wrong order

RULES:
- Output ONLY the complete rewritten method starting with `    def {method_name}(`
- This method is INSIDE A CLASS. Use 4-space indent for the def line, 8-space for body.
- Keep the same method signature (same parameters as the original)
- Use only the sim API from the cookbook
- No imports inside the method
- No markdown fences, no explanation, ONLY Python code
"""
    return ask_ai(prompt, max_tokens=4096)


# ---------------------------------------------------------------------------
# APL Loading
# ---------------------------------------------------------------------------

def load_apl_from_file(path):
    spec = importlib.util.spec_from_file_location("temp_apl", str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name in dir(module):
        obj = getattr(module, name)
        if isinstance(obj, type) and name.endswith("APL") and name != "BaseAPL":
            return obj()
    return None

def find_files(deck_name):
    apl_dir = SIM_ROOT / "apl"
    deck_dir = SIM_ROOT / "decks"
    safe = deck_name.lower().replace(" ", "_").replace("-", "_")
    apl_file = deck_file = None
    for f in apl_dir.glob("*.py"):
        if safe in f.stem.lower():
            apl_file = f; break
    for f in deck_dir.glob("*.txt"):
        if safe in f.stem.lower():
            deck_file = f; break
    return apl_file, deck_file


# ---------------------------------------------------------------------------
# THE GRINDER
# ---------------------------------------------------------------------------

def run_grinder(deck_name, target_kill=5.0, max_iters=10, n_games=200,
                analyze_only=False, stop_time=None):
    stop_label = f"Until: {stop_time.strftime('%I:%M %p')}" if stop_time else f"MaxIter: {max_iters}"
    log(f"")
    log(f"{'='*65}")
    log(f"  APL GRINDER")
    log(f"  Deck: {deck_name} | Target: T{target_kill}")
    log(f"  {stop_label} | Games: {n_games} | Model: {_AI_MODEL}")
    log(f"{'='*65}")
    
    apl_file, deck_file = find_files(deck_name)
    if not apl_file or not deck_file:
        log(f"[FAIL] Missing files for '{deck_name}'"); return
    
    from data.deck import load_deck_from_file
    mainboard, _ = load_deck_from_file(str(deck_file))
    current_source = apl_file.read_text(encoding="utf-8")
    original_source = current_source
    log(f"APL: {apl_file.name} ({len(current_source.splitlines())} lines)")
    
    # Baseline
    log(f"\n--- BASELINE ---")
    apl = load_apl_from_file(apl_file)
    baseline = run_sim_with_logs(apl, mainboard, n_games)
    current_avg = baseline["avg_kill"]
    log(f"  Avg kill: T{current_avg:.2f} | Fastest: T{baseline['fastest']}")
    for t, pct in sorted(baseline["dist"].items()):
        if pct > 0:
            log(f"    T{t}: {pct:5.1f}% {'#'*int(pct)}")
    
    if current_avg <= target_kill:
        log(f"  Already at target!"); return
    
    # Separate fast vs slow
    fast = sorted([g for g in baseline["games"] if g["kill_turn"] <= int(target_kill)],
                  key=lambda g: g["kill_turn"])
    slow = sorted([g for g in baseline["games"] if g["kill_turn"] > int(current_avg) + 1],
                  key=lambda g: -g["kill_turn"])
    log(f"\n  Fast (<= T{int(target_kill)}): {len(fast)}/{len(baseline['games'])}")
    log(f"  Slow (> T{int(current_avg)+1}): {len(slow)}/{len(baseline['games'])}")
    
    if analyze_only:
        log(f"\n[ANALYZE ONLY]")
        if fast: log(f"\n--- FAST (T{fast[0]['kill_turn']}) ---\n{fast[0]['log']}")
        if slow: log(f"\n--- SLOW (T{slow[0]['kill_turn']}) ---\n{slow[0]['log']}")
        bottleneck = find_bottleneck(fast, slow, current_source)
        log(f"\n  Bottleneck method: {bottleneck}")
        code, s, e = extract_method(current_source, bottleneck)
        if code:
            log(f"  Lines {s}-{e} ({e-s} lines)")
            for line in code.split("\n")[:20]:
                log(f"    {line}")
        return
    
    # Grind loop
    all_results = []
    prior_log = ""
    total_start = time.time()
    tried_methods = {}  # {method_name: consecutive_failures}
    effective_max = max_iters if not stop_time else 9999
    
    for iteration in range(1, effective_max + 1):
        # Time check
        if stop_time and datetime.now() >= stop_time:
            log(f"\n  STOP TIME REACHED ({stop_time.strftime('%I:%M %p')})")
            break
        
        remaining = ""
        if stop_time:
            mins_left = (stop_time - datetime.now()).total_seconds() / 60
            remaining = f" | {mins_left:.0f}min left"
        
        log(f"\n{'='*65}")
        log(f"  ITERATION {iteration} | T{current_avg:.2f} -> T{target_kill}{remaining}")
        log(f"{'='*65}")
        
        if current_avg <= target_kill:
            log(f"  TARGET REACHED!"); break
        
        # Find bottleneck method
        bottleneck = find_bottleneck(fast, slow, current_source, tried_methods)
        method_code, m_start, m_end = extract_method(current_source, bottleneck)
        if not method_code:
            log(f"  Could not extract method '{bottleneck}'"); break
        log(f"  Bottleneck: {bottleneck} (lines {m_start}-{m_end}, {m_end-m_start} lines)")
        
        # Ask Gemma to rewrite the method
        log(f"  [Gemma] Rewriting {bottleneck}...")
        new_code = ask_for_rewrite(
            bottleneck, method_code, fast, slow, baseline, deck_name, prior_log
        )
        
        # Clean markdown fences
        new_code = new_code.strip()
        if "```" in new_code:
            # Extract code between fences
            parts = new_code.split("```")
            for part in parts[1:]:  # skip text before first fence
                # Remove language identifier (python, py, etc)
                lines = part.splitlines()
                if lines and lines[0].strip().lower() in ("python", "py", ""):
                    lines = lines[1:]
                candidate = "\n".join(lines).strip()
                if "def " in candidate:
                    new_code = candidate
                    break
        
        # Find the def line even if there's explanation text before it
        if not new_code.strip().startswith("def "):
            lines = new_code.splitlines()
            def_start = None
            for i, line in enumerate(lines):
                stripped = line.strip()
                if stripped.startswith("def ") and "(" in stripped:
                    def_start = i
                    break
            if def_start is not None:
                new_code = "\n".join(lines[def_start:])
            else:
                log(f"  SKIP: Gemma didn't output a valid method")
                prior_log += f"  Iter{iteration}: SKIP (no def)\n"
                tried_methods[bottleneck] = tried_methods.get(bottleneck, 0) + 1
                continue
        
        # Strip trailing explanation after the method ends
        lines = new_code.splitlines()
        method_indent = len(lines[0]) - len(lines[0].lstrip())
        cut_at = len(lines)
        for i in range(1, len(lines)):
            stripped = lines[i].strip()
            if not stripped:
                continue
            line_indent = len(lines[i]) - len(lines[i].lstrip())
            # Non-code line at same or lower indent after method body = explanation
            if line_indent <= method_indent and not stripped.startswith("def ") and not stripped.startswith("#") and not stripped.startswith("\"\"\"") and not stripped.startswith("if ") and not stripped.startswith("for ") and not stripped.startswith("return") and not stripped.startswith("self"):
                # Check if this looks like English explanation, not code
                if any(w in stripped.lower() for w in ["this ", "the ", "note:", "explanation", "changes:", "key ", "important"]):
                    cut_at = i
                    break
        new_code = "\n".join(lines[:cut_at])
        
        # Apply the rewrite
        patched = replace_method(current_source, bottleneck, new_code)
        if patched is None:
            log(f"  SKIP: Could not replace method in source")
            prior_log += f"  Iter{iteration}: SKIP (replace failed)\n"
            tried_methods[bottleneck] = tried_methods.get(bottleneck, 0) + 1
            continue
        
        # Write temp file, load, test
        temp_dir = HARNESS_ROOT / "agents" / "temp"
        temp_dir.mkdir(exist_ok=True)
        temp_file = temp_dir / f"grind_{iteration}.py"
        temp_file.write_text(patched, encoding="utf-8")
        
        try:
            patched_apl = load_apl_from_file(temp_file)
            if not patched_apl:
                log(f"  FAIL: No APL class in patched file")
                prior_log += f"  Iter{iteration}: FAIL (no class)\n"
                tried_methods[bottleneck] = tried_methods.get(bottleneck, 0) + 1
                temp_file.unlink(missing_ok=True); continue
        except Exception as e:
            log(f"  FAIL: {str(e)[:80]}")
            prior_log += f"  Iter{iteration}: SYNTAX ({str(e)[:40]})\n"
            tried_methods[bottleneck] = tried_methods.get(bottleneck, 0) + 1
            temp_file.unlink(missing_ok=True); continue
        
        try:
            result = run_sim_fast(patched_apl, mainboard, n_games)
        except Exception as e:
            log(f"  CRASH: {str(e)[:80]}")
            prior_log += f"  Iter{iteration}: CRASH ({str(e)[:40]})\n"
            tried_methods[bottleneck] = tried_methods.get(bottleneck, 0) + 1
            temp_file.unlink(missing_ok=True); continue
        finally:
            temp_file.unlink(missing_ok=True)
        
        delta = current_avg - result["avg_kill"]
        verdict = "FASTER" if delta > 0.05 else "SLOWER" if delta < -0.05 else "SAME"
        log(f"  Result: T{current_avg:.2f} -> T{result['avg_kill']:.2f} ({delta:+.2f}) [{verdict}]")
        
        entry = {"iter": iteration, "method": bottleneck, "before": round(current_avg, 2),
                 "after": round(result["avg_kill"], 2), "delta": round(delta, 2), "verdict": verdict}
        all_results.append(entry)
        prior_log += f"  Iter{iteration}: {verdict} ({delta:+.2f}) {bottleneck}\n"
        
        # Track failures per method for cycling
        if verdict != "FASTER":
            tried_methods[bottleneck] = tried_methods.get(bottleneck, 0) + 1
        else:
            tried_methods[bottleneck] = 0  # reset on success
        
        # KEEP if faster
        if delta > 0.05:
            log(f"  KEEPING! Updating APL source.")
            current_source = patched
            current_avg = result["avg_kill"]
            # Re-collect fast/slow for next iteration
            fast = sorted([g for g in result["games"] if g["kill_turn"] <= int(target_kill)],
                          key=lambda g: g["kill_turn"])
            slow = sorted([g for g in result["games"] if g["kill_turn"] > int(current_avg) + 1],
                          key=lambda g: -g["kill_turn"])
            baseline = result
    
    # Summary
    elapsed = time.time() - total_start
    kept = [r for r in all_results if r["verdict"] == "FASTER"]
    total_gain = sum(r["delta"] for r in kept)
    
    log(f"\n{'='*65}")
    log(f"  GRINDER COMPLETE")
    log(f"  Original: T{baseline['avg_kill']:.2f} | Final: T{current_avg:.2f}")
    log(f"  Target: T{target_kill} | Gain: {total_gain:+.2f} turns")
    log(f"  Tested: {len(all_results)} | Kept: {len(kept)}")
    log(f"  Time: {elapsed:.0f}s | Cost: $0.00")
    log(f"{'='*65}")
    
    # Save improved APL
    if current_source != original_source:
        save_path = apl_file.parent / f"{apl_file.stem}_grind_{TODAY}.py"
        save_path.write_text(current_source, encoding="utf-8")
        log(f"\n  Saved: {save_path}")
        log(f"  To apply: copy {save_path.name} -> {apl_file.name}")
    
    # Write report
    safe = deck_name.lower().replace(" ", "-")
    report_lines = [
        "---", f'title: "APL Grinder: {deck_name} ({TODAY})"',
        f'domain: "mtg"', f'last_updated: "{TODAY}"',
        f'confidence: "high"', f'sources: ["apl-grinder"]', "---", "",
        f"## APL Grinder: {deck_name}",
        f"Original: T{baseline['avg_kill']:.2f} | Final: T{current_avg:.2f} | Target: T{target_kill}",
        f"Gain: {total_gain:+.2f} turns | Kept: {len(kept)}/{len(all_results)}",
        f"Time: {elapsed:.0f}s | Cost: $0.00", "", "### Results",
    ]
    for r in all_results:
        report_lines.append(
            f"- [{r['verdict']}] {r['method']} T{r['before']:.2f}->T{r['after']:.2f} ({r['delta']:+.2f})"
        )
    report_lines.extend(["", "## Changelog", f"- {TODAY}: Generated by apl_grinder.py"])
    
    path = HARNESS_ROOT / "knowledge" / "mtg" / f"grind-{safe}-{TODAY}.md"
    path.write_text("\n".join(report_lines), encoding="utf-8")
    log(f"  Report: {path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="APL Grinder")
    parser.add_argument("deck", help="Deck name")
    parser.add_argument("--target", type=float, default=5.0)
    parser.add_argument("--max-iterations", type=int, default=10)
    parser.add_argument("--games", type=int, default=200)
    parser.add_argument("--analyze-logs", action="store_true")
    parser.add_argument("--until", default=None,
                        help="Run until this time, e.g. '8:00' or '23:30' (24h format)")
    parser.add_argument("--duration", type=int, default=None,
                        help="Run for N minutes, e.g. --duration 30")
    parser.add_argument("--model", default="gemma4",
                        help="AI model: gemma4, gemma4:26b, gpt4o, gemini")
    args = parser.parse_args()
    
    # Set AI model (module-level variable)
    model_map = {"gpt4o": "gpt-4o", "gpt": "gpt-4o", "gemini": "gemini-flash",
                 "gemma": "gemma4", "gemma26b": "gemma4:26b", "26b": "gemma4:26b"}
    sys.modules[__name__]._AI_MODEL = model_map.get(args.model, args.model)
    
    # Parse stop time
    stop_time = None
    if args.until:
        try:
            parts = args.until.replace("am","").replace("pm","").split(":")
            hour = int(parts[0])
            minute = int(parts[1]) if len(parts) > 1 else 0
            # Handle am/pm
            if "pm" in args.until.lower() and hour < 12:
                hour += 12
            if "am" in args.until.lower() and hour == 12:
                hour = 0
            stop_time = datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)
            # If the time is in the past, assume tomorrow
            if stop_time <= datetime.now():
                stop_time += __import__('datetime').timedelta(days=1)
            log(f"  Will run until {stop_time.strftime('%I:%M %p')} ({(stop_time - datetime.now()).total_seconds()/3600:.1f} hours from now)")
        except Exception as e:
            log(f"  [WARN] Could not parse --until '{args.until}': {e}")
    
    # --duration flag (minutes)
    if args.duration and not stop_time:
        import datetime as dt_module
        stop_time = datetime.now() + dt_module.timedelta(minutes=args.duration)
        log(f"  Will run for {args.duration} minutes (until {stop_time.strftime('%I:%M %p')})")
    
    run_grinder(args.deck, args.target, args.max_iterations, args.games,
                args.analyze_logs, stop_time)
