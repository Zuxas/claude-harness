# Spec: Friday PT-readiness verification + Saturday-Sunday plan

**Status:** SHIPPED
**Created:** 2026-04-28 by claude.ai (for tomorrow Wednesday execution)
**Target executor:** Claude Code OR user (mostly observational)
**Estimated effort:** 30-45 minutes
**Risk level:** MINIMAL (read-mostly verification + small config decisions)
**Dependencies:**
- Today's chain (everything shipped 2026-04-28)
- Tomorrow's earlier specs (whichever land before this one runs)
**Resolves:** No OPEN imperfection (proactive PT preparation)

## Goal

Friday May 1 is PT Strixhaven Day 1. Decklists land Friday evening; meta data starts populating in mtg-meta-analyzer DB. Saturday May 2 is Day 2; Sunday May 3 is Day 3 + finals.

This spec is the explicit pre-flight verification that everything needed for unattended PT-watch is in known-good state. It's a checklist, not a code change. Output: a "Friday-readiness verified at <timestamp>" note in MEMORY.md plus any small config flips needed.

The point of running this Wednesday (vs Thursday or Friday morning) is that any gaps surfaced have time to fix without crunch.

After this ships:
- Confidence that Friday's 5pm scrape → 5:30pm Modern nightly → 6:30pm Standard nightly will run cleanly
- Decisions made on whether to enable optional flags (e.g., `--enable-auto-pipeline`) for Friday's runs
- Saturday/Sunday plan documented (what to do with Day 2/Day 3 meta data)

## Pre-flight reads

1. `harness/HARNESS_STATUS.md` Layer 5 section (auto-pipeline wire status, opt-in flags)
2. Today's RESOLVED entries: tagger-fix, Stage 1.7, auto-pipeline integration, auto-pipeline output flow
3. `harness/MEMORY.md` "post-PT pipeline" reference
4. `harness/scripts/register-harness-tasks.ps1` (the scheduled-task definitions; verify what runs Friday)
5. `mtg-meta-analyzer/run_daily.bat` (the scrape pipeline)
6. Bit-stable baseline canonical 64.5% / variant 78.8% (or 100k post-spec-ABrevalidation if that runs first)

## Scope

### In scope
- Verify scheduled-task definitions still match expected commands (the wrapper signature changed today; tasks might or might not pick that up)
- Verify mtg-meta-analyzer scrape pipeline runs cleanly on existing data (re-run today's PT dry run; should be idempotent)
- Verify nightly_harness STEP 1.5 default-off path produces no surprises
- Decision: enable `--enable-auto-pipeline` for Friday's nightly? (Y/N + rationale)
- Decision: bump `--top-n` higher than 3 for Friday given expected PT-emergent archetype count? (estimate +5 to +10 vs default +3)
- Verify auto_apl_registry.json starts empty (no stale APLs from today's smoke-failed attempts blocking new ones)
- Saturday/Sunday plan: when to re-run post-PT meta detection, what to do if Saturday meta is messy
- Document the decisions + verifications in `harness/MEMORY.md` "PT-readiness 2026-04-29" subsection

### Explicitly out of scope
- Any code change (this is verification + config decisions only)
- New architectural work (anything that surfaces as actually-broken becomes a new spec, not in-scope here)
- Decisions about post-PT competitive deck choice — that's a separate strategy session after Sunday meta is final

## Steps

### T.0 — Verify scheduled tasks (~5 min)

```powershell
schtasks /query /tn "Zuxas-Harness-Nightly-Modern" /fo LIST /v 2>&1
schtasks /query /tn "Zuxas-Harness-Nightly-Standard" /fo LIST /v 2>&1
schtasks /query /tn "MTG-Meta-Analyzer-Daily" /fo LIST /v 2>&1
```

Confirm:
- Task command lines match `register-harness-tasks.ps1` definitions (no manual drift)
- Run-as user / privileges look right
- Last-run-time and last-run-result are healthy (not "0x80070005 access denied" etc.)
- `--enable-auto-pipeline` flag is NOT in any task command line (default-off contract from today)

### T.1 — Re-run PT dry run (~5 min)

```bash
cd "E:/vscode ai project"
python harness/agents/scripts/nightly_harness.py --dry-run --format modern 2>&1 | tail -30
python harness/agents/scripts/nightly_harness.py --dry-run --format standard 2>&1 | tail -30
```

Compare to today's dry-run output. Should be idempotent (same shape; might detect different shifts if data updated overnight, but pipeline shape unchanged).

### T.2 — Verify auto_pipeline standalone path (~3 min)

```bash
cd "E:/vscode ai project"
python harness/agents/scripts/auto_pipeline.py --dry-run --format modern 2>&1 | tail -20
```

Should show "Would generate APL for [...]" without crashing. (Live run NOT needed — that's tomorrow's gemma-quality-lift spec or Friday's actual PT data.)

### T.3 — Check auto_apl_registry.json clean state (~2 min)

```bash
cd "E:/vscode ai project/mtg-sim"
cat data/auto_apl_registry.json 2>&1 || echo "(file does not exist; clean state)"
ls apl/auto_apls/*.py 2>&1
ls decks/auto/*.txt 2>&1
```

Today's S4 generated 3 APLs that failed smoke (committed at 1a4f97a). They're in `apl/auto_apls/` but NOT in registry (smoke gate blocked them). Decision: should they be deleted before Friday so post-PT runs see a clean slate? Or kept for Gemma-quality-lift spec to retry against?

Recommendation: **keep them** until gemma-quality-lift runs. If that spec produces passing versions, it'll overwrite. If it doesn't, we still have the current versions for future reference. Either way, post-PT run will produce different archetypes (PT-emergent, not pre-PT).

### T.4 — Decision: --enable-auto-pipeline for Friday? (~5 min)

Factors:
- Default-off contract from today: scheduled tasks safe in current configuration
- Auto-pipeline value Friday: depends on Gemma quality (which depends on whether tomorrow's gemma-quality-lift spec ran successfully)
- Risk of leaving on: if Gemma still produces 0/3 passes, no harm — registry stays empty
- Risk of leaving off: PT-emergent archetypes don't get APLs; nightly retune SKIPs them; Friday-night gauntlet doesn't reflect post-PT meta correctly

**Decision tree:**
- IF gemma-quality-lift shipped + pass rate ≥1/3: ENABLE for Friday
- IF gemma-quality-lift shipped + pass rate 0/3: keep DISABLED, queue for Saturday after Claude path verified
- IF gemma-quality-lift NOT shipped tomorrow: keep DISABLED (default-off remains right answer)

Document the decision in MEMORY.md.

### T.5 — Decision: --top-n for Friday? (~3 min)

Default 3. Today's dry-run found 8 new archetypes; Friday's PT could surface 30+.

If --enable-auto-pipeline goes ON:
- top-n=3: only top-3 by meta% get APLs; rest SKIP. Conservative.
- top-n=10: covers most of the meta but generates 10 APLs (~25 min runtime if Gemma; bumps nightly wall meaningfully).
- top-n=20: broad coverage; ~50 min runtime addition.

Recommendation: **top-n=10** as middle ground if auto-pipeline enabled. Document.

### T.6 — Saturday/Sunday plan (~5 min)

Sketch the Saturday morning routine:
1. Read overnight inbox (Gemma drift PR for Friday's meta detection)
2. Verify Friday-night nightly completed cleanly
3. Inspect: how many new archetypes did Gemma generate APLs for? What pass rate?
4. Re-run nightly_harness Saturday afternoon if Saturday meta brings new shifts
5. Sunday: same, post-finals meta is final-ish, time to start thinking about RC DC deck choice

Document in MEMORY.md.

### T.7 — MEMORY.md update (~5 min)

Add subsection "PT-readiness verification 2026-04-29":
- Verifications done (T.0-T.3 results)
- Decisions made (T.4, T.5)
- Saturday/Sunday plan
- Any concerns surfaced

## Validation gates

| Gate | Acceptance | Stop trigger |
|---|---|---|
| 1 — scheduled tasks healthy | All 3 tasks query cleanly, last-run looks healthy | task missing or in error state |
| 2 — PT dry runs clean | Both Modern + Standard dry-runs complete without crash | crash |
| 3 — auto-pipeline standalone clean | Dry-run completes | crash |
| 4 — clean state confirmed or accepted | Either registry empty OR explicit decision to keep current state | inconsistent state without decision |
| 5 — decisions documented | T.4 and T.5 decisions in MEMORY.md with rationale | undocumented |
| 6 — Saturday/Sunday plan written | MEMORY.md subsection complete | not written |

## Stop conditions

- **Any scheduled task in error state:** STOP. Investigate before Friday.
- **Dry runs surface crashes:** STOP. Becomes a P0 spec for tomorrow if not already.
- **Discover that today's RMW-race fix didn't actually land at expected path:** STOP, surface, fix before Friday since concurrent gauntlet during PT-watch is a real concern.

## Reporting expectations

1. Scheduled-task health table
2. Dry-run outcomes (Modern + Standard)
3. Auto-pipeline standalone outcome
4. Auto_apl_registry state + decision on cleanup
5. --enable-auto-pipeline decision + rationale
6. --top-n decision + rationale
7. Saturday/Sunday plan (3-5 bullets)
8. Any concerns flagged for follow-up

## Future work this enables (NOT in scope)

- Post-PT competitive analysis spec (Sunday or Monday)
- RC DC deck-choice memo spec (after Sunday final meta)

## Changelog

- 2026-04-28: Created (PROPOSED) by claude.ai for tomorrow Wednesday execution. Last-easy-day-before-PT verification. Scheduled task changes today (PowerShell wrapper added flags) need explicit verification that they didn't break the unattended path.
