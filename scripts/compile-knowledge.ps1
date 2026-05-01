# compile-knowledge.ps1
# Feeds raw source material to Gemma 4 via Ollama API
# Outputs a formatted knowledge block to harness/knowledge/
#
# USAGE:
#   .\compile-knowledge.ps1 -SourceFile "path\to\raw.txt" -Domain "mtg" -BlockName "new-deck"
#   .\compile-knowledge.ps1 -SourceText "paste raw text here" -Domain "tech" -BlockName "new-tool"
#   Get-Content raw.txt | .\compile-knowledge.ps1 -Domain "career" -BlockName "new-cert"
#
# REQUIRES: Ollama running with gemma4 model loaded

param(
    [string]$SourceFile,
    [string]$SourceText,
    [Parameter(Mandatory=$true)]
    [ValidateSet("mtg","career","tech","personal")]
    [string]$Domain,
    [Parameter(Mandatory=$true)]
    [string]$BlockName,
    [string]$Model = "gemma4",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$HarnessRoot = "E:\vscode ai project\harness"
$OllamaAPI = "http://localhost:11434/api/generate"
$Today = Get-Date -Format "yyyy-MM-dd"

# --- Resolve source input ---
if ($SourceFile) {
    if (-not (Test-Path $SourceFile)) {
        Write-Error "Source file not found: $SourceFile"
        exit 1
    }
    $RawContent = Get-Content $SourceFile -Raw
    $SourceLabel = "file: $SourceFile"
} elseif ($SourceText) {
    $RawContent = $SourceText
    $SourceLabel = "direct-input"
} elseif ($input) {
    $RawContent = $input | Out-String
    $SourceLabel = "piped-input"
} else {
    Write-Error "Provide -SourceFile, -SourceText, or pipe content"
    exit 1
}

if ([string]::IsNullOrWhiteSpace($RawContent)) {
    Write-Error "Source content is empty"
    exit 1
}

Write-Host "[compile] Source: $SourceLabel ($($RawContent.Length) chars)" -ForegroundColor Cyan
Write-Host "[compile] Target: knowledge/$Domain/$BlockName.md" -ForegroundColor Cyan
Write-Host "[compile] Model: $Model" -ForegroundColor Cyan

# --- Build the prompt ---
$SystemPrompt = @"
You are a knowledge compiler. Your job is to read raw source material and produce a structured knowledge block in markdown format.

OUTPUT FORMAT (follow exactly):
---
title: "[descriptive title]"
domain: "$Domain"
last_updated: "$Today"
confidence: "medium"
sources: ["$SourceLabel"]
---

## Summary
One paragraph overview of what this block covers.

## Content
Main knowledge organized with headers. Use [[wikilinks]] to reference related topics.
Mark anything you inferred (not directly stated) with [INFERRED].
Mark conflicting information with [CONFLICT].

## Changelog
- $Today`: Created -- source: $SourceLabel

RULES:
- Extract facts, do not editorialize
- Preserve specific numbers, names, dates, versions
- If the source mentions people, include their roles
- If the source mentions tools/tech, include versions
- Keep it concise but complete
- Output ONLY the markdown block, no preamble or explanation
"@

$UserPrompt = @"
Compile this raw source material into a knowledge block:

---BEGIN SOURCE---
$RawContent
---END SOURCE---
"@

# --- Call Ollama API ---
if ($DryRun) {
    Write-Host "[compile] DRY RUN - would send $($RawContent.Length) chars to $Model" -ForegroundColor Yellow
    Write-Host "[compile] System prompt: $($SystemPrompt.Length) chars" -ForegroundColor Yellow
    exit 0
}

Write-Host "[compile] Sending to $Model via Ollama... (this may take 1-5 min)" -ForegroundColor Yellow

$Body = @{
    model  = $Model
    prompt = $UserPrompt
    system = $SystemPrompt
    stream = $false
    options = @{
        temperature = 0.3
        num_predict = 4096
    }
} | ConvertTo-Json -Depth 3

try {
    $Response = Invoke-RestMethod -Uri $OllamaAPI -Method POST -Body $Body -ContentType "application/json" -TimeoutSec 600
} catch {
    Write-Error "Ollama API call failed. Is Ollama running? Error: $_"
    exit 1
}

$CompiledBlock = $Response.response

if ([string]::IsNullOrWhiteSpace($CompiledBlock)) {
    Write-Error "Model returned empty response"
    exit 1
}

# --- Write the knowledge block ---
$OutputDir = Join-Path $HarnessRoot "knowledge\$Domain"
if (-not (Test-Path $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
}

$OutputFile = Join-Path $OutputDir "$BlockName.md"
$CompiledBlock | Set-Content -Path $OutputFile -Encoding UTF8

Write-Host "[compile] Written: $OutputFile" -ForegroundColor Green
Write-Host "[compile] Size: $((Get-Item $OutputFile).Length) bytes" -ForegroundColor Green

# --- Update _index.md ---
$IndexFile = Join-Path $HarnessRoot "knowledge\_index.md"
$IndexEntry = "| $Domain/$BlockName | $Domain | $Today | $SourceLabel |"
$IndexContent = Get-Content $IndexFile -Raw

if ($IndexContent -notmatch [regex]::Escape("$Domain/$BlockName")) {
    Add-Content -Path $IndexFile -Value $IndexEntry
    Write-Host "[compile] Added to _index.md" -ForegroundColor Green
} else {
    Write-Host "[compile] Block already in _index.md (skipped)" -ForegroundColor Yellow
}

# --- Summary ---
$Duration = $Response.total_duration / 1000000000  # nanoseconds to seconds
$TokenCount = $Response.eval_count
$TokenRate = if ($Duration -gt 0) { [math]::Round($TokenCount / $Duration, 1) } else { 0 }

Write-Host ""
Write-Host "=== COMPILATION COMPLETE ===" -ForegroundColor Green
Write-Host "  Block:    knowledge/$Domain/$BlockName.md"
Write-Host "  Tokens:   $TokenCount generated"
Write-Host "  Speed:    $TokenRate tokens/sec"
Write-Host "  Time:     $([math]::Round($Duration, 1)) seconds"
Write-Host "  Cost:     `$0.00 (local model)"
Write-Host ""
Write-Host "Next: Open in Obsidian or ask Claude Code about it." -ForegroundColor Cyan
