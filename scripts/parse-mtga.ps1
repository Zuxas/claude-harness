# parse-mtga.ps1 - MTGA Log Parser harness wrapper
# Parses Arena game logs, saves to match_log DB, optionally generates knowledge block
#
# Usage:
#   .\parse-mtga.ps1                          # parse current log, save to DB
#   .\parse-mtga.ps1 -All                     # parse current + prev log
#   .\parse-mtga.ps1 -DryRun                  # show matches without saving
#   .\parse-mtga.ps1 -Deck "Dimir Tempo"      # tag matches with deck name
#   .\parse-mtga.ps1 -Format "standard"       # tag matches with format
#   .\parse-mtga.ps1 -KnowledgeBlock          # generate harness knowledge block
#   .\parse-mtga.ps1 -RefreshCards            # rebuild card cache from MTGA data

param(
    [switch]$All,
    [switch]$DryRun,
    [switch]$KnowledgeBlock,
    [switch]$RefreshCards,
    [string]$Deck = "",
    [string]$Format = "standard"
)

$ProjectRoot = "E:\vscode ai project\mtg-meta-analyzer"
$HarnessRoot = "E:\vscode ai project\harness"

# Build command args
$args_list = @("--resolve-cards", "--summary")

if ($All)            { $args_list += "--all" }
if ($DryRun)         { $args_list += "--dry-run" }
if ($KnowledgeBlock) { $args_list += "--knowledge-block" }
if ($Deck)           { $args_list += "--deck"; $args_list += $Deck }
if ($Format)         { $args_list += "--format"; $args_list += $Format }

# Run parser
Write-Host "=== MTGA Log Parser ===" -ForegroundColor Cyan
Push-Location $ProjectRoot
python -m scrapers.mtga_log_parser @args_list
$exitCode = $LASTEXITCODE
Pop-Location

if ($exitCode -ne 0) {
    Write-Host "Parser failed with exit code $exitCode" -ForegroundColor Red
    exit $exitCode
}

# Generate knowledge block if requested
if ($KnowledgeBlock -and -not $DryRun) {
    Write-Host "`n=== Generating Knowledge Block ===" -ForegroundColor Cyan

    Push-Location $ProjectRoot
    $blockContent = python -m scrapers.mtga_log_parser @args_list 2>&1 |
        Select-String -Pattern "^---$" -Context 0,1000 |
        ForEach-Object { $_.Context.PostContext } |
        Out-String
    Pop-Location

    if ($blockContent) {
        $date = Get-Date -Format "yyyy-MM-dd"
        $blockPath = Join-Path $HarnessRoot "knowledge\mtg\mtga-session-$date.md"

        # Only write if file doesn't already exist
        if (-not (Test-Path $blockPath)) {
            $blockContent | Out-File -FilePath $blockPath -Encoding UTF8
            Write-Host "Knowledge block written: $blockPath" -ForegroundColor Green
        } else {
            Write-Host "Knowledge block already exists: $blockPath" -ForegroundColor Yellow
        }
    }
}

Write-Host "`nDone." -ForegroundColor Green
