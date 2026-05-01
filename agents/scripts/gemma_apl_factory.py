"""
gemma_apl_factory.py -- Generate match APLs via Gemma 4 with few-shot prompting,
chain-of-thought analysis, validation, and auto-retry.

FLOW:
  1. Load decklist from mtg-sim/decks/
  2. Ask Gemma to ANALYZE the deck (role, key cards, strategy)
  3. Ask Gemma to WRITE a match APL using the analysis + few-shot example
  4. Validate: compile, import, run 100 games
  5. If broken: feed error to Gemma, retry (max 3 attempts)
  6. If valid: install to mtg-sim/apl/{slug}_{format}_match.py

USAGE:
  python gemma_apl_factory.py "Gruul Aggro" --format standard
  python gemma_apl_factory.py --format standard --all-missing
  python gemma_apl_factory.py "Boros Energy" --format modern --dry-run
"""

import sys
import os
import json
import time
import importlib
import tempfile
import argparse
from pathlib import Path
from datetime import datetime

SIM_ROOT = Path("E:/vscode ai project/mtg-sim")
HARNESS_ROOT = Path("E:/vscode ai project/harness")
APL_DIR = SIM_ROOT / "apl"
DECKS_DIR = SIM_ROOT / "decks"

sys.path.insert(0, str(SIM_ROOT))
sys.path.insert(0, str(HARNESS_ROOT / "agents" / "scripts"))

from agent_hardening import AgentLogger, check_ollama_health, ollama_breaker
import urllib.request

log = AgentLogger("gemma-apl-factory")
OLLAMA_API = "http://localhost:11434/api/generate"
TODAY = datetime.now().strftime("%Y-%m-%d")

# ---------------------------------------------------------------------------
# Few-shot example (trimmed mono_red_match.py as the template)
# ---------------------------------------------------------------------------

FEW_SHOT_EXAMPLE = '''
"""Match APL example -- follow this EXACT pattern."""
from typing import Optional
from data.card import Card, Tag
from engine.game_state import GameState
from apl.match_apl import MatchAPL
from engine.match_state import safe_power, safe_toughness

# Card name constants
GOBLIN_GUIDE = "Goblin Guide"
SWIFTSPEAR = "Monastery Swiftspear"
BOLT = "Lightning Bolt"

ONE_DROPS = {GOBLIN_GUIDE, SWIFTSPEAR}
BURN = {BOLT}

class MonoRedMatchAPL(MatchAPL):
    name = "Mono Red Aggro"
    win_condition_damage = 20
    max_turns = 8

    def keep(self, hand, mulligans, on_play):
        if len(hand) <= 4: return True
        lands = sum(1 for c in hand if c.is_land())
        creatures = sum(1 for c in hand if c.name in ONE_DROPS)
        if lands == 0: return False
        if lands >= 2 and creatures >= 1: return True
        return mulligans >= 2

    def bottom(self, hand, n):
        lands = sorted([c for c in hand if c.is_land()], key=lambda c: c.name)
        spells = sorted([c for c in hand if not c.is_land()],
                        key=lambda c: -getattr(c, 'cmc', 0))
        return (lands[2:] + spells)[:n]

    def main_phase(self, gs):
        self.main_phase_match(gs, None)

    def main_phase_match(self, gs, opponent):
        self._play_land_if_able(gs)
        gs.tap_lands()
        # 1. Remove opponent threats
        if opponent:
            self._use_removal(gs, opponent)
        # 2. Deploy creatures by CMC
        for c in list(gs.zones.hand):
            if c.has(Tag.CREATURE) and gs.mana_pool.can_cast(c.mana_cost, c.cmc):
                gs.cast_spell(c)
        # 3. Burn face
        for c in list(gs.zones.hand):
            if c.name in BURN and gs.mana_pool.can_cast(c.mana_cost, c.cmc):
                gs.mana_pool.pay(c.mana_cost, c.cmc)
                gs.zones.hand.remove(c)
                gs.zones.graveyard.append(c)
                gs.damage_dealt += 3
                gs.noncreature_spells_this_turn += 1

    def _use_removal(self, gs, opponent):
        opp_creatures = [c for c in opponent.zones.battlefield
                         if not c.is_land() and c.has(Tag.CREATURE)]
        if not opp_creatures: return
        target = max(opp_creatures, key=lambda c: safe_power(c))
        if safe_power(target) < 2: return
        for c in list(gs.zones.hand):
            if c.name == BOLT and gs.mana_pool.can_cast(c.mana_cost, c.cmc):
                gs.mana_pool.pay(c.mana_cost, c.cmc)
                gs.zones.hand.remove(c); gs.zones.graveyard.append(c)
                if target in opponent.zones.battlefield:
                    opponent.zones.battlefield.remove(target)
                    opponent.zones.graveyard.append(target)
                return

    def declare_attackers(self, gs, opponent):
        return [c for c in gs.zones.battlefield
                if c.has(Tag.CREATURE) and not c.is_land()
                and not getattr(c, 'summoning_sickness', False)
                and not getattr(c, 'tapped', False)]

    def declare_blockers(self, gs, opp, attackers):
        return {}

    def respond_to_spell(self, gs, opponent, spell):
        return None

    def end_step_actions(self, gs, opponent):
        pass

    def _play_land_if_able(self, gs):
        lands = [c for c in gs.zones.hand if c.is_land()]
        if not lands or gs.land_played: return
        gs.play_land(lands[0])
'''


# ---------------------------------------------------------------------------
# Gemma API
# ---------------------------------------------------------------------------

def ask_gemma(prompt, system="", model="gemma4", max_tokens=4096, temperature=0.3):
    """Call Gemma via Ollama API with circuit breaker."""
    if not check_ollama_health():
        return None, "Ollama unavailable"

    body = json.dumps({
        "model": model, "prompt": prompt, "system": system,
        "stream": False,
        "options": {"temperature": temperature, "num_predict": max_tokens}
    }).encode()

    try:
        req = urllib.request.Request(OLLAMA_API, data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=300) as resp:
            result = json.loads(resp.read()).get("response", "")
            ollama_breaker.record_success()
            return result, None
    except Exception as e:
        ollama_breaker.record_failure()
        return None, str(e)


# ---------------------------------------------------------------------------
# Step 0: Load playbook content as strategy source
# ---------------------------------------------------------------------------

WEBSITE_DIR = Path("E:/vscode ai project/My-Website")

def load_playbook_text(deck_name, format_name):
    """Extract strategy text from an existing HTML playbook."""
    import re
    slug = deck_name.lower().replace(" ", "-").replace("_", "-")
    playbook_path = WEBSITE_DIR / format_name / (slug + "-playbook.html")
    if not playbook_path.exists():
        # Try without format suffix
        for f in (WEBSITE_DIR / format_name).glob("*-playbook.html"):
            if slug.split("-")[0] in f.stem:
                playbook_path = f
                break
    if not playbook_path.exists():
        log.info("No existing playbook found for " + deck_name)
        return ""

    html = playbook_path.read_text(encoding="utf-8", errors="replace")
    # Strip HTML tags, keep text
    text = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL)
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    # Trim to reasonable size for Gemma context
    if len(text) > 8000:
        text = text[:8000] + "..."
    log.info("Loaded playbook: " + playbook_path.name + " (" + str(len(text)) + " chars)")
    return text


# ---------------------------------------------------------------------------
# Step 1: Analyze deck (with playbook context)
# ---------------------------------------------------------------------------

def analyze_deck(deck_name, decklist_text, format_name):
    """Ask Gemma to analyze the deck using playbook + decklist."""
    playbook = load_playbook_text(deck_name, format_name)

    playbook_section = ""
    if playbook:
        playbook_section = (
            "\n\nEXISTING PLAYBOOK (from Team Resolve, use this as your PRIMARY source):\n"
            + playbook + "\n"
        )

    prompt = (
        "Analyze this MTG deck for writing a match simulation APL.\n\n"
        "Deck: " + deck_name + " (" + format_name + ")\n"
        "Decklist:\n" + decklist_text
        + playbook_section + "\n\n"
        "Answer these questions concisely:\n"
        "1. ROLE: Is this aggro, midrange, control, combo, or tempo?\n"
        "2. WIN CONDITION: How does this deck win? (combat damage, burn, combo, etc.)\n"
        "3. KEY CARDS: List the 5 most important cards and why\n"
        "4. REMOVAL: List all removal/interaction spells and what they kill (include mana cost and damage amount)\n"
        "5. CURVE: What does the ideal T1/T2/T3/T4 sequence look like?\n"
        "6. MULLIGAN: What makes a keepable hand? What's an auto-mull?\n"
        "7. MAX TURNS: How many turns should this deck take to win? (aggro=8, midrange=12, control=15)\n"
        "8. BLOCKING: Should this deck block? (aggro=never, midrange=favorable trades, control=always)\n"
        "9. BURN SPELLS: List any spells that deal direct damage to the opponent (name, mana cost, damage amount)\n"
        "10. SEQUENCING: What order should spells be cast each turn? (removal first? creatures first?)\n"
    )

    response, err = ask_gemma(prompt,
        system="You are an expert MTG competitive analyst. Be concise and specific. "
               "Use the playbook content as your primary reference if available.",
        temperature=0.2)

    if err:
        log.error("Deck analysis failed: {}".format(err))
        return None

    log.info("Deck analysis complete ({} chars)".format(len(response)))
    return response


# ---------------------------------------------------------------------------
# Step 2: Generate match APL code
# ---------------------------------------------------------------------------

def generate_match_apl_code(deck_name, decklist_text, analysis, format_name):
    """Ask Gemma to write a match APL based on its own analysis."""

    class_name = deck_name.replace(" ", "").replace("-", "").replace("'", "") + "MatchAPL"

    prompt = (
        "Write a Python match APL class for the MTG deck below.\n\n"
        "DECK: " + deck_name + " (" + format_name + ")\n"
        "CLASS NAME: " + class_name + "\n\n"
        "DECKLIST:\n" + decklist_text + "\n\n"
        "YOUR ANALYSIS OF THIS DECK:\n" + analysis + "\n\n"
        "EXAMPLE APL TO FOLLOW (use this EXACT pattern, same imports, same method signatures):\n"
        + FEW_SHOT_EXAMPLE + "\n\n"
        "RULES:\n"
        "- Output ONLY valid Python code. No markdown fences, no explanation.\n"
        "- Start with the docstring, then imports, then card constants, then the class.\n"
        "- The class MUST extend MatchAPL (from apl.match_apl import MatchAPL)\n"
        "- MUST implement: keep(), bottom(), main_phase(), main_phase_match(), "
        "declare_attackers(), declare_blockers(), respond_to_spell(), end_step_actions(), _play_land_if_able()\n"
        "- main_phase() must call self.main_phase_match(gs, None)\n"
        "- In main_phase_match: ALWAYS call self._play_land_if_able(gs) then gs.tap_lands() FIRST\n"
        "- Use gs.mana_pool.can_cast(c.mana_cost, c.cmc) before casting\n"
        "- Use gs.cast_spell(c) for creatures, gs.mana_pool.pay() + manual zone moves for noncreatures\n"
        "- Card names MUST exactly match the decklist (copy-paste them)\n"
        "- Define card name constants at the top\n"
        "- For removal: check opponent.zones.battlefield for creatures, remove + append to graveyard\n"
        "- For burn: add to gs.damage_dealt and gs.noncreature_spells_this_turn += 1\n"
        "\n"
        "CRITICAL PYTHON BUGS TO AVOID:\n"
        "- NEVER use set() with Card objects (Card is not hashable). Use lists instead.\n"
        "- NEVER iterate over a Card object directly. Cards are NOT iterable.\n"
        "- Use 'for c in list(gs.zones.hand):' (copy the list before modifying it)\n"
        "- Check 'c.name == CARD_NAME' for matching, not 'c in some_set'\n"
        "- Use c.has(Tag.CREATURE) to check if a card is a creature, not isinstance()\n"
        "- Card attributes: c.name (str), c.cmc (int), c.mana_cost (str like '{1}{R}'), c.power (str), c.toughness (str)\n"
        "- Use safe_power(c) and safe_toughness(c) to get int values from power/toughness strings\n"
        "- gs.zones.hand, gs.zones.battlefield, gs.zones.graveyard are all lists of Card objects\n"
        "- declare_blockers MUST return a dict (can be empty dict for no blocks)\n"
        "- respond_to_spell MUST return None or a Card\n"
    )

    response, err = ask_gemma(prompt,
        system="You are an expert Python developer writing MTG match simulation code. Output ONLY valid Python.",
        max_tokens=6000, temperature=0.2)

    if err:
        log.error("Code generation failed: {}".format(err))
        return None

    # Clean markdown fences if present
    code = response.strip()
    if code.startswith("```"):
        lines = code.splitlines()
        start = 1
        end = len(lines)
        for i in range(len(lines) - 1, 0, -1):
            if lines[i].strip() == "```":
                end = i
                break
        code = "\n".join(lines[start:end])

    return code


# ---------------------------------------------------------------------------
# Step 3: Validate generated APL
# ---------------------------------------------------------------------------

def validate_apl_code(code, deck_file, slug, format_name):
    """Validate generated APL: compile, import, run 100 games."""

    # 3a. Syntax check
    try:
        compile(code, "<generated>", "exec")
        log.info("  Syntax check: PASS")
    except SyntaxError as e:
        log.error("  Syntax check: FAIL -- {}".format(e))
        return False, "SyntaxError: {}".format(e)

    # 3b. Write to temp file and try importing
    temp_path = APL_DIR / "_temp_generated.py"
    try:
        temp_path.write_text(code, encoding="utf-8")

        # Clear cached module if exists
        if "apl._temp_generated" in sys.modules:
            del sys.modules["apl._temp_generated"]

        mod = importlib.import_module("apl._temp_generated")

        # Find the MatchAPL subclass
        from apl.match_apl import MatchAPL
        apl_cls = None
        for v in vars(mod).values():
            if isinstance(v, type) and issubclass(v, MatchAPL) and v is not MatchAPL:
                apl_cls = v
                break

        if not apl_cls:
            log.error("  Import check: FAIL -- no MatchAPL subclass found")
            return False, "No MatchAPL subclass found in generated code"

        apl_instance = apl_cls()
        log.info("  Import check: PASS ({})".format(apl_cls.__name__))

    except Exception as e:
        log.error("  Import check: FAIL -- {}".format(e))
        return False, "ImportError: {}".format(e)
    finally:
        if temp_path.exists():
            temp_path.unlink()
        if "apl._temp_generated" in sys.modules:
            del sys.modules["apl._temp_generated"]

    # 3c. Run 100 quick games against GenericMatchAPL
    try:
        from data.deck import load_deck_from_file
        from engine.match_engine import run_match_set
        from apl.match_apl import GenericMatchAPL

        main_a, sb_a = load_deck_from_file(deck_file)
        # Use same deck for opponent (self-play test)
        main_b, sb_b = load_deck_from_file(deck_file)

        apl_a = apl_instance
        apl_b = GenericMatchAPL()

        results = run_match_set(apl_a, main_a, apl_b, main_b, n=100, mix_play_draw=True)
        wr = results.win_rate_a()

        log.info("  Sim check: {} WR vs GenericMatchAPL (100 games)".format(
            "{:.1f}%".format(wr * 100)))

        if wr < 0.01:
            return False, "Win rate 0% -- APL is completely broken (never wins)"
        if wr > 0.99:
            return False, "Win rate 100% -- APL is likely not interacting correctly"

        return True, "Valid: {:.1f}% WR".format(wr * 100)

    except Exception as e:
        log.error("  Sim check: FAIL -- {}".format(e))
        return False, "SimError: {}".format(e)


# ---------------------------------------------------------------------------
# Step 4: Fix broken APL
# ---------------------------------------------------------------------------

def fix_apl_code(original_code, error_msg, deck_name, attempt):
    """Ask Gemma to fix a broken APL based on the error."""
    prompt = (
        "The following match APL code has a bug. Fix it.\n\n"
        "DECK: " + str(deck_name) + "\n"
        "ERROR: " + str(error_msg) + "\n"
        "ATTEMPT: " + str(attempt) + " of 3\n\n"
        "BROKEN CODE:\n" + str(original_code) + "\n\n"
        "Fix the bug and output the COMPLETE corrected Python code.\n"
        "Output ONLY valid Python code. No markdown fences, no explanation.\n"
        "Common fixes:\n"
        "- If SyntaxError: check string quotes, parentheses, indentation\n"
        "- If ImportError: check class name matches, MatchAPL imported correctly\n"
        "- If 0% WR: make sure main_phase_match calls _play_land_if_able + gs.tap_lands() first\n"
        "- If 100% WR: make sure opponent interaction works (removal targets opponent.zones.battlefield)\n"
    )

    response, err = ask_gemma(prompt,
        system="You are a Python debugging expert. Fix the code and output ONLY the corrected version.",
        max_tokens=6000, temperature=0.1)

    if err:
        return None

    code = response.strip()
    if code.startswith("```"):
        lines = code.splitlines()
        start = 1
        end = len(lines)
        for i in range(len(lines) - 1, 0, -1):
            if lines[i].strip() == "```":
                end = i
                break
        code = "\n".join(lines[start:end])

    return code


# ---------------------------------------------------------------------------
# Main: Generate + Validate + Install
# ---------------------------------------------------------------------------

def generate_match_apl(deck_name, format_name="standard", max_retries=3, dry_run=False):
    """Full pipeline: analyze deck -> generate APL -> validate -> install."""
    slug = deck_name.lower().replace(" ", "_").replace("-", "_")
    deck_file = str(DECKS_DIR / "{}_{}.txt".format(slug, format_name))
    target_path = APL_DIR / "{}_{}_match.py".format(slug, format_name)

    if not Path(deck_file).exists():
        log.error("No deck file found: {}".format(deck_file))
        return {"status": "no_deck_file"}

    if target_path.exists():
        log.warn("Match APL already exists: {} -- skipping".format(target_path.name))
        return {"status": "already_exists"}

    log.section("Generating match APL: {} ({})".format(deck_name, format_name))

    # Load decklist
    decklist_text = Path(deck_file).read_text(encoding="utf-8")

    if dry_run:
        log.info("[DRY RUN] Would generate APL for {} -> {}".format(deck_name, target_path.name))
        return {"status": "dry_run"}

    # Step 1: Analyze
    log.info("Step 1: Analyzing deck...")
    analysis = analyze_deck(deck_name, decklist_text, format_name)
    if not analysis:
        return {"status": "analysis_failed"}

    # Step 2: Generate
    log.info("Step 2: Generating match APL code...")
    code = generate_match_apl_code(deck_name, decklist_text, analysis, format_name)
    if not code:
        return {"status": "generation_failed"}

    # Step 3: Validate + retry loop
    for attempt in range(1, max_retries + 1):
        log.info("Step 3: Validating (attempt {}/{})...".format(attempt, max_retries))
        valid, msg = validate_apl_code(code, deck_file, slug, format_name)

        if valid:
            log.success("Validation PASSED: {}".format(msg))
            break
        else:
            log.warn("Validation FAILED: {}".format(msg))
            if attempt < max_retries:
                log.info("Step 4: Asking Gemma to fix...")
                fixed = fix_apl_code(code, msg, deck_name, attempt)
                if fixed:
                    code = fixed
                else:
                    log.error("Gemma fix failed, giving up")
                    return {"status": "fix_failed", "error": msg}
            else:
                log.error("Max retries reached, giving up")
                return {"status": "max_retries", "error": msg}

    # Step 5: Install
    header = '# Auto-generated match APL for {} ({}) by Gemma 4\n# Date: {}\n# Validated: {}\n\n'.format(
        deck_name, format_name, TODAY, msg)
    target_path.write_text(header + code, encoding="utf-8")
    log.success("Installed: {}".format(target_path.name))

    return {"status": "installed", "path": str(target_path), "validation": msg}


def generate_all_missing(format_name="standard", dry_run=False):
    """Find all decks without match APLs and generate them."""
    pattern = "*_{}.txt".format(format_name)
    deck_files = sorted(DECKS_DIR.glob(pattern))

    results = []
    for f in deck_files:
        slug = f.stem.replace("_{}" .format(format_name), "")
        name = slug.replace("_", " ").title()

        # Check if match APL exists (format-specific or generic)
        has_fmt_apl = (APL_DIR / "{}_{}_match.py".format(slug, format_name)).exists()
        has_gen_apl = (APL_DIR / "{}_match.py".format(slug)).exists()

        if not has_fmt_apl and not has_gen_apl:
            log.info("Missing match APL: {}".format(name))
            result = generate_match_apl(name, format_name, dry_run=dry_run)
            results.append({"deck": name, **result})
            # Pause between generations to not overload Gemma
            if not dry_run and result.get("status") != "no_deck_file":
                time.sleep(2)

    if not results:
        log.info("All decks have match APLs for {}".format(format_name))

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gemma Match APL Factory")
    parser.add_argument("deck", nargs="?", help="Deck name to generate APL for")
    parser.add_argument("--format", default="standard", help="Format")
    parser.add_argument("--all-missing", action="store_true", help="Generate for all decks without APLs")
    parser.add_argument("--dry-run", action="store_true", help="Show plan only")
    parser.add_argument("--retries", type=int, default=3, help="Max retry attempts")
    args = parser.parse_args()

    if args.all_missing:
        generate_all_missing(args.format, args.dry_run)
    elif args.deck:
        generate_match_apl(args.deck, args.format, args.retries, args.dry_run)
    else:
        parser.print_help()
