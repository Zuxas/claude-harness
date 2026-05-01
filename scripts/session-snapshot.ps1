# session-snapshot.ps1
# Captures current harness + mtg-sim state into a single markdown document.
# Designed as the "shift handoff" pattern: next-session-Claude reads this at
# startup to land into the state of work without re-explaining.
#
# Anthropic's effective-harness post describes structured progress files that
# let a new agent quickly understand the state of work, analogous to a shift
# handoff between engineers who've never met. This script generates one.
#
# USAGE:
#   .\session-snapshot.ps1                       # writes timestamped snapshot
#   .\session-snapshot.ps1 -RunDriftDetect       # also runs drift-detect.ps1, embeds findings in snapshot
#   .\session-snapshot.ps1 -RunLint              # also runs lint-mtg-sim.py, embeds findings in snapshot
#   .\session-snapshot.ps1 -RouteDriftFindings   # also passes -RouteFindings to drift-detect,
#                                                # writes/appends harness/knowledge/tech/drift-YYYY-MM-DD.md
#                                                # (only effective when -RunDriftDetect also set)
#   .\session-snapshot.ps1 -ShowOnly             # print to stdout, don't write
#   .\session-snapshot.ps1 -SkipGraphSnapshot    # skip the daily graph-snapshot.py call
#
# OUTPUT:
#   harness/state/snapshots/snapshot-YYYY-MM-DD-HHMM.md   (timestamped)
#   harness/state/latest-snapshot.md                      (rolling)
#   harness/knowledge/tech/drift-YYYY-MM-DD.md            (only if -RouteDriftFindings)
#   harness/state/graph-snapshots/YYYY-MM-DD.json         (added 2026-04-27, unless -SkipGraphSnapshot)
#
# ENCODING NOTE: this file is intentionally ASCII-only. Windows PowerShell 5.1
# reads .ps1 files as cp1252 by default unless a BOM is present, so any UTF-8
# multibyte character (em-dash, smart quotes, etc.) corrupts on read and breaks
# the parser. If you edit this file, do not introduce non-ASCII characters
# unless you also force UTF-8-with-BOM on save.
#
# Last updated: 2026-04-27 (v1.2: added graph-snapshot.py integration)

param(
    [switch]$RunDriftDetect,
    [switch]$RunLint,
    [switch]$RouteDriftFindings,
    [switch]$ShowOnly,
    [switch]$SkipGraphSnapshot
)

$ErrorActionPreference = "Continue"

# Paths
$projectRoot   = "E:\vscode ai project"
$mtgSimRoot    = "$projectRoot\mtg-sim"
$harnessRoot   = "$projectRoot\harness"
$knowledgeTech = "$harnessRoot\knowledge\tech"
$specsDir      = "$harnessRoot\specs"
$snapshotDir   = "$harnessRoot\state\snapshots"
$imperfPath    = "$harnessRoot\IMPERFECTIONS.md"

if (-not (Test-Path $snapshotDir)) {
    New-Item -ItemType Directory -Path $snapshotDir -Force | Out-Null
}

$timestamp = Get-Date -Format "yyyy-MM-dd-HHmm"
$humanTime = Get-Date -Format "yyyy-MM-dd HH:mm"
$snapshotPath = "$snapshotDir\snapshot-$timestamp.md"
$latestPath   = "$harnessRoot\state\latest-snapshot.md"

# Build the snapshot in a string list, joined at the end
$lines = @()

function Add-Line { param([string]$Line) $script:lines += $Line }
function Add-Header { param([string]$H) $script:lines += ""; $script:lines += "## $H"; $script:lines += "" }
function Add-SubHeader { param([string]$H) $script:lines += ""; $script:lines += "### $H"; $script:lines += "" }
function Add-Code { param([string]$Lang, [string]$Body)
    $script:lines += '```' + $Lang
    $script:lines += $Body
    $script:lines += '```'
}

# ===========================================================================
# HEADER
# ===========================================================================

Add-Line "# Session Snapshot $timestamp"
Add-Line ""
Add-Line "**Generated:** $humanTime"
Add-Line "**By:** session-snapshot.ps1"
Add-Line ""
Add-Line "Read this at session start to land into the state of work. Sections in"
Add-Line "order of operational importance: pending work, drift, open specs, open"
Add-Line "imperfections, recent commits, quality grades."

# ===========================================================================
# PENDING WORK (from MEMORY.md)
# ===========================================================================

Add-Header "Pending work (from MEMORY.md)"

$memPath = "$harnessRoot\MEMORY.md"
if (Test-Path $memPath) {
    $memContent = Get-Content $memPath -Raw
    # Extract the "## Pending Items" section
    $pendingMatch = [regex]::Match($memContent,
        "(?s)##\s+Pending Items\s+(.*?)(?=\n##\s+|\z)")
    if ($pendingMatch.Success) {
        $pending = $pendingMatch.Groups[1].Value.Trim()
        Add-Line $pending
    } else {
        Add-Line "_(Pending Items section not found in MEMORY.md)_"
    }
} else {
    Add-Line "_(MEMORY.md not found)_"
}

# ===========================================================================
# DRIFT FINDINGS (optional -- runs drift-detect.ps1)
# ===========================================================================

if ($RunDriftDetect) {
    Add-Header "Drift findings"
    $driftScript = "$harnessRoot\scripts\drift-detect.ps1"
    if (Test-Path $driftScript) {
        $driftReportPath = "$snapshotDir\drift-$timestamp.md"
        # Build args for drift-detect: always quiet + outfile, optionally route
        $driftArgs = @("-ExecutionPolicy", "Bypass", "-File", $driftScript, "-Quiet", "-OutFile", $driftReportPath)
        if ($RouteDriftFindings) {
            $driftArgs += "-RouteFindings"
        }
        & powershell @driftArgs 2>&1 | Out-Null
        if (Test-Path $driftReportPath) {
            $driftBody = Get-Content $driftReportPath -Raw
            Add-Line $driftBody
            if ($RouteDriftFindings) {
                $dateStr = Get-Date -Format "yyyy-MM-dd"
                $routedDocPath = "$knowledgeTech\drift-$dateStr.md"
                if (Test-Path $routedDocPath) {
                    Add-Line ""
                    Add-Line "_Findings also routed to: ``harness/knowledge/tech/drift-$dateStr.md``_"
                }
            }
        } else {
            Add-Line "_(drift-detect.ps1 ran but produced no report)_"
        }
    } else {
        Add-Line "_(drift-detect.ps1 not found at $driftScript)_"
    }
}

# ===========================================================================
# LINT FINDINGS (optional -- runs lint-mtg-sim.py)
# ===========================================================================

if ($RunLint) {
    Add-Header "Lint findings (mtg-sim)"
    $lintScript = "$harnessRoot\scripts\lint-mtg-sim.py"
    if (Test-Path $lintScript) {
        Push-Location $mtgSimRoot
        try {
            $lintOutput = & python $lintScript 2>&1
            Add-Code "" ($lintOutput -join "`n")
        } finally {
            Pop-Location
        }
    } else {
        Add-Line "_(lint-mtg-sim.py not found at $lintScript)_"
    }
}

# ===========================================================================
# OPEN SPECS (PROPOSED + EXECUTING from harness/specs/)
# ===========================================================================

Add-Header "Open specs"

if (Test-Path $specsDir) {
    $specs = Get-ChildItem -Path $specsDir -Filter "*.md" |
             Where-Object { $_.Name -notin @("README.md", "_template.md", "_index.md", "RETROACTIVE.md") }

    $proposed  = @()
    $executing = @()
    $shipped   = @()
    $other     = @()

    foreach ($spec in $specs) {
        $content = Get-Content $spec.FullName -Raw -ErrorAction SilentlyContinue
        if (-not $content) { continue }
        $statusMatch = [regex]::Match($content, "(?m)^status:\s*[`"']?(\w+)[`"']?")
        $status = if ($statusMatch.Success) { $statusMatch.Groups[1].Value } else { "UNKNOWN" }

        $titleMatch = [regex]::Match($content, "(?m)^title:\s*[`"'](.+?)[`"']")
        $title = if ($titleMatch.Success) { $titleMatch.Groups[1].Value } else { $spec.BaseName }

        $age = ((Get-Date) - $spec.LastWriteTime).TotalDays
        $entry = "- **$($spec.Name)** [$status] -- $title (last touched $([math]::Round($age,1))d ago)"

        switch ($status) {
            "PROPOSED"  { $proposed  += $entry }
            "EXECUTING" { $executing += $entry }
            "SHIPPED"   { $shipped   += $entry }
            default     { $other     += $entry }
        }
    }

    if ($executing.Count -gt 0) {
        Add-SubHeader "Executing ($($executing.Count))"
        $executing | ForEach-Object { Add-Line $_ }
    }
    if ($proposed.Count -gt 0) {
        Add-SubHeader "Proposed ($($proposed.Count))"
        $proposed | ForEach-Object { Add-Line $_ }
    }
    if ($shipped.Count -gt 0) {
        Add-SubHeader "Shipped this session ($($shipped.Count))"
        $shipped | ForEach-Object { Add-Line $_ }
    }
    if ($other.Count -gt 0) {
        Add-SubHeader "Other status ($($other.Count))"
        $other | ForEach-Object { Add-Line $_ }
    }
    if ($executing.Count + $proposed.Count + $shipped.Count + $other.Count -eq 0) {
        Add-Line "_(no specs found in $specsDir)_"
    }
} else {
    Add-Line "_(specs directory not present)_"
}

# ===========================================================================
# OPEN IMPERFECTIONS
# ===========================================================================

Add-Header "Open imperfections"

if (Test-Path $imperfPath) {
    $imperfContent = Get-Content $imperfPath -Raw
    # Extract entry headers (## prefix), exclude top-level # title
    $entryMatches = [regex]::Matches($imperfContent, "(?m)^##\s+(.+)$")
    if ($entryMatches.Count -gt 0) {
        Add-Line "Total entries: $($entryMatches.Count)"
        Add-Line ""
        Add-Line "Top entries (by file order):"
        $count = 0
        foreach ($m in $entryMatches) {
            if ($count -ge 10) { break }
            Add-Line "- $($m.Groups[1].Value)"
            $count++
        }
    } else {
        Add-Line "_(IMPERFECTIONS.md exists but no entries found)_"
    }
} else {
    Add-Line "_(IMPERFECTIONS.md not found)_"
}

# ===========================================================================
# RECENT COMMITS (mtg-sim, last 7 days)
# ===========================================================================

Add-Header "Recent commits (mtg-sim, last 7 days)"

if (Test-Path $mtgSimRoot) {
    Push-Location $mtgSimRoot
    try {
        $log = git log --since="7 days ago" --pretty=format:"%h %ad %s" --date=short 2>&1
        if ($log) {
            Add-Code "" ($log -join "`n")
        } else {
            Add-Line "_(no commits in last 7 days, or git failed)_"
        }
    } finally {
        Pop-Location
    }
} else {
    Add-Line "_(mtg-sim repo not found)_"
}

# ===========================================================================
# UNCOMMITTED CHANGES (mtg-sim)
# ===========================================================================

Add-Header "Uncommitted changes (mtg-sim)"

if (Test-Path $mtgSimRoot) {
    Push-Location $mtgSimRoot
    try {
        $status = git status --short 2>&1
        if ($status) {
            Add-Code "" ($status -join "`n")
            $untracked = ($status | Where-Object { $_ -match "^\?\?" }).Count
            $modified  = ($status | Where-Object { $_ -match "^.M " -or $_ -match "^M " }).Count
            $staged    = ($status | Where-Object { $_ -match "^M " -or $_ -match "^A " }).Count
            Add-Line ""
            Add-Line "Summary: $modified modified, $staged staged, $untracked untracked"
            if ($untracked -gt 0) {
                Add-Line ""
                Add-Line "**WARNING:** untracked files present. Run drift-detect to check for load-bearing-WIP."
            }
        } else {
            Add-Line "_(working tree clean)_"
        }
    } finally {
        Pop-Location
    }
}

# ===========================================================================
# QUALITY GRADES (summary from mtg-sim-quality-grades.md)
# ===========================================================================

Add-Header "Quality grades (latest)"

$qgPath = "$knowledgeTech\mtg-sim-quality-grades.md"
if (Test-Path $qgPath) {
    $qgContent = Get-Content $qgPath -Raw
    # Extract the grade table if present (lines with | Domain | ... |)
    $tableMatches = [regex]::Matches($qgContent,
        "(?m)^\|.*\|.*\|.*\|.*\|.*$")
    if ($tableMatches.Count -gt 0) {
        Add-Line "From mtg-sim-quality-grades.md:"
        Add-Line ""
        $count = 0
        foreach ($m in $tableMatches) {
            if ($count -ge 12) { break }  # avoid dumping the whole doc
            Add-Line $m.Value
            $count++
        }
    } else {
        Add-Line "_(quality-grades.md exists but no table format found; read it directly)_"
    }
    $qgMtime = (Get-Item $qgPath).LastWriteTime
    $qgAge = ((Get-Date) - $qgMtime).TotalDays
    Add-Line ""
    Add-Line "Last updated: $([math]::Round($qgAge,1)) days ago"
} else {
    Add-Line "_(quality-grades.md not found)_"
}

# ===========================================================================
# RECENT FINDINGS DOCS (knowledge/tech/*-2026-*.md, last 14 days)
# ===========================================================================

Add-Header "Recent findings docs (last 14 days)"

if (Test-Path $knowledgeTech) {
    $cutoff = (Get-Date).AddDays(-14)
    $recent = Get-ChildItem -Path $knowledgeTech -Filter "*-2026-*.md" |
              Where-Object { $_.LastWriteTime -gt $cutoff } |
              Sort-Object LastWriteTime -Descending

    if ($recent.Count -gt 0) {
        foreach ($f in $recent) {
            $age = ((Get-Date) - $f.LastWriteTime).TotalDays
            # Pull first line that looks like a status indicator
            $body = Get-Content $f.FullName -Raw
            $statusLine = ""
            if ($body -match "RESOLVED")   { $statusLine = "[RESOLVED]" }
            elseif ($body -match "PARTIAL") { $statusLine = "[PARTIAL]" }
            elseif ($body -match "SURFACED") { $statusLine = "[SURFACED]" }
            elseif ($body -match "in progress|EXECUTING") { $statusLine = "[IN-PROGRESS]" }
            else { $statusLine = "[?]" }
            Add-Line "- **$($f.Name)** $statusLine -- $([math]::Round($age,1))d ago"
        }
    } else {
        Add-Line "_(no findings docs touched in last 14 days)_"
    }
} else {
    Add-Line "_(knowledge/tech/ not found)_"
}

# ===========================================================================
# FOOTER
# ===========================================================================

Add-Line ""
Add-Line "---"
Add-Line ""
Add-Line "_Snapshot generated by session-snapshot.ps1. Re-run via:_"
Add-Line "_``powershell -ExecutionPolicy Bypass -File harness\scripts\session-snapshot.ps1 -RunDriftDetect -RunLint -RouteDriftFindings``_"

# ===========================================================================
# Output
# ===========================================================================

$body = $lines -join "`r`n"

if ($ShowOnly) {
    Write-Output $body
} else {
    Set-Content -Path $snapshotPath -Value $body -Encoding ASCII
    Set-Content -Path $latestPath   -Value $body -Encoding ASCII
    Write-Host "Snapshot written to: $snapshotPath" -ForegroundColor Green
    Write-Host "Latest:              $latestPath" -ForegroundColor Green
    if ($RouteDriftFindings -and $RunDriftDetect) {
        $dateStr = Get-Date -Format "yyyy-MM-dd"
        Write-Host "Drift findings:      $knowledgeTech\drift-$dateStr.md" -ForegroundColor Green
    }

    # =======================================================================
    # GRAPH SNAPSHOT (added 2026-04-27)
    # Emits daily JSON of project nodes/edges to harness/state/graph-snapshots/
    # for time-lapse visualization. Additive artifact; failure here does not
    # affect the main snapshot above.
    # =======================================================================
    if (-not $SkipGraphSnapshot) {
        $graphScript = "$harnessRoot\scripts\graph-snapshot.py"
        if (Test-Path $graphScript) {
            Write-Host ""
            Write-Host "[graph-snapshot] Generating daily project graph snapshot..." -ForegroundColor Cyan
            try {
                $env:PYTHONIOENCODING = "utf-8"
                $graphOutput = & python $graphScript 2>&1
                if ($LASTEXITCODE -eq 0) {
                    Write-Host "[graph-snapshot] $graphOutput" -ForegroundColor Green
                } else {
                    Write-Host "[graph-snapshot] WARN exit code $LASTEXITCODE -- snapshot may be partial" -ForegroundColor Yellow
                    Write-Host $graphOutput -ForegroundColor Yellow
                }
            } catch {
                Write-Host "[graph-snapshot] ERROR: $_" -ForegroundColor Red
                # Do not fail the parent snapshot job
            }
        } else {
            Write-Host "[graph-snapshot] script not found at $graphScript -- skipping" -ForegroundColor Yellow
        }
    }

    Write-Host ""
    Write-Host "Read at next session start to resume context." -ForegroundColor Cyan
}
