# process-inbox.ps1
# Scans harness/inbox/ for raw source files, compiles each into a
# knowledge block via Gemma 4, then moves originals to inbox/processed/
#
# FILE NAMING CONVENTION:
#   domain--blockname.txt
#   domain--blockname.md
#   domain--blockname.log
#
# EXAMPLES:
#   mtg--rcq-results-apr.txt       -> knowledge/mtg/rcq-results-apr.md
#   tech--new-tool-notes.txt       -> knowledge/tech/new-tool-notes.md
#   career--interview-prep.md      -> knowledge/career/interview-prep.md
#
# USAGE:
#   .\process-inbox.ps1            (uses gemma4 default)
#   .\process-inbox.ps1 -Model gemma4:26b  (uses 26B for higher quality)
#
# DROP FILES IN: E:\vscode ai project\harness\inbox\
# They get compiled and moved automatically.

param(
    [string]$Model = "gemma4"
)

$ErrorActionPreference = "Stop"
$HarnessRoot = "E:\vscode ai project\harness"
$InboxDir = Join-Path $HarnessRoot "inbox"
$ProcessedDir = Join-Path $InboxDir "processed"
$CompileScript = Join-Path $HarnessRoot "scripts\compile-knowledge.ps1"

$ValidDomains = @("mtg", "career", "tech", "personal")

# Find all files in inbox (not in processed/)
$Files = Get-ChildItem -Path $InboxDir -File | Where-Object { $_.DirectoryName -eq $InboxDir }

if ($Files.Count -eq 0) {
    Write-Host "[inbox] No files found in $InboxDir" -ForegroundColor Yellow
    Write-Host "[inbox] Drop files named domain--blockname.txt to compile them." -ForegroundColor Yellow
    Write-Host "[inbox] Valid domains: $($ValidDomains -join ', ')" -ForegroundColor Yellow
    exit 0
}

Write-Host "[inbox] Found $($Files.Count) file(s) to process" -ForegroundColor Cyan
Write-Host ""

$Processed = 0
$Failed = 0

foreach ($File in $Files) {
    $BaseName = $File.BaseName  # filename without extension
    
    # Parse domain--blockname pattern
    if ($BaseName -notmatch "^(\w+)--(.+)$") {
        Write-Host "[inbox] SKIP: $($File.Name) -- bad format, use domain--blockname.txt" -ForegroundColor Red
        $Failed++
        continue
    }
    
    $Domain = $Matches[1]
    $BlockName = $Matches[2]
    
    if ($Domain -notin $ValidDomains) {
        Write-Host "[inbox] SKIP: $($File.Name) -- invalid domain '$Domain'" -ForegroundColor Red
        Write-Host "        Valid domains: $($ValidDomains -join ', ')" -ForegroundColor Red
        $Failed++
        continue
    }

    Write-Host "[inbox] Processing: $($File.Name) -> knowledge/$Domain/$BlockName.md" -ForegroundColor Cyan
    
    try {
        & $CompileScript -SourceFile $File.FullName -Domain $Domain -BlockName $BlockName -Model $Model
        
        # Move to processed
        $Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
        $NewName = "${Timestamp}_$($File.Name)"
        Move-Item -Path $File.FullName -Destination (Join-Path $ProcessedDir $NewName)
        Write-Host "[inbox] Moved original to processed/$NewName" -ForegroundColor Green
        $Processed++
    } catch {
        Write-Host "[inbox] FAILED: $($File.Name) -- $_" -ForegroundColor Red
        $Failed++
    }
    
    Write-Host ""
}

Write-Host "=== INBOX COMPLETE ===" -ForegroundColor Green
Write-Host "  Processed: $Processed"
Write-Host "  Failed:    $Failed"
Write-Host "  Remaining: $($Files.Count - $Processed - $Failed)"
