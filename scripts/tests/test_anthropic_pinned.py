"""The optional anthropic SDK dependency must stay pinned (#43).

An autonomous nightly pipeline shouldn't inherit a breaking SDK major bump on a
dep reinstall. The dependency is optional (the pipeline degrades to Gemma without
it), so the line stays commented, but it must carry an == pin, not a bare name.
"""
import re
from pathlib import Path

REQ = (Path(__file__).resolve().parents[2] / "requirements.txt").read_text(encoding="utf-8")


def test_anthropic_is_version_pinned():
    # Find the anthropic requirement line (commented-optional is fine).
    lines = [ln.strip().lstrip("#").strip() for ln in REQ.splitlines()
             if re.match(r"^#?\s*anthropic\b", ln.strip())]
    assert lines, "no anthropic line found in requirements.txt"
    assert any(re.match(r"^anthropic==\d+\.\d+", ln) for ln in lines), \
        f"anthropic must be == pinned, got: {lines}"
