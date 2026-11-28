"""Validation must come from the real smoke gate, and the registry must carry
the smoke avg KILL turn (#18).

- A generated APL that fails smoke (not registered) is never counted validated.
- The registry's smoke_avg_turns reads avg_kill_turn, not the nonexistent
  avg_turns key (which always stored null).

Run: python agents/scripts/test_validate_smoke.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import auto_pipeline as ap


# ---- registry entry carries the smoke avg kill turn ----

def test_registry_entry_uses_avg_kill_turn():
    smoke = {"class_name": "JeskaiPheliaAPL", "avg_kill_turn": 7.25,
             "avg_turns": 999}  # the stale key must be IGNORED
    e = ap._build_registry_entry("Jeskai Phelia", "standard", smoke)
    assert e["smoke_avg_turns"] == 7.25, "smoke_avg_turns must read avg_kill_turn, not avg_turns"
    assert e["module"] == "apl.auto_apls.jeskai_phelia"
    assert e["class"] == "JeskaiPheliaAPL"
    assert e["deck_file"] == "decks/auto/jeskai_phelia_standard.txt"


def test_registry_entry_none_when_no_kill_turn():
    # A 0-win smoke has avg_kill_turn None; the field reflects that, not a crash.
    e = ap._build_registry_entry("X", "modern", {"class_name": "XAPL", "avg_kill_turn": None})
    assert e["smoke_avg_turns"] is None


# ---- validated count comes from the smoke gate ----

def test_failed_smoke_is_not_counted_validated():
    flow = [
        {"deck": "A", "smoke": "pass", "registered": True},
        {"deck": "B", "smoke": "crash", "registered": False},   # SyntaxError APL
        {"deck": "C", "status": "no_apl_file"},
        {"deck": "D", "smoke": "pass", "registered": True},
    ]
    assert ap._count_validated(flow) == 2


def test_zero_when_nothing_registered():
    assert ap._count_validated([{"registered": False}, {"status": "no_deck_data"}]) == 0
    assert ap._count_validated([]) == 0


# ---- the broken legacy function is gone ----

def test_validate_apl_removed():
    assert not hasattr(ap, "validate_apl"), "the legacy apl_tuner-shelling validate_apl must be gone"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"  ok  {name}")
    print("test_validate_smoke: OK")
