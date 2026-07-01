# backup-data-moat.ps1 -- weekly snapshot of everything git does NOT protect (2026-07-01)
# Covers: mtg_meta.db (live-safe sqlite backup), harness MEMORY.md + IMPERFECTIONS.md,
# harness/knowledge/ (mtg/personal/career are gitignored), Team Resolve git bundle.
# Rotation: keep newest 4. Register weekly:
#   schtasks /Create /TN "Zuxas-DataMoat-Backup" /SC WEEKLY /D SUN /ST 05:30 /RL HIGHEST ^
#     /TR "powershell -ExecutionPolicy Bypass -File \"E:\vscode ai project\harness\scripts\backup-data-moat.ps1\""
param([string]$Dest = "D:\backups\data-moat")

$ErrorActionPreference = "Stop"
$stamp = Get-Date -Format "yyyy-MM-dd"
$work  = Join-Path $env:TEMP "moat-$stamp"
New-Item -ItemType Directory -Force -Path $Dest, $work | Out-Null

# 1) sqlite live-safe snapshot via the backup API (never plain-copy a hot DB)
$db = $env:MTG_META_DB
if (-not $db) { $db = "E:\vscode ai project\mtg-meta-analyzer\data\mtg_meta.db" }
python -c "import sqlite3,sys; s=sqlite3.connect(sys.argv[1]); d=sqlite3.connect(sys.argv[2]); s.backup(d); d.close(); s.close(); print('db snapshot ok')" `
    "$db" "$work\mtg_meta.db"

# 2) the gitignored knowledge moat + session memory
Copy-Item "E:\vscode ai project\harness\MEMORY.md"          $work -ErrorAction SilentlyContinue
Copy-Item "E:\vscode ai project\harness\IMPERFECTIONS.md"   $work -ErrorAction SilentlyContinue
Copy-Item "E:\vscode ai project\harness\knowledge" (Join-Path $work "knowledge") -Recurse

# 3) Team Resolve history (local-only repo -> bundle = single-file full clone)
git -C "E:\vscode ai project\Team Resolve" bundle create "$work\team-resolve.bundle" --all 2>$null

# 4) zip + rotate (keep 4)
$zip = Join-Path $Dest "data-moat-$stamp.zip"
Compress-Archive -Path "$work\*" -DestinationPath $zip -Force
Remove-Item $work -Recurse -Force
Get-ChildItem $Dest -Filter "data-moat-*.zip" | Sort-Object Name -Descending | Select-Object -Skip 4 | Remove-Item
Write-Host "Backup written: $zip ($([math]::Round((Get-Item $zip).Length/1MB,1)) MB). Kept newest 4."
