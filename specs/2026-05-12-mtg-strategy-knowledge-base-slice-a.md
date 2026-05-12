---
title: "MTG strategy knowledge base -- Slice A (foundational)"
status: "SHIPPED"
created: "2026-05-12"
updated: "2026-05-12"
project: "harness"
estimated_time: "90-150 min"
related_findings: []
related_commits:
  - "2a0887d -- _overview + gitignore carve-out"
  - "e091530 -- chapin-principles"
  - "064809b -- role-theory"
  - "f21c1b7 -- card-advantage"
  - "18b7884 -- threat-answer-density"
  - "1af8ab7 -- format-standard-spring-2026"
  - "a8d6bc9 -- index + slice close"
supersedes: null
superseded_by: null
---

# MTG strategy knowledge base -- Slice A (foundational)

## Goal

Populate `harness/knowledge/mtg/strategy/` with 6 strategic-theory blocks
(1 overview + 4 theory + 1 format snapshot) that Claude auto-loads
before answering MTG strategic questions. The blocks crystallize the
doctrine already encoded in `mtg-meta-analyzer/analysis/` modules
(`chapin.py`, `deck_roles.py`, `blunders.py`) plus widely-cited MTG
strategy frameworks (Chapin's 6 Principles, Flores' "Who's the
Beatdown?", card-advantage taxonomy).

Decided approach: **Slice A using Approach C (training-derived primer)**.
Approaches A (codebase crystallization) and B (curated external sources)
were considered and explicitly deferred -- Approach C is acceptable
*only with* the epistemic-hygiene rules below.

After this slice ships, future Claude sessions in the harness will read
these blocks before reasoning about MTG strategic questions, instead of
pattern-matching from training. This is the precondition for the May 29
Standard RC deck-lock decision support not being surface-level.

## Scope

### In scope
- New subdirectory `harness/knowledge/mtg/strategy/`
- 6 knowledge blocks following harness `_template.md` frontmatter format:
  1. `_overview.md` -- index/orientation, ~200 words
  2. `chapin-principles.md` -- Chapin's 6 Principles, ~800-1200 words
  3. `role-theory.md` -- Flores' "Who's the Beatdown?", ~600-900 words
  4. `card-advantage.md` -- CA taxonomy, ~700-1000 words
  5. `threat-answer-density.md` -- threat/answer math, ~600-900 words
  6. `format-standard-spring-2026.md` -- format-meta strategic identity,
     ~1200-1800 words, `Format snapshot: 2026-05-12`
- `harness/knowledge/_index.md` updated with a new `## MTG Strategy`
  section listing the 6 blocks
- Per-block self-checklist (see Validation gates below)
- All commits land in the `harness` repo (separate from `mtg-meta-analyzer`)

### Explicitly out of scope
- Slice B (sideboard theory, mulligan theory, mental game) -- separate
  spec when scheduled. Untapped Bo3 SB Plans we shipped 2026-05-12
  partially cover tactically.
- Slice C-E (rules grounding, tournament theory, etc.) -- separate specs
- Modifying `harness/CLAUDE.md` -- the existing rule "MTG questions ->
  read ALL files in `harness/knowledge/mtg/`" already recurses into the
  new subdir. Verifying this assumption is gate 4.1.
- Auto-updating the format-meta block from scraped data -- considered,
  rejected. Manual write-back keeps strategic interpretation human-curated.
- Cross-format strategy blocks (Modern, Pioneer). Theory blocks are
  format-agnostic; the format block is Standard Spring 2026 only.
- Moving the existing 187 operational artifacts in
  `harness/knowledge/mtg/`. They stay flat in `mtg/`; strategy goes in
  `mtg/strategy/`. Side-by-side coexistence.

## Epistemic tag definitions

Every paragraph in every block must carry one of these tags:

- **[Strong]** -- well-established doctrine attributable to a specific
  source (Chapin's 6 Principles, Flores' beatdown/control, generally
  accepted CA definitions). Stable across formats and time. Safe to
  rely on without further verification.
- **[Inference]** -- my synthesis or cross-framework reasoning. Not
  attributable to a single source. Plausible but unverified -- treat as
  a working hypothesis. Most of the format-meta block will land here.
- **[Uncertain]** -- pattern-matched from training, low confidence. If a
  paragraph would be tagged this, prefer to delete it instead. Reserved
  for cases where the gap matters but the alternative is silence.

A block with >40% `[Strong]` paragraphs is well-grounded. A block with
mostly `[Inference]` and no [Strong] anchor is a candidate for deletion
or escalation to Approach A/B in a follow-up spec.

## Pre-flight reads (if any)

The executor must read these BEFORE writing any block:

- `harness/knowledge/_template.md` -- frontmatter format (name,
  description, type, metadata) and `[[name]]` link convention
- `harness/CLAUDE.md` -- confirm the recursive load rule actually pulls
  in `mtg/strategy/`. If not, surface and stop (gate 4.1).
- `mtg-meta-analyzer/analysis/chapin.py` -- the codebase's
  operationalized version of Chapin's 6 Principles. Each principle has
  a calibrated threshold. Block 2 (`chapin-principles.md`) MUST cite the
  specific numeric thresholds from this file, not made-up numbers.
- `mtg-meta-analyzer/analysis/deck_roles.py` -- the
  Aggro/Midrange/Control/Combo/Tempo classification. Block 3
  (`role-theory.md`) must explain how this 5-role taxonomy relates to
  Flores' 2-role beatdown/control framing.
- `mtg-meta-analyzer/analysis/blunders.py` -- sweeper viability checks,
  interaction count thresholds. Block 5 (`threat-answer-density.md`)
  must reference the specific checks this module performs.
- `mtg-meta-analyzer/analysis/meta_scoring.py` -- Pillar / Trap /
  Underplayed / Fringe taxonomy. Useful context for the format block.
- `harness/MEMORY.md` "PT SOS FINDINGS (2026-05-03)" block -- official
  matchup matrix, top 8, key matchup reads from Pro Tour Secrets of
  Strixhaven. The `format-standard-spring-2026.md` block must NOT
  contradict these figures (e.g., Selesnya Landfall's 63.81% PT WR is
  a primary-source data point).

## Steps

### Step 1 -- mkdir + read pre-flight files (~10 min)

```
mkdir -p harness/knowledge/mtg/strategy
```

Read the 5 codebase files listed in Pre-flight reads. Extract the
concrete doctrine each module encodes -- thresholds, taxonomy, scoring
formulas. These are the ground truth the blocks must respect.

### Step 2 -- Write `_overview.md` (~10 min)

~200 words. Acts as the landing page for the strategy subdir. Structure:

- Frontmatter: `name: mtg-strategy-overview`,
  `description: Index of MTG strategic-theory knowledge blocks; pointers to which block answers which question`,
  `type: knowledge`
- One paragraph: what MTG strategic thinking IS (frameworks for evaluating
  decks, matchups, in-game decisions beyond pure stats)
- Block index with one-line "when to consult" for each of the 5 other blocks
- Pointer to the codebase modules each block aligns with

### Step 3 -- Write `chapin-principles.md` (~25 min)

~800-1200 words. The 6 Principles (Threats, Answers, Consistency,
Velocity, Mana, Clock) -- not just enumeration, but how they interact.

Structure:
- Source: Patrick Chapin, *Next Level Magic* / *Next Level Deckbuilding*
- Each principle: definition, when it becomes binding, example of an
  archetype that wins/loses on that principle
- The interaction lattice: e.g. Velocity vs Consistency trade-off; Clock
  vs Answer density; Mana as the necessary-but-not-sufficient enabler
- Codebase pointer: `analysis/chapin.py` cites the calibrated 0-10
  scoring per principle. Reference its specific thresholds.
- Epistemic tags: `[Strong]` for the 6 principles' names + Chapin's
  framing (well-established); `[Inference]` for cross-principle
  interaction commentary
- Closing pointer: "Test against `analysis/chapin.py` if the block's
  framing drifts from the operationalized version"

### Step 4 -- Write `role-theory.md` (~20 min)

~600-900 words. Flores' "Who's the Beatdown?" doctrine.

Structure:
- Source: Mike Flores, *Who's the Beatdown?* (2002 essay, foundational)
- Core thesis: roles are RELATIONAL, not deck-intrinsic
- Beatdown vs Control as the two-pole framing
- Role-switching across games (often G1 you're beatdown, G2 you're
  control because they brought in more sweepers)
- Misassigning role as the dominant cause of close-game losses
- Codebase pointer: `analysis/deck_roles.py` 5-role taxonomy
  (Aggro/Midrange/Control/Combo/Tempo) -- explain how it relates to the
  Flores 2-role frame. Midrange = role-flexible; Tempo = beatdown that
  pretends to be control.
- Epistemic tags: `[Strong]` for the essay's central claims;
  `[Inference]` for the codebase mapping

### Step 5 -- Write `card-advantage.md` (~20 min)

~700-1000 words. CA taxonomy.

Structure:
- Raw CA: draw 2 from 1 (Divination, Read the Bones)
- Virtual CA: a Wrath of God against an aggro deck is an N-for-1
- Tempo as CA: every turn out-of-position is implicit card disadvantage
- Card quality: a Sheoldred is not equivalent to a Llanowar Elves
- Two-for-ones, exchange ratios, value generation
- Codebase pointer: `analysis/blunders.py` checks sweeper viability
  thresholds; references the virtual-CA framing implicitly
- Epistemic tags: `[Strong]` on definitions and exchange-ratio math;
  `[Inference]` on synthesis across categories

### Step 6 -- Write `threat-answer-density.md` (~20 min)

~600-900 words. The density math underneath the previous blocks.

Structure:
- Threat density: % of deck that wins the game on its own (creatures,
  planeswalkers, finishers)
- Answer density: % of deck that disrupts an opposing threat (removal,
  counterspells, sweepers)
- Why high threat density beats removal-light control (you outrun the
  answers)
- Why mass removal (Wrath) breaks the math by being virtual-CA
- The 60-card budget tension: every threat slot is not an answer slot
- Codebase pointer: `analysis/blunders.py` interaction count checks;
  `analysis/chapin.py` Threats/Answers scoring
- Epistemic tags: `[Strong]` on framework; `[Inference]` on specific
  density ratios

### Step 7 -- Write `format-standard-spring-2026.md` (~35 min)

~1200-1800 words. The longest block; format-specific; decays.

Structure:
- Frontmatter requires `Format snapshot: 2026-05-12` in metadata
- Pillar archetypes' strategic identity (NOT just stats):
  - Selesnya Landfall: beatdown with late-game inevitability via
    Up the Beanstalk + landfall payoffs. Express via Chapin: high
    Threat density + medium Velocity + low Clock acceleration.
  - Izzet Prowess: tempo deck; uses cantrips for velocity; role is
    beatdown with reach. Per role theory: usually the beatdown G1,
    switches to control vs aggro decks G2.
  - Izzet Lessons: delayed-clock control. Faithless Looting + late
    payoff. Per Chapin: high Answers, medium Velocity, low Clock.
  - Mono-Green Landfall: linear aggro with go-wide payoffs. High
    Threat density, low Answer density. Punished by sweepers.
  - Selesnya Ouroboroid: hybrid combo-midrange (Nass PT #2 seed deck).
  - Azorius Tempo, Izzet Spellementals: other tier-1 pillars.
- For each archetype: 1-2 paragraph strategic identity, mapping to the
  4 theory blocks
- Codebase pointer: `mtg_meta.db` archetype data + tactical sim notes
  at `harness/knowledge/mtg/sim-*.md`
- Epistemic tags: `[Inference]` heavy -- this is my read on Spring 2026
  Standard. Caveat heavily. Cross-check against PT SOS findings doc.

### Step 8 -- Update `harness/knowledge/_index.md` (~5 min)

Add a new section after the existing `## MTG` entries:

```markdown
## MTG Strategy

- [Overview](mtg/strategy/_overview.md) -- index of strategic-theory blocks
- [Chapin's 6 Principles](mtg/strategy/chapin-principles.md) -- threats/answers/consistency/velocity/mana/clock framework
- [Role theory](mtg/strategy/role-theory.md) -- Flores' beatdown/control as relational roles
- [Card advantage taxonomy](mtg/strategy/card-advantage.md) -- raw, virtual, tempo, quality, exchange ratios
- [Threat/answer density](mtg/strategy/threat-answer-density.md) -- density math, sweepers, the 60-card budget
- [Format -- Standard Spring 2026](mtg/strategy/format-standard-spring-2026.md) -- pillar archetypes' strategic identity (snapshot 2026-05-12)
```

### Step 9 -- Commit + push (~5 min)

```
cd harness
git add knowledge/mtg/strategy/ knowledge/_index.md
git commit -m "feat: MTG strategy knowledge base -- Slice A (6 foundational blocks)"
git push
```

## Validation gates

Every gate must pass before the commit lands.

| Gate | Acceptance | Stop trigger |
|---|---|---|
| 1.1 Source named | Every non-trivial claim has a name attached (Chapin / Flores / Duke / "common doctrine" / "Inference") | Untagged confident-sounding paraphrase |
| 1.2 Confidence tagged | Every paragraph has `[Strong]`, `[Inference]`, or `[Uncertain]` somewhere visible | Block reads as uniformly confident |
| 1.3 Codebase pointer reachable | Every block names a module that exists; the doctrine actually shows up in the code | Pointer references a deleted / renamed module |
| 1.4 Description discriminates | `description:` frontmatter is one specific line distinguishing this block from the other 5 | Generic "general MTG theory" descriptions |
| 1.5 Format snapshot dated | `format-standard-spring-2026.md` has `Format snapshot: 2026-05-12`; theory blocks omit it | Format block missing date, or theory block carrying a date |
| 2.1 Index updated | `harness/knowledge/_index.md` has all 6 entries under `## MTG Strategy` | Missing entries |
| 3.1 Word counts within bounds | Each block within +/- 25% of the target range in the table above | Major over/under-shoot suggests scope drift |
| 4.1 Auto-load verified | Manually grep `harness/CLAUDE.md` to confirm the rule pulls files recursively from `mtg/`. If not, escalate (add explicit rule or move blocks) | Rule only loads flat `mtg/*.md` |
| 4.2 Cross-references resolve | Every `[[name]]` link points to an existing block | Broken links |

## Stop conditions

Explicit "STOP and surface findings" triggers:

- Gate 4.1 fails (the harness CLAUDE.md rule doesn't recurse into
  subdirs): STOP. Surface to user. Decide between (a) adding an explicit
  load rule, or (b) flattening blocks to `mtg/strategy-*.md`.
- Step 1 pre-flight read reveals a codebase module has changed
  substantially and no longer encodes the doctrine I'm planning to
  describe: STOP. Surface, re-scope the block.
- Writing a block, I find myself making confident claims I can't tag
  `[Strong]` for at least 60% of paragraphs: STOP. Either find a source
  to anchor against, or drop the block to `[Inference]` throughout (and
  warn the user the block is largely synthesis).
- A block hits 1.5x the upper word-count bound: STOP. Either decompose
  into sub-blocks or trim ruthlessly.

## Commit message template

```
feat: MTG strategy knowledge base -- Slice A (foundational layer)

Adds 6 knowledge blocks under harness/knowledge/mtg/strategy/ that
Claude auto-loads before MTG strategic questions:

  _overview.md                          orientation + block index
  chapin-principles.md                  6 Principles framework
  role-theory.md                        Flores' beatdown/control
  card-advantage.md                     CA taxonomy
  threat-answer-density.md              density math + sweepers
  format-standard-spring-2026.md        pillar archetypes' identity

Each block:
  - Names sources for non-trivial claims
  - Tags confidence per paragraph [Strong] / [Inference] / [Uncertain]
  - Points back to the codebase module that operationalizes it
  - Format-meta block carries a snapshot date for decay tracking

Per spec 2026-05-12-mtg-strategy-knowledge-base-slice-a.md.

Approach C (training-derived) accepted with strict epistemic hygiene.
Approaches A (codebase crystallization) and B (curated external sources)
deferred to Slice B / iteration if blocks reveal gaps.
```

## Annotated imperfections (if any)

Likely imperfections after Slice A ships:

```
## strategy-blocks-not-codebase-grounded

**What's not perfect:** Approach C is training-derived; the user
explicitly flagged that as the failure mode. Mitigated by epistemic
hygiene rules (sources, confidence tags, codebase pointers) but not
eliminated. Some paragraphs will be confident-sounding paraphrase that
isn't strictly verifiable.

**Why not fixed in this spec:** Approach A (codebase crystallization)
was offered and the user picked C. Speed > grounding for this slice.

**Concrete fix:** Slice A-prime -- re-read the chapin.py / deck_roles.py
/ blunders.py modules in detail and rewrite any block paragraph that
contradicts what the code actually does. ~30-45 min after Slice A
lands.

**Estimated effort:** 30-45 min
```

```
## format-meta-block-decays

**What's not perfect:** format-standard-spring-2026.md is a snapshot.
Standard meta shifts every set release; the block will go stale within
weeks.

**Why not fixed in this spec:** Auto-update was rejected (manual
write-back keeps strategic interpretation human-curated).

**Concrete fix:** Add a calendar reminder (or harness scheduled task)
to rewrite the format block monthly, or whenever a new set drops.

**Estimated effort:** 20-30 min per refresh
```

After this spec ships, MOVE these entries to `harness/IMPERFECTIONS.md`.

## Changelog

- 2026-05-12: Created (status PROPOSED)
- 2026-05-12: Status -> SHIPPED at commit a8d6bc9. 6 blocks live under
  harness/knowledge/mtg/strategy/. .gitignore carve-out added for the
  strategy/ subdir (mid-execution amendment -- knowledge/mtg/ was fully
  ignored, blocking commits). All validation gates passed except
  _overview.md initially exceeded the 200-word target at 285 (1.43x);
  trimmed inline to 245 (within +25% bound) before final commit.
