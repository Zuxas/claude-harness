"""Regression: the oracle gate must fail CLOSED when the model is unreachable
OR gives a cut-off / verdict-less answer -- never a silent PASS.

Before 2026-11-21, verify_card() returned True (PASS) on any ask_gemma
exception, so an Ollama outage silently passed every changed APL. These tests
pin the three-state contract (PASS/FAIL/UNAVAILABLE) and the batch precedence.

#74 section 3B: ask_gemma now returns (text, done_reason), and classify_verdict
decides the bucket. A cut-off answer (done_reason == "length") with no verdict
is UNAVAILABLE ("could not verify"), not a false FAIL.

Run: python -m pytest scripts/test_verify_oracle.py
"""
import urllib.error

import pytest

import verify_oracle as v


@pytest.fixture
def stub_card(monkeypatch):
    """Let verify_card reach the ask_gemma call with no DB or APL file present."""
    monkeypatch.setattr(v, "get_oracle_text", lambda name: "Deal 2 damage.")
    monkeypatch.setattr(v, "grep_apl_context", lambda path, name: "  12: cast()")
    monkeypatch.setattr(v, "grep_handler_context", lambda name: "")


def _gemma(monkeypatch, fn):
    monkeypatch.setattr(v, "ask_gemma", fn)


# ---- verify_card three-state contract (ask_gemma now returns a tuple) ------

def test_pass(stub_card, monkeypatch):
    _gemma(monkeypatch, lambda prompt: ("RESULT: PASS", "stop"))
    assert v.verify_card("X", "f.py", verbose=False) == v.PASS


def test_discrepancy_is_fail(stub_card, monkeypatch):
    _gemma(monkeypatch, lambda prompt: ("RESULT: FAIL\n- oracle vs apl", "stop"))
    assert v.verify_card("X", "f.py", verbose=False) == v.FAIL


def test_model_down_is_unavailable_not_pass(stub_card, monkeypatch):
    def boom(prompt):
        raise urllib.error.URLError(ConnectionRefusedError(111, "refused"))
    _gemma(monkeypatch, boom)
    assert v.verify_card("X", "f.py", verbose=False) == v.UNAVAILABLE


def test_empty_response_is_unavailable(stub_card, monkeypatch):
    _gemma(monkeypatch, lambda prompt: ("   ", "stop"))
    assert v.verify_card("X", "f.py", verbose=False) == v.UNAVAILABLE


def test_cutoff_without_verdict_is_unavailable_not_fail(stub_card, monkeypatch):
    # The core #74-3B case: the model rambled and hit the token cap before it
    # wrote a verdict. That is "could not verify", not a discrepancy.
    _gemma(monkeypatch, lambda prompt: ("The card deals damage and the engine", "length"))
    assert v.verify_card("X", "f.py", verbose=False) == v.UNAVAILABLE


# ---- classify_verdict (pure) ----------------------------------------------

def test_classify_clear_pass():
    assert v.classify_verdict("RESULT: PASS\nDISCREPANCIES: None", "stop") == v.PASS


def test_classify_clear_fail():
    assert v.classify_verdict("RESULT: FAIL\n- oracle X vs apl Y", "stop") == v.FAIL


def test_classify_empty_is_unavailable():
    assert v.classify_verdict("", "length") == v.UNAVAILABLE
    assert v.classify_verdict("   ", "stop") == v.UNAVAILABLE


def test_classify_cutoff_no_verdict_is_unavailable():
    assert v.classify_verdict("The APL casts it and the handler deals", "length") == v.UNAVAILABLE


def test_classify_cutoff_after_verdict_keeps_verdict():
    # Verdict comes first; truncation AFTER it does not change a stated FAIL.
    assert v.classify_verdict("RESULT: FAIL\n- oracle says destroy but the APL only ta", "length") == v.FAIL


def test_classify_malformed_but_complete_stays_fail():
    # A finished answer that ignored the format still gets a human's eyes.
    assert v.classify_verdict("I think this looks fine honestly", "stop") == v.FAIL


def test_classify_preamble_before_verdict_is_pass():
    # A verdict past the first 50 chars used to be mis-scored FAIL.
    long = "Okay, let me carefully work through the oracle text and the handler. " * 2
    assert v.classify_verdict(long + "RESULT: PASS", "stop") == v.PASS


# ---- batch precedence (unchanged) -----------------------------------------

def test_batch_exit_precedence():
    assert v.batch_exit_code([v.PASS, v.PASS]) == 0           # all pass
    assert v.batch_exit_code([v.PASS, v.UNAVAILABLE]) == 2    # unavailable only
    assert v.batch_exit_code([v.PASS, v.FAIL]) == 1           # discrepancy only
    # A real FAIL seen before the model went down must still exit 1.
    assert v.batch_exit_code([v.FAIL, v.UNAVAILABLE]) == 1
