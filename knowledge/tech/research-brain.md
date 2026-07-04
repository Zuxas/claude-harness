---
title: "Research-Brain Tier (obsidian-second-brain integration)"
domain: "tech"
last_updated: "2026-07-04"
confidence: "high"
sources:
  - "harness/specs/2026-07-03-research-brain-integration.md"
  - "harness/knowledge/tech/council-2026-07-03-eugeniughelbur-kepano-repos.md"
  - "session-2026-07-03/04 (install + brainstorming)"
---

## Summary

`research-brain/` is a SECOND, self-rewriting Obsidian vault (the installed
`eugeniughelbur/obsidian-second-brain` skill) that acts as the harness's **Research &
Synthesis Tier** — a provisional front-end where external research is ingested and the
vault rewrites its own pages to synthesize and reconcile. It is deliberately SEPARATE
from the curated harness knowledge base (`harness/knowledge/`), which remains the
canonical source of truth. The two are bridged by ONE human-gated, council-verified
**promotion** path. Scheduled/automatic work runs on LOCAL models only (no scheduled
Claude token spend). This block is the durable record of what it is, why, and how to use it.

## Why (council verdict, 2026-07-03)

A blind 4-seat council (3 Claude + cross-vendor GPT-5.5 Codex) evaluated adopting
`obsidian-second-brain` wholesale and voted AGAINST installing its auto-rewriter over
`harness/knowledge/`: it rewrites 5-15 pages per ingest, this workspace root is not a git
repo (no undo), and auto-synthesis can fabricate/drift and poison falsifiable state. The
ratified path (user-approved): run it on a SEPARATE, git-tracked vault; bridge to the
harness only through a promotion gate. See `council-2026-07-03-eugeniughelbur-kepano-repos.md`.

## Two-tier model

- **Tier R — `E:\vscode ai project\research-brain\`** (provisional): self-rewriting; git-
  tracked (`git checkout -- .` = undo any ingest). Scheduled work is local-draft only.
  Folders: `Sources/` (one note per ingested source, provenance verbatim), `Concepts/`
  (synthesized self-rewriting pages), plus `Projects/People/Tasks/Daily/Logs/Bases/`.
  Own operating rules in `research-brain/_CLAUDE.md`.
- **Tier K — `harness/knowledge/`** (canonical): hand-curated, changelog-disciplined.
  **NEVER auto-written by Tier R.** Promotion into it is the only bridge and is manual.

## Promotion gate (the bridge)

Promotion = moving a vetted Tier-R Concept into a Tier-K knowledge block. Deterministic
file ops live in `harness/agents/scripts/promote_concept.py`; judgment is Claude-driven.
`promote_concept.py --recommend <concept>` returns a **3-bucket** verdict:

- **FAST** — uncontested who/what/when/link facts: Claude drafts the block -> stages to
  `harness/inbox/promoted/` -> user approves -> `--commit` writes Tier K + updates `_index.md`.
- **COUNCIL** — falsifiable/numeric/competitive claims OR `confidence: medium|speculation`:
  convene `/council` (EMPIRICIST re-derives the claim from the Concept's source URLs;
  CONTRARIAN tries to refute) BEFORE blessing. The verdict + evidence index is embedded in
  the promoted block's Changelog (verification lineage travels with the fact). Vetted ->
  `--commit` directly.
- **NEEDS-CONTEXT** — missing what a decision needs (no source/URL, no confidence, a claim
  with nothing to verify against): returns a specific question; not promotable until filled.

The council is the immune system at the tier boundary — it quarantines second-brain's
fabrication risk behind the harness's most rigorous existing tool. It is OPT-IN by
heuristic (rare), never mandatory on every promotion (routine facts take FAST).

## Ingest routing — content-type split

- **Research sources** (URLs, videos, X threads, exploratory reading) -> Tier R via
  `harness/inbox/research-queue.md` + `harness/inbox/research/`, drained nightly by
  `ingest_research.py` (LOCAL fetch + local-model draft; NO Claude on schedule).
- **Text dumps** (tournament reports, discord you KNOW become one block) -> the existing
  gemma `process-inbox.ps1` -> `compile-knowledge.ps1` lane, UNCHANGED.

## Synthesis engine (policy-compliant)

Local-first draft + Claude on-demand. Scheduled ingest + first-pass synthesis run on
local models via the `delegate` MCP (`summarize`/`draft_long` task types). Claude does the
real cross-page reconciliation ONLY when invoked (e.g. before a promotion pass). Honors the
harness rule: local = worker, Claude = thinker, no silent scheduled token burn.

## Install state (as of 2026-07-04)

- Skill: `~/.claude/skills/obsidian-second-brain/` (git clone, MIT). Vault path set in
  `~/.claude/settings.json` env `OBSIDIAN_VAULT_PATH` -> research-brain.
- Hooks: SessionStart `load_vault_context.py` ACTIVE but self-gates to vault cwd (invisible
  in harness sessions). PostCompact bg-agent WIRED INERT (never armed; `OBSIDIAN_BG_AGENT_ENABLED`
  unset — it is cwd-ungated if ever enabled, so leave off). 44 slash commands in `~/.claude/commands/`.
- Vault initialized (`_CLAUDE.md`, `index.md`, `log.md`, `Logs/`, `Bases/`), git-tracked.
- Research toolkit (Grok/Perplexity/`/x-read`/`/research-deep`) is in KEYLESS free-fallback
  mode (Wikipedia/HN/arXiv/Reddit) until API keys are added to
  `~/.config/obsidian-second-brain/.env` — separate opt-in.

## Session-mining loop (SP-5, sibling capability)

`mine_sessions.py` (local-only) mines recent Claude Code session transcripts for recurring
manual patterns and skill/knowledge gaps, emitting 3-bucket gated proposals to
`harness/inbox/session-review--<date>.md`. This is INTERNAL process improvement (how work is
done), orthogonal to research-brain's EXTERNAL knowledge ingest. Proposal-only; never auto-applies.

## Build status

Spec `harness/specs/2026-07-03-research-brain-integration.md` **SHIPPED 2026-07-04** (all
5 SPs, built via a 5-subagent pipeline + independent verification). Scripts:
- `harness/agents/scripts/promote_concept.py` -- council-gated 3-bucket promotion (SP-2)
- `harness/agents/scripts/ingest_research.py` -- local research ingest (SP-3)
- `harness/agents/scripts/research_digest.py` -- nightly digest + LOOP-ALIVE/DEAD liveness (SP-4)
- `harness/agents/scripts/mine_sessions.py` -- session-mining, proposal-only (SP-5)
- wrappers in `harness/scripts/` (ingest-research / register-research-task / mine-sessions)
- `~/.claude/commands/promote-concept.md` command; queue at `harness/inbox/research-queue.md`

**Two user-gated follow-ups (by design, not blockers):** (1) register the 05:10 nightly
task via `register-research-task.ps1 -Execute` (scheduled tasks are a HOT ZONE -> needs
sign-off); (2) add Grok/Perplexity keys for full-strength research (keyless = free-fallback).

## Changelog
- 2026-07-04: Created during SP-1. Records the research-brain tier, two-tier model,
  council-gated 3-bucket promotion, content-type-split ingest, local-first synthesis,
  install state, and the SP-5 session-mining sibling. Motivated by the 2026-07-03 council verdict.
