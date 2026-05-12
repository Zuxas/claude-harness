---
name: mtg-strategy-overview
description: Index of MTG strategic-theory knowledge blocks; pointers to which block answers which question. Read first when approaching any MTG strategic question.
metadata:
  type: knowledge
  domain: mtg
  slice: strategy
---

# MTG Strategy -- Overview

MTG strategic thinking is the layer of frameworks *above* raw statistics:
why a deck wins, when an archetype is the favorite, how to evaluate a
card outside its raw numbers. This subdir crystallizes the doctrine
already encoded in `mtg-meta-analyzer/analysis/` modules plus widely
cited published strategy.

**When to consult which block:**

- [[chapin-principles]] -- evaluating a deck or a card. The
  Threats / Answers / Consistency / Velocity / Mana / Clock framework.
- [[role-theory]] -- "should I be the beatdown or the control?" Game-1
  vs Game-2 role assignment. Misassigning role is the dominant cause
  of close-game losses at competitive levels.
- [[card-advantage]] -- "is this card worth its slot?" Raw, virtual,
  tempo, quality, exchange ratios.
- [[threat-answer-density]] -- "does my deck have enough threats / does
  the field have enough answers?" The math under the previous blocks.
- [[format-standard-spring-2026]] -- the strategic identity of each
  current Standard pillar. *Snapshot dated; rewrite when meta shifts.*

[Strong] Every paragraph in every strategy block carries an epistemic
tag: `[Strong]` (sourced doctrine, stable), `[Inference]` (synthesis,
working hypothesis), `[Uncertain]` (low-confidence pattern-match,
reserved for rare use). When in doubt, distrust `[Inference]`.

[Strong] Every block points to the codebase module that operationalizes
its doctrine. If a block contradicts the code, the code wins -- file
an imperfection and rewrite the block.

[Inference] This overview reflects the structure of the spec
(`harness/specs/2026-05-12-mtg-strategy-knowledge-base-slice-a.md`).
The "when to consult" assignments above are my synthesis of how the
blocks compose; another reader might consult them in a different order.
