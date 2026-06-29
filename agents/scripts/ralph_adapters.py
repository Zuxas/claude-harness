"""
ralph_adapters.py -- LIVE injectable adapters for ralph_executor.run_loop.

ralph_executor.py is pure ORCHESTRATION: its run_loop driver is fed three impure
edges (agent_fn / feedback_fn / commit_fn) plus an optional memory_fn. That module
deliberately ships NO live infrastructure. THIS module is the thin wiring that
turns the pure loop into something that can touch a real subprocess test gate, a
real git repo, and a real local LLM (Ollama) -- WITHOUT editing ralph_executor.

It imports from ralph_executor; it never modifies it.

  Provided here:
    feedback_fn_factory(cmd)            -> feedback_fn(task) -> bool
        A REAL subprocess test-gate. True ONLY on a clean (returncode 0) exit.
        Fully guarded (FileNotFoundError / timeout / OSError all collapse to
        False), mirroring ralph_executor._run_git's guard discipline. Gate is
        run BEFORE any commit by run_loop, so a False here means "do not commit".

    make_scratch_commit_fn(repo_dir, branch=..., allow_empty=True)
                                        -> commit_fn(message) -> bool
        A guarded git commit that ONLY ever lands on a throwaway SCRATCH branch
        (git checkout -B <branch>) inside the given repo_dir. Defaults to
        --allow-empty so a memory-only RALPH iteration still records a commit.
        It binds repo_dir + branch via closure because run_loop calls the commit
        edge with a SINGLE positional arg: commit_fn(message).

    make_ollama_agent_fn(model=..., ...) -> agent_fn(memory, iteration) -> AgentStep
        A constrained local backend: one guarded HTTP call to Ollama
        (qwen2.5-coder:7b by default) at http://localhost:11434/api/generate.
        Renders the MemoryEntry list + RALPH prompt discipline into a prompt,
        asks the model for a fenced-JSON `candidates` array, and parses
        defensively. FAIL-SOFT semantics: if Ollama is unreachable / errors /
        times out, it returns AgentStep(text="<promise>ABORT</promise>") so the
        autonomous loop FAILS CLOSED (halts) rather than spinning to EXHAUSTED.
        (Tradeoff documented in make_ollama_agent_fn.)

============================================================================
HOW TO DO A REAL SUPERVISED RUN  (read before running anything autonomous)
============================================================================
The orchestrator + these adapters CAN run an autonomous code-editing loop. You
MUST NOT do that unsupervised on the real repo. A real supervised run looks like:

  1. Make a sandbox. Either:
       (a) git worktree add ../ralph-sandbox <base-sha>   (preferred: real files,
           isolated branch, easy to throw away), or
       (b) cp/clone the repo to a temp dir.
     NEVER point commit_fn at the live working checkout.

  2. Wire the adapters against the sandbox, with a HUMAN in the loop:
       from ralph_executor import run_loop
       from ralph_adapters import (feedback_fn_factory, make_scratch_commit_fn,
                                   make_ollama_agent_fn)
       gate   = feedback_fn_factory(["python", "-m", "pytest", "-q"])
       commit = make_scratch_commit_fn(SANDBOX, branch="ralph/scratch")
       agent  = make_ollama_agent_fn(model="qwen2.5-coder:7b")
       res    = run_loop(max_iters=1, agent_fn=agent, feedback_fn=gate,
                         commit_fn=commit, memory_fn=lambda: [])
     Run ONE iteration (max_iters=1), then STOP and inspect res.notes /
     res.commits / git log on the scratch branch BEFORE running another.

  3. Promote nothing automatically. Diff the scratch branch, review by hand, and
     cherry-pick/merge deliberately. The scratch branch is disposable.

SAFETY BOUNDARY (hard rules):
  - commit_fn only ever lands on a SCRATCH branch in a SANDBOX dir. It does a
    `git checkout -B`, which is destructive to that branch ref by design -- which
    is exactly why it must never point at the live working branch.
  - The agent edge can only PROPOSE tasks; the feedback gate is the safety
    interlock -- nothing commits unless the real test command exits 0.
  - This module's __main__ self-test proves the wiring end-to-end against a
    TEMP repo only. It never touches the real repo, never calls the real LLM in
    the pass/fail path, and runs exactly the loop iterations it asserts.

----------------------------------------------------------------------------
CLAUDE-IN-DOCKER AGENT VARIANT  (documented, intentionally NOT built here)
----------------------------------------------------------------------------
A stronger agent_fn would run Claude inside a locked-down Docker sandbox instead
of a local Ollama model. Sketch (do NOT implement without explicit sign-off):

  def make_claude_docker_agent_fn(image, workdir, prompt_path):
      def agent_fn(memory, iteration):
          # docker run --rm --network none -v <sandbox>:/work:rw <image> \
          #     claude -p --output-format stream-json --dangerously-skip-permissions \
          #     < prompt.md   (prompt seeded with rendered `memory`)
          # Parse the stream-json with jq into assistant text + proposed task dicts,
          # then return AgentStep(text=..., candidates=[...]).
          ...
  Key constraints for that variant:
    - --network none (or an allowlist proxy) so the container cannot exfiltrate.
    - Mount ONLY the sandbox worktree rw; everything else ro or unmounted.
    - A hard wall-clock + token cap per iteration.
    - Same fail-closed rule: container error / nonzero exit -> ABORT sentinel.
  It is omitted here because it needs a vetted image + credential plumbing that
  is out of scope for the local, supervised, single-iteration wiring deliverable.
"""

import json
import shlex
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable, List, Optional, Sequence, Union

# cwd is frequently NOT this dir (it resets between shell calls), so make the
# sibling ralph_executor importable regardless of where we are launched from.
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from ralph_executor import (  # noqa: E402  (path insert must precede import)
    AgentStep,
    MemoryEntry,
    PROMISE_ABORT,
)

# The literal ABORT sentinel text run_loop scans for (parse_promise). Building it
# from the token keeps it in lockstep with ralph_executor's detector.
_ABORT_SENTINEL = "<promise>%s</promise>" % PROMISE_ABORT.replace("_", " ")


# ---------------------------------------------------------------------------
# 1. feedback_fn_factory -- real subprocess test-gate (guarded; True iff exit 0)
# ---------------------------------------------------------------------------

def feedback_fn_factory(cmd: Union[str, Sequence[str]],
                        cwd: Optional[str] = None,
                        timeout: int = 600) -> Callable[[dict], bool]:
    """Build a feedback_fn(task) -> bool that runs a REAL test command.

    `cmd` may be a list (preferred, no shell) or a string (split with shlex; we
    never use shell=True, which is both safer and consistent across Win/POSIX).
    Examples:
        feedback_fn_factory(["python", "-m", "py_compile", "ralph_executor.py"])
        feedback_fn_factory("python -m pytest -q")

    The returned closure receives the selected task dict (run_loop passes it) but
    by default ignores it -- the gate is a fixed project command. Returns True
    ONLY when the process exits 0. Every failure mode (binary missing, timeout,
    OS error, nonzero exit) collapses to False so the gate is a hard interlock:
    run_loop will NOT commit on a False.
    """
    args: List[str] = shlex.split(cmd) if isinstance(cmd, str) else list(cmd)

    def feedback_fn(task: dict) -> bool:  # noqa: ARG001 -- task accepted, unused
        if not args:
            return False
        try:
            proc = subprocess.run(
                args,
                capture_output=True, text=True, timeout=timeout,
                cwd=cwd,
            )
        except FileNotFoundError:
            return False
        except subprocess.TimeoutExpired:
            return False
        except OSError:
            return False
        return proc.returncode == 0

    return feedback_fn


# ---------------------------------------------------------------------------
# 2. make_scratch_commit_fn -- guarded commit, SCRATCH branch only
# ---------------------------------------------------------------------------

def _run_git(args: Sequence[str], repo_dir: str,
             timeout: int = 30) -> "tuple[bool, str]":
    """Local guarded git edge (does not import ralph_executor's private one).

    Never raises: git absent, nonzero exit, or timeout all collapse to (False,...).
    """
    try:
        proc = subprocess.run(
            ["git", *args],
            capture_output=True, text=True, timeout=timeout, cwd=repo_dir,
        )
    except FileNotFoundError:
        return (False, "")
    except subprocess.TimeoutExpired:
        return (False, "")
    except OSError:
        return (False, "")
    if proc.returncode != 0:
        return (False, proc.stdout or "")
    return (True, proc.stdout or "")


def make_scratch_commit_fn(repo_dir: str,
                           branch: str = "ralph/scratch",
                           allow_empty: bool = True
                           ) -> Callable[[str], bool]:
    """Build a commit_fn(message) -> bool that commits ONLY on a SCRATCH branch.

    Binds `repo_dir` + `branch` by closure because run_loop calls the commit edge
    with a single positional arg (commit_fn(message)).

    On each call it `git checkout -B <branch>` (force-(re)create the scratch ref
    off the current HEAD) THEN commits. Defaulting to --allow-empty means a
    memory-only RALPH iteration still lands a commit on the scratch branch.

    SAFETY: `checkout -B` is destructive to <branch>'s ref. That is intended for a
    throwaway branch and is precisely why this must NEVER be pointed at the live
    working branch. Point it at a sandbox/worktree only. Fully guarded: any git
    failure returns False, so run_loop records "commit_fn failed" rather than
    crashing.
    """
    repo = str(repo_dir)

    def commit_fn(message: str) -> bool:
        # Refuse to operate if repo_dir is not actually a git work tree.
        ok, out = _run_git(["rev-parse", "--is-inside-work-tree"], repo)
        if not ok or "true" not in out.lower():
            return False
        # Move onto / (re)create the scratch branch. Never touches other branches.
        ok, _ = _run_git(["checkout", "-B", branch], repo)
        if not ok:
            return False
        commit_args = ["commit", "-m", message]
        if allow_empty:
            commit_args.insert(1, "--allow-empty")
        ok, _ = _run_git(commit_args, repo)
        return ok

    return commit_fn


# ---------------------------------------------------------------------------
# 3. make_ollama_agent_fn -- constrained local LLM backend (fail-closed)
# ---------------------------------------------------------------------------

_OLLAMA_URL = "http://localhost:11434/api/generate"

_RALPH_SYSTEM = (
    "You are the Executor in a RALPH autonomous loop. Pick the SMALLEST next unit "
    "of work ('do not outrun your headlights'). Respond with a short plain-text "
    "explanation, then a fenced ```json block containing a `candidates` array. "
    "Each candidate is an object with keys: task (str), prd_ref (str), decisions "
    "(list of str), files (list of str), size (int -- smaller is smaller scope). "
    "If there is genuinely no work left, instead include the literal token "
    "<promise>NO MORE TASKS</promise> in your text. If a task is too large to do "
    "safely, write HANG ON A SECOND in your text and propose a smaller re-scope."
)


def _render_memory(memory: List[MemoryEntry]) -> str:
    """Render the MemoryEntry list (NOT strings) into prompt context text."""
    if not memory:
        return "(no prior RALPH commits)"
    lines = []
    for e in memory[:10]:
        bits = ["- " + (e.task or "(untitled)")]
        if e.prd_ref:
            bits.append("[%s]" % e.prd_ref)
        if e.notes_for_next:
            bits.append("notes-for-next: " + e.notes_for_next)
        lines.append(" ".join(bits))
    return "\n".join(lines)


def _extract_candidates(text: str) -> List[dict]:
    """Defensively pull a `candidates` list out of a fenced ```json block.

    Returns [] on any parse failure -- the loop still works text-only because
    parse_promise scans the raw text for sentinels independently.
    """
    if not text or "```" not in text:
        return []
    # Grab the content of the first fenced block (``` or ```json).
    try:
        after = text.split("```", 1)[1]
        # Drop an optional leading "json" language tag on the fence line.
        first_nl = after.find("\n")
        if first_nl != -1 and after[:first_nl].strip().lower() in ("json", ""):
            after = after[first_nl + 1:]
        block = after.split("```", 1)[0].strip()
        if not block:
            return []
        data = json.loads(block)
    except (ValueError, IndexError):
        return []
    if isinstance(data, dict):
        cands = data.get("candidates", [])
    elif isinstance(data, list):
        cands = data
    else:
        return []
    return [c for c in cands if isinstance(c, dict)]


def make_ollama_agent_fn(model: str = "qwen2.5-coder:7b",
                         url: str = _OLLAMA_URL,
                         timeout: int = 180,
                         prd_context: str = ""
                         ) -> Callable[[List[MemoryEntry], int], AgentStep]:
    """Build an agent_fn(memory, iteration) -> AgentStep backed by local Ollama.

    One guarded HTTP POST per call to {url} with stream=false. The prompt embeds
    the rendered memory + RALPH discipline and requests a fenced-JSON candidates
    array, which is parsed defensively.

    FAIL-SOFT / FAIL-CLOSED: if Ollama is down, errors, times out, or returns
    unusable output, this returns AgentStep(text=<ABORT sentinel>). run_loop then
    halts with STATUS_ABORTED rather than idling to EXHAUSTED. Rationale: in an
    UNSUPERVISED autonomous loop, a dead model should stop the run hard, not burn
    iterations doing nothing. (If you prefer fail-OPEN -- idle and keep polling --
    swap the return for AgentStep(text="model unavailable") with no sentinel.)
    """
    def agent_fn(memory: List[MemoryEntry], iteration: int) -> AgentStep:
        prompt = (
            _RALPH_SYSTEM
            + "\n\n## PRD / context\n" + (prd_context or "(none provided)")
            + "\n\n## Recent RALPH memory\n" + _render_memory(memory)
            + "\n\n## Iteration\n" + str(iteration)
            + "\n\nRespond now."
        )
        body = json.dumps({"model": model, "prompt": prompt,
                           "stream": False}).encode("utf-8")
        req = urllib.request.Request(
            url, data=body, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError:
            return AgentStep(text=_ABORT_SENTINEL)
        except (TimeoutError, OSError):
            return AgentStep(text=_ABORT_SENTINEL)
        except ValueError:  # bad JSON envelope from Ollama
            return AgentStep(text=_ABORT_SENTINEL)

        text = payload.get("response", "") if isinstance(payload, dict) else ""
        if not text:
            return AgentStep(text=_ABORT_SENTINEL)
        return AgentStep(text=text, candidates=_extract_candidates(text))

    return agent_fn


def ollama_smoke_probe(model: str = "qwen2.5-coder:7b",
                       url: str = _OLLAMA_URL,
                       timeout: int = 60) -> "tuple[bool, str]":
    """Guarded one-shot probe of the live agent edge. (ok, note).

    Used by the self-test to exercise the REAL Ollama call without coupling the
    wiring test's pass/fail to a (possibly absent / slow) model. ok=False with a
    descriptive note when Ollama is unreachable.
    """
    agent = make_ollama_agent_fn(model=model, url=url, timeout=timeout,
                                 prd_context="Toy PRD: ensure foo() returns 1.")
    step = agent([], 0)
    if not isinstance(step, AgentStep):
        return (False, "agent_fn did not return an AgentStep")
    if step.text == _ABORT_SENTINEL:
        return (False, "Ollama unreachable/errored (fail-closed ABORT returned)")
    return (True, "Ollama responded; %d candidate(s) parsed" % len(step.candidates))


# ===========================================================================
# CONTROLLED self-test -- proves LIVE wiring end-to-end on a TEMP repo.
# Touches NO real repo, does NOT depend on the live LLM for pass/fail.
# Run: python ralph_adapters.py
# ===========================================================================

def _controlled_selftest() -> int:
    import os
    import shutil
    import tempfile

    from ralph_executor import run_loop, STATUS_COMPLETE, parse_ralph_log

    failures: List[str] = []

    def check(cond: bool, label: str):
        if not cond:
            failures.append(label)

    # -- 0. feedback_fn_factory: real subprocess gate, True iff exit 0 --------
    gate_pass = feedback_fn_factory([sys.executable, "-c", "import sys; sys.exit(0)"])
    gate_fail = feedback_fn_factory([sys.executable, "-c", "import sys; sys.exit(1)"])
    gate_missing = feedback_fn_factory(["definitely-not-a-real-binary-xyz"])
    check(gate_pass({"task": "toy"}) is True, "gate must be True on clean exit 0")
    check(gate_fail({"task": "toy"}) is False, "gate must be False on nonzero exit")
    check(gate_missing({"task": "toy"}) is False, "gate must be False (guarded) when binary missing")
    # String form is shlex-split, no shell.
    gate_str = feedback_fn_factory("%s -c \"exit(0)\"" % shlex.quote(sys.executable))
    check(gate_str({"task": "toy"}) is True, "string-form gate must run + pass")

    # -- TEMP repo for the scratch commit_fn (NEVER the real repo) -----------
    sandbox = tempfile.mkdtemp(prefix="ralph_sandbox_")
    try:
        ok, _ = _run_git(["init"], sandbox)
        check(ok, "temp repo: git init failed")
        _run_git(["config", "user.email", "ralph@example.invalid"], sandbox)
        _run_git(["config", "user.name", "Ralph Selftest"], sandbox)
        # Need at least one ref for checkout -B to anchor; allow-empty initial.
        _run_git(["commit", "--allow-empty", "-m", "seed"], sandbox)

        commit_fn = make_scratch_commit_fn(sandbox, branch="ralph/scratch")

        # -- 1. scratch commit_fn lands on the scratch branch ----------------
        ok_commit = commit_fn("RALPH: probe commit\n\nFiles: x.py\n")
        check(ok_commit is True, "scratch commit_fn should succeed on temp repo")
        ok, cur = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], sandbox)
        check(ok and cur.strip() == "ralph/scratch",
              "commit must land on scratch branch, on %r" % cur.strip())

        # commit_fn pointed at a NON-repo dir must fail-soft (False), not raise.
        nonrepo = tempfile.mkdtemp(prefix="ralph_notrepo_")
        try:
            bad_commit = make_scratch_commit_fn(nonrepo)
            check(bad_commit("RALPH: should not land") is False,
                  "commit_fn must return False (guarded) outside a git work tree")
        finally:
            shutil.rmtree(nonrepo, ignore_errors=True)

        # -- 2. FULL run_loop wiring: real gate + real scratch commit --------
        # Deterministic 2-step stub agent (NOT the live LLM) so the wiring
        # test's pass/fail can't be flaked by a model response. Off-by-one note:
        # candidate on iter 0, NO-MORE-TASKS on iter 1, max_iters=2 ->
        # exactly one commit, STATUS_COMPLETE.
        def stub_agent(memory, i):
            check(isinstance(memory, list), "agent_fn must receive a memory list")
            if i == 0:
                return AgentStep(candidates=[{
                    "task": "toy unit: touch sentinel file",
                    "prd_ref": "TOY-1",
                    "decisions": ["use a real py exit-0 gate"],
                    "files": ["toy.py"],
                    "size": 1,
                }])
            return AgentStep(text="done <promise>NO MORE TASKS</promise>")

        real_gate = feedback_fn_factory([sys.executable, "-c", "import sys; sys.exit(0)"])
        res = run_loop(
            max_iters=2,
            agent_fn=stub_agent,
            feedback_fn=real_gate,
            commit_fn=commit_fn,
            memory_fn=lambda: [],   # explicit: do NOT let it git-log the cwd
        )
        check(res.status == STATUS_COMPLETE,
              "wired loop should COMPLETE, got %r (%s)" % (res.status, res.notes))
        check(len(res.commits) == 1,
              "wired loop should land exactly 1 commit, got %d" % len(res.commits))
        # The commit really landed on the scratch branch in the temp repo.
        ok, log = _run_git(["log", "--format=%s", "ralph/scratch"], sandbox)
        check(ok and "RALPH: toy unit: touch sentinel file" in log,
              "scratch branch must contain the RALPH commit; log=%r" % log)
        # And it round-trips back through the parser.
        parsed = parse_ralph_log(res.commits[0])
        check(len(parsed) == 1 and parsed[0].task == "toy unit: touch sentinel file",
              "wired commit message must round-trip through parse_ralph_log")

        # -- 3. gate FALSE blocks the commit (interlock holds) ---------------
        before_commit = {"n": 0}
        def counting_commit(msg):
            before_commit["n"] += 1
            return commit_fn(msg)
        res_blocked = run_loop(
            max_iters=2,
            agent_fn=lambda m, i: AgentStep(candidates=[{"task": "blocked", "size": 1}]),
            feedback_fn=feedback_fn_factory([sys.executable, "-c", "import sys; sys.exit(1)"]),
            commit_fn=counting_commit,
            memory_fn=lambda: [],
            max_retries=1,
        )
        check(before_commit["n"] == 0,
              "failing gate must NEVER reach commit_fn (got %d calls)" % before_commit["n"])
        check(len(res_blocked.commits) == 0, "failing gate must produce 0 commits")

        # -- 4. agent fail-closed: unreachable Ollama -> ABORT sentinel ------
        dead_agent = make_ollama_agent_fn(url="http://127.0.0.1:1/api/generate",
                                          timeout=2)
        step = dead_agent([], 0)
        check(step.text == _ABORT_SENTINEL,
              "unreachable Ollama must fail-closed to ABORT sentinel, got %r" % step.text)
        res_dead = run_loop(
            max_iters=3,
            agent_fn=dead_agent,
            feedback_fn=lambda t: True,
            commit_fn=lambda m: True,
            memory_fn=lambda: [],
        )
        from ralph_executor import STATUS_ABORTED
        check(res_dead.status == STATUS_ABORTED,
              "dead-agent loop should ABORT, got %r" % res_dead.status)
        check(res_dead.iterations == 1, "fail-closed ABORT should halt on iter 1")
    finally:
        shutil.rmtree(sandbox, ignore_errors=True)

    # -- 5. LIVE Ollama smoke probe (guarded; informational, never fails) ----
    ok_live, note = ollama_smoke_probe(timeout=60)
    if ok_live:
        print("OLLAMA SMOKE PROBE: live -- %s" % note)
    else:
        print("OLLAMA SMOKE PROBE: skipped/down -- %s" % note)

    # -- report --------------------------------------------------------------
    if failures:
        print("RALPH_ADAPTERS CONTROLLED SELF-TEST FAILURES (%d):" % len(failures))
        for f in failures:
            print("  - " + f)
        return 1
    print("ALL RALPH_ADAPTERS CONTROLLED TESTS PASS")
    return 0


if __name__ == "__main__":
    sys.exit(_controlled_selftest())
