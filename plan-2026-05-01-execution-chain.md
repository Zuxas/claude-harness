# Execution chain: 2026-05-01 (Thursday — PT Strixhaven Day 1)

**Created:** 2026-05-01 morning by Claude Code (late — authored at session start, not prior evening; acknowledged as protocol miss)
**Target executor:** current Claude Code session
**Estimated wall time:** ~4 hours active work; rest is PT watch + nightly automation
**Hard deadline:** meta_analyzer date fix BEFORE 5PM scrape

## Context

This chain was not authored at yesterday's session end (protocol miss). It is being authored now based on:
- `harness/MEMORY.md` session log (2026-04-30 + 2026-05-01 entries)
- `harness/plan-2026-04-30-execution-chain.md` (yesterday's planned chain)
- `harness/IMPERFECTIONS.md` (open items)
- `harness/specs/_index.md` (spec status)

Yesterday shipped significantly more than the planned chain (unplanned sessions: strategic ROADMAP, CI/CD pipeline, harness git push, tools expansion, Event Hub session 1). One planned item did NOT ship: **Spec #8 (100k re-validation)**. One tagged commit was left incomplete: **Izzet Prowess Lava Dart flashback part 2**.

Today is PT-constrained. The nightly automation handles the PT data pipeline automatically once it lands. Work before 5PM should be self-contained, non-canonical-shifting (nothing that would corrupt a gauntlet if interrupted), and ideally closes durable backlog items.

---

## PT Day 1 pipeline (automatic — no manual intervention needed)

| Time | Event |
|---|---|
| ~5:00 PM | meta-analyzer scraper pulls PT Strixhaven Day 1 decklists |
| 5:30 PM | Zuxas-Harness-Nightly-Modern (Modern retune) |
| 6:30 PM | Zuxas-Harness-Nightly-Standard (Standard retune + auto-pipeline) |

auto-pipeline flags for tonight: `--enable-auto-pipeline --auto-pipeline-use-claude` — safe, verified working as of 2026-04-30.

---

## Pre-conditions

1. Read `harness/state/latest-snapshot.md` (done — snapshot dated 2026-04-30 15:44; stale but acceptable given CI/CD session filled the gap)
2. Read `harness/inbox/drift-pr--2026-04-30.md` (done — Gemma recommendations reviewed)
3. Read `harness/MEMORY.md` (done)
4. Read `harness/IMPERFECTIONS.md` (done)
5. Read this file

---

## Specs in scope today

| # | Item | Type | Effort | Risk | Notes |
|---|---|---|---|---|---|
| 1 | **meta_analyzer Standard date fix** | bug fix | ~30 min | LOW | **MUST SHIP BEFORE 5PM** |
| 2 | `has-keyword-attribute-mismatch` engine fix | bug fix | ~30 min | LOW | HIGH severity; 5-line fix; doesn't touch canonical match runner |
| 3 | `affinity-never-blocks` blocker logic | APL fix | ~45 min | LOW | 9% meta, inflated BE WR; isolated to `apl/affinity_match.py` |
| 4 | Izzet Prowess Lava Dart flashback part 2 | APL fix | ~20 min | LOW | Finish tagged (1/2) commit b4094cc |
| 5 | Event Hub Session 2 | feature | ~90 min | LOW | Spec: `2026-04-30-event-hub.md`; RC countdown, drive time, conflict detection, post-event enrichment |
| 6 | Post-5PM: Standard gauntlet run | validation | ~30 min active | LOW | Kick off after PT data confirmed in DB |

---

## Execution chain

### Section 0 — Pre-5PM mandatory fix (~30 min)

**Spec #1: meta_analyzer Standard date fix**

- File: `mtg-meta-analyzer/` — locate date parsing for Standard tournament entries
- Bug: dates stored/parsed as DD/MM/YY instead of YYYYMMDD
- Fix: update the date normalization in the scraper/parser so PT data lands in the correct format
- Validation: check existing Standard entries in DB before + after; confirm format consistent with Modern entries
- Commit before proceeding

**Stop condition:** If the fix touches more than date parsing (i.e., schema change needed), STOP and surface. Don't chase schema migrations under a 5PM deadline.

**[STOP — confirm date fix shipped; then proceed to Section 1]**

---

### Section 1 — Engine + APL fixes (~90 min)

**Spec #2: has-keyword-attribute-mismatch**

- File: `engine/match_state.py` — `has_keyword()` function
- Bug: checks `card.keywords` (nonexistent attribute); should check `card.tags`
- Affected paths: `engine/match_engine.py`, `engine/bo3_match.py`, `engine/meta_solver.py`, `engine/parallel_match.py`, `engine/combo_model.py`, `engine/variant.py`
- Fix: replace `card.keywords` lookup with `KWTag.X in card.tags` pattern (same as the working match_runner path)
- Validation: confirm 0 regressions on canonical match_runner path (which already uses correct path); spot-check one of the 6 affected callers
- Estimated effort: ~30 min

**Spec #3: affinity-never-blocks**

- File: `apl/affinity_match.py` — `declare_blockers()` returns `{}`
- Fix: implement blocking logic for Kappa Cannoneer (ward 4, typically 4/4+) and large Arcbound Ravager
- Heuristic: block with creatures whose power exceeds attacker's toughness OR whose toughness exceeds attacker's power, prioritizing highest-value blockers
- Validation: run BE vs Affinity N=200 before + after; expect BE WR to drop from ~96.9% toward a more realistic number (likely 70-80% range)
- Estimated effort: ~45 min

**Spec #4: Izzet Prowess Lava Dart flashback part 2**

- Source: commit b4094cc tagged "(1/2)"
- Read that commit to understand what part 1 did; implement the missing flashback path
- Estimated effort: ~20 min

**[STOP — surface WR delta from Affinity fix; confirm Lava Dart 2/2 complete]**

---

### Section 2 — Event Hub Session 2 (~90 min, if time before PT)

Per spec `2026-04-30-event-hub.md` Session 2 scope:
- RC countdown (days to May 29 RC DC from today's date)
- Drive time / travel info per store/event location
- Conflict detection (overlapping events)
- Post-event enrichment (link results after event concludes)

If 5PM is too close, defer to tomorrow. This is quality-of-life, not PT-critical.

**[STOP at 4:30 PM regardless — confirm all pre-5PM commits are clean]**

---

### Section 3 — Post-5PM PT watch (~30 min active, rest passive)

1. Confirm scraper ran: check `mtg-meta-analyzer/` DB for new Standard entries dated 2026-05-01 with PT source tag
2. Confirm Standard date format is correct on new entries (validate the fix from Section 0)
3. Wait for 5:30 + 6:30 nightly jobs to complete
4. Check nightly report: `harness/knowledge/mtg/nightly-2026-05-01.md`
5. Review auto-pipeline results: did any new PT archetypes get registered?
6. Kick off Standard gauntlet run once PT Standard data is confirmed clean: `python parallel_launcher.py --format standard --n 1000`
7. While gauntlet runs: update MEMORY.md with today's outcomes

---

## Stop conditions (chain-wide)

- Date fix requires schema migration: STOP, surface, defer
- Any engine fix shifts canonical Modern baseline >2pp at N=1000: STOP, document, decide
- Affinity blocking logic produces 0% Affinity WR (logic error): STOP, revert, ship `{}`-returning stub with comment
- PT scraper fails at 5PM: STOP, diagnose, don't run Standard gauntlet on bad data

---

## Deferred (explicitly out of scope today)

- **Spec #8** (100k re-validation) — anchors new post-oracle-sprint baseline; needs clean 2-hour block; tomorrow or weekend
- **Phase 3.5 Stages D-K** — keyword coverage; ongoing, no deadline
- **Pioneer L1 backlog** (57 cards) — no event pressure until after May RC
- **Node.js 24 update** — mandatory before 2026-06-02; schedule this week or next
- **Skill system harness** — spec `2026-05-01-skill-system-harness.md`, earliest 2026-05-05
- **Event Hub Session 2** — defer to tomorrow if 5PM comes before Section 2 completes
- **All Phase 3 structural imperfections** (stack priority, hidden info, instant-speed combat) — multi-week scope

---

## Coverage of open imperfections today

| Imperfection | Addressed by | Expected outcome |
|---|---|---|
| `engine-fidelity-gaps-has-keyword-attribute-mismatch` | Spec #2 | RESOLVED |
| `affinity-never-blocks` | Spec #3 | RESOLVED |
| Izzet Prowess Lava Dart (1/2) tag | Spec #4 | RESOLVED |
| `gemma-apl-quality-low-for-smoke-gate` | PT auto-pipeline tonight | PARTIAL — new PT archetypes may register |

---

## End-of-day checklist (author tomorrow's chain)

Before closing the session tonight, author `harness/plan-2026-05-02-execution-chain.md` covering:
- Spec #8 (100k re-validation) — now the top priority
- Standard gauntlet results from tonight (which archetypes moved?)
- Any new PT archetypes that need APL work
- RC DC deck lock decision (May 11-12; ~10 days out)
- Node.js 24 update (before 2026-06-02)
- Event Hub Session 2 if deferred

---

---

## Actual outcomes (end-of-day 2026-05-01)

**Spec #1 — meta_analyzer date fix:** SHIPPED. `scrapers/mtgtop8.py:_normalize_date()`. PT data landed correctly at 5PM.

**Spec #2 — has-keyword-attribute-mismatch:** NOT A LIVE BUG. `has_keyword()` was already checking `card.tags` correctly at b4384dc (2026-04-29). Spec entry had RESOLVED in header but OPEN in Status field — documentation inconsistency. Closed the stale IMPERFECTIONS entry.

**Spec #3 — affinity-never-blocks:** NOT THE REAL ISSUE. `declare_blockers` was already implemented with blocking logic. The real Affinity problem was `card.colors AttributeError` (see below).

**Spec #4 — Lava Dart (2/2):** SHIPPED. Added flashback-only path in `_use_removal_sparingly`: when Dart is in GY but not hand, flashback still kills 1-toughness targets.

**Event Hub Session 2:** SHIPPED. RC countdown, drive time, conflict detection, Spicerack enrichment.

**Unplanned major work (significantly exceeded scope):**

- **Canonical 100k run:** 68.4% FWR (N=100k, seed=42, 18-deck field). New definitive anchor.

- **Variant 100k run:** First attempt revealed `card.colors AttributeError` crash in `apl/boros_energy.py:817` — `boros_energy.py` used `c.colors` directly; this path is only hit by `GoldfishAdapter(BorosEnergyAPL)` (variant), not canonical `BorosEnergyMatchAPL`. Fixed with `getattr(c, 'colors', None)` pattern. Same fix applied to `apl/elves.py:106`. Second crash found: `list.remove()` raises `AttributeError` in `Card.__eq__` during combat cleanup. Added `_safe_remove()` identity-fallback helper to `engine/match_runner.py`. Post-fix variant 100k: **75.1% FWR**, zero errors. Edge over canonical: +6.7pp.

- **ARCHITECTURE.md:** Both 100k anchors documented (canonical 68.4%, variant 75.1%).

- **Spec #8 SHIPPED:** Stage A/B spec amendments, _index.md moved to SHIPPED, spec status updated.

- **auto_pipeline 6-fix overhaul:** Resolved 7-iteration SOS APL batch failure.
  1. `_call_ollama` streaming mode (Ollama `stream=False` returns empty after heavy load)
  2. `num_ctx=4096` added (Gemma tokenizer produces empty tokens without explicit context window; root cause: 9.5GB/10GB VRAM used after batch, leaving 400MB for KV cache)
  3. `_classify_deck` rewritten to use Qwen2.5-Coder with Python-dict prompt (Gemma broken)
  4. `KEY_CARDS` constant injected into generated APLs from classification result (NameError fix)
  5. Exemplar variable naming: `x` for comprehension items, `c` for loop variable (prevents `card.has()` inside `[c for c in hand if card.has(...)]` NameError)
  6. `_patch_invalid_api_calls()`: strips `cast_spell(target=)`, `is_tapped()`, `is_creature()`, `is_spell()`, bare `type_line`, `gs.hand` no-parens
  7. Missing deck file: `_generate_deck_file_from_db()` must be called before smoke gate (batch script was skipping this — was the root cause of `no_deck_file` status on 8/9 APLs)

- **SOS APL batch (9/9 PASS):** All 9 missing Standard archetypes now have smoke-passing auto-generated APLs in `apl/auto_apls/`. Used Claude OAuth for generation, API patcher for fixup, deck file generation added to batch script.

- **Documentation:** NEXT_STEPS.md + ROADMAP.md updated in both repos. mtg-sim ROADMAP.md current-state header added.

**Deferred items shipped (not in original scope):**
- Spec #8 → SHIPPED ✓
- Variant 100k → SHIPPED ✓ (was "tomorrow" in original chain)

**Items from deferred that remain deferred:**
- Phase 3.5 Stages D-K
- Pioneer L1 backlog
- Node.js 24 update (before 2026-06-02)
- Skill system harness (2026-05-05)
- Phase 3 structural imperfections

**End-of-day deliverables:**
- MEMORY.md updated ✓
- plan-2026-05-02-execution-chain.md authored ✓
- All repos pushed ✓

---

## Changelog

- 2026-05-01 morning: Authored at session start (late — should have been authored end-of-2026-04-30). Protocol miss acknowledged.
- 2026-05-01 end-of-day: Actual outcomes section added. Session ran significantly longer than planned (through ~05:40 AM). All chain items complete + major unplanned work shipped.
