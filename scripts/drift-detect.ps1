# drift-detect.ps1
# Drift detection battery for the mtg-sim project + harness state.
# Runs read-only checks against E:\vscode ai project\mtg-sim\ and harness/.
# Codifies the architectural-finding patterns from the 2026-04-26/27 session
# so future sessions catch drift mechanically instead of by accident.
#
# USAGE:
#   .\drift-detect.ps1                     # run all checks, print to stdout
#   .\drift-detect.ps1 -Json               # output JSON report
#   .\drift-detect.ps1 -OutFile <path>     # write findings to file
#   .\drift-detect.ps1 -Quiet              # no console output, exit code only
#   .\drift-detect.ps1 -RouteFindings      # write/append findings doc to
#                                          # harness/knowledge/tech/drift-YYYY-MM-DD.md
#                                          # AND update knowledge/_index.md
#                                          # (only writes if findings present)
#
# EXIT CODES:
#   0 = all checks passed
#   1 = warnings found (non-fatal drift)
#   2 = errors found (real bugs)
#
# ENCODING NOTE: this file is intentionally ASCII-only. Windows PowerShell 5.1
# reads .ps1 files as cp1252 by default unless a BOM is present, so any UTF-8
# multibyte character (em-dash, smart quotes, etc.) corrupts on read and breaks
# the parser. If you edit this file, do not introduce non-ASCII characters
# unless you also force UTF-8-with-BOM on save.
#
# Last updated: 2026-04-27 (v1.1: replaced em-dashes with ASCII -- after a
# cp1252-on-read corruption broke parsing on Windows PowerShell 5.1)

param(
    [switch]$Json,
    [string]$OutFile = "",
    [switch]$Quiet,
    [switch]$RouteFindings,
    [int]$StaleDocDays = 7,
    [int]$StaleSpecDays = 14,
    [int]$CanonicalNThreshold = 10000
)

$ErrorActionPreference = "Continue"

# Paths
$projectRoot   = "E:\vscode ai project"
$mtgSimRoot    = "$projectRoot\mtg-sim"
$harnessRoot   = "$projectRoot\harness"
$knowledgeTech = "$harnessRoot\knowledge\tech"
$specsDir      = "$harnessRoot\specs"
$archMd        = "$mtgSimRoot\ARCHITECTURE.md"

# Findings collector
$findings = @()
$warningCount = 0
$errorCount = 0

function Add-Finding {
    param(
        [string]$Severity,   # INFO | WARN | ERROR
        [string]$Check,
        [string]$Detail,
        [string]$Fix = ""
    )
    $script:findings += [PSCustomObject]@{
        severity = $Severity
        check    = $Check
        detail   = $Detail
        fix      = $Fix
        time     = (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
    }
    if     ($Severity -eq "WARN")  { $script:warningCount++ }
    elseif ($Severity -eq "ERROR") { $script:errorCount++ }
}

function Write-Color {
    param([string]$Text, [string]$Color = "White")
    if (-not $Quiet) { Write-Host $Text -ForegroundColor $Color }
}

# ---------------------------------------------------------------------------
# CHECK 1: Load-bearing WIP detection
# ---------------------------------------------------------------------------

function Check-LoadBearingWIP {
    Write-Color "[1/9] Load-bearing WIP detection..." "Cyan"

    if (-not (Test-Path $mtgSimRoot)) {
        Add-Finding "WARN" "load-bearing-wip" "mtg-sim repo not found at $mtgSimRoot"
        return
    }

    Push-Location $mtgSimRoot
    try {
        $untracked = git status --porcelain | Where-Object {
            $_ -match "^\?\?" -and $_ -match "\.py$"
        } | ForEach-Object {
            $_ -replace "^\?\?\s+", ""
        }

        if (-not $untracked) {
            Write-Color "       OK -- no untracked .py files" "Green"
            return
        }

        $loadBearing = @()
        foreach ($file in $untracked) {
            $module = ($file -replace "\.py$", "" -replace "[\\/]", ".")
            $basename = [System.IO.Path]::GetFileNameWithoutExtension($file)

            $trackedPyFiles = git ls-files "*.py"
            $importers = @()
            foreach ($trackedFile in $trackedPyFiles) {
                if (-not (Test-Path $trackedFile)) { continue }
                $content = Get-Content $trackedFile -Raw -ErrorAction SilentlyContinue
                if (-not $content) { continue }

                if ($content -match "(?m)^\s*(from|import)\s+\S*$([regex]::Escape($basename))(\b|\.)") {
                    $importers += $trackedFile
                }
            }

            if ($importers.Count -gt 0) {
                $loadBearing += [PSCustomObject]@{
                    file     = $file
                    importers = $importers
                }
            }
        }

        if ($loadBearing.Count -gt 0) {
            foreach ($lb in $loadBearing) {
                $importerStr = ($lb.importers | Select-Object -First 3) -join ", "
                if ($lb.importers.Count -gt 3) { $importerStr += " (+$($lb.importers.Count - 3) more)" }
                Add-Finding "ERROR" "load-bearing-wip" `
                    "Untracked file $($lb.file) imported by: $importerStr" `
                    "git add $($lb.file) AND commit before stash/test/branch operations"
            }
            Write-Color "       ERROR -- found $($loadBearing.Count) load-bearing untracked file(s)" "Red"
        } else {
            Write-Color "       OK -- $($untracked.Count) untracked file(s), none imported" "Green"
        }
    } finally {
        Pop-Location
    }
}

# ---------------------------------------------------------------------------
# CHECK 2: Canonical-deck-mismatch detection
# ---------------------------------------------------------------------------

function Check-RegistryConsistency {
    Write-Color "[2/9] APL registry consistency..." "Cyan"

    if (-not (Test-Path $mtgSimRoot)) {
        Add-Finding "WARN" "registry-consistency" "mtg-sim repo not found"
        return
    }

    $lintScript = "$harnessRoot\scripts\lint-mtg-sim.py"
    if (-not (Test-Path $lintScript)) {
        Add-Finding "INFO" "registry-consistency" `
            "lint-mtg-sim.py not found, skipping AST-based registry check"
        Write-Color "       SKIP -- lint-mtg-sim.py not present" "Yellow"
        return
    }

    Push-Location $mtgSimRoot
    try {
        $lintOutput = & python $lintScript --check registry --json 2>&1
        $exitCode = $LASTEXITCODE

        if ($exitCode -eq 0) {
            Write-Color "       OK -- all registry entries resolve" "Green"
        } else {
            try {
                $parsed = $lintOutput | ConvertFrom-Json
                foreach ($issue in $parsed.issues) {
                    Add-Finding $issue.severity "registry-consistency" $issue.detail $issue.fix
                }
            } catch {
                Add-Finding "ERROR" "registry-consistency" `
                    "Lint exited $exitCode but output not parseable: $lintOutput"
            }
            Write-Color "       ISSUES -- see findings" "Red"
        }
    } finally {
        Pop-Location
    }
}

# ---------------------------------------------------------------------------
# CHECK 3: Stale ARCHITECTURE.md vs latest gauntlet results
# ---------------------------------------------------------------------------

function Check-StaleArchitecture {
    Write-Color "[3/9] Stale ARCHITECTURE.md detection..." "Cyan"

    if (-not (Test-Path $archMd)) {
        Add-Finding "WARN" "stale-architecture" "ARCHITECTURE.md not found at $archMd"
        return
    }

    $resultsDir = "$mtgSimRoot\data"
    if (-not (Test-Path $resultsDir)) {
        Write-Color "       SKIP -- $resultsDir not present" "Yellow"
        return
    }

    # ARCHITECTURE.md baselines anchor on canonical (high-N) runs (rare,
    # deliberate). Sub-threshold runs are experimental / throwaway and do NOT
    # shift the baseline. Walk newest-first; stop at the first run with
    # N >= CanonicalNThreshold so a fresh experimental gauntlet doesn't
    # trigger a false-positive WARN. (See IMPERFECTIONS.md
    # drift-detect-arch-staleness-false-positive-on-non-canonical-runs.)
    $allResults = Get-ChildItem -Path $resultsDir -Filter "parallel_results_*.json" `
        -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending

    if (-not $allResults) {
        Write-Color "       SKIP -- no parallel_results_*.json files" "Yellow"
        return
    }

    $canonicalResult = $null
    foreach ($file in $allResults) {
        try {
            $json = Get-Content $file.FullName -Raw -ErrorAction Stop | ConvertFrom-Json
            $n = if ($null -ne $json.n_per_matchup) { [int]$json.n_per_matchup } else { 0 }
            if ($n -ge $CanonicalNThreshold) {
                $canonicalResult = $file
                break
            }
        } catch {
            # Unparseable file; skip silently
        }
    }

    if (-not $canonicalResult) {
        Add-Finding "INFO" "stale-architecture" `
            "No canonical (N>=$CanonicalNThreshold) parallel_results files found across $($allResults.Count) candidates; skipping ARCH staleness check"
        Write-Color "       SKIP -- no canonical (N>=$CanonicalNThreshold) runs found" "Yellow"
        return
    }

    $archMtime   = (Get-Item $archMd).LastWriteTime
    $resultMtime = $canonicalResult.LastWriteTime

    if ($resultMtime -gt $archMtime) {
        $delta = ($resultMtime - $archMtime).TotalHours
        Add-Finding "WARN" "stale-architecture" `
            "ARCHITECTURE.md is older than latest canonical (N>=$CanonicalNThreshold) gauntlet run ($($canonicalResult.Name)) by $([math]::Round($delta, 1)) hours" `
            "Update ARCHITECTURE.md gauntlet entries with results from $($canonicalResult.Name)"
        Write-Color "       WARN -- ARCH is $([math]::Round($delta, 1))h older than latest canonical run" "Yellow"
    } else {
        Write-Color "       OK -- ARCHITECTURE.md is current vs canonical (N>=$CanonicalNThreshold) baseline" "Green"
    }
}

# ---------------------------------------------------------------------------
# CHECK 4: Stale findings docs
# ---------------------------------------------------------------------------

function Check-StaleFindings {
    Write-Color "[4/9] Stale findings docs..." "Cyan"

    if (-not (Test-Path $knowledgeTech)) {
        Add-Finding "WARN" "stale-findings" "$knowledgeTech not found"
        return
    }

    $staleStatuses = @("SURFACED", "PARTIAL", "in progress", "PENDING", "EXECUTING")
    $cutoff = (Get-Date).AddDays(-$StaleDocDays)
    $staleCount = 0

    $findingsDocs = Get-ChildItem -Path $knowledgeTech -Filter "*-2026-*.md" -ErrorAction SilentlyContinue
    foreach ($doc in $findingsDocs) {
        # Skip self-routed drift docs (would create infinite churn)
        if ($doc.Name -like "drift-*.md") { continue }

        $content = Get-Content $doc.FullName -Raw -ErrorAction SilentlyContinue
        if (-not $content) { continue }

        $hasUnresolved = $false
        $matchedStatus = ""
        foreach ($status in $staleStatuses) {
            if ($content -match $status) {
                $hasUnresolved = $true
                $matchedStatus = $status
                break
            }
        }

        if ($content -match "RESOLVED") { $hasUnresolved = $false }

        if ($hasUnresolved -and $doc.LastWriteTime -lt $cutoff) {
            $age = ((Get-Date) - $doc.LastWriteTime).TotalDays
            Add-Finding "WARN" "stale-findings" `
                "$($doc.Name) has status '$matchedStatus' and is $([math]::Round($age,1)) days old" `
                "Review and either resolve or refresh the findings doc"
            $staleCount++
        }
    }

    if ($staleCount -eq 0) {
        Write-Color "       OK -- no stale findings docs" "Green"
    } else {
        Write-Color "       WARN -- $staleCount stale findings doc(s)" "Yellow"
    }
}

# ---------------------------------------------------------------------------
# CHECK 5: Spec status drift
# ---------------------------------------------------------------------------

function Check-SpecStatusDrift {
    Write-Color "[5/9] Spec status drift..." "Cyan"

    if (-not (Test-Path $specsDir)) {
        Write-Color "       SKIP -- $specsDir not present yet" "Yellow"
        return
    }

    $proposedCutoff  = (Get-Date).AddDays(-$StaleSpecDays)
    $executingCutoff = (Get-Date).AddHours(-24)
    $issueCount = 0

    $specs = Get-ChildItem -Path $specsDir -Filter "*.md" -ErrorAction SilentlyContinue |
             Where-Object { $_.Name -notin @("README.md", "_template.md", "_index.md", "RETROACTIVE.md") }

    foreach ($spec in $specs) {
        $content = Get-Content $spec.FullName -Raw -ErrorAction SilentlyContinue
        if (-not $content) { continue }

        $statusMatch = [regex]::Match($content, "(?m)^status:\s*[`"']?(\w+)[`"']?")
        if (-not $statusMatch.Success) { continue }
        $status = $statusMatch.Groups[1].Value

        if ($status -eq "PROPOSED" -and $spec.LastWriteTime -lt $proposedCutoff) {
            $age = ((Get-Date) - $spec.LastWriteTime).TotalDays
            Add-Finding "WARN" "spec-status-drift" `
                "$($spec.Name) has been PROPOSED for $([math]::Round($age,1)) days" `
                "Decide: execute, supersede, or mark ABANDONED"
            $issueCount++
        }
        if ($status -eq "EXECUTING" -and $spec.LastWriteTime -lt $executingCutoff) {
            $age = ((Get-Date) - $spec.LastWriteTime).TotalHours
            Add-Finding "WARN" "spec-status-drift" `
                "$($spec.Name) has been EXECUTING for $([math]::Round($age,1)) hours" `
                "Check if work stalled; either resume or revert to PROPOSED with notes"
            $issueCount++
        }
    }

    if ($issueCount -eq 0) {
        Write-Color "       OK -- no spec status drift" "Green"
    } else {
        Write-Color "       WARN -- $issueCount spec(s) with status drift" "Yellow"
    }
}

# ---------------------------------------------------------------------------
# CHECK 6: Imperfections registry not stagnant
# ---------------------------------------------------------------------------

function Check-Imperfections {
    Write-Color "[6/9] Imperfections registry health..." "Cyan"

    $imperfPath = "$harnessRoot\IMPERFECTIONS.md"
    if (-not (Test-Path $imperfPath)) {
        Add-Finding "INFO" "imperfections" "$imperfPath does not exist yet"
        Write-Color "       SKIP -- IMPERFECTIONS.md not present" "Yellow"
        return
    }

    $content = Get-Content $imperfPath -Raw
    $imperfMtime = (Get-Item $imperfPath).LastWriteTime
    $age = ((Get-Date) - $imperfMtime).TotalDays

    $entryCount = ([regex]::Matches($content, "(?m)^##\s+")).Count

    if ($age -gt 30) {
        Add-Finding "WARN" "imperfections" `
            "IMPERFECTIONS.md has not been updated in $([math]::Round($age,1)) days" `
            "Either burn down entries (resolve in next session) or add new ones discovered"
        Write-Color "       WARN -- registry stale ($([math]::Round($age,1))d)" "Yellow"
    } else {
        Write-Color "       OK -- $entryCount entries, last updated $([math]::Round($age,1))d ago" "Green"
    }
}

# ---------------------------------------------------------------------------
# CHECK 7: Cache-key audit (heuristic detector for cache-collision bug class)
# ---------------------------------------------------------------------------

function Check-CacheKeys {
    Write-Color "[7/9] Cache-key heuristic audit..." "Cyan"

    if (-not (Test-Path $mtgSimRoot)) {
        Add-Finding "INFO" "cache-keys" "mtg-sim repo not found, skipping"
        Write-Color "       SKIP -- mtg-sim not present" "Yellow"
        return
    }

    $lintScript = "$harnessRoot\scripts\lint-cache-keys.py"
    if (-not (Test-Path $lintScript)) {
        Add-Finding "INFO" "cache-keys" `
            "lint-cache-keys.py not found, skipping AST-based cache-key check"
        Write-Color "       SKIP -- lint-cache-keys.py not present" "Yellow"
        return
    }

    $lintOutput = & python $lintScript --json 2>&1
    $exitCode = $LASTEXITCODE

    if ($exitCode -ne 0) {
        Add-Finding "WARN" "cache-keys" "lint-cache-keys.py exited $exitCode"
        Write-Color "       WARN -- lint exit $exitCode" "Yellow"
        return
    }

    try {
        $parsed = $lintOutput | ConvertFrom-Json
        $issueCount = if ($parsed.issues) { $parsed.issues.Count } else { 0 }
        $fileCount  = $parsed.files_scanned

        if ($issueCount -eq 0) {
            Write-Color "       OK -- $fileCount files scanned, no cache-key gaps detected" "Green"
        } else {
            foreach ($issue in $parsed.issues) {
                Add-Finding $issue.severity "cache-keys" $issue.detail $issue.fix
            }
            Write-Color "       INFO -- $issueCount potential cache-key gap(s) in $fileCount files" "Yellow"
        }
    } catch {
        Add-Finding "ERROR" "cache-keys" "lint-cache-keys.py output not parseable: $lintOutput"
        Write-Color "       ERROR -- lint output unparseable" "Red"
    }
}

function Check-RMWPattern {
    Write-Color "[8/9] RMW-pattern heuristic audit..." "Cyan"

    if (-not (Test-Path $mtgSimRoot)) {
        Add-Finding "INFO" "rmw-pattern" "mtg-sim repo not found, skipping"
        Write-Color "       SKIP -- mtg-sim not present" "Yellow"
        return
    }

    $lintScript = "$harnessRoot\scripts\lint-rmw-pattern.py"
    if (-not (Test-Path $lintScript)) {
        Add-Finding "INFO" "rmw-pattern" `
            "lint-rmw-pattern.py not found, skipping RMW-pattern check"
        Write-Color "       SKIP -- lint-rmw-pattern.py not present" "Yellow"
        return
    }

    $lintOutput = & python $lintScript --json 2>&1
    $exitCode = $LASTEXITCODE

    if ($exitCode -ne 0) {
        Add-Finding "WARN" "rmw-pattern" "lint-rmw-pattern.py exited $exitCode"
        Write-Color "       WARN -- lint exit $exitCode" "Yellow"
        return
    }

    try {
        $parsed = $lintOutput | ConvertFrom-Json
        $findingCount = if ($parsed.findings) { $parsed.findings.Count } else { 0 }

        if ($findingCount -eq 0) {
            Write-Color "       OK -- no RMW-pattern findings" "Green"
        } else {
            foreach ($f in $parsed.findings) {
                $detail = "$($f.file):$($f.line) $($f.function)() -- $($f.path)"
                Add-Finding "INFO" "rmw-pattern" $detail `
                    "Use atomic_rmw_json() from engine/atomic_json.py or add # drift-detect:rmw-ok"
            }
            Write-Color "       INFO -- $findingCount RMW-pattern finding(s)" "Yellow"
        }
    } catch {
        Add-Finding "ERROR" "rmw-pattern" "lint-rmw-pattern.py output not parseable: $lintOutput"
        Write-Color "       ERROR -- lint output unparseable" "Red"
    }
}

function Check-SpecReferences {
    Write-Color "[9/9] Spec reference validation..." "Cyan"

    $lintScript = "$harnessRoot\scripts\lint-spec-references.py"
    if (-not (Test-Path $lintScript)) {
        Add-Finding "INFO" "spec-references" `
            "lint-spec-references.py not found, skipping spec reference check"
        Write-Color "       SKIP -- lint-spec-references.py not present" "Yellow"
        return
    }

    $lintOutput = & python $lintScript --json 2>&1
    $exitCode = $LASTEXITCODE

    try {
        $parsed = $lintOutput | ConvertFrom-Json
        $findingCount = if ($parsed.findings) { $parsed.findings.Count } else { 0 }
        $specsChecked = if ($parsed.specs_checked) { $parsed.specs_checked } else { 0 }

        if ($findingCount -eq 0) {
            Write-Color "       OK -- $specsChecked specs checked, 0 issues" "Green"
        } else {
            foreach ($f in $parsed.findings) {
                $detail = "$($f.spec):$($f.line) -- $($f.message)"
                Add-Finding $f.level "spec-references" $detail ($f.fix)
            }
            Write-Color "       $findingCount issue(s) in $specsChecked specs" "Yellow"
        }
    } catch {
        Add-Finding "ERROR" "spec-references" "lint-spec-references.py output not parseable: $lintOutput"
        Write-Color "       ERROR -- lint output unparseable" "Red"
    }
}

# ---------------------------------------------------------------------------
# RouteFindings: write findings doc to harness/knowledge/tech/drift-<date>.md
# Idempotent: if today's drift doc exists, append a new "## Run at HH:MM"
# section. If no findings, do nothing (don't write empty docs that pollute).
# ---------------------------------------------------------------------------

function Route-Findings {
    if ($findings.Count -eq 0) {
        Write-Color "       (no findings to route)" "Gray"
        return
    }

    $dateStr = Get-Date -Format "yyyy-MM-dd"
    $timeStr = Get-Date -Format "HH:mm"
    $routePath = "$knowledgeTech\drift-$dateStr.md"

    $newSection = @()
    $newSection += ""
    $newSection += "## Run at $timeStr"
    $newSection += ""
    $newSection += "Errors: $errorCount | Warnings: $warningCount | Total: $($findings.Count)"
    $newSection += ""
    foreach ($f in $findings) {
        $newSection += ("- **\[{0}\] {1}**: {2}" -f $f.severity, $f.check, $f.detail)
        if ($f.fix) {
            $newSection += "  - fix: " + $f.fix
        }
    }
    $newSection += ""

    if (Test-Path $routePath) {
        # Append new section
        Add-Content -Path $routePath -Value ($newSection -join "`n") -Encoding ASCII
        Write-Color "       Appended run section to $routePath" "Green"
    } else {
        # Create new doc with frontmatter
        $doc = @()
        $doc += "---"
        $doc += "title: ""Drift Report $dateStr"""
        $doc += "domain: ""tech"""
        $doc += "last_updated: ""$dateStr"""
        $doc += "confidence: ""high"""
        $doc += "sources: [""drift-detect.ps1""]"
        $doc += "---"
        $doc += ""
        $doc += "# Drift Report -- $dateStr"
        $doc += ""
        $doc += "Auto-generated by drift-detect.ps1 with -RouteFindings flag."
        $doc += "Multiple runs in the same day are appended as separate ## Run at HH:MM sections."
        $doc += "Review and either: (a) fix the underlying issue, then drift returns clean,"
        $doc += "(b) move persistent findings into harness/IMPERFECTIONS.md if they need real audit,"
        $doc += "or (c) suppress false positives by tightening the drift-detect rule."
        $doc += ""
        $doc += "---"
        $doc += ($newSection -join "`n")
        Set-Content -Path $routePath -Value ($doc -join "`n") -Encoding ASCII
        Write-Color "       Created $routePath" "Green"

        # Update _index.md only on new file (not on append)
        $indexPath = "$harnessRoot\knowledge\_index.md"
        if (Test-Path $indexPath) {
            $indexContent = Get-Content $indexPath -Raw
            $entryLine = "- ``drift-$dateStr.md`` -- Drift Report (auto-generated by drift-detect.ps1)"
            if ($indexContent -notmatch [regex]::Escape("drift-$dateStr.md")) {
                # Add under Tech section if possible; otherwise at end
                if ($indexContent -match "(?m)^## Tech") {
                    # Insert before the next "## " section (after Tech)
                    $newIndex = $indexContent -replace "(?m)(?=^## (?!Tech))", "$entryLine`n`n", 1
                    if ($newIndex -ne $indexContent) {
                        Set-Content -Path $indexPath -Value $newIndex -Encoding ASCII
                        Write-Color "       Updated _index.md with drift-$dateStr entry" "Green"
                    } else {
                        # Append at end if pattern didn't match
                        Add-Content -Path $indexPath -Value "`n$entryLine" -Encoding ASCII
                        Write-Color "       Appended drift-$dateStr entry to _index.md" "Green"
                    }
                }
            }
        }
    }
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

Write-Color "=== DRIFT DETECTION BATTERY ===" "Cyan"
Write-Color "Project: $mtgSimRoot" "Gray"
Write-Color "Harness: $harnessRoot" "Gray"
Write-Color ("Started: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss")) "Gray"
Write-Color ""

Check-LoadBearingWIP
Check-RegistryConsistency
Check-StaleArchitecture
Check-StaleFindings
Check-SpecStatusDrift
Check-Imperfections
Check-CacheKeys
Check-RMWPattern
Check-SpecReferences

Write-Color ""
Write-Color "=== SUMMARY ===" "Cyan"
Write-Color ("Errors:   " + $errorCount)   $(if ($errorCount -gt 0)   { "Red" }    else { "Green" })
Write-Color ("Warnings: " + $warningCount) $(if ($warningCount -gt 0) { "Yellow" } else { "Green" })
Write-Color ("Total findings: " + $findings.Count) "Gray"
Write-Color ""

if (-not $Quiet -and $findings.Count -gt 0) {
    Write-Color "=== FINDINGS DETAIL ===" "Cyan"
    foreach ($f in $findings) {
        $color = switch ($f.severity) {
            "ERROR" { "Red" }
            "WARN"  { "Yellow" }
            "INFO"  { "Gray" }
            default { "White" }
        }
        Write-Color ("[{0}] {1}: {2}" -f $f.severity, $f.check, $f.detail) $color
        if ($f.fix) {
            Write-Color ("       fix: " + $f.fix) "DarkGray"
        }
    }
}

if ($Json) {
    $report = [PSCustomObject]@{
        timestamp     = (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
        error_count   = $errorCount
        warning_count = $warningCount
        findings      = $findings
    }
    $jsonOut = $report | ConvertTo-Json -Depth 5
    if ($OutFile) {
        Set-Content -Path $OutFile -Value $jsonOut -Encoding ASCII
        Write-Color "JSON written to $OutFile" "Gray"
    } else {
        Write-Output $jsonOut
    }
}

if ($OutFile -and -not $Json) {
    $md = @()
    $md += "# Drift Detection Report"
    $md += ""
    $md += "Generated: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
    $md += ""
    $md += "Errors: $errorCount | Warnings: $warningCount | Total: $($findings.Count)"
    $md += ""
    $md += "## Findings"
    $md += ""
    foreach ($f in $findings) {
        $md += ("- **[{0}] {1}**: {2}" -f $f.severity, $f.check, $f.detail)
        if ($f.fix) { $md += "  - fix: " + $f.fix }
    }
    Set-Content -Path $OutFile -Value ($md -join "`n") -Encoding ASCII
    Write-Color "Report written to $OutFile" "Gray"
}

# RouteFindings: write to knowledge/tech/drift-YYYY-MM-DD.md
if ($RouteFindings) {
    Write-Color ""
    Write-Color "=== ROUTING FINDINGS ===" "Cyan"
    Route-Findings
}

# Exit code
if ($errorCount -gt 0)        { exit 2 }
elseif ($warningCount -gt 0)  { exit 1 }
else                          { exit 0 }
