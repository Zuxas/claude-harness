"""
auto_pipeline.py -- Layer 5: Full Pipeline Automation

The endgame. Detects new archetypes, generates APLs, tests them,
tunes them, drafts playbook content, and maintains optimization memory.

FLOW:
  1. Read nightly meta shift data (from nightly_harness output)
  2. Identify NEW archetypes that have no APL
  3. Generate APLs via auto_apl.py (Claude API) or Gemma (free draft)
  4. Validate generated APLs via goldfish sim
  5. Run tuning loop on validated APLs
  6. Draft playbook skeleton from sim + analysis data
  7. Log all experiments to optimization memory
  8. Write pipeline report to knowledge base

USAGE:
  python auto_pipeline.py --format modern          # full pipeline
  python auto_pipeline.py --format standard --dry-run
  python auto_pipeline.py --generate-apl "New Deck Name"
  python auto_pipeline.py --draft-playbook "Boros Energy"
  python auto_pipeline.py --show-memory            # view optimization history

COST MODEL:
  - APL generation via Claude API: ~$0.05-0.10 per deck (one-time)
  - APL generation via Gemma: $0.00 (lower quality, good for drafts)
  - Everything else (sim, tuning, analysis): $0.00
"""

import sys
import os
import json
import time
import argparse
import subprocess
from pathlib import Path
from datetime import datetime
from collections import defaultdict

SIM_ROOT = Path("E:/vscode ai project/mtg-sim")
HARNESS_ROOT = Path("E:/vscode ai project/harness")
META_ANALYZER = Path("E:/vscode ai project/mtg-meta-analyzer")
WEBSITE_ROOT = Path("E:/vscode ai project/My-Website")
MEMORY_FILE = HARNESS_ROOT / "agents" / "optimization_memory.json"

sys.path.insert(0, str(SIM_ROOT))
sys.path.insert(0, str(META_ANALYZER))

TODAY = datetime.now().strftime("%Y-%m-%d")
TIMESTAMP = datetime.now().strftime("%Y-%m-%d %H:%M")

# SQL expression to normalise mixed date formats in events.date to YYYYMMDD.
# MTGTop8 stores DD/MM/YY; MTGDecks stores YYYY-MM-DD. Raw ORDER BY e.date
# DESC is broken because '31/10/25' > '2026-04-30' lexicographically.
_DB_DATE_KEY = (
    "CASE WHEN instr(e.date,'/')>0 "
    "THEN '20'||substr(e.date,7,2)||substr(e.date,4,2)||substr(e.date,1,2) "
    "ELSE replace(e.date,'-','') END"
)

def log(msg, level="INFO"):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [{level}] {msg}")


# ---------------------------------------------------------------------------
# Optimization Memory — persistent log of what worked across all experiments
# ---------------------------------------------------------------------------

def load_memory():
    """Load optimization memory from disk."""
    if MEMORY_FILE.exists():
        return json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
    return {"experiments": [], "generated_apls": [], "playbooks_drafted": [],
            "stats": {"total_experiments": 0, "total_improvements": 0,
                      "total_sim_games": 0, "total_time_sec": 0,
                      "total_api_cost": 0.0}}


def save_memory(memory):
    """Save optimization memory to disk via atomic write (no torn files).

    Note: this is atomic-write only, not full RMW protection. Concurrent
    callers that did load_memory() against the same baseline will still
    last-writer-wins. For true RMW safety, refactor caller to wrap the
    load-mutate-save triple in engine.atomic_json.atomic_rmw_json.
    Currently sequential (single nightly_harness invocation per format),
    so latent only. See IMPERFECTIONS:optimization-memory-rmw-race-latent.
    """
    from engine.atomic_json import atomic_write_json
    MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(MEMORY_FILE, memory)


def log_experiment(memory, deck, format_name, swap_out, swap_in,
                   baseline_wr, variant_wr, delta, status):
    """Log a single experiment to memory."""
    memory["experiments"].append({
        "date": TODAY, "deck": deck, "format": format_name,
        "swap_out": swap_out, "swap_in": swap_in,
        "baseline_wr": baseline_wr, "variant_wr": variant_wr,
        "delta": delta, "status": status
    })
    memory["stats"]["total_experiments"] += 1
    if status == "improved":
        memory["stats"]["total_improvements"] += 1


# ---------------------------------------------------------------------------
# Step 1: Detect New Archetypes Without APLs
# ---------------------------------------------------------------------------

def find_new_archetypes(format_name="modern"):
    """Find archetypes in the meta that have no APL or deck file."""
    from analysis.meta_change import compare_periods
    
    result = compare_periods(format_name, weeks_current=2, weeks_prior=4)
    
    # Get existing APLs and deck files
    apl_dir = SIM_ROOT / "apl"
    deck_dir = SIM_ROOT / "decks"
    existing_apls = {f.stem.lower() for f in apl_dir.glob("*.py")
                     if not f.stem.startswith("_") and f.stem not in
                     ("base_apl","auto_apl","generic_apl","match_apl",
                      "mulligan","sb_mixin","sb_plans","playbook_parser")}
    existing_decks = {f.stem.lower() for f in deck_dir.glob("*.txt")}
    
    new_archetypes = []
    for arch in result["archetypes"]:
        if arch["status"] not in ("new", "rising"):
            continue
        if arch["current_share"] < 0.02:  # skip <2% meta share
            continue
        
        safe = arch["archetype"].lower().replace(" ", "_").replace("-", "_")
        has_apl = any(safe in a for a in existing_apls)
        has_deck = any(safe in d for d in existing_decks)
        
        if not has_apl:
            new_archetypes.append({
                "name": arch["archetype"],
                "share": arch["current_share"],
                "status": arch["status"],
                "has_deck_file": has_deck,
            })
    
    return new_archetypes


# ---------------------------------------------------------------------------
# Step 2: Generate APLs for New Archetypes
# ---------------------------------------------------------------------------

def _safe_slug(deck_name):
    return deck_name.lower().replace(" ", "_").replace("-", "_").replace("'", "")


def _already_generated(deck_name):
    """Skip regeneration if APL file exists AND optimization_memory.json
    has a generated_apls entry for this deck. Both checks because either
    may be deleted/corrupted independently."""
    safe = _safe_slug(deck_name)
    apl_path = SIM_ROOT / "apl" / "auto_apls" / f"{safe}.py"
    if not apl_path.exists():
        return False
    memory = load_memory()
    for entry in memory.get("generated_apls", []):
        if entry.get("deck") == deck_name:
            return True
    return False


def generate_apl(deck_name, use_claude=True, dry_run=False, force=False, format_name="modern"):
    """Generate an APL for a new archetype.

    Stage S4 / 2026-04-28: dedup via _already_generated unless force=True;
    format_name threaded for downstream deck-file generation.
    use_claude=True routes to _generate_via_claude_v2 (same prompt as Gemma,
    higher-quality model, OAuth token). Falls back to Gemma if Claude
    unavailable.
    """
    if dry_run:
        log(f"  [DRY RUN] Would generate APL for {deck_name}")
        return {"status": "dry_run", "deck": deck_name}

    if not force and _already_generated(deck_name):
        log(f"  [DEDUP] APL exists for {deck_name}; skipping (pass --force to regenerate)")
        return {"status": "skipped_dedup", "deck": deck_name}

    if use_claude:
        return _generate_via_claude_v2(deck_name, format_name)
    else:
        return _generate_via_gemma(deck_name, format_name)


def _generate_via_claude(deck_name, format_name="modern"):
    """Generate APL via Claude API (higher quality, costs tokens).

    Stage S4 / 2026-04-28: format_name accepted for API parity with Gemma
    path (deck-file generation needs it). Claude path delegates to
    AutoAPLFactory which doesn't currently use format_name; passed for
    forward-compat. Deck-file + smoke + register handled by the caller
    (run_pipeline) for both paths.
    """
    log(f"  Generating APL via Claude API for {deck_name}...")
    try:
        from apl.auto_apl import AutoAPLFactory
        factory = AutoAPLFactory()
        apl = factory.get_apl(deck_name, force_rebuild=True)
        apl_type = type(apl).__name__

        if "Generic" in apl_type:
            log(f"  Fell back to GenericAPL (no playbook data for {deck_name})")
            return {"status": "fallback_generic", "deck": deck_name, "apl": apl_type}

        log(f"  Generated: {apl_type}")
        return {"status": "generated", "deck": deck_name, "apl": apl_type,
                "cost": 0.05, "method": "claude_api"}
    except Exception as e:
        log(f"  Claude API generation failed: {e}", "ERROR")
        return {"status": "error", "deck": deck_name, "error": str(e)}


def _call_ollama(prompt: str, model: str, temperature: float = 0.3,
                  max_tokens: int = 512) -> str:
    """Low-level Ollama API call. Returns response string or raises."""
    import urllib.request
    body = json.dumps({
        "model": model, "prompt": prompt, "stream": False,
        "options": {"temperature": temperature, "num_predict": max_tokens},
    }).encode()
    req = urllib.request.Request(
        "http://localhost:11434/api/generate", data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        return json.loads(resp.read()).get("response", "").strip()


def _classify_deck(deck_name: str, decklist: str) -> dict:
    """Step 1: Extract structured deck metadata via Gemma 12B.

    Returns a dict with keys: role, key_cards, removal, keep_threshold, must_have.
    Uses the fast 12B model — this is a pure extraction task, not code generation.
    """
    prompt = f"""Analyze this MTG deck and answer in EXACTLY this format (no other text):

DECK: {deck_name}
DECKLIST:
{decklist or "(no decklist — use your knowledge of this archetype)"}

Answer format (fill in each field, no extra lines):
ROLE: aggro|combo|control|midrange|ramp
KEY_CARDS: card1, card2, card3
REMOVAL: card1, card2
KEEP_THRESHOLD: 2|3
MUST_HAVE: card_name_or_NONE
"""
    try:
        response = _call_ollama(prompt, model="gemma4", temperature=0.1, max_tokens=256)
        result = {}
        for line in response.splitlines():
            if ":" in line:
                key, _, val = line.partition(":")
                result[key.strip().lower().replace(" ", "_")] = val.strip()
        return result
    except Exception as e:
        log(f"  Deck classification failed: {e}", "WARN")
        return {}


def _generate_keep_methods(classification: dict, deck_name: str,
                            decklist: str, model: str) -> str:
    """Step 2: Generate keep() and bottom() using classification context."""
    role = classification.get("role", "midrange")
    key_cards = classification.get("key_cards", "")
    keep_threshold = classification.get("keep_threshold", "2")
    must_have = classification.get("must_have", "NONE")

    prompt = f"""Write ONLY the keep() and bottom() methods for a Python MTG APL class.

Deck: {deck_name} | Role: {role}
Key cards: {key_cards}
Minimum lands to keep: {keep_threshold}
Must-have card (or NONE): {must_have}

EXEMPLAR (follow this exact structure):

    def keep(self, hand, mulligans, on_play):
        lands = [c for c in hand if c.is_land()]
        if len(hand) <= 4:
            return True
        if not lands:
            return False
        threats = [c for c in hand if c.name in KEY_CARDS]
        return len(lands) >= {keep_threshold} and (threats or mulligans >= 2)

    def bottom(self, hand, n):
        excess = sorted([c for c in hand if c.is_land()], key=lambda c: c.name)
        to_bottom = excess[3:] if len(excess) > 3 else []
        high_cmc = sorted([c for c in hand if not c.is_land() and c not in to_bottom],
                          key=lambda c: -c.cmc)
        for s in high_cmc:
            if len(to_bottom) >= n:
                break
            to_bottom.append(s)
        return to_bottom[:n]

Write the two methods only. No class definition, no imports, no explanation.
"""
    return _call_ollama(prompt, model=model, temperature=0.2, max_tokens=600)


def _generate_mainphase_methods(classification: dict, deck_name: str,
                                 decklist: str, model: str) -> str:
    """Step 3: Generate main_phase() and main_phase2() using classification context."""
    role = classification.get("role", "midrange")
    key_cards = classification.get("key_cards", "")
    removal = classification.get("removal", "")

    role_guidance = {
        "aggro": "Play threats on curve. Play all lands. Cast cheapest creatures first. Use removal only on blockers.",
        "midrange": "Play lands, then threats by CMC. Hold removal for their best creature.",
        "combo": "Sculpt hand toward key cards. Cast cantrips and card draw. Hold lands.",
        "control": "Hold up mana when possible. Counter threats. Draw cards.",
        "ramp": "Ramp first (play all ramp spells), then cast your big threats.",
    }.get(role, "Play lands and threats on curve.")

    prompt = f"""Write ONLY the main_phase() and main_phase2() methods for a Python MTG APL class.

Deck: {deck_name} | Role: {role}
Key cards (primary win conditions): {key_cards}
Removal spells: {removal}
Strategy: {role_guidance}

VALID Card API:
  card.name, card.cmc, card.mana_cost, card.is_land()
  card.has(Tag.CREATURE), card.has(Tag.INSTANT), card.has(Tag.SORCERY)
  card.power, card.toughness

VALID GameState (gs) API:
  gs.hand(), gs.zones.battlefield, gs.mana_pool.can_cast(mana_cost, cmc)
  gs.cast_spell(card), gs.play_land(card), gs.turn, gs._log(msg)

EXEMPLAR:

    def main_phase(self, gs):
        self._play_land_if_able(gs)
        hand = gs.hand()
        for card in sorted([c for c in hand if not c.is_land()], key=lambda c: c.cmc):
            if gs.mana_pool.can_cast(card.mana_cost, card.cmc):
                gs.cast_spell(card)
                break

    def main_phase2(self, gs):
        pass

Write the two methods only. No class definition, no imports, no explanation.
"""
    return _call_ollama(prompt, model=model, temperature=0.2, max_tokens=600)


def _indent(code: str, spaces: int = 4) -> str:
    """Indent each non-empty line by `spaces` spaces."""
    pad = " " * spaces
    return "\n".join(pad + line if line.strip() else line
                     for line in code.splitlines())


def _assemble_apl(deck_name: str, keep_code: str, mainphase_code: str) -> str:
    """Assemble three generated pieces into a complete APL file.

    Strips any markdown fences, ensures methods are indented 4 spaces
    inside the class body regardless of what indentation Gemma generated.
    """
    class_name = "".join(w.capitalize() for w in
                         deck_name.replace("-", " ").replace("'", "").split()) + "APL"

    def clean(code: str) -> str:
        code = code.strip()
        if code.startswith("```"):
            lines = code.splitlines()
            code = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        # Strip any existing leading indentation so we can re-apply uniformly
        import textwrap
        return textwrap.dedent(code).strip()

    keep_body = _indent(clean(keep_code)) if keep_code.strip() else (
        "    def keep(self, hand, mulligans, on_play):\n"
        "        lands = [c for c in hand if c.is_land()]\n"
        "        return len(hand) <= 4 or len(lands) >= 2\n\n"
        "    def bottom(self, hand, n):\n"
        "        excess = sorted([c for c in hand if c.is_land()], key=lambda c: c.name)\n"
        "        return (excess[3:] + [c for c in hand if not c.is_land()])[:n]"
    )
    main_body = _indent(clean(mainphase_code)) if mainphase_code.strip() else (
        "    def main_phase(self, gs):\n"
        "        self._play_land_if_able(gs)\n"
        "        self._cast_all_castable(gs)\n\n"
        "    def main_phase2(self, gs):\n"
        "        pass"
    )

    return f"""from data.card import Card, Tag
from apl.base_apl import BaseAPL


class {class_name}(BaseAPL):
    name = "{deck_name}"

{keep_body}

{main_body}
"""


def _build_apl_prompt(deck_name, format_name="modern"):
    """Build the shared APL generation prompt used by both Gemma and Claude."""
    decklist = _get_decklist_from_db(deck_name, format_name)
    decklist_block = f"Decklist:\n{decklist}" if decklist else "No decklist available - use your best knowledge of this archetype."
    return f"""Generate a Python APL class for the MTG deck "{deck_name}" ({format_name.title()} format).

{decklist_block}

=== STRICT REQUIREMENTS ===

1. Class name MUST end in "APL". Example: BurnAPL, AggroAPL, ComboAPL. WRONG: Burn, BurnClass.

2. Use EXACTLY these method signatures:
   def keep(self, hand: list, mulligans: int, on_play: bool) -> bool:
   def bottom(self, hand: list, n: int) -> list:
   def main_phase(self, gs) -> None:
   def main_phase2(self, gs) -> None:

3. VALID Card attributes and methods (use ONLY these):
   card.name          # str - oracle name
   card.cmc           # int - converted mana cost (use for cost comparisons, NOT mana_cost)
   card.mana_cost     # str - e.g. "{{1}}{{R}}" (string, do NOT compare with <=)
   card.is_land()     # method - returns bool (MUST use parentheses)
   card.has(Tag.X)    # method - checks tags; Tags: CREATURE, INSTANT, SORCERY, ENCHANTMENT, ARTIFACT
   card.power         # int or None
   card.toughness     # int or None

   DO NOT USE: card.is_removal, card.is_utility, card.is_interaction(), card.is_spell(),
               card.is_creature(), card.type_line (use card.has(Tag.CREATURE) instead)

4. VALID GameState (gs) attributes and methods:
   gs.hand()                          # list[Card] - cards in hand
   gs.zones.battlefield               # list[Card] - permanents on battlefield
   gs.zones.graveyard                 # list[Card]
   gs.mana_pool.can_cast(mana_cost, cmc)  # bool - can pay cost
   gs.cast_spell(card)                # cast a spell from hand
   gs.play_land(card)                 # play a land from hand
   gs.damage_dealt                    # int - total damage dealt this game
   gs.turn                            # int - current turn number
   gs._log(msg)                       # log a message

   DO NOT USE: gs.get(), gs.battlefield (no parens), gs.hand (no parens), gs.cards

=== EXEMPLAR (follow this shape exactly) ===

from data.card import Card, Tag
from apl.base_apl import BaseAPL

THREATS = {{"Dark Confidant", "Tarmogoyf", "Scavenging Ooze"}}

class ExampleAPL(BaseAPL):
    name = "Example"
    win_condition_damage = 20
    max_turns = 15

    def keep(self, hand, mulligans, on_play):
        lands = [c for c in hand if c.is_land()]
        if len(hand) <= 4:
            return True
        if not lands:
            return False
        threats = [c for c in hand if c.name in THREATS]
        return len(lands) >= 2 and (threats or mulligans >= 2)

    def bottom(self, hand, n):
        excess_lands = sorted([c for c in hand if c.is_land()], key=lambda c: c.name)
        to_bottom = excess_lands[3:] if len(excess_lands) > 3 else []
        high_cmc = sorted([c for c in hand if not c.is_land() and c not in to_bottom],
                          key=lambda c: -c.cmc)
        for s in high_cmc:
            if len(to_bottom) >= n:
                break
            to_bottom.append(s)
        return to_bottom[:n]

    def main_phase(self, gs):
        self._play_land_if_able(gs)
        for card in list(gs.hand()):
            if card.name in THREATS and gs.mana_pool.can_cast(card.mana_cost, card.cmc):
                gs.cast_spell(card)

    def main_phase2(self, gs):
        self._cast_all_castable(gs)

=== YOUR TASK ===
Write an APL for "{deck_name}" following the above requirements and exemplar shape exactly.
Use ONLY card names that appear in the decklist above.
Output ONLY valid Python code. No markdown fences, no explanation."""


def _save_apl_code(deck_name, code, method="gemma"):
    """Clean, syntax-check, and save generated APL code to apl/auto_apls/."""
    safe = _safe_slug(deck_name)
    cache_dir = SIM_ROOT / "apl" / "auto_apls"
    cache_dir.mkdir(parents=True, exist_ok=True)
    init_file = cache_dir / "__init__.py"
    if not init_file.exists():
        init_file.write_text("# Auto-generated APL package; populated by auto_pipeline.py\n",
                             encoding="utf-8")
    cache_file = cache_dir / f"{safe}.py"

    code = code.strip()
    if code.startswith("```"):
        lines = code.splitlines()
        code = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    import ast as _ast
    try:
        _ast.parse(code)
    except SyntaxError as _se:
        log(f"  SyntaxError at line {_se.lineno}: {_se.msg} -- saved anyway (smoke gate will catch)")

    header = f"# Auto-generated APL for {deck_name} ({method} draft)\n# {TODAY}\n\n"
    cache_file.write_text(header + code, encoding="utf-8")
    log(f"  Saved: {cache_file}")
    return cache_file


def _ollama_model_available(model_name: str) -> bool:
    """Check if a model is installed in Ollama without making a generate call."""
    import urllib.request
    try:
        req = urllib.request.Request("http://localhost:11434/api/tags")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        installed = [m["name"] for m in data.get("models", [])]
        return any(m == model_name or m.startswith(model_name.split(":")[0]) for m in installed)
    except Exception:
        return False


# Model preference order for APL code generation.
# qwen2.5-coder is a code-specialized model; better at structured Python than general-purpose Gemma.
# Falls back to gemma4:26b (larger, more capable), then gemma4 (12B, always available).
_APL_CODE_MODEL_PREFERENCE = ["qwen2.5-coder:14b", "gemma4:26b", "gemma4"]


def _pick_apl_model() -> str:
    for model in _APL_CODE_MODEL_PREFERENCE:
        if _ollama_model_available(model):
            return model
    return "gemma4"


def _generate_via_gemma(deck_name, format_name="modern"):
    """Generate APL draft via local model (free, fallback quality).

    Uses a decomposed 3-step approach:
      Step 1 (Gemma 12B): classify deck role + extract key cards/removal
      Step 2+3 (best available code model): generate keep/bottom + main_phase methods
      Assembly: stitch pieces into a valid Python APL class

    Decomposed generation reduces per-step reasoning load vs single monolith,
    improving structure correctness and card-name accuracy.

    Model preference for steps 2+3: qwen2.5-coder:14b > gemma4:26b > gemma4.
    Falls back to single-shot monolith if decomposition fails.

    Writes to apl/auto_apls/<slug>.py.
    """
    import urllib.request
    model = _pick_apl_model()
    log(f"  Generating APL via {model} (decomposed 3-step) for {deck_name}...")

    decklist = _get_decklist_from_db(deck_name, format_name)

    try:
        # Step 1: classify deck role + extract key cards (fast 12B — extraction task)
        log("    Step 1/3: classifying deck...")
        classification = _classify_deck(deck_name, decklist or "")
        role = classification.get("role", "midrange")
        log(f"    role={role}  key={classification.get('key_cards', '?')}")

        # Step 2: generate keep() + bottom() (code model — template fill task)
        log("    Step 2/3: generating keep/bottom methods...")
        keep_code = _generate_keep_methods(classification, deck_name, decklist or "", model)

        # Step 3: generate main_phase() + main_phase2() (code model)
        log("    Step 3/3: generating main_phase methods...")
        mainphase_code = _generate_mainphase_methods(classification, deck_name, decklist or "", model)

        # Assemble the three pieces
        code = _assemble_apl(deck_name, keep_code, mainphase_code)

        # Syntax check — fall back to monolith if assembly produced broken code
        import ast as _ast
        try:
            _ast.parse(code)
        except SyntaxError as _se:
            log(f"    Assembly SyntaxError: {_se.msg} -- falling back to monolith", "WARN")
            code = _call_ollama(_build_apl_prompt(deck_name, format_name),
                                model=model, temperature=0.3, max_tokens=4096)

        _save_apl_code(deck_name, code, method=f"decomposed-{model.split(':')[0]}")
        return {"status": "draft", "deck": deck_name, "cost": 0.0,
                "method": f"decomposed-{model}"}
    except Exception as e:
        log(f"  Decomposed generation failed ({e}) -- falling back to monolith", "WARN")
        # Monolith fallback: original single-shot approach
        try:
            code = _call_ollama(_build_apl_prompt(deck_name, format_name),
                                model=model, temperature=0.3, max_tokens=4096)
            _save_apl_code(deck_name, code, method=f"monolith-{model.split(':')[0]}")
            return {"status": "draft", "deck": deck_name, "cost": 0.0,
                    "method": f"monolith-{model}"}
        except Exception as e2:
            log(f"  Monolith fallback also failed: {e2}", "ERROR")
            return {"status": "error", "deck": deck_name, "error": str(e2)}


def _generate_via_claude_v2(deck_name, format_name="modern"):
    """Generate APL via Claude using the same prompt as Gemma (higher quality).

    Uses OAuth token from ~/.claude/.credentials.json -- free under Claude Max.
    Falls back to Gemma if token unavailable. Uses claude-sonnet-4-6 for
    production quality. Writes to apl/auto_apls/<slug>.py.
    """
    log(f"  Generating APL via Claude for {deck_name}...")
    try:
        import pathlib as _pl
        _creds = json.loads((_pl.Path.home() / ".claude" / ".credentials.json").read_text())
        _token = _creds["claudeAiOauth"]["accessToken"]
    except Exception as _e:
        log(f"  OAuth token unavailable ({_e}) -- falling back to Gemma", "WARN")
        return _generate_via_gemma(deck_name, format_name)

    prompt = _build_apl_prompt(deck_name, format_name)
    try:
        import anthropic as _anthropic
        import time as _time
        _client = _anthropic.Anthropic(api_key=_token)

        # Retry once on 429 with a 60s back-off (Sonnet has tighter OAuth rate limits)
        _code = None
        for _attempt in range(2):
            try:
                _msg = _client.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=4096,
                    messages=[{"role": "user", "content": prompt}]
                )
                _code = _msg.content[0].text.strip()
                break
            except _anthropic.RateLimitError:
                if _attempt == 0:
                    log(f"  Claude 429 rate limit -- waiting 60s before retry")
                    _time.sleep(60)
                else:
                    raise
        if _code is None:
            raise RuntimeError("Claude returned no content after retry")
        code = _code

        # One syntax-error retry via Claude
        import ast as _ast
        try:
            _ast.parse(code)
        except SyntaxError as _se:
            log(f"  SyntaxError at line {_se.lineno}: {_se.msg} -- retrying with Claude")
            _retry = _client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=4096,
                messages=[
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": code},
                    {"role": "user", "content": (
                        f"SyntaxError at line {_se.lineno}: {_se.msg}. "
                        f"Return the corrected Python code only."
                    )},
                ]
            )
            code = _retry.content[0].text.strip()

        _save_apl_code(deck_name, code, method="claude")
        return {"status": "draft", "deck": deck_name, "cost": 0.0, "method": "claude"}
    except Exception as e:
        log(f"  Claude generation failed: {e} -- falling back to Gemma", "WARN")
        return _generate_via_gemma(deck_name, format_name)


# ---------------------------------------------------------------------------
# Stage S4 helpers: deck-file generation, smoke gate, auto-registry
# ---------------------------------------------------------------------------

def _generate_deck_file_from_db(deck_name, format_name):
    """Pull most recent top-finish decklist from meta-analyzer DB and write
    to mtg-sim/decks/auto/<slug>_<format>.txt with audit:auto-generated marker.
    Returns the deck file path on success, None on failure.

    Format values in DB are lowercase (verified via T.0 pre-flight).
    """
    import sqlite3
    db_path = META_ANALYZER / "data" / "mtg_meta.db"
    if not db_path.exists():
        log(f"  [DECK-GEN] Meta-analyzer DB not found at {db_path}", level="WARN")
        return None

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        deck_row = conn.execute(f"""
            SELECT d.id FROM decks d
            JOIN events e ON e.id = d.event_id
            WHERE d.archetype = ? AND e.format = ?
            ORDER BY ({_DB_DATE_KEY}) DESC, d.placement ASC
            LIMIT 1
        """, (deck_name, format_name.lower())).fetchone()
        if not deck_row:
            log(f"  [DECK-GEN] No decks in DB for {deck_name} ({format_name})", level="WARN")
            return None

        cards = conn.execute("""
            SELECT c.name AS card_name, dc.quantity, dc.is_sideboard AS sideboard
            FROM deck_cards dc
            JOIN cards c ON c.id = dc.card_id
            WHERE dc.deck_id = ?
            ORDER BY dc.is_sideboard, c.name
        """, (deck_row["id"],)).fetchall()
        if not cards:
            log(f"  [DECK-GEN] Deck {deck_row['id']} has no cards", level="WARN")
            return None
    finally:
        conn.close()

    safe = _safe_slug(deck_name)
    deck_dir = SIM_ROOT / "decks" / "auto"
    deck_dir.mkdir(parents=True, exist_ok=True)
    deck_path = deck_dir / f"{safe}_{format_name}.txt"

    main = [c for c in cards if not c["sideboard"]]
    side = [c for c in cards if c["sideboard"]]
    lines = [f"// audit:auto-generated:{deck_name}:{TODAY}",
             f"// Source: meta-analyzer DB deck_id={deck_row['id']}, archetype={deck_name}",
             ""]
    for c in main:
        lines.append(f"{c['quantity']} {c['card_name']}")
    if side:
        lines.append("")
        lines.append("Sideboard")
        for c in side:
            lines.append(f"{c['quantity']} {c['card_name']}")

    deck_path.write_text("\n".join(lines), encoding="utf-8")
    log(f"  [DECK-GEN] Wrote {deck_path} ({len(main)} mainboard, {len(side)} sideboard)")
    return deck_path


_SMOKE_MIN_WIN_RATE = 0.10   # at least 10% of games must deal lethal
_SMOKE_MIN_KILL_TURN = 3     # faster than T3 means the APL is doing something wrong
_SMOKE_MAX_KILL_TURN = 20    # slower than T20 on average = APL effectively does nothing


def _smoke_test_apl(deck_name, format_name, n=50):
    """Import the auto-generated APL + run N goldfish games.

    Gate: crash-free AND semantic sanity:
      - win_rate >= _SMOKE_MIN_WIN_RATE (APL must actually deal lethal sometimes)
      - avg_kill_turn in [_SMOKE_MIN_KILL_TURN, _SMOKE_MAX_KILL_TURN] (kill timing sane)

    Semantic gate catches APLs that pass by never finding matching cards in the
    deck (win_rate=0%) or by winning impossibly fast (hallucinated kill T1).
    All metrics logged regardless of pass/fail for visibility.
    """
    safe = _safe_slug(deck_name)
    deck_path = SIM_ROOT / "decks" / "auto" / f"{safe}_{format_name}.txt"
    if not deck_path.exists():
        return {"status": "no_deck_file", "passed": False}
    try:
        import importlib
        if str(SIM_ROOT) not in sys.path:
            sys.path.insert(0, str(SIM_ROOT))
        mod_name = f"apl.auto_apls.{safe}"
        if mod_name in sys.modules:
            importlib.reload(sys.modules[mod_name])
        else:
            importlib.import_module(mod_name)
        mod = sys.modules[mod_name]
        cls = None
        for attr_name in dir(mod):
            obj = getattr(mod, attr_name)
            if isinstance(obj, type) and attr_name.endswith("APL") and attr_name != "BaseAPL":
                cls = obj
                cls_name = attr_name
                break
        if cls is None:
            return {"status": "no_apl_class", "passed": False}

        from data.deck import load_deck_from_file
        from engine.runner import run_simulation
        main, _ = load_deck_from_file(str(deck_path))
        apl_instance = cls()
        if not hasattr(apl_instance, 'name') or apl_instance.name is None:
            apl_instance.name = deck_name
        result = run_simulation(apl_instance, main, n=n, verbose_first=0, seed=42)

        win_rate = result.win_rate()
        avg_kt = result.avg_kill_turn()  # None if 0 wins

        metrics = {"win_rate": round(win_rate, 3),
                   "avg_kill_turn": round(avg_kt, 2) if avg_kt is not None else None,
                   "games_completed": n,
                   "class_name": cls_name}

        # Semantic gate
        if win_rate < _SMOKE_MIN_WIN_RATE:
            return {"status": "semantic_fail_win_rate",
                    "reason": f"win_rate={win_rate:.1%} < {_SMOKE_MIN_WIN_RATE:.0%} threshold",
                    "passed": False, **metrics}
        if avg_kt is None or not (_SMOKE_MIN_KILL_TURN <= avg_kt <= _SMOKE_MAX_KILL_TURN):
            return {"status": "semantic_fail_kill_turn",
                    "reason": f"avg_kill_turn={avg_kt} outside [{_SMOKE_MIN_KILL_TURN},{_SMOKE_MAX_KILL_TURN}]",
                    "passed": False, **metrics}

        return {"status": "passed", "passed": True, **metrics}
    except Exception as e:
        return {"status": "crashed", "passed": False, "error": str(e)[:200]}


def _register_auto_apl(deck_name, format_name, smoke_result):
    """Write entry to data/auto_apl_registry.json after smoke test passes.
    Failed smoke -> not registered; APL file stays on disk for manual review.

    Concurrency-safe RMW via engine.atomic_json (closes
    IMPERFECTIONS:auto-apl-registry-rmw-race-latent).
    """
    if not smoke_result.get("passed"):
        log(f"  [REG] Skipping registry insertion: smoke failed ({smoke_result.get('status')})")
        return False
    cls_name = smoke_result.get("class_name")
    if not cls_name:
        log(f"  [REG] Smoke result missing class_name; cannot register")
        return False
    safe = _safe_slug(deck_name)
    norm_key = deck_name.lower().replace(" ", "").replace("'", "").replace("-", "")
    reg_path = SIM_ROOT / "data" / "auto_apl_registry.json"
    new_entry = {
        "module": f"apl.auto_apls.{safe}",
        "class": cls_name,
        "deck_file": f"decks/auto/{safe}_{format_name}.txt",
        "generated_date": TODAY,
        "source": "auto_pipeline:gemma",
        "smoke_avg_turns": smoke_result.get("avg_turns"),
    }

    from engine.atomic_json import atomic_rmw_json
    try:
        atomic_rmw_json(
            reg_path,
            lambda reg: reg.update({norm_key: new_entry}),
            default_factory=dict,
        )
    except (json.JSONDecodeError, OSError) as e:
        log(f"  [REG] Existing registry unreadable ({e}); rewriting from scratch", level="WARN")
        from engine.atomic_json import atomic_write_json
        atomic_write_json(reg_path, {norm_key: new_entry})
    log(f"  [REG] Registered {norm_key} -> {cls_name}")
    return True


def _get_decklist_from_db(deck_name, format_name="modern"):
    """Get mainboard cards from meta-analyzer DB for prompt context.

    Queries DB directly (replaces broken db_bridge.load_saved_deck path).
    Returns formatted string of up to 30 mainboard cards, or "" if not found.
    Tries exact format match first, then any format as fallback.
    """
    try:
        import sqlite3 as _sqlite3
        _db_path = META_ANALYZER / "data" / "mtg_meta.db"
        if not _db_path.exists():
            return ""
        _conn = _sqlite3.connect(str(_db_path))
        _conn.row_factory = _sqlite3.Row
        try:
            _row = _conn.execute(f"""
                SELECT d.id FROM decks d
                JOIN events e ON e.id = d.event_id
                WHERE d.archetype = ? AND e.format = ?
                ORDER BY ({_DB_DATE_KEY}) DESC, d.placement ASC
                LIMIT 1
            """, (deck_name, format_name.lower())).fetchone()
            if not _row:
                _row = _conn.execute(f"""
                    SELECT d.id FROM decks d
                    JOIN events e ON e.id = d.event_id
                    WHERE d.archetype = ?
                    ORDER BY ({_DB_DATE_KEY}) DESC, d.placement ASC
                    LIMIT 1
                """, (deck_name,)).fetchone()
            if not _row:
                return ""
            _cards = _conn.execute("""
                SELECT c.name AS card_name, dc.quantity
                FROM deck_cards dc
                JOIN cards c ON c.id = dc.card_id
                WHERE dc.deck_id = ? AND dc.is_sideboard = 0
                ORDER BY dc.quantity DESC, c.name
            """, (_row["id"],)).fetchall()
            return "\n".join(f"  {c['quantity']}x {c['card_name']}" for c in _cards[:30])
        finally:
            _conn.close()
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Step 3: Validate Generated APLs
# ---------------------------------------------------------------------------

def validate_apl(deck_name, n_games=200):
    """Validate an APL by running a quick goldfish sim."""
    log(f"  Validating APL for {deck_name}...")
    tuner = HARNESS_ROOT / "agents" / "scripts" / "apl_tuner.py"
    try:
        proc = subprocess.run(
            [sys.executable, str(tuner), deck_name,
             "--mode", "validate", "--games", str(n_games)],
            capture_output=True, text=True, timeout=120,
            cwd=str(SIM_ROOT)
        )
        output = proc.stdout
        if "Kill turn" in output or "kill_turn" in output.lower():
            log(f"  APL validated successfully")
            return {"status": "valid", "deck": deck_name}
        elif "FAIL" in output:
            log(f"  APL validation FAILED: {output[-200:]}", "ERROR")
            return {"status": "invalid", "deck": deck_name}
        else:
            log(f"  APL validation unclear: {output[-200:]}")
            return {"status": "unclear", "deck": deck_name}
    except Exception as e:
        return {"status": "error", "deck": deck_name, "error": str(e)}


# ---------------------------------------------------------------------------
# Step 4: Draft Playbook Content
# ---------------------------------------------------------------------------

def draft_playbook(deck_name, format_name="modern", dry_run=False):
    """Draft a playbook skeleton from sim data + knowledge blocks."""
    if dry_run:
        log(f"  [DRY RUN] Would draft playbook for {deck_name}")
        return {"status": "dry_run"}
    
    # Gather data from knowledge blocks
    sim_reports = list((HARNESS_ROOT / "knowledge" / "mtg").glob(f"sim-{deck_name.lower().replace(' ','-')}*"))
    tune_reports = list((HARNESS_ROOT / "knowledge" / "mtg").glob(f"tune-{deck_name.lower().replace(' ','-')}*"))
    
    context = f"Deck: {deck_name}\nFormat: {format_name}\n\n"
    
    for report in sim_reports[-1:]:  # latest sim report
        context += f"=== Latest Sim Report ===\n{report.read_text(encoding='utf-8')[:2000]}\n\n"
    for report in tune_reports[-1:]:  # latest tuning report
        context += f"=== Latest Tuning Report ===\n{report.read_text(encoding='utf-8')[:2000]}\n\n"
    
    # Ask Gemma to draft playbook skeleton
    import urllib.request
    prompt = f"""Based on the sim data below, draft a playbook skeleton for {deck_name} in {format_name}.

{context}

Output a structured playbook with these sections:
1. DECK OVERVIEW (role, kill turn, strengths, weaknesses)
2. MULLIGAN GUIDE (what to keep, what to ship)
3. KEY CARDS (top 5 cards and when to play them)
4. MATCHUP NOTES (one paragraph per matchup from sim data)
5. SIDEBOARD GUIDE (which cards come in/out per matchup)

Write from the pilot-seat perspective (use "you/they" not "the player/the opponent").
Keep it concise and actionable."""

    body = json.dumps({
        "model": "gemma4", "prompt": prompt,
        "system": "You are an expert MTG competitive guide writer.",
        "stream": False, "options": {"temperature": 0.4, "num_predict": 4096}
    }).encode()
    
    try:
        req = urllib.request.Request("http://localhost:11434/api/generate",
                                     data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=300) as resp:
            playbook_content = json.loads(resp.read()).get("response", "")
        
        # Save as knowledge block
        safe = deck_name.lower().replace(" ", "-")
        block_path = HARNESS_ROOT / "knowledge" / "mtg" / f"playbook-draft-{safe}.md"
        
        block = f"""---
title: "Playbook Draft: {deck_name}"
domain: "mtg"
last_updated: "{TODAY}"
confidence: "medium"
sources: ["auto-pipeline", "sim-reports", "gemma-analysis"]
---

## Playbook Draft: {deck_name} ({format_name})
**Status: DRAFT - review before publishing**
**Generated: {TIMESTAMP}**

{playbook_content}

## Changelog
- {TODAY}: Auto-generated by auto_pipeline.py
"""
        block_path.write_text(block, encoding="utf-8")
        log(f"  Playbook draft: {block_path}")
        return {"status": "drafted", "path": str(block_path)}
    except Exception as e:
        log(f"  Playbook draft failed: {e}", "ERROR")
        return {"status": "error", "error": str(e)}


# ---------------------------------------------------------------------------
# Main Pipeline
# ---------------------------------------------------------------------------

def run_pipeline(format_name="modern", use_claude=True, dry_run=False,
                 generate_deck=None, draft_deck=None, show_memory=False,
                 top_n=3, force=False):
    """Run the full Layer 5 automation pipeline.

    Stage S4 / 2026-04-28: top_n caps archetypes per run (default 3 for
    safety; nightly can pass higher for post-PT meta). force=True bypasses
    the dedup check and regenerates existing APLs.
    """
    
    if show_memory:
        mem = load_memory()
        print(json.dumps(mem, indent=2, default=str))
        return
    
    # Single-deck operations
    if generate_deck:
        result = generate_apl(generate_deck, use_claude, dry_run, force=force,
                              format_name=format_name)
        if result["status"] in ("generated", "draft"):
            validate_apl(generate_deck)
        return result
    
    if draft_deck:
        return draft_playbook(draft_deck, format_name, dry_run)
    
    # Full pipeline
    log(f"")
    log(f"{'='*65}")
    log(f"  LAYER 5: FULL PIPELINE AUTOMATION")
    log(f"  Format: {format_name} | Claude API: {use_claude} | Dry run: {dry_run}")
    log(f"{'='*65}")
    
    start = time.time()
    memory = load_memory()
    
    # Step 1: Find new archetypes
    log("\n[STEP 1/5] Scanning for new archetypes without APLs...")
    new_archs = find_new_archetypes(format_name)
    if new_archs:
        log(f"  Found {len(new_archs)} new archetypes:")
        for a in new_archs:
            log(f"    {a['name']}: {a['share']:.1%} meta share [{a['status']}]")
    else:
        log(f"  No new archetypes found (all have APLs)")
    
    # Step 2: Generate APLs for new archetypes (capped by top_n; default 3)
    log(f"\n[STEP 2/5] Generating APLs for new archetypes (top_n={top_n})...")
    gen_results = []
    for arch in new_archs[:top_n]:
        result = generate_apl(arch["name"], use_claude, dry_run, force=force,
                              format_name=format_name)
        gen_results.append(result)
        if result.get("cost"):
            memory["stats"]["total_api_cost"] += result["cost"]
        if result["status"] in ("generated", "draft"):
            memory["generated_apls"].append({
                "date": TODAY, "deck": arch["name"],
                "method": result.get("method", "unknown"),
                "share": arch["share"]
            })

    # Step 2.5 (Stage S4): deck-file generation + smoke gate + auto-registry
    # Output flow: APL on disk -> deck file from meta-analyzer DB -> smoke
    # test (50 goldfish games) -> register if pass. Failed APLs stay on disk
    # for manual review but don't enter auto registry; canonical APL_REGISTRY
    # in apl/__init__.py is never touched.
    #
    # Iterates ALL top_n archetypes that have APL files on disk (whether
    # just-generated or deduped from prior run), skipping those already in
    # auto_apl_registry.json. Dedup-only skip would leave previously-
    # generated APLs unwired forever; this loop catches up.
    log(f"\n[STEP 2.5/N] Output-flow: deck files + smoke gate + auto-registry...")
    flow_results = []
    if not dry_run:
        # Load existing auto registry once
        auto_reg_path = SIM_ROOT / "data" / "auto_apl_registry.json"
        existing_reg = {}
        if auto_reg_path.exists():
            try:
                existing_reg = json.loads(auto_reg_path.read_text(encoding="utf-8"))
            except Exception:
                existing_reg = {}
        for arch in new_archs[:top_n]:
            deck_name = arch["name"]
            safe = _safe_slug(deck_name)
            apl_file = SIM_ROOT / "apl" / "auto_apls" / f"{safe}.py"
            if not apl_file.exists():
                flow_results.append({"deck": deck_name, "status": "no_apl_file"})
                continue
            norm_key = deck_name.lower().replace(" ", "").replace("'", "").replace("-", "")
            if norm_key in existing_reg:
                log(f"  [REG] {deck_name} already in auto_apl_registry; skipping smoke")
                flow_results.append({"deck": deck_name, "status": "already_registered"})
                continue
            deck_path = _generate_deck_file_from_db(deck_name, format_name)
            if not deck_path:
                flow_results.append({"deck": deck_name, "status": "no_deck_data"})
                continue
            smoke = _smoke_test_apl(deck_name, format_name, n=50)
            log(f"  Smoke {deck_name}: {smoke['status']}" +
                (f" (avg_turns={smoke.get('avg_turns'):.2f})"
                 if smoke.get("avg_turns") is not None else ""))
            if smoke.get("error"):
                log(f"    crash: {smoke['error']}")
            registered = _register_auto_apl(deck_name, format_name, smoke)
            flow_results.append({"deck": deck_name, "smoke": smoke["status"],
                                 "registered": registered})

    # Step 3: Validate generated APLs (legacy path - kept for compat)
    log("\n[STEP 3/5] Validating generated APLs...")
    valid_count = 0
    for result in gen_results:
        if result["status"] in ("generated", "draft") and not dry_run:
            val = validate_apl(result["deck"])
            if val["status"] == "valid":
                valid_count += 1
    
    # Step 4: Draft playbooks for top decks
    log("\n[STEP 4/5] Drafting playbooks for top archetypes...")
    playbook_results = []
    # Draft for any deck with sim data but no playbook draft yet
    sim_reports = list((HARNESS_ROOT / "knowledge" / "mtg").glob("sim-*.md"))
    existing_drafts = {f.stem for f in (HARNESS_ROOT / "knowledge" / "mtg").glob("playbook-draft-*.md")}
    
    for report in sim_reports[:3]:
        deck = report.stem.replace("sim-", "").replace("-", " ").title()
        draft_name = f"playbook-draft-{report.stem.replace('sim-', '')}"
        if draft_name not in existing_drafts:
            result = draft_playbook(deck, format_name, dry_run)
            playbook_results.append(result)
            if result["status"] == "drafted":
                memory["playbooks_drafted"].append({"date": TODAY, "deck": deck})
    
    if not playbook_results:
        log(f"  All decks with sim data already have playbook drafts")
    
    # Step 5: Save optimization memory
    log("\n[STEP 5/5] Updating optimization memory...")
    memory["stats"]["total_time_sec"] += time.time() - start
    if not dry_run:
        save_memory(memory)
        log(f"  Memory saved ({len(memory['experiments'])} experiments, "
            f"{len(memory['generated_apls'])} APLs, "
            f"{len(memory['playbooks_drafted'])} playbooks)")
    
    # Summary
    elapsed = time.time() - start
    api_cost = sum(r.get("cost", 0) for r in gen_results)
    log(f"\n{'='*65}")
    log(f"  LAYER 5 PIPELINE COMPLETE")
    log(f"  New archetypes found: {len(new_archs)}")
    log(f"  APLs generated: {len(gen_results)}")
    log(f"  APLs validated: {valid_count}")
    log(f"  Playbooks drafted: {len(playbook_results)}")
    log(f"  API cost: ${api_cost:.2f}")
    log(f"  Time: {elapsed:.1f}s")
    log(f"  Lifetime stats: {memory['stats']['total_experiments']} experiments, "
        f"{memory['stats']['total_improvements']} improvements")
    log(f"{'='*65}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Layer 5: Full Pipeline Automation")
    parser.add_argument("--format", default="modern", help="Format to scan")
    parser.add_argument("--dry-run", action="store_true", help="Show plan only")
    parser.add_argument("--use-gemma", action="store_true",
                        help="Use Gemma instead of Claude API for APL generation ($0.00)")
    parser.add_argument("--generate-apl", default=None, help="Generate APL for specific deck")
    parser.add_argument("--draft-playbook", default=None, help="Draft playbook for specific deck")
    parser.add_argument("--show-memory", action="store_true", help="Show optimization history")
    parser.add_argument("--top-n", type=int, default=3,
                        help="Cap on archetypes to process per run (default 3 for safety; "
                             "raise for post-PT meta with many new archetypes)")
    parser.add_argument("--force", action="store_true",
                        help="Bypass dedup; regenerate APLs even if files exist")
    args = parser.parse_args()

    run_pipeline(
        format_name=args.format,
        use_claude=not args.use_gemma,
        dry_run=args.dry_run,
        generate_deck=args.generate_apl,
        draft_deck=args.draft_playbook,
        show_memory=args.show_memory,
        top_n=args.top_n,
        force=args.force,
    )
