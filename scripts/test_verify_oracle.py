"""Regression: the oracle gate must fail CLOSED when the model is unreachable.

Before 2026-11-21, verify_card() returned True (PASS) on any ask_gemma
exception, so an Ollama outage silently passed every changed APL. These tests
pin the three-state contract (PASS/FAIL/UNAVAILABLE) and the batch precedence:
a real FAIL is never masked by a later UNAVAILABLE.

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


def _gemma(monkeypatch, fn):
    monkeypatch.setattr(v, "ask_gemma", fn)


def test_pass(stub_card, monkeypatch):
    _gemma(monkeypatch, lambda prompt: "RESULT: PASS")
    assert v.verify_card("X", "f.py", verbose=False) == v.PASS


def test_discrepancy_is_fail(stub_card, monkeypatch):
    _gemma(monkeypatch, lambda prompt: "RESULT: FAIL\n- oracle vs apl")
    assert v.verify_card("X", "f.py", verbose=False) == v.FAIL


def test_model_down_is_unavailable_not_pass(stub_card, monkeypatch):
    def boom(prompt):
        raise urllib.error.URLError(ConnectionRefusedError(111, "refused"))
    _gemma(monkeypatch, boom)
    assert v.verify_card("X", "f.py", verbose=False) == v.UNAVAILABLE


def test_empty_response_is_unavailable(stub_card, monkeypatch):
    _gemma(monkeypatch, lambda prompt: "   ")
    assert v.verify_card("X", "f.py", verbose=False) == v.UNAVAILABLE


def test_batch_exit_precedence():
    assert v.batch_exit_code([v.PASS, v.PASS]) == 0           # all pass
    assert v.batch_exit_code([v.PASS, v.UNAVAILABLE]) == 2    # unavailable only
    assert v.batch_exit_code([v.PASS, v.FAIL]) == 1           # discrepancy only
    # Mixed: a real FAIL seen before the model went down must still exit 1,
    # not be masked by the later UNAVAILABLE.
    assert v.batch_exit_code([v.FAIL, v.UNAVAILABLE]) == 1
