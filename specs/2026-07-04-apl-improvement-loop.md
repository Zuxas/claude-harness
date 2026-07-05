---
title: "APL update/improvement loop -- the repeatable cycle for keeping Modern/Standard match APLs current + honest"
status: "PROPOSED"
created: "2026-07-04"
updated: "2026-07-04"
project: "mtg-sim"
estimated_time: "process-spec (no single commit); M per deck iteration, ongoing"
related_findings:
  - "E:\\vscode ai project\\BLUEPRINT-2026-07-03.md (WP-C = the APL-coverage wave; WP-A unblocks the interactive tier; WP-F = anchor pipeline)"
  - "harness/knowledge/mtg/sim-calibration-2026-07-01.md (n=5000 battery -- P1 INVERTED, the interaction-whitelist evidence)"
  - "harness/IMPERFECTIONS.md (OPEN apl/standard/affinity/cross-canonical items this loop drains)"
  - "harness/knowledge/tech/boros-energy-postban-validation-2026-06-29.md (the mismodeled-flag discipline)"
  - "harness/specs/2026-04-29-card-specs-framework.md (Phase B migration)"
  - "harness/specs/2026-04-29-jeskai-blink-oracle-fidelity-audit.md (the JB-style cross-canonical audit template)"
related_commits: []
supersedes: null
superseded_by: null
branch: "modern-postban-arc"
---

# APL update/improvement loop

## Goal

Turn "keep the APLs current + make them better" from a series of one-off
sessions into a single **repeatable cycle** with a fixed method, falsifiable
per-iteration gates, and event-driven triggers -- so any executor (Opus or
Codex) can pick up the queue, source real data, build one match APL to the
proven WP-C standard, run the gate battery, and either SHIP a trustworthy cell
or FLAG a mismodeled one, WITHOUT ever tuning toward an anchor. The loop also
carries two compounding maintenance lanes (cross-canonical oracle-fidelity
audit + card_specs dedup) that make every future build cheaper and every
existing opponent cell more accurate. This is a process/meta-spec: it defines
the cycle and the gates; each individual deck build is its own small execution
under this contract.

## Scope

### In scope
- The repeatable BUILD cycle (the WP-C proven method, formalized as steps + a
  reusable gate battery every deck must clear).
- The WP-A branch gate that unlocks the INTERACTIVE tier (Dimir Murktide,
  UW/Azorius Control, Jeskai) -- and WHY it is a conditional branch, not a
  queue slot.
- The cross-canonical oracle-fidelity audit (JB-style) as a background
  maintenance lane with its own gate discipline (quote oracle text in commits;
  bit-stable per APL per commit; surface deviations >5pp).
- card_specs Phase B migration as the dedup maintenance lane.
- The trigger-driven CADENCE (new set / B&R / meta shift >2% / calibration
  divergence >10pp) that fires the loop, replacing a fixed calendar.
- The prioritized QUEUE (ordered), including in-flight arcs to CONTINUE.
- The honest-flag / never-tune discipline as first-class STOP conditions,
  routed to `mtg-sim/mismodeled_matchups.py`.

### Explicitly out of scope
- The WP-A oracle-driven-responses build itself -- owned by
  `harness/specs/2026-07-04-oracle-driven-responses-execution.md`. This loop
  only CONSUMES its ship as a branch gate.
- The WP-B ISMCTS / search-driven play arc -- separate long spec. Note: WP-B#5
  (resumable rollout) unlocks multi-turn NAVIGATE/TEMPO puzzles + the assembly
  fixes, but is not this loop's territory.
- The WP-F anchor pipeline BUILD -- this loop is a CONSUMER of anchors and
  names re-anchoring as a cadence action, but building the pipeline is WP-F.
- Multi-format expansion (Pioneer/Pauper/Vintage) -- WP-G rides on this proven
  single-format loop after it is running; not in this spec.
- Engine-level fidelity mechanics (warp cost bracing, PW-loyalty wiring, stack
  model) -- these are engine specs; this loop only wires per-deck WANTS_* opt-in
  and FLAGS what the engine cannot yet model.

## Pre-flight reads (per iteration)

Before ANY deck build under this loop, the executor reads:
- `E:\vscode ai project\BLUEPRINT-2026-07-03.md` -- House Rules 0.1-0.8
  (spec-first, falsifiable gates, honest flags, determinism, git discipline,
  DB path, never fabricate) + WP-C queue.
- `harness/knowledge/tech/spec-authoring-lessons.md` -- for the oracle-text
  discipline (v1.6: quote oracle text in every card-mechanic commit body).
- `harness/IMPERFECTIONS.md` -- the OPEN items this build might drain, and the
  known engine gaps that cap which cells can be trustworthy.
- `mtg-sim/mismodeled_matchups.py` -- existing flags (do not re-discover; a
  new build vs a flagged opponent inherits that flag's caveat).
- `mtg-sim/CLAUDE.md` "Current APL status" -- the templates
  (goryos_reanimator_match, boros_energy_match) and in-flight arc state.
- The prior match APL(s) named as TEMPLATE for the deck being built.

## The loop (the repeatable cycle)

```
   [TRIGGER]  event fires (new set / B&R / meta shift >2% / calib >10pp / queue
        |     has an unstarted item) -- NOT a calendar tick
        v
   [SELECT]   pull the highest-priority queue item whose preconditions are met
        |     (interactive tier is gated behind the WP-A branch; in-flight
        |     arcs are RESUMED not restarted)
        v
   [SOURCE]   modal 60+15 from 3-5 June+ top finishes in mtg_meta.db WITH
        |     attribution.  STOP-IF-UNREACHABLE: if fresh modal data is not in
        |     the DB (Modern DB is pre-ban stale to 2026-04-24), STOP + report
        |     -- do NOT fabricate a list (House Rule 8; Rakdos 07-02 precedent).
        v
   [BUILD]    hand-write the MatchAPL in house style (constants for card names,
        |     ASCII output, base on AwareMatchAPL if it needs priority/counters).
        |     Wire per-deck WANTS_* opt-in for already-modeled engine mechanics.
        v
   [GATE]     the per-iteration gate battery (below): goldfish n=1000 ->
        |     gauntlet n=500 vs anchored decks -> Wilson bands vs anchor.
        v
   [DECIDE]   for each cell:  in-band + bands overlap anchor -> SHIP trustworthy
        |                     >10pp out of band -> classify the divergence:
        |                       structural (engine cannot model) -> FLAG in
        |                         mismodeled_matchups.py, cell stays, ship deck
        |                         with caveat  (NEVER tune toward the anchor)
        |                       coverage/staleness -> re-SOURCE or fix fidelity,
        |                         re-GATE  (a /council call disambiguates when
        |                         the classification is contested)
        v
   [MAINTAIN] two compounding background lanes run between/alongside builds:
        |       (a) cross-canonical oracle-fidelity audit (JB-style) on the
        |           opponent APLs this build leaned on -- each fix raises every
        |           downstream cell's accuracy
        |       (b) card_specs Phase B dedup on any shared card the build
        |           touched (Phlage/Solitude/Ephemerate/Phelia/Galvanic)
        v
   back to [TRIGGER]
```

### Stage detail

**TRIGGER (cadence, section below).** The loop is event-driven. A trigger both
(i) fires a fresh cadence pass and (ii) can itself be the >10pp calibration
divergence that a prior SHIP produced -- so DECIDE feeds back into TRIGGER.

**SELECT.** Take the top queue item whose preconditions hold. Two hard rules:
(1) the interactive tier is a **conditional branch** -- see "WP-A branch gate"
below -- not simply "item 5, do it later"; (2) an in-flight arc (Izzet
Affinity, INFLATED flag, #2 deck) is RESUMED at its next unfinished phase, not
restarted from scratch.

**SOURCE.** Modal 60+15 from 3-5 June-or-later top finishes in `mtg_meta.db`,
resolved via the `db.database.DB_PATH` / `db_bridge` ladder (canonical
`E:\mtg-data\mtg_meta.db`). Write attribution into the deck file header (the
June-2026 pattern in `decks/urzatron_modern.txt` / `goryos_reanimator_modern.txt`
-- N first-place finishes, source, date). **STOP-IF-UNREACHABLE is a real
branch, not a formality:** the Modern side of `mtg_meta.db` has NO post-ban
data (most recent Modern event 2026-04-24; the modeled field in
`format_config.py` is a documented best-estimate, not a pulled snapshot). If
the modal list for the target archetype is not sourceable from the DB, STOP and
report -- never fabricate a decklist (House Rule 8). Melee is accruing post-ban
data now, so this branch is live and improving; re-check the DB each pass.

**BUILD.** Hand-write, house style. Card names as module-level constants.
ASCII-only terminal output. Base on `AwareMatchAPL` when the deck needs the R1
priority stack / counters (set `WANTS_PRIORITY_STACK`) or reactive windows;
plain `MatchAPL` otherwise. Wire per-deck `WANTS_*` opt-in for engine mechanics
that ARE modeled (WANTS_WARP, WANTS_PW_LOYALTY, WANTS_PRIORITY_STACK) rather
than re-implementing them in the APL. Register cleanly in BOTH `APL_REGISTRY`
and `MATCH_APL_REGISTRY`.

**GATE / DECIDE / MAINTAIN** -- see the two sections below.

## WP-A branch gate (why the interactive tier is conditional, not queued)

The engine's interaction model is whitelist MEMBERSHIP, not card behavior:
`counter_resolver.COUNTER_VALIDITY` (18 hand-maintained counterspell entries),
`match_apl.MATCH_REMOVAL` (~37 removal entries keyed by card name), and the
legacy `interaction.py` archetype probability tables. A card absent from those
tables does not interact, regardless of its oracle text. This is exactly why
the P1 calibration cell is INVERTED (5.3% measured vs 40-48% anchors, n=5000):
interaction is the binding constraint.

Consequence: **if you hand-build UW/Azorius Control, Dimir Murktide, or Jeskai
today, every interactive cell is BORN needing a mismodeled flag** -- the deck's
entire game plan (counter, remove, blink, grind) is the part the engine cannot
score. Building them pre-WP-A produces flagged fiction, not trustworthy cells.

The branch:

```
   if  WP-A (oracle-driven responses) SHIPPED
   and anchors RE-VERIFIED from accrued melee + untapped M/W/F fill
   and (for UW Control specifically) per-deck WANTS_PW_LOYALTY wired
   then  UNLOCK interactive tier  ->  Dimir Murktide first (cleanest:
         counter/tempo, no PW dependency), then UW/Azorius Control, then Jeskai
   else  interactive tier stays BLOCKED; work the non-interactive queue
```

Honesty note the loop must respect: WP-A is NECESSARY but for UW Control not
SUFFICIENT. IMPERFECTIONS flags `planeswalker-loyalty-inert-in-match-mode` as
"a major reason control/superfriends score far below real WR." R5 shipped the
engine capability; the residual is per-deck `WANTS_PW_LOYALTY` wiring. So the
loop builds Dimir Murktide (no PW) first after WP-A, and treats UW Control as
gated on BOTH WP-A and the PW-loyalty wiring -- say this in the cell caveat
rather than half-shipping.

## Per-iteration gate battery (the falsifiable gates every build clears)

Determinism protocol for all cells: `seed=42`, `PYTHONHASHSEED=0`. P1 is the
byte-identity instrument; P2 has same-seed drift at HEAD until WP-B lands RNG
threading -- do not demand byte-stability from a P2-flavored cell.

| Gate | Method | Acceptance | Stop trigger |
|---|---|---|---|
| G1 Goldfish pilots | `python sim.py <deck>` then n=1000 goldfish | WR that proves the APL PLAYS the deck (not a crash-stub); avg kill turn in a sane band for the archetype (aggro ~T4-6, combo ~T3-8, control -- goldfish WR is not the metric, no-crash is) | APL exception / 0% WR / kill turn absurd -> STOP, debug the APL |
| G2 Gauntlet | `run_matchup.py` / `parallel_launcher.py` gauntlet n=500 vs anchored field decks, seed=42, PYTHONHASHSEED=0, mix_play_draw | runs to completion, both seats call their APLs, no crash | crash / hidden-hand leak / determinism blow-up -> STOP |
| G3 Wilson bands vs anchor | compute Wilson interval on each cell's WR; compare to the anchor's interval | bands OVERLAP the anchor -> cell is trustworthy | non-overlap AND >10pp out of band -> DECIDE branch (flag vs re-source), see stop conditions |
| G4 Never-tuned attestation | diff the build against the anchor numbers | no code path was changed to move a cell TOWARD an anchor | any tuning-toward-anchor edit detected -> revert, re-derive from oracle text |
| G5 Registry + load | both registries resolve; deck loads 60/15 or audit-marked | clean resolution, zero unresolved cards | unresolved cards / registry miss -> STOP |

Gate predictions are pre-registered: before running G3, write down WHERE each
cell should land and WHY (density of interaction across BOTH decks + whether
the matchup is engine-computed or DB-cached). A gate that fires consults that
prediction (spec-authoring-lessons: gates account for both decks + SIM-vs-DB
source).

## Maintenance lanes (compounding, run between builds)

**Lane A -- cross-canonical oracle-fidelity audit (JB-style).** The 12 oracle
bugs surfaced in `apl/jeskai_blink_match.py` (Solitude white-pitch, Ephemerate
{W} payment, Phelia counter/exile-return, etc.) follow patterns present in less
mature canonical match APLs (Goryo's Solitude white-pitch + missing lifegain
clause; Domain Zoo Phlage hardcast; UW/Esper Blink coverage gaps). Maturity
correlates with oracle fidelity: Boros (1115L) has explicit engine-gap
compensation; a 200-400L APL likely hides 3-12 bugs. Discipline (per
IMPERFECTIONS `cross-canonical-apl-shared-card-bug-pattern` +
`2026-04-29-jeskai-blink-oracle-fidelity-audit.md`):
- Per-deck, one APL at a time. QUOTE the oracle text in every commit body
  (spec-authoring-lessons v1.6).
- Bit-stable canonical gauntlet validation per APL per commit;
  `parallel_launcher.py --deck <APL> --format modern --n 1000 --seed 42`
  pre/post; **surface deviations >5pp** as findings.
- Each fix improves opponent quality -> makes the whole 64.5%/78.8%-style
  baseline more accurate. This is compounding ROI, not busywork.
Audit order (highest impact first): Goryo's, Domain Zoo, Murktide, Izzet
Affinity, Esper Blink, UW Blink.

**Lane B -- card_specs Phase B dedup.** Phlage / Galvanic / Phelia / Solitude /
Ephemerate logic is duplicated inline across `boros_energy.py`,
`jeskai_blink_match.py`, `uw_blink*.py`, `esper_blink*.py`. POC shipped
additive (2026-04-29). Phase B migrates each APL site to import
`apl/card_specs/<card>` and call its functions in place of the inline block,
dedup ~70% of nonland card logic so a Phlage rules update lands in ONE place.
Discipline (per IMPERFECTIONS `card-specs-phase-b-migration-pending`): after
each APL migration, `parallel_launcher.py --deck "<APL>" --format modern --n
1000 --seed 42` pre/post; require **bit-identical or <0.1pp**; **stop trigger
>0.5pp per matchup** (Boros Energy is locked at its canonical baseline --
touching its inline Phlage risks shifting that number). Sequence Phase B AFTER
Lane A on a given card (audit fixes the oracle logic once, THEN dedup the
corrected logic -- not the reverse).

## Cadence (real triggers, not a calendar)

The loop fires on events, not dates:

| Trigger | Detection | Action |
|---|---|---|
| New set drops | set release / handler-audit gap | run `scripts/full_audit.py`; source new modal lists; refresh `format_config.py` field; new/changed archetypes -> queue |
| B&R update | announcement | ban hygiene on affected deck files (remove banned lines, keep legal counts); represent unbans; re-source shifted archetypes (post-May-2026 pattern in mtg-sim CLAUDE.md) |
| Meta shift >2% from analyzer | archetype field share moves >2pp vs the modeled `format_config.py` field (analyzer meta shares) | re-weight the field; if a NEW archetype crosses threshold, queue it; if a modeled one falls out of top-18, retire from field (keep files) |
| Calibration divergence >10pp | a cell's sim WR diverges >10pp from a FRESH anchor (post WP-F anchor pipeline / re-anchor pass) | DECIDE branch: structural -> flag; coverage/staleness -> re-source or fidelity-fix, re-gate |
| Anchor refresh available | accrued melee + untapped M/W/F fill produces fresher matchup WRs | re-verify anchors (this is itself a cadence action -- "vs anchor" is only as good as the anchor; anchors are stale to 2026-04-24) then re-score flagged cells |
| Queue has an unstarted item | idle capacity | pull the next SELECT item |

Note the >10pp threshold is a TWO-WAY signal: it both re-triggers the loop
(cadence) and, at DECIDE, routes to an honest flag. The disambiguation
(structural vs coverage/staleness) is the load-bearing judgment -- when
contested, it is a `/council` gate call (blind, cross-vendor, evidence-cited),
not a solo call.

## Prioritized queue (ordered)

1. **Rakdos Scam** (2.4% field, 81% T8 conversion, ZERO coverage) -- FIRST per
   blueprint. Recon done by the 07-02 agent: registry keys `rakdosscam` /
   `rakdosevoke` slot cleanly; `goryos_reanimator_match` + `boros_energy_match`
   are the templates; Grief ETB discard now fires post `_match_opp` fix
   (verify vs the goryos gauntlet). SOURCE-gate applies: confirm a modal June+
   Rakdos Scam list is in `mtg_meta.db` before building.
2. **Belcher real 60** -- currently a 64-card `audit:stub`; BATCH I0 demands a
   real 60. Source + rebuild. (Belcher's activated-ability kill is a known
   ENGINE limit -- expect a structural flag on the kill cell, not an APL fix.)
3. **Death & Taxes** stub -> real (2.7%). Jitte payoff already in the post-ban
   field; promote the synthetic stub to a real hand-written APL + real list.
4. **Izzet Prowess refactor** ("refactor pending" per quality grades; 4.2%).
   RUN IN PARALLEL: **continue** the Izzet Affinity arc (#2 deck, mid-arc,
   INFLATED flag) -- resume at its next unfinished phase, do not restart.
5. **[WP-A BRANCH GATE] interactive tier** -- BLOCKED until WP-A ships AND
   anchors re-verified. Then: **Dimir Murktide** first (cleanest, no PW dep),
   then **UW/Azorius Control** (also needs WANTS_PW_LOYALTY wired), then
   **Jeskai**. Control is 15%+ of the meta combined -> highest value once
   trustworthy, worthless (flagged fiction) before.
6. **Standard match APLs** -- LAST, and cadence-driven not net-new: Standard is
   already 38/38 covered. This slot is refresh work fired by new-set / B&R /
   meta-shift triggers on the Standard field, not a fresh build wave.

## Honest-flag / never-tune discipline (first-class stop conditions)

These are STOP conditions with teeth (SPEC-FIRST Rule 4), not footnotes:

- **STOP-tune:** if at any point an edit would move a cell TOWARD an anchor or
  gate number, STOP. Never tune toward the anchor (Blueprint House Rule 2 +
  the closing line: "don't you dare tune toward the anchor"). Re-derive the
  behavior from oracle text instead.
- **STOP-fabricate:** if the modal list is not sourceable from `mtg_meta.db`,
  STOP and report -- do not invent a decklist (House Rule 8).
- **FLAG, don't force:** a cell >10pp out of band whose divergence is
  STRUCTURAL (engine cannot model the mechanic: 1-land/turn mana, no own-turn
  instant window, combo assembly rate, hand-size advantage, PW loyalty) gets a
  `mtg-sim/mismodeled_matchups.py` entry with structural attribution + the
  Wilson band + the anchor + the "trust DIRECTION not number" caveat. The cell
  stays wrong-but-flagged; the deck ships. This is the goryos_reanimator /
  boros_energy precedent already in the file.
- **Down-weight in consumers:** every flagged cell is down-weighted by
  deck-selection EV, sideboard planning, and the DECK ANALYSIS PROTOCOL context
  block. The gauntlet drivers print the inline `[!MISMODEL ...]` flag + legend.
- **Contested classification -> council:** when "structural vs
  coverage/staleness" is genuinely arguable, convene `/council` (blind,
  cross-vendor Opus + Codex, evidence-cited) rather than deciding solo. This is
  exactly the M+ / gate-verdict case the council exists for.

## Validation gates (loop-level, meta)

The loop itself is healthy when:

| Gate | Acceptance | Stop trigger |
|---|---|---|
| L1 Every SHIP has a gate record | each shipped deck has its G1-G5 numbers in the commit body | a ship with no gate evidence -> reject the commit |
| L2 Every out-of-band cell is dispositioned | flagged in mismodeled_matchups.py OR re-sourced; none silently shipped | an untracked >10pp cell in a shipped gauntlet -> STOP |
| L3 No tuning-toward-anchor | G4 attestation present per build | any anchor-fit edit -> revert |
| L4 Maintenance lanes drain IMPERFECTIONS | cross-canonical + card_specs entries move toward RESOLVED over successive passes | 30+ days no movement on an OPEN entry -> drift-detect flags it |
| L5 Anchors are current | flagged cells re-scored after each anchor refresh | scoring vs a stale (>60-day) anchor without noting it -> caveat required |

## Stop conditions

- SOURCE unreachable (no modal DB list) -> STOP, report (do not fabricate).
- Any edit tunes toward an anchor/gate -> STOP, revert, re-derive from oracle.
- G1-G5 failure per the battery table -> STOP per that gate's trigger.
- >10pp out-of-band cell whose classification is contested -> STOP, convene
  `/council` before flagging or re-sourcing.
- Interactive-tier item SELECTed while WP-A not shipped -> STOP, it is blocked;
  fall back to the non-interactive queue.
- card_specs Phase B deviation >0.5pp per matchup -> STOP, the dedup changed
  behavior; investigate before landing.
- Cross-canonical audit deviation >5pp -> surface as a finding, decide before
  landing.

## Commit message template (per deck build under this loop)

```
apl: <deck> match APL (WP-C loop, iteration <n>)

Sourced: <N> June+ top finishes, mtg_meta.db, <attribution>
Template: <existing match APL>
Engine opt-in: WANTS_<...>

Gate battery (seed=42, PYTHONHASHSEED=0):
  G1 goldfish n=1000: WR <X>%, avg T<Y>
  G2 gauntlet n=500:  runs clean, both seats call APLs
  G3 Wilson bands vs anchor:
     vs <opp>: sim <X>% [<lo>-<hi>] | anchor <A>% -> IN-BAND / FLAGGED
  G4 never-tuned: attested, no anchor-fit edits
  G5 registry+load: both registries, 60/15 clean

Flags: <mismodeled_matchups.py entries added, if any, with structural why>
Findings doc: <link if new fidelity discovery>
Related: harness/specs/2026-07-04-apl-improvement-loop.md
```

## Annotated imperfections (if any)

```
## apl-loop-anchor-dependency-on-wp-f
**What's not perfect:** The GATE stage compares to anchors that are stale
(matchup_matrix 2026-04-24, pre-ban). Until WP-F publishes a current-window
anchors table from accrued melee + untapped fill, "vs anchor" G3 verdicts are
against pre-ban truth for Modern.
**Why not fixed in this spec:** anchor pipeline is WP-F; this loop is a
consumer. Named as a cadence action, not built here.
**Concrete fix:** consume the WP-F anchors table once published; re-score all
flagged cells against it; note anchor date in every G3 record.
**Estimated effort:** ride-along with WP-F ship.

## apl-loop-interactive-tier-double-precondition
**What's not perfect:** UW/Azorius Control is gated on WP-A AND per-deck
WANTS_PW_LOYALTY wiring, but the loop currently only hard-checks WP-A at SELECT.
**Why not fixed in this spec:** PW-loyalty wiring is per-deck engine opt-in,
tracked in IMPERFECTIONS (planeswalker-loyalty-inert-in-match-mode residual).
**Concrete fix:** at SELECT for UW Control, verify WANTS_PW_LOYALTY is wired +
proven before BUILD; Dimir Murktide (no PW) is the sanctioned first interactive
build to avoid the double-precondition.
**Estimated effort:** per-deck S at build time.
```

After this spec is ratified + the loop runs, surviving imperfections move to
`harness/IMPERFECTIONS.md`.

## Changelog

- 2026-07-04: Created (status PROPOSED). Grounded in BLUEPRINT-2026-07-03 WP-C
  (proven method + queue), IMPERFECTIONS OPEN apl/standard/affinity/cross-
  canonical items, and mtg-sim CLAUDE.md current APL status. Advisor-reviewed
  before authoring (transcribe-don't-reinvent; WP-A as hard branch gate;
  SOURCE stop-if-unreachable; >10pp two-way disambiguation; continue in-flight
  arcs).
