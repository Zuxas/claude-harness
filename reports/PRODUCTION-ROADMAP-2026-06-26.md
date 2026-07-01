---
title: Master Production Roadmap — "Stockfish for MTG"
created: 2026-06-26
---

# Master Production Roadmap — "Stockfish for MTG"

North star: a system that quantifies the **best moves, sequences, deckbuilds, sideboard plans, trigger-stacking, and game actions** — eventually for every format. This document synthesizes six grounded research evaluations (engines, MCP composition, ML/calibration, polish/badges, Ollama/watcher, phone app) into one sequenced plan.

Backing docs:
- `harness/knowledge/tech/ext-eval-mtg-engines-2026-06-26.md`
- `harness/knowledge/tech/ext-eval-mcp-composition-2026-06-26.md`
- `harness/knowledge/tech/ext-eval-ml-calibration-2026-06-26.md`
- `harness/knowledge/tech/ext-eval-polish-naereen-2026-06-26.md`
- `harness/specs/2026-06-26-harness-ollama-watcher-optimization.md`
- `harness/specs/2026-06-26-meta-analyzer-phone-app.md`

---

## 1. NORTH STAR ARCHITECTURE

"Stockfish for MTG" is a stack of seven layers. Chess engines win because a *trustworthy deterministic core* feeds a *search/eval layer*. MTG adds two hard complications chess does not have: a **priority/stack interaction model** and **hidden information**. Those two are our long poles; everything search-related is gated behind them.

| # | Layer | Purpose | HAVE | MISSING / IMPERFECTION |
|---|-------|---------|------|------------------------|
| L1 | **Deterministic rules engine** | Resolve any board state identically every time | `mtg-sim` engine: 100% Standard handler coverage (4218/4218 cards), 17 sets at 0 remaining; replacement-effect + layers handling partial | PW-loyalty is **dead code**: `Card.loyalty` + `activate_planeswalker_ability` exist but have **zero callers in the match path**; registry holds 1 PW; Standard PWs are one-shot ETB handlers (Effort M, ~3-4hr, NOT a trivial wire-up). **warp** (~28% of Modern field) unmodeled. |
| L2 | **Legal-move generation + stack/priority** | Enumerate every legal action; resolve the stack with priority passes; instant-speed interaction | `stack.py` exists | **No decision loop wires it.** No legal-action enumeration API, no priority pass-loop. This is the single biggest blocker for both fidelity and the bot. Instant-speed combat falls out of this work "for free." |
| L3 | **Hidden-information model** | Mask opponent hand/library; reason under uncertainty | nothing | Engine is fully observable today. Perfect-play in MTG **requires** masking + determinization. Borrow Argentum's masked-observation pattern (reimplement, see licenses). |
| L4 | **Search / eval (best move & sequence)** | The "Stockfish" core: pick best line | existing APLs (archetype play-lines) can serve as rollout priors / warm start; GBM win-prob model can serve as the leaf evaluator | **No search layer.** Must be **ISMCTS with determinization** (PUCT), NOT plain minimax, because MTG is imperfect-information. Code is small (~hundreds of lines); the cost is the L1-L3 hardening underneath (XL). Gated on L2+L3 + an O(1) fork / `reset/step/observe/legalActions` API. |
| L5 | **Deck / sideboard optimizer** | Best 75; best SB plan per matchup | `bo3_gauntlet.py`, `sb_optimizer.py`, `sim.py` | Present but consumes L1's WR; trustworthiness bounded by L1 fidelity (PW/warp gaps bias WR). |
| L6 | **Calibrated win-probability** | Make every number believable vs reality | GBM win-prob model; sim-vs-real matchup matrix tab; `bo3_match.py` FWR | `win_prob_model.py` is **half-wired**: imports `CalibratedClassifierCV` (unused), prints `brier_score_loss` but never plots reliability or wraps the model. No Wilson bands on FWR. No aggregate sim-vs-real agreement chart. |
| L7 | **Data / meta layer + autonomous research loop (ARL)** | Feed all layers fresh meta; self-improve | meta-analyzer (37,539 Standard decklists / 389 archetypes; 91% classifier), ARL nightly pipeline, MCP server (5 read-only tools), Ollama local-LLM box | MCP server on FastMCP 1.0 (no composition surface); sim/meta not split; Ollama defaults cause reload thrash + truncation bugs; classifier KNN fallback tail under-served (ModernBERT fine-tune candidate). |

### The central architectural decision (made visible, not fudged)

The engines doc identifies **two orthogonal axes** that the rest of the plan must respect:

- **Axis A — engine fidelity / trustworthy WR** (PW-loyalty, warp, instant-speed combat). Improves the believability of *today's* numbers. Orthogonal to the bot.
- **Axis B — perfect-play bot enablement** (legal-action API + O(1) fork → stack-priority decision loop → hidden-info masking → search). This IS the path to "Stockfish for MTG."

**Spine decision:** Because the stated north star is *the bot*, **Axis B is the primary spine** (L2 → L3 → L4). **Axis A runs in parallel** as a separate track — it is independent work that keeps RC-prep / meta WR trustworthy while the long poles are built, and PW-loyalty is "ours to finish" rather than a borrow. The search layer (L4) may never be scheduled before L2+L3 land. This fork (bot-first vs trust-first) is the one strategic call flagged for the user in Section 4.

---

## 2. SEQUENCED ROADMAP (P0 … P6)

Sizing: **S** = hours, **M** = days, **L** = 1-2 weeks, **XL** = multi-week. Each item cites its backing doc. The dependency spine **L2 → L3 → L4** is absolute: nothing search-related precedes it.

### P0 — Quick-win foundation (autonomous-safe, no dependencies)  [this session's waves]
- **Calibration 1A**: finish `mtg-sim/ml/win_prob_model.py` — wire `CalibratedClassifierCV(method="isotonic")`, add `calibration_curve(strategy="quantile")`, hand-rolled ECE, Brier before/after, write `data/win_prob_calibration.png`. **S** — *ml/calibration*.
- **MCP (b)**: mount j4th/mtg-mcp-server (MIT, 69 tools) via `uvx` + `.mcp.json` entry — isolated process, instant rollback. **S** — *mcp*.
- **Ollama A1-A4 + B1/B2/C1/D1 + E1-E4**: env vars (`OLLAMA_MAX_LOADED_MODELS=1`, `NUM_PARALLEL=1`, `KEEP_ALIVE=30m`, `FLASH_ATTENTION=1`), monolith `num_ctx` truncation fix, per-request keep_alive, drop gemma4:26b, retry-with-backoff, watcher supervisor/Error-handler/precheck/lock. **S** — *ollama/watcher*.
- **Badges**: paste-ready blocks into mtg-sim + mtg-meta-analyzer READMEs (both MIT). **S** — *polish*.
- **MCP (a)**: upgrade meta-analyzer server import to `from fastmcp import FastMCP`, pin `fastmcp>=3.2.0`. **S** — *mcp*.

### P1 — Calibration & data-layer hardening
- **Calibration 1B**: aggregate weighted sim-vs-real scatter vs y=x + slope + weighted MAE in `gui/tabs/calibration.py`. **M** — *ml/calibration*.
- **Calibration 1C**: Wilson confidence bands on FWR in `bo3_match.py`. **S** — *ml/calibration*.
- **License gate**: add LICENSE to claude-harness + TeamResolve (no LICENSE today → dynamic license badges break; static MIT badge meanwhile). **S** — *polish*.
- **MCP (c1)**: NEW stateful server inside `mtg-sim/mcp_server/` wrapping `sim.py`/`bo3_gauntlet.py`/`sb_optimizer.py`, job-style first. **M** — *mcp*.
- **`generate_site_data.py`** generalize beyond hardcoded `FORMAT="modern"` + fixed `OUR_DECKS`. **S** — *phone app* (prereq for P-side phone work).

### P2 — Axis A: engine fidelity (parallel track, orthogonal to bot)
- **PW-loyalty**: wire `activate_planeswalker_ability` into the match decision path; add callers; expand registry. **M** — *engines* (V4).
- **warp**: model warp mechanic (~28% of Modern field) using wanqizhu's delayed/intervening-if trigger model as design reference. **M-L** — *engines* (V4).
- *(instant-combat folds into L2 stack work in P3, not done here.)*

### P3 — Axis B core: legal moves + stack/priority (LONG POLE #1)
- **B1 — legal-action API + O(1) fork**: `reset/step/observe/legalActions` + immutable-state fork, borrowing Argentum's design (reimplement w/ attribution). **L-XL** — *engines*.
- **B2 — stack-priority decision loop**: wire `stack.py` into a priority pass-loop (borrow open-mtg pass-loop pattern). Delivers instant-speed combat for free. **L-XL** — *engines*.

### P4 — Axis B: hidden information (LONG POLE #2)
- **B3 — hidden-info masking**: mask opponent hand/library; determinization scaffolding, borrowing Argentum's masked-observation pattern. **L-XL** — *engines*.

### P5 — Axis B: the search/eval layer (the actual "Stockfish")
- **ISMCTS + determinization (PUCT)**: small (~hundreds of lines) on top of B1-B3; existing APLs = rollout priors/warm start; GBM = leaf evaluator. **M** of code on **XL** of prerequisites. Gated on P3+P4. **L** — *engines*.

### P6 — Productization & autonomous improvement
- **ModernBERT fine-tune** (`analysis/modernbert_finetune.py`): decklist-as-text → archetype, promote as classifier Layer 5 only if it beats KNN baseline; route training to Colab/Gemma box (no local GPU), ship inference artifact, lazy torch import. **L** — *ml/calibration*.
- **Phone app v0 PWA**: `manifest.webmanifest` + `sw.js` + mobile CSS on My-Website; offline matchup WR + SB playbook; zero backend. **M** — *phone app*. (Capacitor / FastAPI Tier3 deferred.)
- **MCP (c)-B orchestrator**: single FastMCP endpoint proxy-mounting all servers, only if one endpoint is needed. **M** — *mcp*.
- **ARL loop closes**: search-layer self-play feeds back into APL priors + win-prob model + meta. **XL** — *engines*.

**Honest long-pole statement:** P3 + P4 (stack/priority + hidden information) are multi-week each. The search layer (P5) is cheap code but cannot start until both land. Anyone reading "the MCTS is only a few hundred lines" should read it as: the engine hardening underneath is the real XL cost.

---

## 3. NEXT 3 BUILD WAVES

This autonomous session executes these in order, highest value-to-effort first. Waves 1-2 are S-sized, dependency-free, autonomous-safe builds. Wave 3 is a **spec, not a finish** — the engine long poles get designed, not implemented, this session.

### WAVE 1 — Calibration completion + Ollama/watcher hardening (highest V/E)
**Build:**
- Finish `mtg-sim/ml/win_prob_model.py` (Calibration 1A): wrap GBM in `CalibratedClassifierCV(method="isotonic")`, add `calibration_curve(strategy="quantile")` + hand-rolled ECE, print Brier before/after, save reliability PNG. Credit only the *idea* of validating probs vs external truth (ratloop has NO calibration code — use scikit-learn directly, BSD-3, already a dep).
- Apply Ollama auto-safe set: env A1-A4 (`OLLAMA_MAX_LOADED_MODELS=1`, `OLLAMA_NUM_PARALLEL=1`, `OLLAMA_KEEP_ALIVE=30m`, `OLLAMA_FLASH_ATTENTION=1`); code B1 (monolith `num_ctx` truncation fix), B2 (per-request keep_alive), C1 (drop gemma4:26b), D1 (retry-with-backoff); watcher E1-E4 (supervisor restart-loop, Error handler + 64KB buffer, Ollama precheck, per-file lock).

**Expected artifact:** `mtg-sim/data/win_prob_calibration.png` + Brier-before/after in stdout; patched `win_prob_model.py`; updated Ollama env (machine/service config) + patched `auto_pipeline`/`_call_ollama` + hardened `watch-inbox.ps1`.

**Verify:** Run the win-prob trainer; confirm it prints `Brier (before) → Brier (after)` and `data/win_prob_calibration.png` exists and is non-empty. For Ollama: `ollama ps` shows a single loaded model with no qwen↔gemma reload thrash across a nightly dry-run; confirm `num_ctx` matches requested `max_tokens` (no silent truncation) and the watcher survives a forced child-process kill (supervisor relaunches it).

### WAVE 2 — MCP composition + README badges (biggest win / smallest effort)
**Build:**
- MCP (b): mount j4th/mtg-mcp-server (MIT, 69 tools, `requires-python>=3.12`) via `claude mcp add mtg -- uvx mtg-mcp-server` and a `.mcp.json` entry — isolated process, scraping backends left feature-flagged off.
- MCP (a): upgrade `mtg-meta-analyzer/mcp_server/server.py` to `from fastmcp import FastMCP`, add `fastmcp>=3.2.0` to `requirements.txt`, verify the `annotations=` kwarg (FastMCP 3.x IS GA — the earlier "no 3.x" claim is stale).
- Badges: paste the prepared MIT badge blocks into `mtg-sim/README.md` and `mtg-meta-analyzer/README.md`. For claude-harness + TeamResolve, use the **static** MIT badge only (both have NO LICENSE yet — dynamic license/`github/license` badges 404 until a LICENSE is added; note the prereq).

**Expected artifact:** updated `.mcp.json` with the j4th entry; upgraded `server.py` + `requirements.txt`; badge blocks committed to the two MIT READMEs.

**Verify:** `claude mcp list` shows the mtg server connected with its ~69 tools; the meta-analyzer server still starts and its 5 read-only tools enumerate (pure-`tools.py` tests unaffected); the READMEs render with badges resolving (no broken-image / 404 on the license/last-commit shields for the MIT repos).

### WAVE 3 — Spec the engine long poles (Axis B spine) — SPEC, NOT FINISH
**Build (design only):** Write a concrete implementation spec for the Axis B dependency spine that downstream sessions execute:
- **B1** legal-action API + O(1) fork (`reset/step/observe/legalActions`, immutable state) — design borrowed from Argentum, reimplement-with-attribution (no direct copy; it is unlicensed).
- **B2** stack-priority decision loop wiring the existing `stack.py` (open-mtg pass-loop pattern) — note instant-speed combat falls out for free.
- **B3** hidden-info masking + determinization scaffolding.
- Define the **ISMCTS-on-mtg-sim** interface (PUCT; APLs as rollout priors; GBM as leaf evaluator) so the search layer drops onto B1-B3 later.
Capture the licensing posture explicitly: every engine recommendation is **reimplement-from-ideas with attribution** — MIT repos are wrong-language/stale, Argentum (the right-language one) is unlicensed, Forge is GPL (behavior/oracle reference only, never linked).

**Expected artifact:** `harness/specs/2026-06-26-engine-axis-b-search-spine.md` (status PROPOSED) with sized work items (B1/B2/B3 each L-XL), the dependency graph, the API surface sketch, and the ISMCTS layering diagram.

**Verify:** Spec exists, states the L2→L3→L4 hard dependency order, sizes each long pole as multi-week, and contains no instruction to write engine code this session (it is a plan, not an implementation). A reader can pick up B1 from the spec without re-deriving the design.

---

## 4. RISKS / OPEN QUESTIONS (for the user to decide)

1. **THE STRATEGIC FORK — bot-first vs trust-first.** North star = the bot → run Axis B spine (B1→B2→B3→search) as primary, Axis A in parallel. But if the near-term goal is *trustworthy meta/RC-prep WR this quarter*, do Axis A first (PW → warp → stack-priority) and defer the full search layer. This roadmap assumes **bot-first** per the stated north star; confirm. (Note: the RC dates in memory, ~May 15 / May 29, are already past 2026-06-26 — do not anchor urgency on them.)
2. **Licensing posture on the engine.** Every engine borrow is reimplement-from-ideas-with-attribution: Argentum (the ideal Kotlin reference) is **unlicensed**, Forge is **GPL** (copyleft trap — oracle/validation only, never linked). Confirm we never link or copy, only reimplement. Also: add a LICENSE to claude-harness + TeamResolve before any dynamic license badge.
3. **No-GPU constraint on ML.** ModernBERT fine-tune needs a GPU (philschmid used an L4); plan routes training to Colab/Gemma box and ships an inference artifact. Confirm that's acceptable, and that the fine-tune is worth it given signature rules already resolve most decks (lift is only on the KNN fallback tail).
4. **Ollama VRAM ceiling.** The 14B cannot fully fit 10GB (16% CPU offload persists); Wave 1 minimizes swaps/truncation but does not eliminate the offload. Eliminating it needs C2 (pull qwen2.5-coder:7b or quantize) — benchmark-gated, deferred. Approve the 7b pull?
5. **Phone app backend ownership.** Read-only meta needs no server (v0 PWA is offline), but personal/team match-log sync (Tier3 FastAPI) needs an always-on host + auth/privacy decisions once data leaves the device. Defer to post-v0, or stand up Tier3 now?
6. **Search-layer realism check.** ISMCTS quality is bounded by L1 fidelity — PW/warp gaps bias the WR the bot optimizes against. Decide whether Axis A fidelity must reach a bar (e.g. warp modeled) *before* the search layer's output is trusted for deckbuilding/SB advice.

---

*Synthesized 2026-06-26 by the program architect from six grounded research evaluations. Audit corrections honored: FastMCP 3.x is GA; ratloop has no calibration code; scryfall-mcp is Apache-2.0; KaminaDuck=Apache-2.0, j4th=MIT, artillect/Argentum=unlicensed, Forge=GPL.*
