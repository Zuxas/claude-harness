"""The optimizer report path must include the format (#45).

The same deck name exists in several formats. Before the fix the report path was
`apl-opt-{deck}-{date}.md` with no format, so optimizing the same deck in two
formats on one day overwrote the first report. The path now carries the format.
"""
import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "agents" / "scripts"))

opt = importlib.import_module("apl_optimizer")

BASELINE = {"avg_kill": 7.0, "win_rate": 0.55, "fastest": 5}


def _write(tmp, deck, fmt):
    opt.write_report(deck, fmt, BASELINE, [], None, 1.0)
    return sorted(p.name for p in (tmp / "knowledge" / "mtg").glob("*.md"))


def test_two_formats_same_deck_do_not_collide(tmp_path, monkeypatch):
    monkeypatch.setattr(opt, "HARNESS_ROOT", tmp_path)
    (tmp_path / "knowledge" / "mtg").mkdir(parents=True)

    _write(tmp_path, "Mono Red Aggro", "modern")
    names = _write(tmp_path, "Mono Red Aggro", "standard")

    # Two distinct reports, not one overwritten file.
    assert len(names) == 2, f"formats collided into {names}"
    assert any("modern" in n for n in names) and any("standard" in n for n in names)
    assert all(n.startswith("apl-opt-mono-red-aggro-") for n in names)
