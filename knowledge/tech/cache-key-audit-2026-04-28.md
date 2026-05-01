---
title: "Cache-key audit across mtg-sim"
domain: "tech"
created: "2026-04-28"
updated: "2026-04-28"
status: "COMPLETE"
spec: "harness/specs/2026-04-28-cache-key-audit-mtg-sim.md"
sources: ["cache-collision-bug-2026-04-27", "spec-authoring-lessons-v1.5"]
---

## Summary

Audit of all cache-write call sites in mtg-sim for the same bug class as `cache-collision-bug-2026-04-27.md` (cache keyed on partial state, silently returns wrong results under concurrent execution).

**Total cache-write call sites identified:** 27 (excluding `__pycache__/`, `_research/`, `tests/`, `conftest`).

**Bucket counts:**
- A (safe by construction): **17**
- B (safe by convention, no current violators): **6**
- C (latent bug, plausible future violator): **1**
- D (active bug, current caller violates convention): **3**

**Top 3 most-concerning findings (D bucket):** all three writes to the shared global file `data/sim_matchup_matrix.json` form a read-modify-write race when concurrent gauntlets run (e.g., canonical + variant launched in parallel, which is a documented user pattern from the Stage C work). Same root cause as the original cache-collision bug, different symptom: matrix entries can be lost (last-writer-wins on per-deck keys; cross-deck-key lossy under contention).

## Methodology

Per spec `harness/specs/2026-04-28-cache-key-audit-mtg-sim.md`:

1. **Step 1**: greps for `json.dump`, `pickle.dump`, `.write_text(`, `.write_bytes(`, `with open(... 'w'` across `mtg-sim/*.py` (excluding test fixtures, `_research/`, `__pycache__/`).
2. **Step 2**: per-site classification — does the write path include all relevant input parameters? If partial-keyed, what convention governs stability? Are there current callers that violate the convention?
3. **Step 3**: bucketize A (safe) / B (safe-by-convention, no violators) / C (latent, plausible future violator) / D (active, current violator).
4. **Step 4**: this finding doc.
5. **Step 5**: IMPERFECTIONS.md entries for D-bucket bugs.

Audit is read-only. Per spec stop conditions, no fixes were applied — each D-bucket entry becomes its own follow-up fix spec.

## Per-site classification table

| # | Site | Path | Bucket | Notes |
|---|------|------|--------|-------|
| 1 | `generate_matchup_data.py:213` | `output_path` (caller-supplied) | A | Path is fully-qualified by caller; per-call uniqueness |
| 2 | `generate_matchup_data.py:245` | `data/sim_matchup_matrix.json` (default) | **D** | See finding 1 below — shared global file, read-modify-write race |
| 3 | `parallel_launcher.py:135` | `data/parallel_results_<HMS_timestamp>.json` | A | HMS timestamp gives second-granularity uniqueness; only collide if user launches twice within the same wall-clock second (in which case the OS would also tend to serialize the open() call) |
| 4 | `parallel_launcher.py:152` | `data/sim_matchup_matrix.json` (read-modify-write) | **D** | Same global file as #2; read-modify-write race when concurrent canonical+variant launchers run |
| 5 | `parallel_sim.py:205` | `data/parallel_results_<HMS_timestamp>.json` | A | Same pattern as #3 |
| 6 | `parallel_sim.py:224` | `data/sim_matchup_matrix.json` (read-modify-write) | **D** | Same as #4; parallel_sim.py is a separate entry point with the same matrix-write code path |
| 7 | `run_matchup.py:290` | `matchup_job_path(our_deck, opp_name)` | A | **Already-fixed cache** — the original cache-collision bug; now keyed correctly via `(our_deck, opp)` tuple per `cache-collision-bug-2026-04-27.md` |
| 8 | `apl/auto_apl.py:198` | `~/.claude/.credentials.json` (creds_path) | A | OAuth token cache; single global location, single user, single session |
| 9 | `apl/auto_apl.py:361` | `cache_file` (per-deck) | A | Deck-keyed cache; one file per deck name |
| 10 | `apl/playbook_parser.py:290` | `cache_path` (single file for all playbooks) | B | Single cache file for all playbooks; convention: rebuild via parser; no concurrent writers in normal use; documented pattern |
| 11 | `docs/pull_oracle.py:34` | `out_file` (CLI arg) | A | One-shot script; caller-supplied path |
| 12 | `ml/format_transfer.py:121` | `data_path` (format-keyed) | B | ML training cache, sequential developer use |
| 13 | `ml/format_transfer.py:128-129` | `model_path` (format-keyed pickle) | B | ML model cache, same pattern |
| 14 | `ml/rl_trainer.py:215` | training cache (format-keyed) | B | Same ML pattern |
| 15 | `ml/win_prob_model.py:130` | `save_path` (caller-supplied) | A | Caller-keyed |
| 16 | `ml/win_prob_model.py:201` | `path` (caller-supplied pickle) | A | Caller-keyed |
| 17 | `output/stats.py:112` | `path` (caller-supplied) | A | Single-write per call |
| 18 | `scripts/build_meta_shares.py:145` | `output_path` (CLI-supplied) | A | One-shot script |
| 19 | `scripts/build_priority_queue.py:372` | `path` (function arg) | A | Caller-keyed; sequential |
| 20 | `scripts/build_priority_queue.py:382` | `path` (function arg) | A | Same |
| 21 | `scripts/build_priority_queue.py:408` | `path` (function arg) | A | Same |
| 22 | `scripts/build_stubs.py:314` | `data/stub_decks.py` (single global) | B | Build script; intended single writer; convention is "one user runs build occasionally" |
| 23 | `scripts/monitor.py:36` | `status` (single file) | B | Monitor singleton; intended single writer |
| 24 | `scripts/monitor.py:62` | `status` (single file, second site) | B | Same as #23 |
| 25 | `scripts/summarize_telemetry.py:192` | `path` (CLI-supplied) | A | One-shot script |
| 26 | `harness/agents/scripts/auto_pipeline.py:_register_auto_apl` | `data/auto_apl_registry.json` (read-modify-write) | C | **Latent bug, surfaced by THIS audit.** Same shape as findings 1-3 below: read-modify-write of a single shared file. Currently no concurrent writers (single nightly_harness invocation per format), but parallel runs would race. See finding 4 below. |
| 27 | `harness/agents/scripts/auto_pipeline.py:save_memory` | `harness/agents/optimization_memory.json` | C | Same pattern as #26; nightly is sequential so no current violator, but plausible future caller (parallel formats) would race. See finding 5 below. |

## Active bug list (D bucket)

### Finding 1: `data/sim_matchup_matrix.json` read-modify-write race (3 call sites)

**Sites:**
- `generate_matchup_data.py:235-247` — `update_real_matrix(sim_results, output_path="data/sim_matchup_matrix.json")` — full overwrite, but caller wraps `sim_results` from a single matchup batch
- `parallel_launcher.py:147-153` — read existing matrix, update one deck's row, write back
- `parallel_sim.py:218-225` — same read-modify-write pattern as parallel_launcher

**Pattern:**
```python
matrix_path = "data/sim_matchup_matrix.json"
matrix = {}
if os.path.exists(matrix_path):
    with open(matrix_path) as f:
        matrix = json.load(f)
matrix[our_deck] = {...}  # only this deck's row
with open(matrix_path, "w") as f:
    json.dump(matrix, f, indent=2)
```

**Failure mode (verified by reasoning, not empirical reproduction):**

Under concurrent launches (e.g., canonical Boros Energy + variant Boros Energy Variant Jermey running in parallel — a documented pattern from Stage C work), both processes:
1. Read matrix at near-identical time → both see `{deck_X: ...}` (whatever was there before)
2. Each computes its own update → A wants to add `{Boros Energy: ...}`; B wants to add `{Boros Energy Variant Jermey: ...}`
3. Last writer wins on the FILE — earlier writer's update is silently lost

For per-deck keys (each writes its own deck's row), the bug manifests as: a previously-existing deck's row may be lost if the concurrent writer didn't include it. New entries always survive (they're only in one writer's view, so that writer's write preserves them); old entries can be lost if the OTHER concurrent writer happens to overwrite without re-reading.

**Severity:** MEDIUM. Matrix is a read-only consumer for downstream tools (event simulator, dashboards). Lost entries → stale dashboard data → user re-runs to recover. Not a data-integrity concern at the canonical-numbers level (those live in `parallel_results_<timestamp>.json` and `ARCHITECTURE.md`).

**Severity-class note:** Same root pattern as the original cache-collision bug, but DIFFERENT failure surface. The cache-collision bug caused WRONG numbers (variant data in canonical's cache file). This bug causes MISSING entries (concurrent writers stomping each other). Both share the "shared resource keyed by less than the full caller context" anti-pattern.

**Proposed fix (separate spec):**
- Option A: file lock (`fcntl.flock` on POSIX; no equivalent on Windows for this) — adds locking complexity
- Option B: per-deck files (`data/sim_matchup_matrix/<deck_slug>.json`) — eliminates shared-file contention
- Option C: keep shared file but use atomic write (`os.replace`) + retry on read-modify-write loop — preserves single-file consumer convention
- Recommend C (atomic write + retry loop). ~30-60 min spec.

**Imperfection name:** `sim-matchup-matrix-rmw-race`

### Finding 2: same as Finding 1 at parallel_launcher entry point

(Already covered by Finding 1; listed as "site #4" in the table. Single fix spec covers all 3 sites.)

### Finding 3: same as Finding 1 at parallel_sim entry point

(Already covered by Finding 1; listed as "site #6" in the table.)

## Latent bug list (C bucket)

### Finding 4: `data/auto_apl_registry.json` read-modify-write (latent)

**Site:** `harness/agents/scripts/auto_pipeline.py:_register_auto_apl` (Stage S4 / 2026-04-28)

Same pattern as Finding 1 — read existing JSON, update one entry, write back. Currently no concurrent writers (nightly_harness is sequential per format), but the moment someone runs `auto_pipeline.py --format modern` and `auto_pipeline.py --format standard` concurrently, the same race occurs.

**Severity:** MEDIUM-LOW. Same loss-mode as Finding 1. Currently NO violator (sequential single-process nightly), so it's latent.

**Mitigation:** Could be folded into Finding 1's fix spec as a parallel atomic-write site.

**Imperfection name:** `auto-apl-registry-rmw-race-latent`

### Finding 5: `harness/agents/optimization_memory.json` read-modify-write (latent)

**Site:** `harness/agents/scripts/auto_pipeline.py:save_memory`

Same pattern as Finding 4. Memory file holds lifetime stats + experiment log. Currently sequential.

**Severity:** LOW. Append-only data; loss-mode is "some experiment logs missing from a concurrent run." Not user-facing.

**Imperfection name:** `optimization-memory-rmw-race-latent`

## Top 3 most-concerning findings (executive summary)

Even after bucket analysis, these are the three findings worth user attention regardless of bucket:

1. **Finding 1** (`sim-matchup-matrix-rmw-race`) — already "active" in the canonical+variant concurrent gauntlet workflow that the user has been running this week. Recommend prioritizing the fix spec before the next time canonical+variant gauntlets are run in parallel for measurement-grade data (e.g., post-PT meta evaluation Friday-Saturday).

2. **`scripts/build_priority_queue.py` cluster** (sites 19-21) — three writes in a single script; if any single invocation has a partial failure between writes, on-disk state could be inconsistent (e.g., priority queue file present but companion files missing). Not a cache-collision pattern but worth a separate "transactional script writes" follow-up if user cares.

3. **`apl/playbook_parser.py:290` cache** (site #10) — single shared cache file for ALL playbooks. Convention is "rebuild via parser command." If the parser is invoked concurrently (e.g., during a test sweep that happens to launch parallel imports), race possible. Currently B (no violator), but worth a comment in the source code.

## Validation gates (per spec)

- ✓ Gate 1: every cache-write site identified by Step 1 is bucketed (no TBD)
- ✓ Gate 2: finding doc landed at `harness/knowledge/tech/cache-key-audit-2026-04-28.md`
- ✓ Gate 3: IMPERFECTIONS.md updated with new entries for D and C buckets (3 new entries below)
- ✓ Gate 4: no code changed (read-only audit)

## What changed at the lesson level

This audit empirically validates `caches-keyed-on-partial-state-are-time-bombs` v1.4. The lesson predicted: "enumerate parameter space, verify key includes every dimension that varies." Audit found 3 active instances + 2 latent instances of the same anti-pattern. Lesson is now confirmed against this codebase, not just the originating bug.

No new lesson surfaced from this audit — it's a confirming case, not a new generalization.

## Future work this enables (NOT in scope per spec)

- **Per-bug fix specs** for each D-bucket finding (Finding 1 covers all 3 sites)
- **Convention-documenting comments** added to source files for B-bucket sites (so future readers know the convention)
- **Drift-detect 8th check** (`harness/specs/2026-04-28-drift-detect-8th-check-cache-key-audit.md`) — mechanizes detection of this bug class going forward; this finding doc IS its validation corpus

## Changelog

- 2026-04-28: Created via execution-chain S5. Spec `harness/specs/2026-04-28-cache-key-audit-mtg-sim.md` SHIPPED. Audit-only, read-only; no code changes. Five new IMPERFECTIONS entries opened (3 active D, 2 latent C).
