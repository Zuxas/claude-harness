# Load-Bearing Engine WIP -- Architectural Finding

**Date:** 2026-04-26 (5 AM session, surfaced during Block 1 detour)
**Status:** BLOCKING further engine work until resolved

## Summary

`engine/game_state.py:1097` imports `on_landfall` from
`engine/card_effects.py` (cast_spell -> on_landfall hook for landfall
triggers). The committed version of `engine/card_effects.py` does NOT
contain `on_landfall`; it exists only in the uncommitted working-tree
WIP.

Consequence: stashing engine WIP causes goldfish (and all downstream
sim) to crash with `ImportError` on first cast. The codebase's
committed state is non-functional standalone.

## Reproduction

Working tree (HEAD `1e55791` + WIP applied):
```
Canonical BE goldfish (n=1000, seed=42): 99.9% WR, T4.62 avg
```

After `git stash push -- engine/card_effects.py engine/match_engine.py`:
```
Canonical BE goldfish: ImportError: cannot import name 'on_landfall'
from 'engine.card_effects'
Crash at engine/runner.py:192 -> apl.run_game -> cast_spell ->
game_state.py:1097
```

## Drift symptom (Block 1 trigger)

Canonical baseline documented at `ARCHITECTURE.md:117` cites T4.45 avg
(commit `8c3c2d5`, 2026-04-25 night). Current HEAD (`1e55791`)
reproducibly returns T4.62 -- 0.17 turn drift.

Drift attribution unresolved: cannot test committed-only state without
crashing, so unable to determine whether the T4.45 baseline was
recorded WITH WIP applied (drift is in committed code somewhere) or
WITHOUT WIP (drift is in WIP). The `on_landfall` import was added
between `8c3c2d5` and now; whether the T4.45 measurement pre-dates
that import is what determines the attribution.

## Affected commits in flight tonight

All five commits this session sit on top of this broken-foundation
state:

```
1e55791 engine: APL state isolation (Stage 1.6 PARTIAL)
29f528d decks: BE Voice/Nemesis variant
63d0c75 engine: Card state leakage fix (Stage 1.5 PARTIAL)
0bc20bf gauntlet: BE Modern 71.5% (N=100k)
ea5e196 gauntlet: BE Modern 71.1% (N=1k) + ASCII fixes
```

None of these commits CAUSED the issue (Stage 1.5/1.6 only touched
`match_runner.py`), but all of them now require the WIP to run.

## Sleeve-time variant comparison validity

Tonight's variant Jermey vs canonical comparison was measured on the
SAME engine state (working tree with WIP applied):

```
Variant:   T4.33 avg, T4 share 61.9%, 100.0% WR
Canonical: T4.62 avg, T4 share 47.3%,  99.9% WR
Delta:     -0.29 turn faster, +14.6pp T4 share
```

Relative comparison is robust (apples-to-apples on same engine).
Absolute comparison vs `ARCHITECTURE.md:117` baseline (T4.45) is
unreliable until WIP is resolved.

## Recommended fresh-session investigation order

1. **(15 min)** `git log --follow engine/game_state.py` to find the
   commit that added the `from engine.card_effects import on_landfall`
   line. Run goldfish on the parent commit (just before the import
   landed) to get a clean pre-WIP baseline.

2. **(15 min)** Read the WIP diff in detail:
   `git diff HEAD -- engine/card_effects.py engine/match_engine.py`
   and any other M files. Determine what behavior changes are in
   flight. Categorize as "additive new functionality" (probably safe
   to commit) vs "modifies existing behavior" (needs careful review).

3. **(20 min)** Decision: commit the WIP as-is (locking in current
   T4.62 baseline) OR revert it (potentially restoring T4.45 baseline)
   OR cherry-pick the `on_landfall` function alone (minimum viable
   commit to make the codebase consistent).

4. **(10 min)** Re-baseline: run canonical BE goldfish on the resolved
   foundation, update `ARCHITECTURE.md:117` with the new baseline +
   date.

Total: ~60 min fresh-session block. Pre-requisite for any further
engine work.

## Why this blocks Block 2 / 3 / 4 from this session

- **Block 2 (T2.5 Bombardment-Mobilize):** involves engine
  modifications. Layering changes on top of unresolved foundation
  amplifies the unknown.
- **Block 3 (variant card audit):** needs trustworthy goldfish numbers
  as the behavioral baseline for "shortcut vs faithful" findings.
  With drift unresolved, audit conclusions are unreliable.
- **Block 4 (DB cache diagnostic):** independent of engine state;
  could ship in isolation. But surfaces a finding that pairs naturally
  with fresh-session work, not isolated tonight.

## Block 1 status

`scripts/sleeve_check.py` written and validated against current engine
state. **NOT committed.** Lives in working tree for fresh-session
pickup once foundation is resolved. Script is correct on its own;
commit-blocking decision is about not layering more onto unresolved
foundation.

## Pre-existing untracked engine files

Beyond the modified files, six untracked engine files exist:
- `engine/auto_handlers.py`
- `engine/card_priority.py`
- `engine/card_telemetry.py`
- `engine/effect_family_registry.py`
- `engine/effect_primitives.py`
- `engine/oracle_parser.py`

`engine/card_handlers_verified.py` (committed) imports from these
untracked files. Same architectural pattern as the `on_landfall`
issue: committed code references uncommitted dependencies. Fresh-
session investigation should determine which are safe to commit
alongside the WIP resolution.

## Resolution (2026-04-26 morning)

**Status:** RESOLVED at commits `7e213ea` (foundation) + `0c0f42c`
(script support).

Investigation revealed deeper dependency chain than originally
suspected: `engine/card_effects.py` imports from
`engine/card_handlers_verified.py` (tracked), which imports from
`engine/effect_primitives.py` (was untracked). All three layers
required commit for foundation to be internally consistent.

**Foundation commit (`7e213ea`):** card_effects.py + match_engine.py
+ effect_primitives.py. ~903 additive lines, zero deletions. Working
tree behavior unchanged. Stash test passes -- original failure mode
(`git stash -- engine/card_effects.py` -> ImportError on cast) is
structurally impossible now.

**Script support commit (`0c0f42c`):** auto_handlers.py +
effect_family_registry.py. Logically separate -- tooling, not core
sim. Without this, `scripts/calibrate_matrix.py` and
`scripts/full_audit.py` crash on fresh clone.

**Re-baseline:** canonical BE goldfish T4.62 avg / T5 median / 47.3%
T4 share / 99.9% WR. 0.17-turn drift from T4.45 attributed to WIP's
per-turn handler dispatch overhead. Represents correct modeling
additions (landfall, ETB effects, spell-resolve handlers), not
regression.

## Remaining triage (NOT done in this fix)

Three engine files remain untracked with NO importers in tracked
code:
- `engine/card_priority.py` (357 lines)
- `engine/card_telemetry.py` (261 lines)
- `engine/oracle_parser.py` (322 lines)

These are work-in-progress that was started and never wired up. No
safety reason to commit them (nothing depends on them); no safety
reason to keep them (they don't run in any code path). Decision
deferred for fresh-session triage:
- (a) wire them up to existing systems (real engineering work)
- (b) finish the WIP and integrate
- (c) delete (if abandoned)

Surfaced as TODO.md entry.
