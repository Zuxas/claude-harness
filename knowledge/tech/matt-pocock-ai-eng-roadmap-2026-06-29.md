# Matt Pocock -- AI-Engineering Transition Roadmap (all-repo dig, 2026-06-29)

Full evaluation of every public repo on github.com/mattpocock, through the lens of the
user's transition into AI engineering / "AI controller" (agent-orchestration) work + what
is portable into the Python agent-harness (`harness/`) + mtg-sim. Companion to
`matt-pocock-inventory-2026-06-29.md` (the skills-repo dig + global-install plan).

Matt Pocock is a premier AI-engineering educator; his TypeScript AI work is learning gold
even though it does not import into Python -- evaluated for transferable patterns + named
tools, not drop-in code.

---

## TIER 1 -- INCORPORATE / PORT (highest leverage, do these)

### sandcastle (6.5k* TS) -- the AI-controller blueprint
The TS reference implementation of the exact job being moved into: orchestrating coding
agents in isolated sandboxes with git-aware merging. PORT the domain model:
- `run({agent, sandbox, prompt, branchStrategy, maxIterations, hooks, output}) -> RunResult{iterations[], commits[], branch, output}` -- one inspectable entry point, not fire-and-forget.
- Branch strategies as a first-class enum: `head` (no isolation) / `merge-to-head` (temp branch auto-merge) / `branch` (named reusable worktree). Separates "where changes land" from "what the agent does." Maps onto Planner/Executor/Evaluator named branches.
- `fork()` fan-out: parent explores, forks N children on distinct branches in parallel. INVARIANT to copy: concurrent forks REQUIRE distinct branches (head/merge-to-head unsafe concurrently) -- the safe-parallelism rule (we already follow it ad hoc in our workflows).
- Session capture + `resumeSession`; long-lived container across `run()` calls (Executor->Evaluator handoff).
- Completion signal `<promise>COMPLETE</promise>` to break the loop; `Output.object({schema, maxRetries})` = typed extraction w/ retry-on-validation-fail (Python: Pydantic + retry-with-error-feedback).

### Ralph loop (ralph-workshop-repo-001 + ai-interviewer `ralph/`) -- the autonomous Executor
Stateless self-looping agent whose only persistent state is git history. PORT to Python:
- `afk.sh`: each iteration pulls the last 10 `RALPH:`-tagged commits (`git log --grep=RALPH`) as MEMORY, runs the agent in a Docker sandbox with stream-json output parsed by `jq`.
- `prompt.md` discipline: read PRD -> break into the SMALLEST unit ("don't outrun our headlights") -> pick ONE task -> explore -> execute -> run feedback loops (test/typecheck) BEFORE committing -> commit with a structured `RALPH:` message (task, PRD ref, decisions, files, notes-for-next).
- Termination via sentinels: `<promise>NO MORE TASKS</promise>` (success) / `<promise>ABORT</promise>` (fail). "HANG ON A SECOND" self-interrupt for over-large tasks.
- Maps directly onto our 3-agent (Planner/Executor/Evaluator) pattern + MEMORY.md write-back. The `RALPH:`-commit-as-state trick = zero-infra task DB; usable today for autonomous per-card mtg-sim handler passes (one card/iteration, test as feedback, repeat to NO MORE TASKS).

### evalite (1.6k* TS) -- eval-as-test (the AI-eng dividing-line skill)
"Can you measure whether the agent got better?" -- the hobbyist/engineer line. We already
built `apl_judge` toward this; evalite is the fuller blueprint. PORT the skeleton:
- `evalite(name, {data, task, scorers})`: data = `[{input, expected}]`; task = calls LLM/agent, returns output; scorers = `({input, output, expected}) -> {score 0-1, metadata}`.
- Built-in scorers (autoevals lib): Levenshtein, Factuality (LLM-judge). `reportTrace()` records each LLM call (in/out/tokens/timing). Local web UI + static HTML CI export that fails the build on a score threshold.
- PYTHON PORT: pytest as the runner (vitest analog), parametrized cases = data, the Monte Carlo sim = the scorer (`scorer(case)=winrate_over_N_sims`), normalize 0-1, gate CI on `mean_score >= threshold`. Averaging the score + thresholding the mean = a non-flaky way to test stochastic agents. Pair with an Anthropic LLM-judge scorer.
- Deep API docs paywalled (evalite.dev/guides/scorers, /traces) -- worth a real read.

### agent-rules-books (250* MD) -- on-demand skills, ready today
14 SE classics distilled to markdown at THREE budget tiers full/mini/nano (A Philosophy of
Software Design, Clean Architecture, Refactoring, DDD, Release It!, Working Effectively with
Legacy Code, Pragmatic Programmer, ...). Model+language-agnostic, MIT.
- WRAP selected `mini` files as on-demand skills (add SKILL.md frontmatter name+trigger, drop in skills dir): refactoring->"refactoring" skill, release-it->"reliability", clean-architecture, DDD. Loaded only when triggered = budget-safe (consistent with our CLAUDE.md trim).
- ADOPT the full/mini/nano tiering for OUR OWN knowledge blocks: same content, three context costs, load the tier that fits.

### agent-browser (TS, Rust core) -- USE as a CLI tool
Headless browser automation built FOR agents: navigate -> `snapshot` (accessibility tree w/
deterministic refs `@e1,@e2`) -> act on refs -> re-snapshot. JSON output, CLI = language-agnostic.
- Shell out to it from Python. KILLER pattern: deterministic accessibility-ref snapshots instead of raw DOM/screenshots -- stable IDs that survive re-renders, far cheaper for an LLM. Right model for MTG meta-data web pulls.

### resumable-stream (TS) -- port the offset-replay to Python
Redis pub/sub + INCR/SUBSCRIBE buffer-and-replay so a client that drops mid-LLM-stream
reconnects and replays from offset. PORT the Redis stream-key + offset scheme for any
harness/sim job that outlives its HTTP request.

### slopwatch (TS, code is a stub but the DOCS are a finished architecture) -- telemetry vocab
Self-hosted observability for coding agents. ADOPT from its `CONTEXT.md` + `research/`:
- Domain model for harness telemetry / cost-attribution: Session (one agent run in one cwd, a DAG of turns) -> Turn (one user msg + full assistant response incl. all tool loops) -> Model request (one provider HTTP call, billed separately); + Subagent (child Session w/ parent_session_id + spawned_by_turn_id), Listener (per-agent normalizer), Event (NormalEvent wire unit).
- Capture strategy for Claude Code: hooks ALONE are insufficient (24+ events give session_id + transcript_path but NOT message content) -> combine hooks-as-triggers WITH tailing the JSONL transcript at `~/.claude/projects/<hash>/<session-uuid>.jsonl` (+ optional OTel spans). Rule: per-agent adapter using that agent's most stable surface, normalized into one shared schema.

### mise-en-place (TS) -- direct peer to our harness
Matt's personal agent-harness for running his business: domain model (Notes/Pitches/
Deliverables/Channels), CONTEXT.md + CLAUDE.md + docs/adr/ layering, Work-Clean/Work-Dirty
state machine, `.claude/skills` + `.sandcastle`. STEAL: (1) vocabulary-as-control-surface
(unambiguous domain nouns make agent delegation reliable), (2) state-machine as monitorable
quality gates, (3) CLAUDE.md->CONTEXT.md->ADR layering (separates reusable tools from
single-context docs). Compare against our `knowledge/_index.md`.

### dictionary-of-ai-coding (2.4k* MD) -- vocabulary curriculum + a freshness trick
~80 terms = a literal curriculum for the transition. PRIORITY reads: Harness (read first),
Handoffs (= our MEMORY.md problem), Compaction/Clearing, Attention Degradation / Smart Zone
/ Dumb Zone (why long contexts get dumber -> when to compact), Sandbox, HITL/AFK, Automated
Check, Parametric vs Contextual Knowledge. COPY the pattern: README generated from source +
GitHub Actions CI-freshness check -> apply to `knowledge/_index.md` (generate from blocks,
CI-fail if a block changed but the index did not -- mechanizes our "update _index" rule).

---

## TIER 2 -- STUDY (the AI-eng learning path)

- **cohort-002-project (TS)** -- canonical personal-assistant agent build: HYBRID RETRIEVAL (BM25 + semantic embeddings + rank fusion) over 547 emails, semantic memory, agentic tools, an eval framework, + HUMAN-IN-THE-LOOP approval for sensitive actions. Maps directly onto a meta-analyzer/harness knowledge retriever. Study `persistence-layer.ts` (memory/history seam).
- **ai-sdk-tips / ai-sdk-5-tutorial (TS)** -- most complete curriculum; tracks 01-patterns/02-fundamentals/03-tokens/04-ai-mistakes/05-claude-code. The named stack to LEARN (language-agnostic): evalite, Langfuse (tracing/observability), mem0 (agent memory), okapibm25, js-tiktoken, OpenTelemetry, @ai-sdk/anthropic.
- **poland-ai-talk (TS)** -- tightest conceptual tour: memory systems, multi-agent workflows, HITL, monitoring (AI SDK v5 + Tavily + Langfuse). Read the `explainer/` folders for the WHY.
- **ai = Vercel AI SDK (Matt's fork)** -- THE mental model for an agent runtime: `streamText({model, tools, maxSteps})` single loop + typed tools + normalized streaming events. Mirror this provider-agnostic contract in the Python harness.
- **chat (TS)** -- write bot logic once, deploy across Slack/Teams/Discord/etc. with native LLM streaming. Study the adapter architecture (one event/handler model normalized across platforms = a tool-abstraction layer).
- **ai-engineer-workshop-2026-project (Cadence, TS)** -- model of disciplined AI-ASSISTED development at app scale (built via Claude Code). Skim for workflow, not internals.
- **neverthrow (TS)** -- Result/Ok/Err discipline ("encode failure, no silent throws") -- the right mindset for failure-dense agent orchestration. PORT THE IDEA to Python (returns lib or a Result dataclass): explicit Result objects from every agent/tool boundary instead of raising. (sandcastle's Output.object retry is the same philosophy.) Don't adopt the repo (it's a 12* fork; upstream = supermacro/neverthrow).

---

## TIER 3 -- UX LAYER (if/when building an AI chat front-end)

- **use-stick-to-bottom (TS)** -- USE as-is: zero-dep React hook, keeps a chat pinned to bottom during streaming, handles user-scroll-away, avoids broken overflow-anchor. Best-known fix for "autoscroll fights the user."
- **markdown-streaming-demo (TS)** -- PATTERN: render PARTIAL markdown as tokens arrive (unclosed code fences, half-tables). Pair with use-stick-to-bottom.

---

## TIER 4 -- PATTERN / MINOR

- **total-typescript-monorepo (TS)** -- convention: commit `.claude/skills` + rules INTO the repo so agent behavior is versioned with the code; "tiny scripts package" for one-off automations. Reference only.
- **course-video-manager (TS)** -- webhook-triggered, queue-based async pipeline ("file lands -> AI processes -> multi-channel publish") -- only relevant to the YT-rip/media work.
- **ai-hero-cli-archived (TS)** -- LLM-as-config-auditor loop (feed an artifact -> structured score + recommendations -> interactive follow-up). Study the loop shape.

---

## SKIP (truly not relevant)

- ts-reset (8.5k* -- pure TS DX), ralph-workshop-repo-002 (empty create-next-app scaffold),
  ai-hero-cli (courseware exercise-runner, no LLM logic), claude-code (a mirror), rubix-cube,
  website (hono.dev), mattpocock (profile), course-video-manager (unless media work).

---

## RECURRING TOOLNAMES TO PUT ON THE RADAR (regardless of language)

evalite (evals) | Langfuse (LLM tracing/observability) | mem0 (agent memory) | BM25 + embedding
rank-fusion (hybrid retrieval) | OpenTelemetry (agent spans) | Human-in-the-Loop approval gates
| Docker sandboxing | stream-json + jq (loop control).

---

## CONCRETE NEXT ACTIONS (priority order)

1. PORT the Ralph loop into the harness Executor (afk.sh -> Python: smallest-task + feedback-gate + RALPH:-commit-as-memory + <promise> sentinel). Highest immediate leverage; reuses MEMORY.md.
2. ADOPT sandcastle's domain vocabulary (RunOptions/RunResult/branch-strategy/fork-needs-distinct-branch) as the harness orchestration contract.
3. WRAP agent-rules-books mini books (refactoring, clean-architecture, DDD) as on-demand global skills; adopt full/mini/nano tiering for our knowledge blocks.
4. BUILD the evalite-shaped eval harness (pytest + Monte Carlo sim as scorer, CI mean-threshold) -- extends apl_judge.
5. ADOPT slopwatch's Session/Turn/Model-request/Subagent telemetry vocab + "hooks trigger, JSONL tail for content" capture for harness cost/telemetry.
6. COPY dictionary-of-ai-coding's generated-index + CI-freshness check for knowledge/_index.md; read its core terms as onboarding.
7. WIRE agent-browser as the web-fetch tool for meta-data pulls (accessibility-ref snapshots).
8. PORT resumable-stream's Redis offset-replay for long-running jobs; adopt neverthrow's explicit-Result style at agent/tool boundaries.

Sources: GitHub READMEs + CONTEXT.md/research docs for each repo; evalite.dev guides; aihero.dev.
