# HARNESS_STATUS.md — Current System State & Roadmap
# For: Claude Code context loading
# Updated: 2026-04-15
# Read this file to understand what the harness IS, what it DOES today,
# and what each future layer adds.

---

## WHAT EXISTS RIGHT NOW (Layer 1 — Operational)

### Knowledge Persistence
**Problem solved:** Every Claude Code session used to start from zero.
Jermey had to re-explain his team, his projects, his infrastructure,
his competitive history — every single time.

**How it works now:**
- `CLAUDE.md` at project root forces Claude Code to read knowledge blocks
  before answering ANY question
- 12 knowledge blocks in `harness/knowledge/` contain compiled context:
  team roster, competitive history, project architecture, infrastructure,
  career goals, family context, tool configurations
- Blocks use YAML frontmatter + markdown + wikilinks for cross-referencing
- `MEMORY.md` tracks session state so work carries across conversations
- Obsidian renders the blocks as a visual graph for human editing

**Benefit:** Claude Code answers with YOUR context on the first message.
No re-explaining. No generic advice. Specific, grounded, personalized.


### Local Model Pipeline (Gemma 4 via Ollama)
**Problem solved:** Every question cost API tokens. Routine work like
summarizing articles, compiling notes, quick lookups — all burned tokens
that should have been free.

**How it works now:**
- Ollama runs Gemma 4 locally on RTX 3080 LHR (10GB VRAM)
- Two models: gemma4 (12B, fast) and gemma4:26b (MoE, smarter)
- `ask-gemma.ps1` — quick questions, optional file context, $0.00/query
- `compile-knowledge.ps1` — feeds raw text to Gemma, outputs a formatted
  knowledge block with frontmatter, saves to knowledge/, updates _index.md
- `process-inbox.ps1` — drop files named `domain--blockname.txt` into
  `harness/inbox/`, script batch-compiles them all via Gemma
- Performance: ~18-20 tokens/sec, zero cost, complete privacy

**Benefit:** Knowledge base grows without spending tokens. Copy-paste a
Reddit post, Discord chat, article, or tournament report into a .txt file,
drop it in inbox/, run the processor. Gemma compiles it into a structured
block that Claude Code reads next session.

### Token Compression (RTK)
**Problem solved:** Claude Code terminal commands (git status, dir, cargo
build) dump massive output into the context window, wasting tokens.

**How it works now:**
- RTK v0.36.0 proxies all Claude Code terminal commands
- Compresses output 60-90% before it enters context
- Windows: CLAUDE.md injection mode (global at ~/.claude/CLAUDE.md)
- Claude Code automatically prefixes commands with `rtk`

**Benefit:** Same information, 60-90% fewer tokens consumed. Directly
extends how much work fits in a single Claude Code session.


### APL Tuner Agent
**Problem solved:** Testing and analyzing deck performance in mtg-sim
required manual sim runs, manual interpretation, and manual note-taking.

**How it works now:**
- `apl_tuner.py` orchestrates: load deck -> find APL -> run goldfish sim
  -> (optional) run matchup gauntlet -> feed results to Gemma 4 for
  analysis -> write knowledge block to harness/knowledge/mtg/
- Modes: validate (sim only), analyze (sim + Gemma), full (sim + gauntlet + Gemma)
- Wrapper: `tune-apl.ps1 "Deck Name" -Mode full -Format modern`
- Lists all 32 hand-written APLs + 21 match-aware APLs
- Output: `sim-{deckname}.md` knowledge block with kill turn stats,
  matchup data, Gemma's analysis of weak matchups and improvement suggestions

**Benefit:** One command produces a complete sim report + AI analysis +
persistent knowledge block. Claude Code can read the report next session
and discuss results without re-running anything. Cost: $0.00.

---

## CURRENT DATA FLOW

```
                     YOU (manual input)
                      |
        +-----------+------------+-----------+
        |           |            |           |
   copy-paste   game logs   sim results   notes
        |           |            |           |
        v           v            v           v
   harness/inbox/  (future)  apl_tuner   Obsidian
        |                        |           |
        v                        v           v
  process-inbox.ps1         Gemma analysis  direct edit
        |                        |           |
        v                        v           v
     Gemma 4 (local, $0.00)     |           |
        |                        |           |
        v                        v           v
  harness/knowledge/*.md  <-- all paths lead here
        |
        v
  Claude Code reads on next session startup
        |
        v
  Informed, contextual responses from Claude
```


## WHAT EACH FUTURE LAYER ADDS

### Layer 2 — Scheduled Automation (next build session)
**What changes:** The system works while Jermey sleeps.

**Components to build:**
- Windows Task Scheduler job running `process-inbox.ps1` every 15 minutes
- FileSystemWatcher on `harness/inbox/` for instant compilation on drop
- Nightly job that checks meta-analyzer DB for new events, triggers
  `apl_tuner.py` on any deck whose meta% shifted >2%
- Auto-update of MEMORY.md with what ran overnight

**What improves:**
- No more "run the script manually" — drop file, walk away, it compiles
- Meta shifts detected automatically instead of Jermey checking manually
- Knowledge base grows passively from automated data sources
- Claude Code sessions start with fresher data

**What still requires human input:**
- Feeding non-scraped content (articles, Discord, Reddit)
- Reviewing Gemma's analysis for accuracy
- Making strategic decisions

### Layer 3 — Autonomous Tuning Loop (2-3 sessions after Layer 2)
**What changes:** The system proposes and tests its own improvements.

**Components to build:**
- Git branch manager: creates experiment branches for APL changes
- Tuning loop: applies Gemma's suggested APL changes -> re-sims ->
  compares before/after win rates -> auto-reverts if worse
- Scoring function: defines "better" (field-weighted win rate threshold)
- Notification: Discord bot message or file flag when improvements found
- botctl or PM2: keeps the tuning agent running 24/7 as a background process

**What improves:**
- APL optimization happens automatically between sessions
- System tests card swaps, sequencing changes, mulligan adjustments
  on its own and reports results
- Jermey reviews and approves instead of driving every test manually
- Each successful optimization is logged in knowledge blocks so the
  system learns what types of changes tend to improve performance

**What still requires human input:**
- Approving changes before they go to main branch
- Providing real-match feedback ("that SB plan was wrong because X")
- Setting strategic direction ("optimize for RC DC field")


### Layer 4 — Real Match Feedback Loop (3-5 sessions after Layer 3)
**What changes:** The system learns from actual games, not just simulations.

**Components to build:**
- MTGA log parser: extracts match results, mulligans, card performance
  from Arena game logs automatically
- Feedback ingestion: real match data flows into knowledge blocks
- Sim calibration: compares sim predictions vs real results, adjusts
  eval weights and APL priorities based on discrepancies
- Confidence scoring: blocks track whether they're based on sim data
  (medium confidence) vs real match data (high confidence)

**What improves:**
- System detects when sim predictions don't match reality
- APL tuning is grounded in actual competitive results, not just theory
- Knowledge blocks carry confidence ratings based on data source
- The gap between "what the sim says" and "what happens at the table"
  gets measured and actively closed

**What still requires human input:**
- Playing the actual games
- Qualitative feedback (why a matchup felt different than expected)
- Meta-level strategy that can't be simulated (reads, bluffs, sequencing
  decisions the sim engine doesn't model)

### Layer 5 — Full Pipeline Automation (5-10 sessions after Layer 4)
**What changes:** The system maintains itself end-to-end.

**Components to build:**
- Claude API integration for APL generation (auto_apl.py already exists)
- Auto-detection of new archetypes from scraper data
- APL generation for new decks without human intervention
- Playbook generator: sim data + knowledge blocks -> draft playbook HTML
- Website updater: pushes draft playbooks for review
- Budget manager: tracks Claude API spend, falls back to Gemma for
  cheap tasks, escalates to Claude only when needed
- Long-term optimization memory: tracks which APL changes improved
  win rates across all previous experiments

**What improves:**
- New deck appears in the meta -> system generates APL -> tests it ->
  runs gauntlet -> writes analysis -> drafts playbook -> all without
  human intervention
- The system gets smarter over time because it remembers what worked
- Cost stays controlled because Gemma handles bulk work, Claude handles
  complex reasoning only when needed
- Jermey shifts from "operator" to "reviewer and strategist"


---

## WHY THIS ARCHITECTURE COMPOUNDS

The key insight is that every layer makes every OTHER layer more valuable:

1. **Knowledge blocks** make Claude Code smarter per session
2. **Gemma compiler** makes knowledge blocks cheaper to create
3. **RTK** makes Claude Code sessions longer (more tokens = more work)
4. **APL tuner** creates knowledge blocks automatically from sim data
5. **Scheduled automation** (Layer 2) makes the tuner run without humans
6. **Tuning loop** (Layer 3) makes the sim results feed back into APLs
7. **Real match data** (Layer 4) makes sim calibration more accurate
8. **Full pipeline** (Layer 5) makes the entire system self-maintaining

Each layer removes a human bottleneck. The system doesn't get "smarter"
in the AI sense — it gets more CONNECTED. More data flows automatically,
more analysis happens without manual triggers, more knowledge persists
across sessions. The human shifts from operator to strategist.

## DESIGN PRINCIPLES (for future Claude Code sessions)

1. **Knowledge blocks are the source of truth.** Read them before answering.
2. **Gemma handles cheap work, Claude handles complex work.** Don't use
   Claude API tokens for tasks Gemma can do locally.
3. **Everything writes back to knowledge blocks.** Sim results, analysis,
   session notes — all persist as markdown in harness/knowledge/.
4. **MEMORY.md tracks state.** Update it when completing tasks.
5. **The inbox is the input funnel.** Raw content -> inbox/ -> Gemma compiles
   -> knowledge block. This is the standard ingestion path.
6. **Three-agent pattern when complexity warrants it.** Planner reads
   context + writes plan. Executor works the plan. Evaluator reviews output
   and updates knowledge blocks.

---

## SCRIPT REFERENCE (for Claude Code to call directly)

| Script | Location | Purpose |
|--------|----------|---------|
| `kb-status.ps1` | `harness/scripts/` | Health check: block count, line counts, dates |
| `ask-gemma.ps1` | `harness/scripts/` | Quick query to local Gemma 4 |
| `compile-knowledge.ps1` | `harness/scripts/` | Raw text -> knowledge block via Gemma |
| `process-inbox.ps1` | `harness/scripts/` | Batch compile inbox/ drop folder |
| `tune-apl.ps1` | `harness/scripts/` | APL tuner: sim + analysis + knowledge block |
| `parse-mtga.ps1` | `harness/scripts/` | Parse MTGA logs -> match_log DB + knowledge block |
| `load-context.ps1` | `harness/scripts/` | Load knowledge blocks by domain |
| `apl_tuner.py` | `harness/agents/scripts/` | Python APL tuning pipeline |
| `mtga_log_parser.py` | `mtg-meta-analyzer/scrapers/` | MTGA log parser (core Python module) |

## FILE STRUCTURE

```
harness/
  CLAUDE.md              <- master config (read by Claude Code)
  MEMORY.md              <- session state
  HARNESS_STATUS.md      <- THIS FILE (system overview + roadmap)
  HARNESS_GUIDE.txt      <- operations manual for Jermey
  WORKING_WITHOUT_CLAUDE.txt <- solo operations guide
  THURSDAY_PROCEDURES.txt <- verification checklist
  inbox/                 <- drop raw files here for compilation
    processed/           <- originals move here after compilation
  knowledge/
    _index.md            <- block registry
    _template.md         <- new block template
    mtg/                 <- 5 blocks (team, history, analyzer, legacy, sim report)
    career/              <- 2 blocks (profile, projects)
    tech/                <- 5 blocks (infra, harness, powershell, rtk, obsidian)
    personal/            <- 1 block (family)
  agents/
    planner.md           <- planner system prompt
    evaluator.md         <- evaluator system prompt
    scripts/
      apl_tuner.py       <- APL tuning pipeline
  scripts/
    kb-status.ps1        <- health check
    ask-gemma.ps1        <- quick query
    compile-knowledge.ps1 <- knowledge compiler
    process-inbox.ps1    <- inbox batch processor
    tune-apl.ps1         <- APL tuner wrapper
    load-context.ps1     <- context loader
    install-stack.ps1    <- install reference
```


---

## LAYER 4: Real Match Feedback (OPERATIONAL — 2026-04-16)

### Sim Calibration
**Problem solved:** The sim predicts matchup win rates but has no way
to know if those predictions match reality. A deck that sims at 70%
might actually perform at 50% due to factors the sim doesn't model.

**How it works now:**
- `calibrate.py` reads real match results from `match_log` table
- Aggregates by matchup (my_deck vs opp_deck)
- Runs sim prediction for the same matchup
- Compares: Real WR vs Sim WR = Delta
- Scores accuracy: accurate (<5%), close (<10%), divergent (<20%), wrong (>20%)
- Writes calibration report to `knowledge/mtg/calibration-YYYY-MM-DD.md`
- Integrated into nightly harness as Step 4/5

**Accuracy scoring:**
- `accurate`: sim within 5% of reality (sim is trustworthy)
- `close`: sim within 10% (small adjustment needed)
- `divergent`: sim off by 10-20% (APL or eval weights need work)
- `wrong`: sim off by 20%+ (fundamental modeling error)
- `low_sample_ok/divergent`: fewer than 5 matches (need more data)

**Data flow:**
```
Arena game -> MTGA log -> parse-mtga.ps1 -> match_log DB
                                               |
                                               v
                                   calibrate.py (reads match_log)
                                               |
                                               v
                               sim prediction for same matchup
                                               |
                                               v
                            Real WR vs Sim WR = Delta + accuracy score
                                               |
                                               v
                          calibration-YYYY-MM-DD.md knowledge block
                                               |
                                               v
                     Claude Code + tuning loop know where sim is wrong
```

**What's needed for full calibration:**
- Play Arena games and run parse-mtga.ps1 after each session
- Tag opponent decks (Arena logs don't include opponent decklists)
- Accumulate 5+ matches per matchup for statistically meaningful data
- Future: automatic archetype detection from cards seen in logs


---

## COMPLETE SYSTEM STATUS (2026-04-16)

### All Layers
| Layer | Name | Status | Built |
|-------|------|--------|-------|
| 1 | Knowledge Persistence | OPERATIONAL | 2026-04-14 |
| 1 | Local Model Pipeline | OPERATIONAL | 2026-04-15 |
| 1 | Token Compression | OPERATIONAL | 2026-04-15 |
| 1 | APL Tuner Agent | OPERATIONAL | 2026-04-15 |
| 1 | MTGA Log Parser | OPERATIONAL | 2026-04-15 |
| 2 | Scheduled Nightly Job | OPERATIONAL | 2026-04-16 |
| 2 | Inbox File Watcher | OPERATIONAL | 2026-04-16 |
| 3 | Autonomous Tuning Loop | OPERATIONAL | 2026-04-16 |
| 3 | Card Legality Checker | OPERATIONAL | 2026-04-16 |
| 4 | Sim Calibration | OPERATIONAL | 2026-04-16 |

### Script Inventory (14 wrappers + 4 agents)
| Script | Layer | Purpose |
|--------|-------|---------|
| ask-gemma.ps1 | 1 | Quick Gemma query ($0.00) |
| compile-knowledge.ps1 | 1 | Raw text -> knowledge block |
| process-inbox.ps1 | 1 | Batch compile inbox/ folder |
| kb-status.ps1 | 1 | Knowledge base health check |
| tune-apl.ps1 | 1 | Sim + Gemma analysis |
| parse-mtga.ps1 | 1 | Arena logs -> match DB |
| load-context.ps1 | 1 | Load blocks by domain |
| watch-inbox.ps1 | 2 | Auto-compile on file drop |
| nightly-harness.ps1 | 2 | Nightly automation |
| register-harness-tasks.ps1 | 2 | Task Scheduler setup |
| tune-loop.ps1 | 3 | Autonomous tuning loop |
| calibrate.ps1 | 4 | Sim vs reality comparison |
| stress-test.ps1 | - | Full system health check |
| install-stack.ps1 | - | Install reference |

### Agent Scripts (Python)
| Script | Layer | Purpose |
|--------|-------|---------|
| apl_tuner.py | 1 | APL sim + analysis pipeline |
| nightly_harness.py | 2 | Nightly automation brain |
| tuning_loop.py | 3 | Propose/test/compare swap loop |
| calibrate.py | 4 | Real match feedback calibration |

### Knowledge Base
- 17 blocks, 741 lines across 4 domains
- Auto-generated blocks: sim reports, tuning experiments, calibration reports
- Human-written blocks: team, career, infrastructure, competitive history

### Scheduled Tasks
| Time | Task | Source |
|------|------|--------|
| 6:00 AM | Background fill (all formats) | meta-analyzer |
| 5:00 PM | Daily scraper (Standard) | meta-analyzer |
| 5:30 PM | Nightly harness (Modern) | harness Layer 2 |
| 6:30 PM | Nightly harness (Standard) | harness Layer 2 |
| On login | Inbox watcher | harness Layer 2 |
| Sunday | Scryfall refresh | meta-analyzer |


## LAYER 5: Full Pipeline Automation (OPERATIONAL -- 2026-04-16; nightly-wired feature-flagged 2026-04-28)

### Auto Pipeline
**Problem solved:** When a new deck appears in the meta, someone has to
manually write an APL, test it, analyze it, and draft a playbook. This
is hours of work per archetype.

**Wire status (updated 2026-04-28):** auto_pipeline.py is wired into
nightly_harness.py as STEP 1.5, behind the `--enable-auto-pipeline`
flag (default OFF for Friday-safety). When enabled, defaults to Gemma
($0.00). To opt into Claude path, pass BOTH `--enable-auto-pipeline`
AND `--auto-pipeline-use-claude` (two opt-ins to bill Anthropic).
The PowerShell wrapper `nightly-harness.ps1` exposes both as
`-EnableAutoPipeline` and `-AutoPipelineUseClaude` switches. Friday's
scheduled task command line does NOT include the flag; user can
flip it manually after observing a few unattended runs. Spec:
`harness/specs/2026-04-28-auto-pipeline-nightly-integration.md`.

**Output flow (updated 2026-04-28 via S4):** auto_pipeline now generates
deck files alongside APLs by pulling most-recent-top-finish from the
meta-analyzer DB, runs a smoke gate (50 goldfish games), and registers
passing APLs into a sidecar `data/auto_apl_registry.json`. The canonical
`apl/__init__.py:APL_REGISTRY` is never mutated; auto-registered entries
are a fallback layer in `get_apl_entry`. Failed-smoke APLs stay on disk
for manual review but never enter the auto registry. New CLI flags:
`--top-n` (cap on archetypes per run, default 3) + `--force` (bypass
dedup). Spec: `harness/specs/2026-04-28-auto-pipeline-output-flow-to-retune.md`.

**Current Gemma APL quality (2026-04-28 measurement):** 0/3 of today's
generated APLs passed the smoke gate (Landless Belcher: API misuse
calling `gs.get(...)`; Cutter Affinity: no APL class defined; Jeskai
Phelia: SyntaxError). Infrastructure works; Gemma quality is the gap.
Improving Gemma's prompt or escalating to Claude path are downstream
follow-ups.

**Auth-path topology:** `apl/auto_apl.py:_get_api_token` resolves
from (1) `ANTHROPIC_API_KEY` env var, (2) Claude Code OAuth
credentials at `~/.claude/.credentials.json`, (3) `.env` file.
**VERIFIED 2026-04-29:** OAuth tokens (`sk-ant-oat01...`) work against
`api.anthropic.com/v1/messages` — HTTP 200, valid completion returned.
Prior 2026-04-28 probe showed HTTP 401 (transient policy state; now
corrected). Implication: Claude path in auto-pipeline is FREE under
Claude Max subscription. `--auto-pipeline-use-claude` requires no
console API key. Gemma remains the nightly default for cost reasons,
but Claude path is a zero-cost escalation option for quality.

**How it works now:**
- `auto_pipeline.py` scans meta_change for new archetypes without APLs
- Generates APLs via Claude API ($0.05/deck) or Gemma ($0.00 drafts)
- Validates generated APLs by running goldfish sim
- Drafts playbook skeletons from sim + tuning data via Gemma
- Maintains `optimization_memory.json` — lifetime log of all experiments,
  generated APLs, playbook drafts, costs, improvements

**Optimization memory tracks:**
- Every experiment: deck, swap, delta, status, date
- Every generated APL: deck, method, cost, date
- Every playbook draft: deck, date
- Lifetime stats: total experiments, improvements, sim games, API cost

**Cost model:**
- Claude API APL generation: ~$0.05-0.10/deck (one-time per archetype)
- Gemma APL drafts: $0.00 (lower quality, good for initial pass)
- Everything else: $0.00 (sim, tuning, analysis, playbooks all local)


---

## FINAL SYSTEM INVENTORY (2026-04-18, all 6 layers complete)

### All Layers
| Layer | Name | Status | Built |
|-------|------|--------|-------|
| 1 | Knowledge Persistence | OPERATIONAL | 2026-04-14 |
| 1 | Local Model Pipeline | OPERATIONAL | 2026-04-15 |
| 1 | Token Compression | OPERATIONAL | 2026-04-15 |
| 1 | APL Tuner Agent | OPERATIONAL | 2026-04-15 |
| 1 | MTGA Log Parser | OPERATIONAL | 2026-04-15 |
| 2 | Scheduled Nightly Job | OPERATIONAL | 2026-04-16 |
| 2 | Inbox File Watcher | OPERATIONAL | 2026-04-16 |
| 3 | Autonomous Tuning Loop | HARDENED | 2026-04-16 (hardened 04-18) |
| 3 | Card Legality Checker | OPERATIONAL | 2026-04-16 |
| 4 | Sim Calibration | OPERATIONAL | 2026-04-16 |
| 4 | MTGA Opponent Detection | OPERATIONAL | 2026-04-18 |
| 5 | Full Pipeline Automation | OPERATIONAL | 2026-04-16 |
| 6 | Agent Hardening | OPERATIONAL | 2026-04-18 |
| 6 | Matchup Gauntlet | OPERATIONAL | 2026-04-18 |
| 6 | Playbook Generator | OPERATIONAL | 2026-04-18 |
| 6 | Dashboard | OPERATIONAL | 2026-04-18 |
| 6 | Idempotency Guards | OPERATIONAL | 2026-04-18 |

### Complete Script Inventory (17 PS1 + 8 Python = 25 scripts)

| Script | Layer | Location |
|--------|-------|----------|
| ask-gemma.ps1 | 1 | harness/scripts/ |
| compile-knowledge.ps1 | 1 | harness/scripts/ |
| process-inbox.ps1 | 1 | harness/scripts/ |
| kb-status.ps1 | 1 | harness/scripts/ |
| tune-apl.ps1 | 1 | harness/scripts/ |
| parse-mtga.ps1 | 1 | harness/scripts/ |
| load-context.ps1 | 1 | harness/scripts/ |
| watch-inbox.ps1 | 2 | harness/scripts/ |
| nightly-harness.ps1 | 2 | harness/scripts/ |
| register-harness-tasks.ps1 | 2 | harness/scripts/ |
| tune-loop.ps1 | 3 | harness/scripts/ |
| calibrate.ps1 | 4 | harness/scripts/ |
| auto-pipeline.ps1 | 5 | harness/scripts/ |
| run-gauntlet.ps1 | 6 | harness/scripts/ |
| gen-playbooks.ps1 | 6 | harness/scripts/ |
| stress-test.ps1 | - | harness/scripts/ |
| install-stack.ps1 | - | harness/scripts/ |
| apl_tuner.py | 1 | harness/agents/scripts/ |
| nightly_harness.py | 2 | harness/agents/scripts/ |
| tuning_loop.py | 3 | harness/agents/scripts/ |
| calibrate.py | 4 | harness/agents/scripts/ |
| auto_pipeline.py | 5 | harness/agents/scripts/ |
| agent_hardening.py | 6 | harness/agents/scripts/ |
| matchup_gauntlet.py | 6 | harness/agents/scripts/ |
| playbook_generator.py | 6 | harness/agents/scripts/ |

### Knowledge Base: 27 blocks across 4 domains
### Scheduled Tasks: 6 (3 meta-analyzer + 3 harness)
### Nightly Pipeline: 7 steps (meta shifts, retune, MTGA, calibrate, gauntlet, playbooks, inbox)
### Dashboard: harness/dashboard.md (auto-generated)
### State: harness/state/run_state.json (idempotency tracking)
### Optimization Memory: harness/agents/optimization_memory.json
### Build Time: 5 sessions (2026-04-14 through 2026-04-18)
### Total API Cost: $0.00 (everything built and tested locally)
