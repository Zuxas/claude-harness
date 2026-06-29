# Skill: apl-generation

**One-line:** Generate and tune APLs for new archetypes via the auto-pipeline -- Gemma authors the bulk, Claude refines, with the known Gemma failure modes loaded up front.

## Activate when
Trigger phrases: "generate APL", "auto-pipeline", "new archetype", "Gemma".
Load this skill for any task that produces a new APL, runs the
archetype-detection -> APL pipeline, or tunes a generated APL.

## Load these files
- `harness/knowledge/tech/apl-architecture.md` -- APL structure, sections, and the contract the sim consumes; read before writing any APL line.
- `harness/knowledge/tech/gemma-apl-failure-analysis-2026-04-29.md` -- catalogued Gemma APL failure modes; read BEFORE generating so you do not reproduce them.
- `harness/agents/scripts/auto_pipeline.py` -- Layer 5 archetype-detection + APL generation pipeline; the entry point.
- `harness/agents/scripts/apl_tuner.py` -- post-generation APL tuner; refinement pass over generated output.

## Behavior rules
- Read `harness/knowledge/tech/gemma-apl-failure-analysis-2026-04-29.md` BEFORE generating. Generation that ignores the known failure catalogue repeats it.
- Division of labor (per feedback_token_usage): Gemma AUTHORS the bulk APL; Claude REFINES, does not author from scratch. Delegate generation, then tune.
- Validate every generated APL against the mtg-sim-quality skill gates (lint + oracle) before claiming it is usable.
- Set `PYTHONIOENCODING=utf-8`, add repo root to `sys.path`, ASCII-only output. Do NOT read or modify `mtg-sim/apl/` from this harness skill -- a concurrent workflow owns it.

## Related specs
- `harness/specs/2026-04-29-gemma-apl-quality-lift.md`
- `harness/specs/2026-04-28-auto-pipeline-nightly-integration.md`
- `harness/specs/2026-04-30-llm-as-judge-apl-evaluation.md`
- `harness/specs/2026-06-28-skill-system-impl-plan.md`
