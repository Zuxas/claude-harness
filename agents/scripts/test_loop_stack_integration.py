"""
test_loop_stack_integration.py -- integration test for the autonomous-loop stack.

Proves that the THREE lane modules COMPOSE end-to-end on a CONTROLLED toy task,
with NO live LLM, NO unsupervised run, and NO real-repo commits:

  ralph_executor.py  -- the pure RALPH loop driver (run_loop) + sentinel parser
  ralph_adapters.py  -- LIVE injectable edges (real feedback_fn_factory, etc.)
  orchestrate.py     -- the sandcastle-derived run()/fork() contract + Sentinels

This is NOT a re-run of each module's own self-test. It exercises the two genuine
CROSS-MODULE seams:

  SEAM 1 (executor <- adapters):
    ralph_adapters.feedback_fn_factory wired INTO ralph_executor.run_loop as the
    real test gate. Proven in BOTH directions:
      - passing real gate (py_compile of a VALID tempfile) -> exactly one commit,
        STATUS_COMPLETE, message round-trips through parse_ralph_log;
      - failing real gate (py_compile of a BROKEN tempfile) -> zero commits, the
        commit edge is NEVER reached, retries exhaust -> STATUS_ABORTED.

  SEAM 2 (orchestrate <- executor):
    orchestrate.Sentinels delegates to ralph_executor.parse_promise. Proven by:
      - IDENTITY: orchestrate's ABORT/NO_MORE_TASKS/HANG_ON constants ARE the
        ralph_executor constants (imported, not re-declared);
      - BEHAVIORAL: for any text whose parse_promise verdict is ABORT/
        NO_MORE_TASKS/HANG_ON with no COMPLETE token, Sentinels.parse agrees.
      - The documented layering (COMPLETE outranks NO_MORE_TASKS in Sentinels,
        and parse_promise does not know COMPLETE) is BY DESIGN and is asserted as
        such -- NOT treated as a mismatch.

  Plus: orchestrate.run() yields a well-formed RunResult on a COMPLETE sentinel,
  and orchestrate.fork() RAISES on a duplicate isolation key (cross-module
  fan-out invariant).

Optional enrichment (guarded on git presence; absence is a printed SKIP, never a
failure): ralph_adapters.make_scratch_commit_fn wired through run_loop against a
TEMP git repo, proving the third adapter composes and the commit lands on a
throwaway scratch branch.

Run: python test_loop_stack_integration.py    # prints banner, exits 0/1

NOTE: this test file is the only artifact this lane owns. It does NOT edit any of
the three source modules; it imports them. A real interface mismatch surfaces as a
failing assertion (-> the run exits 1 with the specific failure), not a patch.
"""

import os
import shutil
import sys
import tempfile
from typing import List

# Make this script's own directory importable so the three modules resolve
# regardless of cwd (the same robustness pattern orchestrate.py uses).
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

# -- lane A: the pure loop driver + sentinel parser + constants -------------
from ralph_executor import (
    run_loop,
    parse_promise,
    parse_ralph_log,
    AgentStep,
    STATUS_COMPLETE,
    STATUS_ABORTED,
    PROMISE_ABORT,
    PROMISE_NO_MORE_TASKS,
    PROMISE_HANG_ON,
)

# -- lane B: the LIVE injectable adapters -----------------------------------
from ralph_adapters import (
    feedback_fn_factory,
    make_scratch_commit_fn,
)

# -- lane C: the orchestration contract (pulls in pydantic) -----------------
# If this import fails it is an ENVIRONMENT problem (missing pydantic), NOT a
# composition finding -- the message below makes that distinction explicit.
try:
    from orchestrate import (
        run as orch_run,
        fork as orch_fork,
        RunSpec,
        RunResult as OrchRunResult,
        IterationRecord,
        IsolationStrategy,
        Sentinels,
    )
except Exception as _imp_exc:  # pragma: no cover -- environment guard
    print("ENVIRONMENT ERROR: could not import orchestrate.py "
          "(this is environment, not a composition mismatch): %s" % _imp_exc)
    sys.exit(1)


# ---------------------------------------------------------------------------
# tiny assertion harness (collect-all, report-all)
# ---------------------------------------------------------------------------

_FAILURES: List[str] = []


def check(cond: bool, label: str) -> None:
    if not cond:
        _FAILURES.append(label)


def _write_tempfile(suffix: str, content: str) -> str:
    """Write content to a NamedTemporaryFile and return its path (closed handle
    so Windows can re-open it for py_compile)."""
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "w", encoding="ascii") as fh:
        fh.write(content)
    return path


# ===========================================================================
# PART 1 -- SEAM 1: ralph_adapters.feedback_fn_factory INTO ralph_executor.run_loop
# ===========================================================================

def part1_executor_plus_real_gate() -> None:
    # Real passing gate: py_compile of a VALID python tempfile (exit 0 -> True).
    valid_py = _write_tempfile(".py", "x = 1\ndef foo():\n    return 1\n")
    # Real failing gate: py_compile of a BROKEN python tempfile (nonzero -> False).
    broken_py = _write_tempfile(".py", "def (:\n    return\n")

    try:
        passing_gate = feedback_fn_factory(
            [sys.executable, "-m", "py_compile", valid_py])
        failing_gate = feedback_fn_factory(
            [sys.executable, "-m", "py_compile", broken_py])

        # Sanity: the REAL adapter gate behaves as documented before we wire it.
        check(passing_gate({"task": "probe"}) is True,
              "feedback_fn_factory must return True on a valid py_compile (exit 0)")
        check(failing_gate({"task": "probe"}) is False,
              "feedback_fn_factory must return False on a broken py_compile (nonzero)")

        # -- 1a. PASSING gate -> exactly one commit, STATUS_COMPLETE ----------
        # Deterministic 2-step stub agent (NOT a live LLM): candidate on iter 0,
        # NO MORE TASKS on iter 1. max_iters=2 -> exactly one commit.
        committed: List[str] = []

        def mock_commit(msg: str) -> bool:
            committed.append(msg)
            return True

        def stub_agent_pass(memory, i):
            check(isinstance(memory, list), "agent_fn must receive a memory list")
            if i == 0:
                return AgentStep(candidates=[{
                    "task": "toy unit: add foo() guard",
                    "prd_ref": "TOY-1",
                    "decisions": ["wire the real py_compile gate"],
                    "files": ["toy.py"],
                    "notes_for_next": "next lane wires live LLM",
                    "size": 1,
                }])
            return AgentStep(text="all done <promise>NO MORE TASKS</promise>")

        res = run_loop(
            max_iters=2,
            agent_fn=stub_agent_pass,
            feedback_fn=passing_gate,       # <-- the lane-B real gate, injected
            commit_fn=mock_commit,          # <-- tempdir/mock commit edge
            memory_fn=lambda: [],           # explicit: never git-log the cwd
        )
        check(res.status == STATUS_COMPLETE,
              "passing-gate loop should COMPLETE, got %r (%s)" % (res.status, res.notes))
        check(len(res.commits) == 1,
              "passing-gate loop should land exactly 1 commit, got %d" % len(res.commits))
        check(len(committed) == 1,
              "commit edge should be reached exactly once, got %d" % len(committed))
        check(res.gate_failures == 0,
              "passing gate should record 0 gate failures, got %d" % res.gate_failures)
        # The loop-built RALPH: message round-trips through the lane-A parser.
        parsed = parse_ralph_log(res.commits[0])
        check(len(parsed) == 1 and parsed[0].task == "toy unit: add foo() guard",
              "loop commit must round-trip through parse_ralph_log; got %r" % (parsed,))
        check(parsed and parsed[0].prd_ref == "TOY-1" and parsed[0].files == ["toy.py"],
              "round-tripped commit must preserve prd_ref + files")

        # -- 1b. FAILING gate -> zero commits, commit edge NEVER reached ------
        # The feedback gate is the safety interlock: nothing commits unless the
        # real test command exits 0. max_retries=1 + a candidate every iteration
        # -> iter0 fail (retries=1, not >1), iter1 fail (retries=2 >1) -> ABORT.
        commit_calls = {"n": 0}

        def counting_commit(msg: str) -> bool:
            commit_calls["n"] += 1
            return True

        def stub_agent_every_iter(memory, i):
            return AgentStep(candidates=[{"task": "blocked unit", "size": 1,
                                          "files": ["x.py"]}])

        res_blocked = run_loop(
            max_iters=5,
            agent_fn=stub_agent_every_iter,
            feedback_fn=failing_gate,       # <-- the lane-B real FAILING gate
            commit_fn=counting_commit,
            memory_fn=lambda: [],
            max_retries=1,
        )
        check(commit_calls["n"] == 0,
              "failing gate must NEVER reach the commit edge; got %d calls" % commit_calls["n"])
        check(len(res_blocked.commits) == 0,
              "failing gate must produce 0 commits, got %d" % len(res_blocked.commits))
        check(res_blocked.status == STATUS_ABORTED,
              "exhausted-retry failing gate should ABORT, got %r" % res_blocked.status)
        check(res_blocked.gate_failures == 2,
              "max_retries=1 should yield exactly 2 gate failures, got %d"
              % res_blocked.gate_failures)
    finally:
        for p in (valid_py, broken_py):
            try:
                os.remove(p)
            except OSError:
                pass


# ===========================================================================
# PART 2 -- SEAM 2: orchestrate.run + Sentinels <-> ralph_executor.parse_promise
# ===========================================================================

def part2_orchestrate_run_and_shared_sentinels() -> None:
    # -- 2a. run() yields a well-formed RunResult on a COMPLETE sentinel ------
    def agent_completes(prompt: str, i: int) -> str:
        if i < 2:
            return "working, iteration %d" % i
        return "all done here <promise>COMPLETE</promise>"

    res = orch_run(agent_completes, IsolationStrategy.HEAD, "do the toy thing",
                   Sentinels.COMPLETE, max_iters=10)
    check(isinstance(res, OrchRunResult), "run() must return a RunResult")
    check(res.completed is True, "COMPLETE sentinel should set completed=True")
    check(res.error is None, "clean completion should have error=None, got %r" % res.error)
    check(res.isolation_key == "head", "HEAD run isolation_key should be 'head'")
    check(isinstance(res.iterations, list) and isinstance(res.outputs, list),
          "RunResult.iterations and .outputs must be lists (well-formed)")
    check(len(res.iterations) == 3,
          "run() should terminate on iter 2 (3 records), got %d" % len(res.iterations))
    check(all(isinstance(r, IterationRecord) for r in res.iterations),
          "every RunResult.iterations entry must be an IterationRecord")
    check(res.iterations[-1].sentinel == Sentinels.COMPLETE,
          "last iteration sentinel should be COMPLETE")

    # -- 2b. SHARED SENTINEL CONTRACT: identity (same constant objects) -------
    # orchestrate imports the ralph_executor constants; it does NOT re-declare
    # them. Prove they are literally the same values.
    check(Sentinels.ABORT == PROMISE_ABORT,
          "Sentinels.ABORT must BE ralph_executor.PROMISE_ABORT")
    check(Sentinels.NO_MORE_TASKS == PROMISE_NO_MORE_TASKS,
          "Sentinels.NO_MORE_TASKS must BE ralph_executor.PROMISE_NO_MORE_TASKS")
    check(Sentinels.HANG_ON == PROMISE_HANG_ON,
          "Sentinels.HANG_ON must BE ralph_executor.PROMISE_HANG_ON")

    # -- 2c. SHARED SENTINEL CONTRACT: behavioral agreement -------------------
    # For any text whose parse_promise verdict is one of the SHARED tokens and
    # that carries NO COMPLETE token, Sentinels.parse must return the same token.
    shared_texts = [
        "cannot proceed <promise>ABORT</promise>",
        "done <promise>NO MORE TASKS</promise>",
        "this is too big, HANG ON A SECOND",
        "<promise>NO MORE TASKS</promise> <promise>ABORT</promise>",  # ABORT wins both
        "<PROMISE> no more tasks </PROMISE>",                          # case/space tolerant
        "nothing of interest here",                                   # None on both sides
    ]
    for t in shared_texts:
        rp = parse_promise(t)
        sp = Sentinels.parse(t)
        check(rp == sp,
              "shared-sentinel disagreement on %r: parse_promise=%r Sentinels.parse=%r"
              % (t, rp, sp))

    # -- 2d. DOCUMENTED LAYERING (by design -- NOT a mismatch) ----------------
    # COMPLETE is orchestrate-only: parse_promise does not know it, Sentinels does.
    complete_only = "finished <promise>COMPLETE</promise>"
    check(parse_promise(complete_only) is None,
          "parse_promise must NOT recognise COMPLETE (it is orchestrate-only)")
    check(Sentinels.parse(complete_only) == Sentinels.COMPLETE,
          "Sentinels.parse must recognise COMPLETE (layered on top)")
    # And COMPLETE outranks NO_MORE_TASKS in Sentinels (documented precedence),
    # while ABORT still wins over COMPLETE on safety.
    check(Sentinels.parse("<promise>COMPLETE</promise> <promise>NO MORE TASKS</promise>")
          == Sentinels.COMPLETE,
          "COMPLETE should outrank NO MORE TASKS in Sentinels.parse (by design)")
    check(Sentinels.parse("<promise>COMPLETE</promise> <promise>ABORT</promise>")
          == Sentinels.ABORT,
          "ABORT must win over COMPLETE on safety")


# ===========================================================================
# PART 3 -- orchestrate.fork() RAISES on a duplicate isolation key
# ===========================================================================

def part3_fork_distinct_key_invariant() -> None:
    done = "<promise>COMPLETE</promise>"

    # Two HEAD children collide on the single shared key "head" -> must RAISE.
    raised_head = False
    try:
        orch_fork([
            RunSpec(lambda p, i: done, IsolationStrategy.HEAD, "a", Sentinels.COMPLETE, 1),
            RunSpec(lambda p, i: done, IsolationStrategy.HEAD, "b", Sentinels.COMPLETE, 1),
        ])
    except ValueError:
        raised_head = True
    check(raised_head,
          "fork() must RAISE on a duplicate isolation key (two HEAD children)")

    # Two BRANCH children sharing a branch_name collide on that key -> must RAISE.
    raised_branch = False
    try:
        orch_fork([
            RunSpec(lambda p, i: done, IsolationStrategy.BRANCH, "a",
                    Sentinels.COMPLETE, 1, branch_name="cand-1"),
            RunSpec(lambda p, i: done, IsolationStrategy.BRANCH, "b",
                    Sentinels.COMPLETE, 1, branch_name="cand-1"),
        ])
    except ValueError:
        raised_branch = True
    check(raised_branch,
          "fork() must RAISE on two BRANCH children sharing a branch_name")

    # NEGATIVE direction: distinct branch names do NOT collide -> both complete.
    forked = orch_fork([
        RunSpec(lambda p, i: done, IsolationStrategy.BRANCH, "a",
                Sentinels.COMPLETE, 2, branch_name="cand-1"),
        RunSpec(lambda p, i: done, IsolationStrategy.BRANCH, "b",
                Sentinels.COMPLETE, 2, branch_name="cand-2"),
    ])
    check(len(forked) == 2 and all(r.completed for r in forked),
          "fork() with distinct branch keys should return 2 completed RunResults")
    check([r.isolation_key for r in forked] == ["cand-1", "cand-2"],
          "distinct-branch children should carry their distinct isolation keys")


# ===========================================================================
# PART 4 -- (enrichment, guarded) make_scratch_commit_fn through run_loop
# ===========================================================================

def part4_scratch_commit_composition() -> None:
    """Wire the THIRD adapter (make_scratch_commit_fn) through run_loop against a
    TEMP git repo. Guarded on git presence; absence is a printed SKIP, never a
    failure -- no required assertion rides on git being installed."""
    if shutil.which("git") is None:
        print("SCRATCH-COMMIT COMPOSITION: skipped -- git not on PATH")
        return

    import subprocess

    def _git(args, cwd):
        try:
            p = subprocess.run(["git", *args], capture_output=True, text=True,
                               timeout=30, cwd=cwd)
            return p.returncode == 0, (p.stdout or "")
        except (OSError, subprocess.SubprocessError):
            return False, ""

    sandbox = tempfile.mkdtemp(prefix="loopstack_sandbox_")
    valid_py = _write_tempfile(".py", "y = 2\n")
    try:
        ok, _ = _git(["init"], sandbox)
        if not ok:
            print("SCRATCH-COMMIT COMPOSITION: skipped -- git init failed")
            return
        _git(["config", "user.email", "loopstack@example.invalid"], sandbox)
        _git(["config", "user.name", "Loopstack Test"], sandbox)
        _git(["commit", "--allow-empty", "-m", "seed"], sandbox)

        commit_fn = make_scratch_commit_fn(sandbox, branch="ralph/scratch")
        gate = feedback_fn_factory([sys.executable, "-m", "py_compile", valid_py])

        def stub_agent(memory, i):
            if i == 0:
                return AgentStep(candidates=[{
                    "task": "toy unit: scratch-branch commit",
                    "prd_ref": "TOY-2",
                    "files": ["toy.py"],
                    "size": 1,
                }])
            return AgentStep(text="done <promise>NO MORE TASKS</promise>")

        res = run_loop(max_iters=2, agent_fn=stub_agent, feedback_fn=gate,
                       commit_fn=commit_fn, memory_fn=lambda: [])
        check(res.status == STATUS_COMPLETE,
              "scratch-commit loop should COMPLETE, got %r (%s)" % (res.status, res.notes))
        check(len(res.commits) == 1,
              "scratch-commit loop should land exactly 1 commit, got %d" % len(res.commits))
        ok, cur = _git(["rev-parse", "--abbrev-ref", "HEAD"], sandbox)
        check(ok and cur.strip() == "ralph/scratch",
              "commit must land on the scratch branch, on %r" % cur.strip())
        ok, log = _git(["log", "--format=%s", "ralph/scratch"], sandbox)
        check(ok and "RALPH: toy unit: scratch-branch commit" in log,
              "scratch branch must contain the RALPH commit; log=%r" % log)
        print("SCRATCH-COMMIT COMPOSITION: ran -- commit landed on ralph/scratch")
    finally:
        shutil.rmtree(sandbox, ignore_errors=True)
        try:
            os.remove(valid_py)
        except OSError:
            pass


# ===========================================================================
# main
# ===========================================================================

def main() -> int:
    part1_executor_plus_real_gate()
    part2_orchestrate_run_and_shared_sentinels()
    part3_fork_distinct_key_invariant()
    part4_scratch_commit_composition()

    if _FAILURES:
        print("LOOP_STACK INTEGRATION TEST FAILURES (%d):" % len(_FAILURES))
        for f in _FAILURES:
            print("  - " + f)
        return 1
    print("ALL LOOP_STACK INTEGRATION TESTS PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
