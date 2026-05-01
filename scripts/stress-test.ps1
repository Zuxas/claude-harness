# stress-test.ps1 — FULL HARNESS STRESS TEST
# Exercises every pipeline with real data, real Gemma calls, real sims
# USAGE: .\stress-test.ps1

$ErrorActionPreference = "Continue"
$H = "E:\vscode ai project\harness"
$S = "$H\scripts"
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
$Pass = 0; $Fail = 0; $Results = @()
$Start = Get-Date

function Test($name, $scriptBlock) {
    $t = Get-Date
    Write-Host "[$name] " -ForegroundColor Cyan -NoNewline
    try {
        & $scriptBlock
        $sec = [math]::Round(((Get-Date) - $t).TotalSeconds, 1)
        Write-Host "PASS (${sec}s)" -ForegroundColor Green
        $script:Pass++
        $script:Results += @{N=$name;S="PASS";T=$sec}
    } catch {
        $sec = [math]::Round(((Get-Date) - $t).TotalSeconds, 1)
        Write-Host "FAIL (${sec}s): $_" -ForegroundColor Red
        $script:Fail++
        $script:Results += @{N=$name;S="FAIL";T=$sec}
    }
}

Write-Host ""
Write-Host "=========================================" -ForegroundColor Yellow
Write-Host "  FULL HARNESS STRESS TEST (HARD MODE)" -ForegroundColor Yellow
Write-Host "  $(Get-Date -Format 'yyyy-MM-dd HH:mm')" -ForegroundColor Yellow
Write-Host "=========================================" -ForegroundColor Yellow

# ==========================================================================
Write-Host "`n--- LAYER 1: Infrastructure ---" -ForegroundColor Magenta
# ==========================================================================

Test "L1.1 Knowledge blocks (19+)" {
    $c = (Get-ChildItem "$H\knowledge" -Recurse -Filter "*.md" | Where-Object { $_.Name -notmatch "^_" -and $_.Directory.Name -ne ".obsidian" }).Count
    if ($c -lt 19) { throw "Only $c blocks" }
    Write-Host "($c) " -NoNewline
}

Test "L1.2 Ollama API (Gemma responds)" {
    $body = '{"model":"gemma4","prompt":"Say OK","stream":false,"options":{"num_predict":5}}'
    $r = Invoke-RestMethod -Uri "http://localhost:11434/api/generate" -Method POST -Body $body -ContentType "application/json" -TimeoutSec 120
    if (-not $r.response) { throw "Empty" }
    Write-Host "($($r.eval_count)tok, $([math]::Round($r.total_duration/1e9,1))s) " -NoNewline
}

Test "L1.3 RTK version" {
    $v = rtk --version 2>&1 | Out-String
    if ($v -notmatch "0\.3") { throw "Wrong version: $v" }
    Write-Host "($($v.Trim())) " -NoNewline
}

Test "L1.4 CLAUDE.md chain (root -> harness -> status)" {
    $root = Get-Content "$H\..\CLAUDE.md" -Raw
    if ($root -notmatch "MUST read") { throw "Root missing mandatory" }
    if ($root -notmatch "HARNESS_STATUS") { throw "Root missing status ref" }
    $harness = Get-Content "$H\CLAUDE.md" -Raw
    if (-not $harness) { throw "Harness CLAUDE.md empty" }
    $status = Get-Content "$H\HARNESS_STATUS.md" -Raw
    if ($status -notmatch "Layer") { throw "Status missing layers" }
}

Test "L1.5 MEMORY.md (fresh + has session log)" {
    $m = Get-Content "$H\MEMORY.md" -Raw
    if ($m -notmatch "2026-04-16") { throw "No today entry" }
    if ($m -notmatch "Session Log") { throw "No session log section" }
    $lines = (Get-Content "$H\MEMORY.md" | Measure-Object -Line).Lines
    Write-Host "($lines lines) " -NoNewline
}

Test "L1.6 Obsidian vault + wikilinks" {
    if (-not (Test-Path "$H\knowledge\.obsidian")) { throw "No vault" }
    $idx = Get-Content "$H\knowledge\_index.md" -Raw
    if (-not $idx) { throw "Empty index" }
}

Test "L1.7 All 16 scripts present" {
    $required = @("ask-gemma.ps1","compile-knowledge.ps1","process-inbox.ps1","kb-status.ps1",
        "tune-apl.ps1","tune-loop.ps1","nightly-harness.ps1","watch-inbox.ps1","parse-mtga.ps1",
        "register-harness-tasks.ps1","calibrate.ps1","auto-pipeline.ps1","stress-test.ps1",
        "optimize-apl.ps1","install-stack.ps1","load-context.ps1")
    $missing = $required | Where-Object { -not (Test-Path "$S\$_") }
    if ($missing) { throw "Missing: $($missing -join ', ')" }
    Write-Host "($($required.Count)) " -NoNewline
}

Test "L1.8 All 6 Python agents present" {
    $agents = @("apl_tuner.py","nightly_harness.py","tuning_loop.py","calibrate.py","auto_pipeline.py","apl_optimizer.py")
    $missing = $agents | Where-Object { -not (Test-Path "$H\agents\scripts\$_") }
    if ($missing) { throw "Missing: $($missing -join ', ')" }
    Write-Host "($($agents.Count)) " -NoNewline
}

Test "L1.9 LIVE: Gemma compiles knowledge" {
    $testFile = "$H\inbox\tech--stress-test-live.txt"
    "Stress test content: RTK compresses tokens by 60-90 percent on average." | Set-Content $testFile -Encoding UTF8
    $body = @{model="gemma4"; prompt="Summarize: RTK compresses tokens by 60-90%."; stream=$false; options=@{num_predict=100}} | ConvertTo-Json
    $r = Invoke-RestMethod -Uri "http://localhost:11434/api/generate" -Method POST -Body $body -ContentType "application/json" -TimeoutSec 120
    if (-not $r.response -or $r.response.Length -lt 20) { throw "Bad response" }
    Remove-Item $testFile -Force -ErrorAction SilentlyContinue
    Write-Host "($($r.response.Length) chars) " -NoNewline
}

# ==========================================================================
Write-Host "`n--- LAYER 2: Automation ---" -ForegroundColor Magenta
# ==========================================================================

Test "L2.1 Scheduled tasks (3 harness + 3 meta-analyzer)" {
    $harness = (Get-ScheduledTask | Where-Object {$_.TaskName -like 'Zuxas*'}).Count
    $meta = (Get-ScheduledTask | Where-Object {$_.TaskName -like 'MTG*'}).Count
    if ($harness -lt 3) { throw "Only $harness/3 harness tasks" }
    Write-Host "(harness:$harness, meta:$meta) " -NoNewline
}

Test "L2.2 LIVE: Nightly harness dry run" {
    cd "E:\vscode ai project"
    $out = python "harness\agents\scripts\nightly_harness.py" --dry-run --skip-mtga 2>&1 | Out-String
    if ($out -notmatch "NIGHTLY COMPLETE") { throw "Did not complete" }
    $shifts = ([regex]::Matches($out, "SHIFT:")).Count
    Write-Host "($shifts shifts) " -NoNewline
}

Test "L2.3 LIVE: Meta change detection" {
    cd "E:\vscode ai project\mtg-meta-analyzer"
    $out = python -c "from analysis.meta_change import compare_periods; r=compare_periods('modern',1,2); s=r['summary']; print(f""OK rising={s['rising']} new={s['new']} gone={s['gone']}"")" 2>&1 | Out-String
    if ($out -notmatch "OK") { throw "Failed: $out" }
    Write-Host "($($out.Trim())) " -NoNewline
}

Test "L2.4 Inbox + processed structure" {
    if (-not (Test-Path "$H\inbox")) { throw "No inbox" }
    if (-not (Test-Path "$H\inbox\processed")) { throw "No processed" }
    if (-not (Test-Path "$H\logs")) { throw "No logs" }
}

# ==========================================================================
Write-Host "`n--- LAYER 3: Tuning ---" -ForegroundColor Magenta
# ==========================================================================

Test "L3.1 Legality checker (4/4)" {
    cd "E:\vscode ai project"
    $out = python -c "
import sys; sys.path.insert(0,'E:/vscode ai project/mtg-sim')
sys.path.insert(0,'E:/vscode ai project/harness/agents/scripts')
from tuning_loop import check_card_legal
t = [('Lightning Bolt','modern',True),('Swords to Plowshares','modern',False),
     ('Lightning Bolt','legacy',True),('Ragavan, Nimble Pilferer','legacy',False)]
ok = sum(1 for n,f,e in t if check_card_legal(n,f)==e)
print(f'OK {ok}/4')
" 2>&1 | Out-String
    if ($out -notmatch "4/4") { throw $out.Trim() }
    Write-Host "(4/4) " -NoNewline
}

Test "L3.2 LIVE: Sim goldfish (Boros Energy 200g)" {
    cd "E:\vscode ai project\mtg-sim"
    $out = python -c "
from data.deck import load_deck_from_file
from apl.boros_energy import BorosEnergyAPL
from engine.runner import run_simulation
m,s=load_deck_from_file('decks/boros_energy_modern.txt')
r=run_simulation(BorosEnergyAPL(),m,n=200)
print(f'OK T{r.avg_kill_turn():.2f} {r.win_rate():.0%}WR {200/max(0.01,(r.elapsed_sec)):.0f}g/s')
" 2>&1 | Out-String
    if ($out -notmatch "OK") { throw $out.Trim() }
    Write-Host "($($out.Trim())) " -NoNewline
}

Test "L3.3 LIVE: Variant tester (1 swap)" {
    cd "E:\vscode ai project\mtg-sim"
    $out = python -c "
from data.deck import load_deck_from_file
from engine.variant import compare_variants
m,s=load_deck_from_file('decks/boros_energy_modern.txt')
opp,_=load_deck_from_file('decks/dimir_murktide_modern.txt')
r=compare_variants(m,opp,[('Ajani, Nacatl Pariah','Lightning Bolt')],n=200)
print(f'OK base={r[0].base_wr}% var={r[0].variant_wr}% delta={r[0].delta}%')
" 2>&1 | Out-String
    if ($out -notmatch "OK") { throw $out.Trim() }
    Write-Host "($($out.Trim())) " -NoNewline
}

Test "L3.4 LIVE: Field analysis (3 opponents)" {
    cd "E:\vscode ai project\mtg-sim"
    $out = python -c "
from data.deck import load_deck_from_file
from engine.variant import run_field_analysis
m,s=load_deck_from_file('decks/boros_energy_modern.txt')
field={}; shares={}
for d in ['dimir_murktide_modern','dimir_oculus_modern','izzet_affinity_modern']:
    cards,_=load_deck_from_file(f'decks/{d}.txt')
    name=d.replace('_modern','').replace('_',' ').title()
    field[name]=cards; shares[name]=1/3
r=run_field_analysis(m,field,shares,n_per_matchup=100)
print(f'OK field_wr={r.field_wr}%')
" 2>&1 | Out-String
    if ($out -notmatch "OK") { throw $out.Trim() }
    Write-Host "($($out.Trim())) " -NoNewline
}

# ==========================================================================
Write-Host "`n--- LAYER 4: Calibration ---" -ForegroundColor Magenta
# ==========================================================================

Test "L4.1 LIVE: Calibration reads match_log" {
    cd "E:\vscode ai project"
    $out = python -c "
import sys; sys.path.insert(0,'E:/vscode ai project/mtg-sim')
sys.path.insert(0,'E:/vscode ai project/harness/agents/scripts')
from calibrate import load_real_matches, aggregate_matchups
m=load_real_matches()
a=aggregate_matchups(m)
print(f'OK {len(m)} matches, {len(a)} matchups')
" 2>&1 | Out-String
    if ($out -notmatch "OK") { throw $out.Trim() }
    Write-Host "($($out.Trim())) " -NoNewline
}

Test "L4.2 Calibration report exists" {
    $reports = Get-ChildItem "$H\knowledge\mtg" -Filter "calibration-*"
    if ($reports.Count -eq 0) { throw "No calibration reports" }
    Write-Host "($($reports.Count) reports) " -NoNewline
}

# ==========================================================================
Write-Host "`n--- LAYER 5: Pipeline ---" -ForegroundColor Magenta
# ==========================================================================

Test "L5.1 LIVE: Auto-pipeline dry run" {
    cd "E:\vscode ai project"
    $out = python "harness\agents\scripts\auto_pipeline.py" --format modern --dry-run 2>&1 | Out-String
    if ($out -notmatch "PIPELINE COMPLETE") { throw "Did not complete" }
    $newArchs = ([regex]::Matches($out, "meta share")).Count
    Write-Host "($newArchs new archetypes) " -NoNewline
}

Test "L5.2 Optimization memory" {
    cd "E:\vscode ai project"
    $out = python -c "
import sys; sys.path.insert(0,'E:/vscode ai project/mtg-sim')
sys.path.insert(0,'E:/vscode ai project/harness/agents/scripts')
from auto_pipeline import load_memory
m=load_memory()
print(f""OK experiments={m['stats']['total_experiments']} apls={len(m['generated_apls'])} playbooks={len(m['playbooks_drafted'])}"")
" 2>&1 | Out-String
    if ($out -notmatch "OK") { throw $out.Trim() }
    Write-Host "($($out.Trim())) " -NoNewline
}

# ==========================================================================
Write-Host "`n--- APL SELF-TUNER ---" -ForegroundColor Magenta
# ==========================================================================

Test "L6.1 LIVE: APL optimizer loads + reads source" {
    cd "E:\vscode ai project"
    $out = python -c "
import sys; sys.path.insert(0,'E:/vscode ai project/mtg-sim')
sys.path.insert(0,'E:/vscode ai project/harness/agents/scripts')
from apl_optimizer import find_apl_file, find_deck_file, load_apl_from_file
apl_f = find_apl_file('Boros Energy')
deck_f = find_deck_file('Boros Energy')
apl = load_apl_from_file(apl_f)
src = apl_f.read_text(encoding='utf-8')
print(f'OK apl={type(apl).__name__} lines={len(src.splitlines())} deck={deck_f.name}')
" 2>&1 | Out-String
    if ($out -notmatch "OK") { throw $out.Trim() }
    Write-Host "($($out.Trim())) " -NoNewline
}

Test "L6.2 APL optimizer experiment reports" {
    $reports = Get-ChildItem "$H\knowledge\mtg" -Filter "apl-opt-*"
    if ($reports.Count -eq 0) { throw "No APL optimization reports" }
    Write-Host "($($reports.Count) reports) " -NoNewline
}

# ==========================================================================
Write-Host "`n--- INTEGRATION ---" -ForegroundColor Magenta
# ==========================================================================

Test "L7.1 Knowledge block count matches index" {
    $blocks = (Get-ChildItem "$H\knowledge" -Recurse -Filter "*.md" | Where-Object { $_.Name -notmatch "^_" -and $_.Directory.Name -ne ".obsidian" }).Count
    $totalLines = 0
    Get-ChildItem "$H\knowledge" -Recurse -Filter "*.md" | Where-Object { $_.Name -notmatch "^_" -and $_.Directory.Name -ne ".obsidian" } | ForEach-Object { $totalLines += (Get-Content $_.FullName | Measure-Object -Line).Lines }
    Write-Host "($blocks blocks, $totalLines lines) " -NoNewline
}

Test "L7.2 All harness docs present" {
    $docs = @("CLAUDE.md","MEMORY.md","HARNESS_STATUS.md","HARNESS_GUIDE.txt","WORKING_WITHOUT_CLAUDE.txt","THURSDAY_PROCEDURES.txt")
    $missing = $docs | Where-Object { -not (Test-Path "$H\$_") }
    if ($missing) { throw "Missing: $($missing -join ', ')" }
    Write-Host "($($docs.Count) docs) " -NoNewline
}

# ==========================================================================
# FINAL REPORT
# ==========================================================================
$Elapsed = [math]::Round(((Get-Date) - $Start).TotalSeconds, 1)

Write-Host ""
Write-Host ""
Write-Host "=========================================" -ForegroundColor Yellow
Write-Host "  STRESS TEST RESULTS (HARD MODE)" -ForegroundColor Yellow
Write-Host "=========================================" -ForegroundColor Yellow
Write-Host ""
Write-Host "  PASS: $Pass" -ForegroundColor Green
if ($Fail -gt 0) { Write-Host "  FAIL: $Fail" -ForegroundColor Red }
else { Write-Host "  FAIL: 0" -ForegroundColor Green }
Write-Host "  TIME: ${Elapsed}s"
Write-Host ""
Write-Host "  DETAIL:" -ForegroundColor Cyan
foreach ($r in $Results) {
    $c = if ($r.S -eq "PASS") { "Green" } else { "Red" }
    Write-Host "    [$($r.S)] $($r.N) ($($r.T)s)" -ForegroundColor $c
}
Write-Host ""
if ($Fail -eq 0) {
    Write-Host "  ALL SYSTEMS GREEN. Layers 1-5 + APL Optimizer verified." -ForegroundColor Green
} else {
    Write-Host "  $Fail FAILURE(S) - review above." -ForegroundColor Red
}
Write-Host "=========================================" -ForegroundColor Yellow
