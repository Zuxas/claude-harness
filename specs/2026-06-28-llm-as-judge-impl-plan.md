---
title: "Impl Plan: LLM-as-Judge APL Evaluation (apl_judge.py + 30Q set)"
status: SHIPPED
created: 2026-06-28
updated: 2026-06-28
project: mtg-sim
scopes_spec: harness/specs/2026-04-30-llm-as-judge-apl-evaluation.md
imperfection: no-llm-as-judge-apl-evaluation (IMPERFECTIONS.md:378)
estimated_time: 3-4 hours (spec's 90-120 min is optimistic; see Effort)
related_reads:
  - harness/scripts/verify_oracle.py            # canonical template to mirror
  - harness/agents/scripts/auto_pipeline.py     # streaming Ollama + model pick
  - mtg-sim/engine/card_db.py                   # oracle/type accessors
  - mtg-sim/scripts/arl_loop.py                 # future ARL integration point
  - mtg-sim/scripts/arl_profile.py              # deterministic gate (sibling gate)
---

# Implementation Plan: LLM-as-Judge APL Evaluation

This plan operationalizes `harness/specs/2026-04-30-llm-as-judge-apl-evaluation.md`.
It is grounded in the real code: `verify_oracle.py` is the near-exact template,
`auto_pipeline.py` supplies the resilient Ollama transport, and `CardDB` supplies
oracle text. **All new files live under `harness/` — nothing under
`E:/vscode ai project/mtg-sim/` is edited (READ-ONLY; a concurrent workflow is
writing there).**

---

## Goal

Build a standalone LLM-as-judge scorer (`harness/scripts/apl_judge.py`) plus a
30-question ground-truth set that grades APL *decision quality* (oracle fidelity,
strategic choices, keep/mulligan) independently of gauntlet WR%. WR proves code
runs; the judge catches oracle-incorrect or strategically-wrong decisions that
WR can't see.

---

## Files to create (all NEW, all under harness/)

1. `harness/scripts/apl_judge.py` — the scorer (mirrors `verify_oracle.py`).
2. `harness/data/apl_judge_questions.json` — the 30-question set.
   **`harness/data/` does not exist yet — create the directory** (verified:
   `ls harness/data` → "NO harness/data dir").
3. `harness/data/apl_judge_calibration.json` — 10 self-contained calibration
   fixtures (5 known-correct + 5 known-incorrect) with embedded code snippets.

No edits to any existing file. The IMPERFECTIONS entry update and `_index.md`
status flip happen at ship time (per Rule 8) but are out of this plan's code scope.

---

## Approach

### A. Reuse, don't reinvent — `verify_oracle.py` is the template

`harness/scripts/apl_judge.py` lives in the **same directory** as
`verify_oracle.py`, so:

- **Import its helpers directly**: `from verify_oracle import grep_apl_context,
  get_oracle_text, extract_card_constants`. These are import-safe (no top-level
  side effects beyond `sys.path.insert`). `grep_apl_context(apl_path, term,
  context_lines=25)` (verify_oracle.py:40) already builds contiguous
  numbered-line blocks around every mention of a term — exactly the "RELEVANT APL
  CODE" the judge prompt needs.
- **SIM_ROOT / path resolution**: copy verify_oracle.py:25-26
  (`SIM_ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "mtg-sim")`,
  `sys.path.insert(0, SIM_ROOT)`). The spec's CLI passes APL paths relative to
  mtg-sim (`--apl apl/jeskai_blink_match.py`); resolve them against SIM_ROOT.
- **Oracle text**: prefer `CardDB().oracle_text(name)` (engine/card_db.py:148,
  returns `str`) over verify_oracle's `db.get(name).get("oracle_text")`. Both
  work (`get()` returns `Optional[dict]`, card_db.py:135), but the accessor is
  the canonical API used by arl_profile.py and won't `AttributeError` on a miss.

### B. Transport — gemma4, streaming + retry (NOT verify_oracle's stream=False)

- **Model default `--model gemma4`.** The spec says "Gemma 12B"; the real Ollama
  tag in this repo is **`gemma4`** (used by verify_oracle.py:88 and
  auto_pipeline `draft_playbook`). gemma4 is the reasoning model — correct for a
  judge. Do NOT use `qwen2.5-coder` (that's the code-*generation* preference,
  auto_pipeline.py:740).
- **Use the streaming + retry pattern**, not verify_oracle's `stream=False`
  (verify_oracle.py:88-101). auto_pipeline `_call_ollama` (auto_pipeline.py:233-288)
  documents that `stream=False` returns an **empty response for Gemma under heavy
  load**; it accumulates streamed tokens and retries 3x with 2s/8s backoff. Copy
  that ~40-line helper into apl_judge (don't import auto_pipeline — it has heavy
  module-level deps: `sys.path` mutation, meta-analyzer path, optional hardening
  imports). Use `temperature=0.1` (deterministic judging), `num_predict≈512`,
  `num_ctx=4096` default with bump to 8192 when merged grep context is large.
- **Graceful degrade**: optionally `from agent_hardening import
  check_ollama_health` (harness/agents/scripts/agent_hardening.py:86) guarded in
  try/except; if Ollama is down, exit 2 (ERROR), do NOT report PASS/FAIL.
  Mirror verify_oracle's "don't fail the run if Gemma is down" stance for
  per-question transport errors (verify_oracle.py:145-147).

### C. Canonical question schema (resolves the spec's biggest gap)

The spec's three example blocks have **inconsistent fields** (oracle has
`target_apls`+`apl_grep_term`; strategic has `target_apls` but no grep term;
mulligan has *neither* target_apls nor any APL reference). The scorer cannot run
until one uniform schema exists. **Define every question to conform to:**

```json
{
  "id": "oracle_solitude_evoke",
  "type": "oracle_fidelity | strategic | mulligan",
  "target_apls": ["jeskai_blink_match.py", "goryos_match.py"],   // REQUIRED, all 3 types
  "grep_terms": ["Solitude", "evoke"],                            // REQUIRED, all 3 types
  "card_or_deck": "Solitude",                                     // display label
  "oracle_text": "...",          // oracle_fidelity only (or fetched live via CardDB)
  "board_state": "...",          // strategic only
  "principle": "...",            // strategic only (playbook line)
  "hand": "Mountain, Sacred Foundry, ...",  // mulligan only
  "role": "aggro", "on_play": true,         // mulligan only
  "expected": "PASS: ... FAIL: ..."          // REQUIRED
}
```

Scorer dispatch is then one clean loop:
load question → for each `target_apl` in scope → `grep_apl_context(apl,
grep_terms)` → build a **type-specific prompt** → `gemma4` → parse `RESULT`.

Resolve the two gaps the spec left:

- **Strategic `grep_terms`** = the card(s)/keyword named in `board_state`
  (e.g. `["Lava Dart", "Guide of Souls"]`). The spec's `apl_grep_term`
  (oracle-only) generalizes to `grep_terms` for all types.
- **Mulligan is the orphaned type.** Its example references no APL, yet the goal
  and the scoring formula (`correct / questions_applicable_to_that_deck`) only
  make sense if every question grades an APL. So type 3 **must** target the
  deck's `keep()`/`bottom()` logic: set `target_apls` to the deck's APL file and
  `grep_terms = ["keep", "bottom", "mulligan"]`. The judge reads that code + the
  given hand + 2-1-2 ground truth and decides whether the APL's *logic* yields
  the expected KEEP/MULL. **State explicitly: this is code inspection, not
  executing `keep()`** — honoring the spec's "no engine simulation" out-of-scope
  (spec lines 45-48, 122-124). 2-1-2 ground truth is from
  `external-research-mtg-ai-2026-04-30.md` (keep with ≥2 lands + ≥1 threat,
  max 2 mulligans).

### D. Judge prompt (per type, from spec lines 145-164, mirroring verify_oracle:116-141)

One template with type-conditional sections. Always end with the spec's answer
contract so parsing is uniform:

```
RESULT: PASS | FAIL
REASON: [one sentence]
```

- **oracle_fidelity**: CARD + ORACLE TEXT (live `CardDB.oracle_text` if
  `oracle_text` field omitted) + RELEVANT APL CODE (grep) + EXPECTED. Same shape
  as verify_oracle's audit prompt.
- **strategic**: DECK + PRINCIPLE (playbook line) + BOARD STATE + RELEVANT APL
  CODE + EXPECTED.
- **mulligan**: DECK + HAND + ON_PLAY + ROLE + 2-1-2 RULE + RELEVANT keep/bottom
  CODE + EXPECTED.

### E. Output parsing (more robust than the template)

Parse with a regex over the **whole** response: `re.search(r"RESULT:\s*(PASS|
FAIL)", resp, re.IGNORECASE)`. verify_oracle's `startswith(...) or in resp[:50]`
(verify_oracle.py:149) is fragile — gemma4 often emits a markdown fence or a
sentence of reasoning before `RESULT:`. Treat an unparseable response as FAIL
(decision-quality miss) but log the raw text.

### F. Scoring + CLI (spec lines 138-143, 174-180)

- CLI flags: `--apl <relpath>` (score one APL across its applicable questions),
  `--category oracle_fidelity|strategic|mulligan`, `--all-canonical`,
  `--model gemma4`, `--questions <path>`, `--calibrate`.
- A question is *applicable* to an APL when the APL's basename ∈ `target_apls`.
- `APL score = correct / applicable`. **Thresholds (reconcile the spec's
  internal inconsistency — goal >90 line 18, gate >85 line 188, stop <70 line
  194): pass = 85%, target = 90%, hard-stop = 70%.** State this choice in code
  comments + output. Exit 0 if ≥85%, 1 if <85%, 2 on ERROR (mirrors
  verify_oracle exit codes, spec lines 13-16).
- Print per-question PASS/FAIL + REASON, then a summary line per APL.

### G. Calibration mode (`--calibrate`, spec lines 166-172)

- Load `harness/data/apl_judge_calibration.json`: 5 fixtures whose embedded code
  snippet is **known-correct** and 5 **known-incorrect**, each with an
  `expected_result` (PASS/FAIL).
- **Do NOT rely on the spec's "Goryo's pre-fix Solitude bug" (spec line 170) —
  it is fixed and not reproducible on disk.** Embed self-contained
  correct/incorrect code snippets directly in the fixture JSON (the judge reads
  the snippet from the fixture, not from a live APL). Example incorrect fixture:
  a `cast_solitude()` snippet that omits the white-card-from-hand removal;
  matching correct fixture: one that performs `hand.remove(white_card)` before
  casting.
- Judge must agree with `expected_result` on **9/10**. <9/10 → STOP, adjust
  prompt, re-run (spec gate 1, lines 184-194). This is the long pole (expect
  2-3 prompt iterations).

---

## Concrete gotchas (only the real code reveals these)

1. **[BLOCKING] Boros reference must target `boros_energy_match.py`, not
   `boros_energy.py`.** The spec names `boros_energy.py` as the reference APL
   (spec lines 42, 138, 180). But `boros_energy.py` is the **goldfish** APL that
   casts burn at **face**; `boros_energy_match.py` is the match-aware one whose
   docstring states "Bolt/Galvanic/Phlage target opponent CREATURES (not face)"
   (boros_energy_match.py:5-8). Strategic/targeting questions ("kill Guide vs
   Bolt face", spec line 86, 96) scored against the goldfish file will
   **FAIL artificially**, blowing the >85% reference gate. Question `target_apls`
   for strategic/oracle questions must list `boros_energy_match.py`. (Both files
   exist — verified.)

2. **Model tag is `gemma4`, not `gemma:12b`.** The spec says "Gemma 12B"; the
   installed Ollama alias used everywhere in this repo is `gemma4`
   (verify_oracle.py:88, auto_pipeline draft_playbook). A literal `gemma:12b`
   model string will 404 from Ollama.

3. **`stream=False` is the empty-response trap.** auto_pipeline.py:236-238
   documents that Gemma returns empty under load with `stream=False`. verify_oracle
   uses `stream=False` and is the thing to *not* copy verbatim. Use streaming.

4. **Spec's named target APLs all exist** — verified: `jeskai_blink_match.py`,
   `goryos_match.py`, `izzet_prowess_match.py`, `amulet_titan_match.py`,
   `domain_zoo_match.py`, `boros_energy_match.py`. No filename correction needed
   *except* the Boros goldfish/match distinction (gotcha 1). Note `goryos_match.py`
   (not `goryos_vengeance.py` — that's the goldfish variant).

5. **Grep-context size cap.** A merged multi-term grep on a large match APL
   (e.g. `izzet_prowess_nick_tokyo_standard_match.py` is large) can balloon the
   prompt past `num_ctx=4096`, silently truncating gemma4's view. Cap merged
   context (e.g. ~6000 chars) and bump `num_ctx` to 8192 when exceeded. This is
   the spec's gate-4 "optimize grep context" trigger (spec line 189).

6. **`harness/data/` must be created.** It does not exist. `os.makedirs(...,
   exist_ok=True)` or create as part of authoring the JSON.

7. **Empty grep context = inconclusive, not PASS.** verify_oracle returns PASS
   when a card isn't mentioned (verify_oracle.py:113) — fine for an opt-in oracle
   audit, **wrong for a quality grade**. If `grep_apl_context` returns "" for a
   question whose APL *should* implement that decision, that is a FAIL (the
   decision is absent), or at minimum a logged INCONCLUSIVE excluded from the
   denominator. Pick FAIL for "should-be-present" oracle/strategic questions;
   document the choice.

8. **mulligan APL resolution.** Carry the APL path directly in the mulligan
   question's `target_apls` (simplest, no registry dependency). The alternative
   (resolve deck name → APL via `apl.get_match_apl` with SIM_ROOT on sys.path)
   adds a runtime import and the registry-normalization quirks seen in
   arl_loop.py:172-179 — avoid for the standalone scorer.

---

## byte-identical / no-regression concerns

- **N/A for regressions** — no existing file is edited. Engine, APLs, and ARL
  scripts are untouched, so there is zero risk to gauntlet/sim behavior.
- **Concurrency note (not a regression):** a concurrent workflow is writing under
  `mtg-sim/apl/`. apl_judge only *reads* those files on demand; if run at the
  exact moment a file is mid-write it could read partial content and mis-grade
  one question. Acceptable for an on-demand grader — run it after the apl/ writer
  settles. No locking needed.
- **Determinism:** gemma4 at temperature 0.1 is near-deterministic but not bit-
  exact across runs; scores may wobble +/-1 question. The calibration gate
  (9/10) is the guard. Do not treat a single sub-threshold run as definitive —
  re-run before declaring a FAIL (mirrors arl_loop's 2-run variance discipline).

---

## ARL integration (future hook — NOT this workflow)

The task asks where this plugs into the loop. The spec explicitly defers
integration to "Future work" (spec lines 196-200), and **landing it edits
`mtg-sim/scripts/arl_loop.py`, which is READ-ONLY for this workflow.** Documented,
not implemented here:

- **Hook point:** `arl_loop.run_iteration`, immediately after Step 10 EVALUATE
  (arl_loop.py:1041-1108), where the resolved APL class and `deck_name` are known
  and the result dict is being assembled. Call apl_judge on the resolved APL for
  that deck's *applicable* questions and stamp
  `result["decision_quality_score"]` alongside the existing
  `data_quality`/`confidence` fields (arl_loop.py:1094-1101).
- **Why it's the right seam:** apl_judge is a *decision*-quality gate, orthogonal
  to arl_profile's deterministic *engine-fidelity* gate (arl_profile.py:414) and
  to gauntlet FWR. It would sit beside them as a third, non-blocking signal
  (advisory; never auto-promotes/discards — matching the spec's out-of-scope
  "no auto-commit based on scores", spec line 46).
- **Pre-commit variant** (spec line 199): score only questions whose
  `grep_terms` touch cards in the changed APL — a separate harness hook, also
  future.

---

## Validation gates (from spec lines 182-194, thresholds reconciled)

| Gate | Acceptance | Stop trigger |
|---|---|---|
| 1 — calibration | judge agrees 9/10 | <9/10 → fix prompt, re-run |
| 2 — BE reference | `boros_energy_match.py` ≥ 85% | <85% → questions or judge wrong |
| 3 — coverage | all 3 types present (10 each) | any type missing |
| 4 — performance | 30Q run < 5 min on gemma4 | >10 min → cap/optimize grep context |

Hard stop: Boros reference < 70% → questions or judge are wrong; investigate.

---

## Effort

- apl_judge.py (mirroring verify_oracle + streaming helper): ~1 hr.
- 30 ground-truth questions (10 oracle / 10 strategic / 10 mulligan), each needing
  a real card/board lookup + correct `expected`: ~1.5 hr (the bulk).
- 10 calibration fixtures + iterating the judge prompt to 9/10: ~1 hr
  (2-3 prompt iterations likely).
- Total realistic **3-4 hr** (spec's 90-120 min undercounts question authoring +
  calibration).

---

## Recommendation: build-now

Self-contained, every dependency exists (`CardDB`, the gemma4/Ollama streaming
pattern, `verify_oracle` as a near-drop-in template), and it touches **nothing**
under mtg-sim — so it cannot conflict with the concurrent `apl/` writer. Highest
leverage of the open backlog: it adds a decision-quality signal that WR% and the
deterministic fidelity gate structurally cannot provide. The one ordering caveat:
author + pass calibration (gate 1) before trusting any APL score.

## Reconciliation note (2026-07-01)
Status corrected PLAN->SHIPPED: apl_judge.py + question/calibration data exist under harness/agents/scripts + harness/data; evalite spec (2026-06-29) extends it.
