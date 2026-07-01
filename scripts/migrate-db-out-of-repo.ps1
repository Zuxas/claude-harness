# migrate-db-out-of-repo.ps1 -- move mtg_meta.db out of the repo tree (2026-07-01)
#
# WHY: the DB is the data moat; living inside mtg-meta-analyzer/data/ ties it to a
# git working tree it doesn't belong in. All consumers now resolve the path via
# the MTG_META_DB env var (GUI/scrapers/MCP via db.database, sim via db_bridge,
# site export via generate_site_data) so the file can live anywhere.
#
# USAGE (close the GUI + make sure no nightly task is mid-run first):
#   powershell -ExecutionPolicy Bypass -File migrate-db-out-of-repo.ps1 -Target "D:\mtg-data"
param([string]$Target = "D:\mtg-data")

$ErrorActionPreference = "Stop"
$repo    = "E:\vscode ai project\mtg-meta-analyzer"
$src     = Join-Path $repo "data\mtg_meta.db"
$srcArch = Join-Path $repo "data\mtg_archive.db"

if (-not (Test-Path (Split-Path $Target -Qualifier))) { throw "Target drive missing: $Target" }
New-Item -ItemType Directory -Force -Path $Target | Out-Null

foreach ($pair in @(@($src, "mtg_meta.db"), @($srcArch, "mtg_archive.db"))) {
    $from = $pair[0]; $to = Join-Path $Target $pair[1]
    if (-not (Test-Path $from)) { Write-Host "skip (missing): $from"; continue }
    Write-Host "Copying $from -> $to ..."
    Copy-Item $from $to -Force
    $h1 = (Get-FileHash $from -Algorithm SHA256).Hash
    $h2 = (Get-FileHash $to   -Algorithm SHA256).Hash
    if ($h1 -ne $h2) { throw "HASH MISMATCH on $($pair[1]) -- aborting, originals untouched" }
    Write-Host "  hash verified OK"
}

# Machine-wide knob (new shells only; reboot or re-login for scheduled tasks)
setx MTG_META_DB          (Join-Path $Target "mtg_meta.db")    /M
setx MTG_META_ARCHIVE_DB  (Join-Path $Target "mtg_archive.db") /M

# Belt-and-suspenders: also point config.ini (covers processes started before re-login)
$cfg = Join-Path $repo "config.ini"
if (Test-Path $cfg) {
    $content = Get-Content $cfg -Raw
    $content = $content -replace '(?m)^path\s*=.*$',         ("path = " + (Join-Path $Target "mtg_meta.db"))
    $content = $content -replace '(?m)^archive_path\s*=.*$', ("archive_path = " + (Join-Path $Target "mtg_archive.db"))
    Set-Content $cfg $content -NoNewline
    Write-Host "config.ini updated"
}

# Keep originals as safety net (rename, don't delete) -- remove manually after a clean week
Rename-Item $src     "$src.migrated-$(Get-Date -Format yyyyMMdd)"     -ErrorAction SilentlyContinue
Rename-Item $srcArch "$srcArch.migrated-$(Get-Date -Format yyyyMMdd)" -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "DONE. Verify: (1) launch GUI, check Dashboard loads; (2) python scripts\generate_site_data.py --help;"
Write-Host "(3) after a clean nightly run + one week, delete the *.migrated-* files in $repo\data"
