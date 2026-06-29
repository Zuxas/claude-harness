# Skill: meta-analysis

**One-line:** Analyze the metagame -- field shares, matchup win rates, and gauntlet results across Standard and Modern -- grounded in the DECK ANALYSIS PROTOCOL context block.

## Activate when
Trigger phrases: "meta", "matchup", "WR", "field", "gauntlet", "Standard", "Modern".
Load this skill for any task about field composition, matchup/sideboard
analysis, win-rate reporting, or running/reading a gauntlet.

## Load these files
- `harness/knowledge/mtg/meta-analyzer.md` -- meta-analyzer data model, field shares, scrape cadence; the source of "what is the field."
- `harness/knowledge/tech/sim-framework.md` -- how the sim produces matchup WR; needed to read gauntlet output correctly.
- `harness/scripts/run-gauntlet.ps1` -- gauntlet wrapper; the entry point for a field-weighted WR run.
- `harness/agents/scripts/matchup_gauntlet.py` -- the gauntlet engine itself; matchup pairing + WR computation.

## Behavior rules
- ALWAYS prepend the DECK ANALYSIS PROTOCOL context block (the "Karn pattern" from harness/CLAUDE.md) before any matchup, sideboard, or deck-selection analysis. Fill decklist, format, field-weighted WR (cite the gauntlet run date), last sim baseline, known weaknesses, target event, opponent field.
- Cite the date and N of the gauntlet run behind every WR figure. WR without a run date and sample size is not an answer.
- Distinguish SIM-computed matchups from DB-cached matchups (Rule 5 lesson): engine changes cannot shift DB-cached results, so a flat WR after a sim change may be expected, not a bug.
- ASCII-only output; use "->" and "--".

## Related specs
- `harness/specs/2026-04-29-within-matchup-parallelism.md`
- `harness/specs/2026-04-29-stage-ab-100k-revalidation.md`
- `harness/specs/2026-06-26-archetype-capability-profiles.md`
- `harness/specs/2026-06-28-skill-system-impl-plan.md`
