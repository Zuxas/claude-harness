"""
eval_harness.py -- Anthropic-authoritative LLM-judge scorer (evalite slice)

Implements Step 4 of harness/specs/2026-06-29-evalite-eval-harness.md: the
`make_anthropic_llm` transport callable + the `anthropic_judge` scorer. It
EXTENDS apl_judge through its already-present `llm=` injection seam -- it does
NOT fork or edit apl_judge (spec Gate 5.2). Every bit of grading logic
(build_prompt, parse_result, score_apl, JudgeGrade, run_calibration) is reused
verbatim; only the transport differs.

Two-tier judging (spec section 3.3):
  * gemma4 via Ollama (apl_judge's default `call_llm`) stays the CHEAP LOCAL
    PRE-FILTER -- untouched, still the default of apl_judge.
  * Anthropic `claude-opus-4-8` is the AUTHORITATIVE scorer -- a different
    `llm=` callable built here.

Deferred (spec Steps 1-3, 6, per its Do/Defer): the full evalite skeleton
(EvalCase / winrate_over_N / JSONL trace / CI mean-gate). This file is the
Anthropic-judge half only -- the piece the SDK install unblocks.

Auth precedence (task): Claude Code OAuth at ~/.claude/.credentials.json
(sent as `Authorization: Bearer` + the `anthropic-beta: oauth-2025-04-20`
header), else `ANTHROPIC_API_KEY`. On any auth/transport failure the callable
raises apl_judge.LLMUnavailable, so grade_apl yields a well-formed ERROR grade
(excluded from the score denominator) rather than crashing -- fail-soft, and a
blocked live call is an acceptable, reported outcome (never a retry-loop).

Usage
-----
    python eval_harness.py                 # hermetic self-test (no network)
    python eval_harness.py --selftest      # same
    python eval_harness.py --live          # ONE real Anthropic call on a
                                           #   calibration fixture (may be
                                           #   auth-blocked -> reported)

Public API
----------
    make_anthropic_llm(model=..., ...) -> callable(prompt, model, num_ctx=...)
    anthropic_judge(question, apl_path=None, *, apl_code=None, llm=None) -> ScoreResult
    two_stage_judge(question, ...) -> ScoreResult   # gemma4 pre-filter + Anthropic authoritative
    ScoreResult (dataclass)
"""

import os
import sys
import json
import time
from dataclasses import dataclass, field
from typing import Optional

# --- import the thing we EXTEND (never edit) -------------------------------
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)
import apl_judge  # noqa: E402  (grade_apl, JudgeGrade, LLMUnavailable, load_json, ...)

# Anthropic model + judging knobs. claude-opus-4-8: adaptive thinking only;
# budget_tokens/temperature/top_p are REMOVED (400). effort "low" + a generous
# max_tokens keep the "RESULT: PASS|FAIL" answer contract from truncating under
# adaptive thinking's shared budget (spec gotcha 9).
ANTHROPIC_MODEL = "claude-opus-4-8"
DEFAULT_MAX_TOKENS = 2048
DEFAULT_EFFORT = "low"

_CREDENTIALS_PATH = os.path.join(os.path.expanduser("~"), ".claude", ".credentials.json")


# ---------------------------------------------------------------------------
# Score shape (spec 3.1). PASS->1.0, FAIL->0.0, ERROR/INCONCLUSIVE->None
# (None excluded from the mean, mirroring JudgeGrade.counts_for_score).
# ---------------------------------------------------------------------------
@dataclass
class ScoreResult:
    score: Optional[float]        # 0..1, or None to exclude from the mean
    metadata: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Auth resolution -- lazy; importing this module never contacts anything.
# ---------------------------------------------------------------------------
def _resolve_anthropic_client():
    """Return (client, auth_source). Raises apl_judge.LLMUnavailable with an
    exact, actionable blocker when no credential resolves or the token is
    expired. OAuth wins; ANTHROPIC_API_KEY is the fallback.
    """
    try:
        import anthropic  # local import: no socket on module import
    except Exception as e:  # pragma: no cover
        raise apl_judge.LLMUnavailable(f"anthropic SDK not importable: {e}")

    # 1. Claude Code OAuth (Bearer token + required oauth beta header).
    if os.path.exists(_CREDENTIALS_PATH):
        try:
            creds = json.loads(open(_CREDENTIALS_PATH, encoding="utf-8").read())
            oauth = creds.get("claudeAiOauth") or {}
            token = oauth.get("accessToken")
        except Exception as e:
            token, oauth = None, {}
            _last_oauth_err = e
        else:
            _last_oauth_err = None
        if token:
            expires = oauth.get("expiresAt")
            # expiresAt is epoch-ms in Claude Code creds.
            if isinstance(expires, (int, float)) and expires > 1e12 and (time.time() * 1000) > expires:
                raise apl_judge.LLMUnavailable(
                    f"Claude Code OAuth token expired at epoch-ms {int(expires)} "
                    f"(now {int(time.time() * 1000)}); run a Claude Code login to refresh")
            # auth_token -> Authorization: Bearer; oauth beta header required on /v1/messages.
            # Do NOT also let ANTHROPIC_API_KEY ride along (both -> 401).
            client = anthropic.Anthropic(
                auth_token=token,
                api_key=None,
                default_headers={"anthropic-beta": "oauth-2025-04-20"},
            )
            return client, "oauth(~/.claude/.credentials.json)"
        elif _last_oauth_err is not None:
            # creds file present but unreadable -- fall through to API key.
            pass

    # 2. ANTHROPIC_API_KEY.
    if os.environ.get("ANTHROPIC_API_KEY"):
        return anthropic.Anthropic(), "ANTHROPIC_API_KEY"

    raise apl_judge.LLMUnavailable(
        "no Anthropic credentials resolved: no readable claudeAiOauth.accessToken in "
        f"{_CREDENTIALS_PATH} and ANTHROPIC_API_KEY is unset")


# ---------------------------------------------------------------------------
# The transport callable -- matches apl_judge's `llm=` contract:
#   fn(prompt, model, num_ctx=...) -> str
# grade_apl calls it as fn(prompt, model, num_ctx=num_ctx). We IGNORE the
# positional model (it arrives as "gemma4"/"claude-opus-4-8" from grade_apl)
# and use the baked-in Anthropic model (spec gotcha 8, both halves: we also
# pass model=ANTHROPIC_MODEL into grade_apl so JudgeGrade.model is stamped).
# ---------------------------------------------------------------------------
def make_anthropic_llm(model: str = ANTHROPIC_MODEL,
                       max_tokens: int = DEFAULT_MAX_TOKENS,
                       effort: str = DEFAULT_EFFORT):
    """Build a guarded, lazy Anthropic `llm=` callable for apl_judge.grade_apl.

    The client is resolved on first call and cached. Any auth/transport error,
    or a missing/empty text block, raises apl_judge.LLMUnavailable so grade_apl
    returns a fail-soft ERROR grade instead of crashing or scoring a spurious
    FAIL.
    """
    state = {"client": None, "auth": None}

    def _call(prompt, _model=None, num_ctx=None, **_kw):
        if state["client"] is None:
            state["client"], state["auth"] = _resolve_anthropic_client()
        client = state["client"]
        try:
            msg = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                thinking={"type": "adaptive"},
                output_config={"effort": effort},
                messages=[{"role": "user", "content": prompt}],
            )
        except apl_judge.LLMUnavailable:
            raise
        except Exception as e:
            raise apl_judge.LLMUnavailable(
                f"Anthropic call failed ({type(e).__name__}): {e}")

        # Response is typically [thinking(empty text), text]. Pull the text.
        text = None
        for block in getattr(msg, "content", []) or []:
            if getattr(block, "type", None) == "text":
                text = getattr(block, "text", "") or ""
                if text.strip():
                    break
        if not text or not text.strip():
            raise apl_judge.LLMUnavailable(
                "Anthropic response carried no non-empty text block "
                f"(stop_reason={getattr(msg, 'stop_reason', '?')})")
        return text.strip()

    _call.auth_source = lambda: state["auth"]
    _call.anthropic_model = model
    return _call


# ---------------------------------------------------------------------------
# The scorer (spec 3.3). Reuses grade_apl UNCHANGED via llm=.
# ---------------------------------------------------------------------------
def anthropic_judge(question: dict, apl_path: str = None, *, apl_code: str = None,
                    llm=None, model: str = ANTHROPIC_MODEL) -> ScoreResult:
    """Authoritative Anthropic LLM-judge scorer.

    PASS -> 1.0, FAIL -> 0.0, ERROR/INCONCLUSIVE -> None (excluded from mean).
    """
    llm = llm if llm is not None else make_anthropic_llm(model=model)
    grade = apl_judge.grade_apl(question, apl_path, apl_code=apl_code,
                                model=model, llm=llm)
    if not grade.counts_for_score:
        return ScoreResult(None, {"result": grade.result, "reason": grade.reason,
                                  **grade.to_dict()})
    return ScoreResult(1.0 if grade.is_pass else 0.0, grade.to_dict())


def two_stage_judge(question: dict, apl_path: str = None, *, apl_code: str = None,
                    gemma_model: str = apl_judge.DEFAULT_MODEL,
                    anthropic_model: str = ANTHROPIC_MODEL) -> ScoreResult:
    """gemma4 CHEAP LOCAL PRE-FILTER + Anthropic AUTHORITATIVE verdict.

    Runs the existing apl_judge gemma4 path (advisory) then the Anthropic judge
    (authoritative). The returned score is Anthropic's; the gemma4 verdict is
    attached as metadata['prefilter']. Keeps gemma4 in the loop exactly as the
    spec intends -- both are just different `llm=` callables.
    """
    pre = apl_judge.grade_apl(question, apl_path, apl_code=apl_code, model=gemma_model)
    result = anthropic_judge(question, apl_path, apl_code=apl_code, model=anthropic_model)
    result.metadata["prefilter"] = {"model": gemma_model, "result": pre.result,
                                    "reason": pre.reason}
    return result


# ---------------------------------------------------------------------------
# Calibration-fixture helpers (for the live one-sample verify path).
# ---------------------------------------------------------------------------
def _fixture_to_question(fx: dict) -> dict:
    """Map a calibration fixture to an apl_judge question dict (same shaping
    apl_judge.run_calibration uses)."""
    return {
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


# ---------------------------------------------------------------------------
# Hermetic self-test -- proves the scorer wiring WITHOUT any network. This is
# the DONE/PARTIAL discriminator's "wiring landed" half.
# ---------------------------------------------------------------------------
def _selftest() -> bool:
    ok = True

    def check(name, cond):
        nonlocal ok
        print(f"  {'PASS' if cond else 'FAIL'}  {name}")
        if not cond:
            ok = False

    sample_apl = (
        "LIGHTNING_BOLT = \"Lightning Bolt\"\n\n"
        "def cast_lightning_bolt(self, gs, opp):\n"
        "    # Lightning Bolt deals 3 damage to any target.\n"
        "    self.best_target(gs, opp).take_damage(3)\n"
    )
    q = {
        "id": "st_bolt", "type": "oracle_fidelity",
        "target_apls": ["calibration_fixture"], "grep_terms": ["Lightning Bolt"],
        "card_or_deck": "Lightning Bolt",
        "oracle_text": "Lightning Bolt deals 3 damage to any target.",
        "expected": "PASS if it deals exactly 3 damage to a target.",
    }

    # 1. injected fake PASS -> score 1.0, model stamped to the Anthropic id.
    def fake_pass(prompt, model=None, num_ctx=4096):
        return "RESULT: PASS\nREASON: deals 3 to target."
    r = anthropic_judge(q, apl_code=sample_apl, llm=fake_pass)
    check("PASS -> score 1.0", r.score == 1.0)
    check("metadata carries JudgeGrade dict", r.metadata.get("result") == "PASS")
    check("model stamped claude-opus-4-8 (gotcha 8)",
          r.metadata.get("model") == ANTHROPIC_MODEL)

    # 2. injected fake FAIL -> score 0.0.
    def fake_fail(prompt, model=None, num_ctx=4096):
        return "RESULT: FAIL\nREASON: deals 4, oracle says 3."
    r2 = anthropic_judge(q, apl_code=sample_apl, llm=fake_fail)
    check("FAIL -> score 0.0", r2.score == 0.0)

    # 3. transport down -> ERROR grade -> score None (excluded from mean).
    def fake_down(prompt, model=None, num_ctx=4096):
        raise apl_judge.LLMUnavailable("auth blocked")
    r3 = anthropic_judge(q, apl_code=sample_apl, llm=fake_down)
    check("transport down -> score None (excluded)", r3.score is None)
    check("ERROR reason surfaced", "auth blocked" in (r3.metadata.get("reason") or ""))

    # 4. empty/absent text block -> LLMUnavailable (no spurious FAIL).
    class _Blk:
        type = "thinking"; thinking = ""
    class _Msg:
        content = [_Blk()]; stop_reason = "end_turn"
    class _FakeClient:
        class messages:
            @staticmethod
            def create(**kw):
                return _Msg()

    def llm_empty(prompt, model=None, num_ctx=4096):
        # emulate make_anthropic_llm's extraction against an empty-text response
        m = _FakeClient.messages.create()
        text = None
        for b in m.content:
            if getattr(b, "type", None) == "text":
                text = getattr(b, "text", "")
        if not text or not text.strip():
            raise apl_judge.LLMUnavailable("no text block")
        return text
    r4 = anthropic_judge(q, apl_code=sample_apl, llm=llm_empty)
    check("empty text block -> score None (no spurious FAIL)", r4.score is None)

    # 5. make_anthropic_llm ignores the positional model arg (gotcha 8 half 1).
    captured = {}
    real = make_anthropic_llm(model="claude-opus-4-8")
    # We can't call the real transport hermetically, but we can assert the
    # baked-in model attribute is the Anthropic id, not gemma4.
    check("baked-in model is claude-opus-4-8", real.anthropic_model == "claude-opus-4-8")

    print()
    print("ALL EVAL_HARNESS TESTS PASS" if ok else "EVAL_HARNESS TESTS FAILED")
    return ok


# ---------------------------------------------------------------------------
# Live one-sample verify -- the smallest path that exercises a REAL Anthropic
# call. Auth-blocked is acceptable and reported (no retry-loop).
# ---------------------------------------------------------------------------
def _live_one_sample(fixture_id: str = None) -> int:
    cal_path = apl_judge.DEFAULT_CALIBRATION
    if not os.path.exists(cal_path):
        print(f"ERROR: calibration file not found: {cal_path}")
        return 2
    fixtures = apl_judge.load_json(cal_path)
    fx = None
    if fixture_id:
        fx = next((f for f in fixtures if f.get("id") == fixture_id), None)
    if fx is None:
        fx = fixtures[0]

    q = _fixture_to_question(fx)
    llm = make_anthropic_llm()
    print(f"LIVE Anthropic judge -- ONE sample: {fx.get('id')} "
          f"(expected {fx.get('expected_result')})")
    print(f"  model={ANTHROPIC_MODEL}  effort={DEFAULT_EFFORT}  max_tokens={DEFAULT_MAX_TOKENS}")
    result = anthropic_judge(q, apl_code=fx.get("code_snippet", ""), llm=llm)
    auth = llm.auth_source()
    print(f"  auth_source: {auth}")
    if result.score is None:
        print(f"  OUTCOME: no score (grade={result.metadata.get('result')})")
        print(f"  BLOCKER: {result.metadata.get('reason')}")
        print("  -> live call did NOT complete; wiring is landed, gate is auth-blocked (PARTIAL)")
        return 3
    verdict = result.metadata.get("result")
    agrees = verdict == (fx.get("expected_result") or "").upper()
    print(f"  OUTCOME: live call SUCCEEDED -> {verdict} (score={result.score}) "
          f"| agrees_with_fixture={agrees}")
    print(f"  reason: {result.metadata.get('reason')}")
    print("  -> live Anthropic call completed (DONE)")
    return 0


def main():
    argv = sys.argv[1:]
    if "--live" in argv:
        fid = None
        if "--fixture" in argv:
            i = argv.index("--fixture")
            if i + 1 < len(argv):
                fid = argv[i + 1]
        sys.exit(_live_one_sample(fid))
    # default / --selftest: hermetic
    sys.exit(0 if _selftest() else 1)


if __name__ == "__main__":
    main()
