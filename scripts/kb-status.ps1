# kb-status.ps1
# Shows knowledge base health at a glance
# Usage: powershell -ExecutionPolicy Bypass -File C:\temp\kb-status.ps1

$harnessRoot = "E:\vscode ai project\harness"
$knowledgeDir = "$harnessRoot\knowledge"

Write-Host "=== KNOWLEDGE BASE STATUS ===" -ForegroundColor Cyan
Write-Host ""

$domains = @("mtg", "career", "tech", "personal")
$totalBlocks = 0
$totalLines = 0

foreach ($domain in $domains) {
    $domainPath = "$knowledgeDir\$domain"
    if (Test-Path $domainPath) {
        $files = Get-ChildItem -Path $domainPath -Filter "*.md"
        $blockCount = $files.Count
        $lineCount = 0
        foreach ($f in $files) {
            $lineCount += (Get-Content $f.FullName | Measure-Object -Line).Lines
        }
        $totalBlocks += $blockCount
        $totalLines += $lineCount

        Write-Host "  $domain/: $blockCount blocks, $lineCount lines" -ForegroundColor Yellow
        foreach ($f in $files) {
            $lastWrite = $f.LastWriteTime.ToString("yyyy-MM-dd")
            Write-Host "    - $($f.Name) (updated: $lastWrite)" -ForegroundColor Gray
        }
    } else {
        Write-Host "  $domain/: [MISSING]" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "Total: $totalBlocks blocks, $totalLines lines" -ForegroundColor Green

# Check MEMORY.md
$memPath = "$harnessRoot\MEMORY.md"
if (Test-Path $memPath) {
    $memLines = (Get-Content $memPath | Measure-Object -Line).Lines
    $memDate = (Get-Item $memPath).LastWriteTime.ToString("yyyy-MM-dd HH:mm")
    Write-Host "MEMORY.md: $memLines lines (last updated: $memDate)" -ForegroundColor Magenta
} else {
    Write-Host "MEMORY.md: [MISSING]" -ForegroundColor Red
}

Write-Host ""
Write-Host "=== END STATUS ===" -ForegroundColor Cyan
