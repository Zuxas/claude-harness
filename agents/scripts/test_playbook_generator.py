"""Regression: the generator must never write into the website (2026-10-11 overwrite)."""
import pytest

import playbook_generator as pg

STUB = '<html><head><meta http-equiv="refresh" content="0; url=x"></head></html>'


@pytest.fixture
def tree(tmp_path, monkeypatch):
    kb, site, drafts = tmp_path / "kb", tmp_path / "site", tmp_path / "drafts"
    kb.mkdir()
    (kb / "sim-std-deck.md").write_text("Avg Kill Turn: 5.0\n")
    (kb / "sim-mod-deck.md").write_text("Avg Kill Turn: 4.0\n")
    (kb / "sim-orphan.md").write_text("Avg Kill Turn: 6.0\n")
    (kb / "tune-std-deck-2026-10-01.md").write_text("Format: standard\nvs Foo: 55.0%\n")
    (site / "modern").mkdir(parents=True)
    (site / "modern" / "mod-deck-playbook.html").write_text(STUB)      # redirect stub only
    (site / "archive" / "2026" / "modern").mkdir(parents=True)
    (site / "archive" / "2026" / "modern" / "mod-deck-playbook.html").write_text(
        '<span class="hs-label">Role</span> <span class="hs-val">combo</span>')
    for name, val in [("KNOWLEDGE_DIR", kb), ("WEBSITE_DIR", site), ("DRAFTS_DIR", drafts)]:
        monkeypatch.setattr(pg, name, val)
    return site, drafts


def run_all(fmt):
    return {r["deck"]: r for r in (pg.generate_playbook(pg.slug_to_title(s), fmt,
            require_format_evidence=True) for s in pg.discover_decks_with_data(fmt))}


def test_all_writes_only_drafts_in_the_right_format(tree):
    site, drafts = tree
    before = sorted(p.read_bytes() for p in site.rglob("*.html"))
    std, mod = run_all("standard"), run_all("modern")
    assert std["Std Deck"]["status"] == "written" and mod["Std Deck"]["status"] == "skipped"
    assert mod["Mod Deck"]["status"] == "written" and std["Mod Deck"]["status"] == "skipped"
    assert mod["Orphan"]["status"] == "skipped"                        # no format evidence
    assert sorted(p.read_bytes() for p in site.rglob("*.html")) == before  # site untouched
    assert {p.relative_to(drafts).as_posix() for p in drafts.rglob("*.html")} == {
        "standard/std-deck-playbook.html", "modern/mod-deck-playbook.html"}


def test_archived_page_beats_stub_and_drafts_are_not_clobbered(tree):
    site, drafts = tree
    assert "archive" in str(pg.find_existing_playbook("mod-deck", "modern"))
    run_all("modern")
    draft = drafts / "modern" / "mod-deck-playbook.html"
    draft.write_text("hand edited")
    assert run_all("modern")["Mod Deck"]["reason"] == "draft exists"
    assert draft.read_text() == "hand edited"
