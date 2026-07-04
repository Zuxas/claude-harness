---
name: council-2026-07-04-loop-engineering-handoff
description: Council verdict verifying the disposition of the loop-engineering handoff's 6 items against live harness state
metadata:
  type: reference
---

## COUNCIL VERDICT: how to dispose of the loop-engineering handoff's 6 items (A-F)

**Date:** 2026-07-04 | **Seats:** 4 (Analyst, Contrarian, Empiricist + cross-vendor Codex/gpt-5.5) | **Blind:** y (seats classified independently, not shown the orchestrator's dispositions) | **Vendors:** Anthropic x3 + OpenAI x1

**Question:** For each of the handoff's 6 candidate items, is it ALREADY BUILT, should it FOLD into the in-progress research-brain spec, or DEFER to a separate spec? And does the current spec miss a real gap?

### Per-item verdict (evidence-weighed, not vote-counted)
- **A (gated write-back) — ABSORBED + real gap.** SP-2/SP-5 already implement the 3-bucket + council-as-independent-verifier for research FACTS (spec:103-120). But NO part requires a **numeric eval gate** for changes touching sim code or a skill (Empiricist CONFIRMED; Codex + Contrarian concur). The handoff's load-bearing insight is uncovered.
- **B (loop-that-manages-loops) — DEFER broad form, FOLD a minimal sliver.** `drift-detect.ps1` does imperfections-health + loose-ends only; it does NOT check scheduled-loop liveness/log-health or cross-skill dup logic (Empiricist + Codex CONFIRMED absent). Contrarian's decisive point: the spec is about to ADD scheduled loops (SP-4 05:10 task, SP-5 weekly), and a silently-dead local-only ingest job is the exact failure mode — so a MINIMAL liveness/"did it run + log today" check should ship WITH SP-4, not defer. Broad dup-detection/composability -> separate hygiene spec.
- **C (numeric-gated overnight optimization) — ALREADY BUILT (ARL), with a caveat.** ARL empirically exists and is numeric-gated (Empiricist: `arl_loop.py:1-20,50-51` >8pp variance gate; Codex: `arl_loop.py:6-19,1113-1186`, `arl-spec.md`; generate->smoke->gauntlet->evaluate->promote/mutate/discard). OUT OF SCOPE for the research-brain spec regardless. CAVEAT (Contrarian, unresolved): the ARL does archetype GENERATION; item C is directed SINGLE-DECK event-prep TUNING, and the old `tuning_loop.py` was "superseded" by the ARL. Whether directed single-deck tuning is a live ARL mode or a dropped capability is UNVERIFIED — a separate sim question, not this spec's.
- **D (per-skill gotchas) — DEFER.** Skill-system hygiene; project-level analogue (IMPERFECTIONS + spec-lessons) exists, per-skill blocks don't. All seats agree.
- **E (description-as-trigger audit) — DEFER.** Skill-menu quality, orthogonal to research ingestion. All seats agree.
- **F (automate-vs-augment rule) — FOLD as an explicit boundary rule (NOT defer).** Codex + Contrarian: F's taste-test/80-20 filter is exactly the decision of whether SP-4/SP-5 should be scheduled at all; cheap to record. Analyst dissents (spec already embodies it implicitly) — resolved by writing it as a one-line decision-record justifying SP-4=automate / SP-5=proposal-only.

### Where the council corrected the orchestrator's draft dispositions
1. **Eval gate: upgrade from "a note" to a scoped STOP CONDITION** (Contrarian + Empiricist + Codex). Per Rule 4, it belongs in the spec's Stop-conditions block: *any mined proposal that would edit sim code or a skill must re-pass the relevant numeric regression (lint-mtg-sim / goldfish band / gauntlet WR / drift <= 0.05) before it is applied.* Scope it to code/skill-touching changes so it does NOT misfire on pure-prose/knowledge proposals (Analyst's valid caveat: skill-description edits are taste-based, non-numeric; the human is the verifier there).
2. **B: partial fold, not full defer** — ship a minimal scheduled-loop liveness/log-health check with SP-4; defer only the broad dup-detection form.
3. **F: fold, not defer** — one-line automate-vs-augment decision record.

### Where the council agreed with the draft
- C is out of scope here (ARL exists); don't rebuild.
- D/E defer; folding B/D/E/F's broad forms into this spec WOULD be scope creep.
- "Don't over-build loops" holds — but Contrarian flags it was being misused to defer B, the one item that guards the loops being added.

### Blind spots / unverified TODOs
- **Directed single-deck event-prep tuning vs ARL generation** — is it a live ARL mode or a capability dropped when `tuning_loop.py` was superseded? Check `arl_loop.py` for a directed-metric mode before ever concluding item C is fully redundant. (Separate sim task.)

### EVIDENCE INDEX
- `E:\tools\handoff-loop-engineering-synthesis.md` (items A-F; L73-76 eval-gate, L88-89 loop-liveness, L98-111 item C, L133-135 F filter, L152-153 do-not).
- `harness/specs/2026-07-03-research-brain-integration.md:94,103-120,150-160,167-200` (SP-2 3-bucket, SP-5 proposal-only, gates G1-G9, stop conditions).
- `harness/HARNESS_STATUS.md` current-state ARL note; `mtg-sim/scripts/arl_loop.py:1-20,50-51,1113-1186`; `mtg-sim/docs/arl-spec.md`; `tuning_loop.py` (superseded Layer-3).
- `harness/scripts/drift-detect.ps1` (imperfections-health + loose-ends; no loop-liveness/dup-detection).
- `harness/CLAUDE.md:14` (Gemma drift PR = signoff-only, not auto-applied — CONFIRMED proto).

### CHANGELOG
- 2026-07-04: created. Verifies disposition of loop-engineering handoff items; corrected orchestrator on eval-gate (->stop condition), B (->partial fold), F (->fold).
