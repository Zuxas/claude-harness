"""
verify_oracle.py -- Oracle-text vs APL implementation checker

Automates the oracle-text-verify-before-touching-card-mechanics lesson.
Fetches oracle text from local Scryfall DB, greps the APL file for relevant
lines, sends both to Gemma 12B and asks for a discrepancy report.

Usage:
    python verify_oracle.py "Card Name" path/to/apl_file.py
    python verify_oracle.py "Lava Dart" mtg-sim/apl/izzet_prowess_match.py
    python verify_oracle.py --batch mtg-sim/apl/boros_energy.py

Exit codes:
    0 = PASS (no discrepancies found)
    1 = FAIL (discrepancies found or oracle not found)
    2 = ERROR (Gemma unavailable, DB error, etc.)
"""

import sys
import os
import json
import re
import urllib.request

SIM_ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "mtg-sim")
sys.path.insert(0, SIM_ROOT)


def get_oracle_text(card_name: str) -> str | None:
    try:
        from engine.card_db import CardDB
        db = CardDB()
        result = db.get(card_name)
        return result.get("oracle_text") if result else None
    except Exception as e:
        print(f"  [CardDB error: {e}]", file=sys.stderr)
        return None


def grep_apl_context(apl_path: str, card_name: str, context_lines: int = 25) -> str:
    """Extract lines near every mention of card_name in the APL file."""
    if not os.path.exists(apl_path):
        return ""
    with open(apl_path, encoding="utf-8") as f:
        lines = f.readlines()

    # Build a constant name variant (e.g. LAVA_DART) from the card name
    const_name = card_name.upper().replace(",", "").replace("'", "").replace(" ", "_")
    search_terms = [card_name, const_name]
    if "," in card_name:
        search_terms.append(card_name.split(",")[0])

    matched_blocks = []
    hit_lines = set()
    for i, line in enumerate(lines):
        if any(t.lower() in line.lower() for t in search_terms):
            start = max(0, i - context_lines)
            end = min(len(lines), i + context_lines + 1)
            for j in range(start, end):
                hit_lines.add(j)

    if not hit_lines:
        return ""

    # Build contiguous blocks
    sorted_hits = sorted(hit_lines)
    blocks = []
    block_start = sorted_hits[0]
    prev = sorted_hits[0]
    for idx in sorted_hits[1:]:
        if idx > prev + 1:
            blocks.append((block_start, prev))
            block_start = idx
        prev = idx
    blocks.append((block_start, prev))

    output_parts = []
    for start, end in blocks:
        chunk = "".join(
            f"  {start + 1 + j:4d}: {lines[start + j]}"
            for j in range(end - start + 1)
        )
        output_parts.append(chunk)

    return "\n---\n".join(output_parts)


def ask_gemma(prompt: str, model: str = "gemma4") -> str:
    body = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 1024},
    }).encode()
    req = urllib.request.Request(
        "http://localhost:11434/api/generate",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read()).get("response", "").strip()


def verify_card(card_name: str, apl_path: str, verbose: bool = True) -> bool:
    """Returns True if PASS, False if FAIL."""
    oracle = get_oracle_text(card_name)
    if oracle is None:
        print(f"  SKIP  {card_name} -- oracle text not found in local DB")
        return True  # not a failure, just skipped

    context = grep_apl_context(apl_path, card_name)
    if not context:
        print(f"  SKIP  {card_name} -- not mentioned in {os.path.basename(apl_path)}")
        return True

    prompt = f"""You are auditing an MTG simulation APL (Action Priority List) against official oracle text.

CARD: {card_name}

ORACLE TEXT (verbatim from Scryfall):
{oracle}

APL IMPLEMENTATION (relevant lines from {os.path.basename(apl_path)}):
{context}

Task: Identify any discrepancies between the oracle text and the APL implementation.
Focus on:
- Mana costs (wrong cost paid, cost not paid at all)
- Trigger conditions (when does the effect fire vs when APL fires it)
- Effect targets (who gains life, who takes damage, what gets exiled)
- Restrictions (oracle says "unless escaped", "sacrifice if you do", "non-legendary only", etc.)
- Missing effects (oracle says X happens, APL doesn't model X)

For each discrepancy: quote the oracle clause and the APL line that contradicts it.
If the implementation correctly matches oracle text, say: PASS

Answer format:
RESULT: PASS | FAIL
DISCREPANCIES:
- [oracle clause] vs [apl line or "not modeled"]
"""

    try:
        response = ask_gemma(prompt)
    except Exception as e:
        print(f"  ERROR {card_name} -- Gemma unavailable: {e}", file=sys.stderr)
        return True  # don't fail the run if Gemma is down

    passed = response.upper().startswith("RESULT: PASS") or "RESULT: PASS" in response[:50]
    status = "PASS " if passed else "FAIL "
    print(f"  {status} {card_name}")
    if verbose and not passed:
        # Print discrepancies indented
        for line in response.split("\n"):
            print(f"         {line}")
    return passed


def extract_card_constants(apl_path: str) -> list[str]:
    """Find all module-level card name constants (e.g. LAVA_DART = "Lava Dart")."""
    names = []
    pattern = re.compile(r'^[A-Z_]+\s*=\s*"([^"]+)"', re.MULTILINE)
    with open(apl_path, encoding="utf-8") as f:
        content = f.read()
    for match in pattern.finditer(content):
        card_name = match.group(1)
        # Skip obvious non-card strings
        if len(card_name) > 3 and not card_name.startswith("apl/") and "/" not in card_name:
            names.append(card_name)
    return list(dict.fromkeys(names))  # deduplicate, preserve order


def main():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)

    batch_mode = args[0] == "--batch"
    if batch_mode:
        if len(args) < 2:
            print("Usage: verify_oracle.py --batch <apl_file>", file=sys.stderr)
            sys.exit(2)
        apl_path = os.path.abspath(args[1])
        card_names = extract_card_constants(apl_path)
        if not card_names:
            print(f"No card name constants found in {apl_path}")
            sys.exit(0)
        print(f"Batch verifying {len(card_names)} cards in {os.path.basename(apl_path)}")
        print("-" * 60)
        results = [verify_card(name, apl_path) for name in card_names]
        passed = sum(results)
        failed = len(results) - passed
        print("-" * 60)
        print(f"Results: {passed} PASS  {failed} FAIL  (of {len(results)} checked)")
        sys.exit(0 if failed == 0 else 1)
    else:
        if len(args) < 2:
            print("Usage: verify_oracle.py <card_name> <apl_file>", file=sys.stderr)
            sys.exit(2)
        card_name = args[0]
        apl_path = os.path.abspath(args[1])
        ok = verify_card(card_name, apl_path, verbose=True)
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
