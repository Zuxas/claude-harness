"""
gemma_apl_chunked.py -- Chunked APL generation via Gemma 4.

Instead of asking Gemma to write 200 lines of Python in one shot
(which fails ~70% of the time), this breaks APL generation into
5 small, reliable chunks that get stitched into a template.

CHUNKS (each is a single Gemma call, <30 lines output):
  1. Card catalog: name, cmc, type, role (creature/removal/burn/pump/utility)
  2. Keep logic: what hands to keep/mull (returns True/False conditions)
  3. Play priority: ordered list of which cards to cast and when
  4. Removal targets: which removal hits which targets, priority order
  5. Deck role: aggro/midrange/control, max_turns, blocking policy

TEMPLATE fills in the boilerplate (imports, declare_attackers,
declare_blockers, respond_to_spell -- these are always the same).

USAGE:
  python gemma_apl_chunked.py "Boros Convoke" --format standard
  python gemma_apl_chunked.py --format standard --all-missing
  python gemma_apl_chunked.py --dry-run --format standard --all-missing
"""

import sys
import os
import json
import time
import importlib
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

log = AgentLogger("gemma-chunked")
OLLAMA_API = "http://localhost:11434/api/generate"
TODAY = datetime.now().strftime("%Y-%m-%d")


def ask_gemma(prompt, system="", temperature=0.2, max_tokens=2048):
    if not check_ollama_health():
        return None, "Ollama unavailable"
    body = json.dumps({
        "model": "gemma4", "prompt": prompt, "system": system,
        "stream": False,
        "options": {"temperature": temperature, "num_predict": max_tokens}
    }).encode()
    try:
        req = urllib.request.Request(OLLAMA_API, data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=180) as resp:
            result = json.loads(resp.read()).get("response", "")
            ollama_breaker.record_success()
            return result, None
    except Exception as e:
        ollama_breaker.record_failure()
        return None, str(e)


# ---------------------------------------------------------------------------
# Chunk 1: Card Catalog
# ---------------------------------------------------------------------------

def chunk_card_catalog(deck_name, decklist_text):
    """Ask Gemma to categorize each card. Output: simple structured list."""
    prompt = (
        "Categorize each card in this MTG deck. One line per card.\n\n"
        "Deck: " + deck_name + "\n"
        "Decklist:\n" + decklist_text + "\n\n"
        "For each card, output EXACTLY this format (one per line):\n"
        "CARD|name|cmc|role|damage\n\n"
        "Roles: creature, removal, burn, pump, enchantment, planeswalker, land, utility, counterspell, wrath\n"
        "Damage: how much damage this card deals (0 if none, 3 for Lightning Bolt, etc.)\n\n"
        "Example:\n"
        "CARD|Lightning Bolt|1|burn|3\n"
        "CARD|Monastery Swiftspear|1|creature|0\n"
        "CARD|Mountain|0|land|0\n\n"
        "List ONLY mainboard cards. No explanation, just CARD lines."
    )
    resp, err = ask_gemma(prompt, system="Output structured data only. No explanation.", max_tokens=1500)
    if err:
        return None, err

    cards = []
    for line in resp.strip().split("\n"):
        line = line.strip()
        if not line.startswith("CARD|"):
            continue
        parts = line.split("|")
        if len(parts) >= 4:
            cards.append({
                "name": parts[1].strip(),
                "cmc": int(parts[2].strip()) if parts[2].strip().isdigit() else 0,
                "role": parts[3].strip().lower(),
                "damage": int(parts[4].strip()) if len(parts) > 4 and parts[4].strip().isdigit() else 0,
            })
    return cards, None


# ---------------------------------------------------------------------------
# Chunk 2: Deck Role + Config
# ---------------------------------------------------------------------------

def chunk_deck_role(deck_name, card_catalog):
    """Ask Gemma for deck role, max_turns, blocking policy."""
    card_summary = "\n".join(
        "  " + c["name"] + " (cmc " + str(c["cmc"]) + ", " + c["role"] + ")"
        for c in card_catalog if c["role"] != "land"
    )
    prompt = (
        "What role does this MTG deck play?\n\n"
        "Deck: " + deck_name + "\n"
        "Cards:\n" + card_summary + "\n\n"
        "Answer in EXACTLY this format (3 lines, nothing else):\n"
        "ROLE|aggro or midrange or control or combo or tempo\n"
        "MAX_TURNS|number (aggro=8, midrange=12, control=15)\n"
        "BLOCKING|never or favorable or always\n"
    )
    resp, err = ask_gemma(prompt, system="Output structured data only.", max_tokens=200)
    if err:
        return None, err

    config = {"role": "midrange", "max_turns": 10, "blocking": "favorable"}
    for line in resp.strip().split("\n"):
        if line.startswith("ROLE|"):
            config["role"] = line.split("|")[1].strip().lower()
        elif line.startswith("MAX_TURNS|"):
            val = line.split("|")[1].strip()
            config["max_turns"] = int(val) if val.isdigit() else 10
        elif line.startswith("BLOCKING|"):
            config["blocking"] = line.split("|")[1].strip().lower()
    return config, None


# ---------------------------------------------------------------------------
# Chunk 3: Keep/Mull Logic
# ---------------------------------------------------------------------------

def chunk_keep_logic(deck_name, card_catalog, config):
    """Ask Gemma for mulligan rules as simple conditions."""
    creatures = [c["name"] for c in card_catalog if c["role"] == "creature"]
    removal = [c["name"] for c in card_catalog if c["role"] in ("removal", "burn", "counterspell", "wrath")]

    prompt = (
        "Write mulligan rules for " + deck_name + " (" + config["role"] + " deck).\n\n"
        "Creatures: " + ", ".join(creatures[:10]) + "\n"
        "Removal: " + ", ".join(removal[:8]) + "\n\n"
        "Output EXACTLY this format (conditions to KEEP a hand):\n"
        "KEEP_MIN_LANDS|number (minimum lands to keep)\n"
        "KEEP_MAX_LANDS|number (maximum lands to keep)\n"
        "KEEP_MIN_CREATURES|number (minimum creatures needed)\n"
        "KEEP_MIN_SPELLS|number (minimum nonland noncreature spells)\n"
        "ALWAYS_MULL_IF|condition in plain english\n"
        "ALWAYS_KEEP_IF|condition in plain english\n"
    )
    resp, err = ask_gemma(prompt, system="Output structured data only.", max_tokens=300)
    if err:
        return None, err

    keep = {"min_lands": 1, "max_lands": 5, "min_creatures": 1, "min_spells": 0,
            "mull_if": "no lands", "keep_if": "2+ lands and 2+ creatures"}
    for line in resp.strip().split("\n"):
        if line.startswith("KEEP_MIN_LANDS|"):
            v = line.split("|")[1].strip()
            keep["min_lands"] = int(v) if v.isdigit() else 1
        elif line.startswith("KEEP_MAX_LANDS|"):
            v = line.split("|")[1].strip()
            keep["max_lands"] = int(v) if v.isdigit() else 5
        elif line.startswith("KEEP_MIN_CREATURES|"):
            v = line.split("|")[1].strip()
            keep["min_creatures"] = int(v) if v.isdigit() else 0
        elif line.startswith("KEEP_MIN_SPELLS|"):
            v = line.split("|")[1].strip()
            keep["min_spells"] = int(v) if v.isdigit() else 0
    return keep, None


# ---------------------------------------------------------------------------
# Chunk 4: Play Priority
# ---------------------------------------------------------------------------

def chunk_play_priority(deck_name, card_catalog, config):
    """Ask Gemma for the play order of cards by turn."""
    nonlands = [c for c in card_catalog if c["role"] != "land"]
    card_list = "\n".join(
        "  " + c["name"] + " (cmc " + str(c["cmc"]) + ", " + c["role"] + ")"
        for c in nonlands
    )
    prompt = (
        "What order should " + deck_name + " cast its spells?\n\n"
        "Cards:\n" + card_list + "\n\n"
        "Output a numbered priority list. Cast these in this order each turn.\n"
        "Format: PRIORITY|number|card name|when to cast\n\n"
        "Example:\n"
        "PRIORITY|1|Lightning Bolt|use as removal on opponent creature first, then burn face\n"
        "PRIORITY|2|Monastery Swiftspear|deploy T1 if possible\n"
        "PRIORITY|3|Emberheart Challenger|deploy T2\n\n"
        "List the top 15 cards by priority. No explanation."
    )
    resp, err = ask_gemma(prompt, system="Output structured data only.", max_tokens=1000)
    if err:
        return None, err

    priorities = []
    for line in resp.strip().split("\n"):
        if not line.startswith("PRIORITY|"):
            continue
        parts = line.split("|")
        if len(parts) >= 3:
            priorities.append({
                "rank": int(parts[1].strip()) if parts[1].strip().isdigit() else 99,
                "name": parts[2].strip(),
                "when": parts[3].strip() if len(parts) > 3 else "",
            })
    return priorities, None


# ---------------------------------------------------------------------------
# Template Assembly
# ---------------------------------------------------------------------------

def assemble_apl(deck_name, format_name, card_catalog, config, keep_logic, priorities):
    """Stitch Gemma's chunks into a working APL using a fixed template."""

    class_name = deck_name.replace(" ", "").replace("-", "").replace("'", "") + "StandardMatchAPL"
    slug = deck_name.lower().replace(" ", "_").replace("-", "_")

    # Build card constants
    const_lines = []
    seen = set()
    for c in card_catalog:
        if c["role"] == "land" or c["name"] in seen:
            continue
        seen.add(c["name"])
        var_name = c["name"].upper().replace(" ", "_").replace(",", "").replace("'", "")
        var_name = var_name.replace("-", "_").replace("//", "").replace(":", "")
        # Truncate long names
        if len(var_name) > 30:
            var_name = var_name[:30]
        const_lines.append(var_name + ' = "' + c["name"] + '"')

    # Build creature/removal/burn sets
    creatures = [c["name"] for c in card_catalog if c["role"] == "creature"]
    removal = [c["name"] for c in card_catalog if c["role"] in ("removal", "wrath")]
    burn = [c["name"] for c in card_catalog if c["role"] == "burn"]
    pumps = [c["name"] for c in card_catalog if c["role"] == "pump"]

    # Build priority cast order for main_phase_match
    cast_lines = []
    for p in sorted(priorities, key=lambda x: x["rank"]):
        card = p["name"]
        # Find role
        role = "creature"
        dmg = 0
        for c in card_catalog:
            if c["name"] == card:
                role = c["role"]
                dmg = c["damage"]
                break

        if role in ("removal", "burn", "wrath"):
            if dmg > 0:
                cast_lines.append(
                    '        # ' + card + ' (' + role + ', ' + str(dmg) + ' damage)\n'
                    '        for c in list(gs.zones.hand):\n'
                    '            if c.name == "' + card + '" and gs.mana_pool.can_cast(c.mana_cost, c.cmc):\n'
                    '                gs.mana_pool.pay(c.mana_cost, c.cmc)\n'
                    '                gs.zones.hand.remove(c)\n'
                    '                gs.zones.graveyard.append(c)\n'
                    '                gs.noncreature_spells_this_turn += 1\n'
                    '                if opponent:\n'
                    '                    opp_cr = [x for x in opponent.zones.battlefield\n'
                    '                              if not x.is_land() and x.has(Tag.CREATURE)\n'
                    '                              and safe_toughness(x) <= ' + str(dmg) + ']\n'
                    '                    if opp_cr:\n'
                    '                        t = max(opp_cr, key=lambda x: safe_power(x))\n'
                    '                        opponent.zones.battlefield.remove(t)\n'
                    '                        opponent.zones.graveyard.append(t)\n'
                    '                        gs._log("  ' + card + ': kill " + t.name)\n'
                    '                    else:\n'
                    '                        gs.damage_dealt += ' + str(dmg) + '\n'
                    '                        gs._log("  ' + card + ' face: ' + str(dmg) + ' dmg")\n'
                    '                else:\n'
                    '                    gs.damage_dealt += ' + str(dmg) + '\n'
                    '                break\n'
                )
            else:
                cast_lines.append(
                    '        # ' + card + ' (removal)\n'
                    '        if opponent:\n'
                    '            for c in list(gs.zones.hand):\n'
                    '                if c.name == "' + card + '" and gs.mana_pool.can_cast(c.mana_cost, c.cmc):\n'
                    '                    opp_cr = [x for x in opponent.zones.battlefield\n'
                    '                              if not x.is_land() and x.has(Tag.CREATURE)]\n'
                    '                    if opp_cr:\n'
                    '                        t = max(opp_cr, key=lambda x: safe_power(x))\n'
                    '                        gs.mana_pool.pay(c.mana_cost, c.cmc)\n'
                    '                        gs.zones.hand.remove(c)\n'
                    '                        gs.zones.graveyard.append(c)\n'
                    '                        opponent.zones.battlefield.remove(t)\n'
                    '                        opponent.zones.graveyard.append(t)\n'
                    '                        gs._log("  ' + card + ': kill " + t.name)\n'
                    '                    break\n'
                )
        elif role == "creature":
            cast_lines.append(
                '        # ' + card + '\n'
                '        for c in list(gs.zones.hand):\n'
                '            if c.name == "' + card + '" and gs.mana_pool.can_cast(c.mana_cost, c.cmc):\n'
                '                gs.cast_spell(c)\n'
                '                break\n'
            )
        else:
            # Enchantment, planeswalker, utility -- just cast
            cast_lines.append(
                '        # ' + card + ' (' + role + ')\n'
                '        for c in list(gs.zones.hand):\n'
                '            if c.name == "' + card + '" and gs.mana_pool.can_cast(c.mana_cost, c.cmc):\n'
                '                gs.cast_spell(c)\n'
                '                break\n'
            )

    # Blocking logic
    if config["blocking"] == "never":
        block_body = "        return {}"
    elif config["blocking"] == "always":
        block_body = (
            '        assignments = {}\n'
            '        if not attackers: return assignments\n'
            '        blockers = [c for c in gs.zones.battlefield if c.has(Tag.CREATURE)\n'
            '                    and not c.is_land() and not getattr(c, "tapped", False)]\n'
            '        if blockers and attackers:\n'
            '            biggest_att = max(attackers, key=lambda c: safe_power(c))\n'
            '            best_blocker = max(blockers, key=lambda c: safe_toughness(c))\n'
            '            if safe_toughness(best_blocker) >= safe_power(biggest_att):\n'
            '                assignments[id(biggest_att)] = [best_blocker]\n'
            '        return assignments'
        )
    else:  # favorable
        block_body = (
            '        assignments = {}\n'
            '        if not attackers: return assignments\n'
            '        blockers = [c for c in gs.zones.battlefield if c.has(Tag.CREATURE)\n'
            '                    and not c.is_land() and not getattr(c, "tapped", False)\n'
            '                    and safe_power(c) >= 3]\n'
            '        if blockers and attackers:\n'
            '            biggest_att = max(attackers, key=lambda c: safe_power(c))\n'
            '            if safe_power(biggest_att) >= 3:\n'
            '                best_blocker = max(blockers, key=lambda c: safe_toughness(c))\n'
            '                assignments[id(biggest_att)] = [best_blocker]\n'
            '        return assignments'
        )

    kl = keep_logic
    template = (
        '# Auto-generated match APL for ' + deck_name + ' (' + format_name + ')\n'
        '# Generated: ' + TODAY + ' by gemma_apl_chunked.py\n'
        '# Role: ' + config["role"] + ' | Max turns: ' + str(config["max_turns"]) + ' | Blocking: ' + config["blocking"] + '\n'
        '#\n'
        '# Gemma analyzed ' + str(len(card_catalog)) + ' cards, produced ' + str(len(priorities)) + ' priority rules\n'
        '\n'
        'from typing import Optional\n'
        'from data.card import Card, Tag\n'
        'from engine.game_state import GameState\n'
        'from apl.match_apl import MatchAPL\n'
        'from engine.match_state import safe_power, safe_toughness\n'
        '\n'
        + "\n".join(const_lines) + "\n"
        '\n'
        '\n'
        'class ' + class_name + '(MatchAPL):\n'
        '    name = "' + deck_name + '"\n'
        '    win_condition_damage = 20\n'
        '    max_turns = ' + str(config["max_turns"]) + '\n'
        '\n'
        '    def keep(self, hand, mulligans, on_play):\n'
        '        if len(hand) <= 4: return True\n'
        '        lands = sum(1 for c in hand if c.is_land())\n'
        '        creatures = sum(1 for c in hand if c.has(Tag.CREATURE))\n'
        '        spells = len(hand) - lands - creatures\n'
        '        if lands < ' + str(kl["min_lands"]) + ': return False\n'
        '        if lands > ' + str(kl["max_lands"]) + ': return False\n'
        '        if creatures >= ' + str(kl["min_creatures"]) + ' and lands >= 2: return True\n'
        '        if creatures + spells >= 3 and lands >= 2: return True\n'
        '        return mulligans >= 2\n'
        '\n'
        '    def bottom(self, hand, n):\n'
        '        lands = sorted([c for c in hand if c.is_land()], key=lambda c: c.name)\n'
        '        spells = sorted([c for c in hand if not c.is_land()],\n'
        '                        key=lambda c: -getattr(c, "cmc", 0))\n'
        '        return (lands[3:] + spells)[:n]\n'
        '\n'
        '    def main_phase(self, gs):\n'
        '        self.main_phase_match(gs, None)\n'
        '\n'
        '    def main_phase_match(self, gs, opponent):\n'
        '        self._play_land_if_able(gs)\n'
        '        gs.tap_lands()\n'
        '\n'
        + "\n".join(cast_lines) + "\n"
        '\n'
        '        # Cast any remaining creatures\n'
        '        for c in list(gs.zones.hand):\n'
        '            if c.has(Tag.CREATURE) and gs.mana_pool.can_cast(c.mana_cost, c.cmc):\n'
        '                gs.cast_spell(c)\n'
        '\n'
        '    def declare_attackers(self, gs, opponent):\n'
        '        return [c for c in gs.zones.battlefield\n'
        '                if c.has(Tag.CREATURE) and not c.is_land()\n'
        '                and not getattr(c, "summoning_sickness", False)\n'
        '                and not getattr(c, "tapped", False)]\n'
        '\n'
        '    def declare_blockers(self, gs, opp, attackers):\n'
        + block_body + '\n'
        '\n'
        '    def respond_to_spell(self, gs, opponent, spell):\n'
        '        return None\n'
        '\n'
        '    def end_step_actions(self, gs, opponent):\n'
        '        pass\n'
        '\n'
        '    def _play_land_if_able(self, gs):\n'
        '        lands = [c for c in gs.zones.hand if c.is_land()]\n'
        '        if not lands or gs.land_played: return\n'
        '        gs.play_land(lands[0])\n'
    )

    return template


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_apl(code, deck_file):
    """Compile, import, run 100 games."""
    try:
        compile(code, "<generated>", "exec")
    except SyntaxError as e:
        return False, "SyntaxError: " + str(e)

    temp_path = APL_DIR / "_temp_chunked.py"
    try:
        temp_path.write_text(code, encoding="utf-8")
        if "apl._temp_chunked" in sys.modules:
            del sys.modules["apl._temp_chunked"]
        mod = importlib.import_module("apl._temp_chunked")
        from apl.match_apl import MatchAPL, GenericMatchAPL
        apl_cls = None
        for v in vars(mod).values():
            if isinstance(v, type) and issubclass(v, MatchAPL) and v is not MatchAPL:
                apl_cls = v
                break
        if not apl_cls:
            return False, "No MatchAPL subclass found"
        apl = apl_cls()

        from data.deck import load_deck_from_file
        from engine.match_engine import run_match_set
        main_a, _ = load_deck_from_file(deck_file)
        main_b, _ = load_deck_from_file(deck_file)
        results = run_match_set(apl, main_a, GenericMatchAPL(), main_b, n=100, mix_play_draw=True)
        wr = results.win_rate_a()
        if wr < 0.01:
            return False, "0% WR -- broken"
        if wr > 0.99:
            return False, "100% WR -- broken"
        return True, "Valid: {:.1f}% WR".format(wr * 100)
    except Exception as e:
        return False, "Error: " + str(e)
    finally:
        if temp_path.exists():
            temp_path.unlink()
        if "apl._temp_chunked" in sys.modules:
            del sys.modules["apl._temp_chunked"]


# ---------------------------------------------------------------------------
# Main Pipeline
# ---------------------------------------------------------------------------

def generate_chunked_apl(deck_name, format_name="standard", dry_run=False):
    slug = deck_name.lower().replace(" ", "_").replace("-", "_")
    deck_file = str(DECKS_DIR / (slug + "_" + format_name + ".txt"))
    target = APL_DIR / (slug + "_" + format_name + "_match.py")

    if not Path(deck_file).exists():
        log.error("No deck file: " + deck_file)
        return {"status": "no_deck"}
    if target.exists():
        log.warn("Already exists: " + target.name)
        return {"status": "exists"}

    log.section("Chunked APL: " + deck_name + " (" + format_name + ")")
    decklist = Path(deck_file).read_text(encoding="utf-8")

    if dry_run:
        log.info("[DRY RUN] Would generate " + target.name)
        return {"status": "dry_run"}

    # Chunk 1: Card catalog
    log.info("Chunk 1/4: Card catalog...")
    catalog, err = chunk_card_catalog(deck_name, decklist)
    if err or not catalog:
        log.error("Card catalog failed: " + str(err))
        return {"status": "catalog_failed"}
    log.info("  " + str(len(catalog)) + " cards categorized")

    # Chunk 2: Deck role
    log.info("Chunk 2/4: Deck role...")
    config, err = chunk_deck_role(deck_name, catalog)
    if err:
        log.error("Deck role failed: " + str(err))
        return {"status": "role_failed"}
    log.info("  " + config["role"] + ", max T" + str(config["max_turns"]) + ", blocking=" + config["blocking"])

    # Chunk 3: Keep logic
    log.info("Chunk 3/4: Keep logic...")
    keep, err = chunk_keep_logic(deck_name, catalog, config)
    if err:
        log.error("Keep logic failed: " + str(err))
        return {"status": "keep_failed"}
    log.info("  lands " + str(keep["min_lands"]) + "-" + str(keep["max_lands"]) + ", creatures>=" + str(keep["min_creatures"]))

    # Chunk 4: Play priority
    log.info("Chunk 4/4: Play priority...")
    priorities, err = chunk_play_priority(deck_name, catalog, config)
    if err:
        log.error("Priority failed: " + str(err))
        return {"status": "priority_failed"}
    log.info("  " + str(len(priorities)) + " priority rules")

    # Assemble
    log.info("Assembling APL...")
    code = assemble_apl(deck_name, format_name, catalog, config, keep, priorities)

    # Validate
    log.info("Validating...")
    valid, msg = validate_apl(code, deck_file)
    if valid:
        target.write_text(code, encoding="utf-8")
        log.success("Installed: " + target.name + " (" + msg + ")")
        return {"status": "installed", "validation": msg}
    else:
        log.error("Validation failed: " + msg)
        # Save failed attempt for debugging
        fail_path = HARNESS_ROOT / "agents" / "temp" / (slug + "_failed.py")
        fail_path.parent.mkdir(exist_ok=True)
        fail_path.write_text(code, encoding="utf-8")
        log.info("Failed code saved: " + str(fail_path))
        return {"status": "failed", "error": msg}


def generate_all_missing(format_name="standard", dry_run=False):
    pattern = "*_" + format_name + ".txt"
    deck_files = sorted(DECKS_DIR.glob(pattern))
    results = []
    for f in deck_files:
        slug = f.stem.replace("_" + format_name, "")
        name = slug.replace("_", " ").title()
        has_apl = (APL_DIR / (slug + "_" + format_name + "_match.py")).exists()
        has_generic = (APL_DIR / (slug + "_match.py")).exists()
        if not has_apl and not has_generic:
            result = generate_chunked_apl(name, format_name, dry_run)
            results.append({"deck": name, **result})
            if not dry_run:
                time.sleep(2)
    if not results:
        log.info("All decks have APLs for " + format_name)
    else:
        installed = sum(1 for r in results if r.get("status") == "installed")
        failed = sum(1 for r in results if r.get("status") == "failed")
        log.info("Results: " + str(installed) + " installed, " + str(failed) + " failed out of " + str(len(results)))
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Chunked APL Generator via Gemma")
    parser.add_argument("deck", nargs="?", help="Deck name")
    parser.add_argument("--format", default="standard")
    parser.add_argument("--all-missing", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.all_missing:
        generate_all_missing(args.format, args.dry_run)
    elif args.deck:
        generate_chunked_apl(args.deck, args.format, args.dry_run)
    else:
        parser.print_help()
