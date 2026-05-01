---
title: GitHub Actions self-hosted runner setup + CI/CD pipeline
status: PROPOSED
created: 2026-04-30
updated: 2026-04-30
project: harness / mtg-sim / mtg-meta-analyzer
estimated_time: 30-45 min (runner registration) + 15 min (first push)
---

# Spec: GitHub Actions CI/CD Pipeline

## Goal

Wire the existing local quality tools (lint-mtg-sim.py, test_determinism.py,
verify_oracle.py, predictions.validate) into GitHub Actions so they run
automatically on every PR — before code touches main.

The self-hosted runner on the Windows machine is the key: it has access to
Ollama (Gemma 4 for AI gates), the local SQLite DBs, and the sibling repos.
AI quality gates run at $0.00 cost per check.

## What's novel (vs "AI CI/CD" hype)

Most things calling themselves AI CI/CD use LLMs to generate YAML or explain
test failures. This pipeline is different:

1. **Semantic oracle gate** — verify_oracle.py checks that APL code correctly
   implements MTG oracle text. Not syntax checking; domain-correctness checking.
   Gemma 12B as judge. $0.00 per run.

2. **Predictions accuracy gate** — if a commit to analysis/ or scrapers/ quietly
   breaks the predictive model, this gate fires. That's a regression class that
   unit tests cannot catch because it requires knowing what "correct" means for
   competitive MTG meta prediction.

3. **Progressive cost model** — lint ($0.00) → tests ($0.00) → oracle gate
   ($0.00, Gemma) → gauntlet ($0.00, local sim). Nothing touches paid APIs
   until a PR has already passed all free gates.

## Step 1: Register self-hosted runner on Windows

### mtg-sim repo

1. Go to https://github.com/Zuxas/mtg-sim/settings/actions/runners
2. Click **New self-hosted runner** → Windows → x64
3. Follow the download + configure steps. The token expires in 1 hour.

PowerShell commands (run as Administrator in a new folder):
```powershell
# Create runner directory
New-Item -ItemType Directory -Path "C:\actions-runner-mtgsim" -Force
Set-Location "C:\actions-runner-mtgsim"

# Download (version shown on GitHub page -- use that exact URL)
Invoke-WebRequest -Uri https://github.com/actions/runner/releases/download/v2.x.y/actions-runner-win-x64-2.x.y.zip -OutFile runner.zip
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::ExtractToDirectory("$PWD\runner.zip", "$PWD")

# Configure (token from GitHub settings page)
.\config.cmd --url https://github.com/Zuxas/mtg-sim --token <TOKEN_FROM_GITHUB>

# Install as Windows service (runs even when not logged in)
.\svc.cmd install
.\svc.cmd start
```

4. Verify: green dot appears in GitHub settings → Actions → Runners.

### mtg-meta-analyzer repo

Repeat for https://github.com/Zuxas/mtg-meta-analyzer/settings/actions/runners.
Can use a second runner directory `C:\actions-runner-metaanalyzer`.
Or use ONE runner with labels and target both repos.

## Step 2: Set repository variables

In GitHub settings → Secrets and Variables → Actions → Variables:

| Variable | Value | Repo |
|---|---|---|
| `MTG_META_DB` | `E:/vscode ai project/mtg-meta-analyzer/data/mtg_meta.db` | mtg-sim |
| `HARNESS_ROOT` | `E:/vscode ai project/harness` | mtg-sim |
| `MTG_META_DB` | `E:/vscode ai project/mtg-meta-analyzer/data/mtg_meta.db` | mtg-meta-analyzer |
| `WEBSITE_DATA` | `E:/vscode ai project/My-Website/data` | mtg-meta-analyzer |

## Step 3: Push the outstanding commits

### mtg-sim (186 commits ahead)
```powershell
cd "E:\vscode ai project\mtg-sim"
# Stage untracked files that should be in the repo
git add apl/azorius_momo_standard_match.py apl/golgari_midrange_standard_match.py apl/selesnya_landfall_standard_match.py
git add scripts/lint_ci.py .github/workflows/ci.yml
git add scripts/build_meta_shares.py scripts/build_priority_queue.py scripts/cast_weighted_coverage.py
# Push
git push origin main
```

### mtg-meta-analyzer (8 commits ahead + new CI files)
```powershell
cd "E:\vscode ai project\mtg-meta-analyzer"
git add .github/workflows/ci.yml scripts/generate_site_data.py scripts/sync_session_to_matchlog.py
git add gui/tabs/event_hub_tab.py gui/tabs/tournament_prep.py db/event_hub_db.py
git add scrapers/spicerack_scraper.py scrapers/event_finder.py
git push origin main
```

## Step 4: Verify first CI run

After pushing, go to Actions tab in GitHub. The first run should:
- ✓ lint: APL registry/handler/deck consistency — passes with 0 errors
- ✓ tests: determinism (4/4) + menace combat — passes
- oracle-gate: skipped (no PR)
- goldfish-guard: skipped (no PR)

For meta-analyzer:
- ✓ imports: all 10 modules load cleanly
- scraper-api: Spicerack --counts, event finder geocode
- predictions-gate: skipped (no PR) or skipped (< 5 validated predictions)

## Step 5: First PR to exercise all gates

Make a small change to any `apl/*_match.py` file in a branch, open a PR.
All 4 jobs should run:
1. lint — fast
2. tests — determinism + menace
3. oracle-gate — Gemma verifies the changed APL
4. goldfish-guard — if engine or boros_energy.py was touched

## What each gate catches that code review misses

| Gate | Catches |
|---|---|
| APL lint | Registry/handler mismatch, orphan deck files, card-count anomalies |
| Determinism test | Engine changes that break reproducible results |
| Oracle gate (AI) | APL code that doesn't match oracle text (e.g. wrong mana cost, missing clause) |
| Goldfish guard | Engine changes that silently shift canonical kill-turn baseline |
| Predictions gate (AI) | Analysis/scraper changes that break meta prediction accuracy |
| GUI imports | PyQt6 widget changes that break module-level imports |

## The inner_workers bug — what CI would have caught

Today's NameError bug (`inner_workers` not defined in `_run_fair`) would have
been caught by the determinism test: `test_n_workers_determinism()` runs
`run_match_set` with n_workers=4, which would have triggered the error.

Before today's fix, the bug reached main. After CI is wired, that can't happen.

## Changelog

- 2026-04-30: Created (PROPOSED). Covers runner setup, path fixes, CI workflow
  design. Paths fixed in 5 files across mtg-sim and meta-analyzer. Workflows
  created: mtg-sim/.github/workflows/ci.yml, mtg-meta-analyzer/.github/workflows/ci.yml.
