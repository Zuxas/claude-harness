---
title: "Local-LLM Delegation Layer (routing.yaml + delegate MCP + executor)"
status: "SHIPPED"
created: "2026-07-03"
updated: "2026-07-04"
project: "harness"
estimated_time: "multi-session (P1 ~60m, P2 ~120m, P3 ~90m, P4 ~60m, P5 ongoing)"
related_findings:
  - "harness/specs/2026-06-26-harness-ollama-watcher-optimization.md"
  - "BLUEPRINT-2026-07-03.md (WP-I council, shipped)"
  - "compass_artifact_wf-21eaad84-...text_markdown.md (source research brief)"
related_commits: ["9d41d91 (harness repo, P1-P4 delegation layer)", "7bbd049 (deploy snapshot)", "5d02205 (Gate 5.1 two-lane routing)"]
supersedes: null
superseded_by: null
---

> **Reconciliation 2026-07-04:** Status corrected EXECUTING -> SHIPPED. The 2026-07-04
> verification pass (workflow wotqbyhve, council-ratified SHIPPED, unanimous 3-0) confirmed all
> 5 artifact groups on disk + 3 commits landed + every gate closed (incl. Gate 2.1 subagent->MCP
> `echo` ok:true and Gate 5.1 KEEP_FOR_SUBSET applied). Frontmatter/index had lagged the changelog.
> Two OPTIONAL leftovers moved to IMPERFECTIONS: B4 legacy ~9-site ollama_client consolidation;
> tier-2 --no-mmap/--parallel-1 re-bench.
---

# Local-LLM Delegation Layer

## Goal

Give Claude (and its subagents) the ability to hand bounded, high-output tasks
to *local* models on the RTX 3080 / 64GB rig, with the user in explicit control
of **which local model runs which task**. Shipping this means: (1) a
user-editable `routing.yaml` maps task-types -> models; (2) a thin custom MCP
server exposes `run(task_type|model, prompt)` to Claude and its subagents,
routing to Ollama (tier-1, fast, all-GPU) or a persistent llama.cpp server
(tier-2, MoE expert-offload to 64GB RAM); (3) a delegation policy tells agents
*when* offloading is worth it; (4) Claude — or an agent, or you — can hand a
specific bounded subtask to the local worker whenever the gate says it's worth
it (a case-by-case call Claude makes, NOT an automatic verdict-parser). The
council (Claude / a high-level AI only) decides; local models execute bounded
work. **Local models are workers, never council seats.** Tier-1 (qwen-7b as a
worker) is the reliable core; tier-2 ("can a 30B MoE think a little on this
rig?") is a *fenced experiment* riding on the Gate 5.1 kill switch.

## Scope

### In scope
- `harness/agents/routing.yaml` — declarative task-type -> model map (HYBRID
  control: explicit per-call override > task_type lookup > auto fallback).
- `harness/agents/delegate_mcp/` — thin MCP server (mirror the proven
  `mtg-meta-analyzer/mcp_server/` structure): `server.py`, `router.py`,
  `backends/ollama.py`, `backends/llamacpp.py`, `config.py`. Tools:
  `run(task_type?, model?, prompt, max_tokens?)`, `list_models()`, `health()`.
- Registration via a project `.mcp.json` entry (same mechanism the analyzer MCP
  uses), tool name prefix `mcp__delegate__*`.
- `harness/scripts/start-llamacpp-tier2.ps1` — launch/stop the persistent
  llama-server for Qwen3-Coder-30B-A3B (Q4_K_M, Unsloth GGUF) with the
  brief's flags (`-ngl 999 --n-cpu-moe 32 -fa on --cache-type-k q8_0
  --cache-type-v q8_0 -c 32768 --jinja`).
- `.claude/skills/delegate/SKILL.md` — the delegation skill + policy ("worth
  it?" gate), plus an `executor` usage pattern any agent/subagent can invoke.
- CLAUDE.md routing-rules block + per-run token/time budget cap.
- Fleet (LEAN start): tier-1 `qwen2.5-coder:7b` (ALREADY installed), tier-2
  `Qwen3-Coder-30B-A3B` Q4_K_M (new pull).
- Reuse dividend: factor the ollama client as a plain importable module
  `harness/agents/ollama_client.py` that BOTH the delegate MCP wraps AND the ~9
  legacy `ask_gemma` sites can import — that (not code buried inside the MCP
  package) is what actually finishes spec 2026-06-26 B4. Model it on the proven
  `auto_pipeline.py::_call_ollama` streaming pattern (the `stream=False`
  empty-response-under-load bug is documented there).

### Explicitly out of scope
- Rebuilding / editing the `/council` skill's PROTOCOL — it is SHIPPED WP-I.
  (One allowed fix applied 2026-07-03: its `codex exec` line now passes
  `--skip-git-repo-check` so the cross-vendor seat works in this non-git
  workspace.) Writing new protocol to `.claude/skills/council/` is out of scope.
- AUTOMATIC council-verdict -> executor piping. Council output is prose
  reasoning follow-ups, not a machine task list (council review 2026-07-03,
  finding #3). Delegation is invoked case-by-case by Claude/agents, never by
  auto-parsing a verdict.
- Local models as council SEATS. User's explicit call: local LLMs are workers,
  not deliberators; the council is run by Claude / a high-level AI only. (The
  council's cross-vendor seat is `codex exec` GPT-5.5 — INSTALLED & verified
  2026-07-03; that is the heterogeneity source, not local models.)
- gpt-oss-20b, Qwen3-8B, Qwen3-4B-Thinking, Devstral — deferred to a fleet-
  expansion follow-up after the lean pipeline is proven (see Imperfections).
- Parallel multi-agent CODING. Anthropic + Cognition are explicit: interdependent
  code favors single-agent depth. Delegation targets bounded/mechanical work.
- Per-subagent PROVIDER routing inside Claude Code natively (open upstream issue
  #38698). MCP delegation is the sanctioned workaround; not solving the upstream.

## Grounded Current Reality (probed 2026-07-03)

- Ollama **0.31.1** at `http://localhost:11434`, tuned per spec 2026-06-26
  (shipped): `OLLAMA_MAX_LOADED_MODELS=1`, `OLLAMA_NUM_PARALLEL=1`,
  `OLLAMA_KEEP_ALIVE=30m`, `OLLAMA_FLASH_ATTENTION=1`.
- Installed Ollama models (live `/api/tags`): `qwen2.5-coder:7b` (tier-1 target,
  PRESENT), `qwen2.5-coder:14b`, `gemma4:26b`, `gemma4:latest`.
- `harness/agents/scripts/ollama_client.py` **does NOT exist** — B4 shared
  client never landed; `ask_gemma`/`_call_ollama` bodies are scattered across
  ~9 files. The proven streaming pattern lives in `auto_pipeline.py::_call_ollama`.
- MCP precedent in-repo: `mtg-meta-analyzer/mcp_server/{server,tools,config}.py`
  registered via `mtg-meta-analyzer/.mcp.json`. Mirror this.
- **llama.cpp is absent** — no `llama-server` binary anywhere. Genuinely new.
- Existing orchestration scaffolding to be aware of (do not collide):
  `harness/agents/scripts/{orchestrate,ralph_executor,loop_bridge}.py`.
- **VRAM ceiling (the binding constraint):** on 10GB, `qwen2.5-coder:7b`
  (~7GB fully on GPU) and a persistent llama.cpp 30B-A3B server (attention+KV
  on GPU ~3-5GB, experts in 64GB RAM) very likely **cannot co-reside**. Treat
  "one tier hot at a time" as the design assumption; verify empirically (Gate 1.3).

## Pre-flight reads (executor must read before P1)
- `harness/specs/2026-06-26-harness-ollama-watcher-optimization.md` — existing
  Ollama tuning, VRAM behavior, the `_call_ollama` streaming pattern, breaker.
- `harness/agents/scripts/auto_pipeline.py` (`_call_ollama`, ~line 224) — the
  streaming accumulation body to model the ollama backend on.
- `mtg-meta-analyzer/mcp_server/server.py` + `tools.py` + `.mcp.json` — the MCP
  structure + registration to mirror.
- `.claude/skills/council/SKILL.md` — the verdict format this executor consumes
  (READ ONLY; do not edit).
- `harness/knowledge/tech/spec-authoring-lessons.md` — per Rule 9.

## The routing model (`routing.yaml`)

Hybrid resolution order on any `run()` call:
```
  explicit `model` arg present?  -> use it verbatim (hard override)
      else task_type present?    -> routing.yaml.task_types[task_type].model
      else                       -> routing.yaml.defaults.auto_small | auto_large
                                    (auto picks by prompt size / declared difficulty)
```
Proposed initial `harness/agents/routing.yaml`:
```yaml
version: 1
backends:
  ollama:    { endpoint: "http://localhost:11434", kind: ollama }
  llamacpp:  { endpoint: "http://localhost:8080",  kind: openai_compat }
task_types:
  commit_message:  { model: "qwen2.5-coder:7b",    backend: ollama,   max_ctx: 8192,  max_tokens: 200 }   # low-output: explicit-route only; gate won't auto-pick (Claude writes these cheaper itself)
  test_scaffold:   { model: "qwen2.5-coder:7b",    backend: ollama,   max_ctx: 16384, max_tokens: 1500 }
  summarize:       { model: "qwen2.5-coder:7b",    backend: ollama,   max_ctx: 32768, max_tokens: 800 }
  boilerplate:     { model: "qwen2.5-coder:7b",    backend: ollama,   max_ctx: 8192,  max_tokens: 1200 }
  bulk_edit:       { model: "Qwen3-Coder-30B-A3B", backend: llamacpp, max_ctx: 32768, max_tokens: 4000 }
  draft_long:      { model: "Qwen3-Coder-30B-A3B", backend: llamacpp, max_ctx: 32768, max_tokens: 4000 }
defaults:
  auto_small: "qwen2.5-coder:7b"       # short prompt / low difficulty
  auto_large: "Qwen3-Coder-30B-A3B"    # long prompt / high difficulty
  budget: { max_tokens: 4000, timeout_s: 300 }
policy:
  one_tier_hot: true    # tier-2 up => expect Ollama tier-1 unloaded (VRAM ceiling)
```
The user edits this file to change assignments. No code change needed to
re-route a task type.

## The delegation policy ("worth it?" gate)

Encoded in `SKILL.md` and CLAUDE.md. An agent delegates to a local model only
when **all** hold, and keeps the task on Claude if **any** keep-condition holds:
(Council review 2026-07-03 reconciled this gate with routing.yaml: the old
"ALL of {high-output, machine-verifiable}" made low-output/prose task_types like
`commit_message`/`summarize` un-delegatable. New form:)
```
DELEGATE when BOTH core conditions hold:
  - bounded task (bulk edit, draft, test scaffold, format, summarize, boilerplate)
    AND not tightly coupled to the reasoning just produced
  - worth the round-trip — EITHER high output relative to input (a Claude
    subagent still pays tokens to prompt + read back; that's where savings
    bank) OR cheap-to-verify boilerplate Claude would otherwise grind out
Then verify BY OUTPUT TYPE (this is Gate 4.2):
  - CODE  -> machine-verify (ast.parse / lint / test) before accept
  - PROSE -> lightweight Claude review before accept (not machine-checkable)
KEEP on Claude when ANY:
  - contested judgment / architecture / trade-off (that's /council, not this)
  - tightly-coupled multi-file edit needing one coherent context
  - security-sensitive or irreversible
  - low output AND high precision required (round-trip not worth it —
    e.g. a commit message; Claude writes it cheaper itself)
```

## Steps

### Phase 1 — Fleet + routing.yaml + tier-2 server (~60m)
1. Write `harness/agents/routing.yaml` (above).
2. `ollama pull` — tier-1 already present; confirm `qwen2.5-coder:7b` responds.
3. Install llama.cpp (Windows CUDA prebuilt) to e.g. `E:\tools\llama.cpp\`.
   Pull `Qwen3-Coder-30B-A3B` Q4_K_M **Unsloth GGUF** (tool-calling fix) to
   e.g. `E:\models\`.
4. Write `harness/scripts/start-llamacpp-tier2.ps1` launching:
   `llama-server -m <gguf> -ngl 999 --n-cpu-moe 32 -fa on --cache-type-k q8_0
   --cache-type-v q8_0 -c 32768 --jinja --port 8080`.
5. Smoke-test BOTH endpoints by hand (curl `/api/generate` on 11434;
   curl `/v1/chat/completions` on 8080). Record real tok/s for each on this rig.

### Phase 2 — Thin delegate MCP (~120m)
6. **FIRST, prove the load-bearing assumption (advisor gate):** stand up a
   trivial `echo` MCP tool, register it, and confirm a *Task-spawned subagent*
   (not just the main session) can invoke `mcp__delegate__echo`. If a subagent
   cannot call the MCP, delegation must originate from the main session and the
   executor design changes — STOP and surface before building further.
7. Build `harness/agents/delegate_mcp/`: `router.py` (routing.yaml resolution),
   `backends/ollama.py` (streaming accumulation, modeled on `_call_ollama`;
   retry+backoff; keep_alive; num_ctx bound), `backends/llamacpp.py`
   (OpenAI-compat `/v1/chat/completions`), `server.py` exposing `run`,
   `list_models`, `health`.
8. Register in a **workspace-root** `.mcp.json` (none exists yet; the analyzer's
   is subdir-scoped) with an explicit `cwd`/PYTHONPATH so `python -m
   delegate_mcp.server` resolves the package at `harness/agents/`. Note `run()`
   concurrency: with `OLLAMA_NUM_PARALLEL=1` a second caller blocks up to the
   timeout — the executor serializes tasks; document, don't parallelize tier-1.
   Delegate one throwaway `summarize` (tier-1), then one `bulk_edit` (tier-2).

### Phase 3 — Delegate skill + executor pattern (~90m)
9. Write `.claude/skills/delegate/SKILL.md`: the policy above, the routing
   resolution explanation, and an `executor` pattern — given a task list from
   ANY source (Claude, an agent, or you typing one), for each task apply the
   gate, delegate or keep, run the type-appropriate verify (code: machine;
   prose: light Claude review), record outcome to an artifact.
10. (DESCOPED per council review 2026-07-03, finding #3) No automatic
    council-verdict -> task-list pipe. Councils emit prose reasoning follow-ups,
    not mechanical work, so auto-piping doesn't compose. Instead: when Claude is
    orchestrating (council or not) and hits a bounded subtask worth offloading,
    it calls `mcp__delegate__run` case-by-case. Revisit a council-integration
    spec later only if that manual pattern proves it's wanted.

### Phase 4 — Policy + guardrails (~60m)
11. Add a CLAUDE.md routing-rules block ("route mechanical/high-output work to
    `mcp__delegate__run`; keep reasoning on Claude").
12. Enforce per-run token/time budget cap in the router (`defaults.budget`);
    a delegated task exceeding it aborts and returns partial + a flag.
13. Add a post-executor lint/test hook so delegated output is verified, not trusted.

### Phase 5 — Benchmark & tune (ongoing)
14. Run real tasks through it; record tier-1 vs tier-2 tok/s + quality on YOUR
    tasks (not leaderboards). Tune `routing.yaml`. Confirm 30B-A3B actually
    beats 7B on your bulk tasks; if not, drop tier-2 and reclaim RAM.

## Validation gates

| Gate | Acceptance | Stop trigger |
|---|---|---|
| 1.1 Tier-1 alive | `qwen2.5-coder:7b` returns non-empty generation via 11434 | empty/err |
| 1.2 Tier-2 alive | 30B-A3B returns via 8080; tok/s recorded, **>=14 tok/s** (floor raised from 12 so a full 4000-tok task decodes inside the 300s budget: 4000/14=286s; council review 2026-07-03) | <14 tok/s or OOM |
| 1.3 VRAM co-residency | `ollama ps` + `nvidia-smi` measured with BOTH tiers requested; documented whether they co-reside or must swap | (measurement, not fail) — informs `one_tier_hot` |
| 2.1 Subagent->MCP | a Task subagent successfully calls `mcp__delegate__echo` | subagent cannot call MCP -> redesign executor |
| 2.2 Routing resolution | explicit>task_type>auto all resolve to expected model in a unit test | wrong model selected |
| 2.3 End-to-end delegate | one tier-1 + one tier-2 task complete via `run()` from Claude | error / empty |
| 3.1 Executor gate | on a 5-task synthetic list, gate keeps reasoning tasks on Claude, delegates only high-output mechanical ones | mis-routes a KEEP task to local |
| 4.1 Budget cap | a task set to exceed `max_tokens` aborts with partial+flag, not a hang | unbounded run |
| 4.2 Verify hook | CODE output -> `ast.parse`/lint/test before accept; PROSE output -> lightweight Claude review before accept | unverified output accepted |
| 5.1 Value check | tier-2 beats tier-1 on >=1 real bulk task (quality or speed), documented | if not, deprecate tier-2 |

## Stop conditions
- Gate 2.1 fails (subagent can't reach MCP): STOP, surface, switch to
  main-session-originated delegation before P3.
- Gate 1.3 shows tier-1 and tier-2 fighting over VRAM with heavy CPU spill on
  the 7B: STOP, adopt strict `one_tier_hot` (launch script unloads Ollama model
  before starting llama-server), document.
- Any delegated output shipped WITHOUT passing a verify hook: STOP (Rule: no
  unverified local output enters the tree).
- 30B-A3B tok/s < 14 after `--n-cpu-moe` tuning: STOP, surface; likely DDR4-3600
  bandwidth bound (~28 GB/s effective per addendum). Below 14 tok/s a full
  4000-tok task blows the 300s budget cap — either raise the cap / lower tier-2
  `max_tokens`, or conclude tier-2 isn't worth it on this rig (the fenced-
  experiment kill switch, Gate 5.1).

## Commit message template
```
feat(harness): local-LLM delegation layer (routing.yaml + delegate MCP)

Adds user-controlled task->model routing and a thin MCP that lets Claude
subagents offload bounded/high-output work to local models (Ollama tier-1
qwen2.5-coder:7b, llama.cpp tier-2 Qwen3-Coder-30B-A3B). Local models are
workers invoked case-by-case; council stays Claude-only. Reuses proven
_call_ollama streaming pattern; mirrors mtg-meta-analyzer/mcp_server structure.

Bench (this rig):
  tier-1 qwen2.5-coder:7b: <X> tok/s
  tier-2 30B-A3B (--n-cpu-moe 32): <Y> tok/s
  VRAM co-residency: <co-reside | one-tier-hot>

Gates: 2.1 subagent->MCP <pass/fail>, 2.2 routing <pass>, 4.1 budget <pass>
Related: WP-I council (consumed, not modified); spec 2026-06-26 ollama tuning
```

## Annotated imperfections (planned)
```
## fleet-expansion-deferred
What's not perfect: only qwen2.5-coder:7b + Qwen3-Coder-30B-A3B in the fleet.
Why not fixed here: lean start proves the pipeline before adding models.
Concrete fix: add gpt-oss-20b (--ctx-size 8192 to avoid 128k collapse),
  Qwen3-4B-Thinking (cheap critic/drafter) as routing.yaml task_types; no code
  change beyond backend params.
Estimated effort: ~45m per model incl. bench.

## one-tier-hot-manual
What's not perfect: if VRAM can't co-reside, switching tiers needs the launch
  script to unload the other; not yet automatic mid-session.
Why not fixed here: depends on Gate 1.3 measurement.
Concrete fix: router auto-manages tier lifecycle (stop llama-server / set
  ollama keep_alive=0) on cross-tier calls.
Estimated effort: ~30m.

## ollama-client-consolidation
What's not perfect: legacy ~9 ask_gemma/_call_ollama sites still duplicate the
  client the delegate MCP now embeds.
Why not fixed here: out of scope; delegation-layer-first.
Concrete fix: route the 9 legacy sites through the MCP's ollama backend
  (finishes the never-shipped B4 from spec 2026-06-26).
Estimated effort: ~90m.
```

## ADDENDUM — Storage & Model-Loading (rig-specific)

Drives:
- **E:** MSI Spatium M470 2TB — PCIe Gen4 x4, Phison E16, DRAM cache. Rated
  5000/4400 MB/s R/W. Sustained writes hold up. PRIMARY drive; project lives here.
- **F:** Samsung 980 1TB — PCIe Gen3 x4, DRAM-less (HMB, 64MB host RAM). Rated
  3500/3000 MB/s R/W. Sustained write DROPS to ~900 MB/s after SLC buffer fills.

Rules for the Orchestrator / skill design:
1. Store all GGUF model files on **E:**. Cold-load is sequential-read-bound, so E's
   Gen4+DRAM gives ~40% faster first loads (e.g. ~18GB MoE: ~4s on E vs ~6s on F).
2. Model-load-time budget for the Orchestrator cost model: ~1s (7B Q4) to ~4s
   (18–20GB MoE) COLD; ~instant WARM (Windows caches file pages in the 64GB RAM
   standby list after first load). Treat model swaps between roles as CHEAP, not
   expensive.
3. Keep write-heavy work (logs, checkpoints, dataset gen, large artifacts in a
   loop) on **E:**. Do NOT sustain heavy writes to **F:** — it cliffs to
   ~900 MB/s once the SLC cache saturates.
4. Storage does NOT affect inference throughput. RAM-spilled MoE speed is bounded
   by DDR4-3600 bandwidth (~28 GB/s), not by either NVMe. Fast disk = fast loads,
   not fast tokens/sec.
5. Never rely on disk paging (mmap streaming) during inference. Keep the working
   set inside VRAM + 64GB RAM; with 64GB you have headroom for the whole RAM-spill
   tier, so this is a non-issue in practice.

Net effect on prior recommendations: model tiers UNCHANGED (governed by VRAM +
DDR4 bandwidth). Only change: per-role model swapping is a supported, low-cost
pattern; multi-model cold-start latency is a non-issue on this rig.

## Changelog
- 2026-07-03: Created (status PROPOSED). Authored from compass_artifact research
  brief + BLUEPRINT WP-I (council shipped, execution layer is the new work) +
  live probes (Ollama models, absent ollama_client.py, absent llama.cpp, MCP
  precedent). Advisor review folded in: (#1) reuse shipped council don't rebuild;
  (#2) prove subagent->MCP first (Gate 2.1); (#3) gate biases to high-output.
- 2026-07-03: Added "ADDENDUM — Storage & Model-Loading (rig-specific)": E: (Gen4
  DRAM'd) vs F: (Gen3 DRAM-less) load/write characteristics; model swaps ruled
  CHEAP (warm page cache in 64GB standby); inference throughput bounded by DDR4-3600
  (~28 GB/s effective), not NVMe.
- 2026-07-03: COUNCIL-REVIEWED — WP-I first live use (single-vendor; codex not yet
  installed at review time). Verdict: harness/knowledge/tech/council-2026-07-03-
  local-llm-delegation.md. Revisions applied per user ratification of the fixes:
  (1) Gate 1.2 floor 12->14 tok/s (fixes budget/gate arithmetic miscalibration:
  4000 tok / 12 = 333s > 300s cap); (2) delegation gate reconciled with
  routing.yaml (was un-satisfiable for low-output/prose types) -> "bounded AND
  worth-round-trip (high-output OR cheap-boilerplate)" + verify-by-output-type
  (code machine / prose light review, Gate 4.2 updated); (3) Step 10 automatic
  council->executor pipe DESCOPED (councils emit prose, not task lists; user
  concurs "council = Claude/high-level only, local LLM = worker") -> case-by-case
  `mcp__delegate__run` delegation instead; (4) minor: Ollama 0.30.10->0.31.1,
  .mcp.json workspace-root + explicit cwd, run() serialization note, B4 refactor
  = plain importable `ollama_client.py`. Framing: tier-1 worker = reliable core;
  tier-2 = fenced experiment on Gate 5.1 kill switch.
- 2026-07-03: Codex CLI installed (codex-cli 0.142.5, logged in via ChatGPT) and
  `codex exec --skip-git-repo-check` verified working — the council's cross-vendor
  seat is now LIVE for future runs (this review was single-vendor).
- 2026-07-03: EXECUTING (ratified). Mid-execution log:
  * P1 Step 1 DONE — harness/agents/routing.yaml written, parses clean (6 task
    types, 2 backends). Minor deviation: base Python lacked PyYAML -> installed
    (router dep; mechanical, not council-worthy).
  * P1 Step 2 / Gate 1.1 PASS — qwen2.5-coder:7b generates at 92.5 tok/s (via
    the delegation stack: 101.3 tok/s), validating the brief's ~95.
  * P1 Step 3a DONE — llama.cpp b9870 CUDA-12.4 build installed to
    E:\tools\llama.cpp (picked 12.4 over 13.3: driver 591.86 supports CUDA 13.1;
    12.4 is backward-compatible). All spec flags confirmed present (-ncmoe,
    -ctk/-ctv, -fa on, --jinja, -ngl).
  * P1 Step 3b IN PROGRESS — Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf downloading
    to E:\models (18.6 GB).
  * P1 Step 4 DONE — harness/scripts/start-llamacpp-tier2.ps1 (unloads Ollama
    first for one_tier_hot).
  * P2 built AHEAD (parallel to the download, safe): harness/agents/ollama_client.py
    (the B4 importable client), harness/agents/delegate_mcp/{config,router,
    backends/ollama,backends/llamacpp,server}.py. Gate 2.2 PASS (routing
    resolution explicit>task_type>auto + budget cap, unit-tested). Gate 2.3
    tier-1 PASS (real dispatch(summarize) -> qwen 7b). MCP stdio transport
    PROVEN via a fresh-subprocess MCP client (initialize/tools-list/echo/health/
    run all succeed). Registered in workspace-root .mcp.json (PYTHONPATH+cwd).
  * P1 Step 3b/5 DONE — GGUF downloaded (18,556,689,568 B, byte-exact vs remote,
    GGUF magic valid; the bg "exit -1" was a detached-process artifact).
    llama-server loads it in ~7s. Gate 1.2 PASS: tier-2 = 20.0 tok/s on a clean
    200-tok run (delegate-path run 15.5 tok/s), above the 14 floor (4000 tok @
    20 = 200s < 300s budget). Gate 2.3 tier-2 PASS (dispatch(bulk_edit) ->
    Qwen3-Coder-30B-A3B, correct output).
  * Gate 1.3 MEASURED (decisive): tier-2 alone = 9819/10240 MiB VRAM (96%).
    Tier-1 (7B ~7GB) + tier-2 CANNOT co-reside -> one_tier_hot is MANDATORY,
    not optional. Swap proven BOTH ways: launch unloads Ollama -> tier-2 runs ->
    stop tier-2 -> Ollama 7B reloads on demand and answers.
  * Mid-execution amendments (mechanical tuning from the live run; not council-
    worthy): (a) FINDING — Ollama's internal engine is ALSO named
    llama-server.exe; stop tier-2 by executable PATH, never process name, or you
    kill Ollama's engine. Documented in start-llamacpp-tier2.ps1. (b) Added
    --parallel 1 (default 4 slots ballooned KV to 9.8GB) + --no-mmap (loader
    warns mmap+CPU-offload is slower) to the launch script; freed VRAM leaves
    headroom to lower --n-cpu-moe for more speed later (P5/Gate 5.1).
  * Gate 2.1 CAPABILITY PROVEN (proxy): a Task-spawned subagent successfully
    called an already-loaded MCP tool (mcp__magic__logo_search via ToolSearch).
    Combined with the delegate stdio-transport proof, both independent pieces
    are verified -> after a reload loads the delegate MCP, a subagent calling
    mcp__delegate__echo will work. The hard-STOP risk (advisor #2) is RETIRED;
    executor built with confidence rather than stopping. Formal Gate 2.1 (the
    literal mcp__delegate__echo call) still pends the reload + server approval.
  * P3 DONE — .claude/skills/delegate/SKILL.md (policy gate, routing explanation,
    tier-2 lifecycle, executor pattern for a task list; case-by-case, no council
    pipe). Skill auto-discovered by Claude Code.
  * P4 DONE — root CLAUDE.md "LOCAL-LLM DELEGATION" routing-rules block (route
    mechanical high-output -> mcp__delegate__run; keep reasoning on Claude;
    always verify). Budget cap enforced in router (defaults.budget, tested).
    Verify-by-output-type baked into the skill's executor policy. (Step 13
    deterministic PostToolUse hook deferred: delegated output returns as text,
    verified when Claude applies it; a standalone hook adds little now — noted.)
  * REMAINING: (1) formal Gate 2.1 after reload; (2) P5 ongoing bench + Gate 5.1
    tier-2-vs-7b value check (the fenced-experiment verdict); (3) optional:
    route the ~9 legacy ask_gemma sites through ollama_client.py (B4 finish);
    --no-mmap/--parallel-1 re-benchmark + possible lower --n-cpu-moe for speed.
- 2026-07-03: Gate 2.1 CLOSED + Gate 5.1 measured via workflow `delegation-closeout`
  (wf_6118ae99-722; 10 agents, 0 errors). Added `-Stop` to start-llamacpp-tier2.ps1
  (path-matched kill, avoids Ollama's engine).
  * Gate 2.1 PASS — a workflow Task subagent invoked mcp__delegate__echo ->
    {ok:true, echo:"gate-2.1"}. Subagent-can-call-the-delegate-MCP proven for real.
  * Gate 5.1 (fenced-experiment verdict) = **KEEP_FOR_SUBSET**. 5 real bounded tasks,
    blind A/B judging (position-shuffled). Speeds: tier-1 104 tok/s, tier-2 20 tok/s.
    Blind win count tier-2 4 / tie 1 / tier-1 0 — BUT correctness-adjusted tier-1 is
    3/5 (2 of tier-2's wins were pure style edges where tier-1 was also correct).
    tier-1 (qwen-7b) FAILED exactly 2, both on a live route: (a) summarize —
    FABRICATED a backoff detail ("doubling" vs the passage's 2s->8s) + dropped a key
    point (faithfulness failure); (b) refactor — violated an explicit one-sentence
    limit (verbosity). Recommendation: tier-2 earns its keep for the PROSE/faithfulness
    lane, not the fast mechanical lane. Suggested routing (AWAITING USER RATIFICATION):
    move `summarize` -> tier-2; organize routing.yaml as a tier-2 PROSE lane
    {draft_long, bulk_edit, summarize} vs tier-1 MECHANICAL lane {test_scaffold,
    boilerplate, commit_message} and BATCH by lane so one_tier_hot doesn't thrash.
    CAVEAT: n=1 per task category — directional, not definitive; a wider bench would
    harden the summarize-fabrication finding before rerouting a live route.
- 2026-07-03: Routing change RATIFIED + APPLIED (user "apply both"). routing.yaml
  reorganized into two lanes: tier-1 MECHANICAL {test_scaffold, boilerplate,
  commit_message}; tier-2 PROSE {summarize (moved from tier-1), bulk_edit,
  draft_long}, with batch-by-lane comments (one_tier_hot). Verified: summarize
  now resolves to llamacpp, mechanical lane stays ollama. delegate SKILL.md +
  deploy snapshot updated to match. Gate 5.1 CLOSED (KEEP_FOR_SUBSET, applied).
  Spec substantively COMPLETE; open only: optional B4 legacy consolidation +
  optional tier-2 --no-mmap/--parallel-1 re-bench. Consider status -> SHIPPED
  once those are dispositioned to IMPERFECTIONS.
