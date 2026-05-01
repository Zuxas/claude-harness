#!/usr/bin/env pwsh
# install-pre-commit-hook.ps1
# Installs (or removes) the lint-mtg-sim.py pre-commit hook in the mtg-sim repo.
#
# The hook itself lives at:
#   harness/scripts/templates/mtg-sim-pre-commit.sh
#
# This script copies it to:
#   E:\vscode ai project\mtg-sim\.git\hooks\pre-commit
#
# Why a deployment script:
#   .git/hooks/ is not under version control. If the repo is re-cloned,
#   .git/hooks/ resets. This script makes redeployment a one-liner.
#
# USAGE:
#   .\install-pre-commit-hook.ps1               # install
#   .\install-pre-commit-hook.ps1 -Remove       # remove
#   .\install-pre-commit-hook.ps1 -Force        # overwrite without prompting
#   .\install-pre-commit-hook.ps1 -DryRun       # show what would happen
#
# EXIT CODES:
#   0 = success
#   1 = warning (e.g. existing hook detected, user declined overwrite)
#   2 = error (paths invalid, copy failed)
#
# ENCODING NOTE: ASCII-only. Same Windows cp1252-on-read trap as drift-detect.
# Box-drawing chars (the originals were U+2500 horizontal lines) replaced with
# ASCII dashes so the file parses correctly on Windows PowerShell 5.1.
#
# Last updated: 2026-04-27 (v1.1: ASCII-only enforcement)

param(
    [switch]$Remove,
    [switch]$Force,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

# Paths
$mtgSimRoot   = "E:\vscode ai project\mtg-sim"
$hooksDir     = "$mtgSimRoot\.git\hooks"
$hookTarget   = "$hooksDir\pre-commit"
$hookSource   = "E:\vscode ai project\harness\scripts\templates\mtg-sim-pre-commit.sh"

function Write-Color {
    param([string]$Text, [string]$Color = "White")
    Write-Host $Text -ForegroundColor $Color
}

# --- Validate paths ---------------------------------------------
if (-not (Test-Path $mtgSimRoot)) {
    Write-Color "ERROR: mtg-sim repo not found at $mtgSimRoot" "Red"
    exit 2
}
if (-not (Test-Path $hooksDir)) {
    Write-Color "ERROR: .git/hooks not found -- is $mtgSimRoot a git repo?" "Red"
    exit 2
}

# --- Remove path ------------------------------------------------
if ($Remove) {
    if (-not (Test-Path $hookTarget)) {
        Write-Color "Hook not installed (nothing to remove): $hookTarget" "Yellow"
        exit 0
    }
    # Verify it's our hook before deleting (don't nuke someone else's hook)
    $existing = Get-Content $hookTarget -Raw
    if ($existing -notmatch "zuxas-lint-hook-start") {
        Write-Color "WARN: $hookTarget exists but isn't the zuxas-lint-hook." "Yellow"
        Write-Color "      Refusing to delete to avoid clobbering other tooling." "Yellow"
        Write-Color "      Inspect the file manually and delete by hand if appropriate." "Yellow"
        exit 1
    }
    if ($DryRun) {
        Write-Color "[DRY RUN] Would delete: $hookTarget" "Cyan"
        exit 0
    }
    Remove-Item $hookTarget -Force
    Write-Color "Removed: $hookTarget" "Green"
    exit 0
}

# --- Install path -----------------------------------------------
if (-not (Test-Path $hookSource)) {
    Write-Color "ERROR: hook source not found at $hookSource" "Red"
    Write-Color "       Did you copy the .git/hooks/pre-commit to templates/ for redeployment?" "Yellow"
    exit 2
}

# Check for existing hook (might be ours, might be someone else's)
if (Test-Path $hookTarget) {
    $existing = Get-Content $hookTarget -Raw
    if ($existing -match "zuxas-lint-hook-start") {
        # Our hook already installed; check if up to date
        $sourceContent = Get-Content $hookSource -Raw
        if ($existing -eq $sourceContent) {
            Write-Color "Hook already installed and up to date: $hookTarget" "Green"
            exit 0
        }
        Write-Color "Hook installed but differs from source. Updating..." "Yellow"
    } else {
        Write-Color "WARN: $hookTarget exists and is NOT the zuxas-lint-hook." "Yellow"
        Write-Color "      Existing hook starts with:" "Yellow"
        $firstLines = ($existing -split "`n" | Select-Object -First 5) -join "`n"
        Write-Color $firstLines "DarkYellow"
        Write-Color "" "White"
        if (-not $Force) {
            $reply = Read-Host "Overwrite this hook? (y/N)"
            if ($reply -ne "y" -and $reply -ne "Y") {
                Write-Color "Aborted. To overwrite without prompting use -Force." "Yellow"
                exit 1
            }
        }
    }
}

if ($DryRun) {
    Write-Color "[DRY RUN] Would copy:" "Cyan"
    Write-Color "  $hookSource" "Cyan"
    Write-Color "  -> $hookTarget" "Cyan"
    exit 0
}

Copy-Item -Path $hookSource -Destination $hookTarget -Force

# Note on Windows: git core.fileMode is usually false, so the exec bit
# doesn't strictly matter -- git-bash invokes via shebang detection.
# But on systems where it does matter (WSL, Linux clone), the hook
# needs +x. We can't easily set that from PowerShell on NTFS, so
# document it instead.

Write-Color "Installed: $hookTarget" "Green"
Write-Color "" "White"
Write-Color "If your shell respects POSIX exec bits (WSL/git-bash strict mode):" "DarkGray"
Write-Color "  cd `"$mtgSimRoot`" && chmod +x .git/hooks/pre-commit" "DarkGray"
Write-Color "" "White"
Write-Color "Test the hook by attempting a commit on a lint-relevant file." "Cyan"
Write-Color "Bypass for emergencies: git commit --no-verify" "Cyan"

exit 0
