"""new-archetype detection must use one slug function and a boundary match (#6).

The old code slugged the archetype differently from _safe_slug (so punctuated
names never matched an existing APL and were "new" every run) and used a loose
substring test (`titan` is in `amulet_titan`, so an uncovered archetype looked
covered).

Run: python agents/scripts/test_new_archetype_slug.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import auto_pipeline as ap


# ---- the substring false-positive the issue names ----

def test_prefix_collision_is_not_covered():
    assert ap._slug_covered("titan", {"amulet_titan"}) is False


def test_midname_substring_is_not_covered():
    assert ap._slug_covered("prowess", {"izzet_prowess"}) is False


# ---- real coverage still detected ----

def test_exact_match_is_covered():
    assert ap._slug_covered("amulet_titan", {"amulet_titan"}) is True


def test_descriptive_suffix_is_covered():
    # APLs carry descriptive suffixes; the slug is a boundary prefix.
    assert ap._slug_covered("izzet_prowess", {"izzet_prowess_nick_tokyo_standard"}) is True


def test_boundary_prefix_only_not_loose():
    # "titan" must NOT match "titanic_force" -- the underscore boundary matters.
    assert ap._slug_covered("titan", {"titanic_force"}) is False


def test_uncovered_is_new():
    assert ap._slug_covered("burn", {"mono_red_aggro", "amulet_titan"}) is False


# ---- normalization parity: punctuation no longer "new" every run ----

def test_safe_slug_strips_apostrophe():
    assert ap._safe_slug("Urza's Saga") == "urzas_saga"


def test_punctuated_archetype_matches_its_apl():
    # The whole point: "Urza's Saga" slugs to the same stem the APL file uses,
    # so it is detected as covered instead of regenerated every run.
    slug = ap._safe_slug("Urza's Saga")
    assert ap._slug_covered(slug, {"urzas_saga"}) is True


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"  ok  {name}")
    print("test_new_archetype_slug: OK")
