"""
apl_judge.py -- LLM-as-judge APL decision-quality scorer

Grades an APL (Action Priority List) on *decision quality* -- oracle
fidelity, strategic choices, and keep/mulligan logic -- independently of
gauntlet win-rate. WR proves the code runs; the judge catches
oracle-incorrect or strategically-wrong decisions that WR cannot see.

Implements harness/specs/2026-06-28-llm-as-judge-impl-plan.md
(operationalizing harness/specs/2026-04-30-llm-as-judge-apl-evaluation.md).

It mirrors verify_oracle.py (same grep/oracle helpers, same exit-code
convention) but uses auto_pipeline's streaming+retry Ollama transport
instead of verify_oracle's stream=False (which returns empty for Gemma
under load -- auto_pipeline.py:236-238).

Public API
----------
    call_llm(prompt, model="gemma4", ...) -> str            # guarded, lazy
    check_llm_available(model="gemma4") -> bool             # soft probe
    grade_apl(question, apl_path=None, *, apl_code=None,
              model="gemma4", llm=None) -> JudgeGrade        # the callable
    score_apl(apl_basename, questions, *, model, llm) -> dict
    run_calibration(fixtures, *, model, llm) -> dict
    JudgeGrade (dataclass)                                  # the grade shape

The LLM call is lazy and guarded: importing this module never contacts a
model. call_llm imports urllib only when invoked and raises LLMUnavailable
on any transport failure; grade_apl catches that and returns a well-formed
ERROR grade rather than crashing (fail-soft, per spec).

Usage (CLI scorer)
------------------
    python apl_judge.py --apl boros_energy_match.py
    python apl_judge.py --category oracle_fidelity --all-canonical
    python apl_judge.py --calibrate
    python apl_judge.py                      # no args -> runs self-test

Exit codes (CLI scorer; mirrors verify_oracle):
    0 = PASS (APL score >= 85%, or calibration >= 9/10)
    1 = FAIL (below threshold)
    2 = ERROR (LLM unavailable / bad input)

Self-test (bare `python apl_judge.py` or `--selftest`):
    0 = all tests pass (prints "ALL APL_JUDGE TESTS PASS")
    1 = a test failed
"""

import os
import sys
import json
import re
from dataclasses import dataclass, field, asdict

# --- path wiring -----------------------------------------------------------
# verify_oracle.py lives in harness/scripts/ (this file lives in
# harness/agents/scripts/ per the task path). Put harness/scripts/ on the
# path so we can reuse its import-safe helpers, and mirror its SIM_ROOT.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_HARNESS_ROOT = os.path.normpath(os.path.join(_THIS_DIR, "..", ".."))
_HARNESS_SCRIPTS = os.path.join(_HARNESS_ROOT, "scripts")
if _HARNESS_SCRIPTS not in sys.path:
    sys.path.insert(0, _HARNESS_SCRIPTS)

# SIM_ROOT mirrors verify_oracle.py:25-26 but relative to THIS file's depth.
SIM_ROOT = os.path.normpath(os.path.join(_HARNESS_ROOT, "..", "mtg-sim"))
if SIM_ROOT not in sys.path:
    sys.path.insert(0, SIM_ROOT)

DATA_DIR = os.path.join(_HARNESS_ROOT, "data")
DEFAULT_QUESTIONS = os.path.join(DATA_DIR, "apl_judge_questions.json")
DEFAULT_CALIBRATION = os.path.join(DATA_DIR, "apl_judge_calibration.json")

DEFAULT_MODEL = "gemma4"  # real Ollama tag in this repo (verify_oracle.py:88)

# Thresholds reconcile the spec's internal inconsistency (goal >90 / gate >85
# / stop <70). plan F.
PASS_THRESHOLD = 0.85
TARGET_THRESHOLD = 0.90
HARD_STOP_THRESHOLD = 0.70

# Merged grep context cap (gotcha 5). Beyond this we bump num_ctx to 8192.
CONTEXT_SOFT_CAP = 6000
CONTEXT_HARD_CAP = 12000

VALID_TYPES = ("oracle_fidelity", "strategic", "mulligan")


# ---------------------------------------------------------------------------
# Grade shape
# ---------------------------------------------------------------------------
@dataclass
class JudgeGrade:
    """Structured quality grade for one (question, APL) pair."""
    question_id: str
    apl: str
    type: str
    result: str          # PASS | FAIL | INCONCLUSIVE | ERROR
    reason: str
    model: str = DEFAULT_MODEL
    raw: str = ""
    card_or_deck: str = ""

    @property
    def is_error(self) -> bool:
        return self.result == "ERROR"

    @property
    def is_pass(self) -> bool:
        return self.result == "PASS"

    @property
    def counts_for_score(self) -> bool:
        # ERROR/INCONCLUSIVE are excluded from the denominator; PASS/FAIL count.
        return self.result in ("PASS", "FAIL")

    def to_dict(self) -> dict:
        d = asdict(self)
        d["is_pass"] = self.is_pass
        d["is_error"] = self.is_error
        return d


class LLMUnavailable(RuntimeError):
    """Raised by call_llm when the model cannot be reached."""


# ---------------------------------------------------------------------------
# Transport -- lazy + guarded streaming Ollama call (auto_pipeline.py:233-288)
# ---------------------------------------------------------------------------
def check_llm_available(model: str = DEFAULT_MODEL, timeout: int = 5) -> bool:
    """Soft probe. True if Ollama is responsive. Never raises.

    Prefers agent_hardening.check_ollama_health (circuit-breaker aware); falls
    back to a direct /api/tags probe if that import is unavailable.
    """
    try:
        from agent_hardening import check_ollama_health  # type: ignore
        return bool(check_ollama_health(timeout=timeout))
    except Exception:
        pass
    try:
        import urllib.request
        req = urllib.request.Request("http://localhost:11434/api/tags")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


def call_llm(prompt: str, model: str = DEFAULT_MODEL, *,
             temperature: float = 0.1, max_tokens: int = 512,
             num_ctx: int = 4096, timeout: int = 300) -> str:
    """Guarded, lazy Ollama call. Returns the response string.

    Streaming + 3-attempt retry (2s/8s backoff), accumulating tokens -- copied
    from auto_pipeline._call_ollama because stream=False returns an empty
    response for Gemma under load. urllib is imported here, not at module top,
    so importing apl_judge never opens a socket. Raises LLMUnavailable when
    all attempts fail.
    """
    import time
    import urllib.request
    import urllib.error

    body = json.dumps({
        "model": model, "prompt": prompt, "stream": True,
        "keep_alive": "30m",
        "options": {"temperature": temperature, "num_predict": max_tokens,
                    "num_ctx": num_ctx, "num_batch": 1024},
    }).encode()

    backoffs = [2, 8]  # 3 attempts total
    last_err = None
    for attempt in range(len(backoffs) + 1):
        try:
            req = urllib.request.Request(
                "http://localhost:11434/api/generate", data=body,
                headers={"Content-Type": "application/json"},
            )
            tokens = []
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                for line in resp:
                    if not line.strip():
                        continue
                    chunk = json.loads(line)
                    tokens.append(chunk.get("response", ""))
                    if chunk.get("done"):
                        break
            result = "".join(tokens).strip()
            if not result:
                raise ValueError("empty response from Ollama")
            return result
        except (urllib.error.URLError, TimeoutError, ValueError, OSError) as e:
            last_err = e
            if attempt < len(backoffs):
                time.sleep(backoffs[attempt])
    raise LLMUnavailable(f"Ollama call failed after retries: {last_err}")


# ---------------------------------------------------------------------------
# Context extraction -- reuse verify_oracle, extended to multi-term
# ---------------------------------------------------------------------------
def _oracle_text(card_name: str) -> str:
    """Prefer CardDB.oracle_text (canonical accessor, card_db.py:148); fall
    back to verify_oracle.get_oracle_text. Never raises."""
    try:
        from engine.card_db import CardDB  # type: ignore
        txt = CardDB().oracle_text(card_name)
        if txt:
            return txt
    except Exception:
        pass
    try:
        from verify_oracle import get_oracle_text  # type: ignore
        return get_oracle_text(card_name) or ""
    except Exception:
        return ""


def _grep_lines(lines, terms, context_lines: int = 25) -> str:
    """Core grep: contiguous numbered blocks around any mention of any term.

    Mirrors verify_oracle.grep_apl_context (verify_oracle.py:40) but merges
    hits across a *list* of terms into one block set (the real helper takes a
    single term). Works on an in-memory list of lines so the self-test can run
    against a code string without touching disk.
    """
    search_terms = []
    for term in terms:
        const = term.upper().replace(",", "").replace("'", "").replace(" ", "_")
        search_terms.append(term)
        search_terms.append(const)
        if "," in term:
            search_terms.append(term.split(",")[0])

    hit_lines = set()
    for i, line in enumerate(lines):
        low = line.lower()
        if any(t.lower() in low for t in search_terms):
            start = max(0, i - context_lines)
            end = min(len(lines), i + context_lines + 1)
            hit_lines.update(range(start, end))

    if not hit_lines:
        return ""

    sorted_hits = sorted(hit_lines)
    blocks = []
    block_start = prev = sorted_hits[0]
    for idx in sorted_hits[1:]:
        if idx > prev + 1:
            blocks.append((block_start, prev))
            block_start = idx
        prev = idx
    blocks.append((block_start, prev))

    parts = []
    for start, end in blocks:
        chunk = "".join(
            f"  {start + 1 + j:4d}: {lines[start + j]}"
            for j in range(end - start + 1)
        )
        parts.append(chunk)
    return "\n---\n".join(parts)


def grep_apl_context(apl_path: str, terms, context_lines: int = 25) -> str:
    """Multi-term grep over an APL file. Returns "" if missing or no hits."""
    if not apl_path or not os.path.exists(apl_path):
        return ""
    with open(apl_path, encoding="utf-8") as f:
        lines = f.readlines()
    return _grep_lines(lines, terms, context_lines)


def _cap_context(context: str):
    """Apply the grep-size cap (gotcha 5). Returns (context, num_ctx)."""
    num_ctx = 4096
    if len(context) > CONTEXT_SOFT_CAP:
        num_ctx = 8192
    if len(context) > CONTEXT_HARD_CAP:
        context = context[:CONTEXT_HARD_CAP] + "\n[... context truncated ...]"
    return context, num_ctx


def resolve_apl_path(basename: str) -> str:
    """Resolve an APL basename (e.g. 'boros_energy_match.py') under mtg-sim."""
    if os.path.isabs(basename) and os.path.exists(basename):
        return basename
    candidate = os.path.join(SIM_ROOT, "apl", os.path.basename(basename))
    if os.path.exists(candidate):
        return candidate
    # also try the literal relative path as given (e.g. 'apl/foo.py')
    rel = os.path.join(SIM_ROOT, basename)
    return rel if os.path.exists(rel) else candidate


# ---------------------------------------------------------------------------
# Prompt construction (plan D; mirrors verify_oracle.py:116-141)
# ---------------------------------------------------------------------------
_ANSWER_CONTRACT = (
    "Answer in exactly this format and nothing else:\n"
    "RESULT: PASS | FAIL\n"
    "REASON: [one sentence]\n"
)


def build_prompt(question: dict, context: str) -> str:
    qtype = question.get("type", "oracle_fidelity")
    label = question.get("card_or_deck", question.get("id", "?"))
    expected = question.get("expected", "")
    apl_name = question.get("_apl_display", "the APL")

    header = ("You are an expert MTG judge auditing an MTG simulation APL "
              "(Action Priority List) for DECISION QUALITY. You are strict: "
              "grade only what the code actually does.\n\n")

    if qtype == "oracle_fidelity":
        oracle = question.get("oracle_text") or _oracle_text(label)
        body = (
            f"CARD: {label}\n\n"
            f"ORACLE TEXT (verbatim):\n{oracle or '(oracle text unavailable)'}\n\n"
            f"RELEVANT APL CODE (from {apl_name}):\n{context}\n\n"
            f"EXPECTED: {expected}\n\n"
            "Task: does the APL implement this card faithfully to oracle text "
            "(mana cost, triggers, targets, restrictions, missing effects)?\n\n"
        )
    elif qtype == "strategic":
        body = (
            f"DECK: {label}\n\n"
            f"PRINCIPLE (playbook line): {question.get('principle', '')}\n\n"
            f"BOARD STATE: {question.get('board_state', '')}\n\n"
            f"RELEVANT APL CODE (from {apl_name}):\n{context}\n\n"
            f"EXPECTED: {expected}\n\n"
            "Task: does the APL's logic make the strategically correct decision "
            "for this board state and principle?\n\n"
        )
    elif qtype == "mulligan":
        body = (
            f"DECK: {label}\n\n"
            f"OPENING HAND: {question.get('hand', '')}\n"
            f"ON THE PLAY: {question.get('on_play', '')}\n"
            f"DECK ROLE: {question.get('role', '')}\n\n"
            "MULLIGAN GROUND TRUTH (2-1-2 rule): keep hands with >= 2 lands and "
            ">= 1 threat/relevant spell; mulligan land-light or land-flooded "
            "hands; accept weaker hands after 2 mulligans.\n\n"
            f"RELEVANT keep()/bottom() CODE (from {apl_name}):\n{context}\n\n"
            f"EXPECTED: {expected}\n\n"
            "Task: by INSPECTING the keep/bottom code (do NOT execute it), would "
            "this APL's logic reach the expected KEEP/MULLIGAN decision for this "
            "hand? Grade the code's logic, not a simulated run.\n\n"
        )
    else:
        body = (f"QUESTION: {label}\n\nAPL CODE:\n{context}\n\n"
                f"EXPECTED: {expected}\n\n")

    return header + body + _ANSWER_CONTRACT


# ---------------------------------------------------------------------------
# Output parsing (plan E -- regex over the whole response)
# ---------------------------------------------------------------------------
def parse_result(resp: str):
    """Return (result, reason). Unparseable -> ('FAIL', ...) per plan E."""
    if not resp:
        return "FAIL", "empty judge response"
    m = re.search(r"RESULT:\s*(PASS|FAIL)", resp, re.IGNORECASE)
    result = m.group(1).upper() if m else "FAIL"
    rm = re.search(r"REASON:\s*(.+)", resp, re.IGNORECASE)
    if rm:
        reason = rm.group(1).strip().splitlines()[0].strip()
    elif m:
        reason = "(no reason given)"
    else:
        reason = "unparseable judge response (treated as FAIL)"
    return result, reason


# ---------------------------------------------------------------------------
# The callable: grade one (question, APL) pair
# ---------------------------------------------------------------------------
def grade_apl(question: dict, apl_path: str = None, *, apl_code: str = None,
              model: str = DEFAULT_MODEL, llm=None,
              context_lines: int = 25) -> JudgeGrade:
    """Grade a single APL decision against one question. The core callable.

    question : dict conforming to the canonical schema (plan C). Must carry
        'type', 'grep_terms', and 'expected'.
    apl_path : path to the APL file to inspect. If omitted, resolved from the
        question's first target_apl, or supply apl_code directly.
    apl_code : in-memory APL source (string) to grep instead of a file -- used
        by the hermetic self-test.
    llm      : optional callable(prompt, model, num_ctx=...) -> str. If None,
        the module-level call_llm is looked up at call time (so monkeypatching
        apl_judge.call_llm in tests is honored).

    Returns a JudgeGrade. Never raises on an LLM/transport failure: a failed
    call yields a well-formed ERROR grade (fail-soft, spec).
    """
    qid = question.get("id", "?")
    qtype = question.get("type", "oracle_fidelity")
    terms = question.get("grep_terms") or []
    label = question.get("card_or_deck", qid)

    targets = question.get("target_apls") or []
    apl_display = (os.path.basename(apl_path) if apl_path
                   else (targets[0] if targets else "the APL"))
    question = dict(question)
    question["_apl_display"] = apl_display

    # Extract context (in-memory snippet wins; else grep the file).
    if apl_code is not None:
        context = _grep_lines(apl_code.splitlines(keepends=True), terms,
                              context_lines)
    else:
        if apl_path is None and targets:
            apl_path = resolve_apl_path(targets[0])
            apl_display = os.path.basename(apl_path)
            question["_apl_display"] = apl_display
        context = grep_apl_context(apl_path, terms, context_lines)

    def mk(result, reason, raw=""):
        return JudgeGrade(question_id=qid, apl=apl_display, type=qtype,
                          result=result, reason=reason, model=model, raw=raw,
                          card_or_deck=label)

    # Empty context -> the decision is absent. FAIL for should-be-present
    # oracle/strategic questions (gotcha 7); INCONCLUSIVE otherwise.
    if not context:
        if qtype in ("oracle_fidelity", "strategic"):
            return mk("FAIL", f"decision absent: '{', '.join(terms)}' not found "
                              f"in {apl_display}")
        return mk("INCONCLUSIVE", f"no keep/bottom context for terms "
                                  f"{terms} in {apl_display}")

    context, num_ctx = _cap_context(context)
    prompt = build_prompt(question, context)

    fn = llm if llm is not None else call_llm
    try:
        resp = fn(prompt, model, num_ctx=num_ctx)
    except TypeError:
        # injected fn with a simpler signature
        resp = fn(prompt)
    except LLMUnavailable as e:
        return mk("ERROR", f"LLM unavailable: {e}")
    except Exception as e:  # any unexpected transport error -> fail-soft
        return mk("ERROR", f"judge call failed: {e}")

    result, reason = parse_result(resp)
    return mk(result, reason, raw=resp)


# ---------------------------------------------------------------------------
# Scoring (plan F)
# ---------------------------------------------------------------------------
def applicable_questions(apl_basename: str, questions, category: str = None):
    base = os.path.basename(apl_basename)
    out = []
    for q in questions:
        targets = {os.path.basename(t) for t in (q.get("target_apls") or [])}
        if base not in targets:
            continue
        if category and q.get("type") != category:
            continue
        out.append(q)
    return out


def score_apl(apl_basename, questions, *, model=DEFAULT_MODEL, llm=None,
              category=None) -> dict:
    """Score one APL across its applicable questions. Returns a summary dict."""
    apl_path = resolve_apl_path(apl_basename)
    qs = applicable_questions(apl_basename, questions, category)
    grades = [grade_apl(q, apl_path, model=model, llm=llm) for q in qs]

    scored = [g for g in grades if g.counts_for_score]
    passed = sum(1 for g in scored if g.is_pass)
    errors = [g for g in grades if g.is_error]
    denom = len(scored)
    score = (passed / denom) if denom else None

    return {
        "apl": os.path.basename(apl_basename),
        "questions": len(qs),
        "scored": denom,
        "passed": passed,
        "failed": denom - passed,
        "errors": len(errors),
        "score": score,
        "passing": (score is not None and score >= PASS_THRESHOLD),
        "grades": grades,
    }


def run_calibration(fixtures, *, model=DEFAULT_MODEL, llm=None) -> dict:
    """Run the calibration gate: judge must agree with expected_result on 9/10.

    Each fixture embeds a self-contained code_snippet + expected_result
    (PASS/FAIL), so the judge reads the snippet, not a live APL (plan G).
    """
    rows = []
    agree = 0
    for fx in fixtures:
        q = {
            "id": fx.get("id", "?"),
            "type": fx.get("type", "oracle_fidelity"),
            "grep_terms": fx.get("grep_terms") or [fx.get("card_or_deck", "")],
            "card_or_deck": fx.get("card_or_deck", fx.get("id", "?")),
            "oracle_text": fx.get("oracle_text", ""),
            "board_state": fx.get("board_state", ""),
            "principle": fx.get("principle", ""),
            "hand": fx.get("hand", ""),
            "on_play": fx.get("on_play", ""),
            "role": fx.get("role", ""),
            "expected": fx.get("expected", ""),
            "target_apls": ["calibration_fixture"],
        }
        grade = grade_apl(q, apl_code=fx.get("code_snippet", ""), model=model,
                          llm=llm)
        expected = (fx.get("expected_result") or "").upper()
        matched = (grade.result == expected)
        if matched:
            agree += 1
        rows.append({"id": q["id"], "expected": expected,
                     "judged": grade.result, "agree": matched,
                     "reason": grade.reason})
    return {"agree": agree, "total": len(fixtures),
            "passing": agree >= 9, "rows": rows}


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_json(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        return data.get("questions") or data.get("fixtures") or []
    return data


# ---------------------------------------------------------------------------
# CLI scorer
# ---------------------------------------------------------------------------
def _cli(argv) -> int:
    import argparse
    p = argparse.ArgumentParser(
        description="LLM-as-judge APL decision-quality scorer")
    p.add_argument("--apl", help="APL basename to score (e.g. boros_energy_match.py)")
    p.add_argument("--category", choices=VALID_TYPES, help="restrict to one type")
    p.add_argument("--all-canonical", action="store_true",
                   help="score every APL referenced by the question set")
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--questions", default=DEFAULT_QUESTIONS)
    p.add_argument("--calibrate", action="store_true",
                   help="run the calibration gate (9/10) instead of scoring")
    p.add_argument("--calibration", default=DEFAULT_CALIBRATION)
    p.add_argument("--selftest", action="store_true", help="run self-test")
    args = p.parse_args(argv)

    if args.selftest:
        return 0 if _selftest() else 1

    if not check_llm_available(args.model):
        print(f"ERROR: Ollama/model '{args.model}' not reachable; "
              f"cannot grade. (exit 2)")
        return 2

    if args.calibrate:
        if not os.path.exists(args.calibration):
            print(f"ERROR: calibration file not found: {args.calibration}")
            return 2
        fixtures = load_json(args.calibration)
        res = run_calibration(fixtures, model=args.model)
        print(f"CALIBRATION  agree {res['agree']}/{res['total']}  "
              f"(gate: 9/10)")
        for r in res["rows"]:
            mark = "OK " if r["agree"] else "XX "
            print(f"  {mark} {r['id']:30s} expected {r['expected']:4s} "
                  f"judged {r['judged']:4s}")
        return 0 if res["passing"] else 1

    if not os.path.exists(args.questions):
        print(f"ERROR: question file not found: {args.questions}")
        return 2
    questions = load_json(args.questions)

    if args.apl:
        apls = [args.apl]
    elif args.all_canonical:
        apls = sorted({os.path.basename(t)
                       for q in questions for t in (q.get("target_apls") or [])})
    else:
        print("Specify --apl <basename>, --all-canonical, or --calibrate.")
        return 2

    worst_fail = False
    any_scored = False
    print(f"Thresholds: pass={PASS_THRESHOLD:.0%}  target={TARGET_THRESHOLD:.0%}"
          f"  hard-stop={HARD_STOP_THRESHOLD:.0%}  model={args.model}")
    print("-" * 64)
    for apl in apls:
        res = score_apl(apl, questions, model=args.model, category=args.category)
        for g in res["grades"]:
            print(f"  {g.result:12s} {g.question_id:30s} {g.reason}")
        if res["score"] is None:
            print(f"  >> {res['apl']}: no scorable questions "
                  f"({res['errors']} errors)")
            continue
        any_scored = True
        flag = "PASS" if res["passing"] else "FAIL"
        print(f"  >> {res['apl']}: {res['passed']}/{res['scored']} = "
              f"{res['score']:.0%}  [{flag}]  ({res['errors']} errors)")
        print("-" * 64)
        if not res["passing"]:
            worst_fail = True
    if not any_scored:
        return 2
    return 1 if worst_fail else 0


# ---------------------------------------------------------------------------
# Self-test (MOCKS the LLM; hermetic -- no Ollama, no JSON files, no CardDB)
# ---------------------------------------------------------------------------
def _selftest() -> bool:
    ok = True

    def check(name, cond):
        nonlocal ok
        print(f"  {'PASS' if cond else 'FAIL'}  {name}")
        if not cond:
            ok = False

    # A tiny in-memory APL snippet that mentions the card we grade.
    sample_apl = (
        "LIGHTNING_BOLT = \"Lightning Bolt\"\n"
        "\n"
        "def cast_lightning_bolt(self, gs, opp):\n"
        "    # Lightning Bolt deals 3 damage to any target.\n"
        "    target = self.best_creature_target(gs, opp)\n"
        "    if target is not None:\n"
        "        target.damage += 3\n"
        "    else:\n"
        "        opp.life -= 3\n"
    )

    sample_q = {
        "id": "oracle_lightning_bolt_dmg",
        "type": "oracle_fidelity",
        "target_apls": ["boros_energy_match.py"],
        "grep_terms": ["Lightning Bolt"],
        "card_or_deck": "Lightning Bolt",
        "oracle_text": "Lightning Bolt deals 3 damage to any target.",
        "expected": "PASS if the APL deals exactly 3 damage to a target.",
    }

    # --- Test 1: mocked LLM returns a clean PASS -> well-formed grade --------
    calls = {"n": 0, "saw_prompt": False}

    def fake_pass(prompt, model=DEFAULT_MODEL, num_ctx=4096):
        calls["n"] += 1
        calls["saw_prompt"] = "Lightning Bolt" in prompt and "RESULT:" in prompt
        return "Here is my analysis.\nRESULT: PASS\nREASON: deals 3 to target."

    g = grade_apl(sample_q, apl_code=sample_apl, llm=fake_pass)
    check("mock was actually invoked", calls["n"] == 1)
    check("prompt carried card + answer contract", calls["saw_prompt"])
    check("grade is a JudgeGrade", isinstance(g, JudgeGrade))
    check("result == PASS", g.result == "PASS")
    check("reason is non-empty", bool(g.reason))
    check("grade.question_id preserved", g.question_id == sample_q["id"])
    check("to_dict() is well-formed",
          set(("question_id", "result", "reason", "type", "apl"))
          <= set(g.to_dict().keys()))

    # --- Test 2: monkeypatch module-level call_llm (no injection) -----------
    # grade_apl looks up `call_llm` in THIS module's globals at call time, so
    # patch globals() directly -- robust whether the module runs as __main__
    # (bare `python apl_judge.py`) or is imported as apl_judge.
    _g = globals()
    orig = _g["call_llm"]
    try:
        patched = {"n": 0}

        def fake_fail(prompt, model=DEFAULT_MODEL, num_ctx=4096):
            patched["n"] += 1
            return "RESULT: FAIL\nREASON: deals 4 damage, oracle says 3."
        _g["call_llm"] = fake_fail
        g2 = grade_apl(sample_q, apl_code=sample_apl)  # no llm= -> uses global
        check("monkeypatched call_llm intercepted", patched["n"] == 1)
        check("result == FAIL via monkeypatch", g2.result == "FAIL")
    finally:
        _g["call_llm"] = orig

    # --- Test 3: LLM-unavailable path fails soft (no exception) -------------
    def fake_down(prompt, model=DEFAULT_MODEL, num_ctx=4096):
        raise LLMUnavailable("connection refused")

    try:
        g3 = grade_apl(sample_q, apl_code=sample_apl, llm=fake_down)
        threw = False
    except Exception:
        threw = True
    check("unavailable path did not raise", not threw)
    check("unavailable -> ERROR grade", g3.result == "ERROR")
    check("ERROR grade still well-formed", bool(g3.reason) and g3.is_error)
    check("ERROR excluded from score denominator", not g3.counts_for_score)

    # --- Test 4: unparseable response is treated as FAIL (plan E) -----------
    g4 = grade_apl(sample_q, apl_code=sample_apl,
                   llm=lambda *a, **k: "I cannot determine this.")
    check("unparseable -> FAIL", g4.result == "FAIL")

    # --- Test 5: empty grep context -> FAIL for oracle_fidelity (gotcha 7) ---
    g5 = grade_apl(sample_q, apl_code="def unrelated():\n    return 1\n",
                   llm=fake_pass)
    check("absent decision -> FAIL", g5.result == "FAIL")

    # --- Test 6: scoring aggregates correctly --------------------------------
    qs = [
        dict(sample_q, id="q_pass"),
        dict(sample_q, id="q_fail"),
        dict(sample_q, id="q_err"),
    ]
    seq = iter(["RESULT: PASS\nREASON: ok",
                "RESULT: FAIL\nREASON: no"])

    def scripted(prompt, model=DEFAULT_MODEL, num_ctx=4096):
        try:
            return next(seq)
        except StopIteration:
            raise LLMUnavailable("down")

    # grade against in-memory snippet by patching grep file read away:
    grades = []
    for q in qs:
        grades.append(grade_apl(q, apl_code=sample_apl, llm=scripted))
    scored = [g for g in grades if g.counts_for_score]
    passed = sum(1 for g in grades if g.is_pass)
    check("scoring: 2 scored / 1 error", len(scored) == 2 and
          sum(1 for g in grades if g.is_error) == 1)
    check("scoring: 1 pass of 2 scored = 50%", passed == 1)

    # --- Test 7: parse_result robustness ------------------------------------
    r, _ = parse_result("blah\n```\nRESULT: pass\nREASON: x\n```")
    check("parse_result case-insensitive + fenced", r == "PASS")

    print()
    if ok:
        print("ALL APL_JUDGE TESTS PASS")
    else:
        print("APL_JUDGE TESTS FAILED")
    return ok


def main():
    argv = sys.argv[1:]
    # Bare invocation runs the self-test so `python apl_judge.py` validates the
    # module (task requirement). Any flag routes to the CLI scorer.
    if not argv:
        sys.exit(0 if _selftest() else 1)
    sys.exit(_cli(argv))


if __name__ == "__main__":
    main()
