| [lint-mtg-sim.py](http://lint-mtg-sim.py) | none | lint report + exit code | none (planned 2026-04-27) |

## Future Extensions

- \[x\] MTGA log parser — automated game log -&gt; match_log DB + knowledge blocks
- \[ \] botctl — autonomous agent process manager for 24/7 tasks
- \[ \] Claude Code -&gt; Gemma delegation for cheap subtasks
- \[ \] Auto-updater that refreshes stale blocks on schedule
- \[x\] Spec-first execution protocol (2026-04-27)
- \[x\] Annotated imperfections registry (2026-04-27)
- \[x\] Quality grades doc (2026-04-27)
- \[x\] Drift detection battery (drift-detect.ps1) — 2026-04-27
- \[x\] Pre-commit lint ([lint-mtg-sim.py](http://lint-mtg-sim.py)) — 2026-04-27
- \[ \] Background drift PR equivalent via Gemma (tier 3)

## Changelog

- 2026-04-14: Created — initial architecture design
- 2026-04-15: Updated — added knowledge compiler pipeline, inbox workflow, RTK integration, dual-model architecture, data flow diagram, script inventory
- 2026-04-27: Updated — added Layer 6 (spec-first execution), Layer 7 (planned drift detection). Documented harness/specs/, [IMPERFECTIONS.md](http://IMPERFECTIONS.md), [quality-grades.md](http://quality-grades.md) additions from 2026-04-26/27 mtg-sim marathon session. Aligned with OpenAI Harness Engineering pattern (table-of-contents docs, drift detection planning, spec-first execution, imperfection annotation).
- 2026-04-27 (later): drift-detect.ps1 + [lint-mtg-sim.py](http://lint-mtg-sim.py) BUILT during Phase 3.5 wait window. Layer 7 status changed from "planned" to operational. Both scripts are read-only against mtg-sim and safe to run while Claude Code edits the project (lint uses pure AST parsing, no imports).