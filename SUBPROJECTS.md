# Sub-projects (canonical menu)

**Purpose:** Single source of truth for the sub-projects Claude/Claude Code should offer as pivot options during the morning chain-priority verification step (see `harness/CLAUDE.md` SESSION START PROTOCOL step 6).

**How to use this file:**
- Claude reads this on session start (after snapshot + inbox + memory) so the morning pivot prompt offers a real, current menu instead of guessing
- User edits this file directly to add/remove/rename sub-projects as the workspace evolves
- Order roughly reflects current focus weight, but isn't strict priority

---

## Active sub-projects

### mtg-sim
**Path:** `E:\vscode ai project\mtg-sim\`
**What:** The Magic: The Gathering match simulator. Engine, APLs, decks, gauntlet pipeline. Bit-stable canonical 64.5% / variant 78.8% baseline (post-Stage-1.7, HEAD `30c992a`).
**Current arc:** Phase 3.5 keyword-effects coverage (Stages D-K remaining); auto-pipeline output flow operational but Gemma quality is the gap.

### mtg-meta-analyzer
**Path:** `E:\vscode ai project\mtg-meta-analyzer\`
**What:** Tournament data scraper + SQLite DB (35K+ tournament decks across 4 formats) + Qt GUI app with ~21 tabs (dashboard, deck_analyzer, predictions, simulate, ask_claude, prep_checklist, tournament_prep, calibration, charts, heatmap, breaker math, hypotheses, knowledge_base, match_log, my_decks, search, settings, set_analysis, card_browser, event_optimizer).
**Current arc:** Daily scrape pipeline operational; ~21-tab GUI is meaningful product baseline; Friday PT-watch readiness verified.

### harness (this directory)
**Path:** `E:\vscode ai project\harness\`
**What:** The methodology/automation layer wrapping mtg-sim + meta-analyzer. Spec discipline, IMPERFECTIONS/RESOLVED tracking, drift-detect, methodology lesson compounding (17 v1.5 lessons), nightly_harness orchestration, Gemma drift PR, snapshot generation.
**Current arc:** Ongoing tooling expansion (drift-detect 7th + 8th checks shipped 2026-04-28); chain-on-disk discipline; Layer 5 wired but partial-effect.

### APLs (mtg-sim subset, but called out separately)
**Path:** `E:\vscode ai project\mtg-sim\apl\`
**What:** Per-deck AI pilots that drive sim decisions. 32+ hand-written + 21 match-aware + auto-generated stubs. Quality ranges from canonical (Boros Energy, Izzet Prowess) to needs-iteration.
**Current arc:** Boros Energy variant-adaptive role refactor complete; Izzet Prowess refactor candidate; Pioneer L1 backlog 57 cards.

### decks (mtg-sim subset)
**Path:** `E:\vscode ai project\mtg-sim\decks\`
**What:** Decklist .txt files. 59 from DB + custom variants + auto-generated.
**Current arc:** Standard meta refresh shipped 2026-04-28; auto/ subdirectory for auto-pipeline-generated lists.

### website
**Path:** TBD (not yet started)
**What:** Future deliverable per MASTERPLAN.md backlog. "Website integration (inject sim data into playbooks)." No current code.
**Current arc:** Latent. Could become Friday-PT-watch dashboard, deck-choice memo publisher, or competitive-prep public-facing tool depending on direction.

### calibration / eval-weights
**Path:** `E:\vscode ai project\mtg-sim\` (scripts at root, data at `data/sim_matchup_matrix.json`)
**What:** Eval-weight tuning for the engine's decision-making. Default weights validated at 99.5% accuracy across 600 samples (per MASTERPLAN.md P3). Future work: instrument mid-game eval to improve in-progress game predictions.
**Current arc:** Stable; revisits when sim quality surfaces a calibration gap.

---

## Long-term / not-yet-started

### MTGA log parser
**What:** First autonomous-agent project per MEMORY.md. Parses Arena game logs into match data → feedback loop into harness. Long-term project; deferred.

### botctl (background agent process manager)
**What:** Infrastructure layer for running agent processes 24/7. Per MEMORY.md long-term. Deferred.

### Gemma-powered knowledge updater
**What:** Autonomous knowledge-block compilation. Per MEMORY.md long-term, after botctl. Deferred.

### Productization (lifetime maybe; not current goal)
**What:** Per memory edit #4, user is open to eventually productizing the mtg-sim + meta-analyzer + harness stack as standalone app, web app, or phone app. Lifetime-long maybe. Current goal stays personal competitive prep. Don't push productization unprompted.

---

## How the morning pivot prompt should use this file

Per `harness/CLAUDE.md` SESSION START PROTOCOL step 6, Claude/Claude Code shows the current execution chain and asks:

> "Today's chain from `harness/plan-<date>-execution-chain.md`:
> 1. [first item]
> 2. [second item]
> ...
>
> This is the [current sub-project per the chain] arc. Want to:
> (a) proceed with this plan
> (b) pivot to a different sub-project: mtg-sim / mtg-meta-analyzer / harness / APLs / decks / website / calibration / something else
> (c) re-prioritize within the current sub-project
>
> Standing by."

User picks (a), (b)+name, or (c). If (b) or (c), Claude re-scopes the chain accordingly before starting execution.

Not invasive — single short check at session start, then proceed.

---

## Changelog

- 2026-04-28: Created. Initial sub-project menu authored by claude.ai per user signal that each weekday should be a 9-hour scripted day with morning verification of which sub-project is the focus.
