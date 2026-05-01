---
title: Skill system for the harness (dynamic capability loading)
status: PROPOSED
created: 2026-05-01
updated: 2026-05-01
project: harness
estimated_time: 2-3 hours
source: harness-engineering-guide/guide/skill-system.md
---

# Spec: Skill System for the Harness

## Goal

Replace the flat `knowledge/` + `agents/scripts/` layout with bounded skills
that each bundle related knowledge, scripts, and behavior rules under one
loadable unit. Reduces context overhead and makes capabilities easier to
compose and discover.

## Why (what's missing today)

Current harness loads ALL knowledge blocks at session start for the relevant
domain. A full MTG session loads ~8 knowledge files + all agents/scripts are
always present. No scoping, no on-demand loading.

Skill system: present a menu (~150 tokens) → model loads only the skill it
needs (~2-5 files) → 60-80% context reduction per turn at scale.

Also solves the "where does this live?" question. Right now a capability like
"APL quality" spans: knowledge/tech/mtg-sim-quality-grades.md,
scripts/lint-mtg-sim.py, scripts/drift-detect.ps1,
agents/scripts/apl_optimizer.py — spread across 3 directories with no
grouping. A skill bundles all of these.

## Scope

In:
- Create `harness/skills/` directory with SKILL.md per capability
- 4 initial skills: mtg-sim-quality, meta-analysis, apl-generation, harness-ops
- Update `harness/CLAUDE.md` to reference skill menu at session start
- Skills are additive — existing knowledge/, scripts/, agents/ stay intact

Out:
- No Python SkillRegistry (Claude Code doesn't do programmatic tool loading)
- No changes to specs/, MEMORY.md, IMPERFECTIONS.md
- No changes to mtg-sim or mtg-meta-analyzer

## Skill structure

```
harness/skills/
  mtg-sim-quality/
    SKILL.md          <- what this skill does, when to load it, what files it uses
    README.md         <- optional human-readable docs
  meta-analysis/
    SKILL.md
  apl-generation/
    SKILL.md
  harness-ops/
    SKILL.md
```

Each SKILL.md contains:
- Name + one-line description
- When to activate (trigger phrases)
- Files to load (knowledge blocks, scripts)
- Behavior rules specific to this skill
- Related specs

## Initial skill definitions

### mtg-sim-quality
Trigger: "lint", "oracle", "drift", "APL quality", "test", "CI"
Files: knowledge/tech/mtg-sim-quality-grades.md, spec-authoring-lessons.md,
       scripts/lint-mtg-sim.py, scripts/drift-detect.ps1,
       agents/scripts/apl_optimizer.py, scripts/verify_oracle.py

### meta-analysis
Trigger: "meta", "matchup", "WR", "field", "gauntlet", "Standard", "Modern"
Files: knowledge/mtg/meta-analyzer.md, knowledge/tech/sim-framework.md,
       scripts/run-gauntlet.ps1, agents/scripts/matchup_gauntlet.py

### apl-generation
Trigger: "generate APL", "auto-pipeline", "new archetype", "Gemma"
Files: knowledge/tech/apl-architecture.md, knowledge/tech/gemma-apl-failure-analysis-2026-04-29.md,
       agents/scripts/auto_pipeline.py, agents/scripts/apl_tuner.py

### harness-ops
Trigger: "session", "snapshot", "drift PR", "nightly", "schedule"
Files: MEMORY.md (summary), scripts/session-snapshot.ps1,
       scripts/gemma-drift-pr.ps1, scripts/register-harness-tasks.ps1,
       SUBPROJECTS.md

## CLAUDE.md change

Add to SESSION START PROTOCOL (after step 2):

> **Step 2b: Check skill menu.** Before loading knowledge blocks, check
> `harness/skills/` for the relevant skill. Load only that skill's listed
> files instead of all blocks in the domain.

## Validation

- Session that asks only APL quality questions: loads ≤5 files (vs current ~8+)
- Session startup time: same or faster
- No regressions in existing spec execution (lint, drift, gauntlet)

## Schedule

After PT Strixhaven data is ingested and Standard gauntlet run is complete.
Earliest start: 2026-05-05.

## Changelog

- 2026-05-01: Created from harness-engineering-guide skill-system pattern.
  Parked pending PT data pipeline.
