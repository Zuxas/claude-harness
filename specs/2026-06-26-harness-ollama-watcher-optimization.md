---
title: "Harness + Ollama + Watcher/Controller Optimization"
status: SHIPPED
created: 2026-06-26
updated: 2026-06-26
project: harness
estimated_time: 180
related_findings: []
related_commits: ["f86f799"]
supersedes: []
superseded_by: []
---

## Goal

Make the local-model side of the harness (Ollama on an RTX 3080 10GB) run reliably
on auto: predictable VRAM usage, no model-reload thrash, bounded context, real
timeouts/retries, and a watcher/controller that survives crashes and stalls.

## Scope

- IN: Ollama server env tuning; per-request `num_ctx` / `keep_alive` / `stream`;
  model routing across the pipeline; request timeouts + retries; circuit-breaker
  thresholds; inbox watcher + nightly controller reliability (idempotency, stall
  detection, restart-on-crash).
- OUT: APL prompt-quality work; Claude-API path changes; mtg-sim engine; any
  meta-analyzer code. No changes to scheduled-task *times* (only command lines).

## Grounded Current Reality (measured 2026-06-26)

Ollama **0.30.10**, server up at `http://localhost:11434`. **No `OLLAMA_*` env vars
set** (all defaults). Installed models:

| Model | Disk | Params / quant | Native ctx | Role today |
|---|---|---|---|---|
| `qwen2.5-coder:14b` | 9.0 GB | 14.8B Q4_K_M | 32768 | code-gen (classify, keep/bottom, main_phase) |
| `gemma4:26b` | 17 GB | 25.8B MoE Q4_K_M | - | code-gen fallback only |
| `gemma4:latest` (called `gemma4`) | 9.6 GB | 8.0B Q4_K_M | 131072 | prose (playbooks, tuning swaps, drift PR, inbox) |

**Measured VRAM behavior (the core problem):**
- `qwen2.5-coder:14b` @ `num_ctx=4096` loads as **10.0 GB, 16%/84% CPU/GPU** — it
  does **not** fully fit; ~16% of weights spill to CPU (slow path). Lowering
  `num_ctx` won't fix this; it's the 9 GB of weights + desktop VRAM + compute
  buffer exceeding 10 GB.
- `gemma4` with **no `num_ctx`** loads at **CONTEXT 131072** (full native context).
  Ollama 0.30.10 does NOT default to 2048/4096 here — it uses the model's max.
  KV is allocated lazily (showed 3.3 GB at 1-token gen), but the declared context
  is unbounded and balloons KV on long generations.
- Two ~9-10 GB models cannot co-reside on 10 GB. Any qwen<->gemma alternation
  forces a full unload+reload (~9-10 GB of disk I/O each swap).

**Per-call-site audit (model / stream / num_ctx / keep_alive / retry):**

| File:line | model | stream | num_ctx | keep_alive | retry |
|---|---|---|---|---|---|
| `auto_pipeline.py:224 _call_ollama` | arg (qwen) | True | 4096 | none | none |
| `auto_pipeline.py:1087 draft_playbook` | gemma4 | **False** | none(=131072) | none | none |
| `tuning_loop.py:105 ask_gemma` | gemma4 | **False** | none | none | breaker only |
| `apl_tuner.py:51 ask_gemma` | gemma4 | **False** | none | none | none |
| `gemma_drift_pr.py:205 ask_gemma` | gemma4 | **False** | none | none | none |
| `gemma_apl_factory.py:152 ask_gemma` | gemma4 | **False** | none | none | none |
| `apl_optimizer.py:162 ask_gemma` | gemma4 | **False** | none | none | none |
| `gemma_apl_chunked.py:53` | gemma4 | **False** | none | none | none |
| `scripts/ask-gemma.ps1:37` | gemma4 | **False** | none | none | none |

**Two latent bugs found:**
1. **Monolith truncation** — `auto_pipeline.py` monolith fallback (lines 706-707,
   716-717) calls `_call_ollama(..., max_tokens=4096)` but `_call_ollama` hardcodes
   `num_ctx=4096`. Prompt (~2.5k tokens) + 4096 output > 4096 total context ->
   output is silently truncated. The decomposed path (max_tokens 300-600) is unaffected.
2. **stream=False contradiction** — `auto_pipeline._call_ollama`'s own docstring says
   "stream=False returns empty response for Gemma 4 after heavy load," yet 8 other
   call sites still use `stream=False` against gemma4. They inherit exactly the bug
   the streaming path was written to avoid.

**Circuit breaker (`agent_hardening.py:75`):** `ollama_breaker` = 3 fails / 120 s
recovery. `check_ollama_health` only pings `/api/tags` (server liveness), not model
load or generate success.

**Watcher (`watch-inbox.ps1`):** FileSystemWatcher, 30 s per-name debounce, registers
BOTH Created + Changed. No `Error` event handler (silent death on buffer overflow),
default `InternalBufferSize` (8 KB), no Ollama precheck, no restart-on-crash, no stall
detection. On-login backstop only (no supervisor).

---

## CHANGES

Each change: **[Value 1-5 | Effort S/M/L | Risk]**, exact file+edit, and an
**AUTO-APPLY** verdict (`SAFE NOW` vs `BENCHMARK FIRST`).

### A. Ollama server env tuning (machine-level)

These pin Ollama into a single-user, VRAM-constrained, serialized profile. Set as
**user env vars** then restart `ollama serve` (or reboot). Apply via:
`setx OLLAMA_NUM_PARALLEL 1` etc. (PowerShell convention: write `.ps1` to `C:\temp\`,
run `-ExecutionPolicy Bypass`). Touches: **no repo files** — OS env only.

- **A1. `OLLAMA_MAX_LOADED_MODELS=1`** [V5 | S | Low] — default tries up to 3; on a
  10 GB card a second 9 GB model can't load, causing churn/partial offload. Forcing 1
  makes swaps clean and deterministic. **AUTO-APPLY: SAFE NOW.**
- **A2. `OLLAMA_NUM_PARALLEL=1`** [V5 | S | Low] — default auto-picks up to 4 parallel
  slots, each carving its own KV slice out of the same 10 GB -> fragmentation / extra
  offload. The harness issues strictly sequential requests, so 1 slot is correct and
  maximizes VRAM per request. **AUTO-APPLY: SAFE NOW.**
- **A3. `OLLAMA_KEEP_ALIVE=30m`** [V4 | S | Low] — global default is 5 min; nightly
  steps are spaced far enough apart that the model unloads between them and reloads
  every step. 30 m keeps one model warm across a nightly run while still releasing it
  overnight. (Per-request `keep_alive` in B overrides this where needed.)
  **AUTO-APPLY: SAFE NOW.**
- **A4. `OLLAMA_FLASH_ATTENTION=1`** [V3 | S | Low-Med] — reduces KV-cache memory and
  speeds attention; broadly stable on Ampere (RTX 3080). Prereq for A5.
  **AUTO-APPLY: SAFE NOW** (revert if any gibberish observed).
- **A5. `OLLAMA_KV_CACHE_TYPE=q8_0`** [V3 | S | Med] — halves KV memory vs f16, buying
  headroom for the 14B; q8_0 quality impact is negligible but nonzero. Requires A4.
  **AUTO-APPLY: BENCHMARK FIRST** (compare APL smoke-pass rate with/without).

### B. Per-request params: bound context, keep warm, stop using stream=False

- **B1. Fix monolith truncation** [V5 | S | Low] — in `auto_pipeline.py`, give the
  monolith fallback room. Either (a) change `_call_ollama` signature to accept
  `num_ctx` (default 4096) and pass `num_ctx=8192` at lines 706-707 and 716-717, or
  (b) simplest: bump the hardcoded `num_ctx` in `_call_ollama` (line 234) to `8192`.
  Recommend (a) so short calls keep small contexts. **AUTO-APPLY: SAFE NOW** (bug fix).
- **B2. Add `keep_alive` to every request body** [V4 | S | Low] — add
  `"keep_alive": "30m"` to the JSON body in all 9 call sites (auto_pipeline `_call_ollama`
  line 232-235 and `draft_playbook` 1087-1091; `tuning_loop` 105-110; `apl_tuner`
  51-55; `gemma_drift_pr` 205-209; `gemma_apl_factory` 152-154; `apl_optimizer`
  167-168; `gemma_apl_chunked` 53-55; `ask-gemma.ps1` 32-41). Belt-and-suspenders with
  A3; survives if A3 isn't set. **AUTO-APPLY: SAFE NOW.**
- **B3. Set `num_ctx` explicitly on the prose call sites** [V4 | M | Med] — every
  gemma4 call currently omits `num_ctx` and inherits 131072. Set
  `"num_ctx": 8192` in the `options` block of the 8 prose sites (B2 list minus the
  qwen `_call_ollama`). 8192 covers the longest prompts (drift PR, playbook context ~6k
  tokens) without declaring a 128k KV graph. **AUTO-APPLY: BENCHMARK FIRST** — confirm
  8192 KV + gemma weights stays >=95% on GPU via `ollama ps` (raising declared ctx
  raises KV ceiling; verify no new CPU spill).
- **B4. Switch `stream=False` -> streaming accumulation on the 8 prose sites**
  [V4 | M | Med] — mirrors the proven `_call_ollama` pattern (accumulate
  `chunk["response"]` until `done`). Eliminates the documented empty-response-under-load
  bug. Cleanest implementation: add one shared helper
  `harness/agents/scripts/ollama_client.py::call_ollama(prompt, model, *, system, temperature, max_tokens, num_ctx, keep_alive, timeout, retries)` and route all
  Python sites through it (collapses 8 near-duplicate `ask_gemma` bodies). **AUTO-APPLY:
  BENCHMARK FIRST** — behavior-equivalent but touches parsing in 8 files; smoke each.

### C. Model routing (stop the 9 GB<->9 GB swap)

- **C1. Drop `gemma4:26b` from the code-gen preference** [V4 | S | Low] — in
  `auto_pipeline.py:646` `_APL_CODE_MODEL_PREFERENCE`, remove `"gemma4:26b"`. At 17 GB
  it cannot fit 10 GB and runs at heavy CPU offload (near-unusable). It is only ever
  selected if qwen is missing; keeping it is a latent slow-path trap. New list:
  `["qwen2.5-coder:14b", "gemma4"]`. **AUTO-APPLY: SAFE NOW.**
- **C2. Pull `qwen2.5-coder:7b` and use it for classification** [V4 | M | Med] —
  classification (`_classify_deck`) is an extraction task, not deep reasoning. The 7B
  (~4.7 GB) fits fully on GPU with room to spare and could co-reside with nothing
  needing to swap mid-phase. Lower swap cost + faster. Requires `ollama pull
  qwen2.5-coder:7b`, then point `_classify_deck`'s model at it (or add a
  `_pick_classify_model` preferring 7b). **AUTO-APPLY: BENCHMARK FIRST** — verify 7B
  classification dict-parse success rate matches 14B before adopting.
  **DONE 2026-06-27 (extended to ALL code-gen, not just classify):** pulled
  qwen2.5-coder:7b; set `_APL_CODE_MODEL_PREFERENCE=["qwen2.5-coder:7b","gemma4"]`
  (14b retired from preference), code-gen temps -> 0.1, num_batch 1024 added. Same-prompt
  A/B vs 14b: 95.5 tok/s / 7.7s vs 0.30 tok/s / 27.5min (~320x). Full decomposed gen on a
  Modern deck: ~10s -> valid loadable APL. The 14b 0.30 tok/s spill empirically confirmed the
  VRAM-fit thesis; this is the highest-impact change in the whole spec.
- **C3. Phase-order the nightly to batch same-model steps** [V3 | M | Low] — today
  nightly interleaves qwen (auto-pipeline APL gen) and gemma (retune/playbook/drift),
  forcing >=1 reload. Group all code-gen first, all prose second, so at most one swap
  per run. Touches `nightly_harness.py` step ordering only (no logic change).
  **AUTO-APPLY: BENCHMARK FIRST** (reordering can shift dependencies; dry-run first).
- **C4. (Investigate, do not auto-apply) consolidate prose+code on one model** — a
  single resident model removes swaps entirely, but qwen-coder is weak at prose and
  gemma weaker at structured Python. Only viable with a quality benchmark per task
  class. **AUTO-APPLY: BENCHMARK FIRST.**

### D. Timeouts, retries, circuit breaker

- **D1. Add retry-with-backoff to the shared client** [V4 | S | Low] — wrap the call
  in 2-3 attempts with 2s/8s backoff on `URLError`/timeout/empty-response. Today a
  single transient blip returns `{}` (classification) or an `ERROR:` string. If B4's
  shared client lands, implement once there; otherwise add to `auto_pipeline._call_ollama`.
  **AUTO-APPLY: SAFE NOW** (in `_call_ollama`); via shared client = BENCHMARK FIRST (ships with B4).
- **D2. Split timeouts: connect vs read** [V3 | S | Low] — current single 300 s
  `urlopen` timeout means a stalled stream hangs ~5 min. With streaming (B4), add a
  per-iteration watchdog: if no chunk for 60 s, abort and let D1 retry. **AUTO-APPLY:
  BENCHMARK FIRST** (ships with B4).
- **D3. Circuit-breaker tuning** [V2 | S | Low] — current 3 fails / 120 s is fine for
  an attended box but slow for unattended nightly (a 120 s open window can skip a whole
  step). Recommend keeping `failure_threshold=3` but exposing `recovery_timeout` via
  env and lowering nightly to 45 s. Also have `check_ollama_health` optionally do a
  1-token generate (not just `/api/tags`) so a wedged-but-listening server trips the
  breaker. Touches `agent_hardening.py:75,79`. **AUTO-APPLY: BENCHMARK FIRST** (the
  generate-probe adds a model load; measure cost).

### E. Watcher / controller reliability

- **E1. Restart-on-crash supervisor for the watcher** [V5 | M | Low] — `watch-inbox.ps1`
  has no supervisor; if it throws or the runspace dies, the inbox silently stops
  compiling. Add `harness/scripts/watch-inbox-supervisor.ps1` that runs the watcher in
  a `while($true){ try{ & watch-inbox.ps1 } catch{} ; Start-Sleep 10 }` loop, and
  register THAT as the on-login task instead of the raw watcher. **AUTO-APPLY: SAFE NOW.**
- **E2. Add FileSystemWatcher `Error` handler + bigger buffer** [V4 | S | Low] — in
  `watch-inbox.ps1`, set `$watcher.InternalBufferSize = 65536` and
  `Register-ObjectEvent $watcher "Error"` to log + re-enable `EnableRaisingEvents`.
  Without this, a buffer overflow kills the watcher invisibly. **AUTO-APPLY: SAFE NOW.**
- **E3. Ollama precheck before compile** [V3 | S | Low] — the watcher fires
  `process-inbox.ps1` (Gemma) with no health check; if Ollama is down the compile
  fails (file is correctly retained, but error noise + wasted cycle). Gate the action
  on a `/api/tags` 200 first; if down, leave the file and log "deferred". The nightly
  inbox step (Step 7) will catch it later. **AUTO-APPLY: SAFE NOW.**
- **E4. Idempotency for the watcher** [V3 | S | Low] — `process-inbox.ps1` correctly
  moves files to `processed/` only on success, so reprocessing is already bounded.
  Harden by writing a per-file `.lock`/hash so a Created+Changed double-fire within the
  30 s window can't start two concurrent compiles of the same file. **AUTO-APPLY: SAFE NOW.**
- **E5. Stall detection on the nightly controller** [V2 | M | Low] — `nightly_harness`
  has per-subprocess timeouts (good) and an `IdempotencyGuard`, but no overall
  wall-clock cap. Wrap `run_nightly` in a `LoopController`-style budget (e.g. 90 min)
  so a wedged step can't leave the job "running" forever and block the idempotent
  re-run next day. Touches `nightly_harness.py`. **AUTO-APPLY: BENCHMARK FIRST**
  (need a realistic ceiling from a few timed runs).

---

## SAFE-TO-AUTO-APPLY NOW (subset)

These are config or strict bug/robustness fixes with no model-quality dependence:
**A1, A2, A3, A4, B1, B2, C1, D1 (in `_call_ollama`), E1, E2, E3, E4.**

## NEEDS BENCHMARK FIRST

Anything that can change output quality or VRAM residency:
**A5 (kv q8), B3 (num_ctx=8192 on gemma), B4 (streaming refactor), C2 (7b classifier),
C3 (phase reorder), C4 (single-model), D2 (stream watchdog), D3 (breaker probe),
E5 (nightly wall-clock cap).**

## Validation Gates

1. After A1+A2: `ollama ps` during a nightly run never shows two models loaded;
   `OLLAMA_NUM_PARALLEL` honored (one slot). Falsify: two NAME rows -> A1 not applied.
2. After A3/B2: within a single nightly run, the warm model's `UNTIL` advances rather
   than the model disappearing between steps (grep `nightly-<date>.log` for reload gaps).
3. After B1: a forced monolith APL gen produces a syntactically complete class
   (no truncated tail). Gate: `ast.parse` succeeds on monolith output 5/5 runs.
4. After B3: `ollama ps` shows gemma4 @ ctx 8192 at **>=95% GPU** (no new CPU spill).
   Stop condition: any CPU% appears -> lower to 6144 or keep flash-attn+q8 (A4/A5).
5. After C2: 7B classification dict-parse success >= 14B baseline over 10 decks
   (currently measured ad hoc; capture baseline before swapping).
6. After E1/E2: kill the watcher process; supervisor relaunches within 15 s; drop a
   test `tech--watcher-selftest.txt` and confirm it compiles.

## Stop Conditions

- Any SAFE-NOW change that raises APL smoke-pass *below* current baseline (0/3 today;
  use a stable deck set) -> revert that change, open IMPERFECTIONS entry.
- `qwen` CPU-offload % increases after env changes -> revert A5/B-context bumps.
- Watcher supervisor enters a tight crash loop (>3 restarts/min) -> disable, investigate.

## Rollback

- Env (A): `setx OLLAMA_X ""` / remove user var, restart `ollama serve`.
- Code (B/C/D/E): single-file edits; revert per file. No schema/state migrations.
- Watcher: re-point on-login task from supervisor back to raw `watch-inbox.ps1`.

## Annotated Imperfections (of this spec)

- Does not solve the root VRAM ceiling: `qwen2.5-coder:14b` cannot be made to fully
  fit 10 GB without a smaller model/quant (see C2). This spec minimizes the pain
  (fewer swaps, bounded ctx, flash-attn) but the 16% offload persists unless C2 lands.
- The shared `ollama_client.py` (B4) is the highest-leverage cleanup but is also the
  largest single edit; it is deliberately gated behind a benchmark so the SAFE-NOW
  subset can ship without it.
- Quality baselines (C2, gate 5) are not yet captured; first execution step must record
  them before any model-routing change.

## Changelog
- 2026-06-26: PROPOSED. Authored from read-only audit + live Ollama probes (0.30.10,
  qwen 16% CPU spill @4096, gemma default ctx 131072, no OLLAMA_* env set).
- Reconciled 2026-06-27: verified complete; status was stale after the ~2026-05-16 cadence lapse.
