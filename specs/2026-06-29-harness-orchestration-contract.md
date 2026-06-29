---
title: "Harness Orchestration Contract -- adopting sandcastle's domain model into the Python harness"
status: "PROPOSED"
created: "2026-06-29"
updated: "2026-06-29"
project: "harness"
estimated_time: "DESIGN SPEC (no build). Build effort estimated per-stage inside; ~6-10h total across 4 stages, gated behind lane A (Ralph)."
related_findings:
  - "harness/knowledge/tech/matt-pocock-ai-eng-roadmap-2026-06-29.md (sandcastle section, TIER 1)"
related_commits: []
supersedes: null
superseded_by: null
---

# Harness Orchestration Contract -- adopting sandcastle's domain model

> LANE C DESIGN SPEC. This is spec-first; it produces a contract, files-to-touch, gotchas, and a
> do/defer call. NO code is written here. The roadmap ranks this as CONCRETE NEXT ACTION #2 (behind
> Ralph = #1, lane A). Treat the Ralph executor as a forthcoming sibling build, not an existing module:
> this spec defines the contract boundary so lanes A and C do not diverge.

---

## 0. Pre-flight reads (MANDATORY before any build off this spec)

1. `harness/knowledge/tech/spec-authoring-lessons.md` -- Rule 5/Rule 9 prediction discipline.
2. `harness/knowledge/tech/matt-pocock-ai-eng-roadmap-2026-06-29.md` -- sandcastle subsection (lines 16-23).
3. `harness/agents/planner.md`, `harness/agents/evaluator.md` -- the existing 3-agent prompts the contract maps onto.
4. `harness/agents/scripts/nightly_harness.py` -- the closest existing orchestration entry point (subprocess fan-out, IdempotencyGuard, AgentLogger).
5. `harness/agents/scripts/auto_pipeline.py` -- the streaming+retry Ollama transport (`_call_ollama`, lines ~233-288) that any agent-provider abstraction must wrap.
6. The lane-A Ralph spec when it lands (`harness/specs/2026-06-29-*ralph*.md`) -- to align the termination sentinel and the `RunResult` shape BEFORE building.
7. Existing cache-collision/cache-key work: `specs/2026-04-28-parallel-launcher-cache-collision-fix.md` + `specs/2026-04-28-cache-key-audit-mtg-sim.md` -- these ARE our "distinct-branch invariant" today (see Step 3).

---

## 1. Goal

Adopt sandcastle's orchestration domain model as the harness's explicit contract: a single inspectable
`run()` entry point (agent provider + isolation strategy + prompt + completion criteria -> structured
`RunResult`), a `fork()` fan-out with the distinct-branch (distinct-isolation-key) invariant made
first-class, a `<promise>COMPLETE</promise>` termination signal aligned with lane A's Ralph sentinel, and
an `Output.object`-style typed-extraction-with-retry built on Pydantic. One sentence: give the harness one
named, inspectable orchestration vocabulary -- mapped onto Planner/Executor/Evaluator + the Ralph executor
-- so agent runs stop being fire-and-forget subprocess calls and become inspectable `RunResult` objects.

## 2. Scope

### In scope
- The **contract** (dataclass/Pydantic shapes + function signatures) for `run()`, `RunResult`, the
  `IsolationStrategy` enum, `fork()`, the `<promise>COMPLETE</promise>` parse, and `Output.object`.
- The **mapping** of each sandcastle primitive onto our existing Planner/Executor/Evaluator prompts and
  the Ralph executor (lane A).
- Concrete **files-to-touch**, gotchas, byte-identical/determinism concerns, per-stage effort, do/defer.

### Explicitly out of scope
- Writing the orchestrator code (this is design-only; build is gated behind lane A landing).
- Docker/sandbox isolation (sandcastle's literal sandboxes) -- our isolation is process + cache-key +
  optional git worktree, NOT containers. Containerized isolation is a deferred follow-up (see Step 7).
- Session capture / `resumeSession` / long-lived containers -- defer (Step 7); our handoff surface is
  MEMORY.md + RALPH: commits, not an in-memory session object.
- Replacing nightly_harness.py's subprocess fan-out wholesale. The contract WRAPS it; it does not rewrite it.

## 3. The contract (design output)

### 3.1 `IsolationStrategy` enum -- "where changes land" separated from "what the agent does"

sandcastle: `head` / `merge-to-head` / `branch`. Map onto our reality (we are NOT a coding-agent-on-a-repo
tool; "isolation" for us means where an agent's *outputs and cache keys* land, not git branches per se):

| sandcastle strategy | harness meaning | mechanism today |
|---|---|---|
| `head` | no isolation -- agent writes to the live workspace/cache (Planner reading knowledge, in-place edits) | direct paths; UNSAFE for concurrent forks |
| `merge-to-head` | scratch isolation -- agent works in a temp dir / temp cache namespace, results merged back on success (Executor producing an APL, validated, then promoted) | temp output path + atomic promote (mirrors `atomic_json` pattern) |
| `branch` | named reusable isolation -- a named git worktree OR a named cache namespace reused across `run()` calls (Evaluator re-running against a pinned branch) | `git worktree` (deferred) or a stable named cache key |

The enum makes "where it lands" a first-class parameter, decoupled from the prompt. This is the single
highest-value steal: today nightly_harness picks output paths ad hoc.

### 3.2 `run()` -- the one inspectable entry point

```
# DESIGN ONLY -- signature, not implementation
@dataclass(frozen=True)
class RunOptions:
    agent: AgentProvider              # see 3.5 -- wraps Ollama (gemma4) or Anthropic
    isolation: IsolationStrategy      # head | merge_to_head | branch
    prompt: str
    completion: CompletionCriteria    # sentinel + max_iterations + optional Output schema
    branch_name: str | None = None    # required iff isolation == branch
    hooks: RunHooks | None = None     # pre/post-iteration callbacks (logging, checkpoint to MEMORY.md)

@dataclass
class RunResult:
    iterations: list[IterationRecord] # each: prompt, raw output, parsed Output|None, tool/feedback calls
    outputs: list[str]                # artifacts produced (paths or APL basenames)
    isolation_key: str                # the branch name / temp namespace / "head"
    completed: bool                   # did the sentinel fire?
    object: BaseModel | None          # the validated Output.object result, if a schema was supplied
    error: str | None                 # neverthrow-style explicit failure (do NOT raise across the boundary)

def run(opts: RunOptions) -> RunResult: ...
```

`run()` returns `RunResult` -- never fire-and-forget. `error` is an explicit field (neverthrow idea from the
roadmap Tier 2): the agent/tool boundary returns a Result, it does not raise. This mirrors apl_judge's
existing fail-soft ERROR-grade discipline (`apl_judge.py:449-452`).

### 3.3 `fork()` -- fan-out with the distinct-isolation-key INVARIANT

```
def fork(parent: RunResult, children: list[RunOptions]) -> list[RunResult]: ...
```

INVARIANT (copied verbatim in spirit from sandcastle): **concurrent forks REQUIRE distinct isolation keys.**
`head` and `merge-to-head` are UNSAFE to run concurrently (they collide on the live workspace / a shared
temp namespace). Only `branch` (distinct `branch_name` per child) is concurrency-safe. `fork()` MUST assert
this at call time and return an `error` RunResult for any child that violates it -- do not silently let two
children share a key. See Step 3 (gotchas): we ALREADY follow this ad hoc.

### 3.4 `<promise>COMPLETE</promise>` termination

The `CompletionCriteria` carries the sentinel string + `max_iterations`. `run()` loops the agent until the
sentinel appears in output OR `max_iterations` is hit. **Vocabulary-alignment seam with lane A:** Ralph uses
`<promise>NO MORE TASKS</promise>` (success) / `<promise>ABORT</promise>` (fail). This spec's generic
`run()` should accept the sentinel as a parameter and ship with a `Sentinels` registry that includes BOTH
sandcastle's `COMPLETE` and Ralph's `NO MORE TASKS` / `ABORT`, so the two lanes share one parser. DO NOT
hard-code `COMPLETE`. (Open coordination item -- resolve against the lane-A spec before building.)

### 3.5 `AgentProvider` + `Output.object` (Pydantic + retry-with-error-feedback)

`AgentProvider` is a thin protocol with one method `complete(prompt, *, num_ctx, schema=None) -> str|BaseModel`.
Two implementations:
- `OllamaProvider` -- wraps `auto_pipeline._call_ollama` / `apl_judge.call_llm` (gemma4, streaming, 5-retry).
- `AnthropicProvider` -- wraps the Anthropic SDK (model `claude-opus-4-8`, adaptive thinking). See the
  evalite spec (`2026-06-29-evalite-eval-harness.md`) for the exact SDK call shape; reuse it, do not redefine.

`Output.object({schema, maxRetries})` -> Python: a helper that calls the provider, validates against a
Pydantic model, and on `ValidationError` re-prompts the SAME provider with the validation error appended
(retry-with-error-feedback), up to `maxRetries`. This is DISTINCT from the transport-level retry that
already exists in `call_llm` (which retries on empty/timeout). Output.object is a VALIDATION retry loop on
top. For Anthropic, prefer `client.messages.parse(..., output_config={"format": pydantic_model})` which
validates server-side; the manual re-prompt loop is the Ollama fallback (gemma4 has no structured-output
mode). pydantic 2.13.4 is already installed (confirmed); no new dep for the core, but `anthropic` SDK is NOT
installed -- adding it is a gotcha (Step 3).

### 3.6 Mapping onto Planner / Executor / Evaluator + Ralph

| sandcastle primitive | harness mapping |
|---|---|
| `run({agent, prompt, ...})` | one Planner OR Executor OR Evaluator invocation, now returning RunResult |
| `branchStrategy` | Planner=`head` (reads, no isolation) / Executor=`merge-to-head` (scratch APL, promote on pass) / Evaluator=`branch` (pinned, re-runnable) |
| `fork()` fan-out | Executor fanning N APL-candidate runs on distinct branches (today: parallel_launcher per-matchup workers) |
| `<promise>COMPLETE</promise>` | Evaluator's "all gates pass" signal; aligns with Ralph's `NO MORE TASKS` |
| Ralph loop (lane A) | the autonomous Executor: each iteration = one `run()` with `merge-to-head`, RALPH: commit as the post-hook |
| session capture / resume | MEMORY.md write-back via `RunHooks.post_iteration` (NOT an in-memory session -- deferred) |

## 4. Steps (the design work; mechanical)

1. **Write the contract module stub** (signatures + dataclasses + enum, NO logic) to
   `harness/agents/scripts/orchestration.py`. Docstrings only; `raise NotImplementedError` bodies. This is
   the durable artifact reviewers check the mapping against. (~60 min)
2. **Write the `Sentinels` registry** (COMPLETE + NO MORE TASKS + ABORT) and the parse function signature.
   Coordinate the exact strings with the lane-A Ralph spec. (~20 min)
3. **Wire `OllamaProvider`** as a 20-line adapter over the EXISTING `auto_pipeline._call_ollama` -- do not
   reimplement transport. (build, gated -- ~45 min)
4. **Wire `AnthropicProvider`** using the evalite spec's SDK shape (`claude-opus-4-8`, adaptive thinking,
   `messages.parse` for Output.object). (build, gated -- ~45 min)
5. **Refactor ONE caller (nightly_harness's tuner-dispatch) to go through `run()`** as the proof the
   contract fits a real path -- behind the determinism gate (Section 5). (build, gated -- ~2-3h)
6. Leave Planner/Evaluator paths as adapters in a follow-up; do NOT big-bang migrate.

## 5. Validation gates (DESIGN-ACCEPTANCE, falsifiable)

These are NOT sim-validation gates (no goldfish/mirror/gauntlet here). They are contract-acceptance gates.

| Gate | Acceptance | Stop trigger |
|---|---|---|
| 5.1 Coverage | EVERY sandcastle primitive (run, RunResult, 3 isolation strategies, fork, sentinel, Output.object) maps to one named harness primitive in `orchestration.py` | any primitive unmapped |
| 5.2 Fork invariant | `fork()` signature + a written assertion test that two concurrent `head`/`merge-to-head` children produce an `error` RunResult; two distinct `branch` children do not | invariant not expressible in the contract |
| 5.3 Sentinel alignment | the `Sentinels` registry contains BOTH `COMPLETE` and Ralph's `NO MORE TASKS`/`ABORT`; lane-A spec cross-linked | sentinel hard-coded to one string |
| 5.4 Determinism (byte-identical) | for Step 5 refactor: re-run a LOCKED seed=42 baseline (the Modern canonical 64.5/78.8) through the old path and the `run()`-wrapped path; results byte-identical | any divergence -> the wrapper leaked nondeterminism (seed/order/path) |
| 5.5 No-raise boundary | every provider/tool failure surfaces as `RunResult.error`, never an exception crossing `run()` | any path raises across the boundary |

## 6. Stop conditions (teeth)

- If the lane-A Ralph spec has NOT landed when build starts: STOP at Step 2. The sentinel vocabulary and the
  `RunResult`/iteration shape MUST be co-designed; building `run()` blind to Ralph guarantees divergence.
- If Gate 5.4 (determinism) fails on the Step-5 refactor: STOP, revert the refactor, document the
  nondeterminism source (almost always a seed not threaded through, a dict-iteration order, or a temp path
  collision), do NOT ship a wrapper that perturbs a locked baseline.
- If wiring `AnthropicProvider` reveals the `anthropic` SDK is unavailable in the runtime: STOP the Anthropic
  half, ship Ollama-only, open an imperfection for the SDK install (Step 8).

## 7. Do / Defer

**DO now (this spec + first build slice):** the contract module (Step 1-2), `OllamaProvider` (Step 3),
`Output.object` Ollama re-prompt loop. These are pure-additive, reuse existing transport, and unblock the
evalite spec's LLM-judge scorer (which needs the AnthropicProvider seam).

**DEFER (explicitly):**
- The full nightly_harness migration (Step 5+) until lane A lands -- it is the only piece touching a locked
  baseline (determinism risk) and the only piece coupled to Ralph's shape.
- Docker/container sandboxing (sandcastle's literal isolation) -- our process+cache-key isolation is
  sufficient for now; containers are a separate spec.
- Session capture / `resumeSession` -- MEMORY.md + RALPH: commits already cover handoff; an in-memory
  resumable session is speculative until a use case demands it.
- `git worktree`-backed `branch` isolation -- the named-cache-key form is enough until a use case needs a
  real second working tree (grep confirmed we use ZERO worktrees today).

## 8. Annotated imperfections (to register on ship)

- `orchestration-anthropic-sdk-not-installed` -- `AnthropicProvider` cannot be built/tested until the
  `anthropic` SDK is added to the harness env (confirmed absent 2026-06-29). Concrete fix: `pip install
  anthropic`, set `ANTHROPIC_API_KEY`, smoke-test `claude-opus-4-8`. Effort: 15 min + key provisioning.
- `orchestration-sentinel-vocab-unresolved` -- the COMPLETE vs NO MORE TASKS naming is an open
  lane-A/lane-C coordination item until the Ralph spec lands. Cross-link both specs on ship.

## 9. Gotchas (load-bearing)

1. **The "distinct-branch invariant" is NOT git branches for us -- it is cache keys / output paths.** Our
   grep for `worktree|branchStrategy|fork(` returned EMPTY. The ad-hoc isolation we already follow lives in
   `parallel-launcher-cache-collision-fix` + `cache-key-audit`: concurrent sim workers REQUIRE distinct
   cache keys / distinct output JSON paths, exactly as sandcastle's concurrent forks require distinct
   branches. Frame the invariant in those terms or it reads as a hand-wave.
2. **Byte-identical concern = determinism after the wrapper.** `run()` must be a pure refactor of the call
   path; seeds, dict-iteration order, and temp paths must be threaded identically. Gate 5.4 is the proof.
3. **Two different retries -- do not conflate.** `call_llm` already retries on transport failure (empty/
   timeout). `Output.object` adds a VALIDATION retry (re-prompt with the Pydantic error). They stack; name
   them distinctly in the contract.
4. **Anthropic SDK not installed; pydantic IS (2.13.4).** The core contract + OllamaProvider need no new dep.
   The Anthropic half does -- gate it (Stop condition 3).
5. **Do not rewrite nightly_harness.** It already has IdempotencyGuard + AgentLogger + subprocess fan-out.
   `run()`/`fork()` WRAP it; the first migration is one dispatch path, behind the determinism gate.

## Changelog
- 2026-06-29: Created (status PROPOSED). Lane C design spec; build gated behind lane A (Ralph).
