"""
ralph_executor.py -- Python port of the RALPH autonomous-Executor loop.

Ports the Ralph loop (afk.sh + prompt.md discipline) described in
harness/knowledge/tech/matt-pocock-ai-eng-roadmap-2026-06-29.md (Tier 1) into a
clean, testable Python ORCHESTRATION layer for the 3-agent harness
(Planner / Executor / Evaluator + MEMORY.md write-back).

WHAT RALPH IS:
  A stateless self-looping Executor whose only persistent state is git history.
  Each iteration:
    1. read MEMORY  -> the last N `RALPH:`-tagged commits (git log --grep=RALPH)
    2. read the PRD  -> break into the SMALLEST unit ("don't outrun our headlights")
    3. pick ONE task -> explore -> execute
    4. run feedback loops (test / typecheck) BEFORE committing
    5. commit with a structured `RALPH:` message
       (task, PRD ref, decisions, files, notes-for-next)
  Termination is signalled by sentinels emitted in the agent's output text:
    <promise>NO MORE TASKS</promise>   -> success, stop
    <promise>ABORT</promise>           -> failure, stop
    "HANG ON A SECOND"                 -> self-interrupt: task too big, re-scope,
                                          DO NOT commit, continue the loop

DESIGN (testability seam):
  The cwd is frequently NOT a git repo and the loop must run with no live LLM /
  Docker. So every impure edge is split from a pure core:
    - parse_ralph_log(text)            PURE  -- git-log body text -> [MemoryEntry]
    - memory_from_commits(n, repo)     IMPURE-- guarded `git log`, then parse
    - build_ralph_commit_message(...)  PURE  -- structured RALPH: message builder
    - default_commit_fn(msg, repo)     IMPURE-- guarded `git commit`
    - select_smallest_task(cands)      PURE  -- smallest-unit picker
    - parse_promise(text)              PURE  -- sentinel detection + precedence
    - run_loop(max_iters, agent_fn, feedback_fn, commit_fn, memory_fn)
                                       PURE driver; the impure edges are INJECTED.
  The builder and the parser share one invariant: the message MUST start with the
  `RALPH:` tag that `git log --grep=RALPH` selects on. The self-test round-trips
  builder -> parser to prove the tag survives.

LIVE-ADAPTER TODO (thin wiring, intentionally NOT built here):
  run_loop is driven by three injectable callables. A live run wires them to real
  infrastructure -- this is the only code that needs a real LLM / Docker / git:
    1. agent_fn(memory, iteration) -> AgentStep
         REAL: run Claude (claude -p / API) inside a Docker sandbox with the RALPH
         prompt.md, passing `memory` as context. Parse stream-json output via jq
         into AgentStep(text=<assistant text>, candidates=[<task dicts>]).
    2. feedback_fn(task) -> bool
         REAL: run the project feedback gate -- `pytest -q` / `rtk cargo test`
         / `rtk tsc` -- return True only on a clean exit code (gate BEFORE commit).
    3. commit_fn(message, repo) -> bool
         REAL: default_commit_fn already implements this (guarded `git commit`);
         swap in a sandbox-aware variant if committing inside the container.
  Everything above the adapters (memory parse, smallest-task, sentinels, gate
  ordering, retry/abort, termination) is exercised by the __main__ self-test
  with zero git / LLM / Docker.

USAGE:
  python ralph_executor.py            # runs the offline self-test, exits 0/1

NOTE: this module is ORCHESTRATION ONLY. It does not call an LLM. Wire the live
adapters (above) to make it autonomous.
"""

import sys
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional, Sequence

# ---------------------------------------------------------------------------
# Sentinels (ASCII only -- the <promise> tags are literal in the agent output)
# ---------------------------------------------------------------------------

PROMISE_NO_MORE_TASKS = "NO_MORE_TASKS"   # success: stop the loop
PROMISE_ABORT = "ABORT"                   # failure: stop the loop
PROMISE_HANG_ON = "HANG_ON"               # self-interrupt: re-scope, continue

# Run statuses
STATUS_COMPLETE = "complete"     # NO MORE TASKS sentinel reached
STATUS_ABORTED = "aborted"       # ABORT sentinel, or feedback-gate retries exhausted
STATUS_EXHAUSTED = "exhausted"   # max_iters hit with no terminal sentinel
STATUS_RUNNING = "running"       # initial / in-progress

RALPH_TAG = "RALPH:"             # commit-message tag; git log --grep=RALPH selects on it


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class MemoryEntry:
    """One parsed RALPH: commit -- the unit of persistent loop memory."""
    task: str = ""
    prd_ref: str = ""
    decisions: List[str] = field(default_factory=list)
    files: List[str] = field(default_factory=list)
    notes_for_next: str = ""
    raw: str = ""


@dataclass
class AgentStep:
    """One agent turn.

    text       : raw assistant output, scanned for <promise> sentinels.
    candidates : task dicts the agent proposes this iteration; the driver picks
                 ONE via select_smallest_task (the smallest-unit discipline).
                 A task dict uses keys: task, prd_ref, decisions, files,
                 notes_for_next, and (optional) size for the smallest-unit sort.
    """
    text: str = ""
    candidates: List[dict] = field(default_factory=list)


@dataclass
class RunResult:
    """Inspectable outcome of run_loop (sandcastle-style RunResult)."""
    status: str = STATUS_RUNNING
    iterations: int = 0
    commits: List[str] = field(default_factory=list)
    self_interrupts: int = 0
    gate_failures: int = 0
    last_memory: List[MemoryEntry] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Guarded subprocess edge (the only impure code; never raises into the driver)
# ---------------------------------------------------------------------------

def _run_git(args: Sequence[str], repo_dir: Optional[str] = None,
             timeout: int = 30) -> "tuple[bool, str]":
    """Run a git command, fully guarded. Returns (ok, stdout).

    Never raises: git absent (FileNotFoundError), non-zero exit, or timeout all
    collapse to (False, ""). This keeps the pure driver / parser unaffected by a
    severed checkout or a non-repo cwd.
    """
    try:
        proc = subprocess.run(
            ["git", *args],
            capture_output=True, text=True, timeout=timeout,
            cwd=str(repo_dir) if repo_dir else None,
        )
    except FileNotFoundError:
        return (False, "")          # git not installed / not on PATH
    except subprocess.TimeoutExpired:
        return (False, "")
    except OSError:
        return (False, "")
    if proc.returncode != 0:
        return (False, proc.stdout or "")
    return (True, proc.stdout or "")


# ---------------------------------------------------------------------------
# Memory: RALPH: commits as the persistent task DB
# ---------------------------------------------------------------------------

# Field labels used by BOTH the builder and the parser (round-trip invariant).
_LBL_PRD = "PRD:"
_LBL_DECISIONS = "Decisions:"
_LBL_FILES = "Files:"
_LBL_NOTES = "Notes-for-next:"

_DECISION_SEP = "; "
_FILE_SEP = ", "
# NUL separates commit bodies in the git-log format below; safe because commit
# message bodies cannot contain a NUL byte.
_BODY_SEP = "\x00"


def parse_ralph_log(text: str) -> List[MemoryEntry]:
    """PURE: parse `git log ... --format=%B%x00` output into MemoryEntry list.

    Bodies are NUL-separated. Any body that does not start with the RALPH: tag
    (after stripping) is skipped -- this is the same selection git --grep makes,
    re-asserted on the parsing side so a malformed body never becomes memory.
    """
    entries: List[MemoryEntry] = []
    if not text:
        return entries
    for body in text.split(_BODY_SEP):
        body = body.strip()
        if not body:
            continue
        entry = _parse_one_body(body)
        if entry is not None:
            entries.append(entry)
    return entries


def _parse_one_body(body: str) -> Optional[MemoryEntry]:
    """PURE: parse a single commit body. Returns None if it is not a RALPH commit."""
    lines = body.splitlines()
    # First non-empty line must carry the RALPH: tag.
    task = None
    rest_start = 0
    for i, line in enumerate(lines):
        s = line.strip()
        if not s:
            continue
        if s.startswith(RALPH_TAG):
            task = s[len(RALPH_TAG):].strip()
            rest_start = i + 1
        break
    if task is None:
        return None

    entry = MemoryEntry(task=task, raw=body)
    for line in lines[rest_start:]:
        s = line.strip()
        if s.startswith(_LBL_PRD):
            entry.prd_ref = s[len(_LBL_PRD):].strip()
        elif s.startswith(_LBL_DECISIONS):
            payload = s[len(_LBL_DECISIONS):].strip()
            entry.decisions = [d.strip() for d in payload.split(_DECISION_SEP) if d.strip()]
        elif s.startswith(_LBL_FILES):
            payload = s[len(_LBL_FILES):].strip()
            entry.files = [f.strip() for f in payload.split(_FILE_SEP) if f.strip()]
        elif s.startswith(_LBL_NOTES):
            entry.notes_for_next = s[len(_LBL_NOTES):].strip()
    return entry


def memory_from_commits(n: int = 10, repo_dir: Optional[str] = None) -> List[MemoryEntry]:
    """IMPURE: read the last N RALPH: commits as loop memory.

    Guarded -- if git is absent or the cwd is not a repo, returns [] so the loop
    simply starts from empty memory rather than crashing.
    """
    ok, out = _run_git(
        ["log", "--grep=%s" % RALPH_TAG.rstrip(":"), "-n", str(n), "--format=%B%x00"],
        repo_dir=repo_dir,
    )
    if not ok:
        return []
    return parse_ralph_log(out)


# ---------------------------------------------------------------------------
# Structured RALPH: commit-message builder (PURE; round-trips with the parser)
# ---------------------------------------------------------------------------

def build_ralph_commit_message(task: str,
                               prd_ref: str = "",
                               decisions: Optional[Sequence[str]] = None,
                               files: Optional[Sequence[str]] = None,
                               notes_for_next: str = "") -> str:
    """PURE: build a structured RALPH: commit message.

    The first line is `RALPH: <task>` so `git log --grep=RALPH` selects it and
    parse_ralph_log can read it back. Empty fields are omitted to keep messages
    tight, but the RALPH: subject line is always present.
    """
    decisions = list(decisions or [])
    files = list(files or [])
    subject = "%s %s" % (RALPH_TAG, (task or "").strip())
    lines = [subject.rstrip(), ""]
    if prd_ref:
        lines.append("%s %s" % (_LBL_PRD, prd_ref.strip()))
    if decisions:
        lines.append("%s %s" % (_LBL_DECISIONS, _DECISION_SEP.join(d.strip() for d in decisions)))
    if files:
        lines.append("%s %s" % (_LBL_FILES, _FILE_SEP.join(f.strip() for f in files)))
    if notes_for_next:
        lines.append("%s %s" % (_LBL_NOTES, notes_for_next.strip()))
    # Trailing newline-free; the commit tool adds its own framing.
    return "\n".join(lines).rstrip() + "\n"


def default_commit_fn(message: str, repo_dir: Optional[str] = None) -> bool:
    """IMPURE: guarded `git commit`. Returns True on success, False otherwise.

    This is the real commit edge wired into run_loop by default. The self-test
    injects a mock instead, so this never runs offline. --allow-empty is used so
    a RALPH iteration that only records a decision still lands a memory commit.
    """
    ok, _ = _run_git(["commit", "--allow-empty", "-m", message], repo_dir=repo_dir)
    return ok


# ---------------------------------------------------------------------------
# Smallest-unit task selection ("don't outrun our headlights")
# ---------------------------------------------------------------------------

def _task_size(candidate: dict) -> float:
    """PURE: ordering key -- smaller = pick first.

    Prefer an explicit numeric `size`; else fall back to the file count; else
    deprioritize (inf) so sized/scoped tasks win over unscoped ones.
    """
    size = candidate.get("size")
    if isinstance(size, (int, float)) and not isinstance(size, bool):
        return float(size)
    files = candidate.get("files")
    if files:
        return float(len(files))
    return float("inf")


def select_smallest_task(candidates: Sequence[dict]) -> Optional[dict]:
    """PURE: pick the SMALLEST candidate task (one task per iteration).

    Returns None when there are no candidates. `min` is stable, so ties keep the
    agent's emission order.
    """
    if not candidates:
        return None
    return min(candidates, key=_task_size)


# ---------------------------------------------------------------------------
# Sentinel / promise detection (PURE; precedence: ABORT wins on safety)
# ---------------------------------------------------------------------------

def parse_promise(text: str) -> Optional[str]:
    """PURE: detect a termination/self-interrupt sentinel in agent output.

    Returns one of PROMISE_ABORT / PROMISE_NO_MORE_TASKS / PROMISE_HANG_ON, or
    None. Precedence when multiple appear: ABORT > NO MORE TASKS > HANG ON A
    SECOND. ABORT wins on safety grounds -- a run that wants to stop hard should
    not be overridden by a stray success/continue marker.
    """
    if not text:
        return None
    # Precedence: ABORT > NO MORE TASKS > HANG ON A SECOND.
    if _has_promise(text, "ABORT"):
        return PROMISE_ABORT
    if _has_promise(text, "NO MORE TASKS"):
        return PROMISE_NO_MORE_TASKS
    if "HANG ON A SECOND" in text.upper():
        return PROMISE_HANG_ON
    return None


def _has_promise(text: str, token: str) -> bool:
    """PURE: True if <promise>TOKEN</promise> appears (whitespace/case tolerant)."""
    compact = "".join(text.split()).upper()
    needle = "<PROMISE>%s</PROMISE>" % "".join(token.split()).upper()
    return needle in compact


# ---------------------------------------------------------------------------
# The loop driver (PURE; impure edges are INJECTED)
# ---------------------------------------------------------------------------

def run_loop(max_iters: int,
             agent_fn: Callable[[List[MemoryEntry], int], AgentStep],
             feedback_fn: Callable[[dict], bool],
             commit_fn: Optional[Callable[[str], bool]] = None,
             memory_fn: Optional[Callable[[], List[MemoryEntry]]] = None,
             max_retries: int = 2) -> RunResult:
    """Drive the RALPH loop. Returns an inspectable RunResult.

    Contract:
      agent_fn(memory, iteration) -> AgentStep
      feedback_fn(task_dict)      -> bool   (test/typecheck gate; True == clean)
      commit_fn(message)          -> bool   (defaults to guarded git commit)
      memory_fn()                 -> [MemoryEntry] (defaults to git log --grep)

    Per-iteration order (RALPH discipline):
      read memory -> agent step -> check sentinels -> pick smallest task ->
      FEEDBACK GATE -> only on pass: build RALPH: message + commit.

    Feedback-gate failure policy (chosen + encoded, not implicit): the same task
    is retried on the next iteration up to `max_retries`; on exhaustion the run
    ABORTS. A failed gate NEVER commits. `max_iters` is a hard ceiling so the loop
    always terminates even if no sentinel is ever emitted (-> STATUS_EXHAUSTED).
    """
    if commit_fn is None:
        commit_fn = lambda msg: default_commit_fn(msg)
    if memory_fn is None:
        memory_fn = lambda: memory_from_commits(10)

    result = RunResult()
    retries = 0

    for i in range(max_iters):
        result.iterations += 1

        memory = memory_fn()
        result.last_memory = memory

        step = agent_fn(memory, i)
        text = getattr(step, "text", "") or ""

        promise = parse_promise(text)
        if promise == PROMISE_ABORT:
            result.status = STATUS_ABORTED
            result.notes.append("iter %d: <promise>ABORT</promise> -- halting" % i)
            return result
        if promise == PROMISE_NO_MORE_TASKS:
            result.status = STATUS_COMPLETE
            result.notes.append("iter %d: <promise>NO MORE TASKS</promise> -- done" % i)
            return result
        if promise == PROMISE_HANG_ON:
            # Self-interrupt: task too big. Re-scope next iteration; do not commit.
            result.self_interrupts += 1
            result.notes.append("iter %d: HANG ON A SECOND -- re-scoping, no commit" % i)
            continue

        # No terminal sentinel -> attempt one unit of work.
        candidates = getattr(step, "candidates", None) or []
        task = select_smallest_task(candidates)
        if task is None:
            result.notes.append("iter %d: no task and no sentinel -- idle" % i)
            continue

        # FEEDBACK GATE -- runs BEFORE any commit.
        gate_ok = bool(feedback_fn(task))
        if gate_ok:
            msg = build_ralph_commit_message(
                task=task.get("task", ""),
                prd_ref=task.get("prd_ref", ""),
                decisions=task.get("decisions"),
                files=task.get("files"),
                notes_for_next=task.get("notes_for_next", ""),
            )
            committed = bool(commit_fn(msg))
            if committed:
                result.commits.append(msg)
            else:
                result.notes.append("iter %d: gate passed but commit_fn failed" % i)
            retries = 0
        else:
            retries += 1
            result.gate_failures += 1
            result.notes.append(
                "iter %d: feedback gate FAILED (retry %d/%d) -- no commit"
                % (i, retries, max_retries)
            )
            if retries > max_retries:
                result.status = STATUS_ABORTED
                result.notes.append("feedback-gate retries exhausted -- abort")
                return result

    result.status = STATUS_EXHAUSTED
    result.notes.append("max_iters (%d) reached without a terminal sentinel" % max_iters)
    return result


# ===========================================================================
# Self-test -- offline, no git / LLM / Docker. Run: python ralph_executor.py
# ===========================================================================

def _selftest() -> int:
    failures: List[str] = []

    def check(cond: bool, label: str):
        if not cond:
            failures.append(label)

    # -- 1. Memory parsing + round-trip (builder -> parser invariant) ---------
    fields = dict(
        task="add guard to subprocess call",
        prd_ref="PRD-7",
        decisions=["return empty on FileNotFoundError", "collapse timeout to (False, '')"],
        files=["ralph_executor.py", "nightly_harness.py"],
        notes_for_next="wire real git commit in the live adapter",
    )
    msg_a = build_ralph_commit_message(**fields)
    msg_b = build_ralph_commit_message(task="second unit", prd_ref="PRD-8",
                                       files=["a.py"], notes_for_next="next")
    check(msg_a.startswith(RALPH_TAG + " "), "builder subject must start with 'RALPH:'")

    entries = parse_ralph_log(msg_a + _BODY_SEP + msg_b)
    check(len(entries) == 2, "parser should read 2 RALPH bodies, got %d" % len(entries))
    e0 = entries[0]
    check(e0.task == fields["task"], "round-trip task mismatch: %r" % e0.task)
    check(e0.prd_ref == fields["prd_ref"], "round-trip prd_ref mismatch: %r" % e0.prd_ref)
    check(e0.decisions == fields["decisions"], "round-trip decisions mismatch: %r" % e0.decisions)
    check(e0.files == fields["files"], "round-trip files mismatch: %r" % e0.files)
    check(e0.notes_for_next == fields["notes_for_next"], "round-trip notes mismatch: %r" % e0.notes_for_next)

    # Non-RALPH bodies are ignored (same selection git --grep makes).
    junk = parse_ralph_log("fix: not a ralph commit\n\nbody text" + _BODY_SEP + msg_b)
    check(len(junk) == 1, "parser must skip non-RALPH bodies, got %d" % len(junk))

    # -- 2. select_smallest_task picks the smallest unit ----------------------
    cands = [
        {"task": "big refactor", "size": 50, "files": ["a.py", "b.py", "c.py"]},
        {"task": "tiny guard", "size": 3, "files": ["ralph_executor.py"]},
        {"task": "medium", "size": 12},
    ]
    smallest = select_smallest_task(cands)
    check(smallest is not None and smallest["task"] == "tiny guard",
          "select_smallest_task should pick size=3, got %r" % (smallest,))
    check(select_smallest_task([]) is None, "select_smallest_task([]) should be None")
    # Fallback to file-count when size absent.
    nosize = select_smallest_task([
        {"task": "three files", "files": ["x", "y", "z"]},
        {"task": "one file", "files": ["x"]},
    ])
    check(nosize is not None and nosize["task"] == "one file",
          "smallest-by-filecount fallback failed: %r" % (nosize,))

    # -- 3. parse_promise sentinels + precedence ------------------------------
    check(parse_promise("done <promise>NO MORE TASKS</promise>") == PROMISE_NO_MORE_TASKS,
          "NO MORE TASKS not detected")
    check(parse_promise("fail <promise>ABORT</promise>") == PROMISE_ABORT,
          "ABORT not detected")
    check(parse_promise("this is too big, HANG ON A SECOND") == PROMISE_HANG_ON,
          "HANG ON A SECOND not detected")
    check(parse_promise("no sentinel here") is None, "false-positive sentinel")
    # Precedence: ABORT beats NO MORE TASKS when both appear.
    check(parse_promise("<promise>NO MORE TASKS</promise> <promise>ABORT</promise>") == PROMISE_ABORT,
          "ABORT must win precedence over NO MORE TASKS")
    # Whitespace/case tolerance.
    check(parse_promise("<PROMISE> no more tasks </PROMISE>") == PROMISE_NO_MORE_TASKS,
          "promise detection should be whitespace/case tolerant")

    # -- 4. run_loop terminates on NO MORE TASKS; commits the SMALLEST task ----
    committed: List[str] = []

    def mock_commit(msg: str) -> bool:
        committed.append(msg)
        return True

    def mock_memory() -> List[MemoryEntry]:
        # Memory parsing path exercised without git: feed a prior RALPH commit.
        return parse_ralph_log(msg_b)

    def mock_agent_complete(memory, i):
        check(isinstance(memory, list), "agent_fn must receive a memory list")
        if i == 0:
            return AgentStep(candidates=[
                {"task": "big refactor", "size": 50, "files": ["a.py", "b.py"]},
                {"task": "add guard", "size": 3, "prd_ref": "PRD-7",
                 "decisions": ["guard FileNotFoundError"], "files": ["ralph_executor.py"],
                 "notes_for_next": "wire live adapter"},
            ])
        return AgentStep(text="all units done. <promise>NO MORE TASKS</promise>")

    res = run_loop(10, mock_agent_complete, lambda task: True,
                   commit_fn=mock_commit, memory_fn=mock_memory)
    check(res.status == STATUS_COMPLETE, "loop should COMPLETE on sentinel, got %r" % res.status)
    check(len(res.commits) == 1, "exactly 1 commit expected, got %d" % len(res.commits))
    check(len(committed) == 1 and "add guard" in committed[0],
          "loop should commit the SMALLEST task (add guard)")
    check(res.last_memory and res.last_memory[0].task == "second unit",
          "memory_fn output should be threaded into RunResult.last_memory")

    # -- 5. commit message well-formed (round-trip the loop's own commit) -----
    parsed_back = parse_ralph_log(committed[0])
    check(len(parsed_back) == 1, "loop commit should parse as exactly 1 RALPH entry")
    pb = parsed_back[0]
    check(pb.task == "add guard" and pb.prd_ref == "PRD-7"
          and pb.files == ["ralph_executor.py"] and pb.notes_for_next == "wire live adapter",
          "loop commit message is not well-formed / does not round-trip: %r" % (pb,))

    # -- 6. ABORT halts immediately, no commits -------------------------------
    aborted_commits: List[str] = []

    def mock_agent_abort(memory, i):
        return AgentStep(text="cannot proceed <promise>ABORT</promise>")

    res_abort = run_loop(10, mock_agent_abort, lambda task: True,
                         commit_fn=lambda m: aborted_commits.append(m) or True,
                         memory_fn=lambda: [])
    check(res_abort.status == STATUS_ABORTED, "ABORT should yield STATUS_ABORTED, got %r" % res_abort.status)
    check(len(aborted_commits) == 0, "ABORT must not commit")
    check(res_abort.iterations == 1, "ABORT should halt on the first iteration")

    # -- 7. Failed feedback gate -> NO commit, retries then ABORT -------------
    gate_commits: List[str] = []

    def mock_agent_task_every_iter(memory, i):
        return AgentStep(candidates=[{"task": "flaky unit", "size": 1, "files": ["x.py"]}])

    res_gate = run_loop(10, mock_agent_task_every_iter, lambda task: False,
                        commit_fn=lambda m: gate_commits.append(m) or True,
                        memory_fn=lambda: [], max_retries=2)
    check(len(gate_commits) == 0, "failed feedback gate must NEVER commit")
    check(res_gate.status == STATUS_ABORTED, "exhausted gate retries should ABORT, got %r" % res_gate.status)
    check(res_gate.gate_failures == 3, "expected 3 gate failures (2 retries + 1), got %d" % res_gate.gate_failures)

    # -- 8. max_iters ceiling -> EXHAUSTED when no sentinel ever appears ------
    def mock_agent_idle(memory, i):
        return AgentStep(text="thinking...")  # no sentinel, no candidates

    res_exh = run_loop(4, mock_agent_idle, lambda task: True,
                       commit_fn=mock_commit, memory_fn=lambda: [])
    check(res_exh.status == STATUS_EXHAUSTED, "no sentinel should EXHAUST, got %r" % res_exh.status)
    check(res_exh.iterations == 4, "should run exactly max_iters=4, got %d" % res_exh.iterations)

    # -- 9. HANG ON A SECOND is non-terminal (re-scope, continue) -------------
    def make_hang_then_done():
        state = {"i": 0}
        def agent(memory, i):
            if i == 0:
                return AgentStep(text="this task is too big -- HANG ON A SECOND")
            return AgentStep(text="re-scoped done <promise>NO MORE TASKS</promise>")
        return agent

    res_hang = run_loop(10, make_hang_then_done(), lambda task: True,
                        commit_fn=mock_commit, memory_fn=lambda: [])
    check(res_hang.status == STATUS_COMPLETE, "HANG ON should not terminate the loop, got %r" % res_hang.status)
    check(res_hang.self_interrupts == 1, "expected 1 self-interrupt, got %d" % res_hang.self_interrupts)
    check(res_hang.iterations == 2, "HANG ON then sentinel should take 2 iterations, got %d" % res_hang.iterations)

    # -- report ---------------------------------------------------------------
    if failures:
        print("RALPH_EXECUTOR SELF-TEST FAILURES (%d):" % len(failures))
        for f in failures:
            print("  - " + f)
        return 1
    print("ALL RALPH_EXECUTOR TESTS PASS")
    return 0


if __name__ == "__main__":
    sys.exit(_selftest())
