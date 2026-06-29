#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""loop_bridge.py -- the orchestrate <-> ralph_adapters reconciliation seam.

The autonomous-loop stack ships TWO distinct loop drivers that the arch doc
(harness/knowledge/tech/autonomous-loop-stack-2026-06-29.md, section 1 "the
load-bearing boundary") records as SIBLINGS that share only one sentinel parser:

  - ralph_executor.run_loop : agent_fn(memory, iteration) -> AgentStep
        a memory/candidates/feedback-gate/commit loop; success fires ONLY on
        parse_promise(text) == NO_MORE_TASKS.
  - orchestrate.run         : agent_fn(prompt, iteration) -> str
        an IsolationStrategy + completion-sentinel loop returning a no-raise
        RunResult; success fires when Sentinels.parse(text) == the `completion`
        token (idiomatically COMPLETE).

This module is THIN PLUMBING. It imports all three modules and EDITS NONE of
them. It provides two adapters that reconcile the two drivers:

  as_run_agent(ralph_agent_fn)  -- wrap a (memory,i)->AgentStep agent so
        orchestrate.run() (which calls (prompt,i)->str) can drive it.
  as_ralph_agent(run_style_fn)  -- wrap a (prompt,i)->str agent so
        ralph_executor.run_loop() (which calls (memory,i)->AgentStep) can drive it.

WHAT IS RECONCILED (and what is NOT):
  Reconciled:
    (a) CALLING CONVENTION / SIGNATURE -- (memory,i)->AgentStep vs (prompt,i)->str,
        including return-shape (AgentStep vs raw str) and the prompt<->memory
        asymmetry (see below).
    (b) SUCCESS-TOKEN DIALECT -- Ralph speaks <promise>NO MORE TASKS</promise>;
        sandcastle/orchestrate speaks <promise>COMPLETE</promise>. The bridge
        translates a FOREIGN agent's success token into the HOST driver's NATIVE
        success token, because each driver terminates ONLY on its own token:
        run_loop has NO completion knob -- it fires success solely on
        parse_promise == NO_MORE_TASKS, so an orchestrate-native (COMPLETE) agent
        can NEVER terminate run_loop without translation.
  NOT reconciled (do not overclaim):
    - PER-ITERATION SEMANTICS. A ralph agent driven via orchestrate.run() bypasses
      run_loop's memory read / candidate selection / feedback gate / commit --
      orchestrate only watches sentinels (+ optional Output.object). A run-style
      fn driven via run_loop gives up IsolationStrategy / fork() / Output.object.
    - PROMPT vs MEMORY. orchestrate.run hands the agent a prompt STRING; the ralph
      contract has no prompt slot (context arrives as a MemoryEntry list). So
      as_run_agent DROPS orchestrate's prompt and sources the ralph agent's memory
      from an injected memory_fn; as_ralph_agent SYNTHESIZES a prompt from the
      memory list. Both asymmetries are explicit, not hidden.

SENTINEL DISCIPLINE (reuse, never redefine):
  - ABORT and HANG_ON are SHARED verbatim -- identical wire form, both parsers
    agree -- so they pass through UNTRANSLATED in both directions.
  - ABORT precedence is preserved: translation only acts on a verdict that is a
    SUCCESS token; ABORT outranks success in BOTH parsers, so a text carrying both
    COMPLETE and ABORT stays a hard stop.
  - Detection reuses ralph_executor.parse_promise and orchestrate.Sentinels.parse;
    no new sentinel constant or parser is defined here. Wire tokens are built from
    the existing constants (note: the verdict SYMBOL PROMISE_NO_MORE_TASKS is
    "NO_MORE_TASKS" with an underscore, but the WIRE form parse_promise matches is
    the SPACE form "NO MORE TASKS" -- mirrored via .replace("_", " "), the same
    convention ralph_adapters uses to build its ABORT sentinel).

Conventions: ASCII-only; '->' and '--' (no unicode). sys.path made robust so the
sibling imports resolve regardless of cwd.

Run: python loop_bridge.py     # offline self-test (mock agents), prints banner, exit 0/1
"""

from __future__ import annotations

import os
import sys
from typing import Callable, List, Optional

# -- robust sibling import (cwd resets between shell calls) -----------------
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

# Lane A: the pure Ralph driver + its sentinel parser + verdict constants.
from ralph_executor import (  # noqa: E402
    AgentStep,
    MemoryEntry,
    parse_promise,
    run_loop,
    PROMISE_ABORT,
    PROMISE_NO_MORE_TASKS,
    PROMISE_HANG_ON,
    STATUS_COMPLETE,
    STATUS_ABORTED,
    STATUS_EXHAUSTED,
)

# Lane C: the orchestration contract. Sentinels reuses parse_promise + layers
# COMPLETE; run/IsolationStrategy/RunResult are the host driver for direction 1.
from orchestrate import (  # noqa: E402
    Sentinels,
    IsolationStrategy,
    run as orchestrate_run,
    RunResult as OrchestrateRunResult,
    AgentFn as RunAgentFn,
)


# Type aliases for the two agent contracts the bridge reconciles.
RalphAgentFn = Callable[[List[MemoryEntry], int], AgentStep]


# ---------------------------------------------------------------------------
# Wire-form success tokens -- built from EXISTING constants, never hard-coded.
# ---------------------------------------------------------------------------
# parse_promise matches the SPACE form of the verdict symbol (its needle compacts
# whitespace but keeps underscores), so the underscore constant would NOT match.
# .replace("_", " ") yields the wire form both parsers recognize -- the same
# trick ralph_adapters uses for its ABORT sentinel.
_NMT_WIRE = "<promise>%s</promise>" % PROMISE_NO_MORE_TASKS.replace("_", " ")
_COMPLETE_WIRE = "<promise>%s</promise>" % Sentinels.COMPLETE


def _normalize_success(text: str, target_success: str) -> str:
    """PURE: ensure a SUCCESS outcome is expressed in the host driver's token.

    target_success is one of Sentinels.COMPLETE (orchestrate-native) or
    PROMISE_NO_MORE_TASKS (ralph-native). If the text's unified verdict is a
    SUCCESS token and the target token is not already detectable, append the
    target's wire form. ABORT / HANG_ON / no-sentinel texts are returned VERBATIM
    -- ABORT precedence (it is not a SUCCESS token) is thereby preserved, and a
    non-terminal HANG_ON turn never gets a spurious success marker.

    Detection uses the existing parsers only (Sentinels.parse composes
    parse_promise + COMPLETE); nothing is redefined.
    """
    verdict = Sentinels.parse(text)          # ABORT > COMPLETE/NMT > HANG_ON > None
    if verdict not in Sentinels.SUCCESS_TOKENS:
        return text                          # ABORT / HANG_ON / None: leave alone

    if target_success == Sentinels.COMPLETE:
        # Already carries COMPLETE? (COMPLETE outranks NMT in Sentinels.parse.)
        if verdict == Sentinels.COMPLETE:
            return text
        return text.rstrip() + " " + _COMPLETE_WIRE
    if target_success == PROMISE_NO_MORE_TASKS:
        # run_loop fires success only on parse_promise == NO_MORE_TASKS.
        if parse_promise(text) == PROMISE_NO_MORE_TASKS:
            return text
        return text.rstrip() + " " + _NMT_WIRE
    # Unknown target token -- do not invent semantics; pass through.
    return text


def _default_prompt_from_memory(memory: List[MemoryEntry], iteration: int) -> str:
    """Render the ralph MemoryEntry list into a prompt string for a run-style fn.

    This is the prompt<->memory bridge: run_loop has no prompt, so as_ralph_agent
    synthesizes one. Kept deliberately small (it is plumbing, not a prompt
    engineering surface -- callers can inject their own prompt_fn)."""
    header = "## Iteration %d\n## Recent RALPH memory\n" % iteration
    if not memory:
        return header + "(no prior RALPH commits)\nRespond now."
    lines = []
    for e in memory[:10]:
        bit = "- " + (getattr(e, "task", "") or "(untitled)")
        notes = getattr(e, "notes_for_next", "")
        if notes:
            bit += " | notes-for-next: " + notes
        lines.append(bit)
    return header + "\n".join(lines) + "\nRespond now."


# ---------------------------------------------------------------------------
# Direction 1: drive a RALPH-style agent THROUGH orchestrate.run()
# ---------------------------------------------------------------------------

def as_run_agent(ralph_agent_fn: RalphAgentFn,
                 memory_fn: Optional[Callable[[], List[MemoryEntry]]] = None,
                 target_success: str = Sentinels.COMPLETE) -> RunAgentFn:
    """Adapt a ralph-style (memory,i)->AgentStep agent into orchestrate's
    (prompt,i)->str AgentFn so orchestrate.run() can drive it.

    - SIGNATURE: orchestrate.run passes (prompt, iteration). The prompt has no
      home in the ralph contract, so it is DROPPED; the ralph agent's memory comes
      from `memory_fn` (default: empty list -- a stateless agent). The AgentStep's
      `.text` is returned (orchestrate watches text for sentinels); `.candidates`
      are discarded (orchestrate has no task-selection stage).
    - SUCCESS DIALECT: a ralph success (NO MORE TASKS) is normalized to
      `target_success` (default Sentinels.COMPLETE -- orchestrate's native token).
      CONTRACT: the caller MUST run with completion == target_success
      (e.g. orchestrate.run(..., completion=Sentinels.COMPLETE)), else the host
      watches a token the bridge never emits and the loop runs to max_iters.
    - ABORT / HANG_ON pass through verbatim (shared vocabulary).
    """
    mem = memory_fn or (lambda: [])

    def run_agent(prompt: str, iteration: int) -> str:  # noqa: ARG001 -- prompt dropped by design
        step = ralph_agent_fn(mem(), iteration)
        text = getattr(step, "text", "") or ""
        return _normalize_success(text, target_success)

    return run_agent


# ---------------------------------------------------------------------------
# Direction 2: drive an ORCHESTRATE-style agent THROUGH ralph_executor.run_loop
# ---------------------------------------------------------------------------

def as_ralph_agent(run_style_fn: RunAgentFn,
                   prompt_fn: Optional[Callable[[List[MemoryEntry], int], str]] = None,
                   candidates_fn: Optional[Callable[[str, List[MemoryEntry], int], List[dict]]] = None,
                   target_success: str = PROMISE_NO_MORE_TASKS) -> RalphAgentFn:
    """Adapt an orchestrate-style (prompt,i)->str agent into ralph's
    (memory,i)->AgentStep agent_fn so ralph_executor.run_loop() can drive it.

    - SIGNATURE: run_loop passes (memory, iteration). A prompt is SYNTHESIZED from
      the memory list via `prompt_fn` (default: a small memory renderer). The
      run-style fn's raw string becomes AgentStep.text.
    - SUCCESS DIALECT: a sandcastle success (COMPLETE) is normalized to
      `target_success` (default PROMISE_NO_MORE_TASKS -- ralph's native, and the
      ONLY token run_loop terminates-success on; run_loop has no completion knob).
    - CANDIDATES: run_loop selects the smallest candidate to feed the feedback
      gate + commit. A pure run-style fn proposes none, so `candidates_fn` is an
      optional hook to derive task dicts (default: none -> run_loop idles on
      non-terminal turns, which is correct for a sentinel-only agent).
    - ABORT / HANG_ON pass through verbatim (shared vocabulary).
    """
    pfn = prompt_fn or _default_prompt_from_memory

    def ralph_agent(memory: List[MemoryEntry], iteration: int) -> AgentStep:
        prompt = pfn(memory, iteration)
        raw = run_style_fn(prompt, iteration) or ""
        text = _normalize_success(raw, target_success)
        cands = candidates_fn(text, memory, iteration) if candidates_fn else []
        return AgentStep(text=text, candidates=cands or [])

    return ralph_agent


# ===========================================================================
# Self-test -- mock agents only; no live LLM, no git, no unsupervised run.
# Run: python loop_bridge.py
# ===========================================================================

def _selftest() -> int:
    failures: List[str] = []

    def check(cond: bool, msg: str) -> None:
        if not cond:
            failures.append(msg)

    # -- 0. sentinel discipline: REUSE, do not redefine ----------------------
    import ralph_executor as _re
    import orchestrate as _orc
    check(parse_promise is _re.parse_promise,
          "bridge must REUSE ralph_executor.parse_promise (identity)")
    check(Sentinels is _orc.Sentinels,
          "bridge must REUSE orchestrate.Sentinels (identity)")

    # Wire-form round-trip: the constructed tokens MUST be detected by the
    # parsers they target. (The underscore verdict symbol would NOT match.)
    check(parse_promise(_NMT_WIRE) == PROMISE_NO_MORE_TASKS,
          "NMT wire token %r must be detected as NO_MORE_TASKS by parse_promise" % _NMT_WIRE)
    check(Sentinels.parse(_COMPLETE_WIRE) == Sentinels.COMPLETE,
          "COMPLETE wire token %r must be detected as COMPLETE by Sentinels.parse" % _COMPLETE_WIRE)
    # Guard the underscore-vs-space trap explicitly.
    check(parse_promise("<promise>NO_MORE_TASKS</promise>") != PROMISE_NO_MORE_TASKS,
          "sanity: the underscore form is NOT the wire form parse_promise matches")

    # -- 1. REQUIRED: ralph agent driven THROUGH orchestrate.run() -> COMPLETE -
    def ralph_agent_complete(memory, i):
        check(isinstance(memory, list), "as_run_agent must hand the ralph agent a memory list")
        if i < 2:
            return AgentStep(candidates=[{"task": "unit", "size": 1}])  # no sentinel yet
        return AgentStep(text="all units landed <promise>NO MORE TASKS</promise>")

    wrapped_run = as_run_agent(ralph_agent_complete)          # target_success=COMPLETE
    res1 = orchestrate_run(wrapped_run, IsolationStrategy.HEAD, "drive ralph",
                           Sentinels.COMPLETE, max_iters=5)
    check(isinstance(res1, OrchestrateRunResult), "direction 1 must return an orchestrate RunResult")
    check(res1.completed is True, "ralph->run() should COMPLETE, got completed=%r" % res1.completed)
    check(res1.error is None, "clean ralph->run() should have error=None, got %r" % res1.error)
    check(len(res1.iterations) == 3, "ralph->run() should terminate on iter 2 (3 records), got %d"
          % len(res1.iterations))
    check(res1.iterations[-1].sentinel == Sentinels.COMPLETE,
          "ralph->run() terminal sentinel must be COMPLETE (translated from NO MORE TASKS)")
    check(res1.isolation_key == "head", "RunResult must be well-formed (isolation_key='head')")

    # -- 2. REQUIRED: run-style fn driven THROUGH run_loop -> NO MORE TASKS ----
    def run_style_complete(prompt, i):
        check(isinstance(prompt, str) and prompt, "as_ralph_agent must hand a prompt string")
        if i < 2:
            return "thinking, iteration %d" % i               # no sentinel yet
        return "finished the work <promise>COMPLETE</promise>"

    wrapped_ralph = as_ralph_agent(run_style_complete)        # target_success=NO_MORE_TASKS
    res2 = run_loop(5, wrapped_ralph, lambda task: True,
                    commit_fn=lambda m: True, memory_fn=lambda: [])
    check(res2.status == STATUS_COMPLETE,
          "run-style->run_loop should be STATUS_COMPLETE (translated from COMPLETE), got %r"
          % res2.status)
    check(res2.iterations == 3, "run-style->run_loop should take 3 iterations, got %d" % res2.iterations)

    # -- 3. SYMMETRY TABLE: sentinel semantics identical BOTH ways ------------
    # For each logical outcome, drive the SAME agent text through BOTH bridges and
    # assert the host driver reaches the equivalent terminal state.

    # 3a. SUCCESS (already covered by 1+2; assert the pairing explicitly).
    check(res1.completed and res2.status == STATUS_COMPLETE,
          "SUCCESS must terminate-success on BOTH drivers")

    # 3b. ABORT -- precedence preserved across translation (text carries BOTH
    #     COMPLETE and ABORT; ABORT must win and translation must NOT leak success).
    abort_text = "stop now <promise>COMPLETE</promise> <promise>ABORT</promise>"

    abort_ralph = as_run_agent(lambda mem, i: AgentStep(text=abort_text))
    res_abort_1 = orchestrate_run(abort_ralph, IsolationStrategy.HEAD, "x",
                                  Sentinels.COMPLETE, max_iters=3)
    check(res_abort_1.completed is False, "ABORT via direction 1 must NOT complete")
    check(res_abort_1.error is not None, "ABORT via direction 1 must populate error")
    check(res_abort_1.iterations[-1].sentinel == Sentinels.ABORT,
          "ABORT must win precedence over COMPLETE in direction 1")

    abort_run = as_ralph_agent(lambda prompt, i: abort_text)
    res_abort_2 = run_loop(3, abort_run, lambda task: True,
                           commit_fn=lambda m: True, memory_fn=lambda: [])
    check(res_abort_2.status == STATUS_ABORTED,
          "ABORT via direction 2 must yield STATUS_ABORTED, got %r" % res_abort_2.status)
    check(res_abort_2.iterations == 1, "ABORT must halt on iteration 1 in direction 2")

    # 3c. HANG_ON -- non-terminal both ways; then native success terminates.
    def hang_then_done_ralph(memory, i):
        if i == 0:
            return AgentStep(text="too big -- HANG ON A SECOND")
        return AgentStep(text="re-scoped done <promise>NO MORE TASKS</promise>")

    res_hang_1 = orchestrate_run(as_run_agent(hang_then_done_ralph),
                                 IsolationStrategy.HEAD, "x", Sentinels.COMPLETE, max_iters=5)
    check(res_hang_1.completed is True, "HANG_ON then success must COMPLETE in direction 1")
    check(res_hang_1.iterations[0].sentinel == Sentinels.HANG_ON,
          "HANG_ON must be a non-terminal continue in direction 1 (iter 0)")
    check(len(res_hang_1.iterations) == 2, "HANG_ON then success -> 2 iters in direction 1")

    def hang_then_done_run(prompt, i):
        if i == 0:
            return "too big -- HANG ON A SECOND"
        return "re-scoped done <promise>COMPLETE</promise>"

    res_hang_2 = run_loop(5, as_ralph_agent(hang_then_done_run), lambda task: True,
                          commit_fn=lambda m: True, memory_fn=lambda: [])
    check(res_hang_2.status == STATUS_COMPLETE, "HANG_ON then success must COMPLETE in direction 2")
    check(res_hang_2.self_interrupts == 1, "HANG_ON must self-interrupt once in direction 2")
    check(res_hang_2.iterations == 2, "HANG_ON then success -> 2 iters in direction 2")

    # 3d. NO sentinel ever -> host's exhaustion path, no false termination.
    res_exh_1 = orchestrate_run(as_run_agent(lambda mem, i: AgentStep(text="still working")),
                                IsolationStrategy.HEAD, "x", Sentinels.COMPLETE, max_iters=3)
    check(res_exh_1.completed is False, "no sentinel -> direction 1 must NOT complete")
    check(len(res_exh_1.iterations) == 3, "no sentinel -> direction 1 runs all max_iters")

    res_exh_2 = run_loop(3, as_ralph_agent(lambda prompt, i: "still working"),
                         lambda task: True, commit_fn=lambda m: True, memory_fn=lambda: [])
    check(res_exh_2.status == STATUS_EXHAUSTED, "no sentinel -> direction 2 must EXHAUST")
    check(res_exh_2.iterations == 3, "no sentinel -> direction 2 runs all max_iters")

    # -- 4. _normalize_success leaves shared / non-success tokens VERBATIM -----
    check(_normalize_success("nothing here", Sentinels.COMPLETE) == "nothing here",
          "no-sentinel text must be untouched")
    check(_normalize_success("wait HANG ON A SECOND", PROMISE_NO_MORE_TASKS) == "wait HANG ON A SECOND",
          "HANG_ON text must be untouched (non-terminal)")
    check(_normalize_success(abort_text, Sentinels.COMPLETE) == abort_text,
          "ABORT-bearing text must be untouched (precedence preserved)")
    # An already-native success token is not double-tagged.
    native_c = "done <promise>COMPLETE</promise>"
    check(_normalize_success(native_c, Sentinels.COMPLETE) == native_c,
          "already-COMPLETE text must not be re-tagged")

    # -- banner --------------------------------------------------------------
    if failures:
        print("=" * 60)
        print("loop_bridge.py SELF-TEST: FAIL (%d)" % len(failures))
        for f in failures:
            print("  -- " + f)
        print("=" * 60)
        return 1
    print("=" * 60)
    print("loop_bridge.py SELF-TEST: PASS (all assertions green)")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(_selftest())
