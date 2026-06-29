---
title: "Evalite-shaped pytest eval harness -- data->task->scorers[] over the Monte Carlo sim + Anthropic LLM-judge"
status: "PROPOSED"
created: "2026-06-29"
updated: "2026-06-29"
project: "harness"
estimated_time: "DESIGN SPEC (no build). Build effort estimated per-stage inside; ~4-6h total, mostly additive (extends apl_judge)."
related_findings:
  - "harness/knowledge/tech/matt-pocock-ai-eng-roadmap-2026-06-29.md (evalite section, TIER 1)"
related_commits: []
supersedes: null
superseded_by: null
---

# Evalite-shaped pytest eval harness

> LANE C DESIGN SPEC. Spec-first; produces the harness skeleton, files-to-touch, gotchas, do/defer. NO code
> written here. Roadmap CONCRETE NEXT ACTION #4. It EXTENDS the existing `apl_judge.py` rather than
> replacing it -- the load-bearing mechanism is apl_judge's already-present `llm=` injection seam.

---

## 0. Pre-flight reads (MANDATORY before any build off this spec)

1. `harness/knowledge/tech/spec-authoring-lessons.md` -- Rule 5 (gates falsifiable) / Rule 9.
2. `harness/knowledge/tech/matt-pocock-ai-eng-roadmap-2026-06-29.md` -- evalite subsection (lines 32-38).
3. `harness/agents/scripts/apl_judge.py` -- THE thing being extended. Note especially:
   `grade_apl(..., llm=...)` injection seam (lines 386-455), `score_apl` mean-scoring (474-497),
   `JudgeGrade.to_dict()` (117-121), the hermetic self-test that monkeypatches the LLM (630-758).
4. `harness/specs/2026-06-28-llm-as-judge-impl-plan.md` + `harness/data/apl_judge_questions.json` +
   `apl_judge_calibration.json` -- the existing question/fixture shape (this is already evalite's `data`).
5. `mtg-sim/run_matchup.py` (`main`, the `result` dict with `g1`/`match`/`n`/`elapsed`) and
   `harness/agents/scripts/matchup_gauntlet.py` (`run_gauntlet`, `compute_field_wr`) -- the Monte Carlo sim
   the winrate scorer wraps.
6. `mtg-sim/tests/` + `mtg-sim/pyproject.toml` -- the EXISTING pytest infra (33 test files) that hosts this.
7. The orchestration-contract spec (`2026-06-29-harness-orchestration-contract.md`) -- the
   `AnthropicProvider` seam the LLM-judge scorer reuses.

---

## 1. Goal

Build an evalite-shaped pytest eval harness -- `data -> task -> scorers[]` -- that measures whether an agent
(an APL, an APL-generator, a mulligan policy) got BETTER, not just whether it ran. Ship two scorers: a
Monte-Carlo `winrate_over_N` scorer normalized to 0-1, and an Anthropic LLM-judge scorer that REUSES
`apl_judge` through its `llm=` seam. Capture each LLM call as a JSONL trace. Gate CI on `mean(score) >=
threshold`. One sentence: turn "does the sim run" into "did this change move the mean score above the bar,"
the hobbyist/engineer dividing line the roadmap names.

## 2. Scope

### In scope
- The evalite skeleton: `eval_case` (data row), `Scorer` protocol, an `evalite(name, data, task, scorers)`
  runner that drives pytest.
- `winrate_over_N` scorer: wraps the Monte Carlo sim, returns `{score: 0-1, metadata}`.
- `anthropic_judge` scorer: reuses `apl_judge.grade_apl` with an `AnthropicProvider`-backed `llm=` callable;
  PASS->1.0, FAIL->0.0, ERROR/INCONCLUSIVE -> excluded from denominator (apl_judge's existing rule).
- JSONL trace capture (one row per LLM/sim call).
- CI gate on `mean(score) >= threshold`, with the stochastic-stability rule (average + threshold the mean).

### Explicitly out of scope
- A web UI (evalite ships one; we use pytest output + the JSONL trace + an optional static HTML export -- HTML defer, Step 7).
- Replacing `apl_judge`'s CLI scorer -- the eval harness CALLS into apl_judge, does not fork it.
- The Monte Carlo engine itself (run_matchup/gauntlet already exist; the scorer is a thin wrapper).
- Langfuse / OpenTelemetry integration -- JSONL is the v1 trace surface (roadmap notes Langfuse as a radar tool, not a v1 dep).

## 3. The skeleton (design output)

### 3.1 `data -> task -> scorers[]`

```
# DESIGN ONLY
@dataclass
class EvalCase:
    input: dict          # e.g. {"our_deck": "boros_energy", "opp": "amulet_titan", "format": "modern"}
    expected: dict | None  # e.g. {"pt_truth_wr": 0.629} or a JudgeGrade-style expected

Scorer = Callable[[EvalCase, Any], ScoreResult]   # (case, task_output) -> {score: float 0..1, metadata}

@dataclass
class ScoreResult:
    score: float | None  # 0..1; None = excluded from the mean (ERROR/INCONCLUSIVE)
    metadata: dict

def evalite(name: str, *, data: list[EvalCase], task: Callable[[EvalCase], Any],
            scorers: list[Scorer], threshold: float, trace_path: str) -> EvalReport: ...
```

`task` runs the agent/sim for a case and returns its output; each scorer turns `(case, output)` into a 0-1
score. The runner is invoked from a pytest test so it plugs into the existing `mtg-sim/tests/` infra.

### 3.2 `winrate_over_N` -- the Monte Carlo sim as a 0-1 scorer

```
def winrate_over_N(case, task_output) -> ScoreResult:
    # task_output is the run_matchup result dict: {"g1":.., "match":.., "n":.., "seed":.., "elapsed":..}
    wr = task_output["match"] / 100.0            # run_matchup reports percent; normalize to 0..1
    return ScoreResult(score=wr, metadata={"n": task_output["n"], "g1": task_output["g1"]})
```

The `task` for a winrate eval calls the EXISTING sim (`run_matchup.main` args, or `matchup_gauntlet.run_gauntlet`)
at fixed `N`, `seed`. The scorer just normalizes `result["match"]` (a percent) to 0-1. **Stochastic-stability
rule (the load-bearing eval insight):** a single run is noisy; the eval AVERAGES the score across the data
set (or across seeds) and gates the MEAN, never an individual case. Larger `N` per case tightens variance;
the threshold has an acceptance BAND (Section 5).

### 3.3 `anthropic_judge` -- LLM-judge scorer reusing apl_judge (THE extends-apl_judge mechanism)

apl_judge is Ollama/gemma4 top to bottom (`call_llm` -> localhost:11434, `DEFAULT_MODEL="gemma4"`). The task
wants an *Anthropic* judge. The mechanism already exists: **`grade_apl(question, apl_path, *, llm=callable)`
takes an injectable LLM callable**; the self-test monkeypatches it (lines 665-698). So the Anthropic judge is
a NEW transport callable passed as `llm=` -- `build_prompt`, `parse_result`, `score_apl`, `JudgeGrade`,
`run_calibration` are ALL reused unchanged.

```
def make_anthropic_llm(model="claude-opus-4-8"):
    # returns a callable(prompt, model, num_ctx=...) -> str matching apl_judge's llm= contract.
    # Uses the Anthropic SDK: client.messages.create(model=..., thinking={"type":"adaptive"},
    #   output_config={"effort":"high"}, max_tokens=512, messages=[{"role":"user","content":prompt}])
    # returns the text block. (Adaptive thinking; budget_tokens is REMOVED on claude-opus-4-8 -> 400.)
    ...

def anthropic_judge(case, task_output) -> ScoreResult:
    grade = apl_judge.grade_apl(case.input["question"], case.input["apl_path"],
                                llm=make_anthropic_llm())
    if not grade.counts_for_score:          # ERROR / INCONCLUSIVE -> excluded
        return ScoreResult(score=None, metadata={"result": grade.result, "reason": grade.reason})
    return ScoreResult(score=1.0 if grade.is_pass else 0.0,
                       metadata=grade.to_dict())
```

Natural design (roadmap-aligned): gemma4 stays as a CHEAP local pre-filter (the existing apl_judge CLI),
Anthropic `claude-opus-4-8` is the AUTHORITATIVE scorer -- both are just different `llm=` callables. This
also lets the existing `run_calibration` (9/10 agreement gate) be re-run against the Anthropic judge to
validate it before trusting its scores.

### 3.4 Trace capture as JSONL

One row per call, appended to `trace_path`. **Reuse existing shapes, do not invent:** for judge calls reuse
`JudgeGrade.to_dict()`; for sim calls reuse the `run_matchup` result dict (`g1`/`match`/`n`/`seed`/`elapsed`).
Add only an envelope: `{ts, eval_name, case_id, scorer, score, ...payload}`. JSONL because it is append-only,
greppable by `rtk`, and diffable run-to-run.

### 3.5 CI gate on `mean(score) >= threshold`

The runner computes `mean` over cases with non-None scores, compares to `threshold`, returns exit 0/1
(mirrors apl_judge's CLI exit convention: 0 PASS / 1 FAIL / 2 ERROR). A GitHub Actions step (or the existing
nightly harness) calls the pytest target; failure of the mean gate fails the build. The MEAN is gated, not
any single case -- this is what makes a stochastic agent testable without flakiness.

## 4. Steps (design + first build slice)

1. **Write the skeleton module stub** `harness/agents/scripts/eval_harness.py` (EvalCase, Scorer, ScoreResult,
   `evalite()` signature, `mean`/threshold/exit logic) -- signatures + docstrings, NotImplementedError bodies. (~45 min)
2. **Write a pytest entry** `mtg-sim/tests/test_eval_harness.py` (or `harness/tests/`) that calls `evalite()`
   with a tiny 2-case data set and a mocked task -- proves the runner + mean gate + JSONL trace work hermetically
   (no Ollama, no Anthropic, no sim), mirroring apl_judge's hermetic self-test. (build -- ~45 min)
3. **Implement `winrate_over_N`** as a ~15-line wrapper over `run_matchup` result dicts. (build -- ~45 min)
4. **Implement `make_anthropic_llm` + `anthropic_judge`** -- the `llm=` callable + the scorer. Gate on the
   `anthropic` SDK being installed (see gotchas). (build -- ~1h)
5. **Re-run `apl_judge.run_calibration` with the Anthropic judge** to validate it agrees >=9/10 with the
   fixture expectations BEFORE trusting its scores in CI. (build -- ~30 min)
6. **Wire the CI gate**: a nightly-harness step (or GH Actions) invoking the pytest target; mean < threshold
   fails. (build -- ~45 min)

## 5. Validation gates (DESIGN-ACCEPTANCE, falsifiable)

| Gate | Acceptance | Stop trigger |
|---|---|---|
| 5.1 Shape | `data -> task -> scorers[]` expressible; both scorers conform to the `Scorer` protocol returning 0-1 (or None) | a scorer can't fit the protocol |
| 5.2 Reuse | `anthropic_judge` calls `apl_judge.grade_apl` UNCHANGED via `llm=`; zero edits to apl_judge's grading/parsing/scoring | any fork/copy of apl_judge logic |
| 5.3 Stochastic stability | the runner gates `mean(score)`, never a single case; winrate threshold has an acceptance BAND, and increasing N narrows the band | gate keys on one case -> flaky |
| 5.4 Judge calibration | the Anthropic judge passes the EXISTING `run_calibration` 9/10 agreement gate before its scores count in CI | <9/10 -> judge not trustworthy, do not gate CI on it |
| 5.5 Trace fidelity | JSONL rows reuse `JudgeGrade.to_dict()` / `run_matchup` result fields; one row per call; re-runnable diff | invented ad-hoc schema |
| 5.6 Exit convention | runner exit 0/1/2 matches apl_judge (PASS/FAIL/ERROR), so CI and nightly harness treat it uniformly | divergent exit semantics |

## 6. Stop conditions (teeth)

- If the `anthropic` SDK is unavailable at build time (confirmed absent 2026-06-29): STOP the Anthropic
  scorer half, ship the `winrate_over_N` scorer + the gemma4 judge (apl_judge as-is) under the evalite
  skeleton, open the SDK-install imperfection.
- If Gate 5.4 fails (Anthropic judge <9/10 on calibration): STOP gating CI on the judge score; keep it as a
  reported-but-non-blocking metric until the prompt/model pairing is tuned. Do NOT gate a build on an
  uncalibrated judge.
- If the winrate scorer's variance at the chosen N is wider than the threshold band (Gate 5.3): STOP, raise N
  or widen the band with a documented rationale; do not ship a gate that flips on noise.

## 7. Do / Defer

**DO now:** the skeleton (Step 1), the hermetic pytest entry (Step 2), `winrate_over_N` (Step 3). These are
pure-additive, need no external API, and immediately give a non-flaky "did the sim get better" gate.

**DEFER:**
- `anthropic_judge` (Steps 4-5) until the `anthropic` SDK lands AND the orchestration spec's
  `AnthropicProvider` exists (reuse it -- do not write a second SDK wrapper). Until then the gemma4 judge
  (existing apl_judge) is the LLM-judge scorer.
- Static HTML CI export (evalite ships one) -- JSONL + pytest output suffice for v1.
- Langfuse / OTel trace backends -- JSONL first; upgrade only if trace volume demands it.
- A web UI -- not needed; the value is the CI gate.

## 8. Annotated imperfections (to register on ship)

- `eval-harness-anthropic-sdk-not-installed` -- shared with the orchestration spec; `anthropic_judge` blocked
  until `pip install anthropic` + key. Effort 15 min + key.
- `eval-harness-winrate-variance-unbounded` -- the chosen N-per-case vs threshold-band tradeoff must be
  empirically set on first build (run the same case 5x at candidate N, measure spread, set band > spread).
  Concrete fix: a one-off variance probe before wiring the CI gate. Effort 30 min.

## 9. Gotchas (load-bearing)

1. **The "extends apl_judge" mechanism IS the `llm=` seam -- nothing else.** Do not fork apl_judge. The
   Anthropic judge is a callable passed to `grade_apl(..., llm=...)`; all of build_prompt / parse_result /
   score_apl / JudgeGrade / run_calibration are reused verbatim. A spec/build that copies apl_judge logic
   has missed the point (Gate 5.2).
2. **Stochastic -> average + threshold the MEAN.** A single Monte Carlo run is noisy. Gate `mean(score)`
   across the data set (or across seeds), with an acceptance band, never an individual case. This is the
   roadmap's explicit "non-flaky way to test stochastic agents."
3. **Anthropic model: `claude-opus-4-8`, adaptive thinking, NO `budget_tokens`.** `thinking={"type":
   "adaptive"}` (+ `output_config={"effort": ...}`); `budget_tokens`/`temperature`/`top_p` are REMOVED on
   claude-opus-4-8 and return 400. For structured judge output prefer `messages.parse` with a Pydantic model;
   for the simple PASS/FAIL contract, the existing `parse_result` regex over a text response is fine.
4. **`anthropic` SDK not installed; pydantic IS (2.13.4).** Skeleton + winrate scorer need no new dep; the
   Anthropic scorer does -- gate it (Stop condition 1).
5. **run_matchup reports PERCENT, not 0-1.** `result["match"]` is e.g. `80.0`, not `0.80`. Normalize (`/100`)
   in the scorer or every winrate score is 80x too big.
6. **ERROR/INCONCLUSIVE excluded from the denominator -- reuse `JudgeGrade.counts_for_score`.** apl_judge
   already gets this right (lines 113-115); the scorer must return `score=None` for those, and the mean must
   skip None, or a flaky judge transport silently tanks the mean.
7. **Host it in the EXISTING pytest infra.** `mtg-sim/tests/` already has 33 test files + a pyproject. Add the
   eval test there (or `harness/tests/`); do not stand up a parallel runner -- pytest IS our vitest analog.
8. **The injected `llm=` callable is called with `model="gemma4"`.** `grade_apl`/`run_calibration` invoke the
   injected callable as `fn(prompt, model, num_ctx=...)` where `model` defaults to `DEFAULT_MODEL="gemma4"`
   (apl_judge.py:443-448, 74). `make_anthropic_llm` MUST ignore that positional `model` and use the baked-in
   `claude-opus-4-8`, OR call `grade_apl(..., model="claude-opus-4-8", llm=...)` so the real id threads
   through. Otherwise the first Anthropic call goes out with `model="gemma4"` -> 404. One line; it is exactly
   the seam detail that "reuse apl_judge unchanged" hides.
9. **Adaptive thinking shares the output budget -- `max_tokens=512` can truncate the judge.** A truncated
   response loses the `RESULT:` line, and `parse_result` scores unparseable as FAIL (apl_judge.py:367-380) --
   silent false-negatives that drag the mean down and can trip Gate 5.4 / the CI gate. For the PASS/FAIL +
   one-sentence judge contract, default the Anthropic judge to `effort: "low"` (or thinking disabled) and/or
   raise `max_tokens`, so the answer contract always fits.

## Changelog
- 2026-06-29: Created (status PROPOSED). Lane C design spec; extends apl_judge via the llm= seam.
