---
title: "PT SOS handler batch + Izzet Prowess deck update"
status: "SHIPPED"
created: "2026-05-02"
updated: "2026-05-02"
project: "mtg-sim"
estimated_time: "60-90 min"
related_findings:
  - "harness/inbox/drift-pr--2026-05-01.md"
related_commits: []
supersedes: null
superseded_by: null
---

# PT SOS handler batch + Izzet Prowess deck update

## Goal

Write the 4 missing card handlers for PT Secrets of Strixhaven cards and
update the Izzet Prowess deck file to match the PT build (Flow State +
Colorstorm Stallion added). Prowess is 30.5% of the PT field — highest
priority for field accuracy.

## Scope

### In scope
- Handler: Tablet of Discovery (Izzet Maestro 4x core)
- Handler: Molten-Core Maestro (Izzet Maestro 3x namesake)
- Handler: Professor Dellian Fel (Golgari Midrange 4x mythic)
- Handler: Bloom Tender (Bant Rhythm 4x — fringe, low-effort)
- Deck file update: `decks/izzet_prowess_standard.txt` — add Flow State +
  Colorstorm Stallion, mainboard Eddymurk Crab x4

### Explicitly out of scope
- Izzet Maestro APL — defer until Constructed results (R4-8) confirm
  archetype performance warrants the build effort
- Sultai Control APL — same reason
- Planeswalker loyalty tracking — structural gap; open IMPERFECTIONS entry
- Molten-Core Maestro Opus trigger in APL — Prowess/Opus APL hook exists
  (same pattern as Colorstorm Stallion); wire when building Maestro APL
- WebFetch-corrupted Maestro deck file — do not build from 66-card corrupt
  source; defer until clean list available

## Pre-flight reads
- `engine/card_handlers_verified.py` tail (~27k lines) — insertion point confirmed
- `decks/izzet_prowess_standard.txt` — current list confirmed (60 cards, pre-SOS)
- `harness/knowledge/tech/spec-authoring-lessons.md` — advisor lesson on
  fidelity/placeholder gap tracking

## Known fidelity imperfections (open IMPERFECTIONS entries after ship)

| Card | What's not modeled | Impact |
|---|---|---|
| Tablet of Discovery | Cast-from-GY path; modeled as mill+mana proxy | Minor underrate of Maestro card velocity |
| Molten-Core Maestro | Opus trigger (+1/+1 + {R} per spell); modeled as 2/2 menace | ETB handler is structurally correct; Opus wired in APL later |
| Professor Dellian Fel | Loyalty counter tracking, +2/0/-6 across turns; modeled as one-shot | Underrates Golgari Midrange midgame value engine |
| Bloom Tender | Multi-color mana counting is approximate proxy | Negligible — fringe deck |

## Steps

### Step 1 — Write 4 handlers (~30 min)
Append to `engine/card_handlers_verified.py` before the final `for` loop
at the tail. Pattern: follow `_colorstorm_stallion_etb` / `_impractical_joke_spell`
as structural references.

- `_tablet_of_discovery_etb`: mill 1, add 1 mana proxy (NO free draw)
- `_molten_core_maestro_etb`: 2/2 menace, log Opus-deferred-to-APL
- `_professor_dellian_fel_etb`: one-shot — kill best opp creature if exists, else draw 1 / -1 life
- `_bloom_tender_etb`: 1/1, tap for N mana where N = distinct colors on BF

Register: `_ETB_HANDLERS` for all 4 (Dellian Fel is a PW but enters as an
ETB trigger; treat as ETB for sim purposes).

### Step 2 — Update Izzet Prowess deck file (~10 min)
Replace `decks/izzet_prowess_standard.txt` with PT-accurate build:
- +4 Flow State
- +4 Colorstorm Stallion (was 0 main)
- Eddymurk Crab: 4x main (was 2x)
- Trim outdated pre-SOS flex slots (Bounce Off, Octopus Form, Wild Ride, Elusive Otter)
- Mark header with PT SOS source + date

### Step 3 — Open IMPERFECTIONS entries (~5 min)
Two entries:
1. `planeswalker-loyalty-not-tracked` — structural; affects Prof. Dellian Fel,
   any future PW
2. `maestro-opus-trigger-apl-deferred` — ship when Maestro APL is built

### Step 4 — Commit (~5 min)

## Validation gates

| Gate | Acceptance | Stop trigger |
|---|---|---|
| V.1 Parse | `python -c "import ast; ast.parse(open('engine/card_handlers_verified.py').read())"` passes | SyntaxError |
| V.2 Import | `python -c "from engine.card_handlers_verified import ETB_EFFECTS; print('ok')"` passes | ImportError |
| V.3 Registration | All 4 card names present in `ETB_EFFECTS` after import | Missing key |
| V.4 Prowess deck | `python -c "from data.deck import load_deck_from_file; mb,sb=load_deck_from_file('decks/izzet_prowess_standard.txt'); assert len(mb)==60"` passes | Wrong count |

## Stop conditions
- Any validation gate fails: fix before commit
- Tablet handler model gives free card draw: revert to mill-only

## Changelog
- 2026-05-02: Created (EXECUTING). Advisor review before code.
- Reconciled 2026-06-27: verified complete; status was stale after the ~2026-05-16 cadence lapse.
