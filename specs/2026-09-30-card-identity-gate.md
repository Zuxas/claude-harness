---
title: "Card identity gate: exact-name card loading everywhere + refreshed Scryfall snapshot"
status: "SHIPPED"
created: "2026-09-30"
updated: "2026-09-30"
project: "mtg-sim (engine/card_db.py [hot zone, user-approved], data/deck.py, generate_matchup_data.py, fidelity.py, data/rules_reference snapshot + SNAPSHOT.json, tests)"
estimated_time: "M (~2 h)"
related_specs:
  - "harness/specs/2026-09-30-strict-mode.md (found the fuzzy substitution)"
  - "harness/reports/codex-review-mtg-sim-2026-09-29.md (card-data-first recommendation)"
related_commits:
  - "mtg-sim bd4b87e (exact lookup + loaders), 1d67724 (snapshot + SNAPSHOT.json), 22a91b8 (docs)"
supersedes: null
superseded_by: null
---

# Card identity gate (user: card data first, then the canonical-engine spec)

## Problem (verified 2026-09-30, mtg-sim HEAD 240e53c)
- `engine/card_db.CardDB.get` (line ~135): normalised exact key, else the FIRST index entry where either name contains
  the other -> "Thor, God of Thunder" returns the card "_____", "Kinetic Hellion" -> "Hellion", "Avengers
  Disassembled" -> "Assemble". Used by every name lookup in the engine.
- `generate_matchup_data.build_deck_from_dict` (line ~52): unknown name -> a blank 1/1 creature named after it.
- `data/deck.py _get_cards_local`: unknown locally -> live Scryfall API call.
- Oracle snapshot `data/rules_reference/scryfall_oracle_cards.json` + `scryfall_rulings.json` dated 2026-05-02 (no
  version recorded) -> recent cards missing.

## Scope (user decisions 2026-09-30)
IN: exact-only lookup in ALL modes (approved hot-zone edit); explicit aliases only for known syntax; suggestions in
errors, never substitution; refresh both Scryfall bulk files (download approved) and record the bulk version;
validate every main + sideboard in the current Modern + Standard fields; regression tests.
OUT (stay visible failures): Umezawa's Jitte / Resonating Lute / Walking Ballista handlers, Esper Blink crash, pilot
tuning. Strict mode still admits `auto` / `family` handlers: it guarantees execution honesty, not rules
correctness -- stated in the docs; a verified-semantics requirement belongs to the engine rebuild.

## Rules
- EXACT = the normalised key (lower-case, punctuation/space stripped) of the requested name equals the key of an
  oracle card name or of a card face (DFC / split / adventure faces are indexed already). This makes "Wear / Tear" ==
  "Wear // Tear" and "Jace, the Mind Sculptor" == "jace the mind sculptor" without any substring matching.
- No substring / partial / closest match anywhere in loading or lookup. `CardDB.suggest(name)` (difflib, top 3) is
  used ONLY in error messages.
- Deck loaders raise `UnknownCardError(name, suggestions)`; no placeholder cards, no network fallback.

## Steps + gates (pre-registered)
Step A -- exact lookup + strict loaders (on the OLD snapshot, measured alone):
- A1 UNIT: tests/test_card_identity.py -- Thor / Kinetic Hellion / Avengers Disassembled / made-up name -> None from
  get() and UnknownCardError from the loaders (with suggestions); "Wear / Tear" + "Wear // Tear" -> the split card;
  DFC front face ("Tamiyo, Inquisitive Student") and full DFC name resolve; punctuation/case variants resolve.
- A2 FIELD SCAN: every main + sideboard entry of the 32 Modern + Standard field decks: resolved or explicit error.
  Prediction on the old snapshot: exactly the 5 known names fail (Belion, the Parched; Abrupt Inquiry; Kinetic
  Hellion; Avengers Disassembled; Thor, God of Thunder).
- A3 COLLATERAL: pytest -- any new failure is investigated (a test relying on fuzzy lookup is a finding, not a patch
  target); default launcher Boros Energy (modern) cells identical to 2026-09-30 (its field has no unresolved names);
  Selesnya Landfall (standard): cells vs decks with an unresolved name ERROR explicitly, all others identical.
Step B -- refresh the snapshot:
- Download bulk types "oracle_cards" + "rulings" via https://api.scryfall.com/bulk-data; validate JSON (list, > 30k
  oracle cards); back up old files as *.2026-05-02.json; write data/rules_reference/SNAPSHOT.json {type, updated_at,
  download_uri, size, sha256, card_count} (tracked in git; the big files stay untracked).
- B1: the 5 names resolve IF they are real printed cards in the new bulk; any that do not are reported as deck-file
  errors (typo / unreleased), not aliased.
- B2 FIELD SCAN again: 0 unresolved, or each remaining one explained.
- B3 DIFF: list field-deck cards whose oracle text / type / mana cost changed between snapshots (errata).
- B4 COLLATERAL: pytest; launcher Boros + Landfall re-run: report cell moves; cells whose decks have no changed card
  and no previously-unresolved name should be identical (else investigate).

## Stop conditions
A1 fails; a field entry resolves to a card with a different normalised name; pytest regression not explained by the
removed fuzzy matching; B downloaded JSON invalid (keep old snapshot).

## Changelog
- 2026-09-30: EXECUTING (user approved the card_db hot-zone edit and the Scryfall download).
- 2026-09-30: SHIPPED (not pushed).

## Results
| Gate | Result |
|---|---|
| A1 UNIT | PASS -- tests/test_card_identity.py 6 tests (split spellings, DFC front + full name, punctuation/case, no substring substitution, loader raises with suggestions, dict loader no placeholder) |
| A2 FIELD SCAN (old snapshot) | PASS -- prediction exact: 28/32 decks load; the 5 predicted names fail in 4 Standard decks, each with suggestions, no substitution |
| A3 COLLATERAL | PASS -- default launcher Boros Energy identical cell-for-cell; Selesnya Landfall: the 4 affected cells error explicitly, all others identical. pytest: 2 new failures were my own tests using Izzet Spellementals as opponent (it silently relied on the fuzzy Belion substitution) -> finding, retargeted to Mono Green Landfall after step B |
| B DOWNLOAD | Scryfall bulk now serves gzipped JSONL (oracle 24.6 MB, rulings 5.4 MB compressed); converted to the JSON list card_db reads; 38,690 oracle cards / 79,706 rulings; SNAPSHOT.json records updated_at 2026-09-30T09:01:54Z (oracle) / 09:00:35Z (rulings), URIs, sha256 |
| B1 | Thor, God of Thunder + Avengers Disassembled resolve. Belion, the Parched, Abrupt Inquiry, Kinetic Hellion are NOT Scryfall cards -> left as explicit deck errors (Belion: 183 rows in scraped real decklists -> scraper/source naming, needs a human check; the other two: 0 real rows -> bad entries in curated deck files) |
| B2 FIELD SCAN (new) | 29/32 load; 3 remaining explained above |
| B3 DIFF | 3 of 496 field card names changed oracle text: Arena of Glory, Sarkhan, Dragon Ascendant, Sire of Seven Deaths |
| B4 COLLATERAL | pytest 167 passed (161 + 6) / same 3 failures / 4 errors; launcher Boros Energy identical (59.4); Selesnya Landfall identical except Izzet Control now loads (94.6) |

Fidelity pre-flight after the gate: 25 / 32 OK; Izzet Control now blocked for the right reason (Thor resolves, has no
handler).

## Mid-execution amendments
- A1: fidelity.deck_fidelity catches UnknownCardError (the loader now raises) and reports the deck as blocked.
- A2: .gitignore extended to the dated backup files (data/rules_reference/scryfall_*.20*.json).

## Findings
- Normalised exact matching already existed in the index; the harm was the substring fallback + the placeholder /
  network fallbacks in the loaders. All three are gone in every mode.
- Deck-NAME fuzziness remains in data.stub_decks.get_stub_deck_list (prefix matching of deck keys) -- a separate
  fallback path for decks without registry entries; strict pre-flight blocks such decks (no MatchAPL).
- Next (user-approved order): canonical-engine design spec -- typed legal actions, one state machine, deterministic
  replay, two small test decks.
