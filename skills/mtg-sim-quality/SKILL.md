# Skill: mtg-sim-quality

**One-line:** Verify mtg-sim registry/handler/oracle/APL fidelity -- run the lints, the oracle check, and the drift battery before claiming any consistency or quality result.

## Activate when
Trigger phrases: "lint", "oracle", "drift", "APL quality", "test", "CI".
Load this skill for any task that asserts handler coverage, registry/deck
consistency, oracle text fidelity, APL grade, or CI/drift health.

## Load these files
- `harness/knowledge/tech/mtg-sim-quality-grades.md` -- per-domain quality grades; the baseline you are graded against before/after a change.
- `harness/knowledge/tech/spec-authoring-lessons.md` -- methodology lessons (esp. Rule 3 pre-flight, Rule 5 falsifiable gates); read before authoring or judging quality specs.
- `harness/scripts/lint-mtg-sim.py` -- registry/handler/deck consistency lint; the gate for "handlers match the registry."
- `harness/scripts/verify_oracle.py` -- oracle-text fidelity check; the gate for "card text matches oracle."
- `harness/scripts/drift-detect.ps1` -- the 8-check drift battery; emits finding ids you must cite.
- `harness/agents/scripts/apl_optimizer.py` -- APL optimizer; reference for what "APL quality" means mechanically.

## Behavior rules
- Run `python harness/scripts/lint-mtg-sim.py` AND `python harness/scripts/verify_oracle.py` BEFORE asserting handler or oracle fidelity. Do not claim consistency from reading code alone.
- `harness/scripts/drift-detect.ps1` is the 8-check battery. When you report drift, cite the specific finding ids it emits -- never say "looks clean" without the run output.
- Set `PYTHONIOENCODING=utf-8` and add the repo root to `sys.path` for any Python invoked. ASCII-only output.
- Gates must be falsifiable (Rule 5): state where a metric should land and why before running, then compare. A lint that errors is a stop condition -- fix the root cause, do not soft-stop.

## Related specs
- `harness/specs/2026-04-28-drift-detect-7th-check-spec-validation.md`
- `harness/specs/2026-04-28-drift-detect-8th-check-cache-key-audit.md`
- `harness/specs/2026-04-29-drift-detect-8th-check-rmw-pattern.md`
- `harness/specs/2026-04-29-jeskai-blink-oracle-fidelity-audit.md`
- `harness/specs/2026-06-28-skill-system-impl-plan.md`
