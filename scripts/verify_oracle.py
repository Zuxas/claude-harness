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
import urllib.error

SIM_ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "mtg-sim")
sys.path.insert(0, SIM_ROOT)

# verify_card() result codes, chosen to equal the documented process exit codes:
# 0 PASS, 1 FAIL (oracle discrepancy), 2 UNAVAILABLE (model could not be reached).
PASS, FAIL, UNAVAILABLE = 0, 1, 2


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


# Engine files that hold the real card effects. Gemma sees the APL file only,
# so cards whose effect lives here (Spell Snare, Lightning Bolt, Fatal Push...)
# were reported as "not modeled" false positives (issue #74 section 3B). Feed it
# the handler code too.
_HANDLER_FILES = (
    "engine/card_handlers_verified.py",
    "engine/counter_resolver.py",
    "engine/card_effects.py",
    "engine/game_state.py",
)


def grep_handler_context(card_name: str, context_lines: int = 8,
                         max_chars: int = 6000) -> str:
    """Lines near every mention of card_name across the engine handler files.
    Capped at max_chars so a heavily-referenced card can't blow the model's
    context window."""
    out = []
    for rel in _HANDLER_FILES:
        path = os.path.join(SIM_ROOT, rel)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
        hits = sorted(
            {j for i, line in enumerate(lines) if card_name.lower() in line.lower()
             for j in range(max(0, i - context_lines),
                            min(len(lines), i + context_lines + 1))}
        )
        if not hits:
            continue
        chunk = "".join(f"  {k + 1:5d}: {lines[k]}" for k in hits)
        out.append(f"# {rel}\n{chunk}")
    joined = "\n---\n".join(out)
    if len(joined) > max_chars:
        joined = joined[:max_chars] + "\n  ... (handler context truncated)\n"
    return joined


def warm_up(model: str = "gemma4") -> None:
    """One throwaway call so the first real card doesn't hit a cold model
    (cold starts truncate and get mis-scored as FAIL). Best-effort."""
    try:
        ask_gemma("Reply with exactly: RESULT: PASS", model=model)
    except Exception:
        pass


def ask_gemma(prompt: str, model: str = "gemma4") -> tuple[str, str]:
    """Return (response_text, done_reason). done_reason is 'length' when the
    model hit the token cap and the answer is CUT OFF. num_predict is generous
    because the answer itself is short -- the big context lives in the prompt --
    so a 'length' stop almost always means the model rambled, not that a real
    verdict got clipped."""
    body = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 2048},
    }).encode()
    req = urllib.request.Request(
        "http://localhost:11434/api/generate",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read())
    return data.get("response", "").strip(), data.get("done_reason", "stop")


_VERDICT_RE = re.compile(r"RESULT:\s*(PASS|FAIL)", re.IGNORECASE)


def classify_verdict(response: str, done_reason: str = "stop") -> int:
    """Map a model answer to PASS / FAIL / UNAVAILABLE. Fail-closed: a cut-off
    or verdict-less answer is NEVER a silent PASS.

    - A clear 'RESULT: PASS' / 'RESULT: FAIL' line is authoritative (the verdict
      comes first, so truncation AFTER it does not change it).
    - An empty answer is UNAVAILABLE (the model said nothing).
    - A non-empty answer with no verdict line that was CUT OFF at the token cap
      (done_reason == 'length') is UNAVAILABLE, not FAIL -- we simply never got a
      verdict, so it is 'could not verify', not a reported discrepancy.
    - A non-empty, non-truncated answer that ignored the format stays FAIL, so a
      malformed-but-complete answer still gets a human's eyes."""
    text = response.strip()
    if not text:
        return UNAVAILABLE
    m = _VERDICT_RE.search(text)
    if m:
        return PASS if m.group(1).upper() == "PASS" else FAIL
    if done_reason == "length":
        return UNAVAILABLE
    return FAIL


def verify_card(card_name: str, apl_path: str, verbose: bool = True) -> int:
    """Return PASS, FAIL, or UNAVAILABLE (model could not be reached)."""
    oracle = get_oracle_text(card_name)
    if oracle is None:
        print(f"  SKIP  {card_name} -- oracle text not found in local DB")
        return PASS  # not a failure, just skipped

    context = grep_apl_context(apl_path, card_name)
    if not context:
        print(f"  SKIP  {card_name} -- not mentioned in {os.path.basename(apl_path)}")
        return PASS

    handler = grep_handler_context(card_name)
    handler_section = (
        f"""
ENGINE HANDLER CODE (the card's real effect usually lives here, not in the APL;
if the effect is implemented here, the card IS modeled -- do not report it as
"not modeled" just because the APL file does not repeat it):
{handler}
"""
        if handler
        else ""
    )

    prompt = f"""You are auditing an MTG simulation against official oracle text. The
simulation is split in two: an APL (Action Priority List) decides WHEN to play a
card, and the engine handler code implements WHAT the card does. A card is
correctly modeled if its effect is implemented in EITHER place.

CARD: {card_name}

ORACLE TEXT (verbatim from Scryfall):
{oracle}

APL IMPLEMENTATION (relevant lines from {os.path.basename(apl_path)}):
{context}
{handler_section}
Task: Identify any discrepancies between the oracle text and the implementation
(APL + engine handler together). Focus on:
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

    # Only connection-level failures mean "the model never answered" -- those
    # fail the gate closed (UNAVAILABLE), never pass. A genuine bug in this
    # script must still surface as a crash, not hide behind the infra label.
    try:
        response, done_reason = ask_gemma(prompt)
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
        print(f"  ERROR {card_name} -- Gemma unavailable: {e}", file=sys.stderr)
        return UNAVAILABLE

    verdict = classify_verdict(response, done_reason)
    if verdict == UNAVAILABLE:
        why = "empty response" if not response.strip() else f"no verdict (cut off, done_reason={done_reason})"
        print(f"  ERROR {card_name} -- Gemma gave no usable verdict: {why}", file=sys.stderr)
        return UNAVAILABLE

    status = "PASS " if verdict == PASS else "FAIL "
    print(f"  {status} {card_name}")
    if verbose and verdict == FAIL:
        # Print discrepancies indented
        for line in response.split("\n"):
            print(f"         {line}")
    return verdict


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


def batch_exit_code(results: list) -> int:
    """Discrepancy outranks unavailable outranks pass, so a real FAIL seen
    before the model went down is never masked by a later UNAVAILABLE."""
    if FAIL in results:
        return 1
    if UNAVAILABLE in results:
        return 2
    return 0


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
        warm_up()  # avoid a cold-start truncation on the first card
        results = [verify_card(name, apl_path) for name in card_names]
        passed = results.count(PASS)
        failed = results.count(FAIL)
        unavailable = results.count(UNAVAILABLE)
        print("-" * 60)
        print(f"Results: {passed} PASS  {failed} FAIL  {unavailable} UNVERIFIED  (of {len(results)} checked)")
        sys.exit(batch_exit_code(results))
    else:
        if len(args) < 2:
            print("Usage: verify_oracle.py <card_name> <apl_file>", file=sys.stderr)
            sys.exit(2)
        card_name = args[0]
        apl_path = os.path.abspath(args[1])
        sys.exit(verify_card(card_name, apl_path, verbose=True))


if __name__ == "__main__":
    main()
