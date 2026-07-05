---
title: "/council v2 — beefed roster + argument rubric + standalone repo"
status: "SHIPPED"
created: "2026-07-05"
updated: "2026-07-05"
project: "harness"
estimated_time: "1 session (dogfood build)"
related_findings:
  - "harness/specs/2026-07-04-bob-orchestrator-skill.md"
related_commits: []
supersedes: null
superseded_by: null
---

# /council v2 — beefed roster + argument rubric + standalone repo

## Goal

Upgrade the `council` skill from a 3-4 seat blind panel into a robust board: an 8-seat
roster selected adaptively by blast radius, every seat held to an argument rubric
(evidence-tiered claims + calibrated confidence + a falsifier), and a one-round rebuttal
before the chairman synthesizes by evidence quality. Ship it in two homes, exactly like
`/bob`: (1) upgrade the onsite harness skill, (2) a genericized standalone public repo
`Zuxas/council` with Chair-voice docs. Company metaphor: Council = the board (independent
oversight; recommends), Bob = the foreman (executes; consults the board), the user = the
owner (final ratifier).

## Scope

### In scope
- `council.py` deterministic core (stdlib): `select_panel(weight)`, `anonymize(outputs)`
  (blind shuffle+relabel for peer review), `verdict_scaffold(...)` -- TDD.
- The 8-seat roster: ANALYST, CONTRARIAN, EMPIRICIST, CROSS_VENDOR (have) + ADVOCATE
  (steelman), RED_TEAM (adversary), HISTORIAN (precedent), PRAGMATIST (cost/benefit).
  ADVOCATE and RED_TEAM are ALWAYS paired.
- The argument rubric every seat produces: structured `Position -> Claim[tier] -> Warrant
  -> anticipated-counter`; evidence tiers `PRIMARY (cite) | DERIVED | ASSERTED`; calibrated
  confidence 0-1; a falsifier ("the evidence that would flip me").
- 5-phase flow: FRAME (neutral) -> SELECT (panel by weight) -> ROUND 1 (blind parallel) ->
  ROUND 2 (one rebuttal round on anonymized peers) -> CHAIR (synthesize by evidence tier;
  completeness sweep; verdict + confidence + preserved dissent + evidence index +
  falsifiers-as-TODOs).
- Onsite upgrade: `.claude/skills/council/SKILL.md` (keeps Codex cross-vendor seat, the
  guides/precedent context, "user is final ratifier").
- Public repo `E:\council-public` -> `Zuxas/council`: genericized SKILL + references +
  `council.py` + tests + Chair-voice README/USER-GUIDE + CONVENTION-TEMPLATE + MIT LICENSE.
- Cross-link banners: Bob <-> Council ("pairs well with").

### Explicitly out of scope
- Redistributing third-party skills. Council stands alone (built-in protocol); external
  tools (a cross-vendor CLI) are optional upgrades.
- Auto-publishing / auto-pushing. `gh repo create` + cross-link pushes are the user's button.

## Pre-flight reads
- `.claude/skills/council/SKILL.md` -- the existing skill being upgraded.
- `harness/specs/2026-07-04-bob-orchestrator-skill.md` + `E:\bob-public\*` -- the proven
  two-home / genericize / dogfood pattern to mirror.

## Steps
1. Write `council.py` + `test_council.py`; pytest green (conductor-pinned core).
2. Ultracode dogfood: build the onsite SKILL upgrade + public SKILL/references + Chair-voice
   README/USER-GUIDE + repo meta; independent verifier runs pytest + leakage grep.
3. Conductor: git init `E:\council-public`, verify clean (authorship + zero leakage), commit.
4. Cross-link Bob <-> Council READMEs.
5. `gh repo create Zuxas/council` (user's button) + push cross-link to `Zuxas/bob`.

## Validation gates
| Gate | Acceptance | Stop trigger |
|---|---|---|
| G1 core | `council.py`: select_panel scales routine(3)->irreversible(8); ADVOCATE<->RED_TEAM paired in every panel; anonymize blind+reversible+complete; verdict scaffold has all sections. pytest green | any test fails |
| G2 onsite | SKILL.md has the 8-seat roster + argument rubric (tiers+confidence+falsifier) + rebuttal round + adaptive selection; keeps cross-vendor + user-ratifies | a piece missing |
| G3 public generic | public SKILL + references: ZERO leakage (no zuxas/pinecone/codex-path/harness/mtg); generic cross-vendor note | any leak |
| G4 docs | README + USER-GUIDE in Chair voice (board metaphor), commands listed, NO worked examples | missing/wrong voice |
| G5 repo | public repo git-inited + committed; authorship not real-PII; cross-link banners present | PII in commits |

## Stop conditions
- Leakage grep hits in public content -> STOP, fix before any commit/publish.
- Any hot-zone touch (none expected: skill dirs + new repo are non-hot-zone).

## Commit message template
```
feat(council): v2 -- 8-seat board, argument rubric, rebuttal round (+ standalone repo)
```

## Annotated imperfections
```
## council-cross-vendor-generic
**What's not perfect:** the public council names a cross-vendor seat but can't ship a
specific CLI integration (that's environment-specific).
**Concrete fix:** CONVENTION-TEMPLATE documents how a user wires their own cross-vendor CLI.
**Estimated effort:** included in build.
```

## Changelog
- 2026-07-05: Created (PROPOSED). Brainstormed roster (8 seats) + 3 rubric upgrades
  (evidence-tiering, confidence+falsifier, one rebuttal round) + company metaphor with user.
- 2026-07-05: SHIPPED. Dogfood-built via ultracode wyqjesftb (5 agents); the refute-verifier
  caught + I fixed a `codex` leak in the public CONVENTION template (the loop working). council.py
  5/5 pytest. Onsite `.claude/skills/council/` upgraded to v2 (kept Codex cross-vendor seat);
  public standalone repo published at github.com/Zuxas/council (e9efdfc, MIT, Chair-voice docs,
  cross-vendor "bring your own agent" invitation). Bob <-> Council cross-linked. Companion:
  a clean-room MIT handoff skill shipped in the Bob repo.
