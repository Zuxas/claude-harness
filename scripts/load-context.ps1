# load-context.ps1
# Loads relevant knowledge blocks based on domain keyword
# Usage: powershell -ExecutionPolicy Bypass -File C:\temp\load-context.ps1 -Domain mtg

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("mtg", "career", "tech", "personal", "all")]
    [string]$Domain
)

$harnessRoot = "E:\vscode ai project\harness"
$knowledgeDir = "$harnessRoot\knowledge"

Write-Host "=== HARNESS CONTEXT LOADER ===" -ForegroundColor Cyan
Write-Host "Domain: $Domain" -ForegroundColor Yellow
Write-Host ""

# Always load index first
$indexPath = "$knowledgeDir\_index.md"
if (Test-Path $indexPath) {
    Write-Host "--- _index.md ---" -ForegroundColor Green
    Get-Content $indexPath
    Write-Host ""
}

# Load domain-specific blocks
if ($Domain -eq "all") {
    $dirs = Get-ChildItem -Path $knowledgeDir -Directory
} else {
    $dirs = Get-ChildItem -Path "$knowledgeDir\$Domain" -Directory -ErrorAction SilentlyContinue
    if (-not $dirs) {
        # Single domain folder
        $dirs = @([PSCustomObject]@{FullName = "$knowledgeDir\$Domain"})
    }
}

foreach ($dir in $dirs) {
    $mdFiles = Get-ChildItem -Path $dir.FullName -Filter "*.md" -ErrorAction SilentlyContinue
    foreach ($file in $mdFiles) {
        Write-Host "--- $($file.Name) ---" -ForegroundColor Green
        Get-Content $file.FullName
        Write-Host ""
    }
}

# Always load MEMORY.md
$memoryPath = "$harnessRoot\MEMORY.md"
if (Test-Path $memoryPath) {
    Write-Host "--- MEMORY.md (session state) ---" -ForegroundColor Magenta
    Get-Content $memoryPath
    Write-Host ""
}

Write-Host "=== CONTEXT LOADED ===" -ForegroundColor Cyan
