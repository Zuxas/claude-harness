"""Pins the grind-all.ps1 stop-logic fix (#12).

CI has no pwsh, so this is a source-scan guard (same approach the repo uses for
its other shell/script checks). The behavioural proof lives in the PR: a real
pwsh `-Duration 2` run stopped at ~121s with all 9 decks grinding and every
grinder call carrying --duration, zero --until.

The bug: stopDT was rebuilt per deck from today's HH:mm and rolled to "tomorrow"
whenever it was already past, so the reached-check could never be true; and the
same wall-clock --until was forwarded to every grinder call, so the first deck
ate the whole window.
"""
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "grind-all.ps1"
SRC = SCRIPT.read_text(encoding="utf-8")


def test_grinder_gets_duration_not_wall_clock_until():
    # The grinder is handed a per-deck minute budget, never a wall-clock --until.
    assert '"--duration"' in SRC, "grinder should receive --duration"
    assert '@("--until"' not in SRC, "grinder must no longer receive a wall-clock --until"


def test_stop_time_computed_once_before_the_loop():
    # Exactly one roll-to-tomorrow, and it sits before the deck loop, not inside it.
    assert SRC.count("AddDays(1)") == 1, "stop time should roll forward at most once"
    roll = SRC.index("AddDays(1)")
    loop = SRC.index("while ($keepGoing)")
    assert roll < loop, "stop time must be computed before the grinding loop"


def test_per_deck_budget_splits_the_window():
    assert "$deckBudget" in SRC, "each deck needs a bounded budget so one can't take the whole window"
    assert "$remaining -le 0" in SRC, "loop must exit once the window is used up"
