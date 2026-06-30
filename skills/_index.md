# harness/skills -- Skill Menu
# Load only the skill matching the task. Each skill lists its own files.

| Skill | Load when (triggers) | Path |
|---|---|---|
| mtg-sim-quality | lint, oracle, drift, APL quality, test, CI | skills/mtg-sim-quality/SKILL.md |
| meta-analysis | meta, matchup, WR, field, gauntlet, Standard, Modern | skills/meta-analysis/SKILL.md |
| apl-generation | generate APL, auto-pipeline, new archetype, Gemma | skills/apl-generation/SKILL.md |
| harness-ops | session, snapshot, drift PR, nightly, schedule | skills/harness-ops/SKILL.md |

User-invoked (not auto-fired by Claude):
| `/handoff` | eject a scoped slice of live context to a fresh session / another tool | ~/.claude/skills/handoff (overrides: knowledge/tech/handoff-convention-2026-06-30.md) |

If no skill matches, fall back to the domain knowledge blocks in
harness/knowledge/ (existing behavior).
