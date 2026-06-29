# SCHEDULED TASKS (Windows Task Scheduler)

Relocated from harness/CLAUDE.md on 2026-06-29 (LOW-RISK trim per specs/2026-06-29-claude-md-trim-plan.md).

Updated 2026-04-27 v1.3: snapshot + drift PR moved to early morning so handoff state is fresh when user starts the day. Nightly harness stays in the evening because it depends on the 5pm meta-analyzer scraper.

| Time | Task | Purpose |
|---|---|---|
| 04:30 | Zuxas-Harness-SessionSnapshot | Snapshot + drift detect + lint + drift route |
| 04:50 | Zuxas-Harness-DriftPR | Gemma reads overnight state, generates drift PR |
| 17:00 | MTG-Meta-Analyzer-Daily | meta-analyzer scraper |
| 17:30 | Zuxas-Harness-Nightly-Modern | Modern nightly retune + gauntlet |
| 18:30 | Zuxas-Harness-Nightly-Standard | Standard nightly retune + gauntlet |

Tasks have `-WakeToRun` enabled — Windows wakes the PC from sleep to run the 04:30 / 04:50 / 17:30 / 18:30 slots. If PC is fully off, the on-login backstop catches up.

Register via `harness/scripts/register-harness-tasks.ps1` (must run as Administrator).

Daily flow:

```
17:00  meta-analyzer scraper
17:30  Zuxas-Harness-Nightly-Modern
18:30  Zuxas-Harness-Nightly-Standard

       --- overnight ---

04:30  Zuxas-Harness-SessionSnapshot
04:50  Zuxas-Harness-DriftPR

       --- user wakes up, sits down to work ---

       reads latest-snapshot.md AND inbox/drift-pr--<today>.md
       runs DAILY RHYTHM CHECK (chain priority + sub-project pivot)
       proceeds per user response
```
