# COUNCIL VERDICT: Is the local-LLM delegation spec sound to execute as written?

**Decision artifact:** `harness/specs/2026-07-03-local-llm-delegation.md`
**Convened:** 2026-07-03 (WP-I first live use)

## Verdict + confidence

**SOUND TO START, NOT SOUND AS WRITTEN — ratify Phases 1-2, revise before Phase 3.**
Confidence: **high** on the three required revisions (two rest on checkable
arithmetic / direct format comparison); med on the minor items.

The infrastructure half (routing.yaml + thin MCP mirroring the analyzer server +
tier-1/tier-2 backends) is coherent and correctly front-loads its load-bearing
risk (Gate 2.1: prove a subagent can call the MCP, with a hard STOP). The
"current reality" probes check out against ground truth. But three defects must
be fixed before execution reaches them; none blocks Phase 1.

### The three required revisions
1. **Gate 1.2 floor is miscalibrated against the budget cap.** At the accepted
   floor of 12 tok/s, a full tier-2 task (`max_tokens: 4000`, spec:123-124)
   needs 4000/12 = 333s of decode alone — past the 300s abort cap (spec:128,
   step 12). A config that PASSES Gate 1.2 still ABORTS every maximal tier-2
   task. **Fix: raise the floor to ~14 tok/s** (the empiricist's independent
   DDR4 arithmetic lands 14-16 tok/s realistic, so tier-2 is viable *iff* the
   floor is raised — the defect is the threshold, not the tier).
2. **Delegation gate can never green-light half of routing.yaml.** The
   DELEGATE-when-ALL gate (spec:139-147) requires HIGH-OUTPUT **and**
   machine-verifiable, but `commit_message` (max_tokens 200 = low output) and
   `summarize`/`draft_long` (prose = not verifiable; Gate 4.2 scopes the verify
   hook to *code* only) are shipped first-class task_types. Table contradicts
   policy. **Fix: reconcile — either loosen the gate (verifiable OR high-output,
   with a prose-review path) or drop the disqualified task_types.**
3. **Council-verdict consumption (Step 10) is not backed by what the council
   emits.** RULED by the reviewer against `SKILL.md:44-54`: the verdict format
   has NO machine-readable action-items/task-list field (only free-form "Blind
   spots → TODOs" prose), and its save path is caller-chosen (embedded in a
   spec **or** a standalone council file) — no stable schema. Step 10's "the
   executor reads the verdict artifact the council already writes" assumes an
   interface that does not exist. Worse, council TODOs are *reasoning* follow-ups
   — the exact category the spec's own gate (148-153) says KEEP on Claude — so
   even with a parse step, few council items would delegate. **Fix: either add
   an explicit LLM parse step (costs tokens — kills the "zero-cost handoff"
   framing) or DESCOPE council→executor from the lean pipeline.** ← user fork.

### Minor (fix in-flight, not blocking)
- Ollama version stale: spec says **0.30.10**; live `/api/version` = **0.31.1**.
- `.mcp.json` cwd/location unstated (no workspace-root .mcp.json exists; the
  `harness/agents/delegate_mcp/` package needs explicit cwd/PYTHONPATH). Step 8.
- `run()` concurrency unspecified: with `NUM_PARALLEL=1` + 300s timeout, parallel
  callers block up to 5 min, no queue/backpressure.
- B4 reuse-dividend nuance: to actually finish B4, the shared client must be a
  plain importable module BOTH the MCP wraps and the 9 nightly scripts import —
  not code buried inside `delegate_mcp/`. Factor accordingly.
- Cross-tier interleaving: routing.yaml freely mixes tiers while `one_tier_hot`
  concedes switching is manual. Disclosed as an imperfection, but the table
  invites the thrash. The storage addendum ("swaps cheap, ~4s warm") softens it.

## Where the council agreed / clashed

- **Agreed (2 of 3, third silent):** the council-verdict wiring is broken —
  Response A (flaw 3) and Response C (findings 1-2) independently; reviewer
  ruled them correct against SKILL.md. C's version more precise (isolates
  missing-field from unstable-path).
- **Clash — resolved:** Response A called the spec "internally inconsistent";
  Response B called it "internally consistent." Reviewer ruled these evaluate
  *different* constraint pairs (B: can the rig hit 12 tok/s? yes ~14-16; A: does
  hitting 12 imply tasks finish in budget? no). **Both locally correct; A's is
  decisive** because it exposes the gate/budget miscalibration B never tested.
- **Credit (unanimous-adjacent):** subagent→MCP risk correctly front-loaded;
  `_call_ollama` reuse target real (line 233); MCP mirror real; "council shipped,
  don't rebuild" TRUE (BLUEPRINT:297-301); gates falsifiable per house Rule 5.

## Blind spots flagged (become TODOs)
- **Gate 2.1 (subagent→MCP) is unproven by anyone** — the whole delegation model
  rests on it. It IS front-loaded in the spec as the first build step. Keep it
  as the hard gate; do not build Phase 3 until it passes.
- Tier-2 tok/s, VRAM co-residency (Gate 1.3), and 30B-A3B > 7B (Gate 5.1) are
  all run-time-verifiable only — honestly flagged as measurement gates.
- "Council TODOs = KEEP category" (Response A) is a reasonable inference, mildly
  overstated — some TODOs ("verify claim X via query") could be mechanical.

## Dissent worth preserving
- The one-tier-hot VRAM constraint is *disclosed* by the spec, so it is arguably
  a known limitation rather than a defect (Response C's framing). If tier-swaps
  are genuinely ~4s warm (storage addendum), the two-tier design survives and
  "single-tier marketing" (Response A flaw 2) overstates the harm. Preserve:
  revisit once Gate 1.3 + swap-latency are measured — the tier-2 value case
  (revision #1) and the swap-cost case together decide whether tier-2 stays.

## EVIDENCE INDEX
- `harness/specs/2026-07-03-local-llm-delegation.md`: 123-124 (tier-2 max_tokens
  4000), 128 (budget timeout_s 300), 139-147 (DELEGATE-ALL gate), 148-153 (KEEP
  conditions), 119-121 (low-output/prose task_types), 188-190 + 27-30 (Step 10
  consume-council), 216 (Gate 4.2 code-only verify), 130/259-265 (one_tier_hot +
  imperfection), 209 (Gate 1.2 floor 12 tok/s).
- `.claude/skills/council/SKILL.md`: 44-54 (Stage-3 verdict format — no task-list
  field; caller-chosen save path) — the decisive cross-check.
- `BLUEPRINT-2026-07-03.md`: 297-301 (WP-I council SHIPPED).
- Live probes: `/api/version` → 0.31.1; `/api/tags` → qwen2.5-coder:7b present;
  `nvidia-smi` → RTX 3080 10GB; `ls` → ollama_client.py absent, llama.cpp absent;
  `mtg-meta-analyzer/.mcp.json` → stdio `python -m mcp_server.server`;
  `auto_pipeline.py:233` (_call_ollama streaming). HF: unsloth/Qwen3-Coder-30B-
  A3B-Instruct-GGUF Q4_K_M 18.6GB exists.
- Arithmetic: 4000 tok / 12 tok/s = 333s > 300s cap; 4000 / 14 ≈ 286s < 300s.

## Seats
- N = 3 first-opinion seats (Analyst, Contrarian, Empiricist) + 1 blind reviewer.
- Vendors: **single-vendor (all Claude)** — `codex` CLI NOT installed, so no
  cross-vendor seat. Same-family bias is the known limitation of this verdict.
- Blind protocol confirmed: **yes** — Stage-1 seats spawned in one message,
  blind to each other; Stage-2 reviewer received shuffled A/B/C with roles
  stripped; no seat saw the proposer's (my) conclusion.
- Protocol note: the Empiricist seat edited the decision artifact (appended a
  factual storage addendum + corrected the Ollama version). Minor deviation from
  "seats don't mutate the artifact"; changes were factual and are folded in here.

**The USER is the final ratifier. The council recommends; Jermey decides.**
