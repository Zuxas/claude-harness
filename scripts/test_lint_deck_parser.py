"""The lint deck parser must split main/side like the real loader (#19).

The old parser flipped to the sideboard at the first blank line once any card
was in the mainboard, so a sectioned list (// CREATURES, blank, // LANDS, ...)
was mis-split (e.g. 8 main / 67 side). It must instead match
mtg-sim data/deck.py::_parse_decklist: an explicit 'Sideboard' line, or a blank
line only after 50+ mainboard cards.

Run: python -m pytest scripts/test_lint_deck_parser.py
"""
import importlib.util
import sys
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "lintmtgsim", str(Path(__file__).with_name("lint-mtg-sim.py")))
lint = importlib.util.module_from_spec(_SPEC)
sys.modules["lintmtgsim"] = lint          # dataclass needs the module registered
_SPEC.loader.exec_module(lint)


def _counts(tmp_path, text):
    f = tmp_path / "deck.txt"
    f.write_text(text, encoding="utf-8")
    mb, sb = lint._parse_deck_file(f)
    return len(mb), len(sb)


def test_sectioned_mainboard_is_not_split_by_blank_lines(tmp_path):
    text = (
        "// CREATURES (24)\n"
        "4 Ragavan\n4 Goblin Guide\n4 Monastery Swiftspear\n4 Soul-Scar Mage\n"
        "4 Eidolon of the Great Revel\n4 Bonecrusher Giant\n"
        "\n"
        "// BURN (16)\n"
        "4 Lightning Bolt\n4 Lava Spike\n4 Rift Bolt\n4 Skewer the Critics\n"
        "\n"
        "// LANDS (20)\n"
        "10 Mountain\n4 Sunbaked Canyon\n4 Inspiring Vantage\n2 Ramunap Ruins\n"
        "\n"
        "Sideboard\n"
        "3 Smash to Smithereens\n3 Deflecting Palm\n3 Searing Blaze\n"
        "3 Kor Firewalker\n3 Path to Exile\n"
    )
    assert _counts(tmp_path, text) == (60, 15)


def test_blank_line_after_60_is_the_sideboard_break(tmp_path):
    main = "".join(f"1 Card{i}\n" for i in range(60))
    side = "".join(f"1 SB{i}\n" for i in range(15))
    assert _counts(tmp_path, main + "\n" + side) == (60, 15)


def test_explicit_sideboard_header(tmp_path):
    main = "".join(f"1 Card{i}\n" for i in range(60))
    assert _counts(tmp_path, main + "Sideboard\n2 X\n2 Y\n") == (60, 4)


def test_early_blank_line_does_not_start_sideboard(tmp_path):
    # Fewer than 50 cards before the blank -> still mainboard (section break).
    text = "// A\n4 Alpha\n4 Beta\n\n// B\n4 Gamma\n"
    assert _counts(tmp_path, text) == (12, 0)


def test_bare_name_line_is_skipped_like_the_real_parser(tmp_path):
    # Only "<int> <name>" lines count; a bare name is not a 1-of.
    text = "4 Ragavan\nLightning Bolt\n2 Mountain\n"
    assert _counts(tmp_path, text) == (6, 0)


if __name__ == "__main__":
    import tempfile
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            with tempfile.TemporaryDirectory() as d:
                fn(Path(d))
            print(f"  ok  {name}")
    print("test_lint_deck_parser: OK")
