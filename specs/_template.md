---
title: "[Spec Title]"
status: "PROPOSED"
created: "YYYY-MM-DD"
updated: "YYYY-MM-DD"
project: "[mtg-sim|harness|other]"
estimated_time: "X-Y min"
related_findings:
  - "harness/knowledge/tech/<finding>.md"
related_commits: []
supersedes: null
superseded_by: null
---

# [Spec Title]

## Goal

One paragraph. What does shipping this commit mean? What changes for the
user, the codebase, the future?

## Scope

### In scope
- Item 1 (concrete, testable)
- Item 2

### Explicitly out of scope
- Item A -- reason. Link to follow-up spec or imperfection if relevant.
- Item B -- reason.

DO NOT use "out of scope" as a defer-by-default escape hatch. If the
work is genuinely needed for correctness, it belongs in scope or in a
linked follow-up spec that's already drafted.

## Pre-flight reads (if any)

Files / docs that the executor must read BEFORE making changes:
- `<path>` -- why
- `<path>` -- why

## Steps

### Step 1 -- [name] (~X min)

Concrete commands or code. Be specific. Show:
- What file(s) to edit
- What the diff looks like (before/after if surgical)
- What command to run for validation
- Expected output

```
<concrete code or command>
```

### Step 2 -- [name] (~X min)

...

## Validation gates

Every gate must pass before the commit lands. State numeric thresholds.

| Gate | Acceptance | Stop trigger |
|---|---|---|
| 1.1 Goldfish unchanged | T<X> +/- 0.05 | drift >0.05 |
| 1.2 Mirror | 47-54% at n=1000 | outside band |
| ... | ... | ... |

## Stop conditions

Explicit "STOP and surface findings" triggers. Examples:
- Step 1 reveals X: STOP, surface, decide between Y and Z
- Validation gate 1.2 fails: STOP, debug
- Subprocess crashes / APL exception: STOP

## Commit message template

```
<type>: <subject line>

<body explaining the change, results, and any caveats>

Validation results:
  Goldfish: T<X> -> T<Y>
  Mirror:   <X>% -> <Y>%
  Gauntlet: <X>% -> <Y>%

Findings doc updated: <link>
Related specs: <links>
```

## Annotated imperfections (if any)

If the spec ships but doesn't reach 100% on every aspect, document what's
left here. Each entry must be a concrete next-session spec fragment, not
a vague "TODO improve X."

```
## <imperfection-name>

**What's not perfect:** <specific>
**Why not fixed in this spec:** <reason>
**Concrete fix:** <next-session implementable steps>
**Estimated effort:** <X min>
```

After the spec ships, MOVE these entries to `harness/IMPERFECTIONS.md`.

## Changelog

- YYYY-MM-DD: Created (status PROPOSED)
- YYYY-MM-DD: Status -> EXECUTING
- YYYY-MM-DD: Status -> SHIPPED at commit <hash>
