# gemma-drift-pr.ps1
# Wrapper for gemma_drift_pr.py -- generates the day's drift PR via Gemma.
#
# Pattern: OpenAI Codex background drift PR equivalent from harness-engineering
# blog post. Gemma reads day's harness state overnight, produces a structured
# recommendation report at harness/inbox/drift-pr--YYYY-MM-DD.md for next-
# session-Claude to read alongside latest-snapshot.md.
#
# USAGE:
#   .\gemma-drift-pr.ps1                  # full run
#   .\gemma-drift-pr.ps1 -DryRun          # check Ollama health, don't call Gemma
#   .\gemma-drift-pr.ps1 -ShowPrompt      # print prompt to stdout (debug)
#   .\gemma-drift-pr.ps1 -Model gemma4    # override model
#
# OUTPUT:
#   harness/inbox/drift-pr--YYYY-MM-DD.md
#
# SCHEDULED:
#   04:50 daily (after session-snapshot at 04:30) via Zuxas-Harness-DriftPR
#
# ENCODING NOTE: ASCII-only. Same Windows cp1252-on-read trap as drift-detect.ps1
# and session-snapshot.ps1. Do not introduce em-dashes or other multibyte chars.
#
# Last updated: 2026-04-27 (v1.1: ASCII-only, time-shifted to early morning,
# UTF-8 stdout enforcement for Python child process)

param(
    [switch]$DryRun,
    [switch]$ShowPrompt,
    [string]$Model = "gemma4",
    [int]$MaxTokens = 4096,
    [double]$Temperature = 0.3
)

# Force UTF-8 stdout/stderr for the Python child process.
# Belt-and-suspenders: gemma_drift_pr.py also calls sys.stdout.reconfigure(),
# but setting the env var here ensures correct behavior even on older Python
# builds, on machines where reconfigure() fails, or if the script is invoked
# by something other than this wrapper.
#
# Without this, Python 3.x on Windows defaults stdout to cp1252 when piped
# (e.g. `... | Out-File`), which crashes on any non-Latin-1 char in the
# prompt or output (greater-than-or-equal symbols, em-dashes, smart quotes,
# box drawing, etc.).
$env:PYTHONIOENCODING = "utf-8"

$Script = "E:\vscode ai project\harness\agents\scripts\gemma_drift_pr.py"

if (-not (Test-Path $Script)) {
    Write-Host "ERROR: gemma_drift_pr.py not found at $Script" -ForegroundColor Red
    exit 2
}

$args_list = @(
    "--model", $Model,
    "--max-tokens", $MaxTokens,
    "--temperature", $Temperature
)
if ($DryRun)     { $args_list += "--dry-run" }
if ($ShowPrompt) { $args_list += "--show-prompt" }

python $Script @args_list
exit $LASTEXITCODE
