---
title: "Commit oracle_parser.py to close load-bearing-WIP gap"
status: "SHIPPED"
created: "2026-04-27"
updated: "2026-04-27"
project: "mtg-sim"
estimated_time: "5-10 min"
related_findings:
  - "harness/knowledge/tech/load-bearing-wip-2026-04-26.md"
related_commits:
  - "7e213ea"  # Yesterday's foundation fix (same pattern)
  - "0c0f42c"  # Committed auto_handlers.py but missed oracle_parser dependency
  - "4f62331"  # SHIPPED
supersedes: null
superseded_by: null
---

# Commit oracle_parser.py to close load-bearing-WIP gap

## Goal

Commit `engine/oracle_parser.py` to close the load-bearing-WIP gap
detected by `drift-detect.ps1` during 2026-04-27 session. Tracked
`engine/auto_handlers.py:22` does
`from engine.oracle_parser import parse_oracle` but `oracle_parser.py`
is untracked. Same pattern as yesterday's foundation fix (commit
`7e213ea`). Fresh clones cannot import auto_handlers.

This commit also validates the drift-detection pipeline end-to-end:
drift caught a real bug pattern, fed into spec-first protocol, single
commit closes it, drift returns clean.

## Scope

### In scope
- ONLY `engine/oracle_parser.py`. Single-file fix.

### Explicitly out of scope
- The other 2 orphan engine files (`card_priority.py`,
  `card_telemetry.py`) are NOT load-bearing per drift-detect (no
  tracked imports). They stay in IMPERFECTIONS for fresh-session
  triage decisions (delete vs finish vs wire-up).
- The 3 deck-count WARNs (glockulous/yawgmoth/living_end) — different
  concern, different audit, separate IMPERFECTIONS entry.
- ARCHITECTURE.md stale-by-3.3-hours WARN — separate cleanup task.

## Pre-flight reads

- `engine/oracle_parser.py` -- verify it parses cleanly + has no
  further untracked imports
- `engine/auto_handlers.py` line 22 -- confirm import signature

## Steps

### Step 1 -- parse + import sanity check (~2 min)

```bash
cd "E:/vscode ai project/mtg-sim" && python -c "
import ast
ast.parse(open('engine/oracle_parser.py').read())
print('parses ok')
" && python -c "
from engine.oracle_parser import parse_oracle
print('imports ok')
"
```

If parse or import fails: STOP, the orphan file may need work before
committing.

### Step 2 -- check for further untracked imports (~1 min)

```bash
grep -E "^from engine\.|^import engine\." "E:/vscode ai project/mtg-sim/engine/oracle_parser.py"
```

If oracle_parser imports from another untracked file, surface and
expand scope.

### Step 3 -- stage + commit (~3 min)

```bash
cd "E:/vscode ai project/mtg-sim"
rtk git add engine/oracle_parser.py
rtk git commit -m "<message per template>"
```

### Step 4 -- post-commit validation (~3 min)

1. Goldfish bit-identical: `T4.50 ±0.05 at n=1000 seed=42`
2. Re-run drift-detect: exit code should drop from 2 to 1 (ERROR
   resolved, WARNs remain)

## Validation gates

| Gate | Acceptance | Stop trigger |
|---|---|---|
| oracle_parser.py parses | `ast.parse` succeeds | parse fails |
| import succeeds | `from engine.oracle_parser import parse_oracle` works | ImportError |
| Goldfish unchanged | T4.50 ±0.05 at n=1000 seed=42 | drift >0.05 |
| drift-detect ERROR cleared | exit code 2 → 1 | exit still 2 with same ERROR |

## Stop conditions

- oracle_parser.py doesn't parse / import fails: STOP, file needs
  work before committing
- Goldfish drift >0.05 turn: STOP, file commit somehow changed
  behavior (shouldn't be possible since it was already imported,
  but verify)
- drift-detect still shows ERROR after commit: STOP, didn't actually
  fix the orphan
- Subprocess crash: STOP

## Commit message template

```
engine: commit oracle_parser.py to close load-bearing-WIP gap

drift-detect.ps1 (run during 2026-04-27 session) caught
engine/oracle_parser.py as untracked but imported by tracked
engine/auto_handlers.py:22 (`from engine.oracle_parser import
parse_oracle`). Same load-bearing-WIP pattern as yesterday's
foundation fix (7e213ea) -- fresh clones can't import auto_handlers.

This was missed when 0c0f42c committed auto_handlers.py +
effect_family_registry.py yesterday -- should have committed
oracle_parser too.

Validation:
- oracle_parser.py parses + imports cleanly
- Goldfish T4.50 bit-identical (file was already in use, just not
  tracked)
- drift-detect ERROR cleared (exit 2 -> 1, remaining WARNs unrelated)

Resolves IMPERFECTIONS entry partially (1 of 3 orphan engine files
closed). Remaining: card_priority.py + card_telemetry.py -- neither
is load-bearing per drift-detect, staying in IMPERFECTIONS for
fresh-session triage.

This commit also validates the drift-detection pipeline end-to-end:
drift caught a real bug pattern, fed into spec-first protocol, single
commit closed it, drift returns clean.

Spec: harness/specs/2026-04-27-oracle-parser-orphan-fix.md
```

## Annotated imperfections

None for this spec.

## Changelog

- 2026-04-27: Created (status PROPOSED)
- 2026-04-27: Status -> EXECUTING
- 2026-04-27: Status -> SHIPPED at commit 4f62331; goldfish T4.50
  bit-identical, drift-detect exit 2 -> 1 (ERROR cleared)
