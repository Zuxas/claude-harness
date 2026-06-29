# Autonomous-Controller Stack -- Architecture Map (2026-06-29)

Capability map for the NEW autonomous-controller stack the harness now has. This
is the durable reference for the AI-engineering / "AI controller" transition: it
records what is BUILT, how the pieces COMPOSE, the exact SUPERVISED-RUN procedure
with its HARD safety boundaries, and what is documented-but-not-wired.

Source modules (all verified: each module's offline self-test passes as of
2026-06-29):

- `harness/agents/scripts/ralph_executor.py`   -- loop discipline (pure driver)
- `harness/agents/scripts/ralph_adapters.py`   -- live edges (feedback / commit / agent)
- `harness/agents/scripts/orchestrate.py`       -- run() / fork() / isolation contract
- `harness/agents/scripts/apl_judge.py`         -- the judge (LLM-as-judge scorer)
- `mtg-sim/tests/eval_harness.py`               -- evalite-shaped scoring harness

Companion roadmap (the WHY, with provenance):
`harness/knowledge/tech/matt-pocock-ai-eng-roadmap-2026-06-29.md`.

Design specs this stack realizes:
- `harness/specs/2026-06-29-harness-orchestration-contract.md` (orchestrate.py)
- `harness/specs/2026-06-29-evalite-eval-harness.md` (eval_harness.py)

ASCII-only doc: '->' and '--' are literal, no unicode arrows or em-dashes.

---

## 1. Component map and how they compose

The stack is THREE planes plus TWO shared seams. Each plane is independently
testable; the seams are the only cross-plane coupling.

```
              LOOP / EXECUTION PLANE                 CONTRACT PLANE
  +-------------------------------------+    +---------------------------+
  | ralph_executor.py  (loop discipline)|    | orchestrate.py            |
  |   run_loop(...) pure driver         |    |   run() / fork()          |
  |   parse_promise()  <----------------+----+-- reuses parse_promise    |
  |   build/parse RALPH: commit memory  |    |   IsolationStrategy enum  |
  |   select_smallest_task()            |    |   Sentinels (+ COMPLETE)  |
  +------------------^------------------+    |   Output.object (Pydantic)|
                     | imports                 +---------------------------+
  +------------------+------------------+        SEAM 1: ONE sentinel parser
  | ralph_adapters.py  (live edges)     |        spans loop + contract.
  |   feedback_fn_factory (test gate)   |
  |   make_scratch_commit_fn (git)      |              MEASUREMENT PLANE
  |   make_ollama_agent_fn (local LLM)  |    +---------------------------+
  |   [make_claude_docker_agent_fn:     |    | eval_harness.py           |
  |    DOCUMENTED, NOT BUILT]           |    |   evalite() runner        |
  +-------------------------------------+    |   MonteCarloScorer        |
                                             |   Gemma4JudgeScorer ------+--+
                                             |   AnthropicJudgeScorer    |  | SEAM 2:
                                             +---------------------------+  | grade_apl
                                                       | imports            | llm= seam
                                             +---------------------------+  |
                                             | apl_judge.py  (the judge) |<-+
                                             |   grade_apl(..., llm=)    |
                                             |   build_prompt/parse_result|
                                             |   score_apl/run_calibration|
                                             +---------------------------+
```

### The five components (one line each)

- ralph_executor = LOOP DISCIPLINE. A pure `run_loop` driver: read memory ->
  agent step -> sentinel check -> pick smallest task -> feedback gate -> commit.
  All impure edges are INJECTED. Termination by `<promise>` sentinels.
- orchestrate = the run()/fork/ISOLATION CONTRACT. One inspectable `run()` entry
  point, `fork()` with a distinct-isolation-key invariant, an `IsolationStrategy`
  enum, and `Output.object` typed-extraction-with-retry.
- ralph_adapters = the LIVE EDGES. The thin wiring that turns the pure loop into
  something that touches a real test command, a real git repo, and a real local
  LLM (Ollama). feedback / commit / agent.
- eval_harness = SCORING. The evalite-shaped `data -> task -> scorers[]` runner
  that gates `mean(score) >= threshold` -- measures whether an agent got BETTER.
- apl_judge = THE JUDGE. LLM-as-judge scoring an APL's decision quality
  (oracle fidelity, strategy, mulligan), independent of win rate.

### How they compose (verified by the actual import edges)

1. `ralph_adapters` imports `ralph_executor` (`AgentStep`, `MemoryEntry`,
   `PROMISE_ABORT`). The adapters are FED INTO `run_loop` as its three injected
   callables. This is the live-execution plane: discipline (executor) + edges
   (adapters).

2. `orchestrate` imports `ralph_executor` (`parse_promise` + the promise
   constants) and layers `COMPLETE` on top. This is SEAM 1: lanes A (Ralph) and
   C (sandcastle contract) share ONE sentinel parser, so the two loops can never
   disagree about what "stop" means.

3. `eval_harness` imports `apl_judge` and calls `grade_apl(..., llm=callable)`.
   This is SEAM 2: the eval harness does not fork the judge, it injects a
   transport. `Gemma4JudgeScorer` injects the Ollama transport; `AnthropicJudgeScorer`
   injects an Anthropic-SDK transport. `build_prompt`, `parse_result`,
   `score_apl`, `JudgeGrade`, `run_calibration` are reused verbatim.

4. `apl_judge` is standalone (it path-wires to `verify_oracle` and
   `engine.card_db` for oracle text; importing it opens no socket -- the LLM call
   is lazy and guarded).

### The load-bearing boundary (what is NOT yet connected)

The CONTRACT plane (orchestrate) and the LIVE-EXECUTION plane (ralph_adapters)
are currently UNCONNECTED to each other. Confirmed: `orchestrate` does not import
`ralph_adapters`, and `ralph_adapters` does not import `orchestrate`. They share
the sentinel vocabulary (both reference `ralph_executor.parse_promise`) and
nothing else.

Practical consequence: the SUPERVISED RUNBOOK (section 3) and the one-iteration
data flow (section 2) run on `ralph_executor.run_loop` + `ralph_adapters` -- the
loop/execution plane. `orchestrate.run()/fork()` is the higher-level contract the
harness is converging toward, but it is NOT what the runbook drives today. They
are also two DIFFERENT loop drivers with different agent contracts:

- `ralph_executor.run_loop`: `agent_fn(memory, iteration) -> AgentStep`
  (candidates + text), drives a memory/commit loop.
- `orchestrate.run`: `agent_fn(prompt, iteration) -> str`, plus an
  `IsolationStrategy` and a completion sentinel, returns a no-raise `RunResult`.

They are SIBLINGS that share only the parser. Do not conflate them.

---

## 2. Data flow for one supervised iteration

This traces ONE iteration of `ralph_executor.run_loop` wired to the live
`ralph_adapters` edges against a sandbox (the configuration the runbook in
section 3 sets up). Iteration index `i`:

```
  run_loop(max_iters, agent_fn, feedback_fn, commit_fn, memory_fn)
    |
 1. memory = memory_fn()
    |   live: memory_from_commits(n) -> guarded `git log --grep=RALPH`
    |   -> parse_ralph_log() -> [MemoryEntry]   (NUL-separated commit bodies,
    |                                            non-RALPH bodies skipped)
    |
 2. step = agent_fn(memory, i)
    |   live: make_ollama_agent_fn -> ONE guarded HTTP POST to
    |   localhost:11434/api/generate with rendered memory + RALPH prompt.
    |   Parses a fenced ```json candidates array defensively.
    |   FAIL-CLOSED: unreachable/timeout/bad-JSON -> AgentStep(text=ABORT).
    |
 3. promise = parse_promise(step.text)
    |   ABORT        -> STATUS_ABORTED, return (no commit)
    |   NO_MORE_TASKS-> STATUS_COMPLETE, return (no commit)
    |   HANG_ON      -> self-interrupt: re-scope next iter, NO commit, continue
    |   None         -> proceed to work
    |
 4. task = select_smallest_task(step.candidates)
    |   PURE: smallest `size` (else file-count, else inf) wins. One task / iter.
    |   ("don't outrun our headlights")
    |   no task and no sentinel -> idle, continue
    |
 5. gate_ok = feedback_fn(task)            <-- THE SAFETY INTERLOCK
    |   live: feedback_fn_factory(["python","-m","pytest","-q"]) runs the REAL
    |   test command in a subprocess. True ONLY on exit code 0. Every failure
    |   mode (missing binary / timeout / OS error / nonzero) collapses to False.
    |   Runs BEFORE any commit.
    |
 6. if gate_ok:
    |     msg = build_ralph_commit_message(task, prd_ref, decisions, files,
    |                                       notes_for_next)   (PURE, RALPH:-tagged)
    |     committed = commit_fn(msg)
    |       live: make_scratch_commit_fn -> verify work tree, `git checkout -B
    |       ralph/scratch`, then `git commit` (ONLY ever on the scratch branch)
    |     -> record commit; retries reset to 0
    |   else:
    |     retries += 1; NO commit. retries > max_retries -> STATUS_ABORTED.
    |
 7. loop to next iteration until a terminal sentinel or max_iters
       (max_iters reached with no sentinel -> STATUS_EXHAUSTED)
```

Key invariants visible in this flow:

- The feedback gate is a SUBPROCESS TEST COMMAND (pytest / py_compile), gated on
  exit 0. It is NOT the LLM judge. (The judge plane measures "did it get better"
  separately; wiring `grade_apl` as a `feedback_fn` is possible but is NOT built.)
- Nothing commits unless the test command exits 0. The agent can only PROPOSE;
  the gate is the interlock.
- Memory is git history: the only persistent loop state is the `RALPH:`-tagged
  commit log. The builder and parser round-trip (proven in the self-test) so the
  tag that `git log --grep=RALPH` selects on always survives.
- The Monte Carlo / judge measurement plane (eval_harness + apl_judge) is OUT OF
  BAND from this loop. It scores artifacts after the fact; it is not in the
  commit-gate path.

---

## 3. SUPERVISED-RUN RUNBOOK

This is the exact, supervised procedure for running an autonomous code-editing
loop. It is transcribed from the operational contract in the `ralph_adapters.py`
module docstring ("HOW TO DO A REAL SUPERVISED RUN" + "SAFETY BOUNDARY").

### Steps

1. MAKE A SANDBOX. Either:
   - (a) `git worktree add ../ralph-sandbox <base-sha>` (preferred: real files,
     isolated branch, easy to throw away), or
   - (b) copy/clone the repo to a temp dir.
   NEVER point `commit_fn` at the live working checkout.

2. WIRE THE ADAPTERS AGAINST THE SANDBOX, with a HUMAN in the loop:

   ```
   from ralph_executor import run_loop
   from ralph_adapters import (feedback_fn_factory, make_scratch_commit_fn,
                               make_ollama_agent_fn)
   gate   = feedback_fn_factory(["python", "-m", "pytest", "-q"])
   commit = make_scratch_commit_fn(SANDBOX, branch="ralph/scratch")
   agent  = make_ollama_agent_fn(model="qwen2.5-coder:7b")
   res    = run_loop(max_iters=1, agent_fn=agent, feedback_fn=gate,
                     commit_fn=commit, memory_fn=lambda: [])
   ```

   Run ONE iteration (`max_iters=1`), then STOP and inspect `res.notes`,
   `res.commits`, and `git log` on the scratch branch BEFORE running another.

3. PROMOTE NOTHING AUTOMATICALLY. Diff the scratch branch, review by hand, and
   cherry-pick / merge deliberately. The scratch branch is disposable.

### HARD safety boundaries (these are the teeth)

- SCRATCH BRANCH ONLY. `make_scratch_commit_fn` does a `git checkout -B <branch>`,
  which is DESTRUCTIVE to that branch ref by design. It must NEVER point at the
  live working branch -- only a sandbox / worktree. It refuses to operate if the
  target is not a git work tree (returns False, fail-soft).

- FAIL-CLOSED AGENT. If the local LLM (Ollama) is unreachable, errors, times out,
  or returns unusable output, `make_ollama_agent_fn` returns an ABORT sentinel.
  The loop then HALTS (STATUS_ABORTED) rather than spinning to EXHAUSTED. A dead
  model stops the run hard; it does not burn iterations doing nothing.

- ITERATION CAP (BUILT). `max_iters` is a hard ceiling -- the loop always
  terminates even if no sentinel ever fires (-> STATUS_EXHAUSTED). The
  feedback-gate retry budget (`max_retries`, default 2) is a second cap: exhausted
  retries -> ABORT, never an infinite retry.

- WALL-CLOCK CAPS (BUILT). The Ollama agent edge has an HTTP timeout; the
  feedback gate has a subprocess timeout (default 600s). Both collapse to a
  fail-closed result on expiry.

- TOKEN CAP (NOT YET ENFORCED). The per-iteration token cap is named as a
  REQUIRED boundary only in the Claude-in-Docker sketch (section 4). The current
  Ollama path enforces wall-clock + iteration caps, NOT a token cap. Treat the
  token cap as a hard requirement for the future Docker agent, not as something
  the present path provides.

- NEVER UNSUPERVISED ON REAL CODE. The orchestrator + adapters CAN run an
  autonomous code-editing loop. You MUST NOT do that unsupervised on the real
  repo. Sandbox + one-iteration-at-a-time + human review is the only sanctioned
  mode.

- HUMAN CHECKPOINT. After each single iteration, a human inspects RunResult +
  the scratch git log before authorizing the next. The feedback gate is the
  automated interlock; the human is the promotion gate.

### What the controlled self-test already proves (offline, temp repo)

`python ralph_adapters.py` proves the full wiring end-to-end against a TEMP repo
only: the real subprocess gate (True iff exit 0), the scratch commit landing on
`ralph/scratch` (and failing soft outside a work tree), the full `run_loop`
wiring (real gate + real scratch commit, one commit, STATUS_COMPLETE), the gate
interlock (a False gate NEVER reaches commit_fn), and the fail-closed agent
(unreachable Ollama -> ABORT -> halt on iteration 1). It touches no real repo and
does not depend on the live LLM for pass/fail.

---

## 4. Built vs documented-not-built

### BUILT and verified (self-tests pass 2026-06-29)

- ralph_executor.py: full pure loop (memory parse/build round-trip, smallest-task
  selection, sentinel precedence ABORT > NO MORE TASKS > HANG ON, gate ordering,
  retry/abort, max_iters ceiling). `ALL RALPH_EXECUTOR TESTS PASS`.
- ralph_adapters.py: feedback_fn_factory, make_scratch_commit_fn,
  make_ollama_agent_fn (local Ollama, fail-closed). `ALL RALPH_ADAPTERS
  CONTROLLED TESTS PASS`.
- orchestrate.py: run(), fork() with the distinct-isolation-key invariant
  (raises on collision), IsolationStrategy enum, Sentinels (reuses parse_promise
  + adds COMPLETE), Output.object Pydantic retry-with-error-feedback. `SELF-TEST:
  PASS`. NOTE: the agent is INJECTED (`agent_fn`); there is NO live LLM transport
  in this module.
- apl_judge.py: grade_apl with the llm= seam, build_prompt, parse_result,
  score_apl, run_calibration, fail-soft ERROR grades, gemma4-over-Ollama
  transport. `ALL APL_JUDGE TESTS PASS`.
- eval_harness.py: evalite() runner, MonteCarloScorer (winrate_over_N, /100
  normalization), Gemma4JudgeScorer, AnthropicJudgeScorer, JSONL trace, mean-gate
  with exit 0/1/2. All 7 hermetic pytest cases pass.

### DOCUMENTED, NOT BUILT -- the live-wiring gaps

Three DISTINCT "Claude / Anthropic" states; do not collapse them.

1. CLAUDE-IN-DOCKER AGENT (the headline gap). `make_claude_docker_agent_fn` is a
   SKETCH ONLY, in the `ralph_adapters.py` docstring. It would run Claude inside a
   locked-down Docker sandbox as the agent_fn instead of local Ollama:
   - `docker run --rm --network none -v <sandbox>:/work:rw <image> claude -p
     --output-format stream-json --dangerously-skip-permissions < prompt.md`
   - parse stream-json with jq into assistant text + proposed task dicts.
   Required constraints for that variant (none yet enforced anywhere):
   `--network none` (or allowlist proxy) so the container cannot exfiltrate; mount
   ONLY the sandbox worktree rw; a HARD wall-clock + TOKEN cap per iteration; same
   fail-closed rule (container error / nonzero exit -> ABORT). Omitted because it
   needs a vetted image + credential plumbing out of scope for the local,
   supervised, single-iteration wiring.

2. AnthropicProvider in the orchestration contract -- NOT BUILT. orchestrate.py
   is orchestration-only: providers (Ollama / Anthropic) are a separate, deferred
   slice. The spec (`2026-06-29-harness-orchestration-contract.md`, Step 4 + Do/
   Defer) defers the AnthropicProvider behind the SDK install and behind lane A
   landing. Imperfection key: `orchestration-anthropic-sdk-not-installed`.

3. AnthropicJudgeScorer -- CODE BUILT, DORMANT. The scorer exists in
   eval_harness.py and is exercised by a test, but the `anthropic` SDK is NOT
   installed (confirmed 2026-06-29), so it returns score=None and skips cleanly
   without importing the SDK. It activates on `pip install anthropic` + an API
   key. Imperfection key: `eval-harness-anthropic-sdk-not-installed`.

Other deferred items (from the two specs):

- nightly_harness migration to go through `run()` (orchestration spec Step 5) --
  deferred behind lane A + the byte-identical determinism gate (5.4).
- git-worktree-backed `branch` isolation -- the named-cache-key form is used
  today; a real second working tree is deferred (grep confirmed zero worktrees in
  use).
- Static HTML CI export, Langfuse / OpenTelemetry trace backends -- JSONL is the
  v1 trace surface; deferred.

---

## 5. Relation to Matt Pocock's sandcastle / Ralph / evalite

This stack is a direct port of the TIER 1 "INCORPORATE / PORT" items in
`harness/knowledge/tech/matt-pocock-ai-eng-roadmap-2026-06-29.md`. The roadmap's
CONCRETE NEXT ACTIONS map onto the modules as follows:

| Roadmap source (Tier 1) | NEXT ACTION # | Module(s) realizing it |
|---|---|---|
| Ralph loop (afk.sh + prompt.md) | #1 | ralph_executor.py + ralph_adapters.py |
| sandcastle (AI-controller blueprint) | #2 | orchestrate.py |
| evalite (eval-as-test) | #4 | eval_harness.py (extends apl_judge.py) |
| neverthrow (Tier 2: explicit Result) | -- | RunResult.error field / no-raise boundary in both run_loop and run() |

Mapping detail:

- RALPH (#1). The roadmap describes a stateless self-looping Executor whose only
  persistent state is git history: pull the last 10 `RALPH:`-tagged commits as
  MEMORY, break the PRD into the SMALLEST unit, pick ONE task, run feedback loops
  (test/typecheck) BEFORE committing, commit a structured `RALPH:` message,
  terminate via `<promise>NO MORE TASKS</promise>` / `<promise>ABORT</promise>`
  sentinels with a "HANG ON A SECOND" self-interrupt. ralph_executor implements
  every one of those as pure functions with injected edges; ralph_adapters
  supplies the live test gate, scratch-branch commit, and (local) LLM agent. The
  roadmap's literal afk.sh "Docker sandbox + stream-json + jq" agent is the
  documented-not-built Claude-in-Docker variant (section 4).

- SANDCASTLE (#2). The roadmap says PORT the domain model: one inspectable
  `run({agent, sandbox, prompt, branchStrategy, maxIterations, ...}) -> RunResult`;
  branch strategies as a first-class enum (head / merge-to-head / branch);
  `fork()` fan-out with the INVARIANT that concurrent forks REQUIRE distinct
  branches; `<promise>COMPLETE</promise>` to break the loop; `Output.object(
  {schema, maxRetries})` typed extraction with retry-on-validation-fail.
  orchestrate.py implements `IsolationStrategy` (head / merge-to-head / branch),
  `run()` returning an inspectable no-raise `RunResult`, `fork()` that RAISES on a
  duplicate isolation key, the `COMPLETE` sentinel layered onto Ralph's parser,
  and `Output.object` as a Pydantic re-prompt-with-error loop. The harness reframe
  the spec records: our "distinct branch" invariant is really "distinct cache
  keys / output paths," the same rule the parallel-launcher cache-collision work
  already follows.

- EVALITE (#4). The roadmap names the AI-eng dividing line -- "can you measure
  whether the agent got better?" -- and prescribes a pytest port: data = cases,
  task = runs the agent/sim, scorers turn output into 0..1, gate CI on
  `mean(score) >= threshold`, and AVERAGE + threshold the mean as the non-flaky
  way to test a stochastic agent. eval_harness.py is that skeleton:
  `data -> task -> scorers[]`, the Monte Carlo sim as `winrate_over_N`, the
  gemma4 + Anthropic LLM-judge scorers (reusing apl_judge via the llm= seam),
  JSONL traces, and a mean-gate with apl_judge's 0/1/2 exit convention.

- NEVERTHROW (Tier 2). The roadmap says PORT THE IDEA: explicit Result objects
  from every agent/tool boundary instead of raising. Both loop drivers do this:
  `RunResult.error` is a FIELD (orchestrate.run never raises across its
  boundary; ralph_executor reports status + notes), and every subprocess / HTTP
  edge is fully guarded.

The transition thesis the roadmap states: the job being moved into is exactly
sandcastle's -- orchestrating agents in isolated sandboxes with git-aware merging,
measured by evals. This stack is the Python realization of that thesis, built
spec-first, with the dangerous half (autonomous code editing) deliberately kept
behind the supervised single-iteration runbook and a still-unbuilt Docker agent.

---

## Changelog

- 2026-06-29: Created. Maps the BUILT autonomous-controller stack (ralph_executor,
  ralph_adapters, orchestrate, apl_judge, eval_harness) -- composition, one-iteration
  data flow, supervised-run runbook + hard safety boundaries, built-vs-documented
  live wiring, and the Matt-Pocock roadmap lineage. All five modules' self-tests
  verified passing at authoring time.
