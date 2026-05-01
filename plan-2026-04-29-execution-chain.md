# Execution chain: 2026-04-29 (Wednesday)

**Created:** 2026-04-28 ~end-of-day by claude.ai
**Updated:** 2026-04-28 ~end-of-day (re-scoped to 9-hour budget per user signal; added Section 0 inbox-processing)
**Target executor:** fresh Claude Code session
**Estimated wall time:** 8-10 hours (matches today's 9-hour budget; includes stop-and-discuss between specs)
**Source:** session-end handoff from claude.ai conversation that shipped 7 specs today (2026-04-28)

## Read me first

Tomorrow's specs are paste-ready on disk. This file is the recommended ordering with rationale. Fresh session should:

1. Read `harness/state/latest-snapshot.md` first per `harness/CLAUDE.md` SESSION START PROTOCOL.
2. **Read `harness/inbox/` next** — the 04:50 Gemma drift PR will be there. Process recommendations into chain (some may slot in cleanly, some may need new IMPERFECTIONS entries, some may suggest re-ordering this chain). Don't skip this even if the chain looks complete on disk; Gemma's overnight analysis frequently surfaces things humans miss.
3. Read `harness/IMPERFECTIONS.md` (6 OPEN entries — 5 are addressed by tomorrow's specs; 1 is `oauth-vs-raw-v1-messages-compat-unverified` which is its own spec).
4. Read this file as the day's execution plan.

## State carried forward from 2026-04-28

7 specs SHIPPED today (in execution order):

1. `tagger-load-path-unification` at commit `199d28e` — RESOLVED
2. `stage-1.7-event-bus-determinism` at commit `30c992a` — RESOLVED (closed Stage C A6)
3. `auto-pipeline-nightly-integration` (harness, no commit) — RESOLVED
4. `auto-pipeline-output-flow-to-retune` at commit `1a4f97a` — RESOLVED
5. `cache-key-audit-mtg-sim` (harness, no commit) — RESOLVED, opened 5 IMPERFECTIONS
6. `drift-detect-7th-check-cache-key-audit` (harness, no commit) — RESOLVED
7. `gexf-converter` (harness, no commit) — RESOLVED

8 mtg-sim commits today total. 17 v1.5 lessons in spec-authoring-lessons.md.
Bit-stable canonical 64.5% / variant 78.8% baseline locked at HEAD=`30c992a`.

**6 OPEN imperfections at session end** — all addressed by tomorrow's specs:

- `drift-detect-arch-staleness-false-positive-on-non-canonical-runs` → spec #2
- `sim-matchup-matrix-rmw-race` (active, MEDIUM) → spec #3
- `auto-apl-registry-rmw-race-latent` → spec #3 (folded)
- `optimization-memory-rmw-race-latent` → spec #3 (folded)
- `gemma-apl-quality-low-for-smoke-gate` → spec #4
- `oauth-vs-raw-v1-messages-compat-unverified` → spec #1

## Specs PROPOSED for tomorrow (8 total + sibling-7th already on disk)

| # | Spec | File | Effort | Risk | Resolves |
|---|---|---|---|---|---|
| 0 | Session start (inbox + snapshot) | (procedural, this doc) | 15-30 min | n/a | n/a |
| 1 | OAuth-token compat probe | `2026-04-29-oauth-token-compat-probe.md` | 5-10 min | MINIMAL | 1 IMPERFECTION |
| 2 | Drift-detect ARCH-staleness fix | `2026-04-29-drift-detect-arch-staleness-fix.md` | 15-30 min | LOW | 1 IMPERFECTION |
| 3 | RMW-race cluster fix | `2026-04-29-rmw-race-cluster-fix.md` | 45-75 min | MEDIUM | 3 IMPERFECTIONS |
| 4 | Gemma APL quality lift | `2026-04-29-gemma-apl-quality-lift.md` | 45-90 min | MEDIUM | 1 IMPERFECTION |
| 5 | Drift-detect 8th check (RMW pattern) | `2026-04-29-drift-detect-8th-check-rmw-pattern.md` | 45-75 min | LOW | None (mechanizes) |
| 6 | Sibling 7th check (spec validation) | `2026-04-28-drift-detect-7th-check-spec-validation.md` (already PROPOSED) | 60-90 min | LOW | None (mechanizes) |
| 7 | Within-matchup parallelism | `2026-04-29-within-matchup-parallelism.md` | 60-90 min | MEDIUM | None (Stage 1.7 unblock) |
| 8 | Stage A/B 100k re-validation | `2026-04-29-stage-ab-100k-revalidation.md` | 90-120 min | LOW | None (RC DC prep) |
| 9 | Friday PT-readiness verification | `2026-04-29-friday-pt-readiness.md` | 30-45 min | MINIMAL | None (proactive) |

**Totals at the high end:** ~7-9 hours of pure execution + ~1 hour of stop-and-discuss = ~9 hours wall.

## Recommended execution chain (Option A — Full 9-hour day)

Stop and report between sections (not necessarily between every spec within a section). Within each spec, complete all sub-stages before stopping.

### Section 0 — Session start (~15-30 min)

- Read snapshot (`harness/state/latest-snapshot.md`) per protocol
- Read inbox: `drift-pr--2026-04-29.md` (Gemma overnight analysis, lands ~04:50)
- Process inbox recommendations:
  - If recommendation aligns with chain item below: confirm and proceed
  - If recommendation is new: open IMPERFECTION and decide whether to slot in or defer
  - If recommendation contradicts chain ordering: stop, surface, decide
- Move processed inbox files to `harness/inbox/processed/`
- Confirm baseline state: `git status` clean, drift-detect runs (1 cosmetic WARN expected pre-spec-#2), bit-stable smoke (run `parallel_launcher.py --deck "Boros Energy" --format modern --n 1000 --seed 42` twice, confirm bit-identical aggregate)

**[STOP — surface anything overnight surfaced; confirm proceed]**

### Section 1 — Quick wins (~25-50 min total)

1. **OAuth probe** (#1, 5-10 min) — settles auth question first; informs decisions in #4
2. **Drift-detect ARCH fix** (#2, 15-30 min) — quick win, removes the persistent WARN

**[STOP — section 1 close; confirm proceed to section 2]**

### Section 2 — Foundational fixes (~90-165 min total)

3. **RMW-race cluster fix** (#3, 45-75 min) — closes 3 IMPERFECTIONS in one fix
4. **Gemma APL quality lift** (#4, 45-90 min) — converts auto-pipeline from inert to producing-value

**[STOP — section 2 close; bigger checkpoint, baseline integrity confirmed]**

### Section 3 — Tooling expansion (~165-255 min total)

5. **Drift-detect 8th check (RMW pattern)** (#5, 45-75 min) — companion to #3; catches future regressions
6. **Sibling 7th check (spec validation)** (#6, 60-90 min) — was on disk already; validates spec content for fictional paths/flags
7. **Within-matchup parallelism** (#7, 60-90 min) — pure compounding infra; Stage 1.7 unblock

**[STOP — section 3 close; tooling layer fully expanded]**

### Section 4 — Validation + Friday prep (~120-165 min total)

8. **Stage A/B 100k re-validation** (#8, 90-120 min) — anchors competitive prep numbers at full precision; mostly gauntlet wall time so partial-attention compatible
9. **Friday PT-readiness verification** (#9, 30-45 min) — pre-flight before Friday's PT data

**[STOP — chain complete; final state report]**

## Recommended execution chain (Option B — Friday-leverage focused, ~3-4 hours)

If tomorrow has limited time or competing priorities:

1. Section 0 (mandatory)
2. **OAuth probe** (#1)
3. **Drift-detect ARCH fix** (#2)
4. **Gemma APL quality lift** (#4) — direct Friday-leverage
5. **Friday PT-readiness verification** (#9) — small but high-value

Defers RMW-race cluster + tooling expansion + 100k validation + parallelism to later in the week. Risk: matrix-RMW could fire during Friday's heavy gauntlet load (soft failure, re-run recovers).

## Recommended execution chain (Option C — Conservative low-risk, ~1-2 hours)

If tomorrow gets disrupted:

1. Section 0 (mandatory)
2. **OAuth probe** (#1)
3. **Drift-detect ARCH fix** (#2)
4. **Friday PT-readiness verification** (#9) — make sure Friday is safe even if no other work lands

## My recommendation: Option A in the listed order

Reasons:
- Today's 9-hour scope was exactly the right shape; tomorrow is similarly available
- The OPEN imperfection list (6 entries) gets reduced to 0-1 by end of day
- Tooling layer (specs #5, #6) compounds across all future work
- 100k re-validation (#8) anchors competitive prep numbers BEFORE PT introduces meta noise
- Friday PT-readiness (#9) is the last-easy-day verification that scheduled tasks won't surprise on Friday

Realistic deviation: section 3 spec #7 (parallelism) is the most-skippable if time pressure rises. It's pure compounding infra, not Friday-relevant. If chain runs long, drop #7 and ship #8 + #9.

## Stop conditions across the chain

Standard stop-and-discuss between sections per established discipline. Plus:

- **If overnight inbox surfaces a P0:** STOP, address it first, re-scope chain
- **If OAuth probe (#1) returns network failure:** STOP, surface, this becomes its own diagnostic
- **If RMW-race fix (#3) Gate 3 (concurrent gauntlet test) shows missing rows:** STOP, atomic-write retry loop is insufficient
- **If Gemma quality lift (#4) Gate 3 still shows 0/3 pass rate after ICL changes:** STOP, document new failure modes, decide between option 3 (auto-fix) or pivot to Claude path (informed by #1's outcome)
- **If parallelism (#7) Gate 2 fails (worker count affects aggregate):** STOP, do not ship. Determinism is non-negotiable.
- **If 100k re-validation (#8) shows >2pp deviation from 1k baseline:** STOP, surface; could be sample noise OR could indicate a real subset effect not captured at n=1k OR engine evolution — needs investigation before being trusted as new baseline.
- **If Friday-readiness (#9) surfaces broken scheduled task:** STOP, fix becomes Thursday-priority not future-priority

## Reporting expectations at each stop

Same as today's pattern:
- What got done (commit hashes if applicable)
- Validation gate results
- Anything unexpected
- IMPERFECTIONS state delta (closed / opened / updated)
- Confidence on proceeding to next section

## Methodology notes for tomorrow

- **No v1.5 lesson compounding expected from any of these specs alone.** None are first-instance of a new generalization. Most are confirming cases of existing v1.4/v1.5 lessons. If a third-instance pattern surfaces (e.g., "feature-flagged default-off opt-in" appears in a third spec), that becomes a v1.6 candidate; apply Rule 9 (validate before compound).
- **Today's `parallel-entry-points-need-mirror-fix` v1.5 lesson is directly applicable to specs #3 and #7.** Both have parallel entry points. Apply explicitly in pre-flight checks.
- **Bit-stable baseline is the regression-detection net for #3, #7, and #8.** All three include "production gauntlet bit-identical / within ±X" as a validation gate. If anything drops below 64.5% / 78.8%, that's a regression signal independent of the spec's own gates.
- **Section 0 inbox processing is mandatory, not optional.** Today's morning Gemma drift PR independently aligned with the chain ordering, which was a positive validation signal. If tomorrow's PR diverges from the chain, that's important information; if it converges, that's confirming evidence. Either way, read it.

## Coverage of all 6 OPEN imperfections

| Imperfection | Resolved by spec | Notes |
|---|---|---|
| `oauth-vs-raw-v1-messages-compat-unverified` | #1 | Smallest spec, runs first |
| `drift-detect-arch-staleness-false-positive` | #2 | Quick win |
| `sim-matchup-matrix-rmw-race` | #3 | Active hazard |
| `auto-apl-registry-rmw-race-latent` | #3 (folded) | Same fix pattern |
| `optimization-memory-rmw-race-latent` | #3 (folded) | Same fix pattern |
| `gemma-apl-quality-low-for-smoke-gate` | #4 | Friday-leverage |

End-of-tomorrow IMPERFECTIONS count target: **0 OPEN** if all of Sections 1-2 ship. Tooling/validation specs (#5-9) don't open new IMPERFECTIONS (mechanization + verification, not new findings).

## Changelog

- 2026-04-28 ~end-of-day: Chain v1 authored by claude.ai. 5 specs scoped at 1.5-5 hours.
- 2026-04-28 ~end-of-day v2: Re-scoped to 9-hour budget per user signal. Added Section 0 (inbox processing + session start). Added 3 specs (#5 RMW-pattern detector, #8 100k re-validation, #9 Friday PT-readiness). Slotted in already-on-disk #6 (sibling 7th-check). Three sequencing options retained.
