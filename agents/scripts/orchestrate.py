#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""orchestrate.py -- the run() orchestration contract (lane C build slice).

Implements the sandcastle-derived orchestration vocabulary for the harness, per
harness/specs/2026-06-29-harness-orchestration-contract.md. This is the
ORCHESTRATION layer only: the agent is INJECTED (agent_fn), there is no live LLM
transport here. Providers (Ollama / Anthropic) are a separate, deferred slice.

Surface (exactly what this module owns):
  - IsolationStrategy        enum: HEAD | MERGE_TO_HEAD | BRANCH ("where it lands")
  - Sentinels                shared termination vocabulary; reuses
                             ralph_executor.parse_promise so lanes A and C share
                             ONE parser (<promise>COMPLETE</promise> terminal,
                             plus Ralph's NO MORE TASKS / ABORT).
  - IterationRecord          one agent turn, inspectable.
  - RunResult                neverthrow-style outcome: error is a FIELD, run()
                             does NOT raise across its boundary.
  - Output.object(...)       Pydantic typed extraction with retry-on-validation-fail
                             (re-prompt with the validation error appended).
  - run(...)                 the one inspectable entry point.
  - RunSpec / fork(...)      fan-out with the distinct-isolation-key INVARIANT
                             ENFORCED (fork RAISES on a key collision).

Conventions: ASCII-only; '->' and '--' (no unicode); sys.path made robust so the
ralph_executor import resolves regardless of cwd. Do NOT edit ralph_executor
(lane A owns it) -- import only.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, List, Optional, Type

# -- robust import of the lane-A Ralph sentinel parser ----------------------
# Make this script's own directory importable so `ralph_executor` resolves
# whether run from the repo root, the scripts dir, or a test harness.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

# REQUIRED reuse: import the lane-A pure sentinel parser. We do NOT reimplement
# it; we only layer COMPLETE detection on top so the two lanes share one parser.
from ralph_executor import (  # noqa: E402
    parse_promise,
    PROMISE_ABORT,
    PROMISE_NO_MORE_TASKS,
    PROMISE_HANG_ON,
)

from pydantic import BaseModel, ValidationError  # noqa: E402


# agent_fn is INJECTED. Contract: (prompt, iteration) -> raw assistant text.
AgentFn = Callable[[str, int], str]


# ---------------------------------------------------------------------------
# IsolationStrategy -- "where changes land", decoupled from "what the agent does"
# ---------------------------------------------------------------------------

class IsolationStrategy(Enum):
    """sandcastle's head / merge-to-head / branch, mapped onto harness reality.

    For us "isolation" is where an agent's OUTPUTS and CACHE KEYS land, not git
    branches per se:
      HEAD          -- no isolation; live workspace. UNSAFE for concurrent forks
                       (every HEAD run shares the one "head" key).
      MERGE_TO_HEAD -- scratch namespace, promoted on success. UNSAFE concurrently
                       (children share the one scratch key).
      BRANCH        -- named reusable isolation; the only concurrency-safe strategy,
                       provided each child gets a DISTINCT branch_name.
    """

    HEAD = "head"
    MERGE_TO_HEAD = "merge-to-head"
    BRANCH = "branch"


def isolation_key(isolation: IsolationStrategy, branch_name: Optional[str]) -> str:
    """Derive the isolation key that the distinct-key invariant is asserted on.

    HEAD          -> "head"            (one shared key -- collides if repeated)
    MERGE_TO_HEAD -> "merge-to-head"   (one shared scratch key -- collides if repeated)
    BRANCH        -> branch_name       (must be distinct per concurrent child)

    Raises ValueError if BRANCH is requested without a branch_name -- this is a
    caller precondition, not a provider failure, so it raises (fork() relies on
    this to fail fast before invoking any agent_fn).
    """
    if isolation is IsolationStrategy.BRANCH:
        if not branch_name:
            raise ValueError("IsolationStrategy.BRANCH requires a branch_name")
        return branch_name
    return isolation.value


# ---------------------------------------------------------------------------
# Sentinels -- shared termination vocabulary (reuses ralph_executor.parse_promise)
# ---------------------------------------------------------------------------

class Sentinels:
    """Normalized terminal/continue vocabulary shared with lane A (Ralph).

    Reuses ralph_executor.parse_promise for ABORT / NO_MORE_TASKS / HANG_ON and
    layers sandcastle's COMPLETE on top so the harness has ONE parser. The
    sentinel is a PARAMETER to run() -- never hard-coded -- but COMPLETE is the
    default success token.

    Success-class tokens: COMPLETE, NO_MORE_TASKS. Terminal-fail: ABORT.
    Continue (self-interrupt, non-terminal): HANG_ON.
    """

    COMPLETE = "COMPLETE"                    # sandcastle terminal success
    NO_MORE_TASKS = PROMISE_NO_MORE_TASKS    # Ralph terminal success
    ABORT = PROMISE_ABORT                    # terminal failure (wins on safety)
    HANG_ON = PROMISE_HANG_ON                # self-interrupt; loop continues

    SUCCESS_TOKENS = frozenset({COMPLETE, NO_MORE_TASKS})

    @staticmethod
    def _has_promise(text: str, token: str) -> bool:
        """PURE: True if <promise>TOKEN</promise> appears (whitespace/case tolerant).

        Mirrors ralph_executor._has_promise's compaction so COMPLETE detection is
        identical in tolerance to the Ralph sentinels, WITHOUT importing a private
        lane-A symbol.
        """
        if not text:
            return False
        compact = "".join(text.split()).upper()
        needle = "<PROMISE>%s</PROMISE>" % "".join(token.split()).upper()
        return needle in compact

    @classmethod
    def parse(cls, text: str) -> Optional[str]:
        """Detect a sentinel. Precedence: ABORT > COMPLETE/NO_MORE_TASKS > HANG_ON.

        ABORT wins on safety (a hard stop must not be overridden by a stray
        success marker), matching parse_promise's own precedence.
        """
        if not text:
            return None
        promise = parse_promise(text)            # ABORT/NO_MORE_TASKS/HANG_ON/None
        if promise == PROMISE_ABORT:
            return cls.ABORT
        if cls._has_promise(text, "COMPLETE"):
            return cls.COMPLETE
        if promise == PROMISE_NO_MORE_TASKS:
            return cls.NO_MORE_TASKS
        if promise == PROMISE_HANG_ON:
            return cls.HANG_ON
        return None


# ---------------------------------------------------------------------------
# Inspectable result shapes (neverthrow-style: error is a FIELD, not an exception)
# ---------------------------------------------------------------------------

@dataclass
class IterationRecord:
    """One agent turn within a run()."""
    iteration: int
    prompt: str
    raw_output: str
    sentinel: Optional[str] = None        # Sentinels.* token detected, if any
    parsed: Optional[BaseModel] = None    # Output.object result this turn, if any


@dataclass
class RunResult:
    """Inspectable outcome of run(). run() NEVER raises across this boundary;
    provider/tool failures surface here as `error` (Gate 5.5)."""
    iterations: List[IterationRecord] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)
    isolation_key: str = "head"
    completed: bool = False                # did a SUCCESS sentinel fire?
    object: Optional[BaseModel] = None     # validated Output.object result, if any
    error: Optional[str] = None            # explicit failure; no raise


# ---------------------------------------------------------------------------
# Output.object -- Pydantic typed extraction with retry-on-validation-fail
# ---------------------------------------------------------------------------

def _extract_json(raw: str) -> str:
    """Pull the first {...} JSON object out of agent prose. Best-effort: if no
    braces are present, return the raw text and let validation report the error."""
    if not raw:
        return raw
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end < start:
        return raw
    return raw[start:end + 1]


class Output:
    """sandcastle's Output.object, in Python.

    object(agent_fn, prompt, schema, max_retries) calls the INJECTED agent_fn,
    validates its output against a Pydantic model, and on ValidationError
    re-prompts the SAME agent_fn with the validation error appended (the
    retry-with-error-feedback loop). Returns (model | None, error | None) -- it
    does not raise.

    This VALIDATION retry is distinct from any transport-level retry a real
    provider would do (empty/timeout); they stack, they are not the same loop.
    """

    @staticmethod
    def object(
        agent_fn: AgentFn,
        prompt: str,
        schema: Type[BaseModel],
        max_retries: int = 2,
    ) -> "tuple[Optional[BaseModel], Optional[str]]":
        last_error: Optional[str] = None
        cur_prompt = prompt
        # attempt 0 is the first try; up to max_retries additional re-prompts.
        for attempt in range(max_retries + 1):
            try:
                raw = agent_fn(cur_prompt, attempt)
            except Exception as exc:  # provider blew up -- surface, do not raise
                return None, "agent_fn raised on attempt %d: %s" % (attempt, exc)
            try:
                model = schema.model_validate_json(_extract_json(raw))
                return model, None
            except (ValidationError, ValueError) as exc:
                last_error = str(exc)
                cur_prompt = (
                    prompt
                    + "\n\n-- Your previous output FAILED validation: --\n"
                    + last_error
                    + "\n-- Return ONLY valid JSON matching the schema. --"
                )
        return None, "validation failed after %d attempt(s): %s" % (
            max_retries + 1, last_error)


# ---------------------------------------------------------------------------
# run() -- the one inspectable entry point
# ---------------------------------------------------------------------------

def run(
    agent_fn: AgentFn,
    isolation: IsolationStrategy,
    prompt: str,
    completion: str,
    max_iters: int,
    output_schema: Optional[Type[BaseModel]] = None,
    # branch_name is the one deliberate extension to the literal lane signature:
    # BRANCH isolation needs a name (spec RunOptions.branch_name). It is a trailing
    # optional kwarg so every listed positional param stays identical.
    branch_name: Optional[str] = None,
) -> RunResult:
    """Loop the injected agent_fn until a SUCCESS sentinel fires or max_iters.

    completion is the success-sentinel token to watch for (e.g. Sentinels.COMPLETE
    or Sentinels.NO_MORE_TASKS) -- NOT hard-coded. ABORT terminates as a failure.
    If output_schema is supplied, each iteration also runs Output.object and the
    last validated object lands on RunResult.object.

    NEVER raises: a bad isolation config, an agent_fn exception, or a validation
    failure all surface as RunResult.error.
    """
    result = RunResult()
    # Derive the isolation key first; a BRANCH-without-name is a config error and
    # surfaces as RunResult.error here (run() is no-raise; fork() raises instead).
    try:
        result.isolation_key = isolation_key(isolation, branch_name)
    except ValueError as exc:
        result.error = str(exc)
        return result

    for i in range(max_iters):
        try:
            raw = agent_fn(prompt, i)
        except Exception as exc:  # no-raise boundary (Gate 5.5)
            result.error = "agent_fn raised on iteration %d: %s" % (i, exc)
            return result

        record = IterationRecord(iteration=i, prompt=prompt, raw_output=raw)

        if output_schema is not None:
            obj, obj_err = Output.object(agent_fn, prompt, output_schema)
            if obj is not None:
                record.parsed = obj
                result.object = obj
            elif obj_err is not None:
                # record but keep looping -- extraction may succeed a later turn
                result.error = obj_err

        sentinel = Sentinels.parse(raw)
        record.sentinel = sentinel
        result.iterations.append(record)

        if sentinel == Sentinels.ABORT:
            result.completed = False
            result.error = result.error or "iter %d: <promise>ABORT</promise>" % i
            return result
        if sentinel in Sentinels.SUCCESS_TOKENS and sentinel == completion:
            result.completed = True
            # a clean success clears a transient extraction error from earlier turns
            if result.object is not None or output_schema is None:
                result.error = None
            return result
        # HANG_ON / None -> keep looping

    # max_iters exhausted with no terminal success sentinel
    result.completed = False
    return result


# ---------------------------------------------------------------------------
# fork() -- fan-out with the distinct-isolation-key INVARIANT (RAISES on collision)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RunSpec:
    """One child run for fork(). Bundles the run() arguments."""
    agent_fn: AgentFn
    isolation: IsolationStrategy
    prompt: str
    completion: str
    max_iters: int
    output_schema: Optional[Type[BaseModel]] = None
    branch_name: Optional[str] = None

    def key(self) -> str:
        return isolation_key(self.isolation, self.branch_name)


def fork(children: List[RunSpec]) -> List[RunResult]:
    """Fan out N child runs. ENFORCES the distinct-isolation-key invariant.

    INVARIANT (verbatim in spirit from sandcastle): concurrent forks REQUIRE
    distinct isolation keys. HEAD and MERGE_TO_HEAD are UNSAFE concurrently (they
    collide on the live workspace / shared scratch namespace -- every such child
    yields the same key). Only BRANCH children with DISTINCT branch_name are safe.

    Keys are checked FIRST (fail fast on caller misuse) -- this RAISES a ValueError
    on any collision BEFORE invoking any agent_fn. This is distinct from run()'s
    no-raise provider boundary: a key collision is caller misuse, not a runtime
    failure, so it is loud.
    """
    seen: dict[str, int] = {}
    for idx, child in enumerate(children):
        key = child.key()  # may raise for BRANCH-without-name (precondition)
        if key in seen:
            raise ValueError(
                "fork() distinct-isolation-key invariant violated: child %d and "
                "child %d both map to isolation key %r (isolation=%s). Concurrent "
                "forks REQUIRE distinct keys; use BRANCH with a distinct branch_name."
                % (seen[key], idx, key, child.isolation.value)
            )
        seen[key] = idx

    # Keys are distinct -- safe to run each child.
    return [
        run(
            c.agent_fn, c.isolation, c.prompt, c.completion, c.max_iters,
            output_schema=c.output_schema, branch_name=c.branch_name,
        )
        for c in children
    ]


# ===========================================================================
# Self-test (mock agent_fn; no live LLM). Run directly: python orchestrate.py
# ===========================================================================

def _selftest() -> int:
    failures: List[str] = []

    def check(cond: bool, msg: str) -> None:
        if not cond:
            failures.append(msg)

    # -- 1. completion sentinel terminates -----------------------------------
    def agent_completes(prompt: str, i: int) -> str:
        if i < 2:
            return "working on it, iteration %d" % i
        return "all done here <promise>COMPLETE</promise>"

    res = run(agent_completes, IsolationStrategy.HEAD, "do the thing",
              Sentinels.COMPLETE, max_iters=10)
    check(res.completed is True, "completion sentinel should set completed=True")
    check(res.error is None, "clean completion should have error=None, got %r" % res.error)
    check(len(res.iterations) == 3, "should terminate on iter 2 (3 records), got %d"
          % len(res.iterations))
    check(res.iterations[-1].sentinel == Sentinels.COMPLETE,
          "last iteration sentinel should be COMPLETE")
    check(res.isolation_key == "head", "HEAD isolation_key should be 'head'")

    # max_iters exhaustion without a sentinel -> completed False, no raise
    res_exhaust = run(lambda p, i: "still going", IsolationStrategy.HEAD,
                      "loop", Sentinels.COMPLETE, max_iters=3)
    check(res_exhaust.completed is False, "exhaustion should yield completed=False")
    check(len(res_exhaust.iterations) == 3, "exhaustion should record max_iters turns")

    # ABORT terminates as failure
    res_abort = run(lambda p, i: "cannot proceed <promise>ABORT</promise>",
                    IsolationStrategy.HEAD, "x", Sentinels.COMPLETE, max_iters=5)
    check(res_abort.completed is False, "ABORT should yield completed=False")
    check(res_abort.error is not None, "ABORT should populate error")
    check(len(res_abort.iterations) == 1, "ABORT should halt on first iteration")

    # -- 2. fork distinct-key invariant: RAISES on collision -----------------
    spec_head_a = RunSpec(lambda p, i: "<promise>COMPLETE</promise>",
                          IsolationStrategy.HEAD, "a", Sentinels.COMPLETE, 1)
    spec_head_b = RunSpec(lambda p, i: "<promise>COMPLETE</promise>",
                          IsolationStrategy.HEAD, "b", Sentinels.COMPLETE, 1)
    raised = False
    try:
        fork([spec_head_a, spec_head_b])  # two HEAD children -> same key "head"
    except ValueError:
        raised = True
    check(raised, "fork() must RAISE on a distinct-key collision (two HEAD children)")

    # merge-to-head collision too
    raised_mth = False
    try:
        fork([
            RunSpec(lambda p, i: "x", IsolationStrategy.MERGE_TO_HEAD, "a", Sentinels.COMPLETE, 1),
            RunSpec(lambda p, i: "x", IsolationStrategy.MERGE_TO_HEAD, "b", Sentinels.COMPLETE, 1),
        ])
    except ValueError:
        raised_mth = True
    check(raised_mth, "fork() must RAISE on two MERGE_TO_HEAD children (shared scratch key)")

    # same branch_name collision
    raised_branch = False
    try:
        fork([
            RunSpec(lambda p, i: "<promise>COMPLETE</promise>",
                    IsolationStrategy.BRANCH, "a", Sentinels.COMPLETE, 1, branch_name="cand-1"),
            RunSpec(lambda p, i: "<promise>COMPLETE</promise>",
                    IsolationStrategy.BRANCH, "b", Sentinels.COMPLETE, 1, branch_name="cand-1"),
        ])
    except ValueError:
        raised_branch = True
    check(raised_branch, "fork() must RAISE on two BRANCH children sharing branch_name")

    # -- 2b. fork invariant NEGATIVE direction: distinct branches do NOT raise -
    forked = fork([
        RunSpec(lambda p, i: "done <promise>COMPLETE</promise>",
                IsolationStrategy.BRANCH, "a", Sentinels.COMPLETE, 2, branch_name="cand-1"),
        RunSpec(lambda p, i: "done <promise>COMPLETE</promise>",
                IsolationStrategy.BRANCH, "b", Sentinels.COMPLETE, 2, branch_name="cand-2"),
    ])
    check(len(forked) == 2, "fork() with distinct branches should return 2 RunResults")
    check(all(r.completed for r in forked),
          "both distinct-branch children should complete")
    check([r.isolation_key for r in forked] == ["cand-1", "cand-2"],
          "distinct-branch children should carry their distinct isolation keys")

    # -- 3. Pydantic extraction retries then succeeds ------------------------
    class Plan(BaseModel):
        steps: int
        name: str

    calls = {"n": 0}

    def flaky_agent(prompt: str, i: int) -> str:
        # first attempt: invalid (missing 'name'); retry: valid JSON
        calls["n"] += 1
        if calls["n"] == 1:
            return "here you go: {\"steps\": 3}"
        return "fixed: {\"steps\": 3, \"name\": \"build\"} ok"

    obj, err = Output.object(flaky_agent, "make a plan", Plan, max_retries=2)
    check(err is None, "Output.object should succeed after retry, got error %r" % err)
    check(obj is not None and obj.steps == 3 and obj.name == "build",
          "Output.object should return the validated model")
    check(calls["n"] == 2, "Output.object should have re-prompted exactly once (2 calls)")

    # validation exhaustion -> error, no raise
    obj_fail, err_fail = Output.object(lambda p, i: "{\"steps\": 1}",
                                       "x", Plan, max_retries=1)
    check(obj_fail is None and err_fail is not None,
          "Output.object should return (None, error) on exhausted retries")

    # run() threading a schema: object lands on RunResult.object
    def agent_with_schema(prompt: str, i: int) -> str:
        return "{\"steps\": 5, \"name\": \"go\"} <promise>COMPLETE</promise>"

    res_obj = run(agent_with_schema, IsolationStrategy.MERGE_TO_HEAD, "p",
                  Sentinels.COMPLETE, max_iters=3, output_schema=Plan)
    check(res_obj.completed is True, "schema run should complete")
    check(res_obj.object is not None and res_obj.object.steps == 5,
          "run() should land the validated object on RunResult.object")
    check(res_obj.isolation_key == "merge-to-head",
          "MERGE_TO_HEAD isolation_key should be 'merge-to-head'")

    # -- 4. no-raise boundary: agent_fn throws -> RunResult.error ------------
    def exploding_agent(prompt: str, i: int) -> str:
        raise RuntimeError("provider exploded")

    res_err = run(exploding_agent, IsolationStrategy.HEAD, "x",
                  Sentinels.COMPLETE, max_iters=3)
    check(res_err.error is not None, "agent_fn exception must surface as RunResult.error")
    check(res_err.completed is False, "exploded run should not be completed")
    check(isinstance(res_err, RunResult), "no exception should escape run()")

    # BRANCH without a name in run() -> error (no raise); in fork() -> raise
    res_noname = run(lambda p, i: "x", IsolationStrategy.BRANCH, "p",
                     Sentinels.COMPLETE, max_iters=1)
    check(res_noname.error is not None and not res_noname.completed,
          "run() BRANCH without branch_name should surface error, not raise")

    raised_noname = False
    try:
        fork([RunSpec(lambda p, i: "x", IsolationStrategy.BRANCH, "p", Sentinels.COMPLETE, 1)])
    except ValueError:
        raised_noname = True
    check(raised_noname, "fork() BRANCH without branch_name should raise (precondition)")

    # -- 5. RunResult well-formedness ----------------------------------------
    check(isinstance(res.iterations, list) and isinstance(res.outputs, list),
          "RunResult.iterations and .outputs must be lists")
    check(isinstance(res.iterations[0], IterationRecord),
          "RunResult.iterations entries must be IterationRecord")

    # -- 6. Sentinels reuse parse_promise + COMPLETE layering ----------------
    check(Sentinels.parse("x <promise>NO MORE TASKS</promise>") == Sentinels.NO_MORE_TASKS,
          "Sentinels must reuse parse_promise for NO MORE TASKS")
    check(Sentinels.parse("x <promise>ABORT</promise>") == Sentinels.ABORT,
          "Sentinels must detect ABORT")
    check(Sentinels.parse("done <promise>COMPLETE</promise>") == Sentinels.COMPLETE,
          "Sentinels must detect COMPLETE")
    # ABORT precedence over COMPLETE (safety)
    check(Sentinels.parse("<promise>COMPLETE</promise> <promise>ABORT</promise>") == Sentinels.ABORT,
          "ABORT must win precedence over COMPLETE")
    check(Sentinels.parse("nothing here") is None, "no false-positive sentinel")

    # -- banner --------------------------------------------------------------
    if failures:
        print("=" * 60)
        print("orchestrate.py SELF-TEST: FAIL (%d)" % len(failures))
        for f in failures:
            print("  -- " + f)
        print("=" * 60)
        return 1
    print("=" * 60)
    print("orchestrate.py SELF-TEST: PASS (all assertions green)")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(_selftest())
