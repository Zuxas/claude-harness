---
title: "Research-Brain Integration (obsidian-second-brain as Harness Research & Synthesis Tier)"
status: SHIPPED
created: 2026-07-03
updated: 2026-07-04
project: harness
estimated_time: 180
related_findings:
  - harness/knowledge/tech/council-2026-07-03-eugeniughelbur-kepano-repos.md
related_commits: []
supersedes: null
superseded_by: null
---

## Goal

Integrate the installed `obsidian-second-brain` vault (`research-brain/`) into the
Zuxas harness as a provisional **Research & Synthesis Tier** that feeds the curated
knowledge base through a **council-gated promotion path**, with all scheduled/automatic
work running on **local models only** (no scheduled Claude token spend).

## Design summary (two tiers, one gate)

- **Tier R — `research-brain/`** (provisional): research sources ingest and the vault
  self-rewrites. Scheduled work is local-draft only.
- **Tier K — `harness/knowledge/`** (canonical): hand-curated, changelog-disciplined
  source of truth. NEVER auto-written by Tier R.
- **Promotion gate** (the only bridge): human-triggered, Claude-assisted. Low-stakes
  facts take a fast path (draft -> stage -> review); falsifiable/numeric/competitive/
  low-confidence claims take a **/council** path that re-verifies against source URLs
  before the block is blessed, embedding the verdict + evidence index in the block's
  changelog.
- **Ingest routing — content-type split:** research sources (URLs/videos/threads) ->
  Tier R; text dumps (reports, discord) -> existing gemma `process-inbox.ps1` lane
  (UNCHANGED, byte-identical).

### Automation boundary (automate-vs-augment decision record)

Per the automate-vs-augment filter (taste-required -> AUGMENT/human-in-loop; purely
quantifiable AND 80%-as-good acceptable -> automate), applied to this spec's scheduled work
(council 2026-07-04, item F):
- **SP-4 nightly ingest = AUTOMATE.** Fetch + local-model draft is mechanical/quantifiable;
  no taste in "did we fetch and draft this URL." Runs unattended (local-only).
- **SP-5 session-mining = PROPOSAL-ONLY / AUGMENT.** "What should become a skill / what's a
  knowledge gap" is taste-based judgment (the source itself concedes this is "an art, not a
  science"). So SP-5 NEVER auto-applies — it emits gated proposals; the human is the verifier.
- **Promotion = AUGMENT.** Human-triggered; council-verified for falsifiable claims.

## Scope

**In:**
- SP-1 Awareness & docs (knowledge block, harness `CLAUDE.md` pointer, `_index`, `MEMORY`, `HARNESS_STATUS`)
- SP-2 Council-gated promotion (deterministic `promote_concept.py` + Claude-driven `/promote` procedure)
- SP-3 Research ingest lane (local-only `ingest_research.py` + queue; text-dump lane untouched)
- SP-4 Scheduled autonomy (nightly local-draft task + morning digest, mirrors gemma drift-PR)
- SP-5 Session-mining improvement loop (local-only; learn from Claude Code history ->
  3-bucket gated proposals). Added 2026-07-04 after evaluating the "5-step self-improving
  system" video: its portable ideas were the 3-bucket approval taxonomy (esp. the
  NEEDS-CONTEXT bucket, folded into SP-2) and mining one's own session history.

**Out (explicit):**
- Enabling the second-brain background agent (`obsidian-bg-agent.sh`) — stays INERT.
- Any automatic write into `harness/knowledge/`.
- Scheduled Claude synthesis (Claude synthesis is on-demand only).
- Paid research toolkit (Grok/Perplexity/`XAI_API_KEY`/`PERPLEXITY_API_KEY`) — keyless
  free-fallback mode only for now; keys are a separate future opt-in.
- Modifying the existing gemma inbox / `compile-knowledge.ps1` / `process-inbox.ps1` behavior.

## Pre-flight reads (mandatory before executing)

1. `harness/knowledge/tech/spec-authoring-lessons.md` (Rule 3 + Rule 9) — esp.
   `windows-powershell-ascii-only-for-ps1-files`, `verify-identifiers-before-spec-execution`,
   `teach-the-tool-not-the-data`.
2. `harness/CLAUDE.md` — LOCAL-LLM DELEGATION section + the CONVENTIONS note that
   `harness/CLAUDE.md` and `harness/MEMORY.md` must be edited with **full-content write**,
   never incremental edit (Obsidian auto-formatter destroys them).
3. `harness/specs/2026-07-03-local-llm-delegation.md` + `harness/agents/routing.yaml` —
   the `delegate` MCP task types (`summarize`, `draft_long` tier-2; `boilerplate` tier-1)
   used for local draft synthesis. VERIFY these task types still exist before use.
4. `research-brain/_CLAUDE.md` — the vault's own operating rules (AI-first, sandbox role).
5. `harness/knowledge/tech/council-2026-07-03-eugeniughelbur-kepano-repos.md` — the
   adoption verdict that motivated this.
6. A knowledge-block sample (e.g. `harness/knowledge/tech/infrastructure.md`) — copy its
   frontmatter + Changelog shape exactly for promoted blocks.
7. `harness/scripts/gemma-drift-pr.ps1` (or `.py`) — the digest pattern SP-4 mirrors.
   VERIFY exact filename before referencing in the scheduled task.

## Steps

### SP-1 — Awareness & docs (no runtime; do first)

1. Create `harness/knowledge/tech/research-brain.md` (knowledge block, standard
   frontmatter): describe the two-tier model, the sandbox rule, the promotion gate
   (fast vs council), ingest routing, install state (skill path, hooks wired,
   bg-agent inert), and the `research-brain/` folder map. Add a Changelog line.
2. Full-content rewrite `harness/CLAUDE.md`: add a `RESEARCH-BRAIN TIER` section
   (peer of LOCAL-LLM DELEGATION) — location, "Tier R is provisional; Tier K is truth;
   never auto-write K", promotion is via council-gated `/promote`, scheduled work is
   local-only. Bump version + Changelog entry.
3. Register the block in `harness/knowledge/_index.md`.
4. Full-content rewrite `harness/MEMORY.md`: add a session entry (what shipped, what's pending).
5. Full-content rewrite `harness/HARNESS_STATUS.md` current-state addendum: add
   research-brain as a capability line.
6. Register THIS spec in `harness/specs/_index.md` under EXECUTING.

### SP-2 — Council-gated promotion

7. Write `harness/agents/scripts/promote_concept.py` (deterministic, testable, no LLM):
   - `--concept <path>`: read a `research-brain/Concepts/*.md` note + its `sources`
     frontmatter; scaffold a Tier-K knowledge block (frontmatter title/domain/
     last_updated/confidence/sources[incl. research-brain note path + source URLs] +
     Summary/Content copied + a Changelog line stamped `promoted from research-brain`);
     write to STAGING `harness/inbox/promoted/<domain>--<block>.md`. NEVER write to
     `harness/knowledge/` in this mode.
   - `--recommend <path>`: print one of `FAST | COUNCIL | NEEDS-CONTEXT` (3-bucket, per
     the video's taxonomy). **NEEDS-CONTEXT** if the concept lacks what a decision needs
     (no `sources`/URL, no `confidence`, or a falsifiable claim with nothing to verify
     against) -> also print a specific question for the human; the concept can't be
     auto-decided OR council-verified until the gap is filled. Else **COUNCIL** if
     `confidence` in {medium, speculation} OR body matches the numeric/competitive-claim
     regex (win-rate %, "beats", "favored", card counts, meta share). Else **FAST**.
     Deterministic, no network.
   - `--commit <staged_path>`: move a reviewed staged block into
     `harness/knowledge/<domain>/` and update `_index.md`. This is the ONLY path that
     writes Tier K, and it runs only after human review.
8. Author the `/promote` Claude procedure in two places: a "Promotion procedure"
   section in `harness/knowledge/tech/research-brain.md`, and a thin command file
   `~/.claude/commands/promote-concept.md` (commands dir confirmed present).
   Procedure: Claude runs `promote_concept.py --recommend`; if COUNCIL, convene
   `/council` on the claim (EMPIRICIST re-derives from the source URLs), embed the
   verdict + evidence index into the staged block's Changelog, then `--commit`
   directly (vetted); if FAST, scaffold to staging, show the user, `--commit` on approval.
9. Create `harness/inbox/promoted/` with a `.gitkeep` + a README stating it is a
   review staging area, not canonical.

### SP-3 — Research ingest lane (local-only)

10. Create the queue: `harness/inbox/research-queue.md` (one URL per line, `#` comments)
    + `harness/inbox/research/` drop folder (for pasted text research).
11. Write `harness/agents/scripts/ingest_research.py` (local-only, NO Claude):
    - For each queue URL: fetch page (curl), reduce to text, call `delegate` MCP
      `run(task_type="summarize", ...)` (or `draft_long` for long pages) to produce an
      AI-first draft Source note; write to `research-brain/Sources/Source - <title> (<date>).md`
      with frontmatter `type: source, ai-first: true, status: pending-synthesis`,
      sources verbatim (URL inline). Move the processed URL to a `# done` section.
    - Idempotent: skip URLs already represented by a Source note (dedupe on URL).
    - Emit a JSON summary (count new, count skipped, errors) to stdout.
12. Write `harness/scripts/ingest-research.ps1` (ASCII-ONLY wrapper) calling the Python.
13. Do NOT touch `process-inbox.ps1` / `compile-knowledge.ps1`. Text-dump lane stays as-is.

### SP-4 — Scheduled autonomy + digest

14. Extend `ingest_research.py` (or a sibling `research_digest.py`) to write
    `harness/inbox/research-brain-digest--<YYYY-MM-DD>.md`: new Source drafts,
    pending-synthesis items, and promotion candidates (Concepts with `confidence: high`
    not yet promoted). Mirrors `gemma-drift-pr` output shape.
15. Add a Windows Scheduled Task (via `register-harness-tasks.ps1` pattern) at ~05:10
    (after drift-PR 04:50) running `ingest-research.ps1` then the digest. `-WakeToRun`.
16. Update the scheduled-tasks reference doc (`docs/harness-scheduled-tasks.md`) + the
    SESSION START PROTOCOL note so the morning read includes the research digest.
16b. **Minimal loop-liveness (council 2026-07-04, item B sliver — ships WITH SP-4, not
    deferred).** The nightly run writes a heartbeat (`harness/state/research-ingest-last-run.json`:
    timestamp, URLs processed, errors). The digest header asserts liveness: if the last
    heartbeat is missing or > 26h stale, the digest leads with a LOOP-DEAD warning. This
    guards the exact failure mode of a silently-dead local-only scheduled job. (Broad
    cross-skill dup-detection / composability = still DEFERRED to a separate hygiene spec.)

### SP-5 — Session-mining improvement loop (local-only, gated)

17. Write `harness/agents/scripts/mine_sessions.py` (local-only, NO Claude): scan recent
    Claude Code session transcripts (JSONL under `~/.claude/projects/<slug>/`) for
    recurring manual patterns, repeated hand-work that should be a skill, and knowledge
    gaps. Delegate `summarize`/`draft_long` to draft the observations. Emit proposals
    bucketed `FAST | NEEDS-SIGNOFF | NEEDS-CONTEXT` into
    `harness/inbox/session-review--<YYYY-MM-DD>.md` with checkbox actions per item
    (`[ ] approve` / `[ ] reject` / `[ ] approve + don't ask again`). NEVER auto-apply to
    `harness/knowledge/` or `harness/skills/` — proposals only.
18. Wrapper `harness/scripts/mine-sessions.ps1` (ASCII-ONLY). Optional weekly scheduled
    task (same local-only constraint as SP-4). The human applies approved items by hand.
    Note: this loop is INTERNAL process improvement (how I work), orthogonal to
    research-brain's EXTERNAL knowledge ingest.

## Validation gates (falsifiable)

- **G1 (SP-1):** `grep -c "RESEARCH-BRAIN TIER" harness/CLAUDE.md` == 1 AND
  `research-brain.md` appears in `harness/knowledge/_index.md`. Expect: both true.
- **G2 (SP-2 safety):** Run `promote_concept.py --concept <seeded test concept>` -> a
  valid block appears in `harness/inbox/promoted/` and `git status harness/knowledge/`
  shows ZERO changes. Expect: staged file present, knowledge/ untouched. (This is the
  data-loss guard — the whole council's #1 objection.)
- **G3 (SP-2 recommend):** `--recommend` returns `COUNCIL` on a seeded concept containing
  "60% win rate vs Boros" (with a source), `FAST` on "Karsten published article X on
  2026-06-30" (with a source), and `NEEDS-CONTEXT` on a bare claim with no `sources`.
  Expect: exact strings.
- **G4 (SP-2 commit):** `--commit` on a staged block writes to `harness/knowledge/<domain>/`
  AND `_index.md` gains one line. Expect: block present, index updated, changelog intact.
- **G5 (SP-3 isolation):** `process-inbox.ps1`, `compile-knowledge.ps1`, and
  `watch-inbox.ps1` are unmodified by SP-3 (their file hashes match pre-SP-3). Expect:
  identical hashes — the text-dump lane is untouched (no assumed dry-run flag).
- **G6 (SP-3 local-only):** `grep -riE "anthropic|api\.anthropic|claude -p|ANTHROPIC_API_KEY" harness/agents/scripts/ingest_research.py harness/scripts/ingest-research.ps1`
  returns NOTHING. Expect: no matches (scheduled path spends zero Claude tokens).
- **G7 (SP-4 digest):** A manual run of the scheduled command produces
  `harness/inbox/research-brain-digest--<today>.md` with the three sections. Expect: file exists, non-empty.
- **G8 (ASCII):** Every new `.ps1` has no byte > 0x7F. Expect: clean (per the lesson).
- **G9 (SP-5 local-only + proposal-only):** `grep -riE "anthropic|api\.anthropic|claude -p"`
  over `mine_sessions.py`/`mine-sessions.ps1` returns NOTHING, AND a dry run writes only
  `harness/inbox/session-review--<today>.md` with `git status harness/knowledge harness/skills`
  showing ZERO changes. Expect: no matches; review file present; knowledge/ + skills/ untouched.
- **G10 (SP-4 loop-liveness):** after a nightly run, `harness/state/research-ingest-last-run.json`
  exists with a fresh timestamp; simulate a stale/missing heartbeat and confirm the digest
  header leads with a `LOOP-DEAD` warning. Expect: heartbeat written; stale case flagged.

## Stop conditions (teeth)

- `promote_concept.py` (non-`--commit` mode) writes ANY file under `harness/knowledge/`
  -> ABORT, fix the staging boundary before continuing.
- Any SP-3/SP-4 scheduled-path script imports/invokes the Anthropic API or a Claude CLI
  -> ABORT (violates local-only scheduled constraint).
- SP-3 changes `process-inbox.ps1` output (G5 fails) -> ABORT (scope violation).
- A `delegate` task_type referenced by `ingest_research.py` does not exist in
  `routing.yaml` -> STOP, reconcile identifier before running (verify-identifiers lesson).
- **[SP-5 eval gate — council 2026-07-04]** A mined proposal that would EDIT sim code or a
  skill file is applied WITHOUT first re-passing the relevant numeric regression
  (`lint-mtg-sim.py` / goldfish kill-turn band / gauntlet WR / drift <= 0.05 turn) -> ABORT.
  A self-improving change touching code/skills must clear a NUMERIC gate, not a human
  checkbox alone (Rule 4 + Rule 5 applied to write-back). SCOPE: this gate fires ONLY for
  code/skill-touching changes; pure-prose knowledge/description proposals are EXEMPT (their
  quality is taste-based / non-numeric — human review is the verifier there).

## Estimated time

~245 min: SP-1 ~40 (docs), SP-2 ~70 (script + procedure + tests), SP-3 ~45 (ingest +
dedupe), SP-4 ~40 (digest + task + liveness heartbeat/G10), SP-5 ~35 (session-mining +
gated review + eval-gate stop condition). Build in order; stop-and-report between SPs (Rule 7).

## Annotated imperfections (known limits of this spec's scope)

- **Keyless research = degraded.** Free-fallback sources only (Wikipedia/HN/arXiv/Reddit);
  Grok/Perplexity depth needs keys (out of scope). Fix path: add keys to
  `~/.config/obsidian-second-brain/.env`, separate opt-in.
- **bg-agent remains inert AND cwd-ungated if ever enabled** — enabling would write to
  research-brain on every compaction in every project. Intentionally not wired live.
- **Council promotion cost.** The council path is heavy; the heuristic keeps it rare, but
  a mis-tuned regex could over-escalate. Tune the `--recommend` regex from real usage.
- **Local draft quality.** `summarize`/`draft_long` drafts are provisional by design;
  Claude on-demand synthesis + the promotion gate are the quality backstops.
- **Fetch fragility.** `ingest_research.py` curl-fetch will miss JS-heavy pages; defuddle
  (kepano skill) integration is a follow-up upgrade, not in this spec.

## Mid-execution amendments
- 2026-07-04 (SP-3/4/5 SHIPPED -> spec SHIPPED): built via a 5-subagent pipeline +
  independent verification agent. SP-3: `ingest_research.py` (440L, local-only URL fetch
  + Ollama-direct draft [not the delegate MCP -- a headless script can't call MCP; hits
  localhost:11434 like ask-gemma], Source-note writer, dedupe, heartbeat), `research-queue.md`,
  `inbox/research/`, `ingest-research.ps1`. SP-4: `research_digest.py` (321L, LOOP-ALIVE/
  LOOP-DEAD liveness off the heartbeat, 3 sections), `register-research-task.ps1` (dry-run
  default -- registration is a HOT ZONE, left for user `-Execute` sign-off), scheduled-tasks
  doc row. SP-5: `mine_sessions.py` (404L, local-only, proposal-only, 3-bucket review +
  EVAL-GATE line on code/skill proposals), `mine-sessions.ps1`. ALL GATES PASS
  (independent verifier + my own confirm): G5 text-dump lane unmodified, G6/G9 zero Claude
  refs, G7 digest writes (LOOP-DEAD until first run), G8 ASCII (0 non-ASCII in all 3 .ps1),
  G10 heartbeat liveness, all `--selftest` OK. Design note: `delegate` MCP task-types in
  the original spec are conceptual; the scripts call Ollama HTTP directly (still local, G6-clean).
- 2026-07-04 (SP-2 SHIPPED): built `promote_concept.py` (3 modes + `--selftest`, hard
  `_assert_not_writing_knowledge` guard), `harness/inbox/promoted/` staging + README,
  `~/.claude/commands/promote-concept.md`. Gates G2/G3/G4 PASS. Two bugs caught by the
  gates (not the subagent selftest) and fixed: (1) `--recommend` URL check was body-only
  -> a source-URL-in-frontmatter claim wrongly returned NEEDS-CONTEXT; now checks body OR
  sources. (2) `--commit` appended the index row without a trailing-newline guard -> glued
  onto the prior line; now newline-safe. Repaired one lost `_index.md` row from the first
  test's cleanup. LESSON CANDIDATE (Rule 9, add on SHIP): a subagent's own selftest
  encodes the subagent's assumptions -- only an independent adversarial fixture catches
  the blind spot; and file-appends need a newline guard or they corrupt the prior line.

## Changelog
- 2026-07-03: PROPOSED. Authored via brainstorming after council adoption verdict.
  Decisions ratified by user: Deep integration; local-first draft + Claude on-demand
  synthesis; content-type-split ingest; council-gated promotion; fast-path stages to
  `inbox/promoted/`; build all four SPs.
- 2026-07-04: Amended after user evaluated the "5-step self-improving system" video.
  Folded in two portable ideas: (1) 3-bucket approval taxonomy -> `--recommend` now
  returns FAST | COUNCIL | NEEDS-CONTEXT (SP-2, G3); (2) added SP-5 session-mining loop
  (local-only, proposal-only, G9). Rejected the video's cavalier "not that serious /
  auto-approve" posture as unsafe for falsifiable knowledge (verification is why the
  council gate exists). Est. time 180 -> 215 min.
- 2026-07-04: Amended after council-verifying the loop-engineering handoff (verdict:
  `knowledge/tech/council-2026-07-04-loop-engineering-handoff.md`). Council corrected the
  orchestrator on 3 points: (1) eval-gate is now a scoped STOP CONDITION (mined code/skill
  changes must re-pass a numeric regression before applying; pure-prose exempt); (2) minimal
  loop-liveness heartbeat now ships WITH SP-4 (step 16b, G10) instead of deferring all of
  item B; (3) added an automate-vs-augment decision record (item F folded, not deferred).
  Items C (ALREADY the ARL), D/E, and broad-B remain out of scope / deferred. Est. 215 -> 245 min.
