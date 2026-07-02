---
title: "Calibration probe: April's failed pairings vs the post-R1-R6 engine"
status: "SURFACED"
created: "2026-07-01"
source: "Cowork session, reduced-N sandbox probe (PYTHONHASHSEED=0, seed=42+i, seat-alternating)"
---

# Calibration probe — 2026-07-01 (n=2,000/pairing, single-thread sandbox, ~8ms/game)

April 24's two-pairing calibration FAILED and sidelined the sim. Re-ran both pairings
against today's engine. Caveats up front: n=2,000 (not 5k), decks/APLs are current
(post-PT lists), the "truth" anchors are April-era real-match data, Standard has moved.
Directional evidence, not a formal calibration. Wilson 95% half-width at n=2000 ~ +/-2.2pp.

## P2: Izzet Prowess vs Mono Green Landfall — FAILURE CLASS CURED

| | April sim | April truth | TODAY sim (n=2000) |
|---|---|---|---|
| Prowess WR | 1.4% (WRONG, D51.6) | 53.0% | **62.0%** (D~9 vs old truth) |

The April root cause (`_resolve_combat`/`_safe_power` never applying prowess/combat-phase
buffs) is definitively fixed — the June R-ladder + Phase 3.5 work moved this cell from
impossible to plausible-and-slightly-hot. Proactive-vs-proactive calibration is back.

## P1: Dimir Midrange vs Izzet Prowess — STILL WRONG, BUT INVERTED

| | April sim | April truth | TODAY sim (n=2000) |
|---|---|---|---|
| Dimir WR | 64.6% (D+24.6) | 40.0% | **13.1%** (D~-27) |

The sim swung from over- to under-crediting Dimir. Reading: the same combat fix that
cured P2 made Prowess hit at full strength, while Dimir's game — instant-speed removal
timing, counterspell decisions, R1-whitelist interaction — remains under-modeled, so the
interactive deck now drowns. This is fresh EMPIRICAL confirmation of the
AUDIT-ENGINE-APL Part-A findings: the remaining calibration debt lives in the
interaction model (whitelist responses + R2 combat-trick gap), not in proactive combat.

## Bonus findings (registry, same silent-miss class as landlessbelcher)

1. `get_match_apl('dimirmidrangestd')` resolves to **DimirExcruciatorStandardMatchAPL**
   (a proxy) — NOT Dimir Midrange.
2. `apl/dimir_midrange_standard_match.py::DimirMidrangeStandardMatchAPL` EXISTS,
   hand-written, and is registered NOWHERE in `apl/__init__.py`. One-line fix
   (register + alias) on the workstation (sandbox repo is pre-rewrite; do not
   commit mtg-sim from Cowork until re-synced).

## What this changes

- The full-N calibration on the workstation stays worthwhile but the headline is known:
  P2-class is fixed; P1-class is the oracle-driven-responses work (spec authored today,
  2026-07-01-oracle-driven-responses.md) — now supported by measurement, not just code review.
- Deck-choice consumers: trust proactive-vs-proactive cells; interactive-deck cells
  remain direction-only until the responses work lands.
