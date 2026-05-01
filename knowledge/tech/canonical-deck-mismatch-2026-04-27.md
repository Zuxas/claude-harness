# Canonical BE Deck -- Stub vs .txt Mismatch

**Date:** 2026-04-27 morning (surfaced during Phase 2 investigation)
**Status:** SURFACED, decision-needed for fresh session

## Discovery

Phase 2 investigation traced combat triggers in BE-vs-Murktide
match games. Trace showed Voice Mobilize firing 87x across 50 games
using the "Boros Energy" registry key. But
`decks/boros_energy_modern.txt` has 0 Voice. Confirmed: the
`"boros_energy"` registry key resolves to `data.stub_decks`, NOT to
`decks/boros_energy_modern.txt`.

## Stub vs .txt diff

| Card                  | stub | .txt | Variant Jermey |
|-----------------------|------|------|----------------|
| Voice of Victory      | 3    | 0    | 3              |
| Static Prison         | 3    | 0    | 0              |
| Seasoned Pyromancer   | 3    | 2    | 2              |
| Ranger-Captain of Eos | 0    | 1    | 0              |
| The Legend of Roku    | 0    | 2    | 0 (in SB)      |
| Blood Moon MB         | 0    | 2    | 1              |
| Lightning Bolt        | 0    | 1    | 1              |
| Sunbaked Canyon       | 0    | 1    | 0              |
| Screaming Nemesis     | 0    | 0    | 1              |
| Windswept Heath       | 1    | 0    | 2              |

## Implications for tonight's session

Every "canonical" measurement tonight (T4.62 / T4.72 baselines,
71.7% / 69.1% / 68.4% gauntlets, mirror tests) was on the stub.

The variant Jermey deck
(`decks/boros_energy_variant_jermey_2026-04-26.txt`) was registered
to load from the .txt file (commit `29f528d`).

So the "variant vs canonical" comparison was variant-(.txt-loaded)
vs stub-(stub-loaded). Both decks have 3x Voice -- the variant
doesn't ADD Voice as our session docs claim. The actual variant
differentiation is:
- Variant trades 3x Static Prison (slow tap-down lock) for
  1 Bolt + 1 Nemesis + 1 Blood Moon (faster pressure)
- Variant cuts 1 Pyromancer (already had 3 in stub, variant has 2)
- Manabase swap (Windswept Heath +1, lose Sunbaked Canyon)

Sleeve-up read is still directionally valid (variant did win +11pp
gauntlet edge in tonight's measurements) but our EXPLANATION of why
has been wrong. Variant isn't faster because of Voice -- it's faster
because it cut Static Prison for burn.

## Decision needed (fresh session)

Three options for canonical-deck alignment:

**(a) Point `"boros_energy"` registry at `decks/boros_energy_modern.txt`.**
All tonight's stub-baseline measurements get superseded. New
.txt-canonical numbers will differ -- .txt has Roku MB + Blood Moon
+ RangerCap + Bolt that stub doesn't have. Re-baseline goldfish +
gauntlet on the corrected canonical. Probably ~30-45 min wall.

**(b) Update `decks/boros_energy_modern.txt` to match the stub** and
keep stub as the live registry target. Cleanup. Loses the "real
canonical 75" history if .txt was ever the intended truth.

**(c) Decide which IS the canonical 75 you'd sleeve, promote that
one, delete/archive the other.** Most architecturally correct but
requires Jermey-input on which list is real.

## Affected commits

All session measurements assume stub canonical:
- `7e213ea` (foundation fix re-baseline T4.62)
- `8fc9b82` (Voice+Guide bug fix re-baseline T4.72)
- `a31f360` (Phase 1 gauntlet 69.1%)
- `9721329` (Phase 4 gauntlet 68.4%)

None need re-running tonight. Numbers stand on the stub baseline.
Fresh-session work is the canonical alignment + re-baseline cycle,
after which a new line of measurements starts.

## Resolution (2026-04-27 morning)

**Status:** RESOLVED at commit (see git log). Option (a) chosen:
registry points at `decks/boros_energy_modern.txt`.

**Justification:** stub deck was auto-generated tournament-data scrape
with phantom card ("Static Prison" doesn't exist in Modern) and zero
sideboard. .txt is hand-curated 75 with full SB. Not a competing
canonical -- stale auto-generated data that never got replaced when
proper .txt was authored.

**Re-baseline numbers (n=1000 seed=42):**

| Metric         | Stub canonical | .txt canonical | Delta        |
|----------------|----------------|----------------|--------------|
| Goldfish WR    | 99.9%          | 100.0%         | +0.1pp       |
| Goldfish avg   | T4.72          | **T4.50**      | -0.22 turn   |
| T4 share       | 47.3%          | **53.4%**      | +6.1pp       |
| 1k Modern FW   | 68.4%          | **66.0%**      | -2.4pp       |
| Variant edge   | +11.0pp        | **+11.9pp**    | +0.9pp       |

**Counterintuitive findings:**
- .txt is FASTER goldfish than stub. Spec predicted slower (Roku/Blood
  Moon are slower cards). Reality: stub had 3x Static Prison which is
  in BE APL's `DEAD_IN_GOLDFISH` set, effectively a 57-card deck. .txt
  has zero dead cards.
- Gauntlet net effect mixed: .txt gains vs Mono Red (Blood Moon locks
  Mono Red Mountains) but loses vs Jeskai Blink, Eldrazi Tron, Domain
  Zoo (no Voice Mobilize means slower close vs value/disruption).
- Variant edge GREW slightly (+0.9pp) when measured against the real
  canonical. The variant explanation is now corrected: variant trades
  canonical's Roku + Blood Moon + RangerCap (value engine + lock)
  package for 3x Voice + Bombardment + Nemesis + extra Blood Moon
  (aggro pressure). Both decks have ~similar goldfish speed (T4.40 vs
  T4.50, only -0.10 turn faster) but variant has dramatically better
  field-weighted edge (+11.9pp).

**Stub deck (data.stub_decks "boros_energy") is now orphaned.**
Decision-needed for fresh session: delete the stub entry, or keep for
some non-Modern-canonical purpose? Not blocking.
