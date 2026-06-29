# DIRECTORY STRUCTURE (current)

Relocated from harness/CLAUDE.md on 2026-06-29 (LOW-RISK trim per specs/2026-06-29-claude-md-trim-plan.md).

```
harness/
  CLAUDE.md                <- this file
  MEMORY.md                <- session state log
  IMPERFECTIONS.md         <- tracked imperfections
  RESOLVED.md              <- archive of resolved imperfections
  SUBPROJECTS.md           <- canonical sub-project menu (added 2026-04-28 v1.4)
  HARNESS_STATUS.md        <- system overview + 5-layer roadmap
  plan-<date>.md           <- end-of-day plan documents
  plan-<date>-execution-chain.md  <- daily execution chains (added 2026-04-28 v1.4 as standing pattern)
  knowledge/
    _index.md              <- master block index
    mtg/                   <- MTG-sim, deck tuning, calibration
    career/                <- resume, certs, job search
    tech/                  <- infrastructure, tools, scripts
      mtg-sim-quality-grades.md     <- per-domain grades
      spec-authoring-lessons.md     <- methodology lessons (17 lessons as of 2026-04-28)
      drift-YYYY-MM-DD.md           <- daily drift findings (when -RouteFindings)
      cache-collision-bug-2026-04-27.md  <- foundational finding
      cache-key-audit-2026-04-28.md      <- foundational finding
    personal/              <- homestead, community, family
  specs/                   <- durable execution specs
    README.md              <- workflow doc
    _template.md           <- spec template
    _index.md              <- chronological spec registry by status
    RETROACTIVE.md         <- specs reconstructed for prior commits
  agents/
    scripts/
      gemma_drift_pr.py    <- Gemma drift PR generator
      nightly_harness.py   <- nightly orchestration (Layer 2)
      auto_pipeline.py     <- Layer 5 archetype-detection + APL generation
  scripts/
    drift-detect.ps1       <- drift detection battery (8 checks)
    lint-mtg-sim.py        <- registry/handler/deck consistency lint
    lint-cache-keys.py     <- cache-key heuristic lint (added 2026-04-28)
    session-snapshot.ps1   <- shift-handoff snapshot generator
    gemma-drift-pr.ps1     <- Gemma drift PR wrapper
    nightly-harness.ps1    <- nightly orchestration wrapper
    json-to-gexf.py        <- Gephi GEXF converter (added 2026-04-28)
    register-harness-tasks.ps1    <- Windows Task Scheduler registration
  state/
    latest-snapshot.md     <- rolling latest
    snapshots/             <- timestamped session snapshots
    graph-snapshots/       <- daily project graph JSON
    run_state.json         <- nightly harness run state
  inbox/                   <- drop-folder for Gemma compilation
    processed/             <- archived processed inputs
    drift-pr--YYYY-MM-DD.md       <- daily Gemma drift PRs
  visualizations/
    gephi/                 <- daily GEXF outputs (added 2026-04-28)
```
