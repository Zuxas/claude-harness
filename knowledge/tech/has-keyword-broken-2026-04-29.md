---
title: "engine.match_state.has_keyword always returns False"
date: "2026-04-29"
project: "mtg-sim"
severity: "high"
domain: "engine-fidelity"
discovered_during: "Phase A of jeskai-blink-oracle-fidelity-audit (Item 4 Solitude lifelink check)"
---

# Finding: has_keyword() in match_state.py is structurally broken

## Symptom

Solitude's lifelink (verified in Scryfall oracle: `keywords:["Lifelink","Evoke","Flash"]`)
does not gain life on combat damage.

## Root cause

`engine/match_state.py:218`:

```python
def has_keyword(card: Card, keyword: str) -> bool:
    """Check if a card has a keyword ability."""
    kw = getattr(card, 'keywords', set())
    if isinstance(kw, set):
        return keyword.lower() in {k.lower() for k in kw}
    oracle = getattr(card, 'oracle_text', '') or ''
    return keyword.lower() in oracle.lower()
```

The function attempts `card.keywords` first, falling back to oracle-text scan
only when `keywords` is NOT a set. But:

1. `data/card.py` has no `keywords` field on the `Card` dataclass.
2. `data/deck.py:_get_cards_local` does not pass keywords through from
   the local CardDB.
3. `_build_cards()` (deck.py L161) does not set keywords.
4. No code anywhere in `engine/` or `data/` ever assigns `card.keywords`.

So `getattr(card, 'keywords', set())` always returns the default empty
`set()`. `isinstance(set(), set)` is `True`. The function returns
`'lifelink' in {}` -> `False`. **The oracle-text fallback is unreachable.**

## Verified call sites

`match_state.py:269` checks `atk_lifelink = has_keyword(atk, 'lifelink')`
on every attacker. `match_state.py:307` checks deathtouch on blockers.
`match_engine.py:249` then conditions life gain on
`combat_result.life_gained_attacker > 0`. Since the keyword check is
broken, life gain branches are never entered.

## Affected mechanics

Every keyword check via this function:
- lifelink (Solitude, Phlage if it had it -- Phlage doesn't)
- deathtouch (blocker side)
- the function is also imported elsewhere (`Grep -l has_keyword engine/`
  showed 10 files) -- needs full audit

`tag_keywords()` in `engine/keywords.py` correctly populates
`card.tags` (a set of strings). The bug is that `has_keyword` queries
the wrong attribute (`card.keywords` vs `card.tags`).

## Two-line engine fix (deferred to Phase C)

```python
# engine/match_state.py:218 -- FIX
def has_keyword(card: Card, keyword: str) -> bool:
    tags = getattr(card, 'tags', set()) or set()
    if keyword.lower() in {t.lower() for t in tags}:
        return True
    oracle = getattr(card, 'oracle_text', '') or ''
    return keyword.lower() in oracle.lower()
```

This is a single-file engine change but per Phase A scope I am NOT
touching `engine/`. Surface for Phase C.

## Path analysis

There are TWO combat-resolution paths in this engine:

1. `engine/match_runner.py` (`_resolve_combat`) -- uses
   `KWTag.LIFELINK in atk.tags` directly. **Works correctly** because
   `tag_keywords` (engine/keywords.py) parses oracle text and adds
   "lifelink" to `card.tags` at deck-load time.

2. `engine/match_state.py` (`resolve_combat`, called from
   `engine/match_engine.py`) -- uses `has_keyword` -> `card.keywords`
   path. **Broken** as described above.

`run_matchup.py` (the gauntlet driver used by parallel_sim and
parallel_launcher) imports `engine.match_runner.run_match_set`. So
the match-runner path is what the gauntlet actually exercises. Solitude
lifelink fires correctly in run_matchup gauntlet runs.

The `match_engine` / `match_state` path is used by `bo3_match`,
`variant`, `meta_solver`, `parallel_match`, `combo_model`, and
several legacy callers. Those paths' lifelink/deathtouch results are
silently wrong.

## Phase A decision

Item 4 (Solitude lifelink) is "verified working" through the active
gauntlet path (`match_runner`). NO APL change needed. The
`match_state.has_keyword` bug is documented but deferred to Phase C
engine audit.

## Follow-up

Add IMPERFECTION marker for Phase C engine audit:
`engine-fidelity-gaps-has-keyword-attribute-mismatch`. Scope = audit
all 10 files using `has_keyword` (or sharing the broken
`card.keywords` access pattern); migrate to `card.tags` + oracle
fallback. Affected paths: `match_engine.run_match`, `bo3_match`,
`meta_solver`, `parallel_match`, `combo_model`, `variant`. Estimated
fix: 5-line edit in `match_state.has_keyword`. Estimated WR-shift
risk for callers: medium for `match_engine`-driven simulations.

## Changelog

- 2026-04-29: Discovered during JB Item 4 Solitude lifelink probe.
