# Shared root resolver for the harness PowerShell wrappers (#51, #1 phase 3).
# PowerShell mirror of agents/scripts/roots.py: resolve from env first, else
# derive from this file's location. The wrappers live in harness/scripts/, so
# the harness root is this script's parent directory. Dot-source it:
#     . "$PSScriptRoot\_roots.ps1"
# then use $HarnessRoot / $ProjectRoot / $SimRoot / $MetaRoot / $WebsiteRoot /
# $AgentScripts. Env overrides ($env:HARNESS_ROOT, $env:ZUXAS_PROJECT_ROOT)
# match roots.py's precedence so a clone/worktree/CI run targets the right tree.

if ($env:HARNESS_ROOT) {
    $HarnessRoot = $env:HARNESS_ROOT
} else {
    # $PSScriptRoot here is this file's dir (harness/scripts), regardless of the
    # dot-sourcing caller; its parent is the harness root.
    $HarnessRoot = Split-Path $PSScriptRoot -Parent
}

if ($env:ZUXAS_PROJECT_ROOT) {
    $ProjectRoot = $env:ZUXAS_PROJECT_ROOT
} else {
    $ProjectRoot = Split-Path $HarnessRoot -Parent
}

$SimRoot      = Join-Path $ProjectRoot "mtg-sim"
$MetaRoot     = Join-Path $ProjectRoot "mtg-meta-analyzer"
$WebsiteRoot  = Join-Path $ProjectRoot "My-Website"
$AgentScripts = Join-Path $HarnessRoot "agents\scripts"

# Dry-run: `.\_roots.ps1 -ShowRoots` prints resolved roots vs the legacy values.
if ($args -contains "-ShowRoots" -or $ShowRoots) {
    $legacy = @{
        ProjectRoot  = "E:\vscode ai project"
        HarnessRoot  = "E:\vscode ai project\harness"
        SimRoot      = "E:\vscode ai project\mtg-sim"
        MetaRoot     = "E:\vscode ai project\mtg-meta-analyzer"
        WebsiteRoot  = "E:\vscode ai project\My-Website"
        AgentScripts = "E:\vscode ai project\harness\agents\scripts"
    }
    $resolved = @{
        ProjectRoot = $ProjectRoot; HarnessRoot = $HarnessRoot; SimRoot = $SimRoot
        MetaRoot = $MetaRoot; WebsiteRoot = $WebsiteRoot; AgentScripts = $AgentScripts
    }
    $allMatch = $true
    foreach ($k in "ProjectRoot","HarnessRoot","SimRoot","MetaRoot","WebsiteRoot","AgentScripts") {
        $match = ($resolved[$k] -eq $legacy[$k])
        if (-not $match) { $allMatch = $false }
        $tag = if ($match) { "MATCH " } else { "DIFFER" }
        "  {0,-12} [{1}]  {2}" -f $k, $tag, $resolved[$k]
    }
    ""
    if ($allMatch) { "All roots match the legacy hardcoded values." }
    else { "Some roots differ -- expected off E:\vscode ai project (clone/worktree/CI)." }
}
